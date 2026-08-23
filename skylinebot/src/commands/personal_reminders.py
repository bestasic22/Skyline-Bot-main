from __future__ import annotations

import asyncio
import datetime
import re
import time
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

import storage.user_reminders as reminders_store
from skylinebot.bridge.storage import mongo_is_transient_cluster_error
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


MAX_REMINDER_TEXT = 1500
MAX_SECONDS_AHEAD = 180 * 24 * 60 * 60  # 180 days
MIN_SECONDS_AHEAD = 30
_DURATION_TOKEN_RE = re.compile(r"(\d+)\s*([smhdw])", re.IGNORECASE)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


class PersonalReminders(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._transient_db_log_last_at = 0.0
        if ZoneInfo:
            try:
                self._local_tz = ZoneInfo("Asia/Bangkok")
            except Exception:
                self._local_tz = datetime.timezone(datetime.timedelta(hours=7))
        else:
            self._local_tz = datetime.timezone(datetime.timedelta(hours=7))

        class CogInfo:
            name = "PersonalReminders"
            category = "Main"
            description = "Reminder commands"
            hidden = False
            emoji = "⏰"

        self.cog_info = CogInfo

    def _log_scan_error(self, error: Exception) -> None:
        if mongo_is_transient_cluster_error(error):
            now = time.monotonic()
            if (now - float(self._transient_db_log_last_at or 0.0)) >= 45.0:
                self._transient_db_log_last_at = now
                logger.warning(f"Reminder dispatch transient DB issue (will retry): {error}")
            return
        logger.warning(f"Reminder dispatch scan failed: {error}")

    async def cog_load(self):
        if not self.reminder_dispatch_loop.is_running():
            self.reminder_dispatch_loop.start()

    def cog_unload(self):
        if self.reminder_dispatch_loop.is_running():
            self.reminder_dispatch_loop.cancel()

    async def _wait_until_ready_safely(self) -> bool:
        while not self.bot.is_closed():
            if getattr(self.bot, "user", None) is not None and self.bot.is_ready():
                return True
            await asyncio.sleep(1)
        return False

    def _parse_when_to_utc(self, raw: str) -> tuple[datetime.datetime | None, str]:
        text = str(raw or "").strip()
        if not text:
            return None, ""

        # Duration format: 10m, 2h30m, 1d 3h, 45s, 2w
        normalized = text.lower().replace(",", " ")
        matches = list(_DURATION_TOKEN_RE.finditer(normalized))
        if matches:
            consumed = "".join(m.group(0) for m in matches)
            leftover = re.sub(r"\s+", "", normalized.replace(consumed, "", 1))
            # Robust fallback for multiple tokens with spaces by removing all matched spans.
            stripped = list(normalized)
            for m in matches:
                for idx in range(m.start(), m.end()):
                    stripped[idx] = " "
            leftover = "".join(ch for ch in stripped if not ch.isspace())
            if not leftover:
                unit_seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
                total = 0
                for m in matches:
                    amount = _safe_int(m.group(1), 0)
                    unit = m.group(2).lower()
                    total += amount * unit_seconds.get(unit, 0)
                if MIN_SECONDS_AHEAD <= total <= MAX_SECONDS_AHEAD:
                    target = _utc_now() + datetime.timedelta(seconds=total)
                    return target, f"in {total} seconds"
                return None, ""

        # Absolute formats
        now_local = datetime.datetime.now(self._local_tz)
        candidate_formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d/%m/%Y %H:%M",
        ]
        for fmt in candidate_formats:
            try:
                naive = datetime.datetime.strptime(text, fmt)
                local_dt = naive.replace(tzinfo=self._local_tz)
                delta = (local_dt - now_local).total_seconds()
                if MIN_SECONDS_AHEAD <= delta <= MAX_SECONDS_AHEAD:
                    return local_dt.astimezone(datetime.timezone.utc), local_dt.strftime("%Y-%m-%d %H:%M %Z")
                return None, ""
            except Exception:
                continue

        # ISO format support
        try:
            iso_dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            if iso_dt.tzinfo is None:
                iso_dt = iso_dt.replace(tzinfo=self._local_tz)
            delta = (iso_dt.astimezone(self._local_tz) - now_local).total_seconds()
            if MIN_SECONDS_AHEAD <= delta <= MAX_SECONDS_AHEAD:
                return iso_dt.astimezone(datetime.timezone.utc), iso_dt.astimezone(self._local_tz).strftime("%Y-%m-%d %H:%M %Z")
            return None, ""
        except Exception:
            return None, ""

    @staticmethod
    def _as_utc(value: Any) -> datetime.datetime | None:
        if isinstance(value, datetime.datetime):
            return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
        return None

    @staticmethod
    def _fmt_discord_time(dt_utc: datetime.datetime) -> str:
        unix = int(dt_utc.timestamp())
        return f"<t:{unix}:F> (<t:{unix}:R>)"

    async def _dispatch_one(self, row: dict[str, Any]) -> None:
        reminder_id = _safe_int(row.get("id"), 0)
        user_id = _safe_int(row.get("user_id"), 0)
        channel_id = _safe_int(row.get("channel_id"), 0)
        message = str(row.get("message") or "").strip()[:MAX_REMINDER_TEXT]
        now_utc = _utc_now()
        retry_count = _safe_int(row.get("retry_count"), 0)

        if reminder_id <= 0 or user_id <= 0 or not message:
            await reminders_store.update(
                id=reminder_id,
                status="failed",
                last_error="invalid reminder payload",
                retry_count=retry_count + 1,
                updated_at=now_utc,
            )
            return

        send_error = ""
        sent = False
        allowed = discord.AllowedMentions(users=True, roles=False, everyone=False)
        content = f"⏰ Reminder for <@{user_id}>:\n{message}"

        # Try source channel first
        if channel_id > 0:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    channel = None
            if channel is not None:
                try:
                    await channel.send(content, allowed_mentions=allowed)
                    sent = True
                except Exception as error:
                    send_error = f"channel_send_failed:{type(error).__name__}"

        # Fallback to DM
        if not sent:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                if user is not None:
                    await user.send(f"⏰ Reminder:\n{message}")
                    sent = True
            except Exception as error:
                send_error = f"dm_send_failed:{type(error).__name__}"

        if sent:
            await reminders_store.update(
                id=reminder_id,
                status="sent",
                sent_at=now_utc,
                updated_at=now_utc,
                last_error="",
            )
            return

        next_retry = retry_count + 1
        final_status = "failed" if next_retry >= 3 else "pending"
        await reminders_store.update(
            id=reminder_id,
            status=final_status,
            retry_count=next_retry,
            last_error=(send_error or "unknown_send_error")[:220],
            updated_at=now_utc,
        )

    @tasks.loop(seconds=20)
    async def reminder_dispatch_loop(self):
        if not (getattr(self.bot, "user", None) is not None and self.bot.is_ready()):
            return
        try:
            rows = await reminders_store.gets(status="pending")
        except Exception as error:
            self._log_scan_error(error)
            return

        if not rows:
            return
        now_utc = _utc_now()
        due: list[dict[str, Any]] = []
        for row in rows:
            dt = self._as_utc(row.get("remind_at"))
            if dt and dt <= now_utc:
                due.append(row)
        due.sort(key=lambda item: (self._as_utc(item.get("remind_at")) or now_utc, _safe_int(item.get("id"), 0)))
        for row in due[:50]:
            try:
                await self._dispatch_one(row)
            except Exception as error:
                logger.warning(f"Reminder dispatch failed for id={row.get('id')}: {error}")

    @reminder_dispatch_loop.before_loop
    async def before_reminder_dispatch_loop(self):
        await self._wait_until_ready_safely()

    @commands.hybrid_group(
        name="reminder",
        with_app_command=True,
        help="คำสั่งเตือนความจำ",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def reminder_group(self, ctx: commands.Context):
        await ctx.send(
            "Reminder commands:\n"
            "`/reminder add <when> <message>`\n"
            "`/reminder list`\n"
            "`/reminder next`\n"
            "`/reminder cancel <id>`\n"
            "`/reminder clear`\n\n"
            "Examples for `when`: `10m`, `2h30m`, `1d`, `2026-05-20 14:30`"
        )

    @reminder_group.command(
        name="add",
        help="Create a reminder (สร้างการเตือน)",
        description="Create a reminder (สร้างการเตือน)",
    )
    @app_commands.describe(when="e.g. 10m, 2h30m, 1d, 2026-05-20 14:30", message="Reminder message")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def reminder_add(self, ctx: commands.Context, when: str, *, message: str):
        clean_message = str(message or "").strip()[:MAX_REMINDER_TEXT]
        if not clean_message:
            return await ctx.send("Reminder message cannot be empty.")

        remind_at_utc, parsed_text = self._parse_when_to_utc(when)
        if not remind_at_utc:
            return await ctx.send(
                "Invalid `when` format.\n"
                "Use duration (`10m`, `2h30m`, `1d`) or date-time (`2026-05-20 14:30`)."
            )

        now_utc = _utc_now()
        row = await reminders_store.insert(
            user_id=int(ctx.author.id),
            guild_id=int(ctx.guild.id) if ctx.guild else 0,
            channel_id=int(ctx.channel.id) if ctx.channel else 0,
            message=clean_message,
            status="pending",
            retry_count=0,
            remind_at=remind_at_utc,
            updated_at=now_utc,
        )
        reminder_id = _safe_int((row or {}).get("id"), 0)
        await ctx.send(
            f"Saved reminder `#{reminder_id}` for {self._fmt_discord_time(remind_at_utc)}.\n"
            f"Parsed: `{parsed_text}`"
        )

    @reminder_group.command(
        name="list",
        help="List your pending reminders (แสดงรายการเตือนที่รอดำเนินการ)",
        description="List your pending reminders (แสดงรายการเตือนที่รอดำเนินการ)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def reminder_list(self, ctx: commands.Context):
        rows = await reminders_store.gets(user_id=int(ctx.author.id), status="pending")
        if not rows:
            return await ctx.send("You have no pending reminders.")
        items = []
        now_utc = _utc_now()
        for row in rows:
            dt = self._as_utc(row.get("remind_at"))
            if not dt:
                continue
            if dt < now_utc - datetime.timedelta(days=1):
                continue
            reminder_id = _safe_int(row.get("id"), 0)
            msg = str(row.get("message") or "").replace("\n", " ").strip()
            msg_short = (msg[:70] + "...") if len(msg) > 70 else msg
            items.append((dt, f"`#{reminder_id}` {self._fmt_discord_time(dt)} - {msg_short}"))
        if not items:
            return await ctx.send("You have no valid pending reminders.")
        items.sort(key=lambda x: x[0])
        lines = [line for _, line in items[:20]]
        await ctx.send("Your pending reminders:\n" + "\n".join(lines))

    @reminder_group.command(
        name="next",
        help="Show your next reminder (ดูรายการเตือนถัดไป)",
        description="Show your next reminder (ดูรายการเตือนถัดไป)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def reminder_next(self, ctx: commands.Context):
        rows = await reminders_store.gets(user_id=int(ctx.author.id), status="pending")
        next_row = None
        next_dt = None
        for row in rows:
            dt = self._as_utc(row.get("remind_at"))
            if not dt:
                continue
            if next_dt is None or dt < next_dt:
                next_dt = dt
                next_row = row
        if not next_row or not next_dt:
            return await ctx.send("You have no pending reminders.")
        reminder_id = _safe_int(next_row.get("id"), 0)
        msg = str(next_row.get("message") or "").strip()
        await ctx.send(
            f"Next reminder is `#{reminder_id}` at {self._fmt_discord_time(next_dt)}\n"
            f"Message: {msg}"
        )

    @reminder_group.command(
        name="cancel",
        help="Cancel a reminder by ID (ยกเลิกรายการเตือนตาม ID)",
        description="Cancel a reminder by ID (ยกเลิกรายการเตือนตาม ID)",
    )
    @app_commands.describe(reminder_id="Reminder ID")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def reminder_cancel(self, ctx: commands.Context, reminder_id: int):
        row = await reminders_store.get(id=int(reminder_id), user_id=int(ctx.author.id))
        if not row:
            return await ctx.send("Reminder not found.")
        if str(row.get("status") or "") != "pending":
            return await ctx.send("Only pending reminders can be cancelled.")
        now_utc = _utc_now()
        await reminders_store.update(
            id=int(reminder_id),
            status="cancelled",
            cancelled_at=now_utc,
            updated_at=now_utc,
        )
        await ctx.send(f"Cancelled reminder `#{int(reminder_id)}`.")

    @reminder_group.command(
        name="clear",
        help="Clear all pending reminders (ล้างรายการเตือนที่รอดำเนินการทั้งหมด)",
        description="Clear all pending reminders (ล้างรายการเตือนที่รอดำเนินการทั้งหมด)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=25, type=commands.BucketType.user)
    async def reminder_clear(self, ctx: commands.Context):
        deleted = await reminders_store.delete(user_id=int(ctx.author.id), status="pending")
        count = len(deleted or [])
        await ctx.send(f"Cleared {count} pending reminder(s).")


