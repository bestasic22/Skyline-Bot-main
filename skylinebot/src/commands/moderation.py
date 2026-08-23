import discord
from discord.ext import commands
import datetime
import re
from skylinebot.src.checks import checks
from skylinebot.memory.cache import cache

import storage.guilds
import storage.ignore_data
import storage.media_channels
import storage.promote_channels
import storage.ai_chat_channels
from skylinebot.console.logging import logger

from skylinebot.style import color
from skylinebot.style import urls as style_urls
from skylinebot.utils import pings
from skylinebot.utils import i18n

PROMOTE_COOLDOWN_SECONDS = 12 * 3600
PROMOTE_COOLDOWN_HOURS = 12
PROMOTE_SAVED_LIMITS_BY_PLAN = {
    "free": 0,
    "silver": 1,
    "golden": 2,
    "diamond": 5,
}
DELAST_LIMITS_BY_PLAN = {
    "free": 100,
    "silver": 200,
    "golden": 400,
    "diamond": 500,
}
DELETE_MODE_VALUES = frozenset(
    {
        "messages",
        "specificuser",
        "embeds",
        "emojis",
        "links",
        "usermessages",
        "botmessages",
        "deleteall",
    }
)
DELETE_MODE_LABELS = {
    "messages": "ลบข้อความทั่วไป",
    "specificuser": "ลบข้อความของผู้ใช้ที่ระบุ",
    "embeds": "ลบข้อความที่มี Embed",
    "emojis": "ลบข้อความที่มี Emoji",
    "links": "ลบข้อความที่มีลิงก์",
    "usermessages": "ลบข้อความของสมาชิก",
    "botmessages": "ลบข้อความของบอท",
    "deleteall": "ลบทุกข้อความตามช่วง/จำนวน",
}
LINK_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:[a-zA-Z0-9_]{2,}:[0-9]{5,}>")
UNICODE_EMOJI_PATTERN = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def _normalize_promote_plan_tier(raw_value):
    normalized = str(raw_value or "free").strip().lower().replace(" ", "_")
    mapping = {
        "free": "free",
        "basic": "free",
        "silver": "silver",
        "silver_guild_preminum": "silver",
        "premium_silver": "silver",
        "gold": "golden",
        "golden": "golden",
        "golden_guild_premium": "golden",
        "pro": "golden",
        "diamond": "diamond",
        "diamond_guild_premium": "diamond",
        "permanent": "diamond",
        "lifetime": "diamond",
        "forever": "diamond",
        "permanent_guild_premium": "diamond",
        "lifetime_guild_premium": "diamond",
        "ultra": "diamond",
    }
    return mapping.get(normalized, "free")


def _promote_saved_limit(raw_plan):
    tier = _normalize_promote_plan_tier(raw_plan)
    return int(PROMOTE_SAVED_LIMITS_BY_PLAN.get(tier, 0))


def _delast_limit(raw_plan):
    tier = _normalize_promote_plan_tier(raw_plan)
    return int(DELAST_LIMITS_BY_PLAN.get(tier, 100))


