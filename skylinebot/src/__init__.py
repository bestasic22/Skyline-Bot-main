import asyncio
import importlib

from skylinebot.bridge import lavalink
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.startup import tickets_creator
from skylinebot.workflows.startup import (
    check_guilds_subscription,
    check_users_subscription,
    resume_afk_functions,
)
from skylinebot.workflows.billing import run_billing_scheduler

from .commands.automod import Automod
from .commands.alerts import Alerts
from .commands.activity import Activity
from .commands.birthday import Birthday
from .commands.economy import Economy
from .commands.fun import Fun
from .commands.giveaway import Giveaway
from .commands.help import Help
from .commands.context_apps import ContextApps
from .commands.translator import Translator
from .commands.guildstyle import GuildStyler
from .commands.levels import Levels
from .commands.moderation import Moderation
from .commands.more import More
from .commands.music import Music
from .commands.nsfw import NSFW
from .commands.personal_notes import PersonalNotes
from .commands.personal_reminders import PersonalReminders
from .commands.poll import Poll
from .commands.root import Root
from .commands.security import Security
from .commands.shop import Shop
from .commands.ticket import Ticket
from .commands.utils import Utils
from .commands.voice import Voice
from .commands.welcomer import Welcomer
from .commands.roleplay import Roleplay
from .commands.enterprise_ops import EnterpriseOps
from .modules.image_ocr import ImageOCR
from .modules.server_stats import ServerStats
from .modules.donate import Donate
from .modules.verify import Verify
from .modules.voice_randomizer import VoiceRandomizer
from .modules.color_roles import ColorRoles
from .modules.reaction_roles import ReactionRoles
from .modules.starboard import Starboard
from .modules.photoroom import PhotoRoom
from .events.message import message
from .events.on_command import on_command
from .events.on_command_error import on_command_error
from .events.on_guild_channel_create import on_guild_channel_create
from .events.on_guild_channel_delete import on_guild_channel_delete
from .events.on_guild_channel_update import on_guild_channel_update
from .events.on_guild_emojis_update import on_guild_emojis_update
from .events.on_guild_join import on_guild_join
from .events.on_guild_remove import on_guild_remove
from .events.on_guild_role_create import on_guild_role_create
from .events.on_guild_role_delete import on_guild_role_delete
from .events.on_guild_role_update import on_guild_role_update
from .events.on_guild_update import on_guild_update
from .events.on_invite_create import on_invite_create
from .events.on_invite_delete import on_invite_delete
from .events.on_member_join import on_member_join
from .events.on_member_remove import on_member_remove
from .events.on_member_unban import on_member_unban
from .events.on_member_update import on_member_update
from .events.on_message_delete import on_message_delete
from .events.on_message_edit import on_message_edit
from .events.on_voice_state_update import on_voice_state_update
from .events.on_webhooks_update import on_webhooks_update
from .events.ready import ready
from .events.wavelink import Wavelink


