from __future__ import annotations

import datetime
import json
from typing import Any

import storage


CONFIG_KEY = "guild_growth_history_v1"
MAX_EVENTS = 4000
_history_cache: list[dict[str, int]] = []
_loaded = False


def _normalize_events(raw: Any) -> list[dict[str, int]]:
    out: list[dict[str, int]] = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            ts = int(item.get("ts") or 0)
            count = int(item.get("count") or 0)
        except Exception:
            continue
        if ts <= 0:
            continue
        out.append({"ts": ts, "count": max(0, count)})
    out.sort(key=lambda e: e["ts"])
    merged: list[dict[str, int]] = []
    for event in out:
        if merged and merged[-1]["ts"] == event["ts"]:
            merged[-1] = event
        else:
            merged.append(event)
    return merged[-MAX_EVENTS:]


async def ensure_loaded() -> None:
    global _loaded, _history_cache
    if _loaded:
        return
    try:
        row = await storage.dashboard_config.get(config_key=CONFIG_KEY)
        raw_value = (row or {}).get("config_value") or "[]"
    except Exception:
        raw_value = "[]"
    _history_cache = _normalize_events(raw_value)
    _loaded = True


def get_history(current_count: int | None = None) -> list[dict[str, int]]:
    events = list(_history_cache)
    if current_count is None:
        return events
    now_ms = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)
    current = max(0, int(current_count))
    if not events:
        return [{"ts": now_ms, "count": current}]
    last = events[-1]
    if int(last.get("count") or 0) != current or int(last.get("ts") or 0) != now_ms:
        events.append({"ts": now_ms, "count": current})
    return events[-MAX_EVENTS:]


async def record_snapshot(current_count: int, *, source: str = "runtime") -> None:
    global _history_cache
    del source
    await ensure_loaded()
    now_ms = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)
    count = max(0, int(current_count))
    events = list(_history_cache)

    if events:
        last = events[-1]
        last_count = int(last.get("count") or 0)
        last_ts = int(last.get("ts") or 0)
        unchanged_recent = (last_count == count) and ((now_ms - last_ts) < (20 * 60 * 1000))
        if unchanged_recent:
            return
    events.append({"ts": now_ms, "count": count})
    events = _normalize_events(events)[-MAX_EVENTS:]

    config_value = json.dumps(events, ensure_ascii=False)
    try:
        existing = await storage.dashboard_config.get(config_key=CONFIG_KEY)
        if existing:
            await storage.dashboard_config.update(id=existing["id"], config_value=config_value)
        else:
            await storage.dashboard_config.insert(config_key=CONFIG_KEY, config_value=config_value)
    except Exception:
        return
    _history_cache = events
