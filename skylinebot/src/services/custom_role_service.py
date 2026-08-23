from __future__ import annotations

from typing import Any

from skylinebot.memory.cache import cache

import storage.custom_roles as custom_roles_db


class CustomRoleService:
    """Business rules for custom role commands."""

    LIMIT_BY_SUBSCRIPTION = {
        "free": 5,
        "silver_guild_preminum": 10,
        "golden_guild_premium": 15,
        "diamond_guild_premium": 20,
        "permanent_guild_premium": 30,
        "lifetime_guild_premium": 30,
    }

    def __init__(self, bot):
        self.bot = bot

    def get_cache(self, guild_id: int) -> dict[str, Any]:
        return cache.custom_roles.get(str(guild_id), {})

    def limit_for_guild(self, guild_id: int) -> int:
        subscription = cache.guilds.get(str(guild_id), {}).get("subscription", "free")
        return self.LIMIT_BY_SUBSCRIPTION.get(subscription, 5)

    async def add(self, guild_id: int, name: str, role_id: int) -> None:
        await custom_roles_db.insert(guild_id=guild_id, name=name, role_id=role_id)

    async def remove(self, guild_id: int, name: str) -> None:
        await custom_roles_db.delete(guild_id=guild_id, name=name)

    async def update(self, *, record_id: int, guild_id: int, name: str, role_id: int) -> None:
        await custom_roles_db.update(id=record_id, guild_id=guild_id, name=name, role_id=role_id)

    async def delete_if_missing_role(self, guild_id: int, name: str) -> None:
        await custom_roles_db.delete(guild_id=guild_id, name=name)
