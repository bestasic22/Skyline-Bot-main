from __future__ import annotations

import datetime
import json
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import storage.dashboard_config as dashboard_config_db
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color

NSFW_GUARD_CONFIG_KEY_PREFIX = "nsfw_guard_v1_guild_"
EXTRA_PROTECTION_CONFIG_KEY_PREFIX = "extra_protection_v1_guild_"
EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY = "allowlist_only"
EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST = "all_except_allowlist"


def _default_nsfw_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "allowed_channel_ids": [],
        "allowed_role_ids": [],
        "log_channel_id": "",
        "block_dm": True,
        "require_discord_nsfw_channel": True,
        "strict_mode": False,
    }


def _normalize_id_list(raw_value: Any, *, max_items: int = 120) -> list[str]:
    out: list[str] = []
    if isinstance(raw_value, (list, tuple, set)):
        iterable = raw_value
    else:
        iterable = str(raw_value or "").replace("\n", ",").replace(" ", ",").split(",")

    for item in iterable:
        text = str(item or "").strip()
        if not text.isdigit() or text in out:
            continue
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return bool(default)


def _normalize_nsfw_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_nsfw_settings()
    out["enabled"] = _safe_bool(src.get("enabled"), False)
    out["allowed_channel_ids"] = _normalize_id_list(src.get("allowed_channel_ids"))
    out["allowed_role_ids"] = _normalize_id_list(src.get("allowed_role_ids"))
    log_channel_id = str(src.get("log_channel_id") or "").strip()
    out["log_channel_id"] = log_channel_id if log_channel_id.isdigit() else ""
    out["block_dm"] = _safe_bool(src.get("block_dm"), True)
    out["require_discord_nsfw_channel"] = _safe_bool(
        src.get("require_discord_nsfw_channel"),
        True,
    )
    out["strict_mode"] = _safe_bool(src.get("strict_mode"), False)
    return out


def _default_extra_protection_nsfw_image_settings() -> dict[str, Any]:
    return {
        "detect_nsfw_image_enabled": False,
        "detect_nsfw_image_mode": EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
        "detect_nsfw_image_threshold": 0.72,
    }


def _normalize_extra_protection_nsfw_image_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_extra_protection_nsfw_image_settings()
    out["detect_nsfw_image_enabled"] = _safe_bool(
        src.get("detect_nsfw_image_enabled"),
        out["detect_nsfw_image_enabled"],
    )
    mode = str(src.get("detect_nsfw_image_mode") or out["detect_nsfw_image_mode"]).strip().lower()
    if mode not in {
        EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
        EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST,
    }:
        mode = out["detect_nsfw_image_mode"]
    out["detect_nsfw_image_mode"] = mode
    try:
        threshold = float(str(src.get("detect_nsfw_image_threshold") or out["detect_nsfw_image_threshold"]).strip())
    except Exception:
        threshold = float(out["detect_nsfw_image_threshold"])
    out["detect_nsfw_image_threshold"] = max(0.05, min(0.995, threshold))
    return out


