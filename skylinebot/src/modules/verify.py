from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit

import discord
from discord import app_commands
from discord.ext import commands

import storage
import storage.dashboard_config as dashboard_config_db
from skylinebot.bridge.storage import get_collection
from skylinebot.config.config import BotConfigClass
from skylinebot.console.logging import logger
from skylinebot.src.checks import checks

BOT_CONFIG = BotConfigClass()
SUPPORT_PLAN_AUTOROLE_CONFIG_KEY = "ownerbot_support_plan_autorole_v1"
SUPPORT_PLAN_TIERS: tuple[str, ...] = ("free", "silver", "golden", "diamond", "permanent")
SUPPORT_PLAN_TIER_ALIASES: dict[str, str] = {
    "free": "free",
    "silver": "silver",
    "silver_guild_preminum": "silver",
    "silver_guild_premium": "silver",
    "gold": "golden",
    "gole": "golden",
    "golden": "golden",
    "golden_guild_premium": "golden",
    "gole_guild_premium": "golden",
    "diamond": "diamond",
    "diamond_guild_premium": "diamond",
    "permanent": "permanent",
    "lifetime": "permanent",
    "forever": "permanent",
    "permanent_guild_premium": "permanent",
    "lifetime_guild_premium": "permanent",
}
SUPPORT_PLAN_TIER_RANK: dict[str, int] = {tier: index for index, tier in enumerate(SUPPORT_PLAN_TIERS)}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _normalize_support_plan_tier(raw_value: Any) -> str:
    text = str(raw_value or "").strip().lower()
    return SUPPORT_PLAN_TIER_ALIASES.get(text, "free")


def _normalize_support_plan_autorole_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    tier_source = src.get("tier_role_ids") if isinstance(src.get("tier_role_ids"), dict) else {}

    tier_role_ids: dict[str, int] = {}
    for tier in SUPPORT_PLAN_TIERS:
        raw_role_id = tier_source.get(tier)
        if raw_role_id is None and tier == "golden":
            raw_role_id = tier_source.get("gole") or tier_source.get("gold")
        if raw_role_id is None:
            raw_role_id = src.get(f"{tier}_role_id")
        if raw_role_id is None and tier == "golden":
            raw_role_id = src.get("gole_role_id") or src.get("gold_role_id")
        role_id = _safe_int(raw_role_id, 0)
        tier_role_ids[tier] = role_id if role_id > 0 else 0

    required_role_id = _safe_int(src.get("required_role_id"), 0)
    support_guild_id = _safe_int(src.get("support_guild_id"), 0)
    enabled = bool(_as_bool(src.get("enabled")) and any(tier_role_ids.values()))

    return {
        "enabled": enabled,
        "support_guild_id": support_guild_id if support_guild_id > 0 else 0,
        "required_role_id": required_role_id if required_role_id > 0 else 0,
        "tier_role_ids": tier_role_ids,
        "updated_by_user_id": _safe_int(src.get("updated_by_user_id"), 0),
        "updated_at": str(src.get("updated_at") or "").strip()[:80],
    }


def _normalize_role_ids(raw_value: Any, *, max_items: int = 20) -> list[int]:
    values: list[int] = []
    if isinstance(raw_value, str):
        candidates = raw_value.replace(" ", ",").split(",")
    elif isinstance(raw_value, (list, tuple, set)):
        candidates = [str(item or "").strip() for item in raw_value]
    else:
        candidates = [str(raw_value or "").strip()]

    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text.isdigit():
            continue
        role_id = int(text)
        if role_id in values:
            continue
        values.append(role_id)
        if len(values) >= max_items:
            break
    return values


def _normalize_verify_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload or {}
    reward_role_ids = _normalize_role_ids(src.get("reward_role_ids"))
    if not reward_role_ids:
        reward_role_ids = _normalize_role_ids(src.get("reward_role_id"))
    remove_role_ids = _normalize_role_ids(src.get("remove_role_ids"))
    web_verify_reward_role_ids = _normalize_role_ids(src.get("web_verify_reward_role_ids"))
    if "web_verify_reward_role_ids" not in src:
        web_verify_reward_role_ids = list(reward_role_ids)
    web_verify_remove_role_ids = _normalize_role_ids(src.get("web_verify_remove_role_ids"))
    if "web_verify_remove_role_ids" not in src:
        web_verify_remove_role_ids = list(remove_role_ids)
    pages = src.get("pages") if isinstance(src.get("pages"), list) else []

    def _to_optional_int(value: Any) -> int | None:
        text = str(value or "").strip()
        return int(text) if text.isdigit() else None

    button_color = str(src.get("button_color") or "green").strip().lower()
    if button_color not in {"green", "blurple", "red", "gray"}:
        button_color = "green"

    web_verify_button_color = str(src.get("web_verify_button_color") or "").strip().lower()
    if not web_verify_button_color:
        web_verify_button_color = button_color
    if web_verify_button_color not in {"green", "blurple", "red", "gray"}:
        web_verify_button_color = "green"

    verify_channel_id = _to_optional_int(src.get("verify_channel_id"))
    web_verify_channel_id = _to_optional_int(src.get("web_verify_channel_id"))
    if web_verify_channel_id is None:
        web_verify_channel_id = verify_channel_id
    notify_channel_id = _to_optional_int(src.get("notify_channel_id"))
    web_verify_notify_channel_id = _to_optional_int(src.get("web_verify_notify_channel_id"))
    if web_verify_notify_channel_id is None:
        web_verify_notify_channel_id = notify_channel_id

    enabled = _as_bool(src.get("enabled"))
    web_verify_enabled = _as_bool(src.get("web_verify_enabled")) if "web_verify_enabled" in src else enabled
    auto_role_enabled = _as_bool(src.get("auto_role_enabled"))
    web_verify_auto_role_enabled = (
        _as_bool(src.get("web_verify_auto_role_enabled"))
        if "web_verify_auto_role_enabled" in src
        else auto_role_enabled
    )

    web_verify_embed_image_url = str(src.get("web_verify_embed_image_url") or "").strip()[:500]
    if not web_verify_embed_image_url:
        web_verify_embed_image_url = str(src.get("slip_image_url") or "").strip()[:500]

    button_emoji = str(src.get("button_emoji") or "").strip()[:64]
    web_verify_button_emoji = str(src.get("web_verify_button_emoji") or "").strip()[:64] or button_emoji

    return {
        "enabled": enabled,
        "web_verify_enabled": web_verify_enabled,
        "verify_channel_id": verify_channel_id,
        "web_verify_channel_id": web_verify_channel_id,
        "notify_channel_id": notify_channel_id,
        "web_verify_notify_channel_id": web_verify_notify_channel_id,
        "reward_role_ids": reward_role_ids,
        "remove_role_ids": remove_role_ids,
        "web_verify_reward_role_ids": web_verify_reward_role_ids,
        "web_verify_remove_role_ids": web_verify_remove_role_ids,
        "auto_role_enabled": auto_role_enabled,
        "web_verify_auto_role_enabled": web_verify_auto_role_enabled,
        "nickname_from_first_input": _as_bool(src.get("nickname_from_first_input")),
        "button_color": button_color,
        "button_label": str(src.get("button_label") or "Verify").strip()[:45] or "Verify",
        "button_emoji": button_emoji,
        "color": str(src.get("color") or "#39ff14").strip(),
        "description": str(src.get("description") or "").strip()[:400],
        "embed_title": str(src.get("embed_title") or "Verify").strip()[:120],
        "embed_footer": str(src.get("embed_footer") or "").strip()[:200],
        "embed_thumbnail_url": str(src.get("embed_thumbnail_url") or "").strip()[:500],
        "embed_image_url": str(src.get("embed_image_url") or "").strip()[:500],
        "web_verify_color": str(src.get("web_verify_color") or src.get("color") or "#5865f2").strip(),
        "web_verify_embed_title": str(src.get("web_verify_embed_title") or "Web Verify").strip()[:120],
        "web_verify_embed_description": str(src.get("web_verify_embed_description") or "Click the button below to open Web Verify").strip()[:400],
        "web_verify_embed_footer": str(src.get("web_verify_embed_footer") or "").strip()[:200],
        "web_verify_embed_thumbnail_url": str(src.get("web_verify_embed_thumbnail_url") or "").strip()[:500],
        "web_verify_embed_image_url": web_verify_embed_image_url,
        "slip_image_url": web_verify_embed_image_url,
        "web_verify_intro": str(src.get("web_verify_intro") or "Click the button below to verify via web").strip()[:280],
        "web_verify_success": str(src.get("web_verify_success") or "Verification complete. You can return to the server now.").strip()[:280],
        "web_verify_error": str(src.get("web_verify_error") or "Unable to verify. Please try again.").strip()[:280],
        "web_verify_button_label": str(src.get("web_verify_button_label") or "Verify Now").strip()[:45] or "Verify Now",
        "web_verify_button_color": web_verify_button_color,
        "web_verify_button_emoji": web_verify_button_emoji,
        "web_back_button_label": str(src.get("web_back_button_label") or "Back to Server").strip()[:45] or "Back to Server",
        "back_to_server_url": str(src.get("back_to_server_url") or "").strip()[:500],
        "pages": pages,
    }


