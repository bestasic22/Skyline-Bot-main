from __future__ import annotations

import asyncio
import calendar
import html as py_html
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from ..dashboard_core import (
    Any,
    BOT_CONFIG,
    DASHBOARD_TAB_REQUIRED_PLAN_TIERS,
    DEVELOPER_SOCIAL_LINKS_CONFIG_KEY,
    HTMLResponse,
    JSONResponse,
    OWNERBOT_HIDEABLE_TABS,
    OWNERBOT_PAYMENT_PROVIDER_CONFIG_KEY,
    OWNERBOT_PAYMENT_PROVIDER_TYPES,
    OWNERBOT_RUNTIME_CONFIG_KEY,
    OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY,
    OWNERBOT_UPLOAD_TARGETS,
    OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS,
    PROMOTE_OWNER_POLICY_CONFIG_KEY,
    PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY,
    REDEEM_CODE_TYPES,
    RedirectResponse,
    Request,
    TRUSTED_ORDER_CONFIG_KEY,
    _bool_from_form,
    _ensure_dashboard_config_cache,
    _fetch_donatebot_verify_logs,
    _format_datetime_local,
    _format_datetime_th,
    _int_from_form,
    _invalidate_landing_plan_pricing_snapshot_cache,
    _is_dashboard_admin,
    _manageable_guilds,
    _default_ownerbot_upload_channel_settings,
    _normalize_ownerbot_payment_provider_settings,
    _normalize_promote_allowed_domains,
    _normalize_promote_allowed_urls,
    _normalize_promote_blocked_words,
    _normalize_ownerbot_upload_channel_settings,
    _normalize_ownerbot_runtime_settings,
    _normalize_subscription_code,
    _ownerbot_payment_provider_settings_from_db,
    _ownerbot_promote_policy_from_db,
    _ownerbot_promote_policy_from_raw,
    _promote_suspension_map_from_db,
    _promote_suspension_map_from_raw,
    _ownerbot_upload_channel_settings_from_db,
    _ownerbot_runtime_from_db,
    _parse_command_name_list,
    _parse_datetime_local,
    _parse_developer_social_links,
    _parse_form,
    _parse_guild_id_list,
    _parse_trusted_server_order,
    _render_donatebot_verify_logs_admin_page,
    _render_guild_picker,
    _render_layout,
    _render_login,
    _render_ownerbot_console_page,
    _render_ownerbot_settings_page,
    _render_trusted_servers_manager_page,
    _session_from_request,
    _session_user_id,
    _set_dashboard_config_value,
    _trusted_order_from_db,
    cache,
    change_guild_subscription,
    datetime,
    discord,
    generate_redeem_code,
    get_bot,
    get_discord_service_state,
    json,
    storage,
    urlencode,
)
from skylinebot.bridge import storage as bridge_storage
from skylinebot.style import urls as style_urls
from skylinebot.workflows import billing as billing_workflow
from skylinebot.workflows.redeem_control import (
    coerce_max_claims,
    is_valid_custom_redeem_code,
    lock_mode_from_flags,
    normalize_redeem_code,
    normalize_redeem_lock_mode,
)
from skylinebot.surface.routes.dashboard_helpers.image_storage import (
    build_dashboard_asset_url,
    cleanup_orphan_dashboard_assets,
    collect_referenced_dashboard_asset_keys,
)

_OWNERBOT_LIVE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

_OWNERBOT_MONGO_DEFAULT_PRUNE_LIMITS: dict[str, int] = {
    "donatebot_verify_logs": 5000,
    "snipe_data": 8000,
    "promote_history": 6000,
    "bot_billing_events": 6000,
    "bot_wallet_ledger": 12000,
}
_OWNERBOT_ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
_OWNERBOT_ROOT_PATH = Path(__file__).resolve().parents[4]
_OWNERBOT_MONGO_MIGRATION_SCRIPT_PATH = _OWNERBOT_ROOT_PATH / "tools" / "mongo_multi_migrate.py"
_OWNERBOT_MONGO_MIGRATION_HISTORY_COLLECTION = "ownerbot_mongo_migration_history"
_OWNERBOT_MONGO_MIGRATION_HISTORY_RETENTION_ENV_KEY = "MONGO_MIGRATION_HISTORY_RETENTION_DAYS"
_OWNERBOT_MONGO_URI_RE = re.compile(r"^mongodb(?:\+srv)?://", flags=re.IGNORECASE)
_OWNERBOT_REDEEM_RECENT_LIMIT = 120
_OWNERBOT_REDEEM_RECENT_SCAN_LIMIT = 480
_OWNERBOT_MONGO_DIAGNOSTIC_TIMEOUT_SECONDS = 6.0
_OWNERBOT_MONGO_DIAGNOSTIC_MAX_COLLECTIONS = 24
_OWNERBOT_MONGO_CACHE_TTL_SECONDS = 20.0
_OWNERBOT_MONGO_HISTORY_CACHE_TTL_SECONDS = 12.0
_OWNERBOT_SETTINGS_SECTION_DEFAULT = "runtime"
_OWNERBOT_SETTINGS_SECTIONS: tuple[str, ...] = (
    "runtime",
    "payment",
    "mongo",
    "redeem",
    "wallet",
    "guild",
    "promote",
)
_OWNERBOT_RUNTIME_SUBPAGE_DEFAULT = "overview"
_OWNERBOT_RUNTIME_SUBPAGES: tuple[str, ...] = (
    "overview",
    "ai",
    "vote",
    "dashboard",
    "commands",
    "social",
    "upload",
)
_OWNERBOT_MONGO_ROWS_CACHE: dict[str, Any] = {
    "payload": None,
    "expires_at": 0.0,
}
_OWNERBOT_MONGO_HISTORY_CACHE: dict[int, dict[str, Any]] = {}
_OWNERBOT_COMMAND_CHOICES_CACHE_TTL_SECONDS = 300.0
_OWNERBOT_COMMAND_CHOICES_CACHE: dict[str, Any] = {
    "rows": [],
    "expires_at": 0.0,
}
_OWNERBOT_WALLET_HISTORY_PER_USER_LIMIT = 48
_OWNERBOT_WALLET_HISTORY_FETCH_LIMIT = 12000


def _ownerbot_split_uri_text(raw_value: Any) -> list[str]:
    rows: list[str] = []
    for part in str(raw_value or "").replace("\r", "\n").replace(";", "\n").replace(",", "\n").split("\n"):
        text = str(part or "").strip()
        if not text or text in rows:
            continue
        rows.append(text)
    return rows


def _ownerbot_parse_collection_text(raw_value: Any) -> list[str]:
    rows: list[str] = []
    for part in str(raw_value or "").replace("\r", "\n").replace(";", "\n").replace(",", "\n").split("\n"):
        name = str(part or "").strip()
        if not name or name in rows:
            continue
        rows.append(name)
    return rows


def _ownerbot_normalize_settings_section(raw_value: Any, default: str = _OWNERBOT_SETTINGS_SECTION_DEFAULT) -> str:
    section = str(raw_value or "").strip().lower()
    if section in _OWNERBOT_SETTINGS_SECTIONS:
        return section
    return str(default or _OWNERBOT_SETTINGS_SECTION_DEFAULT)


def _ownerbot_normalize_runtime_subpage(
    raw_value: Any,
    default: str = _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT,
) -> str:
    subpage = str(raw_value or "").strip().lower()
    if subpage in _OWNERBOT_RUNTIME_SUBPAGES:
        return subpage
    return str(default or _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT)


def _ownerbot_settings_collect_flags(
    section: str,
    *,
    runtime_subpage: str = _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT,
) -> dict[str, bool]:
    resolved = _ownerbot_normalize_settings_section(section)
    resolved_runtime_subpage = _ownerbot_normalize_runtime_subpage(runtime_subpage)
    include_upload_rows = resolved == "runtime" and resolved_runtime_subpage == "upload"
    return {
        "include_command_choices": False,
        "include_upload_rows": include_upload_rows,
        "include_mongo_rows": resolved == "mongo",
        "include_wallet_rows": resolved == "wallet",
        "include_recent_redeem_rows": resolved == "redeem",
    }


def _render_ownerbot_settings_page_safe(**render_kwargs: Any) -> str:
    optional_kwargs = ("settings_active_runtime_page", "settings_active_section")
    attempt_kwargs = dict(render_kwargs)
    while True:
        try:
            return _render_ownerbot_settings_page(**attempt_kwargs)
        except TypeError as exc:
            message = str(exc)
            removed_any = False
            for key in optional_kwargs:
                if key in message and key in attempt_kwargs:
                    attempt_kwargs.pop(key, None)
                    removed_any = True
            if not removed_any:
                raise


def _ownerbot_parse_history_id_text(raw_value: Any, *, max_items: int = 1000) -> list[str]:
    rows: list[str] = []
    for part in re.split(r"[\r\n,;\s]+", str(raw_value or "").strip()):
        run_id = str(part or "").strip()
        if not run_id:
            continue
        if len(run_id) > 140:
            continue
        if run_id in rows:
            continue
        rows.append(run_id)
        if len(rows) >= max_items:
            break
    return rows


def _ownerbot_tail_text(raw_value: Any, *, max_lines: int = 40, max_chars: int = 4000) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return ""
    lines = [str(line or "").rstrip() for line in text.splitlines()]
    if len(lines) > int(max_lines):
        lines = lines[-int(max_lines):]
    compact = "\n".join(line for line in lines if line)
    if len(compact) > int(max_chars):
        compact = compact[-int(max_chars):]
    return compact


def _ownerbot_mongo_history_retention_days_from_env(default: int = 90) -> int:
    return _ownerbot_int_clamp(
        os.getenv(_OWNERBOT_MONGO_MIGRATION_HISTORY_RETENTION_ENV_KEY, str(default)),
        default=default,
        minimum=0,
        maximum=3650,
    )


def _ownerbot_invalidate_mongo_dashboard_cache() -> None:
    _OWNERBOT_MONGO_ROWS_CACHE["payload"] = None
    _OWNERBOT_MONGO_ROWS_CACHE["expires_at"] = 0.0
    _OWNERBOT_MONGO_HISTORY_CACHE.clear()


async def _ownerbot_safe_call(awaitable: Any, default: Any) -> Any:
    try:
        return await awaitable
    except Exception:
        return default


def _ownerbot_command_choices_from_cache(*, now_monotonic: float | None = None) -> list[str]:
    now_value = float(now_monotonic if now_monotonic is not None else time.monotonic())
    expires_at = float(_OWNERBOT_COMMAND_CHOICES_CACHE.get("expires_at") or 0.0)
    rows = _OWNERBOT_COMMAND_CHOICES_CACHE.get("rows")
    if now_value < expires_at and isinstance(rows, list):
        return [str(item or "").strip().lower() for item in rows if str(item or "").strip()]
    return []


def _ownerbot_collect_command_choices(bot: Any) -> list[str]:
    now_monotonic = time.monotonic()
    cached_rows = _ownerbot_command_choices_from_cache(now_monotonic=now_monotonic)
    if cached_rows:
        return cached_rows

    if not bot:
        return []

    try:
        prefix_names = sorted(
            {
                str(getattr(cmd, "qualified_name", "")).strip().lower()
                for cmd in bot.walk_commands()
                if str(getattr(cmd, "qualified_name", "")).strip()
            }
        )
        slash_names = sorted(
            {
                str(getattr(cmd, "qualified_name", "")).strip().lower()
                for cmd in bot.tree.walk_commands()
                if str(getattr(cmd, "qualified_name", "")).strip()
            }
        )
        rows = sorted(set(prefix_names + slash_names))
    except Exception:
        rows = []

    if rows:
        _OWNERBOT_COMMAND_CHOICES_CACHE["rows"] = rows
        _OWNERBOT_COMMAND_CHOICES_CACHE["expires_at"] = now_monotonic + _OWNERBOT_COMMAND_CHOICES_CACHE_TTL_SECONDS
        return rows

    # Return stale rows if fresh rebuild failed.
    stale_rows = _OWNERBOT_COMMAND_CHOICES_CACHE.get("rows")
    if isinstance(stale_rows, list):
        return [str(item or "").strip().lower() for item in stale_rows if str(item or "").strip()]
    return []


def _ownerbot_redeem_sort_key(item: dict[str, Any]) -> tuple[float, int]:
    created_at = item.get("created_at")
    created_epoch = 0.0
    if isinstance(created_at, datetime.datetime):
        normalized = created_at if created_at.tzinfo else created_at.replace(tzinfo=datetime.timezone.utc)
        try:
            created_epoch = float(normalized.timestamp())
        except Exception:
            created_epoch = 0.0
    try:
        item_id = int(item.get("id") or 0)
    except Exception:
        item_id = 0
    return (created_epoch, item_id)


async def _ownerbot_fetch_recent_redeem_rows(
    *,
    limit: int = _OWNERBOT_REDEEM_RECENT_LIMIT,
    scan_limit: int = _OWNERBOT_REDEEM_RECENT_SCAN_LIMIT,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(500, int(limit)))
    safe_scan_limit = max(safe_limit, min(5000, int(scan_limit)))
    projection = {
        "_id": 0,
        "id": 1,
        "code": 1,
        "code_type": 1,
        "code_value": 1,
        "valid_for_days": 1,
        "expires_at": 1,
        "claimed": 1,
        "claimed_by": 1,
        "claimed_at": 1,
        "claim_count": 1,
        "max_claims": 1,
        "lock_mode": 1,
        "lock_unique_user": 1,
        "lock_unique_guild": 1,
        "claim_history": {"$slice": -25},
        "created_at": 1,
    }
    try:
        collection = await bridge_storage.get_collection(storage.redeem_codes.COLLECTION_NAME)
        rows = await collection.find({}, projection).sort("id", -1).limit(safe_scan_limit).to_list(length=safe_scan_limit)
        payload = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
        payload.sort(key=_ownerbot_redeem_sort_key, reverse=True)
        return payload[:safe_limit]
    except Exception:
        fallback = await _ownerbot_safe_call(storage.redeem_codes.get_all(), [])
        payload = [dict(row) for row in list(fallback or []) if isinstance(row, dict)]
        payload.sort(key=_ownerbot_redeem_sort_key, reverse=True)
        return payload[:safe_limit]


async def _ownerbot_fetch_redeem_summary() -> dict[str, Any]:
    try:
        collection = await bridge_storage.get_collection(storage.redeem_codes.COLLECTION_NAME)
        total_count, claimed_count = await asyncio.gather(
            collection.count_documents({}),
            collection.count_documents({"claimed": True}),
        )
        total = int(total_count or 0)
        claimed = int(claimed_count or 0)
        return {
            "total_codes": total,
            "claimed_codes": claimed,
            "unclaimed_codes": max(0, total - claimed),
        }
    except Exception:
        return {
            "total_codes": 0,
            "claimed_codes": 0,
            "unclaimed_codes": 0,
        }


async def _ownerbot_fetch_wallet_summary() -> dict[str, Any]:
    try:
        collection = await bridge_storage.get_collection(storage.bot_wallet_accounts.COLLECTION_NAME)
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_users": {"$sum": 1},
                    "positive_users": {
                        "$sum": {
                            "$cond": [
                                {"$gt": [{"$ifNull": ["$balance", 0]}, 0]},
                                1,
                                0,
                            ]
                        }
                    },
                    "total_balance": {"$sum": {"$ifNull": ["$balance", 0]}},
                }
            }
        ]
        rows = await collection.aggregate(pipeline).to_list(length=1)
        row = dict(rows[0]) if rows and isinstance(rows[0], dict) else {}
        total_users = int(row.get("total_users") or 0)
        positive_users = int(row.get("positive_users") or 0)
        total_balance = 0.0
        try:
            total_balance = float(row.get("total_balance") or 0.0)
        except Exception:
            total_balance = 0.0
        return {
            "total_wallet_users": total_users,
            "wallet_positive_users": positive_users,
            "wallet_balance_total": round(total_balance, 2),
            "wallet_balance_total_text": f"{round(total_balance, 2):,.2f}",
        }
    except Exception:
        return {
            "total_wallet_users": 0,
            "wallet_positive_users": 0,
            "wallet_balance_total": 0.0,
            "wallet_balance_total_text": "0.00",
        }


def _ownerbot_wallet_ledger_sort_key(row: dict[str, Any]) -> tuple[int, float, int]:
    safe_row = row if isinstance(row, dict) else {}
    id_value = 0
    try:
        id_value = int(safe_row.get("id") or 0)
    except Exception:
        id_value = 0

    created_at = safe_row.get("created_at")
    parsed_dt: datetime.datetime | None = None
    if isinstance(created_at, datetime.datetime):
        parsed_dt = created_at if created_at.tzinfo else created_at.replace(tzinfo=datetime.timezone.utc)
    elif isinstance(created_at, (int, float)):
        try:
            timestamp = float(created_at)
            if timestamp > 10_000_000_000:
                timestamp /= 1000.0
            parsed_dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        except Exception:
            parsed_dt = None
    else:
        text = str(created_at or "").strip()
        if text:
            try:
                parsed_dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                parsed_dt = None

    if parsed_dt is None:
        return (0, 0.0, id_value)
    try:
        ts_value = float(parsed_dt.timestamp())
    except Exception:
        ts_value = 0.0
    return (1, ts_value, id_value)


async def _ownerbot_fetch_wallet_ledger_rows(*, limit: int = _OWNERBOT_WALLET_HISTORY_FETCH_LIMIT) -> list[dict[str, Any]]:
    safe_limit = max(200, min(12000, int(limit)))
    projection = {
        "_id": 0,
        "id": 1,
        "user_id": 1,
        "amount": 1,
        "balance_before": 1,
        "balance_after": 1,
        "kind": 1,
        "source_mode": 1,
        "session_key": 1,
        "note": 1,
        "meta": 1,
        "created_at": 1,
    }
    try:
        collection = await bridge_storage.get_collection(storage.bot_wallet_ledger.COLLECTION_NAME)
        rows = (
            await collection.find({}, projection)
            .sort([("created_at", -1), ("id", -1)])
            .limit(safe_limit)
            .to_list(length=safe_limit)
        )
        payload = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    except Exception:
        fallback_rows = await _ownerbot_safe_call(storage.bot_wallet_ledger.get_all(), [])
        payload = [dict(row) for row in list(fallback_rows or []) if isinstance(row, dict)]
    payload.sort(key=_ownerbot_wallet_ledger_sort_key, reverse=True)
    return payload[:safe_limit]


async def _ownerbot_apply_mongo_migration_history_retention(*, retention_days: int) -> dict[str, Any]:
    safe_days = max(0, min(3650, int(retention_days)))
    ttl_seconds = int(safe_days * 86400)
    candidate_uris = bridge_storage.mongo_candidate_uris()

    payload: dict[str, Any] = {
        "retention_days": safe_days,
        "ttl_seconds": ttl_seconds,
        "updated_clusters": 0,
        "failed_clusters": 0,
        "updated_hosts": [],
        "errors": [],
    }
    if not candidate_uris:
        payload["errors"] = ["No Mongo URI configured"]
        return payload

    for index_value, uri in enumerate(candidate_uris, start=1):
        host = str(bridge_storage.mongo_uri_host(uri) or f"cluster-{index_value}")
        client = None
        try:
            client = bridge_storage.mongo_build_client(uri)
            await client.admin.command("ping")
            database = client[bridge_storage.mongo_database_name()]
            collection = database[_OWNERBOT_MONGO_MIGRATION_HISTORY_COLLECTION]
            index_info = await collection.index_information()
            ttl_indexes_to_drop: list[str] = []
            for index_name, info in dict(index_info or {}).items():
                if not isinstance(info, dict):
                    continue
                key_rows = list(info.get("key") or [])
                if key_rows != [("created_at", 1)]:
                    continue
                if "expireAfterSeconds" in info:
                    ttl_indexes_to_drop.append(str(index_name))

            for index_name in ttl_indexes_to_drop:
                try:
                    await collection.drop_index(index_name)
                except Exception:
                    pass

            if safe_days > 0:
                await collection.create_index(
                    [("created_at", 1)],
                    name="ownerbot_migration_history_ttl",
                    expireAfterSeconds=ttl_seconds,
                    background=True,
                )

            payload["updated_clusters"] = int(payload["updated_clusters"]) + 1
            if isinstance(payload.get("updated_hosts"), list):
                payload["updated_hosts"].append(host)
        except Exception as error:
            payload["failed_clusters"] = int(payload["failed_clusters"]) + 1
            if isinstance(payload.get("errors"), list):
                payload["errors"].append(f"{host}: {type(error).__name__}: {error}")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    return payload


