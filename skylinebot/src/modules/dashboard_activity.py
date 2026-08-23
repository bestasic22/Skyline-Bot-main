from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any

import storage


CONFIG_KEY_PREFIX = "guild_activity_history_v1_"
MAX_BUCKETS = 24 * 400
BUCKET_SECONDS = 3600
BUCKET_MS = BUCKET_SECONDS * 1000
MESSAGE_FLUSH_THRESHOLD = 25
FLUSH_INTERVAL_SECONDS = 18

_history_cache: dict[int, list[dict[str, int]]] = {}
_loaded_guild_ids: set[int] = set()
_locks: dict[int, asyncio.Lock] = {}
_last_saved_monotonic: dict[int, float] = {}
_unsaved_message_events: dict[int, int] = {}


def _config_key(guild_id: int) -> str:
    return f"{CONFIG_KEY_PREFIX}{int(guild_id)}"


def _utc_now_ms() -> int:
    return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)


def _bucket_ts_ms(ts_ms: int) -> int:
    ts_ms = max(0, int(ts_ms or 0))
    return ts_ms - (ts_ms % BUCKET_MS)


def _normalize_history(raw: Any) -> list[dict[str, int]]:
    payload = raw
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = []
    if isinstance(payload, dict):
        payload = payload.get("buckets") if isinstance(payload.get("buckets"), list) else []
    if not isinstance(payload, list):
        return []

    normalized: list[dict[str, int]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            ts = _bucket_ts_ms(int(row.get("ts") or 0))
            joins = max(0, int(row.get("joins") or 0))
            leaves = max(0, int(row.get("leaves") or 0))
            messages = max(0, int(row.get("messages") or 0))
        except Exception:
            continue
        if ts <= 0:
            continue
        item: dict[str, int] = {
            "ts": ts,
            "joins": joins,
            "leaves": leaves,
            "messages": messages,
        }
        member_count_raw = row.get("member_count")
        if member_count_raw is not None:
            try:
                member_count = max(0, int(member_count_raw))
            except Exception:
                member_count = None
            if member_count is not None:
                item["member_count"] = member_count
        normalized.append(item)

    normalized.sort(key=lambda x: int(x.get("ts") or 0))
    compact: list[dict[str, int]] = []
    for row in normalized:
        if compact and compact[-1]["ts"] == row["ts"]:
            compact[-1]["joins"] += row["joins"]
            compact[-1]["leaves"] += row["leaves"]
            compact[-1]["messages"] += row["messages"]
            if "member_count" in row:
                compact[-1]["member_count"] = row["member_count"]
        else:
            compact.append(dict(row))

    return compact[-MAX_BUCKETS:]


def _guild_lock(guild_id: int) -> asyncio.Lock:
    lock = _locks.get(guild_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[guild_id] = lock
    return lock


async def _persist_history(guild_id: int) -> None:
    rows = _history_cache.get(guild_id, [])
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    config_key = _config_key(guild_id)
    try:
        current = await storage.dashboard_config.get(config_key=config_key)
    except Exception:
        current = None

    if current:
        await storage.dashboard_config.update(id=current["id"], config_value=encoded)
    else:
        await storage.dashboard_config.insert(config_key=config_key, config_value=encoded)

    _last_saved_monotonic[guild_id] = asyncio.get_running_loop().time()
    _unsaved_message_events[guild_id] = 0


async def ensure_loaded(guild_id: int) -> None:
    guild_id = int(guild_id)
    if guild_id in _loaded_guild_ids:
        return

    lock = _guild_lock(guild_id)
    async with lock:
        if guild_id in _loaded_guild_ids:
            return
        raw_value: Any = "[]"
        try:
            row = await storage.dashboard_config.get(config_key=_config_key(guild_id))
            raw_value = (row or {}).get("config_value") or "[]"
        except Exception:
            raw_value = "[]"
        _history_cache[guild_id] = _normalize_history(raw_value)
        _loaded_guild_ids.add(guild_id)
        _last_saved_monotonic.setdefault(guild_id, 0.0)
        _unsaved_message_events.setdefault(guild_id, 0)


def get_history(guild_id: int) -> list[dict[str, int]]:
    guild_id = int(guild_id)
    rows = _history_cache.get(guild_id, [])
    return [dict(item) for item in rows]


async def record_event(
    guild_id: int,
    kind: str,
    *,
    count: int = 1,
    member_count: int | None = None,
    ts_ms: int | None = None,
) -> None:
    guild_id = int(guild_id)
    kind = str(kind or "").strip().lower()
    if kind not in {"message", "join", "leave", "snapshot"}:
        return

    amount = max(0, int(count or 0))
    if kind != "snapshot" and amount <= 0:
        return

    await ensure_loaded(guild_id)
    lock = _guild_lock(guild_id)
    async with lock:
        rows = list(_history_cache.get(guild_id, []))
        event_ts_ms = _bucket_ts_ms(int(ts_ms or _utc_now_ms()))

        if rows and rows[-1]["ts"] == event_ts_ms:
            bucket = rows[-1]
        else:
            bucket = {"ts": event_ts_ms, "joins": 0, "leaves": 0, "messages": 0}
            rows.append(bucket)

        if kind == "message":
            bucket["messages"] = int(bucket.get("messages") or 0) + amount
            _unsaved_message_events[guild_id] = int(_unsaved_message_events.get(guild_id, 0) or 0) + amount
        elif kind == "join":
            bucket["joins"] = int(bucket.get("joins") or 0) + amount
        elif kind == "leave":
            bucket["leaves"] = int(bucket.get("leaves") or 0) + amount

        if member_count is not None:
            try:
                safe_member_count = max(0, int(member_count))
            except Exception:
                safe_member_count = None
            if safe_member_count is not None:
                bucket["member_count"] = safe_member_count

        rows = _normalize_history(rows)
        _history_cache[guild_id] = rows

        force_flush = kind in {"join", "leave", "snapshot"}
        if not force_flush:
            loop_now = asyncio.get_running_loop().time()
            last_saved = float(_last_saved_monotonic.get(guild_id, 0.0) or 0.0)
            pending_messages = int(_unsaved_message_events.get(guild_id, 0) or 0)
            force_flush = (
                pending_messages >= MESSAGE_FLUSH_THRESHOLD
                or (loop_now - last_saved) >= FLUSH_INTERVAL_SECONDS
            )

        if force_flush:
            try:
                await _persist_history(guild_id)
            except Exception:
                pass


async def record_join(guild_id: int, *, member_count: int | None = None) -> None:
    await record_event(guild_id, "join", member_count=member_count)


async def record_leave(guild_id: int, *, member_count: int | None = None) -> None:
    await record_event(guild_id, "leave", member_count=member_count)


async def record_message(guild_id: int) -> None:
    await record_event(guild_id, "message")


async def record_member_snapshot(guild_id: int, member_count: int) -> None:
    await record_event(guild_id, "snapshot", member_count=member_count)
