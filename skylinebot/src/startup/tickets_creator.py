from skylinebot.memory.cache import cache
from skylinebot.console.logging import logger
from discord.ext import commands

import asyncio
from storage import tickets as tickets_db

from skylinebot.src.modules import ticket_panel

import traceback

resumed = False


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _safe_int(value) -> int:
    try:
        return int(value)
    except Exception:
        return 0


async def resume_ticket_creator(bot: commands.Bot):
    global resumed
    if resumed:
        return logger.info("ระบบ Ticket Creator ถูกกู้คืนแล้ว")

    resumed = True

    # Wait for the bot to be ready.
    while not bot.is_ready():
        await asyncio.sleep(1)

    async def create_ticket_message(data, bot_obj):
        try:
            await ticket_panel.send_ticket_panel_message(data, bot_obj)
            return True
        except Exception:
            logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
            return False

    skipped_disabled = 0
    skipped_unconfigured = 0
    skipped_missing_guild = 0
    resumed_modules = 0
    failed_modules = 0

    async def create_ticket_message_guild(guild_id, ticket_modules):
        nonlocal skipped_disabled
        nonlocal skipped_unconfigured
        nonlocal skipped_missing_guild
        nonlocal resumed_modules
        nonlocal failed_modules
        try:
            guild = bot.get_guild(int(guild_id))
            if not guild:
                skipped_missing_guild += len(ticket_modules)
                return

            modules_to_resume = []
            for _, data in ticket_modules.items():
                if not isinstance(data, dict):
                    skipped_unconfigured += 1
                    continue
                if not _truthy(data.get("enabled")):
                    skipped_disabled += 1
                    continue

                panel_channel_id = _safe_int(data.get("ticket_panel_channel_id"))
                if panel_channel_id <= 0:
                    skipped_unconfigured += 1
                    continue
                if guild.get_channel(panel_channel_id) is None:
                    skipped_unconfigured += 1
                    continue

                modules_to_resume.append(data)

            if not modules_to_resume:
                return

            logger.info(
                f"Resuming Ticket Creator for guild {guild_id} ({guild.name}) "
                f"active_modules={len(modules_to_resume)}"
            )

            results = await asyncio.gather(
                *(create_ticket_message(data, bot) for data in modules_to_resume),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, Exception):
                    failed_modules += 1
                elif bool(result):
                    resumed_modules += 1
                else:
                    failed_modules += 1
        except Exception as error:
            logger.error(f"Error while resuming ticket modules for guild {guild_id}: {error}")

    total_guilds = len(cache.ticket_settings)
    total_modules = sum(
        len(ticket_modules)
        for ticket_modules in cache.ticket_settings.values()
        if isinstance(ticket_modules, dict)
    )
    logger.info(f"Ticket Creator cache scan: guilds={total_guilds}, modules={total_modules}")

    tasks = []
    for guild_id, ticket_modules in cache.ticket_settings.items():
        try:
            if not isinstance(ticket_modules, dict) or not ticket_modules:
                continue
            tasks.append(asyncio.create_task(create_ticket_message_guild(guild_id, ticket_modules)))
        except Exception as error:
            logger.error(f"Failed to create task for guild {guild_id}: {error}")

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(
        "Ticket Creator resume summary: "
        f"resumed_modules={resumed_modules}, "
        f"failed_modules={failed_modules}, "
        f"skipped_disabled={skipped_disabled}, "
        f"skipped_unconfigured={skipped_unconfigured}, "
        f"skipped_missing_guild={skipped_missing_guild}"
    )


ticket_closed_resumed = False


async def resume_ticket_closer(bot: commands.Bot):
    global ticket_closed_resumed
    if ticket_closed_resumed:
        return logger.info("ระบบ Ticket Closer ถูกกู้คืนแล้ว")

    ticket_closed_resumed = True

    # Wait for the bot to be ready.
    while not bot.is_ready():
        await asyncio.sleep(1)

    async def close_ticket(data, bot_obj):
        try:
            await ticket_panel.send_close_ticket_module(data, bot_obj)
            logger.info(f"Resumed Ticket Closer for {data.get('guild_id')} - Module {data.get('ticket_module_id')}")
        except Exception:
            logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

    for ticket in await tickets_db.gets(closed=False):
        try:
            asyncio.create_task(close_ticket(ticket, bot))
        except Exception as error:
            logger.error(f"Failed to create task for ticket module {ticket.get('id')}: {error}")

    logger.info("กู้คืน Ticket Closer ครบทุกกิลด์แล้ว")
