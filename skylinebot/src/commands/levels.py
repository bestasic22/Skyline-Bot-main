from __future__ import annotations

import asyncio
import datetime
import json
import random
import time
from typing import Any

import discord
from discord.ext import commands

import storage.dashboard_config as dashboard_config_db
import storage.levels_users as levels_users_db
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.memory.cache import cache
from skylinebot.src.checks import checks
from skylinebot.src.checks.variables import fetch_variables
from skylinebot.style import color
from skylinebot.workflows.notice_cards import build_member_notice_card

LEVELS_CONFIG_KEY_PREFIX = "probot_levels_v1_guild_"


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_plan_tier(raw_plan: Any) -> str:
    raw = str(raw_plan or "").strip().lower()
    mapping = {
        "free": "free",
        "silver": "silver",
        "silver_guild_preminum": "silver",
        "silver_guild_premium": "silver",
        "premium_silver": "silver",
        "golden": "golden",
        "gold": "golden",
        "golden_guild_premium": "golden",
        "diamond": "diamond",
        "diamond_guild_premium": "diamond",
        "permanent": "permanent",
        "lifetime": "permanent",
        "forever": "permanent",
        "permanent_guild_premium": "permanent",
        "lifetime_guild_premium": "permanent",
        "ultra": "diamond",
    }
    return mapping.get(raw, "free")


def _levels_plan_caps(plan_tier: str) -> dict[str, Any]:
    tier = _normalize_plan_tier(plan_tier)
    caps_map: dict[str, dict[str, Any]] = {
        "free": {
            "can_use": False,
            "text_xp": False,
            "voice_xp": False,
            "command_xp": False,
            "reaction_xp": False,
            "max_rewards": 0,
            "max_level": 50,
        },
        "silver": {
            "can_use": True,
            "text_xp": True,
            "voice_xp": False,
            "command_xp": True,
            "reaction_xp": False,
            "max_rewards": 3,
            "max_level": 120,
        },
        "golden": {
            "can_use": True,
            "text_xp": True,
            "voice_xp": True,
            "command_xp": True,
            "reaction_xp": False,
            "max_rewards": 8,
            "max_level": 200,
        },
        "diamond": {
            "can_use": True,
            "text_xp": True,
            "voice_xp": True,
            "command_xp": True,
            "reaction_xp": True,
            "max_rewards": 20,
            "max_level": 500,
        },
        "permanent": {
            "can_use": True,
            "text_xp": True,
            "voice_xp": True,
            "command_xp": True,
            "reaction_xp": True,
            "max_rewards": 20,
            "max_level": 500,
        },
    }
    return dict(caps_map.get(tier, caps_map["free"]))


def _default_levels_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "notify_channel_id": "",
        "notify_message": "🎉 {user} อัปเลเวลเป็น {level} แล้ว!",
        "notify_send_text": True,
        "notify_send_embed": False,
        "notify_send_image": False,
        "notify_embed_title": "Level up!",
        "notify_embed_description": "{user.mention} reached level {level} (XP {xp})",
        "notify_image_theme": "music",
        "notify_image_theme_url": "",
        "notify_image_layout_mode": "center_stack",
        "notify_image_avatar_position": "center",
        "notify_image_text_align": "center",
        "notify_image_font_style": "classic",
        "notify_image_top_text": "{user}",
        "notify_image_bottom_text": "Level {level}",
        "max_level": 120,
        "sources": {
            "text": True,
            "voice": False,
            "command": True,
            "reaction": False,
        },
        "text_xp_min": 8,
        "text_xp_max": 14,
        "text_cooldown": 45,
        "voice_xp_gain": 6,
        "voice_cooldown": 300,
        "command_xp_gain": 5,
        "command_cooldown": 120,
        "reaction_xp_gain": 2,
        "reaction_cooldown": 90,
        "reward_roles": [],
        "stack_reward_roles": False,
    }


