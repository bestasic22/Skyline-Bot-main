import asyncio
import datetime
import json
import time
from typing import Any

import discord
from discord.ext import commands, tasks

import storage.dashboard_config
import storage.users
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.memory.cache import cache
from skylinebot.src.checks import checks
from skylinebot.src.checks.variables import fetch_variables
from skylinebot.style import color

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


BIRTHDAY_GUILD_CONFIG_KEY_PREFIX = "birthday_v1_guild_"
DEFAULT_BIRTHDAY_MESSAGE = "🎂 สุขสันต์วันเกิด {user.mention}! ขอให้มีความสุขมากๆ จาก {server}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "enabled", "enable"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "disable"}:
        return False
    return bool(default)


class Birthday(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._guild_settings_cache: dict[int, dict[str, Any]] = {}
        self._guild_settings_expire: dict[int, float] = {}
        self._guild_settings_ttl_seconds = 300.0
        self._announced_date_by_guild: dict[int, str] = {}
        self._announce_hour = max(0, min(23, _safe_int(timezone_hour_env("BIRTHDAY_ANNOUNCE_HOUR"), 9)))
        if ZoneInfo:
            try:
                self._tz = ZoneInfo("Asia/Bangkok")
            except Exception:
                self._tz = datetime.timezone(datetime.timedelta(hours=7))
        else:
            self._tz = datetime.timezone(datetime.timedelta(hours=7))

        class CogInfo:
            name = "Birthday"
            category = "Main"
            description = "Birthday commands"
            hidden = False
            emoji = "🎂"

        self.cog_info = CogInfo

    async def cog_load(self):
        if not self.birthday_dispatch_loop.is_running():
            self.birthday_dispatch_loop.start()

    def cog_unload(self):
        if self.birthday_dispatch_loop.is_running():
            self.birthday_dispatch_loop.cancel()

    async def _wait_until_ready_safely(self) -> bool:
        while not self.bot.is_closed():
            if getattr(self.bot, "user", None) is not None and self.bot.is_ready():
                return True
            await asyncio.sleep(1)
        return False

    @staticmethod
    def _guild_config_key(guild_id: int) -> str:
        return f"{BIRTHDAY_GUILD_CONFIG_KEY_PREFIX}{int(guild_id)}"

    @staticmethod
    def _default_guild_settings() -> dict[str, Any]:
        return {
            "enabled": False,
            "channel_id": 0,
            "message": DEFAULT_BIRTHDAY_MESSAGE,
        }

    @classmethod
    def _normalize_guild_settings(cls, payload: dict[str, Any] | None) -> dict[str, Any]:
        src = payload if isinstance(payload, dict) else {}
        out = cls._default_guild_settings()
        out["enabled"] = _safe_bool(src.get("enabled"), False)
        channel_id = _safe_int(src.get("channel_id"), 0)
        out["channel_id"] = channel_id if channel_id > 0 else 0
        out["message"] = str(src.get("message") or DEFAULT_BIRTHDAY_MESSAGE).strip()[:900] or DEFAULT_BIRTHDAY_MESSAGE
        return out

    async def _get_guild_settings(self, guild_id: int, *, force: bool = False) -> dict[str, Any]:
        guild_id_int = int(guild_id)
        now_ts = time.monotonic()
        if not force:
            cached = self._guild_settings_cache.get(guild_id_int)
            expire_at = float(self._guild_settings_expire.get(guild_id_int, 0.0) or 0.0)
            if cached is not None and now_ts < expire_at:
                return cached

        settings = self._default_guild_settings()
        try:
            row = await storage.dashboard_config.get(config_key=self._guild_config_key(guild_id_int))
            if row and isinstance(row, dict):
                raw = str(row.get("config_value") or "").strip()
                if raw:
                    decoded = json.loads(raw)
                    if isinstance(decoded, dict):
                        settings = self._normalize_guild_settings(decoded)
        except Exception as error:
            logger.warning(f"Birthday settings load failed for guild {guild_id_int}: {error}")

        self._guild_settings_cache[guild_id_int] = settings
        self._guild_settings_expire[guild_id_int] = now_ts + self._guild_settings_ttl_seconds
        return settings

    async def _save_guild_settings(self, guild_id: int, settings: dict[str, Any]) -> dict[str, Any]:
        guild_id_int = int(guild_id)
        payload = self._normalize_guild_settings(settings)
        row = await storage.dashboard_config.get(config_key=self._guild_config_key(guild_id_int))
        encoded = json.dumps(payload, ensure_ascii=False)
        if row and row.get("id"):
            await storage.dashboard_config.update(
                id=row["id"],
                config_key=self._guild_config_key(guild_id_int),
                config_value=encoded,
            )
        else:
            await storage.dashboard_config.insert(
                config_key=self._guild_config_key(guild_id_int),
                config_value=encoded,
            )
        self._guild_settings_cache[guild_id_int] = payload
        self._guild_settings_expire[guild_id_int] = time.monotonic() + self._guild_settings_ttl_seconds
        return payload

    async def _ensure_user_row(self, user_id: int) -> dict[str, Any] | None:
        cached = cache.users.get(str(user_id), {})
        if cached and cached.get("id"):
            return cached
        try:
            created = await storage.users.insert(user_id=int(user_id))
            if created:
                return created
        except Exception:
            pass
        try:
            return await storage.users.get(user_id=int(user_id))
        except Exception:
            return None

    @staticmethod
    def _user_birthday_data(user_row: dict[str, Any] | None) -> tuple[int, int, int, bool]:
        if not isinstance(user_row, dict):
            return 0, 0, 0, True
        day = _safe_int(user_row.get("birthday_day"), 0)
        month = _safe_int(user_row.get("birthday_month"), 0)
        year = _safe_int(user_row.get("birthday_year"), 0)
        notify_enabled = _safe_bool(user_row.get("birthday_notify_enabled"), True)
        return day, month, year, notify_enabled

    @staticmethod
    def _is_valid_birthday(day: int, month: int, year: int | None = None) -> bool:
        if day <= 0 or month <= 0:
            return False
        if year and year > 0:
            try:
                datetime.date(year, month, day)
                return True
            except Exception:
                return False
        leap_reference = 2004 if (month == 2 and day == 29) else 2001
        try:
            datetime.date(leap_reference, month, day)
            return True
        except Exception:
            return False

    def _birthday_age(self, year: int, now_dt: datetime.datetime) -> int | None:
        if year <= 1900:
            return None
        age = int(now_dt.year) - int(year)
        if age <= 0:
            return None
        return age

    def _members_with_birthday_today(
        self, guild: discord.Guild, *, day: int, month: int
    ) -> list[discord.Member]:
        rows: list[discord.Member] = []
        for member in guild.members:
            if member.bot:
                continue
            user_row = cache.users.get(str(member.id), {})
            bday_day, bday_month, _, notify_enabled = self._user_birthday_data(user_row)
            if not notify_enabled:
                continue
            if bday_day == int(day) and bday_month == int(month):
                rows.append(member)
        rows.sort(key=lambda item: item.display_name.lower())
        return rows

    async def _send_birthday_message(
        self,
        *,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        member: discord.Member,
        settings: dict[str, Any],
        now_dt: datetime.datetime,
    ) -> None:
        template = str(settings.get("message") or DEFAULT_BIRTHDAY_MESSAGE).strip() or DEFAULT_BIRTHDAY_MESSAGE
        content = fetch_variables(
            text=template,
            member=member,
            guild=guild,
            channel=channel,
        ) or f"🎂 สุขสันต์วันเกิด {member.mention}!"
        user_row = cache.users.get(str(member.id), {})
        _, _, year, _ = self._user_birthday_data(user_row)
        age = self._birthday_age(year, now_dt)
        if age is not None:
            content += f"\n-# อายุ {age} ปี"
        await channel.send(
            content=content,
            allowed_mentions=discord.AllowedMentions(
                users=True, roles=False, everyone=False, replied_user=False
            ),
        )

    async def _send_today_birthdays_for_guild(
        self, *, guild: discord.Guild, now_dt: datetime.datetime
    ) -> str:
        settings = await self._get_guild_settings(guild.id)
        if not settings.get("enabled"):
            return "not_configured"
        channel_id = _safe_int(settings.get("channel_id"), 0)
        if channel_id <= 0:
            return "not_configured"

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                fetched = await self.bot.fetch_channel(channel_id)
                if isinstance(fetched, (discord.TextChannel, discord.Thread)):
                    channel = fetched
            except Exception:
                channel = None
        if channel is None:
            return "missing_channel"

        members = self._members_with_birthday_today(
            guild, day=now_dt.day, month=now_dt.month
        )
        if not members:
            return "no_birthdays"

        for member in members:
            try:
                await self._send_birthday_message(
                    guild=guild,
                    channel=channel,
                    member=member,
                    settings=settings,
                    now_dt=now_dt,
                )
            except Exception as error:
                logger.warning(
                    f"Birthday message failed in guild {guild.id} for member {member.id}: {error}"
                )
            await asyncio.sleep(0.6)
        return "sent"

    async def _require_guild_admin(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์")
            return False
        if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
            return False
        return True

    @tasks.loop(minutes=30)
    async def birthday_dispatch_loop(self):
        now_dt = datetime.datetime.now(self._tz)
        today_iso = now_dt.date().isoformat()
        if now_dt.hour < self._announce_hour:
            return
        if len(self._announced_date_by_guild) > 2000:
            self._announced_date_by_guild = {
                gid: day
                for gid, day in self._announced_date_by_guild.items()
                if day == today_iso
            }
        for guild in self.bot.guilds:
            if self._announced_date_by_guild.get(guild.id) == today_iso:
                continue
            try:
                result = await self._send_today_birthdays_for_guild(
                    guild=guild,
                    now_dt=now_dt,
                )
                if result == "sent":
                    logger.info(
                        f"Birthday notifications sent in guild {guild.id} ({guild.name})"
                    )
                if result in {"sent", "no_birthdays"}:
                    self._announced_date_by_guild[guild.id] = today_iso
            except Exception as error:
                logger.warning(
                    f"Birthday dispatch failed in guild {guild.id} ({guild.name}): {error}"
                )

    @birthday_dispatch_loop.before_loop
    async def before_birthday_dispatch_loop(self):
        await self._wait_until_ready_safely()

    @commands.hybrid_group(
        name="birthday",
        aliases=["bday"],
        with_app_command=True,
        invoke_without_command=True,
        help="ระบบวันเกิดและแจ้งเตือนวันเกิด",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def birthday_group(self, ctx: commands.Context):
        user_row = await self._ensure_user_row(ctx.author.id)
        day, month, year, notify_enabled = self._user_birthday_data(user_row)
        embed = discord.Embed(
            title="🎂 ระบบวันเกิด",
            color=color.blue,
        )
        if day > 0 and month > 0:
            birthday_text = f"{day:02d}/{month:02d}"
            if year > 0:
                birthday_text += f"/{year}"
            embed.description = f"วันเกิดของคุณ: **{birthday_text}**\nแจ้งเตือนส่วนตัว: **{'เปิด' if notify_enabled else 'ปิด'}**"
        else:
            embed.description = "คุณยังไม่ได้ตั้งวันเกิด\nใช้ `/birthday set day month year(optional)` เพื่อตั้งค่า"
        if ctx.guild:
            settings = await self._get_guild_settings(ctx.guild.id)
            channel_id = _safe_int(settings.get("channel_id"), 0)
            channel_text = f"<#{channel_id}>" if channel_id > 0 else "`ยังไม่ตั้งค่า`"
            embed.add_field(
                name="การแจ้งเตือนวันเกิดในกิลด์",
                value=f"สถานะ: **{'เปิด' if settings.get('enabled') else 'ปิด'}**\nห้อง: {channel_text}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @birthday_group.command(
        name="set",
        help="Set your birthday date (ตั้งวันเกิดของคุณ)",
        description="Set your birthday date (ตั้งวันเกิดของคุณ)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=25, type=commands.BucketType.user)
    async def birthday_set(
        self,
        ctx: commands.Context,
        day: int,
        month: int,
        year: int | None = None,
    ):
        now_dt = datetime.datetime.now(self._tz)
        year_value = _safe_int(year, 0) if year is not None else 0
        if year is not None and (year_value < 1900 or year_value > now_dt.year):
            await ctx.send("ปีเกิดไม่ถูกต้อง (รองรับช่วง 1900 ถึงปีปัจจุบัน)")
            return
        if not self._is_valid_birthday(day, month, year_value if year_value > 0 else None):
            await ctx.send("รูปแบบวันเกิดไม่ถูกต้อง กรุณาตรวจสอบวัน/เดือน/ปีอีกครั้ง")
            return

        user_row = await self._ensure_user_row(ctx.author.id)
        if not user_row or not user_row.get("id"):
            await ctx.send("ไม่สามารถบันทึกวันเกิดได้ในตอนนี้ กรุณาลองใหม่อีกครั้ง")
            return

        await storage.users.update(
            id=user_row["id"],
            user_id=ctx.author.id,
            birthday_day=int(day),
            birthday_month=int(month),
            birthday_year=int(year_value),
        )
        birthday_text = f"{int(day):02d}/{int(month):02d}"
        if year_value > 0:
            birthday_text += f"/{year_value}"
        await ctx.send(f"บันทึกวันเกิดของคุณเป็น **{birthday_text}** แล้ว")

    @birthday_group.command(
        name="clear",
        help="Clear your saved birthday date (ลบวันเกิดที่บันทึกไว้)",
        description="Clear your saved birthday date (ลบวันเกิดที่บันทึกไว้)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def birthday_clear(self, ctx: commands.Context):
        user_row = await self._ensure_user_row(ctx.author.id)
        if not user_row or not user_row.get("id"):
            await ctx.send("ไม่พบข้อมูลผู้ใช้สำหรับลบวันเกิด")
            return
        await storage.users.update(
            id=user_row["id"],
            user_id=ctx.author.id,
            birthday_day=0,
            birthday_month=0,
            birthday_year=0,
        )
        await ctx.send("ลบวันเกิดของคุณเรียบร้อยแล้ว")

    @birthday_group.command(
        name="me",
        help="Show your birthday profile (ดูข้อมูลวันเกิดของคุณ)",
        description="Show your birthday profile (ดูข้อมูลวันเกิดของคุณ)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def birthday_me(self, ctx: commands.Context):
        user_row = await self._ensure_user_row(ctx.author.id)
        day, month, year, notify_enabled = self._user_birthday_data(user_row)
        if day <= 0 or month <= 0:
            await ctx.send("คุณยังไม่ได้ตั้งวันเกิด ใช้ `/birthday set day month year(optional)`")
            return
        birthday_text = f"{day:02d}/{month:02d}"
        if year > 0:
            birthday_text += f"/{year}"
        age = self._birthday_age(year, datetime.datetime.now(self._tz))
        age_text = f"\nอายุโดยประมาณ: **{age} ปี**" if age is not None else ""
        await ctx.send(
            f"วันเกิดของคุณคือ **{birthday_text}**{age_text}\nแจ้งเตือนส่วนตัว: **{'เปิด' if notify_enabled else 'ปิด'}**"
        )

    @birthday_group.command(
        name="notify",
        help="Toggle personal birthday notifications (เปิดหรือปิดแจ้งเตือนวันเกิดส่วนตัว)",
        description="Toggle personal birthday notifications (เปิดหรือปิดแจ้งเตือนวันเกิดส่วนตัว)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def birthday_notify(self, ctx: commands.Context, enabled: bool):
        user_row = await self._ensure_user_row(ctx.author.id)
        if not user_row or not user_row.get("id"):
            await ctx.send("ไม่พบข้อมูลผู้ใช้")
            return
        await storage.users.update(
            id=user_row["id"],
            user_id=ctx.author.id,
            birthday_notify_enabled=bool(enabled),
        )
        await ctx.send(
            f"ตั้งค่าแจ้งเตือนวันเกิดสำหรับบัญชีของคุณเป็น **{'เปิด' if enabled else 'ปิด'}** แล้ว"
        )

    @birthday_group.command(
        name="today",
        help="List members with birthdays today (แสดงสมาชิกที่มีวันเกิดวันนี้)",
        description="List members with birthdays today (แสดงสมาชิกที่มีวันเกิดวันนี้)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=25, type=commands.BucketType.user)
    async def birthday_today(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์")
            return
        now_dt = datetime.datetime.now(self._tz)
        members = self._members_with_birthday_today(
            ctx.guild,
            day=now_dt.day,
            month=now_dt.month,
        )
        if not members:
            await ctx.send("วันนี้ยังไม่มีสมาชิกที่ตั้งวันเกิดตรงกับวันนี้")
            return
        lines = []
        for index, member in enumerate(members[:25], start=1):
            user_row = cache.users.get(str(member.id), {})
            _, _, year, _ = self._user_birthday_data(user_row)
            age = self._birthday_age(year, now_dt)
            suffix = f" (อายุ {age})" if age is not None else ""
            lines.append(f"`#{index}` {member.mention}{suffix}")
        embed = discord.Embed(
            title=f"🎂 Birthday Today ({now_dt.day:02d}/{now_dt.month:02d})",
            description="\n".join(lines),
            color=color.green,
        )
        await ctx.send(embed=embed)

    @birthday_group.command(
        name="channel",
        help="Set the birthday announcement channel (ตั้งค่าห้องประกาศวันเกิด)",
        description="Set the birthday announcement channel (ตั้งค่าห้องประกาศวันเกิด)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.guild)
    async def birthday_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        if not await self._require_guild_admin(ctx):
            return
        settings = await self._get_guild_settings(ctx.guild.id, force=True)
        settings["enabled"] = True
        settings["channel_id"] = int(channel.id)
        await self._save_guild_settings(ctx.guild.id, settings)
        await ctx.send(
            f"ตั้งค่าห้องแจ้งเตือนวันเกิดเป็น {channel.mention} และเปิดระบบเรียบร้อยแล้ว"
        )

    @birthday_group.command(
        name="disable",
        help="Disable guild birthday announcements (ปิดระบบประกาศวันเกิดของเซิร์ฟเวอร์)",
        description="Disable guild birthday announcements (ปิดระบบประกาศวันเกิดของเซิร์ฟเวอร์)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.guild)
    async def birthday_disable(self, ctx: commands.Context):
        if not await self._require_guild_admin(ctx):
            return
        settings = await self._get_guild_settings(ctx.guild.id, force=True)
        settings["enabled"] = False
        await self._save_guild_settings(ctx.guild.id, settings)
        await ctx.send("ปิดระบบแจ้งเตือนวันเกิดของกิลด์เรียบร้อยแล้ว")

    @birthday_group.command(
        name="message",
        help="Set the birthday announcement template (ตั้งค่าข้อความประกาศวันเกิด)",
        description="Set the birthday announcement template (ตั้งค่าข้อความประกาศวันเกิด)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.guild)
    async def birthday_message(self, ctx: commands.Context, *, message: str):
        if not await self._require_guild_admin(ctx):
            return
        clean_message = str(message or "").strip()[:900]
        if not clean_message:
            await ctx.send("ข้อความแจ้งเตือนห้ามว่าง")
            return
        settings = await self._get_guild_settings(ctx.guild.id, force=True)
        settings["message"] = clean_message
        await self._save_guild_settings(ctx.guild.id, settings)
        await ctx.send(
            "บันทึกข้อความแจ้งเตือนวันเกิดแล้ว\nตัวแปรที่รองรับ: `{user}` `{user.mention}` `{server}` `{member.count}` `{channel.id}`"
        )

    @birthday_group.command(
        name="test",
        help="Send a test birthday announcement (ส่งข้อความทดสอบวันเกิด)",
        description="Send a test birthday announcement (ส่งข้อความทดสอบวันเกิด)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.guild)
    async def birthday_test(
        self, ctx: commands.Context, member: discord.Member | None = None
    ):
        if not await self._require_guild_admin(ctx):
            return
        settings = await self._get_guild_settings(ctx.guild.id, force=True)
        channel_id = _safe_int(settings.get("channel_id"), 0)
        if channel_id <= 0:
            await ctx.send("ยังไม่ได้ตั้งค่าห้องแจ้งเตือนวันเกิด ใช้ `/birthday channel` ก่อน")
            return
        channel = ctx.guild.get_channel(channel_id)
        if not channel:
            await ctx.send("ไม่พบห้องที่ตั้งค่าไว้ กรุณาตั้งค่าใหม่อีกครั้ง")
            return
        target = member or ctx.author
        await self._send_birthday_message(
            guild=ctx.guild,
            channel=channel,
            member=target,
            settings=settings,
            now_dt=datetime.datetime.now(self._tz),
        )
        await ctx.send(f"ส่งข้อความทดสอบไปที่ {channel.mention} เรียบร้อยแล้ว")


def timezone_hour_env(name: str) -> str:
    try:
        import os

        return str(os.getenv(name, "9") or "9").strip()
    except Exception:
        return "9"


