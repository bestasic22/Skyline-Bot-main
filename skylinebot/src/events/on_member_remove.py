import datetime,asyncio,discord
from discord.ext import commands
import io

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks
import traceback, sys

from skylinebot.memory.cache import cache
from skylinebot.src.checks.variables import fetch_variables


from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot
import skylinebot.src.modules.dashboard_activity as dashboard_activity
from skylinebot.workflows.notice_cards import build_member_notice_card


def _normalize_plan_tier(raw_plan):
    raw = str(raw_plan or "").strip().lower()
    mapping = {
        "free": "free",
        "silver": "silver",
        "silver_guild_preminum": "silver",
        "silver_guild_premium": "silver",
        "premium_silver": "silver",
        "golden": "golden",
        "gold": "golden",
        "golden_guild_premium": "golden",
        "diamond": "diamond",
        "diamond_guild_premium": "diamond",
        "permanent": "permanent",
        "lifetime": "permanent",
        "forever": "permanent",
        "permanent_guild_premium": "permanent",
        "lifetime_guild_premium": "permanent",
        "ultra": "diamond",
    }
    return mapping.get(raw, "free")


def _plan_at_least(raw_plan, required_tier):
    order = {"free": 0, "silver": 1, "golden": 2, "diamond": 3, "permanent": 4}
    current = order.get(_normalize_plan_tier(raw_plan), 0)
    required = order.get(_normalize_plan_tier(required_tier), 0)
    return current >= required


