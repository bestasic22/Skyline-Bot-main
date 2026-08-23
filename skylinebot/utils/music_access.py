from __future__ import annotations

import re
from typing import Any

_DIGIT_RE = re.compile(r"\d+")


def parse_entity_id_list(raw: Any, *, limit: int = 200) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()

    def _push(token: Any) -> None:
        text = str(token or "").strip()
        if not text:
            return
        for match in _DIGIT_RE.findall(text):
            normalized = match.lstrip("0") or "0"
            if normalized in seen:
                continue
            seen.add(normalized)
            values.append(normalized)
            if len(values) >= max(1, int(limit)):
                return

    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            _push(item)
            if len(values) >= max(1, int(limit)):
                break
        return values

    text = str(raw or "").strip()
    if not text:
        return []
    for token in re.split(r"[\s,;|]+", text):
        _push(token)
        if len(values) >= max(1, int(limit)):
            break
    return values


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_music_access_settings(source: dict[str, Any] | None) -> dict[str, Any]:
    data = source or {}
    role_ids = parse_entity_id_list(data.get("music_usage_role_ids"))
    user_ids = parse_entity_id_list(data.get("music_usage_user_ids"))
    channel_ids = parse_entity_id_list(data.get("music_usage_channel_ids"))
    return {
        "music_usage_enabled": _as_bool(data.get("music_usage_enabled"), True),
        "music_usage_admin_only": _as_bool(data.get("music_usage_admin_only"), False),
        "music_usage_restrict_enabled": _as_bool(
            data.get("music_usage_restrict_enabled"), False
        ),
        "music_usage_allow_admin_bypass": _as_bool(
            data.get("music_usage_allow_admin_bypass"), True
        ),
        "music_usage_role_ids": role_ids,
        "music_usage_user_ids": user_ids,
        "music_usage_channel_ids": channel_ids,
    }


def is_member_admin_like(member: Any | None) -> bool:
    perms = getattr(member, "guild_permissions", None)
    if not perms:
        return False
    return bool(
        getattr(perms, "administrator", False)
        or getattr(perms, "manage_guild", False)
    )


def evaluate_music_access(
    settings: dict[str, Any] | None,
    *,
    actor_user_id: int | str | None,
    actor_role_ids: list[int | str] | None = None,
    actor_channel_id: int | str | None = None,
    is_owner: bool = False,
    is_admin: bool = False,
) -> tuple[bool, str]:
    policy = normalize_music_access_settings(settings)
    can_bypass = bool(policy["music_usage_allow_admin_bypass"]) and bool(
        is_owner or is_admin
    )

    if not policy["music_usage_enabled"]:
        if can_bypass:
            return True, ""
        return False, "ระบบเพลงถูกปิดใช้งานโดยผู้ดูแลเซิร์ฟเวอร์"

    if can_bypass:
        return True, ""

    if policy["music_usage_admin_only"] and not (is_owner or is_admin):
        return False, "เฉพาะแอดมินหรือเจ้าของเซิร์ฟเวอร์เท่านั้นที่ใช้ระบบเพลงได้"

    if not policy["music_usage_restrict_enabled"]:
        return True, ""

    allowed_role_ids = set(policy["music_usage_role_ids"])
    allowed_user_ids = set(policy["music_usage_user_ids"])
    allowed_channel_ids = set(policy["music_usage_channel_ids"])

    if not allowed_role_ids and not allowed_user_ids and not allowed_channel_ids:
        return (
            False,
            "ระบบเพลงถูกจำกัดการใช้งาน แต่ยังไม่ได้ตั้งค่าผู้ใช้ บทบาท หรือห้องที่อนุญาต",
        )

    actor_user_id_text = (
        str(int(actor_user_id))
        if str(actor_user_id or "").strip().isdigit()
        else str(actor_user_id or "").strip()
    )
    if actor_user_id_text and actor_user_id_text in allowed_user_ids:
        return True, ""

    actor_channel_id_text = (
        str(int(actor_channel_id))
        if str(actor_channel_id or "").strip().isdigit()
        else str(actor_channel_id or "").strip()
    )
    if actor_channel_id_text and actor_channel_id_text in allowed_channel_ids:
        return True, ""

    role_texts = []
    for role_id in list(actor_role_ids or []):
        role_text = str(role_id or "").strip()
        if role_text.isdigit():
            role_text = str(int(role_text))
        if role_text:
            role_texts.append(role_text)
    if any(role_id in allowed_role_ids for role_id in role_texts):
        return True, ""

    return False, "คุณไม่มีสิทธิ์ใช้ระบบเพลงในเซิร์ฟเวอร์นี้"