def _parse_message_id(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw
    if "/" in candidate:
        candidate = candidate.rstrip("/").split("/")[-1].strip()
    if "?" in candidate:
        candidate = candidate.split("?", 1)[0].strip()
    if candidate.startswith("<") and candidate.endswith(">"):
        candidate = candidate[1:-1].strip()
    if not candidate.isdigit():
        return None
    parsed = int(candidate)
    if parsed <= 0:
        return None
    return parsed


def _normalize_delete_mode(raw_value):
    value = str(raw_value or "messages").strip().lower()
    aliases = {
        "message": "messages",
        "msg": "messages",
        "user": "specificuser",
        "embed": "embeds",
        "emoji": "emojis",
        "link": "links",
        "users": "usermessages",
        "bots": "botmessages",
        "all": "deleteall",
    }
    normalized = aliases.get(value, value)
    if normalized not in DELETE_MODE_VALUES:
        return "messages"
    return normalized


def _extract_links_from_text(value):
    text = str(value or "")
    if not text:
        return []
    return LINK_PATTERN.findall(text)


def _collect_message_links(message: discord.Message):
    collected: list[str] = []
    collected.extend(_extract_links_from_text(getattr(message, "content", "")))

    for attachment in getattr(message, "attachments", []) or []:
        attachment_url = str(getattr(attachment, "url", "") or "").strip()
        if attachment_url:
            collected.append(attachment_url)

    for embed in getattr(message, "embeds", []) or []:
        collected.extend(_extract_links_from_text(getattr(embed, "url", None)))
        collected.extend(_extract_links_from_text(getattr(embed, "title", None)))
        collected.extend(_extract_links_from_text(getattr(embed, "description", None)))
        thumbnail = getattr(embed, "thumbnail", None)
        image = getattr(embed, "image", None)
        thumb_url = str(getattr(thumbnail, "url", "") or "").strip()
        image_url = str(getattr(image, "url", "") or "").strip()
        if thumb_url:
            collected.append(thumb_url)
        if image_url:
            collected.append(image_url)

    deduped: list[str] = []
    seen: set[str] = set()
    for link in collected:
        normalized = str(link).strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(normalized)
    return deduped


def _message_contains_emoji(message: discord.Message):
    content = str(getattr(message, "content", "") or "")
    if not content:
        return False
    return bool(CUSTOM_EMOJI_PATTERN.search(content) or UNICODE_EMOJI_PATTERN.search(content))


def _message_matches_delete_mode(
    message: discord.Message,
    *,
    mode: str,
    selected_user_id: int | None = None,
    link_filter: str | None = None,
):
    author = getattr(message, "author", None)
    author_id = int(getattr(author, "id", 0) or 0)
    author_is_bot = bool(getattr(author, "bot", False))

    if mode in {"messages", "deleteall"}:
        return True
    if mode == "specificuser":
        return selected_user_id is not None and author_id == selected_user_id
    if mode == "usermessages":
        if author_is_bot:
            return False
        if selected_user_id is not None:
            return author_id == selected_user_id
        return True
    if mode == "botmessages":
        if selected_user_id is not None:
            return author_id == selected_user_id and author_is_bot
        return author_is_bot
    if mode == "embeds":
        return bool(getattr(message, "embeds", []))
    if mode == "emojis":
        return _message_contains_emoji(message)
    if mode == "links":
        links = _collect_message_links(message)
        if not links:
            return False
        normalized_filter = str(link_filter or "").strip().lower()
        if not normalized_filter or normalized_filter == "all":
            return True
        return any(normalized_filter in link.lower() for link in links)
    return False


async def _delete_messages_with_fallback(
    channel,
    messages: list[discord.Message],
    *,
    reason: str,
) -> tuple[list[int], int]:
    if not messages:
        return [], 0

    now_utc = discord.utils.utcnow()
    bulk_cutoff = now_utc - datetime.timedelta(days=14)
    recent_messages = [
        message for message in messages if message.created_at >= bulk_cutoff
    ]
    older_messages = [message for message in messages if message.created_at < bulk_cutoff]

    deleted_ids: list[int] = []
    failed_count = 0
    delete_many = getattr(channel, "delete_messages", None)

    for start in range(0, len(recent_messages), 100):
        chunk = recent_messages[start : start + 100]
        if not chunk:
            continue
        if len(chunk) > 1 and callable(delete_many):
            try:
                await delete_many(chunk, reason=reason)
                deleted_ids.extend(int(message.id) for message in chunk)
                continue
            except Exception:
                pass
        for message in chunk:
            try:
                await message.delete(reason=reason)
                deleted_ids.append(int(message.id))
            except Exception:
                failed_count += 1

    for message in older_messages:
        try:
            await message.delete(reason=reason)
            deleted_ids.append(int(message.id))
        except Exception:
            failed_count += 1

    return deleted_ids, failed_count

from skylinebot.config.config import BotConfigClass
BotConfig = BotConfigClass()

import traceback, sys

import storage
import asyncio
import json


from skylinebot.engine.bot_runtime import AutoShardedBot

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot:AutoShardedBot = bot
        class CogInfo:
            name =  "Moderation"
            category = "Main"
            description =  "Moderation commands"
            hidden =  False
            emoji =  self.bot.emoji.MODERATION 
        self.cog_info = CogInfo

    def _bot_can_manage_channel(self, guild: discord.Guild, channel: discord.abc.GuildChannel) -> tuple[bool, list[str]]:
        bot_member = guild.me or guild.get_member(getattr(self.bot.user, "id", 0))
        if bot_member is None:
            return False, ["ไม่พบบัญชีบอทในกิลด์นี้"]
        perms = channel.permissions_for(bot_member)
        missing: list[str] = []
        if not perms.manage_channels:
            missing.append("Manage Channels")
        if not perms.manage_roles:
            missing.append("Manage Roles")
        return len(missing) == 0, missing

    @staticmethod
    def _channel_permission_gaps(
        channels: list[discord.abc.GuildChannel],
        bot_member: discord.Member,
        required: dict[str, str],
    ) -> list[tuple[discord.abc.GuildChannel, list[str]]]:
        gaps: list[tuple[discord.abc.GuildChannel, list[str]]] = []
        for channel in channels:
            try:
                perms = channel.permissions_for(bot_member)
            except Exception:
                continue
            missing = [label for perm_name, label in required.items() if not getattr(perms, perm_name, False)]
            if missing:
                gaps.append((channel, missing))
        return gaps

    @staticmethod
    def _format_permission_gap_lines(
        rows: list[tuple[discord.abc.GuildChannel, list[str]]],
        *,
        max_items: int = 8,
    ) -> str:
        if not rows:
            return "ครบถ้วน"
        lines: list[str] = []
        for channel, missing in rows[: max_items]:
            mention = getattr(channel, "mention", f"#{getattr(channel, 'name', 'unknown')}")
            lines.append(f"- {mention}: {', '.join(missing)}")
        hidden = len(rows) - min(len(rows), max_items)
        if hidden > 0:
            lines.append(f"- และอีก {hidden} ห้อง")
        output = "\n".join(lines)
        return output[:1000]

    @staticmethod
    def _channel_missing_permissions(
        channel: discord.abc.GuildChannel,
        bot_member: discord.Member,
        required: dict[str, str],
    ) -> list[str]:
        try:
            perms = channel.permissions_for(bot_member)
        except Exception:
            return list(required.values())
        return [
            label
            for perm_name, label in required.items()
            if not getattr(perms, perm_name, False)
        ]

    @commands.group(
        name="purge",
        help="ลบข้อความในห้อง",
        invoke_without_command=True,
        aliases=['clear','clean','c'],
        usage="purge <amount:int>, purge user <user:discord.Member> <amount:int>, purge images <amount:int>, purge links <amount:int>, purge bots <amount:int>"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2,per=60,type=commands.BucketType.channel)
    async def purge_command(self,ctx:commands.Context,amount:int):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_messages'):
                return
            if amount > 1000:
                await ctx.send(embed=discord.Embed(description="คุณลบข้อความได้สูงสุดครั้งละ 1000 ข้อความ",color=color.red),delete_after=10)
                return
            bot_member = ctx.guild.me or ctx.guild.get_member(getattr(self.bot.user, "id", 0))
            if bot_member is None:
                await ctx.send(
                    embed=discord.Embed(
                        description="ไม่พบบัญชีบอทในเซิร์ฟเวอร์นี้ กรุณาลองใหม่อีกครั้ง",
                        color=color.red,
                    ),
                    delete_after=10,
                )
                return
            bot_perms = ctx.channel.permissions_for(bot_member)
            if not (bot_perms.manage_messages and bot_perms.read_message_history):
                await ctx.send(
                    embed=discord.Embed(
                        description=(
                            "บอทยังไม่มีสิทธิ์ลบข้อความในห้องนี้ครับ\n"
                            "ต้องเปิดสิทธิ์ `Manage Messages` และ `Read Message History` ให้บอทก่อน"
                        ),
                        color=color.red,
                    ),
                    delete_after=12,
                )
                return
            try:
                await ctx.channel.purge(limit=amount+1,reason=f"Purged by {ctx.author}")
                await ctx.send(embed=discord.Embed(description=f"Deleted {amount} messages",color=color.green),delete_after=10)
            except discord.Forbidden:
                await ctx.send(
                    embed=discord.Embed(
                        description="บอทไม่มีสิทธิ์เพียงพอสำหรับลบข้อความในห้องนี้",
                        color=color.red,
                    ),
                    delete_after=10,
                )
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while purging messages",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    @commands.hybrid_command(
        name="delete",
        aliases=["delast"],
        with_app_command=False,
        help="ลบข้อความตามโหมดที่ต้องการ รองรับจำนวนและช่วงข้อความ",
        usage="delete <mode> <messages> [user] [link]",
    )
    @discord.app_commands.describe(
        mode="โหมดการลบข้อความ",
        messages="จำนวน หรือช่วงข้อความ เช่น 50 หรือ 1400000000000000000-1400000000000000999",
        user="เลือกผู้ใช้ (ใช้กับ specificuser/usermessages/botmessages)",
        link="โหมด links: ใส่ลิงก์ที่ต้องการลบ หรือ all",
    )
    @discord.app_commands.choices(
        mode=[
            discord.app_commands.Choice(name="messages", value="messages"),
            discord.app_commands.Choice(name="specificuser", value="specificuser"),
            discord.app_commands.Choice(name="embeds", value="embeds"),
            discord.app_commands.Choice(name="emojis", value="emojis"),
            discord.app_commands.Choice(name="links", value="links"),
            discord.app_commands.Choice(name="usermessages", value="usermessages"),
            discord.app_commands.Choice(name="botmessages", value="botmessages"),
            discord.app_commands.Choice(name="deleteall", value="deleteall"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.channel)
    async def delete_command(
        self,
        ctx: commands.Context,
        mode: str = "messages",
        messages: str = "20",
        user: discord.Member | None = None,
        link: str | None = None,
    ):
        try:
            async def _safe_send(*args, **kwargs):
                if not getattr(ctx, "interaction", None):
                    kwargs.pop("ephemeral", None)
                try:
                    return await ctx.send(*args, **kwargs)
                except TypeError:
                    kwargs.pop("ephemeral", None)
                    return await ctx.send(*args, **kwargs)
                except discord.NotFound:
                    if getattr(ctx, "channel", None):
                        kwargs.pop("ephemeral", None)
                        return await ctx.channel.send(*args, **kwargs)
                    raise

            if ctx.interaction and not ctx.interaction.response.is_done():
                try:
                    await ctx.defer(ephemeral=True)
                except (discord.InteractionResponded, discord.NotFound):
                    pass
                except discord.HTTPException as interaction_error:
                    if getattr(interaction_error, "code", None) != 10062:
                        raise

            if not await checks.check_is_moderator_permissions(ctx, "manage_messages"):
                return
            if not ctx.guild or not ctx.channel:
                await _safe_send(
                    embed=discord.Embed(
                        description="ใช้คำสั่งนี้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น",
                        color=color.red,
                    ),
                    delete_after=10,
                    ephemeral=True,
                )
                return

            guild_cache = cache.guilds.get(str(ctx.guild.id), {}) or {}
            max_allowed = _delast_limit(guild_cache.get("subscription", "free"))
            delete_mode = _normalize_delete_mode(mode)
            raw_target = str(messages or "").strip()
            selected_user_id = int(user.id) if user else None

            if delete_mode == "specificuser" and selected_user_id is None:
                await _safe_send(
                    embed=discord.Embed(
                        description="โหมด `specificuser` ต้องระบุ `user`",
                        color=color.red,
                    ),
                    delete_after=10,
                    ephemeral=True,
                )
                return

            if not raw_target:
                await _safe_send(
                    embed=discord.Embed(
                        description="กรุณาระบุจำนวน หรือช่วงข้อความ เช่น `50` หรือ `123-456`",
                        color=color.red,
                    ),
                    delete_after=10,
                    ephemeral=True,
                )
                return

            invocation_message_id = None
            if getattr(ctx, "message", None):
                try:
                    invocation_message_id = int(ctx.message.id)
                except Exception:
                    invocation_message_id = None

            target_messages: list[discord.Message] = []
            request_mode = "amount"
            requested_amount = 0
            range_start_id = None
            range_end_id = None
            scanned_count = 0

            if raw_target.isdigit():
                requested_amount = int(raw_target)
                if requested_amount <= 0:
                    await _safe_send(
                        embed=discord.Embed(
                            description="จำนวนข้อความต้องมากกว่า 0",
                            color=color.red,
                        ),
                        delete_after=10,
                        ephemeral=True,
                    )
                    return
                if requested_amount > max_allowed:
                    await _safe_send(
                        embed=discord.Embed(
                            description=f"แพลนเซิร์ฟเวอร์นี้ลบได้สูงสุดครั้งละ {max_allowed} ข้อความ",
                            color=color.red,
                        ),
                        delete_after=10,
                        ephemeral=True,
                    )
                    return
                scan_limit = min(max(max_allowed * 40, requested_amount * 40, 400), 20000)
                async for message in ctx.channel.history(limit=scan_limit, oldest_first=False):
                    if invocation_message_id and int(message.id) == int(invocation_message_id):
                        continue
                    scanned_count += 1
                    if not _message_matches_delete_mode(
                        message,
                        mode=delete_mode,
                        selected_user_id=selected_user_id,
                        link_filter=link,
                    ):
                        continue
                    target_messages.append(message)
                    if len(target_messages) >= requested_amount:
                        break
            else:
                request_mode = "range"
                range_parts = re.split(r"\s*-\s*", raw_target, maxsplit=1)
                if len(range_parts) != 2:
                    await _safe_send(
                        embed=discord.Embed(
                            description=(
                                "รูปแบบช่วงข้อความไม่ถูกต้อง\n"
                                "ตัวอย่าง: `1400000000000000000-1400000000000000999`"
                            ),
                            color=color.red,
                        ),
                        delete_after=12,
                        ephemeral=True,
                    )
                    return

                start_id = _parse_message_id(range_parts[0])
                end_id = _parse_message_id(range_parts[1])
                if not start_id or not end_id:
                    await _safe_send(
                        embed=discord.Embed(
                            description="อ่านข้อความไม่สำเร็จ กรุณาใช้ Message ID หรือ URL ข้อความที่ถูกต้อง",
                            color=color.red,
                        ),
                        delete_after=12,
                        ephemeral=True,
                    )
                    return

                range_start_id = min(int(start_id), int(end_id))
                range_end_id = max(int(start_id), int(end_id))
                after_ref = discord.Object(id=max(range_start_id - 1, 0))
                before_ref = discord.Object(id=range_end_id + 1)
                scan_limit = min(max(max_allowed * 60, 2000), 30000)

                async for message in ctx.channel.history(
                    limit=scan_limit,
                    after=after_ref,
                    before=before_ref,
                    oldest_first=True,
                ):
                    if invocation_message_id and int(message.id) == int(invocation_message_id):
                        continue
                    scanned_count += 1
                    if not _message_matches_delete_mode(
                        message,
                        mode=delete_mode,
                        selected_user_id=selected_user_id,
                        link_filter=link,
                    ):
                        continue
                    target_messages.append(message)
                    if len(target_messages) > max_allowed:
                        break

                if len(target_messages) > max_allowed:
                    await _safe_send(
                        embed=discord.Embed(
                            description=(
                                f"ช่วงข้อความที่เข้าเงื่อนไขมีมากกว่า {max_allowed} ข้อความ\n"
                                f"กรุณาแบ่งช่วงให้เล็กลง (ลิมิตแพลนปัจจุบัน: {max_allowed})"
                            ),
                            color=color.red,
                        ),
                        delete_after=12,
                        ephemeral=True,
                    )
                    return
                if scanned_count >= scan_limit:
                    await _safe_send(
                        embed=discord.Embed(
                            description=(
                                "ช่วงข้อความกว้างเกินขีดจำกัดการสแกนในครั้งเดียว\n"
                                f"กรุณาลดช่วงลง (สแกนได้สูงสุด {scan_limit} ข้อความต่อครั้ง)"
                            ),
                            color=color.red,
                        ),
                        delete_after=12,
                        ephemeral=True,
                    )
                    return

            if not target_messages:
                await _safe_send(
                    embed=discord.Embed(
                        description="ไม่พบข้อความที่ลบได้ในเงื่อนไขที่ระบุ",
                        color=color.red,
                    ),
                    delete_after=10,
                    ephemeral=True,
                )
                return

            delete_count = len(target_messages)

            class DeleteConfirmView(discord.ui.View):
                def __init__(self, owner_id: int):
                    super().__init__(timeout=40)
                    self.owner_id = int(owner_id)
                    self.confirmed: bool | None = None
                    self.message: discord.Message | None = None

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if int(getattr(interaction.user, "id", 0)) != self.owner_id:
                        await interaction.response.send_message(
                            "คุณไม่มีสิทธิ์ใช้ปุ่มนี้",
                            ephemeral=True,
                        )
                        return False
                    return True

                async def _disable_all(self):
                    for item in self.children:
                        item.disabled = True

                @discord.ui.button(label="ยืนยันการลบ", style=discord.ButtonStyle.danger, emoji="🗑️")
                async def confirm_button(self, interaction: discord.Interaction, _: discord.ui.Button):
                    self.confirmed = True
                    await self._disable_all()
                    await interaction.response.edit_message(view=self)
                    self.stop()

                @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary, emoji="✖️")
                async def cancel_button(self, interaction: discord.Interaction, _: discord.ui.Button):
                    self.confirmed = False
                    await self._disable_all()
                    await interaction.response.edit_message(view=self)
                    self.stop()

                async def on_timeout(self):
                    await self._disable_all()
                    if self.message:
                        try:
                            await self.message.edit(view=self)
                        except Exception:
                            pass

            preview_lines = [
                f"โหมด: **{DELETE_MODE_LABELS.get(delete_mode, delete_mode)}**",
                f"ข้อความที่เข้าเงื่อนไข: **{delete_count}** ข้อความ",
                f"ลิมิตแพลนปัจจุบัน: **{max_allowed}**",
            ]
            if request_mode == "amount":
                preview_lines.append(f"รูปแบบ: ลบตามจำนวน (`{requested_amount}`)")
                if delete_count < requested_amount:
                    preview_lines.append(
                        f"พบข้อความตามเงื่อนไข `{delete_count}` จากที่ต้องการ `{requested_amount}`"
                    )
            else:
                preview_lines.append(
                    f"รูปแบบ: ลบตามช่วงข้อความ (`{range_start_id}` - `{range_end_id}`)"
                )
            if user is not None:
                preview_lines.append(f"ผู้ใช้ที่เลือก: {user.mention} (`{user.id}`)")
            if delete_mode == "links":
                normalized_link = str(link or "").strip() or "all"
                preview_lines.append(f"ลิงก์ที่เลือก: `{normalized_link}`")
            preview_lines.append("กดยืนยันเพื่อเริ่มลบข้อความ")

            preview_embed = discord.Embed(
                title="ยืนยันการลบข้อความ",
                description="\n".join(preview_lines),
                color=color.yellow,
            )

            view = DeleteConfirmView(owner_id=ctx.author.id)
            prompt = await _safe_send(
                embed=preview_embed,
                view=view,
                ephemeral=bool(ctx.interaction),
            )
            view.message = prompt

            timed_out = await view.wait()
            if timed_out or view.confirmed is None:
                timeout_embed = discord.Embed(
                    description="หมดเวลาการยืนยันแล้ว กรุณาสั่งใหม่อีกครั้ง",
                    color=color.red,
                )
                try:
                    await prompt.edit(embed=timeout_embed, view=view)
                except Exception:
                    pass
                return

            if view.confirmed is False:
                cancel_embed = discord.Embed(
                    description="ยกเลิกการลบข้อความแล้ว",
                    color=color.yellow,
                )
                try:
                    await prompt.edit(embed=cancel_embed, view=view)
                except Exception:
                    pass
                return

            deleted_ids, failed_count = await _delete_messages_with_fallback(
                ctx.channel,
                target_messages,
                reason=f"Delete by {ctx.author} | mode={delete_mode}",
            )
            deleted_count = len(deleted_ids)
            result_lines = [f"ลบข้อความสำเร็จ **{deleted_count}** ข้อความ"]
            if deleted_ids:
                sorted_ids = sorted(deleted_ids)
                result_lines.append(f"ช่วง Message ID ที่ลบ: `{sorted_ids[0]}` - `{sorted_ids[-1]}`")
            if failed_count:
                result_lines.append(f"ลบไม่สำเร็จ **{failed_count}** ข้อความ")
            result_embed = discord.Embed(
                description="\n".join(result_lines),
                color=color.green if deleted_count > 0 else color.red,
            )
            try:
                await prompt.edit(embed=result_embed, view=None)
                if prompt is not None:
                    async def _delete_prompt_later(message: discord.Message):
                        await asyncio.sleep(120)
                        try:
                            await message.delete()
                        except Exception:
                            pass

                    asyncio.create_task(_delete_prompt_later(prompt))
            except Exception:
                await _safe_send(embed=result_embed, delete_after=120, ephemeral=True)
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )
            await _safe_send(
                embed=discord.Embed(
                    description="เกิดข้อผิดพลาดระหว่างลบข้อความ",
                    color=color.red,
                ),
                delete_after=10,
                ephemeral=True,
            )
    
    @purge_command.command(
        name="user",
        help="ลบข้อความของผู้ใช้ในห้อง"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2,per=60,type=commands.BucketType.channel)
    async def purge_user_command(self,ctx:commands.Context,user:discord.Member,amount:int=10):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_messages'):
                return
            if amount > 1000:
                await ctx.send(embed=discord.Embed(description="คุณลบข้อความได้สูงสุดครั้งละ 100 ข้อความ",color=color.red),delete_after=10)
                return
            try:
                def check(message:discord.Message):
                    return message.author.id == user.id
                await ctx.channel.purge(limit=amount+1,check=check)
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
                await ctx.send(embed=discord.Embed(description=f"Deleted {amount} messages of {user.mention}",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while purging messages",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @purge_command.command(
        name="images",
        help="ลบข้อความที่มีรูปภาพในห้อง"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2,per=60,type=commands.BucketType.channel)
    async def purge_images_command(self,ctx:commands.Context,amount:int=10):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_messages'):
                return
            if amount > 1000:
                await ctx.send(embed=discord.Embed(description="คุณลบข้อความได้สูงสุดครั้งละ 100 ข้อความ",color=color.red),delete_after=10)
                return
            try:
                def check_images(message:discord.Message):
                    return len(message.attachments) > 0
                def check(message:discord.Message):
                    return check_images(message) or message.embeds
                await ctx.channel.purge(limit=amount+1,check=check)
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
                await ctx.send(embed=discord.Embed(description=f"Deleted {amount} messages containing images",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while purging messages",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @purge_command.command(
        name="links",
        help="ลบข้อความที่มีลิงก์ในห้อง"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2,per=60,type=commands.BucketType.channel)
    async def purge_links_command(self,ctx:commands.Context,amount:int=10):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_messages'):
                return
            if amount > 1000:
                await ctx.send(embed=discord.Embed(description="คุณลบข้อความได้สูงสุดครั้งละ 100 ข้อความ",color=color.red),delete_after=10)
                return
            try:
                def check_links(text):
                    pattern = re.compile(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+")
                    return True if pattern.match(text) else False
                def check(message:discord.Message):
                    return check_links(message.content)
                await ctx.channel.purge(limit=amount+1,check=check)
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
                await ctx.send(embed=discord.Embed(description=f"Deleted {amount} messages containing links",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while purging messages",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    @purge_command.command(
        name="bots",
        help="ลบข้อความของบอทในห้อง"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2,per=60,type=commands.BucketType.channel)
    async def purge_bots_command(self,ctx:commands.Context,amount:int=10):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_messages'):
                return
            if amount > 1000:
                await ctx.send(embed=discord.Embed(description="คุณลบข้อความได้สูงสุดครั้งละ 100 ข้อความ",color=color.red),delete_after=10)
                return
            try:
                def check(message:discord.Message):
                    return message.author.bot
                await ctx.channel.purge(limit=amount+1,check=check)
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
                await ctx.send(embed=discord.Embed(description=f"Deleted {amount} messages of bots",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while purging messages",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    @commands.hybrid_command(
        name="ban",
        with_app_command=False,
        help="แบนผู้ใช้ออกจากเซิร์ฟเวอร์"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3,per=30,type=commands.BucketType.user)
    async def ban_command(self,ctx:commands.Context,user:discord.Member,*,reason:str=None):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'ban_members'):
                return
            if not await checks.check_if_user_can_be_banned_or_kicked(ctx,user):
                return
            try:
                ban_embed = discord.Embed(
                    title=f"You have been banned from {ctx.guild.name}",
                    description=f"Reason: {reason if reason else 'No Reason Provided'}\n\nBy: {ctx.author.mention}\nTime: <t:{int(datetime.datetime.now().timestamp())}:F>",
                    color=color.red
                )
                ban_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
                ban_embed.set_footer(text=f"Server ID: {ctx.guild.id}",icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
                await user.send(embed=ban_embed)
            except Exception:
                logger.warning(f"Couldn't send a DM to the user {user.id} in guild {ctx.guild.id} while banning the user")
            pre_reason = reason if reason else 'No Reason Provided'
            reason = f"Banned by {ctx.author} with reason: {reason if reason else 'No Reason Provided'}"
            await user.ban(reason=reason)
            embed = discord.Embed(
                description=f"{self.bot.emoji.BAN} | Successfully Banned {user.mention} !\nReason: `{pre_reason}`",
                color=color.green
            )
            embed.set_footer(text=f"Action by {ctx.author}",icon_url=ctx.author.display_avatar.url)
            embed.set_author(
                name=f"User Banned",
                icon_url=user.display_avatar.url
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            bot_member = ctx.guild.me if ctx.guild else None
            bot_role_info = "-"
            target_role_info = "-"
            if bot_member is not None:
                bot_role_info = f"{bot_member.top_role.name} ({bot_member.top_role.position})"
            if user is not None:
                target_role_info = f"{user.top_role.name} ({user.top_role.position})"
            await ctx.send(
                embed=discord.Embed(
                    description=(
                        "บอทไม่สามารถแบนสมาชิกนี้ได้ เพราะยศบอทต่ำกว่าหรือสิทธิ์ไม่พอ\n"
                        f"ยศบอท: `{bot_role_info}` | ยศเป้าหมาย: `{target_role_info}`\n"
                        "กรุณาเลื่อนยศบอทให้สูงกว่าเป้าหมาย และเปิดสิทธิ์ `Ban Members`"
                    ),
                    color=color.red,
                ),
                delete_after=15,
            )
        except Exception as e:
            logger.error(f"ข้อผิดพลาด while banning user {user.id} in guild {ctx.guild.id} with error {e}")
            await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while banning the user",color=color.red),delete_after=10)

    @commands.hybrid_command(
        name="kick",
        with_app_command=False,
        help="เตะผู้ใช้ออกจากเซิร์ฟเวอร์"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3,per=30,type=commands.BucketType.user)
    async def kick_command(self,ctx:commands.Context,user:discord.Member,*,reason:str=None):
        if not await checks.check_is_moderator_permissions(ctx, 'kick_members'):
            return
        if not await checks.check_if_user_can_be_banned_or_kicked(ctx,user):
            return
        try:
            try:
                kick_embed = discord.Embed(
                    title=f"You have been kicked from {ctx.guild.name}",
                    description=f"Reason: {reason if reason else 'No Reason Provided'}\n\nBy: {ctx.author.mention}\nTime: <t:{int(datetime.datetime.now().timestamp())}:F>",
                    color=color.red
                )
                kick_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
                kick_embed.set_footer(text=f"Server ID: {ctx.guild.id}",icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
                await user.send(embed=kick_embed)
            except Exception:
                logger.warning(f"Couldn't send a DM to the user {user.id} in guild {ctx.guild.id} while kicking the user")
            pre_reason = reason if reason else 'No Reason Provided'
            reason = f"Kicked by {ctx.author} with reason: {reason if reason else 'No Reason Provided'}"
            await user.kick(reason=reason)
            embed = discord.Embed(
                description=f"{self.bot.emoji.KICK} | Successfully Kicked {user.mention} !\nReason: `{pre_reason}`",
                color=color.green
            )
            embed.set_footer(text=f"Action by {ctx.author}",icon_url=ctx.author.display_avatar.url)
            embed.set_author(
                name=f"User Kicked",
                icon_url=user.display_avatar.url
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            bot_member = ctx.guild.me if ctx.guild else None
            bot_role_info = "-"
            target_role_info = "-"
            if bot_member is not None:
                bot_role_info = f"{bot_member.top_role.name} ({bot_member.top_role.position})"
            if user is not None:
                target_role_info = f"{user.top_role.name} ({user.top_role.position})"
            await ctx.send(
                embed=discord.Embed(
                    description=(
                        "บอทไม่สามารถเตะสมาชิกนี้ได้ เพราะยศบอทต่ำกว่าหรือสิทธิ์ไม่พอ\n"
                        f"ยศบอท: `{bot_role_info}` | ยศเป้าหมาย: `{target_role_info}`\n"
                        "กรุณาเลื่อนยศบอทให้สูงกว่าเป้าหมาย และเปิดสิทธิ์ `Kick Members`"
                    ),
                    color=color.red,
                ),
                delete_after=15,
            )
        except Exception as e:
            logger.error(f"ข้อผิดพลาด while kicking user {user.id} in guild {ctx.guild.id} with error {e}")
            await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while kicking the user",color=color.red),delete_after=10)
        

    @commands.hybrid_command(
        name="unban",
        with_app_command=False,
        help="ปลดแบนผู้ใช้จากเซิร์ฟเวอร์"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def unban_command(self,ctx:commands.Context,user:discord.User,*,reason:str=None):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'ban_members'):
                return
            user_to_unban = None
            async for entry in ctx.guild.bans(limit=None):
                if entry.user.id == user.id:
                    user_to_unban = entry.user
                    break
                
            if not user_to_unban:
                await ctx.send(embed=discord.Embed(description="ผู้ใช้นี้ไม่ได้ถูกแบน",color=color.red),delete_after=10)
                return
            try:
                await ctx.guild.unban(user,reason=reason if reason else "No Reason Provided")
                await ctx.send(embed=discord.Embed(description=f"{user.mention} has been unbanned. Reason: {reason if reason else 'No Reason Provided'}",color=color.green),delete_after=10)
                try:
                    unban_embed = discord.Embed(
                        title=f"You have been unbanned from {ctx.guild.name}",
                        description=f"Reason: {reason if reason else 'No Reason Provided'}\n\nBy: {ctx.author.mention}\nTime: <t:{int(datetime.datetime.now().timestamp())}:F>",
                        color=color.green
                    )
                    unban_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
                    unban_embed.set_footer(text=f"Server ID: {ctx.guild.id}",icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
                    await user.send(embed=unban_embed)
                except Exception:
                    logger.warning(f"Couldn't send a DM to the user {user.id} in guild {ctx.guild.id} while unbanning the user")
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while unbanning the user",color=color.red),delete_after=10)
                return
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    @commands.command(
        name="unbanall",
        help="ปลดแบนผู้ใช้ทั้งหมดจากเซิร์ฟเวอร์"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=60,type=commands.BucketType.guild)
    async def unbanall_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'ban_members'):
                return
            try:
                banned_users = []
                message = await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.LOADING} Unbanning all users",color=color.yellow))
                async for ban in ctx.guild.bans(limit=None):
                    banned_users.append(ban.user)

                for banned_user in banned_users:
                    try:
                        await ctx.guild.unban(banned_user)
                    except Exception:
                        pass
                await message.edit(embed=discord.Embed(description=f"{len(banned_users)} users have been unbanned",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while unbanning all users",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    
    @commands.command(
        name='snipe',
        help='ดูข้อความล่าสุดที่ถูกลบในห้อง',
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.channel)
    async def snipe_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_messages'):
                return
            snipe_data = cache.snipe_data.get('delete',{}).get(str(ctx.channel.id))
            if not snipe_data:
                await ctx.send(embed=discord.Embed(description="ไม่มีข้อความให้ดึงกลับ",color=color.red),delete_after=10)
                return
            message_id = snipe_data.get('message_id')
            content = snipe_data.get('before_content')
            author_id = snipe_data.get('author_id')
            created_at = snipe_data.get('created_at').replace(tzinfo=None)
            embed = discord.Embed(
                title=f"Sniped Message",
                description=f"**__Author:__** <@{author_id}>\n**__Deleted At:__** <t:{int(created_at.timestamp())}:F>",
                color=color.green
            )
            embed.add_field(name="Content",value=content,inline=False)
            embed.set_footer(text=f"Message ID: {message_id}")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
        
    @commands.command(
        name='editsnipe',
        help='ดูข้อความล่าสุดที่ถูกแก้ไขในห้อง',
        aliases=['esnipe','es']
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.channel)
    async def editsnipe_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_messages'):
                return
            snipe_data = cache.snipe_data.get('edit',{}).get(str(ctx.channel.id))
            if not snipe_data:
                await ctx.send(embed=discord.Embed(description="ไม่มีข้อความให้ดึงกลับ",color=color.red),delete_after=10)
                return
            message_id = snipe_data.get('message_id')
            before_content = snipe_data.get('before_content')
            after_content = snipe_data.get('after_content')
            author_id = snipe_data.get('author_id')
            created_at = snipe_data.get('created_at').replace(tzinfo=None)
            embed = discord.Embed(
                title=f"Sniped Message",
                description=f"**__Author:__** <@{author_id}>\n**__Edited At:__** <t:{int(created_at.timestamp())}:F>",
                color=color.green
            )
            embed.add_field(name="Before Edit",value=before_content,inline=True)
            embed.add_field(name="After Edit",value=after_content,inline=True)
            embed.set_footer(text=f"Message ID: {message_id}")
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    
    # want to make a group name ignore with subcommands user, channel and in the user,channel subcommand want to add a subcommand add and remove and list

    @commands.group(
        name="ignore",
        help="เพิกเฉยผู้ใช้หรือห้อง",
        invoke_without_command=True,
        usage="ignore user <user:discord.Member>, ignore channel <channel:discord.TextChannel>"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            
            embed = discord.Embed(
                title="คำสั่งการยกเว้น",
                description="ยกเว้นผู้ใช้หรือช่อง",
                color=color.random_color()
            )

            if hasattr(ctx.command,'commands'):
                for command in ctx.command.commands:
                    embed.description += f"\n\n`{self.bot.BotConfig.PREFIX}{ctx.command.name} {command.name}` : {command.help}"
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @ignore_command.group(
        name="user",
        help="เพิกเฉยผู้ใช้",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_user_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            
            embed = discord.Embed(
                title="คำสั่งยกเว้นผู้ใช้",
                description="นี่คือคำสั่งสำหรับยกเว้นผู้ใช้",
                color=color.random_color()
            )
            if hasattr(ctx.command,'commands'):
                for command in ctx.command.commands:
                    embed.description += f"\n\n`{self.bot.BotConfig.PREFIX}{ctx.command.parent.name} {ctx.command.name} {command.name}` : {command.help}"
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @ignore_user_command.command(
        name="add",
        help="เพิกเฉยผู้ใช้"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_user_add_command(self,ctx:commands.Context,member:discord.Member):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            try:
                if cache.ignore_data.get('users',{}).get(str(ctx.guild.id),{}).get(str(member.id)):
                    await ctx.send(embed=discord.Embed(description=f"{member.mention} is already ignored",color=color.red),delete_after=10)
                    return
                await storage.ignore_data.insert(guild_id=ctx.guild.id,user_id=member.id)
                await ctx.send(embed=discord.Embed(description=f"{member.mention} has been ignored",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while ignoring the member",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
        
    @ignore_user_command.command(
        name="remove",
        help="ยกเลิกเพิกเฉยผู้ใช้"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_user_remove_command(self,ctx:commands.Context,member:discord.Member):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            try:
                if not cache.ignore_data.get('users',{}).get(str(ctx.guild.id),{}).get(str(member.id)):
                    await ctx.send(embed=discord.Embed(description=f"{member.mention} is not ignored",color=color.red),delete_after=10)
                    return
                await storage.ignore_data.delete(guild_id=ctx.guild.id,user_id=member.id)
                await ctx.send(embed=discord.Embed(description=f"{member.mention} has been unignored",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while unignoring the member",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @ignore_user_command.command(
        name="list",
        help="แสดงรายการผู้ใช้ที่ถูกเพิกเฉย"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_user_list_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            try:
                ignored_users = cache.ignore_data.get('users',{}).get(str(ctx.guild.id),{})
                
                if not ignored_users:
                    await ctx.send(embed=discord.Embed(description="ยังไม่มีผู้ใช้ที่ถูกยกเว้น",color=color.red),delete_after=10)
                    return
                ignored_users = list(ignored_users.keys())
                # make ignored_users 5 by 5 list
                ignored_users = [ignored_users[i:i + 5] for i in range(0, len(ignored_users), 5)]
                
                current_page_index = 0
                view_timeout = 60
                cancled = False
                def reset_view_timeout():
                    nonlocal view_timeout
                    view_timeout = 60
                
                async def get_embed():
                    nonlocal ignored_users,current_page_index
                    embed = discord.Embed(
                        title="ผู้ใช้ที่ถูกยกเว้น",
                        color=color.random_color()
                    )
                    embed.description = ', '.join([f"<@{user_id}>" for user_id in ignored_users[current_page_index]])
                    embed.set_footer(text=f"Page {current_page_index+1}/{len(ignored_users)}")
                    return embed
                
                async def get_view(disabled=False):
                    nonlocal view_timeout
                    reset_view_timeout()
                    view = discord.ui.View()
                    previous_button = discord.ui.Button(
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.PREVIOUS,
                        row=0,
                        disabled=current_page_index <= 0
                    )
                    stop_button = discord.ui.Button(
                        style=discord.ButtonStyle.danger,
                        emoji=self.bot.emoji.STOP,
                        row=0,
                        disabled=len(ignored_users) == 1
                    )
                    next_button = discord.ui.Button(
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.NEXT,
                        row=0,
                        disabled=current_page_index >= len(ignored_users)-1
                    )
                    previous_button.callback = lambda i: previous_button_callback(i)
                    stop_button.callback = lambda i: stop_button_callback(i)
                    next_button.callback = lambda i: next_button_callback(i)
                    view.add_item(previous_button)
                    view.add_item(stop_button)
                    view.add_item(next_button)
                    if disabled:
                        for item in view.children:
                            item.disabled = True
                    return view
                
                async def previous_button_callback(interaction:discord.Interaction):
                    try:
                        nonlocal current_page_index
                        current_page_index -= 1
                        await interaction.response.edit_message(embed=await get_embed(),view=await get_view())
                    except Exception as e:
                        logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                
                async def stop_button_callback(interaction:discord.Interaction):
                    try:
                        nonlocal cancled
                        cancled = True
                        await interaction.response.edit_message(embed=await get_embed(),view=await get_view(disabled=True))
                    except Exception as e:
                        logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                
                async def next_button_callback(interaction:discord.Interaction):
                    try:
                        nonlocal current_page_index
                        current_page_index += 1
                        await interaction.response.edit_message(embed=await get_embed(),view=await get_view())
                    except Exception as e:
                        logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                
                message = await ctx.send(embed=await get_embed(),view=await get_view())

                while not cancled:
                    view_timeout -= 1
                    if view_timeout <= 0:
                        await message.edit(embed=await get_embed(),view=await get_view(disabled=True))
                        break
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while listing ignored users",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @ignore_command.group(
        name="channel",
        help="เพิกเฉยห้อง",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_channel_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            
            embed = discord.Embed(
                title="คำสั่งยกเว้นช่อง",
                description="นี่คือคำสั่งสำหรับยกเว้นช่อง",
                color=color.random_color()
            )
            if hasattr(ctx.command,'commands'):
                for command in ctx.command.commands:
                    embed.description += f"\n\n`{self.bot.BotConfig.PREFIX}{ctx.command.parent.name} {ctx.command.name} {command.name}` : {command.help}"
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @ignore_channel_command.command(
        name="add",
        help="เพิกเฉยห้อง"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_channel_add_command(self,ctx:commands.Context,channel:discord.TextChannel):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            try:
                if cache.ignore_data.get('channels',{}).get(str(ctx.guild.id),{}).get(str(channel.id)):
                    await ctx.send(embed=discord.Embed(description=f"{channel.mention} is already ignored",color=color.red),delete_after=10)
                    return
                await storage.ignore_data.insert(guild_id=ctx.guild.id,channel_id=channel.id,type='channel')
                await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been ignored",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while ignoring the channel",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
        
    @ignore_channel_command.command(
        name="remove",
        help="ยกเลิกเพิกเฉยห้อง"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_channel_remove_command(self,ctx:commands.Context,channel:discord.TextChannel):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            try:
                if not cache.ignore_data.get('channels',{}).get(str(ctx.guild.id),{}).get(str(channel.id)):
                    await ctx.send(embed=discord.Embed(description=f"{channel.mention} is not ignored",color=color.red),delete_after=10)
                    return
                await storage.ignore_data.delete(guild_id=ctx.guild.id,channel_id=channel.id)
                await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been unignored",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while unignoring the channel",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    @ignore_channel_command.command(
        name="list",
        help="แสดงรายการห้องที่ถูกเพิกเฉย"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=10,type=commands.BucketType.user)
    async def ignore_channel_list_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_owner(ctx,notify=True):
                return
            try:
                ignored_channels = cache.ignore_data.get('channels',{}).get(str(ctx.guild.id),{})
                
                if not ignored_channels:
                    await ctx.send(embed=discord.Embed(description="ยังไม่มีช่องที่ถูกยกเว้น",color=color.red),delete_after=10)
                    return
                ignored_channels = list(ignored_channels.keys())
                # make ignored_channels 5 by 5 list
                ignored_channels = [ignored_channels[i:i + 5] for i in range(0, len(ignored_channels), 5)]
                
                current_page_index = 0
                view_timeout = 60
                cancled = False
                def reset_view_timeout():
                    nonlocal view_timeout
                    view_timeout = 60
                
                async def get_embed():
                    nonlocal ignored_channels,current_page_index
                    embed = discord.Embed(
                        title="ช่องที่ถูกยกเว้น",
                        color=color.random_color()
                    )
                    embed.description = ', '.join([f"<#{channel_id}>" for channel_id in ignored_channels[current_page_index]])
                    embed.set_footer(text=f"Page {current_page_index+1}/{len(ignored_channels)}")
                    return embed
                
                async def get_view(disabled=False):
                    nonlocal view_timeout
                    reset_view_timeout()
                    view = discord.ui.View()
                    previous_button = discord.ui.Button(
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.PREVIOUS,
                        row=0,
                        disabled=current_page_index <= 0
                    )
                    stop_button = discord.ui.Button(
                        style=discord.ButtonStyle.danger,
                        emoji=self.bot.emoji.STOP,
                        row=0,
                        disabled=len(ignored_channels) == 1
                    )
                    next_button = discord.ui.Button(
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.NEXT,
                        row=0,
                        disabled=current_page_index >= len(ignored_channels)-1
                    )
                    previous_button.callback = lambda i: previous_button_callback(i)
                    stop_button.callback = lambda i: stop_button_callback(i)
                    next_button.callback = lambda i: next_button_callback(i)
                    view.add_item(previous_button)
                    view.add_item(stop_button)
                    view.add_item(next_button)
                    if disabled:
                        for item in view.children:
                            item.disabled = True
                    return view
                
                async def previous_button_callback(interaction:discord.Interaction):
                    try:
                        nonlocal current_page_index
                        current_page_index -= 1
                        await interaction.response.edit_message(embed=await get_embed(),view=await get_view())
                    except Exception as e:
                        logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

                async def stop_button_callback(interaction:discord.Interaction):
                    try:
                        nonlocal cancled
                        cancled = True
                        await interaction.response.edit_message(embed=await get_embed(),view=await get_view(disabled=True))
                    except Exception as e:
                        logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                
                async def next_button_callback(interaction:discord.Interaction):
                    try:
                        nonlocal current_page_index
                        current_page_index += 1
                        await interaction.response.edit_message(embed=await get_embed(),view=await get_view())
                    except Exception as e:
                        logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                
                message = await ctx.send(embed=await get_embed(),view=await get_view())

                while not cancled:
                    view_timeout -= 1
                    if view_timeout <= 0:
                        await message.edit(embed=await get_embed(),view=await get_view(disabled=True))
                        break
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                await ctx.send(embed=discord.Embed(description="An ข้อผิดพลาด occurred while listing ignored channels",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    @commands.hybrid_command(
        name="checkperms",
        help="เช็กสิทธิ์บอทอัตโนมัติ และสรุปว่าขาดอะไรในห้องไหน",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.guild)
    async def checkperms_command(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            if not ctx.guild:
                await ctx.send(
                    embed=discord.Embed(
                        description="ใช้คำสั่งนี้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น",
                        color=color.red,
                    ),
                    delete_after=10,
                )
                return

            bot_member = ctx.guild.me or ctx.guild.get_member(getattr(self.bot.user, "id", 0))
            if not bot_member:
                await ctx.send(
                    embed=discord.Embed(
                        description="ไม่พบบัญชีบอทในเซิร์ฟเวอร์นี้ กรุณาลองใหม่อีกครั้ง",
                        color=color.red,
                    ),
                    delete_after=10,
                )
                return

            global_required = {
                "manage_channels": "Manage Channels",
                "manage_roles": "Manage Roles",
                "manage_messages": "Manage Messages",
                "ban_members": "Ban Members",
                "kick_members": "Kick Members",
                "moderate_members": "Moderate Members",
                "view_audit_log": "View Audit Log",
            }
            global_missing = [
                label
                for perm_name, label in global_required.items()
                if not getattr(bot_member.guild_permissions, perm_name, False)
            ]

            text_channels = list(ctx.guild.text_channels or [])
            voice_channels = list(ctx.guild.voice_channels or [])

            lock_profile = self._channel_permission_gaps(
                text_channels,
                bot_member,
                {
                    "view_channel": "View Channel",
                    "manage_channels": "Manage Channels",
                    "manage_roles": "Manage Roles",
                },
            )
            purge_profile = self._channel_permission_gaps(
                text_channels,
                bot_member,
                {
                    "view_channel": "View Channel",
                    "manage_messages": "Manage Messages",
                    "read_message_history": "Read Message History",
                },
            )
            ai_profile = self._channel_permission_gaps(
                text_channels,
                bot_member,
                {
                    "view_channel": "View Channel",
                    "send_messages": "Send Messages",
                    "embed_links": "Embed Links",
                    "add_reactions": "Add Reactions",
                },
            )
            music_profile = self._channel_permission_gaps(
                voice_channels,
                bot_member,
                {
                    "view_channel": "View Channel",
                    "connect": "Connect",
                    "speak": "Speak",
                },
            )

            role_above_count = 0
            try:
                role_above_count = len(
                    [
                        role
                        for role in list(ctx.guild.roles or [])
                        if int(getattr(role, "position", 0) or 0) > int(bot_member.top_role.position or 0)
                    ]
                )
            except Exception:
                role_above_count = 0

            total_issue_count = (
                len(global_missing)
                + len(lock_profile)
                + len(purge_profile)
                + len(ai_profile)
                + len(music_profile)
            )
            title = "Bot Permission Check"
            if total_issue_count <= 0:
                title = "Bot Permission Check - OK"

            embed = discord.Embed(
                title=title,
                color=color.green if total_issue_count <= 0 else color.orange,
                description=(
                    f"ตรวจสิทธิ์ให้แล้วใน `{ctx.guild.name}`\n"
                    f"- บอท: {bot_member.mention}\n"
                    f"- Top role: `{bot_member.top_role.name}` (pos `{bot_member.top_role.position}`)\n"
                    f"- Roles ที่สูงกว่าบอท: `{role_above_count}`"
                ),
            )
            embed.add_field(
                name="Global (Guild) Permissions",
                value=(
                    "ครบถ้วน"
                    if not global_missing
                    else "- " + "\n- ".join(global_missing[:12])
                )[:1020],
                inline=False,
            )
            embed.add_field(
                name=f"Lock/Unlock Gaps ({len(lock_profile)} ห้อง)",
                value=self._format_permission_gap_lines(lock_profile),
                inline=False,
            )
            embed.add_field(
                name=f"Purge Gaps ({len(purge_profile)} ห้อง)",
                value=self._format_permission_gap_lines(purge_profile),
                inline=False,
            )
            embed.add_field(
                name=f"AI Reply Gaps ({len(ai_profile)} ห้อง)",
                value=self._format_permission_gap_lines(ai_profile),
                inline=False,
            )
            embed.add_field(
                name=f"Voice/Music Gaps ({len(music_profile)} ห้อง)",
                value=self._format_permission_gap_lines(music_profile),
                inline=False,
            )
            embed.set_footer(
                text="Tip: เปิด Administrator ชั่วคราวเพื่อเทส หรือขยับ role บอทให้สูงขึ้นแล้วค่อยจำกัดสิทธิ์"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in checkperms command: {e} | guild={ctx.guild.id if ctx.guild else 'unknown'}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description="เกิดข้อผิดพลาดระหว่างตรวจสิทธิ์บอทครับ ลองใหม่อีกครั้ง",
                    color=color.red,
                ),
                delete_after=10,
            )

    @commands.hybrid_command(
        name='lock',
        help='ล็อกห้อง',
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3,per=60,type=commands.BucketType.guild)
    async def lock_command(self,ctx:commands.Context,channel:discord.abc.GuildChannel=None):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_channels'):
                return
            if not channel:
                channel = ctx.channel
            can_manage, missing = self._bot_can_manage_channel(ctx.guild, channel)
            if not can_manage:
                await ctx.send(
                    embed=discord.Embed(
                        description=(
                            f"บอทยังล็อกห้องนี้ไม่ได้ เพราะสิทธิ์ไม่พอ: {', '.join(missing)}\n"
                            "กรุณาขยับยศบอทให้สูงขึ้นและเปิดสิทธิ์ที่จำเป็นก่อน"
                        ),
                        color=color.red,
                    ),
                    delete_after=12,
                )
                return
            if isinstance(channel, discord.TextChannel):
                await channel.set_permissions(ctx.guild.default_role, send_messages=False)
            elif isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(ctx.guild.default_role, connect=False,send_messages=False)
            else:
                await channel.set_permissions(ctx.guild.default_role, send_messages=False)
            await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been locked",color=color.green))
        except discord.Forbidden:
            logger.warning(
                f"lock command missing permissions | guild={ctx.guild.id if ctx.guild else 'unknown'} "
                f"channel={channel.id if channel else getattr(getattr(ctx, 'channel', None), 'id', 'unknown')}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description="บอทไม่มีสิทธิ์ล็อกห้องนี้ (Missing Permissions)",
                    color=color.red,
                ),
                delete_after=10,
            )
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in lock command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    @commands.hybrid_command(
        name='unlock',
        help='ปลดล็อกห้อง',
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3,per=60,type=commands.BucketType.guild)
    async def unlock_command(self,ctx:commands.Context,channel:discord.abc.GuildChannel=None):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_channels'):
                return
            if not channel:
                channel = ctx.channel
            can_manage, missing = self._bot_can_manage_channel(ctx.guild, channel)
            if not can_manage:
                await ctx.send(
                    embed=discord.Embed(
                        description=(
                            f"บอทยังปลดล็อกห้องนี้ไม่ได้ เพราะสิทธิ์ไม่พอ: {', '.join(missing)}\n"
                            "กรุณาขยับยศบอทให้สูงขึ้นและเปิดสิทธิ์ที่จำเป็นก่อน"
                        ),
                        color=color.red,
                    ),
                    delete_after=12,
                )
                return
            if isinstance(channel, discord.TextChannel):
                await channel.set_permissions(ctx.guild.default_role, send_messages=True)
            elif isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(ctx.guild.default_role, connect=True,send_messages=True)
            else:
                await channel.set_permissions(ctx.guild.default_role, send_messages=True)
            await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been unlocked",color=color.green))
        except discord.Forbidden:
            logger.warning(
                f"unlock command missing permissions | guild={ctx.guild.id if ctx.guild else 'unknown'} "
                f"channel={channel.id if channel else getattr(getattr(ctx, 'channel', None), 'id', 'unknown')}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description="บอทไม่มีสิทธิ์ปลดล็อกห้องนี้ (Missing Permissions)",
                    color=color.red,
                ),
                delete_after=10,
            )
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in unlock command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)


    running_lockall = {}
    @commands.hybrid_command(
        name="lockall",
        help="ล็อกทุกห้องในเซิร์ฟเวอร์",
        aliases=["lockchannels"],
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=300,type=commands.BucketType.guild)
    async def lockall(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx,'manage_channels',role_position_check=True):
                return
            if self.running_lockall.get(ctx.guild.id,False):
                await ctx.send(embed=discord.Embed(description="มีคำสั่ง lockall อื่นกำลังทำงานอยู่",color=color.red),delete_after=10)
                return
            async def lock_channel(channel):
                try:
                    if isinstance(channel, discord.TextChannel):
                        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
                    elif isinstance(channel, discord.VoiceChannel):
                        await channel.set_permissions(ctx.guild.default_role, connect=False,send_messages=False)
                    else:
                        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
                except Exception as e:
                    logger.error(f"ข้อผิดพลาด in lockall command: {e}")
            processing_message = await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.LOADING} Locking all channels",color=color.yellow))
            self.running_lockall[ctx.guild.id] = True
            for channel in ctx.guild.text_channels:
                try:
                    await lock_channel(channel)
                except Exception as e:
                    pass
            if ctx.guild.id in self.running_lockall:
                del self.running_lockall[ctx.guild.id]
            await processing_message.edit(embed=discord.Embed(description="ล็อกทุกช่องเรียบร้อยแล้ว",color=color.green))
        except Exception as e:
            if ctx.guild.id in self.running_lockall:
                del self.running_lockall[ctx.guild.id]
            logger.error(f"ข้อผิดพลาด in lockall command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
    
    


    running_unhideall = {}
    @commands.hybrid_command(
        name="unlockall",
        help="ปลดล็อกทุกห้องในเซิร์ฟเวอร์",
        aliases=["unlockchannels"],
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=300,type=commands.BucketType.guild)
    async def unlockall(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx,'manage_channels',role_position_check=True):
                return
            if self.running_unhideall.get(ctx.guild.id,False):
                await ctx.send(embed=discord.Embed(description="มีคำสั่ง unlockall อื่นกำลังทำงานอยู่",color=color.red),delete_after=10)
                return
            async def unlock_channel(channel:discord.abc.GuildChannel):
                try:
                    if isinstance(channel, discord.TextChannel):
                        await channel.set_permissions(ctx.guild.default_role, send_messages=True)
                    elif isinstance(channel, discord.VoiceChannel):
                        await channel.set_permissions(ctx.guild.default_role, connect=True,send_messages=True)
                    else:
                        await channel.set_permissions(ctx.guild.default_role, send_messages=True)
                except Exception as e:
                    logger.error(f"ข้อผิดพลาด in unlockall command: {e}")
            processing_message = await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.LOADING} Unlocking all channels",color=color.yellow))
            self.running_unhideall[ctx.guild.id] = True
            for channel in ctx.guild.channels:
                try:
                    await unlock_channel(channel)
                except Exception as e:
                    pass
            if ctx.guild.id in self.running_unhideall:
                del self.running_unhideall[ctx.guild.id]
            await processing_message.edit(embed=discord.Embed(description="ปลดล็อกทุกช่องเรียบร้อยแล้ว",color=color.green))
        except Exception as e:
            if ctx.guild.id in self.running_unhideall:
                del self.running_unhideall[ctx.guild.id]
            logger.error(f"ข้อผิดพลาด in unlockall command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
    @commands.hybrid_command(
        name="hide",
        help="ซ่อนห้อง",
        aliases=["hidechannel"],
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3,per=60,type=commands.BucketType.guild)
    async def hide(self, ctx: commands.Context, channel: discord.abc.GuildChannel = None):
        try:
            if not await checks.check_is_moderator_permissions(ctx,'manage_channels'):
                return
            if not channel:
                channel = ctx.channel
            await channel.set_permissions(ctx.guild.default_role, view_channel=False)
            await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been hidden",color=color.green))
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in hide command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
    
    running_hideall = {}
    @commands.hybrid_command(
        name="hideall",
        help="ซ่อนทุกห้องในเซิร์ฟเวอร์",
        aliases=["hidechannels"],
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()  
    @commands.cooldown(rate=1,per=300,type=commands.BucketType.guild)
    async def hideall(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx,'manage_channels',role_position_check=True):
                return
            if self.running_hideall.get(ctx.guild.id,False):
                await ctx.send(embed=discord.Embed(description="มีคำสั่ง hideall อื่นกำลังทำงานอยู่",color=color.red),delete_after=10)
                return
            async def hide_channel(channel):
                try:
                    if isinstance(channel, discord.TextChannel):
                        if channel.permissions_for(ctx.guild.default_role).view_channel == False:
                            return
                        await channel.set_permissions(ctx.guild.default_role, view_channel=False)
                    elif isinstance(channel, discord.VoiceChannel):
                        if channel.permissions_for(ctx.guild.default_role).view_channel == False and channel.permissions_for(ctx.guild.default_role).connect == False:
                            return
                        await channel.set_permissions(ctx.guild.default_role, view_channel=False, connect=False)
                    else:
                        if channel.permissions_for(ctx.guild.default_role).view_channel == False:
                            return
                        await channel.set_permissions(ctx.guild.default_role, view_channel=False)
                except Exception as e:
                    logger.error(f"ข้อผิดพลาด in hideall command: {e}")
            processing_message = await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.LOADING} Hiding all channels",color=color.yellow))
            self.running_hideall[ctx.guild.id] = True
            for channel in ctx.guild.channels:
                try:
                    await hide_channel(channel)
                    await asyncio.sleep(1.5)
                except Exception as e:
                    pass
            if ctx.guild.id in self.running_hideall:
                del self.running_hideall[ctx.guild.id]
            await processing_message.edit(embed=discord.Embed(description="ซ่อนทุกช่องเรียบร้อยแล้ว",color=color.green))
        except Exception as e:
            if ctx.guild.id in self.running_hideall:
                del self.running_hideall[ctx.guild.id]
            logger.error(f"ข้อผิดพลาด in hideall command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    @commands.hybrid_command(
        name="unhide",
        help="ยกเลิกซ่อนห้อง",
        aliases=["unhidechannel"],
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3,per=60,type=commands.BucketType.guild)
    async def unhide(self, ctx: commands.Context, channel: discord.abc.GuildChannel = None):
        try:
            if not await checks.check_is_moderator_permissions(ctx,'manage_channels'):
                return
            if not channel:
                channel = ctx.channel
            await channel.set_permissions(ctx.guild.default_role, view_channel=True)
            await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been unhidden",color=color.green))
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in unhide command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    running_unhideall = {}
    @commands.hybrid_command(
        name="unhideall",
        help="ยกเลิกซ่อนทุกห้องในเซิร์ฟเวอร์",
        aliases=["unhidechannels"],
        with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=300,type=commands.BucketType.guild)
    async def unhideall(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx,'manage_channels',role_position_check=True):
                return
            if self.running_unhideall.get(ctx.guild.id,False):
                await ctx.send(embed=discord.Embed(description="มีคำสั่ง unhideall อื่นกำลังทำงานอยู่",color=color.red),delete_after=10)
                return
            async def unhide_channel(channel):
                try:
                    if isinstance(channel, discord.TextChannel):
                        if channel.permissions_for(ctx.guild.default_role).view_channel == True:
                            return
                        await channel.set_permissions(ctx.guild.default_role, view_channel=True)
                    elif isinstance(channel, discord.VoiceChannel):
                        if channel.permissions_for(ctx.guild.default_role).view_channel == True and channel.permissions_for(ctx.guild.default_role).connect == True:
                            return
                        await channel.set_permissions(ctx.guild.default_role, view_channel=True, connect=True)
                    else:
                        if channel.permissions_for(ctx.guild.default_role).view_channel == True:
                            return
                        await channel.set_permissions(ctx.guild.default_role, view_channel=True)
                except Exception as e:
                    logger.error(f"ข้อผิดพลาด in unhideall command: {e}")
            processing_message = await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.LOADING} Unhiding all channels",color=color.yellow))
            self.running_unhideall[ctx.guild.id] = True
            for channel in ctx.guild.channels:
                try:
                    await unhide_channel(channel)
                    await asyncio.sleep(1.5)
                except Exception as e:
                    pass
            if ctx.guild.id in self.running_unhideall:
                del self.running_unhideall[ctx.guild.id]
            await processing_message.edit(embed=discord.Embed(description="ยกเลิกการซ่อนทุกช่องเรียบร้อยแล้ว",color=color.green))
        except Exception as e:
            if ctx.guild.id in self.running_unhideall:
                del self.running_unhideall[ctx.guild.id]
            logger.error(f"ข้อผิดพลาด in unhideall command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    @commands.hybrid_group(
        name="mod",
        help="รวมคำสั่งดูแลเซิร์ฟเวอร์ไว้ในหมวดเดียว",
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    async def mod_group(self, ctx: commands.Context):
        if getattr(ctx, "invoked_subcommand", None) is not None:
            return
        embed = discord.Embed(
            title="คำสั่งการกลั่นกรอง",
            description=(
                "ใช้คำสั่งย่อยผ่าน `/mod ...`\n"
                "เช่น `/mod delete`, `/mod ban`, `/mod lock`"
            ),
            color=color.random_color(),
        )
        if hasattr(self.mod_group, "commands"):
            command_names = sorted(
                {
                    str(getattr(command, "name", "") or "").strip()
                    for command in list(getattr(self.mod_group, "commands", []) or [])
                    if str(getattr(command, "name", "") or "").strip()
                }
            )
            if command_names:
                embed.add_field(
                    name="Available Subcommands",
                    value=", ".join(f"`{name}`" for name in command_names)[:1024],
                    inline=False,
                )
        await ctx.send(embed=embed)

    @mod_group.command(name="delete", help="ลบข้อความตามโหมดที่ต้องการ")
    @discord.app_commands.describe(
        mode="โหมดการลบข้อความ",
        messages="จำนวน หรือช่วงข้อความ เช่น 50 หรือ 1400000000000000000-1400000000000000999",
        user="เลือกผู้ใช้ (ใช้กับ specificuser/usermessages/botmessages)",
        link="โหมด links: ใส่ลิงก์ที่ต้องการลบ หรือ all",
    )
    @discord.app_commands.choices(
        mode=[
            discord.app_commands.Choice(name="messages", value="messages"),
            discord.app_commands.Choice(name="specificuser", value="specificuser"),
            discord.app_commands.Choice(name="embeds", value="embeds"),
            discord.app_commands.Choice(name="emojis", value="emojis"),
            discord.app_commands.Choice(name="links", value="links"),
            discord.app_commands.Choice(name="usermessages", value="usermessages"),
            discord.app_commands.Choice(name="botmessages", value="botmessages"),
            discord.app_commands.Choice(name="deleteall", value="deleteall"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.channel)
    async def mod_delete(
        self,
        ctx: commands.Context,
        mode: str = "messages",
        messages: str = "20",
        user: discord.Member | None = None,
        link: str | None = None,
    ):
        await ctx.invoke(
            self.delete_command,
            mode=mode,
            messages=messages,
            user=user,
            link=link,
        )

    @mod_group.command(name="ban", help="แบนผู้ใช้ออกจากเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def mod_ban(
        self,
        ctx: commands.Context,
        user: discord.Member,
        *,
        reason: str | None = None,
    ):
        await ctx.invoke(self.ban_command, user=user, reason=reason)

    @mod_group.command(name="kick", help="เตะผู้ใช้ออกจากเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def mod_kick(
        self,
        ctx: commands.Context,
        user: discord.Member,
        *,
        reason: str | None = None,
    ):
        await ctx.invoke(self.kick_command, user=user, reason=reason)

    @mod_group.command(name="unban", help="ปลดแบนผู้ใช้จากเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def mod_unban(
        self,
        ctx: commands.Context,
        user: discord.User,
        *,
        reason: str | None = None,
    ):
        await ctx.invoke(self.unban_command, user=user, reason=reason)

    @mod_group.command(name="checkperms", help="เช็กสิทธิ์บอทในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.guild)
    async def mod_checkperms(self, ctx: commands.Context):
        await ctx.invoke(self.checkperms_command)

    @mod_group.command(name="lock", help="ล็อกห้อง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.guild)
    async def mod_lock(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel = None,
    ):
        await ctx.invoke(self.lock_command, channel=channel)

    @mod_group.command(name="unlock", help="ปลดล็อกห้อง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.guild)
    async def mod_unlock(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel = None,
    ):
        await ctx.invoke(self.unlock_command, channel=channel)

    @mod_group.command(name="lockall", help="ล็อกทุกห้องในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=300, type=commands.BucketType.guild)
    async def mod_lockall(self, ctx: commands.Context):
        await ctx.invoke(self.lockall)

    @mod_group.command(name="unlockall", help="ปลดล็อกทุกห้องในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=300, type=commands.BucketType.guild)
    async def mod_unlockall(self, ctx: commands.Context):
        await ctx.invoke(self.unlockall)

    @mod_group.command(name="hide", help="ซ่อนห้อง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.guild)
    async def mod_hide(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel = None,
    ):
        await ctx.invoke(self.hide, channel=channel)

    @mod_group.command(name="hideall", help="ซ่อนทุกห้องในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=300, type=commands.BucketType.guild)
    async def mod_hideall(self, ctx: commands.Context):
        await ctx.invoke(self.hideall)

    @mod_group.command(name="unhide", help="ยกเลิกซ่อนห้อง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.guild)
    async def mod_unhide(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel = None,
    ):
        await ctx.invoke(self.unhide, channel=channel)

    @mod_group.command(name="unhideall", help="ยกเลิกซ่อนทุกห้องในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=300, type=commands.BucketType.guild)
    async def mod_unhideall(self, ctx: commands.Context):
        await ctx.invoke(self.unhideall)


    # main primary command will also will be in slash command
    # role is not in the slashcommand fix it
    @commands.hybrid_group(
        name="role",
        help="จัดการบทบาทของผู้ใช้",
        with_app_command=True,
        invoke_without_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=60,type=commands.BucketType.user)
    # role @member @role
    @discord.app_commands.describe(member="The member to assign or remove the role", role="The role to assign or remove")
    async def role_command(self,ctx:commands.Context,member:discord.Member=None,*,role:discord.Role=None):
        try:
            if not member:
                # show all the commands this group has
                embed = discord.Embed(
                    title="คำสั่งบทบาท",
                    description="จัดการบทบาทของผู้ใช้",
                    color=color.random_color()
                )
                embed.description += f"\n\n`{self.bot.BotConfig.PREFIX}{ctx.command.name} <member> <role>` : give or remove a role to a member"
                if hasattr(ctx.command,'commands'):
                    for command in ctx.command.commands:
                        embed.description += f"\n\n`{self.bot.BotConfig.PREFIX}{ctx.command.name} {command.name}` : {command.help}"
                await ctx.send(embed=embed)
            elif not role:
                return await ctx.send(embed=discord.Embed(description=f"Invalid Syntax\n\n`{self.bot.BotConfig.PREFIX}{ctx.command.name} <member> <role>`",color=color.red))


            else:
                try:
                    if not await checks.check_is_moderator_permissions(ctx, 'manage_roles'):
                        return
                    if not await checks.check_if_user_can_manage_this_role(ctx,role):
                        return
                    
                    if role in member.roles:
                        await member.remove_roles(role)
                        await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.DELETE} Removed {role.mention} from {member.mention}",color=color.green))
                    else:
                        await member.add_roles(role)
                        await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.CREATE} Added {role.mention} to {member.mention}",color=color.green))          
                except Exception as e:
                    logger.error(f"ข้อผิดพลาด in role command: {e}")
                    await ctx.send("An error occurred while processing the command.",delete_after=5)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in role command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)


    running_humans_command = {} # running_humans_command[guild_id] = True/False

    # role humans @role
    @role_command.command(
        name="humans",
        help="จัดการยศของผู้ใช้จริงในเซิร์ฟเวอร์",
        with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=300,type=commands.BucketType.guild)
    async def role_humans_command(self,ctx:commands.Context,role:discord.Role):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_roles'):
                return
            if not await checks.check_if_user_can_manage_this_role(ctx,role):
                return
            
            if self.running_humans_command.get(ctx.guild.id,False):
                await ctx.send(embed=discord.Embed(description="มีคำสั่ง humans อื่นกำลังทำงานอยู่",color=color.red),delete_after=10)
                return

            def calculate_role_delay(user_count: int) -> float:
                # Maximum allowed rate per second
                max_rate_per_second = 16.67
                
                # Calculate delay per role change (in seconds)
                delay_per_user = 1 / max_rate_per_second
                
                # Adding a safety buffer
                safe_delay = delay_per_user + 2 # 0.04 seconds is added as a safety buffer
                
                # Calculate total time required for the given number of users
                total_time = user_count * safe_delay
                
                return safe_delay, total_time
            
            # Get all the humans in the server
            humans = [member for member in ctx.guild.members if not member.bot and role not in member.roles]
            total_humans = len(humans)
            delay_per_user, total_time = calculate_role_delay(total_humans)

            # Send a message aproximating the time required to complete the task
            message = await ctx.send(embed=discord.Embed(description=f"Estimated time to complete the task: <t:{int(datetime.datetime.now().timestamp() + datetime.timedelta(seconds=total_time).total_seconds()+20)}:R>",color=color.random_color()))
            self.running_humans_command[ctx.guild.id] = True

            # Add the role to all the humans
            added_users = 0
            for human in humans:
                try:
                    if role in human.roles:
                        continue
                    await human.add_roles(role)
                    await asyncio.sleep(delay_per_user)
                    added_users += 1
                except Exception as e:
                    pass
            await message.edit(embed=discord.Embed(description=f"Added {role.mention} to {added_users} users",color=color.green))
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in role humans command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
        self.running_humans_command[ctx.guild.id] = False


    running_bots_command = {} # running_bots_command[guild_id] = True/False

    # role bots @role
    @role_command.command(
        name="bots",
        help="จัดการยศของบอทในเซิร์ฟเวอร์",
        with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=300,type=commands.BucketType.guild)
    async def role_bots_command(self,ctx:commands.Context,role:discord.Role):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_roles'):
                return
            if not await checks.check_if_user_can_manage_this_role(ctx,role):
                return
            
            if self.running_bots_command.get(ctx.guild.id,False):
                await ctx.send(embed=discord.Embed(description="มีคำสั่ง bots อื่นกำลังทำงานอยู่",color=color.red),delete_after=10)
                return

            def calculate_role_delay(user_count: int) -> float:
                # Maximum allowed rate per second
                max_rate_per_second = 16.67
                
                # Calculate delay per role change (in seconds)
                delay_per_user = 1 / max_rate_per_second
                
                # Adding a safety buffer
                safe_delay = delay_per_user + 2 # 0.04 seconds is added as a safety buffer
                
                # Calculate total time required for the given number of users
                total_time = user_count * safe_delay
                
                return safe_delay, total_time
            
            # Get all the bots in the server
            bots = [member for member in ctx.guild.members if member.bot and role not in member.roles]
            total_bots = len(bots)
            delay_per_user, total_time = calculate_role_delay(total_bots)

            # Send a message aproximating the time required to complete the task
            message = await ctx.send(embed=discord.Embed(description=f"Estimated time to complete the task: <t:{int(datetime.datetime.now().timestamp() + datetime.timedelta(seconds=total_time).total_seconds()+20)}:R>",color=color.random_color()))

            self.running_bots_command[ctx.guild.id] = True

            # Add the role to all the bots
            added_users = 0
            for bot in bots:
                try:
                    if role in bot.roles:
                        continue
                    await bot.add_roles(role)
                    await asyncio.sleep(delay_per_user)
                    added_users += 1
                except Exception as e:
                    pass
            await message.edit(embed=discord.Embed(description=f"Added {role.mention} to {added_users} bots",color=color.green))
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in role bots command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
        self.running_bots_command[ctx.guild.id] = False

    @commands.command(
        name="mute",
        help="ปิดเสียงสมาชิกในเซิร์ฟเวอร์",
        aliases=["timeout"]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5,per=60,type=commands.BucketType.user)
    # mute @member 2h[optional] reason[optional]
    async def mute_command(self,ctx:commands.Context,member:discord.Member,time:str,*,reason:str='No reason provided'):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'moderate_members'):
                return
            
            # check if the bot has the required permissions
            if not ctx.guild.me.guild_permissions.moderate_members:
                await ctx.send(embed=discord.Embed(description="บอทไม่มีสิทธิ์ที่จำเป็นสำหรับปิดเสียงสมาชิก",color=color.red),delete_after=10)
                return

            if member.guild_permissions.administrator:
                await ctx.send(embed=discord.Embed(description=f"{member.mention} is an administrator",color=color.red),delete_after=10)
                return
            
            if member == ctx.author:
                await ctx.send(embed=discord.Embed(description=f"Dropping a piano on your head...",color=color.red),delete_after=10)
                return
            
            if member == ctx.guild.me:
                await ctx.send(embed=discord.Embed(description=f"What have I done to you?",color=color.red),delete_after=10)
                return
            
            if member.top_role >= ctx.author.top_role:
                await ctx.send(embed=discord.Embed(description=f"คุณไม่สามารถมิวต์ {member.mention} เพราะยศของเขาสูงกว่าคุณ",color=color.red),delete_after=10)
                return

            if member.top_role >= ctx.guild.me.top_role:
                await ctx.send(embed=discord.Embed(description=f"I can't mute {member.mention} cause their role is higher than me",color=color.red),delete_after=10)
                return

            if await checks.check_is_owner_raw(member,ctx.guild):
                await ctx.send(embed=discord.Embed(description=f"คุณไม่สามารถมิวต์ the owner of the server",color=color.red),delete_after=10)
                return
            
            if member.is_timed_out():
                await ctx.send(embed=discord.Embed(description=f"{member.mention} is already muted",color=color.red),delete_after=10)
                return
            
            # convert time from 1s, 1m, 1h, 1d to seconds
            
            try:
                time = time.lower()
                if time:
                    time = time.replace('s','').replace('m','*60').replace('h','*60*60').replace('d','*60*60*24')
                    time = eval(time)
            except Exception as e:
                time = None
                
            try:
                await member.timeout(datetime.timedelta(seconds=time),reason=reason)
                await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.SUCCESS} {member.mention} has been muted",color=color.green))
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in mute command: {e}")
                await ctx.send("An error occurred while processing the command.",delete_after=5)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in mute command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    @commands.group(
        name="unmute",
        help="ยกเลิกปิดเสียงสมาชิกในเซิร์ฟเวอร์",
        invoke_without_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5,per=60,type=commands.BucketType.user)
    # unmute @member reason[optional]
    async def unmute_command(self,ctx:commands.Context,member:discord.Member,*,reason:str='No reason provided'):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'moderate_members'):
                return
            
            # check if the bot has the required permissions
            if not ctx.guild.me.guild_permissions.moderate_members:
                await ctx.send(embed=discord.Embed(description="บอทไม่มีสิทธิ์ที่จำเป็นสำหรับยกเลิกปิดเสียงสมาชิก",color=color.red),delete_after=10)
                return

            if member.is_timed_out():
                await member.timeout(None,reason=reason)
                await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.SUCCESS} {member.mention} has been unmuted",color=color.green))
            else:
                await ctx.send(embed=discord.Embed(description=f"{self.bot.emoji.ERROR} {member.mention} is not muted",color=color.red),delete_after=10)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in unmute command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
    
    @unmute_command.command(
        name="all",
        help="ยกเลิกปิดเสียงสมาชิกทั้งหมดในเซิร์ฟเวอร์"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=120,type=commands.BucketType.guild)
    async def unmute_all_command(self,ctx:commands.Context,*,reason:str='No reason provided'):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'moderate_members'):
                return
            
            # check if the bot has the required permissions
            if not ctx.guild.me.guild_permissions.moderate_members:
                await ctx.send(embed=discord.Embed(description="บอทไม่มีสิทธิ์ที่จำเป็นสำหรับยกเลิกปิดเสียงสมาชิก",color=color.red),delete_after=10)
                return

            muted_members = [member for member in ctx.guild.members if member.is_timed_out()]
            count = 0
            for member in muted_members:
                try:
                    await member.timeout(None,reason=reason)
                    count += 1
                except Exception as e:
                    pass
            await ctx.send(embed=discord.Embed(description=f"Unmuted {len(count)} members out of {len(muted_members)} muted members",color=color.green))
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in unmute all command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
    
    @commands.hybrid_group(
        name="mediachannel",
        help="จัดการห้องมีเดียในเซิร์ฟเวอร์",
        invoke_without_command=True,
        with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=30,type=commands.BucketType.guild)
    async def media_channel_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'administrator'):
                return
            
            embed = discord.Embed(
                title="คำสั่งจัดการช่องมีเดีย",
                description="นี่คือคำสั่งสำหรับจัดการช่องมีเดีย",
                color=color.random_color()
            )
            if hasattr(ctx.command,'commands'):
                for command in ctx.command.commands:
                    embed.description += f"\n\n`{self.bot.BotConfig.PREFIX}{ctx.command.name} {command.name}` : {command.help}"
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in media channel command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    @media_channel_command.command(
        name="add",
        help="เพิ่มห้องมีเดีย",
        with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=30,type=commands.BucketType.guild)
    async def media_channel_add_command(self,ctx:commands.Context,channel:discord.TextChannel):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'administrator'):
                return
            try:
                if cache.media_channels.get(str(ctx.guild.id),{}).get(str(channel.id)):
                    await ctx.send(embed=discord.Embed(description=f"{channel.mention} is already a media channel",color=color.red),delete_after=10)
                    return
                
                guilds_subscription = cache.guilds.get(str(ctx.guild.id),{}).get('subscription','free')

                if guilds_subscription == 'free':
                    media_channels_limit = 1
                elif guilds_subscription == 'silver_guild_preminum':
                    media_channels_limit = 3
                elif guilds_subscription == 'golden_guild_premium':
                    media_channels_limit = 5
                elif guilds_subscription in {'diamond_guild_premium', 'permanent_guild_premium', 'lifetime_guild_premium'}:
                    media_channels_limit = 10
                else:
                    media_channels_limit = 1
                
                if len(cache.media_channels.get(str(ctx.guild.id),{})) >= media_channels_limit:
                    await ctx.send(embed=discord.Embed(description=f"Media channels limit reached. You can only have {media_channels_limit} media channels",color=color.red),delete_after=10)
                    return

                await storage.media_channels.insert(guild_id=ctx.guild.id,channel_id=channel.id)
                await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been added as a media channel",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in media channel add command: {e}")
                await ctx.send("An error occurred while processing the command.",delete_after=5)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in media channel add command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
    
    @media_channel_command.command(
        name="remove",
        help="ลบห้องมีเดีย",
        with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=30,type=commands.BucketType.guild)
    async def media_channel_remove_command(self,ctx:commands.Context,channel:discord.TextChannel):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'administrator'):
                return
            try:
                if not cache.media_channels.get(str(ctx.guild.id),{}).get(str(channel.id)):
                    await ctx.send(embed=discord.Embed(description=f"{channel.mention} is not a media channel",color=color.red),delete_after=10)
                    return
                await storage.media_channels.delete(guild_id=ctx.guild.id,channel_id=channel.id)
                await ctx.send(embed=discord.Embed(description=f"{channel.mention} has been removed as a media channel",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in media channel remove command: {e}")
                await ctx.send("An error occurred while processing the command.",delete_after=5)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in media channel remove command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
    
    @media_channel_command.command(
        name="list",
        help="แสดงรายการห้องมีเดีย",
        with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=30,type=commands.BucketType.guild)
    async def media_channel_list_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'administrator'):
                return
            try:
                media_channels = cache.media_channels.get(str(ctx.guild.id),{})
                
                if not media_channels:
                    await ctx.send(embed=discord.Embed(description="ยังไม่มีการเพิ่มช่องมีเดีย",color=color.red),delete_after=10)
                    return
                embed = discord.Embed(
                    title="ช่องมีเดีย",
                    color=color.random_color()
                )
                embed.description = ' | '.join([f"<#{channel_id}>" for channel_id in media_channels.keys()])
                embed.set_footer(text=f"Total media channels: {len(media_channels)}")
                await ctx.send(embed=embed)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in media channel list command: {e}")
                await ctx.send("An error occurred while processing the command.",delete_after=5)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in media channel list command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    @media_channel_command.command(
        name='reset',
        help="รีเซ็ตห้องมีเดียทั้งหมด",
        with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=120,type=commands.BucketType.guild)
    async def media_channel_reset_command(self,ctx:commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'administrator'):
                return
            try:
                await storage.media_channels.delete(guild_id=ctx.guild.id)
                await ctx.send(embed=discord.Embed(description="รีเซ็ตช่องมีเดียทั้งหมดเรียบร้อยแล้ว",color=color.green),delete_after=10)
            except Exception as e:
                logger.error(f"ข้อผิดพลาด in media channel reset command: {e}")
                await ctx.send("An error occurred while processing the command.",delete_after=5)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in media channel reset command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)

    @commands.hybrid_group(
        name="promote",
        help="จัดการห้องส่งโปรโมตและห้องสาธารณะ",
        invoke_without_command=True,
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=20,type=commands.BucketType.guild)
    async def promote_command(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "administrator"):
                return
            is_th = i18n.guild_lang(ctx.guild.id) == "th"
            promote_data = await storage.promote_channels.get(guild_id=ctx.guild.id)
            embed = discord.Embed(
                title=i18n.tr("promote_cmd_title", ctx.guild.id),
                description=(
                    f"`{self.bot.BotConfig.PREFIX}promote setup <submit_channel> <public_channel>`\n"
                    f"`{self.bot.BotConfig.PREFIX}promote delete`\n\n"
                    f"`{self.bot.BotConfig.PREFIX}promote saved`\n"
                    f"`{self.bot.BotConfig.PREFIX}promote saved_add <name> <content> [attachments] [invite_url]`\n"
                    f"`{self.bot.BotConfig.PREFIX}promote saved_send <id>`\n"
                    f"`{self.bot.BotConfig.PREFIX}promote saved_delete <id>`\n"
                    f"`{self.bot.BotConfig.PREFIX}promote saved_edit <id> [name] [content] [attachments] [invite_url]`\n\n"
                    f"{i18n.tr('promote_cmd_desc', ctx.guild.id)}"
                ),
                color=color.random_color(),
            )
            if promote_data:
                embed.add_field(
                    name=i18n.tr("promote_current_setup", ctx.guild.id),
                    value=(
                        f"{i18n.tr('promote_submit', ctx.guild.id)}: <#{promote_data.get('submit_channel_id')}>\n"
                        f"{i18n.tr('promote_public', ctx.guild.id)}: <#{promote_data.get('public_channel_id')}>\n"
                        f"{i18n.tr('promote_cooldown', ctx.guild.id)}: `{PROMOTE_COOLDOWN_HOURS} {i18n.tr('promote_hours', ctx.guild.id)}`"
                    ),
                    inline=False,
                )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in promote command: {e}")
            await ctx.send(
                ("เกิดข้อผิดพลาดระหว่างประมวลผลคำสั่ง" if i18n.guild_lang(ctx.guild.id) == "th" else "An error occurred while processing the command."),
                delete_after=5,
            )

    @promote_command.command(name="setup", with_app_command=True, help="ตั้งค่าห้องส่งโปรโมตและห้องสาธารณะ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=20,type=commands.BucketType.guild)
    async def promote_setup_command(
        self,
        ctx: commands.Context,
        submit_channel: discord.TextChannel,
        public_channel: discord.TextChannel,
    ):
        try:
            async def _safe_send(*args, **kwargs):
                try:
                    return await ctx.send(*args, **kwargs)
                except discord.NotFound:
                    if getattr(ctx, "channel", None):
                        kwargs.pop("ephemeral", None)
                        return await ctx.channel.send(*args, **kwargs)
                    raise

            if ctx.interaction and not ctx.interaction.response.is_done():
                try:
                    await ctx.defer(ephemeral=True)
                except (discord.InteractionResponded, discord.NotFound):
                    pass
                except discord.HTTPException as interaction_error:
                    if getattr(interaction_error, "code", None) != 10062:
                        raise
            if not await checks.check_is_moderator_permissions(ctx, "administrator"):
                return
            is_th = i18n.guild_lang(ctx.guild.id) == "th"
            if submit_channel.id == public_channel.id:
                return await _safe_send(
                    embed=discord.Embed(
                        description=i18n.tr("promote_channel_must_different", ctx.guild.id),
                        color=color.red,
                    ),
                    delete_after=10,
                )
            bot_member = ctx.guild.me or ctx.guild.get_member(getattr(self.bot.user, "id", 0))
            if bot_member is None:
                return await _safe_send(
                    embed=discord.Embed(
                        description=(
                            "ไม่พบบัญชีบอทในเซิร์ฟเวอร์นี้ กรุณาลองใหม่อีกครั้ง"
                            if is_th
                            else "Bot account was not found in this server. Please try again."
                        ),
                        color=color.red,
                    ),
                    delete_after=10,
                )

            submit_missing = self._channel_missing_permissions(
                submit_channel,
                bot_member,
                {
                    "view_channel": "View Channel",
                    "send_messages": "Send Messages",
                    "embed_links": "Embed Links",
                },
            )
            public_missing = self._channel_missing_permissions(
                public_channel,
                bot_member,
                {
                    "view_channel": "View Channel",
                    "send_messages": "Send Messages",
                    "embed_links": "Embed Links",
                },
            )
            if submit_missing or public_missing:
                lines: list[str] = []
                if submit_missing:
                    lines.append(
                        f"{i18n.tr('promote_submit_channel', ctx.guild.id)} {submit_channel.mention}: "
                        f"{', '.join(submit_missing)}"
                    )
                if public_missing:
                    lines.append(
                        f"{i18n.tr('promote_public_channel', ctx.guild.id)} {public_channel.mention}: "
                        f"{', '.join(public_missing)}"
                    )
                details = "\n".join([f"- {line}" for line in lines])[:1200]
                return await _safe_send(
                    embed=discord.Embed(
                        description=(
                            (
                                "บอทยังไม่มีสิทธิ์ที่จำเป็นสำหรับระบบ Promote ในห้องที่เลือก:\n"
                                f"{details}\n"
                                "กรุณาแก้สิทธิ์ของบอทก่อน แล้วค่อยรัน /promote setup ใหม่"
                            )
                            if is_th
                            else (
                                "Bot is missing required permissions for Promote in selected channels:\n"
                                f"{details}\n"
                                "Please fix bot permissions, then run /promote setup again."
                            )
                        ),
                        color=color.red,
                    ),
                    delete_after=15,
                )
            cooldown_seconds = PROMOTE_COOLDOWN_SECONDS

            storage_failed = False
            try:
                promote_data = await storage.promote_channels.get(guild_id=ctx.guild.id)
            except Exception as error:
                storage_failed = True
                logger.warning(
                    "promote setup load failed | guild=%s error=%s",
                    ctx.guild.id,
                    error,
                )
                promote_data = cache.promote_channels.get(str(ctx.guild.id), {})

            is_first_setup = not bool(promote_data)
            try:
                if not promote_data:
                    promote_data = await storage.promote_channels.insert(
                        guild_id=ctx.guild.id,
                        submit_channel_id=submit_channel.id,
                        public_channel_id=public_channel.id,
                        cooldown_seconds=cooldown_seconds,
                        cooldowns={},
                        enabled=True,
                    )
                else:
                    promote_row_id = int(promote_data.get("id") or 0) if str(promote_data.get("id") or "").isdigit() else 0
                    if promote_row_id > 0:
                        promote_data = await storage.promote_channels.update(
                            id=promote_row_id,
                            submit_channel_id=submit_channel.id,
                            public_channel_id=public_channel.id,
                            cooldown_seconds=cooldown_seconds,
                            enabled=True,
                        )
                    else:
                        promote_data = await storage.promote_channels.insert(
                            guild_id=ctx.guild.id,
                            submit_channel_id=submit_channel.id,
                            public_channel_id=public_channel.id,
                            cooldown_seconds=cooldown_seconds,
                            cooldowns=dict(promote_data.get("cooldowns") or {}),
                            enabled=True,
                        )
            except Exception as error:
                storage_failed = True
                logger.warning(
                    "promote setup save failed | guild=%s error=%s",
                    ctx.guild.id,
                    error,
                )
            if isinstance(promote_data, dict):
                cache.promote_channels[str(ctx.guild.id)] = dict(promote_data)
            else:
                cache.promote_channels[str(ctx.guild.id)] = {
                    "guild_id": int(ctx.guild.id),
                    "submit_channel_id": int(submit_channel.id),
                    "public_channel_id": int(public_channel.id),
                    "cooldown_seconds": int(cooldown_seconds),
                    "cooldowns": {},
                    "enabled": True,
                }
            cache_snapshot = dict(cache.promote_channels.get(str(ctx.guild.id), {}) or {})
            cache_snapshot["guild_id"] = int(ctx.guild.id)
            cache_snapshot["submit_channel_id"] = int(submit_channel.id)
            cache_snapshot["public_channel_id"] = int(public_channel.id)
            cache_snapshot["cooldown_seconds"] = int(cooldown_seconds)
            cache_snapshot["enabled"] = True
            if not isinstance(cache_snapshot.get("cooldowns"), dict):
                cache_snapshot["cooldowns"] = {}
            cache.promote_channels[str(ctx.guild.id)] = cache_snapshot

            try:
                if ctx.guild.me and ctx.guild.me.guild_permissions.manage_channels:
                    await public_channel.set_permissions(
                        ctx.guild.default_role,
                        send_messages=False,
                        add_reactions=False,
                    )
            except Exception:
                pass

            if is_first_setup:
                try:
                    welcome_embed = discord.Embed(
                        title="เปิดใช้งานห้องโปรโมตสาธารณะแล้ว",
                        description=(
                            "ห้องนี้ถูกตั้งเป็นห้องโปรโมตสาธารณะของเซิร์ฟเวอร์นี้\n"
                            "โพสต์โปรโมตใหม่ที่อนุมัติแล้วจะถูกส่งมายังห้องนี้อัตโนมัติ"
                        ),
                        color=discord.Color.blurple(),
                    )
                    welcome_embed.set_image(url=style_urls.PROMOTE_FIRST_SETUP_IMAGE)
                    welcome_embed.set_footer(text="SkylineBOT Promote")
                    await public_channel.send(embed=welcome_embed)
                except Exception as exc:
                    logger.warning(
                        "ไม่สามารถส่งรูปแนะนำโปรโมตครั้งแรกได้ | guild=%s channel=%s err=%s",
                        ctx.guild.id,
                        public_channel.id,
                        exc,
                    )

            await _safe_send(
                embed=discord.Embed(
                    description=(
                        f"{self.bot.emoji.SUCCESS} {i18n.tr('promote_setup_updated', ctx.guild.id)}\n"
                        f"{i18n.tr('promote_submit_channel', ctx.guild.id)}: {submit_channel.mention}\n"
                        f"{i18n.tr('promote_public_channel', ctx.guild.id)}: {public_channel.mention}\n"
                        f"{i18n.tr('promote_cooldown', ctx.guild.id)}: `{PROMOTE_COOLDOWN_HOURS} {i18n.tr('promote_hours', ctx.guild.id)}`"
                        + (
                            "\nหมายเหตุ: บันทึกแบบชั่วคราวในหน่วยความจำ เพราะฐานข้อมูลยังไม่พร้อม"
                            if storage_failed and is_th
                            else (
                                "\nNote: Temporary in-memory setup was used because database is unavailable."
                                if storage_failed
                                else ""
                            )
                        )
                    ),
                    color=color.green,
                )
            )
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in promote setup command: {e}")
            try:
                await ctx.send(
                    ("An error occurred while processing the command."),
                    delete_after=5,
                )
            except discord.NotFound:
                if getattr(ctx, "channel", None):
                    await ctx.channel.send(
                        "An error occurred while processing the command.",
                        delete_after=5,
                    )

    async def _promote_delete_setup(self, ctx: commands.Context):
        if not await checks.check_is_moderator_permissions(ctx, "administrator"):
            return
        deleted = []
        storage_failed = False
        try:
            deleted = await storage.promote_channels.delete(guild_id=ctx.guild.id)
        except Exception as error:
            storage_failed = True
            logger.warning(
                "promote delete failed | guild=%s error=%s",
                ctx.guild.id,
                error,
            )
        cache.promote_channels.pop(str(ctx.guild.id), None)
        if storage_failed:
            return await ctx.send(
                embed=discord.Embed(
                    description="รีเซ็ตค่าในหน่วยความจำแล้ว แต่ฐานข้อมูลยังไม่พร้อมชั่วคราว",
                    color=color.yellow,
                ),
                delete_after=12,
            )
        if not deleted:
            return await ctx.send(
                embed=discord.Embed(
                    description=i18n.tr("promote_not_configured", ctx.guild.id),
                    color=color.red,
                ),
                delete_after=10,
            )
        await ctx.send(
            embed=discord.Embed(
                description=f"{self.bot.emoji.SUCCESS} {i18n.tr('promote_setup_removed', ctx.guild.id)}",
                color=color.green,
            )
        )

    @promote_command.command(name="delete", with_app_command=True, help="ลบ/รีเซ็ตค่าระบบโปรโมตในกิลด์นี้")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=20,type=commands.BucketType.guild)
    async def promote_delete_command(self, ctx: commands.Context):
        try:
            await self._promote_delete_setup(ctx)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in promote delete command: {e}")
            await ctx.send(
                ("เกิดข้อผิดพลาดระหว่างประมวลผลคำสั่ง" if i18n.guild_lang(ctx.guild.id) == "th" else "An error occurred while processing the command."),
                delete_after=5,
            )

    @promote_command.command(
        name="delead",
        with_app_command=False,
        hidden=True,
        help="คำสั่งลัดแบบข้อความของ promote delete",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=20,type=commands.BucketType.guild)
    async def promote_delead_command(self, ctx: commands.Context):
        try:
            await self._promote_delete_setup(ctx)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in promote delead command: {e}")
            await ctx.send(
                ("เกิดข้อผิดพลาดระหว่างประมวลผลคำสั่ง" if i18n.guild_lang(ctx.guild.id) == "th" else "An error occurred while processing the command."),
                delete_after=5,
            )

    @promote_command.command(
        name="delest",
        with_app_command=False,
        hidden=True,
        help="คำสั่งลัดแบบข้อความของ promote delete",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1,per=20,type=commands.BucketType.guild)
    async def promote_delest_command(self, ctx: commands.Context):
        try:
            await self._promote_delete_setup(ctx)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in promote delest command: {e}")
            await ctx.send(
                ("เกิดข้อผิดพลาดระหว่างประมวลผลคำสั่ง" if i18n.guild_lang(ctx.guild.id) == "th" else "An error occurred while processing the command."),
                delete_after=5,
            )

    def _promote_saved_messages(self, promote_data: dict) -> list[dict]:
        raw_items = promote_data.get("saved_messages") if isinstance(promote_data, dict) else []
        if not isinstance(raw_items, list):
            return []
        rows = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            try:
                row_id = int(raw.get("id"))
            except Exception:
                continue
            attachments = raw.get("attachments")
            if not isinstance(attachments, list):
                attachments = []
            rows.append(
                {
                    "id": row_id,
                    "name": str(raw.get("name") or f"บันทึก #{row_id}")[:80],
                    "content": str(raw.get("content") or "")[:1800],
                    "attachments": [str(item).strip() for item in attachments if str(item).strip()][:5],
                    "invite_url": str(raw.get("invite_url") or "").strip() or None,
                }
            )
        rows.sort(key=lambda item: int(item.get("id") or 0))
        return rows

    @promote_command.command(name="saved", with_app_command=True, help="ดูรายการโปรโมตที่บันทึกไว้")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    async def promote_saved_list_command(self, ctx: commands.Context):
        if not await checks.check_is_moderator_permissions(ctx, "administrator"):
            return
        promote_data = await storage.promote_channels.get(guild_id=ctx.guild.id)
        if not promote_data:
            await ctx.send("ยังไม่ได้ตั้งค่าระบบโปรโมต")
            return
        if not promote_data.get("submit_channel_id") or not promote_data.get("public_channel_id"):
            await ctx.send("ยังไม่ได้ตั้งค่าห้องส่งคำขอ/ห้องสาธารณะ")
            return
        if not bool(promote_data.get("enabled", True)):
            await ctx.send("ระบบโปรโมตถูกปิดใช้งานอยู่")
            return
        saved = self._promote_saved_messages(promote_data)
        plan = cache.guilds.get(str(ctx.guild.id), {}).get("subscription", "free")
        limit = _promote_saved_limit(plan)
        if not saved:
            await ctx.send(f"ยังไม่มีรายการบันทึกโปรโมต (`0/{limit}`)")
            return
        lines = [f"`#{item['id']}` {item['name']}" for item in saved[:15]]
        await ctx.send(
            embed=discord.Embed(
                title="รายการโปรโมตที่บันทึกไว้",
                description="\n".join(lines) + f"\n\nรวม `{len(saved)}/{limit}` รายการ",
                color=color.blue,
            )
        )

    @promote_command.command(name="saved_add", with_app_command=True, help="บันทึกข้อความโปรโมตใหม่")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    async def promote_saved_add_command(
        self,
        ctx: commands.Context,
        name: str,
        content: str,
        attachments: str = None,
        invite_url: str = None,
    ):
        if not await checks.check_is_moderator_permissions(ctx, "administrator"):
            return
        promote_data = await storage.promote_channels.get(guild_id=ctx.guild.id)
        if not promote_data:
            await ctx.send("ยังไม่ได้ตั้งค่าระบบโปรโมต")
            return
        plan = cache.guilds.get(str(ctx.guild.id), {}).get("subscription", "free")
        limit = _promote_saved_limit(plan)
        if limit <= 0:
            await ctx.send("แพ็กเกจ Free ยังบันทึกโปรโมตไม่ได้")
            return
        saved = self._promote_saved_messages(promote_data)
        if len(saved) >= limit:
            await ctx.send(f"ลิมิตรายการบันทึกเต็มแล้ว ({len(saved)}/{limit})")
            return
        next_id = (max((int(item.get("id") or 0) for item in saved), default=0) + 1) if saved else 1
        attachments_list = [part.strip() for part in str(attachments or "").split(",") if part.strip()][:5]
        saved.append(
            {
                "id": next_id,
                "name": str(name or "").strip()[:80] or f"บันทึก #{next_id}",
                "content": str(content or "").strip()[:1800],
                "attachments": attachments_list,
                "invite_url": str(invite_url or "").strip() or None,
                "created_by": str(ctx.author.id),
                "created_at": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            }
        )
        await storage.promote_channels.update(id=promote_data.get("id"), saved_messages=saved)
        await ctx.send(f"{self.bot.emoji.SUCCESS} บันทึกรายการโปรโมต #{next_id} แล้ว")

    @promote_command.command(
        name="saved_delete",
        with_app_command=True,
        help="ลบโปรโมตที่บันทึกไว้ด้วยรหัส ID",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    async def promote_saved_delete_command(self, ctx: commands.Context, template_id: int):
        if not await checks.check_is_moderator_permissions(ctx, "administrator"):
            return
        promote_data = await storage.promote_channels.get(guild_id=ctx.guild.id)
        if not promote_data:
            await ctx.send("ยังไม่ได้ตั้งค่าระบบโปรโมต")
            return
        saved = self._promote_saved_messages(promote_data)
        before = len(saved)
        saved = [row for row in saved if int(row.get("id") or 0) != int(template_id)]
        if len(saved) == before:
            await ctx.send("ไม่พบรายการบันทึกที่ต้องการลบ")
            return
        await storage.promote_channels.update(id=promote_data.get("id"), saved_messages=saved)
        await ctx.send(f"ลบรายการบันทึก #{template_id} แล้ว")

    @promote_command.command(
        name="saved_edit",
        with_app_command=True,
        help="แก้ไขโปรโมตที่บันทึกไว้ด้วยรหัส ID",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    async def promote_saved_edit_command(
        self,
        ctx: commands.Context,
        template_id: int,
        name: str = None,
        content: str = None,
        attachments: str = None,
        invite_url: str = None,
    ):
        if not await checks.check_is_moderator_permissions(ctx, "administrator"):
            return
        promote_data = await storage.promote_channels.get(guild_id=ctx.guild.id)
        if not promote_data:
            await ctx.send("ยังไม่ได้ตั้งค่าระบบโปรโมต")
            return
        saved = self._promote_saved_messages(promote_data)
        target = None
        for row in saved:
            if int(row.get("id") or 0) == int(template_id):
                target = row
                break
        if not target:
            await ctx.send("ไม่พบรายการบันทึกที่ต้องการแก้ไข")
            return
        if name is not None:
            target["name"] = str(name).strip()[:80] or target["name"]
        if content is not None:
            target["content"] = str(content).strip()[:1800]
        if attachments is not None:
            target["attachments"] = [part.strip() for part in str(attachments).split(",") if part.strip()][:5]
        if invite_url is not None:
            invite_clean = str(invite_url).strip()
            target["invite_url"] = invite_clean or None
        await storage.promote_channels.update(id=promote_data.get("id"), saved_messages=saved)
        await ctx.send(f"บันทึกรายการ #{template_id} แล้ว")

    @promote_command.command(name="saved_send", with_app_command=True, help="ส่งโปรโมตจากรายการที่บันทึกไว้")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    async def promote_saved_send_command(self, ctx: commands.Context, template_id: int):
        if not await checks.check_is_moderator_permissions(ctx, "administrator"):
            return
        promote_data = await storage.promote_channels.get(guild_id=ctx.guild.id)
        if not promote_data:
            await ctx.send("ยังไม่ได้ตั้งค่าระบบโปรโมต")
            return
        saved = self._promote_saved_messages(promote_data)
        target = None
        for row in saved:
            if int(row.get("id") or 0) == int(template_id):
                target = row
                break
        if not target:
            await ctx.send("ไม่พบรายการบันทึกที่ต้องการส่ง")
            return

        cooldown_seconds = int(promote_data.get("cooldown_seconds") or PROMOTE_COOLDOWN_SECONDS)
        cooldowns = dict(promote_data.get("cooldowns") or {})
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        user_key = str(ctx.author.id)
        last_post = int(cooldowns.get(user_key, 0) or 0)
        if now_ts - last_post < cooldown_seconds:
            retry_at = now_ts + (cooldown_seconds - (now_ts - last_post))
            await ctx.send(i18n.tr("promote_retry_after", ctx.guild.id, retry=f"<t:{retry_at}:R>"))
            return

        message_cog = self.bot.get_cog("message")
        if not message_cog or not hasattr(message_cog, "promote_queue"):
            await ctx.send("ระบบคิวโปรโมตยังไม่พร้อมใช้งาน")
            return

        invite_url = target.get("invite_url")
        if not invite_url:
            try:
                if ctx.guild.me and ctx.channel.permissions_for(ctx.guild.me).create_instant_invite:
                    invite = await ctx.channel.create_invite(
                        max_age=86400,
                        max_uses=0,
                        unique=False,
                        reason=f"Promote saved message requested by {ctx.author}",
                    )
                    invite_url = invite.url
            except Exception:
                invite_url = None

        cooldowns[user_key] = now_ts
        await storage.promote_channels.update(id=promote_data.get("id"), cooldowns=cooldowns)
        queued, queue_size, queue_status = await message_cog.enqueue_promote_job(
            {
                "guild_id": ctx.guild.id,
                "author_id": ctx.author.id,
                "author_mention": ctx.author.mention,
                "content": target.get("content") or "",
                "attachments": list(target.get("attachments") or [])[:5],
                "invite_url": invite_url,
            }
        )
        if not queued and queue_status == "duplicate":
            await ctx.send("มีโปรโมตลิงก์เดียวกันอยู่ในคิวแล้ว ระบบจะส่งเพียงครั้งเดียว")
            return
        await ctx.send(f"{self.bot.emoji.SUCCESS} ส่งโปรโมตจากบันทึกแล้ว (คิวที่ {queue_size})")
    
    @commands.hybrid_group(
        name="aichat",
        help="ตั้งค่าห้องแชทเอไอ",
        invoke_without_command=True,
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.guild)
    async def aichat_command(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "administrator"):
                return

            ai_data = cache.ai_chat_channels.get(str(ctx.guild.id), {})
            channel_id = ai_data.get("channel_id")
            channel_text = f"<#{channel_id}>" if channel_id else "Not set"

            embed = discord.Embed(
                title="ห้องแชต AI",
                description=(
                    f"`{self.bot.BotConfig.PREFIX}aichat setting <channel>`\n"
                    f"`{self.bot.BotConfig.PREFIX}aichat remove`\n\n"
                    f"Current channel: {channel_text}"
                ),
                color=color.random_color(),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in aichat command: {e}")
            await ctx.send("An error occurred while processing the command.", delete_after=5)

    @aichat_command.command(name="setting", with_app_command=True, help="ตั้งค่าช่องแชทเอไอ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.guild)
    async def aichat_setting_command(self, ctx: commands.Context, channel: discord.TextChannel = None):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "administrator"):
                return

            target_channel = channel or ctx.channel

            ai_data = await storage.ai_chat_channels.get(guild_id=ctx.guild.id)
            if not ai_data:
                await storage.ai_chat_channels.insert(
                    guild_id=ctx.guild.id,
                    channel_id=target_channel.id,
                )
            else:
                await storage.ai_chat_channels.update(
                    id=ai_data.get("id"),
                    channel_id=target_channel.id,
                )

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.SUCCESS} AI chat room set to {target_channel.mention}",
                    color=color.green,
                )
            )
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in aichat setting command: {e}")
            await ctx.send("An error occurred while processing the command.", delete_after=5)

    @aichat_command.command(name="remove", with_app_command=True, help="ลบการตั้งค่าห้องแชทเอไอ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.guild)
    async def aichat_remove_command(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "administrator"):
                return

            deleted = await storage.ai_chat_channels.delete(guild_id=ctx.guild.id)
            if not deleted:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ยังไม่ได้ตั้งค่าห้องแชต AI",
                        color=color.red,
                    ),
                    delete_after=10,
                )

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.SUCCESS} AI chat room setup removed.",
                    color=color.green,
                )
            )
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in aichat remove command: {e}")
            await ctx.send("An error occurred while processing the command.", delete_after=5)

    @commands.command(
        name="nickname",
        help="เปลี่ยนชื่อเล่นของสมาชิก",
        aliases=["nick"]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3,per=30,type=commands.BucketType.user)
    async def nickname_command(self,ctx:commands.Context,member:discord.Member,*,nickname:str=None):
        try:
            if not await checks.check_is_moderator_permissions(ctx, 'manage_nicknames'):
                return

            if not await checks.check_if_user_can_manage_this_member(ctx,member):
                return
            print (nickname)
            await member.edit(nick=nickname)
            await ctx.send(embed=discord.Embed(description=f"{member.mention}'s nickname has been changed to {nickname}",color=color.green))
        except Exception as e:
            logger.error(f"ข้อผิดพลาด in nickname command: {e}")
            await ctx.send("An error occurred while processing the command.",delete_after=5)
        






