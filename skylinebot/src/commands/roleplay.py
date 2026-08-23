from __future__ import annotations

import asyncio
import datetime
import random
import re
import traceback
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import storage.rp_characters as rp_characters_db
import storage.rp_economy_guard as rp_economy_guard_db
import storage.rp_event_history as rp_event_history_db
import storage.rp_events as rp_events_db
import storage.rp_scenarios as rp_scenarios_db
import storage.rp_scenario_stats as rp_scenario_stats_db
import storage.rp_schedules as rp_schedules_db
import storage.rp_settings as rp_settings_db
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _as_utc(value: Any) -> datetime.datetime | None:
    if not isinstance(value, datetime.datetime):
        return None
    if value.tzinfo:
        return value
    return value.replace(tzinfo=datetime.timezone.utc)


def _normalize_key(value: str) -> str:
    clean = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    return clean.strip("_")


def _duration_text(seconds: int) -> str:
    remain = max(0, int(seconds))
    hours, remainder = divmod(remain, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _schedule_next_run_utc(
    *,
    frequency: str,
    weekday: int,
    hour: int,
    minute: int,
    timezone_offset_minutes: int,
    from_utc: datetime.datetime | None = None,
) -> datetime.datetime:
    now_utc = from_utc if isinstance(from_utc, datetime.datetime) else _utc_now()
    now_utc = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=datetime.timezone.utc)
    offset = datetime.timedelta(minutes=int(timezone_offset_minutes or 0))
    now_local = now_utc + offset
    local_base = now_local.replace(second=0, microsecond=0)
    candidate_local = local_base.replace(hour=int(hour), minute=int(minute))
    normalized_frequency = "weekly" if str(frequency or "").strip().lower() == "weekly" else "daily"
    if normalized_frequency == "weekly":
        wanted_weekday = max(0, min(6, int(weekday or 0)))
        delta_days = (wanted_weekday - candidate_local.weekday()) % 7
        candidate_local = candidate_local + datetime.timedelta(days=delta_days)
        if candidate_local <= now_local:
            candidate_local += datetime.timedelta(days=7)
    else:
        if candidate_local <= now_local:
            candidate_local += datetime.timedelta(days=1)
    return candidate_local - offset


RP_PRESETS: dict[str, dict[str, Any]] = {
    "modern_city": {
        "title": "Modern City",
        "summary": "Fast-paced urban stories with crime, racing, and detective arcs.",
        "settings": {
            "currency_symbol": "credit",
            "start_coins": 350,
            "daily_reward_min": 100,
            "daily_reward_max": 240,
            "story_reward_min": 18,
            "story_reward_max": 50,
            "event_reward_xp": 140,
            "event_reward_coins": 260,
        },
        "scenarios": [
            {
                "scenario_key": "city_bank_heist",
                "name": "City Bank Heist",
                "description": "Plan a high-risk heist and escape before security closes all exits.",
                "difficulty": "hard",
                "reward_xp": 95,
                "reward_coins": 220,
            },
            {
                "scenario_key": "underground_race",
                "name": "Underground Race",
                "description": "Win an illegal night race through downtown checkpoints.",
                "difficulty": "normal",
                "reward_xp": 65,
                "reward_coins": 160,
            },
            {
                "scenario_key": "district_investigation",
                "name": "District Investigation",
                "description": "Track clues, question witnesses, and reveal the culprit.",
                "difficulty": "normal",
                "reward_xp": 75,
                "reward_coins": 180,
            },
        ],
    },
    "fantasy_kingdom": {
        "title": "Fantasy Kingdom",
        "summary": "Guild quests, dragons, relics, and kingdom politics.",
        "settings": {
            "currency_symbol": "gold",
            "start_coins": 300,
            "daily_reward_min": 90,
            "daily_reward_max": 220,
            "story_reward_min": 16,
            "story_reward_max": 48,
            "event_reward_xp": 170,
            "event_reward_coins": 300,
        },
        "scenarios": [
            {
                "scenario_key": "dragon_hunt",
                "name": "Dragon Hunt",
                "description": "Gather hunters and defeat a dragon threatening trade routes.",
                "difficulty": "hard",
                "reward_xp": 120,
                "reward_coins": 250,
            },
            {
                "scenario_key": "royal_court_trial",
                "name": "Royal Court Trial",
                "description": "Defend your faction in a tense political trial at the palace.",
                "difficulty": "normal",
                "reward_xp": 80,
                "reward_coins": 170,
            },
            {
                "scenario_key": "ancient_ruins",
                "name": "Ancient Ruins Expedition",
                "description": "Enter cursed ruins and recover a lost relic.",
                "difficulty": "hard",
                "reward_xp": 110,
                "reward_coins": 210,
            },
        ],
    },
    "school_life": {
        "title": "School Life",
        "summary": "Club rivalries, class events, exams, and social drama.",
        "settings": {
            "currency_symbol": "point",
            "start_coins": 200,
            "daily_reward_min": 70,
            "daily_reward_max": 180,
            "story_reward_min": 12,
            "story_reward_max": 38,
            "event_reward_xp": 120,
            "event_reward_coins": 190,
        },
        "scenarios": [
            {
                "scenario_key": "festival_preparation",
                "name": "Festival Preparation",
                "description": "Lead your class through deadlines before the school festival.",
                "difficulty": "normal",
                "reward_xp": 70,
                "reward_coins": 140,
            },
            {
                "scenario_key": "exam_mystery",
                "name": "Exam Mystery",
                "description": "Investigate suspicious leaks before the final exams begin.",
                "difficulty": "normal",
                "reward_xp": 75,
                "reward_coins": 135,
            },
            {
                "scenario_key": "sports_tournament",
                "name": "Sports Tournament",
                "description": "Win key matches and secure the championship trophy.",
                "difficulty": "easy",
                "reward_xp": 60,
                "reward_coins": 120,
            },
        ],
    },
    "custom_sandbox": {
        "title": "Custom Sandbox",
        "summary": "Neutral preset designed for fully custom roleplay worlds.",
        "settings": {
            "currency_symbol": "coin",
            "start_coins": 250,
            "daily_reward_min": 80,
            "daily_reward_max": 180,
            "story_reward_min": 12,
            "story_reward_max": 40,
            "event_reward_xp": 120,
            "event_reward_coins": 220,
        },
        "scenarios": [
            {
                "scenario_key": "starter_mission",
                "name": "Starter Mission",
                "description": "Complete your first mission and establish your character identity.",
                "difficulty": "easy",
                "reward_xp": 50,
                "reward_coins": 110,
            },
            {
                "scenario_key": "faction_negotiation",
                "name": "Faction Negotiation",
                "description": "Broker a deal between two factions with conflicting goals.",
                "difficulty": "normal",
                "reward_xp": 70,
                "reward_coins": 150,
            },
        ],
    },
}
RP_CITY_ONLY_PRESET_KEY = "modern_city"

BOOL_CONFIG_KEYS = {"enabled", "allow_custom_config", "allow_custom_scenarios"}
INT_CONFIG_LIMITS: dict[str, tuple[int, int]] = {
    "start_coins": (0, 2_000_000),
    "start_xp": (0, 500_000),
    "xp_per_level": (20, 10_000),
    "daily_reward_min": (0, 200_000),
    "daily_reward_max": (0, 300_000),
    "story_min_length": (5, 2_000),
    "story_cooldown_seconds": (0, 86_400),
    "story_reward_min": (0, 100_000),
    "story_reward_max": (0, 150_000),
    "scenario_cooldown_seconds": (0, 86_400),
    "event_reward_xp": (0, 250_000),
    "event_reward_coins": (0, 250_000),
    "max_custom_scenarios": (1, 200),
}
TEXT_CONFIG_LIMITS: dict[str, int] = {
    "currency_symbol": 12,
}

