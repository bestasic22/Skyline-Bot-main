from __future__ import annotations

from typing import Any

from skylinebot.memory.cache import cache

import storage.antinuke_settings as antinuke_settings_db


class AntiNukeService:
    """Service facade for antinuke persistence and cache-safe mutations."""

    def __init__(self, bot):
        self.bot = bot
        self.rule_keys = [f"anti_{rule_name}" for rule_name in antinuke_settings_db.RULE_NAMES]

    async def ensure_settings(self, guild_id: int) -> dict[str, Any]:
        existing = cache.antinuke_settings.get(str(guild_id), {})
        if existing:
            return existing
        created = await antinuke_settings_db.insert(guild_id=guild_id)
        return created or cache.antinuke_settings.get(str(guild_id), {})

    async def set_enabled(self, guild_id: int, enabled: bool) -> dict[str, Any]:
        settings = await self.ensure_settings(guild_id)
        if settings.get("enabled") == enabled:
            return settings
        updated = await antinuke_settings_db.update(settings.get("id"), enabled=enabled)
        return updated or await self.ensure_settings(guild_id)

    async def apply_profile(self, guild_id: int, profile_name: str) -> dict[str, Any]:
        if str(profile_name).lower().strip() == "extream":
            profile_name = "extreme"
        settings = await self.ensure_settings(guild_id)
        await antinuke_settings_db.change_antinuke_settings_type(settings, profile_name)
        return await self.ensure_settings(guild_id)

    async def patch_rules(self, guild_id: int, **patch: Any) -> dict[str, Any]:
        settings = await self.ensure_settings(guild_id)
        updated = await antinuke_settings_db.update(settings.get("id"), **patch)
        return updated or await self.ensure_settings(guild_id)

    def are_all_modules_enabled(self, settings: dict[str, Any]) -> bool:
        return all(bool(settings.get(key)) for key in self.rule_keys)

    async def set_all_modules(self, guild_id: int, enabled: bool) -> dict[str, Any]:
        patch = {key: enabled for key in self.rule_keys}
        return await self.patch_rules(guild_id, **patch)
