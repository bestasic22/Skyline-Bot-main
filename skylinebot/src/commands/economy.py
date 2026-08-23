from __future__ import annotations

import datetime
import io
import random
import sys
import traceback
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

import storage.economy_audit as economy_audit_db
import storage.economy_settings as economy_settings_db
import storage.economy_wallets as economy_wallets_db
import storage.invite_stats as invite_stats_db
import storage.levels_users as levels_users_db
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageOps = None
    UnidentifiedImageError = Exception


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


_LEADERBOARD_BOARD_OPTIONS: list[tuple[str, str, str, str]] = [
    ("money", "Money", "อันดับเงินรวมในกิลด์", "💰"),
    ("level_chat", "Overall XP", "อันดับ XP จากการพิมพ์", "🏆"),
    ("level_voice", "Voice Time", "อันดับ XP จาก Voice", "🎙️"),
    ("invite", "Invite", "อันดับการเชิญสมาชิก", "📨"),
    ("user_money", "User Rank (Money)", "ดูอันดับเงินของตัวเอง", "👤"),
    ("user_level_chat", "User Rank (XP)", "ดูอันดับ XP ของตัวเอง", "🧍"),
    ("user_level_voice", "User Rank (Voice)", "ดูอันดับ Voice XP ของตัวเอง", "🗣️"),
    ("user_invite", "User Rank (Invite)", "ดูอันดับ Invite ของตัวเอง", "📌"),
]


