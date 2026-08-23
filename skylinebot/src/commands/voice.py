import discord


from discord.ext import commands


import psutil


import asyncio


import io


import platform


import datetime


import time


from skylinebot.src.checks import checks


from skylinebot.memory.cache import cache


import traceback, sys


import re


import storage.afk


import storage.guilds


import storage.shop


import storage.users


from skylinebot.console.logging import logger


from skylinebot.style import color


from skylinebot.workflows import ui


from skylinebot.utils import pings


from skylinebot.utils import i18n


from skylinebot.config.config import BotConfigClass


BotConfig = BotConfigClass()


import storage


from skylinebot.workflows.afk_delay import afk_delay


from skylinebot.engine.bot_runtime import AutoShardedBot


class Voice(commands.Cog):

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        class CogInfo:

            name = "Voice"

            category = "Extra"

            description = "Voice related commands"

            hidden = False

            emoji = self.bot.emoji.MICROPHONE or "🎤"

        self.cog_info = CogInfo

    @commands.command(name="vcmute", help="ปิดเสียงผู้ใช้ในห้องเสียง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcmute(self, ctx: commands.Context, member: discord.Member):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "mute_members"):

                return

            if not member.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_in_voice", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            if member.voice.mute:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_already_muted", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            try:

                await member.edit(mute=True)

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_muted", guild_id, member=member.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcunmute",
        help="Unmute a user in a voice channel (ยกเลิกปิดเสียงผู้ใช้ในห้องเสียง)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcunmute(self, ctx: commands.Context, member: discord.Member):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "mute_members"):

                return

            if not member.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_in_voice", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            if not member.voice.mute:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_muted", guild_id, member=member.mention), color=color.red
                    )
                )

            try:

                await member.edit(mute=False)

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_unmuted", guild_id, member=member.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="vcdeafen", help="ปิดการได้ยินผู้ใช้ในห้องเสียง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcdeafen(self, ctx: commands.Context, member: discord.Member):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "deafen_members"):

                return

            if not member.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_in_voice", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            if member.voice.deaf:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_already_deafened", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            try:

                await member.edit(deafen=True)

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_deafened", guild_id, member=member.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcundeafen",
        help="Undeafen a user in a voice channel (ยกเลิกปิดการได้ยินผู้ใช้ในห้องเสียง)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcundeafen(self, ctx: commands.Context, member: discord.Member):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "deafen_members"):

                return

            if not member.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_in_voice", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            if not member.voice.deaf:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_deafened", guild_id, member=member.mention), color=color.red
                    )
                )

            try:

                await member.edit(deafen=False)

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_undeafened", guild_id, member=member.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(name="vcmove", help="ย้ายผู้ใช้ไปยังห้องเสียง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcmove(
        self,
        ctx: commands.Context,
        member: discord.Member,
        channel: discord.VoiceChannel,
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "move_members"):

                return

            if not member.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_in_voice", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            try:

                await member.move_to(channel)

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_moved", guild_id, member=member.mention, channel=channel.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(
        name="vcmoveall",
        help="ย้ายผู้ใช้ทั้งหมดในห้องเสียงไปยังอีกห้องเสียง",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def vcmoveall(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel,
        new_channel: discord.VoiceChannel = None,
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "manage_channels"):

                return

            if not await checks.check_is_moderator_permissions(ctx, "move_members"):

                return

            if not new_channel:

                if not ctx.author.voice:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=i18n.tr("vc_you_not_in_voice", guild_id),
                            color=color.red,
                        )
                    )

                new_channel = channel

                channel = ctx.author.voice.channel

            if len(channel.members) == 0:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_no_users", guild_id, channel=channel.mention), color=color.red
                    )
                )

            try:

                for member in channel.members:

                    try:

                        await member.move_to(new_channel)

                    except Exception as e:

                        pass

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_all_moved", guild_id, channel=channel.mention, new_channel=new_channel.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcdisconnect", help="ตัดการเชื่อมต่อผู้ใช้ออกจากห้องเสียง"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcdisconnect(self, ctx: commands.Context, member: discord.Member):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "move_members"):

                return

            if not member.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_in_voice", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            try:

                await member.move_to(None)

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_disconnected", guild_id, member=member.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcpull",
        help="Pull a user to your voice channel (ดึงผู้ใช้เข้าห้องเสียงของคุณ)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcpull(self, ctx: commands.Context, member: discord.Member):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "move_members"):

                return

            if not ctx.author.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_you_not_in_voice", guild_id), color=color.red
                    )
                )

            if not member.voice:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_not_in_voice", guild_id, member=member.mention),
                        color=color.red,
                    )
                )

            try:

                await member.move_to(ctx.author.voice.channel)

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_pulled", guild_id, member=member.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    # vcmuteall

    # vcunmuteall

    # vcdeafenall

    # vcundeafenall

    @commands.command(name="vcmuteall", help="ปิดเสียงผู้ใช้ทั้งหมดในห้องเสียง")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcmuteall(
        self, ctx: commands.Context, channel: discord.VoiceChannel = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "mute_members"):

                return

            if not channel:

                if not ctx.author.voice:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=i18n.tr("vc_you_not_in_voice", guild_id),
                            color=color.red,
                        )
                    )

                channel = ctx.author.voice.channel

            if len(channel.members) == 0:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_no_users", guild_id, channel=channel.mention), color=color.red
                    )
                )

            try:

                for member in channel.members:

                    try:

                        await member.edit(mute=True)

                    except Exception as e:

                        pass

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_all_muted", guild_id, channel=channel.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcunmuteall",
        help="Unmute all users in a voice channel (ยกเลิกปิดเสียงผู้ใช้ทั้งหมดในห้องเสียง)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcunmuteall(
        self, ctx: commands.Context, channel: discord.VoiceChannel = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "mute_members"):

                return

            if not channel:

                if not ctx.author.voice:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=i18n.tr("vc_you_not_in_voice", guild_id),
                            color=color.red,
                        )
                    )

                channel = ctx.author.voice.channel

            if len(channel.members) == 0:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_no_users", guild_id, channel=channel.mention), color=color.red
                    )
                )

            try:

                for member in channel.members:

                    try:

                        await member.edit(mute=False)

                    except Exception as e:

                        pass

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_all_unmuted", guild_id, channel=channel.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcdeafenall",
        help="ปิดการได้ยินผู้ใช้ทั้งหมดในห้องเสียง",
        aliases=["vcdefall"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcdeafenall(
        self, ctx: commands.Context, channel: discord.VoiceChannel = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "deafen_members"):

                return

            if not channel:

                if not ctx.author.voice:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=i18n.tr("vc_you_not_in_voice", guild_id),
                            color=color.red,
                        )
                    )

                channel = ctx.author.voice.channel

            if len(channel.members) == 0:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_no_users", guild_id, channel=channel.mention), color=color.red
                    )
                )

            try:

                for member in channel.members:

                    try:

                        await member.edit(deafen=True)

                    except Exception as e:

                        pass

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_all_deafened", guild_id, channel=channel.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcundeafenall",
        help="Undeafen all users in a voice channel (ยกเลิกปิดการได้ยินผู้ใช้ทั้งหมดในห้องเสียง)",
        aliases=["vcundefall"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcundeafenall(
        self, ctx: commands.Context, channel: discord.VoiceChannel = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "deafen_members"):

                return

            if not channel:

                if not ctx.author.voice:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=i18n.tr("vc_you_not_in_voice", guild_id),
                            color=color.red,
                        )
                    )

                channel = ctx.author.voice.channel

            if len(channel.members) == 0:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_no_users", guild_id, channel=channel.mention), color=color.red
                    )
                )

            try:

                for member in channel.members:

                    try:

                        await member.edit(deafen=False)

                    except Exception as e:

                        pass

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_all_undeafened", guild_id, channel=channel.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="vcdisconnectall",
        help="ตัดการเชื่อมต่อผู้ใช้ทั้งหมดออกจากห้องเสียง",
        aliases=["vckickall"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def vcdisconnectall(
        self, ctx: commands.Context, channel: discord.VoiceChannel = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not await checks.check_is_moderator_permissions(ctx, "move_members"):

                return

            if not channel:

                if not ctx.author.voice:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=i18n.tr("vc_you_not_in_voice", guild_id),
                            color=color.red,
                        )
                    )

                channel = ctx.author.voice.channel

            if len(channel.members) == 0:

                return await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_no_users", guild_id, channel=channel.mention), color=color.red
                    )
                )

            try:

                for member in channel.members:

                    try:

                        await member.move_to(None)

                    except Exception as e:

                        pass

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_all_disconnected", guild_id, channel=channel.mention),
                        color=color.green,
                    )
                )

            except Exception as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=i18n.tr("vc_error", guild_id, error=str(e)), color=color.red
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")