def _normalize_levels_settings(payload: dict[str, Any] | None, *, plan_tier: str = "free") -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_levels_settings()
    caps = _levels_plan_caps(plan_tier)

    def _safe_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    out["enabled"] = _safe_bool(src.get("enabled"), out["enabled"])
    channel_id = str(src.get("notify_channel_id") or "").strip()
    out["notify_channel_id"] = channel_id if channel_id.isdigit() else ""
    out["notify_message"] = str(src.get("notify_message") or out["notify_message"]).strip()[:800] or out["notify_message"]
    out["notify_send_text"] = _safe_bool(src.get("notify_send_text"), True)
    out["notify_send_embed"] = _safe_bool(src.get("notify_send_embed"), False)
    out["notify_send_image"] = _safe_bool(src.get("notify_send_image"), False)
    out["notify_embed_title"] = str(src.get("notify_embed_title") or out["notify_embed_title"]).strip()[:200]
    out["notify_embed_description"] = str(src.get("notify_embed_description") or out["notify_embed_description"]).strip()[:900]
    allowed_theme_keys = {"music", "security", "giveaway", "custom", "user", "guild"}
    notify_image_theme = str(src.get("notify_image_theme") or out["notify_image_theme"]).strip().lower()[:32]
    out["notify_image_theme"] = notify_image_theme if notify_image_theme in allowed_theme_keys else "music"
    out["notify_image_theme_url"] = str(src.get("notify_image_theme_url") or out["notify_image_theme_url"]).strip()[:1000]
    out["notify_image_layout_mode"] = str(src.get("notify_image_layout_mode") or out["notify_image_layout_mode"]).strip().lower()[:32] or "center_stack"
    out["notify_image_avatar_position"] = str(src.get("notify_image_avatar_position") or out["notify_image_avatar_position"]).strip().lower()[:32] or "center"
    out["notify_image_text_align"] = str(src.get("notify_image_text_align") or out["notify_image_text_align"]).strip().lower()[:32] or "center"
    allowed_font_styles = {"classic", "clean", "impact", "soft"}
    notify_image_font_style = str(src.get("notify_image_font_style") or out["notify_image_font_style"]).strip().lower()[:32]
    out["notify_image_font_style"] = notify_image_font_style if notify_image_font_style in allowed_font_styles else "classic"
    out["notify_image_top_text"] = str(src.get("notify_image_top_text") or out["notify_image_top_text"]).strip()[:240]
    out["notify_image_bottom_text"] = str(src.get("notify_image_bottom_text") or out["notify_image_bottom_text"]).strip()[:260]
    out["max_level"] = _safe_int(src.get("max_level"), out["max_level"], 5, int(caps.get("max_level") or 120))
    raw_sources = src.get("sources") if isinstance(src.get("sources"), dict) else {}
    out["sources"] = {
        "text": _safe_bool(raw_sources.get("text"), True) and bool(caps.get("text_xp")),
        "voice": _safe_bool(raw_sources.get("voice"), False) and bool(caps.get("voice_xp")),
        "command": _safe_bool(raw_sources.get("command"), True) and bool(caps.get("command_xp")),
        "reaction": _safe_bool(raw_sources.get("reaction"), False) and bool(caps.get("reaction_xp")),
    }
    out["text_xp_min"] = _safe_int(src.get("text_xp_min"), out["text_xp_min"], 0, 300)
    out["text_xp_max"] = _safe_int(src.get("text_xp_max"), out["text_xp_max"], out["text_xp_min"], 600)
    out["text_cooldown"] = _safe_int(src.get("text_cooldown"), out["text_cooldown"], 0, 3600)
    out["voice_xp_gain"] = _safe_int(src.get("voice_xp_gain"), out["voice_xp_gain"], 0, 200)
    out["voice_cooldown"] = _safe_int(src.get("voice_cooldown"), out["voice_cooldown"], 10, 3600)
    out["command_xp_gain"] = _safe_int(src.get("command_xp_gain"), out["command_xp_gain"], 0, 300)
    out["command_cooldown"] = _safe_int(src.get("command_cooldown"), out["command_cooldown"], 10, 3600)
    out["reaction_xp_gain"] = _safe_int(src.get("reaction_xp_gain"), out["reaction_xp_gain"], 0, 100)
    out["reaction_cooldown"] = _safe_int(src.get("reaction_cooldown"), out["reaction_cooldown"], 5, 3600)
    out["stack_reward_roles"] = _safe_bool(src.get("stack_reward_roles"), False)

    raw_rewards = src.get("reward_roles")
    rewards: list[dict[str, Any]] = []
    if isinstance(raw_rewards, list):
        for index, raw_row in enumerate(raw_rewards[:30]):
            row = raw_row if isinstance(raw_row, dict) else {}
            role_id = str(row.get("role_id") or "").strip()
            if not role_id.isdigit():
                continue
            rewards.append(
                {
                    "id": str(row.get("id") or f"reward_{index+1}"),
                    "level": _safe_int(row.get("level"), (index + 1) * 10, 1, 1000),
                    "role_id": role_id,
                }
            )
    rewards.sort(key=lambda item: int(item.get("level") or 0))
    out["reward_roles"] = rewards[: int(caps.get("max_rewards") or 0)]

    if not bool(caps.get("can_use")):
        out["enabled"] = False
        out["sources"] = {"text": False, "voice": False, "command": False, "reaction": False}
        out["reward_roles"] = []
        out["notify_send_image"] = False
    return out


