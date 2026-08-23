from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from skylinebot.bridge.storage import get_collection
from skylinebot.console.logging import logger
from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "promote_history"
CollectionName = COLLECTION_NAME
MAX_GUILD_HISTORY_RECORDS = 10

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "guild_name": "",
        "source_origin": "unknown",
        "source_channel_name": "",
        "author_name": "",
        "author_label": "",
        "content": "",
        "invite_url": "",
        "queue_key": "",
        "status": "queued",
        "attachments": [],
        "content_links": [],
        "target_guild_ids": [],
        "target_channel_ids": [],
        "target_guild_count": 0,
        "dispatch_count": 0,
        "hidden": False,
        "owner_note": "",
        "owner_action_by_id": 0,
        "owner_action_by_name": "",
        "owner_channel_id": 0,
        "owner_message_id": 0,
        "created_at": NOW,
        "dispatched_at": None,
        "owner_action_at": None,
    },
    json_fields={"attachments", "content_links", "target_guild_ids", "target_channel_ids"},
    datetime_fields={"created_at", "dispatched_at", "owner_action_at"},
)


def _clean_doc(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(document, dict):
        return None
    cleaned = dict(document)
    cleaned.pop("_id", None)
    for field_name in ("created_at", "dispatched_at", "owner_action_at"):
        value = cleaned.get(field_name)
        if isinstance(value, datetime) and value.tzinfo is None:
            cleaned[field_name] = value.replace(tzinfo=timezone.utc)
    return cleaned


def _normalize_source(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"web", "discord"}:
        return raw
    return "unknown"


def _search_terms(raw_search: str) -> list[str]:
    base = str(raw_search or "").strip()
    if not base:
        return []
    terms: list[str] = []
    for chunk in [base, *re.split(r"[\s,|/]+", base)]:
        term = str(chunk or "").strip()
        if not term or term in terms:
            continue
        terms.append(term)
    return terms[:14]


def _search_numeric_values(raw_search: str, terms: list[str]) -> list[int]:
    values: set[int] = set()
    for term in [str(raw_search or "").strip(), *(terms or [])]:
        text = str(term or "")
        if not text:
            continue
        for matched in re.findall(r"\d{6,22}", text):
            try:
                values.add(int(matched))
            except Exception:
                continue
    return list(values)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    guild_name: str = None,
    source_origin: str = None,
    source_channel_id: int = None,
    source_channel_name: str = None,
    author_id: int = None,
    author_name: str = None,
    author_label: str = None,
    content: str = None,
    invite_url: str = None,
    queue_key: str = None,
    status: str = None,
    attachments: list[str] = None,
    content_links: list[str] = None,
    target_guild_ids: list[int] = None,
    target_channel_ids: list[int] = None,
    target_guild_count: int = None,
    dispatch_count: int = None,
    hidden: bool = None,
    owner_note: str = None,
    owner_action_by_id: int = None,
    owner_action_by_name: str = None,
    owner_channel_id: int = None,
    owner_message_id: int = None,
    created_at: datetime = None,
    dispatched_at: datetime = None,
    owner_action_at: datetime = None,
):
    payload = locals()
    payload["source_origin"] = _normalize_source(source_origin)
    row = await _store.insert(payload)

    guild_id_value: Any = guild_id
    if isinstance(row, dict):
        guild_id_value = row.get("guild_id", guild_id_value)
    try:
        guild_id_int = int(guild_id_value or 0)
    except Exception:
        guild_id_int = 0

    if guild_id_int > 0:
        try:
            await _store.delete_limited(limit=MAX_GUILD_HISTORY_RECORDS, filters={"guild_id": guild_id_int})
        except Exception as error:
            logger.warning(f"Promote history prune failed for guild {guild_id_int}: {error}")

    return row


async def update(
    id: int,
    guild_id: int = None,
    guild_name: str = None,
    source_origin: str = None,
    source_channel_id: int = None,
    source_channel_name: str = None,
    author_id: int = None,
    author_name: str = None,
    author_label: str = None,
    content: str = None,
    invite_url: str = None,
    queue_key: str = None,
    status: str = None,
    attachments: list[str] = None,
    content_links: list[str] = None,
    target_guild_ids: list[int] = None,
    target_channel_ids: list[int] = None,
    target_guild_count: int = None,
    dispatch_count: int = None,
    hidden: bool = None,
    owner_note: str = None,
    owner_action_by_id: int = None,
    owner_action_by_name: str = None,
    owner_channel_id: int = None,
    owner_message_id: int = None,
    created_at: datetime = None,
    dispatched_at: datetime = None,
    owner_action_at: datetime = None,
):
    payload = locals()
    if source_origin is not None:
        payload["source_origin"] = _normalize_source(source_origin)
    return await _store.update(payload)


async def get(
    id: int = None,
    guild_id: int = None,
    source_origin: str = None,
    source_channel_id: int = None,
    author_id: int = None,
    status: str = None,
    queue_key: str = None,
):
    payload = locals()
    if source_origin is not None:
        payload["source_origin"] = _normalize_source(source_origin)
    return await _store.get(payload)


