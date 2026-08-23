from __future__ import annotations

import asyncio
import datetime
import uuid
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import storage.activity_panels as activity_panels_db
import storage.activity_join_requests as activity_join_requests_db
import storage.activity_sessions as activity_sessions_db
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _as_utc_datetime(raw_value: Any) -> datetime.datetime | None:
    if not raw_value:
        return None
    if isinstance(raw_value, datetime.datetime):
        return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0, minimum: int = 0, maximum: int = 9999) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = int(default)
    return max(minimum, min(maximum, parsed))


def _safe_text(value: Any, default: str = "", maximum: int = 120) -> str:
    text = " ".join(str(value or default).strip().split())
    return text[:maximum]


class ActivityOwnerApprovalView(discord.ui.View):
    def __init__(self, cog: "Activity", request_token: str):
        super().__init__(timeout=600)
        self.cog = cog
        self.request_token = request_token

    @discord.ui.button(label="อนุมัติ", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.handle_join_approval(interaction, self.request_token, approve=True)

    @discord.ui.button(label="ปฏิเสธ", style=discord.ButtonStyle.danger)
    async def deny_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.handle_join_approval(interaction, self.request_token, approve=False)


class ActivityJoinOwnerSelect(discord.ui.Select):
    def __init__(self, cog: "Activity", options: list[discord.SelectOption]):
        super().__init__(
            placeholder="เลือกผู้สร้างกิจกรรมที่ต้องการขอเข้าร่วม",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        owner_id_text = str(self.values[0] if self.values else "").strip()
        await self.cog.request_join_by_user_id(interaction, owner_id_text, from_select=True)


class ActivityJoinPickerView(discord.ui.View):
    def __init__(self, cog: "Activity", options: list[discord.SelectOption]) -> None:
        super().__init__(timeout=120)
        self.add_item(ActivityJoinOwnerSelect(cog, options))


class ActivityRequestsTargetSelect(discord.ui.Select):
    def __init__(self, cog: "Activity", owner_id: int, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="เลือกคำขอรายคนที่ต้องการจัดการ",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.cog = cog
        self.owner_id = int(owner_id)

    async def callback(self, interaction: discord.Interaction) -> None:
        request_token = str(self.values[0] if self.values else "").strip()
        await self.cog.present_single_request_actions(interaction, self.owner_id, request_token)


class ActivityRequestsManageView(discord.ui.View):
    def __init__(self, cog: "Activity", guild_id: int, owner_id: int, options: list[discord.SelectOption]):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = int(guild_id)
        self.owner_id = int(owner_id)
        if options:
            self.add_item(ActivityRequestsTargetSelect(cog, owner_id, options))

    @discord.ui.button(label="อนุมัติทั้งหมด", style=discord.ButtonStyle.success)
    async def approve_all_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.handle_requests_bulk_action(
            interaction,
            owner_id=self.owner_id,
            guild_id=self.guild_id,
            approve=True,
        )

    @discord.ui.button(label="ปฏิเสธทั้งหมด", style=discord.ButtonStyle.danger)
    async def deny_all_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.handle_requests_bulk_action(
            interaction,
            owner_id=self.owner_id,
            guild_id=self.guild_id,
            approve=False,
        )

    @discord.ui.button(label="รีเฟรช", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.present_owner_requests(interaction, owner_id=self.owner_id, guild_id=self.guild_id, force_send=False)


class ActivitySingleRequestActionView(discord.ui.View):
    def __init__(self, cog: "Activity", owner_id: int, request_token: str):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = int(owner_id)
        self.request_token = str(request_token)

    @discord.ui.button(label="อนุมัติรายคน", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.handle_single_request_action(
            interaction,
            owner_id=self.owner_id,
            request_token=self.request_token,
            approve=True,
        )

    @discord.ui.button(label="ปฏิเสธรายคน", style=discord.ButtonStyle.danger)
    async def deny_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.handle_single_request_action(
            interaction,
            owner_id=self.owner_id,
            request_token=self.request_token,
            approve=False,
        )


class ActivityPanelView(discord.ui.View):
    def __init__(self, cog: "Activity") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="รีเฟรช", style=discord.ButtonStyle.secondary, custom_id="activity:refresh")
    async def refresh_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=False)
        ok = await self.cog.render_panel_for_guild(interaction.guild_id or 0)
        if ok:
            await interaction.followup.send("รีเฟรช Activity Panel แล้ว", ephemeral=True)
        else:
            await interaction.followup.send("ไม่พบ Activity Panel ของเซิร์ฟเวอร์นี้", ephemeral=True)

    @discord.ui.button(label="ขอเข้าร่วม", style=discord.ButtonStyle.primary, custom_id="activity:join")
    async def join_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.cog.present_join_owner_picker(interaction)

    @discord.ui.button(label="ออกจากปาร์ตี้", style=discord.ButtonStyle.danger, custom_id="activity:leave")
    async def leave_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not interaction.guild_id or not interaction.user:
            await interaction.response.send_message("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        await activity_sessions_db.delete(guild_id=int(interaction.guild_id), user_id=int(interaction.user.id))
        await self.cog.render_panel_for_guild(interaction.guild_id)
        await interaction.response.send_message("ออกจาก Activity แล้ว", ephemeral=True)


class Activity(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._panel_loop_task: asyncio.Task | None = None
        self._panel_view = ActivityPanelView(self)
        self.bot.add_view(self._panel_view)
        self._panel_loop_task = asyncio.create_task(self._panel_refresh_loop())

    def cog_unload(self):
        if self._panel_loop_task and not self._panel_loop_task.done():
            self._panel_loop_task.cancel()

    async def _panel_refresh_loop(self):
        while not self.bot.is_closed():
            try:
                await self.cleanup_expired_sessions()
                await self.cleanup_expired_join_requests()
                panel_rows = await activity_panels_db.get_all()
                for row in list(panel_rows or []):
                    if not isinstance(row, dict):
                        continue
                    await self.render_panel_for_guild(int(row.get("guild_id") or 0))
            except Exception:
                logger.error(f"Activity panel refresh loop error: {__file__}")
            await asyncio.sleep(30)

    async def cleanup_expired_sessions(self) -> None:
        rows = await activity_sessions_db.get_all()
        now = _utc_now()
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            expires_at = _as_utc_datetime(row.get("expires_at"))
            if expires_at and now >= expires_at:
                await activity_sessions_db.delete(id=int(row.get("id") or 0))

    async def cleanup_expired_join_requests(self) -> None:
        rows = await activity_join_requests_db.gets(status="pending")
        now = _utc_now()
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            expires_at = _as_utc_datetime(row.get("expires_at"))
            if expires_at and now >= expires_at:
                await activity_join_requests_db.update(
                    id=int(row.get("id") or 0),
                    status="expired",
                    updated_at=now.isoformat(),
                )

    async def _session_rows(self, guild_id: int) -> list[dict[str, Any]]:
        rows = await activity_sessions_db.gets(guild_id=int(guild_id))
        now = _utc_now()
        valid: list[dict[str, Any]] = []
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            expires_at = _as_utc_datetime(row.get("expires_at"))
            if expires_at and now >= expires_at:
                await activity_sessions_db.delete(id=int(row.get("id") or 0))
                continue
            valid.append(dict(row))
        valid.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return valid

    def _build_panel_embed(self, guild: discord.Guild, rows: list[dict[str, Any]]) -> discord.Embed:
        embed = discord.Embed(
            title="Live Activity Card",
            description="แสดงสถานะกิจกรรมล่าสุดของสมาชิกในเซิร์ฟเวอร์",
            color=color.blue,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if not rows:
            embed.add_field(
                name="ยังไม่มีกิจกรรม",
                value="ให้สมาชิกใช้ `/activity set` เพื่อแสดงสถานะกิจกรรม",
                inline=False,
            )
        else:
            for row in rows[:12]:
                user_id = int(row.get("user_id") or 0)
                game = _safe_text(row.get("game"), "Unknown", 80)
                details = _safe_text(row.get("details"), "-", 120)
                state = _safe_text(row.get("state"), "-", 120)
                party_size = _safe_int(row.get("party_size"), 1, 1, 99)
                party_max = _safe_int(row.get("party_max"), 1, 1, 99)
                join_enabled = bool(row.get("join_enabled", True))
                join_text = "เปิด" if join_enabled else "ปิด"
                embed.add_field(
                    name=f"{game} โดย <@{user_id}>",
                    value=(
                        f"details: `{details}`\n"
                        f"state: `{state}`\n"
                        f"party: `{party_size}/{party_max}` | join: `{join_text}`\n"
                        f"owner_id: `{user_id}`"
                    ),
                    inline=False,
                )

        embed.set_footer(text=f"Updated {_utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return embed

    async def render_panel_for_guild(self, guild_id: int) -> bool:
        if guild_id <= 0:
            return False
        row = await activity_panels_db.get(guild_id=int(guild_id))
        if not row:
            return False
        channel_id = int(row.get("channel_id") or 0)
        message_id = int(row.get("message_id") or 0)
        if channel_id <= 0 or message_id <= 0:
            return False
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return False
        guild = channel.guild
        rows = await self._session_rows(guild.id)
        embed = self._build_panel_embed(guild, rows)
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=embed, view=self._panel_view)
            await activity_panels_db.update(id=int(row.get("id") or 0), updated_at=_utc_now().isoformat())
            return True
        except Exception:
            return False

    async def _owner_request_rows(self, guild_id: int, owner_id: int) -> list[dict[str, Any]]:
        rows = await activity_join_requests_db.gets(guild_id=int(guild_id), owner_id=int(owner_id))
        payload = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
        payload.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return payload

    def _build_owner_requests_embed(
        self,
        guild: discord.Guild,
        owner_id: int,
        rows: list[dict[str, Any]],
        *,
        view_filter: str = "all",
    ) -> discord.Embed:
        pending_rows = [row for row in rows if str(row.get("status") or "").strip().lower() == "pending"]
        recent_rows = rows[:10]
        filter_key = str(view_filter or "all").strip().lower()
        if filter_key not in {"all", "pending", "recent"}:
            filter_key = "all"
        embed = discord.Embed(
            title="Activity Requests Center",
            description=f"คำขอเข้าร่วมของ <@{int(owner_id)}> ในเซิร์ฟเวอร์ `{guild.name}`",
            color=color.blue,
        )
        embed.add_field(
            name="สรุป",
            value=f"pending: `{len(pending_rows)}` | recent: `{len(recent_rows)}`",
            inline=False,
        )

        if filter_key in {"all", "pending"} and pending_rows:
            lines: list[str] = []
            for row in pending_rows[:10]:
                requester_id = int(row.get("requester_id") or 0)
                token = str(row.get("request_token") or "")
                expires_at = _as_utc_datetime(row.get("expires_at"))
                expires_text = (
                    expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                    if isinstance(expires_at, datetime.datetime)
                    else "-"
                )
                lines.append(
                    f"• <@{requester_id}> | token `{token[:8]}` | หมดอายุ `{expires_text}`"
                )
            embed.add_field(name="Pending", value="\n".join(lines), inline=False)
        elif filter_key in {"all", "pending"}:
            embed.add_field(name="Pending", value="ไม่มีคำขอค้าง", inline=False)

        if filter_key in {"all", "recent"} and recent_rows:
            lines = []
            for row in recent_rows:
                requester_id = int(row.get("requester_id") or 0)
                status = str(row.get("status") or "unknown").strip().lower()
                created_at = _as_utc_datetime(row.get("created_at"))
                created_text = (
                    created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                    if isinstance(created_at, datetime.datetime)
                    else "-"
                )
                lines.append(f"• <@{requester_id}> | `{status}` | `{created_text}`")
            embed.add_field(name="Recent", value="\n".join(lines[:10]), inline=False)
        elif filter_key in {"all", "recent"}:
            embed.add_field(name="Recent", value="ยังไม่มีรายการล่าสุด", inline=False)
        embed.set_footer(text=f"ตัวกรอง: {filter_key} | ใช้ปุ่มด้านล่างเพื่ออนุมัติ/ปฏิเสธทั้งหมด หรือเลือกจัดการรายคน")
        return embed

    def _pending_options_from_rows(self, rows: list[dict[str, Any]]) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        for row in rows:
            status = str(row.get("status") or "").strip().lower()
            if status != "pending":
                continue
            requester_id = int(row.get("requester_id") or 0)
            token = str(row.get("request_token") or "").strip()
            if not token:
                continue
            options.append(
                discord.SelectOption(
                    label=f"Requester {requester_id}"[:100],
                    value=token,
                    description=f"token: {token[:16]}"[:100],
                )
            )
            if len(options) >= 25:
                break
        return options

    async def present_owner_requests(
        self,
        interaction: discord.Interaction,
        *,
        owner_id: int,
        guild_id: int,
        force_send: bool,
    ) -> None:
        if int(getattr(interaction.user, "id", 0) or 0) != int(owner_id):
            await interaction.response.send_message("คุณไม่มีสิทธิ์ดูคำขอนี้", ephemeral=True)
            return
        guild = interaction.guild or self.bot.get_guild(int(guild_id))
        if not guild:
            await interaction.response.send_message("ไม่พบเซิร์ฟเวอร์", ephemeral=True)
            return
        await self.cleanup_expired_join_requests()
        rows = await self._owner_request_rows(int(guild_id), int(owner_id))
        embed = self._build_owner_requests_embed(guild, int(owner_id), rows)
        options = self._pending_options_from_rows(rows)
        view = ActivityRequestsManageView(self, int(guild_id), int(owner_id), options)

        if force_send:
            send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
            await send(embed=embed, view=view, ephemeral=True)
            return

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def present_single_request_actions(
        self,
        interaction: discord.Interaction,
        owner_id: int,
        request_token: str,
    ) -> None:
        if int(getattr(interaction.user, "id", 0) or 0) != int(owner_id):
            await interaction.response.send_message("คุณไม่มีสิทธิ์จัดการคำขอนี้", ephemeral=True)
            return
        row = await activity_join_requests_db.get(request_token=str(request_token))
        if not row:
            await interaction.response.send_message("ไม่พบคำขอที่เลือก", ephemeral=True)
            return
        status = str(row.get("status") or "").strip().lower()
        requester_id = int(row.get("requester_id") or 0)
        embed = discord.Embed(
            title="จัดการคำขอรายคน",
            description=(
                f"requester: <@{requester_id}>\n"
                f"status: `{status}`\n"
                f"token: `{str(request_token)[:20]}`"
            ),
            color=color.orange if status == "pending" else color.blue,
        )
        if status != "pending":
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.send_message(
            embed=embed,
            view=ActivitySingleRequestActionView(self, int(owner_id), str(request_token)),
            ephemeral=True,
        )

    async def _apply_request_decision(
        self,
        *,
        request_row: dict[str, Any],
        approve: bool,
    ) -> tuple[bool, str]:
        status = str(request_row.get("status") or "").strip().lower()
        if status != "pending":
            return False, "skipped_non_pending"
        expires_at = _as_utc_datetime(request_row.get("expires_at"))
        now = _utc_now()
        if expires_at and now >= expires_at:
            await activity_join_requests_db.update(
                id=int(request_row.get("id") or 0),
                status="expired",
                updated_at=now.isoformat(),
            )
            return False, "expired"

        owner_id = int(request_row.get("owner_id") or 0)
        requester_id = int(request_row.get("requester_id") or 0)
        guild_id = int(request_row.get("guild_id") or 0)
        requester_user = self.bot.get_user(requester_id) or await self.bot.fetch_user(requester_id)

        if not approve:
            await activity_join_requests_db.update(
                id=int(request_row.get("id") or 0),
                status="denied",
                updated_at=now.isoformat(),
            )
            try:
                await requester_user.send("คำขอเข้าร่วมกิจกรรมของคุณถูกปฏิเสธโดยผู้จัดกิจกรรม")
            except Exception:
                pass
            return True, "denied"

        session = await activity_sessions_db.get(guild_id=guild_id, user_id=owner_id)
        if not session:
            await activity_join_requests_db.update(
                id=int(request_row.get("id") or 0),
                status="invalid_session",
                updated_at=now.isoformat(),
            )
            return False, "invalid_session"
        if not bool(session.get("join_enabled", True)):
            await activity_join_requests_db.update(
                id=int(request_row.get("id") or 0),
                status="owner_closed",
                updated_at=now.isoformat(),
            )
            return False, "owner_closed"

        party_size = _safe_int(session.get("party_size"), 1, 1, 99)
        party_max = _safe_int(session.get("party_max"), 1, 1, 99)
        if party_size >= party_max:
            await activity_join_requests_db.update(
                id=int(request_row.get("id") or 0),
                status="party_full",
                updated_at=now.isoformat(),
            )
            try:
                await requester_user.send("คำขอเข้าร่วมไม่สำเร็จ เนื่องจากปาร์ตี้เต็มแล้ว")
            except Exception:
                pass
            return False, "party_full"

        await activity_sessions_db.update(
            id=int(session.get("id") or 0),
            party_size=int(party_size + 1),
            updated_at=now.isoformat(),
        )
        await activity_join_requests_db.update(
            id=int(request_row.get("id") or 0),
            status="approved",
            updated_at=now.isoformat(),
        )
        await self.render_panel_for_guild(guild_id)
        try:
            await requester_user.send("คำขอเข้าร่วมกิจกรรมของคุณได้รับการอนุมัติแล้ว")
        except Exception:
            pass
        return True, "approved"

    async def handle_single_request_action(
        self,
        interaction: discord.Interaction,
        *,
        owner_id: int,
        request_token: str,
        approve: bool,
    ) -> None:
        if int(getattr(interaction.user, "id", 0) or 0) != int(owner_id):
            await interaction.response.send_message("คุณไม่มีสิทธิ์จัดการคำขอนี้", ephemeral=True)
            return
        row = await activity_join_requests_db.get(request_token=str(request_token))
        if not row:
            await interaction.response.send_message("ไม่พบคำขอที่เลือก", ephemeral=True)
            return
        ok, reason = await self._apply_request_decision(request_row=row, approve=approve)
        action_text = "อนุมัติ" if approve else "ปฏิเสธ"
        if ok:
            await interaction.response.send_message(f"{action_text}รายคนเรียบร้อย", ephemeral=True)
        else:
            await interaction.response.send_message(f"{action_text}ไม่สำเร็จ: `{reason}`", ephemeral=True)

    async def handle_requests_bulk_action(
        self,
        interaction: discord.Interaction,
        *,
        owner_id: int,
        guild_id: int,
        approve: bool,
    ) -> None:
        if int(getattr(interaction.user, "id", 0) or 0) != int(owner_id):
            await interaction.response.send_message("คุณไม่มีสิทธิ์จัดการคำขอนี้", ephemeral=True)
            return
        await self.cleanup_expired_join_requests()
        rows = await self._owner_request_rows(int(guild_id), int(owner_id))
        pending_rows = [row for row in rows if str(row.get("status") or "").strip().lower() == "pending"]
        if not pending_rows:
            await interaction.response.send_message("ไม่มีคำขอค้างให้จัดการ", ephemeral=True)
            return
        success_count = 0
        failed_count = 0
        for row in pending_rows:
            ok, _ = await self._apply_request_decision(request_row=row, approve=approve)
            if ok:
                success_count += 1
            else:
                failed_count += 1
        action_text = "อนุมัติ" if approve else "ปฏิเสธ"
        await interaction.response.send_message(
            f"{action_text}ทั้งหมดเสร็จแล้ว: สำเร็จ `{success_count}` | ไม่สำเร็จ `{failed_count}`",
            ephemeral=True,
        )

    async def _owner_options_for_guild(self, guild: discord.Guild, requester_id: int) -> list[discord.SelectOption]:
        rows = await self._session_rows(guild.id)
        options: list[discord.SelectOption] = []
        for row in rows:
            owner_id = int(row.get("user_id") or 0)
            if owner_id <= 0 or owner_id == requester_id:
                continue
            if not bool(row.get("join_enabled", True)):
                continue
            owner_member = guild.get_member(owner_id)
            owner_name = owner_member.display_name if owner_member else f"User {owner_id}"
            game = _safe_text(row.get("game"), "Unknown", 60)
            state = _safe_text(row.get("state"), "-", 70)
            options.append(
                discord.SelectOption(
                    label=f"{owner_name} - {game}"[:100],
                    value=str(owner_id),
                    description=f"สถานะ: {state}"[:100],
                )
            )
            if len(options) >= 25:
                break
        return options

    async def present_join_owner_picker(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        options = await self._owner_options_for_guild(interaction.guild, int(interaction.user.id))
        if not options:
            await interaction.response.send_message("ไม่พบกิจกรรมที่เปิดให้ขอเข้าร่วมตอนนี้", ephemeral=True)
            return
        await interaction.response.send_message(
            "เลือกผู้จัดกิจกรรมที่ต้องการขอเข้าร่วม",
            view=ActivityJoinPickerView(self, options),
            ephemeral=True,
        )

    async def request_join_by_user_id(
        self,
        interaction: discord.Interaction,
        user_id_text: str,
        *,
        from_select: bool = False,
    ) -> None:
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        if not interaction.guild_id or not interaction.user:
            await send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        if not user_id_text.isdigit():
            await send("User ID ไม่ถูกต้อง", ephemeral=True)
            return

        owner_id = int(user_id_text)
        if owner_id == int(interaction.user.id):
            await send("คุณเป็นเจ้าของกิจกรรมนี้อยู่แล้ว", ephemeral=True)
            return

        session = await activity_sessions_db.get(guild_id=int(interaction.guild_id), user_id=owner_id)
        if not session:
            await send("ไม่พบกิจกรรมของผู้ใช้ที่เลือก", ephemeral=True)
            return
        if not bool(session.get("join_enabled", True)):
            await send("เจ้าของกิจกรรมปิดการขอเข้าร่วมไว้", ephemeral=True)
            return

        owner_user = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
        request_token = str(uuid.uuid4())
        now = _utc_now()
        await activity_join_requests_db.insert(
            request_token=request_token,
            guild_id=int(interaction.guild_id),
            owner_id=int(owner_id),
            requester_id=int(interaction.user.id),
            status="pending",
            expires_at=(now + datetime.timedelta(minutes=10)).isoformat(),
            updated_at=now.isoformat(),
            created_at=now.isoformat(),
        )

        guild_name = interaction.guild.name if interaction.guild else str(interaction.guild_id)
        dm_embed = discord.Embed(
            title="คำขอเข้าร่วมกิจกรรม",
            description=(
                f"{interaction.user.mention} ต้องการเข้าร่วมกิจกรรมของคุณ\n"
                f"เซิร์ฟเวอร์: `{guild_name}`\n"
                f"เกม: `{_safe_text(session.get('game'), 'Unknown', 80)}`\n"
                f"รายละเอียด: `{_safe_text(session.get('details'), '-', 120)}`\n"
                f"สถานะ: `{_safe_text(session.get('state'), '-', 120)}`"
            ),
            color=color.blue,
        )

        try:
            await owner_user.send(embed=dm_embed, view=ActivityOwnerApprovalView(self, request_token))
        except Exception:
            request_row = await activity_join_requests_db.get(request_token=request_token)
            if request_row:
                await activity_join_requests_db.update(
                    id=int(request_row.get("id") or 0),
                    status="failed_dm",
                    updated_at=_utc_now().isoformat(),
                )
            await send("ส่งคำขอไม่สำเร็จ: ผู้จัดกิจกรรมปิดรับ DM หรือไม่สามารถรับข้อความได้", ephemeral=True)
            return

        response_text = "ส่งคำขอเข้าร่วมแล้ว ระบบส่ง DM ให้ผู้จัดกิจกรรมเพื่อกดอนุมัติ/ปฏิเสธเรียบร้อย"
        if from_select:
            response_text += "\nคุณจะได้รับแจ้งผลทาง DM เมื่อผู้จัดกิจกรรมตอบกลับ"
        await send(response_text, ephemeral=True)

    async def handle_join_approval(
        self,
        interaction: discord.Interaction,
        request_token: str,
        *,
        approve: bool,
    ) -> None:
        payload = await activity_join_requests_db.get(request_token=str(request_token))
        if not payload:
            await interaction.response.send_message("คำขอนี้หมดอายุหรือถูกจัดการไปแล้ว", ephemeral=True)
            return

        owner_id = int(payload.get("owner_id") or 0)
        if int(getattr(interaction.user, "id", 0) or 0) != owner_id:
            await interaction.response.send_message("คุณไม่มีสิทธิ์จัดการคำขอนี้", ephemeral=True)
            return

        ok, reason = await self._apply_request_decision(request_row=payload, approve=approve)
        action_text = "อนุมัติ" if approve else "ปฏิเสธ"
        if ok:
            await interaction.response.send_message(f"{action_text}คำขอแล้ว", ephemeral=True)
        else:
            await interaction.response.send_message(f"{action_text}ไม่สำเร็จ: `{reason}`", ephemeral=True)

    async def _upsert_session(
        self,
        *,
        guild_id: int,
        user_id: int,
        game: str,
        details: str,
        state: str,
        party_size: int,
        party_max: int,
        join_enabled: bool,
    ) -> dict[str, Any]:
        now = _utc_now()
        expires_at = (now + datetime.timedelta(hours=6)).isoformat()
        payload = {
            "guild_id": int(guild_id),
            "user_id": int(user_id),
            "game": _safe_text(game, "Unknown", 80),
            "details": _safe_text(details, "-", 120),
            "state": _safe_text(state, "-", 120),
            "party_id": str(uuid.uuid4()),
            "party_size": _safe_int(party_size, 1, 1, 99),
            "party_max": _safe_int(party_max, 1, 1, 99),
            "join_enabled": bool(join_enabled),
            "expires_at": expires_at,
            "updated_at": now.isoformat(),
        }
        existing = await activity_sessions_db.get(guild_id=int(guild_id), user_id=int(user_id))
        if existing:
            await activity_sessions_db.update(id=int(existing.get("id") or 0), **payload)
            return await activity_sessions_db.get(id=int(existing.get("id") or 0)) or payload
        return await activity_sessions_db.insert(**payload) or payload

    @commands.hybrid_group(name="activity", help="Live activity system", with_app_command=True, invoke_without_command=True)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def activity(self, ctx: commands.Context):
        await ctx.send(
            embed=discord.Embed(
                title="Activity Commands",
                description=(
                    "`/activity set` - ตั้งสถานะกิจกรรม\n"
                    "`/activity leave` - ออกจากกิจกรรม\n"
                    "`/activity panel` - สร้าง/อัปเดต live card\n"
                    "`/activity requests` - ดูและจัดการคำขอเข้าร่วม"
                ),
                color=color.green,
            )
        )

    @activity.command(name="set", help="Set your live activity")
    @app_commands.describe(
        game="ชื่อเกมหรือกิจกรรม",
        details="รายละเอียดหลัก",
        state="สถานะรอง",
        party_size="จำนวนสมาชิกปาร์ตี้ปัจจุบัน",
        party_max="จำนวนสมาชิกปาร์ตี้สูงสุด",
        join_enabled="เปิดรับคำขอเข้าร่วม",
    )
    async def activity_set(
        self,
        ctx: commands.Context,
        game: str,
        details: str = "Competitive",
        state: str = "Playing Solo",
        party_size: int = 1,
        party_max: int = 5,
        join_enabled: bool = True,
    ):
        if not ctx.guild:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", delete_after=8)
            return
        party_max = _safe_int(party_max, 5, 1, 99)
        party_size = _safe_int(party_size, 1, 1, party_max)
        row = await self._upsert_session(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            game=game,
            details=details,
            state=state,
            party_size=party_size,
            party_max=party_max,
            join_enabled=join_enabled,
        )
        await self.render_panel_for_guild(ctx.guild.id)
        await ctx.send(
            embed=discord.Embed(
                title="อัปเดตกิจกรรมแล้ว",
                description=(
                    f"game: `{row.get('game')}`\n"
                    f"details: `{row.get('details')}`\n"
                    f"state: `{row.get('state')}`\n"
                    f"party: `{row.get('party_size')}/{row.get('party_max')}`"
                ),
                color=color.green,
            )
        )

    @activity.command(name="requests", help="ดูและจัดการคำขอเข้าร่วมกิจกรรม")
    @app_commands.describe(view_filter="เลือกประเภทที่ต้องการดู")
    @app_commands.choices(
        view_filter=[
            app_commands.Choice(name="all", value="all"),
            app_commands.Choice(name="pending", value="pending"),
            app_commands.Choice(name="recent", value="recent"),
        ]
    )
    async def activity_requests(self, ctx: commands.Context, view_filter: str = "all"):
        if not ctx.guild:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", delete_after=8)
            return
        filter_key = str(view_filter or "all").strip().lower()
        if filter_key not in {"all", "pending", "recent"}:
            filter_key = "all"
        owner_id = int(ctx.author.id)
        owner_session = await activity_sessions_db.get(guild_id=int(ctx.guild.id), user_id=owner_id)
        if not owner_session:
            await ctx.send("คุณต้องมี activity ของตัวเองก่อน จึงจะจัดการคำขอได้", delete_after=10)
            return

        await self.cleanup_expired_join_requests()
        rows = await self._owner_request_rows(int(ctx.guild.id), owner_id)
        embed = self._build_owner_requests_embed(ctx.guild, owner_id, rows, view_filter=filter_key)
        options = self._pending_options_from_rows(rows)
        view = ActivityRequestsManageView(self, int(ctx.guild.id), owner_id, options)

        if ctx.interaction:
            send = (
                ctx.interaction.followup.send
                if ctx.interaction.response.is_done()
                else ctx.interaction.response.send_message
            )
            await send(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)

    @activity.command(name="leave", help="Leave your activity")
    async def activity_leave(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", delete_after=8)
            return
        await activity_sessions_db.delete(guild_id=int(ctx.guild.id), user_id=int(ctx.author.id))
        await self.render_panel_for_guild(ctx.guild.id)
        await ctx.send(embed=discord.Embed(description="ลบกิจกรรมของคุณแล้ว", color=color.orange))

    @activity.command(name="panel", help="Create or move live activity panel")
    @app_commands.describe(channel="ห้องที่ต้องการส่ง live panel")
    async def activity_panel(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        if not ctx.guild:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", delete_after=8)
            return
        if (
            not await checks.check_is_moderator_permissions(ctx, "manage_guild")
            and not checks.check_is_admin_predicate(ctx)
            and not await checks.check_is_owner(ctx)
        ):
            await ctx.send("ต้องมีสิทธิ์ Manage Server เพื่อใช้คำสั่งนี้", delete_after=8)
            return
        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("ระบุห้องข้อความเท่านั้น", delete_after=8)
            return

        rows = await self._session_rows(ctx.guild.id)
        embed = self._build_panel_embed(ctx.guild, rows)
        message = await target_channel.send(embed=embed, view=self._panel_view)

        existing = await activity_panels_db.get(guild_id=int(ctx.guild.id))
        payload = {
            "guild_id": int(ctx.guild.id),
            "channel_id": int(target_channel.id),
            "message_id": int(message.id),
            "updated_at": _utc_now().isoformat(),
        }
        if existing:
            await activity_panels_db.update(id=int(existing.get("id") or 0), **payload)
        else:
            await activity_panels_db.insert(**payload)

        await ctx.send(embed=discord.Embed(description=f"ตั้งค่า Activity Panel ที่ {target_channel.mention} แล้ว", color=color.green))


async def setup(bot: AutoShardedBot):
    await bot.add_cog(Activity(bot))
