import datetime,asyncio,discord
from discord.ext import commands

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks

from skylinebot.memory.cache import cache


from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot


class on_guild_channel_update(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot

    async def _resolve_channel_update_entry(
        self,
        channel: discord.abc.GuildChannel,
        *,
        retries: int = 3,
        per_try_limit: int = 8,
        max_age_seconds: int = 25,
    ):
        guild = getattr(channel, "guild", None)
        if not guild:
            return None
        for attempt in range(max(1, int(retries))):
            try:
                now = datetime.datetime.now(tz=datetime.timezone.utc)
                async for entry in guild.audit_logs(
                    limit=max(1, int(per_try_limit)),
                    action=discord.AuditLogAction.channel_update,
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
                await asyncio.sleep(0.4)
        return None

    async def _resolve_actor_member(
        self,
        guild: discord.Guild,
        actor: discord.abc.User | discord.Member | None,
    ) -> discord.Member | None:
        if guild is None or actor is None:
            return None
        if isinstance(actor, discord.Member):
            return actor
        actor_id = int(getattr(actor, "id", 0) or 0)
        if actor_id <= 0:
            return None
        member = guild.get_member(actor_id)
        if member:
            return member
        try:
            return await guild.fetch_member(actor_id)
        except Exception:
            return None

    async def channel_update_log(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        try:
            guilds_log_cache = cache.guilds_log.get(str(after.guild.id))
            if not guilds_log_cache:
                return 
            if not guilds_log_cache.get('enabled'):
                return
            channel_id = guilds_log_cache.get('channel_update_channel_id')
            if not channel_id:
                return

            entry = await self._resolve_channel_update_entry(after)
            if entry:
                user = entry.user.mention
                user_id = entry.user.id
                reason = entry.reason
            else:
                user = "Unknown"
                user_id = "Unknown"
                reason = "Unknown"

            category_details = ""
            if after.category:
                category_details = (
                    f"\n**__Channel Category:__** {after.category.mention}"
                    f"\n**__Channel Category ID:__** `{after.category.id}`"
                )
            separator = "-" * 50
            embed = discord.Embed(
                title=f'#{after.name} has been updated',
                description=(
                    f"**__ห้อง:__** {after.mention}\n"
                    f"**__Channel Name:__** `#{after.name}`\n"
                    f"**__Channel ID:__** `{after.id}`\n"
                    f"**__Channel Type:__** {after.type}"
                    f"{category_details}\n"
                    f"**__Channel สร้าง:__** <t:{int(after.created_at.timestamp())}>\n\n"
                    f"**__Updated By:__** {user}\n"
                    f"**__Updated By ID:__** `{user_id}`\n"
                    f"**__Reason:__** `{reason}`\n\n"
                    f"**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>\n"
                    f"{separator}"
                ),
                color=color.white
            )
            if before.name != after.name:
                embed.add_field(name="ชื่อถูกเปลี่ยน",value=f"**Before:** {before.name}\n**After:** {after.name}")
            if isinstance(before, discord.TextChannel) and before.topic != after.topic:
                embed.add_field(name="หัวข้อถูกเปลี่ยน",value=f"**Before:** {before.topic}\n**After:** {after.topic}")
            if before.category != after.category:
                embed.add_field(name="หมวดหมู่ถูกเปลี่ยน",value=f"**Before:** {before.category.mention}\n**After:** {after.category.mention}")
            try:
                if before.slowmode_delay != after.slowmode_delay:
                    embed.add_field(name="โหมดหน่วงเวลาถูกเปลี่ยน",value=f"**Before:** {before.slowmode_delay}\n**After:** {after.slowmode_delay}")
            except Exception:
                pass
            if before.nsfw != after.nsfw:
                embed.add_field(name="สถานะ NSFW ถูกเปลี่ยน",value=f"**Before:** {before.nsfw}\n**After:** {after.nsfw}")
            if before.position != after.position:
                embed.add_field(name="ตำแหน่งถูกเปลี่ยน",value=f"**Before:** {before.position}\n**After:** {after.position}")
            if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
                embed.add_field(name="บิตเรตถูกเปลี่ยน",value=f"**Before:** {before.bitrate}\n**After:** {after.bitrate}")
            if isinstance(before, discord.VoiceChannel) and before.user_limit != after.user_limit:
                embed.add_field(name="ผู้ใช้ limit changed",value=f"**Before:** {before.user_limit}\n**After:** {after.user_limit}")
            if before.overwrites != after.overwrites:
                embed.add_field(name="สิทธิ์ทับซ้อนถูกเปลี่ยน",value=f"**Before:** {before.overwrites}\n**After:** {after.overwrites}")
            embed.set_footer(text=f'Channel ID: {after.id}')
            embed.set_thumbnail(url=after.guild.icon.url if after.guild.icon else None)
            await self.bot.log.send(guild=after.guild,embed=embed,type=f"channel_update")
        except Exception as e:
            logger.error(f"Error in on_guild_channel_update.channel_update_log: {e}")

    update_channel_timeouts = {}

    async def anti_channel_update_module(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        channel = after

        # check if the channel is a j2channel

        try:
            j2c_guild_cache = self.bot.cache.j2c.get(str(channel.guild.id), {}) or {}
            if isinstance(j2c_guild_cache, dict) and j2c_guild_cache.get(str(channel.id), None):
                return
        except Exception:
            pass

        
        try:
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(channel.guild.id))
            if not anti_nuke_cache:
                return 
            if not anti_nuke_cache.get('enabled'):
                return
            
            if not anti_nuke_cache.get('anti_channel_update'):
                return
            
            entry = await self._resolve_channel_update_entry(channel)

            if not entry:
                return

            actor = getattr(entry, "user", None)
            if actor is None:
                return
            if actor == self.bot.user:
                return
            if bool(getattr(actor, "bot", False)) or bool(getattr(actor, "system", False)):
                return logger.info(
                    f"Skip anti channel update for bot/system actor {actor} in {channel.guild.name}"
                )

            deletor = await self._resolve_actor_member(channel.guild, actor)
            if deletor is None:
                return logger.info(
                    f"Skip anti channel update: actor is not a guild member (likely integration/system) in {channel.guild.name}"
                )
            
            guild_bypass = self.bot.cache.antinuke_bypass.get(str(channel.guild.id), {}) or {}
            anti_nuke_bypass_cache = (
                guild_bypass.get(str(deletor.id), {}) if isinstance(guild_bypass, dict) else {}
            )
            if anti_nuke_bypass_cache.get('anti_channel_update'):
                return
            
            if deletor.top_role.position >= channel.guild.me.top_role.position:
                return
            if deletor == channel.guild.owner or await checks.check_is_owner_raw(deletor,channel.guild):
                return
            
            # =============================================

            if str(channel.guild.id) not in self.update_channel_timeouts:
                self.update_channel_timeouts[str(channel.guild.id)] = {}
            if str(deletor.id) not in self.update_channel_timeouts.get(str(channel.guild.id)):
                self.update_channel_timeouts[str(channel.guild.id)][str(deletor.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.update_channel_timeouts[str(channel.guild.id)][str(deletor.id)]['count'] += 1
            self.update_channel_timeouts[str(channel.guild.id)][str(deletor.id)]['created_at'] = datetime.datetime.now()


            if str(channel.guild.id) in self.update_channel_timeouts:
                if self.update_channel_timeouts.get(str(channel.guild.id)):
                    if self.update_channel_timeouts.get(str(channel.guild.id),{}).get(str(deletor.id)):
                        if (self.update_channel_timeouts.get(str(channel.guild.id),{}).get(str(deletor.id),{}).get('count') >= anti_nuke_cache.get('anti_channel_update_limit',1)
                            and
                            self.update_channel_timeouts.get(str(channel.guild.id),{}).get(str(deletor.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_channel_update_punishment')

                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {channel.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__กิล:__ `{channel.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Channel Update\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
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
                                        description=f"**__ผู้ใช้__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Channel Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    await channel.guild.ban(deletor,reason="Banned by Antinuke System: Anti Channel Update")
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_update.anti_channel_update_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__กิล:__ `{channel.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Channel Update\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
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
                                        description=f"**__ผู้ใช้__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Channel Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    await channel.guild.kick(deletor,reason="Kicked by Antinuke System: Anti Channel Update")
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_update.anti_channel_update_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Warning",
                                        description=f"**__กิล:__ `{channel.guild.name}`**\n**Details:** ```\nระบบป้องกัน: Anti Channel Update\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
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
                                        description=f"**__ผู้ใช้__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Channel Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_update.anti_channel_update_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Restriction",
                                        description=f"**__กิล:__ `{channel.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Channel Update\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
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
                                        description=f"**__ผู้ใช้__**: {deletor.mention}\n**__ID__**: `{deletor.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Channel Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deletor.display_avatar.url)
                                    try:
                                        await deletor.edit(roles=[],reason="Muted by Antinuke System: Anti Channel Update")
                                    except Exception:
                                        pass
                                    await deletor.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Channel Update")
                                    await self.bot.antinuke_log.send(guild=channel.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_channel_update.anti_channel_update_module: {e}")
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {channel.guild.name}")

                            if action != 'warn':
                            # reset the timeout
                                if str(channel.guild.id) in self.update_channel_timeouts:
                                    if str(deletor.id) in self.update_channel_timeouts.get(str(channel.guild.id)):
                                        self.update_channel_timeouts[str(channel.guild.id)][str(deletor.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return

        except Exception as e:
            logger.error(f"Error in on_guild_channel_update.anti_channel_update_module: {e}")
                        
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        try:
            asyncio.create_task(self.anti_channel_update_module(before, after))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.channel_update_log(before, after))
        except Exception as e:
            pass





