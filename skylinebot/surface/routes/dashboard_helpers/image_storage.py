from __future__ import annotations

import asyncio
import datetime
import hashlib
import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from PIL import Image

import storage.dashboard_image_assets as dashboard_image_assets_db
import storage.dashboard_image_original_meta as dashboard_image_original_meta_db
import storage.dashboard_image_usage_refs as dashboard_image_usage_refs_db
from skylinebot.bridge import storage as bridge_storage
from skylinebot.config.config import BotConfigClass

_BOT_CONFIG = BotConfigClass()
_GRIDFS_BUCKET_NAME = "dashboard_image_blob"
_ASSET_ROUTE_PREFIX = "/dashboard/assets/db"
_ASSET_KEY_URL_RE = re.compile(r"/dashboard/assets/db/([a-z0-9]{24,64})(?:/|$)", flags=re.IGNORECASE)
_AUTO_ORPHAN_CLEANUP_LOCK = asyncio.Lock()
_AUTO_ORPHAN_CLEANUP_NEXT_AT_MONOTONIC = 0.0
_DEFAULT_REFERENCE_COLLECTIONS: tuple[str, ...] = (
    "dashboard_config",
    "guilds",
    "welcomer_settings",
    "donate_settings",
    "promote_channels",
    "ticket_settings",
    "shop",
    "bot_payment_sessions",
    "image_ocr_settings",
    "shop_settings",
    "shop_products",
)


def dashboard_gridfs_bucket_name() -> str:
    return _GRIDFS_BUCKET_NAME