def _safe_color(raw: Any) -> int:
    text = str(raw or "#39ff14").strip().lstrip("#")
    try:
        return int(text[:6], 16)
    except Exception:
        return 0x39FF14


class VerifyModal(discord.ui.Modal):
    def __init__(self, cog: "Verify", settings: dict[str, Any]):
        super().__init__(title="ยืนยันตัวตน")
        self.cog = cog
        self.settings = settings
        self.inputs: list[discord.ui.TextInput] = []

        pages = settings.get("pages") or []
        first_page = pages[0] if pages and isinstance(pages[0], dict) else {}
        items = first_page.get("items") if isinstance(first_page.get("items"), list) else []
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "ข้อความ").strip()[:45] or "ข้อความ"
            placeholder = str(item.get("placeholder") or "").strip()[:100]
            style = discord.TextStyle.long if str(item.get("input_type") or "").lower() == "paragraph" else discord.TextStyle.short
            text_input = discord.ui.TextInput(
                label=label,
                placeholder=placeholder or None,
                required=False,
                max_length=200 if style == discord.TextStyle.long else 100,
                style=style,
            )
            self.inputs.append(text_input)
            self.add_item(text_input)

        if not self.inputs:
            fallback = discord.ui.TextInput(label="ชื่อที่ต้องการใช้", required=False, max_length=100)
            self.inputs.append(fallback)
            self.add_item(fallback)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
            guild_id = int(getattr(interaction.guild, "id", 0) or 0)
            settings = await self.cog._fetch_verify_settings(
                guild_id,
                ensure_back_url=False,
                use_cache=True,
            )
            if not settings.get("enabled"):
                await interaction.followup.send("Verify system is currently disabled.", ephemeral=True)
                return

            values = [str(input_item.value or "").strip() for input_item in self.inputs]
            result = await self.cog.apply_verification(
                member=interaction.user if isinstance(interaction.user, discord.Member) else None,
                guild=interaction.guild,
                settings=settings,
                form_values=values,
                actor=interaction.user,
                source="verify",
            )
            if result:
                await interaction.followup.send("ยืนยันตัวตนสำเร็จแล้ว", ephemeral=True)
            else:
                await interaction.followup.send("ไม่สามารถยืนยันตัวตนได้ กรุณาติดต่อแอดมิน", ephemeral=True)
        except discord.NotFound as error:
            if getattr(error, "code", None) != 10062:
                raise
        except Exception as error:
            logger.error(f"Verify modal submit failed: {error}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Unable to process verify interaction right now.", ephemeral=True)
                else:
                    await interaction.response.send_message("Unable to process verify interaction right now.", ephemeral=True)
            except discord.NotFound as follow_error:
                if getattr(follow_error, "code", None) != 10062:
                    raise


class VerifyStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    def build_single_button_view(
        cls,
        *,
        mode: Literal["verify", "web_verify"],
        label: str,
        style: discord.ButtonStyle,
        emoji: str | None = None,
    ) -> "VerifyStartView":
        view = cls()
        mode_key = str(mode or "verify").strip().lower()
        if mode_key == "web_verify":
            view.remove_item(view.verify_start)
            target_button = view.verify_start_web
            default_label = "Web Verify"
        else:
            view.remove_item(view.verify_start_web)
            target_button = view.verify_start
            default_label = "Verify"

        target_button.label = str(label or default_label).strip()[:45] or default_label
        target_button.style = style

        emoji_text = str(emoji or "").strip()[:64]
        if emoji_text:
            try:
                target_button.emoji = emoji_text
            except Exception:
                target_button.emoji = None
        else:
            target_button.emoji = None
        return view

    @staticmethod
    def _is_unknown_interaction_error(error: Exception) -> bool:
        return getattr(error, "code", None) in {10062, 10015, 40060}

    async def _safe_send_response(
        self,
        interaction: discord.Interaction,
        content: str,
        *,
        ephemeral: bool = True,
        view: discord.ui.View | None = None,
    ) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content, ephemeral=ephemeral, view=view)
            else:
                await interaction.response.send_message(content, ephemeral=ephemeral, view=view)
        except discord.NotFound as error:
            if not self._is_unknown_interaction_error(error):
                raise

    async def _safe_followup_send(
        self,
        interaction: discord.Interaction,
        content: str,
        *,
        ephemeral: bool = True,
        view: discord.ui.View | None = None,
    ) -> None:
        try:
            await interaction.followup.send(content, ephemeral=ephemeral, view=view)
        except discord.NotFound as error:
            if not self._is_unknown_interaction_error(error):
                raise

    async def _handle_start(self, interaction: discord.Interaction, *, mode: str) -> None:
        try:
            cog = interaction.client.get_cog("Verify")
            if not cog or not isinstance(cog, Verify):
                await self._safe_send_response(interaction, "Verify system is not ready right now.", ephemeral=True)
                return

            try:
                interaction_age = (
                    discord.utils.utcnow() - interaction.created_at
                ).total_seconds()
                if interaction_age >= 2.5:
                    logger.warning(
                        f"Verify interaction dispatch delay is high ({interaction_age:.3f}s) "
                        f"for mode={mode}"
                    )
            except Exception:
                pass

            guild_id = int(interaction.guild.id) if interaction.guild else 0

            if mode == "web_verify":
                try:
                    await interaction.response.defer(ephemeral=True)
                except discord.NotFound as error:
                    if self._is_unknown_interaction_error(error):
                        return
                    raise
                settings = await asyncio.wait_for(
                    cog._fetch_verify_settings(
                        guild_id,
                        ensure_back_url=False,
                        use_cache=True,
                    ),
                    timeout=2.4,
                )
                if not settings.get("web_verify_enabled"):
                    await self._safe_followup_send(interaction, "Web Verify is currently disabled.", ephemeral=True)
                    return

                verify_url = cog.build_web_verify_url(
                    guild_id=int(getattr(interaction.guild, "id", 0) or 0),
                    user_id=int(getattr(interaction.user, "id", 0) or 0),
                )
                if not verify_url:
                    await self._safe_followup_send(interaction, "Unable to create a Web Verify link right now.", ephemeral=True)
                    return

                view = discord.ui.View(timeout=180)
                button_kwargs: dict[str, Any] = {
                    "label": str(settings.get("web_verify_button_label") or "Verify Now")[:45] or "Verify Now",
                    "style": discord.ButtonStyle.link,
                    "url": verify_url,
                }
                emoji = str(settings.get("web_verify_button_emoji") or "").strip()[:64]
                if emoji:
                    button_kwargs["emoji"] = emoji
                try:
                    view.add_item(discord.ui.Button(**button_kwargs))
                except Exception:
                    button_kwargs.pop("emoji", None)
                    view.add_item(discord.ui.Button(**button_kwargs))

                await self._safe_followup_send(
                    interaction,
                    str(settings.get("web_verify_intro") or "Click the button below to verify via web")[:280],
                    ephemeral=True,
                    view=view,
                )
                return

            settings = cog._get_cached_settings(guild_id)
            if settings is not None and not settings.get("enabled"):
                await self._safe_send_response(interaction, "Verify system is currently disabled.", ephemeral=True)
                return
            if settings is None:
                try:
                    settings = await asyncio.wait_for(
                        cog._fetch_verify_settings(
                            guild_id,
                            ensure_back_url=False,
                            use_cache=True,
                        ),
                        timeout=0.75,
                    )
                except Exception:
                    settings = _normalize_verify_settings({})
                    if guild_id > 0:
                        asyncio.create_task(
                            cog._fetch_verify_settings(
                                guild_id,
                                ensure_back_url=False,
                                use_cache=True,
                            )
                        )
                if settings is not None and not settings.get("enabled"):
                    await self._safe_send_response(interaction, "Verify system is currently disabled.", ephemeral=True)
                    return

            modal = VerifyModal(cog=cog, settings=settings)
            try:
                await interaction.response.send_modal(modal)
            except discord.NotFound as error:
                if self._is_unknown_interaction_error(error):
                    return
                raise
        except Exception as error:
            logger.error(f"Verify start interaction failed: {error}")
            if self._is_unknown_interaction_error(error):
                return
            try:
                await self._safe_send_response(interaction, "Unable to process verify interaction right now.", ephemeral=True)
            except Exception:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, _: discord.ui.Item[Any]) -> None:
        logger.error(f"Verify view error: {error}")
        if self._is_unknown_interaction_error(error):
            return
        try:
            await self._safe_send_response(interaction, "Verify interaction failed. Please try again.", ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_start")
    async def verify_start(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._handle_start(interaction, mode="verify")

    @discord.ui.button(label="Web Verify", style=discord.ButtonStyle.blurple, custom_id="verify_start_web")
    async def verify_start_web(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._handle_start(interaction, mode="web_verify")


class Verify(commands.Cog):
    verify_group = app_commands.Group(
        name="verify",
        description="คำสั่งระบบยืนยันตัวตน",
    )
    plan_group = app_commands.Group(
        name="plan",
        description="จัดการยศ Plan สำหรับกิลด์ Support",
    )

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerifyStartView())
        self._settings_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._settings_cache_ttl_seconds = 180.0
        self._support_plan_settings_cache: tuple[float, dict[str, Any]] | None = None
        self._support_plan_settings_cache_ttl_seconds = 60.0
        self._support_plan_sync_last_at = 0.0
        self._support_plan_sync_interval_seconds = 180.0

    @staticmethod
    def _button_style(color_value: Any, default: discord.ButtonStyle = discord.ButtonStyle.green) -> discord.ButtonStyle:
        return {
            "green": discord.ButtonStyle.green,
            "blurple": discord.ButtonStyle.blurple,
            "red": discord.ButtonStyle.red,
            "gray": discord.ButtonStyle.gray,
        }.get(str(color_value or "").strip().lower(), default)

    @staticmethod
    def _support_guild_id_candidates() -> list[int]:
        candidate_ids: list[int] = []
        for key in ("SUPPORT_GUILD_ID", "SUPPORT_HOME_GUILD_ID"):
            raw = str(os.getenv(key, "") or "").strip()
            if not raw or not raw.isdigit():
                continue
            guild_id = int(raw)
            if guild_id > 0 and guild_id not in candidate_ids:
                candidate_ids.append(guild_id)
        return candidate_ids

    def _resolve_support_guild_id(self, settings: dict[str, Any] | None = None) -> int | None:
        candidates = self._support_guild_id_candidates()
        if not candidates and isinstance(settings, dict):
            settings_guild_id = _safe_int(settings.get("support_guild_id"), 0)
            if settings_guild_id > 0:
                candidates.append(settings_guild_id)
        return candidates[0] if candidates else None

    @staticmethod
    def _support_plan_tier_label(tier: str) -> str:
        return {
            "free": "Free",
            "silver": "Silver",
            "golden": "Gole",
            "diamond": "Diamond",
            "permanent": "Permanent",
        }.get(_normalize_support_plan_tier(tier), "Free")

    def _is_ownerbot_operator(self, user: discord.abc.User | discord.Member | None) -> bool:
        actor_id = _safe_int(getattr(user, "id", 0), 0)
        if actor_id <= 0:
            return False
        if checks.check_is_admin_predicate(user):
            return True
        owner_ids = set(getattr(self.bot, "owner_ids", set()) or set())
        if actor_id in owner_ids:
            return True
        developers = list(getattr(self.bot, "developers", []) or [])
        if any(_safe_int(getattr(dev, "id", 0), 0) == actor_id for dev in developers):
            return True
        for env_name in ("OWNER_ID", "OWNER_IDS", "BOT_OWNER_ID", "BOT_OWNER_IDS"):
            raw = str(os.getenv(env_name, "") or "").replace("\n", ",")
            for item in raw.split(","):
                if _safe_int(item, 0) == actor_id:
                    return True
        return False

    @staticmethod
    def _member_has_role(member: discord.Member, role_id: int) -> bool:
        if role_id <= 0:
            return True
        return any(int(getattr(role, "id", 0) or 0) == int(role_id) for role in list(getattr(member, "roles", []) or []))

    async def _load_support_plan_autorole_settings(self, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and self._support_plan_settings_cache:
            cached_at, cached_settings = self._support_plan_settings_cache
            if (now - float(cached_at)) <= float(self._support_plan_settings_cache_ttl_seconds):
                return _normalize_support_plan_autorole_settings(cached_settings)

        payload: dict[str, Any] = {}
        try:
            row = await dashboard_config_db.get(config_key=SUPPORT_PLAN_AUTOROLE_CONFIG_KEY)
            raw = str((row or {}).get("config_value") or "").strip()
            if raw:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    payload = decoded
        except Exception as error:
            logger.error(f"Load support plan autorole settings failed: {error}")
            payload = {}

        normalized = _normalize_support_plan_autorole_settings(payload)
        support_guild_id = self._resolve_support_guild_id(normalized)
        if support_guild_id and _safe_int(normalized.get("support_guild_id"), 0) <= 0:
            normalized["support_guild_id"] = int(support_guild_id)
        self._support_plan_settings_cache = (now, normalized)
        return normalized

    async def _save_support_plan_autorole_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_support_plan_autorole_settings(settings)
        support_guild_id = self._resolve_support_guild_id(normalized)
        if support_guild_id and _safe_int(normalized.get("support_guild_id"), 0) <= 0:
            normalized["support_guild_id"] = int(support_guild_id)

        encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        writer = getattr(dashboard_config_db, "set_config_value", None)
        if callable(writer):
            await writer(config_key=SUPPORT_PLAN_AUTOROLE_CONFIG_KEY, config_value=encoded)
        else:
            row = await dashboard_config_db.get(config_key=SUPPORT_PLAN_AUTOROLE_CONFIG_KEY)
            if row and row.get("id"):
                await dashboard_config_db.update(
                    id=row["id"],
                    config_key=SUPPORT_PLAN_AUTOROLE_CONFIG_KEY,
                    config_value=encoded,
                )
            else:
                await dashboard_config_db.insert(
                    config_key=SUPPORT_PLAN_AUTOROLE_CONFIG_KEY,
                    config_value=encoded,
                )
        self._support_plan_settings_cache = (time.monotonic(), normalized)
        return normalized

    async def _user_top_plan_tiers(self) -> dict[int, str]:
        top_tiers: dict[int, str] = {}
        rows = await storage.bot_plan_subscriptions.get_all()
        for row in rows or []:
            user_id = _safe_int((row or {}).get("user_id"), 0)
            if user_id <= 0:
                continue
            tier = _normalize_support_plan_tier((row or {}).get("current_plan"))
            current = top_tiers.get(user_id, "free")
            if SUPPORT_PLAN_TIER_RANK.get(tier, 0) > SUPPORT_PLAN_TIER_RANK.get(current, 0):
                top_tiers[user_id] = tier
        return top_tiers

    async def sync_support_plan_roles(
        self,
        *,
        target_user_ids: set[int] | None = None,
        force: bool = False,
        reason: str = "Support plan role sync",
    ) -> dict[str, Any]:
        now = time.monotonic()
        if not force and not target_user_ids:
            if (now - float(self._support_plan_sync_last_at or 0.0)) < float(self._support_plan_sync_interval_seconds):
                return {"ok": True, "skipped": "cooldown"}

        settings = await self._load_support_plan_autorole_settings(force=False)
        if not settings.get("enabled"):
            return {"ok": False, "skipped": "disabled"}

        support_guild_id = self._resolve_support_guild_id(settings)
        if not support_guild_id:
            return {"ok": False, "skipped": "missing_support_guild_id"}

        support_guild = self.bot.get_guild(int(support_guild_id))
        if support_guild is None:
            return {"ok": False, "skipped": "support_guild_unavailable"}

        me = support_guild.me
        if me is None and self.bot.user:
            me = support_guild.get_member(int(self.bot.user.id))
        if me is None and self.bot.user:
            try:
                me = await support_guild.fetch_member(int(self.bot.user.id))
            except Exception:
                me = None
        if me is None:
            return {"ok": False, "skipped": "bot_member_unavailable"}
        if not bool(getattr(me.guild_permissions, "manage_roles", False)):
            return {"ok": False, "skipped": "missing_manage_roles"}

        tier_role_ids = settings.get("tier_role_ids") if isinstance(settings.get("tier_role_ids"), dict) else {}
        managed_role_ids = {
            _safe_int(tier_role_ids.get("free"), 0),
            _safe_int(tier_role_ids.get("silver"), 0),
            _safe_int(tier_role_ids.get("golden"), 0),
            _safe_int(tier_role_ids.get("diamond"), 0),
            _safe_int(tier_role_ids.get("permanent"), 0),
        }
        managed_role_ids = {role_id for role_id in managed_role_ids if role_id > 0}
        if not managed_role_ids:
            return {"ok": False, "skipped": "no_managed_roles"}

        required_role_id = _safe_int(settings.get("required_role_id"), 0)
        user_top_tiers = await self._user_top_plan_tiers()
        candidate_user_ids: set[int] = set()

        if target_user_ids:
            for user_id in target_user_ids:
                parsed_user_id = _safe_int(user_id, 0)
                if parsed_user_id > 0:
                    candidate_user_ids.add(parsed_user_id)
        else:
            candidate_user_ids.update(user_top_tiers.keys())
            for role_id in managed_role_ids:
                role_obj = support_guild.get_role(int(role_id))
                if role_obj:
                    candidate_user_ids.update(int(member.id) for member in list(role_obj.members))
            if required_role_id > 0:
                required_role = support_guild.get_role(required_role_id)
                if required_role:
                    candidate_user_ids.update(int(member.id) for member in list(required_role.members))

        summary = {
            "ok": True,
            "checked": 0,
            "updated": 0,
            "added": 0,
            "removed": 0,
            "missing_member": 0,
            "skipped_unmanageable": 0,
            "errors": 0,
        }
        action_reason = str(reason or "Support plan role sync")[:500]

        for user_id in sorted(candidate_user_ids):
            member = support_guild.get_member(int(user_id))
            if member is None and (target_user_ids is not None or int(user_id) in user_top_tiers):
                try:
                    member = await support_guild.fetch_member(int(user_id))
                except Exception:
                    member = None
            if member is None:
                summary["missing_member"] += 1
                continue
            if bool(getattr(member, "bot", False)):
                continue

            summary["checked"] += 1
            has_required_role = self._member_has_role(member, required_role_id)
            target_tier = user_top_tiers.get(int(member.id), "free")
            target_role_id = _safe_int(tier_role_ids.get(target_tier), 0) if has_required_role else 0

            member_managed_roles: list[discord.Role] = []
            for role_id in managed_role_ids:
                role_obj = support_guild.get_role(int(role_id))
                if role_obj and role_obj in member.roles:
                    member_managed_roles.append(role_obj)

            roles_to_remove: list[discord.Role] = []
            for role_obj in member_managed_roles:
                if int(role_obj.id) != int(target_role_id):
                    if int(role_obj.position) >= int(me.top_role.position) or bool(getattr(role_obj, "managed", False)):
                        summary["skipped_unmanageable"] += 1
                    else:
                        roles_to_remove.append(role_obj)

            role_to_add = support_guild.get_role(int(target_role_id)) if int(target_role_id) > 0 else None
            roles_to_add: list[discord.Role] = []
            if role_to_add and role_to_add not in member.roles:
                if int(role_to_add.position) >= int(me.top_role.position) or bool(getattr(role_to_add, "managed", False)):
                    summary["skipped_unmanageable"] += 1
                else:
                    roles_to_add.append(role_to_add)

            if not roles_to_remove and not roles_to_add:
                continue

            try:
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason=action_reason)
                    summary["removed"] += len(roles_to_remove)
                if roles_to_add:
                    await member.add_roles(*roles_to_add, reason=action_reason)
                    summary["added"] += len(roles_to_add)
                summary["updated"] += 1
            except Exception:
                summary["errors"] += 1

        if target_user_ids is None:
            self._support_plan_sync_last_at = now
        return summary

    def _web_verify_signing_secret(self) -> bytes:
        candidates = [
            str(os.getenv("BOT_VERIFY_WEB_SECRET", "") or "").strip(),
            str(os.getenv("VERIFY_WEB_SECRET", "") or "").strip(),
            str(getattr(BOT_CONFIG, "DISCORD_CLIENT_SECRET", "") or "").strip(),
            str(getattr(BOT_CONFIG, "TOKEN", "") or "").strip(),
        ]
        joined = "|".join([item for item in candidates if item])
        if not joined:
            return b""
        return hashlib.sha256(joined.encode("utf-8")).digest()

    def _dashboard_base_url(self) -> str:
        candidates = [
            str(getattr(BOT_CONFIG, "DASHBOARD_BASE_URL", "") or "").strip(),
            str(os.getenv("DASHBOARD_BASE_URL", "") or "").strip(),
            str(os.getenv("PRIMARY_BASE_URL", "") or "").strip(),
            str(os.getenv("PUBLIC_BASE_URL", "") or "").strip(),
            str(os.getenv("BOT_PUBLIC_BASE_URL", "") or "").strip(),
        ]
        fallback_local = ""
        for configured in candidates:
            if not configured:
                continue
            if "://" not in configured:
                configured = f"https://{configured}"
            cleaned = configured.rstrip("/")
            parsed = urlsplit(cleaned)
            host = str(parsed.hostname or "").strip().lower()
            if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
                if not fallback_local:
                    fallback_local = cleaned
                continue
            return cleaned
        return fallback_local

    @staticmethod
    def _is_http_url(value: Any) -> bool:
        text = str(value or "").strip().lower()
        return text.startswith("http://") or text.startswith("https://")

    @staticmethod
    def _is_discord_back_url(value: Any) -> bool:
        text = str(value or "").strip().lower()
        return (
            text.startswith("https://discord.com/channels/")
            or text.startswith("http://discord.com/channels/")
        )

    async def _create_back_invite_url(
        self,
        guild: discord.Guild,
        *,
        preferred_channel_id: int | None = None,
    ) -> str:
        if not guild:
            return ""

        candidates: list[discord.abc.GuildChannel] = []
        seen_ids: set[int] = set()

        def _push_channel(channel: Any) -> None:
            if not isinstance(channel, discord.abc.GuildChannel):
                return
            channel_id = int(getattr(channel, "id", 0) or 0)
            if channel_id <= 0 or channel_id in seen_ids:
                return
            seen_ids.add(channel_id)
            candidates.append(channel)

        if int(preferred_channel_id or 0) > 0:
            _push_channel(guild.get_channel(int(preferred_channel_id)))

        _push_channel(getattr(guild, "system_channel", None))
        _push_channel(getattr(guild, "rules_channel", None))
        _push_channel(getattr(guild, "public_updates_channel", None))

        for text_channel in list(getattr(guild, "text_channels", []) or []):
            _push_channel(text_channel)

        me = getattr(guild, "me", None)
        for channel in candidates:
            if not hasattr(channel, "create_invite"):
                continue
            if me and hasattr(channel, "permissions_for"):
                try:
                    perms = channel.permissions_for(me)
                except Exception:
                    perms = None
                if perms and not bool(
                    getattr(perms, "view_channel", False)
                    and getattr(perms, "create_instant_invite", False)
                ):
                    continue
            try:
                invite = await channel.create_invite(
                    max_age=0,
                    max_uses=0,
                    temporary=False,
                    unique=False,
                    reason="SkylineBOT Verify back link sync",
                )
            except Exception:
                continue
            invite_url = str(getattr(invite, "url", "") or "").strip()
            if self._is_http_url(invite_url):
                return invite_url
        return ""

    async def ensure_back_to_server_url(
        self,
        *,
        guild_id: int,
        settings: dict[str, Any] | None = None,
        force_regenerate: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        normalized = _normalize_verify_settings(settings or {})
        current_url = str(normalized.get("back_to_server_url") or "").strip()
        current_lower = current_url.lower()
        expected_prefixes = (
            f"https://discord.com/channels/{int(guild_id)}".lower(),
            f"http://discord.com/channels/{int(guild_id)}".lower(),
        )

        if any(current_lower.startswith(prefix) for prefix in expected_prefixes) and not force_regenerate:
            return current_url, normalized

        back_url = f"https://discord.com/channels/{int(guild_id)}"

        normalized["back_to_server_url"] = back_url
        try:
            guilds_col = await get_collection("guilds")
            await guilds_col.update_one(
                {"guild_id": int(guild_id)},
                {"$set": {"verify_settings_fallback": _normalize_verify_settings(normalized)}},
                upsert=True,
            )
        except Exception as error:
            logger.error(f"Verify back link sync failed: {error}")

        return back_url, normalized

    @staticmethod
    def _urlsafe_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _urlsafe_decode(raw: str) -> bytes:
        text = str(raw or "").strip()
        if not text:
            return b""
        pad = "=" * ((4 - (len(text) % 4)) % 4)
        return base64.urlsafe_b64decode(text + pad)

    def _sign_web_token_payload(self, payload: dict[str, Any]) -> str:
        secret = self._web_verify_signing_secret()
        if not secret:
            return ""
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        body_enc = self._urlsafe_encode(body)
        signature = hmac.new(secret, body_enc.encode("utf-8"), hashlib.sha256).digest()
        sig_enc = self._urlsafe_encode(signature)
        return f"{body_enc}.{sig_enc}"

    def _unsign_web_token_payload(self, token: str) -> dict[str, Any] | None:
        secret = self._web_verify_signing_secret()
        raw_token = str(token or "").strip()
        if not secret or "." not in raw_token:
            return None
        body_enc, sig_enc = raw_token.split(".", 1)
        expected_sig = self._urlsafe_encode(hmac.new(secret, body_enc.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected_sig, sig_enc):
            return None
        try:
            payload_bytes = self._urlsafe_decode(body_enc)
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        now = int(time.time())
        expires_at = int(payload.get("exp") or 0)
        if expires_at <= 0 or now > expires_at:
            return None
        guild_id = int(payload.get("gid") or 0)
        user_id = int(payload.get("uid") or 0)
        if guild_id <= 0 or user_id <= 0:
            return None
        return payload

    def build_web_verify_url(self, *, guild_id: int, user_id: int) -> str:
        base_url = self._dashboard_base_url()
        if not base_url or guild_id <= 0 or user_id <= 0:
            return ""
        now = int(time.time())
        token = self._sign_web_token_payload(
            {
                "v": 1,
                "gid": int(guild_id),
                "uid": int(user_id),
                "iat": now,
                "exp": now + 3600,
                "nonce": secrets.token_urlsafe(8),
            }
        )
        if not token:
            return ""
        return f"{base_url}/dashboard/verify/session?{urlencode({'t': token})}"

    def decode_web_verify_token(self, token: str) -> dict[str, Any] | None:
        return self._unsign_web_token_payload(token)

    async def fetch_verify_settings(self, guild_id: int) -> dict[str, Any]:
        return await self._fetch_verify_settings(
            guild_id,
            ensure_back_url=True,
            use_cache=True,
        )

    def _cache_settings(self, guild_id: int, settings: dict[str, Any]) -> None:
        if guild_id <= 0:
            return
        self._settings_cache[int(guild_id)] = (time.monotonic(), _normalize_verify_settings(settings))

    def _get_cached_settings(self, guild_id: int, *, max_age_seconds: float | None = None) -> dict[str, Any] | None:
        if guild_id <= 0:
            return None
        cached = self._settings_cache.get(int(guild_id))
        if not cached:
            return None
        created_at, payload = cached
        ttl = float(self._settings_cache_ttl_seconds if max_age_seconds is None else max_age_seconds)
        if ttl > 0 and (time.monotonic() - float(created_at)) > ttl:
            return None
        return _normalize_verify_settings(payload)

    async def _fetch_verify_settings(
        self,
        guild_id: int,
        *,
        ensure_back_url: bool,
        use_cache: bool,
    ) -> dict[str, Any]:
        if not guild_id:
            return _normalize_verify_settings({})
        if use_cache:
            cached = self._get_cached_settings(guild_id)
            if cached:
                return cached
        try:
            guilds_col = await get_collection("guilds")
            doc = await guilds_col.find_one({"guild_id": guild_id}, {"verify_settings_fallback": 1, "_id": 0})
            payload = (doc or {}).get("verify_settings_fallback")
            normalized = _normalize_verify_settings(payload if isinstance(payload, dict) else {})
            if ensure_back_url:
                _, normalized = await self.ensure_back_to_server_url(
                    guild_id=int(guild_id),
                    settings=normalized,
                )
            self._cache_settings(guild_id, normalized)
            return normalized
        except Exception as error:
            logger.error(f"Verify settings load failed: {error}")
            return _normalize_verify_settings({})

    def _build_verify_embed(self, guild: discord.Guild, settings: dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=str(settings.get("embed_title") or "ยืนยันตัวตน"),
            description=str(settings.get("description") or "กดปุ่มด้านล่างเพื่อเริ่มยืนยันตัวตน"),
            color=_safe_color(settings.get("color")),
        )
        thumb = str(settings.get("embed_thumbnail_url") or "").strip()
        image = str(settings.get("embed_image_url") or "").strip()
        footer = str(settings.get("embed_footer") or "").strip()

        if thumb:
            embed.set_thumbnail(url=thumb)
        if image:
            embed.set_image(url=image)
        if footer:
            embed.set_footer(text=footer)
        embed.add_field(name="Server", value=guild.name, inline=True)
        return embed

    def _build_web_verify_embed(self, guild: discord.Guild, settings: dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title=str(settings.get("web_verify_embed_title") or "ยืนยันตัวตนผ่านเว็บ"),
            description=str(settings.get("web_verify_embed_description") or "กดปุ่มด้านล่างเพื่อเปิดหน้า Web Verify"),
            color=_safe_color(settings.get("web_verify_color") or settings.get("color")),
        )
        thumb = str(settings.get("web_verify_embed_thumbnail_url") or "").strip()
        image = str(settings.get("web_verify_embed_image_url") or "").strip()
        footer = str(settings.get("web_verify_embed_footer") or "").strip()

        if thumb:
            embed.set_thumbnail(url=thumb)
        if image:
            embed.set_image(url=image)
        if footer:
            embed.set_footer(text=footer)
        embed.add_field(name="Server", value=guild.name, inline=True)
        return embed

    def _build_verify_button_view(
        self,
        *,
        custom_id: str,
        label: str,
        color: Any,
        emoji: str | None = None,
    ) -> discord.ui.View:
        custom_id_value = str(custom_id or "").strip().lower()
        if custom_id_value in {"verify_start", "verify_start_web"}:
            return VerifyStartView.build_single_button_view(
                mode="web_verify" if custom_id_value == "verify_start_web" else "verify",
                label=str(label or "Verify")[:45] or "Verify",
                style=self._button_style(color),
                emoji=str(emoji or "").strip()[:64] or None,
            )

        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label=str(label or "Verify")[:45] or "Verify",
                style=self._button_style(color),
                custom_id=custom_id_value or "verify_start",
            )
        )
        return view

    @staticmethod
    def _message_has_button_custom_id(message: discord.Message, custom_id: str) -> bool:
        wanted = str(custom_id or "").strip()
        if not wanted:
            return False
        for row in list(getattr(message, "components", []) or []):
            children = getattr(row, "children", None)
            if children is None and isinstance(row, dict):
                children = row.get("components") or []
            for child in list(children or []):
                child_custom_id = str(getattr(child, "custom_id", "") or "")
                if not child_custom_id and isinstance(child, dict):
                    child_custom_id = str(child.get("custom_id") or "")
                if child_custom_id == wanted:
                    return True
        return False

    async def _find_existing_panel_messages(
        self,
        channel: discord.TextChannel | discord.Thread,
        *,
        custom_id: str,
        limit: int = 120,
    ) -> list[discord.Message]:
        if not self.bot.user:
            return []
        found: list[discord.Message] = []
        try:
            async for message in channel.history(limit=limit):
                if int(getattr(message.author, "id", 0) or 0) != int(self.bot.user.id):
                    continue
                if self._message_has_button_custom_id(message, custom_id):
                    found.append(message)
        except Exception as error:
            logger.error(f"Verify panel history scan failed: {error}")
        return found

    async def _publish_panel_in_channel(
        self,
        *,
        channel: discord.TextChannel | discord.Thread,
        custom_id: str,
        embed: discord.Embed,
        view: discord.ui.View,
    ) -> tuple[discord.Message, bool, int]:
        existing_messages = await self._find_existing_panel_messages(channel, custom_id=custom_id)
        edited_existing = False
        primary_message: discord.Message | None = None

        if existing_messages:
            candidate = existing_messages[0]
            try:
                await candidate.edit(embed=embed, view=view)
                primary_message = candidate
                edited_existing = True
            except Exception as error:
                logger.error(f"Verify panel edit failed: {error}")

        if primary_message is None:
            primary_message = await channel.send(embed=embed, view=view)

        duplicates_deleted = 0
        for message in existing_messages:
            if edited_existing and message.id == primary_message.id:
                continue
            try:
                await message.delete()
                duplicates_deleted += 1
            except Exception:
                pass

        return primary_message, edited_existing, duplicates_deleted

    def plan_role_changes(
        self,
        *,
        member: discord.Member,
        guild: discord.Guild,
        settings: dict[str, Any],
        source: Literal["verify", "web_verify"] = "verify",
    ) -> tuple[list[discord.Role], list[discord.Role]]:
        add_roles: list[discord.Role] = []
        remove_roles: list[discord.Role] = []

        source_mode = str(source or "verify").strip().lower()
        auto_role_enabled = settings.get("auto_role_enabled")
        reward_role_ids = settings.get("reward_role_ids", [])
        remove_role_ids = settings.get("remove_role_ids", [])
        if source_mode == "web_verify":
            auto_role_enabled = settings.get("web_verify_auto_role_enabled", auto_role_enabled)
            reward_role_ids = settings.get("web_verify_reward_role_ids", reward_role_ids)
            remove_role_ids = settings.get("web_verify_remove_role_ids", remove_role_ids)

        if auto_role_enabled:
            for role_id in reward_role_ids:
                role = guild.get_role(int(role_id))
                if role and role not in member.roles:
                    add_roles.append(role)

        for role_id in remove_role_ids:
            role = guild.get_role(int(role_id))
            if role and role in member.roles:
                remove_roles.append(role)
        return add_roles, remove_roles

    async def apply_verification(
        self,
        *,
        member: discord.Member | None,
        guild: discord.Guild | None,
        settings: dict[str, Any],
        form_values: list[str] | None = None,
        actor: discord.abc.User | discord.Member | None = None,
        source: Literal["verify", "web_verify"] = "verify",
    ) -> bool:
        if not member or not guild:
            return False
        try:
            add_roles, remove_roles = self.plan_role_changes(
                member=member,
                guild=guild,
                settings=settings,
                source=source,
            )

            if add_roles:
                await member.add_roles(*add_roles, reason="Verification success")
            if remove_roles:
                await member.remove_roles(*remove_roles, reason="Verification success")

            if settings.get("nickname_from_first_input") and form_values:
                first_value = str(form_values[0] or "").strip()
                if first_value:
                    await member.edit(nick=first_value[:32], reason="Verification nickname update")

            try:
                await self.sync_support_plan_roles(
                    target_user_ids={int(member.id)},
                    force=True,
                    reason="Verification success plan role sync",
                )
            except Exception as sync_error:
                logger.warning(f"Support plan role sync on verify failed: {sync_error}")

            source_mode = str(source or "verify").strip().lower()
            notify_channel_id = (
                settings.get("web_verify_notify_channel_id") or settings.get("notify_channel_id")
                if source_mode == "web_verify"
                else settings.get("notify_channel_id")
            )
            notify_channel = (
                guild.get_channel(int(notify_channel_id))
                if str(notify_channel_id or "").strip().isdigit()
                else None
            )
            if notify_channel and isinstance(notify_channel, (discord.TextChannel, discord.Thread)):
                embed = discord.Embed(
                    title="ยืนยันตัวตนสำเร็จ",
                    description=f"{member.mention} ยืนยันตัวตนเรียบร้อยแล้ว",
                    color=_safe_color(settings.get("color")),
                )
                if add_roles:
                    embed.add_field(name="Roles Added", value=", ".join(role.mention for role in add_roles), inline=False)
                if remove_roles:
                    embed.add_field(name="Roles Removed", value=", ".join(role.mention for role in remove_roles), inline=False)
                if actor:
                    embed.set_footer(text=f"Action by {actor}")
                await notify_channel.send(embed=embed)

            return True
        except Exception as error:
            logger.error(f"Verify apply failed: {error}")
            return False

    @verify_group.command(name="publish", description="ส่งแผงยืนยันตัวตนไปยังห้องที่ตั้งค่าไว้")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def verify_publish(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        settings = await self.fetch_verify_settings(interaction.guild.id)
        channel_id = settings.get("verify_channel_id")
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("ยังไม่ได้ตั้งค่าห้องยืนยันตัวตน", ephemeral=True)
            return
        embed = self._build_verify_embed(interaction.guild, settings)
        view = self._build_verify_button_view(
            custom_id="verify_start",
            label=str(settings.get("button_label") or "ยืนยันตัวตน"),
            color=settings.get("button_color"),
            emoji=str(settings.get("button_emoji") or "").strip()[:64] or None,
        )

        _, edited_existing, duplicates_deleted = await self._publish_panel_in_channel(
            channel=channel,
            custom_id="verify_start",
            embed=embed,
            view=view,
        )

        action_text = "อัปเดตแผงยืนยันตัวตน" if edited_existing else "ส่งแผงยืนยันตัวตน"
        duplicates_note = f" (ลบข้อความซ้ำ {duplicates_deleted} ข้อความ)" if duplicates_deleted > 0 else ""
        await interaction.response.send_message(
            f"{action_text}ไปที่ {channel.mention} แล้ว{duplicates_note}",
            ephemeral=True,
        )

    @verify_group.command(name="web", description="ส่งแผง Web Verify ไปยังห้องที่ตั้งค่าไว้")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def verify_web(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        settings = await self.fetch_verify_settings(interaction.guild.id)
        channel_id = settings.get("web_verify_channel_id")
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("ยังไม่ได้ตั้งค่าห้อง Web Verify", ephemeral=True)
            return

        embed = self._build_web_verify_embed(interaction.guild, settings)
        view = self._build_verify_button_view(
            custom_id="verify_start_web",
            label=str(settings.get("web_verify_button_label") or "ยืนยันตัวตนตอนนี้"),
            color=settings.get("web_verify_button_color"),
            emoji=str(settings.get("web_verify_button_emoji") or "").strip()[:64] or None,
        )

        _, edited_existing, duplicates_deleted = await self._publish_panel_in_channel(
            channel=channel,
            custom_id="verify_start_web",
            embed=embed,
            view=view,
        )

        action_text = "อัปเดตแผง Web Verify" if edited_existing else "ส่งแผง Web Verify"
        duplicates_note = f" (ลบข้อความซ้ำ {duplicates_deleted} ข้อความ)" if duplicates_deleted > 0 else ""
        await interaction.response.send_message(
            f"{action_text}ไปที่ {channel.mention} แล้ว{duplicates_note}",
            ephemeral=True,
        )

    @verify_group.command(name="success", description="ยืนยันผู้ใช้สำเร็จและจัดการยศตามตั้งค่า")
    @app_commands.describe(user="ผู้ใช้ที่ยืนยันสำเร็จ", nickname="ชื่อใหม่ (ถ้าต้องการ)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def verify_success(self, interaction: discord.Interaction, user: discord.Member, nickname: str | None = None):
        if not interaction.guild:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        settings = await self.fetch_verify_settings(interaction.guild.id)
        values = [nickname or ""]
        success = await self.apply_verification(
            member=user,
            guild=interaction.guild,
            settings=settings,
            form_values=values,
            actor=interaction.user,
            source="verify",
        )
        if success:
            await interaction.response.send_message(f"ยืนยัน {user.mention} สำเร็จแล้ว", ephemeral=True)
        else:
            await interaction.response.send_message("ไม่สามารถยืนยันผู้ใช้ได้", ephemeral=True)

    @plan_group.command(name="setupautorole", description="ตั้งค่ายศ Plan อัตโนมัติในกิลด์ Support")
    @app_commands.describe(
        required_role="ยศที่สมาชิกต้องมีอยู่ก่อน (เช่น ยศยืนยันตัว)",
        free_role="ยศสำหรับแผน Free",
        silver_role="ยศสำหรับแผน Silver",
        golden_role="ยศสำหรับแผน Gole",
        diamond_role="ยศสำหรับแผน Diamond",
        permanent_role="ยศสำหรับแผน Permanent",
    )
    async def plan_setupautorole(
        self,
        interaction: discord.Interaction,
        required_role: discord.Role,
        free_role: discord.Role,
        silver_role: discord.Role | None = None,
        golden_role: discord.Role | None = None,
        diamond_role: discord.Role | None = None,
        permanent_role: discord.Role | None = None,
    ):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        if not self._is_ownerbot_operator(interaction.user):
            await interaction.response.send_message("คำสั่งนี้ใช้ได้เฉพาะ OwnerBOT เท่านั้น", ephemeral=True)
            return

        support_guild_id = self._resolve_support_guild_id()
        if not support_guild_id:
            await interaction.response.send_message(
                "ยังไม่ได้ตั้งค่า `SUPPORT_GUILD_ID` หรือ `SUPPORT_HOME_GUILD_ID`",
                ephemeral=True,
            )
            return
        if int(guild.id) != int(support_guild_id):
            await interaction.response.send_message(
                f"คำสั่งนี้ใช้ได้เฉพาะใน Support Guild (`{support_guild_id}`) เท่านั้น",
                ephemeral=True,
            )
            return

        me = guild.me
        if me is None and self.bot.user:
            me = guild.get_member(int(self.bot.user.id))
        if me is None:
            await interaction.response.send_message("ไม่พบบอทในกิลด์นี้", ephemeral=True)
            return
        if not bool(getattr(me.guild_permissions, "manage_roles", False)):
            await interaction.response.send_message("บอทต้องมีสิทธิ์ Manage Roles ก่อน", ephemeral=True)
            return

        tier_roles: dict[str, discord.Role | None] = {
            "free": free_role,
            "silver": silver_role,
            "golden": golden_role,
            "diamond": diamond_role,
            "permanent": permanent_role,
        }
        for tier_key, role_obj in tier_roles.items():
            if role_obj is None:
                continue
            if int(role_obj.position) >= int(me.top_role.position) or bool(getattr(role_obj, "managed", False)):
                await interaction.response.send_message(
                    f"บอทไม่สามารถจัดการยศ `{self._support_plan_tier_label(tier_key)}` ({role_obj.mention}) ได้ "
                    "กรุณาวางยศบอทให้สูงกว่ายศนี้",
                    ephemeral=True,
                )
                return

        settings_payload = {
            "enabled": True,
            "support_guild_id": int(support_guild_id),
            "required_role_id": int(required_role.id),
            "tier_role_ids": {
                "free": int(free_role.id),
                "silver": int(silver_role.id) if silver_role else 0,
                "golden": int(golden_role.id) if golden_role else 0,
                "diamond": int(diamond_role.id) if diamond_role else 0,
                "permanent": int(permanent_role.id) if permanent_role else 0,
            },
            "updated_by_user_id": int(getattr(interaction.user, "id", 0) or 0),
            "updated_at": discord.utils.utcnow().isoformat(),
        }
        saved = await self._save_support_plan_autorole_settings(settings_payload)
        sync_result = await self.sync_support_plan_roles(
            force=True,
            reason=f"/plan setupautorole by {getattr(interaction.user, 'id', 0)}",
        )

        role_map = saved.get("tier_role_ids", {}) if isinstance(saved.get("tier_role_ids"), dict) else {}

        def _role_text(role_id: Any) -> str:
            rid = _safe_int(role_id, 0)
            return f"<@&{rid}>" if rid > 0 else "`disabled`"

        lines = [
            "ตั้งค่า Plan Auto Role สำเร็จ",
            f"Support Guild: `{support_guild_id}`",
            f"Required Role: {required_role.mention}",
            f"Free: {_role_text(role_map.get('free'))}",
            f"Silver: {_role_text(role_map.get('silver'))}",
            f"Gole: {_role_text(role_map.get('golden'))}",
            f"Diamond: {_role_text(role_map.get('diamond'))}",
            f"Permanent: {_role_text(role_map.get('permanent'))}",
            (
                "Sync now: "
                f"updated={_safe_int(sync_result.get('updated'), 0)}, "
                f"added={_safe_int(sync_result.get('added'), 0)}, "
                f"removed={_safe_int(sync_result.get('removed'), 0)}"
            ),
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @plan_setupautorole.error
    async def plan_setupautorole_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "เกิดข้อผิดพลาดระหว่างตั้งค่า Plan Auto Role",
                ephemeral=True,
            )
        logger.error(f"Plan setupautorole error: {error}")

    @plan_group.command(name="showautorole", description="ดู mapping ยศ Plan ปัจจุบันในกิลด์ Support")
    async def plan_showautorole(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        if not self._is_ownerbot_operator(interaction.user):
            await interaction.response.send_message("คำสั่งนี้ใช้ได้เฉพาะ OwnerBOT เท่านั้น", ephemeral=True)
            return

        settings = await self._load_support_plan_autorole_settings(force=True)
        support_guild_id = self._resolve_support_guild_id(settings)
        if not support_guild_id:
            await interaction.response.send_message(
                "ยังไม่ได้ตั้งค่า `SUPPORT_GUILD_ID` หรือ `SUPPORT_HOME_GUILD_ID`",
                ephemeral=True,
            )
            return
        if int(guild.id) != int(support_guild_id):
            await interaction.response.send_message(
                f"คำสั่งนี้ใช้ได้เฉพาะใน Support Guild (`{support_guild_id}`) เท่านั้น",
                ephemeral=True,
            )
            return

        role_map = settings.get("tier_role_ids", {}) if isinstance(settings.get("tier_role_ids"), dict) else {}
        required_role_id = _safe_int(settings.get("required_role_id"), 0)
        updated_by_user_id = _safe_int(settings.get("updated_by_user_id"), 0)
        updated_at = str(settings.get("updated_at") or "").strip() or "-"
        enabled = bool(settings.get("enabled"))

        def _role_text(role_id: Any) -> str:
            rid = _safe_int(role_id, 0)
            if rid <= 0:
                return "`disabled`"
            role_obj = guild.get_role(rid)
            return role_obj.mention if role_obj else f"<@&{rid}> (`missing`)"

        required_role_text = _role_text(required_role_id) if required_role_id > 0 else "`not-set`"

        lines = [
            "Plan Auto Role Mapping",
            f"Enabled: {'yes' if enabled else 'no'}",
            f"Support Guild: `{support_guild_id}`",
            f"Required Role: {required_role_text}",
            f"Free: {_role_text(role_map.get('free'))}",
            f"Silver: {_role_text(role_map.get('silver'))}",
            f"Gole: {_role_text(role_map.get('golden'))}",
            f"Diamond: {_role_text(role_map.get('diamond'))}",
            f"Permanent: {_role_text(role_map.get('permanent'))}",
            f"Updated By: {f'<@{updated_by_user_id}>' if updated_by_user_id > 0 else '-'}",
            f"Updated At: `{updated_at}`",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @plan_showautorole.error
    async def plan_showautorole_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "เกิดข้อผิดพลาดระหว่างแสดง Plan Auto Role",
                ephemeral=True,
            )
        logger.error(f"Plan showautorole error: {error}")

    @plan_group.command(name="syncroles", description="ซิงก์ยศ Plan ในกิลด์ Support ทันที")
    @app_commands.describe(
        user="ถ้าระบุ จะซิงก์เฉพาะผู้ใช้นี้ (ไม่ระบุ = ซิงก์ทั้งกิลด์)",
    )
    async def plan_syncroles(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        if not self._is_ownerbot_operator(interaction.user):
            await interaction.response.send_message("คำสั่งนี้ใช้ได้เฉพาะ OwnerBOT เท่านั้น", ephemeral=True)
            return

        support_guild_id = self._resolve_support_guild_id()
        if not support_guild_id:
            await interaction.response.send_message(
                "ยังไม่ได้ตั้งค่า `SUPPORT_GUILD_ID` หรือ `SUPPORT_HOME_GUILD_ID`",
                ephemeral=True,
            )
            return
        if int(guild.id) != int(support_guild_id):
            await interaction.response.send_message(
                f"คำสั่งนี้ใช้ได้เฉพาะใน Support Guild (`{support_guild_id}`) เท่านั้น",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        target_user_ids = {int(user.id)} if user else None
        sync_result = await self.sync_support_plan_roles(
            target_user_ids=target_user_ids,
            force=True,
            reason=f"/plan syncroles by {getattr(interaction.user, 'id', 0)}",
        )

        lines = [
            "ซิงก์ยศ Plan เรียบร้อยแล้ว",
            f"Scope: {'single-user' if user else 'all-users'}",
            f"Checked: {_safe_int(sync_result.get('checked'), 0)}",
            f"Updated: {_safe_int(sync_result.get('updated'), 0)}",
            f"Added: {_safe_int(sync_result.get('added'), 0)}",
            f"Removed: {_safe_int(sync_result.get('removed'), 0)}",
            f"Missing member: {_safe_int(sync_result.get('missing_member'), 0)}",
            f"Skipped (unmanageable role): {_safe_int(sync_result.get('skipped_unmanageable'), 0)}",
            f"Errors: {_safe_int(sync_result.get('errors'), 0)}",
        ]
        if user:
            lines.insert(1, f"User: {user.mention} (`{user.id}`)")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @plan_syncroles.error
    async def plan_syncroles_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "เกิดข้อผิดพลาดระหว่างซิงก์ยศ Plan",
                ephemeral=True,
            )
        else:
            try:
                await interaction.followup.send("เกิดข้อผิดพลาดระหว่างซิงก์ยศ Plan", ephemeral=True)
            except Exception:
                pass
        logger.error(f"Plan syncroles error: {error}")

    @verify_publish.error
    @verify_web.error
    @verify_success.error
    async def verify_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message("ต้องมีสิทธิ์ Manage Server เพื่อใช้คำสั่งนี้", ephemeral=True)
            return
        if not interaction.response.is_done():
            await interaction.response.send_message("เกิดข้อผิดพลาดในการทำงาน", ephemeral=True)
        logger.error(f"Verify command error: {error}")