class EconomyLeaderboardView(discord.ui.View):
    def __init__(
        self,
        cog: "Economy",
        ctx: commands.Context,
        *,
        current_board: str = "money",
        limit: int = 10,
        timeout: float = 240.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.limit = max(1, min(100, _safe_int(limit, 10)))
        self.current_board = str(current_board or "money").strip().lower()
        self.message: discord.Message | None = None
        website_root = str(
            getattr(getattr(self.cog.bot, "urls", None), "WEBSITE", "https://skylinebot.xyz")
            or "https://skylinebot.xyz"
        ).strip().rstrip("/")
        self.web_leaderboard_url = f"{website_root}/leaderboard"

        if self.web_leaderboard_url.lower().startswith(("http://", "https://")):
            self.add_item(
                discord.ui.Button(
                    label="View leaderboard",
                    style=discord.ButtonStyle.link,
                    url=self.web_leaderboard_url,
                    row=0,
                )
            )
        select = discord.ui.Select(
            placeholder="เลือกระบบ leaderboard ที่ต้องการดู",
            min_values=1,
            max_values=1,
            options=self._build_options(self.current_board),
            row=1,
        )
        select.callback = self._on_select
        self.add_item(select)
        self._select = select

    def _build_options(self, active_key: str) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        for key, label, description, emoji_text in _LEADERBOARD_BOARD_OPTIONS:
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=key,
                    description=description[:100],
                    emoji=emoji_text,
                    default=(key == active_key),
                )
            )
        return options

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.ctx.author or interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "เมนูนี้ใช้ได้เฉพาะคนที่เรียกคำสั่งนี้เท่านั้น",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

    async def _on_select(self, interaction: discord.Interaction) -> None:
        selected = str(self._select.values[0] if self._select.values else self.current_board).strip().lower()
        if selected.startswith("user_"):
            board_key = selected.replace("user_", "", 1)
            user_embed = await self.cog._build_user_rank_embed(
                guild=self.ctx.guild,
                member=self.ctx.author if isinstance(self.ctx.author, discord.Member) else None,
                board=board_key,
            )
            if user_embed is None:
                await interaction.response.send_message(
                    "ยังไม่พบข้อมูลอันดับของคุณในบอร์ดนี้",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(embed=user_embed, ephemeral=True)
            return

        self.current_board = selected
        self._select.options = self._build_options(self.current_board)
        await interaction.response.defer()
        embed, leaderboard_file = await self.cog._build_unified_leaderboard_embed(
            self.ctx,
            board=self.current_board,
            limit=self.limit,
        )
        attachments: list[discord.File] = [leaderboard_file] if leaderboard_file is not None else []
        self.message = interaction.message
        await interaction.message.edit(
            embed=embed,
            attachments=attachments,
            view=self,
        )


class Economy(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot

        class CogInfo:
            name = "Economy"
            category = "Fun"
            description = "Economy System"
            hidden = False
            emoji = bot.emoji.ECONOMY

        self.cog_info = CogInfo

    async def _ensure_settings(self, guild_id: int) -> dict[str, Any]:
        settings = await economy_settings_db.get(guild_id=guild_id)
        if settings:
            return settings
        await economy_settings_db.insert(guild_id=guild_id)
        return await economy_settings_db.get(guild_id=guild_id) or {}

    async def _ensure_wallet(
        self, guild_id: int, user_id: int, settings: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        wallet = await economy_wallets_db.get(guild_id=guild_id, user_id=user_id)
        if wallet:
            return wallet
        cfg = settings or await self._ensure_settings(guild_id)
        start_cash = max(0, _safe_int(cfg.get("start_cash"), 0))
        start_bank = max(0, _safe_int(cfg.get("start_bank"), 0))
        await economy_wallets_db.insert(
            guild_id=guild_id,
            user_id=user_id,
            cash=start_cash,
            bank=start_bank,
            total_earned=0,
            total_spent=0,
        )
        return await economy_wallets_db.get(guild_id=guild_id, user_id=user_id) or {}

    def _fmt(self, amount: int, currency_symbol: str) -> str:
        return f"{currency_symbol}{int(max(0, amount)):,}"

    async def _send_temporary_message(
        self, ctx: commands.Context, content: str, *, seconds: int = 8
    ) -> None:
        try:
            await ctx.send(content, delete_after=max(3, int(seconds)))
        except Exception:
            await ctx.send(content)

    async def _is_economy_command_channel_allowed(
        self,
        ctx: commands.Context,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        if not ctx.guild:
            return False
        cfg = settings or await self._ensure_settings(ctx.guild.id)
        if not bool(cfg.get("economy_channels_enabled")):
            return True
        if bool(cfg.get("economy_allow_all_channels")):
            return True

        raw_channels = (
            cfg.get("economy_command_channels")
            if isinstance(cfg.get("economy_command_channels"), list)
            else []
        )
        allowed_ids = {
            str(item).strip()
            for item in raw_channels
            if str(item).strip().isdigit()
        }
        if not allowed_ids:
            return False

        channel_ids = {str(ctx.channel.id)}
        parent_id = getattr(ctx.channel, "parent_id", None)
        if parent_id:
            channel_ids.add(str(parent_id))
        return bool(allowed_ids.intersection(channel_ids))

    async def cog_check(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False
        try:
            settings = await self._ensure_settings(ctx.guild.id)
            if await self._is_economy_command_channel_allowed(ctx, settings=settings):
                return True
            await self._send_temporary_message(
                ctx,
                "คำสั่ง Economy ใช้ได้เฉพาะห้องที่ตั้งค่าไว้ในแดชบอร์ด",
                seconds=10,
            )
            return False
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")
            return False

    async def _update_wallet_values(
        self,
        wallet: dict[str, Any],
        *,
        cash: int | None = None,
        bank: int | None = None,
        total_earned: int | None = None,
        total_spent: int | None = None,
        work_at: datetime.datetime | None = None,
        slut_at: datetime.datetime | None = None,
        crime_at: datetime.datetime | None = None,
        rob_at: datetime.datetime | None = None,
        chat_at: datetime.datetime | None = None,
        collect_income_at: datetime.datetime | None = None,
        collect_income_role_at: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await economy_wallets_db.update(
            id=wallet["id"],
            cash=cash if cash is not None else _safe_int(wallet.get("cash"), 0),
            bank=bank if bank is not None else _safe_int(wallet.get("bank"), 0),
            total_earned=(
                total_earned
                if total_earned is not None
                else _safe_int(wallet.get("total_earned"), 0)
            ),
            total_spent=(
                total_spent
                if total_spent is not None
                else _safe_int(wallet.get("total_spent"), 0)
            ),
            work_at=work_at if work_at is not None else wallet.get("work_at"),
            slut_at=slut_at if slut_at is not None else wallet.get("slut_at"),
            crime_at=crime_at if crime_at is not None else wallet.get("crime_at"),
            rob_at=rob_at if rob_at is not None else wallet.get("rob_at"),
            chat_at=chat_at if chat_at is not None else wallet.get("chat_at"),
            collect_income_at=(
                collect_income_at
                if collect_income_at is not None
                else wallet.get("collect_income_at")
            ),
            collect_income_role_at=(
                collect_income_role_at
                if collect_income_role_at is not None
                else (
                    wallet.get("collect_income_role_at")
                    if isinstance(wallet.get("collect_income_role_at"), dict)
                    else None
                )
            ),
            updated_at=_utc_now(),
        ) or wallet

    async def _check_income_command_enabled(
        self, ctx: commands.Context, settings: dict[str, Any], command_key: str
    ) -> bool:
        enabled = bool(settings.get(f"command_{command_key}_enabled"))
        if enabled:
            return True
        await ctx.send(f"`{command_key}` ถูกปิดใช้งานในเซิร์ฟเวอร์")
        return False

    async def _run_income_command(
        self,
        ctx: commands.Context,
        *,
        command_key: str,
        timestamp_key: str,
        action_key: str,
    ) -> None:
        settings = await self._ensure_settings(ctx.guild.id)
        if not await self._check_income_command_enabled(ctx, settings, command_key):
            return
        wallet = await self._ensure_wallet(ctx.guild.id, ctx.author.id, settings)
        symbol = str(settings.get("currency_symbol") or "฿")
        now = _utc_now()
        cooldown = max(10, _safe_int(settings.get(f"{command_key}_cooldown"), 3600))
        last_run = wallet.get(timestamp_key)
        if isinstance(last_run, datetime.datetime):
            last = (
                last_run
                if last_run.tzinfo
                else last_run.replace(tzinfo=datetime.timezone.utc)
            )
            remain = cooldown - int((now - last).total_seconds())
            if remain > 0:
                await self._send_temporary_message(
                    ctx,
                    f"คุณต้องรออีก {remain} วินาที ก่อนใช้ `{command_key}` อีกครั้ง",
                    seconds=min(max(remain, 6), 20),
                )
                return

        payout_min = max(1, _safe_int(settings.get(f"{command_key}_payout_min"), 100))
        payout_max = max(
            payout_min, _safe_int(settings.get(f"{command_key}_payout_max"), payout_min)
        )
        fail_rate = max(0, min(100, _safe_int(settings.get(f"{command_key}_fail_rate"), 0)))
        fine_type = str(settings.get(f"{command_key}_fine_type") or "fixed").lower().strip()
        fine_min = max(0, _safe_int(settings.get(f"{command_key}_fine_min"), 0))
        fine_max = max(fine_min, _safe_int(settings.get(f"{command_key}_fine_max"), fine_min))
        custom_enabled = bool(settings.get("custom_replies_enabled"))
        custom_replies = (
            settings.get(f"{command_key}_replies")
            if isinstance(settings.get(f"{command_key}_replies"), list)
            else []
        )

        cash_before = _safe_int(wallet.get("cash"), 0)
        bank_before = _safe_int(wallet.get("bank"), 0)
        earned_before = _safe_int(wallet.get("total_earned"), 0)
        spent_before = _safe_int(wallet.get("total_spent"), 0)
        max_cash = max(0, _safe_int(settings.get("max_cash"), 0))
        failed = random.randint(1, 100) <= fail_rate
        message_text = ""
        amount = 0

        update_kwargs: dict[str, Any] = {
            "cash": cash_before,
            "bank": bank_before,
            "total_earned": earned_before,
            "total_spent": spent_before,
            timestamp_key: now,
        }

        if failed:
            if fine_type == "percent":
                percent = random.randint(fine_min, fine_max)
                percent = max(0, min(100, percent))
                amount = int((cash_before * percent) / 100)
            else:
                amount = random.randint(fine_min, fine_max)
            amount = min(amount, cash_before)
            cash_after = max(0, cash_before - amount)
            update_kwargs["cash"] = cash_after
            update_kwargs["total_spent"] = spent_before + amount
            message_text = (
                f"ไม่สำเร็จ `{command_key}` และเสียเงิน {self._fmt(amount, symbol)}"
            )
        else:
            gain = random.randint(payout_min, payout_max)
            cash_after = cash_before + gain
            if max_cash > 0:
                cash_after = min(cash_after, max_cash)
            amount = max(0, cash_after - cash_before)
            update_kwargs["cash"] = cash_after
            update_kwargs["total_earned"] = earned_before + amount
            message_text = (
                f"สำเร็จ `{command_key}` ได้รับเงิน {self._fmt(amount, symbol)}"
            )

        if custom_enabled and custom_replies:
            custom_text = str(random.choice(custom_replies) or "").strip()
            if custom_text:
                message_text = (
                    f"{custom_text}\n{'เสีย' if failed else 'ได้รับ'} {self._fmt(amount, symbol)}"
                )

        updated = await self._update_wallet_values(wallet, **update_kwargs)
        await self._write_audit(
            ctx.guild,
            settings,
            action=action_key,
            user_id=ctx.author.id,
            actor_id=ctx.author.id,
            target_user_id=ctx.author.id,
            location="cash",
            amount=amount,
            before_cash=cash_before,
            before_bank=bank_before,
            after_cash=_safe_int(updated.get("cash"), 0),
            after_bank=_safe_int(updated.get("bank"), 0),
            note="failed" if failed else "success",
        )
        await ctx.send(message_text)

    async def _write_audit(
        self,
        guild: discord.Guild,
        settings: dict[str, Any],
        *,
        action: str,
        user_id: int,
        actor_id: int,
        target_user_id: int | None,
        location: str,
        amount: int,
        before_cash: int,
        before_bank: int,
        after_cash: int,
        after_bank: int,
        note: str = "",
    ) -> None:
        try:
            await economy_audit_db.insert(
                guild_id=guild.id,
                user_id=user_id,
                actor_id=actor_id,
                target_user_id=target_user_id,
                action=action,
                location=location,
                amount=amount,
                before_cash=before_cash,
                before_bank=before_bank,
                after_cash=after_cash,
                after_bank=after_bank,
                note=note[:400],
            )
        except Exception:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {traceback.format_exc()}"
            )

        audit_channel_id = settings.get("audit_channel_id")
        if not audit_channel_id:
            return
        channel = guild.get_channel(_safe_int(audit_channel_id))
        if channel is None or not hasattr(channel, "send"):
            return
        symbol = str(settings.get("currency_symbol") or "฿")
        embed = discord.Embed(
            title="บันทึกตรวจสอบเศรษฐกิจ",
            description=(
                f"Action: `{action}`\n"
                f"User: <@{user_id}>\n"
                f"Actor: <@{actor_id}>\n"
                f"Amount: `{self._fmt(amount, symbol)}` ({location})\n"
                f"Before: cash `{self._fmt(before_cash, symbol)}` | bank `{self._fmt(before_bank, symbol)}`\n"
                f"After: cash `{self._fmt(after_cash, symbol)}` | bank `{self._fmt(after_bank, symbol)}`\n"
                f"Note: {note or '-'}"
            ),
            color=color.blue,
        )
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    async def _change_balance(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member | discord.User,
        actor: discord.Member | discord.User,
        delta: int,
        location: str,
        action: str,
        note: str = "",
    ) -> tuple[bool, str, dict[str, Any] | None]:
        if delta == 0:
            return False, "จำนวนเงินต้องไม่เป็นศูนย์", None
        settings = await self._ensure_settings(guild.id)
        wallet = await self._ensure_wallet(guild.id, member.id, settings)
        before_cash = _safe_int(wallet.get("cash"), 0)
        before_bank = _safe_int(wallet.get("bank"), 0)
        max_cash = max(0, _safe_int(settings.get("max_cash"), 0))
        max_bank = max(0, _safe_int(settings.get("max_bank"), 0))

        cash_value = before_cash
        bank_value = before_bank
        if location == "bank":
            bank_value = max(0, bank_value + delta)
            if max_bank > 0:
                bank_value = min(bank_value, max_bank)
        else:
            cash_value = max(0, cash_value + delta)
            if max_cash > 0:
                cash_value = min(cash_value, max_cash)

        earned = _safe_int(wallet.get("total_earned"), 0)
        spent = _safe_int(wallet.get("total_spent"), 0)
        if delta >= 0:
            earned += delta
        else:
            spent += abs(delta)

        updated = await self._update_wallet_values(
            wallet,
            cash=cash_value,
            bank=bank_value,
            total_earned=earned,
            total_spent=spent,
        )
        await self._write_audit(
            guild,
            settings,
            action=action,
            user_id=member.id,
            actor_id=actor.id,
            target_user_id=member.id,
            location=location,
            amount=abs(delta),
            before_cash=before_cash,
            before_bank=before_bank,
            after_cash=_safe_int(updated.get("cash"), 0),
            after_bank=_safe_int(updated.get("bank"), 0),
            note=note,
        )
        return True, "done", updated

    async def _get_leaderboard(self, guild_id: int) -> list[dict[str, Any]]:
        wallets = await economy_wallets_db.gets(guild_id=guild_id)
        wallets = wallets or []
        wallets.sort(
            key=lambda row: (_safe_int(row.get("cash"), 0) + _safe_int(row.get("bank"), 0)),
            reverse=True,
        )
        return wallets

    async def _get_level_leaderboard(self, guild_id: int, mode: str) -> list[dict[str, Any]]:
        rows = await levels_users_db.gets(guild_id=guild_id)
        rows = rows or []
        scope = str(mode or "chat").strip().lower()
        if scope in {"vc", "voice"}:
            rows.sort(
                key=lambda row: (
                    _safe_int(row.get("voice_xp"), 0),
                    _safe_int(row.get("total_xp"), 0),
                ),
                reverse=True,
            )
            return rows
        rows.sort(
            key=lambda row: (
                _safe_int(row.get("text_xp"), 0),
                _safe_int(row.get("total_xp"), 0),
            ),
            reverse=True,
        )
        return rows

    async def _get_invite_leaderboard(self, guild_id: int) -> list[dict[str, Any]]:
        rows = await invite_stats_db.gets(guild_id=guild_id)
        rows = rows or []
        rows.sort(
            key=lambda row: (
                _safe_int(row.get("invite_count"), 0),
                _safe_int(row.get("last_invited_user_id"), 0),
            ),
            reverse=True,
        )
        return rows

    @staticmethod
    def _member_label(guild: discord.Guild, user_id: int) -> str:
        member = guild.get_member(int(user_id))
        if member is not None:
            return str(member.display_name or member.name or user_id)
        return f"User {int(user_id)}"

    @staticmethod
    def _normalize_leaderboard_board(board: str) -> str:
        key = str(board or "money").strip().lower()
        aliases = {
            "money": "money",
            "cash": "money",
            "coin": "money",
            "level": "level_chat",
            "chat": "level_chat",
            "xp": "level_chat",
            "overall": "level_chat",
            "level_chat": "level_chat",
            "voice": "level_voice",
            "vc": "level_voice",
            "voice_time": "level_voice",
            "level_voice": "level_voice",
            "invite": "invite",
            "invites": "invite",
            "user_money": "user_money",
            "user_level_chat": "user_level_chat",
            "user_level_voice": "user_level_voice",
            "user_invite": "user_invite",
        }
        return aliases.get(key, "money")

    @staticmethod
    def _leaderboard_rank_icon(index: int) -> str:
        if index == 1:
            return "🥇"
        if index == 2:
            return "🥈"
        if index == 3:
            return "🥉"
        return "•"

    @staticmethod
    def _clip_text(text: str, limit: int = 28) -> str:
        raw = " ".join(str(text or "").split())
        if len(raw) <= limit:
            return raw
        if limit <= 3:
            return raw[:limit]
        return raw[: limit - 3] + "..."

    @staticmethod
    def _pil_font(size: int, *, bold: bool = False):
        if ImageFont is None:
            return None
        candidates = []
        if bold:
            candidates.extend(
                [
                    "C:/Windows/Fonts/segoeuib.ttf",
                    "C:/Windows/Fonts/arialbd.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                ]
            )
        else:
            candidates.extend(
                [
                    "C:/Windows/Fonts/segoeui.ttf",
                    "C:/Windows/Fonts/arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                ]
            )
        for path in candidates:
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    async def _collect_unified_leaderboard_entries(
        self,
        guild: discord.Guild,
        *,
        board: str,
        limit: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
        limit = max(1, min(100, _safe_int(limit, 10)))
        board_key = self._normalize_leaderboard_board(board)
        entries: list[dict[str, Any]] = []
        total_rows = 0

        if board_key == "money":
            settings = await self._ensure_settings(guild.id)
            symbol = str(settings.get("currency_symbol") or "฿")
            rows = await self._get_leaderboard(guild.id)
            total_rows = len(rows)
            for index, row in enumerate(rows[:limit], start=1):
                user_id = _safe_int(row.get("user_id"), 0)
                if user_id <= 0:
                    continue
                cash = _safe_int(row.get("cash"), 0)
                bank = _safe_int(row.get("bank"), 0)
                total = cash + bank
                member = guild.get_member(user_id)
                entries.append(
                    {
                        "rank": index,
                        "user_id": user_id,
                        "name": self._member_label(guild, user_id),
                        "metric_value": total,
                        "metric_text": self._fmt(total, symbol),
                        "sub_text": f"Cash {self._fmt(cash, symbol)} • Bank {self._fmt(bank, symbol)}",
                        "member": member,
                    }
                )
            meta = {
                "board": "money",
                "title": f"Leaderboard Money • {guild.name}",
                "color": color.purple,
                "empty_text": "ยังไม่มีข้อมูลอันดับเงินในกิลด์",
            }
            return meta, entries, total_rows

        if board_key == "invite":
            rows = await self._get_invite_leaderboard(guild.id)
            total_rows = len(rows)
            for index, row in enumerate(rows[:limit], start=1):
                inviter_id = _safe_int(row.get("inviter_id"), 0)
                if inviter_id <= 0:
                    continue
                invite_count = _safe_int(row.get("invite_count"), 0)
                invite_url = str(row.get("last_invite_url") or "").strip()
                invite_preview = invite_url if invite_url.lower().startswith(("http://", "https://")) else "-"
                member = guild.get_member(inviter_id)
                entries.append(
                    {
                        "rank": index,
                        "user_id": inviter_id,
                        "name": self._member_label(guild, inviter_id),
                        "metric_value": invite_count,
                        "metric_text": f"{invite_count:,} invites",
                        "sub_text": f"Last invite: {self._clip_text(invite_preview, 40)}",
                        "member": member,
                    }
                )
            meta = {
                "board": "invite",
                "title": f"Leaderboard Invite Server • {guild.name}",
                "color": color.green,
                "empty_text": "ยังไม่มีข้อมูล Invite ในกิลด์",
            }
            return meta, entries, total_rows

        is_voice = board_key == "level_voice"
        rows = await self._get_level_leaderboard(guild.id, "voice" if is_voice else "chat")
        total_rows = len(rows)
        for index, row in enumerate(rows[:limit], start=1):
            user_id = _safe_int(row.get("user_id"), 0)
            if user_id <= 0:
                continue
            metric = _safe_int(row.get("voice_xp"), 0) if is_voice else _safe_int(row.get("text_xp"), 0)
            level_value = _safe_int(row.get("level"), 0)
            total_xp = _safe_int(row.get("total_xp"), 0)
            member = guild.get_member(user_id)
            entries.append(
                {
                    "rank": index,
                    "user_id": user_id,
                    "name": self._member_label(guild, user_id),
                    "metric_value": metric,
                    "metric_text": f"Lv.{level_value} • {metric:,} XP",
                    "sub_text": f"Total XP {total_xp:,}",
                    "member": member,
                }
            )
        meta = {
            "board": "level_voice" if is_voice else "level_chat",
            "title": f"Leaderboard Level ({'VC' if is_voice else 'Chat'}) • {guild.name}",
            "color": color.blue,
            "empty_text": "ยังไม่มีข้อมูลเลเวลในกิลด์",
        }
        return meta, entries, total_rows

    async def _build_leaderboard_card_file(
        self,
        *,
        guild: discord.Guild,
        meta: dict[str, Any],
        entries: list[dict[str, Any]],
    ) -> discord.File | None:
        if Image is None or ImageDraw is None:
            return None
        if not entries:
            return None

        rows = entries[:10]
        width = 980
        height = 170 + len(rows) * 70 + 28
        canvas = Image.new("RGBA", (width, height), (23, 26, 33, 255))
        draw = ImageDraw.Draw(canvas)
        for y in range(height):
            ratio = y / max(1, height - 1)
            r = int(18 + (40 - 18) * ratio)
            g = int(22 + (47 - 22) * ratio)
            b = int(29 + (63 - 29) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

        title_font = self._pil_font(44, bold=True)
        subtitle_font = self._pil_font(22, bold=False)
        rank_font = self._pil_font(30, bold=True)
        name_font = self._pil_font(26, bold=True)
        info_font = self._pil_font(20, bold=False)
        value_font = self._pil_font(24, bold=True)

        board_label = str(meta.get("title") or "Leaderboard")
        draw.text((34, 22), "Skyline Endless", font=title_font, fill=(243, 247, 252, 255))
        draw.text((38, 80), self._clip_text(board_label, 58), font=subtitle_font, fill=(173, 187, 211, 255))

        max_metric = max(1, max(_safe_int(item.get("metric_value"), 0) for item in rows))
        for row_index, item in enumerate(rows):
            row_y = 122 + row_index * 70
            row_x = 24
            row_w = width - 48
            row_h = 60
            draw.rounded_rectangle(
                [row_x, row_y, row_x + row_w, row_y + row_h],
                radius=14,
                fill=(28, 34, 45, 230),
                outline=(73, 82, 97, 255),
                width=1,
            )

            rank = _safe_int(item.get("rank"), row_index + 1)
            rank_text = f"#{rank}"
            rank_color = (252, 208, 70, 255) if rank == 1 else ((206, 216, 229, 255) if rank == 2 else ((228, 155, 95, 255) if rank == 3 else (186, 195, 210, 255)))
            draw.text((40, row_y + 12), rank_text, font=rank_font, fill=rank_color)

            avatar_size = 46
            avatar_x = 118
            avatar_y = row_y + 7
            member = item.get("member")
            if member is not None and ImageOps is not None:
                try:
                    avatar_asset = member.display_avatar
                    try:
                        avatar_asset = avatar_asset.replace(size=128, format="png")
                    except Exception:
                        avatar_asset = member.display_avatar.with_size(128)
                    avatar_raw = await avatar_asset.read()
                    avatar_image = Image.open(io.BytesIO(avatar_raw)).convert("RGBA")
                    avatar_image = ImageOps.fit(avatar_image, (avatar_size, avatar_size), method=Image.LANCZOS)
                    mask = Image.new("L", (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    canvas.paste(avatar_image, (avatar_x, avatar_y), mask)
                except (discord.HTTPException, OSError, UnidentifiedImageError):
                    draw.ellipse(
                        (avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size),
                        fill=(80, 95, 115, 255),
                    )
            else:
                draw.ellipse(
                    (avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size),
                    fill=(80, 95, 115, 255),
                )

            name_text = self._clip_text(item.get("name", "Unknown"), 28)
            draw.text((176, row_y + 10), name_text, font=name_font, fill=(240, 245, 250, 255))
            draw.text((176, row_y + 34), self._clip_text(item.get("sub_text", ""), 42), font=info_font, fill=(154, 167, 188, 255))
            metric_text = self._clip_text(item.get("metric_text", "-"), 28)
            metric_bbox = draw.textbbox((0, 0), metric_text, font=value_font)
            metric_w = max(0, metric_bbox[2] - metric_bbox[0])
            draw.text((row_x + row_w - metric_w - 18, row_y + 18), metric_text, font=value_font, fill=(221, 234, 255, 255))

            bar_x = 176
            bar_y = row_y + row_h - 11
            bar_w = row_w - 206
            draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + 5), radius=2, fill=(71, 79, 90, 255))
            metric_value = _safe_int(item.get("metric_value"), 0)
            progress = int((metric_value / max_metric) * bar_w) if max_metric > 0 else 0
            if progress > 0:
                draw.rounded_rectangle((bar_x, bar_y, bar_x + progress, bar_y + 5), radius=2, fill=(19, 226, 255, 255))

        file_bytes = io.BytesIO()
        canvas.convert("RGB").save(file_bytes, format="PNG", optimize=True)
        file_bytes.seek(0)
        return discord.File(file_bytes, filename="leaderboard-card.png")

    async def _build_unified_leaderboard_embed(
        self,
        ctx: commands.Context,
        *,
        board: str,
        limit: int = 10,
    ) -> tuple[discord.Embed, discord.File | None]:
        guild = ctx.guild
        board_key = self._normalize_leaderboard_board(board)
        meta, entries, total_rows = await self._collect_unified_leaderboard_entries(
            guild,
            board=board_key,
            limit=limit,
        )
        embed = discord.Embed(
            title=str(meta.get("title") or f"Leaderboard • {guild.name}"),
            color=int(meta.get("color") or color.blue),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if not entries:
            embed.description = str(meta.get("empty_text") or "ยังไม่มีข้อมูลที่แสดงได้")
            embed.set_footer(text="No data")
            return embed, None

        lines: list[str] = []
        for item in entries:
            rank = _safe_int(item.get("rank"), 0)
            name = str(item.get("name") or "Unknown")
            metric_text = str(item.get("metric_text") or "-")
            sub_text = str(item.get("sub_text") or "")
            icon = self._leaderboard_rank_icon(rank)
            lines.append(
                f"{icon} `#{rank}` **{self._clip_text(name, 36)}** • {metric_text}\n`   ` {self._clip_text(sub_text, 62)}"
            )
        embed.description = "\n".join(lines[:20])
        embed.set_footer(text=f"Top {len(entries)}/{total_rows}")

        card_file = await self._build_leaderboard_card_file(
            guild=guild,
            meta=meta,
            entries=entries,
        )
        if card_file is not None:
            embed.set_image(url="attachment://leaderboard-card.png")
        return embed, card_file

    async def _build_user_rank_embed(
        self,
        *,
        guild: discord.Guild | None,
        member: discord.Member | None,
        board: str,
    ) -> discord.Embed | None:
        if guild is None or member is None:
            return None
        board_key = self._normalize_leaderboard_board(board)
        if board_key.startswith("user_"):
            board_key = board_key.replace("user_", "", 1)

        if board_key == "money":
            rows = await self._get_leaderboard(guild.id)
            for index, row in enumerate(rows, start=1):
                if _safe_int(row.get("user_id"), 0) == member.id:
                    settings = await self._ensure_settings(guild.id)
                    symbol = str(settings.get("currency_symbol") or "฿")
                    cash = _safe_int(row.get("cash"), 0)
                    bank = _safe_int(row.get("bank"), 0)
                    total = cash + bank
                    return discord.Embed(
                        title=f"Your Money Rank • {member.display_name}",
                        description=(
                            f"อันดับ: **#{index}**\n"
                            f"Cash: **{self._fmt(cash, symbol)}**\n"
                            f"Bank: **{self._fmt(bank, symbol)}**\n"
                            f"Total: **{self._fmt(total, symbol)}**"
                        ),
                        color=color.purple,
                    )
            return None

        if board_key == "invite":
            rows = await self._get_invite_leaderboard(guild.id)
            for index, row in enumerate(rows, start=1):
                if _safe_int(row.get("inviter_id"), 0) == member.id:
                    count_value = _safe_int(row.get("invite_count"), 0)
                    invite_url = str(row.get("last_invite_url") or "").strip()
                    text = f"อันดับ: **#{index}**\nเชิญสำเร็จ: **{count_value:,}** คน"
                    if invite_url.lower().startswith(("http://", "https://")):
                        text += f"\nลิงก์ล่าสุด: {invite_url}"
                    return discord.Embed(
                        title=f"Your Invite Rank • {member.display_name}",
                        description=text,
                        color=color.green,
                    )
            return None

        scope = "voice" if board_key == "level_voice" else "chat"
        rows = await self._get_level_leaderboard(guild.id, scope)
        for index, row in enumerate(rows, start=1):
            if _safe_int(row.get("user_id"), 0) != member.id:
                continue
            source_xp = _safe_int(row.get("voice_xp"), 0) if scope == "voice" else _safe_int(row.get("text_xp"), 0)
            return discord.Embed(
                title=f"Your Level Rank ({'VC' if scope == 'voice' else 'Chat'}) • {member.display_name}",
                description=(
                    f"อันดับ: **#{index}**\n"
                    f"Level: **{_safe_int(row.get('level'), 0)}**\n"
                    f"{'VC' if scope == 'voice' else 'Chat'} XP: **{source_xp:,}**\n"
                    f"Total XP: **{_safe_int(row.get('total_xp'), 0):,}**"
                ),
                color=color.blue,
            )
        return None

    async def _send_unified_leaderboard(
        self,
        ctx: commands.Context,
        *,
        board: str,
        limit: int = 10,
        with_selector: bool = False,
    ) -> None:
        embed, card_file = await self._build_unified_leaderboard_embed(
            ctx,
            board=board,
            limit=limit,
        )
        files = [card_file] if card_file is not None else []
        if with_selector:
            view = EconomyLeaderboardView(
                self,
                ctx,
                current_board=self._normalize_leaderboard_board(board),
                limit=limit,
            )
            if card_file is not None:
                message = await ctx.send(embed=embed, file=card_file, view=view)
            else:
                message = await ctx.send(embed=embed, view=view)
            view.message = message
            return
        if files:
            await ctx.send(embed=embed, file=card_file)
            return
        await ctx.send(embed=embed)

    async def _send_money_leaderboard_embed(self, ctx: commands.Context, limit: int = 10) -> None:
        await self._send_unified_leaderboard(ctx, board="money", limit=limit, with_selector=False)

    async def _send_level_leaderboard_embed(
        self,
        ctx: commands.Context,
        *,
        mode: str = "chat",
        limit: int = 10,
    ) -> None:
        scope = str(mode or "chat").strip().lower()
        if scope not in {"chat", "vc", "voice"}:
            await ctx.send("เลือกโหมดได้เฉพาะ `chat` หรือ `vc`")
            return
        board_key = "level_voice" if scope in {"vc", "voice"} else "level_chat"
        await self._send_unified_leaderboard(ctx, board=board_key, limit=limit, with_selector=False)

    async def _send_invite_leaderboard_embed(self, ctx: commands.Context, limit: int = 10) -> None:
        await self._send_unified_leaderboard(ctx, board="invite", limit=limit, with_selector=False)

    async def _send_leaderboard_self_embed(
        self,
        ctx: commands.Context,
        *,
        member: discord.Member,
        board: str,
        mode: str = "chat",
    ) -> None:
        normalized_board = str(board or "money").strip().lower()
        if normalized_board == "level":
            scope = str(mode or "chat").strip().lower()
            if scope not in {"chat", "vc", "voice"}:
                await ctx.send("เลือกโหมดเลเวลได้เฉพาะ `chat` หรือ `vc`")
                return
            normalized_board = "level_voice" if scope in {"vc", "voice"} else "level_chat"

        embed = await self._build_user_rank_embed(
            guild=ctx.guild,
            member=member,
            board=normalized_board,
        )
        if embed is not None:
            await ctx.send(embed=embed)
            return
        await ctx.send("ยังไม่พบข้อมูลอันดับของผู้ใช้ในลีดเดอร์บอร์ดนี้")

    async def _show_money_card(
        self, ctx: commands.Context, member: discord.Member | discord.User
    ):
        settings = await self._ensure_settings(ctx.guild.id)
        wallet = await self._ensure_wallet(ctx.guild.id, member.id, settings)
        symbol = str(settings.get("currency_symbol") or "฿")
        cash = _safe_int(wallet.get("cash"), 0)
        bank = _safe_int(wallet.get("bank"), 0)
        total = cash + bank
        ranking = await self._get_leaderboard(ctx.guild.id)
        rank = "-"
        for idx, row in enumerate(ranking, start=1):
            if _safe_int(row.get("user_id"), 0) == member.id:
                rank = str(idx)
                break

        embed = discord.Embed(
            title=f"กระเป๋าเงินของ {member.display_name}",
            color=color.green,
            description=(
                f"เงินสด: **{self._fmt(cash, symbol)}**\n"
                f"ธนาคาร: **{self._fmt(bank, symbol)}**\n"
                f"รวมทั้งหมด: **{self._fmt(total, symbol)}**\n"
                f"อันดับในกิลด์: **#{rank}**"
            ),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_group(
        name="economy",
        help="Economy command group (คำสั่งระบบเศรษฐกิจ)",
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def economy(self, ctx: commands.Context):
        embed = discord.Embed(
            title="คำสั่งเศรษฐกิจ",
            color=color.blue,
            description=(
                "ตัวอย่างคำสั่งหลัก:\n"
                "`/economy money`, `/economy leaderboard`, `/economy deposit`, `/economy withdraw`, `/economy give-money`, `/economy work`\n\n"
                "คำสั่งแอดมิน:\n"
                "`/economy set-currency`, `/economy set-start-balance`, `/economy maximum-balance`,\n"
                "`/economy add-money`, `/economy remove-money`, `/economy reset-money`, `/economy reset-economy`"
            ),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="money", help="ตรวจสอบยอดเงิน", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def money(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        try:
            target = member or ctx.author
            await self._show_money_card(ctx, target)
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_group(
        name="leaderboard",
        help="Unified leaderboards: level (chat/voice), money, invite (ลีดเดอร์บอร์ดรวม: เลเวล (แชต/เสียง), เงิน, คำเชิญ)",
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.user)
    @app_commands.describe(limit="จำนวนอันดับที่ต้องการแสดง (1-100)")
    async def leaderboard(self, ctx: commands.Context, limit: int = 10):
        try:
            if ctx.invoked_subcommand is not None:
                return
            await self._send_unified_leaderboard(
                ctx,
                board="money",
                limit=limit,
                with_selector=True,
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @leaderboard.command(
        name="default",
        help="Leaderboard page with artwork and board selector (หน้าแสดงลีดเดอร์บอร์ดพร้อมภาพและเมนูเลือกบอร์ด)",
    )
    @app_commands.describe(
        board="เลือก leaderboard ที่ต้องการให้เปิดเป็นค่าเริ่มต้น",
        limit="จำนวนอันดับที่ต้องการแสดง (1-100)",
    )
    @app_commands.choices(
        board=[
            app_commands.Choice(name="money", value="money"),
            app_commands.Choice(name="overall_xp", value="level_chat"),
            app_commands.Choice(name="voice_time", value="level_voice"),
            app_commands.Choice(name="invite", value="invite"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def leaderboard_default(
        self,
        ctx: commands.Context,
        board: str = "money",
        limit: int = 10,
    ):
        await self._send_unified_leaderboard(
            ctx,
            board=board,
            limit=limit,
            with_selector=True,
        )

    @leaderboard.command(name="money", help="ลีดเดอร์บอร์ดเงิน")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def leaderboard_money(self, ctx: commands.Context, limit: int = 10):
        await self._send_money_leaderboard_embed(ctx, limit=limit)

    @leaderboard.command(name="level", help="ลีดเดอร์บอร์ดเลเวล (chat/vc)")
    @app_commands.describe(mode="เลือกโหมดเลเวลที่ต้องการดู")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="chat", value="chat"),
            app_commands.Choice(name="vc", value="vc"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def leaderboard_level(self, ctx: commands.Context, mode: str = "chat", limit: int = 10):
        await self._send_level_leaderboard_embed(ctx, mode=mode, limit=limit)

    @leaderboard.command(name="invite", help="ลีดเดอร์บอร์ดคำเชิญ")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def leaderboard_invite(self, ctx: commands.Context, limit: int = 10):
        await self._send_invite_leaderboard_embed(ctx, limit=limit)

    @leaderboard.command(name="me", help="ตรวจอันดับของตัวเอง")
    @app_commands.describe(
        board="เลือกบอร์ดที่ต้องการตรวจอันดับ",
        mode="โหมดสำหรับบอร์ดเลเวล",
        member="เลือกผู้ใช้ (เว้นว่าง = ตัวเอง)",
    )
    @app_commands.choices(
        board=[
            app_commands.Choice(name="money", value="money"),
            app_commands.Choice(name="level", value="level"),
            app_commands.Choice(name="invite", value="invite"),
        ],
        mode=[
            app_commands.Choice(name="chat", value="chat"),
            app_commands.Choice(name="vc", value="vc"),
        ],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def leaderboard_me(
        self,
        ctx: commands.Context,
        board: str = "money",
        mode: str = "chat",
        member: Optional[discord.Member] = None,
    ):
        target = member or ctx.author
        if target.bot:
            await ctx.send("ไม่รองรับการตรวจอันดับของบอท")
            return
        normalized_board = str(board or "money").strip().lower()
        if normalized_board not in {"money", "level", "invite"}:
            await ctx.send("เลือก board ได้เฉพาะ `money`, `level`, `invite`")
            return
        await self._send_leaderboard_self_embed(
            ctx,
            member=target,
            board=normalized_board,
            mode=mode,
        )

    @leaderboard.command(name="user", help="ตรวจอันดับของผู้ใช้ในบอร์ดต่างๆ")
    @app_commands.describe(
        board="เลือกบอร์ดที่ต้องการตรวจอันดับ",
        mode="โหมดสำหรับบอร์ดเลเวล",
        member="ผู้ใช้ที่ต้องการตรวจอันดับ",
    )
    @app_commands.choices(
        board=[
            app_commands.Choice(name="money", value="money"),
            app_commands.Choice(name="level", value="level"),
            app_commands.Choice(name="invite", value="invite"),
        ],
        mode=[
            app_commands.Choice(name="chat", value="chat"),
            app_commands.Choice(name="vc", value="vc"),
        ],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def leaderboard_user(
        self,
        ctx: commands.Context,
        board: str = "money",
        mode: str = "chat",
        member: Optional[discord.Member] = None,
    ):
        await self.leaderboard_me(ctx, board=board, mode=mode, member=member)

    @commands.hybrid_command(name="deposit", help="ฝากเงินเข้าธนาคาร", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def deposit(self, ctx: commands.Context, amount: str):
        try:
            settings = await self._ensure_settings(ctx.guild.id)
            wallet = await self._ensure_wallet(ctx.guild.id, ctx.author.id, settings)
            symbol = str(settings.get("currency_symbol") or "฿")
            cash = _safe_int(wallet.get("cash"), 0)
            bank = _safe_int(wallet.get("bank"), 0)
            max_bank = max(0, _safe_int(settings.get("max_bank"), 0))

            if amount.lower() == "all":
                move = cash
            else:
                move = _safe_int(amount, 0)
            if move <= 0:
                return await ctx.send("จำนวนเงินต้องมากกว่า 0")
            if move > cash:
                return await ctx.send("เงินสดของคุณไม่พอ")

            if max_bank > 0 and bank + move > max_bank:
                move = max(0, max_bank - bank)
            if move <= 0:
                return await ctx.send("ธนาคารของคุณเต็มตามลิมิตแล้ว")

            updated = await self._update_wallet_values(
                wallet,
                cash=cash - move,
                bank=bank + move,
            )
            await self._write_audit(
                ctx.guild,
                settings,
                action="deposit",
                user_id=ctx.author.id,
                actor_id=ctx.author.id,
                target_user_id=ctx.author.id,
                location="bank",
                amount=move,
                before_cash=cash,
                before_bank=bank,
                after_cash=_safe_int(updated.get("cash"), 0),
                after_bank=_safe_int(updated.get("bank"), 0),
            )
            await ctx.send(f"ฝากเงินสำเร็จ {self._fmt(move, symbol)}")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="withdraw", help="ถอนเงินจากธนาคาร", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def withdraw(self, ctx: commands.Context, amount: str):
        try:
            settings = await self._ensure_settings(ctx.guild.id)
            wallet = await self._ensure_wallet(ctx.guild.id, ctx.author.id, settings)
            symbol = str(settings.get("currency_symbol") or "฿")
            cash = _safe_int(wallet.get("cash"), 0)
            bank = _safe_int(wallet.get("bank"), 0)
            max_cash = max(0, _safe_int(settings.get("max_cash"), 0))

            if amount.lower() == "all":
                move = bank
            else:
                move = _safe_int(amount, 0)
            if move <= 0:
                return await ctx.send("จำนวนเงินต้องมากกว่า 0")
            if move > bank:
                return await ctx.send("เงินในธนาคารของคุณไม่พอ")

            if max_cash > 0 and cash + move > max_cash:
                move = max(0, max_cash - cash)
            if move <= 0:
                return await ctx.send("เงินสดของคุณเต็มตามลิมิตแล้ว")

            updated = await self._update_wallet_values(
                wallet,
                cash=cash + move,
                bank=bank - move,
            )
            await self._write_audit(
                ctx.guild,
                settings,
                action="withdraw",
                user_id=ctx.author.id,
                actor_id=ctx.author.id,
                target_user_id=ctx.author.id,
                location="cash",
                amount=move,
                before_cash=cash,
                before_bank=bank,
                after_cash=_safe_int(updated.get("cash"), 0),
                after_bank=_safe_int(updated.get("bank"), 0),
            )
            await ctx.send(f"ถอนเงินสำเร็จ {self._fmt(move, symbol)}")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="give-money", help="โอนเงินให้สมาชิก", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def give_money(
        self, ctx: commands.Context, member: discord.Member, amount: int
    ):
        try:
            if member.bot:
                return await ctx.send("ไม่สามารถโอนให้บอทได้")
            if member.id == ctx.author.id:
                return await ctx.send("ไม่สามารถโอนให้ตัวเองได้")
            if amount <= 0:
                return await ctx.send("จำนวนเงินต้องมากกว่า 0")

            settings = await self._ensure_settings(ctx.guild.id)
            symbol = str(settings.get("currency_symbol") or "฿")
            sender_wallet = await self._ensure_wallet(ctx.guild.id, ctx.author.id, settings)
            receiver_wallet = await self._ensure_wallet(ctx.guild.id, member.id, settings)
            sender_cash = _safe_int(sender_wallet.get("cash"), 0)
            receiver_cash = _safe_int(receiver_wallet.get("cash"), 0)
            max_cash = max(0, _safe_int(settings.get("max_cash"), 0))

            if sender_cash < amount:
                return await ctx.send("เงินสดของคุณไม่พอ")
            if max_cash > 0 and receiver_cash >= max_cash:
                return await ctx.send("ผู้รับมีเงินสดเต็มลิมิตแล้ว")

            receive_amount = amount
            if max_cash > 0 and receiver_cash + receive_amount > max_cash:
                receive_amount = max_cash - receiver_cash
            if receive_amount <= 0:
                return await ctx.send("ผู้รับไม่สามารถรับเงินเพิ่มได้ในตอนนี้")

            updated_sender = await self._update_wallet_values(
                sender_wallet, cash=sender_cash - receive_amount
            )
            updated_receiver = await self._update_wallet_values(
                receiver_wallet, cash=receiver_cash + receive_amount
            )
            await self._write_audit(
                ctx.guild,
                settings,
                action="give_money_sender",
                user_id=ctx.author.id,
                actor_id=ctx.author.id,
                target_user_id=member.id,
                location="cash",
                amount=receive_amount,
                before_cash=sender_cash,
                before_bank=_safe_int(sender_wallet.get("bank"), 0),
                after_cash=_safe_int(updated_sender.get("cash"), 0),
                after_bank=_safe_int(updated_sender.get("bank"), 0),
                note=f"to:{member.id}",
            )
            await self._write_audit(
                ctx.guild,
                settings,
                action="give_money_receiver",
                user_id=member.id,
                actor_id=ctx.author.id,
                target_user_id=ctx.author.id,
                location="cash",
                amount=receive_amount,
                before_cash=receiver_cash,
                before_bank=_safe_int(receiver_wallet.get("bank"), 0),
                after_cash=_safe_int(updated_receiver.get("cash"), 0),
                after_bank=_safe_int(updated_receiver.get("bank"), 0),
                note=f"from:{ctx.author.id}",
            )
            await ctx.send(
                f"โอนเงินให้ {member.mention} สำเร็จ {self._fmt(receive_amount, symbol)}"
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="work", help="คำสั่งทำงานรับเงิน", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def work(self, ctx: commands.Context):
        try:
            await self._run_income_command(
                ctx,
                command_key="work",
                timestamp_key="work_at",
                action_key="work",
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="slut", help="คำสั่งหาเงินด่วน (slut)", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def slut(self, ctx: commands.Context):
        try:
            await self._run_income_command(
                ctx,
                command_key="slut",
                timestamp_key="slut_at",
                action_key="slut",
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="crime", help="คำสั่งหาเงินด่วน (crime)", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def crime(self, ctx: commands.Context):
        try:
            await self._run_income_command(
                ctx,
                command_key="crime",
                timestamp_key="crime_at",
                action_key="crime",
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="rob", help="พยายามปล้นผู้ใช้อื่น", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def rob(self, ctx: commands.Context):
        try:
            await self._run_income_command(
                ctx,
                command_key="rob",
                timestamp_key="rob_at",
                action_key="rob",
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="collect-income", help="รับรายได้จากบทบาท", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def collect_income(self, ctx: commands.Context):
        try:
            settings = await self._ensure_settings(ctx.guild.id)
            if not bool(settings.get("role_income_enabled")):
                return await ctx.send("Role Income ยังไม่ได้เปิดใช้งานในเซิร์ฟเวอร์")
            wallet = await self._ensure_wallet(ctx.guild.id, ctx.author.id, settings)
            role_rows = settings.get("role_income_entries") if isinstance(settings.get("role_income_entries"), list) else []
            if not role_rows:
                return await ctx.send("ยังไม่พบการตั้งค่า Role Income")
            member_role_ids = {
                str(getattr(role, "id", "")).strip()
                for role in getattr(ctx.author, "roles", [])
                if str(getattr(role, "id", "")).strip().isdigit()
            }
            matched: list[dict[str, Any]] = []
            for row in role_rows:
                if not isinstance(row, dict):
                    continue
                role_id = str(row.get("role_id") or "").strip()
                if role_id and role_id in member_role_ids:
                    matched.append(row)
            if not matched:
                return await ctx.send("คุณไม่มียศที่รับ Role Income ในตอนนี้")
            now = _utc_now()

            def _to_utc_dt(value: Any) -> datetime.datetime | None:
                if isinstance(value, datetime.datetime):
                    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
                raw = str(value or "").strip()
                if not raw:
                    return None
                normalized = raw.replace("Z", "+00:00")
                for candidate in (normalized, normalized.replace(" ", "T")):
                    try:
                        parsed = datetime.datetime.fromisoformat(candidate)
                        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
                    except Exception:
                        continue
                return None

            raw_role_state = wallet.get("collect_income_role_at")
            role_state: dict[str, Any] = raw_role_state if isinstance(raw_role_state, dict) else {}
            next_role_state: dict[str, Any] = {
                str(key).strip(): value
                for key, value in role_state.items()
                if str(key).strip().isdigit()
            }

            # Legacy fallback for wallets that only have single collect_income_at timestamp.
            legacy_last_collect = _to_utc_dt(wallet.get("collect_income_at"))

            channel_ids = {str(ctx.channel.id)}
            parent_id = getattr(ctx.channel, "parent_id", None)
            if parent_id:
                channel_ids.add(str(parent_id))

            eligible_rows: list[dict[str, Any]] = []
            cooldown_remains: list[int] = []
            channel_locked = 0

            for row in matched:
                role_id = str(row.get("role_id") or "").strip()
                if not role_id:
                    continue
                amount = max(0, _safe_int(row.get("amount"), 0))
                cooldown_seconds = max(10, _safe_int(row.get("cooldown"), 3600))
                channel_id = str(row.get("channel_id") or "").strip()

                if channel_id and channel_id not in channel_ids:
                    channel_locked += 1
                    continue

                if amount <= 0:
                    continue

                last_role_collect = _to_utc_dt(next_role_state.get(role_id))
                if last_role_collect is None:
                    last_role_collect = legacy_last_collect
                if isinstance(last_role_collect, datetime.datetime):
                    remain = cooldown_seconds - int((now - last_role_collect).total_seconds())
                    if remain > 0:
                        cooldown_remains.append(remain)
                        continue

                eligible_rows.append(
                    {
                        "role_id": role_id,
                        "amount": amount,
                    }
                )
                next_role_state[role_id] = now

            gain_total = sum(int(item.get("amount") or 0) for item in eligible_rows)
            if gain_total <= 0:
                if cooldown_remains:
                    remain = max(1, min(cooldown_remains))
                    await self._send_temporary_message(
                        ctx,
                        f"คุณต้องรออีก {remain} วินาที ก่อนรับ Role Income ได้อีกครั้ง",
                        seconds=min(max(remain, 6), 20),
                    )
                    return
                if channel_locked > 0:
                    return await ctx.send("ห้องนี้ไม่อยู่ในเงื่อนไข Role Income ของยศที่คุณถืออยู่")
                return await ctx.send("ยศที่คุณมีไม่ได้ตั้งค่าเงินรางวัลไว้")

            cash_before = _safe_int(wallet.get("cash"), 0)
            bank_before = _safe_int(wallet.get("bank"), 0)
            earned_before = _safe_int(wallet.get("total_earned"), 0)
            max_cash = max(0, _safe_int(settings.get("max_cash"), 0))
            cash_after = cash_before + gain_total
            if max_cash > 0:
                cash_after = min(cash_after, max_cash)
            gain_applied = max(0, cash_after - cash_before)
            updated = await self._update_wallet_values(
                wallet,
                cash=cash_after,
                total_earned=earned_before + gain_applied,
                collect_income_at=now,
                collect_income_role_at=next_role_state,
            )
            await self._write_audit(
                ctx.guild,
                settings,
                action="collect_income",
                user_id=ctx.author.id,
                actor_id=ctx.author.id,
                target_user_id=ctx.author.id,
                location="cash",
                amount=gain_applied,
                before_cash=cash_before,
                before_bank=bank_before,
                after_cash=_safe_int(updated.get("cash"), 0),
                after_bank=_safe_int(updated.get("bank"), 0),
                note=f"roles:{len(eligible_rows)}",
            )
            symbol = str(settings.get("currency_symbol") or "฿")
            await ctx.send(
                f"รับ Role Income สำเร็จ {self._fmt(gain_applied, symbol)} จาก {len(eligible_rows)} ยศ"
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="money", help="ตรวจสอบยอดเงิน")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def economy_money(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        await ctx.invoke(self.money, member=member)

    @economy.command(name="leaderboard", help="อันดับเงินในกิลด์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.user)
    async def economy_leaderboard(self, ctx: commands.Context, limit: int = 10):
        await ctx.invoke(self.leaderboard_money, limit=limit)

    @economy.command(name="deposit", help="ฝากเงินเข้าธนาคาร")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def economy_deposit(self, ctx: commands.Context, amount: str):
        await ctx.invoke(self.deposit, amount=amount)

    @economy.command(name="withdraw", help="ถอนเงินจากธนาคาร")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def economy_withdraw(self, ctx: commands.Context, amount: str):
        await ctx.invoke(self.withdraw, amount=amount)

    @economy.command(name="give-money", help="โอนเงินให้สมาชิก")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def economy_give_money(
        self, ctx: commands.Context, member: discord.Member, amount: int
    ):
        await ctx.invoke(self.give_money, member=member, amount=amount)

    @economy.command(name="work", help="คำสั่งทำงานรับเงิน")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def economy_work(self, ctx: commands.Context):
        await ctx.invoke(self.work)

    @economy.command(name="slut", help="คำสั่งหาเงินด่วน (slut)", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def economy_slut(self, ctx: commands.Context):
        await ctx.invoke(self.slut)

    @economy.command(name="crime", help="คำสั่งหาเงินด่วน (crime)", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def economy_crime(self, ctx: commands.Context):
        await ctx.invoke(self.crime)

    @economy.command(name="rob", help="พยายามปล้นผู้ใช้อื่น", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def economy_rob(self, ctx: commands.Context):
        await ctx.invoke(self.rob)

    @economy.command(name="collect-income", help="รับรายได้จากบทบาท")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def economy_collect_income(self, ctx: commands.Context):
        await ctx.invoke(self.collect_income)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if not message.guild or message.author.bot:
                return
            if not isinstance(message.author, discord.Member):
                return
            settings = await self._ensure_settings(message.guild.id)
            if not bool(settings.get("chat_money_enabled")):
                return
            allowed_channels = (
                settings.get("chat_money_channels")
                if isinstance(settings.get("chat_money_channels"), list)
                else []
            )
            if allowed_channels:
                channel_id_str = str(message.channel.id)
                if channel_id_str not in {str(item) for item in allowed_channels}:
                    return

            wallet = await self._ensure_wallet(message.guild.id, message.author.id, settings)
            cooldown = max(5, _safe_int(settings.get("chat_money_cooldown"), 60))
            now = _utc_now()
            last_chat = wallet.get("chat_at")
            if isinstance(last_chat, datetime.datetime):
                last = last_chat if last_chat.tzinfo else last_chat.replace(tzinfo=datetime.timezone.utc)
                if (now - last).total_seconds() < cooldown:
                    return

            gain_min = max(0, _safe_int(settings.get("chat_money_min"), 5))
            gain_max = max(gain_min, _safe_int(settings.get("chat_money_max"), 15))
            gain = random.randint(gain_min, gain_max)
            if gain <= 0:
                await self._update_wallet_values(wallet, chat_at=now)
                return
            cash_before = _safe_int(wallet.get("cash"), 0)
            bank_before = _safe_int(wallet.get("bank"), 0)
            earned_before = _safe_int(wallet.get("total_earned"), 0)
            max_cash = max(0, _safe_int(settings.get("max_cash"), 0))
            cash_after = cash_before + gain
            if max_cash > 0:
                cash_after = min(cash_after, max_cash)
            gain_applied = max(0, cash_after - cash_before)
            updated = await self._update_wallet_values(
                wallet,
                cash=cash_after,
                total_earned=earned_before + gain_applied,
                chat_at=now,
            )
            await self._write_audit(
                message.guild,
                settings,
                action="chat_money",
                user_id=message.author.id,
                actor_id=message.author.id,
                target_user_id=message.author.id,
                location="cash",
                amount=gain_applied,
                before_cash=cash_before,
                before_bank=bank_before,
                after_cash=_safe_int(updated.get("cash"), 0),
                after_bank=_safe_int(updated.get("bank"), 0),
                note=f"channel:{message.channel.id}",
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="set-currency", help="ตั้งค่าสัญลักษณ์สกุลเงิน")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def set_currency(self, ctx: commands.Context, symbol: str):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            symbol = str(symbol or "").strip()[:5]
            if not symbol:
                return await ctx.send("กรุณาระบุสัญลักษณ์สกุลเงิน เช่น ฿ หรือ $")
            settings = await self._ensure_settings(ctx.guild.id)
            await economy_settings_db.update(
                id=settings["id"], currency_symbol=symbol, updated_at=_utc_now()
            )
            await ctx.send(f"ตั้งค่าสัญลักษณ์สกุลเงินเป็น `{symbol}` แล้ว")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="set-start-balance", help="ตั้งค่ายอดเงินธนาคารเริ่มต้น")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def set_start_balance(
        self, ctx: commands.Context, start_cash: int = 0, start_bank: int = 0
    ):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            start_cash = max(0, start_cash)
            start_bank = max(0, start_bank)
            settings = await self._ensure_settings(ctx.guild.id)
            await economy_settings_db.update(
                id=settings["id"],
                start_cash=start_cash,
                start_bank=start_bank,
                updated_at=_utc_now(),
            )
            await ctx.send(
                f"ตั้งค่าเงินเริ่มต้น: cash `{start_cash:,}` | bank `{start_bank:,}`"
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(
        name="money-audit-log",
        help="Set the money transaction audit log channel (ตั้งค่าช่องบันทึกธุรกรรมการเงิน)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def money_audit_log(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            settings = await self._ensure_settings(ctx.guild.id)
            if channel is None:
                await economy_settings_db.update(
                    id=settings["id"], audit_channel_id=None, updated_at=_utc_now()
                )
                return await ctx.send("ปิด Audit Log แล้ว")
            await economy_settings_db.update(
                id=settings["id"], audit_channel_id=channel.id, updated_at=_utc_now()
            )
            await ctx.send(f"ตั้งห้อง audit log เป็น {channel.mention} แล้ว")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="maximum-balance", help="ตั้งค่ายอดเงินสดและ/หรือยอดธนาคารสูงสุดที่อนุญาต")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def maximum_balance(
        self,
        ctx: commands.Context,
        max_cash: Optional[int] = None,
        max_bank: Optional[int] = None,
    ):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            settings = await self._ensure_settings(ctx.guild.id)
            new_cash = (
                max(0, int(max_cash))
                if max_cash is not None
                else max(0, _safe_int(settings.get("max_cash"), 1_000_000_000))
            )
            new_bank = (
                max(0, int(max_bank))
                if max_bank is not None
                else max(0, _safe_int(settings.get("max_bank"), 1_000_000_000))
            )
            await economy_settings_db.update(
                id=settings["id"], max_cash=new_cash, max_bank=new_bank, updated_at=_utc_now()
            )
            await ctx.send(f"ตั้ง max cash `{new_cash:,}` | max bank `{new_bank:,}` แล้ว")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="add-money", help="เพิ่มเงินให้สมาชิก")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def add_money(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
        location: str = "cash",
    ):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            location = "bank" if str(location).lower().strip() == "bank" else "cash"
            if amount <= 0:
                return await ctx.send("จำนวนเงินต้องมากกว่า 0")
            ok, _, wallet = await self._change_balance(
                guild=ctx.guild,
                member=member,
                actor=ctx.author,
                delta=amount,
                location=location,
                action="add_money",
                note="admin_add",
            )
            if not ok or wallet is None:
                return await ctx.send("เพิ่มเงินไม่สำเร็จ")
            symbol = str((await self._ensure_settings(ctx.guild.id)).get("currency_symbol") or "฿")
            await ctx.send(
                f"เพิ่มเงินให้ {member.mention} สำเร็จ {self._fmt(amount, symbol)} ({location})"
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="remove-money", help="หักเงินจากสมาชิก")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def remove_money(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
        location: str = "cash",
    ):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            location = "bank" if str(location).lower().strip() == "bank" else "cash"
            if amount <= 0:
                return await ctx.send("จำนวนเงินต้องมากกว่า 0")
            settings = await self._ensure_settings(ctx.guild.id)
            wallet = await self._ensure_wallet(ctx.guild.id, member.id, settings)
            cur_cash = _safe_int(wallet.get("cash"), 0)
            cur_bank = _safe_int(wallet.get("bank"), 0)
            if location == "bank":
                if cur_bank < amount:
                    amount = cur_bank
            else:
                if cur_cash < amount:
                    amount = cur_cash
            if amount <= 0:
                return await ctx.send("ผู้ใช้ไม่มีเงินในช่องที่เลือก")
            ok, _, updated = await self._change_balance(
                guild=ctx.guild,
                member=member,
                actor=ctx.author,
                delta=-amount,
                location=location,
                action="remove_money",
                note="admin_remove",
            )
            if not ok or updated is None:
                return await ctx.send("หักเงินไม่สำเร็จ")
            symbol = str(settings.get("currency_symbol") or "฿")
            await ctx.send(
                f"หักเงินจาก {member.mention} สำเร็จ {self._fmt(amount, symbol)} ({location})"
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="add-money-role", help="เพิ่มเงินให้สมาชิกทุกคนในบทบาท")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def add_money_role(
        self, ctx: commands.Context, role: discord.Role, amount: int, location: str = "cash"
    ):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            if amount <= 0:
                return await ctx.send("จำนวนเงินต้องมากกว่า 0")
            location = "bank" if str(location).lower().strip() == "bank" else "cash"
            applied = 0
            for member in role.members:
                if member.bot:
                    continue
                ok, _, _ = await self._change_balance(
                    guild=ctx.guild,
                    member=member,
                    actor=ctx.author,
                    delta=amount,
                    location=location,
                    action="add_money_role",
                    note=f"role:{role.id}",
                )
                if ok:
                    applied += 1
            await ctx.send(f"เพิ่มเงินให้สมาชิกยศ {role.mention} สำเร็จ {applied} คน")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="remove-money-role", help="หักเงินจากสมาชิกทุกคนในบทบาท")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def remove_money_role(
        self, ctx: commands.Context, role: discord.Role, amount: int, location: str = "cash"
    ):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            if amount <= 0:
                return await ctx.send("จำนวนเงินต้องมากกว่า 0")
            location = "bank" if str(location).lower().strip() == "bank" else "cash"
            applied = 0
            for member in role.members:
                if member.bot:
                    continue
                settings = await self._ensure_settings(ctx.guild.id)
                wallet = await self._ensure_wallet(ctx.guild.id, member.id, settings)
                available = (
                    _safe_int(wallet.get("bank"), 0)
                    if location == "bank"
                    else _safe_int(wallet.get("cash"), 0)
                )
                delta = min(amount, max(0, available))
                if delta <= 0:
                    continue
                ok, _, _ = await self._change_balance(
                    guild=ctx.guild,
                    member=member,
                    actor=ctx.author,
                    delta=-delta,
                    location=location,
                    action="remove_money_role",
                    note=f"role:{role.id}",
                )
                if ok:
                    applied += 1
            await ctx.send(f"หักเงินสมาชิกยศ {role.mention} สำเร็จ {applied} คน")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="economy-stats", help="สถิติต่างๆ ของระบบเศรษฐกิจ")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def economy_stats(self, ctx: commands.Context):
        try:
            settings = await self._ensure_settings(ctx.guild.id)
            symbol = str(settings.get("currency_symbol") or "฿")
            wallets = await economy_wallets_db.gets(guild_id=ctx.guild.id)
            wallets = wallets or []
            total_cash = sum(_safe_int(w.get("cash"), 0) for w in wallets)
            total_bank = sum(_safe_int(w.get("bank"), 0) for w in wallets)
            total_wallets = len(wallets)
            embed = discord.Embed(
                title=f"Economy Stats - {ctx.guild.name}",
                color=color.aqua,
                description=(
                    f"จำนวนบัญชี: **{total_wallets:,}**\n"
                    f"เงินสดรวม: **{self._fmt(total_cash, symbol)}**\n"
                    f"ธนาคารรวม: **{self._fmt(total_bank, symbol)}**\n"
                    f"ทรัพย์สินรวม: **{self._fmt(total_cash + total_bank, symbol)}**"
                ),
            )
            await ctx.send(embed=embed)
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="clean-leaderboard", help="ลบผู้ใช้ออกจากลีดเดอร์บอร์ดที่ออกจากเซิร์ฟเวอร์แล้ว")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def clean_leaderboard(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            wallets = await economy_wallets_db.gets(guild_id=ctx.guild.id)
            wallets = wallets or []
            removed = 0
            for row in wallets:
                user_id = _safe_int(row.get("user_id"), 0)
                if user_id <= 0:
                    continue
                if ctx.guild.get_member(user_id) is None:
                    await economy_wallets_db.delete(id=row.get("id"))
                    removed += 1
            await ctx.send(f"ล้าง leaderboard เรียบร้อย ลบข้อมูล {removed} รายการ")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="reset-money", help="รีเซ็ตยอดเงินของสมาชิก")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def reset_money(self, ctx: commands.Context, member: discord.Member):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            settings = await self._ensure_settings(ctx.guild.id)
            wallet = await self._ensure_wallet(ctx.guild.id, member.id, settings)
            before_cash = _safe_int(wallet.get("cash"), 0)
            before_bank = _safe_int(wallet.get("bank"), 0)
            updated = await self._update_wallet_values(wallet, cash=0, bank=0)
            await self._write_audit(
                ctx.guild,
                settings,
                action="reset_money",
                user_id=member.id,
                actor_id=ctx.author.id,
                target_user_id=member.id,
                location="both",
                amount=before_cash + before_bank,
                before_cash=before_cash,
                before_bank=before_bank,
                after_cash=_safe_int(updated.get("cash"), 0),
                after_bank=_safe_int(updated.get("bank"), 0),
            )
            await ctx.send(f"รีเซ็ตเงินของ {member.mention} แล้ว")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="reset-economy", help="รีเซ็ตระบบเศรษฐกิจ")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def reset_economy(self, ctx: commands.Context, confirm: str):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "administrator"):
                return
            if str(confirm).strip().upper() != "CONFIRM":
                return await ctx.send("พิมพ์ `CONFIRM` เพื่อยืนยันการรีเซ็ตระบบเศรษฐกิจทั้งหมด")
            deleted = await economy_wallets_db.delete(guild_id=ctx.guild.id)
            await ctx.send(f"รีเซ็ตระบบ Economy ของกิลด์แล้ว {len(deleted or [])} บัญชี")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(
        name="set-cooldown",
        help="Set cooldown for the work command (ตั้งค่าคูลดาวน์ของคำสั่งทำงาน)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def set_cooldown(self, ctx: commands.Context, seconds: int):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            seconds = max(10, min(86400, seconds))
            settings = await self._ensure_settings(ctx.guild.id)
            await economy_settings_db.update(
                id=settings["id"], work_cooldown=seconds, updated_at=_utc_now()
            )
            await ctx.send(f"ตั้งค่า work cooldown เป็น `{seconds}` วินาที")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(
        name="set-payout",
        help="Set min/max payout for the work command (ตั้งค่าเงินรางวัลขั้นต่ำ/สูงสุดของคำสั่งทำงาน)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def set_payout(self, ctx: commands.Context, minimum: int, maximum: int):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            minimum = max(1, minimum)
            maximum = max(minimum, maximum)
            settings = await self._ensure_settings(ctx.guild.id)
            await economy_settings_db.update(
                id=settings["id"],
                work_payout_min=minimum,
                work_payout_max=maximum,
                updated_at=_utc_now(),
            )
            await ctx.send(f"ตั้งค่า payout ของ work เป็น `{minimum}` - `{maximum}`")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @economy.command(name="set-bet-limit", help="ตั้งค่าขั้นต่ำและขั้นสูงสุดที่อนุญาตสำหรับการเดิมพัน")
    @checks.ignore_check()
    @checks.blacklist_check()
    async def set_bet_limit(self, ctx: commands.Context, minimum: int, maximum: int):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            minimum = max(1, minimum)
            maximum = max(minimum, maximum)
            settings = await self._ensure_settings(ctx.guild.id)
            await economy_settings_db.update(
                id=settings["id"], bet_min=minimum, bet_max=maximum, updated_at=_utc_now()
            )
            await ctx.send(f"ตั้งค่าขีดจำกัดการเดิมพันเป็น `{minimum}` - `{maximum}` แล้ว")
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")


