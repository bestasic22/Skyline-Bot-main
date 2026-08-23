import datetime
import discord
from discord.ext import commands

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks
from skylinebot.utils import i18n
import traceback

class on_command_error(commands.Cog):
    def __init__(self, bot):
        self.bot:commands.Bot = bot

    @staticmethod
    def _is_expired_interaction_error(error: Exception) -> bool:
        transient_codes = {10062, 10008}
        visited_ids: set[int] = set()
        current = error
        while current is not None and id(current) not in visited_ids:
            visited_ids.add(id(current))
            if isinstance(current, discord.NotFound) and getattr(current, "code", None) in transient_codes:
                return True
            if isinstance(current, discord.HTTPException) and getattr(current, "code", None) in transient_codes:
                return True
            current = (
                getattr(current, "original", None)
                or getattr(current, "__cause__", None)
                or getattr(current, "__context__", None)
            )
        return False

    @commands.Cog.listener()
    async def on_command_error(self,ctx:commands.Context,error):
        guild_id = getattr(getattr(ctx, "guild", None), "id", None)
        if self._is_expired_interaction_error(error):
            logger.warning(
                f"Ignored expired interaction for command {getattr(ctx.command, 'qualified_name', ctx.command)} "
                f"(message_id={getattr(getattr(ctx, 'message', None), 'id', 'unknown')})"
            )
            return

        if isinstance(error, (commands.CommandNotFound, commands.MissingRequiredArgument, commands.BadArgument, commands.CommandOnCooldown, commands.CheckFailure)):
            # Handling these below but don't log them as "Errors" in console
            pass
        else:
            logger.error(f"Error in file {__file__}: {repr(error)}")
            logger.error(f"Error in {ctx.command}, Command: {ctx.message.content}, Message ID: {ctx.message.id}, Error: {error}")

        if isinstance(error, commands.CommandOnCooldown):
            # if the colldown type is user, then the error.retry_after will be the time left for the user to use the command again
            if error.type == commands.BucketType.user:
                retry = f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>"
                await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('cooldown_user', guild_id, retry=retry)}**",delete_after=int(error.retry_after))
            elif (error.type == commands.BucketType.guild):
                retry = f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>"
                await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('cooldown_guild', guild_id, retry=retry)}**",delete_after=int(error.retry_after))
            elif (error.type == commands.BucketType.channel):
                retry = f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>"
                await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('cooldown_channel', guild_id, retry=retry)}**",delete_after=int(error.retry_after))
            elif (error.type == commands.BucketType.category):
                retry = f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>"
                await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('cooldown_member', guild_id, retry=retry)}**",delete_after=int(error.retry_after))
            elif (error.type == commands.BucketType.member):
                retry = f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>"
                await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('cooldown_member', guild_id, retry=retry)}**",delete_after=int(error.retry_after))
            elif (error.type == commands.BucketType.role):
                retry = f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>"
                await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('cooldown_role', guild_id, retry=retry)}**",delete_after=int(error.retry_after))
            else:
                retry = f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>"
                await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('cooldown_user', guild_id, retry=retry)}**",delete_after=int(error.retry_after))
        if isinstance(error, commands.MissingRequiredArgument):
            usage = f"{ctx.prefix}{ctx.command} {ctx.command.signature}"
            await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('missing_required_arg', guild_id, usage=usage)}**",delete_after=5)
        if isinstance(error, commands.BadArgument):
            usage = f"{ctx.prefix}{ctx.command} {ctx.command.signature}"
            await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('bad_argument', guild_id, usage=usage)}**",delete_after=5)
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('missing_permissions', guild_id, perms=error.missing_perms)}**",delete_after=5)
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('bot_missing_permissions', guild_id, perms=error.missing_perms)}**",delete_after=5)
        if isinstance(error, commands.NotOwner):
            await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('not_owner', guild_id)}**",delete_after=5)
        if isinstance(error, commands.CheckFailure):
            if checks.check_ignore_predicate in ctx.command.checks:
                if not checks.check_ignore_predicate(ctx):
                    return
                
            if checks.check_blacklist_predicate in ctx.command.checks:
                if not checks.check_blacklist_predicate(ctx):
                    return
                
            if checks.check_is_admin_predicate in ctx.command.checks:
                if not checks.check_is_admin_predicate(ctx.author):
                    await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('admin_only', guild_id)}**",delete_after=5)
            
            if checks.check_is_owner_predicate in ctx.command.checks:
                if not checks.check_is_owner_predicate(ctx):
                    await ctx.reply(f"**{self.bot.emoji.WARNING} - {i18n.tr('owner_only', guild_id)}**",delete_after=5)
