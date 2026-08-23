from __future__ import annotations

import os
import re
from typing import Any, Iterable
from urllib.parse import urlparse


def format_ms(ms: int | float | None) -> str:
    total_seconds = max(0, int((ms or 0) / 1000))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def first_env_value(*keys: str) -> str:
    for key in keys:
        value = str(os.getenv(str(key), "")).strip()
        if value:
            return value
    return ""


def bool_from_form(data: dict[str, str], key: str) -> bool:
    return data.get(key) == "on"


def int_from_form(data: dict[str, str], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(data.get(key, default) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def parse_trusted_server_order(raw: str | None) -> list[str]:
    if not isinstance(raw, str):
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_guild_id_list(raw: str | None, *, max_items: int = 200) -> list[str]:
    if not isinstance(raw, str):
        return []
    out: list[str] = []
    for item in re.split(r"[\s,\n\r\t]+", raw):
        guild_id = str(item or "").strip()
        if not guild_id or not guild_id.isdigit() or guild_id in out:
            continue
        out.append(guild_id)
        if len(out) >= max_items:
            break
    return out


def parse_command_name_list(raw: str | None, *, max_items: int = 400) -> list[str]:
    if not isinstance(raw, str):
        return []
    out: list[str] = []
    for item in re.split(r"[\n,]+", raw):
        name = str(item or "").strip().lower()
        if not name:
            continue
        if name.startswith("/"):
            name = name[1:].strip()
        if not name or name in out:
            continue
        out.append(name)
        if len(out) >= max_items:
            break
    return out


def parse_tab_slug_list(
    raw: str | None,
    *,
    allowed_tabs: Iterable[str],
    max_items: int = 100,
) -> list[str]:
    if not isinstance(raw, str):
        return []
    allowed = set(str(item or "").strip().lower() for item in allowed_tabs if str(item or "").strip())
    out: list[str] = []
    for item in re.split(r"[\n,]+", raw):
        slug = str(item or "").strip().lower()
        if not slug or slug not in allowed or slug in out:
            continue
        out.append(slug)
        if len(out) >= max_items:
            break
    return out


def normalize_http_url(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not (parsed.hostname or "").strip():
        return ""
    return value
