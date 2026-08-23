from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import storage.dashboard_config as dashboard_config_db
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color as style_color

COLOR_SETS_CONFIG_KEY_PREFIX = "probot_colors_v1_guild_"
SETTINGS_FETCH_TIMEOUT_SECONDS = 2.4


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _default_color_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "command_color_enabled": True,
        "command_colors_enabled": True,
        "list_name": "Color List",
    }


def _normalize_color_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_color_settings()
    out["enabled"] = _as_bool(src.get("enabled"), out["enabled"])
    out["command_color_enabled"] = _as_bool(
        src.get("command_color_enabled"),
        out["command_color_enabled"],
    )
    out["command_colors_enabled"] = _as_bool(
        src.get("command_colors_enabled"),
        out["command_colors_enabled"],
    )
    out["list_name"] = str(src.get("list_name") or out["list_name"]).strip()[:60] or out["list_name"]
    return out


def _collect_color_roles(guild: discord.Guild) -> list[discord.Role]:
    roles: list[discord.Role] = []
    for role in guild.roles:
        role_name = str(getattr(role, "name", "") or "").strip()
        if not role_name.isdigit():
            continue
        if role.is_default() or role.managed:
            continue
        roles.append(role)
    roles.sort(key=lambda item: int(item.name))
    return roles


