from __future__ import annotations

from typing import Any

from .plan_utils import normalize_plan_tier

VERIFY_LIMITS_BY_TIER: dict[str, dict[str, int]] = {
    "free": {"max_pages": 1, "max_items_per_page": 3, "title_max_length": 24},
    "silver": {"max_pages": 1, "max_items_per_page": 6, "title_max_length": 30},
    "golden": {"max_pages": 1, "max_items_per_page": 9, "title_max_length": 40},
    "diamond": {"max_pages": 1, "max_items_per_page": 12, "title_max_length": 45},
    "permanent": {"max_pages": 1, "max_items_per_page": 15, "title_max_length": 60},
}

LEVELS_PLAN_CAPS: dict[str, dict[str, Any]] = {
    "free": {
        "can_use": False,
        "text_xp": False,
        "voice_xp": False,
        "command_xp": False,
        "reaction_xp": False,
        "max_rewards": 0,
        "max_level": 50,
        "max_notify_len": 120,
    },
    "silver": {
        "can_use": True,
        "text_xp": True,
        "voice_xp": False,
        "command_xp": True,
        "reaction_xp": False,
        "max_rewards": 3,
        "max_level": 120,
        "max_notify_len": 180,
    },
    "golden": {
        "can_use": True,
        "text_xp": True,
        "voice_xp": True,
        "command_xp": True,
        "reaction_xp": False,
        "max_rewards": 8,
        "max_level": 200,
        "max_notify_len": 300,
    },
    "diamond": {
        "can_use": True,
        "text_xp": True,
        "voice_xp": True,
        "command_xp": True,
        "reaction_xp": True,
        "max_rewards": 20,
        "max_level": 500,
        "max_notify_len": 600,
    },
    "permanent": {
        "can_use": True,
        "text_xp": True,
        "voice_xp": True,
        "command_xp": True,
        "reaction_xp": True,
        "max_rewards": 30,
        "max_level": 1000,
        "max_notify_len": 900,
    },
}


def verify_limits_by_tier(plan_tier: str) -> dict[str, int]:
    selected = VERIFY_LIMITS_BY_TIER.get(plan_tier, VERIFY_LIMITS_BY_TIER["free"])
    return dict(selected)


def verify_limits_from_guild_state(guild_state: dict[str, Any]) -> dict[str, int]:
    tier = normalize_plan_tier(guild_state.get("subscription", "free"))
    return verify_limits_by_tier(tier)


def levels_plan_caps(plan_tier: str) -> dict[str, Any]:
    tier = str(plan_tier or "free").strip().lower()
    selected = LEVELS_PLAN_CAPS.get(tier, LEVELS_PLAN_CAPS["free"])
    return dict(selected)
