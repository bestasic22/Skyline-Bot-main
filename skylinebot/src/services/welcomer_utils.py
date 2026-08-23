from __future__ import annotations

import json
from typing import Any

import requests


def unescape_newlines(text: str) -> str:
    return str(text).replace(r"\n", "\n")


def is_valid_image_url(url: str) -> bool:
    try:
        normalized = str(url or "").strip()
        if normalized.lower() in {"{user.avatar}", "{guild.icon}", "{server.icon}"}:
            return True
        response = requests.head(normalized, timeout=5)
        content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
        return content_type in {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
    except Exception:
        return False


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            if isinstance(loaded, list):
                return loaded
        except Exception:
            return []
    return []


def channel_mentions(channel_ids: Any) -> str:
    ids = parse_json_list(channel_ids)
    mentions = [f"<#{int(ch)}>" for ch in ids if str(ch).isdigit()]
    return ", ".join(mentions) if mentions else "`No channel set`"