async def gets(
    id: int = None,
    guild_id: int = None,
    source_origin: str = None,
    source_channel_id: int = None,
    author_id: int = None,
    status: str = None,
    queue_key: str = None,
):
    payload = locals()
    if source_origin is not None:
        payload["source_origin"] = _normalize_source(source_origin)
    return await _store.gets(payload)


async def delete(
    id: int = None,
    guild_id: int = None,
    source_origin: str = None,
    source_channel_id: int = None,
    author_id: int = None,
    status: str = None,
    queue_key: str = None,
):
    payload = locals()
    if source_origin is not None:
        payload["source_origin"] = _normalize_source(source_origin)
    return await _store.delete(payload)


async def get_all():
    return await _store.get_all()


async def delete_limited(limit: int, guild_id: int):
    safe_limit = max(1, int(limit or MAX_GUILD_HISTORY_RECORDS))
    try:
        guild_id_int = int(guild_id or 0)
    except Exception:
        guild_id_int = 0
    if guild_id_int <= 0:
        return []
    return await _store.delete_limited(limit=safe_limit, filters={"guild_id": guild_id_int})


async def query_recent(
    *,
    limit: int = 50,
    guild_id: int = 0,
    source_origin: str = "",
    search_text: str = "",
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(250, int(limit or 50)))
    query: dict[str, Any] = {"status": {"$ne": "deleted"}}
    if int(guild_id or 0) > 0:
        query["guild_id"] = int(guild_id)

    source_filter = _normalize_source(source_origin) if str(source_origin or "").strip() else ""
    if source_filter:
        # Legacy rows from old builds may have unknown source;
        # keep them discoverable when filtering Web.
        if source_filter == "web":
            query["source_origin"] = {"$in": ["web", "unknown"]}
        else:
            query["source_origin"] = source_filter

    search = str(search_text or "").strip()
    if search:
        terms = _search_terms(search)
        search_conditions: list[dict[str, Any]] = []
        for term in terms:
            escaped = re.escape(term)
            regex = {"$regex": escaped, "$options": "i"}
            search_conditions.extend(
                [
                    {"guild_name": regex},
                    {"author_name": regex},
                    {"author_label": regex},
                    {"source_channel_name": regex},
                    {"content": regex},
                    {"invite_url": regex},
                    {"attachments": regex},
                    {"content_links": regex},
                    {"queue_key": regex},
                ]
            )
        for number in _search_numeric_values(search, terms):
            search_conditions.extend(
                [
                    {"guild_id": number},
                    {"author_id": number},
                    {"source_channel_id": number},
                ]
            )
        if search_conditions:
            query["$or"] = search_conditions

    collection = await get_collection(COLLECTION_NAME)
    cursor = collection.find(query).sort("id", -1).limit(safe_limit)
    rows = await cursor.to_list(length=safe_limit)
    cleaned_rows: list[dict[str, Any]] = []
    for row in rows:
        cleaned = _clean_doc(row)
        if isinstance(cleaned, dict):
            cleaned_rows.append(cleaned)
    return cleaned_rows


async def recent_guild_filters(*, limit: int = 200) -> list[dict[str, Any]]:
    safe_limit = max(10, min(500, int(limit or 200)))
    collection = await get_collection(COLLECTION_NAME)
    cursor = collection.find({}, {"guild_id": 1, "guild_name": 1, "created_at": 1}).sort("id", -1).limit(safe_limit)
    rows = await cursor.to_list(length=safe_limit)
    seen: set[int] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        guild_id = int(row.get("guild_id") or 0)
        if guild_id <= 0 or guild_id in seen:
            continue
        seen.add(guild_id)
        output.append(
            {
                "guild_id": guild_id,
                "guild_name": str(row.get("guild_name") or f"Guild {guild_id}").strip() or f"Guild {guild_id}",
                "last_at": row.get("created_at"),
            }
        )
    return output


async def query_recent_latest_guild_records(
    *,
    limit: int = 50,
    source_origin: str = "",
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(200, int(limit or 50)))
    source_filter = _normalize_source(source_origin) if str(source_origin or "").strip() else ""
    query: dict[str, Any] = {"status": {"$ne": "deleted"}}
    if source_filter:
        query["source_origin"] = source_filter

    collection = await get_collection(COLLECTION_NAME)
    fetch_size = max(300, safe_limit * 30)
    cursor = collection.find(query).sort("id", -1).limit(fetch_size)
    rows = await cursor.to_list(length=fetch_size)

    seen_guilds: set[int] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        guild_id = int(row.get("guild_id") or 0)
        if guild_id <= 0 or guild_id in seen_guilds:
            continue
        cleaned = _clean_doc(row)
        if not isinstance(cleaned, dict):
            continue
        seen_guilds.add(guild_id)
        output.append(cleaned)
        if len(output) >= safe_limit:
            break
    return output
