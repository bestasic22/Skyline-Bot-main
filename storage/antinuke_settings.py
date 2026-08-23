from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from skylinebot.console.logging import logger

from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "antinuke_settings"
CollectionName = COLLECTION_NAME

RULE_NAMES = [
    "channel_create",
    "channel_delete",
    "channel_update",
    "role_create",
    "role_delete",
    "role_update",
    "member_ban",
    "member_unban",
    "member_kick",
    "member_update",
    "bot_add",
    "invite_delete",
    "webhook_create",
    "webhook_delete",
    "webhook_update",
    "server_update",
    "emote_create",
    "emote_delete",
    "emote_update",
    "prune_member",
    "everyone_mention",
]


def _default_rules() -> dict[str, dict[str, Any]]:
    rules = {
        name: {"enabled": False, "limit": 1, "punishment": "kick"} for name in RULE_NAMES
    }
    rules["everyone_mention"]["punishment"] = "mute"
    return rules


def _normal_rules() -> dict[str, dict[str, Any]]:
    rules = {name: {"enabled": True, "limit": 3, "punishment": "kick"} for name in RULE_NAMES}
    rules["bot_add"]["limit"] = 2
    rules["everyone_mention"]["limit"] = 1
    rules["everyone_mention"]["punishment"] = "mute"
    return rules


def _extreme_rules() -> dict[str, dict[str, Any]]:
    rules = {name: {"enabled": True, "limit": 1, "punishment": "ban"} for name in RULE_NAMES}
    rules["everyone_mention"]["punishment"] = "kick"
    return rules


PROFILE_BUILDERS = {
    "normal": _normal_rules,
    "extreme": _extreme_rules,
}

DEFAULT_RULES = _default_rules()


def _now_unix_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _coerce_unix_ts(value: Any) -> int:
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return max(0, int(parsed.timestamp()))
    try:
        parsed = int(float(str(value).strip()))
    except Exception:
        return 0
    return max(0, parsed)


def _rule_flag_key(rule_name: str) -> str:
    return f"anti_{rule_name}"


def _rule_limit_key(rule_name: str) -> str:
    return f"anti_{rule_name}_limit"