class Levels(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._cooldowns: dict[str, float] = {}
        self._voice_xp_task: asyncio.Task | None = None

        class CogInfo:
            name = "Levels"
            category = "Fun"
            description = "Guild leveling system"
            hidden = False
            emoji = "📈"

        self.cog_info = CogInfo

    async def cog_load(self) -> None:
        if self._voice_xp_task is None or self._voice_xp_task.done():
            self._voice_xp_task = asyncio.create_task(self._voice_xp_loop())

    def cog_unload(self) -> None:
        task = self._voice_xp_task
        if task and not task.done():
            task.cancel()

    async def _wait_until_ready_safely(self) -> bool:
        while not self.bot.is_closed():
            # This loop may start before login() during extension bootstrap.
            # Polling bot.is_ready() avoids RuntimeError from wait_until_ready().
            if getattr(self.bot, "user", None) is not None and self.bot.is_ready():
                return True
            await asyncio.sleep(1)
        return False

    async def _voice_xp_loop(self) -> None:
        if not await self._wait_until_ready_safely():
            return
        while not self.bot.is_closed():
            for guild in list(getattr(self.bot, "guilds", []) or []):
                try:
                    await self._tick_voice_xp_for_guild(guild)
                except Exception:
                    continue
            await asyncio.sleep(12)

    def _config_key(self, guild_id: int) -> str:
        return f"{LEVELS_CONFIG_KEY_PREFIX}{int(guild_id)}"

    def _guild_plan_tier(self, guild_id: int) -> str:
        guild_data = cache.guilds.get(str(guild_id), {}) or {}
        return _normalize_plan_tier(guild_data.get("subscription", "free"))

    async def _get_levels_settings(self, guild_id: int) -> dict[str, Any]:
        row = await dashboard_config_db.get(config_key=self._config_key(guild_id))
        if not row:
            return _normalize_levels_settings({}, plan_tier=self._guild_plan_tier(guild_id))
        raw = str(row.get("config_value") or "").strip()
        if not raw:
            return _normalize_levels_settings({}, plan_tier=self._guild_plan_tier(guild_id))
        try:
            decoded = json.loads(raw)
        except Exception:
            decoded = {}
        return _normalize_levels_settings(decoded if isinstance(decoded, dict) else {}, plan_tier=self._guild_plan_tier(guild_id))

    async def _set_levels_settings(self, guild_id: int, payload: dict[str, Any]) -> None:
        normalized = _normalize_levels_settings(payload, plan_tier=self._guild_plan_tier(guild_id))
        config_value = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        writer = getattr(dashboard_config_db, "set_config_value", None)
        if callable(writer):
            await writer(config_key=self._config_key(guild_id), config_value=config_value)
        else:
            row = await dashboard_config_db.get(config_key=self._config_key(guild_id))
            if row:
                await dashboard_config_db.update(id=row["id"], config_value=config_value)
            else:
                await dashboard_config_db.insert(config_key=self._config_key(guild_id), config_value=config_value)

    def _xp_needed_for_level(self, level: int) -> int:
        value = 80 + int((level ** 2) * 35)
        return max(100, value)

    def _resolve_level(self, total_xp: int, max_level: int) -> int:
        xp = max(0, int(total_xp))
        level = 0
        while level < max_level and xp >= self._xp_needed_for_level(level + 1):
            level += 1
        return level

    def _cooldown_key(self, guild_id: int, user_id: int, source: str) -> str:
        return f"{int(guild_id)}:{int(user_id)}:{str(source)}"

    def _cooldown_passed(self, guild_id: int, user_id: int, source: str, cooldown: int) -> bool:
        now = time.monotonic()
        key = self._cooldown_key(guild_id, user_id, source)
        last = float(self._cooldowns.get(key, 0.0))
        if (now - last) < max(0, cooldown):
            return False
        self._cooldowns[key] = now
        return True

    def _touch_cooldown(self, guild_id: int, user_id: int, source: str) -> None:
        key = self._cooldown_key(guild_id, user_id, source)
        self._cooldowns[key] = time.monotonic()

    def _clear_cooldown(self, guild_id: int, user_id: int, source: str) -> None:
        key = self._cooldown_key(guild_id, user_id, source)
        self._cooldowns.pop(key, None)

    async def _tick_voice_xp_for_guild(self, guild: discord.Guild) -> None:
        if guild is None:
            return
        settings = await self._get_levels_settings(guild.id)
        if not bool(settings.get("enabled")):
            return
        sources = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
        if not bool(sources.get("voice")):
            return
        gain = _safe_int(settings.get("voice_xp_gain"), 6)
        if gain <= 0:
            return
        cooldown = _safe_int(settings.get("voice_cooldown"), 300)
        afk_channel_id = getattr(getattr(guild, "afk_channel", None), "id", None)

        for channel in list(getattr(guild, "voice_channels", []) or []):
            if afk_channel_id and int(getattr(channel, "id", 0)) == int(afk_channel_id):
                continue
            for member in list(getattr(channel, "members", []) or []):
                if member.bot:
                    continue
                voice_state = getattr(member, "voice", None)
                if voice_state is None or getattr(voice_state, "channel", None) is None:
                    continue
                if bool(getattr(voice_state, "deaf", False)) or bool(getattr(voice_state, "self_deaf", False)):
                    continue
                if not self._cooldown_passed(guild.id, member.id, "voice_live", cooldown):
                    continue
                await self._add_xp(guild=guild, member=member, source="voice", amount=gain)

    async def _ensure_user_row(self, guild_id: int, user_id: int) -> dict[str, Any]:
        row = await levels_users_db.get(guild_id=guild_id, user_id=user_id)
        if row:
            return row
        await levels_users_db.insert(guild_id=guild_id, user_id=user_id)
        return await levels_users_db.get(guild_id=guild_id, user_id=user_id) or {}

    async def _apply_reward_roles(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        settings: dict[str, Any],
        level: int,
    ) -> None:
        rewards = settings.get("reward_roles") if isinstance(settings.get("reward_roles"), list) else []
        if not rewards:
            return
        candidate_roles: list[tuple[int, discord.Role]] = []
        all_reward_ids: set[int] = set()
        for row in rewards:
            if not isinstance(row, dict):
                continue
            role_id = _safe_int(row.get("role_id"), 0)
            level_gate = _safe_int(row.get("level"), 0)
            if role_id <= 0:
                continue
            all_reward_ids.add(role_id)
            role = guild.get_role(role_id)
            if role is None:
                continue
            if level >= level_gate:
                candidate_roles.append((level_gate, role))
        if not candidate_roles:
            return
        stack = bool(settings.get("stack_reward_roles"))
        try:
            if stack:
                to_add = [role for _, role in candidate_roles if role not in member.roles]
                if to_add:
                    await member.add_roles(*to_add, reason="Levels reward roles")
                return
            top_reward_role = sorted(candidate_roles, key=lambda item: item[0], reverse=True)[0][1]
            removable = [role for role in member.roles if role.id in all_reward_ids and role.id != top_reward_role.id]
            if removable:
                await member.remove_roles(*removable, reason="Levels reward role sync")
            if top_reward_role not in member.roles:
                await member.add_roles(top_reward_role, reason="Levels reward role")
        except Exception:
            return

    async def _announce_level_up(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        settings: dict[str, Any],
        level: int,
        total_xp: int,
    ) -> None:
        channel_id = _safe_int(settings.get("notify_channel_id"), 0)
        if channel_id <= 0:
            return
        channel = guild.get_channel(channel_id)
        if channel is None or not hasattr(channel, "send"):
            return
        send_text = bool(settings.get("notify_send_text", True))
        send_embed = bool(settings.get("notify_send_embed", False))
        send_image = bool(settings.get("notify_send_image", False))
        if not (send_text or send_embed or send_image):
            return

        def _render_template(raw_template: Any, fallback: str = "") -> str:
            source = str(raw_template or fallback).strip()
            if not source:
                return ""
            rendered = fetch_variables(text=source, member=member, guild=guild) or ""
            rendered = rendered.replace("{level}", str(level)).replace("{xp}", str(total_xp))
            return rendered

        fallback_text = "🎉 {user.mention} reached level {level}!"
        message = _render_template(settings.get("notify_message"), fallback_text)
        if not message:
            message = _render_template(fallback_text, fallback_text)

        embed: discord.Embed | None = None
        if send_embed:
            embed_title = _render_template(settings.get("notify_embed_title"), "Level up!")
            embed_description = _render_template(
                settings.get("notify_embed_description"),
                "{user.mention} reached level {level} (XP {xp})",
            )
            embed = discord.Embed(
                title=(embed_title or "Level up!")[:256],
                description=(embed_description or message or fallback_text)[:4096],
                color=color.green,
            )
            try:
                embed.set_thumbnail(url=member.display_avatar.url)
            except Exception:
                pass

        attached_file: discord.File | None = None
        if send_image:
            top_text = _render_template(settings.get("notify_image_top_text"), "{user}")
            bottom_text = _render_template(settings.get("notify_image_bottom_text"), "Level {level}")
            card_bytes = build_member_notice_card(
                avatar_url=str(member.display_avatar.url),
                top_text=top_text,
                bottom_text=bottom_text,
                theme_key=settings.get("notify_image_theme", "music"),
                theme_url=settings.get("notify_image_theme_url"),
                user_theme_url=str(member.display_avatar.url),
                guild_theme_url=str(getattr(getattr(guild, "icon", None), "url", "") or ""),
                layout_mode=settings.get("notify_image_layout_mode", "center_stack"),
                avatar_position=settings.get("notify_image_avatar_position", "center"),
                text_align=settings.get("notify_image_text_align", "center"),
                font_style=settings.get("notify_image_font_style", "classic"),
            )
            if card_bytes is not None:
                attached_file = discord.File(card_bytes, filename="level-notice.png")
                if embed and not (getattr(embed, "image", None) and getattr(embed.image, "url", "")):
                    embed.set_image(url="attachment://level-notice.png")

        payload: dict[str, Any] = {}
        if send_text:
            payload["content"] = message[:1800]
        if embed is not None:
            payload["embed"] = embed
        if attached_file is not None:
            payload["file"] = attached_file
        if not payload:
            payload["content"] = message[:1800]

        try:
            await channel.send(**payload)
        except Exception:
            return

    async def _add_xp(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        source: str,
        amount: int,
    ) -> None:
        if guild is None or member is None or member.bot:
            return
        settings = await self._get_levels_settings(guild.id)
        plan_caps = _levels_plan_caps(self._guild_plan_tier(guild.id))
        if not bool(plan_caps.get("can_use")):
            return
        if not bool(settings.get("enabled")):
            return
        source_map = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
        if not bool(source_map.get(source)):
            return
        gain = max(0, int(amount))
        if gain <= 0:
            return

        row = await self._ensure_user_row(guild.id, member.id)
        before_total = _safe_int(row.get("total_xp"), 0)
        max_level = _safe_int(settings.get("max_level"), 120)
        before_level = self._resolve_level(before_total, max_level)
        after_total = max(0, before_total + gain)
        after_level = self._resolve_level(after_total, max_level)
        payload: dict[str, Any] = {
            "id": row["id"],
            "total_xp": after_total,
            "level": after_level,
            "updated_at": _utc_now(),
        }
        field_name = {
            "text": "text_xp",
            "voice": "voice_xp",
            "command": "command_xp",
            "reaction": "reaction_xp",
        }.get(source, "")
        if field_name:
            payload[field_name] = _safe_int(row.get(field_name), 0) + gain
        await levels_users_db.update(**payload)

        if after_level > before_level:
            await self._apply_reward_roles(guild=guild, member=member, settings=settings, level=after_level)
            await self._announce_level_up(
                guild=guild,
                member=member,
                settings=settings,
                level=after_level,
                total_xp=after_total,
            )

    async def _is_level_admin(self, ctx: commands.Context) -> bool:
        if ctx.author == ctx.guild.owner:
            return True
        if getattr(ctx.author.guild_permissions, "administrator", False):
            return True
        return bool(getattr(ctx.author.guild_permissions, "manage_guild", False))

    async def _ensure_guild_enabled(self, ctx: commands.Context) -> tuple[bool, dict[str, Any], dict[str, Any]]:
        settings = await self._get_levels_settings(ctx.guild.id)
        plan_tier = self._guild_plan_tier(ctx.guild.id)
        caps = _levels_plan_caps(plan_tier)
        if not bool(caps.get("can_use")):
            await ctx.send(embed=discord.Embed(description="แพ็กเกจ Free ไม่สามารถใช้งานระบบเลเวลได้", color=color.red))
            return False, settings, caps
        return True, settings, caps

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        settings = await self._get_levels_settings(message.guild.id)
        if not settings.get("enabled"):
            return
        sources = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
        if not bool(sources.get("text")):
            return
        cooldown = _safe_int(settings.get("text_cooldown"), 45)
        if not self._cooldown_passed(message.guild.id, message.author.id, "text", cooldown):
            return
        content = str(message.content or "").strip()
        if len(content) < 3 and not message.attachments:
            return
        minimum = _safe_int(settings.get("text_xp_min"), 8)
        maximum = _safe_int(settings.get("text_xp_max"), 14)
        if maximum < minimum:
            maximum = minimum
        gain = random.randint(minimum, maximum)
        await self._add_xp(guild=message.guild, member=message.author, source="text", amount=gain)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or member.guild is None:
            return
        if before.channel == after.channel:
            return
        if before.channel is None and after.channel is not None:
            # Start counting from the time user joined voice; XP will be granted per cooldown cycle.
            self._touch_cooldown(member.guild.id, member.id, "voice_live")
        if before.channel is not None and after.channel is None:
            self._clear_cooldown(member.guild.id, member.id, "voice_live")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        if not ctx.guild or not ctx.author or ctx.author.bot:
            return
        settings = await self._get_levels_settings(ctx.guild.id)
        if not settings.get("enabled"):
            return
        sources = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
        if not bool(sources.get("command")):
            return
        cooldown = _safe_int(settings.get("command_cooldown"), 120)
        if not self._cooldown_passed(ctx.guild.id, ctx.author.id, "command", cooldown):
            return
        gain = _safe_int(settings.get("command_xp_gain"), 5)
        await self._add_xp(guild=ctx.guild, member=ctx.author, source="command", amount=gain)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return
        settings = await self._get_levels_settings(guild.id)
        if not settings.get("enabled"):
            return
        sources = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
        if not bool(sources.get("reaction")):
            return
        cooldown = _safe_int(settings.get("reaction_cooldown"), 90)
        if not self._cooldown_passed(guild.id, member.id, "reaction", cooldown):
            return
        gain = _safe_int(settings.get("reaction_xp_gain"), 2)
        await self._add_xp(guild=guild, member=member, source="reaction", amount=gain)

    @commands.hybrid_group(
        name="level",
        aliases=["levels"],
        help="Leveling system commands (คำสั่งระบบเลเวล)",
        description="Leveling system commands (คำสั่งระบบเลเวล)",
        invoke_without_command=True,
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def level_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is not None:
            return
        ok, settings, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        status = "เปิดใช้งาน" if settings.get("enabled") else "ปิดใช้งาน"
        embed = discord.Embed(
            title="ระบบเลเวล",
            color=color.blue,
            description=(
                f"สถานะ: **{status}**\n"
                "คำสั่งหลัก: `/level rank`, `/level leaderboard`, `/level settings`"
            ),
        )
        await ctx.send(embed=embed)

    @level_group.command(
        name="rank",
        help="Show a member's level rank (แสดงเลเวลของสมาชิก)",
        description="Show a member's level rank (แสดงเลเวลของสมาชิก)",
    )
    async def level_rank(self, ctx: commands.Context, member: discord.Member | None = None):
        ok, settings, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not settings.get("enabled"):
            await ctx.send("ระบบเลเวลยังไม่เปิดใช้งานในเซิร์ฟเวอร์นี้")
            return
        target = member or ctx.author
        row = await self._ensure_user_row(ctx.guild.id, target.id)
        total_xp = _safe_int(row.get("total_xp"), 0)
        level = _safe_int(row.get("level"), 0)
        embed = discord.Embed(
            title=f"ระดับของ {target.display_name}",
            description=f"Level: **{level}**\nXP รวม: **{total_xp:,}**",
            color=color.green,
        )
        await ctx.send(embed=embed)

    @level_group.command(
        name="leaderboard",
        help="Show the level leaderboard (แสดงลีดเดอร์บอร์ดเลเวล)",
        description="Show the level leaderboard (แสดงลีดเดอร์บอร์ดเลเวล)",
    )
    async def level_leaderboard(self, ctx: commands.Context):
        ok, settings, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not settings.get("enabled"):
            await ctx.send("ระบบเลเวลยังไม่เปิดใช้งานในเซิร์ฟเวอร์นี้")
            return
        rows = await levels_users_db.gets(guild_id=ctx.guild.id)
        rows = rows or []
        rows.sort(key=lambda item: _safe_int(item.get("total_xp"), 0), reverse=True)
        lines: list[str] = []
        for index, row in enumerate(rows[:10], start=1):
            user_id = _safe_int(row.get("user_id"), 0)
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else str(user_id)
            lines.append(
                f"`#{index}` **{name}** - Lv.{_safe_int(row.get('level'), 0)} ({_safe_int(row.get('total_xp'), 0):,} XP)"
            )
        if not lines:
            lines.append("ยังไม่มีข้อมูลเลเวล")
        embed = discord.Embed(title="Leaderboard ระบบเลเวล", description="\n".join(lines), color=color.blue)
        await ctx.send(embed=embed)

    @level_group.command(
        name="settings",
        help="Show level system settings (แสดงการตั้งค่าระบบเลเวล)",
        description="Show level system settings (แสดงการตั้งค่าระบบเลเวล)",
    )
    async def level_settings(self, ctx: commands.Context):
        ok, settings, caps = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        status = "เปิดใช้งาน" if settings.get("enabled") else "ปิดใช้งาน"
        sources = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
        embed = discord.Embed(
            title="ตั้งค่าระบบเลเวล",
            color=color.blue,
            description=(
                f"สถานะ: **{status}**\n"
                f"โหมดพิมพ์: `{bool(sources.get('text'))}` | โหมดเสียง: `{bool(sources.get('voice'))}`\n"
                f"โหมดคำสั่ง: `{bool(sources.get('command'))}` | โหมดรีแอ็กชัน: `{bool(sources.get('reaction'))}`\n"
                f"รางวัลสูงสุดตามแพ็กเกจ: **{int(caps.get('max_rewards') or 0)}**"
            ),
        )
        await ctx.send(embed=embed)

    @level_group.command(
        name="toggle",
        help="Enable or disable the level system (เปิดหรือปิดระบบเลเวล)",
        description="Enable or disable the level system (เปิดหรือปิดระบบเลเวล)",
    )
    async def level_toggle(self, ctx: commands.Context, enabled: bool):
        ok, settings, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not await self._is_level_admin(ctx):
            await ctx.send("คุณไม่มีสิทธิ์จัดการระบบเลเวล")
            return
        settings["enabled"] = bool(enabled)
        await self._set_levels_settings(ctx.guild.id, settings)
        await ctx.send(f"อัปเดตระบบเลเวลเป็น: {'เปิดใช้งาน' if enabled else 'ปิดใช้งาน'}")

    @level_group.command(
        name="source",
        help="Enable or disable XP sources (เปิดหรือปิดแหล่งรับ XP)",
        description="Enable or disable XP sources (เปิดหรือปิดแหล่งรับ XP)",
    )
    async def level_source(self, ctx: commands.Context, source: str, enabled: bool):
        ok, settings, caps = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not await self._is_level_admin(ctx):
            await ctx.send("คุณไม่มีสิทธิ์จัดการระบบเลเวล")
            return
        source_key = str(source or "").strip().lower()
        if source_key not in {"text", "voice", "command", "reaction"}:
            await ctx.send("เลือก source ได้เฉพาะ: text, voice, command, reaction")
            return
        cap_key = f"{source_key}_xp"
        if not bool(caps.get(cap_key)):
            await ctx.send(f"แพ็กเกจปัจจุบันยังไม่รองรับโหมด `{source_key}`")
            return
        sources = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
        sources[source_key] = bool(enabled)
        settings["sources"] = sources
        await self._set_levels_settings(ctx.guild.id, settings)
        await ctx.send(f"อัปเดตโหมด `{source_key}` เป็น {'เปิด' if enabled else 'ปิด'} แล้ว")

    @level_group.command(
        name="notify-channel",
        help="Set level-up notification channel (ตั้งค่าห้องแจ้งเตือนเลเวล)",
        description="Set level-up notification channel (ตั้งค่าห้องแจ้งเตือนเลเวล)",
    )
    async def level_notify_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        ok, settings, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not await self._is_level_admin(ctx):
            await ctx.send("คุณไม่มีสิทธิ์จัดการระบบเลเวล")
            return
        settings["notify_channel_id"] = str(channel.id)
        await self._set_levels_settings(ctx.guild.id, settings)
        await ctx.send(f"ตั้งห้องแจ้งเตือนเลเวลเป็น {channel.mention} แล้ว")

    @level_group.command(
        name="notify-message",
        help="Set level-up notification message (ตั้งค่าข้อความแจ้งเตือนเลเวล)",
        description="Set level-up notification message (ตั้งค่าข้อความแจ้งเตือนเลเวล)",
    )
    async def level_notify_message(self, ctx: commands.Context, *, message: str):
        ok, settings, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not await self._is_level_admin(ctx):
            await ctx.send("คุณไม่มีสิทธิ์จัดการระบบเลเวล")
            return
        settings["notify_message"] = str(message or "").strip()[:800] or "🎉 {user} อัปเลเวลเป็น {level} แล้ว!"
        await self._set_levels_settings(ctx.guild.id, settings)
        await ctx.send("บันทึกข้อความแจ้งเตือนเลเวลแล้ว")


    @level_group.command(
        name="reset_user",
        help="Reset one member's level data (รีเซ็ตข้อมูลเลเวลของสมาชิกคนเดียว)",
        description="Reset one member's level data (รีเซ็ตข้อมูลเลเวลของสมาชิกคนเดียว)",
    )
    async def level_reset_user(self, ctx: commands.Context, member: discord.Member):
        ok, _, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not await self._is_level_admin(ctx):
            await ctx.send("คุณไม่มีสิทธิ์รีเซ็ตเลเวลในเซิร์ฟเวอร์นี้")
            return
        if member.bot:
            await ctx.send("ไม่สามารถรีเซ็ตข้อมูลเลเวลของบอทได้")
            return
        deleted_rows = await levels_users_db.delete(guild_id=ctx.guild.id, user_id=member.id)
        if deleted_rows:
            await ctx.send(f"รีเซ็ตข้อมูลเลเวลของ {member.mention} เรียบร้อยแล้ว")
            return
        await ctx.send(f"{member.mention} ยังไม่มีข้อมูลเลเวลให้รีเซ็ต")

    @level_group.command(
        name="reset_all",
        help="Reset all level data in this guild (รีเซ็ตข้อมูลเลเวลทั้งเซิร์ฟเวอร์)",
        description="Reset all level data in this guild (รีเซ็ตข้อมูลเลเวลทั้งเซิร์ฟเวอร์)",
    )
    async def level_reset_all(self, ctx: commands.Context, confirm: bool = False):
        ok, _, _ = await self._ensure_guild_enabled(ctx)
        if not ok:
            return
        if not await self._is_level_admin(ctx):
            await ctx.send("คุณไม่มีสิทธิ์รีเซ็ตเลเวลในเซิร์ฟเวอร์นี้")
            return
        if not confirm:
            await ctx.send("เพื่อความปลอดภัย ให้ยืนยันคำสั่ง: `/level reset_all confirm:true`")
            return
        deleted_rows = await levels_users_db.delete(guild_id=ctx.guild.id)
        await ctx.send(f"รีเซ็ตข้อมูลเลเวลสมาชิกทั้งหมดในเซิร์ฟเวอร์แล้ว ({len(deleted_rows or [])} คน)")
