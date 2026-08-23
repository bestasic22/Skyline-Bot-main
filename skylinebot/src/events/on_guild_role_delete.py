import datetime,asyncio,discord
from discord.ext import commands

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks

from skylinebot.memory.cache import cache

import traceback,sys
from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot

class on_guild_role_delete(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot

    async def role_delete_log(self,role:discord.Role):
        try:
            guilds_log_cache = cache.guilds_log.get(str(role.guild.id))
            if not guilds_log_cache:
                return 
            if not guilds_log_cache.get('enabled'):
                return logger.debug(f"Guild {role.guild.name} has logging disabled")
            channel_id = guilds_log_cache.get('role_delete_channel_id')
            if not channel_id:
                return logger.debug(f"Channel ID not found for role delete log in {role.guild.name}")
            
            async def check_entry():
                async for entry in role.guild.audit_logs(limit=1,action=discord.AuditLogAction.role_delete):
                    if entry.target.id == role.id:
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
            
            embed = discord.Embed(
                title=f'Role {role.name} has been deleted',
                description=f'**__Role:__** {role.mention}\n**__Role Name:__** {role.name}\n**__Role ID:__** `{role.id}`\n**__Role Created At:__** <t:{int(role.created_at.timestamp())}>\n\n**__Deleted By:__** {user}\n**__Deleted By ID:__** `{user_id}`\n**__Reason:__** `{reason}`\n\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>',
                color=color.red
            )
            embed.set_footer(text=f'Role ID: {role.id}')
            embed.set_thumbnail(url=role.guild.icon.url if role.guild.icon else None)
            await self.bot.log.send(guild=role.guild,embed=embed,type=f"role_delete")
        except Exception as e:
            logger.error(f"Error in on_guild_role_delete.role_delete_log: {e}")

    delete_role_timeouts = {}

    async def anti_role_delete_module(self,role:discord.Role):
        try:
            managed_role = bool(getattr(role, "managed", False))
            try:
                managed_role = managed_role or bool(role.is_bot_managed()) or bool(role.is_integration())
            except Exception:
                pass
            if managed_role:
                return logger.info(f"Skip anti role delete for managed/integration role {role.name}")
            
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(role.guild.id))
            if not anti_nuke_cache:
                return 
            if not anti_nuke_cache.get('enabled'):
                return
            if not anti_nuke_cache.get('anti_role_delete'):
                return logger.warning(f"Guild {role.guild.name} has anti role delete disabled")
            
            async def check_entry():
                async for entry in role.guild.audit_logs(limit=1,action=discord.AuditLogAction.role_delete,after=datetime.datetime.now()-datetime.timedelta(seconds=5)):
                    if entry.target.id == role.id:
                        return entry
            entry = await check_entry()
            if entry:
                deleter = entry.user
                if deleter == self.bot.user:
                    return logger.warning(f"Role {role.name} was deleted by the bot")
            else:
                return logger.info(f"Role {role.name} delete audit entry not found (likely system/integration)")
            
            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(str(role.guild.id),{}).get(str(deleter.id),{})
            if anti_nuke_bypass_cache.get('anti_role_delete'):
                return logger.warning(f"User {deleter} is bypassed from anti role delete")
            
            if deleter.id == role.guild.owner.id or await checks.check_is_owner_raw(deleter,role.guild):
                return logger.warning(f"Role {role.name} was deleted by the owner")
            if deleter.top_role.position >= role.guild.me.top_role.position:
                return logger.warning(f"Role {role.name} was deleted by a user with a higher role than the bot")
            
            # ==================================
            if str(role.guild.id) not in self.delete_role_timeouts:
                self.delete_role_timeouts[str(role.guild.id)] = {}
            if str(deleter.id) not in self.delete_role_timeouts.get(str(role.guild.id)):
                self.delete_role_timeouts[str(role.guild.id)][str(deleter.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.delete_role_timeouts[str(role.guild.id)][str(deleter.id)]['count'] += 1
            self.delete_role_timeouts[str(role.guild.id)][str(deleter.id)]['created_at'] = datetime.datetime.now()


            if str(role.guild.id) in self.delete_role_timeouts:
                if self.delete_role_timeouts.get(str(role.guild.id)):
                    if self.delete_role_timeouts.get(str(role.guild.id),{}).get(str(deleter.id)):
                        if (self.delete_role_timeouts.get(str(role.guild.id),{}).get(str(deleter.id),{}).get('count') >= anti_nuke_cache.get('anti_role_delete_limit',1)
                            and
                            self.delete_role_timeouts.get(str(role.guild.id),{}).get(str(deleter.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_role_delete_punishment')

                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {role.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__Guild:__ `{role.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Role Delete\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=role.guild.icon.url if role.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deleter,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__User__**: {deleter.mention}\n**__ID__**: `{deleter.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Role Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deleter.display_avatar.url)
                                    await role.guild.ban(deleter,reason="Banned by Antinuke System: Anti Role Delete")
                                    await self.bot.antinuke_log.send(guild=role.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_role_delete.anti_role_delete_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__Guild:__ `{role.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Role Delete\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=role.guild.icon.url if role.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deleter,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Protection System",
                                        description=f"**__User__**: {deleter.mention}\n**__ID__**: `{deleter.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Role Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deleter.display_avatar.url)
                                    await role.guild.kick(deleter,reason="Kicked by Antinuke System: Anti Role Delete")
                                    await self.bot.antinuke_log.send(guild=role.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_role_delete.anti_role_delete_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Warning",
                                        description=f"**__Guild:__ `{role.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Role Delete\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=role.guild.icon.url if role.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deleter,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Warning",
                                        description=f"**__User__**: {deleter.mention}\n**__ID__**: `{deleter.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Role Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deleter.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=role.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_guild_role_delete.anti_role_delete_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Restriction",
                                        description=f"**__Guild:__ `{role.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Role Delete\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=role.guild.icon.url if role.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(deleter,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="Antinuke Restriction",
                                        description=f"**__User__**: {deleter.mention}\n**__ID__**: `{deleter.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Role Delete\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=deleter.display_avatar.url)
                                    try:
                                        await deleter.edit(roles=[],reason="Muted by Antinuke System: Anti Role Delete")
                                    except Exception:
                                        pass
                                    await deleter.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Role Delete")
                                    await self.bot.antinuke_log.send(guild=role.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {role.guild.name}")
                            
                            if action != 'warn':
                            # reset the timeout
                                if str(role.guild.id) in self.delete_role_timeouts:
                                    if str(deleter.id) in self.delete_role_timeouts.get(str(role.guild.id)):
                                        self.delete_role_timeouts[str(role.guild.id)][str(deleter.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return
                        


        except Exception as e:
            logger.error(f"Error in on_guild_role_delete.anti_role_delete_module: {e}")

    



    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        try:
            asyncio.create_task(self.anti_role_delete_module(role))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.role_delete_log(role))
        except Exception as e:
            pass


