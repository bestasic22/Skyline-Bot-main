from __future__ import annotations

import datetime
from typing import Any

PLAN_ORDER: tuple[str, ...] = ("free", "silver", "golden", "diamond", "permanent")

PLAN_DISPLAY_NAMES: dict[str, str] = {
    "free": "Free",
    "silver": "Silver",
    "golden": "Gole",
    "diamond": "Diamond",
    "permanent": "Permanent",
}

PLAN_LIMITS_BY_TIER: dict[str, dict[str, int]] = {
    "free": {
        "custom_roles": 5,
        "auto_responders": 5,
        "autoroles": 3,
        "server_stats_channels": 4,
        "reaction_roles": 10,
        "music_user_playlists": 5,
        "music_playlist_items": 25,
    },
    "silver": {
        "custom_roles": 10,
        "auto_responders": 10,
        "autoroles": 5,
        "server_stats_channels": 6,
        "reaction_roles": 30,
        "music_user_playlists": 10,
        "music_playlist_items": 35,
    },
    "golden": {
        "custom_roles": 15,
        "auto_responders": 15,
        "autoroles": 10,
        "server_stats_channels": 8,
        "reaction_roles": 60,
        "music_user_playlists": 15,
        "music_playlist_items": 45,
    },
    "diamond": {
        "custom_roles": 20,
        "auto_responders": 20,
        "autoroles": 15,
        "server_stats_channels": 9,
        "reaction_roles": 100,
        "music_user_playlists": 20,
        "music_playlist_items": 50,
    },
    "permanent": {
        "custom_roles": 30,
        "auto_responders": 30,
        "autoroles": 20,
        "server_stats_channels": 12,
        "reaction_roles": 150,
        "music_user_playlists": 25,
        "music_playlist_items": 50,
    },
}

_PLAN_NORMALIZE_MAP: dict[str, str] = {
    "free": "free",
    "basic": "free",
    "silver": "silver",
    "silver_guild_preminum": "silver",
    "silver_guild_premium": "silver",
    "premium_silver": "silver",
    "gold": "golden",
    "gole": "golden",
    "golden": "golden",
    "golden_guild_premium": "golden",
    "gole_guild_premium": "golden",
    "pro": "golden",
    "diamond": "diamond",
    "diamond_guild_premium": "diamond",
    "ultra": "diamond",
    "permanent": "permanent",
    "lifetime": "permanent",
    "forever": "permanent",
    "perm": "permanent",
    "permanent_guild_premium": "permanent",
    "lifetime_guild_premium": "permanent",
    "permanent_guild_preminum": "permanent",
    "lifetime_guild_preminum": "permanent",
}

_PREMIUM_PREFIX_MAP: dict[str, str] = {
    "music settings": "silver",
    "customrole add": "free",
    "autoresponder add": "free",
    "setup antinuke custom": "silver",
}


def is_premium_subscription(raw_value: Any) -> bool:
    normalized = str(raw_value or "free").strip().lower()
    return normalized not in {"", "free", "none", "basic"}


def normalize_plan_tier(raw_value: Any) -> str:
    normalized = str(raw_value or "free").strip().lower().replace(" ", "_")
    return _PLAN_NORMALIZE_MAP.get(normalized, "free")


def plan_display_name(raw_value: Any) -> str:
    return PLAN_DISPLAY_NAMES.get(normalize_plan_tier(raw_value), "Free")


def plan_rank(raw_value: Any) -> int:
    tier = normalize_plan_tier(raw_value)
    try:
        return PLAN_ORDER.index(tier)
    except ValueError:
        return 0


def plan_limits_by_tier(plan_tier: str) -> dict[str, int]:
    selected = PLAN_LIMITS_BY_TIER.get(plan_tier, PLAN_LIMITS_BY_TIER["free"])
    return dict(selected)


def plan_limits_from_guild_state(guild_state: dict[str, Any]) -> dict[str, int]:
    return plan_limits_by_tier(normalize_plan_tier(guild_state.get("subscription", "free")))


def is_plan_at_least(raw_plan: Any, target_tier: str) -> bool:
    return plan_rank(raw_plan) >= plan_rank(target_tier)


def required_plan_for_command(command_name: str) -> str:
    normalized = (command_name or "").strip().lower()
    for prefix, tier in _PREMIUM_PREFIX_MAP.items():
        if normalized == prefix or normalized.startswith(f"{prefix} "):
            return tier
    return "free"


def looks_like_active_premium_from_state(guild_state: dict[str, Any]) -> bool:
    if not isinstance(guild_state, dict):
        return False
    if not is_premium_subscription(guild_state.get("subscription")):
        return False

    raw_end = guild_state.get("subscription_end")
    if not raw_end:
        return True

    if isinstance(raw_end, datetime.datetime):
        end_dt = raw_end
    else:
        end_dt = None
        text = str(raw_end).strip()
        if text:
            try:
                if text.isdigit():
                    end_dt = datetime.datetime.fromtimestamp(int(text))
                else:
                    end_dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                end_dt = None
    if end_dt is None:
        return True
    if getattr(end_dt, "tzinfo", None) is None:
        end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
    else:
        end_dt = end_dt.astimezone(datetime.timezone.utc)
    return end_dt > datetime.datetime.now(tz=datetime.timezone.utc)
