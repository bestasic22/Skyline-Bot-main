from __future__ import annotations

import io
import json
import os
import re
import time
from datetime import timedelta
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.console.logging import logger
from skylinebot.src.checks import checks
from skylinebot.src.services import OpsHubService
from skylinebot.style import color
import storage.ops_hub_records as ops_hub_db
import storage.ticket_settings as ticket_settings_db

_MESSAGE_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(?P<guild>\d+)/(?P<channel>\d+)/(?P<message>\d+)",
    re.IGNORECASE,
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


class SupportTicketThreadView(discord.ui.View):
    def __init__(
        self,
        cog: "EnterpriseOps",
        *,
        guild_id: int,
        ticket_id: int,
        owner_id: int,
        claimed_by: int = 0,
        deleted: bool = False,
        closed: bool = False,
    ):
        super().__init__(timeout=7 * 24 * 60 * 60)
        self.cog = cog
        self.guild_id = int(guild_id)
        self.ticket_id = int(ticket_id)
        self.owner_id = int(owner_id)
        self.claimed_by = int(claimed_by)
        self.deleted = bool(deleted)
        self.closed = bool(closed)
        if self.deleted:
            self.closed = True

        if self.claimed_by > 0:
            self.claim_button.label = "เปลี่ยนผู้รับเคส"
            self.claim_button.style = discord.ButtonStyle.secondary

        if self.closed:
            self.claim_button.disabled = True
            self.close_button.disabled = True
            self.reopen_button.disabled = self.deleted
            self.delete_button.disabled = self.deleted
        else:
            self.reopen_button.disabled = True
            self.delete_button.disabled = False

    @discord.ui.button(label="รับเคส", style=discord.ButtonStyle.primary, emoji="🧩")
    async def claim_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.cog._support_thread_claim(interaction, self)

    @discord.ui.button(label="ข้อมูลตั๋ว", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    async def info_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.cog._support_thread_info(interaction, self)

    @discord.ui.button(label="ปิดตั๋ว", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.cog._support_thread_close(interaction, self)

    @discord.ui.button(label="เปิดใหม่", style=discord.ButtonStyle.success, emoji="🔓")
    async def reopen_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.cog._support_thread_reopen(interaction, self)

    @discord.ui.button(label="ลบตั๋ว", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.cog._support_thread_delete(interaction, self)


class SupportTicketCreateModal(discord.ui.Modal, title="เปิดตั๋วซัพพอร์ต"):
    issue = discord.ui.TextInput(
        label="รายละเอียดปัญหา",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=900,
        placeholder="อธิบายปัญหาที่ต้องการให้ทีมงานช่วย",
    )
    tag = discord.ui.TextInput(
        label="แท็ก (general/bug/billing)",
        style=discord.TextStyle.short,
        required=False,
        max_length=24,
        default="general",
    )

    def __init__(self, cog: "EnterpriseOps"):
        super().__init__(timeout=300)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog._handle_support_modal_submit(
            interaction,
            issue=str(self.issue or ""),
            tag=str(self.tag or "general"),
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "เกิดข้อผิดพลาดขณะสร้างตั๋ว กรุณาลองใหม่อีกครั้ง",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "เกิดข้อผิดพลาดขณะสร้างตั๋ว กรุณาลองใหม่อีกครั้ง",
                    ephemeral=True,
                )
        except Exception:
            pass


class SupportServerTicketCreateModal(discord.ui.Modal, title="Open Support Ticket"):
    issue = discord.ui.TextInput(
        label="Issue Details",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=900,
        placeholder="Describe your issue for the server support team",
    )
    tag = discord.ui.TextInput(
        label="Tag (general/bug/billing)",
        style=discord.TextStyle.short,
        required=False,
        max_length=24,
        default="general",
    )

    def __init__(self, cog: "EnterpriseOps"):
        super().__init__(timeout=300)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog._handle_supportserver_modal_submit(
            interaction,
            issue=str(self.issue or ""),
            tag=str(self.tag or "general"),
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "Failed to open support ticket. Please try again.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "Failed to open support ticket. Please try again.",
                    ephemeral=True,
                )
        except Exception:
            pass


class SupportServerSetupView(discord.ui.View):
    def __init__(self, cog: "EnterpriseOps", *, guild_id: int):
        super().__init__(timeout=20 * 60)
        self.cog = cog
        self.guild_id = int(guild_id)

    @discord.ui.button(label="Toggle", style=discord.ButtonStyle.secondary, emoji="🔁")
    async def toggle_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.guild is None or int(interaction.guild.id) != self.guild_id:
            return await self.cog._safe_interaction_reply(
                interaction,
                "This setup view belongs to another server.",
                ephemeral=True,
            )
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None or not (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
            or self.cog._is_ownerbot_operator(member)
        ):
            return await self.cog._safe_interaction_reply(
                interaction,
                "Only server admins can change support server settings.",
                ephemeral=True,
            )
        module = await self.cog._get_or_create_supportserver_module(self.guild_id)
        if not module:
            return await self.cog._safe_interaction_reply(
                interaction,
                "Cannot load supportserver settings.",
                ephemeral=True,
            )
        module_id = _safe_int(module.get("id"), 0)
        if module_id <= 0:
            return await self.cog._safe_interaction_reply(
                interaction,
                "Cannot load supportserver settings.",
                ephemeral=True,
            )
        new_enabled = not bool(module.get("enabled"))
        module = await ticket_settings_db.update(
            id=module_id,
            guild_id=self.guild_id,
            ticket_module_id=_safe_int(module.get("ticket_module_id"), 1),
            enabled=new_enabled,
        )
        if not module:
            module = await self.cog._get_or_create_supportserver_module(self.guild_id)
        embed = await self.cog._build_supportserver_setup_embed_with_state(interaction.guild, module or {})
        self.cog._sync_supportserver_setup_toggle(self, module or {})
        if interaction.response.is_done():
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
                view=self,
            )
        else:
            await interaction.response.edit_message(embed=embed, view=self)


class SupportDmSendConfirmView(discord.ui.View):
    def __init__(self, cog: "EnterpriseOps", *, user_id: int, request_token: str):
        super().__init__(timeout=10 * 60)
        self.cog = cog
        self.user_id = int(user_id)
        self.request_token = str(request_token or "").strip()

    async def _guard_user(self, interaction: discord.Interaction) -> bool:
        actor_id = _safe_int(getattr(getattr(interaction, "user", None), "id", 0), 0)
        if actor_id != self.user_id:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "This confirmation belongs to another user.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "This confirmation belongs to another user.",
                        ephemeral=True,
                    )
            except Exception:
                pass
            return False
        return True

    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.success, emoji="📨")
    async def send_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        await self.cog._handle_dm_support_confirm_send(
            interaction,
            self.user_id,
            self,
            request_token=self.request_token,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._guard_user(interaction):
            return
        await self.cog._handle_dm_support_confirm_cancel(
            interaction,
            self.user_id,
            self,
            request_token=self.request_token,
        )


class EnterpriseOps(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot

        class CogInfo:
            name = "EnterpriseOps"
            category = "Main"
            description = "Operational toolkit for large Discord communities"
            hidden = False
            emoji = "🧭"

        self.cog_info = CogInfo
        self.ops = OpsHubService(bot)
        self._raid_join_windows: dict[int, list[float]] = {}
        self._raid_mention_windows: dict[int, list[tuple[float, int]]] = {}
        self._supportbot_config_key = "supportbot_bridge"
        self._supportserver_extra_config_key = "supportserver_thread"
        self._dm_support_pending: dict[int, dict[str, Any]] = {}
        self._dm_support_ack_last_at: dict[int, float] = {}

    async def _require_manage_guild(self, ctx: commands.Context) -> bool:
        return await checks.check_is_moderator_permissions(ctx, "manage_guild")

    @staticmethod
    def _extract_target_ids(target: str, fallback_channel_id: int) -> tuple[int, int]:
        text = str(target or "").strip()
        if not text:
            return int(fallback_channel_id), 0

        match = _MESSAGE_LINK_RE.search(text)
        if match:
            return _safe_int(match.group("channel"), 0), _safe_int(match.group("message"), 0)

        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            return int(fallback_channel_id), _safe_int(digits, 0)
        return int(fallback_channel_id), 0

    @staticmethod
    def _parse_discord_id(value: str | int | None) -> int:
        text = str(value or "").strip()
        if not text:
            return 0
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return 0
        return _safe_int(digits, 0)

    @staticmethod
    def _account_age_days(member: discord.Member | discord.User) -> int:
        created_at = getattr(member, "created_at", None)
        if created_at is None:
            return 9999
        age = OpsHubService.now_utc() - created_at
        return max(0, int(age.total_seconds() // 86400))

    async def _get_raid_state(self, guild_id: int) -> dict[str, Any]:
        defaults = {
            "armed": False,
            "join_threshold": 6,
            "window_seconds": 20,
            "min_account_age_days": 3,
            "mention_threshold": 12,
            "lockdown_active": False,
            "trigger_count": 0,
            "triggered_at": "",
            "last_reason": "",
        }
        data = await self.ops.get_config_data(guild_id, "raid_state", defaults)
        merged = dict(defaults)
        merged.update(data or {})
        return merged

    async def _set_raid_state(self, guild_id: int, state: dict[str, Any]) -> dict[str, Any]:
        payload = dict(state or {})
        payload["updated_at"] = self.ops.now_iso()
        return await self.ops.set_config_data(guild_id, "raid_state", payload)

    async def _pick_alert_channel(self, guild: discord.Guild) -> discord.abc.Messageable | None:
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            return guild.system_channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel
        return None

    async def _trigger_raid_lockdown(self, guild: discord.Guild, reason: str, detail: str) -> None:
        state = await self._get_raid_state(guild.id)
        if not state.get("armed"):
            return
        state["lockdown_active"] = True
        state["trigger_count"] = _safe_int(state.get("trigger_count"), 0) + 1
        state["triggered_at"] = self.ops.now_iso()
        state["last_reason"] = str(reason)
        await self._set_raid_state(guild.id, state)
        await self.ops.bump_health_metric(guild.id, "raids_triggered", 1)

        channel = await self._pick_alert_channel(guild)
        if channel is not None:
            try:
                await channel.send(
                    embed=discord.Embed(
                        title="คำสั่งสำหรับใช้งานในระบบ",
                        description=f"Reason: **{reason}**\nDetail: {detail}\nUse `/raid release` when safe.",
                        color=color.red,
                    )
                )
            except Exception:
                pass

    async def _sync_trust_roles(self, member: discord.Member, profile_data: dict[str, Any], rules: dict[str, Any]) -> None:
        if not rules.get("enabled", True):
            return
        if not member.guild.me.guild_permissions.manage_roles:
            return

        silver_role_id = _safe_int(rules.get("silver_role_id"), 0)
        gold_role_id = _safe_int(rules.get("gold_role_id"), 0)
        if silver_role_id <= 0 and gold_role_id <= 0:
            return

        tier = str(profile_data.get("tier") or "new").strip().lower()
        silver_role = member.guild.get_role(silver_role_id) if silver_role_id > 0 else None
        gold_role = member.guild.get_role(gold_role_id) if gold_role_id > 0 else None

        add_list: list[discord.Role] = []
        remove_list: list[discord.Role] = []

        if tier == "gold":
            if silver_role and silver_role not in member.roles:
                add_list.append(silver_role)
            if gold_role and gold_role not in member.roles:
                add_list.append(gold_role)
        elif tier == "silver":
            if silver_role and silver_role not in member.roles:
                add_list.append(silver_role)
            if gold_role and gold_role in member.roles:
                remove_list.append(gold_role)
        else:
            if silver_role and silver_role in member.roles:
                remove_list.append(silver_role)
            if gold_role and gold_role in member.roles:
                remove_list.append(gold_role)

        for role in add_list:
            try:
                if role < member.guild.me.top_role:
                    await member.add_roles(role, reason="Trust tier sync")
            except Exception:
                pass

        for role in remove_list:
            try:
                if role < member.guild.me.top_role:
                    await member.remove_roles(role, reason="Trust tier sync")
            except Exception:
                pass

    async def _fetch_message(self, guild: discord.Guild, channel_id: int, message_id: int) -> discord.Message | None:
        if channel_id <= 0 or message_id <= 0:
            return None
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception:
                return None
        if channel is None or not hasattr(channel, "fetch_message"):
            return None
        try:
            return await channel.fetch_message(message_id)
        except Exception:
            return None

    @staticmethod
    def _is_support_staff(member: discord.abc.User | discord.Member) -> bool:
        perms = getattr(member, "guild_permissions", None)
        if perms is None:
            return False
        return bool(
            getattr(perms, "administrator", False)
            or getattr(perms, "manage_guild", False)
            or getattr(perms, "manage_messages", False)
        )

    async def _safe_ctx_defer(self, ctx: commands.Context, *, ephemeral: bool = False) -> bool:
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return False
        if interaction.response.is_done():
            return True
        try:
            await ctx.defer(ephemeral=ephemeral)
            return True
        except (discord.NotFound, discord.InteractionResponded):
            return False
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                return False
            raise

    async def _safe_ctx_send(self, ctx: commands.Context, content: str | None = None, **kwargs):
        send_kwargs = dict(kwargs)
        if getattr(ctx, "interaction", None) is None:
            send_kwargs.pop("ephemeral", None)
        try:
            if content is not None:
                return await ctx.send(content, **send_kwargs)
            return await ctx.send(**send_kwargs)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except TypeError:
            send_kwargs.pop("ephemeral", None)
            if content is not None:
                return await ctx.send(content, **send_kwargs)
            return await ctx.send(**send_kwargs)
        except discord.HTTPException as send_error:
            if getattr(send_error, "code", None) != 10062:
                raise

        channel = getattr(ctx, "channel", None)
        if channel is None:
            return None
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("ephemeral", None)
        if content is not None:
            return await channel.send(content, **fallback_kwargs)
        return await channel.send(**fallback_kwargs)

    async def _safe_interaction_reply(
        self,
        interaction: discord.Interaction,
        content: str,
        *,
        ephemeral: bool = True,
    ):
        if interaction.response.is_done():
            return await interaction.followup.send(content, ephemeral=ephemeral)
        return await interaction.response.send_message(content, ephemeral=ephemeral)

    def _default_supportbot_config(self) -> dict[str, Any]:
        support_guild_id = _safe_int(
            os.getenv("SUPPORT_GUILD_ID") or os.getenv("SUPPORT_HOME_GUILD_ID"),
            0,
        )
        return {
            "enabled": True,
            "support_guild_id": support_guild_id,
            "support_channel_id": 0,
            "archive_category_id": 0,
            "archive_channel_id": 0,
            "updated_at": self.ops.now_iso(),
        }

    async def _get_supportbot_config_for_guild(self, guild_id: int) -> dict[str, Any]:
        defaults = self._default_supportbot_config()
        payload = await self.ops.get_config_data(guild_id, self._supportbot_config_key, defaults)
        out = dict(defaults)
        out.update(payload or {})
        out["enabled"] = bool(out.get("enabled", True))
        out["support_guild_id"] = _safe_int(out.get("support_guild_id"), defaults["support_guild_id"])
        out["support_channel_id"] = _safe_int(out.get("support_channel_id"), 0)
        out["archive_category_id"] = _safe_int(out.get("archive_category_id"), 0)
        out["archive_channel_id"] = _safe_int(out.get("archive_channel_id"), 0)
        return out

    @staticmethod
    def _parse_role_id_list(value: Any) -> list[int]:
        if value is None:
            return []
        parsed: Any = value
        if isinstance(value, str):
            raw_text = value.strip()
            if not raw_text:
                return []
            if raw_text.startswith("[") and raw_text.endswith("]"):
                try:
                    parsed = json.loads(raw_text)
                except Exception:
                    parsed = []
            else:
                parsed = [item.strip() for item in raw_text.replace("\n", ",").split(",")]
        elif isinstance(value, (tuple, set)):
            parsed = list(value)
        if not isinstance(parsed, list):
            return []
        out: list[int] = []
        for item in parsed:
            role_id = _safe_int(item, 0)
            if role_id > 0 and role_id not in out:
                out.append(role_id)
        return out

    async def _get_or_create_supportserver_module(self, guild_id: int) -> dict[str, Any]:
        try:
            modules = await ticket_settings_db.gets(guild_id=int(guild_id))
        except Exception:
            modules = []
        if isinstance(modules, list):
            valid_rows = [row for row in modules if isinstance(row, dict)]
            if valid_rows:
                valid_rows.sort(key=lambda row: _safe_int(row.get("ticket_module_id"), 9999))
                return valid_rows[0]
        try:
            created = await ticket_settings_db.insert(guild_id=int(guild_id))
            if created and isinstance(created, dict):
                return created
        except Exception:
            pass
        try:
            fallback = await ticket_settings_db.get(guild_id=int(guild_id), ticket_module_id=1)
            if fallback and isinstance(fallback, dict):
                return fallback
        except Exception:
            pass
        return {}

    async def _get_supportserver_extra_config(self, guild_id: int) -> dict[str, Any]:
        defaults = {
            "archive_channel_id": 0,
            "updated_at": self.ops.now_iso(),
        }
        payload = await self.ops.get_config_data(guild_id, self._supportserver_extra_config_key, defaults)
        out = dict(defaults)
        out.update(payload or {})
        out["archive_channel_id"] = _safe_int(out.get("archive_channel_id"), 0)
        return out

    async def _set_supportserver_extra_config(self, guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        data["archive_channel_id"] = _safe_int(data.get("archive_channel_id"), 0)
        data["updated_at"] = self.ops.now_iso()
        return await self.ops.set_config_data(guild_id, self._supportserver_extra_config_key, data)

    def _is_supportserver_ticket(self, data: dict[str, Any]) -> bool:
        mode = str((data or {}).get("mode") or "").strip().lower()
        return mode == "supportserver"

    def _supportserver_staff_role_ids(self, module: dict[str, Any] | None) -> list[int]:
        if not isinstance(module, dict):
            return []
        return self._parse_role_id_list(module.get("support_roles"))

    @staticmethod
    def _member_has_any_role(member: discord.Member | None, role_ids: list[int]) -> bool:
        if member is None or not role_ids:
            return False
        member_role_ids = {_safe_int(getattr(role, "id", 0), 0) for role in list(getattr(member, "roles", []) or [])}
        for role_id in role_ids:
            if role_id > 0 and role_id in member_role_ids:
                return True
        return False

    async def _can_manage_support_ticket(
        self,
        member: discord.Member | None,
        *,
        ticket: dict[str, Any],
        data: dict[str, Any],
        action: str,
        actor_id: int,
    ) -> bool:
        if member is None:
            return False
        if self._is_support_staff(member) or self._is_ownerbot_operator(member) or self._is_adminbot_member(member):
            return True

        support_role_ids = self._parse_role_id_list(data.get("support_role_ids"))
        if not support_role_ids and self._is_supportserver_ticket(data):
            guild_id = _safe_int(ticket.get("guild_id"), 0)
            if guild_id > 0:
                module = await self._get_or_create_supportserver_module(guild_id)
                support_role_ids = self._supportserver_staff_role_ids(module)
        if self._member_has_any_role(member, support_role_ids):
            return True

        opened_by = _safe_int(data.get("opened_by"), 0)
        claimed_by = _safe_int(data.get("claimed_by"), 0)
        lowered_action = str(action or "").strip().lower()
        if lowered_action in {"close", "info"}:
            if actor_id > 0 and actor_id == opened_by:
                return True
            if actor_id > 0 and claimed_by > 0 and actor_id == claimed_by:
                return True
        return False

    async def _resolve_supportserver_hub_channel(
        self,
        guild: discord.Guild,
        module: dict[str, Any],
    ) -> tuple[discord.TextChannel | None, str | None]:
        if not bool(module.get("enabled")):
            return None, "SupportServer ticket system is disabled in this server."
        channel_id = _safe_int(module.get("ticket_panel_channel_id"), 0)
        if channel_id <= 0:
            return None, "Support thread channel is not set. Use /supportserver setup first."
        maybe_channel = guild.get_channel(channel_id)
        if not isinstance(maybe_channel, discord.TextChannel):
            return None, "Configured support thread channel was not found. Please setup again."
        me = guild.me
        if me is None:
            return None, "Bot is not ready."
        perms = maybe_channel.permissions_for(me)
        if not perms.send_messages or not perms.create_public_threads:
            return None, "Bot needs Send Messages and Create Public Threads in support channel."
        return maybe_channel, None

    async def _ensure_supportserver_hub_channel(
        self,
        guild: discord.Guild,
        module: dict[str, Any],
    ) -> tuple[dict[str, Any], discord.TextChannel | None, str | None]:
        channel_id = _safe_int(module.get("ticket_panel_channel_id"), 0)
        if channel_id > 0:
            existing = guild.get_channel(channel_id)
            if isinstance(existing, discord.TextChannel):
                return module, existing, None

        category_id = _safe_int(module.get("open_ticket_category_id"), 0)
        category = guild.get_channel(category_id) if category_id > 0 else None
        if not isinstance(category, discord.CategoryChannel):
            category = None
        target_name = "support-threads"
        for channel in guild.text_channels:
            if str(channel.name or "").strip().lower() == target_name:
                updated = await ticket_settings_db.update(
                    id=_safe_int(module.get("id"), 0),
                    guild_id=int(guild.id),
                    ticket_module_id=_safe_int(module.get("ticket_module_id"), 1),
                    ticket_panel_channel_id=int(channel.id),
                )
                return updated or module, channel, None

        if guild.me is None or not guild.me.guild_permissions.manage_channels:
            return module, None, "Bot cannot auto-create support channel (missing Manage Channels)."
        try:
            created = await guild.create_text_channel(
                name=target_name,
                category=category,
                topic=f"SupportServer thread hub for {guild.name}"[:1024],
                reason="Auto-created by /supportserver setupall"[:512],
            )
        except discord.Forbidden:
            return module, None, "Bot has no permission to create channels."
        except discord.HTTPException as create_error:
            return module, None, f"Failed to create support channel: {create_error}"

        updated = await ticket_settings_db.update(
            id=_safe_int(module.get("id"), 0),
            guild_id=int(guild.id),
            ticket_module_id=_safe_int(module.get("ticket_module_id"), 1),
            ticket_panel_channel_id=int(created.id),
        )
        return updated or module, created, None

    async def _ensure_supportserver_archive_channel(
        self,
        guild: discord.Guild,
        module: dict[str, Any],
    ) -> tuple[discord.TextChannel | None, str | None]:
        extra = await self._get_supportserver_extra_config(guild.id)
        archive_channel_id = _safe_int(extra.get("archive_channel_id"), 0)
        if archive_channel_id > 0:
            found_channel = guild.get_channel(archive_channel_id)
            if isinstance(found_channel, discord.TextChannel):
                return found_channel, None

        category_id = _safe_int(module.get("closed_ticket_category_id"), 0)
        category = guild.get_channel(category_id) if category_id > 0 else None
        if not isinstance(category, discord.CategoryChannel):
            category = None

        target_name = "supportserver-archive"
        source_channels = category.text_channels if category is not None else guild.text_channels
        for text_channel in source_channels:
            if str(text_channel.name or "").strip().lower() == target_name:
                extra["archive_channel_id"] = int(text_channel.id)
                await self._set_supportserver_extra_config(guild.id, extra)
                return text_channel, None

        if guild.me is None or not guild.me.guild_permissions.manage_channels:
            return None, "Archive channel not found and bot cannot create one (missing Manage Channels)."
        try:
            created = await guild.create_text_channel(
                name=target_name,
                category=category,
                topic=f"Archived supportserver transcripts for {guild.name}"[:1024],
                reason="Auto-created for /supportserver archive logs"[:512],
            )
        except discord.Forbidden:
            return None, "Bot has no permission to create archive channel."
        except discord.HTTPException as create_error:
            return None, f"Failed to create archive channel: {create_error}"

        extra["archive_channel_id"] = int(created.id)
        await self._set_supportserver_extra_config(guild.id, extra)
        return created, None

    def _sync_supportserver_setup_toggle(self, view: SupportServerSetupView, module: dict[str, Any]) -> None:
        enabled = bool((module or {}).get("enabled"))
        toggle = view.toggle_button
        if enabled:
            toggle.label = "Disable"
            toggle.style = discord.ButtonStyle.danger
            toggle.emoji = "⏹️"
        else:
            toggle.label = "Enable"
            toggle.style = discord.ButtonStyle.success
            toggle.emoji = "▶️"

    def _build_supportserver_setup_embed(self, guild: discord.Guild, module: dict[str, Any]) -> discord.Embed:
        enabled = bool(module.get("enabled"))
        support_roles = self._supportserver_staff_role_ids(module)
        support_roles_text = " ".join(f"<@&{role_id}>" for role_id in support_roles[:8]) if support_roles else "-"
        panel_channel_id = _safe_int(module.get("ticket_panel_channel_id"), 0)
        open_category_id = _safe_int(module.get("open_ticket_category_id"), 0)
        closed_category_id = _safe_int(module.get("closed_ticket_category_id"), 0)
        archive_channel_id = _safe_int(module.get("supportserver_archive_channel_id"), 0)

        embed = discord.Embed(
            title="คำสั่งสำหรับใช้งานในระบบ",
            description=(
                f"Status: **{'ENABLED' if enabled else 'DISABLED'}**\n"
                f"Guild: **{guild.name}** (`{guild.id}`)\n"
                f"Thread channel: {f'<#{panel_channel_id}>' if panel_channel_id > 0 else '-'}\n"
                f"Open category: {f'<#{open_category_id}>' if open_category_id > 0 else '-'}\n"
                f"Closed category: {f'<#{closed_category_id}>' if closed_category_id > 0 else '-'}\n"
                f"Archive log channel: {f'<#{archive_channel_id}>' if archive_channel_id > 0 else '-'}\n"
                f"Case roles: {support_roles_text}"
            ),
            color=color.green if enabled else color.orange,
        )
        embed.set_footer(text="Configure in dashboard tab: Tickets | open tickets with /supportserver")
        return embed

    async def _build_supportserver_setup_embed_with_state(
        self,
        guild: discord.Guild,
        module: dict[str, Any],
    ) -> discord.Embed:
        extra = await self._get_supportserver_extra_config(guild.id)
        merged = dict(module or {})
        merged["supportserver_archive_channel_id"] = _safe_int(extra.get("archive_channel_id"), 0)
        return self._build_supportserver_setup_embed(guild, merged)

    async def _resolve_support_hub_channel(
        self,
        origin_guild_id: int,
    ) -> tuple[discord.Guild | None, discord.TextChannel | None, str | None]:
        cfg = await self._get_supportbot_config_for_guild(origin_guild_id)
        if not cfg.get("enabled", True):
            return None, None, "ระบบ supportbot ถูกปิดอยู่สำหรับกิลด์นี้"

        support_guild_id = _safe_int(cfg.get("support_guild_id"), 0)
        if support_guild_id <= 0:
            return None, None, "ยังไม่ได้ตั้งค่า `support_guild_id`"
        support_guild = self.bot.get_guild(support_guild_id)
        if support_guild is None:
            return None, None, f"บอทยังไม่ได้อยู่ในกิลด์ซัพพอร์ต `{support_guild_id}`"

        channel_id = _safe_int(cfg.get("support_channel_id"), 0)
        if channel_id <= 0 and support_guild_id > 0:
            fallback_cfg = await self._get_supportbot_config_for_guild(support_guild_id)
            fallback_channel_id = _safe_int(fallback_cfg.get("support_channel_id"), 0)
            if fallback_channel_id > 0:
                channel_id = fallback_channel_id
                cfg["support_channel_id"] = int(fallback_channel_id)
                cfg["updated_at"] = self.ops.now_iso()
                try:
                    await self.ops.set_config_data(origin_guild_id, self._supportbot_config_key, cfg)
                except Exception:
                    pass
        if channel_id <= 0:
            return (
                None,
                None,
                "ยังไม่ได้ตั้งค่าห้องรับตั๋วของ SupportBot กรุณาใช้ /supportbotsetup แล้วเลือกห้องที่ต้องการ",
            )
        maybe_channel = support_guild.get_channel(channel_id)
        if not isinstance(maybe_channel, discord.TextChannel):
            return (
                None,
                None,
                f"ไม่พบห้องที่ตั้งค่าไว้ (`{channel_id}`) ในกิลด์ซัพพอร์ต กรุณาตั้งค่าใหม่ด้วย /supportbotsetup",
            )
        support_channel: discord.TextChannel = maybe_channel

        me = support_guild.me

        if me is None:
            return None, None, "Bot is not ready."
        perms = support_channel.permissions_for(me)
        if not perms.send_messages or not perms.create_public_threads:
            return None, None, "บอทไม่มีสิทธิ์ `Send Messages` หรือ `Create Public Threads` ในกิลด์ซัพพอร์ต"
        return support_guild, support_channel, None

    async def _resolve_dm_support_hub_channel(
        self,
        *,
        origin_guild_id: int = 0,
    ) -> tuple[discord.Guild | None, discord.TextChannel | None, str | None]:
        preferred_origin_guild_id = _safe_int(origin_guild_id, 0)
        if preferred_origin_guild_id > 0:
            preferred_guild, preferred_channel, preferred_error = await self._resolve_support_hub_channel(
                preferred_origin_guild_id
            )
            if preferred_guild is not None and preferred_channel is not None and not preferred_error:
                return preferred_guild, preferred_channel, None

        default_cfg = self._default_supportbot_config()
        support_guild_id = _safe_int(default_cfg.get("support_guild_id"), 0)
        if support_guild_id <= 0:
            return None, None, "SUPPORT_GUILD_ID is not configured for DM support."

        support_guild = self.bot.get_guild(support_guild_id)
        if support_guild is None:
            return None, None, f"Bot is not in support guild `{support_guild_id}`."
        me = support_guild.me
        if me is None:
            return None, None, "Bot is not ready."

        candidate_channel_ids: list[int] = []

        support_guild_cfg = await self._get_supportbot_config_for_guild(support_guild_id)
        support_guild_channel_id = _safe_int(support_guild_cfg.get("support_channel_id"), 0)
        if support_guild_channel_id > 0 and support_guild_channel_id not in candidate_channel_ids:
            candidate_channel_ids.append(support_guild_channel_id)

        try:
            config_rows = await ops_hub_db.gets(
                kind=self.ops.CONFIG_KIND,
                key=str(self._supportbot_config_key).strip().lower(),
            )
        except Exception:
            config_rows = []
        valid_rows = [row for row in (config_rows or []) if isinstance(row, dict)]
        valid_rows.sort(key=lambda row: _safe_int(row.get("id"), 0), reverse=True)
        for row in valid_rows:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            if _safe_int(data.get("support_guild_id"), 0) != support_guild_id:
                continue
            channel_id = _safe_int(data.get("support_channel_id"), 0)
            if channel_id > 0 and channel_id not in candidate_channel_ids:
                candidate_channel_ids.append(channel_id)

        env_channel_id = _safe_int(os.getenv("SUPPORT_CHANNEL_ID"), 0)
        if env_channel_id > 0 and env_channel_id not in candidate_channel_ids:
            candidate_channel_ids.append(env_channel_id)

        for channel_id in candidate_channel_ids:
            maybe_channel = support_guild.get_channel(channel_id)
            if not isinstance(maybe_channel, discord.TextChannel):
                continue
            perms = maybe_channel.permissions_for(me)
            if not perms.send_messages or not perms.create_public_threads:
                continue
            return support_guild, maybe_channel, None

        return (
            None,
            None,
            "Support channel for DM tickets is not configured or missing permissions. "
            "Please run /supportbotsetup and choose a valid support room.",
        )

    async def _auto_create_support_hub_channel(
        self,
        *,
        support_guild: discord.Guild,
        origin_guild: discord.Guild,
    ) -> tuple[discord.TextChannel | None, str | None]:
        me = support_guild.me
        if me is None:
            return None, "Bot is not ready."

        base_name = f"support-{origin_guild.id}"
        safe_name = re.sub(r"[^0-9A-Za-z-]+", "-", base_name).strip("-").lower()[:80] or "supportbot-hub"
        channel_name = safe_name
        existing_names = {str(ch.name).strip().lower() for ch in support_guild.text_channels}
        if channel_name in existing_names:
            channel_name = f"{safe_name[:70]}-{origin_guild.id % 10000}"

        topic = f"SupportBot hub for {origin_guild.name} ({origin_guild.id})"
        reason = f"Auto-created by /supportbotsetup for guild {origin_guild.id}"
        try:
            created = await support_guild.create_text_channel(
                name=channel_name,
                topic=topic[:1024],
                reason=reason[:512],
            )
        except discord.Forbidden:
            return None, "Bot does not have permission to create channels in support guild."
        except discord.HTTPException as create_error:
            return None, f"Failed to create support channel: {create_error}"

        perms = created.permissions_for(me)
        if not perms.send_messages or not perms.create_public_threads:
            return (
                None,
                "Created a channel but bot still needs Send Messages and Create Public Threads permission.",
            )
        return created, None

    @staticmethod
    def _supportbot_archive_category_name(origin_guild: discord.Guild) -> str:
        base_name = f"support-archive-{origin_guild.id}"
        safe_name = re.sub(r"[^0-9A-Za-z-]+", "-", base_name).strip("-").lower()
        return safe_name[:90] or f"support-archive-{origin_guild.id % 100000}"

    @staticmethod
    def _supportbot_archive_channel_name(origin_guild: discord.Guild) -> str:
        base_name = f"ticket-archive-{origin_guild.id}"
        safe_name = re.sub(r"[^0-9A-Za-z-]+", "-", base_name).strip("-").lower()
        return safe_name[:90] or f"ticket-archive-{origin_guild.id % 100000}"

    async def _ensure_support_archive_channel(
        self,
        *,
        origin_guild: discord.Guild,
        support_guild: discord.Guild,
        cfg: dict[str, Any],
    ) -> tuple[discord.TextChannel | None, str | None, bool]:
        me = support_guild.me
        if me is None:
            return None, "Bot is not ready.", False
        created_any = False

        archive_category_id = _safe_int(cfg.get("archive_category_id"), 0)
        archive_channel_id = _safe_int(cfg.get("archive_channel_id"), 0)

        archive_category = support_guild.get_channel(archive_category_id) if archive_category_id > 0 else None
        if not isinstance(archive_category, discord.CategoryChannel):
            archive_category = None

        archive_channel = support_guild.get_channel(archive_channel_id) if archive_channel_id > 0 else None
        if not isinstance(archive_channel, discord.TextChannel):
            archive_channel = None

        if archive_channel is not None:
            channel_perms = archive_channel.permissions_for(me)
            if channel_perms.send_messages and channel_perms.embed_links and channel_perms.attach_files:
                cfg["archive_channel_id"] = int(archive_channel.id)
                if archive_category is None:
                    category_candidate = support_guild.get_channel(_safe_int(archive_channel.category_id, 0))
                    if isinstance(category_candidate, discord.CategoryChannel):
                        archive_category = category_candidate
                if archive_category is not None:
                    cfg["archive_category_id"] = int(archive_category.id)
                return archive_channel, None, False
            archive_channel = None

        archive_category_name = self._supportbot_archive_category_name(origin_guild)
        if archive_category is None:
            for maybe_category in support_guild.categories:
                if str(maybe_category.name or "").strip().lower() == archive_category_name:
                    archive_category = maybe_category
                    break
            if archive_category is None:
                try:
                    archive_category = await support_guild.create_category(
                        name=archive_category_name,
                        reason=f"Auto-created archive category for supportbot guild {origin_guild.id}"[:512],
                    )
                    created_any = True
                except discord.Forbidden:
                    return None, "Bot does not have permission to create archive category.", False
                except discord.HTTPException as create_error:
                    return None, f"Failed to create archive category: {create_error}", False

        archive_channel_name = self._supportbot_archive_channel_name(origin_guild)
        if archive_channel is None:
            for maybe_channel in archive_category.text_channels:
                if str(maybe_channel.name or "").strip().lower() == archive_channel_name:
                    archive_channel = maybe_channel
                    break
            if archive_channel is None:
                try:
                    archive_channel = await support_guild.create_text_channel(
                        name=archive_channel_name,
                        category=archive_category,
                        topic=f"Archived support tickets for {origin_guild.name} ({origin_guild.id})"[:1024],
                        reason=f"Auto-created archive channel for supportbot guild {origin_guild.id}"[:512],
                    )
                    created_any = True
                except discord.Forbidden:
                    return None, "Bot does not have permission to create archive channel.", False
                except discord.HTTPException as create_error:
                    return None, f"Failed to create archive channel: {create_error}", False

        perms = archive_channel.permissions_for(me)
        if not perms.send_messages or not perms.embed_links or not perms.attach_files:
            return (
                None,
                "Archive channel needs Send Messages, Embed Links and Attach Files permissions for the bot.",
                False,
            )

        cfg["archive_category_id"] = int(archive_category.id)
        cfg["archive_channel_id"] = int(archive_channel.id)
        return archive_channel, None, created_any

    def _is_ownerbot_operator(self, member: discord.abc.User | discord.Member) -> bool:
        actor_id = _safe_int(getattr(member, "id", 0), 0)
        if actor_id <= 0:
            return False
        if checks.check_is_admin_predicate(member):
            return True
        owner_ids = set(getattr(self.bot, "owner_ids", set()) or set())
        if actor_id in owner_ids:
            return True
        developers = list(getattr(self.bot, "developers", []) or [])
        if any(_safe_int(getattr(dev, "id", 0), 0) == actor_id for dev in developers):
            return True
        return False

    @staticmethod
    def _is_adminbot_member(member: discord.abc.User | discord.Member) -> bool:
        if not isinstance(member, discord.Member):
            return False

        role_names: list[str] = []
        for role in list(getattr(member, "roles", []) or []):
            name = str(getattr(role, "name", "") or "").strip().lower()
            if not name:
                continue
            role_names.append(re.sub(r"[\s_-]+", "", name))
        if any("adminbot" in name for name in role_names):
            return True

        if bool(getattr(member, "bot", False)):
            perms = getattr(member, "guild_permissions", None)
            if perms is None:
                return False
            return bool(
                getattr(perms, "administrator", False)
                or getattr(perms, "manage_guild", False)
                or getattr(perms, "manage_messages", False)
            )
        return False

    @staticmethod
    def _ticket_thread_name(prefix: str, ticket_id: int, display_name: str) -> str:
        suffix = str(display_name or "user").strip().replace(" ", "-")
        safe_suffix = re.sub(r"[^0-9A-Za-zก-๙_-]+", "", suffix) or "user"
        return f"support-{prefix}-{int(ticket_id)}-{safe_suffix}"[:95]

    @staticmethod
    async def _fetch_thread(
        guild: discord.Guild | None,
        thread_id: int,
        *,
        ensure_exists: bool = False,
    ) -> discord.Thread | None:
        if guild is None or thread_id <= 0:
            return None
        cached = guild.get_channel(thread_id) or guild.get_thread(thread_id)
        if isinstance(cached, discord.Thread):
            if not ensure_exists:
                return cached
            try:
                fetched_cached = await guild.fetch_channel(thread_id)
                if isinstance(fetched_cached, discord.Thread):
                    return fetched_cached
                return None
            except discord.NotFound:
                return None
            except Exception:
                # Keep cached object on transient API failures.
                return cached
        try:
            fetched = await guild.fetch_channel(thread_id)
            if isinstance(fetched, discord.Thread):
                return fetched
        except Exception:
            return None
        return None

    async def _resolve_user(self, user_id: int) -> discord.User | None:
        if user_id <= 0:
            return None
        cached = self.bot.get_user(int(user_id))
        if cached is not None:
            return cached
        try:
            fetched = await self.bot.fetch_user(int(user_id))
            if isinstance(fetched, discord.User):
                return fetched
        except Exception:
            return None
        return None

    async def _get_open_dm_support_ticket_for_user(self, user_id: int) -> dict[str, Any] | None:
        if user_id <= 0:
            return None
        try:
            rows = await ops_hub_db.gets(kind="support_ticket", user_id=int(user_id), status="open")
        except Exception:
            rows = []
        valid_rows = [row for row in (rows or []) if isinstance(row, dict)]
        valid_rows.sort(key=lambda row: _safe_int(row.get("id"), 0), reverse=True)
        for row in valid_rows:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            if str(data.get("mode") or "").strip().lower() == "supportbot_dm":
                return row
        return None

    async def _get_latest_dm_support_ticket_for_user(self, user_id: int) -> dict[str, Any] | None:
        if user_id <= 0:
            return None
        try:
            rows = await ops_hub_db.gets(kind="support_ticket", user_id=int(user_id))
        except Exception:
            rows = []
        valid_rows = [row for row in (rows or []) if isinstance(row, dict)]
        valid_rows.sort(key=lambda row: _safe_int(row.get("id"), 0), reverse=True)
        for row in valid_rows:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            if str(data.get("mode") or "").strip().lower() == "supportbot_dm":
                return row
        return None

    def _build_issue_text_from_dm_message(self, message: discord.Message) -> str:
        body = self._truncate_text(str(message.content or "").strip(), 900)
        if not body:
            body = "[Attachment only]"
        attachments = list(message.attachments or [])
        if not attachments:
            return body
        lines = [body, "", "Attachments:"]
        for att in attachments[:5]:
            filename = self._truncate_text(str(getattr(att, "filename", "file")), 80)
            lines.append(f"- {filename}: {att.url}")
        return self._truncate_text("\n".join(lines).strip(), 900)

    async def _relay_pending_dm_issue_to_thread(
        self,
        *,
        actor: discord.abc.User,
        payload: dict[str, Any],
        support_thread: discord.Thread,
        ticket_id: int,
    ) -> bool:
        source_message_id = _safe_int(payload.get("source_message_id"), 0)
        if source_message_id <= 0:
            return False
        dm_channel = getattr(actor, "dm_channel", None)
        if dm_channel is None:
            try:
                dm_channel = await actor.create_dm()
            except Exception:
                dm_channel = None
        if dm_channel is None or not hasattr(dm_channel, "fetch_message"):
            return False
        try:
            source_message = await dm_channel.fetch_message(source_message_id)
        except Exception:
            return False
        if source_message is None:
            return False
        await self._relay_message_to_thread(
            source_message,
            support_thread,
            title=self._status_prefixed_title(
                "USER-DM",
                f"DM from {self._truncate_text(str(getattr(actor, 'display_name', getattr(actor, 'name', 'user')) or 'user'), 60)} "
                f"({getattr(actor, 'id', 0)}) | Ticket #{ticket_id}"
            ),
            source_label="Direct Message",
        )
        return True

    async def _prompt_dm_support_confirmation(self, message: discord.Message) -> bool:
        if message.guild is not None:
            return False
        if not hasattr(message.channel, "send"):
            return False
        user_id = _safe_int(getattr(message.author, "id", 0), 0)
        if user_id <= 0:
            return False

        existing_payload = self._dm_support_pending.get(user_id) if isinstance(self._dm_support_pending, dict) else None
        issue_text = self._build_issue_text_from_dm_message(message)
        request_token = f"{user_id}:{time.time_ns()}"
        pending_payload = {
            "requested_at": self.ops.now_iso(),
            "source_message_id": _safe_int(getattr(message, "id", 0), 0),
            "issue_text": issue_text,
            "tag": "general",
            "request_token": request_token,
        }

        preview = self._truncate_text(issue_text, 800)
        embed = discord.Embed(
            title="คำสั่งสำหรับใช้งานในระบบ",
            description=preview,
            color=color.orange,
        )
        embed.set_footer(text="Press Contact Support to create ticket in configured support room. Press Cancel to ignore.")
        view = SupportDmSendConfirmView(self, user_id=user_id, request_token=request_token)
        confirmation_message: discord.Message | None = None
        existing_confirmation_message_id = _safe_int(
            (existing_payload or {}).get("confirmation_message_id"),
            0,
        )
        if existing_confirmation_message_id > 0:
            try:
                existing_confirmation_message = await message.channel.fetch_message(existing_confirmation_message_id)
            except Exception:
                existing_confirmation_message = None
            if existing_confirmation_message is not None:
                try:
                    await existing_confirmation_message.edit(
                        content=None,
                        embed=embed,
                        view=view,
                    )
                    confirmation_message = existing_confirmation_message
                except Exception as edit_error:
                    logger.warning(
                        f"Support DM confirmation edit failed for user {user_id}: {edit_error}"
                    )
        try:
            if confirmation_message is None:
                confirmation_message = await message.channel.send(embed=embed, view=view)
        except Exception as send_error:
            logger.warning(
                f"Support DM confirmation send failed for user {user_id}: {send_error}"
            )
            return False
        pending_payload["confirmation_message_id"] = _safe_int(
            getattr(confirmation_message, "id", 0),
            0,
        )
        self._dm_support_pending[user_id] = pending_payload
        return True

    @staticmethod
    def _disable_view_components(view: discord.ui.View) -> discord.ui.View:
        for child in list(getattr(view, "children", []) or []):
            try:
                child.disabled = True
            except Exception:
                continue
        return view

    async def _handle_dm_support_confirm_send(
        self,
        interaction: discord.Interaction,
        user_id: int,
        view: SupportDmSendConfirmView,
        *,
        request_token: str,
    ) -> None:
        payload = self._dm_support_pending.get(int(user_id))
        if not payload:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("This confirmation has expired. Please send your message again.", ephemeral=True)
                else:
                    await interaction.response.send_message("This confirmation has expired. Please send your message again.", ephemeral=True)
            except Exception:
                pass
            return
        if str(payload.get("request_token") or "").strip() != str(request_token or "").strip():
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("This confirmation has expired. Please send your message again.", ephemeral=True)
                else:
                    await interaction.response.send_message("This confirmation has expired. Please send your message again.", ephemeral=True)
            except Exception:
                pass
            return

        actor = interaction.user
        if actor is None:
            return
        issue_text = self._truncate_text(str(payload.get("issue_text") or "").strip(), 900) or "Need support"
        normalized_tag = str(payload.get("tag") or "general").strip().lower()[:24] or "general"
        try:
            thread, ticket_id, error_message, created_ticket = await self._create_support_ticket_from_dm(
                actor=actor,
                issue_text=issue_text,
                normalized_tag=normalized_tag,
                origin_guild_id=0,
            )
        except Exception as create_error:
            logger.error(
                f"Support DM ticket create crashed for user {user_id}: {create_error}"
            )
            thread, ticket_id, error_message = None, 0, "internal error"
            created_ticket = False
        if error_message or thread is None:
            try:
                if interaction.response.is_done():
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        content=(
                            f"Failed to send to support team: {error_message or 'unknown error'}\n"
                            f"Please press **Contact Support** again."
                        ),
                    )
                else:
                    await interaction.response.edit_message(
                        content=(
                            f"Failed to send to support team: {error_message or 'unknown error'}\n"
                            f"Please press **Contact Support** again."
                        ),
                    )
            except Exception:
                pass
            return

        if not created_ticket:
            try:
                await self._relay_pending_dm_issue_to_thread(
                    actor=actor,
                    payload=payload,
                    support_thread=thread,
                    ticket_id=ticket_id,
                )
            except Exception as relay_error:
                logger.warning(
                    f"Support DM pending relay failed for user {user_id} ticket #{ticket_id}: {relay_error}"
                )

        self._dm_support_pending.pop(int(user_id), None)
        disabled_view = self._disable_view_components(view)
        try:
            if interaction.response.is_done():
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    content=f"Sent to support team. Ticket `#{ticket_id}` opened successfully.",
                    embed=None,
                    view=disabled_view,
                )
            else:
                await interaction.response.edit_message(
                    content=f"Sent to support team. Ticket `#{ticket_id}` opened successfully.",
                    embed=None,
                    view=disabled_view,
                )
        except Exception:
            pass

    async def _handle_dm_support_confirm_cancel(
        self,
        interaction: discord.Interaction,
        user_id: int,
        view: SupportDmSendConfirmView,
        *,
        request_token: str,
    ) -> None:
        payload = self._dm_support_pending.get(int(user_id))
        if payload and str(payload.get("request_token") or "").strip() == str(request_token or "").strip():
            self._dm_support_pending.pop(int(user_id), None)
        disabled_view = self._disable_view_components(view)
        try:
            if interaction.response.is_done():
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    content="Cancelled. Message was not sent to support team.",
                    embed=None,
                    view=disabled_view,
                )
            else:
                await interaction.response.edit_message(
                    content="Cancelled. Message was not sent to support team.",
                    embed=None,
                    view=disabled_view,
                )
        except Exception:
            pass

    async def _get_support_ticket_by_id(self, ticket_id: int) -> dict[str, Any] | None:
        if ticket_id <= 0:
            return None
        row = await ops_hub_db.get(id=int(ticket_id), kind="support_ticket")
        if row and isinstance(row, dict):
            return row
        return None

    async def _get_open_support_ticket_by_thread_id(self, thread_id: int) -> dict[str, Any] | None:
        if thread_id <= 0:
            return None
        try:
            rows = await ops_hub_db.gets(kind="support_ticket", status="open")
        except Exception:
            rows = []
        valid_rows = [row for row in (rows or []) if isinstance(row, dict)]
        valid_rows.sort(key=lambda row: _safe_int(row.get("id"), 0), reverse=True)
        for row in valid_rows:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            origin_thread_id = _safe_int(data.get("origin_thread_id") or data.get("thread_id"), 0)
            support_thread_id = _safe_int(data.get("support_thread_id"), 0)
            if thread_id in {origin_thread_id, support_thread_id}:
                return row
        return None

    def _build_support_panel_embed(self, ticket: dict[str, Any]) -> discord.Embed:
        data = ticket.get("data") if isinstance(ticket.get("data"), dict) else {}
        ticket_id = _safe_int(ticket.get("id"), 0)
        status = str(ticket.get("status") or "open").strip().lower()
        opened_by = _safe_int(data.get("opened_by"), 0)
        claimed_by = _safe_int(data.get("claimed_by"), 0)
        issue = str(data.get("issue") or "-")
        tag = str(data.get("tag") or "general")
        jump_url = str(data.get("source_message_url") or "").strip()
        status_title = "OPEN" if status == "open" else status.upper()
        panel_color = color.green if status == "open" else color.red
        embed = discord.Embed(
            title=f"Support Ticket #{ticket_id}",
            description=(
                f"สถานะ: **{status_title}**\n"
                f"ผู้เปิด: {f'<@{opened_by}>' if opened_by > 0 else '-'}\n"
                f"ผู้รับเคส: {f'<@{claimed_by}>' if claimed_by > 0 else 'ยังไม่มี'}\n"
                f"แท็ก: `{tag}`\n\n"
                f"ปัญหา:\n{issue[:1200]}"
            ),
            color=panel_color,
        )
        if jump_url:
            embed.add_field(name="ต้นทาง", value=f"[คลิกเพื่อดูข้อความแจ้งปัญหา]({jump_url})", inline=False)
        closed_by = _safe_int(data.get("closed_by"), 0)
        deleted_by = _safe_int(data.get("deleted_by"), 0)
        if status != "open":
            embed.add_field(
                name="ปิดโดย",
                value=(f"<@{closed_by}>" if closed_by > 0 else "-"),
                inline=True,
            )
        if status == "deleted":
            embed.add_field(
                name="Deleted By",
                value=(f"<@{deleted_by}>" if deleted_by > 0 else "-"),
                inline=True,
            )
        embed.set_footer(text="รับเคส/ปิด/เปิดใหม่/Delete ได้จากปุ่มด้านล่าง")
        return embed

    async def _sync_ticket_panels(self, ticket: dict[str, Any]) -> None:
        data = ticket.get("data") if isinstance(ticket.get("data"), dict) else {}
        opened_by = _safe_int(data.get("opened_by"), 0)
        claimed_by = _safe_int(data.get("claimed_by"), 0)
        status = str(ticket.get("status") or "open").strip().lower()
        closed = status != "open"
        deleted = status == "deleted"
        embed = self._build_support_panel_embed(ticket)

        panel_targets = [
            (
                _safe_int(ticket.get("guild_id"), 0),
                _safe_int(data.get("origin_thread_id") or data.get("thread_id"), 0),
                _safe_int(data.get("origin_panel_message_id") or data.get("panel_message_id"), 0),
            ),
            (
                _safe_int(data.get("support_guild_id"), 0),
                _safe_int(data.get("support_thread_id"), 0),
                _safe_int(data.get("support_panel_message_id"), 0),
            ),
        ]
        for guild_id, thread_id, panel_message_id in panel_targets:
            if guild_id <= 0 or thread_id <= 0 or panel_message_id <= 0:
                continue
            guild = self.bot.get_guild(guild_id)
            thread = await self._fetch_thread(guild, thread_id)
            if thread is None:
                continue
            try:
                panel_message = await thread.fetch_message(panel_message_id)
            except Exception:
                continue
            view = SupportTicketThreadView(
                self,
                guild_id=guild_id,
                ticket_id=_safe_int(ticket.get("id"), 0),
                owner_id=opened_by,
                claimed_by=claimed_by,
                deleted=deleted,
                closed=closed,
            )
            try:
                await panel_message.edit(embed=embed, view=view)
            except Exception:
                continue

    async def _support_sync_panel_message(
        self,
        interaction: discord.Interaction,
        ticket: dict[str, Any],
        view: SupportTicketThreadView,
    ) -> None:
        try:
            await self._sync_ticket_panels(ticket)
        except Exception:
            pass
        try:
            updated_view = SupportTicketThreadView(
                self,
                guild_id=view.guild_id,
                ticket_id=view.ticket_id,
                owner_id=_safe_int((ticket.get("data") or {}).get("opened_by"), 0),
                claimed_by=_safe_int((ticket.get("data") or {}).get("claimed_by"), 0),
                deleted=str(ticket.get("status") or "open").strip().lower() == "deleted",
                closed=str(ticket.get("status") or "open").strip().lower() != "open",
            )
            await interaction.message.edit(embed=self._build_support_panel_embed(ticket), view=updated_view)
        except Exception:
            pass

    async def _relay_message_to_thread(
        self,
        source_message: discord.Message,
        target_thread: discord.Thread,
        *,
        title: str,
        source_label: str,
    ) -> None:
        body_raw = str(source_message.content or "").strip()
        body = self._truncate_text(body_raw or "[Attachment only]", 3800)
        reply_quote = await self._build_reply_quote_line(source_message)
        avatar_url = str(getattr(source_message.author.display_avatar, "url", ""))
        attachments = list(source_message.attachments or [])
        embed = discord.Embed(
            title=self._truncate_text(self._one_line(title), 250) or "Support relay",
            description=body,
            color=color.blue,
            timestamp=source_message.created_at,
        )
        author_name = f"{source_message.author.display_name} ({source_message.author.id})"
        if avatar_url:
            embed.set_author(name=self._truncate_text(author_name, 250), icon_url=avatar_url)
        else:
            embed.set_author(name=self._truncate_text(author_name, 250))
        embed.set_footer(text=self._truncate_text(self._one_line(source_label), 190))

        if reply_quote:
            clean_reply = reply_quote.lstrip("> ").strip()
            embed.add_field(
                name="Reply",
                value=self._truncate_text(clean_reply or "-", 1000),
                inline=False,
            )

        if attachments:
            attachment_lines = [
                f"[{self._truncate_text(att.filename, 60)}]({att.url})"
                for att in attachments[:5]
            ]
            embed.add_field(
                name="Attachments",
                value="\n".join(attachment_lines),
                inline=False,
            )
            first_image = next(
                (
                    att.url
                    for att in attachments
                    if str(getattr(att, "content_type", "") or "").startswith("image/")
                ),
                "",
            )
            if first_image:
                embed.set_image(url=first_image)

        await target_thread.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def _relay_message_to_dm(
        self,
        source_message: discord.Message,
        target_user: discord.User,
        *,
        title: str,
        source_label: str,
    ) -> None:
        dm_channel = target_user.dm_channel
        if dm_channel is None:
            dm_channel = await target_user.create_dm()
        body_raw = str(source_message.content or "").strip()
        body = self._truncate_text(body_raw or "[Attachment only]", 3800)
        reply_quote = await self._build_reply_quote_line(source_message)
        avatar_url = str(getattr(source_message.author.display_avatar, "url", ""))
        attachments = list(source_message.attachments or [])
        embed = discord.Embed(
            title=self._truncate_text(self._one_line(title), 250) or "Support relay",
            description=body,
            color=color.blue,
            timestamp=source_message.created_at,
        )
        author_name = f"{source_message.author.display_name} ({source_message.author.id})"
        if avatar_url:
            embed.set_author(name=self._truncate_text(author_name, 250), icon_url=avatar_url)
        else:
            embed.set_author(name=self._truncate_text(author_name, 250))
        embed.set_footer(text=self._truncate_text(self._one_line(source_label), 190))

        if reply_quote:
            clean_reply = reply_quote.lstrip("> ").strip()
            embed.add_field(
                name="Reply",
                value=self._truncate_text(clean_reply or "-", 1000),
                inline=False,
            )

        if attachments:
            attachment_lines = [
                f"[{self._truncate_text(att.filename, 60)}]({att.url})"
                for att in attachments[:5]
            ]
            embed.add_field(
                name="Attachments",
                value="\n".join(attachment_lines),
                inline=False,
            )
            first_image = next(
                (
                    att.url
                    for att in attachments
                    if str(getattr(att, "content_type", "") or "").startswith("image/")
                ),
                "",
            )
            if first_image:
                embed.set_image(url=first_image)

        await dm_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def _notify_dm_ticket_user_status(
        self,
        *,
        row: dict[str, Any],
        data: dict[str, Any],
        status_code: str,
        description: str,
        color_value: discord.Colour,
    ) -> bool:
        mode = str(data.get("mode") or "supportbot").strip().lower()
        if mode != "supportbot_dm":
            return False
        target_user_id = _safe_int(data.get("opened_by") or row.get("user_id"), 0)
        if target_user_id <= 0:
            return False
        target_user = await self._resolve_user(target_user_id)
        if target_user is None:
            return False
        ticket_id = _safe_int(row.get("id"), 0)
        try:
            dm_channel = target_user.dm_channel or await target_user.create_dm()
            await dm_channel.send(
                embed=discord.Embed(
                    title=self._status_prefixed_title(status_code, f"Ticket #{ticket_id}"),
                    description=self._truncate_text(str(description or "").strip(), 1400),
                    color=color_value,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return True
        except Exception as notify_error:
            logger.warning(
                f"DM ticket status notify failed user={target_user_id} ticket={ticket_id}: {notify_error}"
            )
            return False

    @staticmethod
    def _truncate_text(text: str, limit: int) -> str:
        value = str(text or "").strip()
        if len(value) <= max(0, int(limit)):
            return value
        safe_limit = max(3, int(limit))
        return value[: safe_limit - 3].rstrip() + "..."

    @staticmethod
    def _one_line(text: str) -> str:
        return str(text or '').replace('\r', ' ').replace('\n', ' ').strip()

    @staticmethod
    def _status_prefixed_title(status: str, title: str) -> str:
        status_code = re.sub(r"[^A-Za-z0-9_-]+", "", str(status or "").upper()) or "INFO"
        normalized_title = str(title or "").strip()
        if not normalized_title:
            return f"[{status_code}]"
        return f"[{status_code}] {normalized_title}"

    async def _build_reply_quote_line(self, source_message: discord.Message) -> str:
        reference = source_message.reference
        if reference is None or reference.message_id is None:
            return ""
        replied_message = reference.resolved if isinstance(reference.resolved, discord.Message) else None
        if replied_message is None:
            try:
                replied_message = await source_message.channel.fetch_message(reference.message_id)
            except Exception:
                replied_message = None
        if replied_message is None:
            return f"> Reply to message `{reference.message_id}`"
        reply_author = getattr(replied_message.author, "display_name", "unknown")
        reply_text = self._truncate_text(self._one_line(getattr(replied_message, "content", "")), 180) or "[no text]"
        return f"> Reply to **{reply_author}**: {reply_text}"

    async def _build_thread_transcript_lines(
        self,
        thread: discord.Thread,
        *,
        section_title: str,
        limit: int = 400,
    ) -> list[str]:
        lines = [
            f"=== {section_title} ===",
            f"Guild: {thread.guild.name} ({thread.guild.id})",
            f"Thread: {thread.name} ({thread.id})",
            "",
        ]
        try:
            messages = [msg async for msg in thread.history(limit=max(50, int(limit)), oldest_first=True)]
        except Exception as fetch_error:
            lines.append(f"[failed to fetch messages: {fetch_error}]")
            lines.append("")
            return lines

        if not messages:
            lines.append("[no messages]")
            lines.append("")
            return lines

        for message in messages:
            timestamp_text = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            author_text = f"{message.author.display_name} ({message.author.id})"
            text_body = self._truncate_text(self._one_line(message.content), 1300) or "[no text]"
            transcript_line = f"[{timestamp_text}] {author_text}: {text_body}"
            reply_id = _safe_int(getattr(getattr(message, "reference", None), "message_id", 0), 0)
            if reply_id > 0:
                transcript_line = f"{transcript_line} [reply_to:{reply_id}]"
            lines.append(transcript_line)

            attachments = list(message.attachments or [])
            if attachments:
                attachment_text = ", ".join(str(item.url) for item in attachments[:5])
                lines.append(f"  attachments: {attachment_text}")
        lines.append("")
        return lines

    async def _post_ownerbot_close_transcript(
        self,
        *,
        ticket: dict[str, Any],
        data: dict[str, Any],
        closed_by: int,
        origin_thread: discord.Thread | None,
        support_thread: discord.Thread | None,
    ) -> bool:
        if origin_thread is None and support_thread is None:
            return False
        ticket_id = _safe_int(ticket.get("id"), 0)
        transcript_lines = [
            f"Ticket #{ticket_id} Transcript",
            f"Closed by: {closed_by}",
            f"Closed at: {self.ops.now_iso()}",
            "",
        ]

        if origin_thread is not None:
            transcript_lines.extend(
                await self._build_thread_transcript_lines(
                    origin_thread,
                    section_title="Origin Ticket Thread",
                )
            )
        if support_thread is not None and (origin_thread is None or support_thread.id != origin_thread.id):
            transcript_lines.extend(
                await self._build_thread_transcript_lines(
                    support_thread,
                    section_title="OwnerBOT Support Thread",
                )
            )

        transcript_payload = ("\n".join(transcript_lines).strip() + "\n").encode("utf-8", errors="replace")
        file_obj = discord.File(
            io.BytesIO(transcript_payload),
            filename=f"support-ticket-{ticket_id}-transcript.txt",
        )
        target_thread = support_thread or origin_thread
        if target_thread is None:
            return False
        try:
            transcript_message = await target_thread.send(
                content=f"Transcript log for ticket #{ticket_id} (closed by user {closed_by})",
                file=file_obj,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception:
            return False

        data["ownerbot_transcript_message_id"] = int(transcript_message.id)
        data["ownerbot_transcript_thread_id"] = int(target_thread.id)
        data["ownerbot_transcript_at"] = self.ops.now_iso()
        return True

    async def _post_support_ticket_deleted_archive(
        self,
        *,
        ticket: dict[str, Any],
        data: dict[str, Any],
        deleted_by: int,
        origin_thread: discord.Thread | None,
        support_thread: discord.Thread | None,
    ) -> bool:
        origin_guild_id = _safe_int(ticket.get("guild_id"), 0)
        if origin_guild_id <= 0:
            return False
        origin_guild = self.bot.get_guild(origin_guild_id)
        if origin_guild is None:
            return False

        mode = str(data.get("mode") or "supportbot").strip().lower()
        archive_channel: discord.TextChannel | None = None
        archive_error: str | None = None

        if mode == "supportserver":
            module = await self._get_or_create_supportserver_module(origin_guild_id)
            archive_channel, archive_error = await self._ensure_supportserver_archive_channel(origin_guild, module)
        else:
            support_guild = self.bot.get_guild(_safe_int(data.get("support_guild_id"), 0))
            if support_guild is None:
                return False
            cfg = await self._get_supportbot_config_for_guild(origin_guild_id)
            archive_channel, archive_error, _ = await self._ensure_support_archive_channel(
                origin_guild=origin_guild,
                support_guild=support_guild,
                cfg=cfg,
            )
            if archive_channel is not None:
                cfg["updated_at"] = self.ops.now_iso()
                await self.ops.set_config_data(origin_guild_id, self._supportbot_config_key, cfg)

        if archive_channel is None:
            if archive_error:
                data["delete_archive_error"] = self._truncate_text(archive_error, 500)
            return False

        ticket_id = _safe_int(ticket.get("id"), 0)
        opened_by = _safe_int(data.get("opened_by"), 0)
        claimed_by = _safe_int(data.get("claimed_by"), 0)
        issue = self._truncate_text(str(data.get("issue") or "-"), 900)
        deleted_at = self.ops.now_iso()

        transcript_lines = [
            f"Ticket #{ticket_id} Deleted Archive",
            f"Deleted by: {deleted_by}",
            f"Deleted at: {deleted_at}",
            "",
        ]
        if origin_thread is not None:
            transcript_lines.extend(
                await self._build_thread_transcript_lines(
                    origin_thread,
                    section_title="Origin Ticket Thread",
                )
            )
        if support_thread is not None and (origin_thread is None or support_thread.id != origin_thread.id):
            transcript_lines.extend(
                await self._build_thread_transcript_lines(
                    support_thread,
                    section_title="OwnerBOT Support Thread",
                )
            )

        transcript_payload = ("\n".join(transcript_lines).strip() + "\n").encode("utf-8", errors="replace")
        transcript_file = discord.File(
            io.BytesIO(transcript_payload),
            filename=f"support-ticket-{ticket_id}-deleted-transcript.txt",
        )

        archive_title = f"Deleted Support Ticket #{ticket_id}"
        if mode == "supportserver":
            archive_title = f"Deleted SupportServer Ticket #{ticket_id}"
        archive_embed = discord.Embed(
            title=archive_title,
            description=(
                f"Origin Guild: **{origin_guild.name}** (`{origin_guild.id}`)\n"
                f"Deleted by: <@{deleted_by}> (`{deleted_by}`)\n"
                f"Opened by: {f'<@{opened_by}>' if opened_by > 0 else '-'}\n"
                f"Claimed by: {f'<@{claimed_by}>' if claimed_by > 0 else '-'}\n"
                f"Deleted at: `{deleted_at}`"
            ),
            color=color.red,
        )
        archive_embed.add_field(name="Issue", value=issue, inline=False)

        try:
            archive_message = await archive_channel.send(
                embed=archive_embed,
                file=transcript_file,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception as archive_error_obj:
            data["delete_archive_error"] = self._truncate_text(str(archive_error_obj), 500)
            return False

        data.pop("delete_archive_error", None)
        data["delete_archive_message_id"] = int(archive_message.id)
        data["delete_archive_channel_id"] = int(archive_channel.id)
        data["delete_archive_at"] = deleted_at
        return True

    async def _relay_support_thread_message(self, message: discord.Message) -> bool:
        if not isinstance(message.channel, discord.Thread):
            return False
        lowered_name = str(message.channel.name or "").strip().lower()
        matched = re.search(r"support-(?:origin|owner)-(?P<ticket>\d+)", lowered_name)
        ticket = None
        if matched:
            ticket_id = _safe_int(matched.group("ticket"), 0)
            ticket = await self._get_support_ticket_by_id(ticket_id)
        if not ticket:
            ticket = await self._get_open_support_ticket_by_thread_id(_safe_int(getattr(message.channel, "id", 0), 0))
        if not ticket:
            return False
        ticket_id = _safe_int(ticket.get("id"), 0)
        data = ticket.get("data") if isinstance(ticket.get("data"), dict) else {}
        mode = str(data.get("mode") or "supportbot").strip().lower()
        origin_thread_id = _safe_int(data.get("origin_thread_id"), 0)
        support_thread_id = _safe_int(data.get("support_thread_id"), 0)
        legacy_thread_id = _safe_int(data.get("thread_id"), 0)
        if origin_thread_id <= 0 and support_thread_id <= 0 and legacy_thread_id > 0:
            origin_thread_id = legacy_thread_id
        if support_thread_id <= 0 and legacy_thread_id > 0:
            support_thread_id = legacy_thread_id
        valid_thread_ids = {thread_id for thread_id in {origin_thread_id, support_thread_id} if thread_id > 0}
        if message.channel.id not in valid_thread_ids:
            return False

        status = str(ticket.get("status") or "open").strip().lower()
        if status != "open":
            return True

        origin_guild = self.bot.get_guild(_safe_int(ticket.get("guild_id"), 0))
        support_guild = self.bot.get_guild(_safe_int(data.get("support_guild_id"), 0))
        origin_thread = await self._fetch_thread(origin_guild, origin_thread_id) if origin_thread_id > 0 else None
        support_thread = await self._fetch_thread(support_guild, support_thread_id) if support_thread_id > 0 else None

        if origin_thread_id > 0 and message.channel.id == origin_thread_id:
            if support_thread is None:
                return True
            await self._relay_message_to_thread(
                message,
                support_thread,
                title=f"ข้อความจากผู้ใช้ Ticket #{ticket_id}",
                source_label=f"{message.guild.name} / {message.channel.name}",
            )
            return True

        member = message.author if isinstance(message.author, discord.Member) else None
        can_reply = bool(
            member
            and (
                self._is_ownerbot_operator(member)
                or self._is_support_staff(member)
                or self._is_adminbot_member(member)
            )
        )
        if (
            not can_reply
            and mode == "supportbot_dm"
            and support_thread_id > 0
            and message.channel.id == support_thread_id
        ):
            can_reply = True
        if not can_reply:
            return False
        if origin_thread is None:
            if mode == "supportbot_dm":
                target_user = await self._resolve_user(_safe_int(data.get("opened_by") or ticket.get("user_id"), 0))
                if target_user is not None:
                    await self._relay_message_to_dm(
                        message,
                        target_user,
                        title=self._status_prefixed_title("STAFF-REPLY", f"OwnerBOT reply Ticket #{ticket_id}"),
                        source_label=f"{message.guild.name} / {message.channel.name}",
                    )
            return True
        await self._relay_message_to_thread(
            message,
            origin_thread,
            title=f"ตอบกลับจาก OwnerBOT Ticket #{ticket_id}",
            source_label=f"{message.guild.name} / {message.channel.name}",
        )
        return True

    async def _relay_dm_support_message(self, message: discord.Message) -> bool:
        if message.guild is not None:
            return False
        if not isinstance(message.channel, discord.DMChannel):
            return False

        ticket = await self._get_open_dm_support_ticket_for_user(_safe_int(getattr(message.author, "id", 0), 0))
        if not ticket:
            return False
        if str(ticket.get("status") or "").strip().lower() != "open":
            return True

        data = ticket.get("data") if isinstance(ticket.get("data"), dict) else {}
        support_guild = self.bot.get_guild(_safe_int(data.get("support_guild_id"), 0))
        support_thread = await self._fetch_thread(
            support_guild,
            _safe_int(data.get("support_thread_id"), 0),
            ensure_exists=True,
        )
        if support_thread is None:
            ticket_data = dict(data)
            ticket_data["closed_at"] = self.ops.now_iso()
            ticket_data["auto_closed_reason"] = "stale_dm_ticket_thread_missing"
            try:
                await self.ops.update_record(
                    _safe_int(ticket.get("id"), 0),
                    status="closed",
                    data=ticket_data,
                    actor_id=_safe_int(getattr(message.author, "id", 0), 0),
                )
            except Exception:
                pass
            return False
        expected_channel_id = _safe_int(data.get("support_channel_id"), 0)
        if expected_channel_id > 0:
            parent_channel_id = _safe_int(getattr(support_thread, "parent_id", 0), 0)
            if parent_channel_id > 0 and parent_channel_id != expected_channel_id:
                ticket_data = dict(data)
                ticket_data["closed_at"] = self.ops.now_iso()
                ticket_data["auto_closed_reason"] = "stale_dm_ticket_parent_mismatch"
                try:
                    await self.ops.update_record(
                        _safe_int(ticket.get("id"), 0),
                        status="closed",
                        data=ticket_data,
                        actor_id=_safe_int(getattr(message.author, "id", 0), 0),
                    )
                except Exception:
                    pass
                return False

        if bool(getattr(support_thread, "archived", False)) or bool(getattr(support_thread, "locked", False)):
            try:
                await support_thread.edit(
                    archived=False,
                    locked=False,
                    reason=f"Resume DM support thread for user {_safe_int(getattr(message.author, 'id', 0), 0)}",
                )
            except Exception:
                # Keep going and attempt to send anyway.
                pass

        try:
            await self._relay_message_to_thread(
                message,
                support_thread,
                title=self._status_prefixed_title(
                    "USER-DM",
                    f"DM from {self._truncate_text(str(getattr(message.author, 'display_name', getattr(message.author, 'name', 'user')) or 'user'), 60)} "
                    f"({message.author.id}) | Ticket #{_safe_int(ticket.get('id'), 0)}"
                ),
                source_label="Direct Message",
            )
        except Exception as relay_error:
            logger.warning(
                f"Support DM relay send failed for user {_safe_int(getattr(message.author, 'id', 0), 0)}: {relay_error}"
            )
            # Ticket is still open; avoid forcing user to press Contact Support again on transient send failures.
            try:
                await message.channel.send("ระบบซัพพอร์ตกำลังหน่วงเล็กน้อย กรุณาลองส่งอีกครั้งในอีกสักครู่")
            except Exception:
                pass
            return True

        author_id = _safe_int(getattr(message.author, "id", 0), 0)
        if author_id > 0:
            now_ts = time.time()
            last_ack_at = float(self._dm_support_ack_last_at.get(author_id, 0.0))
            if (now_ts - last_ack_at) >= 3.0:
                try:
                    await message.channel.send("ส่งข้อความถึงทีมซัพพอร์ตแล้ว")
                    self._dm_support_ack_last_at[author_id] = now_ts
                except Exception:
                    pass
        return True

    async def _create_support_ticket(
        self,
        *,
        guild: discord.Guild,
        actor: discord.Member,
        base_channel: discord.TextChannel,
        issue_text: str,
        normalized_tag: str,
    ) -> tuple[discord.Thread | None, int, str | None]:
        me = guild.me
        if me is None:
            return None, 0, "Bot is not ready."
        perms = base_channel.permissions_for(me)
        if not perms.send_messages or not perms.create_public_threads:
            return None, 0, "บอทยังไม่มีสิทธิ์ `Send Messages` หรือ `Create Public Threads` ในช่องนี้"

        support_guild, support_channel, support_error = await self._resolve_support_hub_channel(guild.id)
        if support_error:
            return None, 0, support_error
        if support_guild is None or support_channel is None:
            return None, 0, "ไม่พบปลายทางกิลด์ซัพพอร์ต"

        created_at = self.ops.now_iso()
        ticket_record = await self.ops.create_record(
            guild_id=guild.id,
            kind="support_ticket",
            status="open",
            actor_id=actor.id,
            user_id=actor.id,
            data={
                "opened_at": created_at,
                "issue": issue_text,
                "tag": normalized_tag,
                "opened_by": int(actor.id),
                "claimed_by": 0,
                "claimed_at": "",
                "source_message_url": "",
                "channel_id": int(base_channel.id),
                "message_id": 0,
                "thread_id": 0,
                "origin_channel_id": int(base_channel.id),
                "origin_message_id": 0,
                "origin_thread_id": 0,
                "origin_panel_message_id": 0,
                "support_guild_id": int(support_guild.id),
                "support_channel_id": int(support_channel.id),
                "support_message_id": 0,
                "support_thread_id": 0,
                "support_panel_message_id": 0,
            },
        )
        ticket_id = _safe_int(ticket_record.get("id"), 0)
        if ticket_id <= 0:
            return None, 0, "สร้างตั๋วไม่สำเร็จ กรุณาลองใหม่อีกครั้ง"

        origin_embed = discord.Embed(
            title=f"Support Ticket #{ticket_id}",
            description=f"ผู้เปิด: {actor.mention}\nแท็ก: `{normalized_tag}`\n\n{issue_text}",
            color=color.blue,
        )
        origin_message = await base_channel.send(embed=origin_embed)
        origin_thread = await origin_message.create_thread(
            name=self._ticket_thread_name("origin", ticket_id, actor.display_name)
        )

        support_embed = discord.Embed(
            title=self._status_prefixed_title("OPEN", f"Incoming Support Ticket #{ticket_id}"),
            description=(
                f"Guild: **{guild.name}** (`{guild.id}`)\n"
                f"User: {actor.mention} (`{actor.id}`)\n"
                f"Tag: `{normalized_tag}`\n\n"
                f"{issue_text}"
            ),
            color=color.orange,
        )
        support_message = await support_channel.send(embed=support_embed)
        support_thread = await support_message.create_thread(
            name=self._ticket_thread_name("owner", ticket_id, actor.display_name)
        )

        ticket_data = ticket_record.get("data") if isinstance(ticket_record.get("data"), dict) else {}
        ticket_data.update(
            {
                "source_message_url": str(origin_message.jump_url),
                "message_id": int(origin_message.id),
                "thread_id": int(origin_thread.id),
                "origin_message_id": int(origin_message.id),
                "origin_thread_id": int(origin_thread.id),
                "support_message_id": int(support_message.id),
                "support_thread_id": int(support_thread.id),
            }
        )
        await self.ops.update_record(ticket_id, data=ticket_data, actor_id=actor.id)
        ticket_record["data"] = ticket_data

        case_record = await self.ops.create_record(
            guild_id=guild.id,
            kind="case",
            status="open",
            actor_id=actor.id,
            user_id=actor.id,
            reference_id=ticket_id,
            data={
                "title": f"Support ticket #{ticket_id}",
                "opened_at": created_at,
                "source": "supportbot",
                "thread_id": int(origin_thread.id),
                "support_thread_id": int(support_thread.id),
                "support_ticket_id": ticket_id,
            },
        )
        ticket_data["case_id"] = _safe_int(case_record.get("id"), 0)

        origin_view = SupportTicketThreadView(
            self,
            guild_id=guild.id,
            ticket_id=ticket_id,
            owner_id=actor.id,
            claimed_by=0,
            closed=False,
        )
        origin_panel = await origin_thread.send(
            content=f"{actor.mention} ทีมงานจะเข้ามาดูแลในเธรดนี้",
            embed=self._build_support_panel_embed(ticket_record),
            view=origin_view,
        )

        support_view = SupportTicketThreadView(
            self,
            guild_id=support_guild.id,
            ticket_id=ticket_id,
            owner_id=actor.id,
            claimed_by=0,
            closed=False,
        )
        support_panel = await support_thread.send(
            content=(
                "เธรดนี้เชื่อมต่อกับผู้ใช้แล้ว ทีม OwnerBOT สามารถพิมพ์ตอบกลับได้ตามปกติ "
                "ข้อความจะถูกส่งกลับไปยังเธรดของผู้ใช้อัตโนมัติ"
            ),
            embed=self._build_support_panel_embed(ticket_record),
            view=support_view,
        )

        ticket_data["panel_message_id"] = int(origin_panel.id)
        ticket_data["origin_panel_message_id"] = int(origin_panel.id)
        ticket_data["support_panel_message_id"] = int(support_panel.id)
        await self.ops.update_record(ticket_id, data=ticket_data, actor_id=actor.id)
        await self.ops.bump_health_metric(guild.id, "support_opened", 1)
        await self.ops.bump_health_metric(guild.id, "cases_opened", 1)
        return origin_thread, ticket_id, None

    async def _create_supportserver_ticket(
        self,
        *,
        guild: discord.Guild,
        actor: discord.Member,
        issue_text: str,
        normalized_tag: str,
    ) -> tuple[discord.Thread | None, int, str | None, bool]:
        module = await self._get_or_create_supportserver_module(guild.id)
        if not module:
            return None, 0, "SupportServer settings are unavailable."
        base_channel, channel_error = await self._resolve_supportserver_hub_channel(guild, module)
        if channel_error:
            return None, 0, channel_error
        if base_channel is None:
            return None, 0, "Support thread channel is not available."

        me = guild.me
        if me is None:
            return None, 0, "Bot is not ready."
        perms = base_channel.permissions_for(me)
        if not perms.send_messages or not perms.create_public_threads:
            return None, 0, "Bot needs Send Messages and Create Public Threads in support channel."

        support_role_ids = self._supportserver_staff_role_ids(module)
        created_at = self.ops.now_iso()
        ticket_record = await self.ops.create_record(
            guild_id=guild.id,
            kind="support_ticket",
            status="open",
            actor_id=actor.id,
            user_id=actor.id,
            data={
                "mode": "supportserver",
                "opened_at": created_at,
                "issue": issue_text,
                "tag": normalized_tag,
                "opened_by": int(actor.id),
                "claimed_by": 0,
                "claimed_at": "",
                "source_message_url": "",
                "channel_id": int(base_channel.id),
                "message_id": 0,
                "thread_id": 0,
                "origin_channel_id": int(base_channel.id),
                "origin_message_id": 0,
                "origin_thread_id": 0,
                "origin_panel_message_id": 0,
                "support_guild_id": int(guild.id),
                "support_channel_id": int(base_channel.id),
                "support_message_id": 0,
                "support_thread_id": 0,
                "support_panel_message_id": 0,
                "support_role_ids": support_role_ids,
            },
        )
        ticket_id = _safe_int(ticket_record.get("id"), 0)
        if ticket_id <= 0:
            return None, 0, "Failed to create support ticket record."

        root_embed = discord.Embed(
            title=self._status_prefixed_title("OPEN", f"Incoming Support Ticket #{ticket_id}"),
            description=(
                f"User: {actor.mention} (`{actor.id}`)\n"
                f"Tag: `{normalized_tag}`\n\n"
                f"{issue_text}"
            ),
            color=color.orange,
        )
        root_message = await base_channel.send(embed=root_embed, allowed_mentions=discord.AllowedMentions.none())
        thread = await root_message.create_thread(
            name=self._ticket_thread_name("server", ticket_id, actor.display_name)
        )

        ticket_data = ticket_record.get("data") if isinstance(ticket_record.get("data"), dict) else {}
        ticket_data.update(
            {
                "source_message_url": str(root_message.jump_url),
                "message_id": int(root_message.id),
                "thread_id": int(thread.id),
                "origin_message_id": int(root_message.id),
                "origin_thread_id": int(thread.id),
            }
        )
        await self.ops.update_record(ticket_id, data=ticket_data, actor_id=actor.id)
        ticket_record["data"] = ticket_data

        case_record = await self.ops.create_record(
            guild_id=guild.id,
            kind="case",
            status="open",
            actor_id=actor.id,
            user_id=actor.id,
            reference_id=ticket_id,
            data={
                "title": f"SupportServer ticket #{ticket_id}",
                "opened_at": created_at,
                "source": "supportserver",
                "thread_id": int(thread.id),
                "support_ticket_id": ticket_id,
            },
        )
        ticket_data["case_id"] = _safe_int(case_record.get("id"), 0)

        view = SupportTicketThreadView(
            self,
            guild_id=guild.id,
            ticket_id=ticket_id,
            owner_id=actor.id,
            claimed_by=0,
            closed=False,
        )
        role_mentions = " ".join(f"<@&{role_id}>" for role_id in support_role_ids[:8])
        mention_parts = [actor.mention]
        if role_mentions:
            mention_parts.append(role_mentions)
        mention_line = " ".join(mention_parts)

        panel_message = await thread.send(
            content=mention_line,
            embed=self._build_support_panel_embed(ticket_record),
            view=view,
            allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
        )
        ticket_data["panel_message_id"] = int(panel_message.id)
        ticket_data["origin_panel_message_id"] = int(panel_message.id)
        await self.ops.update_record(ticket_id, data=ticket_data, actor_id=actor.id)
        await self.ops.bump_health_metric(guild.id, "support_opened", 1)
        await self.ops.bump_health_metric(guild.id, "cases_opened", 1)
        return thread, ticket_id, None

    async def _create_support_ticket_from_dm(
        self,
        *,
        actor: discord.abc.User,
        issue_text: str,
        normalized_tag: str,
        origin_guild_id: int = 0,
    ) -> tuple[discord.Thread | None, int, str | None, bool]:
        actor_id = _safe_int(getattr(actor, "id", 0), 0)
        if actor_id <= 0:
            return None, 0, "Cannot identify ticket owner.", False

        preferred_origin_guild_id = _safe_int(origin_guild_id, 0)
        support_guild, support_channel, support_error = await self._resolve_dm_support_hub_channel(
            origin_guild_id=preferred_origin_guild_id
        )
        if support_error:
            return None, 0, support_error, False
        if support_guild is None or support_channel is None:
            return None, 0, "Support channel is not available.", False

        existing_ticket = await self._get_open_dm_support_ticket_for_user(actor_id)
        if existing_ticket:
            existing_data = existing_ticket.get("data") if isinstance(existing_ticket.get("data"), dict) else {}
            existing_support_guild = self.bot.get_guild(_safe_int(existing_data.get("support_guild_id"), 0))
            existing_support_thread = await self._fetch_thread(
                existing_support_guild,
                _safe_int(existing_data.get("support_thread_id"), 0),
                ensure_exists=True,
            )
            stale_reason = "stale_dm_ticket_thread_missing"
            if existing_support_thread is not None:
                existing_support_channel_id = _safe_int(existing_data.get("support_channel_id"), 0)
                existing_parent_channel_id = _safe_int(getattr(existing_support_thread, "parent_id", 0), 0)
                same_routing = (
                    _safe_int(existing_data.get("support_guild_id"), 0) == int(support_guild.id)
                    and existing_support_channel_id == int(support_channel.id)
                    and (existing_parent_channel_id <= 0 or existing_parent_channel_id == int(support_channel.id))
                )
                stale_reason = "stale_dm_ticket_routing_mismatch"
                if same_routing:
                    if bool(getattr(existing_support_thread, "archived", False)) or bool(
                        getattr(existing_support_thread, "locked", False)
                    ):
                        try:
                            await existing_support_thread.edit(
                                archived=False,
                                locked=False,
                                reason=f"DM user {actor_id} resumed support ticket",
                            )
                        except Exception:
                            existing_support_thread = None
                            stale_reason = "stale_dm_ticket_thread_unusable"
                    if existing_support_thread is not None:
                        return existing_support_thread, _safe_int(existing_ticket.get("id"), 0), None, False
            existing_data["closed_at"] = self.ops.now_iso()
            existing_data["closed_by"] = actor_id
            existing_data["auto_closed_reason"] = stale_reason
            try:
                await self.ops.update_record(
                    _safe_int(existing_ticket.get("id"), 0),
                    status="closed",
                    data=existing_data,
                    actor_id=actor_id,
                )
            except Exception:
                pass

        latest_ticket = await self._get_latest_dm_support_ticket_for_user(actor_id)
        if latest_ticket:
            latest_status = str(latest_ticket.get("status") or "").strip().lower()
            if latest_status == "closed":
                latest_data = latest_ticket.get("data") if isinstance(latest_ticket.get("data"), dict) else {}
                latest_support_guild = self.bot.get_guild(_safe_int(latest_data.get("support_guild_id"), 0))
                latest_support_thread = await self._fetch_thread(
                    latest_support_guild,
                    _safe_int(latest_data.get("support_thread_id"), 0),
                    ensure_exists=True,
                )
                if latest_support_thread is not None:
                    latest_support_channel_id = _safe_int(latest_data.get("support_channel_id"), 0)
                    latest_parent_channel_id = _safe_int(getattr(latest_support_thread, "parent_id", 0), 0)
                    same_routing = (
                        _safe_int(latest_data.get("support_guild_id"), 0) == int(support_guild.id)
                        and latest_support_channel_id == int(support_channel.id)
                        and (latest_parent_channel_id <= 0 or latest_parent_channel_id == int(support_channel.id))
                    )
                    if not same_routing:
                        latest_support_thread = None
                if latest_support_thread is not None:
                    try:
                        await latest_support_thread.edit(
                            archived=False,
                            locked=False,
                            reason=f"DM user {actor_id} reopened support ticket",
                        )
                    except Exception:
                        latest_support_thread = None
                if latest_support_thread is not None:
                    reopened_at = self.ops.now_iso()
                    latest_data["reopened_at"] = reopened_at
                    latest_data["reopened_by"] = actor_id
                    latest_data["reopen_count"] = _safe_int(latest_data.get("reopen_count"), 0) + 1
                    latest_data["issue"] = issue_text
                    latest_data["tag"] = normalized_tag
                    latest_data["opened_by"] = actor_id
                    latest_data.pop("closed_at", None)
                    latest_data.pop("closed_by", None)
                    latest_data.pop("auto_closed_reason", None)
                    latest_ticket_id = _safe_int(latest_ticket.get("id"), 0)
                    if latest_ticket_id <= 0:
                        return None, 0, "Failed to reopen previous DM support ticket.", False
                    try:
                        await self.ops.update_record(
                            latest_ticket_id,
                            status="open",
                            data=latest_data,
                            actor_id=actor_id,
                        )
                    except Exception as reopen_error:
                        return None, 0, f"Failed to reopen previous DM support ticket: {reopen_error}", False

                    latest_ticket["status"] = "open"
                    latest_ticket["data"] = latest_data
                    try:
                        await self._sync_ticket_panels(latest_ticket)
                    except Exception:
                        pass

                    actor_name = str(getattr(actor, "display_name", getattr(actor, "name", "user")) or "user")
                    try:
                        await latest_support_thread.send(
                            embed=discord.Embed(
                                title=self._status_prefixed_title(
                                    "REOPEN",
                                    f"\u0e1c\u0e39\u0e49\u0e43\u0e0a\u0e49 {actor_name} \u0e40\u0e1b\u0e34\u0e14\u0e01\u0e32\u0e23\u0e15\u0e34\u0e14\u0e15\u0e48\u0e2d\u0e43\u0e2b\u0e21\u0e48 (Ticket #{latest_ticket_id})",
                                ),
                                description=(
                                    f"User: <@{actor_id}> (`{actor_id}`)\n"
                                    f"Name: `{actor_name}`\n"
                                    f"Tag: `{normalized_tag}`\n\n"
                                    f"{issue_text}"
                                ),
                                color=color.green,
                            ),
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                    except Exception:
                        pass
                    return latest_support_thread, latest_ticket_id, None, True

        dm_channel = getattr(actor, "dm_channel", None)
        if dm_channel is None:
            try:
                dm_channel = await actor.create_dm()
            except Exception:
                return None, 0, "Cannot open DM channel with this user.", False

        created_at = self.ops.now_iso()
        ticket_record = await self.ops.create_record(
            guild_id=support_guild.id,
            kind="support_ticket",
            status="open",
            actor_id=actor_id,
            user_id=actor_id,
            data={
                "mode": "supportbot_dm",
                "opened_at": created_at,
                "issue": issue_text,
                "tag": normalized_tag,
                "origin_request_guild_id": int(preferred_origin_guild_id),
                "opened_by": actor_id,
                "claimed_by": 0,
                "claimed_at": "",
                "source_message_url": "",
                "channel_id": int(getattr(dm_channel, "id", 0)),
                "message_id": 0,
                "thread_id": 0,
                "origin_channel_id": int(getattr(dm_channel, "id", 0)),
                "origin_message_id": 0,
                "origin_thread_id": 0,
                "origin_panel_message_id": 0,
                "origin_is_dm": True,
                "support_guild_id": int(support_guild.id),
                "support_channel_id": int(support_channel.id),
                "support_message_id": 0,
                "support_thread_id": 0,
                "support_panel_message_id": 0,
            },
        )
        ticket_id = _safe_int(ticket_record.get("id"), 0)
        if ticket_id <= 0:
            return None, 0, "Failed to create support ticket record.", False

        support_embed = discord.Embed(
            title=self._status_prefixed_title("OPEN", f"Incoming DM Support Ticket #{ticket_id}"),
            description=(
                f"User: <@{actor_id}> (`{actor_id}`)\n"
                f"Name: `{self._truncate_text(str(getattr(actor, 'display_name', getattr(actor, 'name', 'user')) or 'user'), 80)}`\n"
                f"Source: **Direct Message**\n"
                f"Tag: `{normalized_tag}`\n\n"
                f"{issue_text}"
            ),
            color=color.orange,
        )
        support_message = await support_channel.send(embed=support_embed)
        support_thread = await support_message.create_thread(
            name=self._ticket_thread_name("owner", ticket_id, getattr(actor, "display_name", getattr(actor, "name", "user")))
        )

        ticket_data = ticket_record.get("data") if isinstance(ticket_record.get("data"), dict) else {}
        ticket_data.update(
            {
                "message_id": int(support_message.id),
                "thread_id": int(support_thread.id),
                "support_message_id": int(support_message.id),
                "support_thread_id": int(support_thread.id),
            }
        )
        await self.ops.update_record(ticket_id, data=ticket_data, actor_id=actor_id)
        ticket_record["data"] = ticket_data

        case_record = await self.ops.create_record(
            guild_id=support_guild.id,
            kind="case",
            status="open",
            actor_id=actor_id,
            user_id=actor_id,
            reference_id=ticket_id,
            data={
                "title": f"Support DM ticket #{ticket_id}",
                "opened_at": created_at,
                "source": "supportbot_dm",
                "support_thread_id": int(support_thread.id),
                "support_ticket_id": ticket_id,
            },
        )
        ticket_data["case_id"] = _safe_int(case_record.get("id"), 0)

        support_view = SupportTicketThreadView(
            self,
            guild_id=support_guild.id,
            ticket_id=ticket_id,
            owner_id=actor_id,
            claimed_by=0,
            closed=False,
        )
        support_panel = await support_thread.send(
            content=(
                "Thread นี้เชื่อมกับผู้ใช้ผ่าน DM แล้ว ทีมงานตอบใน Thread นี้ได้เลย "
                "ระบบจะส่งข้อความกลับไปที่ DM ของผู้ใช้โดยอัตโนมัติ"
            ),
            embed=self._build_support_panel_embed(ticket_record),
            view=support_view,
        )
        ticket_data["panel_message_id"] = int(support_panel.id)
        ticket_data["support_panel_message_id"] = int(support_panel.id)
        await self.ops.update_record(ticket_id, data=ticket_data, actor_id=actor_id)
        await self.ops.bump_health_metric(support_guild.id, "support_opened", 1)
        await self.ops.bump_health_metric(support_guild.id, "cases_opened", 1)
        return support_thread, ticket_id, None, True

    async def _handle_support_modal_submit(
        self,
        interaction: discord.Interaction,
        *,
        issue: str,
        tag: str,
    ) -> None:
        if interaction.channel is None:
            return await self._safe_interaction_reply(
                interaction,
                "Channel context is unavailable.",
                ephemeral=True,
            )
        actor = interaction.user
        if actor is None:
            return await self._safe_interaction_reply(
                interaction,
                "Member context is unavailable.",
                ephemeral=True,
            )

        issue_text = str(issue or "").strip()[:900] or "Need support"
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            pass

        normalized_tag = str(tag or "general").strip().lower()[:24] or "general"
        try:
            thread, ticket_id, error_message, created_ticket = await self._create_support_ticket_from_dm(
                actor=actor,
                issue_text=issue_text,
                normalized_tag=normalized_tag,
                origin_guild_id=_safe_int(getattr(getattr(interaction, "guild", None), "id", 0), 0),
            )
        except Exception as create_error:
            logger.error(
                f"/supportbot ticket create crashed for user {getattr(actor, 'id', 0)}: {create_error}"
            )
            return await self._safe_interaction_reply(
                interaction,
                "Failed to open support ticket. Please try again.",
                ephemeral=True,
            )
        if error_message:
            return await self._safe_interaction_reply(interaction, error_message, ephemeral=True)
        if thread is None:
            return await self._safe_interaction_reply(
                interaction,
                "Failed to open support ticket. Please try again.",
                ephemeral=True,
            )

        if interaction.guild is not None and created_ticket:
            try:
                dm_channel = getattr(actor, "dm_channel", None) or await actor.create_dm()
                await dm_channel.send(
                    embed=discord.Embed(
                        title=self._status_prefixed_title("OPEN", f"Support Ticket #{ticket_id}"),
                        description="คำสั่งสำหรับใช้งานในระบบ",
                        color=color.green,
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except Exception:
                pass

        await self._safe_interaction_reply(
            interaction,
            f"Sent to support team. Ticket `#{ticket_id}` opened. Please continue in DM with the bot.",
            ephemeral=True,
        )

    async def _handle_supportserver_modal_submit(
        self,
        interaction: discord.Interaction,
        *,
        issue: str,
        tag: str,
    ) -> None:
        if interaction.guild is None:
            return await self._safe_interaction_reply(
                interaction,
                "This command can only be used in a server.",
                ephemeral=True,
            )
        actor = interaction.user if isinstance(interaction.user, discord.Member) else None
        if actor is None:
            return await self._safe_interaction_reply(
                interaction,
                "Member context is unavailable.",
                ephemeral=True,
            )

        issue_text = str(issue or "").strip()[:900] or "Need support"
        normalized_tag = str(tag or "general").strip().lower()[:24] or "general"
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            pass

        thread, ticket_id, error_message = await self._create_supportserver_ticket(
            guild=interaction.guild,
            actor=actor,
            issue_text=issue_text,
            normalized_tag=normalized_tag,
        )
        if error_message:
            return await self._safe_interaction_reply(interaction, error_message, ephemeral=True)
        if thread is None:
            return await self._safe_interaction_reply(
                interaction,
                "Failed to open support ticket.",
                ephemeral=True,
            )
        await self._safe_interaction_reply(
            interaction,
            f"Opened support ticket at {thread.mention} (Ticket `#{ticket_id}`).",
            ephemeral=True,
        )

    async def _support_thread_claim(self, interaction: discord.Interaction, view: SupportTicketThreadView) -> None:
        if interaction.guild is None:
            return await self._safe_interaction_reply(interaction, "Use this in a server.", ephemeral=True)
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            return await self._safe_interaction_reply(interaction, "Member context is unavailable.", ephemeral=True)

        row = await self._get_support_ticket_by_id(view.ticket_id)
        if not row:
            return await self._safe_interaction_reply(interaction, "Ticket not found.", ephemeral=True)
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        actor_id = _safe_int(getattr(member, "id", 0), 0)
        if not await self._can_manage_support_ticket(
            member,
            ticket=row,
            data=data,
            action="claim",
            actor_id=actor_id,
        ):
            return await self._safe_interaction_reply(
                interaction,
                "You need support permissions or assigned case role to claim this ticket.",
                ephemeral=True,
            )

        status = str(row.get("status") or "").strip().lower()
        if status == "deleted":
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(interaction, "Ticket is already deleted and archived.", ephemeral=True)
        if status != "open":
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(interaction, "Ticket is already closed.", ephemeral=True)

        current_claimed_by = _safe_int(data.get("claimed_by"), 0)
        if current_claimed_by == int(member.id):
            data["claimed_by"] = 0
            data["claimed_at"] = ""
            message = "Case unclaimed."
        else:
            data["claimed_by"] = int(member.id)
            data["claimed_at"] = self.ops.now_iso()
            message = "Case claimed."

        await self.ops.update_record(_safe_int(row.get("id"), 0), data=data, actor_id=int(member.id))
        row["data"] = data
        await self._support_sync_panel_message(interaction, row, view)
        if _safe_int(data.get("claimed_by"), 0) > 0:
            await self._notify_dm_ticket_user_status(
                row=row,
                data=data,
                status_code="CLAIM",
                description=(
                    "ทีมซัพพอร์ตรับเคสของคุณแล้ว "
                    "คุณสามารถคุยต่อใน DM นี้ได้ และทีมงานจะได้รับข้อความของคุณ"
                ),
                color_value=color.green,
            )
        else:
            await self._notify_dm_ticket_user_status(
                row=row,
                data=data,
                status_code="UNCLAIM",
                description=(
                    "เคสของคุณยังไม่ได้มอบหมายผู้ดูแล แต่ยังเปิดอยู่ "
                    "คุณสามารถคุยต่อใน DM นี้ได้"
                ),
                color_value=color.orange,
            )
        await self._safe_interaction_reply(interaction, message, ephemeral=True)

    async def _support_thread_info(self, interaction: discord.Interaction, view: SupportTicketThreadView) -> None:
        row = await self._get_support_ticket_by_id(view.ticket_id)
        if not row:
            return await self._safe_interaction_reply(interaction, "ไม่พบบันทึกตั๋วนี้", ephemeral=True)
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        opened_by = _safe_int(data.get("opened_by"), 0)
        claimed_by = _safe_int(data.get("claimed_by"), 0)
        created_at = str(data.get("opened_at") or "-")
        closed_at = str(data.get("closed_at") or "-")
        status = str(row.get("status") or "open").strip().upper()
        message = (
            f"Ticket `#{_safe_int(row.get('id'), 0)}`\n"
            f"Status: **{status}**\n"
            f"Opened by: {f'<@{opened_by}>' if opened_by > 0 else '-'}\n"
            f"Claimed by: {f'<@{claimed_by}>' if claimed_by > 0 else '-'}\n"
            f"Opened at: `{created_at}`\n"
            f"Closed at: `{closed_at}`"
        )
        await self._safe_interaction_reply(interaction, message, ephemeral=True)

    async def _support_thread_close(self, interaction: discord.Interaction, view: SupportTicketThreadView) -> None:
        row = await self._get_support_ticket_by_id(view.ticket_id)
        if not row:
            return await self._safe_interaction_reply(interaction, "Ticket not found.", ephemeral=True)

        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        actor_id = _safe_int(getattr(interaction.user, "id", 0), 0)
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            return await self._safe_interaction_reply(interaction, "Member context is unavailable.", ephemeral=True)
        can_close = await self._can_manage_support_ticket(
            member,
            ticket=row,
            data=data,
            action="close",
            actor_id=actor_id,
        )
        if not can_close:
            return await self._safe_interaction_reply(
                interaction,
                "Only ticket owner, claimed staff, or support roles can close this ticket.",
                ephemeral=True,
            )

        status = str(row.get("status") or "").strip().lower()
        if status == "deleted":
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(interaction, "Ticket is already deleted and archived.", ephemeral=True)
        if status != "open":
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(interaction, "Ticket is already closed.", ephemeral=True)

        data["closed_at"] = self.ops.now_iso()
        data["closed_by"] = actor_id
        await self.ops.update_record(_safe_int(row.get("id"), 0), status="closed", data=data, actor_id=actor_id)
        origin_guild_id = _safe_int(row.get("guild_id"), 0)
        if origin_guild_id > 0:
            await self.ops.bump_health_metric(origin_guild_id, "support_closed", 1)
        row["status"] = "closed"
        row["data"] = data
        await self._support_sync_panel_message(interaction, row, view)

        origin_guild = self.bot.get_guild(origin_guild_id)
        support_guild = self.bot.get_guild(_safe_int(data.get("support_guild_id"), 0))
        origin_thread = await self._fetch_thread(origin_guild, _safe_int(data.get("origin_thread_id") or data.get("thread_id"), 0))
        support_thread = await self._fetch_thread(support_guild, _safe_int(data.get("support_thread_id"), 0))
        mode = str(data.get("mode") or "supportbot").strip().lower()

        if origin_thread is not None:
            try:
                await origin_thread.send(
                    embed=discord.Embed(
                        title=self._status_prefixed_title("CLOSE", f"Ticket #{_safe_int(row.get('id'), 0)} closed"),
                        description=f"Ticket closed by <@{actor_id}>",
                        color=color.red,
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except Exception:
                pass
        await self._notify_dm_ticket_user_status(
            row=row,
            data=data,
            status_code="CLOSE",
            description=(
                "แชทซัพพอร์ตของคุณถูกปิดแล้ว "
                "หากยังต้องการความช่วยเหลือ ให้ส่ง DM ใหม่และกด Contact Support อีกครั้ง"
            ),
            color_value=color.red,
        )

        if self._is_ownerbot_operator(member):
            try:
                transcript_logged = await self._post_ownerbot_close_transcript(
                    ticket=row,
                    data=data,
                    closed_by=actor_id,
                    origin_thread=origin_thread,
                    support_thread=support_thread,
                )
                if transcript_logged:
                    await self.ops.update_record(_safe_int(row.get("id"), 0), data=data, actor_id=actor_id)
                    row["data"] = data
            except Exception:
                pass

        close_targets: list[discord.Thread] = []
        seen_thread_ids: set[int] = set()
        for thread_obj in (origin_thread, support_thread):
            if thread_obj is None:
                continue
            thread_id = _safe_int(getattr(thread_obj, "id", 0), 0)
            if thread_id <= 0 or thread_id in seen_thread_ids:
                continue
            seen_thread_ids.add(thread_id)
            close_targets.append(thread_obj)

        owner_closed_and_deleted_origin = False
        owner_closed_origin_attempted = False
        owner_close_mode = bool(mode == "supportbot" and self._is_ownerbot_operator(member))
        for thread_obj in close_targets:
            is_origin_thread = bool(origin_thread is not None and int(thread_obj.id) == int(origin_thread.id))
            if owner_close_mode and is_origin_thread:
                owner_closed_origin_attempted = True
                try:
                    await thread_obj.delete(reason=f"Support ticket {row['id']} closed by ownerbot")
                    data["origin_thread_deleted_at"] = self.ops.now_iso()
                    data["origin_thread_deleted_by"] = actor_id
                    owner_closed_and_deleted_origin = True
                    continue
                except Exception:
                    pass
            try:
                await thread_obj.edit(archived=True, locked=True, reason=f"Support ticket {row['id']} closed")
            except Exception:
                pass

        if owner_closed_and_deleted_origin or owner_closed_origin_attempted:
            try:
                await self.ops.update_record(_safe_int(row.get("id"), 0), data=data, actor_id=actor_id)
                row["data"] = data
            except Exception:
                pass

        if owner_closed_and_deleted_origin:
            return await self._safe_interaction_reply(
                interaction,
                "Ticket closed and origin thread deleted.",
                ephemeral=True,
            )
        await self._safe_interaction_reply(interaction, "Ticket closed successfully.", ephemeral=True)

    async def _support_thread_delete(self, interaction: discord.Interaction, view: SupportTicketThreadView) -> None:
        row = await self._get_support_ticket_by_id(view.ticket_id)
        if not row:
            return await self._safe_interaction_reply(interaction, "Ticket not found.", ephemeral=True)

        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        actor_id = _safe_int(getattr(interaction.user, "id", 0), 0)
        if member is None:
            return await self._safe_interaction_reply(interaction, "Member context is unavailable.", ephemeral=True)

        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        can_delete = await self._can_manage_support_ticket(
            member,
            ticket=row,
            data=data,
            action="delete",
            actor_id=actor_id,
        )
        if not can_delete:
            return await self._safe_interaction_reply(
                interaction,
                "Only support staff or configured support roles can delete tickets.",
                ephemeral=True,
            )

        status = str(row.get("status") or "").strip().lower()
        if status == "deleted":
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(interaction, "Ticket already deleted.", ephemeral=True)

        now_iso = self.ops.now_iso()
        if not str(data.get("closed_at") or "").strip():
            data["closed_at"] = now_iso
        if _safe_int(data.get("closed_by"), 0) <= 0 and actor_id > 0:
            data["closed_by"] = actor_id
        data["deleted_at"] = now_iso
        data["deleted_by"] = actor_id
        data["deleted_from_status"] = status or "open"

        origin_guild = self.bot.get_guild(_safe_int(row.get("guild_id"), 0))
        support_guild = self.bot.get_guild(_safe_int(data.get("support_guild_id"), 0))
        origin_thread = await self._fetch_thread(
            origin_guild,
            _safe_int(data.get("origin_thread_id") or data.get("thread_id"), 0),
        )
        support_thread = await self._fetch_thread(support_guild, _safe_int(data.get("support_thread_id"), 0))

        archive_ok = False
        try:
            archive_ok = await self._post_support_ticket_deleted_archive(
                ticket=row,
                data=data,
                deleted_by=actor_id,
                origin_thread=origin_thread,
                support_thread=support_thread,
            )
        except Exception as archive_error:
            data["delete_archive_error"] = self._truncate_text(str(archive_error), 500)

        case_id = _safe_int(data.get("case_id"), 0)
        if case_id > 0:
            try:
                await self.ops.update_record(case_id, status="archived", actor_id=actor_id)
            except Exception:
                pass

        await self.ops.update_record(_safe_int(row.get("id"), 0), status="deleted", data=data, actor_id=actor_id)
        row["status"] = "deleted"
        row["data"] = data
        await self._support_sync_panel_message(interaction, row, view)

        notice_targets: list[discord.Thread] = []
        seen_thread_ids: set[int] = set()
        for thread_obj in (origin_thread, support_thread):
            if thread_obj is None:
                continue
            if int(thread_obj.id) in seen_thread_ids:
                continue
            seen_thread_ids.add(int(thread_obj.id))
            notice_targets.append(thread_obj)

        for thread_obj in notice_targets:
            try:
                await thread_obj.send(
                    embed=discord.Embed(
                        title=self._status_prefixed_title("DELETE", f"Ticket #{_safe_int(row.get('id'), 0)} deleted"),
                        description=f"Ticket deleted and archived by <@{actor_id}>",
                        color=color.red,
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except Exception:
                pass
            try:
                await thread_obj.edit(archived=True, locked=True, reason=f"Support ticket {row['id']} deleted")
            except Exception:
                pass
        await self._notify_dm_ticket_user_status(
            row=row,
            data=data,
            status_code="DELETE",
            description=(
                "แชทซัพพอร์ตของคุณถูกลบและเก็บถาวรแล้ว "
                "หากต้องการความช่วยเหลืออีกครั้ง ให้ส่ง DM ใหม่เพื่อเริ่มติดต่อใหม่"
            ),
            color_value=color.red,
        )

        if _safe_int(row.get("guild_id"), 0) > 0:
            await self.ops.bump_health_metric(_safe_int(row.get("guild_id"), 0), "support_deleted", 1)

        if archive_ok:
            return await self._safe_interaction_reply(interaction, "Ticket deleted and archived.", ephemeral=True)
        return await self._safe_interaction_reply(
            interaction,
            "Ticket deleted, but archive failed. Check archive channel permissions.",
            ephemeral=True,
        )

    async def _support_thread_reopen(self, interaction: discord.Interaction, view: SupportTicketThreadView) -> None:
        row = await self._get_support_ticket_by_id(view.ticket_id)
        if not row:
            return await self._safe_interaction_reply(interaction, "Ticket not found.", ephemeral=True)

        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member is None:
            return await self._safe_interaction_reply(interaction, "Member context is unavailable.", ephemeral=True)

        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        actor_id = _safe_int(getattr(member, "id", 0), 0)
        can_reopen = await self._can_manage_support_ticket(
            member,
            ticket=row,
            data=data,
            action="reopen",
            actor_id=actor_id,
        )
        if not can_reopen:
            return await self._safe_interaction_reply(
                interaction,
                "Only support staff or configured support roles can reopen tickets.",
                ephemeral=True,
            )

        status = str(row.get("status") or "").strip().lower()
        if status == "deleted":
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(interaction, "Ticket is deleted and cannot be reopened.", ephemeral=True)
        if status == "open":
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(interaction, "Ticket is already open.", ephemeral=True)
        if str(data.get("origin_thread_deleted_at") or "").strip():
            await self._support_sync_panel_message(interaction, row, view)
            return await self._safe_interaction_reply(
                interaction,
                "Origin thread was deleted after close and cannot be reopened.",
                ephemeral=True,
            )

        data["reopened_at"] = self.ops.now_iso()
        data["reopened_by"] = int(member.id)
        await self.ops.update_record(_safe_int(row.get("id"), 0), status="open", data=data, actor_id=int(member.id))
        row["status"] = "open"
        row["data"] = data
        await self._support_sync_panel_message(interaction, row, view)

        origin_guild = self.bot.get_guild(_safe_int(row.get("guild_id"), 0))
        support_guild = self.bot.get_guild(_safe_int(data.get("support_guild_id"), 0))
        origin_thread = await self._fetch_thread(origin_guild, _safe_int(data.get("origin_thread_id") or data.get("thread_id"), 0))
        support_thread = await self._fetch_thread(support_guild, _safe_int(data.get("support_thread_id"), 0))
        mode = str(data.get("mode") or "supportbot").strip().lower()

        reopen_targets: list[discord.Thread] = []
        seen_thread_ids: set[int] = set()
        for thread_obj in (origin_thread, support_thread):
            if thread_obj is None:
                continue
            thread_id = _safe_int(getattr(thread_obj, "id", 0), 0)
            if thread_id <= 0 or thread_id in seen_thread_ids:
                continue
            seen_thread_ids.add(thread_id)
            reopen_targets.append(thread_obj)

        for thread_obj in reopen_targets:
            try:
                await thread_obj.edit(archived=False, locked=False, reason=f"Support ticket {row['id']} reopened")
            except Exception:
                pass

        if origin_thread is not None:
            try:
                await origin_thread.send(
                    embed=discord.Embed(
                        title=self._status_prefixed_title("REOPEN", f"Ticket #{_safe_int(row.get('id'), 0)} reopened"),
                        description=f"Ticket reopened by <@{member.id}>",
                        color=color.green,
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except Exception:
                pass
        elif mode == "supportbot_dm":
            try:
                target_user = await self._resolve_user(_safe_int(data.get("opened_by") or row.get("user_id"), 0))
                if target_user is not None:
                    dm_channel = target_user.dm_channel or await target_user.create_dm()
                    await dm_channel.send(
                        embed=discord.Embed(
                            title=self._status_prefixed_title("REOPEN", f"Ticket #{_safe_int(row.get('id'), 0)}"),
                            description="Ticket นี้ถูกเปิดใหม่แล้ว คุณสามารถพิมพ์ข้อความต่อได้ในแชทนี้",
                            color=color.green,
                        ),
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
            except Exception:
                pass
        await self._safe_interaction_reply(interaction, "Ticket reopened.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot or member.guild is None:
            return

        await self.ops.mark_onboard_stage(member.guild.id, "joined", 1)
        await self.ops.bump_health_metric(member.guild.id, "joins", 1)
        await self.ops.get_trust_profile(member.guild.id, member.id)

        state = await self._get_raid_state(member.guild.id)
        if not state.get("armed"):
            return

        now_ts = time.time()
        window_seconds = max(5, _safe_int(state.get("window_seconds"), 20))
        join_threshold = max(2, _safe_int(state.get("join_threshold"), 6))
        min_age_days = max(0, _safe_int(state.get("min_account_age_days"), 3))

        join_window = self._raid_join_windows.setdefault(member.guild.id, [])
        join_window.append(now_ts)
        join_window[:] = [ts for ts in join_window if now_ts - ts <= window_seconds]

        burst_hit = len(join_window) >= join_threshold
        low_age = self._account_age_days(member) < min_age_days
        if burst_hit or (low_age and len(join_window) >= max(2, join_threshold // 2)):
            await self._trigger_raid_lockdown(
                member.guild,
                "join_spike",
                f"{len(join_window)} joins/{window_seconds}s, age={self._account_age_days(member)}d",
            )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild is None or before.bot:
            return
        flow = await self.ops.get_config_data(
            before.guild.id, "onboard_flow", {"verify_role_id": 0, "member_role_id": 0}
        )
        verify_role_id = _safe_int(flow.get("verify_role_id"), 0)
        member_role_id = _safe_int(flow.get("member_role_id"), 0)

        before_ids = {role.id for role in before.roles}
        after_ids = {role.id for role in after.roles}

        if verify_role_id > 0 and verify_role_id not in before_ids and verify_role_id in after_ids:
            await self.ops.mark_onboard_stage(before.guild.id, "verified", 1)
        if member_role_id > 0 and member_role_id not in before_ids and member_role_id in after_ids:
            await self.ops.mark_onboard_stage(before.guild.id, "role_assigned", 1)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is None:
            if bool(getattr(message, "_support_dm_handled", False)):
                return
            try:
                setattr(message, "_support_dm_handled", True)
            except Exception:
                pass
            try:
                if await self._relay_dm_support_message(message):
                    return
            except Exception as relay_error:
                logger.error(
                    f"Support DM relay failed for user {getattr(message.author, 'id', 0)}: {relay_error}"
                )
            try:
                prompted = await self._prompt_dm_support_confirmation(message)
                if not prompted:
                    await message.channel.send(
                        "Support system is temporarily unavailable. Please try again in a moment."
                    )
            except Exception as prompt_error:
                logger.error(
                    f"Support DM confirmation prompt failed for user {getattr(message.author, 'id', 0)}: {prompt_error}"
                )
                try:
                    await message.channel.send(
                        "Support system is temporarily unavailable. Please try again in a moment."
                    )
                except Exception:
                    pass
            return

        if isinstance(message.channel, discord.Thread):
            try:
                if await self._relay_support_thread_message(message):
                    return
            except Exception:
                pass

        if await self.ops.mark_first_message(message.guild.id, message.author.id):
            await self.ops.mark_onboard_stage(message.guild.id, "first_message", 1)
            await self.ops.bump_health_metric(message.guild.id, "first_messages", 1)

        rules = await self.ops.get_trust_rules(message.guild.id)
        if rules.get("enabled", True) and self.ops.should_award_trust(message.guild.id, message.author.id):
            delta = max(0, _safe_int(rules.get("message_gain"), 1))
            if delta > 0:
                profile = await self.ops.adjust_trust_score(message.guild.id, message.author.id, delta)
                data = profile.get("data") if isinstance(profile.get("data"), dict) else {}
                if isinstance(message.author, discord.Member):
                    await self._sync_trust_roles(message.author, data, rules)
                await self.ops.bump_health_metric(message.guild.id, "active_messages", 1)

        state = await self._get_raid_state(message.guild.id)
        if not state.get("armed"):
            return

        now_ts = time.time()
        window_seconds = max(5, _safe_int(state.get("window_seconds"), 20))
        mention_threshold = max(3, _safe_int(state.get("mention_threshold"), 12))
        min_age_days = max(0, _safe_int(state.get("min_account_age_days"), 3))

        mention_count = len([m for m in message.mentions if not m.bot])
        if mention_count > 0:
            mention_window = self._raid_mention_windows.setdefault(message.guild.id, [])
            mention_window.append((now_ts, mention_count))
            mention_window[:] = [(ts, c) for ts, c in mention_window if now_ts - ts <= window_seconds]
            if sum(c for _, c in mention_window) >= mention_threshold:
                await self._trigger_raid_lockdown(
                    message.guild,
                    "mention_burst",
                    f"mentions>={mention_threshold} in {window_seconds}s",
                )

        if state.get("lockdown_active") and isinstance(message.author, discord.Member):
            if self._account_age_days(message.author) < min_age_days:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    if message.guild.me.guild_permissions.moderate_members:
                        await message.author.timeout(
                            timedelta(minutes=10),
                            reason="Raid lockdown: suspicious new account",
                        )
                        await self.ops.bump_health_metric(message.guild.id, "lockdown_actions", 1)
                except Exception:
                    pass

    @commands.hybrid_group(
        name="raid",
        with_app_command=True,
        invoke_without_command=True,
        help="ตั้งค่าและติดตามระบบป้องกัน Raid Shield",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def raid_group(self, ctx: commands.Context):
        await ctx.send("`/raid arm`, `/raid status`, `/raid release`")

    @raid_group.command(name="arm", help="เปิดใช้งาน Raid Shield พร้อมตั้งค่าเกณฑ์")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def raid_arm(
        self,
        ctx: commands.Context,
        join_threshold: int = 6,
        window_seconds: int = 20,
        min_account_age_days: int = 3,
        mention_threshold: int = 12,
    ):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        state = await self._get_raid_state(ctx.guild.id)
        state["armed"] = True
        state["join_threshold"] = max(2, min(100, int(join_threshold)))
        state["window_seconds"] = max(5, min(120, int(window_seconds)))
        state["min_account_age_days"] = max(0, min(365, int(min_account_age_days)))
        state["mention_threshold"] = max(3, min(200, int(mention_threshold)))
        await self._set_raid_state(ctx.guild.id, state)
        await ctx.send(embed=discord.Embed(description="เปิดใช้งาน Raid Shield แล้ว", color=color.green))

    @raid_group.command(name="status", help="แสดงสถานะปัจจุบันของ Raid Shield")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def raid_status(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        state = await self._get_raid_state(ctx.guild.id)
        embed = discord.Embed(title="คำสั่งสำหรับใช้งานในระบบ", color=color.blue)
        embed.add_field(name="Armed", value=str(bool(state.get("armed"))), inline=True)
        embed.add_field(name="Lockdown", value=str(bool(state.get("lockdown_active"))), inline=True)
        embed.add_field(name="Trigger Count", value=str(_safe_int(state.get("trigger_count"), 0)), inline=True)
        embed.add_field(
            name="Rule",
            value=f"joins={state.get('join_threshold')}/{state.get('window_seconds')}s | mentions={state.get('mention_threshold')}",
            inline=False,
        )
        embed.add_field(name="Last Reason", value=str(state.get("last_reason") or "-"), inline=False)
        embed.add_field(name="Triggered At", value=str(state.get("triggered_at") or "-"), inline=False)
        await ctx.send(embed=embed)

    @raid_group.command(name="release", help="ยกเลิกการล็อกดาวน์จาก Raid ที่กำลังทำงาน")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def raid_release(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        state = await self._get_raid_state(ctx.guild.id)
        state["lockdown_active"] = False
        state["last_reason"] = "released_by_staff"
        await self._set_raid_state(ctx.guild.id, state)
        self._raid_join_windows.pop(ctx.guild.id, None)
        self._raid_mention_windows.pop(ctx.guild.id, None)
        await ctx.send(embed=discord.Embed(description="ยกเลิกการล็อกดาวน์จาก Raid แล้ว", color=color.green))

    @commands.hybrid_group(
        name="case",
        with_app_command=True,
        invoke_without_command=True,
        help="จัดการเคสงานดูแล",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def case_group(self, ctx: commands.Context):
        await ctx.send("`/case queue`, `/case assign`, `/case resolve`")

    @case_group.command(name="queue", help="แสดงรายการเคสตามสถานะ")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def case_queue(self, ctx: commands.Context, status: str = "open"):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        status_norm = str(status or "open").strip().lower()
        if status_norm not in {"open", "assigned", "resolved", "pending"}:
            status_norm = "open"
        rows = await self.ops.list_records(guild_id=ctx.guild.id, kind="case", status=status_norm, limit=20)
        if not rows:
            return await ctx.send(f"No `{status_norm}` cases.")
        lines = []
        for row in rows:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            lines.append(
                f"`#{row['id']}` {str(data.get('title') or 'Untitled')[:70]} | opened_by=<@{_safe_int(row.get('actor_id'))}>"
            )
        await ctx.send(embed=discord.Embed(title=f"Case Queue ({status_norm})", description="\n".join(lines), color=color.blue))

    @case_group.command(name="assign", help="มอบหมายเคสให้ผู้ดูแล")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def case_assign(self, ctx: commands.Context, case_id: int, moderator: discord.Member):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        row = await self.ops.get_record(guild_id=ctx.guild.id, kind="case", record_id=case_id)
        if not row:
            return await ctx.send("Case not found.")
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        data["assigned_to"] = int(moderator.id)
        data["assigned_at"] = self.ops.now_iso()
        await self.ops.update_record(row["id"], status="assigned", data=data)
        await ctx.send(embed=discord.Embed(description=f"Assigned case `#{row['id']}` to {moderator.mention}.", color=color.green))

    @case_group.command(name="resolve", help="ปิดเคสพร้อมบันทึกหมายเหตุ (ไม่บังคับ)")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def case_resolve(self, ctx: commands.Context, case_id: int, note: str = ""):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        row = await self.ops.get_record(guild_id=ctx.guild.id, kind="case", record_id=case_id)
        if not row:
            return await ctx.send("Case not found.")
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        data["resolved_at"] = self.ops.now_iso()
        data["resolved_by"] = int(ctx.author.id)
        data["resolution_note"] = str(note or "")[:700]
        await self.ops.update_record(row["id"], status="resolved", data=data)
        await self.ops.bump_health_metric(ctx.guild.id, "cases_resolved", 1)
        await ctx.send(embed=discord.Embed(description=f"Case `#{row['id']}` resolved.", color=color.green))

    @commands.hybrid_group(
        name="evidence",
        with_app_command=True,
        invoke_without_command=True,
        help="บันทึกและส่งออกหลักฐานงานดูแล",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def evidence_group(self, ctx: commands.Context):
        await ctx.send("`/evidence capture`, `/evidence export`")

    @evidence_group.command(name="capture", help="บันทึกสแนปช็อตข้อความเป็นหลักฐาน")
    @app_commands.describe(target="Message link or ID")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def evidence_capture(self, ctx: commands.Context, target: str, reason: str = "No reason"):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        fallback_channel = int(ctx.channel.id) if ctx.channel else 0
        channel_id, message_id = self._extract_target_ids(target, fallback_channel)
        if message_id <= 0:
            return await ctx.send("Invalid target.")
        message = await self._fetch_message(ctx.guild, channel_id, message_id)
        if message is None:
            return await ctx.send("Message not found.")

        snapshot = {
            "message_id": int(message.id),
            "channel_id": int(message.channel.id),
            "author_id": int(message.author.id),
            "author_name": str(message.author),
            "content": str(message.content or "")[:1800],
            "attachments": [str(a.url) for a in list(message.attachments or [])][:8],
            "jump_url": str(message.jump_url),
            "captured_at": self.ops.now_iso(),
            "captured_by": int(ctx.author.id),
            "reason": str(reason or "")[:250],
        }
        evidence = await self.ops.create_record(
            guild_id=ctx.guild.id,
            kind="evidence",
            status="active",
            actor_id=ctx.author.id,
            user_id=message.author.id,
            data=snapshot,
        )
        case_row = await self.ops.create_record(
            guild_id=ctx.guild.id,
            kind="case",
            status="open",
            actor_id=ctx.author.id,
            user_id=message.author.id,
            reference_id=int(evidence.get("id", 0)),
            data={
                "title": f"Evidence snapshot #{evidence.get('id')}",
                "opened_at": self.ops.now_iso(),
                "source": "evidence",
                "evidence_ids": [int(evidence.get("id", 0))],
            },
        )
        await self.ops.bump_health_metric(ctx.guild.id, "cases_opened", 1)
        await ctx.send(embed=discord.Embed(description=f"Evidence `#{evidence['id']}` captured. Case `#{case_row['id']}` opened.", color=color.green))

    @evidence_group.command(name="export", help="ส่งออกหลักฐานของเคสเป็นไฟล์ข้อความ")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def evidence_export(self, ctx: commands.Context, case_id: int):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        case_row = await self.ops.get_record(guild_id=ctx.guild.id, kind="case", record_id=case_id)
        if not case_row:
            return await ctx.send("Case not found.")
        case_data = case_row.get("data") if isinstance(case_row.get("data"), dict) else {}
        evidence_ids = [int(item) for item in list(case_data.get("evidence_ids") or []) if _safe_int(item, 0) > 0]
        if not evidence_ids and _safe_int(case_row.get("reference_id"), 0) > 0:
            evidence_ids = [_safe_int(case_row.get("reference_id"), 0)]

        lines = [f"Case #{case_row['id']}", f"Status: {case_row.get('status')}", ""]
        for evidence_id in evidence_ids:
            row = await self.ops.get_record(guild_id=ctx.guild.id, kind="evidence", record_id=evidence_id)
            if not row:
                continue
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            lines.extend(
                [
                    f"Evidence #{row['id']}",
                    f"Message: {data.get('message_id')}",
                    f"Channel: {data.get('channel_id')}",
                    f"Author: {data.get('author_id')} ({data.get('author_name')})",
                    f"Reason: {data.get('reason')}",
                    "Content:",
                    str(data.get("content") or ""),
                    f"Attachments: {', '.join(data.get('attachments') or []) or '-'}",
                    f"Jump URL: {data.get('jump_url')}",
                    "-" * 40,
                ]
            )
        payload = "\n".join(lines)
        fp = io.BytesIO(payload.encode("utf-8"))
        await ctx.send(file=discord.File(fp=fp, filename=f"case-{case_row['id']}-evidence.txt"))

    @commands.hybrid_group(
        name="appeal",
        with_app_command=True,
        invoke_without_command=True,
        help="ยื่นและตรวจสอบคำอุทธรณ์งานดูแล",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def appeal_group(self, ctx: commands.Context):
        await ctx.send("`/appeal submit`, `/appeal review`, `/appeal verdict`")

    @appeal_group.command(name="submit", help="ยื่นอุทธรณ์ต่อการดำเนินการของผู้ดูแล")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def appeal_submit(self, ctx: commands.Context, action: str, reason: str):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        row = await self.ops.create_record(
            guild_id=ctx.guild.id,
            kind="appeal",
            status="pending",
            actor_id=ctx.author.id,
            user_id=ctx.author.id,
            data={
                "action": str(action or "")[:120],
                "reason": str(reason or "")[:1200],
                "submitted_at": self.ops.now_iso(),
                "sla_due_at": (OpsHubService.now_utc() + timedelta(hours=72)).replace(microsecond=0).isoformat(),
            },
        )
        await ctx.send(embed=discord.Embed(description=f"Appeal submitted. ID: `#{row['id']}`", color=color.green))

    @appeal_group.command(name="review", help="แสดงคำอุทธรณ์ที่รอพิจารณา")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def appeal_review(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        rows = await self.ops.list_records(guild_id=ctx.guild.id, kind="appeal", status="pending", limit=15)
        if not rows:
            return await ctx.send("No pending appeals.")
        lines = []
        for row in rows:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            lines.append(f"`#{row['id']}` user=<@{_safe_int(row.get('user_id'))}> due={data.get('sla_due_at', '-')}")
        await ctx.send(embed=discord.Embed(title="คำสั่งสำหรับใช้งานในระบบ", description="\n".join(lines), color=color.blue))

    @appeal_group.command(name="verdict", help="ตัดสินผลคำอุทธรณ์")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def appeal_verdict(self, ctx: commands.Context, appeal_id: int, verdict: str, note: str = ""):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        row = await self.ops.get_record(guild_id=ctx.guild.id, kind="appeal", record_id=appeal_id)
        if not row:
            return await ctx.send("Appeal not found.")
        verdict_norm = str(verdict or "").strip().lower()
        if verdict_norm not in {"approve", "reject", "need_more_info"}:
            return await ctx.send("Use: approve / reject / need_more_info")
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        data["verdict"] = verdict_norm
        data["reviewed_by"] = int(ctx.author.id)
        data["reviewed_at"] = self.ops.now_iso()
        data["review_note"] = str(note or "")[:1200]
        status = "approved" if verdict_norm == "approve" else "rejected" if verdict_norm == "reject" else "pending"
        await self.ops.update_record(row["id"], status=status, data=data)
        await ctx.send(embed=discord.Embed(description=f"Appeal `#{row['id']}` -> {verdict_norm}", color=color.green))

    @commands.hybrid_group(
        name="onboard",
        with_app_command=True,
        invoke_without_command=True,
        help="ตั้งค่าโฟลว์ onboarding และตัวชี้วัด",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def onboard_group(self, ctx: commands.Context):
        await ctx.send("`/onboard flow`, `/onboard stats`")

    @onboard_group.command(name="flow", help="ตั้งค่าหรือดูยศ onboarding")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def onboard_flow(
        self,
        ctx: commands.Context,
        verify_role: discord.Role | None = None,
        member_role: discord.Role | None = None,
    ):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        config = await self.ops.get_config_data(
            ctx.guild.id, "onboard_flow", {"verify_role_id": 0, "member_role_id": 0}
        )
        if verify_role is not None:
            config["verify_role_id"] = int(verify_role.id)
        if member_role is not None:
            config["member_role_id"] = int(member_role.id)
        await self.ops.set_config_data(ctx.guild.id, "onboard_flow", config)
        verify_text = f"<@&{_safe_int(config.get('verify_role_id'), 0)}>" if _safe_int(config.get("verify_role_id"), 0) else "-"
        member_text = f"<@&{_safe_int(config.get('member_role_id'), 0)}>" if _safe_int(config.get("member_role_id"), 0) else "-"
        await ctx.send(embed=discord.Embed(description=f"Verify role: {verify_text}\nJourney role: {member_text}", color=color.green))

    @onboard_group.command(name="stats", help="แสดงสถิติ funnel onboarding")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def onboard_stats(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        stats = await self.ops.get_onboard_stats(ctx.guild.id)
        joined = max(0, _safe_int(stats.get("joined"), 0))
        verified = max(0, _safe_int(stats.get("verified"), 0))
        role_assigned = max(0, _safe_int(stats.get("role_assigned"), 0))
        first_message = max(0, _safe_int(stats.get("first_message"), 0))

        def _rate(value: int) -> str:
            if joined <= 0:
                return "0.0%"
            return f"{(float(value) / float(joined) * 100.0):.1f}%"

        embed = discord.Embed(title="คำสั่งสำหรับใช้งานในระบบ", color=color.blue)
        embed.add_field(name="Joined", value=str(joined), inline=True)
        embed.add_field(name="Verified", value=f"{verified} ({_rate(verified)})", inline=True)
        embed.add_field(name="Role Assigned", value=f"{role_assigned} ({_rate(role_assigned)})", inline=True)
        embed.add_field(name="First Message", value=f"{first_message} ({_rate(first_message)})", inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_group(
        name="supportserver",
        with_app_command=True,
        invoke_without_command=True,
        help="เปิดเธรดทิกเก็ตซัพพอร์ตในเซิร์ฟเวอร์นี้",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def supportserver_group(self, ctx: commands.Context):
        if getattr(ctx, "invoked_subcommand", None) is not None:
            return
        if ctx.guild is None:
            return await self._safe_ctx_send(ctx, "This command can only be used in a server.")
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return await self._safe_ctx_send(
                ctx,
                "Use slash command `/supportserver` to open the support ticket form.",
            )
        try:
            if getattr(interaction, "is_expired", None) and interaction.is_expired():
                return await self._safe_ctx_send(
                    ctx,
                    "อินเทอร์แอคชั่นหมดอายุแล้ว กรุณาลองใหม่",
                    ephemeral=True,
                )
            if interaction.response.is_done():
                return await interaction.followup.send(
                    "Please run `/supportserver` again.",
                    ephemeral=True,
                )
            await interaction.response.send_modal(SupportServerTicketCreateModal(self))
        except discord.NotFound:
            await self._safe_ctx_send(ctx, "Interaction expired. Please run the command again.", ephemeral=True)
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                await self._safe_ctx_send(ctx, "Interaction expired. Please run the command again.", ephemeral=True)
            else:
                raise

    @supportserver_group.command(name="open", with_app_command=True, help="เปิดฟอร์มทิกเก็ตซัพพอร์ต")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def supportserver_open(self, ctx: commands.Context):
        if ctx.guild is None:
            return await self._safe_ctx_send(ctx, "This command can only be used in a server.")
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return await self._safe_ctx_send(
                ctx,
                "Use slash command `/supportserver open` to open the support ticket form.",
            )
        try:
            if getattr(interaction, "is_expired", None) and interaction.is_expired():
                return await self._safe_ctx_send(
                    ctx,
                    "Interaction expired. Please run the command again.",
                    ephemeral=True,
                )
            if interaction.response.is_done():
                return await interaction.followup.send(
                    "Please run `/supportserver open` again.",
                    ephemeral=True,
                )
            await interaction.response.send_modal(SupportServerTicketCreateModal(self))
        except discord.NotFound:
            await self._safe_ctx_send(ctx, "Interaction expired. Please run the command again.", ephemeral=True)
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                await self._safe_ctx_send(ctx, "Interaction expired. Please run the command again.", ephemeral=True)
            else:
                raise

    @supportserver_group.command(name="setup", with_app_command=True, help="ตั้งค่าระบบเธรด supportserver")
    @app_commands.describe(
        enabled="Enable or disable supportserver ticket system",
        channel="Thread hub channel (where tickets are created)",
        archive_channel="Archive log channel for deleted ticket transcripts",
        open_category="Category to use when auto-creating support hub channel",
        closed_category="Category for archive channel",
        add_role="Add case receiver role",
        remove_role="Remove case receiver role",
        clear_roles="Clear all case receiver roles",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def supportserver_setup(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
        channel: discord.TextChannel | None = None,
        archive_channel: discord.TextChannel | None = None,
        open_category: discord.CategoryChannel | None = None,
        closed_category: discord.CategoryChannel | None = None,
        add_role: discord.Role | None = None,
        remove_role: discord.Role | None = None,
        clear_roles: bool = False,
    ):
        if ctx.guild is None:
            return await self._safe_ctx_send(ctx, "This command can only be used in a server.")
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if member is None or not (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
            or self._is_ownerbot_operator(member)
        ):
            return await self._safe_ctx_send(
                ctx,
                "Only server admins can configure supportserver.",
                ephemeral=True,
            )

        module = await self._get_or_create_supportserver_module(ctx.guild.id)
        if not module:
            return await self._safe_ctx_send(ctx, "Cannot load supportserver settings.", ephemeral=True)
        module_id = _safe_int(module.get("id"), 0)
        if module_id <= 0:
            return await self._safe_ctx_send(ctx, "Supportserver settings row is invalid.", ephemeral=True)

        support_roles = self._supportserver_staff_role_ids(module)
        if clear_roles:
            support_roles = []
        if add_role is not None and int(add_role.id) not in support_roles:
            support_roles.append(int(add_role.id))
        if remove_role is not None:
            support_roles = [role_id for role_id in support_roles if role_id != int(remove_role.id)]

        update_payload: dict[str, Any] = {
            "id": module_id,
            "guild_id": int(ctx.guild.id),
            "ticket_module_id": _safe_int(module.get("ticket_module_id"), 1),
            "support_roles": support_roles,
        }
        if enabled is not None:
            update_payload["enabled"] = bool(enabled)
        if channel is not None:
            if int(channel.guild.id) != int(ctx.guild.id):
                return await self._safe_ctx_send(ctx, "Channel must be from this server.", ephemeral=True)
            update_payload["ticket_panel_channel_id"] = int(channel.id)
        if open_category is not None:
            if int(open_category.guild.id) != int(ctx.guild.id):
                return await self._safe_ctx_send(ctx, "Open category must be from this server.", ephemeral=True)
            update_payload["open_ticket_category_id"] = int(open_category.id)
        if closed_category is not None:
            if int(closed_category.guild.id) != int(ctx.guild.id):
                return await self._safe_ctx_send(ctx, "Closed category must be from this server.", ephemeral=True)
            update_payload["closed_ticket_category_id"] = int(closed_category.id)

        module = await ticket_settings_db.update(**update_payload)
        if not module:
            module = await self._get_or_create_supportserver_module(ctx.guild.id)
        if not module:
            return await self._safe_ctx_send(ctx, "Cannot save supportserver settings.", ephemeral=True)

        extra = await self._get_supportserver_extra_config(ctx.guild.id)
        if archive_channel is not None:
            if int(archive_channel.guild.id) != int(ctx.guild.id):
                return await self._safe_ctx_send(ctx, "Archive channel must be from this server.", ephemeral=True)
            extra["archive_channel_id"] = int(archive_channel.id)
            await self._set_supportserver_extra_config(ctx.guild.id, extra)

        embed = await self._build_supportserver_setup_embed_with_state(ctx.guild, module)
        view = SupportServerSetupView(self, guild_id=int(ctx.guild.id))
        self._sync_supportserver_setup_toggle(view, module)
        await self._safe_ctx_send(ctx, embed=embed, view=view, ephemeral=True)

    @supportserver_group.command(name="setupall", with_app_command=True, help="สร้างห้อง supportserver อัตโนมัติและเปิดใช้งานระบบ")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def supportserver_setupall(self, ctx: commands.Context):
        if ctx.guild is None:
            return await self._safe_ctx_send(ctx, "This command can only be used in a server.")
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if member is None or not (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
            or self._is_ownerbot_operator(member)
        ):
            return await self._safe_ctx_send(
                ctx,
                "Only server admins can run setupall.",
                ephemeral=True,
            )

        module = await self._get_or_create_supportserver_module(ctx.guild.id)
        if not module:
            return await self._safe_ctx_send(ctx, "Cannot load supportserver settings.", ephemeral=True)

        if _safe_int(module.get("open_ticket_category_id"), 0) <= 0 and ctx.guild.me and ctx.guild.me.guild_permissions.manage_channels:
            try:
                open_category = next(
                    (
                        category
                        for category in list(ctx.guild.categories or [])
                        if str(category.name or "").strip().lower() == "support-open"
                    ),
                    None,
                )
                if open_category is None:
                    open_category = await ctx.guild.create_category(
                        name="support-open",
                        reason="Auto-created by /supportserver setupall"[:512],
                    )
                module = await ticket_settings_db.update(
                    id=_safe_int(module.get("id"), 0),
                    guild_id=int(ctx.guild.id),
                    ticket_module_id=_safe_int(module.get("ticket_module_id"), 1),
                    open_ticket_category_id=int(open_category.id),
                ) or module
            except Exception:
                pass

        if _safe_int(module.get("closed_ticket_category_id"), 0) <= 0 and ctx.guild.me and ctx.guild.me.guild_permissions.manage_channels:
            try:
                closed_category = next(
                    (
                        category
                        for category in list(ctx.guild.categories or [])
                        if str(category.name or "").strip().lower() == "support-archive"
                    ),
                    None,
                )
                if closed_category is None:
                    closed_category = await ctx.guild.create_category(
                        name="support-archive",
                        reason="Auto-created by /supportserver setupall"[:512],
                    )
                module = await ticket_settings_db.update(
                    id=_safe_int(module.get("id"), 0),
                    guild_id=int(ctx.guild.id),
                    ticket_module_id=_safe_int(module.get("ticket_module_id"), 1),
                    closed_ticket_category_id=int(closed_category.id),
                ) or module
            except Exception:
                pass

        module, _, create_error = await self._ensure_supportserver_hub_channel(ctx.guild, module)
        if create_error:
            return await self._safe_ctx_send(ctx, create_error, ephemeral=True)

        module = await ticket_settings_db.update(
            id=_safe_int(module.get("id"), 0),
            guild_id=int(ctx.guild.id),
            ticket_module_id=_safe_int(module.get("ticket_module_id"), 1),
            enabled=True,
        ) or module

        _, archive_error = await self._ensure_supportserver_archive_channel(ctx.guild, module)
        if archive_error:
            # Non-fatal: system can still run without dedicated archive channel.
            pass

        embed = await self._build_supportserver_setup_embed_with_state(ctx.guild, module)
        if archive_error:
            embed.add_field(name="Archive Notice", value=self._truncate_text(archive_error, 1000), inline=False)
        view = SupportServerSetupView(self, guild_id=int(ctx.guild.id))
        self._sync_supportserver_setup_toggle(view, module)
        await self._safe_ctx_send(ctx, embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="supportbot", with_app_command=True, help="Open support ticket (DM mode) (ไทย)")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def supportbot(self, ctx: commands.Context):
        if ctx.channel is None:
            return await self._safe_ctx_send(ctx, "Channel context is unavailable.")
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return await self._safe_ctx_send(
                ctx,
                "ใช้คำสั่ง `/supportbot` แบบ Slash เพื่อกรอกฟอร์มและเปิดตั๋ว",
            )
        try:
            if getattr(interaction, "is_expired", None) and interaction.is_expired():
                return await self._safe_ctx_send(
                    ctx,
                    "Interaction expired. Please run the command again.",
                    ephemeral=True,
                )
            if interaction.response.is_done():
                return await interaction.followup.send(
                    "กรุณาเรียกคำสั่งใหม่อีกครั้ง แล้วกรอกฟอร์มเปิดตั๋ว",
                    ephemeral=True,
                )
            await interaction.response.send_modal(SupportTicketCreateModal(self))
        except discord.NotFound as interaction_error:
            logger.warning(f"/supportbot interaction not found: {interaction_error}")
            await self._safe_ctx_send(ctx, "อินเทอร์แอคชันหมดอายุแล้ว กรุณาลองใหม่", ephemeral=True)
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                logger.warning(f"/supportbot interaction expired (10062): {interaction_error}")
                await self._safe_ctx_send(ctx, "อินเทอร์แอคชันหมดอายุแล้ว กรุณาลองใหม่", ephemeral=True)
            else:
                logger.error(
                    f"/supportbot interaction send_modal failed code={getattr(interaction_error, 'code', None)}: {interaction_error}"
                )
                raise

    @commands.hybrid_command(
        name="supportbotdm",
        with_app_command=True,
        help="OwnerBOT: initiate DM support ticket with a user (ไทย)",
    )
    @app_commands.describe(
        user="User to contact",
        message="Message to send in DM",
        tag="Ticket tag (default: general)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def supportbotdm(
        self,
        ctx: commands.Context,
        user: discord.User,
        message: str,
        tag: str = "general",
    ):
        if not self._is_ownerbot_operator(ctx.author):
            return await self._safe_ctx_send(
                ctx,
                "คำสั่งนี้ให้ใช้ได้เฉพาะ OwnerBOT เท่านั้น",
                ephemeral=True,
            )
        if user is None:
            return await self._safe_ctx_send(ctx, "User not found.", ephemeral=True)
        if bool(getattr(user, "bot", False)):
            return await self._safe_ctx_send(ctx, "Please target a real user, not a bot.", ephemeral=True)

        outbound_text = self._truncate_text(str(message or "").strip(), 1800)
        if not outbound_text:
            return await self._safe_ctx_send(ctx, "Please provide a message to send.", ephemeral=True)

        await self._safe_ctx_defer(ctx, ephemeral=True)

        normalized_tag = str(tag or "general").strip().lower()[:24] or "general"
        opener_id = _safe_int(getattr(ctx.author, "id", 0), 0)
        opener_name = str(getattr(ctx.author, "display_name", getattr(ctx.author, "name", "OwnerBOT")) or "OwnerBOT")
        issue_text = self._truncate_text(
            (
                f"OwnerBOT initiated support outreach\n"
                f"Initiated by: {opener_name} ({opener_id})\n\n"
                f"Initial outbound message:\n{outbound_text}"
            ),
            900,
        )

        support_thread, ticket_id, error_message, _ = await self._create_support_ticket_from_dm(
            actor=user,
            issue_text=issue_text,
            normalized_tag=normalized_tag,
            origin_guild_id=_safe_int(getattr(getattr(ctx, "guild", None), "id", 0), 0),
        )
        if error_message:
            return await self._safe_ctx_send(ctx, error_message, ephemeral=True)
        if support_thread is None:
            return await self._safe_ctx_send(ctx, "Failed to open DM support ticket.", ephemeral=True)

        ticket_row = await self._get_support_ticket_by_id(ticket_id)
        if isinstance(ticket_row, dict):
            ticket_data = ticket_row.get("data") if isinstance(ticket_row.get("data"), dict) else {}
            ticket_data["ownerbot_initiated_by"] = opener_id
            ticket_data["ownerbot_initiated_at"] = self.ops.now_iso()
            ticket_data["ownerbot_initial_outbound"] = self._truncate_text(outbound_text, 900)
            try:
                await self.ops.update_record(ticket_id, data=ticket_data, actor_id=opener_id or _safe_int(getattr(self.bot.user, "id", 0), 0))
            except Exception:
                pass

        dm_embed = discord.Embed(
            title=self._status_prefixed_title("OWNER-OUTBOUND", f"Message from support team (Ticket #{ticket_id})"),
            description=outbound_text,
            color=color.blue,
        )
        dm_embed.add_field(
            name="OwnerBOT sender",
            value=f"{self._truncate_text(opener_name, 80)} (`{opener_id}`)",
            inline=False,
        )
        dm_embed.set_footer(text="Reply in this DM to continue with support team.")
        try:
            dm_channel = user.dm_channel or await user.create_dm()
            await dm_channel.send(embed=dm_embed, allowed_mentions=discord.AllowedMentions.none())
        except Exception as dm_error:
            dm_error_text = self._truncate_text(str(dm_error), 300) or "unknown error"
            try:
                await support_thread.send(
                    embed=discord.Embed(
                        title=self._status_prefixed_title("OWNER-OUTBOUND-FAIL", f"OwnerBOT outbound DM failed (Ticket #{ticket_id})"),
                        description=f"Target: <@{user.id}> (`{user.id}`)\nError: `{dm_error_text}`",
                        color=color.red,
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except Exception:
                pass
            return await self._safe_ctx_send(
                ctx,
                f"Ticket `#{ticket_id}` opened, but DM send failed: {dm_error_text}",
                ephemeral=True,
            )

        source_label = "OwnerBOT outbound DM"
        if getattr(ctx, "guild", None) is not None and getattr(ctx, "channel", None) is not None:
            channel_name = str(getattr(ctx.channel, "name", "channel") or "channel")
            source_label = f"{ctx.guild.name} / {channel_name}"
        try:
            log_embed = discord.Embed(
                title=self._status_prefixed_title("OWNER-OUTBOUND", f"OwnerBOT outbound message (Ticket #{ticket_id})"),
                description=(
                    f"From: <@{opener_id}> (`{opener_id}`)\n"
                    f"To: <@{user.id}> (`{user.id}`)\n"
                    f"Source: {source_label}\n\n"
                    f"{outbound_text}"
                ),
                color=color.blue,
            )
            await support_thread.send(embed=log_embed, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            pass

        await self._safe_ctx_send(
            ctx,
            f"DM sent to <@{user.id}> and support ticket `#{ticket_id}` is ready.",
            ephemeral=True,
        )

    @commands.hybrid_command(
        name="supportbotsetup",
        with_app_command=True,
        help="ตั้งค่าห้องรับตั๋วของ supportbot",
    )
    @app_commands.describe(channel="เลือกห้องซัพพอร์ต (เว้นว่างให้บอทสร้างให้อัตโนมัติ)")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def supportbotsetup(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ):
        if ctx.guild is None:
            return await self._safe_ctx_send(ctx, "This command can only be used in a server.")
        if not self._is_ownerbot_operator(ctx.author):
            return await self._safe_ctx_send(
                ctx,
                "คำสั่งนี้ให้ใช้ได้เฉพาะ OwnerBOT เท่านั้น",
                ephemeral=True,
            )

        cfg = await self._get_supportbot_config_for_guild(ctx.guild.id)
        new_cfg = dict(cfg)
        new_cfg["enabled"] = True

        support_guild_id = _safe_int(new_cfg.get("support_guild_id"), 0)
        if support_guild_id <= 0:
            default_cfg = self._default_supportbot_config()
            support_guild_id = _safe_int(default_cfg.get("support_guild_id"), 0)
            if support_guild_id > 0:
                new_cfg["support_guild_id"] = support_guild_id
        if support_guild_id <= 0:
            return await self._safe_ctx_send(
                ctx,
                "ยังไม่ได้ตั้งค่า SUPPORT_GUILD_ID สำหรับระบบ supportbot",
                ephemeral=True,
            )

        support_guild = self.bot.get_guild(support_guild_id)
        if support_guild is None:
            return await self._safe_ctx_send(
                ctx,
                f"Bot is not in support guild `{support_guild_id}`.",
                ephemeral=True,
            )
        me = support_guild.me
        if me is None:
            return await self._safe_ctx_send(ctx, "Bot is not ready.", ephemeral=True)

        selected_channel: discord.TextChannel | None = None
        auto_created = False
        if channel is not None:
            if int(channel.guild.id) != int(support_guild.id):
                return await self._safe_ctx_send(
                    ctx,
                    (
                        f"เลือกห้องได้เฉพาะใน Support Guild `{support_guild.id}` ({support_guild.name})\n"
                        "ให้ใช้คำสั่งนี้ในกิลด์ซัพพอร์ต หรือเว้นช่อง `channel` ไว้เพื่อให้บอทสร้างห้องให้อัตโนมัติ"
                    ),
                    ephemeral=True,
                )
            selected_channel = channel
        else:
            current_channel_id = _safe_int(new_cfg.get("support_channel_id"), 0)
            existing_channel = support_guild.get_channel(current_channel_id) if current_channel_id > 0 else None
            if isinstance(existing_channel, discord.TextChannel):
                selected_channel = existing_channel
            else:
                created_channel, create_error = await self._auto_create_support_hub_channel(
                    support_guild=support_guild,
                    origin_guild=ctx.guild,
                )
                if created_channel is not None:
                    selected_channel = created_channel
                    auto_created = True
                else:
                    return await self._safe_ctx_send(
                        ctx,
                        create_error or "สร้างห้องอัตโนมัติไม่สำเร็จ กรุณาระบุห้องในคำสั่ง /supportbotsetup channel:#ห้อง",
                        ephemeral=True,
                    )

        perms = selected_channel.permissions_for(me)
        if not perms.send_messages or not perms.create_public_threads:
            return await self._safe_ctx_send(
                ctx,
                "Bot needs Send Messages and Create Public Threads in the support channel.",
                ephemeral=True,
            )

        archive_channel, archive_error, archive_created = await self._ensure_support_archive_channel(
            origin_guild=ctx.guild,
            support_guild=support_guild,
            cfg=new_cfg,
        )
        if archive_channel is None:
            return await self._safe_ctx_send(
                ctx,
                archive_error or "Unable to prepare archive channel for deleted tickets.",
                ephemeral=True,
            )

        new_cfg["support_channel_id"] = int(selected_channel.id)
        new_cfg["archive_channel_id"] = int(archive_channel.id)
        new_cfg["archive_category_id"] = _safe_int(getattr(archive_channel, "category_id", 0), 0)
        new_cfg["updated_at"] = self.ops.now_iso()
        await self.ops.set_config_data(ctx.guild.id, self._supportbot_config_key, new_cfg)

        embed = discord.Embed(
            title="คำสั่งสำหรับใช้งานในระบบ",
            description=(
                f"Enabled: `{bool(new_cfg.get('enabled', True))}`\n"
                f"Support Guild: `{support_guild_id}` ({support_guild.name})\n"
                f"Support Channel: <#{selected_channel.id}>\n"
                f"Archive Category: `{_safe_int(new_cfg.get('archive_category_id'), 0)}`\n"
                f"Archive Channel: <#{archive_channel.id}>\n"
                f"Auto Created Hub: `{'yes' if auto_created else 'no'}`\n"
                f"Auto Created Archive: `{'yes' if archive_created else 'no'}`"
            ),
            color=color.green,
        )
        embed.set_footer(text="Users in this guild can now open tickets with /supportbot")
        await self._safe_ctx_send(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_group(
        name="event",
        with_app_command=True,
        invoke_without_command=True,
        help="สร้างและติดตามกิจกรรมชุมชน",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def event_group(self, ctx: commands.Context):
        await ctx.send("`/event create`, `/event checkin`, `/event recap`")

    @event_group.command(name="create", help="สร้างบันทึกกิจกรรมใหม่")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def event_create(self, ctx: commands.Context, title: str, when: str, capacity: int = 0):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        row = await self.ops.create_record(
            guild_id=ctx.guild.id,
            kind="event",
            status="scheduled",
            actor_id=ctx.author.id,
            data={
                "title": str(title or "").strip()[:120],
                "when": str(when or "").strip()[:120],
                "capacity": max(0, int(capacity)),
                "created_by": int(ctx.author.id),
                "created_at": self.ops.now_iso(),
                "attendees": [],
            },
        )
        await ctx.send(
            embed=discord.Embed(
                title=f"Event #{row['id']}",
                description=f"{title}\nWhen: {when}\nCapacity: {capacity if capacity > 0 else 'Unlimited'}",
                color=color.green,
            )
        )

    @event_group.command(name="checkin", help="เช็กอินเข้าร่วมกิจกรรม")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def event_checkin(self, ctx: commands.Context, event_id: int):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        row = await self.ops.get_record(guild_id=ctx.guild.id, kind="event", record_id=event_id)
        if not row:
            return await ctx.send("Event not found.")
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        attendees = [int(item) for item in list(data.get("attendees") or []) if _safe_int(item, 0) > 0]
        if int(ctx.author.id) in attendees:
            return await ctx.send("You are already checked in.")
        cap = max(0, _safe_int(data.get("capacity"), 0))
        if cap > 0 and len(attendees) >= cap:
            return await ctx.send("Event is full.")
        attendees.append(int(ctx.author.id))
        data["attendees"] = attendees
        data["last_checkin_at"] = self.ops.now_iso()
        await self.ops.update_record(row["id"], data=data)
        await ctx.send(embed=discord.Embed(description=f"Checked in to event `#{row['id']}`.", color=color.green))

    @event_group.command(name="recap", help="แสดงสรุปกิจกรรมและผู้เข้าร่วม")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def event_recap(self, ctx: commands.Context, event_id: int):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        row = await self.ops.get_record(guild_id=ctx.guild.id, kind="event", record_id=event_id)
        if not row:
            return await ctx.send("Event not found.")
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        attendees = [int(item) for item in list(data.get("attendees") or []) if _safe_int(item, 0) > 0]
        members = "\n".join(f"- <@{uid}>" for uid in attendees[:25]) or "-"
        await ctx.send(
            embed=discord.Embed(
                title=f"Event Recap #{row['id']}",
                description=f"Title: {data.get('title', '-')}\nWhen: {data.get('when', '-')}\nCheck-ins: {len(attendees)}",
                color=color.blue,
            ).add_field(name="Attendees", value=members[:1024], inline=False)
        )

    @commands.hybrid_group(
        name="trust",
        with_app_command=True,
        invoke_without_command=True,
        help="จัดการคะแนนความน่าเชื่อถือและกฎ Trust",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def trust_group(self, ctx: commands.Context):
        await ctx.send("`/trust profile`, `/trust rules`")

    @trust_group.command(name="profile", help="แสดงโปรไฟล์ความน่าเชื่อถือของสมาชิก")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def trust_profile(self, ctx: commands.Context, member: discord.Member | None = None):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        target = member or ctx.author
        profile = await self.ops.get_trust_profile(ctx.guild.id, target.id)
        data = profile.get("data") if isinstance(profile.get("data"), dict) else {}
        await ctx.send(
            embed=discord.Embed(
                title=f"Trust Profile: {target.display_name}",
                description=f"Score: **{_safe_int(data.get('score'), 0)}**\nTier: **{str(data.get('tier') or 'new').upper()}**",
                color=color.blue,
            )
        )

    @trust_group.command(name="rules", help="ตั้งค่าเกณฑ์ Trust และรางวัลยศ")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def trust_rules(
        self,
        ctx: commands.Context,
        enabled: bool | None = None,
        silver_threshold: int | None = None,
        gold_threshold: int | None = None,
        silver_role: discord.Role | None = None,
        gold_role: discord.Role | None = None,
        message_gain: int | None = None,
    ):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        patch: dict[str, Any] = {}
        if enabled is not None:
            patch["enabled"] = bool(enabled)
        if silver_threshold is not None:
            patch["silver_threshold"] = int(silver_threshold)
        if gold_threshold is not None:
            patch["gold_threshold"] = int(gold_threshold)
        if silver_role is not None:
            patch["silver_role_id"] = int(silver_role.id)
        if gold_role is not None:
            patch["gold_role_id"] = int(gold_role.id)
        if message_gain is not None:
            patch["message_gain"] = int(message_gain)
        rules = await self.ops.set_trust_rules(ctx.guild.id, patch) if patch else await self.ops.get_trust_rules(ctx.guild.id)
        silver_role_id = _safe_int(rules.get("silver_role_id"), 0)
        gold_role_id = _safe_int(rules.get("gold_role_id"), 0)
        silver_role = f"<@&{silver_role_id}>" if silver_role_id else "-"
        gold_role = f"<@&{gold_role_id}>" if gold_role_id else "-"
        await ctx.send(
            embed=discord.Embed(
                title="คำสั่งสำหรับใช้งานในระบบ",
                description=(
                    f"Enabled: {bool(rules.get('enabled', True))}\n"
                    f"Silver threshold: {_safe_int(rules.get('silver_threshold'), 30)}\n"
                    f"Gold threshold: {_safe_int(rules.get('gold_threshold'), 70)}\n"
                    f"Silver role: {silver_role}\n"
                    f"Gold role: {gold_role}\n"
                    f"Message gain: {_safe_int(rules.get('message_gain'), 1)}"
                ),
                color=color.green,
            )
        )

    @commands.hybrid_group(
        name="health",
        with_app_command=True,
        invoke_without_command=True,
        help="ดูตัวชี้วัดสุขภาพชุมชน",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def health_group(self, ctx: commands.Context):
        await ctx.send("`/health daily`, `/health weekly`")

    @health_group.command(name="daily", help="แสดงตัวชี้วัดรายวัน")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def health_daily(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        summary = await self.ops.get_health_summary(ctx.guild.id, days=1)
        totals = summary.get("totals") if isinstance(summary.get("totals"), dict) else {}
        if not totals:
            return await ctx.send("No health data yet for today.")
        lines = [f"- **{k}**: {int(v)}" for k, v in sorted(totals.items())]
        await ctx.send(embed=discord.Embed(title="คำสั่งสำหรับใช้งานในระบบ", description="\n".join(lines), color=color.blue))

    @health_group.command(name="weekly", help="แสดงตัวชี้วัดรายสัปดาห์")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def health_weekly(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        summary = await self.ops.get_health_summary(ctx.guild.id, days=7)
        totals = summary.get("totals") if isinstance(summary.get("totals"), dict) else {}
        if not totals:
            return await ctx.send("No health data yet for this week.")
        lines = [f"- **{k}**: {int(v)}" for k, v in sorted(totals.items())]
        await ctx.send(embed=discord.Embed(title="คำสั่งสำหรับใช้งานในระบบ", description="\n".join(lines), color=color.blue))

    @commands.hybrid_group(
        name="partner",
        with_app_command=True,
        invoke_without_command=True,
        help="จัดการบันทึก onboarding พาร์ตเนอร์",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def partner_group(self, ctx: commands.Context):
        await ctx.send("`/partner onboard`")

    @partner_group.command(name="onboard", help="สร้างบันทึก onboarding พาร์ตเนอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def partner_onboard(self, ctx: commands.Context, name: str, contact: str, tier: str = "community"):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        row = await self.ops.create_record(
            guild_id=ctx.guild.id,
            kind="partner",
            status="active",
            actor_id=ctx.author.id,
            data={
                "name": str(name or "").strip()[:120],
                "contact": str(contact or "").strip()[:150],
                "tier": str(tier or "community").strip()[:60],
                "onboarded_at": self.ops.now_iso(),
                "owner_id": int(ctx.author.id),
            },
        )
        await ctx.send(embed=discord.Embed(description=f"Partner onboarded: `#{row['id']}`", color=color.green))

    @commands.hybrid_group(
        name="sponsor",
        with_app_command=True,
        invoke_without_command=True,
        help="จัดการการจองสล็อตผู้สนับสนุน",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def sponsor_group(self, ctx: commands.Context):
        await ctx.send("`/sponsor slot`")

    @sponsor_group.command(name="slot", help="สร้างสล็อตผู้สนับสนุนสำหรับพาร์ตเนอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def sponsor_slot(self, ctx: commands.Context, slot_name: str, partner_id: int, value: str = ""):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        partner_row = await self.ops.get_record(guild_id=ctx.guild.id, kind="partner", record_id=partner_id)
        if not partner_row:
            return await ctx.send("Partner not found.")
        row = await self.ops.create_record(
            guild_id=ctx.guild.id,
            kind="sponsor_slot",
            status="reserved",
            actor_id=ctx.author.id,
            reference_id=int(partner_id),
            data={
                "slot_name": str(slot_name or "").strip()[:80],
                "partner_id": int(partner_id),
                "value": str(value or "").strip()[:120],
                "assigned_at": self.ops.now_iso(),
            },
        )
        await ctx.send(embed=discord.Embed(description=f"Sponsor slot created: `#{row['id']}`", color=color.green))

    @commands.hybrid_group(
        name="crm",
        with_app_command=True,
        invoke_without_command=True,
        help="จัดการบันทึก CRM ของพาร์ตเนอร์",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def crm_group(self, ctx: commands.Context):
        await ctx.send("`/crm note`")

    @crm_group.command(name="note", help="เพิ่มบันทึก CRM ให้พาร์ตเนอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def crm_note(self, ctx: commands.Context, partner_id: int, note: str):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        if not await self._require_manage_guild(ctx):
            return
        partner_row = await self.ops.get_record(guild_id=ctx.guild.id, kind="partner", record_id=partner_id)
        if not partner_row:
            return await ctx.send("Partner not found.")
        row = await self.ops.create_record(
            guild_id=ctx.guild.id,
            kind="crm_note",
            status="active",
            actor_id=ctx.author.id,
            reference_id=int(partner_id),
            data={
                "partner_id": int(partner_id),
                "note": str(note or "").strip()[:1800],
                "created_at": self.ops.now_iso(),
            },
        )
        await ctx.send(embed=discord.Embed(description=f"CRM note saved: `#{row['id']}`", color=color.green))
