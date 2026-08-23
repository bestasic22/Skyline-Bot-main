from __future__ import annotations

import json
import random
import time
from typing import Any

import discord
from discord.ext import commands

import storage.dashboard_config as dashboard_config_db
from skylinebot.console.logging import logger


VOICE_RANDOMIZER_CONFIG_KEY_PREFIX = "probot_voice_randomizer_v1_guild_"
CATEGORY_SELECT_CUSTOM_ID = "voice_randomizer:category"
MODE_SELECT_CUSTOM_ID = "voice_randomizer:mode"
RUN_BUTTON_CUSTOM_ID = "voice_randomizer:run"
ALLOWED_ROOM_MODES = {"normal", "occupied", "empty"}


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _normalize_id_list(raw_value: Any, *, max_items: int = 25) -> list[str]:
    if isinstance(raw_value, list):
        source = raw_value
    elif isinstance(raw_value, tuple):
        source = list(raw_value)
    elif isinstance(raw_value, set):
        source = list(raw_value)
    else:
        text = str(raw_value or "").strip()
        if not text:
            source = []
        else:
            try:
                decoded = json.loads(text)
            except Exception:
                decoded = None
            if isinstance(decoded, list):
                source = decoded
            else:
                source = text.replace(" ", ",").split(",")

    out: list[str] = []
    for item in source:
        candidate = str(item or "").strip()
        if not candidate.isdigit():
            continue
        if candidate in out:
            continue
        out.append(candidate)
        if len(out) >= max_items:
            break
    return out


def _normalize_channel_id(raw_value: Any) -> str:
    text = str(raw_value or "").strip()
    return text if text.isdigit() else ""


def _normalize_color_hex(raw_value: Any, default: str = "#5865F2") -> str:
    text = str(raw_value or default).strip()
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) != 7:
        return default
    for ch in text[1:]:
        if ch not in "0123456789abcdefABCDEF":
            return default
    return text


def _default_voice_randomizer_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "panel_channel_id": "",
        "panel_message_id": "",
        "panel_message_channel_id": "",
        "allowed_category_ids": [],
        "default_category_id": "",
        "room_mode": "normal",
        "embed_title": "Voice Room Randomizer",
        "embed_description": "Pick a category and room mode, then press the button to move into a random voice room.",
        "embed_color": "#5865F2",
        "embed_footer": "",
        "embed_thumbnail_url": "",
        "embed_image_url": "",
        "category_placeholder": "Select category",
        "mode_placeholder": "Select room type",
        "button_label": "Random move me",
        "button_color": "green",
        "button_emoji": "",
    }


def _normalize_voice_randomizer_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_voice_randomizer_settings()
    out["enabled"] = _as_bool(src.get("enabled"), out["enabled"])
    out["panel_channel_id"] = _normalize_channel_id(src.get("panel_channel_id"))
    out["panel_message_id"] = _normalize_channel_id(src.get("panel_message_id"))
    out["panel_message_channel_id"] = _normalize_channel_id(src.get("panel_message_channel_id"))
    out["allowed_category_ids"] = _normalize_id_list(src.get("allowed_category_ids"), max_items=25)
    default_category_id = _normalize_channel_id(src.get("default_category_id"))
    if out["allowed_category_ids"]:
        out["default_category_id"] = (
            default_category_id
            if default_category_id in out["allowed_category_ids"]
            else out["allowed_category_ids"][0]
        )
    else:
        out["default_category_id"] = default_category_id
    room_mode = str(src.get("room_mode") or out["room_mode"]).strip().lower()
    out["room_mode"] = room_mode if room_mode in ALLOWED_ROOM_MODES else "normal"
    out["embed_title"] = str(src.get("embed_title") or out["embed_title"]).strip()[:120] or out["embed_title"]
    out["embed_description"] = str(src.get("embed_description") or out["embed_description"]).strip()[:2000]
    out["embed_color"] = _normalize_color_hex(src.get("embed_color"), out["embed_color"])
    out["embed_footer"] = str(src.get("embed_footer") or out["embed_footer"]).strip()[:200]
    out["embed_thumbnail_url"] = str(src.get("embed_thumbnail_url") or out["embed_thumbnail_url"]).strip()[:600]
    out["embed_image_url"] = str(src.get("embed_image_url") or out["embed_image_url"]).strip()[:600]
    out["category_placeholder"] = str(src.get("category_placeholder") or out["category_placeholder"]).strip()[:100] or out["category_placeholder"]
    out["mode_placeholder"] = str(src.get("mode_placeholder") or out["mode_placeholder"]).strip()[:100] or out["mode_placeholder"]
    out["button_label"] = str(src.get("button_label") or out["button_label"]).strip()[:45] or out["button_label"]
    button_color = str(src.get("button_color") or out["button_color"]).strip().lower()
    if button_color not in {"green", "blurple", "red", "gray"}:
        button_color = out["button_color"]
    out["button_color"] = button_color
    out["button_emoji"] = str(src.get("button_emoji") or out["button_emoji"]).strip()[:64] or out["button_emoji"]
    return out


