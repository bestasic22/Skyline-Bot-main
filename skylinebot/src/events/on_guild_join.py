import asyncio
import traceback

import discord
import requests
from discord.ext import commands

from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.style import color
from skylinebot.surface import guild_growth


class on_guild_join(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot

    def _support_view(self) -> discord.ui.View:
        return discord.ui.View().add_item(
            discord.ui.Button(
                label="Support Hub",
                url=self.bot.urls.SUPPORT_SERVER,
                style=discord.ButtonStyle.link,
                emoji=self.bot.emoji.SUPPORT,
            )
        )

    async def send_join_server_notification(self, guild: discord.Guild):
        try:
            logger.info(f"Joined Guild {guild.name} ({guild.id})")

            if self.bot.cache.ban_data.get("guilds").get(str(guild.id)):
                owner = guild.owner
                if owner is not None:
                    try:
                        await owner.send(
                            embed=discord.Embed(
                                title=f"Your Guild {guild.name} is banned from using {self.bot.user.name}",
                                description=(
                                    "If you think this is a mistake, please join our Support Server "
                                    "and contact the Management Team"
                                ),
                                color=color.red,
                            ),
                            view=self._support_view(),
                        )
                    except discord.Forbidden:
                        logger.warning(
                            f"Could not DM owner of banned guild {guild.name} ({guild.id}); "
                            "DM blocked or no mutual guild"
                        )
                    except discord.HTTPException as exc:
                        logger.warning(f"Could not DM owner of banned guild {guild.name} ({guild.id}): {exc}")

                await guild.leave()
                logger.warning(f"Guild {guild.name} ({guild.id}) is banned from using {self.bot.user.name}")
                return

            await asyncio.sleep(5)

            inviter = None
            try:
                async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.bot_add):
                    if entry.target == self.bot.user:
                        inviter = entry.user
                        break
            except discord.Forbidden:
                logger.warning(
                    f"Missing permission to read audit logs in {guild.name} ({guild.id}); inviter will be Unknown"
                )
            except discord.HTTPException as exc:
                logger.warning(f"Failed to read audit logs in {guild.name} ({guild.id}): {exc}")

            owner = guild.owner
            owner_info = f"{owner.mention} ({owner.id})" if owner else "Unknown"
            inviter_info = f"{inviter.mention} ({inviter.id})" if inviter else "Unknown"

            embed = discord.Embed(
                title="Joined a New Server",
                description=(
                    f"> {self.bot.emoji.NAME} **Name:** {guild.name}\n"
                    f"> {self.bot.emoji.ID} **ID:** {guild.id}\n"
                    f"> {self.bot.emoji.MEMBER} **Members:** {guild.member_count}\n"
                    f"> {self.bot.emoji.OWNER} **Owner:** {owner_info}\n"
                    f"> {self.bot.emoji.INVITE} **Inviter:** {inviter_info}"
                ),
                color=color.green,
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.set_footer(text=f"Guild Count: {len(self.bot.guilds)}")

            webhook_url = self.bot.channels.guild_join_webhook
            if webhook_url:
                try:
                    requests.post(webhook_url, json={"embeds": [embed.to_dict()]}, timeout=10)
                except Exception as exc:
                    logger.warning(f"Failed to send guild join webhook for {guild.name} ({guild.id}): {exc}")
        except Exception:
            logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

    async def send_notify_to_server_owner(self, guild: discord.Guild):
        try:
            owner = guild.owner
            if owner is None:
                logger.warning(f"Guild owner not found for {guild.name} ({guild.id}); skip owner DM")
                return

            try:
                await owner.send(
                    embed=discord.Embed(
                        title="Thanks for Adding SkylineBOT",
                        description=(
                            f"Hello {owner.mention},\n\n"
                            f"Thank you for adding me to your server. I am {self.bot.user.name} "
                            "and I am here to help you manage your server.\n\n"
                            f"To get started, you can use the command `{self.bot.BotConfig.PREFIX}help` "
                            "to get a list of commands that I can do.\n\n"
                            "If you have any questions or need help, you can join our Support Server "
                            "by clicking the button below."
                        ),
                        color=color.green,
                    ),
                    view=self._support_view(),
                )
            except discord.Forbidden:
                logger.warning(
                    f"Could not DM server owner for {guild.name} ({guild.id}); "
                    "DM blocked or no mutual guild"
                )
            except discord.HTTPException as exc:
                logger.warning(f"Could not DM server owner for {guild.name} ({guild.id}): {exc}")
        except Exception:
            logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            asyncio.create_task(
                guild_growth.record_snapshot(len(getattr(self.bot, "guilds", []) or []), source="on_guild_join")
            )
        except Exception:
            pass

        try:
            asyncio.create_task(self.send_join_server_notification(guild))
        except Exception:
            pass

        try:
            asyncio.create_task(self.send_notify_to_server_owner(guild))
        except Exception:
            pass
