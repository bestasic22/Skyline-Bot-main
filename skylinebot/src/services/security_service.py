from __future__ import annotations

import json
from typing import Any

from skylinebot.memory.cache import cache

import storage.antinuke_bypass as antinuke_bypass_db
import storage.antinuke_settings as antinuke_settings_db
import storage.guilds as guilds_db


class SecurityService:
    """Shared persistence/business logic for security commands."""

    WHITELIST_LIMIT = 50
    EXTRA_OWNER_LIMIT_BY_SUBSCRIPTION = {
        "free": 1,
        "silver_guild_preminum": 5,
        "golden_guild_premium": 10,
        "diamond_guild_premium": 20,
        "permanent_guild_premium": 20,
        "lifetime_guild_premium": 20,
    }

    def __init__(self, bot):
        self.bot = bot
        self.whitelist_rule_keys = [
            f"anti_{rule_name}" for rule_name in antinuke_settings_db.RULE_NAMES
        ]

    def get_whitelist_cache(self, guild_id: int) -> dict[str, Any]:
        return cache.antinuke_bypass.get(str(guild_id), {})

    def get_whitelist_user(self, guild_id: int, user_id: int) -> dict[str, Any] | None:
        return self.get_whitelist_cache(guild_id).get(str(user_id))

    def whitelist_count(self, guild_id: int) -> int:
        return len(self.get_whitelist_cache(guild_id))

    async def add_whitelist_user(self, guild_id: int, user_id: int) -> dict[str, Any]:
        await antinuke_bypass_db.insert(guild_id=guild_id, user_id=user_id)
        return self.get_whitelist_user(guild_id, user_id) or {}

    async def remove_whitelist_user(self, guild_id: int, user_id: int) -> None:
        await antinuke_bypass_db.delete(guild_id=guild_id, user_id=user_id)

    async def set_all_whitelist_permissions(
        self, guild_id: int, user_id: int, enabled: bool
    ) -> dict[str, Any]:
        entry = self.get_whitelist_user(guild_id, user_id) or {}
        await antinuke_bypass_db.update(
            id=entry.get("id"),
            guild_id=guild_id,
            user_id=user_id,
            **{key: enabled for key in self.whitelist_rule_keys},
        )
        return self.get_whitelist_user(guild_id, user_id) or {}

    async def toggle_whitelist_permission(
        self, guild_id: int, user_id: int, rule_key: str
    ) -> dict[str, Any]:
        if rule_key not in self.whitelist_rule_keys:
            raise ValueError(f"Unknown whitelist permission: {rule_key}")
        entry = self.get_whitelist_user(guild_id, user_id) or {}
        await antinuke_bypass_db.update(
            id=entry.get("id"),
            guild_id=guild_id,
            user_id=user_id,
            **{rule_key: not bool(entry.get(rule_key))},
        )
        return self.get_whitelist_user(guild_id, user_id) or {}

    async def ensure_guild_record(self, guild_id: int) -> dict[str, Any]:
        existing = cache.guilds.get(str(guild_id), {})
        if existing:
            return existing
        await guilds_db.insert(guild_id=guild_id)
        return cache.guilds.get(str(guild_id), {})

    @staticmethod
    def parse_extra_owner_ids(guild_record: dict[str, Any]) -> list[str]:
        raw = guild_record.get("extra_owner_ids", "[]")
        if isinstance(raw, list):
            return [str(item) for item in raw]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                return []
        return []

    async def save_extra_owner_ids(self, guild_record: dict[str, Any], owner_ids: list[str]) -> None:
        await guilds_db.update(
            id=guild_record.get("id"),
            extra_owner_ids=json.dumps([str(item) for item in owner_ids]),
        )

    def extra_owner_limit_for(self, subscription_name: str) -> int:
        return self.EXTRA_OWNER_LIMIT_BY_SUBSCRIPTION.get(subscription_name, 1)
