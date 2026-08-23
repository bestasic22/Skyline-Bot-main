import datetime,asyncio,discord
from discord.ext import commands

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks

from skylinebot.memory.cache import cache


from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot

class on_guild_role_update(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot

    async def role_update_log(self,before:discord.Role,after:discord.Role):
        try:
            guilds_log_cache = cache.guilds_log.get(str(after.guild.id))
            if not guilds_log_cache:
                return
            if not guilds_log_cache.get('enabled'):
                return logger.debug(f"กิล {after.guild.name} has logging disabled")
            channel_id = guilds_log_cache.get('role_update_channel_id')
            if not channel_id:
                return logger.debug(f"Channel ID not found for role update log in {after.guild.name}")
            
            async def check_entry():
                async for entry in after.guild.audit_logs(limit=1,action=discord.AuditLogAction.role_update):
                    if entry.target.id == after.id:
                        return entry
            entry = await check_entry()
            if entry:
                user = entry.user.mention
                user_id = entry.user.id
                reason = entry.reason
            else:
                user = "Unknown"
                user_id = "Unknown"
                reason = "Unknown"
            
            separator = "-" * 50
            embed = discord.Embed(
                title=f'Role {after.name} has been updated',
                description=(
                    f"**__Role:__** {after.mention}\n"
                    f"**__Role Name:__** {after.name}\n"
                    f"**__Role ID:__** `{after.id}`\n"
                    f"**__Bot Role:__** {after.is_bot_managed()}\n"
                    f"**__Role สร้าง:__** <t:{int(after.created_at.timestamp())}>\n\n"
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
            if before.colour != after.colour:
                embed.add_field(name="สีถูกเปลี่ยน",value=f"**Before:** {before.colour}\n**After:** {after.colour}")
            if before.hoist != after.hoist:
                embed.add_field(name="การแสดงแยกยศถูกเปลี่ยน",value=f"**Before:** {before.hoist}\n**After:** {after.hoist}")
            if before.mentionable != after.mentionable:
                embed.add_field(name="สถานะแท็กได้ถูกเปลี่ยน",value=f"**Before:** {before.mentionable}\n**After:** {after.mentionable}")
            if before.permissions != after.permissions:
                removed, added = [], []
                before_perms = [perm for perm in before.permissions]
                after_perms = [perm for perm in after.permissions]
                after_dict = dict(after_perms)
                for perm, before_value in before_perms:
                    after_value = after_dict.get(perm, None)
                    if after_value is not None:
                        if not before_value and after_value:
                            added.append(perm.replace('_', ' ').capitalize())
                        elif before_value and not after_value:
                            removed.append(perm.replace('_', ' ').capitalize())
                joined_removed = ', '.join(removed)
                joined_added = ', '.join(added)
                permissions_text = ""
                if removed:
                    permissions_text += f"**Removed:** `{joined_removed}`\n"
                if added:
                    permissions_text += f"**Added:** `{joined_added}`"
                embed.add_field(name="สิทธิ์ถูกเปลี่ยน",value=permissions_text)
            if before.position != after.position:
                embed.add_field(name="ตำแหน่งถูกเปลี่ยน",value=f"**Before:** {before.position}\n**After:** {after.position}")
            embed.set_footer(text=f'Role ID: {after.id}')
            embed.set_thumbnail(url=after.guild.icon.url if after.guild.icon else None)
            await self.bot.log.send(guild=after.guild,embed=embed,type=f"role_update")
        except Exception as e:
            logger.error(f"Error in on_guild_role_update.role_update_log: {e}")
    update_role_timeouts = {}
    async def update_role_module(self,before:discord.Role,after:discord.Role):
        try:
            managed_role = bool(getattr(after, "managed", False))
            try:
                managed_role = managed_role or bool(after.is_bot_managed()) or bool(after.is_integration())
            except Exception:
                pass
            if managed_role:
                return logger.debug(f"Skip anti role update for managed/integration role {after.name}")
            
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(before.guild.id))
            if not anti_nuke_cache:
                return 
            if not anti_nuke_cache.get('enabled'):
                return
            if not anti_nuke_cache.get('anti_role_update'):
                return
            
            async def check_entry():
                async for entry in before.guild.audit_logs(limit=1,action=discord.AuditLogAction.role_update,after=datetime.datetime.now()-datetime.timedelta(seconds=5)):
                    if entry.target.id == after.id:
                        return entry
            entry = await check_entry()
            if entry:
                updater = entry.user
                if updater == self.bot.user:
                    return
            else:
                return logger.debug(f"Role {after.name} update audit entry not found (likely system/integration)")
            
            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(str(before.guild.id),{}).get(str(updater.id),{})
            if anti_nuke_bypass_cache.get('anti_role_update'):
                return logger.warning(f"ผู้ใช้ {updater} is bypassed from anti role update")
            
            if updater.id == before.guild.owner.id or await checks.check_is_owner_raw(updater,after.guild):
                return logger.warning(f"Role {after.name} was updated by the owner")
            if updater.top_role.position >= before.guild.me.top_role.position:
                return logger.warning(f"Role {after.name} was updated by a user with a higher role than the bot")
            
            # ==================================
            if str(before.guild.id) not in self.update_role_timeouts:
                self.update_role_timeouts[str(before.guild.id)] = {}
            if str(updater.id) not in self.update_role_timeouts.get(str(before.guild.id)):
                self.update_role_timeouts[str(before.guild.id)][str(updater.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.update_role_timeouts[str(before.guild.id)][str(updater.id)]['count'] += 1
            self.update_role_timeouts[str(before.guild.id)][str(updater.id)]['created_at'] = datetime.datetime.now()


            if str(before.guild.id) in self.update_role_timeouts:
                if self.update_role_timeouts.get(str(before.guild.id)):
                    if self.update_role_timeouts.get(str(before.guild.id),{}).get(str(updater.id)):
                        if (self.update_role_timeouts.get(str(before.guild.id),{}).get(str(updater.id),{}).get('count') >= anti_nuke_cache.get('anti_role_update_limit',1)
                            and
                            self.update_role_timeouts.get(str(before.guild.id),{}).get(str(updater.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_role_update_punishment')
                            
                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {before.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__กิล:__ `{before.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Role Update\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=before.guild.icon.url if before.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(updater,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__ผู้ใช้__**: {updater.mention}\n**__ID__**: `{updater.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Role Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=updater.display_avatar.url)
                                    await before.guild.ban(updater,reason="Banned by Antinuke System: Anti Role Update")
                                    await self.bot.antinuke_log.send(guild=before.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_role_update.update_role_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__กิล:__ `{before.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Role Update\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=before.guild.icon.url if before.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(updater,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__ผู้ใช้__**: {updater.mention}\n**__ID__**: `{updater.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Role Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=updater.display_avatar.url)
                                    await before.guild.kick(updater,reason="Kicked by Antinuke System: Anti Role Update")
                                    await self.bot.antinuke_log.send(guild=before.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_role_update.update_role_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Warning",
                                        description=f"**__กิล:__ `{before.guild.name}`**\n**Details:** ```\nระบบป้องกัน: Anti Role Update\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=before.guild.icon.url if before.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(updater,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Warning",
                                        description=f"**__ผู้ใช้__**: {updater.mention}\n**__ID__**: `{updater.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Role Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=updater.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=before.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_role_update.update_role_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Restriction",
                                        description=f"**__กิล:__ `{before.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Role Update\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=before.guild.icon.url if before.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(updater,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Restriction",
                                        description=f"**__ผู้ใช้__**: {updater.mention}\n**__ID__**: `{updater.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Role Update\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=updater.display_avatar.url)
                                    try:
                                        await updater.edit(roles=[],reason="Muted by Antinuke System: Anti Role Update")
                                    except Exception:
                                        pass
                                    await updater.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Role Update")
                                    await self.bot.antinuke_log.send(guild=before.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_role_update.update_role_module: {e}")
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {before.guild.name}")
                            
                            if action != 'warn':
                            # reset the timeout
                                if str(before.guild.id) in self.update_role_timeouts:
                                    if str(updater.id) in self.update_role_timeouts.get(str(before.guild.id)):
                                        self.update_role_timeouts[str(before.guild.id)][str(updater.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return
                        


        except Exception as e:
            logger.error(f"Error in on_guild_role_update.update_role_module: {e}")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        try:
            asyncio.create_task(self.update_role_module(before,after))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.role_update_log(before,after))
        except Exception as e:
            pass