class VoiceRandomizer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._settings_cache: dict[int, dict[str, Any]] = {}
        self._user_choices: dict[tuple[int, int], dict[str, Any]] = {}

    def _config_key(self, guild_id: int) -> str:
        return f"{VOICE_RANDOMIZER_CONFIG_KEY_PREFIX}{int(guild_id)}"

    @staticmethod
    def _interaction_custom_id(interaction: discord.Interaction) -> str:
        payload = interaction.data if isinstance(interaction.data, dict) else {}
        return str(payload.get("custom_id") or "").strip()

    @staticmethod
    async def _send_ephemeral(interaction: discord.Interaction, message: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message[:1900], ephemeral=True)
        else:
            await interaction.response.send_message(message[:1900], ephemeral=True)

    async def _get_settings(self, guild_id: int, *, force: bool = False) -> dict[str, Any]:
        now = time.time()
        cached = self._settings_cache.get(int(guild_id))
        if not force and cached and (now - float(cached.get("ts", 0.0))) <= 12:
            data = cached.get("data")
            if isinstance(data, dict):
                return data

        payload: dict[str, Any] = {}
        try:
            row = await dashboard_config_db.get(config_key=self._config_key(guild_id))
            raw = str((row or {}).get("config_value") or "").strip()
            if raw:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    payload = decoded
        except Exception as error:
            logger.error(f"VoiceRandomizer settings load failed ({guild_id}): {error}")
            payload = {}

        normalized = _normalize_voice_randomizer_settings(payload)
        self._settings_cache[int(guild_id)] = {"ts": now, "data": normalized}
        return normalized

    def _cleanup_user_choices(self) -> None:
        now = time.time()
        stale_keys: list[tuple[int, int]] = []
        for key, payload in self._user_choices.items():
            ts = float(payload.get("ts", 0.0) or 0.0)
            if (now - ts) > 1800:
                stale_keys.append(key)
        for key in stale_keys:
            self._user_choices.pop(key, None)
        if len(self._user_choices) > 4000:
            sorted_items = sorted(
                self._user_choices.items(),
                key=lambda item: float((item[1] or {}).get("ts", 0.0) or 0.0),
            )
            for key, _ in sorted_items[: len(self._user_choices) - 3500]:
                self._user_choices.pop(key, None)

    def _set_user_choice(
        self,
        *,
        guild_id: int,
        user_id: int,
        category_id: str | None = None,
        room_mode: str | None = None,
    ) -> None:
        self._cleanup_user_choices()
        key = (int(guild_id), int(user_id))
        current = self._user_choices.get(key, {})
        data = {
            "category_id": str(current.get("category_id") or ""),
            "room_mode": str(current.get("room_mode") or ""),
            "ts": time.time(),
        }
        if category_id is not None:
            data["category_id"] = str(category_id)
        if room_mode is not None:
            data["room_mode"] = str(room_mode)
        self._user_choices[key] = data

    def _get_user_choice(self, *, guild_id: int, user_id: int) -> dict[str, str]:
        self._cleanup_user_choices()
        payload = self._user_choices.get((int(guild_id), int(user_id)), {})
        if not isinstance(payload, dict):
            return {"category_id": "", "room_mode": ""}
        return {
            "category_id": str(payload.get("category_id") or ""),
            "room_mode": str(payload.get("room_mode") or ""),
        }

    @staticmethod
    def _mode_label(mode: str) -> str:
        if mode == "occupied":
            return "Room with users"
        if mode == "empty":
            return "Empty room"
        return "Normal room"

    @staticmethod
    def _voice_categories_for_settings(guild: discord.Guild, settings: dict[str, Any]) -> list[discord.CategoryChannel]:
        allowed = {str(item) for item in (settings.get("allowed_category_ids") or []) if str(item).isdigit()}
        channel_counts: dict[int, int] = {}
        for channel in list(getattr(guild, "voice_channels", []) or []):
            category_id = int(getattr(channel, "category_id", 0) or 0)
            if category_id <= 0:
                continue
            channel_counts[category_id] = channel_counts.get(category_id, 0) + 1

        categories: list[discord.CategoryChannel] = []
        for category in sorted(list(getattr(guild, "categories", []) or []), key=lambda c: int(getattr(c, "position", 0) or 0)):
            cid = str(int(getattr(category, "id", 0) or 0))
            if not cid or cid == "0":
                continue
            if allowed and cid not in allowed:
                continue
            if channel_counts.get(int(cid), 0) <= 0:
                continue
            categories.append(category)
        return categories

    @staticmethod
    def _filter_candidate_channels(
        *,
        member: discord.Member,
        category_id: str,
        mode: str,
    ) -> list[discord.VoiceChannel]:
        guild = member.guild
        candidates: list[discord.VoiceChannel] = []
        for channel in sorted(list(getattr(guild, "voice_channels", []) or []), key=lambda c: int(getattr(c, "position", 0) or 0)):
            if str(int(getattr(channel, "category_id", 0) or 0)) != category_id:
                continue
            permissions = channel.permissions_for(member)
            if not bool(getattr(permissions, "view_channel", False)) or not bool(getattr(permissions, "connect", False)):
                continue
            limit = int(getattr(channel, "user_limit", 0) or 0)
            if limit > 0 and member not in channel.members and len(channel.members) >= limit:
                continue
            human_members = [user for user in list(getattr(channel, "members", []) or []) if not bool(getattr(user, "bot", False))]
            if mode == "occupied" and not human_members:
                continue
            if mode == "empty" and human_members:
                continue
            candidates.append(channel)
        return candidates

    async def _handle_category_select(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._send_ephemeral(interaction, "This panel works only in a server.")
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            await self._send_ephemeral(interaction, "Unable to identify member.")
            return

        settings = await self._get_settings(interaction.guild.id)
        if not settings.get("enabled"):
            await self._send_ephemeral(interaction, "Voice randomizer is disabled.")
            return

        categories = self._voice_categories_for_settings(interaction.guild, settings)
        allowed_ids = {str(category.id) for category in categories}
        data = interaction.data if isinstance(interaction.data, dict) else {}
        values = data.get("values") if isinstance(data.get("values"), list) else []
        selected = str(values[0] or "").strip() if values else ""
        if selected not in allowed_ids:
            await self._send_ephemeral(interaction, "Selected category is not allowed.")
            return

        self._set_user_choice(
            guild_id=interaction.guild.id,
            user_id=member.id,
            category_id=selected,
            room_mode=None,
        )
        selected_category = interaction.guild.get_channel(int(selected))
        selected_name = str(getattr(selected_category, "name", "Unknown category"))
        await self._send_ephemeral(interaction, f"Selected category: **{selected_name}**")

    async def _handle_mode_select(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._send_ephemeral(interaction, "This panel works only in a server.")
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            await self._send_ephemeral(interaction, "Unable to identify member.")
            return

        settings = await self._get_settings(interaction.guild.id)
        if not settings.get("enabled"):
            await self._send_ephemeral(interaction, "Voice randomizer is disabled.")
            return

        data = interaction.data if isinstance(interaction.data, dict) else {}
        values = data.get("values") if isinstance(data.get("values"), list) else []
        selected_mode = str(values[0] or "").strip().lower() if values else ""
        if selected_mode not in ALLOWED_ROOM_MODES:
            await self._send_ephemeral(interaction, "Invalid room mode.")
            return

        self._set_user_choice(
            guild_id=interaction.guild.id,
            user_id=member.id,
            category_id=None,
            room_mode=selected_mode,
        )
        await self._send_ephemeral(interaction, f"Selected mode: **{self._mode_label(selected_mode)}**")

    async def _handle_run_button(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._send_ephemeral(interaction, "This panel works only in a server.")
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            await self._send_ephemeral(interaction, "Unable to identify member.")
            return

        settings = await self._get_settings(interaction.guild.id)
        if not settings.get("enabled"):
            await self._send_ephemeral(interaction, "Voice randomizer is disabled.")
            return

        categories = self._voice_categories_for_settings(interaction.guild, settings)
        if not categories:
            await self._send_ephemeral(interaction, "No voice categories available in current settings.")
            return

        available_category_ids = {str(category.id) for category in categories}
        choices = self._get_user_choice(guild_id=interaction.guild.id, user_id=member.id)
        selected_category_id = str(choices.get("category_id") or "").strip()
        if selected_category_id not in available_category_ids:
            selected_category_id = str(settings.get("default_category_id") or "").strip()
        if selected_category_id not in available_category_ids:
            selected_category_id = str(categories[0].id)

        selected_mode = str(choices.get("room_mode") or settings.get("room_mode") or "normal").strip().lower()
        if selected_mode not in ALLOWED_ROOM_MODES:
            selected_mode = "normal"

        candidates = self._filter_candidate_channels(
            member=member,
            category_id=selected_category_id,
            mode=selected_mode,
        )
        if not candidates:
            category_obj = interaction.guild.get_channel(int(selected_category_id))
            category_name = str(getattr(category_obj, "name", "Unknown category"))
            await self._send_ephemeral(
                interaction,
                f"No matching voice channels in **{category_name}** for mode **{self._mode_label(selected_mode)}**.",
            )
            return

        selected_channel = random.choice(candidates)
        try:
            await member.move_to(selected_channel, reason="Voice randomizer panel")
        except discord.Forbidden:
            await self._send_ephemeral(
                interaction,
                "I do not have permission to move members to that voice channel.",
            )
            return
        except discord.HTTPException as error:
            await self._send_ephemeral(interaction, f"Cannot move you right now: {str(error)[:120]}")
            return

        await self._send_ephemeral(
            interaction,
            f"Moved you to {selected_channel.mention} (`{self._mode_label(selected_mode)}`)",
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            if getattr(interaction, "type", None) != discord.InteractionType.component:
                return
            message = getattr(interaction, "message", None)
            bot_user_id = int(getattr(getattr(self.bot, "user", None), "id", 0) or 0)
            message_author_id = int(getattr(getattr(message, "author", None), "id", 0) or 0)
            if bot_user_id <= 0 or message_author_id != bot_user_id:
                return
            custom_id = self._interaction_custom_id(interaction)
            if not custom_id.startswith("voice_randomizer:"):
                return
            if custom_id == CATEGORY_SELECT_CUSTOM_ID:
                await self._handle_category_select(interaction)
            elif custom_id == MODE_SELECT_CUSTOM_ID:
                await self._handle_mode_select(interaction)
            elif custom_id == RUN_BUTTON_CUSTOM_ID:
                await self._handle_run_button(interaction)
        except Exception as error:
            logger.error(f"VoiceRandomizer interaction error: {error}")


async def setup(bot):
    await bot.add_cog(VoiceRandomizer(bot))