RP_GUARD_DEFAULTS: dict[str, int | bool] = {
    "enabled": False,
    "max_reward_xp": 250000,
    "max_reward_coins": 250000,
    "inflation_threshold_avg_coins": 25000,
    "base_reduce_percent": 20,
    "min_multiplier_percent": 55,
    "last_multiplier_percent": 100,
}


class Roleplay(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._scheduler_task: asyncio.Task | None = None

        class CogInfo:
            name = "Roleplay"
            category = "Fun"
            description = "Guild roleplay system"
            hidden = False
            emoji = "🎭"

        self.cog_info = CogInfo

    async def cog_load(self):
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    def cog_unload(self):
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()

    async def _wait_until_ready_safely(self) -> bool:
        while not self.bot.is_closed():
            if getattr(self.bot, "user", None) is not None and self.bot.is_ready():
                return True
            await asyncio.sleep(1)
        return False

    async def _resolve_event_announce_channel(
        self,
        guild: discord.Guild,
        settings: dict[str, Any],
    ) -> Any | None:
        channel_id_raw = str(settings.get("event_announce_channel_id") or "").strip()
        if not channel_id_raw.isdigit():
            return None
        channel_id = int(channel_id_raw)
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                channel = None
        if channel is not None:
            channel_guild_id = int(getattr(getattr(channel, "guild", None), "id", 0) or 0)
            if channel_guild_id and channel_guild_id != int(guild.id):
                return None
        if channel is None or not hasattr(channel, "send"):
            return None
        try:
            if hasattr(channel, "permissions_for") and guild.me:
                perms = channel.permissions_for(guild.me)
                if not bool(getattr(perms, "send_messages", False)):
                    return None
        except Exception:
            pass
        return channel

    async def _send_schedule_start_notice(
        self,
        guild: discord.Guild,
        settings: dict[str, Any],
        event_payload: dict[str, Any],
        *,
        schedule_name: str,
        duration_minutes: int,
    ) -> None:
        if not _safe_bool(settings.get("schedule_notify_on_start"), True):
            return
        channel = await self._resolve_event_announce_channel(guild, settings)
        if channel is None:
            return
        reward_xp = max(0, _safe_int(event_payload.get("reward_xp"), 0))
        reward_coins = max(0, _safe_int(event_payload.get("reward_coins"), 0))
        message = (
            "[RP Scheduler] Event started\n"
            f"Event: **{event_payload.get('event_title', 'Roleplay Event')}**\n"
            f"Schedule: `{schedule_name or 'schedule'}`\n"
            f"Duration: {max(1, int(duration_minutes))} minutes\n"
            f"Reward per participant: +{reward_xp} XP and +{self._coins_text(settings, reward_coins)}\n"
            "Join with `/rp eventjoin`."
        )
        try:
            await channel.send(message)
        except Exception:
            pass

    async def _send_schedule_end_notice(
        self,
        guild: discord.Guild,
        settings: dict[str, Any],
        event_row: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        if not _safe_bool(settings.get("schedule_notify_on_end"), True):
            return
        channel = await self._resolve_event_announce_channel(guild, settings)
        if channel is None:
            return
        message = (
            "[RP Scheduler] Event ended\n"
            f"Event: **{summary.get('title', event_row.get('event_title', 'Roleplay Event'))}**\n"
            f"Schedule: `{str(event_row.get('schedule_name') or 'schedule')}`\n"
            f"Rewarded players: {int(summary.get('participants') or 0)}\n"
            f"Total rewards: +{int(summary.get('total_xp') or 0)} XP and +{summary.get('coins_text', '0 coin')}"
        )
        try:
            await channel.send(message)
        except Exception:
            pass

    async def _ensure_guard_settings(self, guild_id: int) -> dict[str, Any]:
        row = await rp_economy_guard_db.get(guild_id=guild_id)
        if row:
            return row
        await rp_economy_guard_db.insert(guild_id=guild_id, **RP_GUARD_DEFAULTS)
        return await rp_economy_guard_db.get(guild_id=guild_id) or dict(RP_GUARD_DEFAULTS)

    async def _average_coins(self, guild_id: int) -> int:
        rows = await rp_characters_db.gets(guild_id=guild_id)
        if not rows:
            return 0
        total = 0
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            total += max(0, _safe_int(row.get("coins"), 0))
            count += 1
        if count <= 0:
            return 0
        return int(total / count)

    async def _apply_reward_guard(
        self,
        guild_id: int,
        *,
        base_xp: int,
        base_coins: int,
    ) -> tuple[int, int, dict[str, int]]:
        row = await self._ensure_guard_settings(guild_id)
        enabled = _safe_bool(row.get("enabled"), False)
        reward_xp = max(0, int(base_xp or 0))
        reward_coins = max(0, int(base_coins or 0))
        if not enabled:
            return reward_xp, reward_coins, {"multiplier_percent": 100, "avg_coins": await self._average_coins(guild_id)}
        max_xp = max(0, _safe_int(row.get("max_reward_xp"), _safe_int(RP_GUARD_DEFAULTS["max_reward_xp"], 250000)))
        max_coins = max(0, _safe_int(row.get("max_reward_coins"), _safe_int(RP_GUARD_DEFAULTS["max_reward_coins"], 250000)))
        threshold = max(1, _safe_int(row.get("inflation_threshold_avg_coins"), _safe_int(RP_GUARD_DEFAULTS["inflation_threshold_avg_coins"], 25000)))
        base_reduce = max(0, min(95, _safe_int(row.get("base_reduce_percent"), _safe_int(RP_GUARD_DEFAULTS["base_reduce_percent"], 20))))
        min_multiplier = max(5, min(100, _safe_int(row.get("min_multiplier_percent"), _safe_int(RP_GUARD_DEFAULTS["min_multiplier_percent"], 55))))
        avg_coins = await self._average_coins(guild_id)
        overflow_ratio = max(0.0, float(avg_coins - threshold) / float(threshold)) if avg_coins > threshold else 0.0
        dynamic_reduce = int(base_reduce + min(70.0, overflow_ratio * 40.0))
        multiplier = max(min_multiplier, min(100, 100 - dynamic_reduce))
        reward_xp = min(reward_xp, max_xp)
        reward_coins = min(reward_coins, max_coins)
        reward_xp = max(0, int(reward_xp * multiplier / 100))
        reward_coins = max(0, int(reward_coins * multiplier / 100))
        if row.get("id"):
            await rp_economy_guard_db.update(id=row["id"], last_multiplier_percent=multiplier, updated_at=_utc_now())
        return reward_xp, reward_coins, {"multiplier_percent": multiplier, "avg_coins": avg_coins}

    async def _upsert_scenario_stats(
        self,
        guild_id: int,
        *,
        scenario_key: str,
        scenario_name: str,
        play_count_delta: int = 0,
        event_start_delta: int = 0,
        reward_xp_delta: int = 0,
        reward_coins_delta: int = 0,
    ) -> None:
        key = _normalize_key(scenario_key)[:48] or "scenario"
        row = await rp_scenario_stats_db.get(guild_id=guild_id, scenario_key=key) or {}
        now = _utc_now()
        if row.get("id"):
            await rp_scenario_stats_db.update(
                id=row["id"],
                scenario_name=str(scenario_name or row.get("scenario_name") or key)[:160],
                play_count=max(0, _safe_int(row.get("play_count"), 0) + int(play_count_delta)),
                event_start_count=max(0, _safe_int(row.get("event_start_count"), 0) + int(event_start_delta)),
                total_reward_xp=max(0, _safe_int(row.get("total_reward_xp"), 0) + int(reward_xp_delta)),
                total_reward_coins=max(0, _safe_int(row.get("total_reward_coins"), 0) + int(reward_coins_delta)),
                last_played_at=now,
                updated_at=now,
            )
            return
        await rp_scenario_stats_db.insert(
            guild_id=guild_id,
            scenario_key=key,
            scenario_name=str(scenario_name or key)[:160],
            play_count=max(0, int(play_count_delta)),
            event_start_count=max(0, int(event_start_delta)),
            total_reward_xp=max(0, int(reward_xp_delta)),
            total_reward_coins=max(0, int(reward_coins_delta)),
            last_played_at=now,
            updated_at=now,
        )

    async def _process_schedules_once(self) -> None:
        now = _utc_now()
        active_events = await rp_events_db.gets(status="active") or []
        for active in active_events:
            if not isinstance(active, dict):
                continue
            guild_id = _safe_int(active.get("guild_id"), 0)
            if guild_id <= 0:
                continue
            ends_at = _as_utc(active.get("ends_at"))
            if not ends_at or now < ends_at:
                continue
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            try:
                await self._finish_event(guild, active, trigger_type="auto_expire_scheduler")
            except Exception as error:
                logger.warning(f"Roleplay auto-expire failed for guild {guild_id}: {error}")

        rows = await rp_schedules_db.gets(enabled=True) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            guild_id = _safe_int(row.get("guild_id"), 0)
            if guild_id <= 0:
                continue
            next_run = _as_utc(row.get("next_run_at"))
            if not next_run:
                next_run = _schedule_next_run_utc(
                    frequency=str(row.get("frequency") or "daily"),
                    weekday=_safe_int(row.get("weekday"), 0),
                    hour=_safe_int(row.get("hour"), 20),
                    minute=_safe_int(row.get("minute"), 0),
                    timezone_offset_minutes=_safe_int(row.get("timezone_offset_minutes"), 0),
                    from_utc=now,
                )
                if row.get("id"):
                    await rp_schedules_db.update(id=row["id"], next_run_at=next_run, updated_at=now)
                continue
            if next_run > now:
                continue
            next_after = _schedule_next_run_utc(
                frequency=str(row.get("frequency") or "daily"),
                weekday=_safe_int(row.get("weekday"), 0),
                hour=_safe_int(row.get("hour"), 20),
                minute=_safe_int(row.get("minute"), 0),
                timezone_offset_minutes=_safe_int(row.get("timezone_offset_minutes"), 0),
                from_utc=now + datetime.timedelta(minutes=1),
            )
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                if row.get("id"):
                    await rp_schedules_db.update(id=row["id"], next_run_at=next_after, last_run_at=now, updated_at=now)
                continue
            settings = await self._ensure_settings(guild_id)
            if not _safe_bool(settings.get("enabled"), False):
                if row.get("id"):
                    await rp_schedules_db.update(id=row["id"], next_run_at=next_after, last_run_at=now, updated_at=now)
                continue
            active_event = await self._load_event(guild_id)
            if active_event and str(active_event.get("status") or "").lower() == "active":
                if row.get("id"):
                    await rp_schedules_db.update(id=row["id"], next_run_at=next_after, last_run_at=now, updated_at=now)
                continue
            scenarios = await self._list_scenarios(guild_id)
            if not scenarios:
                if row.get("id"):
                    await rp_schedules_db.update(id=row["id"], next_run_at=next_after, last_run_at=now, updated_at=now)
                continue
            selected = None
            scenario_id = _safe_int(row.get("scenario_id"), 0)
            if scenario_id > 0:
                selected = await rp_scenarios_db.get(id=scenario_id, guild_id=guild_id)
            if not selected:
                wanted_key = _normalize_key(str(row.get("scenario_key") or ""))
                for scenario in scenarios:
                    if _normalize_key(str(scenario.get("scenario_key") or "")) == wanted_key and wanted_key:
                        selected = scenario
                        break
            if not selected:
                selected = random.choice(scenarios)
            duration_minutes = max(5, min(180, _safe_int(row.get("duration_minutes"), 30)))
            reward_xp = _safe_int(row.get("reward_xp_override"), 0)
            reward_coins = _safe_int(row.get("reward_coins_override"), 0)
            if reward_xp <= 0:
                reward_xp = max(_safe_int(settings.get("event_reward_xp"), 120), _safe_int(selected.get("reward_xp"), 50))
            if reward_coins <= 0:
                reward_coins = max(_safe_int(settings.get("event_reward_coins"), 220), _safe_int(selected.get("reward_coins"), 100))
            payload = {
                "guild_id": guild_id,
                "status": "active",
                "event_title": str(selected.get("name") or "Roleplay Event"),
                "template_key": str(selected.get("scenario_key") or ""),
                "description": str(selected.get("description") or ""),
                "reward_xp": reward_xp,
                "reward_coins": reward_coins,
                "participants": [],
                "started_by": 0,
                "trigger_type": "scheduled_auto_start",
                "schedule_name": str(row.get("schedule_name") or "")[:80],
                "started_at": now,
                "ends_at": now + datetime.timedelta(minutes=duration_minutes),
                "updated_at": now,
            }
            if active_event and active_event.get("id"):
                await rp_events_db.update(id=active_event["id"], **payload)
            else:
                await rp_events_db.insert(**payload)
            await self._send_schedule_start_notice(
                guild,
                settings,
                payload,
                schedule_name=str(row.get("schedule_name") or ""),
                duration_minutes=duration_minutes,
            )
            await self._upsert_scenario_stats(
                guild_id,
                scenario_key=str(selected.get("scenario_key") or ""),
                scenario_name=str(selected.get("name") or "Scenario"),
                event_start_delta=1,
            )
            if row.get("id"):
                await rp_schedules_db.update(id=row["id"], next_run_at=next_after, last_run_at=now, updated_at=now)

    async def _scheduler_loop(self) -> None:
        ready = await self._wait_until_ready_safely()
        if not ready:
            return
        while not self.bot.is_closed():
            try:
                await self._process_schedules_once()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning(f"Roleplay scheduler loop failed: {error}")
            await asyncio.sleep(60)

    def _coins_text(self, settings: dict[str, Any], amount: int) -> str:
        symbol = str(settings.get("currency_symbol") or "coin").strip()[:12]
        return f"{int(max(0, amount)):,} {symbol}"

    def _level_from_xp(self, xp: int, xp_per_level: int) -> int:
        threshold = max(1, int(xp_per_level))
        return max(1, (max(0, int(xp)) // threshold) + 1)

    async def _ensure_settings(self, guild_id: int) -> dict[str, Any]:
        settings = await rp_settings_db.get(guild_id=guild_id)
        if settings:
            return settings
        await rp_settings_db.insert(guild_id=guild_id)
        return await rp_settings_db.get(guild_id=guild_id) or {}

    async def _ensure_character(
        self,
        guild_id: int,
        user_id: int,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = await rp_characters_db.get(guild_id=guild_id, user_id=user_id)
        if row:
            return row
        cfg = settings or await self._ensure_settings(guild_id)
        start_xp = max(0, _safe_int(cfg.get("start_xp"), 0))
        start_coins = max(0, _safe_int(cfg.get("start_coins"), 0))
        xp_per_level = max(1, _safe_int(cfg.get("xp_per_level"), 120))
        await rp_characters_db.insert(
            guild_id=guild_id,
            user_id=user_id,
            xp=start_xp,
            coins=start_coins,
            level=self._level_from_xp(start_xp, xp_per_level),
        )
        return await rp_characters_db.get(guild_id=guild_id, user_id=user_id) or {}

    async def _save_character(
        self,
        row: dict[str, Any],
        *,
        settings: dict[str, Any],
        xp: int | None = None,
        coins: int | None = None,
        reputation: int | None = None,
        completed_scenarios: int | None = None,
        completed_events: int | None = None,
        daily_streak: int | None = None,
        last_daily_at: datetime.datetime | None = None,
        last_story_at: datetime.datetime | None = None,
        last_scenario_at: datetime.datetime | None = None,
        character_name: str | None = None,
        character_job: str | None = None,
        character_faction: str | None = None,
        character_bio: str | None = None,
    ) -> dict[str, Any]:
        next_xp = max(0, int(xp if xp is not None else _safe_int(row.get("xp"), 0)))
        xp_per_level = max(1, _safe_int(settings.get("xp_per_level"), 120))
        payload: dict[str, Any] = {
            "id": row["id"],
            "xp": next_xp,
            "level": self._level_from_xp(next_xp, xp_per_level),
            "coins": max(0, int(coins if coins is not None else _safe_int(row.get("coins"), 0))),
            "reputation": max(0, int(reputation if reputation is not None else _safe_int(row.get("reputation"), 0))),
            "completed_scenarios": max(
                0,
                int(
                    completed_scenarios
                    if completed_scenarios is not None
                    else _safe_int(row.get("completed_scenarios"), 0)
                ),
            ),
            "completed_events": max(
                0,
                int(
                    completed_events
                    if completed_events is not None
                    else _safe_int(row.get("completed_events"), 0)
                ),
            ),
            "daily_streak": max(0, int(daily_streak if daily_streak is not None else _safe_int(row.get("daily_streak"), 0))),
            "last_daily_at": last_daily_at if last_daily_at is not None else row.get("last_daily_at"),
            "last_story_at": last_story_at if last_story_at is not None else row.get("last_story_at"),
            "last_scenario_at": last_scenario_at if last_scenario_at is not None else row.get("last_scenario_at"),
            "character_name": character_name if character_name is not None else str(row.get("character_name") or ""),
            "character_job": character_job if character_job is not None else str(row.get("character_job") or ""),
            "character_faction": character_faction if character_faction is not None else str(row.get("character_faction") or ""),
            "character_bio": character_bio if character_bio is not None else str(row.get("character_bio") or ""),
            "updated_at": _utc_now(),
        }
        saved = await rp_characters_db.update(**payload)
        return saved or row

    async def _is_manager(self, ctx: commands.Context) -> bool:
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return False
        perms = ctx.author.guild_permissions
        if bool(getattr(perms, "administrator", False) or getattr(perms, "manage_guild", False)):
            return True
        return await checks.check_is_owner(ctx, notify=False)

    async def _require_manager(self, ctx: commands.Context) -> bool:
        if await self._is_manager(ctx):
            return True
        await ctx.send("Only server managers can configure the roleplay system.")
        return False

    async def _upsert_scenario(
        self,
        guild_id: int,
        *,
        scenario_key: str,
        name: str,
        description: str,
        template_key: str,
        difficulty: str,
        reward_xp: int,
        reward_coins: int,
        is_preset: bool,
    ) -> dict[str, Any] | None:
        key = _normalize_key(scenario_key)[:48]
        if not key:
            return None
        payload = {
            "guild_id": guild_id,
            "scenario_key": key,
            "name": str(name or "Scenario").strip()[:120],
            "description": str(description or "").strip()[:800],
            "template_key": _normalize_key(template_key)[:48] or "custom",
            "difficulty": _normalize_key(difficulty)[:24] or "normal",
            "reward_xp": max(0, min(500_000, int(reward_xp))),
            "reward_coins": max(0, min(500_000, int(reward_coins))),
            "is_enabled": True,
            "is_preset": bool(is_preset),
            "updated_at": _utc_now(),
        }
        existing = await rp_scenarios_db.get(guild_id=guild_id, scenario_key=key)
        if existing:
            return await rp_scenarios_db.update(id=existing["id"], **payload)
        return await rp_scenarios_db.insert(**payload)

    async def _apply_preset(self, guild_id: int, preset_key: str) -> tuple[dict[str, Any], int]:
        _ = _normalize_key(preset_key)
        preset = RP_PRESETS.get(RP_CITY_ONLY_PRESET_KEY)
        if not preset:
            raise ValueError("Preset not found")
        settings = await self._ensure_settings(guild_id)
        settings_update = dict(preset.get("settings") or {})
        settings_update["enabled"] = True
        settings_update["preset_key"] = RP_CITY_ONLY_PRESET_KEY
        settings_update["updated_at"] = _utc_now()
        updated_settings = await rp_settings_db.update(id=settings["id"], **settings_update) or settings
        created_count = 0
        for scenario in list(preset.get("scenarios") or []):
            upserted = await self._upsert_scenario(
                guild_id,
                scenario_key=str(scenario.get("scenario_key") or scenario.get("name") or ""),
                name=str(scenario.get("name") or "Scenario"),
                description=str(scenario.get("description") or ""),
                template_key=RP_CITY_ONLY_PRESET_KEY,
                difficulty=str(scenario.get("difficulty") or "normal"),
                reward_xp=_safe_int(scenario.get("reward_xp"), 60),
                reward_coins=_safe_int(scenario.get("reward_coins"), 120),
                is_preset=True,
            )
            if upserted:
                created_count += 1
        return updated_settings, created_count

    async def _list_scenarios(self, guild_id: int) -> list[dict[str, Any]]:
        rows = await rp_scenarios_db.gets(guild_id=guild_id)
        rows = [row for row in rows if bool(row.get("is_enabled"))]
        rows.sort(key=lambda row: (0 if bool(row.get("is_preset")) else 1, str(row.get("name") or "").lower()))
        return rows

    async def _find_scenario(self, guild_id: int, token: str) -> dict[str, Any] | None:
        rows = await self._list_scenarios(guild_id)
        lookup = str(token or "").strip()
        if not lookup:
            return None
        if lookup.isdigit():
            wanted_id = int(lookup)
            for row in rows:
                if int(row.get("id") or 0) == wanted_id:
                    return row
        normalized_lookup = _normalize_key(lookup)
        for row in rows:
            if _normalize_key(str(row.get("scenario_key") or "")) == normalized_lookup:
                return row
        lowered = lookup.lower()
        for row in rows:
            if str(row.get("name") or "").strip().lower() == lowered:
                return row
        for row in rows:
            if lowered in str(row.get("name") or "").strip().lower():
                return row
        return None

    async def _load_event(self, guild_id: int) -> dict[str, Any] | None:
        return await rp_events_db.get(guild_id=guild_id)

    async def _finish_event(
        self,
        guild: discord.Guild,
        event_row: dict[str, Any],
        *,
        trigger_type: str = "manual",
    ) -> dict[str, Any]:
        settings = await self._ensure_settings(guild.id)
        now = _utc_now()
        participants_raw = (
            event_row.get("participants") if isinstance(event_row.get("participants"), list) else []
        )
        participant_ids: list[int] = []
        for raw in participants_raw:
            text = str(raw).strip()
            if text.isdigit():
                member_id = int(text)
                if member_id not in participant_ids:
                    participant_ids.append(member_id)

        base_xp = max(0, _safe_int(event_row.get("reward_xp"), 0))
        base_coins = max(0, _safe_int(event_row.get("reward_coins"), 0))
        payout_xp, payout_coins, guard_meta = await self._apply_reward_guard(
            guild.id,
            base_xp=base_xp,
            base_coins=base_coins,
        )
        total_xp = 0
        total_coins = 0
        rewarded_users = 0
        for member_id in participant_ids:
            profile = await self._ensure_character(guild.id, member_id, settings)
            if not profile:
                continue
            xp_bonus = random.randint(0, max(4, payout_xp // 6 if payout_xp > 0 else 6))
            coins_bonus = random.randint(0, max(8, payout_coins // 6 if payout_coins > 0 else 10))
            add_xp = payout_xp + xp_bonus
            add_coins = payout_coins + coins_bonus
            await self._save_character(
                profile,
                settings=settings,
                xp=_safe_int(profile.get("xp"), 0) + add_xp,
                coins=_safe_int(profile.get("coins"), 0) + add_coins,
                completed_events=_safe_int(profile.get("completed_events"), 0) + 1,
            )
            rewarded_users += 1
            total_xp += add_xp
            total_coins += add_coins

        await rp_events_db.update(
            id=event_row["id"],
            status="idle",
            participants=[],
            ends_at=None,
            updated_at=now,
        )
        participants_count = max(0, rewarded_users)
        scenario_key = str(event_row.get("template_key") or "")
        event_title = str(event_row.get("event_title") or "Roleplay Event")
        if scenario_key:
            await self._upsert_scenario_stats(
                guild.id,
                scenario_key=scenario_key,
                scenario_name=event_title,
                reward_xp_delta=total_xp,
                reward_coins_delta=total_coins,
            )
        if participants_count > 0:
            await rp_event_history_db.insert(
                guild_id=guild.id,
                event_title=event_title,
                scenario_key=scenario_key,
                trigger_type=str(trigger_type or "manual")[:60],
                participants_count=participants_count,
                total_reward_xp=total_xp,
                total_reward_coins=total_coins,
                reward_xp_per_player=int(total_xp / participants_count),
                reward_coins_per_player=int(total_coins / participants_count),
                started_at=event_row.get("started_at"),
                ended_at=now,
                created_at=now,
            )
            await rp_event_history_db.delete_limited(500, {"guild_id": guild.id})
        summary = {
            "title": event_title,
            "participants": rewarded_users,
            "total_xp": total_xp,
            "total_coins": total_coins,
            "coins_text": self._coins_text(settings, total_coins),
            "guard_multiplier_percent": int(guard_meta.get("multiplier_percent") or 100),
        }
        trigger_source = str(event_row.get("trigger_type") or "").strip().lower()
        is_scheduled_event = trigger_source.startswith("scheduled")
        if is_scheduled_event:
            await self._send_schedule_end_notice(guild, settings, event_row, summary)
        return summary

    async def _finish_expired_event_if_needed(
        self,
        guild: discord.Guild,
    ) -> dict[str, Any] | None:
        row = await self._load_event(guild.id)
        if not row or str(row.get("status") or "").lower() != "active":
            return None
        ends_at = _as_utc(row.get("ends_at"))
        if not ends_at or _utc_now() < ends_at:
            return None
        return await self._finish_event(guild, row, trigger_type="auto_expire")

    def _event_remaining_seconds(self, event_row: dict[str, Any]) -> int:
        ends_at = _as_utc(event_row.get("ends_at"))
        if not ends_at:
            return 0
        return max(0, int((ends_at - _utc_now()).total_seconds()))

    @commands.hybrid_group(
        name="rp",
        help="คำสั่งสวมบทบาท",
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def rp(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        embed = discord.Embed(
            title="ระบบสวมบทบาท",
            description=(
                "`/rp setup <preset>` configure a starter roleplay world (ไทย)\n"
                "`/rp character` create or edit your character profile\n"
                "`/rp daily`, `/rp story`, `/rp play` earn XP and rewards\n"
                "`/rp eventstart` and `/rp eventjoin` run group events"
            ),
            color=color.blue,
        )
        embed.set_footer(text="Tip: use /rp presets to browse ready-made roleplay packs.")
        await ctx.send(embed=embed)

    @rp.command(name="presets", help="แสดงค่าที่ตั้งไว้ล่วงหน้าสำหรับบทบาทสมมติที่มีอยู่")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_presets(self, ctx: commands.Context):
        lines = []
        preset_items = [(RP_CITY_ONLY_PRESET_KEY, RP_PRESETS.get(RP_CITY_ONLY_PRESET_KEY, {}))]
        for key, preset in preset_items:
            if not isinstance(preset, dict):
                continue
            lines.append(
                f"`{key}` - **{preset.get('title', key)}**\n{str(preset.get('summary') or '')}"
            )
        embed = discord.Embed(
            title="ค่าที่ตั้งไว้ล่วงหน้าสำหรับบทบาทสมมุติ",
            description="\n\n".join(lines) if lines else "No presets available.",
            color=color.blue,
        )
        await ctx.send(embed=embed)

    @rp.command(name="setup", help="เปิดใช้งานบทบาทสมมติและใช้การตั้งค่าล่วงหน้า")
    @app_commands.describe(preset="Preset key (for example: modern_city)")
    @app_commands.choices(
        preset=[
            app_commands.Choice(name="modern_city", value="modern_city"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_setup(self, ctx: commands.Context, preset: str = "modern_city"):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manager(ctx):
            return
        try:
            preset_key = _normalize_key(preset)
            if preset_key != RP_CITY_ONLY_PRESET_KEY:
                return await ctx.send("Roleplay setup is limited to `modern_city` on this bot.")
            settings, scenario_count = await self._apply_preset(ctx.guild.id, preset_key)
            preset_data = RP_PRESETS[preset_key]
            embed = discord.Embed(
                title=f"Roleplay Setup Complete - {preset_data.get('title', preset_key)}",
                description=str(preset_data.get("summary") or ""),
                color=color.green,
            )
            embed.add_field(name="Preset Key", value=f"`{preset_key}`", inline=True)
            embed.add_field(name="Scenarios Ready", value=str(int(scenario_count)), inline=True)
            embed.add_field(
                name="Daily Reward",
                value=(
                    f"{self._coins_text(settings, _safe_int(settings.get('daily_reward_min'), 0))}"
                    f" - {self._coins_text(settings, _safe_int(settings.get('daily_reward_max'), 0))}"
                ),
                inline=False,
            )
            embed.set_footer(text="Players can now use /rp character, /rp daily, /rp story, /rp play.")
            await ctx.send(embed=embed)
        except Exception:
            logger.error(f"Roleplay setup failed: {traceback.format_exc()}")
            await ctx.send("Failed to setup roleplay preset.")

    @rp.command(name="config", help="แสดงการตั้งค่าบทบาทปัจจุบัน")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_config(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        settings = await self._ensure_settings(ctx.guild.id)
        embed = discord.Embed(
            title=f"Roleplay Config - {ctx.guild.name}",
            color=color.blue,
        )
        embed.add_field(name="Enabled", value=str(bool(settings.get("enabled"))), inline=True)
        embed.add_field(name="Preset", value=f"`{str(settings.get('preset_key') or 'modern_city')}`", inline=True)
        embed.add_field(name="Currency", value=f"`{str(settings.get('currency_symbol') or 'coin')}`", inline=True)
        embed.add_field(name="Start Coins", value=f"`{_safe_int(settings.get('start_coins'), 0):,}`", inline=True)
        embed.add_field(name="XP per Level", value=f"`{_safe_int(settings.get('xp_per_level'), 120):,}`", inline=True)
        embed.add_field(name="Story Cooldown", value=f"`{_safe_int(settings.get('story_cooldown_seconds'), 300)}s`", inline=True)
        embed.add_field(
            name="Daily Range",
            value=f"`{_safe_int(settings.get('daily_reward_min'), 0):,}` - `{_safe_int(settings.get('daily_reward_max'), 0):,}`",
            inline=True,
        )
        embed.add_field(
            name="Custom Controls",
            value=(
                f"config: `{bool(settings.get('allow_custom_config'))}` | "
                f"scenarios: `{bool(settings.get('allow_custom_scenarios'))}`"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @rp.command(name="set", help="แก้ไขคีย์การกำหนดค่าบทบาทสมมุติ")
    @app_commands.describe(key="Config key", value="New value")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_set(self, ctx: commands.Context, key: str, value: str):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manager(ctx):
            return
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("allow_custom_config")):
            return await ctx.send("Custom config is disabled for this server preset.")

        normalized_key = _normalize_key(key)
        if normalized_key in BOOL_CONFIG_KEYS:
            parsed: Any = _safe_bool(value, default=False)
        elif normalized_key in INT_CONFIG_LIMITS:
            min_value, max_value = INT_CONFIG_LIMITS[normalized_key]
            parsed = max(min_value, min(max_value, _safe_int(value, min_value)))
            if normalized_key.endswith("_max"):
                min_key = normalized_key.replace("_max", "_min")
                if min_key in INT_CONFIG_LIMITS:
                    parsed = max(parsed, _safe_int(settings.get(min_key), parsed))
            if normalized_key.endswith("_min"):
                max_key = normalized_key.replace("_min", "_max")
                if max_key in INT_CONFIG_LIMITS:
                    current_max = _safe_int(settings.get(max_key), parsed)
                    if parsed > current_max:
                        await rp_settings_db.update(id=settings["id"], **{max_key: parsed})
        elif normalized_key in TEXT_CONFIG_LIMITS:
            limit = TEXT_CONFIG_LIMITS[normalized_key]
            parsed = str(value or "").strip()[:limit]
            if not parsed:
                return await ctx.send("Text value cannot be empty.")
        else:
            allowed_keys = (
                sorted(BOOL_CONFIG_KEYS)
                + sorted(INT_CONFIG_LIMITS.keys())
                + sorted(TEXT_CONFIG_LIMITS.keys())
            )
            return await ctx.send(f"Unknown key. Allowed keys: `{', '.join(allowed_keys)}`")

        try:
            updated = await rp_settings_db.update(
                id=settings["id"],
                **{normalized_key: parsed, "updated_at": _utc_now()},
            )
            if not updated:
                return await ctx.send("Failed to update this config key.")
            await ctx.send(f"Updated `{normalized_key}` to `{parsed}`.")
        except Exception:
            logger.error(f"Roleplay set config failed: {traceback.format_exc()}")
            await ctx.send("Failed to apply config update.")

    @rp.command(name="character", help="สร้างหรือแก้ไขตัวละครสวมบทบาทของคุณ")
    @app_commands.describe(
        name="Character name",
        job="Character job",
        faction="Character faction",
        bio="Character short bio",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_character(
        self,
        ctx: commands.Context,
        name: str | None = None,
        job: str | None = None,
        faction: str | None = None,
        bio: str | None = None,
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")
        profile = await self._ensure_character(ctx.guild.id, ctx.author.id, settings)
        if not profile:
            return await ctx.send("Unable to create or load your character.")

        if name is None and job is None and faction is None and bio is None:
            return await self.rp_profile(ctx, member=ctx.author)

        updated = await self._save_character(
            profile,
            settings=settings,
            character_name=str(name).strip()[:80] if name is not None else None,
            character_job=str(job).strip()[:80] if job is not None else None,
            character_faction=str(faction).strip()[:80] if faction is not None else None,
            character_bio=str(bio).strip()[:500] if bio is not None else None,
        )
        display_name = str(updated.get("character_name") or ctx.author.display_name)
        await ctx.send(f"Character updated: **{display_name}**")

    @rp.command(name="profile", help="แสดงโปรไฟล์บทบาทสมมติ")
    @app_commands.describe(member="Target member")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_profile(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        target = member or ctx.author
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")
        profile = await self._ensure_character(ctx.guild.id, target.id, settings)
        display_name = str(profile.get("character_name") or target.display_name)
        embed = discord.Embed(
            title=f"{display_name} - Roleplay Profile",
            color=color.blue,
        )
        embed.add_field(name="Level", value=f"`{_safe_int(profile.get('level'), 1)}`", inline=True)
        embed.add_field(name="XP", value=f"`{_safe_int(profile.get('xp'), 0):,}`", inline=True)
        embed.add_field(name="Coins", value=f"`{self._coins_text(settings, _safe_int(profile.get('coins'), 0))}`", inline=True)
        embed.add_field(name="Job", value=str(profile.get("character_job") or "-"), inline=True)
        embed.add_field(name="Faction", value=str(profile.get("character_faction") or "-"), inline=True)
        embed.add_field(name="Reputation", value=f"`{_safe_int(profile.get('reputation'), 0)}`", inline=True)
        embed.add_field(name="Scenarios", value=f"`{_safe_int(profile.get('completed_scenarios'), 0)}`", inline=True)
        embed.add_field(name="Events", value=f"`{_safe_int(profile.get('completed_events'), 0)}`", inline=True)
        embed.add_field(name="Daily Streak", value=f"`{_safe_int(profile.get('daily_streak'), 0)}`", inline=True)
        bio_text = str(profile.get("character_bio") or "").strip()
        if bio_text:
            embed.add_field(name="Bio", value=bio_text[:900], inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @rp.command(name="daily", help="รับรางวัลสวมบทบาทรายวัน")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_daily(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")

        profile = await self._ensure_character(ctx.guild.id, ctx.author.id, settings)
        now = _utc_now()
        last_daily = _as_utc(profile.get("last_daily_at"))
        if last_daily:
            elapsed = int((now - last_daily).total_seconds())
            if elapsed < 86_400:
                return await ctx.send(
                    f"Daily already claimed. Try again in {_duration_text(86_400 - elapsed)}."
                )

        reward_min = max(0, _safe_int(settings.get("daily_reward_min"), 80))
        reward_max = max(reward_min, _safe_int(settings.get("daily_reward_max"), reward_min))
        reward_coins = random.randint(reward_min, reward_max)
        reward_xp = random.randint(max(10, reward_coins // 4), max(20, reward_coins // 2))
        reward_xp, reward_coins, guard_meta = await self._apply_reward_guard(
            ctx.guild.id,
            base_xp=reward_xp,
            base_coins=reward_coins,
        )

        streak_before = _safe_int(profile.get("daily_streak"), 0)
        streak_now = 1
        if last_daily:
            elapsed = int((now - last_daily).total_seconds())
            if elapsed <= 172_800:
                streak_now = streak_before + 1

        updated = await self._save_character(
            profile,
            settings=settings,
            xp=_safe_int(profile.get("xp"), 0) + reward_xp,
            coins=_safe_int(profile.get("coins"), 0) + reward_coins,
            daily_streak=streak_now,
            last_daily_at=now,
        )
        await ctx.send(
            f"Daily claimed: +{self._coins_text(settings, reward_coins)} and +{reward_xp} XP. "
            f"Streak: {streak_now}. Level: {_safe_int(updated.get('level'), 1)}."
            + (
                f" (Economy Guard {int(guard_meta.get('multiplier_percent') or 100)}%)"
                if int(guard_meta.get("multiplier_percent") or 100) < 100
                else ""
            )
        )

    @rp.command(name="story", help="โพสต์เรื่องราวสวมบทบาทเพื่อรับ XP และเหรียญ")
    @app_commands.describe(story="Your roleplay action or story line")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_story(self, ctx: commands.Context, *, story: str):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")

        text = str(story or "").strip()
        min_length = max(5, _safe_int(settings.get("story_min_length"), 20))
        if len(text) < min_length:
            return await ctx.send(f"Story is too short. Minimum length is {min_length} characters.")

        profile = await self._ensure_character(ctx.guild.id, ctx.author.id, settings)
        now = _utc_now()
        last_story = _as_utc(profile.get("last_story_at"))
        cooldown = max(0, _safe_int(settings.get("story_cooldown_seconds"), 300))
        if last_story and cooldown > 0:
            elapsed = int((now - last_story).total_seconds())
            if elapsed < cooldown:
                return await ctx.send(
                    f"Story cooldown active. Try again in {_duration_text(cooldown - elapsed)}."
                )

        reward_min = max(0, _safe_int(settings.get("story_reward_min"), 12))
        reward_max = max(reward_min, _safe_int(settings.get("story_reward_max"), reward_min))
        reward_coins = random.randint(reward_min, reward_max)
        reward_xp = random.randint(max(6, reward_coins // 3), max(12, reward_coins // 2))
        reward_xp, reward_coins, guard_meta = await self._apply_reward_guard(
            ctx.guild.id,
            base_xp=reward_xp,
            base_coins=reward_coins,
        )
        updated = await self._save_character(
            profile,
            settings=settings,
            xp=_safe_int(profile.get("xp"), 0) + reward_xp,
            coins=_safe_int(profile.get("coins"), 0) + reward_coins,
            reputation=_safe_int(profile.get("reputation"), 0) + 1,
            last_story_at=now,
        )
        await ctx.send(
            f"Story accepted: +{self._coins_text(settings, reward_coins)} and +{reward_xp} XP. "
            f"Reputation: {_safe_int(updated.get('reputation'), 0)}."
            + (
                f" (Economy Guard {int(guard_meta.get('multiplier_percent') or 100)}%)"
                if int(guard_meta.get("multiplier_percent") or 100) < 100
                else ""
            )
        )

    @rp.command(name="scenarios", help="แสดงรายการสถานการณ์สมมติที่มีอยู่")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_scenarios(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")
        rows = await self._list_scenarios(ctx.guild.id)
        if not rows:
            return await ctx.send("No scenarios found. Run `/rp setup` to install preset scenarios.")
        lines = []
        for row in rows[:20]:
            difficulty = str(row.get("difficulty") or "normal")
            lines.append(
                f"`{row.get('scenario_key')}` | **{row.get('name', 'Scenario')}** | "
                f"{difficulty} | +{_safe_int(row.get('reward_xp'), 0)} XP | "
                f"+{self._coins_text(settings, _safe_int(row.get('reward_coins'), 0))}"
            )
        embed = discord.Embed(
            title=f"Roleplay Scenarios - {ctx.guild.name}",
            description="\n".join(lines),
            color=color.blue,
        )
        embed.set_footer(text="Use /rp play <scenario_key> to run a scenario.")
        await ctx.send(embed=embed)

    @rp.command(name="play", help="ดำเนินสถานการณ์สวมบทบาท")
    @app_commands.describe(scenario="Scenario key, id, or name")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_play(self, ctx: commands.Context, scenario: str):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")

        chosen = await self._find_scenario(ctx.guild.id, scenario)
        if not chosen:
            return await ctx.send("Scenario not found. Use `/rp scenarios` first.")

        profile = await self._ensure_character(ctx.guild.id, ctx.author.id, settings)
        now = _utc_now()
        cooldown = max(0, _safe_int(settings.get("scenario_cooldown_seconds"), 900))
        last_scenario = _as_utc(profile.get("last_scenario_at"))
        if last_scenario and cooldown > 0:
            elapsed = int((now - last_scenario).total_seconds())
            if elapsed < cooldown:
                return await ctx.send(
                    f"Scenario cooldown active. Try again in {_duration_text(cooldown - elapsed)}."
                )

        base_xp = max(0, _safe_int(chosen.get("reward_xp"), 50))
        base_coins = max(0, _safe_int(chosen.get("reward_coins"), 100))
        reward_xp = random.randint(max(0, int(base_xp * 80 / 100)), max(1, int(base_xp * 120 / 100)))
        reward_coins = random.randint(max(0, int(base_coins * 80 / 100)), max(1, int(base_coins * 120 / 100)))
        reward_xp, reward_coins, guard_meta = await self._apply_reward_guard(
            ctx.guild.id,
            base_xp=reward_xp,
            base_coins=reward_coins,
        )
        updated = await self._save_character(
            profile,
            settings=settings,
            xp=_safe_int(profile.get("xp"), 0) + reward_xp,
            coins=_safe_int(profile.get("coins"), 0) + reward_coins,
            completed_scenarios=_safe_int(profile.get("completed_scenarios"), 0) + 1,
            last_scenario_at=now,
        )
        await self._upsert_scenario_stats(
            ctx.guild.id,
            scenario_key=str(chosen.get("scenario_key") or ""),
            scenario_name=str(chosen.get("name") or "Scenario"),
            play_count_delta=1,
            reward_xp_delta=reward_xp,
            reward_coins_delta=reward_coins,
        )
        await ctx.send(
            f"Scenario completed: **{chosen.get('name', 'Scenario')}** | "
            f"+{reward_xp} XP | +{self._coins_text(settings, reward_coins)} | "
            f"Level {_safe_int(updated.get('level'), 1)}"
            + (
                f" (Economy Guard {int(guard_meta.get('multiplier_percent') or 100)}%)"
                if int(guard_meta.get("multiplier_percent") or 100) < 100
                else ""
            )
        )

    @rp.command(name="scenarioadd", help="สร้างสถานการณ์การสวมบทบาทแบบกำหนดเอง")
    @app_commands.describe(
        name="Scenario title",
        description="คำอธิบายสถานการณ์",
        reward_xp="XP reward",
        reward_coins="Coin reward",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_scenario_add(
        self,
        ctx: commands.Context,
        name: str,
        description: str,
        reward_xp: int = 60,
        reward_coins: int = 120,
    ):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manager(ctx):
            return
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("allow_custom_scenarios")):
            return await ctx.send("Custom scenarios are disabled in this server config.")
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")

        all_rows = await rp_scenarios_db.gets(guild_id=ctx.guild.id)
        custom_rows = [row for row in all_rows if not bool(row.get("is_preset"))]
        max_custom = max(1, _safe_int(settings.get("max_custom_scenarios"), 30))
        if len(custom_rows) >= max_custom:
            return await ctx.send(
                f"Custom scenario limit reached ({max_custom}). Remove one with `/rp scenariodel`."
            )

        base_key = _normalize_key(name)[:36] or "scenario"
        scenario_key = f"custom_{base_key}"
        suffix = 2
        while await rp_scenarios_db.get(guild_id=ctx.guild.id, scenario_key=scenario_key):
            scenario_key = f"custom_{base_key[:28]}_{suffix}"
            suffix += 1

        created = await self._upsert_scenario(
            ctx.guild.id,
            scenario_key=scenario_key,
            name=str(name or "").strip()[:120] or "Custom Scenario",
            description=str(description or "").strip()[:800],
            template_key="custom",
            difficulty="normal",
            reward_xp=max(0, min(500_000, int(reward_xp))),
            reward_coins=max(0, min(500_000, int(reward_coins))),
            is_preset=False,
        )
        if not created:
            return await ctx.send("Failed to create custom scenario.")
        await ctx.send(f"Custom scenario created with key `{scenario_key}`.")

    @rp.command(name="scenariodel", help="ลบสถานการณ์การสวมบทบาทแบบกำหนดเอง")
    @app_commands.describe(scenario="Scenario key, id, or name")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_scenario_delete(self, ctx: commands.Context, scenario: str):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manager(ctx):
            return
        target = await self._find_scenario(ctx.guild.id, scenario)
        if not target:
            return await ctx.send("Scenario not found.")
        if bool(target.get("is_preset")):
            return await ctx.send("Preset scenarios cannot be deleted. Add custom scenarios instead.")
        await rp_scenarios_db.delete(id=target["id"])
        await ctx.send(f"Deleted scenario `{target.get('scenario_key', target.get('id'))}`.")

    @rp.command(name="event", help="แสดงกิจกรรมการสวมบทบาทที่ใช้งานอยู่")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_event(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        expired_summary = await self._finish_expired_event_if_needed(ctx.guild)
        if expired_summary:
            await ctx.send(
                f"Event ended automatically: **{expired_summary['title']}** | "
                f"Players rewarded: {expired_summary['participants']}."
            )
        event_row = await self._load_event(ctx.guild.id)
        if not event_row or str(event_row.get("status") or "").lower() != "active":
            return await ctx.send("No active roleplay event right now.")
        remain = self._event_remaining_seconds(event_row)
        participants = (
            event_row.get("participants") if isinstance(event_row.get("participants"), list) else []
        )
        await ctx.send(
            f"Active event: **{event_row.get('event_title', 'Roleplay Event')}**\n"
            f"Reward: +{_safe_int(event_row.get('reward_xp'), 0)} XP and "
            f"+{_safe_int(event_row.get('reward_coins'), 0):,}\n"
            f"Participants: {len(participants)}\n"
            f"Remaining: {_duration_text(remain)}\n"
            f"Join with `/rp eventjoin`."
        )

    @rp.command(name="eventstart", help="เริ่มงานแสดงบทบาทสมมติแบบสด")
    @app_commands.describe(
        scenario="Scenario key/name for this event (optional)",
        minutes="Event duration in minutes (5-180)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_event_start(
        self,
        ctx: commands.Context,
        scenario: str | None = None,
        minutes: int = 30,
    ):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manager(ctx):
            return
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")

        expired_summary = await self._finish_expired_event_if_needed(ctx.guild)
        if expired_summary:
            await ctx.send(
                f"Previous event auto-closed: **{expired_summary['title']}** "
                f"({expired_summary['participants']} players rewarded)."
            )

        event_row = await self._load_event(ctx.guild.id)
        if event_row and str(event_row.get("status") or "").lower() == "active":
            remain = self._event_remaining_seconds(event_row)
            return await ctx.send(
                f"An event is already active. Remaining time: {_duration_text(remain)}."
            )

        scenarios = await self._list_scenarios(ctx.guild.id)
        if not scenarios:
            return await ctx.send("No scenarios found. Run `/rp setup` first.")
        picked = None
        if scenario:
            picked = await self._find_scenario(ctx.guild.id, scenario)
            if not picked:
                return await ctx.send("Scenario not found for event start.")
        if not picked:
            picked = random.choice(scenarios)

        duration_minutes = max(5, min(180, int(minutes or 30)))
        now = _utc_now()
        ends_at = now + datetime.timedelta(minutes=duration_minutes)
        base_xp = max(_safe_int(settings.get("event_reward_xp"), 120), _safe_int(picked.get("reward_xp"), 50))
        base_coins = max(
            _safe_int(settings.get("event_reward_coins"), 220),
            _safe_int(picked.get("reward_coins"), 100),
        )

        payload = {
            "guild_id": ctx.guild.id,
            "status": "active",
            "event_title": str(picked.get("name") or "Roleplay Event"),
            "template_key": str(picked.get("scenario_key") or ""),
            "description": str(picked.get("description") or ""),
            "reward_xp": base_xp,
            "reward_coins": base_coins,
            "participants": [],
            "started_by": ctx.author.id,
            "trigger_type": "manual_command_start",
            "schedule_name": "",
            "started_at": now,
            "ends_at": ends_at,
            "updated_at": now,
        }
        if event_row:
            await rp_events_db.update(id=event_row["id"], **payload)
        else:
            await rp_events_db.insert(**payload)
        await self._upsert_scenario_stats(
            ctx.guild.id,
            scenario_key=str(picked.get("scenario_key") or ""),
            scenario_name=str(picked.get("name") or "Scenario"),
            event_start_delta=1,
        )

        await ctx.send(
            f"Event started: **{payload['event_title']}**\n"
            f"Duration: {duration_minutes} minutes\n"
            f"Reward per participant: +{base_xp} XP and +{self._coins_text(settings, base_coins)}\n"
            f"Use `/rp eventjoin` to participate."
        )

    @rp.command(name="eventjoin", help="เข้าร่วมกิจกรรมสวมบทบาทที่กระตือรือร้น")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_event_join(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        settings = await self._ensure_settings(ctx.guild.id)
        if not bool(settings.get("enabled")):
            return await ctx.send("Roleplay is disabled. Use `/rp setup` first.")

        expired_summary = await self._finish_expired_event_if_needed(ctx.guild)
        if expired_summary:
            await ctx.send(
                f"You were late: previous event **{expired_summary['title']}** has already ended."
            )
            return

        event_row = await self._load_event(ctx.guild.id)
        if not event_row or str(event_row.get("status") or "").lower() != "active":
            return await ctx.send("No active event to join.")
        await self._ensure_character(ctx.guild.id, ctx.author.id, settings)
        participants = (
            event_row.get("participants") if isinstance(event_row.get("participants"), list) else []
        )
        participant_ids = {str(item).strip() for item in participants}
        author_id = str(ctx.author.id)
        if author_id in participant_ids:
            return await ctx.send("You already joined this event.")
        participants.append(author_id)
        await rp_events_db.update(id=event_row["id"], participants=participants, updated_at=_utc_now())
        await ctx.send(
            f"You joined **{event_row.get('event_title', 'Roleplay Event')}**. "
            f"Total participants: {len(participants)}."
        )

    @rp.command(name="eventend", help="ยุติกิจกรรมสวมบทบาทที่ดำเนินอยู่และแจกจ่ายรางวัล")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def rp_event_end(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manager(ctx):
            return
        event_row = await self._load_event(ctx.guild.id)
        if not event_row or str(event_row.get("status") or "").lower() != "active":
            return await ctx.send("No active event to end.")
        summary = await self._finish_event(ctx.guild, event_row, trigger_type="manual_command")
        await ctx.send(
            f"Event ended: **{summary['title']}**\n"
            f"Rewarded players: {summary['participants']}\n"
            f"Total rewards: +{summary['total_xp']} XP and +{summary['coins_text']}"
            + (
                f"\nEconomy Guard applied: {int(summary.get('guard_multiplier_percent') or 100)}%"
                if int(summary.get("guard_multiplier_percent") or 100) < 100
                else ""
            )
        )