async def _ownerbot_load_mongo_migration_history_rows(*, limit: int = 40) -> list[dict[str, Any]]:
    safe_limit = max(1, min(200, int(limit)))
    now_monotonic = time.monotonic()
    cached = _OWNERBOT_MONGO_HISTORY_CACHE.get(safe_limit)
    if cached and float(cached.get("expires_at") or 0.0) > now_monotonic:
        cached_rows = cached.get("rows") or []
        return [dict(row) for row in cached_rows if isinstance(row, dict)]
    try:
        database = await bridge_storage.get_database()
        collection = database[_OWNERBOT_MONGO_MIGRATION_HISTORY_COLLECTION]
        rows = await collection.find({}).sort("created_at", -1).limit(safe_limit).to_list(length=safe_limit)
    except Exception:
        if cached:
            cached_rows = cached.get("rows") or []
            return [dict(row) for row in cached_rows if isinstance(row, dict)]
        return []
    payload: list[dict[str, Any]] = []
    for row in list(rows or []):
        if isinstance(row, dict):
            payload.append(dict(row))
    _OWNERBOT_MONGO_HISTORY_CACHE[safe_limit] = {
        "rows": [dict(row) for row in payload],
        "expires_at": time.monotonic() + _OWNERBOT_MONGO_HISTORY_CACHE_TTL_SECONDS,
    }
    return payload


async def _ownerbot_save_mongo_migration_history(payload: dict[str, Any]) -> dict[str, Any]:
    document = dict(payload or {})
    run_id = str(document.get("run_id") or document.get("_id") or uuid.uuid4().hex).strip() or uuid.uuid4().hex
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    created_at = document.get("created_at")
    if not isinstance(created_at, datetime.datetime):
        created_at = now_utc
    try:
        created_epoch = int(created_at.timestamp())
    except Exception:
        created_epoch = int(now_utc.timestamp())
    document["_id"] = run_id
    document["run_id"] = run_id
    document["created_at"] = created_at
    document["created_at_epoch"] = created_epoch
    retention_days = _ownerbot_mongo_history_retention_days_from_env(default=90)
    retention_seconds = int(max(0, retention_days) * 86400)

    candidate_uris = bridge_storage.mongo_candidate_uris()
    if not candidate_uris:
        return {
            "run_id": run_id,
            "saved_clusters": 0,
            "failed_clusters": 0,
            "saved_hosts": [],
            "errors": ["No Mongo URI configured"],
        }

    saved_hosts: list[str] = []
    error_rows: list[str] = []
    for index_value, uri in enumerate(candidate_uris, start=1):
        client = None
        host = str(bridge_storage.mongo_uri_host(uri) or f"cluster-{index_value}")
        try:
            client = bridge_storage.mongo_build_client(uri)
            await client.admin.command("ping")
            database = client[bridge_storage.mongo_database_name()]
            collection = database[_OWNERBOT_MONGO_MIGRATION_HISTORY_COLLECTION]
            await collection.replace_one({"_id": run_id}, document, upsert=True)
            try:
                await collection.create_index([("created_at", -1)])
            except Exception:
                pass
            if retention_seconds > 0:
                try:
                    await collection.create_index(
                        [("created_at", 1)],
                        name="ownerbot_migration_history_ttl",
                        expireAfterSeconds=retention_seconds,
                        background=True,
                    )
                except Exception:
                    pass
            saved_hosts.append(host)
        except Exception as error:
            error_rows.append(f"{host}: {type(error).__name__}: {error}")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    return {
        "run_id": run_id,
        "saved_clusters": len(saved_hosts),
        "failed_clusters": len(error_rows),
        "saved_hosts": saved_hosts,
        "errors": error_rows,
    }


def _ownerbot_uri_valid(uri: str) -> bool:
    text = str(uri or "").strip()
    return bool(text and _OWNERBOT_MONGO_URI_RE.match(text))


def _ownerbot_notice_encode(message: str) -> str:
    return urlencode({"notice": str(message or "").strip()}).split("=", 1)[1]


def _ownerbot_save_env_keys(updates: dict[str, str]) -> tuple[bool, str]:
    try:
        env_path = _OWNERBOT_ENV_PATH
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        else:
            lines = []
    except Exception as error:
        return False, f"read .env failed: {error}"

    rewritten = list(lines)
    for raw_key, raw_value in dict(updates or {}).items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        value = str(raw_value or "")
        safe_value = value.replace("\\", "\\\\").replace('"', '\\"')
        new_line = f'{key}="{safe_value}"'
        matched = False
        for idx, line in enumerate(rewritten):
            if str(line).lstrip().startswith(f"{key}="):
                rewritten[idx] = new_line
                matched = True
                break
        if not matched:
            rewritten.append(new_line)

    try:
        env_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    except Exception as error:
        return False, f"write .env failed: {error}"
    return True, ""


def _ownerbot_int_clamp(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(str(value).strip()))
    except Exception:
        parsed = int(default)
    return max(int(minimum), min(int(maximum), int(parsed)))


async def _ownerbot_trim_collection_keep_latest(collection: Any, *, keep_latest: int) -> int:
    keep = max(0, int(keep_latest))
    if keep <= 0:
        deleted = await collection.delete_many({})
        return int(getattr(deleted, "deleted_count", 0) or 0)

    pivot_rows = await collection.find({}, {"id": 1}).sort("id", -1).skip(max(0, keep - 1)).limit(1).to_list(length=1)
    if pivot_rows and isinstance(pivot_rows[0], dict) and pivot_rows[0].get("id") is not None:
        pivot_id = pivot_rows[0].get("id")
        deleted = await collection.delete_many({"id": {"$lt": pivot_id}})
        return int(getattr(deleted, "deleted_count", 0) or 0)

    pivot_created_rows = await collection.find({}, {"created_at": 1}).sort("created_at", -1).skip(max(0, keep - 1)).limit(1).to_list(length=1)
    if pivot_created_rows and isinstance(pivot_created_rows[0], dict) and pivot_created_rows[0].get("created_at") is not None:
        pivot_created_at = pivot_created_rows[0].get("created_at")
        deleted = await collection.delete_many({"created_at": {"$lt": pivot_created_at}})
        return int(getattr(deleted, "deleted_count", 0) or 0)

    return 0


async def _ownerbot_collect_mongo_row(
    *,
    index_value: int,
    uri: str,
    health_row: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    try:
        diagnostics = await bridge_storage.mongo_uri_diagnostics(
            uri,
            timeout_seconds=_OWNERBOT_MONGO_DIAGNOSTIC_TIMEOUT_SECONDS,
            max_collections=_OWNERBOT_MONGO_DIAGNOSTIC_MAX_COLLECTIONS,
        )
    except Exception as error:
        diagnostics = {
            "host": str(bridge_storage.mongo_uri_host(uri) or f"cluster-{index_value}"),
            "database": bridge_storage.mongo_database_name(),
            "ok": False,
            "detail": f"{type(error).__name__}: {error}",
            "latency_ms": 0,
            "collections_total": 0,
            "estimated_documents_total": 0,
            "storage_size_bytes": 0,
            "data_size_bytes": 0,
            "quota_warning": False,
            "collection_rows": [],
        }
    row = {
        "index": index_value,
        "uri": str(uri or ""),
        "host": str(diagnostics.get("host") or "-"),
        "database": str(diagnostics.get("database") or bridge_storage.mongo_database_name()),
        "ok": bool(diagnostics.get("ok")),
        "detail": str(diagnostics.get("detail") or ""),
        "latency_ms": int(diagnostics.get("latency_ms") or 0),
        "collections_total": int(diagnostics.get("collections_total") or 0),
        "estimated_documents_total": int(diagnostics.get("estimated_documents_total") or 0),
        "storage_size_bytes": int(diagnostics.get("storage_size_bytes") or 0),
        "data_size_bytes": int(diagnostics.get("data_size_bytes") or 0),
        "quota_warning": bool(diagnostics.get("quota_warning")),
        "collection_rows": list(diagnostics.get("collection_rows") or []),
        "read_ok": int(health_row.get("read_ok") or 0),
        "read_fail": int(health_row.get("read_fail") or 0),
        "write_ok": int(health_row.get("write_ok") or 0),
        "write_fail": int(health_row.get("write_fail") or 0),
        "read_total": int(health_row.get("read_total") or 0),
        "write_total": int(health_row.get("write_total") or 0),
        "read_success_rate": health_row.get("read_success_rate"),
        "write_success_rate": health_row.get("write_success_rate"),
        "last_error": str(health_row.get("last_error") or ""),
        "last_error_at": float(health_row.get("last_error_at") or 0.0),
        "last_read_at": float(health_row.get("last_read_at") or 0.0),
        "last_write_at": float(health_row.get("last_write_at") or 0.0),
    }
    read_ok = int(row.get("read_ok") or 0)
    write_ok = int(row.get("write_ok") or 0)
    if not bool(row.get("ok")) and (read_ok > 0 or write_ok > 0):
        row["ok"] = True
        base_detail = str(row.get("detail") or "").strip()
        row["detail"] = f"io-health-fallback | {base_detail}" if base_detail else "io-health-fallback"
    names: set[str] = set()
    for collection_row in row["collection_rows"]:
        name = str((collection_row or {}).get("name") or "").strip()
        if name:
            names.add(name)
    return row, names


async def _ownerbot_collect_mongo_rows() -> dict[str, Any]:
    now_monotonic = time.monotonic()
    cached_payload = _OWNERBOT_MONGO_ROWS_CACHE.get("payload")
    cached_expires_at = float(_OWNERBOT_MONGO_ROWS_CACHE.get("expires_at") or 0.0)
    if isinstance(cached_payload, dict) and cached_expires_at > now_monotonic:
        return dict(cached_payload)

    candidate_uris = bridge_storage.mongo_candidate_uris()
    health_snapshot = bridge_storage.mongo_cluster_health_snapshot()
    retention_days = _ownerbot_mongo_history_retention_days_from_env(default=90)
    health_rows = list(health_snapshot.get("rows") or [])
    health_by_index: dict[int, dict[str, Any]] = {}
    for row in health_rows:
        idx = int((row or {}).get("index") or 0)
        if idx > 0:
            health_by_index[idx] = dict(row or {})

    rows: list[dict[str, Any]] = []
    collection_names: set[str] = set()
    healthy_count = 0
    quota_warning_count = 0

    tasks = [
        _ownerbot_collect_mongo_row(
            index_value=idx,
            uri=uri,
            health_row=dict(health_by_index.get(idx) or {}),
        )
        for idx, uri in enumerate(candidate_uris, start=1)
    ]
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results, start=1):
            if isinstance(result, Exception):
                fallback_row = {
                    "index": idx,
                    "uri": str(candidate_uris[idx - 1] if idx - 1 < len(candidate_uris) else ""),
                    "host": str(
                        bridge_storage.mongo_uri_host(candidate_uris[idx - 1]) if idx - 1 < len(candidate_uris) else "-"
                    ),
                    "database": bridge_storage.mongo_database_name(),
                    "ok": False,
                    "detail": f"{type(result).__name__}: {result}",
                    "latency_ms": 0,
                    "collections_total": 0,
                    "estimated_documents_total": 0,
                    "storage_size_bytes": 0,
                    "data_size_bytes": 0,
                    "quota_warning": False,
                    "collection_rows": [],
                    "read_ok": 0,
                    "read_fail": 0,
                    "write_ok": 0,
                    "write_fail": 0,
                    "read_total": 0,
                    "write_total": 0,
                    "read_success_rate": None,
                    "write_success_rate": None,
                    "last_error": "",
                    "last_error_at": 0.0,
                    "last_read_at": 0.0,
                    "last_write_at": 0.0,
                }
                rows.append(fallback_row)
                continue
            row, row_collection_names = result
            rows.append(dict(row))
            collection_names.update(set(row_collection_names or set()))
            if bool(row.get("ok")):
                healthy_count += 1
            if bool(row.get("quota_warning")):
                quota_warning_count += 1

    payload = {
        "rows": rows,
        "uris_count": len(candidate_uris),
        "healthy_count": healthy_count,
        "quota_warning_count": quota_warning_count,
        "collection_options": sorted(collection_names),
        "primary_uri": str(os.getenv("MONGO_URI", "") or ""),
        "backup_uri_text": str(os.getenv("MONGO_URI_BACKUP", "") or ""),
        "database_name": bridge_storage.mongo_database_name(),
        "read_mode": bridge_storage.mongo_current_read_mode(),
        "write_mode": bridge_storage.mongo_current_write_mode(),
        "migration_history_retention_days": int(retention_days),
        "health_totals": dict(health_snapshot.get("totals") or {}),
    }
    _OWNERBOT_MONGO_ROWS_CACHE["payload"] = dict(payload)
    _OWNERBOT_MONGO_ROWS_CACHE["expires_at"] = time.monotonic() + _OWNERBOT_MONGO_CACHE_TTL_SECONDS
    return payload


def _ownerbot_escape(value: Any) -> str:
    return py_html.escape(str(value if value is not None else ""), quote=True)


def _ownerbot_plan_bucket(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"free", "none", ""}:
        return "free"
    if "permanent" in raw or "lifetime" in raw or "forever" in raw:
        return "permanent"
    if "diamond" in raw:
        return "diamond"
    if "golden" in raw or "gold" in raw:
        return "golden"
    if "silver" in raw:
        return "silver"
    return "other"


def _ownerbot_plan_display_from_subscription(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "free": "Free",
        "silver_guild_preminum": "Silver",
        "silver_guild_premium": "Silver",
        "golden_guild_premium": "Gole",
        "gole_guild_premium": "Gole",
        "diamond_guild_premium": "Diamond",
        "permanent_guild_premium": "Permanent (Lifetime)",
        "lifetime_guild_premium": "Permanent (Lifetime)",
    }
    return mapping.get(raw, str(value or "free"))


