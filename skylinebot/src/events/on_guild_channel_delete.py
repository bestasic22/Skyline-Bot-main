import datetime,asyncio,discord
from discord.ext import commands

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks

from skylinebot.memory.cache import cache


from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot


class on_guild_channel_delete(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot

    async def _resolve_channel_delete_entry(
        self,
        channel: discord.abc.GuildChannel,
        *,
        retries: int = 4,
        per_try_limit: int = 8,
        max_age_seconds: int = 25,
    ):
        """Fetch the matching delete audit entry with small retries.

        Discord audit entries can arrive slightly after the gateway event,
        especially during bulk actions.
        """
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        for attempt in range(max(1, int(retries))):
            try:
                now = datetime.datetime.now(tz=datetime.timezone.utc)
                async for entry in guild.audit_logs(
                    limit=max(1, int(per_try_limit)),
                    action=discord.AuditLogAction.channel_delete,
                ):
                    target = getattr(entry, "target", None)
                    if not target or int(getattr(target, "id", 0) or 0) != int(channel.id):
                        continue
                    created_at = getattr(entry, "created_at", None)
                    if isinstance(created_at, datetime.datetime):
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                        if (now - created_at).total_seconds() > max_age_seconds:
                            continue
                    return entry
            except Exception:
                return None
            if attempt < retries - 1:
                await asyncio.sleep(0.45)
        return None

    async def channel_delete_log(self,channel:discord.abc.GuildChannel):
        try:
            guilds_log_cache = cache.guilds_log.get(str(channel.guild.id))
            if not guilds_log_cache:
                return 
            if not guilds_log_cache.get('enabled'):
                return
            channel_id = guilds_log_cache.get('channel_delete_channel_id')
            if not channel_id:
                return

            entry = await self._resolve_channel_delete_entry(channel)
            if entry:
                user = entry.user.mention
                user_id = entry.user.id
                reason = entry.reason
            else:
                user = "Unknown"
                user_id = "Unknown"
                reason = "Unknown"
            
            category_details = ""
            if channel.category:
                category_details = (
                    f"\n**__Channel Category:__** {channel.category.mention}"
                    f"\n**__Channel Category ID:__** `{channel.category.id}`"
                )
            embed = discord.Embed(
                title=f'#{channel.name} has been deleted',
                description=(
                    f"**__Channel:__** {channel.mention}\n"
                    f"**__Channel Name:__** `#{channel.name}`\n"
                    f"**__Channel ID:__** `{channel.id}`\n"
                    f"**__Channel Type:__** {channel.type}"
                    f"{category_details}\n"
                    f"**__Channel Created At:__** <t:{int(channel.created_at.timestamp())}>\n\n"
                    f"**__Deleted By:__** {user}\n"
                    f"**__Deleted By ID:__** {user_id}\n"
                    f"**__Reason:__** `{reason}`\n\n"
                    f"**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>"
                ),
                color=color.red
            )
            embed.set_footer(text=f'Channel ID: {channel.id}')
            embed.set_thumbnail(url=channel.guild.icon.url if channel.guild.icon else None)
            await self.bot.log.send(guild=channel.guild,embed=embed,type=f"channel_delete")
        except Exception as e:
            logger.error(f"Error in on_guild_channel_delete.channel_delete_log: {e}")
    
    delete_channel_timeouts = {}

    async def anti_channel_delete_module(self,channel:discord.abc.GuildChannel):
        
        try:
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(channel.guild.id))
            if not anti_nuke_cache:
                return 
            if not anti_nuke_cache.get('enabled'):
                return
            
            if not anti_nuke_cache.get('anti_channel_delete'):
                return

            entry = await self._resolve_channel_delete_entry(channel)

            if entry:
                deletor = entry.user
                if deletor == self.bot.user:
                    return
            else:
                # Unknown actor in audit log (race/permission) -> skip punitive flow to avoid false positives.
                return
            
            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(str(channel.guild.id),{}).get(str(deletor.id),{})
            if anti_nuke_bypass_cache.get('anti_channel_delete'):
                return
            
            if deletor.top_role.position >= channel.guild.me.top_role.position:
                return
            if deletor == channel.guild.owner or await checks.check_is_owner_raw(deletor,channel.guild):
                return
            
            # ===========================
            if str(channel.guild.id) not in self.delete_channel_timeouts:
                self.delete_channel_timeouts[str(channel.guild.id)] = {}
            if str(deletor.id) not in self.delete_channel_timeouts.get(str(channel.guild.id)):
                self.delete_channel_timeouts[str(channel.guild.id)][str(deletor.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.delete_channel_timeouts[str(channel.guild.id)][str(deletor.id)]['count'] += 1
            self.delete_channel_timeouts[str(channel.guild.id)][str(deletor.id)]['created_at'] = datetime.datetime.now()

            if str(channel.guild.id) in self.delete_channel_timeouts:
                if self.delete_channel_timeouts.get(str(channel.guild.id)):
                    if self.delete_channel_timeouts.get(str(channel.guild.id),{}).get(str(deletor.id)):
                        if (self.delete_channel_timeouts.get(str(channel.guild.id),{}).get(str(deletor.id),{}).get('count') >= anti_nuke_cache.get('anti_channel_delete_limit',1)
                            and
                            self.delete_channel_timeouts.get(str(channel.guild.id),{}).get(str(deletor.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_channel_delete_punishment')

                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {channel.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Channel Delete\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=channel.guild.icon.url if channel.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deletor,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__User__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Channel Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    await channel.guild.ban(deletor,reason="Banned by Antinuke System: Anti Channel Delete")
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_delete.anti_channel_delete_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Channel Delete\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=channel.guild.icon.url if channel.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deletor,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__User__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Channel Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    await channel.guild.kick(deletor,reason="Kicked by Antinuke System: Anti Channel Delete")
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_delete.anti_channel_delete_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Warning",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Channel Delete\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=channel.guild.icon.url if channel.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deletor,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Warning",
                                        description=f"**__User__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Channel Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_delete.anti_channel_delete_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Restriction",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Channel Delete\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=channel.guild.icon.url if channel.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deletor,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Restriction",
                                        description=f"**__User__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Channel Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    try:
                                        await deletor.edit(roles=[],reason="Muted by Antinuke System: Anti Channel Delete")
                                    except Exception:
                                        pass
                                    await deletor.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Channel Delete")
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_delete.anti_channel_delete_module: {e}")
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {channel.guild.name}")

                            if action != 'warn':
                            # reset the timeout
                                if str(channel.guild.id) in self.delete_channel_timeouts:
                                    if str(deletor.id) in self.delete_channel_timeouts.get(str(channel.guild.id)):
                                        self.delete_channel_timeouts[str(channel.guild.id)][str(deletor.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return


        except Exception as e:
            logger.error(f"Error in on_guild_channel_delete.anti_channel_delete_module: {e}")
                        





    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        try:
            asyncio.create_task(self.anti_channel_delete_module(channel))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.channel_delete_log(channel))
        except Exception as e:
            pass




