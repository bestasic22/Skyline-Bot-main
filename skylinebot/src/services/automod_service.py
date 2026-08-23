from __future__ import annotations

from typing import Any

from skylinebot.memory.cache import cache

import storage.automod as automod_db


class AutoModService:
    """Shared automod mutations to avoid duplicated command flow logic."""

    def __init__(self, bot):
        self.bot = bot

    async def ensure_settings(self, guild_id: int) -> dict[str, Any]:
        existing = cache.automod.get(str(guild_id), {})
        if existing:
            return existing
        await automod_db.insert(guild_id=guild_id)
        return cache.automod.get(str(guild_id), {})

    async def sync_rule_state(self, guild, rule_id: Any, enabled: bool) -> bool:
        if not rule_id:
            return False
        try:
            rule = await guild.fetch_automod_rule(int(rule_id))
            await rule.edit(enabled=enabled)
            return enabled
        except Exception:
            return False

    async def set_core_state(self, guild, *, antispam: bool) -> dict[str, Any]:
        settings = await self.ensure_settings(guild.id)
        antilink_state = settings.get("antilink_enabled", False)
        antibadwords_state = settings.get("antibadwords_enabled", False)

        if settings.get("antilink_rule_id"):
            synced = await self.sync_rule_state(
                guild, settings.get("antilink_rule_id"), antispam
            )
            if synced in {True, False}:
                antilink_state = synced

        if settings.get("antibadwords_rule_id"):
            synced = await self.sync_rule_state(
                guild, settings.get("antibadwords_rule_id"), antispam
            )
            if synced in {True, False}:
                antibadwords_state = synced

        await automod_db.update(
            id=settings.get("id"),
            guild_id=guild.id,
            antispam_enabled=antispam,
            antilink_enabled=antilink_state,
            antibadwords_enabled=antibadwords_state,
        )
        return await self.ensure_settings(guild.id)

    async def set_module_state(
        self,
        guild,
        *,
        module_enabled_field: str,
        module_rule_id_field: str,
        enabled: bool,
    ) -> dict[str, Any]:
        settings = await self.ensure_settings(guild.id)
        await self.sync_rule_state(guild, settings.get(module_rule_id_field), enabled)
        await automod_db.update(
            id=settings.get("id"),
            guild_id=guild.id,
            **{module_enabled_field: enabled},
        )
        return await self.ensure_settings(guild.id)