def _float_from_form(form: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> float:
    raw = str(form.get(key) or "").strip().replace(",", "")
    if not raw:
        return float(default)
    try:
        parsed = float(raw)
    except Exception:
        parsed = float(default)
    parsed = max(float(minimum), min(float(maximum), float(parsed)))
    return float(round(parsed, 2))


def _add_months_utc(base: datetime.datetime, months: int) -> datetime.datetime:
    safe_months = max(0, int(months))
    if safe_months <= 0:
        return base
    year = int(base.year) + (int(base.month) - 1 + safe_months) // 12
    month = (int(base.month) - 1 + safe_months) % 12 + 1
    day = min(int(base.day), calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


async def _ownerbot_collect_console_data(
    *,
    include_command_choices: bool = True,
    include_upload_rows: bool = True,
    include_mongo_rows: bool = False,
    include_wallet_rows: bool = True,
    include_recent_redeem_rows: bool = True,
) -> dict[str, Any]:
    bot = get_bot()
    bot_guild_map = {str(g.id): g for g in (getattr(bot, "guilds", []) or [])}
    redeem_task = (
        _ownerbot_fetch_recent_redeem_rows(limit=_OWNERBOT_REDEEM_RECENT_LIMIT)
        if include_recent_redeem_rows
        else _ownerbot_safe_call(asyncio.sleep(0, result=[]), [])
    )
    wallet_rows_task = (
        _ownerbot_safe_call(storage.bot_wallet_accounts.get_all(), [])
        if include_wallet_rows
        else _ownerbot_safe_call(asyncio.sleep(0, result=[]), [])
    )
    wallet_ledger_rows_task = (
        _ownerbot_fetch_wallet_ledger_rows(limit=_OWNERBOT_WALLET_HISTORY_FETCH_LIMIT)
        if include_wallet_rows
        else _ownerbot_safe_call(asyncio.sleep(0, result=[]), [])
    )
    raw_guild_rows_result, redeem_rows_result, wallet_rows_result, wallet_ledger_rows_result, plan_pricing_settings_result, redeem_summary_result, wallet_summary_result = await asyncio.gather(
        _ownerbot_safe_call(storage.guilds.get_all(), []),
        redeem_task,
        wallet_rows_task,
        wallet_ledger_rows_task,
        _ownerbot_safe_call(billing_workflow.get_plan_pricing_settings(), {}),
        _ownerbot_fetch_redeem_summary(),
        _ownerbot_fetch_wallet_summary(),
    )
    raw_guild_rows = [dict(row) for row in list(raw_guild_rows_result or []) if isinstance(row, dict)]
    redeem_rows = [dict(row) for row in list(redeem_rows_result or []) if isinstance(row, dict)]
    wallet_rows_raw = [dict(row) for row in list(wallet_rows_result or []) if isinstance(row, dict)]
    wallet_ledger_rows_raw = [dict(row) for row in list(wallet_ledger_rows_result or []) if isinstance(row, dict)]
    redeem_summary = dict(redeem_summary_result or {}) if isinstance(redeem_summary_result, dict) else {}
    wallet_summary = dict(wallet_summary_result or {}) if isinstance(wallet_summary_result, dict) else {}
    guild_rows: list[dict[str, Any]] = []
    seen_guild_ids: set[str] = set()
    for row in raw_guild_rows or []:
        guild_id = str(row.get("guild_id") or "").strip()
        if guild_id:
            seen_guild_ids.add(guild_id)
        bot_guild = bot_guild_map.get(guild_id)
        guild_rows.append(
            {
                **row,
                "name": getattr(
                    bot_guild,
                    "name",
                    f"กิลด์ {guild_id}" if guild_id else "ไม่ทราบชื่อกิลด์",
                ),
            }
        )
    for guild_id, bot_guild in bot_guild_map.items():
        if guild_id in seen_guild_ids:
            continue
        guild_rows.append(
            {
                "guild_id": int(guild_id),
                "subscription": "free",
                "subscription_end": "",
                "name": getattr(bot_guild, "name", f"กิลด์ {guild_id}"),
            }
        )
    guild_rows.sort(key=lambda item: str(item.get("name") or "").lower())

    runtime_settings = _ownerbot_runtime_from_db()
    payment_provider_settings = _ownerbot_payment_provider_settings_from_db()
    plan_pricing_settings = (
        dict(plan_pricing_settings_result)
        if isinstance(plan_pricing_settings_result, dict)
        else {}
    )
    plan_pricing_snapshot = billing_workflow.build_plan_pricing_snapshot_from_settings(plan_pricing_settings)
    upload_channel_settings = _ownerbot_upload_channel_settings_from_db()

    upload_guild_rows: list[dict[str, str]] = []
    upload_channel_rows: list[dict[str, str]] = []
    if include_upload_rows:
        sorted_guilds = sorted(
            list(getattr(bot, "guilds", []) or []),
            key=lambda item: str(getattr(item, "name", "") or "").lower(),
        )
        guild_id_order: list[str] = []
        for guild in sorted_guilds:
            guild_id_text = str(getattr(guild, "id", "") or "").strip()
            guild_name_text = str(getattr(guild, "name", "") or guild_id_text).strip()
            if not guild_id_text:
                continue
            guild_id_order.append(guild_id_text)
            upload_guild_rows.append({"id": guild_id_text, "name": guild_name_text})
        selected_storage_guild_id = str(upload_channel_settings.get("storage_guild_id") or "").strip()
        if guild_id_order and selected_storage_guild_id not in set(guild_id_order):
            selected_storage_guild_id = guild_id_order[0]
        if selected_storage_guild_id:
            upload_channel_settings["storage_guild_id"] = selected_storage_guild_id
        for guild in sorted_guilds:
            guild_id_text = str(getattr(guild, "id", "") or "").strip()
            if not guild_id_text or guild_id_text != selected_storage_guild_id:
                continue
            guild_name_text = str(getattr(guild, "name", "") or guild_id_text).strip()
            for channel in sorted(
                list(getattr(guild, "text_channels", []) or []),
                key=lambda item: (
                    int(getattr(item, "position", 0) or 0),
                    str(getattr(item, "name", "") or "").lower(),
                ),
            ):
                channel_id_text = str(getattr(channel, "id", "") or "").strip()
                channel_name_text = str(getattr(channel, "name", "") or channel_id_text).strip()
                if not channel_id_text:
                    continue
                upload_channel_rows.append(
                    {
                        "id": channel_id_text,
                        "guild_id": guild_id_text,
                        "name": channel_name_text,
                        "label": f"{guild_name_text} - #{channel_name_text}",
                    }
                )

    command_choices: list[str] = []
    if include_command_choices:
        command_choices = _ownerbot_collect_command_choices(bot)

    wallet_rows: list[dict[str, Any]] = []
    if include_wallet_rows:
        wallet_ledger_rows_raw.sort(key=_ownerbot_wallet_ledger_sort_key, reverse=True)
        wallet_ledger_by_user: dict[int, list[dict[str, Any]]] = {}
        for row in wallet_ledger_rows_raw:
            user_id_text = str((row or {}).get("user_id") or "").strip()
            if not user_id_text.isdigit():
                continue
            user_id_int = int(user_id_text)
            user_rows = wallet_ledger_by_user.setdefault(user_id_int, [])
            if len(user_rows) >= _OWNERBOT_WALLET_HISTORY_PER_USER_LIMIT:
                continue
            amount_value = 0.0
            balance_before_value = 0.0
            balance_after_value = 0.0
            try:
                amount_value = round(float((row or {}).get("amount") or 0.0), 2)
            except Exception:
                amount_value = 0.0
            try:
                balance_before_value = round(float((row or {}).get("balance_before") or 0.0), 2)
            except Exception:
                balance_before_value = 0.0
            try:
                balance_after_value = round(float((row or {}).get("balance_after") or 0.0), 2)
            except Exception:
                balance_after_value = 0.0
            row_id_value = 0
            try:
                row_id_value = int((row or {}).get("id") or 0)
            except Exception:
                row_id_value = 0
            user_rows.append(
                {
                    "id": row_id_value,
                    "user_id": user_id_int,
                    "amount": amount_value,
                    "balance_before": balance_before_value,
                    "balance_after": balance_after_value,
                    "kind": str((row or {}).get("kind") or "").strip().lower(),
                    "source_mode": str((row or {}).get("source_mode") or "").strip().lower(),
                    "session_key": str((row or {}).get("session_key") or "").strip(),
                    "note": str((row or {}).get("note") or "").strip(),
                    "meta": dict((row or {}).get("meta") or {}) if isinstance((row or {}).get("meta"), dict) else {},
                    "created_at": (row or {}).get("created_at"),
                }
            )

        for row in wallet_rows_raw:
            user_id_text = str((row or {}).get("user_id") or "").strip()
            if not user_id_text.isdigit():
                continue
            user_id_int = int(user_id_text)
            balance_value = 0.0
            try:
                balance_value = float((row or {}).get("balance") or 0.0)
            except Exception:
                balance_value = 0.0
            display_name = f"User {user_id_text}"
            if bot:
                cached_user = bot.get_user(user_id_int)
                if cached_user is not None:
                    user_name = str(getattr(cached_user, "name", "") or "").strip()
                    user_discriminator = str(getattr(cached_user, "discriminator", "") or "").strip()
                    if user_name and user_discriminator and user_discriminator != "0":
                        display_name = f"{user_name}#{user_discriminator}"
                    elif user_name:
                        display_name = user_name
            wallet_rows.append(
                {
                    **(row if isinstance(row, dict) else {}),
                    "user_id": user_id_int,
                    "display_name": display_name,
                    "balance": round(balance_value, 2),
                    "recent_ledger": list(wallet_ledger_by_user.get(user_id_int) or []),
                }
            )
        wallet_rows.sort(
            key=lambda item: (
                float(item.get("balance") or 0.0),
                str(item.get("updated_at") or ""),
                int(item.get("user_id") or 0),
            ),
            reverse=True,
        )
        wallet_rows = wallet_rows[:500]

    mongo_payload: dict[str, Any] = {
        "rows": [],
        "uris_count": 0,
        "healthy_count": 0,
        "quota_warning_count": 0,
        "collection_options": [],
        "primary_uri": str(os.getenv("MONGO_URI", "") or ""),
        "backup_uri_text": str(os.getenv("MONGO_URI_BACKUP", "") or ""),
        "database_name": bridge_storage.mongo_database_name(),
        "read_mode": bridge_storage.mongo_current_read_mode(),
        "write_mode": bridge_storage.mongo_current_write_mode(),
        "migration_history_retention_days": _ownerbot_mongo_history_retention_days_from_env(default=90),
        "health_totals": {
            "read_ok": 0,
            "read_fail": 0,
            "write_ok": 0,
            "write_fail": 0,
            "read_total": 0,
            "write_total": 0,
            "read_success_rate": None,
            "write_success_rate": None,
        },
    }
    mongo_migration_history_rows: list[dict[str, Any]] = []
    if include_mongo_rows:
        try:
            mongo_payload = await _ownerbot_collect_mongo_rows()
        except Exception:
            mongo_payload = {
                "rows": [],
                "uris_count": 0,
                "healthy_count": 0,
                "quota_warning_count": 0,
                "collection_options": [],
                "primary_uri": str(os.getenv("MONGO_URI", "") or ""),
                "backup_uri_text": str(os.getenv("MONGO_URI_BACKUP", "") or ""),
                "database_name": bridge_storage.mongo_database_name(),
                "read_mode": bridge_storage.mongo_current_read_mode(),
                "write_mode": bridge_storage.mongo_current_write_mode(),
                "migration_history_retention_days": _ownerbot_mongo_history_retention_days_from_env(default=90),
                "health_totals": {
                    "read_ok": 0,
                    "read_fail": 0,
                    "write_ok": 0,
                    "write_fail": 0,
                    "read_total": 0,
                    "write_total": 0,
                    "read_success_rate": None,
                    "write_success_rate": None,
                },
            }
        try:
            mongo_migration_history_rows = await _ownerbot_load_mongo_migration_history_rows(limit=40)
        except Exception:
            mongo_migration_history_rows = []

    promote_policy_settings = _ownerbot_promote_policy_from_db()
    promote_suspension_map = _promote_suspension_map_from_db()

    return {
        "guild_rows": guild_rows,
        "redeem_rows": redeem_rows,
        "wallet_rows": wallet_rows,
        "redeem_summary": redeem_summary,
        "wallet_summary": wallet_summary,
        "runtime_settings": runtime_settings,
        "payment_provider_settings": payment_provider_settings,
        "plan_pricing_settings": plan_pricing_settings,
        "plan_pricing_snapshot": plan_pricing_snapshot,
        "upload_channel_settings": upload_channel_settings,
        "upload_guild_rows": upload_guild_rows,
        "upload_channel_rows": upload_channel_rows,
        "command_choices": command_choices,
        "discord_runtime": get_discord_service_state(),
        "mongo_rows": list(mongo_payload.get("rows") or []),
        "mongo_uris_count": int(mongo_payload.get("uris_count") or 0),
        "mongo_healthy_count": int(mongo_payload.get("healthy_count") or 0),
        "mongo_quota_warning_count": int(mongo_payload.get("quota_warning_count") or 0),
        "mongo_collection_options": list(mongo_payload.get("collection_options") or []),
        "mongo_primary_uri": str(mongo_payload.get("primary_uri") or ""),
        "mongo_backup_uri_text": str(mongo_payload.get("backup_uri_text") or ""),
        "mongo_database_name": str(mongo_payload.get("database_name") or bridge_storage.mongo_database_name()),
        "mongo_read_mode": str(mongo_payload.get("read_mode") or bridge_storage.mongo_current_read_mode()),
        "mongo_write_mode": str(mongo_payload.get("write_mode") or bridge_storage.mongo_current_write_mode()),
        "mongo_migration_history_retention_days": _ownerbot_int_clamp(
            mongo_payload.get("migration_history_retention_days"),
            default=_ownerbot_mongo_history_retention_days_from_env(default=90),
            minimum=0,
            maximum=3650,
        ),
        "mongo_health_totals": dict(mongo_payload.get("health_totals") or {}),
        "mongo_migration_history_rows": list(mongo_migration_history_rows or []),
        "promote_policy_settings": dict(promote_policy_settings or {}),
        "promote_suspension_map": dict(promote_suspension_map or {}),
    }


def _ownerbot_build_live_payload(data: dict[str, Any]) -> dict[str, Any]:
    guild_rows = [dict(row) for row in list(data.get("guild_rows") or []) if isinstance(row, dict)]
    redeem_rows = [dict(row) for row in list(data.get("redeem_rows") or []) if isinstance(row, dict)]
    runtime_settings = _normalize_ownerbot_runtime_settings(data.get("runtime_settings") or {})
    discord_runtime = data.get("discord_runtime") if isinstance(data.get("discord_runtime"), dict) else {}
    redeem_summary = dict(data.get("redeem_summary") or {}) if isinstance(data.get("redeem_summary"), dict) else {}
    wallet_summary = dict(data.get("wallet_summary") or {}) if isinstance(data.get("wallet_summary"), dict) else {}
    mongo_rows = [dict(row) for row in list(data.get("mongo_rows") or []) if isinstance(row, dict)]

    plan_counts = {
        "free": 0,
        "silver": 0,
        "golden": 0,
        "diamond": 0,
        "permanent": 0,
        "other": 0,
    }
    for row in guild_rows:
        plan_counts[_ownerbot_plan_bucket(row.get("subscription"))] += 1

    total_codes = int(redeem_summary.get("total_codes") or 0)
    total_claimed = int(redeem_summary.get("claimed_codes") or 0)
    total_unclaimed = int(redeem_summary.get("unclaimed_codes") or 0)
    total_guilds = len(guild_rows)
    total_wallet_users = int(wallet_summary.get("total_wallet_users") or 0)
    wallet_positive_users = int(wallet_summary.get("wallet_positive_users") or 0)
    wallet_balance_total_text = str(wallet_summary.get("wallet_balance_total_text") or "0.00")

    disabled_commands_count = len(list(runtime_settings.get("global_disabled_commands") or []))
    hidden_tabs_count = len(
        {
            str(item or "").strip().lower()
            for item in list(runtime_settings.get("hidden_dashboard_tabs") or [])
            if str(item or "").strip().lower() in set(OWNERBOT_HIDEABLE_TABS)
        }
    )
    whitelist_count = len(list(runtime_settings.get("whitelist_guild_ids") or []))
    blacklist_count = len(list(runtime_settings.get("blacklist_guild_ids") or []))
    tester_guild_count = len(list(runtime_settings.get("tester_guild_ids") or []))

    snapshot_key = "|".join(
        [
            str(total_codes),
            str(total_claimed),
            str(total_unclaimed),
            str(total_guilds),
            str(total_wallet_users),
            str(wallet_positive_users),
            wallet_balance_total_text,
            str(disabled_commands_count),
            str(hidden_tabs_count),
            str(plan_counts.get("free") or 0),
            str(plan_counts.get("silver") or 0),
            str(plan_counts.get("golden") or 0),
            str(plan_counts.get("diamond") or 0),
            str(plan_counts.get("permanent") or 0),
            str(len(mongo_rows)),
        ]
    )

    recent_redeem_rows = []
    for row in redeem_rows[:8]:
        recent_redeem_rows.append(
            {
                "code": str(row.get("code") or "-"),
                "status": "used" if bool(row.get("claimed")) else "unused",
                "type": str(REDEEM_CODE_TYPES.get(str(row.get("code_value") or ""), str(row.get("code_value") or "-"))),
                "created_at": _format_datetime_th(row.get("created_at")),
                "claimed_by": str(row.get("claimed_by") or "-"),
            }
        )

    return {
        "runtime": discord_runtime,
        "snapshot_key": snapshot_key,
        "kpi": {
            "total_codes": total_codes,
            "total_unclaimed": total_unclaimed,
            "total_claimed": total_claimed,
            "total_guilds": total_guilds,
            "disabled_commands_count": disabled_commands_count,
            "hidden_tabs_count": hidden_tabs_count,
            "total_wallet_users": total_wallet_users,
            "wallet_balance_total_text": wallet_balance_total_text,
            "wallet_positive_users": wallet_positive_users,
            "whitelist_count": whitelist_count,
            "blacklist_count": blacklist_count,
            "tester_guild_count": tester_guild_count,
        },
        "plan_counts": plan_counts,
        "mongo": {
            "rows": mongo_rows,
            "uris_count": int(data.get("mongo_uris_count") or 0),
            "healthy_count": int(data.get("mongo_healthy_count") or 0),
            "quota_warning_count": int(data.get("mongo_quota_warning_count") or 0),
        },
        "recent_redeem_rows": recent_redeem_rows,
    }
async def dashboard_trusted_servers_manager(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(_render_guild_picker(session, _manageable_guilds(session), "ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    bot = get_bot()
    guilds = list(getattr(bot, "guilds", []) or [])
    guilds.sort(key=lambda guild: int(getattr(guild, "member_count", 0) or 0), reverse=True)
    available_names = [str(getattr(guild, "name", "")).strip() for guild in guilds if str(getattr(guild, "name", "")).strip()]
    order = _trusted_order_from_db()
    return HTMLResponse(
        _render_trusted_servers_manager_page(
            session=session,
            order=order,
            available_names=available_names,
            notice=notice,
        )
    )

async def dashboard_admin_donatebot_verify_logs(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(_render_guild_picker(session, _manageable_guilds(session), "ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    guilds = _manageable_guilds(session)
    status_filter = str(request.query_params.get("status") or "").strip().lower()
    keyword = str(request.query_params.get("q") or "").strip()
    page_raw = str(request.query_params.get("page") or "1").strip()
    try:
        page = max(1, int(page_raw))
    except Exception:
        page = 1
    page_size = 60
    rows, total_count, resolved_page = await _fetch_donatebot_verify_logs(
        status_filter=status_filter,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return HTMLResponse(
        _render_donatebot_verify_logs_admin_page(
            session=session,
            guilds=guilds,
            rows=rows,
            total_count=total_count,
            page=resolved_page,
            page_size=page_size,
            status_filter=status_filter,
            keyword=keyword,
            notice=notice,
        )
    )

async def dashboard_trusted_servers_manager_save(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    trusted_server_order = ", ".join(_parse_trusted_server_order(form.get("trusted_server_order")))
    await _set_dashboard_config_value(TRUSTED_ORDER_CONFIG_KEY, trusted_server_order)
    return RedirectResponse("/dashboard/admin/trusted-servers?notice=บันทึกลำดับเซิร์ฟเวอร์ที่เชื่อถือแล้ว", status_code=303)

async def dashboard_ownerbot_console(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(_render_guild_picker(session, _manageable_guilds(session), "ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    data = await _ownerbot_collect_console_data(
        include_command_choices=False,
        include_upload_rows=False,
        include_mongo_rows=False,
        include_wallet_rows=False,
        include_recent_redeem_rows=True,
    )

    return HTMLResponse(
        _render_ownerbot_console_page(
            session=session,
            guild_rows=list(data.get("guild_rows") or []),
            redeem_rows=list(data.get("redeem_rows") or []),
            redeem_summary=dict(data.get("redeem_summary") or {}),
            wallet_rows=list(data.get("wallet_rows") or []),
            wallet_summary=dict(data.get("wallet_summary") or {}),
            runtime_settings=dict(data.get("runtime_settings") or {}),
            payment_provider_settings=dict(data.get("payment_provider_settings") or {}),
            plan_pricing_settings=dict(data.get("plan_pricing_settings") or {}),
            plan_pricing_snapshot=dict(data.get("plan_pricing_snapshot") or {}),
            command_choices=list(data.get("command_choices") or []),
            upload_channel_settings=dict(data.get("upload_channel_settings") or {}),
            upload_guild_rows=list(data.get("upload_guild_rows") or []),
            upload_channel_rows=list(data.get("upload_channel_rows") or []),
            mongo_cluster_rows=list(data.get("mongo_rows") or []),
            mongo_uris_count=int(data.get("mongo_uris_count") or 0),
            mongo_healthy_count=int(data.get("mongo_healthy_count") or 0),
            mongo_quota_warning_count=int(data.get("mongo_quota_warning_count") or 0),
            mongo_collection_options=list(data.get("mongo_collection_options") or []),
            mongo_primary_uri=str(data.get("mongo_primary_uri") or ""),
            mongo_backup_uri_text=str(data.get("mongo_backup_uri_text") or ""),
            mongo_database_name=str(data.get("mongo_database_name") or bridge_storage.mongo_database_name()),
            mongo_read_mode=str(data.get("mongo_read_mode") or bridge_storage.mongo_current_read_mode()),
            mongo_write_mode=str(data.get("mongo_write_mode") or bridge_storage.mongo_current_write_mode()),
            mongo_migration_history_retention_days=_ownerbot_int_clamp(
                data.get("mongo_migration_history_retention_days"),
                default=_ownerbot_mongo_history_retention_days_from_env(default=90),
                minimum=0,
                maximum=3650,
            ),
            mongo_health_totals=dict(data.get("mongo_health_totals") or {}),
            mongo_migration_history_rows=list(data.get("mongo_migration_history_rows") or []),
            promote_policy_settings=dict(data.get("promote_policy_settings") or {}),
            promote_suspension_map=dict(data.get("promote_suspension_map") or {}),
            discord_runtime=(data.get("discord_runtime") if isinstance(data.get("discord_runtime"), dict) else {}),
            notice=notice,
        )
    )


async def dashboard_ownerbot_settings(request: Request, notice: str | None = None):
    target = (
        f"/dashboard/admin/ownerbot/settings/"
        f"{_OWNERBOT_SETTINGS_SECTION_DEFAULT}/{_OWNERBOT_RUNTIME_SUBPAGE_DEFAULT}"
    )
    if notice:
        target = f"{target}?notice={_ownerbot_notice_encode(notice)}"
    return RedirectResponse(target, status_code=303)


async def dashboard_ownerbot_settings_section(request: Request, section: str, notice: str | None = None):
    return await _dashboard_ownerbot_settings_section_page(
        request=request,
        section=section,
        runtime_page=None,
        notice=notice,
    )


async def dashboard_ownerbot_settings_runtime_page(
    request: Request,
    runtime_page: str,
    notice: str | None = None,
):
    return await _dashboard_ownerbot_settings_section_page(
        request=request,
        section="runtime",
        runtime_page=runtime_page,
        notice=notice,
    )


async def _dashboard_ownerbot_settings_section_page(
    *,
    request: Request,
    section: str,
    runtime_page: str | None = None,
    notice: str | None = None,
):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(_render_guild_picker(session, _manageable_guilds(session), "ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    settings_section = _ownerbot_normalize_settings_section(section)
    settings_runtime_page = _ownerbot_normalize_runtime_subpage(
        runtime_page,
        _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT,
    )
    collect_flags = _ownerbot_settings_collect_flags(
        settings_section,
        runtime_subpage=settings_runtime_page,
    )
    data = await _ownerbot_collect_console_data(**collect_flags)

    return HTMLResponse(
        _render_ownerbot_settings_page_safe(
            session=session,
            guild_rows=list(data.get("guild_rows") or []),
            redeem_rows=list(data.get("redeem_rows") or []),
            redeem_summary=dict(data.get("redeem_summary") or {}),
            wallet_rows=list(data.get("wallet_rows") or []),
            wallet_summary=dict(data.get("wallet_summary") or {}),
            runtime_settings=dict(data.get("runtime_settings") or {}),
            payment_provider_settings=dict(data.get("payment_provider_settings") or {}),
            plan_pricing_settings=dict(data.get("plan_pricing_settings") or {}),
            plan_pricing_snapshot=dict(data.get("plan_pricing_snapshot") or {}),
            command_choices=list(data.get("command_choices") or []),
            upload_channel_settings=dict(data.get("upload_channel_settings") or {}),
            upload_guild_rows=list(data.get("upload_guild_rows") or []),
            upload_channel_rows=list(data.get("upload_channel_rows") or []),
            mongo_cluster_rows=list(data.get("mongo_rows") or []),
            mongo_uris_count=int(data.get("mongo_uris_count") or 0),
            mongo_healthy_count=int(data.get("mongo_healthy_count") or 0),
            mongo_quota_warning_count=int(data.get("mongo_quota_warning_count") or 0),
            mongo_collection_options=list(data.get("mongo_collection_options") or []),
            mongo_primary_uri=str(data.get("mongo_primary_uri") or ""),
            mongo_backup_uri_text=str(data.get("mongo_backup_uri_text") or ""),
            mongo_database_name=str(data.get("mongo_database_name") or bridge_storage.mongo_database_name()),
            mongo_read_mode=str(data.get("mongo_read_mode") or bridge_storage.mongo_current_read_mode()),
            mongo_write_mode=str(data.get("mongo_write_mode") or bridge_storage.mongo_current_write_mode()),
            mongo_migration_history_retention_days=_ownerbot_int_clamp(
                data.get("mongo_migration_history_retention_days"),
                default=_ownerbot_mongo_history_retention_days_from_env(default=90),
                minimum=0,
                maximum=3650,
            ),
            mongo_health_totals=dict(data.get("mongo_health_totals") or {}),
            mongo_migration_history_rows=list(data.get("mongo_migration_history_rows") or []),
            promote_policy_settings=dict(data.get("promote_policy_settings") or {}),
            promote_suspension_map=dict(data.get("promote_suspension_map") or {}),
            discord_runtime=(data.get("discord_runtime") if isinstance(data.get("discord_runtime"), dict) else {}),
            notice=notice,
            settings_active_section=settings_section,
            settings_active_runtime_page=settings_runtime_page,
        )
    )


async def dashboard_ownerbot_console_live(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return JSONResponse(
            {"ok": False, "error": "unauthorized", "login_url": "/dashboard"},
            status_code=401,
            headers=_OWNERBOT_LIVE_HEADERS,
        )
    if not _is_dashboard_admin(session):
        return JSONResponse(
            {"ok": False, "error": "forbidden"},
            status_code=403,
            headers=_OWNERBOT_LIVE_HEADERS,
        )

    data = await _ownerbot_collect_console_data(
        include_command_choices=False,
        include_upload_rows=False,
        include_mongo_rows=True,
        include_wallet_rows=False,
        include_recent_redeem_rows=True,
    )
    payload = _ownerbot_build_live_payload(data)
    payload["ok"] = True
    payload["server_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    return JSONResponse(payload, headers=_OWNERBOT_LIVE_HEADERS)


async def dashboard_ownerbot_command_catalog(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return JSONResponse(
            {"ok": False, "error": "unauthorized", "login_url": "/dashboard"},
            status_code=401,
            headers=_OWNERBOT_LIVE_HEADERS,
        )
    if not _is_dashboard_admin(session):
        return JSONResponse(
            {"ok": False, "error": "forbidden"},
            status_code=403,
            headers=_OWNERBOT_LIVE_HEADERS,
        )

    query_text = str(request.query_params.get("q") or "").strip().lower()
    limit = _ownerbot_int_clamp(
        request.query_params.get("limit"),
        default=320,
        minimum=50,
        maximum=5000,
    )
    bot = get_bot()
    rows = _ownerbot_collect_command_choices(bot)
    if query_text:
        rows = [name for name in rows if query_text in str(name or "")]
    total_count = len(rows)
    rows = rows[:limit]
    return JSONResponse(
        {
            "ok": True,
            "query": query_text,
            "total": int(total_count),
            "count": int(len(rows)),
            "commands": list(rows),
        },
        headers=_OWNERBOT_LIVE_HEADERS,
    )


async def dashboard_ownerbot_update_runtime(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    hidden_tabs = [
        slug
        for slug in OWNERBOT_HIDEABLE_TABS
        if not _bool_from_form(form, f"show_tab_{slug}")
    ]
    current_runtime_settings = _ownerbot_runtime_from_db()
    allowed_plan_tiers = set(str(item or "").strip().lower() for item in DASHBOARD_TAB_REQUIRED_PLAN_TIERS if str(item or "").strip())
    if not allowed_plan_tiers:
        allowed_plan_tiers = {"free", "silver", "golden", "diamond", "permanent"}
    tab_required_plan: dict[str, str] = {}
    tab_new_badges: list[str] = []
    tab_policy_enabled = str(form.get("dashboard_tab_policy_enabled") or "").strip() in {"1", "true", "on"}
    if tab_policy_enabled:
        for slug in OWNERBOT_HIDEABLE_TABS:
            selected_tier = str(form.get(f"required_plan_{slug}") or "free").strip().lower()
            if selected_tier not in allowed_plan_tiers:
                selected_tier = "free"
            tab_required_plan[slug] = selected_tier
            if _bool_from_form(form, f"new_badge_{slug}"):
                tab_new_badges.append(slug)
    else:
        existing_required_plan = current_runtime_settings.get("dashboard_tab_required_plan")
        if isinstance(existing_required_plan, dict):
            for slug in OWNERBOT_HIDEABLE_TABS:
                tier = str(existing_required_plan.get(slug) or "free").strip().lower()
                if tier not in allowed_plan_tiers:
                    tier = "free"
                tab_required_plan[slug] = tier
        existing_new_badges = current_runtime_settings.get("dashboard_tab_new_badges")
        if isinstance(existing_new_badges, list):
            seen_new_badges: set[str] = set()
            for slug in existing_new_badges:
                normalized_slug = str(slug or "").strip().lower()
                if (
                    not normalized_slug
                    or normalized_slug not in OWNERBOT_HIDEABLE_TABS
                    or normalized_slug in seen_new_badges
                ):
                    continue
                seen_new_badges.add(normalized_slug)
                tab_new_badges.append(normalized_slug)
    payload = _normalize_ownerbot_runtime_settings(
        {
            "global_command_response_enabled": _bool_from_form(form, "global_command_response_enabled"),
            "global_bot_response_enabled": _bool_from_form(form, "global_bot_response_enabled"),
            "global_ai_provider": str(form.get("global_ai_provider") or "").strip().lower(),
            "global_ai_model": str(form.get("global_ai_model") or "").strip(),
            "guild_mode": (form.get("guild_mode") or "all").strip().lower(),
            "whitelist_guild_ids": _parse_guild_id_list(form.get("whitelist_guild_ids")),
            "blacklist_guild_ids": _parse_guild_id_list(form.get("blacklist_guild_ids")),
            "tester_enabled": _bool_from_form(form, "tester_enabled"),
            "tester_guild_ids": _parse_guild_id_list(form.get("tester_guild_ids")),
            "global_disabled_commands": _parse_command_name_list(form.get("global_disabled_commands")),
            "developer_social_links": _parse_developer_social_links(form.get("developer_social_links")),
            "hidden_dashboard_tabs": hidden_tabs,
            "dashboard_tab_required_plan": tab_required_plan,
            "dashboard_tab_new_badges": tab_new_badges,
            "discordbotlist_vote_result_channel_id": str(form.get("discordbotlist_vote_result_channel_id") or "").strip(),
            "discordbotlist_vote_embed_channel_id": str(form.get("discordbotlist_vote_embed_channel_id") or "").strip(),
            "discordbotlist_vote_button_url": str(form.get("discordbotlist_vote_button_url") or "").strip(),
            "discordbotlist_vote_webhook_secret": str(form.get("discordbotlist_vote_webhook_secret") or "").strip(),
            "dashboard_status_override_level": str(current_runtime_settings.get("dashboard_status_override_level") or "auto"),
            "dashboard_status_override_activity": str(current_runtime_settings.get("dashboard_status_override_activity") or "auto"),
            "dashboard_status_override_display": str(current_runtime_settings.get("dashboard_status_override_display") or "auto"),
            "dashboard_status_override_message": str(current_runtime_settings.get("dashboard_status_override_message") or ""),
            "dashboard_status_override_messages": list(current_runtime_settings.get("dashboard_status_override_messages") or []),
        }
    )
    await _set_dashboard_config_value(
        OWNERBOT_RUNTIME_CONFIG_KEY,
        json.dumps(payload, ensure_ascii=False),
    )
    await _set_dashboard_config_value(
        DEVELOPER_SOCIAL_LINKS_CONFIG_KEY,
        json.dumps(payload.get("developer_social_links") or {}, ensure_ascii=False),
    )
    try:
        bot = get_bot()
        if bot and hasattr(bot, "_load_ownerbot_runtime_settings"):
            await bot._load_ownerbot_runtime_settings(force=True)
            presence_cog = bot.get_cog("ready") or bot.get_cog("Ready")
            if presence_cog and hasattr(presence_cog, "request_presence_refresh"):
                presence_cog.request_presence_refresh()
    except Exception:
        pass
    return _ownerbot_notice_redirect(request, "บันทึก Runtime Control แล้ว")


async def dashboard_ownerbot_update_status(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    form = await _parse_form(request)
    current_runtime_settings = _ownerbot_runtime_from_db()
    next_runtime_settings = dict(current_runtime_settings)
    force_auto = _bool_from_form(form, "dashboard_status_force_auto")
    allowed_levels = {"auto", "online", "idle", "dnd", "offline"}
    allowed_activities = {"auto", "playing", "streaming", "listening", "watching", "competing"}
    non_auto_activities = allowed_activities - {"auto"}
    legacy_level_map = {"live": "online", "stream": "idle", "ded": "dnd"}
    legacy_activity_map = {"custom": "watching"}
    selected_display = str(form.get("dashboard_status_override_display") or "").strip().lower()
    selected_profile = str(form.get("dashboard_status_override_presence") or "").strip().lower()
    raw_level = str(form.get("dashboard_status_override_level") or "").strip().lower()
    raw_activity = str(form.get("dashboard_status_override_activity") or "").strip().lower()
    raw_level = legacy_level_map.get(raw_level, raw_level)
    raw_activity = legacy_activity_map.get(raw_activity, raw_activity)
    level = raw_level if raw_level in allowed_levels else ""
    activity = raw_activity if raw_activity in allowed_activities else ""
    if force_auto:
        level = "auto"
        activity = "auto"
    else:
        if selected_display == "auto":
            level = "auto"
            activity = "auto"
        elif selected_display in allowed_levels:
            if not level:
                level = selected_display
            if not activity:
                activity = "auto"
        elif selected_display in non_auto_activities:
            if not level:
                level = "online"
            if not activity:
                activity = selected_display
        elif ":" in selected_profile:
            legacy_profile_level, legacy_profile_activity = selected_profile.split(":", 1)
            legacy_profile_level = str(legacy_profile_level or "").strip().lower()
            legacy_profile_activity = str(legacy_profile_activity or "").strip().lower()
            if not level and legacy_profile_level in allowed_levels:
                level = legacy_profile_level
            if not activity and legacy_profile_activity in allowed_activities:
                activity = legacy_profile_activity
        if not level:
            level = "auto"
        if not activity:
            activity = "auto"
        # Allow selecting only activity from UI: treat it as online + chosen activity.
        if level == "auto" and activity in non_auto_activities:
            level = "online"
    if force_auto:
        message_text = ""
    else:
        message_text = str(form.get("dashboard_status_override_message") or "").strip()[:2000]
    message_lines = [
        " ".join(str(line or "").strip().split())[:120]
        for line in message_text.splitlines()
        if str(line or "").strip()
    ][:12]
    next_runtime_settings["dashboard_status_override_level"] = level
    next_runtime_settings["dashboard_status_override_activity"] = activity
    next_runtime_settings["dashboard_status_override_display"] = (
        "auto"
        if level == "auto" and activity == "auto"
        else (activity if activity in non_auto_activities and level == "online" else level)
    )
    next_runtime_settings["dashboard_status_override_message"] = message_text
    next_runtime_settings["dashboard_status_override_messages"] = message_lines
    payload = _normalize_ownerbot_runtime_settings(next_runtime_settings)
    await _set_dashboard_config_value(
        OWNERBOT_RUNTIME_CONFIG_KEY,
        json.dumps(payload, ensure_ascii=False),
    )
    try:
        bot = get_bot()
        if bot and hasattr(bot, "_load_ownerbot_runtime_settings"):
            await bot._load_ownerbot_runtime_settings(force=True)
            presence_cog = bot.get_cog("ready") or bot.get_cog("Ready")
            if presence_cog and hasattr(presence_cog, "request_presence_refresh"):
                presence_cog.request_presence_refresh()
    except Exception:
        pass
    return _ownerbot_notice_redirect(request, "บันทึกสถานะบอทแล้ว")


def _ownerbot_notice_redirect(request: Request | None, message: str) -> RedirectResponse:
    target_path = "/dashboard/admin/ownerbot"
    if request is not None:
        referer = str(request.headers.get("referer") or "")
        settings_match = re.search(
            r"/dashboard/admin/ownerbot/settings(?:/([a-zA-Z0-9_-]+)(?:/([a-zA-Z0-9_-]+))?)?",
            referer,
        )
        if settings_match:
            settings_section = _ownerbot_normalize_settings_section(
                settings_match.group(1),
                _OWNERBOT_SETTINGS_SECTION_DEFAULT,
            )
            if settings_section == "runtime":
                runtime_subpage = _ownerbot_normalize_runtime_subpage(
                    settings_match.group(2),
                    _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT,
                )
                target_path = f"/dashboard/admin/ownerbot/settings/runtime/{runtime_subpage}"
            else:
                target_path = f"/dashboard/admin/ownerbot/settings/{settings_section}"
    return RedirectResponse(
        f"{target_path}?notice={_ownerbot_notice_encode(message)}",
        status_code=303,
    )


def _ownerbot_assets_notice_redirect(
    request: Request | None,
    message: str,
    *,
    guild_id: int = 0,
) -> RedirectResponse:
    target_path = "/dashboard/admin/ownerbot/assets"
    query: dict[str, Any] = {"notice": message}
    if int(guild_id or 0) > 0:
        query["guild_id"] = str(int(guild_id))
    return RedirectResponse(
        f"{target_path}?{urlencode(query)}",
        status_code=303,
    )


def _ownerbot_promote_notice_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(
        f"/dashboard/admin/ownerbot/settings/promote?notice={_ownerbot_notice_encode(message)}",
        status_code=303,
    )


async def dashboard_ownerbot_update_promote_policy(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    payload = _ownerbot_promote_policy_from_raw(
        {
            "allowed_domains": _normalize_promote_allowed_domains(form.get("allowed_domains") or ""),
            "allowed_urls": _normalize_promote_allowed_urls(form.get("allowed_urls") or ""),
            "blocked_words": _normalize_promote_blocked_words(form.get("blocked_words") or ""),
            "blocked_domains": _normalize_promote_allowed_domains(form.get("blocked_domains") or ""),
            "blocked_urls": _normalize_promote_allowed_urls(form.get("blocked_urls") or ""),
        }
    )
    await _set_dashboard_config_value(
        PROMOTE_OWNER_POLICY_CONFIG_KEY,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    return _ownerbot_promote_notice_redirect("บันทึก Promote policy (global) แล้ว")


async def dashboard_ownerbot_manage_promote_suspension(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    action = str(form.get("action") or "").strip().lower()
    guild_id_text = str(form.get("guild_id") or "").strip()
    if not guild_id_text.isdigit():
        return _ownerbot_promote_notice_redirect("กรุณากรอก Guild ID ให้ถูกต้อง")
    guild_id = int(guild_id_text)
    if guild_id <= 0:
        return _ownerbot_promote_notice_redirect("กรุณากรอก Guild ID ให้ถูกต้อง")

    suspension_map = _promote_suspension_map_from_db()
    if not isinstance(suspension_map, dict):
        suspension_map = {}

    actor = dict((session or {}).get("user") or {})
    actor_name = str(actor.get("global_name") or actor.get("username") or "OwnerBOT").strip()[:120] or "OwnerBOT"
    _clean_note = str(form.get("note") or "").replace("\r", " ").replace("\n", " ").strip()[:600]

    if action == "suspend":
        suspension_map[str(guild_id)] = {
            "note": _clean_note,
            "by_name": actor_name,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        message = f"ระงับ Promote ของกิลด์ {guild_id} แล้ว"
    elif action == "unsuspend":
        suspension_map.pop(str(guild_id), None)
        message = f"ปลดระงับ Promote ของกิลด์ {guild_id} แล้ว"
    else:
        return _ownerbot_promote_notice_redirect("ไม่รู้จัก action ที่ส่งมา")

    safe_map = _promote_suspension_map_from_raw(suspension_map)
    await _set_dashboard_config_value(
        PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY,
        json.dumps(safe_map, ensure_ascii=False, separators=(",", ":")),
    )
    return _ownerbot_promote_notice_redirect(message)


def _ownerbot_asset_bytes_text(raw_value: Any) -> str:
    value = float(raw_value or 0.0)
    if value < 1024:
        return f"{int(value)} B"
    if value < 1024 * 1024:
        return f"{value / 1024.0:,.2f} KB"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024.0 * 1024.0):,.2f} MB"
    return f"{value / (1024.0 * 1024.0 * 1024.0):,.2f} GB"


async def _ownerbot_collect_dashboard_asset_stats(
    *,
    guild_id: int = 0,
    sample_limit: int = 20,
    request: Request | None = None,
) -> dict[str, Any]:
    assets_collection = await bridge_storage.get_collection(storage.dashboard_image_assets.COLLECTION_NAME)
    base_match: dict[str, Any] = {"is_active": True}
    if int(guild_id or 0) > 0:
        base_match["guild_id"] = int(guild_id)

    totals_task = assets_collection.aggregate(
        [
            {"$match": dict(base_match)},
            {
                "$group": {
                    "_id": None,
                    "assets": {"$sum": 1},
                    "optimized_bytes": {"$sum": {"$ifNull": ["$optimized_size", 0]}},
                    "original_bytes": {"$sum": {"$ifNull": ["$original_size", 0]}},
                }
            },
        ]
    ).to_list(length=1)

    target_task = assets_collection.aggregate(
        [
            {"$match": dict(base_match)},
            {
                "$group": {
                    "_id": "$upload_target",
                    "count": {"$sum": 1},
                    "optimized_bytes": {"$sum": {"$ifNull": ["$optimized_size", 0]}},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 40},
        ]
    ).to_list(length=40)

    kind_task = assets_collection.aggregate(
        [
            {"$match": dict(base_match)},
            {
                "$group": {
                    "_id": "$asset_kind",
                    "count": {"$sum": 1},
                    "optimized_bytes": {"$sum": {"$ifNull": ["$optimized_size", 0]}},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 20},
        ]
    ).to_list(length=20)

    guild_task = assets_collection.aggregate(
        [
            {"$match": dict(base_match)},
            {
                "$group": {
                    "_id": "$guild_id",
                    "count": {"$sum": 1},
                    "optimized_bytes": {"$sum": {"$ifNull": ["$optimized_size", 0]}},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 30},
        ]
    ).to_list(length=30)

    totals_rows, target_rows, kind_rows, guild_rows = await asyncio.gather(
        totals_task,
        target_task,
        kind_task,
        guild_task,
    )

    totals_row = dict(totals_rows[0]) if totals_rows and isinstance(totals_rows[0], dict) else {}
    referenced_keys = await collect_referenced_dashboard_asset_keys()
    orphan_filter = dict(base_match)
    if referenced_keys:
        orphan_filter["asset_key"] = {"$nin": list(referenced_keys)}
    orphan_count = int(await assets_collection.count_documents(orphan_filter))
    orphan_bytes = 0
    sample_rows: list[dict[str, Any]] = []
    if orphan_count > 0:
        sample = await assets_collection.find(
            orphan_filter,
            {
                "_id": 0,
                "id": 1,
                "guild_id": 1,
                "asset_key": 1,
                "upload_target": 1,
                "asset_kind": 1,
                "optimized_size": 1,
                "stored_filename": 1,
                "created_at": 1,
            },
        ).sort("id", 1).limit(max(1, min(int(sample_limit or 20), 80))).to_list(length=max(1, min(int(sample_limit or 20), 80)))
        for row in list(sample or []):
            if not isinstance(row, dict):
                continue
            sample_rows.append(dict(row))
            orphan_bytes += int(row.get("optimized_size") or 0)

    for row in list(sample_rows):
        row_key = str(row.get("asset_key") or "").strip()
        row_name = str(row.get("stored_filename") or "").strip()
        row["url"] = build_dashboard_asset_url(row_key, filename=row_name, request=request) if row_key else ""

    return {
        "base_match": dict(base_match),
        "totals": {
            "assets": int(totals_row.get("assets") or 0),
            "optimized_bytes": int(totals_row.get("optimized_bytes") or 0),
            "original_bytes": int(totals_row.get("original_bytes") or 0),
        },
        "by_target": [dict(row) for row in list(target_rows or []) if isinstance(row, dict)],
        "by_kind": [dict(row) for row in list(kind_rows or []) if isinstance(row, dict)],
        "by_guild": [dict(row) for row in list(guild_rows or []) if isinstance(row, dict)],
        "orphan_count": int(orphan_count),
        "orphan_bytes_preview": int(orphan_bytes),
        "orphan_sample": sample_rows,
        "referenced_key_count": int(len(referenced_keys)),
    }


async def dashboard_ownerbot_asset_stats(request: Request, notice: str | None = None, guild_id: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    guild_filter = _ownerbot_int_clamp(guild_id, default=0, minimum=0, maximum=9_999_999_999_999_999_999)
    stats = await _ownerbot_collect_dashboard_asset_stats(
        guild_id=int(guild_filter),
        sample_limit=25,
        request=request,
    )

    totals = dict(stats.get("totals") or {})
    total_assets = int(totals.get("assets") or 0)
    optimized_bytes = int(totals.get("optimized_bytes") or 0)
    original_bytes = int(totals.get("original_bytes") or 0)
    orphan_count = int(stats.get("orphan_count") or 0)
    orphan_bytes_preview = int(stats.get("orphan_bytes_preview") or 0)
    referenced_key_count = int(stats.get("referenced_key_count") or 0)

    compression_ratio = 0.0
    if original_bytes > 0:
        compression_ratio = (optimized_bytes / float(original_bytes)) * 100.0

    def _render_rows(rows: list[dict[str, Any]], key_label: str) -> str:
        if not rows:
            return '<tr><td colspan="3" class="muted">No data</td></tr>'
        lines: list[str] = []
        for row in rows:
            key_value = py_html.escape(str(row.get("_id") or "unknown"))
            count_value = int(row.get("count") or 0)
            bytes_value = _ownerbot_asset_bytes_text(row.get("optimized_bytes") or 0)
            lines.append(
                "<tr>"
                f"<td>{key_value if key_value else py_html.escape(key_label)}</td>"
                f"<td>{count_value:,}</td>"
                f"<td>{py_html.escape(bytes_value)}</td>"
                "</tr>"
            )
        return "".join(lines)

    orphan_rows = list(stats.get("orphan_sample") or [])
    if orphan_rows:
        orphan_rows_html = "".join(
            (
                "<tr>"
                f"<td>{int(row.get('id') or 0)}</td>"
                f"<td>{int(row.get('guild_id') or 0)}</td>"
                f"<td>{py_html.escape(str(row.get('upload_target') or '-'))}</td>"
                f"<td>{py_html.escape(str(row.get('asset_kind') or '-'))}</td>"
                f"<td>{py_html.escape(_ownerbot_asset_bytes_text(row.get('optimized_size') or 0))}</td>"
                f"<td><a href=\"{py_html.escape(str(row.get('url') or '#'))}\" target=\"_blank\" rel=\"noopener\">open</a></td>"
                "</tr>"
            )
            for row in orphan_rows
        )
    else:
        orphan_rows_html = '<tr><td colspan="6" class="muted">No orphan sample</td></tr>'

    notice_html = (
        f'<div class="notice">{py_html.escape(str(notice or ""))}</div>'
        if str(notice or "").strip()
        else ""
    )

    body = f"""
<section class="panel">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
    <div>
      <h1 style="margin:0;">OwnerBOT Image DB</h1>
      <p class="muted" style="margin:6px 0 0;">Stats + orphan cleanup for dashboard image assets stored in GridFS.</p>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a class="ghost-btn" href="/dashboard/admin/ownerbot">OwnerBOT Console</a>
      <a class="ghost-btn" href="/dashboard/admin/ownerbot/settings/mongo">OwnerBOT Settings</a>
    </div>
  </div>
  {notice_html}
  <div class="field-group" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-top:12px;">
    <div class="field-item"><label>Active Assets</label><input value="{total_assets:,}" readonly></div>
    <div class="field-item"><label>Optimized Size</label><input value="{py_html.escape(_ownerbot_asset_bytes_text(optimized_bytes))}" readonly></div>
    <div class="field-item"><label>Original Size</label><input value="{py_html.escape(_ownerbot_asset_bytes_text(original_bytes))}" readonly></div>
    <div class="field-item"><label>Compression</label><input value="{compression_ratio:,.2f}%" readonly></div>
    <div class="field-item"><label>Referenced Keys</label><input value="{referenced_key_count:,}" readonly></div>
    <div class="field-item"><label>Orphan Assets</label><input value="{orphan_count:,}" readonly></div>
  </div>
  <form method="get" action="/dashboard/admin/ownerbot/assets" class="field-group" style="grid-template-columns:220px auto;margin-top:14px;">
    <div class="field-item">
      <label>Filter Guild ID (0 = all)</label>
      <input type="number" name="guild_id" value="{int(guild_filter)}" min="0" step="1">
    </div>
    <div class="field-item" style="display:flex;align-items:flex-end;gap:8px;">
      <button class="primary-btn" type="submit">Refresh Stats</button>
      <a class="ghost-btn" href="/dashboard/admin/ownerbot/assets">Reset</a>
    </div>
  </form>
  <form method="post" action="/dashboard/admin/ownerbot/assets/cleanup" class="field-group" style="grid-template-columns:170px 170px 170px auto;margin-top:10px;">
    <input type="hidden" name="guild_id" value="{int(guild_filter)}">
    <div class="field-item">
      <label>Limit / Run</label>
      <input type="number" name="limit" value="300" min="1" max="5000" step="1">
    </div>
    <div class="field-item">
      <label>Min Age (minutes)</label>
      <input type="number" name="min_age_minutes" value="30" min="0" max="10080" step="1">
    </div>
    <div class="field-item">
      <label>Mode</label>
      <select name="dry_run">
        <option value="1">Dry Run</option>
        <option value="0">Delete Orphan</option>
      </select>
    </div>
    <div class="field-item" style="display:flex;align-items:flex-end;">
      <button class="danger-btn" type="submit">Run Orphan Cleanup</button>
    </div>
  </form>
  <p class="muted" style="margin-top:6px;">Orphan preview size in this page: {py_html.escape(_ownerbot_asset_bytes_text(orphan_bytes_preview))} (sample only)</p>
  <div class="settings-grid" style="margin-top:14px;">
    <article class="card">
      <h3 style="margin:0 0 8px;">By Upload Target</h3>
      <div class="table-wrap"><table class="ownerbot-table"><thead><tr><th>Target</th><th>Count</th><th>Size</th></tr></thead><tbody>{_render_rows(list(stats.get('by_target') or []), "target")}</tbody></table></div>
    </article>
    <article class="card">
      <h3 style="margin:0 0 8px;">By Asset Kind</h3>
      <div class="table-wrap"><table class="ownerbot-table"><thead><tr><th>Kind</th><th>Count</th><th>Size</th></tr></thead><tbody>{_render_rows(list(stats.get('by_kind') or []), "kind")}</tbody></table></div>
    </article>
  </div>
  <details class="command-category" style="margin-top:14px;" open>
    <summary><span>Orphan Sample ({len(orphan_rows)} rows)</span></summary>
    <div class="command-category-body">
      <div class="table-wrap">
        <table class="ownerbot-table">
          <thead><tr><th>ID</th><th>Guild</th><th>Target</th><th>Kind</th><th>Size</th><th>URL</th></tr></thead>
          <tbody>{orphan_rows_html}</tbody>
        </table>
      </div>
    </div>
  </details>
</section>
"""
    return HTMLResponse(
        _render_layout(
            title="ฐานข้อมูลรูปภาพ OwnerBOT",
            body=body,
            session=session,
            guilds=_manageable_guilds(session),
            active_tab="overview",
            notice=notice,
        )
    )


async def dashboard_ownerbot_asset_cleanup(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    form = await _parse_form(request)
    guild_id = _ownerbot_int_clamp(form.get("guild_id"), default=0, minimum=0, maximum=9_999_999_999_999_999_999)
    limit = _ownerbot_int_clamp(form.get("limit"), default=300, minimum=1, maximum=5000)
    min_age_minutes = _ownerbot_int_clamp(form.get("min_age_minutes"), default=30, minimum=0, maximum=10080)
    dry_run_value = str(form.get("dry_run") or "1").strip().lower()
    dry_run = dry_run_value not in {"0", "false", "off", "no"}

    result = await cleanup_orphan_dashboard_assets(
        guild_id=int(guild_id),
        dry_run=bool(dry_run),
        limit=int(limit),
        min_age_seconds=int(min_age_minutes) * 60,
    )
    if not bool(result.get("ok")):
        return _ownerbot_assets_notice_redirect(
            request,
            f"Asset cleanup failed: {str(result.get('error') or 'unknown')}",
            guild_id=guild_id,
        )

    orphan_count = int(result.get("orphan_count") or 0)
    deleted_assets = int(result.get("deleted_assets") or 0)
    deleted_bytes = int(result.get("deleted_blob_bytes") or 0)
    candidate_bytes = int(result.get("candidate_blob_bytes") or 0)
    scanned = int(result.get("scanned") or 0)
    if dry_run:
        notice = (
            f"Dry run: scanned {scanned:,} assets, orphan={orphan_count:,}, "
            f"estimated reclaim={_ownerbot_asset_bytes_text(candidate_bytes)}"
        )
    else:
        notice = (
            f"Cleanup done: scanned {scanned:,}, orphan={orphan_count:,}, "
            f"deleted={deleted_assets:,}, reclaimed={_ownerbot_asset_bytes_text(deleted_bytes)}"
        )
    errors = list(result.get("errors") or [])
    if errors:
        notice = f"{notice} (errors={len(errors)})"
    return _ownerbot_assets_notice_redirect(request, notice, guild_id=guild_id)


async def dashboard_ownerbot_update_mongo_settings(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    form = await _parse_form(request)
    primary_uri = str(form.get("mongo_primary_uri") or "").strip()
    backup_text = str(form.get("mongo_backup_uri_text") or "").strip()
    read_mode = bridge_storage.mongo_normalize_read_mode(form.get("mongo_read_mode"))
    write_mode = bridge_storage.mongo_normalize_write_mode(form.get("mongo_write_mode"))
    retention_days = _ownerbot_int_clamp(
        form.get("mongo_migration_history_retention_days"),
        default=_ownerbot_mongo_history_retention_days_from_env(default=90),
        minimum=0,
        maximum=3650,
    )
    persist_env = _bool_from_form(form, "persist_env")

    if not _ownerbot_uri_valid(primary_uri):
        return _ownerbot_notice_redirect(request, "Mongo Primary URI ไม่ถูกต้อง (ต้องขึ้นต้นด้วย mongodb:// หรือ mongodb+srv://)")

    backup_uris = [
        uri
        for uri in _ownerbot_split_uri_text(backup_text)
        if _ownerbot_uri_valid(uri) and uri != primary_uri
    ]
    backup_uris = backup_uris[:24]

    old_primary = str(os.getenv("MONGO_URI", "") or "")
    old_backups = _ownerbot_split_uri_text(os.getenv("MONGO_URI_BACKUP", "") or "")
    old_read_mode = str(os.getenv("MONGO_MULTI_READ_MODE", bridge_storage.mongo_current_read_mode()) or "")
    old_write_mode = str(os.getenv("MONGO_MULTI_WRITE_MODE", bridge_storage.mongo_current_write_mode()) or "")
    old_retention_days = _ownerbot_mongo_history_retention_days_from_env(default=90)

    bridge_storage.mongo_set_runtime_uris(primary_uri, backup_uris)
    os.environ["MONGO_MULTI_READ_MODE"] = read_mode
    os.environ["MONGO_MULTI_WRITE_MODE"] = write_mode
    os.environ[_OWNERBOT_MONGO_MIGRATION_HISTORY_RETENTION_ENV_KEY] = str(retention_days)
    bridge_storage.mongo_reset_runtime_connections()
    try:
        await bridge_storage.get_client()
    except Exception as error:
        bridge_storage.mongo_set_runtime_uris(old_primary, old_backups)
        os.environ["MONGO_MULTI_READ_MODE"] = old_read_mode
        os.environ["MONGO_MULTI_WRITE_MODE"] = old_write_mode
        os.environ[_OWNERBOT_MONGO_MIGRATION_HISTORY_RETENTION_ENV_KEY] = str(old_retention_days)
        bridge_storage.mongo_reset_runtime_connections()
        try:
            await bridge_storage.get_client()
        except Exception:
            pass
        return _ownerbot_notice_redirect(request, f"MongoDB connection test failed: {error}")

    retention_result: dict[str, Any] = {
        "updated_clusters": 0,
        "failed_clusters": 0,
        "errors": [],
    }
    try:
        retention_result = await _ownerbot_apply_mongo_migration_history_retention(retention_days=retention_days)
    except Exception as error:
        retention_result = {
            "updated_clusters": 0,
            "failed_clusters": max(1, len(bridge_storage.mongo_candidate_uris())),
            "errors": [f"retention apply failed: {type(error).__name__}: {error}"],
        }

    if persist_env:
        ok, detail = _ownerbot_save_env_keys(
            {
                "MONGO_URI": primary_uri,
                "MONGO_URI_BACKUP": ",".join(backup_uris),
                "MONGO_MULTI_READ_MODE": read_mode,
                "MONGO_MULTI_WRITE_MODE": write_mode,
                _OWNERBOT_MONGO_MIGRATION_HISTORY_RETENTION_ENV_KEY: str(retention_days),
            }
        )
        if not ok:
            return _ownerbot_notice_redirect(request, 
                f"Mongo runtime updated but save .env failed: {detail}"
            )

    _ownerbot_invalidate_mongo_dashboard_cache()
    retention_suffix = (
        f", retention={retention_days}d"
        if retention_days > 0
        else ", retention=OFF"
    )
    if int(retention_result.get("failed_clusters") or 0) > 0:
        return _ownerbot_notice_redirect(request, 
            f"Mongo settings saved with partial retention apply: "
            f"updated={int(retention_result.get('updated_clusters') or 0)}, "
            f"failed={int(retention_result.get('failed_clusters') or 0)}"
            f"{retention_suffix}"
        )
    return _ownerbot_notice_redirect(request, 
        f"Mongo settings saved: 1 primary + {len(backup_uris)} backup URI(s), "
        f"read={read_mode}, write={write_mode}{retention_suffix}"
    )


async def dashboard_ownerbot_mongo_cleanup(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    form = await _parse_form(request)
    action = str(form.get("cleanup_action") or "prune_defaults").strip().lower()
    target_raw = str(form.get("mongo_target_index") or "all").strip().lower()
    collection_name = str(form.get("collection_name") or "").strip()
    keep_latest = _ownerbot_int_clamp(form.get("keep_latest"), default=5000, minimum=0, maximum=400000)
    confirm_text = str(form.get("confirm_text") or "").strip().upper()

    candidate_uris = bridge_storage.mongo_candidate_uris()
    if not candidate_uris:
        return _ownerbot_notice_redirect(request, "ยังไม่พบ Mongo URI ในระบบ")

    targets: list[tuple[int, str]] = []
    if target_raw == "all":
        targets = list(enumerate(candidate_uris, start=1))
    else:
        target_idx = _ownerbot_int_clamp(target_raw, default=1, minimum=1, maximum=len(candidate_uris))
        if target_idx > len(candidate_uris):
            return _ownerbot_notice_redirect(request, "Mongo target index ไม่ถูกต้อง")
        targets = [(target_idx, candidate_uris[target_idx - 1])]

    if action in {"trim_collection", "clear_collection"} and not collection_name:
        return _ownerbot_notice_redirect(request, "กรุณาเลือก collection ก่อน cleanup")
    if action == "clear_collection" and confirm_text != "DELETE":
        return _ownerbot_notice_redirect(request, "พิมพ์ DELETE เพื่อยืนยันการล้างข้อมูลทั้ง collection")

    total_deleted = 0
    touched_collections: set[str] = set()
    error_rows: list[str] = []

    for target_idx, uri in targets:
        client = None
        try:
            client = bridge_storage.mongo_build_client(uri)
            await client.admin.command("ping")
            database = client[bridge_storage.mongo_database_name()]

            if action == "prune_defaults":
                for collection_key, default_keep in _OWNERBOT_MONGO_DEFAULT_PRUNE_LIMITS.items():
                    deleted_count = await _ownerbot_trim_collection_keep_latest(
                        database[str(collection_key)],
                        keep_latest=int(default_keep),
                    )
                    if deleted_count > 0:
                        total_deleted += int(deleted_count)
                        touched_collections.add(str(collection_key))
            elif action == "trim_collection":
                deleted_count = await _ownerbot_trim_collection_keep_latest(
                    database[str(collection_name)],
                    keep_latest=keep_latest,
                )
                total_deleted += int(deleted_count)
                touched_collections.add(str(collection_name))
            elif action == "clear_collection":
                deleted = await database[str(collection_name)].delete_many({})
                deleted_count = int(getattr(deleted, "deleted_count", 0) or 0)
                total_deleted += deleted_count
                touched_collections.add(str(collection_name))
            else:
                return _ownerbot_notice_redirect(request, "cleanup_action ไม่ถูกต้อง")
        except Exception as error:
            host = str(bridge_storage.mongo_uri_host(uri) or f"#{target_idx}")
            error_rows.append(f"{host}: {type(error).__name__}: {error}")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    _ownerbot_invalidate_mongo_dashboard_cache()
    if error_rows:
        return _ownerbot_notice_redirect(request, 
            f"Mongo cleanup partial: deleted {total_deleted} doc(s), errors={len(error_rows)}"
        )

    target_label = "all clusters" if target_raw == "all" else f"cluster #{targets[0][0]}"
    touched_count = len(touched_collections)
    return _ownerbot_notice_redirect(request, 
        f"Mongo cleanup done: deleted {total_deleted} doc(s) from {touched_count} collection(s) on {target_label}"
    )


async def dashboard_ownerbot_mongo_migrate(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    if not _OWNERBOT_MONGO_MIGRATION_SCRIPT_PATH.exists():
        return _ownerbot_notice_redirect(request, "Mongo migration script not found in tools/mongo_multi_migrate.py")

    form = await _parse_form(request)
    candidate_uris = bridge_storage.mongo_candidate_uris()
    if len(candidate_uris) < 2:
        return _ownerbot_notice_redirect(request, "Need at least 2 MongoDB clusters before running migration")

    source_index = _ownerbot_int_clamp(
        form.get("migration_source_index"),
        default=1,
        minimum=1,
        maximum=len(candidate_uris),
    )
    target_raw = str(form.get("migration_target_index") or "all").strip().lower()
    if target_raw != "all":
        target_index = _ownerbot_int_clamp(target_raw, default=1, minimum=1, maximum=len(candidate_uris))
        if target_index == source_index:
            return _ownerbot_notice_redirect(request, "Source and target Mongo index must be different")
        target_raw = str(target_index)

    collection_rows = _ownerbot_parse_collection_text(form.get("migration_collections_text"))
    chunk_size = _ownerbot_int_clamp(form.get("migration_chunk_size"), default=500, minimum=50, maximum=5000)
    max_docs = _ownerbot_int_clamp(
        form.get("migration_max_docs_per_collection"),
        default=0,
        minimum=0,
        maximum=5_000_000,
    )
    only_if_missing = _bool_from_form(form, "migration_only_if_missing")
    execute = _bool_from_form(form, "migration_execute")

    command: list[str] = [
        str(sys.executable),
        str(_OWNERBOT_MONGO_MIGRATION_SCRIPT_PATH),
        "--source-index",
        str(source_index),
        "--target-index",
        str(target_raw),
        "--db-name",
        bridge_storage.mongo_database_name(),
        "--chunk-size",
        str(chunk_size),
        "--max-docs-per-collection",
        str(max_docs),
    ]
    if collection_rows:
        command.extend(["--collections", ",".join(collection_rows[:500])])
    if only_if_missing:
        command.append("--only-if-missing")
    if execute:
        command.append("--execute")

    run_started_at = float(time.time())
    run_finished_at = run_started_at
    run_id = uuid.uuid4().hex
    return_code = -1
    timed_out = False
    launch_error_text = ""
    stdout_text = ""
    stderr_text = ""

    try:
        result = subprocess.run(
            command,
            cwd=str(_OWNERBOT_ROOT_PATH),
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        return_code = int(result.returncode or 0)
        stdout_text = str(result.stdout or "")
        stderr_text = str(result.stderr or "")
    except subprocess.TimeoutExpired as error:
        timed_out = True
        return_code = 124
        stdout_text = str(getattr(error, "stdout", "") or "")
        stderr_text = str(getattr(error, "stderr", "") or "")
        launch_error_text = "Mongo migration timeout (> 30 minutes). Please narrow collections/chunk."
    except Exception as error:
        return_code = 125
        launch_error_text = f"Mongo migration failed to start: {error}"
    run_finished_at = float(time.time())

    output_text = "\n".join([str(stdout_text or "").strip(), str(stderr_text or "").strip()]).strip()

    summary_payload: dict[str, Any] = {}
    for row in reversed(output_text.splitlines()):
        line = str(row or "").strip()
        if not line.startswith("SUMMARY_JSON:"):
            continue
        raw_json = line.split("SUMMARY_JSON:", 1)[1].strip()
        try:
            decoded = json.loads(raw_json)
        except Exception:
            decoded = {}
        if isinstance(decoded, dict):
            summary_payload = decoded
            break

    mode_label = str(summary_payload.get("mode") or ("execute" if execute else "dry_run")).strip().lower()
    mode_text = "EXECUTE" if mode_label == "execute" else "DRY-RUN"
    summary_totals_raw = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    summary_totals = {
        "scanned": int((summary_totals_raw or {}).get("scanned") or 0),
        "actionable": int((summary_totals_raw or {}).get("actionable") or 0),
        "skipped_no_key": int((summary_totals_raw or {}).get("skipped_no_key") or 0),
        "upserted": int((summary_totals_raw or {}).get("upserted") or 0),
        "matched": int((summary_totals_raw or {}).get("matched") or 0),
        "modified": int((summary_totals_raw or {}).get("modified") or 0),
        "errors": int((summary_totals_raw or {}).get("errors") or 0),
    }
    collections_total = int(summary_payload.get("collections_total") or 0)
    summary_duration_seconds = 0.0
    try:
        summary_duration_seconds = float(summary_payload.get("duration_seconds") or 0.0)
    except Exception:
        summary_duration_seconds = 0.0

    if timed_out:
        notice_message = launch_error_text or "Mongo migration timeout"
    elif launch_error_text:
        notice_message = launch_error_text
    elif summary_payload:
        notice_message = (
            f"Mongo migration {mode_text}: collections={collections_total}, "
            f"scanned={summary_totals['scanned']}, upserted={summary_totals['upserted']}, errors={summary_totals['errors']}"
        )
    elif return_code == 0:
        notice_message = f"Mongo migration {mode_text} done (no summary payload)"
    else:
        tail = output_text.splitlines()[-1] if output_text else "unknown error"
        notice_message = f"Mongo migration failed (rc={return_code}): {tail[:240]}"

    target_indexes: list[int] = []
    if isinstance(summary_payload.get("target_indexes"), list):
        for item in list(summary_payload.get("target_indexes") or []):
            try:
                idx = int(item)
            except Exception:
                idx = 0
            if idx > 0 and idx not in target_indexes:
                target_indexes.append(idx)
    if not target_indexes:
        if target_raw == "all":
            target_indexes = [idx for idx in range(1, len(candidate_uris) + 1) if idx != source_index]
        else:
            try:
                parsed_target = int(target_raw)
            except Exception:
                parsed_target = 0
            if parsed_target > 0 and parsed_target != source_index:
                target_indexes = [parsed_target]

    summary_target_hosts = summary_payload.get("target_hosts") if isinstance(summary_payload.get("target_hosts"), dict) else {}
    target_hosts_payload: dict[str, str] = {}
    if isinstance(summary_target_hosts, dict):
        for key, value in summary_target_hosts.items():
            idx_text = str(key or "").strip()
            host_text = str(value or "").strip()
            if idx_text and host_text:
                target_hosts_payload[idx_text] = host_text
    if not target_hosts_payload:
        for idx in target_indexes:
            if 1 <= idx <= len(candidate_uris):
                target_hosts_payload[str(idx)] = str(bridge_storage.mongo_uri_host(candidate_uris[idx - 1]) or f"cluster-{idx}")

    actor_user_id = str(_session_user_id(session) or "").strip()
    actor_label = str(
        session.get("display_name")
        or session.get("username")
        or session.get("name")
        or session.get("email")
        or actor_user_id
        or "unknown"
    ).strip()
    history_payload = {
        "_id": run_id,
        "run_id": run_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "created_by_user_id": actor_user_id,
        "created_by_label": actor_label[:120],
        "source_index": int(source_index),
        "source_host": str(bridge_storage.mongo_uri_host(candidate_uris[source_index - 1]) or f"cluster-{source_index}"),
        "target_index_input": str(target_raw),
        "target_indexes": target_indexes,
        "target_hosts": target_hosts_payload,
        "database_name": str(bridge_storage.mongo_database_name() or "skylinebot"),
        "collections_filter": list(collection_rows[:500]),
        "chunk_size": int(chunk_size),
        "max_docs_per_collection": int(max_docs),
        "only_if_missing": bool(only_if_missing),
        "execute": bool(execute),
        "mode": mode_label,
        "command": list(command),
        "return_code": int(return_code),
        "timed_out": bool(timed_out),
        "ok": bool((not timed_out) and (not launch_error_text) and int(return_code) == 0 and int(summary_totals["errors"]) <= 0),
        "error_text": str(launch_error_text or "").strip()[:600],
        "collections_total": int(collections_total),
        "totals": dict(summary_totals),
        "summary": dict(summary_payload or {}),
        "output_tail": _ownerbot_tail_text(output_text, max_lines=80, max_chars=8000),
        "stdout_tail": _ownerbot_tail_text(stdout_text),
        "stderr_tail": _ownerbot_tail_text(stderr_text),
        "started_at_epoch": int(run_started_at),
        "finished_at_epoch": int(run_finished_at),
        "duration_seconds": float(summary_duration_seconds if summary_duration_seconds > 0 else max(0.0, run_finished_at - run_started_at)),
    }
    history_saved = 0
    history_failed = 0
    try:
        history_result = await _ownerbot_save_mongo_migration_history(history_payload)
        history_saved = int(history_result.get("saved_clusters") or 0)
        history_failed = int(history_result.get("failed_clusters") or 0)
    except Exception:
        history_saved = 0
        history_failed = max(1, len(candidate_uris))

    if history_saved > 0:
        notice_message = f"{notice_message} | audit log saved on {history_saved} cluster(s)"
    elif history_failed > 0:
        notice_message = f"{notice_message} | audit log failed"

    _ownerbot_invalidate_mongo_dashboard_cache()
    return _ownerbot_notice_redirect(request, notice_message)


async def dashboard_ownerbot_mongo_history_manage(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    form = await _parse_form(request)
    action = str(form.get("history_action") or "").strip().lower()
    candidate_uris = bridge_storage.mongo_candidate_uris()
    if not candidate_uris:
        return _ownerbot_notice_redirect(request, "No MongoDB clusters configured")

    query: dict[str, Any] = {}
    action_label = ""
    purge_days = 0
    selected_run_ids: list[str] = []
    if action == "delete_selected":
        selected_run_ids = _ownerbot_parse_history_id_text(form.get("mongo_history_selected_ids"), max_items=1500)
        if not selected_run_ids:
            return _ownerbot_notice_redirect(request, "Please select at least one migration history row")
        query = {
            "$or": [
                {"_id": {"$in": selected_run_ids}},
                {"run_id": {"$in": selected_run_ids}},
            ]
        }
        action_label = f"delete_selected ({len(selected_run_ids)} run id(s))"
    elif action == "purge_older":
        purge_days = _ownerbot_int_clamp(form.get("mongo_history_purge_days"), default=90, minimum=1, maximum=36500)
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=purge_days)
        cutoff_epoch = int(cutoff.timestamp())
        query = {
            "$or": [
                {"created_at": {"$lt": cutoff}},
                {
                    "$and": [
                        {"created_at": {"$exists": False}},
                        {"created_at_epoch": {"$lt": cutoff_epoch}},
                    ]
                },
            ]
        }
        action_label = f"purge_older ({purge_days} day(s))"
    else:
        return _ownerbot_notice_redirect(request, "history_action is invalid")

    total_deleted = 0
    touched_clusters = 0
    error_rows: list[str] = []
    for index_value, uri in enumerate(candidate_uris, start=1):
        client = None
        host = str(bridge_storage.mongo_uri_host(uri) or f"cluster-{index_value}")
        try:
            client = bridge_storage.mongo_build_client(uri)
            await client.admin.command("ping")
            database = client[bridge_storage.mongo_database_name()]
            collection = database[_OWNERBOT_MONGO_MIGRATION_HISTORY_COLLECTION]
            deleted = await collection.delete_many(dict(query))
            total_deleted += int(getattr(deleted, "deleted_count", 0) or 0)
            touched_clusters += 1
        except Exception as error:
            error_rows.append(f"{host}: {type(error).__name__}: {error}")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    _ownerbot_invalidate_mongo_dashboard_cache()
    if error_rows:
        return _ownerbot_notice_redirect(request, 
            f"Mongo history {action_label} partial: deleted {total_deleted} row(s), "
            f"updated={touched_clusters}, errors={len(error_rows)}"
        )

    if action == "purge_older":
        return _ownerbot_notice_redirect(request, 
            f"Mongo history purged older than {purge_days} day(s): deleted {total_deleted} row(s) on {touched_clusters} cluster(s)"
        )
    return _ownerbot_notice_redirect(request, 
        f"Mongo history deleted {len(selected_run_ids)} selected run id(s): removed {total_deleted} row(s) on {touched_clusters} cluster(s)"
    )


def _ownerbot_default_discordbotlist_vote_url() -> str:
    env_url = str(os.getenv("DISCORDBOTLIST_VOTE_URL", "") or "").strip()
    if env_url.lower().startswith(("http://", "https://")):
        return env_url
    runtime_url = str(style_urls.VOTE or "").strip()
    if runtime_url and "discordbotlist.com" in runtime_url.lower():
        return runtime_url
    bot_id = str(getattr(BOT_CONFIG, "DISCORD_CLIENT_ID", "") or "").strip()
    if bot_id.isdigit():
        return f"https://discordbotlist.com/bots/{bot_id}/upvote"
    return "https://discordbotlist.com/"


async def dashboard_ownerbot_send_discordbotlist_vote_embed(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    form = await _parse_form(request)
    runtime_settings = _ownerbot_runtime_from_db()

    channel_id_text = str(
        form.get("discordbotlist_vote_embed_channel_id")
        or runtime_settings.get("discordbotlist_vote_embed_channel_id")
        or ""
    ).strip()
    if not channel_id_text.isdigit():
        return _ownerbot_notice_redirect(request, "กรุณาตั้งค่า DiscordBotList Embed Channel ID ก่อนส่งข้อความ")

    vote_url = str(
        form.get("discordbotlist_vote_button_url")
        or runtime_settings.get("discordbotlist_vote_button_url")
        or ""
    ).strip()
    if not vote_url:
        vote_url = _ownerbot_default_discordbotlist_vote_url()
    if not vote_url.lower().startswith(("http://", "https://")):
        return _ownerbot_notice_redirect(request, "DiscordBotList Vote URL ไม่ถูกต้อง")

    bot = get_bot()
    if not bot:
        return _ownerbot_notice_redirect(request, "บอทยังไม่พร้อมใช้งาน")

    channel = bot.get_channel(int(channel_id_text))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id_text))
        except Exception:
            channel = None
    if channel is None or not hasattr(channel, "send"):
        return _ownerbot_notice_redirect(request, "ไม่พบห้องเป้าหมาย หรือบอทยังเข้าไม่ถึงห้องนี้")

    embed = discord.Embed(
        title="โหวตให้ SkylineBOT",
        description=(
            "ช่วยกดโหวตให้บอทบน DiscordBotList เพื่อสนับสนุนการพัฒนา\n"
            "คุณสามารถโหวตได้ทุก 12 ชั่วโมง"
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Vote URL", value=vote_url, inline=False)
    embed.set_footer(text="ขอบคุณทุกการสนับสนุน")

    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label="โหวตบน DiscordBotList",
            style=discord.ButtonStyle.link,
            url=vote_url,
        )
    )

    try:
        await channel.send(embed=embed, view=view)
    except Exception as error:
        return _ownerbot_notice_redirect(request, f"ส่ง Embed ไม่สำเร็จ: {error}")
    return _ownerbot_notice_redirect(request, "ส่ง Embed ปุ่มโหวต DiscordBotList สำเร็จ")


def _ownerbot_parse_amount(raw_value: Any) -> float:
    text = str(raw_value or "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return round(float(text), 2)
    except Exception:
        return 0.0


async def dashboard_ownerbot_update_user_wallet(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("Admin permission required"), status_code=403)

    form = await _parse_form(request)
    action = str(form.get("action") or "add").strip().lower()
    user_id = _int_from_form(form, "user_id", 0, 0, 9_999_999_999_999_999_999)
    if user_id <= 0:
        return _ownerbot_notice_redirect(request, "User ID is invalid")

    amount = _ownerbot_parse_amount(form.get("amount"))
    note = str(form.get("note") or "").strip()[:220]
    admin_user_id = _session_user_id(session)
    admin_tag = f"admin:{admin_user_id}" if admin_user_id else "admin:unknown"
    session_key = f"ownerbot_wallet_{int(datetime.datetime.now().timestamp())}_{user_id}"

    await billing_workflow.ensure_wallet_account(int(user_id))
    current_balance = round(float(await billing_workflow.get_wallet_balance(int(user_id))), 2)

    if action in {"delete", "remove", "clear", "reset"}:
        if current_balance <= 0:
            return _ownerbot_notice_redirect(request, "Wallet is already 0.00 THB")
        ok, message, _ledger = await billing_workflow.debit_wallet(
            user_id=int(user_id),
            amount=current_balance,
            kind="ownerbot_admin_clear",
            source_mode="ownerbot_admin",
            session_key=session_key,
            note=(f"OwnerBOT clear by {admin_tag} | {note}" if note else f"OwnerBOT clear by {admin_tag}"),
            meta={"admin_user_id": int(admin_user_id) if admin_user_id else None},
        )
        if not ok:
            return _ownerbot_notice_redirect(request, str(message or "Unable to clear wallet"))
        return _ownerbot_notice_redirect(request, f"Cleared wallet for user {user_id}")

    if action in {"set", "edit", "update"}:
        if amount < 0:
            return _ownerbot_notice_redirect(request, "Amount must be >= 0.00")
        target_balance = round(amount, 2)
        delta = round(target_balance - current_balance, 2)
        if abs(delta) < 0.01:
            return _ownerbot_notice_redirect(request, f"No change: wallet already {target_balance:.2f} THB")
        if delta > 0:
            ok, message, _ledger = await billing_workflow.credit_wallet(
                user_id=int(user_id),
                amount=delta,
                kind="ownerbot_admin_set",
                source_mode="ownerbot_admin",
                session_key=session_key,
                note=(
                    f"OwnerBOT set wallet {current_balance:.2f}->{target_balance:.2f} by {admin_tag}"
                    + (f" | {note}" if note else "")
                ),
                meta={"admin_user_id": int(admin_user_id) if admin_user_id else None},
            )
        else:
            ok, message, _ledger = await billing_workflow.debit_wallet(
                user_id=int(user_id),
                amount=abs(delta),
                kind="ownerbot_admin_set",
                source_mode="ownerbot_admin",
                session_key=session_key,
                note=(
                    f"OwnerBOT set wallet {current_balance:.2f}->{target_balance:.2f} by {admin_tag}"
                    + (f" | {note}" if note else "")
                ),
                meta={"admin_user_id": int(admin_user_id) if admin_user_id else None},
            )
        if not ok:
            return _ownerbot_notice_redirect(request, str(message or "Unable to update wallet"))
        return _ownerbot_notice_redirect(request, f"Updated wallet {user_id}: {current_balance:.2f} -> {target_balance:.2f} THB")

    if amount <= 0:
        return _ownerbot_notice_redirect(request, "Amount must be greater than 0.00")

    ok, message, _ledger = await billing_workflow.credit_wallet(
        user_id=int(user_id),
        amount=amount,
        kind="ownerbot_admin_credit",
        source_mode="ownerbot_admin",
        session_key=session_key,
        note=(f"OwnerBOT add by {admin_tag} | {note}" if note else f"OwnerBOT add by {admin_tag}"),
        meta={"admin_user_id": int(admin_user_id) if admin_user_id else None},
    )
    if not ok:
        return _ownerbot_notice_redirect(request, str(message or "Unable to credit wallet"))
    return _ownerbot_notice_redirect(request, f"Added {amount:.2f} THB to user {user_id}")


async def dashboard_ownerbot_update_payment_provider(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    plan_pricing_action = str(form.get("plan_pricing_action") or "").strip().lower()
    if plan_pricing_action == "reset":
        now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
        pricing_payload = billing_workflow.normalize_plan_pricing_settings(
            {"updated_at": now_utc.isoformat()}
        )
        pricing_payload["updated_at"] = now_utc.isoformat()
        await _set_dashboard_config_value(
            billing_workflow.PLAN_PRICING_CONFIG_KEY,
            json.dumps(pricing_payload, ensure_ascii=False),
        )
        _invalidate_landing_plan_pricing_snapshot_cache()
        return _ownerbot_notice_redirect(request, "รีเซ็ต Plan Pricing + Promotion แล้ว")

    topup_provider = str(form.get("topup_provider") or "promptpay").strip().lower()
    donate_provider = str(form.get("donate_provider") or "promptpay").strip().lower()
    if topup_provider not in OWNERBOT_PAYMENT_PROVIDER_TYPES:
        topup_provider = "promptpay"
    if donate_provider not in OWNERBOT_PAYMENT_PROVIDER_TYPES:
        donate_provider = "promptpay"

    payload = _normalize_ownerbot_payment_provider_settings(
        {
            "topup_provider": topup_provider,
            "donate_provider": donate_provider,
            "enable_bank_provider": _bool_from_form(form, "enable_bank_provider"),
            "enable_gateway_provider": _bool_from_form(form, "enable_gateway_provider"),
            "enable_stripe_provider": _bool_from_form(form, "enable_stripe_provider"),
            "enable_truemoney_qr_provider": _bool_from_form(form, "enable_truemoney_qr_provider"),
            "bank_topup_verification_mode": form.get("bank_topup_verification_mode"),
            "bank_donate_verification_mode": form.get("bank_donate_verification_mode"),
            "promptpay_account_name": form.get("promptpay_account_name"),
            "promptpay_number": form.get("promptpay_number"),
            "truemoney_phone": form.get("truemoney_phone"),
            "truemoney_gift_phone": form.get("truemoney_gift_phone"),
            "truemoney_gift_url": form.get("truemoney_gift_url"),
            "bank_name": form.get("bank_name"),
            "bank_account_name": form.get("bank_account_name"),
            "bank_account_number": form.get("bank_account_number"),
            "gateway_name": form.get("gateway_name"),
            "webhook_secret": form.get("webhook_secret"),
            "gateway_webhook_secret": form.get("gateway_webhook_secret"),
            "gateway_signature_header": form.get("gateway_signature_header"),
            "gateway_signature_prefix": form.get("gateway_signature_prefix"),
            "gateway_signature_algorithm": form.get("gateway_signature_algorithm"),
            "gateway_metadata_session_key_field": form.get("gateway_metadata_session_key_field"),
            "stripe_secret_key": form.get("stripe_secret_key"),
            "stripe_publishable_key": form.get("stripe_publishable_key"),
            "stripe_webhook_secret": form.get("stripe_webhook_secret"),
            "stripe_signature_header": form.get("stripe_signature_header"),
            "stripe_signature_tolerance_seconds": form.get("stripe_signature_tolerance_seconds"),
            "stripe_api_base_url": form.get("stripe_api_base_url"),
            "stripe_checkout_session_url": form.get("stripe_checkout_session_url"),
            "stripe_inquiry_url": form.get("stripe_inquiry_url"),
            "stripe_success_url": form.get("stripe_success_url"),
            "stripe_cancel_url": form.get("stripe_cancel_url"),
            "stripe_auto_verify": _bool_from_form(form, "stripe_auto_verify"),
            "truemoney_create_payment_url": form.get("truemoney_create_payment_url"),
            "truemoney_inquiry_url": form.get("truemoney_inquiry_url"),
            "truemoney_api_key": form.get("truemoney_api_key"),
            "truemoney_api_secret": form.get("truemoney_api_secret"),
            "truemoney_bearer_token": form.get("truemoney_bearer_token"),
            "truemoney_callback_url": form.get("truemoney_callback_url"),
            "truemoney_webhook_secret": form.get("truemoney_webhook_secret"),
            "truemoney_signature_header": form.get("truemoney_signature_header"),
            "truemoney_signature_prefix": form.get("truemoney_signature_prefix"),
            "truemoney_signature_algorithm": form.get("truemoney_signature_algorithm"),
            "truemoney_amount_field": form.get("truemoney_amount_field"),
            "truemoney_currency_field": form.get("truemoney_currency_field"),
            "truemoney_reference_field": form.get("truemoney_reference_field"),
            "truemoney_callback_field": form.get("truemoney_callback_field"),
            "truemoney_qr_image_field": form.get("truemoney_qr_image_field"),
            "truemoney_qr_code_field": form.get("truemoney_qr_code_field"),
            "truemoney_payment_url_field": form.get("truemoney_payment_url_field"),
            "truemoney_reference_resp_field": form.get("truemoney_reference_resp_field"),
            "truemoney_transaction_id_field": form.get("truemoney_transaction_id_field"),
            "truemoney_inquiry_status_field": form.get("truemoney_inquiry_status_field"),
            "truemoney_paid_status_values": form.get("truemoney_paid_status_values"),
            "truemoney_auto_verify": _bool_from_form(form, "truemoney_auto_verify"),
            "slipok_api_url": form.get("slipok_api_url"),
            "slipok_key": form.get("slipok_key"),
            "slipcheck_verify_engine": form.get("slipcheck_verify_engine"),
            "slipcheck_expected_receiver_name": form.get("slipcheck_expected_receiver_name"),
            "slipcheck_expected_receiver_first_name_th": form.get("slipcheck_expected_receiver_first_name_th"),
            "slipcheck_expected_receiver_last_name_th": form.get("slipcheck_expected_receiver_last_name_th"),
            "slipcheck_expected_receiver_first_name_en": form.get("slipcheck_expected_receiver_first_name_en"),
            "slipcheck_expected_receiver_last_name_en": form.get("slipcheck_expected_receiver_last_name_en"),
            "slipcheck_expected_receiver_bank": form.get("slipcheck_expected_receiver_bank"),
            "slipcheck_expected_receiver_account": form.get("slipcheck_expected_receiver_account"),
            "slipcheck_expected_sender_name": form.get("slipcheck_expected_sender_name"),
            "slipcheck_expected_sender_first_name_th": form.get("slipcheck_expected_sender_first_name_th"),
            "slipcheck_expected_sender_last_name_th": form.get("slipcheck_expected_sender_last_name_th"),
            "slipcheck_expected_sender_first_name_en": form.get("slipcheck_expected_sender_first_name_en"),
            "slipcheck_expected_sender_last_name_en": form.get("slipcheck_expected_sender_last_name_en"),
            "slipcheck_expected_sender_bank": form.get("slipcheck_expected_sender_bank"),
            "slipcheck_expected_sender_account": form.get("slipcheck_expected_sender_account"),
            "slipcheck_expected_reference": form.get("slipcheck_expected_reference"),
            "slipcheck_expected_qr_reference": form.get("slipcheck_expected_qr_reference"),
            "slipcheck_max_age_minutes": form.get("slipcheck_max_age_minutes"),
            "slipcheck_auto_approve_confidence": form.get("slipcheck_auto_approve_confidence"),
            "slipcheck_manual_review_confidence": form.get("slipcheck_manual_review_confidence"),
            "slipcheck_duplicate_window_hours": form.get("slipcheck_duplicate_window_hours"),
            "slipcheck_review_channel_id": form.get("slipcheck_review_channel_id"),
            "slipcheck_review_dm_user_ids": form.get("slipcheck_review_dm_user_ids"),
            "slipcheck_low_confidence_route": form.get("slipcheck_low_confidence_route"),
        }
    )
    await _set_dashboard_config_value(
        OWNERBOT_PAYMENT_PROVIDER_CONFIG_KEY,
        json.dumps(payload, ensure_ascii=False),
    )
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    try:
        current_pricing = await billing_workflow.get_plan_pricing_settings()
    except Exception:
        current_pricing = billing_workflow.normalize_plan_pricing_settings({})
    guild_prices_existing = dict((current_pricing.get("guild_prices") or {}))
    promotions_existing = dict((current_pricing.get("promotions") or {}))

    guild_prices_next = {
        "silver": _float_from_form(
            form,
            "price_silver",
            float(guild_prices_existing.get("silver") or billing_workflow.PLAN_PRICE_THB.get("silver", 40.0)),
            0.0,
            1_000_000.0,
        ),
        "golden": _float_from_form(
            form,
            "price_golden",
            float(guild_prices_existing.get("golden") or billing_workflow.PLAN_PRICE_THB.get("golden", 120.0)),
            0.0,
            1_000_000.0,
        ),
        "diamond": _float_from_form(
            form,
            "price_diamond",
            float(guild_prices_existing.get("diamond") or billing_workflow.PLAN_PRICE_THB.get("diamond", 250.0)),
            0.0,
            1_000_000.0,
        ),
        "permanent": _float_from_form(
            form,
            "price_permanent",
            float(guild_prices_existing.get("permanent") or billing_workflow.PLAN_PRICE_THB.get("permanent", 500.0)),
            0.0,
            1_000_000.0,
        ),
    }
    pricing_form = dict(form)
    if not str(pricing_form.get("price_user_app") or "").strip():
        legacy_user_app_price = str(pricing_form.get("price_app_user") or "").strip()
        if legacy_user_app_price:
            pricing_form["price_user_app"] = legacy_user_app_price

    user_app_price_next = _float_from_form(
        pricing_form,
        "price_user_app",
        float(current_pricing.get("user_app_price") or billing_workflow.USER_APP_PLAN_PRICE_THB),
        0.0,
        1_000_000.0,
    )

    def _promo_discount_from_form(field_name: str, fallback: Any) -> float:
        # Missing discount field should clear promotion instead of retaining stale value.
        if field_name not in form:
            return 0.0
        raw = str(form.get(field_name) or "").strip().replace(",", "")
        if not raw:
            return 0.0
        try:
            parsed = float(raw)
        except Exception:
            parsed = 0.0
        parsed = max(0.0, min(100.0, parsed))
        return float(round(parsed, 2))

    def _promo_duration_from_form(field_name: str, fallback: Any) -> int:
        # Missing duration field should clear promotion instead of retaining stale value.
        if field_name not in form:
            return 0
        raw = str(form.get(field_name) or "").strip().replace(",", "")
        if not raw:
            return 0
        try:
            parsed = int(float(raw))
        except Exception:
            parsed = 0
        return int(max(0, min(1200, parsed)))

    promotions_next: dict[str, dict[str, Any]] = {}
    for promo_key in ("silver", "golden", "diamond", "permanent", billing_workflow.USER_APP_PLAN_CODE):
        current_entry = promotions_existing.get(promo_key) if isinstance(promotions_existing.get(promo_key), dict) else {}
        discount_field_name = f"promo_{promo_key}_discount_percent"
        duration_field_name = f"promo_{promo_key}_duration_value"
        duration_unit_field_name = f"promo_{promo_key}_duration_unit"
        discount_percent = _promo_discount_from_form(discount_field_name, current_entry.get("discount_percent"))
        duration_value = _promo_duration_from_form(duration_field_name, current_entry.get("duration_value"))
        duration_unit = str(
            form.get(duration_unit_field_name) or "day"
        ).strip().lower()
        if duration_unit not in {"day", "month"}:
            duration_unit = "day"
        if discount_percent > 0 and duration_value <= 0:
            try:
                duration_value = int(float(current_entry.get("duration_value") or 30))
            except Exception:
                duration_value = 30
            duration_value = int(max(1, min(1200, duration_value)))

        if discount_percent > 0 and duration_value > 0:
            start_at = now_utc
            if duration_unit == "month":
                end_at = _add_months_utc(start_at, duration_value)
            else:
                end_at = start_at + datetime.timedelta(days=duration_value)
            promotions_next[promo_key] = {
                "discount_percent": float(discount_percent),
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "duration_value": int(duration_value),
                "duration_unit": duration_unit,
            }
        else:
            promotions_next[promo_key] = {
                "discount_percent": 0.0,
                "start_at": "",
                "end_at": "",
                "duration_value": 0,
                "duration_unit": duration_unit,
            }

    pricing_payload = billing_workflow.normalize_plan_pricing_settings(
        {
            "guild_prices": guild_prices_next,
            "user_app_price": user_app_price_next,
            "promotions": promotions_next,
            "updated_at": now_utc.isoformat(),
        }
    )
    pricing_payload["updated_at"] = now_utc.isoformat()
    await _set_dashboard_config_value(
        billing_workflow.PLAN_PRICING_CONFIG_KEY,
        json.dumps(pricing_payload, ensure_ascii=False),
    )
    _invalidate_landing_plan_pricing_snapshot_cache()
    return _ownerbot_notice_redirect(request, "บันทึก Payment Provider + Plan Pricing แล้ว")


async def dashboard_ownerbot_update_plan_pricing(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    plan_pricing_action = str(form.get("plan_pricing_action") or "").strip().lower()
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    if plan_pricing_action == "reset":
        pricing_payload = billing_workflow.normalize_plan_pricing_settings({"updated_at": now_utc.isoformat()})
        pricing_payload["updated_at"] = now_utc.isoformat()
        await _set_dashboard_config_value(
            billing_workflow.PLAN_PRICING_CONFIG_KEY,
            json.dumps(pricing_payload, ensure_ascii=False),
        )
        _invalidate_landing_plan_pricing_snapshot_cache()
        return _ownerbot_notice_redirect(request, "รีเซ็ต Plan Pricing + Promotion แล้ว")

    current_pricing = billing_workflow.normalize_plan_pricing_settings({})
    try:
        current_pricing = await billing_workflow.get_plan_pricing_settings()
    except Exception:
        pass
    guild_prices_existing = dict((current_pricing.get("guild_prices") or {}))
    promotions_existing = dict((current_pricing.get("promotions") or {}))

    guild_prices_next = {
        "silver": _float_from_form(form, "price_silver", float(guild_prices_existing.get("silver") or billing_workflow.PLAN_PRICE_THB.get("silver", 40.0)), 0.0, 1_000_000.0),
        "golden": _float_from_form(form, "price_golden", float(guild_prices_existing.get("golden") or billing_workflow.PLAN_PRICE_THB.get("golden", 120.0)), 0.0, 1_000_000.0),
        "diamond": _float_from_form(form, "price_diamond", float(guild_prices_existing.get("diamond") or billing_workflow.PLAN_PRICE_THB.get("diamond", 250.0)), 0.0, 1_000_000.0),
        "permanent": _float_from_form(form, "price_permanent", float(guild_prices_existing.get("permanent") or billing_workflow.PLAN_PRICE_THB.get("permanent", 500.0)), 0.0, 1_000_000.0),
    }
    pricing_form = dict(form)
    if not str(pricing_form.get("price_user_app") or "").strip():
        legacy_user_app_price = str(pricing_form.get("price_app_user") or "").strip()
        if legacy_user_app_price:
            pricing_form["price_user_app"] = legacy_user_app_price
    user_app_price_next = _float_from_form(pricing_form, "price_user_app", float(current_pricing.get("user_app_price") or billing_workflow.USER_APP_PLAN_PRICE_THB), 0.0, 1_000_000.0)

    def _promo_discount_from_form(field_name: str, fallback: Any) -> float:
        if field_name not in form:
            return 0.0
        raw = str(form.get(field_name) or "").strip().replace(",", "")
        if not raw:
            return 0.0
        try:
            parsed = float(raw)
        except Exception:
            parsed = 0.0
        return float(round(max(0.0, min(100.0, parsed)), 2))

    def _promo_duration_from_form(field_name: str, fallback: Any) -> int:
        if field_name not in form:
            return 0
        raw = str(form.get(field_name) or "").strip().replace(",", "")
        if not raw:
            return 0
        try:
            parsed = int(float(raw))
        except Exception:
            parsed = 0
        return int(max(0, min(1200, parsed)))

    promotions_next: dict[str, dict[str, Any]] = {}
    for promo_key in ("silver", "golden", "diamond", "permanent", billing_workflow.USER_APP_PLAN_CODE):
        current_entry = promotions_existing.get(promo_key) if isinstance(promotions_existing.get(promo_key), dict) else {}
        discount_field_name = f"promo_{promo_key}_discount_percent"
        duration_field_name = f"promo_{promo_key}_duration_value"
        duration_unit_field_name = f"promo_{promo_key}_duration_unit"
        discount_percent = _promo_discount_from_form(discount_field_name, current_entry.get("discount_percent"))
        duration_value = _promo_duration_from_form(duration_field_name, current_entry.get("duration_value"))
        duration_unit = str(form.get(duration_unit_field_name) or "day").strip().lower()
        if duration_unit not in {"day", "month"}:
            duration_unit = "day"
        if discount_percent > 0 and duration_value <= 0:
            try:
                duration_value = int(float(current_entry.get("duration_value") or 30))
            except Exception:
                duration_value = 30
            duration_value = int(max(1, min(1200, duration_value)))
        if discount_percent > 0 and duration_value > 0:
            start_at = now_utc
            end_at = _add_months_utc(start_at, duration_value) if duration_unit == "month" else (start_at + datetime.timedelta(days=duration_value))
            promotions_next[promo_key] = {"discount_percent": float(discount_percent), "start_at": start_at.isoformat(), "end_at": end_at.isoformat(), "duration_value": int(duration_value), "duration_unit": duration_unit}
        else:
            promotions_next[promo_key] = {"discount_percent": 0.0, "start_at": "", "end_at": "", "duration_value": 0, "duration_unit": duration_unit}

    pricing_payload = billing_workflow.normalize_plan_pricing_settings(
        {"guild_prices": guild_prices_next, "user_app_price": user_app_price_next, "promotions": promotions_next, "updated_at": now_utc.isoformat()}
    )
    pricing_payload["updated_at"] = now_utc.isoformat()
    await _set_dashboard_config_value(
        billing_workflow.PLAN_PRICING_CONFIG_KEY,
        json.dumps(pricing_payload, ensure_ascii=False),
    )
    _invalidate_landing_plan_pricing_snapshot_cache()
    return _ownerbot_notice_redirect(request, "บันทึก Plan Pricing + Promotion แล้ว")


async def dashboard_ownerbot_update_upload_channels(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    action = str(form.get("action") or "save").strip().lower()

    current_settings = _ownerbot_upload_channel_settings_from_db()
    payload = _normalize_ownerbot_upload_channel_settings(current_settings)

    if "storage_guild_id" in form:
        storage_guild_id = str(form.get("storage_guild_id") or "").strip()
    else:
        storage_guild_id = str(payload.get("storage_guild_id") or "").strip()
    payload["storage_guild_id"] = storage_guild_id if storage_guild_id.isdigit() else ""

    if action == "clear_all":
        payload = _default_ownerbot_upload_channel_settings()
        await _set_dashboard_config_value(
            OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY,
            json.dumps(payload, ensure_ascii=False),
        )
        return _ownerbot_notice_redirect(request, "ล้าง Upload Mapping ทั้งหมดแล้ว")

    channels = payload.get("channels")
    if not isinstance(channels, dict):
        channels = {key: "" for key in OWNERBOT_UPLOAD_TARGETS}
    for target in OWNERBOT_UPLOAD_TARGETS:
        raw_channel_id = str(form.get(f"channel_{target}") or "").strip()
        channels[target] = raw_channel_id if raw_channel_id.isdigit() else ""
    if payload.get("storage_guild_id"):
        bot = get_bot()
        if bot:
            storage_guild_id = int(payload["storage_guild_id"])
            for target in OWNERBOT_UPLOAD_TARGETS:
                cid_text = str(channels.get(target) or "").strip()
                if not cid_text.isdigit():
                    continue
                resolved_channel = bot.get_channel(int(cid_text))
                resolved_gid = int(getattr(getattr(resolved_channel, "guild", None), "id", 0) or 0)
                if resolved_gid != storage_guild_id:
                    channels[target] = ""
    payload["channels"] = channels

    await _set_dashboard_config_value(
        OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY,
        json.dumps(_normalize_ownerbot_upload_channel_settings(payload), ensure_ascii=False),
    )
    return _ownerbot_notice_redirect(request, "บันทึก Upload Mapping แล้ว")


async def dashboard_ownerbot_create_upload_channels(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    only_missing = _bool_from_form(form, "only_missing")
    settings = _ownerbot_upload_channel_settings_from_db()
    payload = _normalize_ownerbot_upload_channel_settings(settings)

    if "storage_guild_id" in form:
        storage_guild_id = str(form.get("storage_guild_id") or "").strip()
    else:
        storage_guild_id = str(payload.get("storage_guild_id") or "").strip()
    if not storage_guild_id.isdigit():
        return _ownerbot_notice_redirect(request, "กรุณาเลือก Storage Guild ก่อนสร้างห้อง")

    bot = get_bot()
    if not bot:
        return _ownerbot_notice_redirect(request, "บอทยังไม่พร้อมใช้งาน")
    guild = bot.get_guild(int(storage_guild_id))
    if not guild:
        return _ownerbot_notice_redirect(request, "บอทไม่อยู่ใน Storage Guild ที่เลือก")

    default_role = getattr(guild, "default_role", None)
    bot_member = getattr(guild, "me", None)

    def _private_overwrites() -> dict[Any, Any]:
        overwrites: dict[Any, Any] = {}
        if default_role is not None:
            overwrites[default_role] = discord.PermissionOverwrite(view_channel=False)
        if bot_member is not None:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True,
            )
        return overwrites

    async def _ensure_private_channel(channel: Any) -> bool:
        if channel is None:
            return False
        try:
            if default_role is not None:
                await channel.set_permissions(default_role, view_channel=False)
            if bot_member is not None:
                await channel.set_permissions(
                    bot_member,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    read_message_history=True,
                )
            return True
        except Exception:
            return False

    category_name = "Skyline Upload Storage"
    category = None
    for item in list(getattr(guild, "categories", []) or []):
        if str(getattr(item, "name", "") or "").strip().lower() == category_name.lower():
            category = item
            break
    if category is not None:
        try:
            if default_role is not None:
                await category.set_permissions(default_role, view_channel=False)
            if bot_member is not None:
                await category.set_permissions(
                    bot_member,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    read_message_history=True,
                    manage_channels=True,
                )
        except Exception:
            pass
    if category is None:
        try:
            category = await guild.create_category(
                category_name,
                overwrites=_private_overwrites() or None,
            )
        except Exception:
            category = None

    channels = payload.get("channels")
    if not isinstance(channels, dict):
        channels = {key: "" for key in OWNERBOT_UPLOAD_TARGETS}

    created_count = 0
    bound_count = 0
    for target in OWNERBOT_UPLOAD_TARGETS:
        existing_channel_id = str(channels.get(target) or "").strip()
        if only_missing and existing_channel_id.isdigit():
            existing_channel = guild.get_channel(int(existing_channel_id))
            if existing_channel is not None:
                if category is not None:
                    try:
                        await existing_channel.edit(category=category, sync_permissions=False)
                    except Exception:
                        pass
                await _ensure_private_channel(existing_channel)
                bound_count += 1
                continue
            if only_missing:
                continue
        if existing_channel_id.isdigit():
            existing_channel = guild.get_channel(int(existing_channel_id))
            if existing_channel is not None:
                if category is not None:
                    try:
                        await existing_channel.edit(category=category, sync_permissions=False)
                    except Exception:
                        pass
                await _ensure_private_channel(existing_channel)
                bound_count += 1
                continue
        wanted_name = str(OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS.get(target) or f"upload-{target}").strip().lower()
        channel = None
        for item in list(getattr(guild, "text_channels", []) or []):
            if str(getattr(item, "name", "") or "").strip().lower() == wanted_name:
                channel = item
                break
        if channel is None:
            try:
                channel = await guild.create_text_channel(
                    wanted_name,
                    category=category,
                    topic=f"Storage for {target} uploads from SkylineBOT dashboard",
                    overwrites=_private_overwrites() or None,
                )
                created_count += 1
            except Exception:
                channel = None
        if channel is not None:
            if category is not None:
                try:
                    await channel.edit(category=category, sync_permissions=False)
                except Exception:
                    pass
            await _ensure_private_channel(channel)
            channels[target] = str(getattr(channel, "id", "") or "")
            bound_count += 1

    payload["storage_guild_id"] = storage_guild_id
    payload["channels"] = channels
    await _set_dashboard_config_value(
        OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY,
        json.dumps(_normalize_ownerbot_upload_channel_settings(payload), ensure_ascii=False),
    )
    return _ownerbot_notice_redirect(request, 
        f"สร้าง/ผูกห้องเก็บไฟล์แล้ว (ผูกสำเร็จ {bound_count} รายการ, สร้างใหม่ {created_count} ห้อง)"
    )

async def dashboard_ownerbot_generate_redeem(request: Request):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    code_value = str(form.get("code_value") or "").strip()
    if code_value not in REDEEM_CODE_TYPES:
        return _ownerbot_notice_redirect(request, "ประเภทรหัส Redeem ไม่ถูกต้อง")

    code_count = _int_from_form(form, "code_count", 1, 1, 300)
    custom_code = normalize_redeem_code(form.get("custom_code"))
    if custom_code:
        if not is_valid_custom_redeem_code(custom_code):
            return _ownerbot_notice_redirect(
                request,
                "รูปแบบโค้ดไม่ถูกต้อง (ใช้ได้ A-Z, 0-9, - และ _ ความยาว 4-64 ตัวอักษร)",
            )
        if code_count != 1:
            return _ownerbot_notice_redirect(request, "กำหนดโค้ดเองได้ครั้งละ 1 โค้ดเท่านั้น")
        duplicate_row = await storage.redeem_codes.get(code=custom_code)
        if not duplicate_row:
            lower_custom = custom_code.lower()
            for existing_code, payload in (cache.redeem_codes or {}).items():
                if str(existing_code or "").strip().lower() == lower_custom:
                    duplicate_row = payload if isinstance(payload, dict) else {"code": existing_code}
                    break
        if duplicate_row:
            return _ownerbot_notice_redirect(request, "โค้ดนี้มีอยู่แล้ว กรุณาใช้โค้ดอื่น")

    valid_for_days = _int_from_form(form, "valid_for_days", 30, 0, 3650)
    max_claims = coerce_max_claims(form.get("max_claims"), 1)
    mode_user, mode_guild, _ = normalize_redeem_lock_mode(form.get("lock_mode"))
    lock_unique_user = bool(mode_user or _bool_from_form(form, "lock_unique_user"))
    lock_unique_guild = bool(mode_guild or _bool_from_form(form, "lock_unique_guild"))
    lock_mode = lock_mode_from_flags(
        lock_unique_user=lock_unique_user,
        lock_unique_guild=lock_unique_guild,
    )
    valid_until_at = _parse_datetime_local(form.get("valid_until_at"))
    expires_at = _parse_datetime_local(form.get("expires_at"))

    if valid_until_at:
        now_local = datetime.datetime.now()
        remaining_seconds = (valid_until_at - now_local).total_seconds()
        if remaining_seconds <= 0:
            return _ownerbot_notice_redirect(request, "วันหมดอายุสิทธิ์ต้องมากกว่าวันปัจจุบัน")
        valid_for_days = max(1, min(3650, int((remaining_seconds + 86399) // 86400)))

    created_codes: list[str] = []
    try:
        for index in range(code_count):
            if custom_code and index == 0:
                code = custom_code
            else:
                code = normalize_redeem_code(generate_redeem_code())
            if not code:
                code = normalize_redeem_code(generate_redeem_code())
            await storage.redeem_codes.insert(
                code=code,
                code_type="subscription",
                code_value=code_value,
                valid_for_days=None if valid_for_days == 0 else valid_for_days,
                expires_at=expires_at,
                claimed=False,
                claimed_by=None,
                claimed_at=None,
                claim_count=0,
                max_claims=max_claims,
                lock_unique_user=lock_unique_user,
                lock_unique_guild=lock_unique_guild,
                lock_mode=lock_mode,
                used_user_ids=[],
                used_guild_ids=[],
                claim_history=[],
            )
            created_codes.append(code)
    except Exception:
        if created_codes:
            return _ownerbot_notice_redirect(
                request,
                f"สร้างโค้ดได้ {len(created_codes)}/{code_count} โค้ด แล้วเกิดข้อผิดพลาด",
            )
        return _ownerbot_notice_redirect(request, "สร้างโค้ดไม่สำเร็จ")

    if valid_for_days > 0:
        approx_end = datetime.datetime.now() + datetime.timedelta(days=valid_for_days)
        validity_text = f"{valid_for_days} วัน (หมดสิทธิ์โดยประมาณ {approx_end.strftime('%Y-%m-%d %H:%M')})"
    else:
        validity_text = "ถาวร"
    usage_limit_text = "ไม่จำกัดจำนวนครั้ง" if max_claims == 0 else f"{max_claims} ครั้ง"
    lock_text = (
        "ล็อก 1 User + 1 Server"
        if lock_unique_user and lock_unique_guild
        else "ล็อก 1 User"
        if lock_unique_user
        else "ล็อก 1 Server"
        if lock_unique_guild
        else "ไม่ล็อก user/server"
    )
    preview_codes = ", ".join(created_codes[:10])
    more_suffix = f" (+{len(created_codes) - 10} โค้ด)" if len(created_codes) > 10 else ""
    return _ownerbot_notice_redirect(
        request,
        (
            f"สร้างโค้ดสำเร็จ {len(created_codes)} โค้ด | สิทธิ์: {validity_text} | "
            f"จำนวนใช้: {usage_limit_text} | โหมดล็อก: {lock_text} | "
            f"ตัวอย่าง: {preview_codes}{more_suffix}"
        ),
    )

async def dashboard_ownerbot_update_redeem(request: Request):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    action = str(form.get("action") or "save").strip().lower()
    if action in {"remove", "del"}:
        action = "delete"
    elif action in {"reset", "reset_claim", "unclaimed"}:
        action = "unclaim"
    redeem_id = _int_from_form(form, "redeem_id", 0, 0, 9_999_999_999_999_999_999)
    redeem_code_lookup = normalize_redeem_code(
        form.get("redeem_code_lookup") or form.get("code")
    )

    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(str(value or "").strip())
        except Exception:
            return int(default)

    async def _assign_redeem_id_by_code(code_value: str) -> int:
        normalized_code = normalize_redeem_code(code_value)
        if not normalized_code:
            return 0
        try:
            collection = await bridge_storage.get_collection(storage.redeem_codes.COLLECTION_NAME)
            escaped_code = re.escape(normalized_code)
            current_row = await collection.find_one({"code": normalized_code}, {"_id": 0, "id": 1})
            if not isinstance(current_row, dict):
                current_row = await collection.find_one(
                    {"code": {"$regex": f"^{escaped_code}$", "$options": "i"}},
                    {"_id": 0, "id": 1},
                )
            current_id = _safe_int((current_row or {}).get("id"), 0)
            if current_id > 0:
                return current_id
            latest_rows = (
                await collection.find({}, {"_id": 0, "id": 1})
                .sort("id", -1)
                .limit(1)
                .to_list(length=1)
            )
            latest_row = latest_rows[0] if latest_rows and isinstance(latest_rows[0], dict) else {}
            next_id = max(1, _safe_int(latest_row.get("id"), 0) + 1)
            assign_result = await collection.update_one({"code": normalized_code}, {"$set": {"id": int(next_id)}})
            if int(getattr(assign_result, "matched_count", 0) or 0) <= 0:
                await collection.update_one(
                    {"code": {"$regex": f"^{escaped_code}$", "$options": "i"}},
                    {"$set": {"id": int(next_id)}},
                )
            refreshed = await collection.find_one({"code": normalized_code}, {"_id": 0, "id": 1})
            if not isinstance(refreshed, dict):
                refreshed = await collection.find_one(
                    {"code": {"$regex": f"^{escaped_code}$", "$options": "i"}},
                    {"_id": 0, "id": 1},
                )
            return _safe_int((refreshed or {}).get("id"), 0)
        except Exception:
            return 0

    async def _update_redeem_by_code(code_value: str, updates: dict[str, Any]) -> bool:
        normalized_code = normalize_redeem_code(code_value)
        if not normalized_code or not isinstance(updates, dict):
            return False
        try:
            collection = await bridge_storage.get_collection(storage.redeem_codes.COLLECTION_NAME)
            result = await collection.update_one({"code": normalized_code}, {"$set": dict(updates)})
            matched_count = int(getattr(result, "matched_count", 0) or 0)
            if matched_count <= 0:
                escaped_code = re.escape(normalized_code)
                result = await collection.update_one(
                    {"code": {"$regex": f"^{escaped_code}$", "$options": "i"}},
                    {"$set": dict(updates)},
                )
                matched_count = int(getattr(result, "matched_count", 0) or 0)
            return bool(matched_count > 0)
        except Exception:
            return False

    async def _update_redeem_by_id(redeem_id_value: int, updates: dict[str, Any]) -> bool:
        resolved_id = int(redeem_id_value or 0)
        if resolved_id <= 0 or not isinstance(updates, dict):
            return False
        try:
            updated_row = await storage.redeem_codes.update(id=resolved_id, **dict(updates))
            return isinstance(updated_row, dict) and bool(updated_row)
        except Exception:
            return False

    def _drop_redeem_cache_keys(code_value: str) -> None:
        normalized_code = normalize_redeem_code(code_value)
        if not normalized_code:
            return
        lower_code = normalized_code.lower()
        try:
            cache.redeem_codes.pop(normalized_code, None)
            for existing_code in list((cache.redeem_codes or {}).keys()):
                if str(existing_code or "").strip().lower() == lower_code:
                    cache.redeem_codes.pop(existing_code, None)
        except Exception:
            pass

    async def _delete_redeem_row(*, redeem_id_value: int, code_value: str) -> int:
        deleted_count = 0
        resolved_id = int(redeem_id_value or 0)
        normalized_code = normalize_redeem_code(code_value)

        if resolved_id > 0:
            try:
                deleted_rows = await storage.redeem_codes.delete(id=resolved_id)
                deleted_count = len(list(deleted_rows or []))
            except Exception:
                deleted_count = 0

        if deleted_count <= 0 and normalized_code:
            try:
                deleted_rows = await storage.redeem_codes.delete(code=normalized_code)
                deleted_count = len(list(deleted_rows or []))
            except Exception:
                deleted_count = 0

        if deleted_count <= 0 and normalized_code:
            try:
                collection = await bridge_storage.get_collection(storage.redeem_codes.COLLECTION_NAME)
                escaped_code = re.escape(normalized_code)
                delete_result = await collection.delete_many(
                    {"code": {"$regex": f"^{escaped_code}$", "$options": "i"}}
                )
                deleted_count = int(getattr(delete_result, "deleted_count", 0) or 0)
            except Exception:
                deleted_count = 0

        if deleted_count > 0 and normalized_code:
            _drop_redeem_cache_keys(normalized_code)
        return deleted_count

    resolved_redeem_id = int(redeem_id or 0)
    redeem_data: dict[str, Any] | None = None
    if resolved_redeem_id > 0:
        redeem_data = await storage.redeem_codes.get(id=resolved_redeem_id)
    if not redeem_data and redeem_code_lookup:
        redeem_data = await storage.redeem_codes.get(code=redeem_code_lookup)
        if not redeem_data:
            lower_lookup = redeem_code_lookup.lower()
            for existing_code, payload in (cache.redeem_codes or {}).items():
                if str(existing_code or "").strip().lower() == lower_lookup:
                    if isinstance(payload, dict):
                        redeem_data = dict(payload)
                    else:
                        redeem_data = {"code": existing_code}
                    break
        if redeem_data:
            payload_id = _safe_int(redeem_data.get("id"), 0)
            if payload_id <= 0:
                payload_id = await _assign_redeem_id_by_code(redeem_data.get("code"))
            if payload_id > 0:
                resolved_redeem_id = payload_id
                resolved_row = await storage.redeem_codes.get(id=resolved_redeem_id)
                if resolved_row:
                    redeem_data = resolved_row
                else:
                    resolved_redeem_id = 0
            elif resolved_redeem_id <= 0:
                resolved_redeem_id = 0

    if not redeem_data:
        return _ownerbot_notice_redirect(request, "ไม่พบข้อมูลโค้ด")

    current_row_code = normalize_redeem_code(redeem_data.get("code") or redeem_code_lookup)
    if resolved_redeem_id <= 0 and current_row_code:
        resolved_redeem_id = await _assign_redeem_id_by_code(current_row_code)
        if resolved_redeem_id > 0:
            resolved_row = await storage.redeem_codes.get(id=resolved_redeem_id)
            if resolved_row:
                redeem_data = resolved_row
            else:
                resolved_redeem_id = 0

    if action == "delete":
        if not current_row_code and resolved_redeem_id <= 0:
            return _ownerbot_notice_redirect(request, "ไม่พบโค้ดที่ต้องการลบ")
        deleted_count = await _delete_redeem_row(
            redeem_id_value=resolved_redeem_id,
            code_value=current_row_code,
        )
        if deleted_count <= 0:
            return _ownerbot_notice_redirect(request, "ลบโค้ดไม่สำเร็จ (ไม่พบโค้ดเดิม)")
        return _ownerbot_notice_redirect(request, f"ลบโค้ดสำเร็จ {int(deleted_count)} รายการ")

    if action == "unclaim":
        unclaim_payload = {
            "claimed": False,
            "claimed_by": None,
            "claimed_at": None,
            "claim_count": 0,
            "used_user_ids": [],
            "used_guild_ids": [],
            "claim_history": [],
        }
        updated = False
        if resolved_redeem_id > 0:
            updated = await _update_redeem_by_id(resolved_redeem_id, unclaim_payload)
        if not updated:
            updated = await _update_redeem_by_code(current_row_code, unclaim_payload)
        if not updated:
            return _ownerbot_notice_redirect(request, "รีเซ็ตสถานะไม่สำเร็จ (ไม่พบโค้ดเดิม)")
        return _ownerbot_notice_redirect(request, "รีเซ็ตสถานะการเคลมสำเร็จ")

    old_code = normalize_redeem_code(redeem_data.get("code"))
    code = normalize_redeem_code(form.get("code") or redeem_data.get("code"))
    if not is_valid_custom_redeem_code(code):
        return _ownerbot_notice_redirect(
            request,
            "รูปแบบโค้ดไม่ถูกต้อง (ใช้ได้ A-Z, 0-9, - และ _ ความยาว 4-64 ตัวอักษร)",
        )
    existing_row = await storage.redeem_codes.get(code=code)
    if not existing_row:
        lower_code = code.lower()
        for existing_code, payload in (cache.redeem_codes or {}).items():
            if str(existing_code or "").strip().lower() == lower_code:
                existing_row = payload if isinstance(payload, dict) else {"code": existing_code}
                break
    if existing_row:
        existing_id = _safe_int(existing_row.get("id"), 0)
        existing_code = normalize_redeem_code(existing_row.get("code"))
        if resolved_redeem_id > 0 and existing_id > 0:
            if existing_id != resolved_redeem_id:
                return _ownerbot_notice_redirect(request, "โค้ดนี้ซ้ำกับรายการอื่น กรุณาใช้โค้ดใหม่")
        elif existing_code and current_row_code and existing_code != current_row_code:
            return _ownerbot_notice_redirect(request, "โค้ดนี้ซ้ำกับรายการอื่น กรุณาใช้โค้ดใหม่")

    code_value = str(form.get("code_value") or redeem_data.get("code_value") or "").strip()
    if code_value not in REDEEM_CODE_TYPES:
        code_value = str(redeem_data.get("code_value") or "")
    valid_for_days = _int_from_form(form, "valid_for_days", int(redeem_data.get("valid_for_days") or 0), 0, 3650)
    max_claims = coerce_max_claims(form.get("max_claims"), int(redeem_data.get("max_claims") or 1))
    claim_count = coerce_max_claims(form.get("claim_count"), int(redeem_data.get("claim_count") or 0))
    if max_claims > 0 and claim_count > max_claims:
        claim_count = max_claims
    mode_user, mode_guild, _ = normalize_redeem_lock_mode(form.get("lock_mode"))
    lock_unique_user = bool(mode_user or _bool_from_form(form, "lock_unique_user"))
    lock_unique_guild = bool(mode_guild or _bool_from_form(form, "lock_unique_guild"))
    lock_mode = lock_mode_from_flags(
        lock_unique_user=lock_unique_user,
        lock_unique_guild=lock_unique_guild,
    )
    expires_at = _parse_datetime_local(form.get("expires_at"))
    claimed_flag = str(form.get("claimed") or "false").strip().lower() == "true"
    if claimed_flag and max_claims > 0 and claim_count < max_claims:
        claim_count = max_claims
    claimed = bool(claimed_flag or (max_claims > 0 and claim_count >= max_claims))
    claimed_by = redeem_data.get("claimed_by") if claimed else None
    claimed_at = redeem_data.get("claimed_at") if claimed else None
    if claimed and not claimed_at:
        claimed_at = datetime.datetime.now()

    update_payload = {
        "code": code,
        "code_value": code_value,
        "valid_for_days": None if valid_for_days == 0 else valid_for_days,
        "expires_at": expires_at,
        "max_claims": max_claims,
        "claim_count": claim_count,
        "lock_unique_user": lock_unique_user,
        "lock_unique_guild": lock_unique_guild,
        "lock_mode": lock_mode,
        "claimed": claimed,
        "claimed_by": claimed_by,
        "claimed_at": claimed_at,
    }
    updated = False
    if resolved_redeem_id > 0:
        updated = await _update_redeem_by_id(resolved_redeem_id, update_payload)
    if not updated:
        updated = await _update_redeem_by_code(current_row_code, update_payload)
    if not updated:
        return _ownerbot_notice_redirect(request, "บันทึกโค้ดไม่สำเร็จ (ไม่พบโค้ดเดิม)")
    if old_code and code and old_code != code:
        try:
            cache.redeem_codes.pop(old_code, None)
            lower_old_code = old_code.lower()
            for existing_code in list((cache.redeem_codes or {}).keys()):
                if str(existing_code or "").strip().lower() == lower_old_code:
                    cache.redeem_codes.pop(existing_code, None)
                    break
        except Exception:
            pass
    return _ownerbot_notice_redirect(request, "บันทึกโค้ดสำเร็จ")

async def dashboard_ownerbot_update_guild_plan(request: Request):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(await _render_login("ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    form = await _parse_form(request)
    guild_id = _int_from_form(form, "guild_id", 0, 0, 9_999_999_999_999_999_999)
    if guild_id <= 0:
        return _ownerbot_notice_redirect(request, "Guild ID ไม่ถูกต้อง")

    subscription = _normalize_subscription_code(form.get("subscription"))
    if not subscription:
        return _ownerbot_notice_redirect(request, "แพ็กเกจไม่ถูกต้อง")
    subscription_key = str(subscription).strip().lower()
    is_non_expiring_plan = subscription_key in {"free", "permanent_guild_premium", "lifetime_guild_premium"}
    add_days = _int_from_form(form, "add_days", 0, 0, 3650)
    exact_end = _parse_datetime_local(form.get("subscription_end"))
    effective_add_days = 0 if is_non_expiring_plan else add_days
    effective_exact_end = None if is_non_expiring_plan else exact_end

    bot = get_bot()
    if bot:
        await change_guild_subscription(
            bot=bot,
            guild_id=int(guild_id),
            subscription=subscription,
            valid_for_days=effective_add_days if effective_add_days > 0 else None,
            exact_end=effective_exact_end,
        )
    else:
        guild_cache = cache.guilds.get(str(guild_id), {})
        if not guild_cache:
            await storage.guilds.insert(guild_id=int(guild_id))
            guild_cache = cache.guilds.get(str(guild_id), {}) or await storage.guilds.get(guild_id=int(guild_id)) or {}
        if guild_cache and guild_cache.get("id"):
            await storage.guilds.update(
                id=guild_cache.get("id"),
                guild_id=int(guild_id),
                subscription=subscription,
            )

    guild_state = cache.guilds.get(str(guild_id), {}) or await storage.guilds.get(guild_id=int(guild_id)) or {}
    if guild_state and guild_state.get("id"):
        if is_non_expiring_plan:
            await storage.guilds.update(id=guild_state["id"], subscription_end="")
        elif effective_exact_end:
            await storage.guilds.update(id=guild_state["id"], subscription_end=effective_exact_end)

    try:
        await billing_workflow.sync_plan_subscription_with_guild_state(
            guild_id=int(guild_id),
            clear_pending_plan=True,
            status_override="free" if str(subscription).strip().lower() == "free" else "active",
        )
    except Exception:
        pass

    return _ownerbot_notice_redirect(request, "อัปเดตแพ็กเกจกิลด์สำเร็จ")
