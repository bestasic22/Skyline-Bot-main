import datetime,asyncio,discord
from discord.ext import commands

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks

from skylinebot.memory.cache import cache

import traceback,sys

from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot
import requests
from skylinebot.surface import guild_growth

class on_guild_remove(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot

    @commands.Cog.listener()
    async def on_guild_remove(self, guild:discord.Guild):
        try:
            asyncio.create_task(
                guild_growth.record_snapshot(len(getattr(self.bot, "guilds", []) or []), source="on_guild_remove")
            )
        except Exception:
            pass
        try:
            logger.info(f"Left Guild {guild.name} ({guild.id})")
            webhook_url = self.bot.channels.guild_leave_webhook
            
            embed = discord.Embed(
                title="Removed from a Server",
                description=f"> {self.bot.emoji.NAME} **Name:** {guild.name}\n> {self.bot.emoji.ID} **ID:** {guild.id}\n> {self.bot.emoji.MEMBER} **Members:** {guild.member_count}\n> {self.bot.emoji.OWNER} **Owner:** {guild.owner.name if guild.owner else 'Unknown'}",
                color=color.red
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.set_footer(text=f"Guild Count: {len(self.bot.guilds)}")

            if webhook_url:
                requests.post(webhook_url,json={"embeds":[embed.to_dict()]})
        except Exception as e:
            logger.error(f"Error in file {__file__}: {traceback.format_exc()}")