class NSFW(commands.Cog):
    SOFT_THEME_CHOICES: list[app_commands.Choice[str]] = [
        app_commands.Choice(name="anime", value="anime"),
        app_commands.Choice(name="waifu", value="waifu"),
        app_commands.Choice(name="neko", value="neko"),
        app_commands.Choice(name="art", value="art"),
        app_commands.Choice(name="random", value="random"),
    ]
    IMAGE_FILTER_MODE_CHOICES: list[app_commands.Choice[str]] = [
        app_commands.Choice(
            name="allowlist_only (scan only nsfw allowlist channels)",
            value=EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
        ),
        app_commands.Choice(
            name="all_except_allowlist (scan all except allowlist channels)",
            value=EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST,
        ),
    ]

    SOFT_API_ENDPOINTS: dict[str, list[tuple[str, str]]] = {
        "anime": [
            ("waifu.pics", "https://api.waifu.pics/sfw/waifu"),
            ("nekos.best", "https://nekos.best/api/v2/waifu"),
        ],
        "waifu": [
            ("waifu.pics", "https://api.waifu.pics/sfw/waifu"),
            ("nekos.best", "https://nekos.best/api/v2/waifu"),
        ],
        "neko": [
            ("waifu.pics", "https://api.waifu.pics/sfw/neko"),
            ("nekos.best", "https://nekos.best/api/v2/neko"),
        ],
        "art": [
            ("waifu.pics", "https://api.waifu.pics/sfw/shinobu"),
            ("nekos.best", "https://nekos.best/api/v2/kitsune"),
        ],
        "random": [
            ("waifu.pics", "https://api.waifu.pics/sfw/waifu"),
            ("waifu.pics", "https://api.waifu.pics/sfw/neko"),
            ("waifu.pics", "https://api.waifu.pics/sfw/shinobu"),
            ("nekos.best", "https://nekos.best/api/v2/waifu"),
            ("nekos.best", "https://nekos.best/api/v2/neko"),
            ("nekos.best", "https://nekos.best/api/v2/kitsune"),
        ],
    }

    def __init__(self, bot: AutoShardedBot):
        self.bot = bot

        class CogInfo:
            name = "NSFW"
            category = "Safety"
            description = "NSFW guard and safe prompt commands"
            hidden = False
            emoji = "🔞"

        self.cog_info = CogInfo
        self._settings_cache: dict[str, dict[str, Any]] = {}
        self._settings_cache_expire_at: dict[str, float] = {}
        self._settings_cache_ttl_seconds: float = 20.0

    def _config_key(self, guild_id: int) -> str:
        return f"{NSFW_GUARD_CONFIG_KEY_PREFIX}{int(guild_id)}"

    def _extra_protection_config_key(self, guild_id: int) -> str:
        return f"{EXTRA_PROTECTION_CONFIG_KEY_PREFIX}{int(guild_id)}"

    async def _get_settings(self, guild_id: int) -> dict[str, Any]:
        key = str(guild_id)
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        cached = self._settings_cache.get(key)
        expires_at = float(self._settings_cache_expire_at.get(key, 0.0) or 0.0)
        if cached is not None and now_ts < expires_at:
            return cached

        settings = _default_nsfw_settings()
        try:
            row = await dashboard_config_db.get(config_key=self._config_key(guild_id))
            raw_value = str((row or {}).get("config_value") or "").strip()
            if raw_value:
                decoded = json.loads(raw_value)
                if isinstance(decoded, dict):
                    settings = _normalize_nsfw_settings(decoded)
        except Exception:
            settings = _default_nsfw_settings()

        self._settings_cache[key] = settings
        self._settings_cache_expire_at[key] = now_ts + self._settings_cache_ttl_seconds
        return settings

    async def _set_settings(self, guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_nsfw_settings(payload)
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
        key = str(guild_id)
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        self._settings_cache[key] = normalized
        self._settings_cache_expire_at[key] = now_ts + self._settings_cache_ttl_seconds
        return normalized

    async def _get_extra_protection_raw(self, guild_id: int) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        try:
            row = await dashboard_config_db.get(config_key=self._extra_protection_config_key(guild_id))
            raw_value = str((row or {}).get("config_value") or "").strip()
            if raw_value:
                decoded = json.loads(raw_value)
                if isinstance(decoded, dict):
                    payload = decoded
        except Exception:
            payload = {}
        return payload

    async def _set_extra_protection_raw(self, guild_id: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        writer = getattr(dashboard_config_db, "set_config_value", None)
        if callable(writer):
            await writer(config_key=self._extra_protection_config_key(guild_id), config_value=encoded)
        else:
            row = await dashboard_config_db.get(config_key=self._extra_protection_config_key(guild_id))
            if row:
                await dashboard_config_db.update(id=row["id"], config_value=encoded)
            else:
                await dashboard_config_db.insert(
                    config_key=self._extra_protection_config_key(guild_id),
                    config_value=encoded,
                )

    async def _get_extra_protection_nsfw_image_settings(self, guild_id: int) -> dict[str, Any]:
        payload = await self._get_extra_protection_raw(guild_id)
        return _normalize_extra_protection_nsfw_image_settings(payload)

    async def _update_extra_protection_nsfw_image_settings(
        self,
        guild_id: int,
        *,
        enabled: bool | None = None,
        mode: str | None = None,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        payload = await self._get_extra_protection_raw(guild_id)
        current = _normalize_extra_protection_nsfw_image_settings(payload)

        if enabled is not None:
            payload["detect_nsfw_image_enabled"] = bool(enabled)
        else:
            payload["detect_nsfw_image_enabled"] = bool(current["detect_nsfw_image_enabled"])

        if mode is not None:
            payload["detect_nsfw_image_mode"] = str(mode).strip().lower()
        else:
            payload["detect_nsfw_image_mode"] = str(current["detect_nsfw_image_mode"])

        if threshold is not None:
            payload["detect_nsfw_image_threshold"] = float(threshold)
        else:
            payload["detect_nsfw_image_threshold"] = float(current["detect_nsfw_image_threshold"])

        normalized = _normalize_extra_protection_nsfw_image_settings(payload)
        payload["detect_nsfw_image_enabled"] = normalized["detect_nsfw_image_enabled"]
        payload["detect_nsfw_image_mode"] = normalized["detect_nsfw_image_mode"]
        payload["detect_nsfw_image_threshold"] = normalized["detect_nsfw_image_threshold"]
        await self._set_extra_protection_raw(guild_id, payload)
        return normalized

    async def _send(
        self,
        ctx: commands.Context,
        *,
        content: str | None = None,
        embed: discord.Embed | None = None,
        ephemeral: bool = False,
        delete_after: float | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if content:
            kwargs["content"] = str(content)
        if embed is not None:
            kwargs["embed"] = embed
        if delete_after is not None:
            kwargs["delete_after"] = delete_after
        if getattr(ctx, "interaction", None):
            kwargs["ephemeral"] = bool(ephemeral)
        try:
            await ctx.send(**kwargs)
            return
        except TypeError:
            kwargs.pop("ephemeral", None)
        except discord.NotFound:
            kwargs.pop("ephemeral", None)
            channel = getattr(ctx, "channel", None)
            if channel is not None:
                try:
                    await channel.send(**kwargs)
                except Exception:
                    pass
            return
        except Exception:
            kwargs.pop("ephemeral", None)

        try:
            await ctx.send(**kwargs)
        except Exception:
            pass

    async def _require_manage_guild(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            await self._send(
                ctx,
                content="This command can only be used in a server.",
                ephemeral=True,
            )
            return False
        if not getattr(ctx.author.guild_permissions, "manage_guild", False):
            await self._send(
                ctx,
                content="You need `Manage Server` permission to configure NSFW settings.",
                ephemeral=True,
            )
            return False
        return True

    @staticmethod
    def _channel_is_nsfw(channel: Any) -> bool:
        if channel is None:
            return False
        is_nsfw_callable = getattr(channel, "is_nsfw", None)
        if callable(is_nsfw_callable):
            try:
                return bool(is_nsfw_callable())
            except Exception:
                pass
        parent = getattr(channel, "parent", None)
        parent_is_nsfw = getattr(parent, "is_nsfw", None)
        if callable(parent_is_nsfw):
            try:
                return bool(parent_is_nsfw())
            except Exception:
                pass
        return bool(getattr(channel, "nsfw", False))

    @staticmethod
    def _member_has_any_required_role(member: discord.Member | None, required_role_ids: set[str]) -> bool:
        if not required_role_ids:
            return True
        if member is None:
            return False
        for role in list(getattr(member, "roles", []) or []):
            if str(getattr(role, "id", "")) in required_role_ids:
                return True
        return False

    @staticmethod
    def _extract_soft_image_url(payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("url", "image_url", "image", "link"):
                value = payload.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value

            results = payload.get("results")
            if isinstance(results, list) and results:
                first = results[0]
                if isinstance(first, dict):
                    for key in ("url", "image_url", "image", "link"):
                        value = first.get(key)
                        if isinstance(value, str) and value.startswith(("http://", "https://")):
                            return value

            files = payload.get("files")
            if isinstance(files, list) and files:
                first_file = files[0]
                if isinstance(first_file, str) and first_file.startswith(("http://", "https://")):
                    return first_file

        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, str) and first.startswith(("http://", "https://")):
                return first
            if isinstance(first, dict):
                for key in ("url", "image_url", "image", "link"):
                    value = first.get(key)
                    if isinstance(value, str) and value.startswith(("http://", "https://")):
                        return value
        return ""

    async def _fetch_soft_image(self, theme: str) -> tuple[str, str, str]:
        normalized_theme = str(theme or "anime").strip().lower()
        if normalized_theme not in self.SOFT_API_ENDPOINTS:
            normalized_theme = "anime"
        endpoints = list(self.SOFT_API_ENDPOINTS.get(normalized_theme) or self.SOFT_API_ENDPOINTS["anime"])
        headers = {"User-Agent": "SkylineBOT/1.0 (https://skylinebot.xyz)"}
        timeout = aiohttp.ClientTimeout(total=10)
        last_error = "no_response"

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            for provider, endpoint in endpoints:
                try:
                    async with session.get(endpoint) as response:
                        if response.status != 200:
                            last_error = f"{provider}:http_{response.status}"
                            continue
                        payload = await response.json(content_type=None)
                except Exception as error:
                    last_error = f"{provider}:{type(error).__name__}"
                    continue

                image_url = self._extract_soft_image_url(payload)
                if image_url:
                    return image_url, provider, normalized_theme
                last_error = f"{provider}:invalid_payload"

        raise RuntimeError(last_error)

    def _build_access_issues(self, ctx: commands.Context, settings: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        guild = getattr(ctx, "guild", None)
        channel = getattr(ctx, "channel", None)
        strict_mode = bool(settings.get("strict_mode", False))

        if guild is None:
            if strict_mode:
                issues.append("DM usage is blocked while NSFW strict mode is enabled.")
            elif bool(settings.get("block_dm", True)):
                issues.append("DM usage is blocked for NSFW commands.")
            return issues

        if not bool(settings.get("enabled", False)):
            issues.append("NSFW command system is disabled in this server.")

        require_discord_nsfw_channel = bool(settings.get("require_discord_nsfw_channel", True)) or strict_mode
        if require_discord_nsfw_channel and not self._channel_is_nsfw(channel):
            issues.append("This command requires a Discord NSFW-marked channel.")

        allowed_channels = {
            str(value)
            for value in list(settings.get("allowed_channel_ids") or [])
            if str(value).isdigit()
        }
        if strict_mode and not allowed_channels:
            issues.append("Strict mode requires at least one NSFW allowlist channel.")
        elif allowed_channels:
            channel_id = str(getattr(channel, "id", ""))
            if channel_id not in allowed_channels:
                issues.append("This channel is not in the NSFW allowlist.")

        required_roles = {
            str(value)
            for value in list(settings.get("allowed_role_ids") or [])
            if str(value).isdigit()
        }
        member = ctx.author if isinstance(ctx.author, discord.Member) else guild.get_member(getattr(ctx.author, "id", 0))
        if strict_mode and not required_roles:
            issues.append("Strict mode requires at least one NSFW access role.")
        elif required_roles and not self._member_has_any_required_role(member, required_roles):
            issues.append("You do not have any required NSFW access role.")

        log_channel_id = str(settings.get("log_channel_id") or "").strip()
        if strict_mode and not log_channel_id.isdigit():
            issues.append("Strict mode requires a NSFW usage log channel (`nsfw log #channel`).")
        return issues

    async def _assert_access(self, ctx: commands.Context, settings: dict[str, Any]) -> bool:
        issues = self._build_access_issues(ctx, settings)
        if not issues:
            return True
        await self._send(ctx, content="Access denied:\n- " + "\n- ".join(issues), ephemeral=True)
        return False

    async def _log_usage(
        self,
        *,
        guild: discord.Guild | None,
        channel: Any,
        member: discord.Member | discord.User | None,
        category: str,
        settings: dict[str, Any],
        action: str = "preview",
    ) -> None:
        if guild is None:
            return
        log_channel_id = str(settings.get("log_channel_id") or "").strip()
        if not log_channel_id.isdigit():
            return
        log_channel = guild.get_channel(int(log_channel_id))
        if log_channel is None:
            return
        try:
            embed = discord.Embed(
                title=f"NSFW {str(action or 'preview').title()} Used",
                description=f"Category: `{category}`",
                color=color.orange,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            if member is not None:
                embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            if channel is not None:
                channel_id = getattr(channel, "id", None)
                channel_text = f"<#{channel_id}>" if channel_id else str(channel)
                embed.add_field(name="Channel", value=channel_text, inline=False)
            await log_channel.send(embed=embed)
        except Exception as error:
            logger.warning(f"NSFW log send failed in guild {guild.id}: {error}")

    @commands.hybrid_group(
        name="nsfw",
        with_app_command=True,
        invoke_without_command=True,
        help="จัดการการตั้งค่าการป้องกัน NSFW กฎการเข้าถึง และคำสั่งซอฟต์ฟีด",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def nsfw(self, ctx: commands.Context):
        await self._send(
            ctx,
            content=(
                "Available commands: `nsfw status`, `nsfw enable`, `nsfw disable`, "
                "`nsfw channeladd`, `nsfw channelremove`, `nsfw channels`, "
                "`nsfw roleadd`, `nsfw roleremove`, `nsfw roles`, `nsfw log`, "
                "`nsfw guard`, `nsfw strict`, `nsfw imagefilter`, `nsfw soft`, `nsfw check`"
            ),
            ephemeral=bool(getattr(ctx, "interaction", None)),
        )

    @nsfw.command(
        name="status",
        help="แสดงการตั้งค่าการป้องกัน NSFW ปัจจุบันสำหรับเซิร์ฟเวอร์นี้",
        description="แสดงการตั้งค่าการป้องกัน NSFW ปัจจุบันสำหรับเซิร์ฟเวอร์นี้",
    )
    async def nsfw_status(self, ctx: commands.Context):
        if not ctx.guild:
            await self._send(ctx, content="This command can only be used in a server.", ephemeral=True)
            return
        settings = await self._get_settings(ctx.guild.id)
        extra_image_filter = await self._get_extra_protection_nsfw_image_settings(ctx.guild.id)
        channel_mentions = [
            f"<#{channel_id}>"
            for channel_id in settings.get("allowed_channel_ids", [])
            if str(channel_id).isdigit()
        ]
        role_mentions = [
            f"<@&{role_id}>"
            for role_id in settings.get("allowed_role_ids", [])
            if str(role_id).isdigit()
        ]
        log_channel_text = (
            f"<#{settings['log_channel_id']}>"
            if str(settings.get("log_channel_id") or "").isdigit()
            else "Not set"
        )
        embed = discord.Embed(
            title="สถานะยาม NSFW",
            color=color.blue,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Enabled", value="Yes" if settings.get("enabled") else "No", inline=True)
        embed.add_field(
            name="Require Discord NSFW Channel",
            value="Yes" if settings.get("require_discord_nsfw_channel") else "No",
            inline=True,
        )
        embed.add_field(name="DM Block", value="Yes" if settings.get("block_dm") else "No", inline=True)
        embed.add_field(name="Strict Mode", value="Yes" if settings.get("strict_mode") else "No", inline=True)
        mode = str(extra_image_filter.get("detect_nsfw_image_mode") or EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY)
        mode_text = (
            "all channels except allowlist"
            if mode == EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST
            else "allowlist channels only"
        )
        embed.add_field(
            name="Extra Protection Image Filter",
            value="On" if extra_image_filter.get("detect_nsfw_image_enabled") else "Off",
            inline=True,
        )
        embed.add_field(
            name="Image Filter Mode",
            value=mode_text,
            inline=True,
        )
        embed.add_field(
            name="Image Filter Threshold",
            value=f"{float(extra_image_filter.get('detect_nsfw_image_threshold', 0.72) or 0.72):.2f}",
            inline=True,
        )
        embed.add_field(
            name="Allowed Channels",
            value="\n".join(channel_mentions[:15]) if channel_mentions else "Any NSFW channel",
            inline=False,
        )
        embed.add_field(
            name="Required Roles",
            value="\n".join(role_mentions[:15]) if role_mentions else "No role restriction",
            inline=False,
        )
        embed.add_field(name="Usage Log Channel", value=log_channel_text, inline=False)
        await self._send(ctx, embed=embed, ephemeral=bool(getattr(ctx, "interaction", None)))

    @nsfw.command(
        name="enable",
        help="เปิดใช้งานระบบคำสั่ง NSFW และเพิ่มช่องทางรายการที่อนุญาต",
        description="เปิดใช้งานระบบคำสั่ง NSFW และเพิ่มช่องทางรายการที่อนุญาต",
    )
    async def nsfw_enable(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        settings["enabled"] = True
        target_channel = channel
        if target_channel is None and isinstance(ctx.channel, discord.TextChannel):
            target_channel = ctx.channel
        if target_channel is not None:
            channel_id = str(target_channel.id)
            if channel_id not in settings["allowed_channel_ids"]:
                settings["allowed_channel_ids"].append(channel_id)
        settings = await self._set_settings(ctx.guild.id, settings)
        added_text = ""
        if target_channel is not None:
            added_text = f" and channel {target_channel.mention} was added to allowlist"
        await self._send(ctx, content=f"NSFW system enabled{added_text}.")

    @nsfw.command(
        name="disable",
        help="ปิดใช้งานระบบคำสั่ง NSFW สำหรับเซิร์ฟเวอร์นี้",
        description="ปิดใช้งานระบบคำสั่ง NSFW สำหรับเซิร์ฟเวอร์นี้",
    )
    async def nsfw_disable(self, ctx: commands.Context):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        settings["enabled"] = False
        await self._set_settings(ctx.guild.id, settings)
        await self._send(ctx, content="NSFW system disabled.")

    @nsfw.command(
        name="channeladd",
        help="เพิ่มช่องในรายการที่อนุญาตของ NSFW",
        description="เพิ่มช่องในรายการที่อนุญาตของ NSFW",
    )
    async def nsfw_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        channel_id = str(channel.id)
        if channel_id in settings["allowed_channel_ids"]:
            await self._send(ctx, content=f"{channel.mention} is already in NSFW allowlist.")
            return
        settings["allowed_channel_ids"].append(channel_id)
        await self._set_settings(ctx.guild.id, settings)
        await self._send(ctx, content=f"Added {channel.mention} to NSFW allowlist.")

    @nsfw.command(
        name="channelremove",
        help="ลบช่องออกจากรายการที่อนุญาตของ NSFW",
        description="ลบช่องออกจากรายการที่อนุญาตของ NSFW",
    )
    async def nsfw_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        channel_id = str(channel.id)
        if channel_id not in settings["allowed_channel_ids"]:
            await self._send(ctx, content=f"{channel.mention} is not in NSFW allowlist.")
            return
        settings["allowed_channel_ids"] = [
            value for value in settings["allowed_channel_ids"] if str(value) != channel_id
        ]
        await self._set_settings(ctx.guild.id, settings)
        await self._send(ctx, content=f"Removed {channel.mention} from NSFW allowlist.")

    @nsfw.command(
        name="channels",
        help="แสดงรายการช่องรายการที่อนุญาตของ NSFW",
        description="แสดงรายการช่องรายการที่อนุญาตของ NSFW",
    )
    async def nsfw_channels(self, ctx: commands.Context):
        if not ctx.guild:
            await self._send(ctx, content="This command can only be used in a server.", ephemeral=True)
            return
        settings = await self._get_settings(ctx.guild.id)
        entries = [
            f"<#{channel_id}>"
            for channel_id in settings.get("allowed_channel_ids", [])
            if str(channel_id).isdigit()
        ]
        if not entries:
            await self._send(
                ctx,
                content="No channel allowlist is set. Any Discord NSFW channel can be used.",
                ephemeral=bool(getattr(ctx, "interaction", None)),
            )
            return
        await self._send(ctx, content="NSFW allowlist channels:\n" + "\n".join(entries[:30]))

    @nsfw.command(
        name="roleadd",
        help="เพิ่มบทบาทที่จำเป็นสำหรับการเข้าถึง NSFW",
        description="เพิ่มบทบาทที่จำเป็นสำหรับการเข้าถึง NSFW",
    )
    async def nsfw_role_add(self, ctx: commands.Context, role: discord.Role):
        if not await self._require_manage_guild(ctx):
            return
        if role.is_default():
            await self._send(ctx, content="Cannot add @everyone as NSFW required role.")
            return
        settings = await self._get_settings(ctx.guild.id)
        role_id = str(role.id)
        if role_id in settings["allowed_role_ids"]:
            await self._send(ctx, content=f"{role.mention} is already a required role.")
            return
        settings["allowed_role_ids"].append(role_id)
        await self._set_settings(ctx.guild.id, settings)
        await self._send(ctx, content=f"Added required NSFW role: {role.mention}")

    @nsfw.command(
        name="roleremove",
        help="ลบบทบาทที่จำเป็นสำหรับการเข้าถึง NSFW",
        description="ลบบทบาทที่จำเป็นสำหรับการเข้าถึง NSFW",
    )
    async def nsfw_role_remove(self, ctx: commands.Context, role: discord.Role):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        role_id = str(role.id)
        if role_id not in settings["allowed_role_ids"]:
            await self._send(ctx, content=f"{role.mention} is not in required role list.")
            return
        settings["allowed_role_ids"] = [
            value for value in settings["allowed_role_ids"] if str(value) != role_id
        ]
        await self._set_settings(ctx.guild.id, settings)
        await self._send(ctx, content=f"Removed required NSFW role: {role.mention}")

    @nsfw.command(
        name="roles",
        help="แสดงรายการบทบาทที่จำเป็นสำหรับการเข้าถึง NSFW",
        description="แสดงรายการบทบาทที่จำเป็นสำหรับการเข้าถึง NSFW",
    )
    async def nsfw_roles(self, ctx: commands.Context):
        if not ctx.guild:
            await self._send(ctx, content="This command can only be used in a server.", ephemeral=True)
            return
        settings = await self._get_settings(ctx.guild.id)
        entries = [
            f"<@&{role_id}>"
            for role_id in settings.get("allowed_role_ids", [])
            if str(role_id).isdigit()
        ]
        if not entries:
            await self._send(
                ctx,
                content="No required role is set for NSFW commands.",
                ephemeral=bool(getattr(ctx, "interaction", None)),
            )
            return
        await self._send(ctx, content="Required NSFW roles:\n" + "\n".join(entries[:30]))

    @nsfw.command(
        name="log",
        help="ตั้งค่าหรือล้างช่องทางบันทึกการใช้งาน NSFW",
        description="ตั้งค่าหรือล้างช่องทางบันทึกการใช้งาน NSFW",
    )
    async def nsfw_log(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        if channel is None:
            settings["log_channel_id"] = ""
            await self._set_settings(ctx.guild.id, settings)
            await self._send(ctx, content="Cleared NSFW usage log channel.")
            return
        settings["log_channel_id"] = str(channel.id)
        await self._set_settings(ctx.guild.id, settings)
        await self._send(ctx, content=f"NSFW usage logs will be sent to {channel.mention}")

    @nsfw.command(
        name="guard",
        help="กำหนดค่าการตรวจสอบการป้องกัน NSFW สำหรับข้อกำหนดช่อง DM และ NSFW",
        description="กำหนดค่าการตรวจสอบการป้องกัน NSFW สำหรับข้อกำหนดช่อง DM และ NSFW",
    )
    @app_commands.describe(
        block_dm="Block NSFW commands in DM",
        require_nsfw_channel="Require command channel to be marked NSFW by Discord",
    )
    async def nsfw_guard(
        self,
        ctx: commands.Context,
        block_dm: bool = True,
        require_nsfw_channel: bool = True,
    ):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        settings["block_dm"] = bool(block_dm)
        settings["require_discord_nsfw_channel"] = bool(require_nsfw_channel)
        settings = await self._set_settings(ctx.guild.id, settings)
        strict_note = ""
        if settings.get("strict_mode"):
            strict_note = " Strict mode is ON, so DM and NSFW-channel checks are always enforced."
        await self._send(
            ctx,
            content=(
                f"NSFW guard updated: block_dm={'on' if settings['block_dm'] else 'off'}, "
                f"require_nsfw_channel={'on' if settings['require_discord_nsfw_channel'] else 'off'}."
                f"{strict_note}"
            ),
        )

    @nsfw.command(
        name="strict",
        help="เปิดหรือปิดใช้งานโหมดล็อค NSFW ที่เข้มงวด",
        description="เปิดหรือปิดใช้งานโหมดล็อค NSFW ที่เข้มงวด",
    )
    @app_commands.describe(enabled="Turn strict mode on/off")
    async def nsfw_strict(self, ctx: commands.Context, enabled: bool):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        settings["strict_mode"] = bool(enabled)
        if enabled:
            settings["block_dm"] = True
            settings["require_discord_nsfw_channel"] = True
        settings = await self._set_settings(ctx.guild.id, settings)
        if not enabled:
            await self._send(ctx, content="NSFW strict mode disabled.")
            return

        warnings: list[str] = []
        if not list(settings.get("allowed_channel_ids") or []):
            warnings.append("add at least 1 allowlist channel using `nsfw channeladd`")
        if not list(settings.get("allowed_role_ids") or []):
            warnings.append("add at least 1 required role using `nsfw roleadd`")
        if not str(settings.get("log_channel_id") or "").isdigit():
            warnings.append("set log channel using `nsfw log #channel`")

        if warnings:
            await self._send(
                ctx,
                content="NSFW strict mode enabled, but setup is incomplete:\n- " + "\n- ".join(warnings),
            )
            return
        await self._send(ctx, content="NSFW strict mode enabled and fully configured.")

    @nsfw.command(
        name="imagefilter",
        help="กำหนดค่าการสแกนรูปภาพ NSFW ในการป้องกันพิเศษ",
        description="กำหนดค่าการสแกนรูปภาพ NSFW ในการป้องกันพิเศษ",
    )
    @app_commands.describe(
        enabled="Turn NSFW image filter on/off",
        mode="allowlist_only = scan only allowlist channels, all_except_allowlist = scan every channel except allowlist",
        threshold="Sexual score threshold (0.05-0.995), lower means stricter",
    )
    @app_commands.choices(mode=IMAGE_FILTER_MODE_CHOICES)
    async def nsfw_image_filter(
        self,
        ctx: commands.Context,
        enabled: bool,
        mode: str = EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
        threshold: float = 0.72,
    ):
        if not await self._require_manage_guild(ctx):
            return
        normalized_mode = str(mode or EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY).strip().lower()
        if normalized_mode not in {
            EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
            EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST,
        }:
            normalized_mode = EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY
        threshold_value = max(0.05, min(0.995, float(threshold)))
        updated = await self._update_extra_protection_nsfw_image_settings(
            ctx.guild.id,
            enabled=bool(enabled),
            mode=normalized_mode,
            threshold=threshold_value,
        )
        extra_raw = await self._get_extra_protection_raw(ctx.guild.id)
        extra_enabled = _safe_bool(extra_raw.get("enabled"), False)

        nsfw_settings = await self._get_settings(ctx.guild.id)
        allowlist_count = len(list(nsfw_settings.get("allowed_channel_ids") or []))
        if updated["detect_nsfw_image_mode"] == EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST:
            mode_text = "all channels except NSFW allowlist channels"
        else:
            mode_text = "NSFW allowlist channels only"

        notice = ""
        if allowlist_count <= 0 and updated["detect_nsfw_image_mode"] == EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY:
            notice = " Note: allowlist is empty, so no channels will be scanned until you use `nsfw channeladd`."
        if not extra_enabled:
            notice += " Note: Extra Protection is currently disabled, so filtering will not run until you enable Extra Protection."
        await self._send(
            ctx,
            content=(
                f"Extra Protection NSFW image filter updated: "
                f"enabled={'on' if updated['detect_nsfw_image_enabled'] else 'off'}, "
                f"mode={mode_text}, "
                f"threshold={float(updated['detect_nsfw_image_threshold']):.2f}."
                f"{notice}"
            ),
        )

    @nsfw.command(
        name="soft",
        help="ส่งภาพอนิเมะ/อาร์ตที่ไม่โจ่งแจ้งจาก SFW API",
        description="ส่งภาพอนิเมะ/อาร์ตที่ไม่โจ่งแจ้งจาก SFW API",
    )
    @app_commands.describe(theme="Soft image theme")
    @app_commands.choices(theme=SOFT_THEME_CHOICES)
    async def nsfw_soft(self, ctx: commands.Context, theme: str = "anime"):
        if not ctx.guild:
            await self._send(ctx, content="This command can only be used in a server.", ephemeral=True)
            return
        settings = await self._get_settings(ctx.guild.id)
        if not await self._assert_access(ctx, settings):
            return

        try:
            image_url, provider, normalized_theme = await self._fetch_soft_image(theme)
        except Exception as error:
            logger.warning(f"NSFW soft API fetch failed in guild {ctx.guild.id}: {error}")
            await self._send(
                ctx,
                content="Soft image API is unavailable right now. Please try again later.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="ฟีดอ่อน NSFW",
            description="ภาพอะนิเมะ/ศิลปะที่ไม่โจ่งแจ้งจากแหล่ง SFW API",
            color=color.blue,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Theme", value=f"`{normalized_theme}`", inline=True)
        embed.add_field(name="Source", value=f"`{provider}`", inline=True)
        embed.add_field(name="Open", value=f"[Image Link]({image_url})", inline=False)
        embed.set_image(url=image_url)
        await self._send(ctx, embed=embed)
        await self._log_usage(
            guild=ctx.guild,
            channel=getattr(ctx, "channel", None),
            member=ctx.author if isinstance(ctx.author, (discord.Member, discord.User)) else None,
            category=normalized_theme,
            settings=settings,
            action="soft",
        )

    @nsfw.command(
        name="check",
        help="ตรวจสอบว่าอนุญาตให้ใช้คำสั่ง NSFW ในช่องนี้หรือไม่",
        description="ตรวจสอบว่าอนุญาตให้ใช้คำสั่ง NSFW ในช่องนี้หรือไม่",
    )
    async def nsfw_check(self, ctx: commands.Context):
        guild = getattr(ctx, "guild", None)
        settings = _default_nsfw_settings() if guild is None else await self._get_settings(guild.id)
        issues = self._build_access_issues(ctx, settings)
        if issues:
            await self._send(ctx, content="Access denied:\n- " + "\n- ".join(issues), ephemeral=True)
            return
        await self._send(ctx, content="Access OK: you can use `nsfw soft` in this channel.")