async def setup(bot: AutoShardedBot):
    units_to_mount = [
        Utils(bot=bot),
        Security(bot=bot),
        EnterpriseOps(bot=bot),
        Automod(bot=bot),
        Alerts(bot=bot),
        Activity(bot=bot),
        Birthday(bot=bot),
        GuildStyler(bot=bot),
        Poll(bot=bot),
        Moderation(bot=bot),
        Ticket(bot=bot),
        Welcomer(bot=bot),
        Music(bot=bot),
        NSFW(bot=bot),
        PersonalNotes(bot=bot),
        PersonalReminders(bot=bot),
        Giveaway(bot=bot),
        Economy(bot=bot),
        Shop(bot=bot),
        Roleplay(bot=bot),
        Levels(bot=bot),
        Help(bot=bot),
        ContextApps(bot=bot),
        Translator(bot=bot),
        Fun(bot=bot),
        Voice(bot=bot),
        More(bot=bot),
        Root(bot=bot),
        on_command(bot=bot),
        Wavelink(bot=bot),
        message(bot=bot),
        on_guild_join(bot=bot),
        on_guild_remove(bot=bot),
        on_member_join(bot=bot),
        on_member_remove(bot=bot),
        ready(bot=bot),
        on_command_error(bot=bot),
        on_member_unban(bot=bot),
        on_member_update(bot=bot),
        on_message_delete(bot=bot),
        on_message_edit(bot=bot),
        on_guild_channel_create(bot=bot),
        on_guild_channel_delete(bot=bot),
        on_guild_channel_update(bot=bot),
        on_guild_role_create(bot=bot),
        on_guild_role_delete(bot=bot),
        on_guild_role_update(bot=bot),
        on_guild_emojis_update(bot=bot),
        on_voice_state_update(bot=bot),
        on_webhooks_update(bot=bot),
        on_invite_create(bot=bot),
        on_invite_delete(bot=bot),
        on_guild_update(bot=bot),
        ImageOCR(bot=bot),
        ServerStats(bot=bot),
        Donate(bot=bot),
        Verify(bot=bot),
        VoiceRandomizer(bot=bot),
        ColorRoles(bot=bot),
        Starboard(bot=bot),
        ReactionRoles(bot=bot),
        PhotoRoom(bot=bot),
    ]

    await asyncio.gather(*[bot.add_cog(unit) for unit in units_to_mount])
    logger.cog(f"โหลดหน่วยคำสั่งและอีเวนต์สำเร็จ {len(units_to_mount)} รายการ")
    overflowed = list(getattr(bot, "_slash_overflow_commands", []) or [])
    if overflowed:
        logger.warning(
            "เปิดโหมดสำรอง Slash อัตโนมัติ: "
            f"มี {len(overflowed)} คำสั่งที่ใช้งานได้เฉพาะ prefix เนื่องจากชนลิมิต Slash รวมของ Discord"
        )
    filtered = list(getattr(bot, "_slash_filtered_commands", []) or [])
    if filtered:
        logger.info(
            "เปิดโหมดคัดกรอง Slash แบบสำคัญ: "
            f"คงไว้ {len(filtered)} คำสั่งเป็นแบบ prefix/context เท่านั้น"
        )
    if bool(getattr(bot, "_slash_group_only_mode", False)):
        logger.info(
            "เปิดโหมด Slash แบบกลุ่มเท่านั้น: "
            "คำสั่งเดี่ยวระดับบนสุดจะไม่แสดงในหน้า Slash"
        )
    slash_profiles = list(getattr(bot, "_slash_profiles_active", []) or [])
    if slash_profiles:
        logger.info(
            "เปิดใช้งานโปรไฟล์คำสั่ง Slash: "
            + ", ".join(slash_profiles)
        )
    unknown_profiles = list(getattr(bot, "_slash_profiles_unknown", []) or [])
    if unknown_profiles:
        logger.warning(
            "พบชื่อโปรไฟล์ Slash ที่ไม่รู้จัก ระบบข้ามโปรไฟล์เหล่านี้: "
            + ", ".join(unknown_profiles)
        )

    try:
        importlib.reload(lavalink)
        asyncio.create_task(lavalink.on_node(bot))
    except Exception:
        pass

    try:
        asyncio.create_task(check_guilds_subscription(bot))
    except Exception:
        pass

    try:
        asyncio.create_task(check_users_subscription(bot))
    except Exception:
        pass

    try:
        asyncio.create_task(run_billing_scheduler(bot))
    except Exception:
        pass

    try:
        asyncio.create_task(resume_afk_functions(bot))
    except Exception:
        pass

    try:
        asyncio.create_task(tickets_creator.resume_ticket_creator(bot))
    except Exception:
        pass
    logger.cog("กู้คืนระบบสร้างทิกเก็ตอัตโนมัติแล้ว")

    try:
        asyncio.create_task(tickets_creator.resume_ticket_closer(bot))
    except Exception:
        pass
    logger.cog("กู้คืนระบบปิดทิกเก็ตอัตโนมัติแล้ว")
    logger.success("SkylineBOT พร้อมทำงานแล้ว")
