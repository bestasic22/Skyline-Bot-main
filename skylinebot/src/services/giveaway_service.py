from __future__ import annotations

import json
import random
import re
from typing import Any

from skylinebot.memory.cache import cache

import storage.giveaway_participants as giveaway_participants_db
import storage.giveaways as giveaways_db


class GiveawayService:
    """Business helpers for giveaway command flows."""

    LIMIT_BY_SUBSCRIPTION = {
        "free": 1,
        "silver_guild_preminum": 3,
        "golden_guild_premium": 5,
        "diamond_guild_premium": 10,
        "permanent_guild_premium": 10,
        "lifetime_guild_premium": 10,
    }

    @staticmethod
    def parse_duration_to_seconds(duration: str) -> int | None:
        if not duration:
            return None
        raw = duration.lower().strip()
        matches = re.findall(r"(\d+)\s*([smhd])", raw)
        if not matches:
            return None
        unit_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        total = 0
        consumed = ""
        for value, unit in matches:
            total += int(value) * unit_map[unit]
            consumed += f"{value}{unit}"
        normalized = re.sub(r"\s+", "", raw)
        if consumed != normalized:
            return None
        return total if total > 0 else None

    @staticmethod
    def normalize_winners(winners: Any) -> list:
        if winners is None:
            return []
        if isinstance(winners, list):
            return winners
        if isinstance(winners, str):
            try:
                loaded = json.loads(winners)
                return loaded if isinstance(loaded, list) else []
            except Exception:
                return []
        return []

    @staticmethod
    def pick_winners(participants: list[dict[str, Any]], winner_limit: int) -> list[int]:
        if len(participants) == 0:
            return []
        if len(participants) < winner_limit:
            winner_limit = len(participants)
        return random.choices(
            population=[item["user_id"] for item in participants],
            weights=[item.get("winning_rate", 50) for item in participants],
            k=winner_limit,
        )

    def giveaway_limit_for_guild(self, guild_id: int) -> int:
        subscription = cache.guilds.get(str(guild_id), {}).get("subscription", "free")
        return self.LIMIT_BY_SUBSCRIPTION.get(subscription, 1)

    def cached_giveaway_map(self, guild_id: int) -> dict[str, Any]:
        return cache.giveaways.get(str(guild_id), {})

    def cached_giveaway(self, guild_id: int, giveaway_id: int) -> dict[str, Any]:
        return self.cached_giveaway_map(guild_id).get(str(giveaway_id), {})

    async def get_giveaway(self, guild_id: int, giveaway_id: int) -> dict[str, Any] | None:
        return await giveaways_db.get(guild_id=guild_id, giveaway_id=giveaway_id)

    async def delete_giveaway_and_participants(self, record: dict[str, Any]) -> None:
        await giveaways_db.delete(id=record.get("id"))
        await giveaway_participants_db.delete(
            guild_id=record.get("guild_id"),
            giveaway_id=record.get("giveaway_id"),
        )

    async def build_giveaway_snapshot(self, guild_id: int) -> list[dict[str, Any]]:
        all_giveaways = await giveaways_db.gets(guild_id=guild_id)
        if not all_giveaways:
            return []
        snapshots: list[dict[str, Any]] = []
        for giveaway in reversed(all_giveaways):
            participants = await giveaway_participants_db.gets(
                guild_id=guild_id, giveaway_id=giveaway.get("giveaway_id")
            )
            snapshots.append(
                {
                    "id": giveaway.get("id"),
                    "giveaway_id": giveaway.get("giveaway_id"),
                    "guild_id": giveaway.get("guild_id"),
                    "channel_id": giveaway.get("channel_id"),
                    "message_id": giveaway.get("message_id"),
                    "host_id": giveaway.get("host_id"),
                    "winners": giveaway.get("winners"),
                    "winner_limit": giveaway.get("winner_limit"),
                    "prize": giveaway.get("prize"),
                    "ends_at": giveaway.get("ends_at"),
                    "ended": giveaway.get("ended"),
                    "participants": participants,
                    "created_at": giveaway.get("created_at"),
                }
            )
        return snapshots