def _safe_asset_key(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower()
    if not value:
        return ""
    if not re.fullmatch(r"[a-z0-9]{24,64}", value):
        return ""
    return value


def _safe_filename(raw_value: Any, *, fallback: str = "asset.webp") -> str:
    name = Path(str(raw_value or "")).name.strip()
    if not name:
        return fallback
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    if not name:
        return fallback
    if len(name) > 120:
        name = name[-120:]
    return name


def _configured_dashboard_origin() -> str:
    raw = str(getattr(_BOT_CONFIG, "DASHBOARD_BASE_URL", "") or "").strip()
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"https://{raw}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return ""
    scheme = str(parsed.scheme or "").strip().lower()
    netloc = str(parsed.netloc or "").strip()
    if scheme not in {"http", "https"} or not netloc:
        return ""
    return f"{scheme}://{netloc}".rstrip("/")


def _origin_from_request(request: Any) -> str:
    if request is None:
        return ""
    raw_host = (
        str(getattr(request, "headers", {}).get("x-forwarded-host") or "").split(",")[0].strip()
        or str(getattr(request, "headers", {}).get("host") or "").strip()
    )
    if not raw_host:
        return ""
    forwarded_proto = str(getattr(request, "headers", {}).get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    request_scheme = str(getattr(getattr(request, "url", None), "scheme", "") or "").strip().lower()
    scheme = forwarded_proto if forwarded_proto in {"http", "https"} else request_scheme
    if scheme not in {"http", "https"}:
        scheme = "http"
    return f"{scheme}://{raw_host}".rstrip("/")


def build_dashboard_asset_url(asset_key: str, *, filename: str = "", request: Any = None) -> str:
    safe_key = _safe_asset_key(asset_key)
    if not safe_key:
        return ""
    safe_name = _safe_filename(filename) if filename else ""
    path = f"{_ASSET_ROUTE_PREFIX}/{safe_key}"
    if safe_name:
        path = f"{path}/{safe_name}"
    base = _origin_from_request(request) or _configured_dashboard_origin()
    if base:
        return f"{base}{path}"
    return path


def extract_dashboard_asset_keys_from_text(raw_value: Any) -> set[str]:
    text = str(raw_value or "").strip()
    if not text:
        return set()
    found: set[str] = set()
    for match in _ASSET_KEY_URL_RE.finditer(text):
        key = _safe_asset_key(match.group(1))
        if key:
            found.add(key)
    return found


def collect_dashboard_asset_keys_from_payload(raw_payload: Any) -> set[str]:
    found: set[str] = set()
    if raw_payload is None:
        return found
    if isinstance(raw_payload, dict):
        for value in raw_payload.values():
            found.update(collect_dashboard_asset_keys_from_payload(value))
        return found
    if isinstance(raw_payload, (list, tuple, set)):
        for value in raw_payload:
            found.update(collect_dashboard_asset_keys_from_payload(value))
        return found
    return extract_dashboard_asset_keys_from_text(raw_payload)


async def collect_referenced_dashboard_asset_keys(
    *,
    collection_names: list[str] | None = None,
) -> set[str]:
    keys: set[str] = set()
    database = await bridge_storage.get_database()
    if collection_names is None:
        names = list(_DEFAULT_REFERENCE_COLLECTIONS)
    else:
        names = [str(name or "").strip() for name in collection_names if str(name or "").strip()]

    for collection_name in names:
        try:
            collection = database[collection_name]
            cursor = collection.find({}, {"_id": 0})
            async for row in cursor:
                if isinstance(row, dict):
                    keys.update(collect_dashboard_asset_keys_from_payload(row))
        except Exception:
            continue
    return keys


def _image_dimensions(payload: bytes) -> tuple[int, int]:
    if not payload:
        return 0, 0
    try:
        from io import BytesIO

        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
            return int(width or 0), int(height or 0)
    except Exception:
        return 0, 0


def _guess_mime_type(*, filename: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(str(filename or ""))
    mime = str(guessed or fallback).strip().lower()
    return mime or fallback


async def _get_gridfs_database() -> Any:
    # Multi-cluster mode can return a proxy object; GridFS requires a real MotorDatabase.
    database = await bridge_storage.get_database()
    db_name = str(getattr(database, "name", "") or "").strip()
    client = getattr(database, "client", None)
    if client is not None and db_name:
        try:
            return client[db_name]
        except Exception:
            return database
    return database


async def _gridfs_upload_payload(
    *,
    bucket_name: str,
    file_id: str,
    filename: str,
    payload: bytes,
    metadata: dict[str, Any] | None = None,
) -> bool:
    database = await _get_gridfs_database()
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=bucket_name)
    try:
        await bucket.upload_from_stream_with_id(
            file_id,
            filename,
            payload,
            metadata=dict(metadata or {}),
        )
        return True
    except Exception:
        return False


async def _gridfs_delete_payload(*, bucket_name: str, file_id: str) -> None:
    database = await _get_gridfs_database()
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=bucket_name)
    try:
        await bucket.delete(file_id)
    except Exception:
        return


async def read_dashboard_asset_blob(asset_key: str) -> tuple[dict[str, Any] | None, bytes]:
    safe_key = _safe_asset_key(asset_key)
    if not safe_key:
        return None, b""
    asset = await dashboard_image_assets_db.get(asset_key=safe_key, is_active=True)
    if not asset:
        return None, b""
    bucket_name = str(asset.get("gridfs_bucket") or _GRIDFS_BUCKET_NAME).strip() or _GRIDFS_BUCKET_NAME
    file_id = str(asset.get("gridfs_file_id") or "").strip()
    if not file_id:
        return None, b""
    database = await _get_gridfs_database()
    bucket = AsyncIOMotorGridFSBucket(database, bucket_name=bucket_name)
    try:
        grid_out = await bucket.open_download_stream(file_id)
        payload = await grid_out.read()
    except Exception:
        return None, b""
    return asset, bytes(payload or b"")


async def store_dashboard_image_asset(
    *,
    guild_id: int,
    raw_bytes: bytes,
    optimized_bytes: bytes,
    original_filename: str,
    stored_filename: str,
    upload_target: str,
    asset_kind: str,
    uploader_id: int = 0,
    source_route: str = "",
    source_field: str = "",
    request: Any = None,
) -> dict[str, Any] | None:
    if not raw_bytes or not optimized_bytes:
        return None

    safe_original_name = _safe_filename(original_filename, fallback="upload.bin")
    safe_stored_name = _safe_filename(stored_filename, fallback="asset.webp")
    asset_key = uuid.uuid4().hex
    gridfs_file_id = uuid.uuid4().hex
    bucket_name = dashboard_gridfs_bucket_name()
    optimized_mime = _guess_mime_type(filename=safe_stored_name, fallback="application/octet-stream")
    original_mime = _guess_mime_type(filename=safe_original_name, fallback="application/octet-stream")

    metadata = {
        "asset_key": asset_key,
        "guild_id": int(guild_id or 0),
        "upload_target": str(upload_target or "")[:64],
        "asset_kind": str(asset_kind or "")[:32],
        "mime_type": optimized_mime,
        "filename": safe_stored_name,
    }
    uploaded = await _gridfs_upload_payload(
        bucket_name=bucket_name,
        file_id=gridfs_file_id,
        filename=safe_stored_name,
        payload=optimized_bytes,
        metadata=metadata,
    )
    if not uploaded:
        return None

    optimized_width, optimized_height = _image_dimensions(optimized_bytes)
    original_width, original_height = _image_dimensions(raw_bytes)
    sha256 = hashlib.sha256(optimized_bytes).hexdigest()

    asset_doc = await dashboard_image_assets_db.insert(
        asset_key=asset_key,
        guild_id=int(guild_id or 0),
        upload_target=str(upload_target or "").strip()[:64],
        asset_kind=str(asset_kind or "").strip()[:32],
        original_filename=safe_original_name,
        stored_filename=safe_stored_name,
        storage_backend="gridfs",
        gridfs_bucket=bucket_name,
        gridfs_file_id=gridfs_file_id,
        mime_type=optimized_mime[:120],
        sha256=sha256,
        width=int(optimized_width),
        height=int(optimized_height),
        original_size=int(len(raw_bytes)),
        optimized_size=int(len(optimized_bytes)),
        uploader_id=int(uploader_id or 0),
        is_active=True,
    )
    if not asset_doc or not asset_doc.get("id"):
        await _gridfs_delete_payload(bucket_name=bucket_name, file_id=gridfs_file_id)
        return None

    asset_id = int(asset_doc.get("id") or 0)
    await dashboard_image_original_meta_db.insert(
        asset_id=asset_id,
        guild_id=int(guild_id or 0),
        original_filename=safe_original_name,
        original_mime_type=original_mime[:120],
        original_size=int(len(raw_bytes)),
        original_width=int(original_width),
        original_height=int(original_height),
        optimized_size=int(len(optimized_bytes)),
        optimized_width=int(optimized_width),
        optimized_height=int(optimized_height),
    )
    await dashboard_image_usage_refs_db.insert(
        asset_id=asset_id,
        guild_id=int(guild_id or 0),
        upload_target=str(upload_target or "").strip()[:64],
        asset_kind=str(asset_kind or "").strip()[:32],
        source_route=str(source_route or "").strip()[:120],
        source_field=str(source_field or "").strip()[:120],
        is_active=True,
    )
    public_url = build_dashboard_asset_url(
        asset_key,
        filename=safe_stored_name,
        request=request,
    )
    return {
        "asset_id": asset_id,
        "asset_key": asset_key,
        "url": public_url,
        "mime_type": optimized_mime,
        "original_size": int(len(raw_bytes)),
        "optimized_size": int(len(optimized_bytes)),
        "original_width": int(original_width),
        "original_height": int(original_height),
        "optimized_width": int(optimized_width),
        "optimized_height": int(optimized_height),
    }


async def cleanup_orphan_dashboard_assets(
    *,
    guild_id: int = 0,
    dry_run: bool = False,
    limit: int = 250,
    min_age_seconds: int = 1800,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit or 250), 5000))
    safe_guild_id = int(guild_id or 0)
    safe_min_age_seconds = max(0, min(int(min_age_seconds or 0), 60 * 60 * 24 * 365))

    referenced_keys = await collect_referenced_dashboard_asset_keys()
    where: dict[str, Any] = {"is_active": True}
    if safe_guild_id > 0:
        where["guild_id"] = safe_guild_id
    if referenced_keys:
        where["asset_key"] = {"$nin": list(referenced_keys)}
    if safe_min_age_seconds > 0:
        cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(seconds=safe_min_age_seconds)
        where["created_at"] = {"$lte": cutoff}

    assets_collection = await bridge_storage.get_collection(dashboard_image_assets_db.COLLECTION_NAME)
    cursor = assets_collection.find(where, {"_id": 0}).sort("id", 1).limit(safe_limit)
    scanned = 0
    orphan_rows: list[dict[str, Any]] = []
    for row in await cursor.to_list(length=safe_limit):
        if not isinstance(row, dict):
            continue
        asset_key = _safe_asset_key(row.get("asset_key"))
        if not asset_key:
            continue
        if referenced_keys and asset_key in referenced_keys:
            continue
        scanned += 1
        orphan_rows.append(dict(row))
    candidate_blob_bytes = sum(int(row.get("optimized_size") or 0) for row in orphan_rows)

    deleted_assets = 0
    deleted_blob_bytes = 0
    deleted_meta_rows = 0
    deleted_usage_rows = 0
    errors: list[str] = []

    if not dry_run:
        for row in orphan_rows:
            asset_id = int(row.get("id") or 0)
            gridfs_bucket = str(row.get("gridfs_bucket") or _GRIDFS_BUCKET_NAME).strip() or _GRIDFS_BUCKET_NAME
            gridfs_file_id = str(row.get("gridfs_file_id") or "").strip()
            optimized_size = int(row.get("optimized_size") or 0)
            try:
                if gridfs_file_id:
                    await _gridfs_delete_payload(bucket_name=gridfs_bucket, file_id=gridfs_file_id)
            except Exception as error:
                errors.append(f"gridfs_delete_failed:{asset_id}:{type(error).__name__}")
            try:
                if asset_id > 0:
                    meta_deleted = await dashboard_image_original_meta_db.delete(asset_id=asset_id)
                    usage_deleted = await dashboard_image_usage_refs_db.delete(asset_id=asset_id)
                    asset_deleted = await dashboard_image_assets_db.delete(id=asset_id)
                    deleted_meta_rows += len(list(meta_deleted or []))
                    deleted_usage_rows += len(list(usage_deleted or []))
                    if asset_deleted:
                        deleted_assets += 1
                        deleted_blob_bytes += max(0, optimized_size)
            except Exception as error:
                errors.append(f"doc_delete_failed:{asset_id}:{type(error).__name__}")

    sample_orphans: list[dict[str, Any]] = []
    for row in orphan_rows[:30]:
        sample_orphans.append(
            {
                "id": int(row.get("id") or 0),
                "guild_id": int(row.get("guild_id") or 0),
                "asset_key": str(row.get("asset_key") or ""),
                "upload_target": str(row.get("upload_target") or ""),
                "asset_kind": str(row.get("asset_kind") or ""),
                "optimized_size": int(row.get("optimized_size") or 0),
                "stored_filename": str(row.get("stored_filename") or ""),
            }
        )

    return {
        "ok": True,
        "dry_run": bool(dry_run),
        "scanned": int(scanned),
        "orphan_count": int(len(orphan_rows)),
        "deleted_assets": int(deleted_assets),
        "deleted_blob_bytes": int(deleted_blob_bytes),
        "candidate_blob_bytes": int(candidate_blob_bytes),
        "deleted_meta_rows": int(deleted_meta_rows),
        "deleted_usage_rows": int(deleted_usage_rows),
        "errors": list(errors[:100]),
        "sample_orphans": sample_orphans,
        "referenced_key_count": int(len(referenced_keys)),
    }


