from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import storage.dashboard_config as dashboard_config_db
from skylinebot.console.logging import logger

REACTION_ROLES_CONFIG_KEY_PREFIX = "probot_reaction_roles_v1_guild_"
REACTION_ROLES_ALL_ITEMS_VALUE = "__all_items__"


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _safe_int(value: Any, default: int = 0, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _default_reaction_roles_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "selection_mode": "single",
        "items": [],
    }


def _normalize_option_row(raw_option: Any) -> dict[str, Any] | None:
    row = raw_option if isinstance(raw_option, dict) else {}
    role_id = str(row.get("role_id") or "").strip()
    if not role_id.isdigit():
        return None

    emoji_value = str(row.get("emoji") or "🎯").strip()[:64] or "🎯"
    return {
        "id": str(row.get("id") or uuid.uuid4().hex).strip()[:64] or uuid.uuid4().hex,
        "emoji": emoji_value,
        "role_id": role_id,
        "label": str(row.get("label") or "").strip()[:80],
        "description": str(row.get("description") or "").strip()[:160],
        "active": _as_bool(row.get("active"), True),
    }


def _normalize_reaction_roles_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_reaction_roles_settings()
    out["enabled"] = _as_bool(src.get("enabled"), out["enabled"])

    root_selection_mode = str(src.get("selection_mode") or out["selection_mode"]).strip().lower()
    out["selection_mode"] = root_selection_mode if root_selection_mode in {"single", "multiple"} else "single"

    raw_items = src.get("items")
    items: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for raw_item in raw_items[:100]:
            row = raw_item if isinstance(raw_item, dict) else {}
            channel_id = str(row.get("channel_id") or "").strip()
            options: list[dict[str, Any]] = []

            raw_options = row.get("options")
            if isinstance(raw_options, list):
                for raw_option in raw_options[:100]:
                    normalized_option = _normalize_option_row(raw_option)
                    if normalized_option:
                        options.append(normalized_option)

            if not options:
                legacy_option = _normalize_option_row(
                    {
                        "id": row.get("option_id") or row.get("id"),
                        "emoji": row.get("emoji"),
                        "role_id": row.get("role_id"),
                        "label": row.get("label") or row.get("title"),
                        "description": row.get("description"),
                        "active": row.get("active", True),
                    }
                )
                if legacy_option:
                    options.append(legacy_option)

            if not options:
                continue

            row_selection_mode = str(row.get("selection_mode") or out["selection_mode"]).strip().lower()
            selection_mode_value = row_selection_mode if row_selection_mode in {"single", "multiple"} else out["selection_mode"]
            max_select_value = _safe_int(
                row.get("max_select") or (1 if selection_mode_value == "single" else 2),
                1 if selection_mode_value == "single" else 2,
                minimum=1,
                maximum=25,
            )
            if selection_mode_value == "single":
                max_select_value = 1

            items.append(
                {
                    "id": str(row.get("id") or uuid.uuid4().hex).strip()[:64] or uuid.uuid4().hex,
                    "title": str(row.get("title") or "Reaction Role").strip()[:80] or "Reaction Role",
                    "description": str(row.get("description") or "").strip()[:400],
                    "channel_id": channel_id if channel_id.isdigit() else "",
                    "style": (
                        str(row.get("style") or "button").strip().lower()
                        if str(row.get("style") or "button").strip().lower() in {"button", "select"}
                        else "button"
                    ),
                    "mode": (
                        str(row.get("mode") or "toggle").strip().lower()
                        if str(row.get("mode") or "toggle").strip().lower() in {"toggle", "give", "remove"}
                        else "toggle"
                    ),
                    "selection_mode": selection_mode_value,
                    "max_select": max_select_value,
                    "options": options,
                    "active": _as_bool(row.get("active"), True),
                }
            )

    out["items"] = items
    return out