class ColorRoles(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._settings_cache: dict[int, dict[str, Any]] = {}

        class CogInfo:
            name = "ColorRoles"
            category = "Main"
            description = "Guild color role commands"
            hidden = False
            emoji = "color"

        self.cog_info = CogInfo

    def _config_key(self, guild_id: int) -> str:
        return f"{COLOR_SETS_CONFIG_KEY_PREFIX}{int(guild_id)}"

    async def _safe_ctx_defer(self, ctx: commands.Context) -> bool:
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return True
        if interaction.response.is_done():
            return True
        try:
            await ctx.defer()
            return True
        except (discord.NotFound, discord.InteractionResponded):
            return False
        except discord.HTTPException as error:
            if getattr(error, "code", None) == 10062:
                return False
            raise

    async def _get_settings(self, guild_id: int, *, force: bool = False) -> dict[str, Any]:
        now = time.time()
        cached = self._settings_cache.get(int(guild_id))
        cached_data = cached.get("data") if isinstance(cached, dict) else None
        if not force and cached and (now - float(cached.get("ts", 0.0) or 0.0)) <= 12:
            data = cached_data
            if isinstance(data, dict):
                return data

        payload: dict[str, Any] = {}
        load_error = False
        try:
            row = await asyncio.wait_for(
                dashboard_config_db.get(config_key=self._config_key(guild_id)),
                timeout=SETTINGS_FETCH_TIMEOUT_SECONDS,
            )
            raw = str((row or {}).get("config_value") or "").strip()
            if raw:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    payload = decoded
        except Exception as error:
            logger.error(f"ColorRoles settings load failed ({guild_id}): {error}")
            payload = {}
            load_error = True

        if load_error and isinstance(cached_data, dict):
            fallback = dict(cached_data)
            fallback["_load_error"] = True
            self._settings_cache[int(guild_id)] = {"ts": now, "data": fallback}
            return fallback

        normalized = _normalize_color_settings(payload)
        normalized["_load_error"] = load_error
        self._settings_cache[int(guild_id)] = {"ts": now, "data": normalized}
        return normalized

    @staticmethod
    def _role_hex(role: discord.Role) -> str:
        return f"#{int(getattr(getattr(role, 'color', None), 'value', 0) or 0):06X}"

    @commands.hybrid_command(
        name="colors",
        with_app_command=True,
        help="แสดงรายการ Color Roles ที่เลือกได้",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=12, type=commands.BucketType.user)
    async def colors(self, ctx: commands.Context):
        if not await self._safe_ctx_defer(ctx):
            return
        guild = ctx.guild
        if guild is None:
            return await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น")

        settings = await self._get_settings(guild.id, force=False)
        if not bool(settings.get("_load_error")) and not bool(settings.get("enabled")):
            return await ctx.send("ระบบ Color Roles ยังปิดอยู่ใน Dashboard")
        if not bool(settings.get("command_colors_enabled")):
            return await ctx.send("คำสั่ง `/colors` ถูกปิดไว้ใน Dashboard")

        roles = _collect_color_roles(guild)
        if not roles:
            return await ctx.send(
                "ยังไม่มีบทบาทสีในกิลด์นี้\n"
                "ให้ไปที่ Dashboard > Colors แล้วกด Apply ชุดสีเพื่อสร้าง role อัตโนมัติก่อน"
            )

        lines: list[str] = []
        for role in roles:
            lines.append(f"`{role.name}` {role.mention} `{self._role_hex(role)}`")

        visible_lines = lines[:30]
        if len(lines) > 30:
            visible_lines.append(f"... และอีก {len(lines) - 30} รายการ")

        embed = discord.Embed(
            title=str(settings.get("list_name") or "Color List").strip()[:60] or "Color List",
            description="\n".join(visible_lines),
            color=style_color.blue,
        )
        embed.set_footer(text="ใช้ /color <หมายเลข> เพื่อเลือกสีของคุณ")
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="color",
        with_app_command=True,
        help="เลือกสีจากบทบาทเลข เช่น /color 1",
    )
    @app_commands.describe(number="หมายเลขสีที่ต้องการ เช่น 1, 2, 3")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=10, type=commands.BucketType.user)
    async def color(self, ctx: commands.Context, number: int):
        if not await self._safe_ctx_defer(ctx):
            return
        guild = ctx.guild
        if guild is None:
            return await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น")

        if number <= 0:
            return await ctx.send("หมายเลขสีต้องมากกว่า 0")

        member = ctx.author if isinstance(ctx.author, discord.Member) else guild.get_member(getattr(ctx.author, "id", 0))
        if member is None:
            return await ctx.send("ไม่พบสมาชิกในเซิร์ฟเวอร์")

        settings = await self._get_settings(guild.id, force=False)
        if not bool(settings.get("_load_error")) and not bool(settings.get("enabled")):
            return await ctx.send("ระบบ Color Roles ยังปิดอยู่ใน Dashboard")
        if not bool(settings.get("command_color_enabled")):
            return await ctx.send("คำสั่ง `/color` ถูกปิดไว้ใน Dashboard")

        me = guild.me
        if me is None:
            return await ctx.send("บอทยังไม่พร้อมใช้งานในเซิร์ฟเวอร์นี้")
        if not me.guild_permissions.manage_roles:
            return await ctx.send("บอทไม่มีสิทธิ์ Manage Roles")

        target_name = str(int(number))
        all_color_roles = _collect_color_roles(guild)
        target_role = next((role for role in all_color_roles if role.name == target_name), None)
        if target_role is None:
            return await ctx.send(
                f"ไม่พบบทบาทสีหมายเลข `{target_name}`\n"
                "ให้ไปที่ Dashboard > Colors แล้วกด Apply ชุดสีก่อน"
            )

        if me.top_role <= target_role:
            return await ctx.send("บอทไม่สามารถจัดการ role สีนี้ได้ เพราะ role สูงกว่าหรือเท่ากับ role ของบอท")

        member_color_roles = [
            role
            for role in member.roles
            if not role.is_default() and not role.managed and str(role.name or "").strip().isdigit()
        ]

        removable_roles = [
            role
            for role in member_color_roles
            if role.id != target_role.id and me.top_role > role
        ]
        blocked_roles = [
            role
            for role in member_color_roles
            if role.id != target_role.id and me.top_role <= role
        ]
        need_add_target = target_role.id not in {role.id for role in member.roles}

        if not need_add_target and not removable_roles:
            return await ctx.send(
                f"คุณใช้สี `{target_role.name}` อยู่แล้ว `{self._role_hex(target_role)}`"
            )

        try:
            if removable_roles:
                await member.remove_roles(
                    *removable_roles,
                    reason=f"Color role switch by {ctx.author} ({ctx.author.id})",
                )
            if need_add_target:
                await member.add_roles(
                    target_role,
                    reason=f"Color role set by {ctx.author} ({ctx.author.id})",
                )
        except discord.Forbidden:
            return await ctx.send("บอทไม่มีสิทธิ์พอในการเพิ่ม/ลบบทบาทสี")
        except Exception as error:
            logger.error(f"ColorRoles update failed in guild {guild.id}: {error}")
            return await ctx.send("เกิดข้อผิดพลาดระหว่างปรับบทบาทสี ลองใหม่อีกครั้ง")

        message = (
            f"ตั้งค่าสีของคุณเป็น `{target_role.name}` `{self._role_hex(target_role)}` เรียบร้อยแล้ว\n"
            f"Role: {target_role.mention}"
        )
        if blocked_roles:
            message += (
                f"\nหมายเหตุ: มีบทบาทสี {len(blocked_roles)} บทบาทที่สูงเกินกว่า role ของบอท "
                "จึงลบอัตโนมัติไม่ได้"
            )
        await ctx.send(message)