async def maybe_run_auto_orphan_cleanup(
    *,
    min_interval_seconds: int = 60 * 20,
    limit: int = 80,
    min_age_seconds: int = 60 * 30,
) -> dict[str, Any]:
    global _AUTO_ORPHAN_CLEANUP_NEXT_AT_MONOTONIC
    now = time.monotonic()
    if now < float(_AUTO_ORPHAN_CLEANUP_NEXT_AT_MONOTONIC):
        return {"ok": True, "skipped": "cooldown"}
    if _AUTO_ORPHAN_CLEANUP_LOCK.locked():
        return {"ok": True, "skipped": "running"}
    async with _AUTO_ORPHAN_CLEANUP_LOCK:
        now = time.monotonic()
        if now < float(_AUTO_ORPHAN_CLEANUP_NEXT_AT_MONOTONIC):
            return {"ok": True, "skipped": "cooldown"}
        _AUTO_ORPHAN_CLEANUP_NEXT_AT_MONOTONIC = now + max(120, int(min_interval_seconds or 1200))
        try:
            result = await cleanup_orphan_dashboard_assets(
                dry_run=False,
                limit=max(20, min(int(limit or 80), 3000)),
                min_age_seconds=max(0, int(min_age_seconds or 1800)),
            )
            result["auto"] = True
            return result
        except Exception as error:
            return {"ok": False, "auto": True, "error": f"{type(error).__name__}: {error}"}