def _rule_punishment_key(rule_name: str) -> str:
    return f"anti_{rule_name}_punishment"


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "on"}:
            return True
        if lowered in {"false", "no", "0", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_limit(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _normalize_rules(raw_rules: Any) -> dict[str, dict[str, Any]]:
    rules = deepcopy(DEFAULT_RULES)
    if not isinstance(raw_rules, dict):
        return rules

    for rule_name in RULE_NAMES:
        incoming = raw_rules.get(rule_name)
        if not isinstance(incoming, dict):
            continue
        current = rules[rule_name]
        current["enabled"] = _coerce_bool(incoming.get("enabled"), current["enabled"])
        current["limit"] = _coerce_limit(incoming.get("limit"), current["limit"])
        punishment = incoming.get("punishment")
        if isinstance(punishment, str) and punishment.strip():
            current["punishment"] = punishment.strip().lower()
    return rules


def _rules_to_flat(rules: dict[str, dict[str, Any]]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for rule_name in RULE_NAMES:
        config = rules.get(rule_name, {})
        flat[_rule_flag_key(rule_name)] = _coerce_bool(config.get("enabled"), False)
        flat[_rule_limit_key(rule_name)] = _coerce_limit(config.get("limit"), 1)
        punishment = config.get("punishment", "kick")
        flat[_rule_punishment_key(rule_name)] = (
            punishment.strip().lower() if isinstance(punishment, str) and punishment.strip() else "kick"
        )
    return flat


def _legacy_fields_to_rules(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules = deepcopy(DEFAULT_RULES)
    for rule_name in RULE_NAMES:
        rules[rule_name] = {
            "enabled": _coerce_bool(document.get(_rule_flag_key(rule_name)), rules[rule_name]["enabled"]),
            "limit": _coerce_limit(document.get(_rule_limit_key(rule_name)), rules[rule_name]["limit"]),
            "punishment": str(
                document.get(_rule_punishment_key(rule_name), rules[rule_name]["punishment"])
            ).lower(),
        }
    return rules


def _resolve_rules(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if isinstance(document.get("rules"), dict):
        return _normalize_rules(document.get("rules"))
    return _legacy_fields_to_rules(document)


def _extract_rule_patch(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    patch: dict[str, dict[str, Any]] = {}
    for key, value in payload.items():
        if not key.startswith("anti_"):
            continue

        rule_name: str | None = None
        target_field: str | None = None

        if key.endswith("_punishment"):
            rule_name = key[5:-11]
            target_field = "punishment"
        elif key.endswith("_limit"):
            rule_name = key[5:-6]
            target_field = "limit"
        else:
            rule_name = key[5:]
            target_field = "enabled"

        if rule_name not in RULE_NAMES:
            continue

        if rule_name not in patch:
            patch[rule_name] = {}
        patch[rule_name][target_field] = value
    return patch


def _prepare_payload_for_write(
    payload: dict[str, Any], current: dict[str, Any] | None = None
) -> dict[str, Any]:
    prepared = dict(payload)
    if str(prepared.get("type", "")).lower().strip() == "extream":
        prepared["type"] = "extreme"
    rule_patch = _extract_rule_patch(prepared)
    has_rule_input = "rules" in prepared or bool(rule_patch)

    if not has_rule_input:
        return prepared

    if current:
        rules = _resolve_rules(current)
    else:
        rules = deepcopy(DEFAULT_RULES)

    if "rules" in prepared:
        rules = _normalize_rules(prepared.get("rules"))

    for rule_name, changes in rule_patch.items():
        target = rules.setdefault(rule_name, deepcopy(DEFAULT_RULES[rule_name]))
        if "enabled" in changes:
            target["enabled"] = _coerce_bool(changes["enabled"], target["enabled"])
        if "limit" in changes:
            target["limit"] = _coerce_limit(changes["limit"], target["limit"])
        if "punishment" in changes:
            punishment = changes["punishment"]
            if isinstance(punishment, str) and punishment.strip():
                target["punishment"] = punishment.strip().lower()

    prepared["rules"] = rules
    prepared.update(_rules_to_flat(rules))
    return prepared


def _normalize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return document
    normalized = dict(document)
    rules = _resolve_rules(normalized)
    normalized["rules"] = rules
    normalized.update(_rules_to_flat(rules))
    armed_at_ts = _coerce_unix_ts(normalized.get("anti_bot_add_armed_at_ts"))
    if armed_at_ts <= 0 and _coerce_bool(normalized.get("anti_bot_add"), False):
        armed_at_ts = _coerce_unix_ts(normalized.get("created_at"))
    normalized["anti_bot_add_armed_at_ts"] = armed_at_ts
    if normalized.get("type") not in {"normal", "extreme", "custom"}:
        normalized["type"] = "custom"
    return normalized


_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "enabled": False,
        "type": "normal",
        "rules": deepcopy(DEFAULT_RULES),
        **_rules_to_flat(DEFAULT_RULES),
        "anti_bot_add_armed_at_ts": 0,
        "created_at": NOW,
    },
    unique_sets=[["guild_id"]],
    json_fields={"rules"},
    datetime_fields={"created_at"},
    sequence_fields={},
    update_cache=("antinuke_settings_cache", ["guild_id"]),
    delete_cache=("antinuke_settings_cache", ["guild_id"]),
)


async def create_table():
    return await _store.prepare()


async def insert(**payload):
    prepared = _prepare_payload_for_write(payload)
    if _coerce_bool(prepared.get("anti_bot_add"), False):
        if _coerce_unix_ts(prepared.get("anti_bot_add_armed_at_ts")) <= 0:
            prepared["anti_bot_add_armed_at_ts"] = _now_unix_ts()
    row = await _store.insert(prepared)
    return _normalize_document(row)


async def update(id: int | None = None, **payload):
    prepared = dict(payload)
    if id is not None:
        prepared["id"] = id
    if prepared.get("id") is None:
        raise ValueError("antinuke_settings.update requires id")

    current = await _store.get({"id": prepared["id"]})
    prepared = _prepare_payload_for_write(prepared, current=current)
    previous_bot_add_enabled = _coerce_bool((current or {}).get("anti_bot_add"), False)
    next_bot_add_enabled = _coerce_bool(prepared.get("anti_bot_add"), previous_bot_add_enabled)
    current_armed_at = _coerce_unix_ts((current or {}).get("anti_bot_add_armed_at_ts"))
    next_armed_at = _coerce_unix_ts(prepared.get("anti_bot_add_armed_at_ts"))

    if next_bot_add_enabled:
        if (not previous_bot_add_enabled) or (next_armed_at <= 0 and current_armed_at <= 0):
            prepared["anti_bot_add_armed_at_ts"] = _now_unix_ts()
    else:
        prepared["anti_bot_add_armed_at_ts"] = 0

    row = await _store.update(prepared)
    return _normalize_document(row)


async def get(**filters):
    row = await _store.get(filters)
    return _normalize_document(row)


async def gets(**filters):
    rows = await _store.gets(filters)
    return [_normalize_document(row) for row in rows]


async def delete(**filters):
    rows = await _store.delete(filters)
    return [_normalize_document(row) for row in rows]


async def get_all():
    rows = await _store.get_all()
    return [_normalize_document(row) for row in rows]


async def change_antinuke_settings_type(cache_antinuke_settings: dict, new_type: str):
    requested = str(new_type or "").lower().strip()
    if requested == "extream":
        requested = "extreme"
    if requested not in {"normal", "extreme", "custom"}:
        return logger.warning(
            f"Invalid type {requested} selected for guild {cache_antinuke_settings.get('guild_id')}"
        )

    if requested == "custom":
        await update(cache_antinuke_settings.get("id"), type="custom")
        return logger.info(
            f"Custom anti-nuke profile selected for guild {cache_antinuke_settings.get('guild_id')}"
        )

    profile_rules = PROFILE_BUILDERS[requested]()
    await update(cache_antinuke_settings.get("id"), type=requested, rules=profile_rules)
    return logger.info(
        f"{requested.capitalize()} anti-nuke profile selected for guild {cache_antinuke_settings.get('guild_id')}"
    )
