from __future__ import annotations

from typing import Any

from skylinebot.memory.cache import cache

import storage.welcomer_settings as welcomer_settings_db


class WelcomerRepository:
    """Repository facade for welcomer settings with cache-first semantics."""

    def __init__(self, bot):
        self.bot = bot

    async def ensure_settings(self, guild_id: int) -> dict[str, Any]:
        existing = cache.welcomer_settings.get(str(guild_id), {})
        if existing:
            return existing
        await welcomer_settings_db.insert(guild_id=guild_id)
        return cache.welcomer_settings.get(str(guild_id), {})

    async def get_settings(self, guild_id: int) -> dict[str, Any]:
        return await self.ensure_settings(guild_id)

    async def update_settings(self, guild_id: int, **patch: Any) -> dict[str, Any]:
        current = await self.ensure_settings(guild_id)
        if not current:
            return {}
        await welcomer_settings_db.update(id=current.get("id"), **patch)
        return await self.ensure_settings(guild_id)

    async def update_by_id(self, settings_id: int, **patch: Any) -> dict[str, Any] | None:
        if settings_id is None:
            return None
        return await welcomer_settings_db.update(id=settings_id, **patch)