class on_member_remove(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot


    async def check_if_user_banned_or_kicked_module(self,member:discord.Member):
        try:
            guilds_log_cache = cache.guilds_log.get(str(member.guild.id))
            if not guilds_log_cache:
                return
            if not guilds_log_cache.get('enabled'):
                return logger.debug(f"Guild {member.guild.name} has logging disabled")
            async def check_for_entry():
                # check if the member was kicked under 1 minute
                async for entry in member.guild.audit_logs(limit=1,action=discord.AuditLogAction.ban,after=datetime.datetime.now()-datetime.timedelta(minutes=1)):
                    if entry.target.id == member.id:
                        return entry
                # check if the member was banned under 1 minute
                async for entry in member.guild.audit_logs(limit=1,action=discord.AuditLogAction.kick,after=datetime.datetime.now()-datetime.timedelta(minutes=1)):
                    if entry.target.id == member.id:
                        return entry
                return None
            
            entry = await check_for_entry()
            if entry:
                if entry.action == discord.AuditLogAction.ban:
                    action = 'ban'
                    try:
                        asyncio.create_task(self.anti_ban_module(member))
                    except Exception as e:
                        pass
                else:
                    action = 'kick'
                    try:
                        asyncio.create_task(self.anti_kick_module(member))
                    except Exception as e:
                        pass

                user = entry.target
                reason = entry.reason
                action_by = entry.user


                embed = discord.Embed(
                    title=f'{user.display_name} has been {action}ned',
                    description=f'**__User:__** {user.mention}\n**__Username:__** {user.name}\n**__User ID:__** {user.id}\n\n**__Action:__** {action}\n**__Reason:__** {reason}\n**__Action By:__** {action_by.mention}\n**__Time:__** <t:{int(entry.created_at.timestamp())}>',
                    color=color.red
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                embed.set_footer(text=f'User ID: {user.id}')
                await self.bot.log.send(guild=member.guild,embed=embed,type=f"member_{action}")
            else:
                try:
                    asyncio.create_task(self.anti_prune_module(member))
                except Exception as e:
                    pass
                action = 'leave'
                embed = discord.Embed(
                    title=f'{member.display_name} has left the server',
                    description=f'**__User__** {member.mention}\n**__Username:__** {member.name}\n**__User ID:__** {member.id}\n\n**__Action:__** {action}\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>',
                    color=color.red
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f'User ID: {member.id}')
                await self.bot.log.send(guild=member.guild,embed=embed,type=f"member_{action}")
        except Exception as e:
            logger.error(f"Error in on_member_remove.check_if_user_banned_or_kicked_module: {e}")
            return
        

    ban_user_timeouts = {}
    async def anti_ban_module(self,ban:discord.Member):
        try:
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(ban.guild.id))
            if not anti_nuke_cache:
                return
            if not anti_nuke_cache.get('enabled'):
                return
            if not anti_nuke_cache.get('anti_member_ban'):
                return logger.warning(f"Guild {ban.guild.name} has anti member ban disabled")
            
            async def check_entry():
                async for entry in ban.guild.audit_logs(limit=1,action=discord.AuditLogAction.ban,after=datetime.datetime.now()-datetime.timedelta(seconds=5)):
                    if entry.target.id == ban.id:
                        return entry
            entry = await check_entry()
            if entry:
                banner = entry.user
                if banner == self.bot.user:
                    return logger.warning(f"User {ban} was banned by the bot")
            else:
                return logger.warning(f"User {ban} was not banned by a user or maybe unknown user")
            
            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(str(ban.guild.id),{}).get(str(banner.id),{})
            if anti_nuke_bypass_cache.get('anti_member_ban'):
                return logger.warning(f"User {banner} is bypassed from anti member ban")
            
            if banner.id == ban.guild.owner.id or await checks.check_is_owner_raw(banner,ban.guild):
                return logger.warning(f"User {ban} was banned by the owner")
            if banner.top_role.position >= ban.guild.me.top_role.position:
                return logger.warning(f"User {ban} was banned by a user with a higher role than the bot")
            
            # ==================================
            if str(ban.guild.id) not in self.ban_user_timeouts:
                self.ban_user_timeouts[str(ban.guild.id)] = {}
            if str(banner.id) not in self.ban_user_timeouts.get(str(ban.guild.id)):
                self.ban_user_timeouts[str(ban.guild.id)][str(banner.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.ban_user_timeouts[str(ban.guild.id)][str(banner.id)]['count'] += 1
            self.ban_user_timeouts[str(ban.guild.id)][str(banner.id)]['created_at'] = datetime.datetime.now()

            if str(ban.guild.id) in self.ban_user_timeouts:
                if self.ban_user_timeouts.get(str(ban.guild.id)):
                    if self.ban_user_timeouts.get(str(ban.guild.id),{}).get(str(banner.id)):
                        if (self.ban_user_timeouts.get(str(ban.guild.id),{}).get(str(banner.id),{}).get('count') >= anti_nuke_cache.get('anti_member_ban_limit',1)
                            and
                            self.ban_user_timeouts.get(str(ban.guild.id),{}).get(str(banner.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_member_ban_punishment')

                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {ban.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{ban.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Member Ban\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=ban.guild.icon.url if ban.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(banner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {banner.mention}\n**__ID__**: `{banner.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Member Ban\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=banner.display_avatar.url)
                                    await ban.guild.ban(banner,reason="Banned by Antinuke System: Anti Member Ban")
                                    await self.bot.antinuke_log.send(guild=ban.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_ban_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{ban.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Member Ban\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=ban.guild.icon.url if ban.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(banner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {banner.mention}\n**__ID__**: `{banner.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Member Ban\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=banner.display_avatar.url)
                                    await ban.guild.kick(banner,reason="Kicked by Antinuke System: Anti Member Ban")
                                    await self.bot.antinuke_log.send(guild=ban.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_ban_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__Guild:__ `{ban.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Member Ban\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=ban.guild.icon.url if ban.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(banner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__User__**: {banner.mention}\n**__ID__**: `{banner.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Member Ban\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=banner.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=ban.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_ban_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__Guild:__ `{ban.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Member Ban\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=ban.guild.icon.url if ban.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(banner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__User__**: {banner.mention}\n**__ID__**: `{banner.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Member Ban\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=banner.display_avatar.url)
                                    try:
                                        await banner.edit(roles=[],reason="Muted by Antinuke System: Anti Member Ban")
                                    except Exception:
                                        pass
                                    await banner.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Member Ban")
                                    await self.bot.antinuke_log.send(guild=ban.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_ban_module: {e}")
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {ban.guild.name}")
                            
                            if action != 'warn':
                            # reset the timeout
                                if str(ban.guild.id) in self.ban_user_timeouts:
                                    if str(banner.id) in self.ban_user_timeouts.get(str(ban.guild.id)):
                                        self.ban_user_timeouts[str(ban.guild.id)][str(banner.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return
                        

        except Exception as e:
            logger.error(f"Error in on_member_remove.anti_ban_module: {e}")

    kick_user_timeouts = {}
    async def anti_kick_module(self,kick:discord.User):
        try:
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(kick.guild.id))
            if not anti_nuke_cache:
                return
            if not anti_nuke_cache.get('enabled'):
                return
            if not anti_nuke_cache.get('anti_member_kick'):
                return logger.warning(f"Guild {kick.guild.name} has anti member kick disabled")
            
            async def check_entry():
                async for entry in kick.guild.audit_logs(limit=1,action=discord.AuditLogAction.kick,after=datetime.datetime.now()-datetime.timedelta(seconds=5)):
                    if entry.target.id == kick.id:
                        return entry
            entry = await check_entry()
            if entry:
                kicker = entry.user
                if kicker == self.bot.user:
                    return logger.warning(f"User {kick} was kicked by the bot")
            else:
                return logger.warning(f"User {kick} was not kicked by a user or maybe unknown user")
            
            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(str(kick.guild.id),{}).get(str(kicker.id),{})
            if anti_nuke_bypass_cache.get('anti_member_kick'):
                return logger.warning(f"User {kicker} is bypassed from anti member kick")
            
            if kicker.id == kick.guild.owner.id or await checks.check_is_owner_raw(kicker,kick.guild):
                return logger.warning(f"User {kick} was kicked by the owner")
            if kicker.top_role.position >= kick.guild.me.top_role.position:
                return logger.warning(f"User {kick} was kicked by a user with a higher role than the bot")
            
            # ==================================
            if str(kick.guild.id) not in self.kick_user_timeouts:
                self.kick_user_timeouts[str(kick.guild.id)] = {}
            if str(kicker.id) not in self.kick_user_timeouts.get(str(kick.guild.id)):
                self.kick_user_timeouts[str(kick.guild.id)][str(kicker.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.kick_user_timeouts[str(kick.guild.id)][str(kicker.id)]['count'] += 1
            self.kick_user_timeouts[str(kick.guild.id)][str(kicker.id)]['created_at'] = datetime.datetime.now()

            if str(kick.guild.id) in self.kick_user_timeouts:
                if self.kick_user_timeouts.get(str(kick.guild.id)):
                    if self.kick_user_timeouts.get(str(kick.guild.id),{}).get(str(kicker.id)):
                        if (self.kick_user_timeouts.get(str(kick.guild.id),{}).get(str(kicker.id),{}).get('count') >= anti_nuke_cache.get('anti_member_kick_limit',1)
                            and
                            self.kick_user_timeouts.get(str(kick.guild.id),{}).get(str(kicker.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_member_kick_punishment')

                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {kick.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{kick.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Member Kick\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kick.guild.icon.url if kick.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(kicker,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {kicker.mention}\n**__ID__**: `{kicker.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Member Kick\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kicker.display_avatar.url)
                                    await kick.guild.ban(kicker,reason="Banned by Antinuke System: Anti Member Kick")
                                    await self.bot.antinuke_log.send(guild=kick.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_kick_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{kick.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Member Kick\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kick.guild.icon.url if kick.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(kicker,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {kicker.mention}\n**__ID__**: `{kicker.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Member Kick\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kicker.display_avatar.url)
                                    await kick.guild.kick(kicker,reason="Kicked by Antinuke System: Anti Member Kick")
                                    await self.bot.antinuke_log.send(guild=kick.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_kick_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__Guild:__ `{kick.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Member Kick\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kick.guild.icon.url if kick.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(kicker,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__User__**: {kicker.mention}\n**__ID__**: `{kicker.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Member Kick\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kicker.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=kick.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_kick_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__Guild:__ `{kick.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Member Kick\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kick.guild.icon.url if kick.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(kicker,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__User__**: {kicker.mention}\n**__ID__**: `{kicker.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Member Kick\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=kicker.display_avatar.url)
                                    try:
                                        await kicker.edit(roles=[],reason="Muted by Antinuke System: Anti Member Kick")
                                    except Exception:
                                        pass
                                    await kicker.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Member Kick")
                                    await self.bot.antinuke_log.send(guild=kick.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_kick_module: {e}")
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {kick.guild.name}")
                            
                            if action != 'warn':
                            # reset the timeout
                                if str(kick.guild.id) in self.kick_user_timeouts:
                                    if str(kicker.id) in self.kick_user_timeouts.get(str(kick.guild.id)):
                                        self.kick_user_timeouts[str(kick.guild.id)][str(kicker.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return
                        

        except Exception as e:
            logger.error(f"Error in on_member_remove.anti_kick_module: {e}")

    prune_user_timeouts = {}
    async def anti_prune_module(self,prune:discord.Member):
        try:
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(prune.guild.id))
            if not anti_nuke_cache:
                return
            if not anti_nuke_cache.get('enabled'):
                return
            if not anti_nuke_cache.get('anti_prune_member'):
                return logger.warning(f"Guild {prune.guild.name} has anti prune member disabled")
            
            async def check_entry():
                async for entry in prune.guild.audit_logs(limit=1,action=discord.AuditLogAction.member_prune,after=datetime.datetime.now()-datetime.timedelta(seconds=5)):
                    if entry.target.id == prune.id:
                        return entry
                    
            entry = await check_entry()
            if entry:
                pruner = entry.user
                if pruner == self.bot.user:
                    return logger.warning(f"User {prune} was pruned by the bot")
            else:
                return logger.warning(f"User {prune} was not pruned by a user or maybe unknown user")
            
            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(str(prune.guild.id),{}).get(str(pruner.id),{})
            if anti_nuke_bypass_cache.get('anti_prune_member'):
                return logger.warning(f"User {pruner} is bypassed from anti prune member")
            
            if pruner.id == prune.guild.owner.id or await checks.check_is_owner_raw(pruner,prune.guild):
                return logger.warning(f"User {prune} was pruned by the owner")
            if pruner.top_role.position >= prune.guild.me.top_role.position:
                return logger.warning(f"User {prune} was pruned by a user with a higher role than the bot")
            
            # ==================================
            if str(prune.guild.id) not in self.prune_user_timeouts:
                self.prune_user_timeouts[str(prune.guild.id)] = {}
            if str(pruner.id) not in self.prune_user_timeouts.get(str(prune.guild.id)):
                self.prune_user_timeouts[str(prune.guild.id)][str(pruner.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.prune_user_timeouts[str(prune.guild.id)][str(pruner.id)]['count'] += 1
            self.prune_user_timeouts[str(prune.guild.id)][str(pruner.id)]['created_at'] = datetime.datetime.now()
            
            if str(prune.guild.id) in self.prune_user_timeouts:
                if self.prune_user_timeouts.get(str(prune.guild.id)):
                    if self.prune_user_timeouts.get(str(prune.guild.id),{}).get(str(pruner.id)):
                        if (self.prune_user_timeouts.get(str(prune.guild.id),{}).get(str(pruner.id),{}).get('count') >= anti_nuke_cache.get('anti_prune_member_limit',1)
                            and
                            self.prune_user_timeouts.get(str(prune.guild.id),{}).get(str(pruner.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_prune_member_punishment')

                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {prune.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{prune.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Prune Member\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=prune.guild.icon.url if prune.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(pruner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {pruner.mention}\n**__ID__**: `{pruner.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Prune Member\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=pruner.display_avatar.url)
                                    await prune.guild.ban(pruner,reason="Banned by Antinuke System: Anti Prune Member")
                                    await self.bot.antinuke_log.send(guild=prune.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_prune_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{prune.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Prune Member\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=prune.guild.icon.url if prune.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(pruner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {pruner.mention}\n**__ID__**: `{pruner.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Prune Member\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=pruner.display_avatar.url)
                                    await prune.guild.kick(pruner,reason="Kicked by Antinuke System: Anti Prune Member")
                                    await self.bot.antinuke_log.send(guild=prune.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_prune_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__Guild:__ `{prune.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Prune Member\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=prune.guild.icon.url if prune.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(pruner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__User__**: {pruner.mention}\n**__ID__**: `{pruner.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Prune Member\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=pruner.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=prune.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_prune_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__Guild:__ `{prune.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Prune Member\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=prune.guild.icon.url if prune.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(pruner,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__User__**: {pruner.mention}\n**__ID__**: `{pruner.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Prune Member\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=pruner.display_avatar.url)
                                    try:
                                        await pruner.edit(roles=[],reason="Muted by Antinuke System: Anti Prune Member")
                                    except Exception:
                                        pass
                                    await pruner.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Prune Member")
                                    await self.bot.antinuke_log.send(guild=prune.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_prune_module: {e}")                            
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {prune.guild.name}")
                            
                            if action != 'warn':
                            # reset the timeout
                                if str(prune.guild.id) in self.prune_user_timeouts:
                                    if str(pruner.id) in self.prune_user_timeouts.get(str(prune.guild.id)):
                                        self.prune_user_timeouts[str(prune.guild.id)][str(pruner.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return
                        

        except Exception as e:
            logger.error(f"Error in on_member_remove.anti_prune_module: {e}")

    async def guild_leaver_module(self, member: discord.Member):
        guild = member.guild
        try:
            welcomer_cache = self.bot.cache.welcomer_settings.get(str(guild.id), {})
            if not welcomer_cache:
                return
            if not welcomer_cache.get("leave"):
                return logger.warning(f"Guild {guild.name} has leaver disabled")

            guild_data = cache.guilds.get(str(guild.id), {}) or {}
            can_use_image_cards = _plan_at_least(guild_data.get("subscription", "free"), "silver")
            send_leave_message = bool(welcomer_cache.get("leave_message_enabled", True))
            send_leave_embed = bool(welcomer_cache.get("leave_embed"))
            send_leave_image = bool(welcomer_cache.get("leave_image")) and can_use_image_cards
            if not (send_leave_message or send_leave_embed or send_leave_image):
                return logger.warning(f"Guild {guild.name} has leave message/embed/image disabled")

            channel_ids = welcomer_cache.get("leave_channels") or []
            if isinstance(channel_ids, str):
                try:
                    import json

                    channel_ids = json.loads(channel_ids)
                except Exception:
                    channel_ids = []
            channel_ids = [int(ch) for ch in channel_ids if str(ch).isdigit()]
            if not channel_ids:
                return logger.warning(f"Guild {guild.name} has no leave channels")

            template = (
                welcomer_cache.get("leave_message")
                or "{user.mention} ออกจาก {server} แล้ว"
            )
            delete_after_raw = welcomer_cache.get("leave_delete_after", 0)
            try:
                delete_after = int(delete_after_raw or 0)
            except (TypeError, ValueError):
                delete_after = 0
            if delete_after < 0:
                delete_after = 0

            message_content = fetch_variables(text=template, member=member, guild=guild) if send_leave_message else None

            embed = None
            if send_leave_embed:
                embed_title = fetch_variables(
                    text=welcomer_cache.get("leave_embed_title") or "{user} left {server}",
                    member=member,
                    guild=guild,
                ) or f"{member.display_name} left {guild.name}"
                embed_description = fetch_variables(
                    text=welcomer_cache.get("leave_embed_description") or "{user.mention} ออกจาก {server} แล้ว",
                    member=member,
                    guild=guild,
                ) or f"{member.mention} ออกจาก {guild.name} แล้ว"
                embed = discord.Embed(
                    title=str(embed_title)[:256],
                    description=str(embed_description)[:4096],
                    color=color.orange,
                )
                try:
                    embed.set_thumbnail(url=member.display_avatar.url)
                except Exception:
                    pass

            image_bytes: bytes | None = None
            if send_leave_image:
                top_text = fetch_variables(
                    text=welcomer_cache.get("leave_image_top_text") or "{user}",
                    member=member,
                    guild=guild,
                ) or member.display_name
                bottom_text = fetch_variables(
                    text=welcomer_cache.get("leave_image_bottom_text") or "ออกจาก {server}",
                    member=member,
                    guild=guild,
                ) or f"ออกจาก {guild.name}"
                card_bytes = build_member_notice_card(
                    avatar_url=str(member.display_avatar.url),
                    top_text=top_text,
                    bottom_text=bottom_text,
                    theme_key=welcomer_cache.get("leave_image_theme", "security"),
                    theme_url=welcomer_cache.get("leave_image_theme_url"),
                    user_theme_url=str(member.display_avatar.url),
                    guild_theme_url=str(getattr(getattr(guild, "icon", None), "url", "") or ""),
                    layout_mode=welcomer_cache.get("leave_image_layout_mode", "center_stack"),
                    avatar_position=welcomer_cache.get("leave_image_avatar_position", "center"),
                    text_align=welcomer_cache.get("leave_image_text_align", "center"),
                    font_style=welcomer_cache.get("leave_image_font_style", "classic"),
                )
                if card_bytes is not None:
                    image_bytes = card_bytes.getvalue()
                    if embed and not (getattr(embed, "image", None) and getattr(embed.image, "url", "")):
                        embed.set_image(url="attachment://leave-card.png")

            if not message_content and embed is None and image_bytes is None:
                return
            for channel_id in channel_ids:
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    continue
                try:
                    send_payload = {}
                    if message_content:
                        send_payload["content"] = message_content
                    if embed is not None:
                        send_payload["embed"] = embed
                    if image_bytes is not None:
                        send_payload["file"] = discord.File(
                            fp=io.BytesIO(image_bytes),
                            filename="leave-card.png",
                        )
                    if delete_after > 0:
                        await channel.send(**send_payload, delete_after=delete_after)
                    else:
                        await channel.send(**send_payload)
                    await asyncio.sleep(0.6)
                except Exception:
                    continue
        except Exception as e:
            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )


    @commands.Cog.listener()
    async def on_member_remove(self, member:discord.Member):
        try:
            asyncio.create_task(
                dashboard_activity.record_leave(
                    member.guild.id,
                    member_count=int(getattr(member.guild, "member_count", 0) or 0),
                )
            )
        except Exception:
            pass
        try:
            asyncio.create_task(self.check_if_user_banned_or_kicked_module(member))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.guild_leaver_module(member))
        except Exception:
            pass
        