def _channel_mention(channel: Any) -> str:
    try:
        return str(getattr(channel, "mention", None) or f"`{getattr(channel, 'id', '?')}`")
    except Exception:
        return "`unknown-channel`"


class ReactionRoles(commands.Cog):
    reaction_roles_group = app_commands.Group(
        name="reaction_roles",
        description="Reaction Roles commands",
    )

    def __init__(self, bot):
        self.bot = bot
        self._settings_cache: dict[int, dict[str, Any]] = {}

    def _config_key(self, guild_id: int) -> str:
        return f"{REACTION_ROLES_CONFIG_KEY_PREFIX}{int(guild_id)}"

    @staticmethod
    def _token(raw_value: Any) -> str:
        text = str(raw_value or "").strip().lower()
        if not text:
            return "0" * 8
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]

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
            logger.error(f"ReactionRoles settings load failed ({guild_id}): {error}")
            payload = {}

        normalized = _normalize_reaction_roles_settings(payload)
        self._settings_cache[int(guild_id)] = {"ts": now, "data": normalized}
        return normalized

    @staticmethod
    def _parse_component_emoji(raw_value: Any) -> str | discord.PartialEmoji | None:
        value = str(raw_value or "").strip()
        if not value:
            return None
        try:
            parsed = discord.PartialEmoji.from_str(value)
            if parsed and (parsed.id or parsed.name):
                return parsed
        except Exception:
            pass
        if len(value) <= 64:
            return value
        return None

    @staticmethod
    def _item_options(item: dict[str, Any]) -> list[dict[str, Any]]:
        raw = item.get("options")
        if not isinstance(raw, list):
            return []
        return [option for option in raw if isinstance(option, dict) and _as_bool(option.get("active"), True)]

    def _find_item_by_token(self, settings: dict[str, Any], token: str) -> dict[str, Any] | None:
        rows = settings.get("items")
        if not isinstance(rows, list):
            return None
        for item in rows:
            if not isinstance(item, dict):
                continue
            if self._token(item.get("id")) == token:
                return item
        return None

    def _find_option_by_token(self, item: dict[str, Any], token: str) -> dict[str, Any] | None:
        for option in self._item_options(item):
            if self._token(option.get("id")) == token:
                return option
        return None

    @staticmethod
    def _active_items(settings: dict[str, Any]) -> list[dict[str, Any]]:
        rows = settings.get("items")
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict) and _as_bool(row.get("active"), True)]

    @staticmethod
    def _item_title(item: dict[str, Any], fallback_index: int = 0) -> str:
        fallback = f"Item {fallback_index}" if fallback_index > 0 else "Item"
        title = str(item.get("title") or "").strip()[:80]
        return title or fallback

    def _find_active_item_by_query(self, settings: dict[str, Any], query: str) -> dict[str, Any] | None:
        key = str(query or "").strip().lower()
        if not key or key == REACTION_ROLES_ALL_ITEMS_VALUE:
            return None

        for index, item in enumerate(self._active_items(settings), start=1):
            if self._token(item.get("id")) == key:
                return item

            item_id = str(item.get("id") or "").strip().lower()
            if item_id and item_id == key:
                return item

            title = self._item_title(item, index).strip().lower()
            if title and title == key:
                return item

        return None

    def _build_panel_embed(
        self,
        *,
        item: dict[str, Any],
        visible_options: list[dict[str, Any]],
        item_index: int,
        item_total: int,
        truncated: bool,
    ) -> discord.Embed:
        mode = str(item.get("mode") or "toggle").strip().lower()
        selection_mode = str(item.get("selection_mode") or "single").strip().lower()
        max_select = _safe_int(item.get("max_select"), 1, minimum=1, maximum=25)
        if selection_mode != "multiple":
            max_select = 1
            selection_mode = "single"

        mode_label = {
            "toggle": "Toggle (กดซ้ำเพื่อเปิด/ปิดยศ)",
            "give": "Give only (ให้ยศเท่านั้น)",
            "remove": "Remove only (ถอดยศเท่านั้น)",
        }.get(mode, "Toggle")
        select_label = "Single role" if selection_mode != "multiple" else f"Multiple roles (max {max_select})"

        description_lines: list[str] = []
        row_description = str(item.get("description") or "").strip()
        if row_description:
            description_lines.append(row_description)
            description_lines.append("")
        description_lines.append(f"Mode: **{mode_label}**")
        description_lines.append(f"Selection: **{select_label}**")
        if truncated:
            description_lines.append("")
            description_lines.append("หมายเหตุ: แสดงตัวเลือกสูงสุด 25 รายการต่อแผง")

        embed = discord.Embed(
            title=str(item.get("title") or "Reaction Role").strip()[:80] or "Reaction Role",
            description="\n".join(description_lines),
            color=discord.Color.blurple(),
        )
        preview_lines: list[str] = []
        for option in visible_options[:10]:
            emoji_text = str(option.get("emoji") or "🎯").strip() or "🎯"
            role_id = str(option.get("role_id") or "").strip()
            role_text = f"<@&{role_id}>" if role_id.isdigit() else "`unknown-role`"
            label = str(option.get("label") or "").strip()
            if label:
                preview_lines.append(f"{emoji_text} {label} -> {role_text}")
            else:
                preview_lines.append(f"{emoji_text} -> {role_text}")
        if preview_lines:
            embed.add_field(name="Mappings", value="\n".join(preview_lines), inline=False)
        embed.set_footer(text=f"Reaction Roles {item_index}/{item_total}")
        return embed

    def _build_panel_view(self, *, guild_id: int, item: dict[str, Any], options: list[dict[str, Any]]) -> discord.ui.View:
        item_token = self._token(item.get("id"))
        style = str(item.get("style") or "button").strip().lower()
        mode = str(item.get("selection_mode") or "single").strip().lower()
        max_select = _safe_int(item.get("max_select"), 1, minimum=1, maximum=25)
        if mode != "multiple":
            max_select = 1

        view = discord.ui.View(timeout=None)
        if style == "select":
            select_options: list[discord.SelectOption] = []
            for option in options:
                option_token = self._token(option.get("id"))
                label = str(option.get("label") or "").strip()[:100]
                if not label:
                    label = f"Role {str(option.get('role_id') or '-').strip()}"
                description = str(option.get("description") or "").strip()[:100] or None
                emoji = self._parse_component_emoji(option.get("emoji"))
                select_options.append(
                    discord.SelectOption(
                        label=label,
                        value=option_token,
                        description=description,
                        emoji=emoji,
                    )
                )

            select = discord.ui.Select(
                custom_id=f"rrs:{int(guild_id)}:{item_token}",
                placeholder="เลือกยศที่ต้องการรับ/ถอด",
                min_values=1,
                max_values=min(max_select, len(select_options)) if select_options else 1,
                options=select_options or [discord.SelectOption(label="No options", value="none", description="No active mappings")],
                disabled=not bool(select_options),
            )
            view.add_item(select)
            return view

        for idx, option in enumerate(options):
            option_token = self._token(option.get("id"))
            button_label = str(option.get("label") or "").strip()[:80]
            if not button_label:
                role_id = str(option.get("role_id") or "").strip()
                button_label = f"Role {role_id}" if role_id.isdigit() else "Assign role"
            emoji = self._parse_component_emoji(option.get("emoji"))
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label=button_label,
                    emoji=emoji,
                    custom_id=f"rrb:{int(guild_id)}:{item_token}:{option_token}",
                    row=min(4, idx // 5),
                )
            )
        return view

    async def _send_ephemeral(self, interaction: discord.Interaction, content: str) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content=content, ephemeral=True)
            else:
                await interaction.response.send_message(content=content, ephemeral=True)
        except Exception:
            return

    async def _resolve_publish_channel(self, guild: discord.Guild, channel_id: int) -> tuple[Any | None, str | None]:
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            channel = guild.get_thread(int(channel_id))
        if channel is None:
            channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(channel_id))
            except discord.NotFound:
                return None, f"Item target channel not found ({channel_id})"
            except discord.Forbidden:
                return None, f"Bot cannot access target channel ({channel_id})"
            except Exception as error:
                return None, f"Failed to fetch channel ({channel_id}): {error}"

        channel_guild_id = int(getattr(getattr(channel, "guild", None), "id", 0) or 0)
        if channel_guild_id and channel_guild_id != guild.id:
            return None, f"Target channel is not in this guild ({channel_id})"
        return channel, None

    @staticmethod
    def _can_send_to_channel(*, channel: Any, me: Any) -> tuple[bool, bool]:
        if not channel or me is None or not hasattr(channel, "permissions_for"):
            return True, True
        try:
            perms = channel.permissions_for(me)
        except Exception:
            return True, True

        can_view = bool(getattr(perms, "view_channel", True))
        if isinstance(channel, discord.Thread):
            can_send = bool(getattr(perms, "send_messages_in_threads", getattr(perms, "send_messages", False)))
        else:
            can_send = bool(getattr(perms, "send_messages", False))
        can_embed = bool(getattr(perms, "embed_links", True))
        return (can_view and can_send), can_embed

    async def _publish_item(
        self,
        *,
        guild: discord.Guild,
        item: dict[str, Any],
        item_index: int,
        item_total: int,
        override_channel: Any | None = None,
    ) -> tuple[bool, str]:
        options = self._item_options(item)
        if not options:
            return False, f"Item {item_index}: ไม่มี mapping ที่เปิดใช้งาน"

        visible_options = options[:25]
        truncated = len(options) > len(visible_options)

        channel: Any | None = None
        channel_id_raw = ""
        if override_channel is not None:
            channel = override_channel
            channel_id_raw = str(getattr(channel, "id", "") or "").strip()
            channel_guild_id = int(getattr(getattr(channel, "guild", None), "id", 0) or 0)
            if channel_guild_id and channel_guild_id != guild.id:
                return False, f"Item {item_index}: target channel is not in this guild ({channel_id_raw or 'unknown'})"
        else:
            channel_id_raw = str(item.get("channel_id") or "").strip()
            if not channel_id_raw.isdigit():
                return False, f"Item {item_index}: ยังไม่ได้ตั้งค่า channel"
            channel, channel_error = await self._resolve_publish_channel(guild, int(channel_id_raw))
            if channel is None:
                fallback_message = f"channel not found ({channel_id_raw})"
                return False, f"Item {item_index}: {channel_error or fallback_message}"
        if isinstance(channel, discord.ForumChannel):
            return False, f"Item {item_index}: Forum channels are not supported yet ({_channel_mention(channel)})"
        if not hasattr(channel, "send"):
            return False, f"Item {item_index}: channel type is not messageable ({_channel_mention(channel)})"

        can_send, can_embed = self._can_send_to_channel(channel=channel, me=getattr(guild, "me", None))
        if not can_send:
            return False, f"Item {item_index}: bot cannot send messages in {_channel_mention(channel)}"
        if not can_embed:
            return False, f"Item {item_index}: bot cannot embed links in {_channel_mention(channel)}"

        embed = self._build_panel_embed(
            item=item,
            visible_options=visible_options,
            item_index=item_index,
            item_total=item_total,
            truncated=truncated,
        )
        view = self._build_panel_view(guild_id=guild.id, item=item, options=visible_options)
        await channel.send(embed=embed, view=view)
        return True, f"Item {item_index}: ส่งไปที่ {_channel_mention(channel)}"

    async def _apply_role_action(
        self,
        *,
        interaction: discord.Interaction,
        guild: discord.Guild,
        member: discord.Member,
        item: dict[str, Any],
        target_options: list[dict[str, Any]],
    ) -> None:
        mode = str(item.get("mode") or "toggle").strip().lower()
        selection_mode = str(item.get("selection_mode") or "single").strip().lower()
        if selection_mode not in {"single", "multiple"}:
            selection_mode = "single"

        available_roles: dict[int, discord.Role] = {}
        for option in self._item_options(item):
            role_id = _safe_int(option.get("role_id"), 0)
            if role_id <= 0:
                continue
            role = guild.get_role(role_id)
            if role is None:
                continue
            available_roles[role_id] = role

        selected_roles: list[discord.Role] = []
        for option in target_options:
            role_id = _safe_int(option.get("role_id"), 0)
            role = available_roles.get(role_id)
            if role:
                selected_roles.append(role)
        if not selected_roles:
            await self._send_ephemeral(interaction, "ไม่พบบทบาทที่ตั้งค่าไว้ในเซิร์ฟเวอร์นี้")
            return

        me = guild.me
        if me is None:
            await self._send_ephemeral(interaction, "บอทยังไม่พร้อมทำงานในเซิร์ฟเวอร์นี้")
            return
        if not me.guild_permissions.manage_roles:
            await self._send_ephemeral(interaction, "บอทไม่มีสิทธิ์ Manage Roles")
            return

        blocked_roles = [role for role in selected_roles if role >= me.top_role]
        if blocked_roles:
            await self._send_ephemeral(interaction, "บอทไม่สามารถจัดการ role ที่สูงกว่าหรือเท่ากับ role ของบอทได้")
            return

        role_ids_in_item = set(available_roles.keys())
        member_role_ids = {role.id for role in member.roles}

        to_add: list[discord.Role] = []
        to_remove: list[discord.Role] = []

        if mode == "give":
            to_add = [role for role in selected_roles if role.id not in member_role_ids]
            if selection_mode == "single":
                to_remove = [
                    role
                    for role in available_roles.values()
                    if role.id not in {selected_roles[0].id} and role.id in member_role_ids
                ]
        elif mode == "remove":
            to_remove = [role for role in selected_roles if role.id in member_role_ids]
        else:
            # toggle
            if selection_mode == "single":
                preferred = selected_roles[0]
                if preferred.id in member_role_ids:
                    to_remove = [preferred]
                else:
                    to_add = [preferred]
                    to_remove = [
                        role
                        for role in available_roles.values()
                        if role.id != preferred.id and role.id in member_role_ids
                    ]
            else:
                for role in selected_roles:
                    if role.id in member_role_ids:
                        to_remove.append(role)
                    else:
                        to_add.append(role)

        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason=f"Reaction Roles panel ({mode})")
            if to_add:
                await member.add_roles(*to_add, reason=f"Reaction Roles panel ({mode})")
        except discord.Forbidden:
            await self._send_ephemeral(interaction, "บอทไม่มีสิทธิ์ปรับ role ให้สมาชิกนี้")
            return
        except Exception as error:
            logger.error(f"ReactionRoles apply failed in guild {guild.id}: {error}")
            await self._send_ephemeral(interaction, "เกิดข้อผิดพลาดระหว่างปรับ role")
            return

        added_text = ", ".join(role.mention for role in to_add) if to_add else "-"
        removed_text = ", ".join(role.mention for role in to_remove) if to_remove else "-"
        await self._send_ephemeral(
            interaction,
            f"อัปเดตยศเรียบร้อย\nเพิ่ม: {added_text}\nลบ: {removed_text}",
        )

    async def _handle_button_interaction(self, interaction: discord.Interaction, parts: list[str]) -> None:
        if len(parts) != 4:
            await self._send_ephemeral(interaction, "รูปแบบปุ่มไม่ถูกต้อง")
            return
        _, guild_id_raw, item_token, option_token = parts
        if not guild_id_raw.isdigit():
            await self._send_ephemeral(interaction, "ไม่พบข้อมูลเซิร์ฟเวอร์")
            return

        if not interaction.guild or int(guild_id_raw) != interaction.guild.id:
            await self._send_ephemeral(interaction, "ปุ่มนี้ไม่ใช่ของเซิร์ฟเวอร์นี้")
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            await self._send_ephemeral(interaction, "ไม่พบบัญชีสมาชิก")
            return

        settings = await self._get_settings(interaction.guild.id)
        item = self._find_item_by_token(settings, item_token)
        if not item or not _as_bool(item.get("active"), True):
            await self._send_ephemeral(interaction, "Item นี้ถูกปิดหรือไม่พบแล้ว")
            return
        option = self._find_option_by_token(item, option_token)
        if not option:
            await self._send_ephemeral(interaction, "ไม่พบ mapping ที่เลือก")
            return
        await self._apply_role_action(
            interaction=interaction,
            guild=interaction.guild,
            member=member,
            item=item,
            target_options=[option],
        )

    async def _handle_select_interaction(self, interaction: discord.Interaction, parts: list[str]) -> None:
        if len(parts) != 3:
            await self._send_ephemeral(interaction, "รูปแบบเมนูไม่ถูกต้อง")
            return
        _, guild_id_raw, item_token = parts
        if not guild_id_raw.isdigit():
            await self._send_ephemeral(interaction, "ไม่พบข้อมูลเซิร์ฟเวอร์")
            return
        if not interaction.guild or int(guild_id_raw) != interaction.guild.id:
            await self._send_ephemeral(interaction, "เมนูนี้ไม่ใช่ของเซิร์ฟเวอร์นี้")
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            await self._send_ephemeral(interaction, "ไม่พบบัญชีสมาชิก")
            return

        data = interaction.data if isinstance(interaction.data, dict) else {}
        values = data.get("values") if isinstance(data.get("values"), list) else []
        selected_tokens = [str(value or "").strip() for value in values if str(value or "").strip()]
        if not selected_tokens:
            await self._send_ephemeral(interaction, "ยังไม่ได้เลือก role")
            return

        settings = await self._get_settings(interaction.guild.id)
        item = self._find_item_by_token(settings, item_token)
        if not item or not _as_bool(item.get("active"), True):
            await self._send_ephemeral(interaction, "Item นี้ถูกปิดหรือไม่พบแล้ว")
            return

        selected_options: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()
        for token in selected_tokens:
            if token in seen_tokens:
                continue
            seen_tokens.add(token)
            option = self._find_option_by_token(item, token)
            if option:
                selected_options.append(option)
        if not selected_options:
            await self._send_ephemeral(interaction, "ไม่พบ mapping ที่เลือก")
            return

        max_select = _safe_int(item.get("max_select"), 1, minimum=1, maximum=25)
        selection_mode = str(item.get("selection_mode") or "single").strip().lower()
        if selection_mode != "multiple":
            selected_options = selected_options[:1]
        else:
            selected_options = selected_options[:max_select]

        await self._apply_role_action(
            interaction=interaction,
            guild=interaction.guild,
            member=member,
            item=item,
            target_options=selected_options,
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            if getattr(interaction, "type", None) != discord.InteractionType.component:
                return
            data = interaction.data if isinstance(interaction.data, dict) else {}
            custom_id = str(data.get("custom_id") or "").strip()
            if not custom_id:
                return
            if custom_id.startswith("rrb:"):
                await self._handle_button_interaction(interaction, custom_id.split(":"))
            elif custom_id.startswith("rrs:"):
                await self._handle_select_interaction(interaction, custom_id.split(":"))
        except Exception as error:
            logger.error(f"ReactionRoles interaction error: {error}")

    async def reaction_roles_item_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []

        settings = await self._get_settings(interaction.guild.id)
        active_items = self._active_items(settings)
        if not active_items:
            return []

        current_key = str(current or "").strip().lower()
        choices: list[app_commands.Choice[str]] = []

        all_choice = app_commands.Choice(name="All active items", value=REACTION_ROLES_ALL_ITEMS_VALUE)
        if not current_key or "all".startswith(current_key) or "active".startswith(current_key):
            choices.append(all_choice)

        for idx, row in enumerate(active_items, start=1):
            token = self._token(row.get("id"))
            title = self._item_title(row, idx)
            option_count = len(self._item_options(row))
            label = f"{idx}. {title} ({option_count} roles)"

            haystacks = {
                token.lower(),
                str(row.get("id") or "").strip().lower(),
                title.lower(),
                str(idx),
            }
            if current_key and not any(current_key in value for value in haystacks):
                continue

            choices.append(app_commands.Choice(name=label[:100], value=token))
            if len(choices) >= 25:
                break

        if choices:
            return choices[:25]
        return [all_choice]

    @reaction_roles_group.command(name="publish", description="Publish Reaction Roles panels")
    @app_commands.describe(
        item="Choose which panel to send (empty = all active panels)",
        channel="Choose destination channel (empty = each panel default channel)",
    )
    @app_commands.autocomplete(item=reaction_roles_item_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reaction_roles_publish(
        self,
        interaction: discord.Interaction,
        item: str | None = None,
        channel: discord.TextChannel | None = None,
    ):
        if not interaction.guild:
            await self._send_ephemeral(interaction, "This command can only be used in a server")
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            pass

        settings = await self._get_settings(interaction.guild.id, force=True)
        if not settings.get("enabled"):
            await self._send_ephemeral(interaction, "Reaction Roles is not enabled in dashboard")
            return

        active_items = self._active_items(settings)
        if not active_items:
            await self._send_ephemeral(interaction, "No active reaction role panels found")
            return

        item_key = str(item or "").strip()
        item_key_normalized = item_key.lower()

        selected_item: dict[str, Any] | None = None
        if item_key and item_key_normalized not in {REACTION_ROLES_ALL_ITEMS_VALUE, "all", "*"}:
            selected_item = self._find_active_item_by_query(settings, item_key)
            if selected_item is None:
                await self._send_ephemeral(interaction, "Selected item was not found or not active")
                return

        publish_items = [selected_item] if selected_item else active_items

        success_rows: list[str] = []
        error_rows: list[str] = []
        total = len(publish_items)

        for idx, row in enumerate(publish_items, start=1):
            try:
                ok, message = await self._publish_item(
                    guild=interaction.guild,
                    item=row,
                    item_index=idx,
                    item_total=total,
                    override_channel=channel,
                )
                if ok:
                    success_rows.append(message)
                else:
                    error_rows.append(message)
            except Exception as error:
                logger.error(f"ReactionRoles publish failed in guild {interaction.guild.id}: {error}")
                error_rows.append(f"Item {idx}: failed ({error})")

        lines: list[str] = []
        lines.append(f"Published {len(success_rows)}/{total} item(s)")
        if selected_item:
            lines.append(f"Selected item: {self._item_title(selected_item, 1)}")
        if channel is not None:
            lines.append(f"Target channel: {_channel_mention(channel)}")

        if success_rows:
            lines.append("")
            lines.append("Success:")
            lines.extend(f"- {row}" for row in success_rows[:10])
            if len(success_rows) > 10:
                lines.append(f"- ... and {len(success_rows) - 10} more")

        if error_rows:
            lines.append("")
            lines.append("Failed:")
            lines.extend(f"- {row}" for row in error_rows[:10])
            if len(error_rows) > 10:
                lines.append(f"- ... and {len(error_rows) - 10} more")

        await self._send_ephemeral(interaction, "\n".join(lines))

    @reaction_roles_publish.error
    async def reaction_roles_publish_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await self._send_ephemeral(interaction, "ต้องมีสิทธิ์ Manage Server เพื่อใช้คำสั่งนี้")
            return
        logger.error(f"ReactionRoles command error: {error}")
        await self._send_ephemeral(interaction, "เกิดข้อผิดพลาดระหว่างส่งแผง Reaction Roles")
