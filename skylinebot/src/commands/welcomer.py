import discord
from discord import app_commands


from discord.ext import commands


import datetime


import traceback, sys


import json


from skylinebot.src.checks import checks


from skylinebot.memory.cache import cache


import storage.antinuke_bypass


import storage.antinuke_settings


import storage.guilds


import storage.guilds_backup


import storage.welcomer_settings


from skylinebot.console.logging import logger


from skylinebot.style import color


from skylinebot.utils import i18n

import asyncio


from skylinebot.config.config import BotConfigClass


BotConfig = BotConfigClass()
SUBSCRIBE_PLAN_URL = f"{BotConfig.DASHBOARD_BASE_URL.rstrip('/')}/dashboard/subscribe-plan"


from skylinebot.src.checks.variables import fetch_variables


from skylinebot.engine.bot_runtime import AutoShardedBot


import storage
from skylinebot.src.services import CommandFlow, WelcomerRepository
from skylinebot.src.services.welcomer_utils import (
    channel_mentions,
    is_valid_image_url,
    parse_json_list,
    unescape_newlines,
)


def fetch_line(text: str):
    return unescape_newlines(text)


def check_image_url(url: str):
    return is_valid_image_url(url)


class Welcomer(commands.Cog):

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        self.variables_text = "\n".join(
            [f"{key} -> {value}" for key, value in bot.variables.items()]
        )

        class CogInfo:

            name = "Welcomer"

            category = "Main"

            description = "Welcomer commands"

            hidden = False

            emoji = self.bot.emoji.WELCOMER or "👋"

        self.cog_info = CogInfo
        self.command_flow = CommandFlow(bot)
        self.welcomer_repo = WelcomerRepository(bot)

    async def _require_manage_guild(self, ctx: commands.Context) -> bool:
        return await checks.check_is_moderator_permissions(ctx, "manage_guild")

    async def _get_welcomer_cache(self, guild_id: int):
        return await self.welcomer_repo.get_settings(guild_id)

    @commands.hybrid_group(
        name="welcome",
        help="ตั้งค่าข้อความต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
        aliases=["welcomer", "welcomers"],
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def welcome(self, ctx: commands.Context):

        try:

            if not await self._require_manage_guild(ctx):

                return

            await self.welcome_settings(ctx)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @welcome.command(
        name="leaver",
        help="ตั้งค่าข้อความลาสำหรับเซิร์ฟเวอร์ของคุณ",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def welcome_leaver(self, ctx):

        await self.leaver_settings(ctx)

    @welcome.command(
        name="autorole",
        help="ตั้งค่ายศอัตโนมัติสำหรับเซิร์ฟเวอร์ของคุณ",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def welcome_autorole(self, ctx):

        await self.autorole_settings(ctx)

    @welcome.command(
        name="greet",
        help="ตั้งค่าห้องและข้อความทักทายสำหรับเซิร์ฟเวอร์ของคุณ",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def welcome_greet(self, ctx):

        await self.greet_settings(ctx)

    @commands.hybrid_group(
        name="leaver",
        help="ตั้งค่าข้อความลาสำหรับเซิร์ฟเวอร์ของคุณ",
        aliases=["leave"],
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def leaver(self, ctx: commands.Context):

        try:

            if not await self._require_manage_guild(ctx):

                return

            await self.leaver_settings(ctx)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @leaver.command(
        name="settings",
        help="ตั้งค่าข้อความลาสำหรับเซิร์ฟเวอร์ของคุณ",
        with_app_command=True,
        aliases=["setting"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def leaver_settings(self, ctx: commands.Context):
        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            if getattr(ctx, "interaction", None):
                try:
                    if not ctx.interaction.response.is_done():
                        await ctx.interaction.response.defer(ephemeral=False)
                except Exception:
                    pass

            welcomer_cache = await self._get_welcomer_cache(ctx.guild.id)
            channel_mentions_text = channel_mentions(
                welcomer_cache.get("leave_channels") or []
            )
            leave_message = welcomer_cache.get("leave_message") or "No leave message set"
            delete_after = welcomer_cache.get("leave_delete_after", 0)

            embed = discord.Embed(
                title="ตั้งค่าโมดูลข้อความลาจาก",
                description="ระบบ Leaver",
                color=color.green if welcomer_cache.get("leave") else color.red,
            )
            embed.add_field(
                name="Status",
                value=f"{self.bot.emoji.ENABLED if welcomer_cache.get('leave') else self.bot.emoji.DISABLED}",
                inline=True,
            )
            embed.add_field(name="Channels", value=channel_mentions_text, inline=True)
            embed.add_field(
                name="Delete After",
                value=f"`{delete_after} sec`" if int(delete_after or 0) > 0 else "`Off`",
                inline=True,
            )
            embed.add_field(name="Message", value=f"```{leave_message}```", inline=False)
            embed.add_field(
                name="Dashboard",
                value=f"[เปิดหน้า Welcome/Leaver]({BotConfig.DASHBOARD_BASE_URL.rstrip('/')}/dashboard/guild/{ctx.guild.id}/welcome)",
                inline=False,
            )
            if getattr(ctx, "interaction", None):
                try:
                    await ctx.interaction.followup.send(embed=embed)
                except Exception:
                    await ctx.send(embed=embed)
            else:
                await ctx.send(embed=embed)
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @welcome.command(
        name="settings",
        help="ตั้งค่าการตั้งค่าข้อความต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
        with_app_command=True,
        aliases=["setting"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def welcome_settings(self, ctx: commands.Context):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):

                return

            await self.welcomer_repo.ensure_settings(ctx.guild.id)

            async def get_embed():

                try:

                    welcomer_cache = await self._get_welcomer_cache(ctx.guild.id)

                    embed = discord.Embed(
                        title=f"{self.bot.emoji.ENABLED if welcomer_cache.get('welcome') else self.bot.emoji.DISABLED} - Welcome Module Settings",
                        description="",
                        color=(
                            color.green if welcomer_cache.get("welcome") else color.red
                        ),
                    )

                    if welcomer_cache.get("welcome_message") and welcomer_cache.get(
                        "welcome_embed"
                    ):

                        welcome_type = "Message & Embed"

                    elif welcomer_cache.get(
                        "welcome_message"
                    ) and not welcomer_cache.get("welcome_embed"):

                        welcome_type = "Message"

                    elif not welcomer_cache.get(
                        "welcome_message"
                    ) and welcomer_cache.get("welcome_embed"):

                        welcome_type = "Embed"

                    else:

                        welcome_type = "Not Set"

                    welcomer_channel_id = welcomer_cache.get("welcome_channel")

                    embed.description += (
                        f"> Configure the welcome message settings for your server"
                    )

                    embed.description += f"\n> **Channel:** {f'<#{welcomer_channel_id}>' if welcomer_channel_id else '`No channel set`'}"

                    embed.description += f"\n> **Welcome Type:** `{welcome_type}`"

                    embed.add_field(
                        name=f"{self.bot.emoji.ENABLED if welcomer_cache.get('welcome_message') else self.bot.emoji.DISABLED} - Message",
                        value=f"```{welcomer_cache.get('welcome_message_content') or 'No message set'}```",
                        inline=True,
                    )

                    thumbnail_url = "`No thumbnail set`"

                    if welcomer_cache.get("welcome_embed_thumbnail"):

                        if (
                            str(welcomer_cache.get("welcome_embed_thumbnail")).lower()
                            in self.bot.variables.keys()
                        ):

                            thumbnail_url = (
                                f"`{welcomer_cache.get('welcome_embed_thumbnail')}`"
                            )

                        else:

                            thumbnail_url = f"[Thumbnail]({welcomer_cache.get('welcome_embed_thumbnail')})"

                    image_url = "`No image set`"

                    if welcomer_cache.get("welcome_embed_image"):

                        if (
                            str(welcomer_cache.get("welcome_embed_image")).lower()
                            in self.bot.variables.keys()
                        ):

                            image_url = f"`{welcomer_cache.get('welcome_embed_image')}`"

                        else:

                            image_url = (
                                f"[Image]({welcomer_cache.get('welcome_embed_image')})"
                            )

                    footer_icon_url = "`No footer icon set`"

                    if welcomer_cache.get("welcome_embed_footer_icon"):

                        if (
                            str(welcomer_cache.get("welcome_embed_footer_icon")).lower()
                            in self.bot.variables.keys()
                        ):

                            footer_icon_url = (
                                f"`{welcomer_cache.get('welcome_embed_footer_icon')}`"
                            )

                        else:

                            footer_icon_url = f"[Footer Icon]({welcomer_cache.get('welcome_embed_footer_icon')})"

                    author_icon_url = "`No author icon set`"

                    if welcomer_cache.get("welcome_embed_author_icon"):

                        if (
                            str(welcomer_cache.get("welcome_embed_author_icon")).lower()
                            in self.bot.variables.keys()
                        ):

                            author_icon_url = (
                                f"`{welcomer_cache.get('welcome_embed_author_icon')}`"
                            )

                        else:

                            author_icon_url = f"[Author Icon]({welcomer_cache.get('welcome_embed_author_icon')})"

                    author_url = "`No author url set`"

                    if welcomer_cache.get("welcome_embed_author_url"):

                        if (
                            str(welcomer_cache.get("welcome_embed_author_url")).lower()
                            in self.bot.variables.keys()
                        ):

                            author_url = (
                                f"`{welcomer_cache.get('welcome_embed_author_url')}`"
                            )

                        else:

                            author_url = f"[Author URL]({welcomer_cache.get('welcome_embed_author_url')})"

                    embed.add_field(
                        name=f"{self.bot.emoji.ENABLED if welcomer_cache.get('welcome_embed') else self.bot.emoji.DISABLED} - Embed",
                        value=(
                            "Enabled"
                            if welcomer_cache.get("welcome_embed")
                            else "Disabled"
                        ),
                        inline=True,
                    )

                    embed.add_field(
                        name=f"Embed Title",
                        value=f"`{welcomer_cache.get('welcome_embed_title') or 'No title set'}`",
                        inline=True,
                    )

                    embed.add_field(name="", value="", inline=False)

                    embed.add_field(
                        name="Embed Description",
                        value=f"```{welcomer_cache.get('welcome_embed_description') or 'No description set'}```",
                        inline=True,
                    )

                    embed.add_field(
                        name="Embed Thumbnail", value=thumbnail_url, inline=True
                    )

                    embed.add_field(name="Embed Image", value=image_url, inline=True)

                    embed.add_field(name="", value="", inline=False)

                    embed.add_field(
                        name="Embed Footer Text",
                        value=f"`{welcomer_cache.get('welcome_embed_footer') or 'No footer set'}`",
                        inline=True,
                    )

                    embed.add_field(
                        name="Embed Footer Icon", value=footer_icon_url, inline=True
                    )

                    if welcomer_cache.get("welcome_embed_color"):

                        if (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "red"
                        ):

                            embed_color = self.bot.emoji.RED

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "green"
                        ):

                            embed_color = self.bot.emoji.GREEN

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "blue"
                        ):

                            embed_color = self.bot.emoji.BLUE

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "yellow"
                        ):

                            embed_color = self.bot.emoji.YELLOW

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "purple"
                        ):

                            embed_color = self.bot.emoji.PURPLE

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "pink"
                        ):

                            embed_color = self.bot.emoji.PINK

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "orange"
                        ):

                            embed_color = self.bot.emoji.ORANGE

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "black"
                        ):

                            embed_color = self.bot.emoji.BLACK

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "white"
                        ):

                            embed_color = self.bot.emoji.WHITE

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "gray"
                        ):

                            embed_color = self.bot.emoji.GRAY

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "cyan"
                        ):

                            embed_color = self.bot.emoji.CYAN

                        else:

                            embed_color = None

                    else:

                        embed_color = None

                    embed.add_field(
                        name="Color",
                        value=f"`{embed_color if embed_color else 'No color set'}`",
                        inline=True,
                    )

                    embed.add_field(name="", value="", inline=False)

                    embed.add_field(
                        name="Embed Author Text",
                        value=f"`{welcomer_cache.get('welcome_embed_author') or 'No author set'}`",
                        inline=True,
                    )

                    embed.add_field(
                        name="Embed Author Icon", value=author_icon_url, inline=True
                    )

                    embed.add_field(
                        name="Embed Author URL", value=author_url, inline=True
                    )

                    embed.set_footer(
                        text=f"SkylineBOT | Skyline Development",
                        icon_url=self.bot.user.display_avatar.url,
                    )

                    embed.set_thumbnail(
                        url=(
                            ctx.guild.icon.url
                            if ctx.guild.icon
                            else self.bot.user.display_avatar.url
                        )
                    )

                    return embed

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

                    return None

            timeout_time = 200

            cancled = False

            def reset_timeout(timeout: int = 200):

                nonlocal timeout_time

                timeout_time = timeout

            async def get_view(disabled=False):

                try:

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    view = discord.ui.View(timeout=200)

                    reset_timeout()

                    enable_disable_button = discord.ui.Button(
                        label=(
                            "Enable Welcome"
                            if not welcomer_cache.get("welcome")
                            else "Disable Welcome"
                        ),
                        style=(
                            discord.ButtonStyle.green
                            if not welcomer_cache.get("welcome")
                            else discord.ButtonStyle.gray
                        ),
                        emoji=(
                            self.bot.emoji.ENABLED
                            if not welcomer_cache.get("welcome")
                            else self.bot.emoji.DISABLED
                        ),
                        row=0,
                    )

                    enable_disable_button.callback = (
                        lambda i: enable_disable_button_callback(i)
                    )

                    view.add_item(enable_disable_button)

                    preview_button = discord.ui.Button(
                        label="Preview Welcome",
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.PREVIEW,
                        row=0,
                    )

                    preview_button.callback = lambda i: preview_button_callback(i)

                    view.add_item(preview_button)

                    select_type = discord.ui.Select(
                        placeholder="Select the welcome type",
                        options=[
                            discord.SelectOption(
                                label="Message & Embed",
                                value="message_and_embed",
                                default=(
                                    True
                                    if welcomer_cache.get("welcome_message")
                                    and welcomer_cache.get("welcome_embed")
                                    else False
                                ),
                            ),
                            discord.SelectOption(
                                label="Message",
                                value="message",
                                default=(
                                    True
                                    if welcomer_cache.get("welcome_message")
                                    and not welcomer_cache.get("welcome_embed")
                                    else False
                                ),
                            ),
                            discord.SelectOption(
                                label="Embed",
                                value="embed",
                                default=(
                                    True
                                    if welcomer_cache.get("welcome_embed")
                                    and not welcomer_cache.get("welcome_message")
                                    else False
                                ),
                            ),
                        ],
                        row=1,
                        max_values=1,
                        min_values=1,
                    )

                    select_type.callback = lambda i: select_type_callback(i)

                    view.add_item(select_type)

                    channel_select = discord.ui.ChannelSelect(
                        placeholder="Select the welcome channel",
                        row=2,
                        min_values=1,
                        max_values=1,
                        channel_types=[discord.ChannelType.text],
                        default_values=(
                            [
                                discord.Object(
                                    id=int(welcomer_cache.get("welcome_channel"))
                                )
                            ]
                            if welcomer_cache.get("welcome_channel")
                            else None
                        ),
                    )

                    channel_select.callback = lambda i: channel_select_callback(i)

                    view.add_item(channel_select)

                    edit_message_button = discord.ui.Button(
                        label="Edit Message Text",
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.EDIT,
                        row=3,
                        disabled=(
                            True if not welcomer_cache.get("welcome_message") else False
                        ),
                    )

                    edit_message_button.callback = (
                        lambda i: edit_message_button_callback(i)
                    )

                    view.add_item(edit_message_button)

                    edit_embed_button = discord.ui.Button(
                        label="Edit Embed Card",
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.EDIT,
                        row=3,
                        disabled=(
                            True if not welcomer_cache.get("welcome_embed") else False
                        ),
                    )

                    edit_embed_button.callback = lambda i: edit_embed_button_callback(i)

                    view.add_item(edit_embed_button)

                    cancle_button = discord.ui.Button(
                        label="ปิดเมนู",
                        style=discord.ButtonStyle.gray,
                        emoji=self.bot.emoji.CANCLED,
                        row=4,
                    )

                    cancle_button.callback = lambda i: cancle_button_callback(i)

                    view.add_item(cancle_button)

                    if disabled:

                        for item in view.children:

                            item.disabled = True

                    return view

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

                    return None

            async def preview_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    if not welcomer_cache.get(
                        "welcome_message"
                    ) and not welcomer_cache.get("welcome_embed"):

                        temp_msg = await interaction.followup.send(
                            embed=discord.Embed(
                                description="คุณต้องตั้งค่าข้อความต้อนรับหรือ embed ก่อนแสดงตัวอย่าง",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                        await asyncio.sleep(10)

                        try:

                            await temp_msg.delete()

                        except Exception:
                            pass

                        return

                    if welcomer_cache.get("welcome_message"):

                        message_content = fetch_variables(
                            welcomer_cache.get("welcome_message_content"),
                            member=ctx.author,
                            guild=ctx.guild,
                        )

                    else:

                        message_content = None

                    embed_color = discord.Color.blurple()

                    if welcomer_cache.get("welcome_embed_color"):

                        if (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "red"
                        ):

                            embed_color = color.red

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "green"
                        ):

                            embed_color = color.green

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "blue"
                        ):

                            embed_color = color.blue

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "yellow"
                        ):

                            embed_color = color.yellow

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "purple"
                        ):

                            embed_color = color.purple

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "orange"
                        ):

                            embed_color = color.orange

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "pink"
                        ):

                            embed_color = color.pink

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "cyan"
                        ):

                            embed_color = color.black

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "white"
                        ):

                            embed_color = color.white

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "black"
                        ):

                            embed_color = color.black

                        elif (
                            str(welcomer_cache.get("welcome_embed_color")).lower()
                            == "gray"
                        ):

                            embed_color = color.gray

                        else:

                            embed_color = discord.Color.blurple()

                    if welcomer_cache.get("welcome_embed"):

                        embed = discord.Embed(
                            title=fetch_variables(
                                text=welcomer_cache.get("welcome_embed_title"),
                                member=ctx.author,
                                guild=ctx.guild,
                            ),
                            description=fetch_variables(
                                text=welcomer_cache.get("welcome_embed_description"),
                                member=ctx.author,
                                guild=ctx.guild,
                            ),
                            color=embed_color,
                        )

                        if welcomer_cache.get("welcome_embed_thumbnail"):

                            embed.set_thumbnail(
                                url=fetch_variables(
                                    text=welcomer_cache.get("welcome_embed_thumbnail"),
                                    member=ctx.author,
                                    guild=ctx.guild,
                                )
                            )

                        if welcomer_cache.get("welcome_embed_image"):

                            embed.set_image(
                                url=fetch_variables(
                                    text=welcomer_cache.get("welcome_embed_image"),
                                    member=ctx.author,
                                    guild=ctx.guild,
                                )
                            )

                        if welcomer_cache.get("welcome_embed_footer"):

                            embed.set_footer(
                                text=fetch_variables(
                                    text=welcomer_cache.get("welcome_embed_footer"),
                                    member=ctx.author,
                                    guild=ctx.guild,
                                ),
                                icon_url=fetch_variables(
                                    text=welcomer_cache.get(
                                        "welcome_embed_footer_icon"
                                    ),
                                    member=ctx.author,
                                    guild=ctx.guild,
                                ),
                            )

                        if welcomer_cache.get("welcome_embed_author"):

                            embed.set_author(
                                name=fetch_variables(
                                    text=welcomer_cache.get("welcome_embed_author"),
                                    member=ctx.author,
                                    guild=ctx.guild,
                                ),
                                icon_url=fetch_variables(
                                    text=welcomer_cache.get(
                                        "welcome_embed_author_icon"
                                    ),
                                    member=ctx.author,
                                    guild=ctx.guild,
                                ),
                                url=fetch_variables(
                                    text=welcomer_cache.get("welcome_embed_author_url"),
                                    member=ctx.author,
                                    guild=ctx.guild,
                                ),
                            )

                    else:

                        embed = None

                    preview_message = await interaction.followup.send(
                        content=message_content, embed=embed, ephemeral=True
                    )

                    await asyncio.sleep(30)

                    try:

                        await preview_message.delete()

                    except Exception:
                        pass

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    nonlocal cancled

                    cancled = True

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def enable_disable_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    await storage.welcomer_settings.update(
                        id=welcomer_cache.get("id"),
                        guild_id=ctx.guild.id,
                        welcome=not welcomer_cache.get("welcome"),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            async def select_type_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    value = interaction.data["values"][0]

                    if value == "message_and_embed":

                        await storage.welcomer_settings.update(
                            id=welcomer_cache.get("id"),
                            guild_id=ctx.guild.id,
                            welcome_message=True,
                            welcome_embed=True,
                        )

                    elif value == "message":

                        await storage.welcomer_settings.update(
                            id=welcomer_cache.get("id"),
                            guild_id=ctx.guild.id,
                            welcome_message=True,
                            welcome_embed=False,
                        )

                    elif value == "embed":

                        await storage.welcomer_settings.update(
                            id=welcomer_cache.get("id"),
                            guild_id=ctx.guild.id,
                            welcome_message=False,
                            welcome_embed=True,
                        )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            async def channel_select_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    channel = interaction.data["values"][0]

                    await storage.welcomer_settings.update(
                        id=welcomer_cache.get("id"),
                        guild_id=ctx.guild.id,
                        welcome_channel=int(channel),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            async def edit_message_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    async def get_message_edit_embed():

                        try:

                            welcomer_cache = cache.welcomer_settings.get(
                                str(ctx.guild.id), {}
                            )

                            embed = discord.Embed(
                                title="แก้ไขข้อความต้อนรับ",
                                description="แก้ไขข้อความต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
                                color=color.green,
                            )

                            embed.description += f"\n\n**Message:**\n```{welcomer_cache.get('welcome_message_content') or 'No message set'}```"

                            embed.description += f"\n\n**These are the self.bot.variables you can use in your message:**\n```fix\n{self.variables_text}```"

                            _gid = getattr(getattr(ctx, "guild", None), "id", None)

                            embed.set_footer(
                                text=f"{i18n.tr('requested_by', _gid)} {ctx.author}",
                                icon_url=ctx.author.display_avatar.url,
                            )

                            embed.set_thumbnail(
                                url=(
                                    ctx.guild.icon.url
                                    if ctx.guild.icon
                                    else self.bot.user.display_avatar.url
                                )
                            )

                            return embed

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                            return None

                    async def get_message_edit_view():

                        try:

                            welcomer_cache = cache.welcomer_settings.get(
                                str(ctx.guild.id), {}
                            )

                            view = discord.ui.View(timeout=200)

                            reset_timeout()

                            edit_message_content_button = discord.ui.Button(
                                label="Edit Message Content",
                                style=discord.ButtonStyle.primary,
                                emoji=self.bot.emoji.EDIT,
                                row=0,
                            )

                            edit_message_content_button.callback = (
                                lambda i: edit_message_content_button_callback(i)
                            )

                            view.add_item(edit_message_content_button)

                            back_button = discord.ui.Button(
                                label="Back to Welcomer",
                                style=discord.ButtonStyle.gray,
                                emoji=self.bot.emoji.BACK,
                                row=1,
                            )

                            back_button.callback = lambda i: back_button_callback(i)

                            view.add_item(back_button)

                            return view

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                            return None

                    async def edit_message_content_button_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            class edit_message_content_modal(
                                discord.ui.Modal, title="แก้ไขเนื้อหาข้อความ"
                            ):

                                try:

                                    new_content = discord.ui.TextInput(
                                        label="Enter the new message content",
                                        placeholder="Enter the new message content",
                                        style=discord.TextStyle.long,
                                        required=True,
                                        row=0,
                                        default=(
                                            fetch_line(
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                ).get("welcome_message_content")
                                            )
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_message_content")
                                            else ""
                                        ),
                                    )

                                    async def on_submit(
                                        self, interaction: discord.Interaction
                                    ):

                                        try:

                                            if ctx.author.id != interaction.user.id:

                                                return await interaction.response.send_message(
                                                    embed=discord.Embed(
                                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                            await interaction.response.defer()

                                            welcomer_cache = (
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                )
                                            )

                                            await storage.welcomer_settings.update(
                                                id=welcomer_cache.get("id"),
                                                guild_id=ctx.guild.id,
                                                welcome_message_content=self.new_content.value,
                                            )

                                            await interaction.message.edit(
                                                embed=await get_message_edit_embed(),
                                                view=await get_message_edit_view(),
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                            )

                                except Exception as e:

                                    logger.error(
                                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                    )

                            await interaction.response.send_modal(
                                edit_message_content_modal()
                            )

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def back_button_callback(interaction: discord.Interaction):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            await interaction.response.defer()

                            await interaction.message.edit(
                                embed=await get_embed(), view=await get_view()
                            )

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    embed = await get_message_edit_embed()

                    view = await get_message_edit_view()

                    await interaction.message.edit(embed=embed, view=view)

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            async def edit_embed_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    async def get_embed_edit_embed():

                        try:

                            welcomer_cache = cache.welcomer_settings.get(
                                str(ctx.guild.id), {}
                            )

                            embed = discord.Embed(
                                title="แก้ไข Welcome Embed",
                                description="แก้ไข Welcome Embed สำหรับเซิร์ฟเวอร์ของคุณ",
                                color=color.green,
                            )

                            embed_color = "⬛"

                            if welcomer_cache.get("welcome_embed_color"):

                                if (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "red"
                                ):

                                    embed_color = self.bot.emoji.RED

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "green"
                                ):

                                    embed_color = self.bot.emoji.GREEN

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "blue"
                                ):

                                    embed_color = self.bot.emoji.BLUE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "yellow"
                                ):

                                    embed_color = self.bot.emoji.YELLOW

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "purple"
                                ):

                                    embed_color = self.bot.emoji.PURPLE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "pink"
                                ):

                                    embed_color = self.bot.emoji.PINK

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "orange"
                                ):

                                    embed_color = self.bot.emoji.ORANGE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "black"
                                ):

                                    embed_color = self.bot.emoji.BLACK

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "white"
                                ):

                                    embed_color = self.bot.emoji.WHITE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "gray"
                                ):

                                    embed_color = self.bot.emoji.GRAY

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "cyan"
                                ):

                                    embed_color = self.bot.emoji.CYAN

                            thumbnail_url = "`No thumbnail set`"

                            if welcomer_cache.get("welcome_embed_thumbnail"):

                                if (
                                    str(
                                        welcomer_cache.get("welcome_embed_thumbnail")
                                    ).lower()
                                    in self.bot.variables.keys()
                                ):

                                    thumbnail_url = f"`{welcomer_cache.get('welcome_embed_thumbnail')}`"

                                else:

                                    thumbnail_url = f"[Thumbnail]({welcomer_cache.get('welcome_embed_thumbnail')})"

                            image_url = "`No image set`"

                            if welcomer_cache.get("welcome_embed_image"):

                                if (
                                    str(
                                        welcomer_cache.get("welcome_embed_image")
                                    ).lower()
                                    in self.bot.variables.keys()
                                ):

                                    image_url = (
                                        f"`{welcomer_cache.get('welcome_embed_image')}`"
                                    )

                                else:

                                    image_url = f"[Image]({welcomer_cache.get('welcome_embed_image')})"

                            footer_icon_url = "`No footer icon set`"

                            if welcomer_cache.get("welcome_embed_footer_icon"):

                                if (
                                    str(
                                        welcomer_cache.get("welcome_embed_footer_icon")
                                    ).lower()
                                    in self.bot.variables.keys()
                                ):

                                    footer_icon_url = f"`{welcomer_cache.get('welcome_embed_footer_icon')}`"

                                else:

                                    footer_icon_url = f"[Footer Icon]({welcomer_cache.get('welcome_embed_footer_icon')})"

                            author_icon_url = "`No author icon set`"

                            if welcomer_cache.get("welcome_embed_author_icon"):

                                if (
                                    str(
                                        welcomer_cache.get("welcome_embed_author_icon")
                                    ).lower()
                                    in self.bot.variables.keys()
                                ):

                                    author_icon_url = f"`{welcomer_cache.get('welcome_embed_author_icon')}`"

                                else:

                                    author_icon_url = f"[Author Icon]({welcomer_cache.get('welcome_embed_author_icon')})"

                            author_url = "`No author url set`"

                            if welcomer_cache.get("welcome_embed_author_url"):

                                if (
                                    str(
                                        welcomer_cache.get("welcome_embed_author_url")
                                    ).lower()
                                    in self.bot.variables.keys()
                                ):

                                    author_url = f"`{welcomer_cache.get('welcome_embed_author_url')}`"

                                else:

                                    author_url = f"[Author URL]({welcomer_cache.get('welcome_embed_author_url')})"

                            embed.description += f"\n\n**These are the self.bot.variables you can use in your embed:**\n```fix\n{self.variables_text}```\n\n**Current Embed Data:**"

                            # embed.description += f"\n\n**Title:** `{welcomer_cache.get('welcome_embed_title') or 'No title set'}`"

                            # embed.description += f"\n**Description:** {f'```\n{welcomer_cache.get('welcome_embed_description')}```' if welcomer_cache.get('welcome_embed_description') else '`No description set`'}"

                            # embed.description += f"\n**Thumbnail:** {thumbnail_url}"

                            # embed.description += f"\n**Image:** {image_url}"

                            # embed.description += f"\n**Footer Text:** `{welcomer_cache.get('welcome_embed_footer') or 'No footer set'}`"

                            # embed.description += f"\n**Footer Icon:** {footer_icon_url}"

                            # embed.description += f"\n**Color:** {embed_color}"

                            # embed.description += f"\n**Author Text:** `{welcomer_cache.get('welcome_embed_author') or 'No author set'}`"

                            # embed.description += f"\n**Author Icon:** {author_icon_url}"

                            # embed.description += f"\n**Author URL:** {author_url}"

                            embed.add_field(
                                name=f"{self.bot.emoji.ENABLED if welcomer_cache.get('welcome_embed') else self.bot.emoji.DISABLED} - Embed",
                                value=(
                                    "Enabled"
                                    if welcomer_cache.get("welcome_embed")
                                    else "Disabled"
                                ),
                                inline=True,
                            )

                            embed.add_field(
                                name=f"Embed Title",
                                value=f"`{welcomer_cache.get('welcome_embed_title') or 'No title set'}`",
                                inline=True,
                            )

                            embed.add_field(name="", value="", inline=False)

                            embed.add_field(
                                name="Embed Description",
                                value=f"```{welcomer_cache.get('welcome_embed_description') or 'No description set'}```",
                                inline=True,
                            )

                            embed.add_field(
                                name="Embed Thumbnail", value=thumbnail_url, inline=True
                            )

                            embed.add_field(
                                name="Embed Image", value=image_url, inline=True
                            )

                            embed.add_field(name="", value="", inline=False)

                            embed.add_field(
                                name="Embed Footer Text",
                                value=f"`{welcomer_cache.get('welcome_embed_footer') or 'No footer set'}`",
                                inline=True,
                            )

                            embed.add_field(
                                name="Embed Footer Icon",
                                value=footer_icon_url,
                                inline=True,
                            )

                            if welcomer_cache.get("welcome_embed_color"):

                                if (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "red"
                                ):

                                    embed_color = self.bot.emoji.RED

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "green"
                                ):

                                    embed_color = self.bot.emoji.GREEN

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "blue"
                                ):

                                    embed_color = self.bot.emoji.BLUE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "yellow"
                                ):

                                    embed_color = self.bot.emoji.YELLOW

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "purple"
                                ):

                                    embed_color = self.bot.emoji.PURPLE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "pink"
                                ):

                                    embed_color = self.bot.emoji.PINK

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "orange"
                                ):

                                    embed_color = self.bot.emoji.ORANGE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "black"
                                ):

                                    embed_color = self.bot.emoji.BLACK

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "white"
                                ):

                                    embed_color = self.bot.emoji.WHITE

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "gray"
                                ):

                                    embed_color = self.bot.emoji.GRAY

                                elif (
                                    str(
                                        welcomer_cache.get("welcome_embed_color")
                                    ).lower()
                                    == "cyan"
                                ):

                                    embed_color = self.bot.emoji.CYAN

                                else:

                                    embed_color = None

                            embed.add_field(
                                name="Color",
                                value=f"`{embed_color or 'No color set'}`",
                                inline=True,
                            )

                            embed.add_field(name="", value="", inline=False)

                            embed.add_field(
                                name="Embed Author Text",
                                value=f"`{welcomer_cache.get('welcome_embed_author') or 'No author set'}`",
                                inline=True,
                            )

                            embed.add_field(
                                name="Embed Author Icon",
                                value=author_icon_url,
                                inline=True,
                            )

                            embed.add_field(
                                name="Embed Author URL", value=author_url, inline=True
                            )

                            embed.set_footer(
                                text=f"SkylineBOT | Skyline Development",
                                icon_url=self.bot.user.display_avatar.url,
                            )

                            embed.set_thumbnail(
                                url=(
                                    ctx.guild.icon.url
                                    if ctx.guild.icon
                                    else self.bot.user.display_avatar.url
                                )
                            )

                            return embed

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                            return None

                    async def get_embed_edit_view():

                        try:

                            welcomer_cache = cache.welcomer_settings.get(
                                str(ctx.guild.id), {}
                            )

                            view = discord.ui.View(timeout=200)

                            reset_timeout()

                            edit_title_button = discord.ui.Button(
                                label="Edit Embed Title",
                                style=discord.ButtonStyle.primary,
                                emoji=self.bot.emoji.EDIT,
                                row=0,
                            )

                            edit_title_button.callback = (
                                lambda i: edit_title_button_callback(i)
                            )

                            view.add_item(edit_title_button)

                            edit_description_button = discord.ui.Button(
                                label="Edit Embed Description",
                                style=discord.ButtonStyle.primary,
                                emoji=self.bot.emoji.EDIT,
                                row=0,
                            )

                            edit_description_button.callback = (
                                lambda i: edit_description_button_callback(i)
                            )

                            view.add_item(edit_description_button)

                            edit_thumbnail_button = discord.ui.Button(
                                label="Edit Embed Thumbnail",
                                style=discord.ButtonStyle.primary,
                                emoji=self.bot.emoji.EDIT,
                                row=1,
                            )

                            edit_thumbnail_button.callback = (
                                lambda i: edit_thumbnail_button_callback(i)
                            )

                            view.add_item(edit_thumbnail_button)

                            edit_image_button = discord.ui.Button(
                                label="Edit Embed Image",
                                style=discord.ButtonStyle.primary,
                                emoji=self.bot.emoji.EDIT,
                                row=1,
                            )

                            edit_image_button.callback = (
                                lambda i: edit_image_button_callback(i)
                            )

                            view.add_item(edit_image_button)

                            edit_color_select = discord.ui.Select(
                                placeholder="Select the embed color",
                                options=[
                                    discord.SelectOption(
                                        label="Red",
                                        value="red",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "red"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.RED,
                                    ),
                                    discord.SelectOption(
                                        label="Green",
                                        value="green",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "green"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.GREEN,
                                    ),
                                    discord.SelectOption(
                                        label="Blue",
                                        value="blue",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "blue"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.BLUE,
                                    ),
                                    discord.SelectOption(
                                        label="Yellow",
                                        value="yellow",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "yellow"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.YELLOW,
                                    ),
                                    discord.SelectOption(
                                        label="Purple",
                                        value="purple",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "purple"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.PURPLE,
                                    ),
                                    discord.SelectOption(
                                        label="Pink",
                                        value="pink",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "pink"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.PINK,
                                    ),
                                    discord.SelectOption(
                                        label="Orange",
                                        value="orange",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "orange"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.ORANGE,
                                    ),
                                    discord.SelectOption(
                                        label="Black",
                                        value="black",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "black"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.BLACK,
                                    ),
                                    discord.SelectOption(
                                        label="White",
                                        value="white",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "white"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.WHITE,
                                    ),
                                    discord.SelectOption(
                                        label="Gray",
                                        value="gray",
                                        default=(
                                            True
                                            if welcomer_cache.get("welcome_embed_color")
                                            == "gray"
                                            else False
                                        ),
                                        emoji=self.bot.emoji.GRAY,
                                    ),
                                ],
                                row=2,
                                max_values=1,
                                min_values=1,
                            )

                            edit_color_select.callback = (
                                lambda i: edit_color_select_callback(i)
                            )

                            view.add_item(edit_color_select)

                            edit_author_button = discord.ui.Button(
                                label="Edit Author",
                                style=discord.ButtonStyle.primary,
                                emoji=self.bot.emoji.EDIT,
                                row=3,
                            )

                            edit_author_button.callback = (
                                lambda i: edit_author_button_callback(i)
                            )

                            view.add_item(edit_author_button)

                            edit_footer_button = discord.ui.Button(
                                label="Edit Footer",
                                style=discord.ButtonStyle.primary,
                                emoji=self.bot.emoji.EDIT,
                                row=3,
                            )

                            edit_footer_button.callback = (
                                lambda i: edit_footer_button_callback(i)
                            )

                            view.add_item(edit_footer_button)

                            back_button = discord.ui.Button(
                                label="Back to Welcomer",
                                style=discord.ButtonStyle.gray,
                                emoji=self.bot.emoji.BACK,
                                row=4,
                            )

                            back_button.callback = lambda i: back_button_callback(i)

                            view.add_item(back_button)

                            return view

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                            return None

                    async def edit_title_button_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            class edit_title_modal(
                                discord.ui.Modal, title="แก้ไขชื่อเรื่อง"
                            ):

                                try:

                                    new_title = discord.ui.TextInput(
                                        label="Enter the new title",
                                        placeholder="Enter the new title",
                                        required=False,
                                        style=discord.TextStyle.short,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_title")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_title")
                                            else ""
                                        ),
                                    )

                                    async def on_submit(
                                        self, interaction: discord.Interaction
                                    ):

                                        try:

                                            if ctx.author.id != interaction.user.id:

                                                return await interaction.response.send_message(
                                                    embed=discord.Embed(
                                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                            await interaction.response.defer()

                                            welcomer_cache = (
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                )
                                            )

                                            await storage.welcomer_settings.update(
                                                id=welcomer_cache.get("id"),
                                                guild_id=ctx.guild.id,
                                                welcome_embed_title=self.new_title.value,
                                            )

                                            await interaction.message.edit(
                                                embed=await get_embed_edit_embed(),
                                                view=await get_embed_edit_view(),
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                            )

                                except Exception as e:

                                    logger.error(
                                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                    )

                            await interaction.response.send_modal(edit_title_modal())

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def edit_description_button_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            class edit_description_modal(
                                discord.ui.Modal, title="แก้ไขคำอธิบาย"
                            ):

                                try:

                                    new_description = discord.ui.TextInput(
                                        label="Enter the new description",
                                        placeholder="Enter the new description",
                                        required=False,
                                        style=discord.TextStyle.long,
                                        row=0,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_description")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_description")
                                            else ""
                                        ),
                                    )

                                    async def on_submit(
                                        self, interaction: discord.Interaction
                                    ):

                                        try:

                                            if ctx.author.id != interaction.user.id:

                                                return await interaction.response.send_message(
                                                    embed=discord.Embed(
                                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                            await interaction.response.defer()

                                            welcomer_cache = (
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                )
                                            )

                                            await storage.welcomer_settings.update(
                                                id=welcomer_cache.get("id"),
                                                guild_id=ctx.guild.id,
                                                welcome_embed_description=self.new_description.value,
                                            )

                                            await interaction.message.edit(
                                                embed=await get_embed_edit_embed(),
                                                view=await get_embed_edit_view(),
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                            )

                                except Exception as e:

                                    logger.error(
                                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                    )

                            await interaction.response.send_modal(
                                edit_description_modal()
                            )

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def edit_thumbnail_button_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            class edit_thumbnail_modal(
                                discord.ui.Modal, title="แก้ไขภาพขนาดย่อ"
                            ):

                                try:

                                    new_thumbnail = discord.ui.TextInput(
                                        label="Enter the new thumbnail",
                                        placeholder="Enter the new thumbnail",
                                        style=discord.TextStyle.short,
                                        required=False,
                                        row=0,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_thumbnail")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_thumbnail")
                                            else ""
                                        ),
                                    )

                                    async def on_submit(
                                        self, interaction: discord.Interaction
                                    ):

                                        try:

                                            if ctx.author.id != interaction.user.id:

                                                return await interaction.response.send_message(
                                                    embed=discord.Embed(
                                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                            await interaction.response.defer()

                                            welcomer_cache = (
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                )
                                            )

                                            new_thumbnail = self.new_thumbnail.value

                                            if new_thumbnail and not check_image_url(
                                                new_thumbnail
                                            ):

                                                temp_message = await interaction.followup.send(
                                                    embed=discord.Embed(
                                                        description="ลิงก์รูปภาพไม่ถูกต้อง",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                                await asyncio.sleep(5)

                                                try:

                                                    await temp_message.delete()

                                                except Exception:
                                                    pass

                                                return

                                            await storage.welcomer_settings.update(
                                                id=welcomer_cache.get("id"),
                                                guild_id=ctx.guild.id,
                                                welcome_embed_thumbnail=new_thumbnail,
                                            )

                                            await interaction.message.edit(
                                                embed=await get_embed_edit_embed(),
                                                view=await get_embed_edit_view(),
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                            )

                                except Exception as e:

                                    logger.error(
                                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                    )

                            await interaction.response.send_modal(
                                edit_thumbnail_modal()
                            )

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def edit_image_button_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            class edit_image_modal(
                                discord.ui.Modal, title="แก้ไขรูปภาพ"
                            ):

                                try:

                                    new_image = discord.ui.TextInput(
                                        label="Enter the new image",
                                        placeholder="Must be a valid image url or image variable",
                                        style=discord.TextStyle.short,
                                        required=False,
                                        row=0,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_image")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_image")
                                            else ""
                                        ),
                                    )

                                    async def on_submit(
                                        self, interaction: discord.Interaction
                                    ):

                                        try:

                                            if ctx.author.id != interaction.user.id:

                                                return await interaction.response.send_message(
                                                    embed=discord.Embed(
                                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                            await interaction.response.defer()

                                            welcomer_cache = (
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                )
                                            )

                                            new_image = self.new_image.value

                                            if new_image and not check_image_url(
                                                new_image
                                            ):

                                                temp_message = await interaction.followup.send(
                                                    embed=discord.Embed(
                                                        description="ลิงก์รูปภาพไม่ถูกต้อง",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                                await asyncio.sleep(5)

                                                try:

                                                    await temp_message.delete()

                                                except Exception:
                                                    pass

                                                return

                                            await storage.welcomer_settings.update(
                                                id=welcomer_cache.get("id"),
                                                guild_id=ctx.guild.id,
                                                welcome_embed_image=new_image,
                                            )

                                            await interaction.message.edit(
                                                embed=await get_embed_edit_embed(),
                                                view=await get_embed_edit_view(),
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                            )

                                except Exception as e:

                                    logger.error(
                                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                    )

                            await interaction.response.send_modal(edit_image_modal())

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def edit_footer_button_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            class edit_footer_modal(
                                discord.ui.Modal, title="แก้ไขส่วนท้าย"
                            ):

                                try:

                                    new_footer = discord.ui.TextInput(
                                        label="Enter the new footer text",
                                        placeholder="Enter the new footer text",
                                        required=False,
                                        style=discord.TextStyle.short,
                                        row=0,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_footer")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_footer")
                                            else ""
                                        ),
                                    )

                                    new_footer_icon = discord.ui.TextInput(
                                        label="Enter the new footer icon",
                                        placeholder="Must be a valid image url or image variable",
                                        required=False,
                                        style=discord.TextStyle.short,
                                        row=1,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_footer_icon")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_footer_icon")
                                            else ""
                                        ),
                                    )

                                    async def on_submit(
                                        self, interaction: discord.Interaction
                                    ):

                                        try:

                                            if ctx.author.id != interaction.user.id:

                                                return await interaction.response.send_message(
                                                    embed=discord.Embed(
                                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                            await interaction.response.defer()

                                            welcomer_cache = (
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                )
                                            )

                                            new_footer_icon = self.new_footer_icon.value

                                            new_footer_text = self.new_footer.value

                                            if new_footer_icon and not check_image_url(
                                                new_footer_icon
                                            ):

                                                temp_message = await interaction.followup.send(
                                                    embed=discord.Embed(
                                                        description="ลิงก์รูปภาพไม่ถูกต้อง",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                                await asyncio.sleep(5)

                                                try:

                                                    await temp_message.delete()

                                                except Exception:
                                                    pass

                                                return

                                            await storage.welcomer_settings.update(
                                                id=welcomer_cache.get("id"),
                                                guild_id=ctx.guild.id,
                                                welcome_embed_footer=new_footer_text,
                                                welcome_embed_footer_icon=new_footer_icon,
                                            )

                                            await interaction.message.edit(
                                                embed=await get_embed_edit_embed(),
                                                view=await get_embed_edit_view(),
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                            )

                                except Exception as e:

                                    logger.error(
                                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                    )

                            await interaction.response.send_modal(edit_footer_modal())

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def edit_color_select_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            await interaction.response.defer()

                            welcomer_cache = cache.welcomer_settings.get(
                                str(ctx.guild.id), {}
                            )

                            color = interaction.data["values"][0]

                            await storage.welcomer_settings.update(
                                id=welcomer_cache.get("id"),
                                guild_id=ctx.guild.id,
                                welcome_embed_color=color,
                            )

                            await interaction.message.edit(
                                embed=await get_embed_edit_embed(),
                                view=await get_embed_edit_view(),
                            )

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def edit_author_button_callback(
                        interaction: discord.Interaction,
                    ):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            class edit_author_modal(
                                discord.ui.Modal, title="แก้ไขผู้เขียน"
                            ):

                                try:

                                    new_author = discord.ui.TextInput(
                                        label="Enter the new author name",
                                        placeholder="Enter the new author name",
                                        required=False,
                                        style=discord.TextStyle.short,
                                        row=0,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_author")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_author")
                                            else ""
                                        ),
                                    )

                                    new_author_icon = discord.ui.TextInput(
                                        label="Enter the new author icon",
                                        placeholder="Must be a valid image url or image variable",
                                        required=False,
                                        style=discord.TextStyle.short,
                                        row=1,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_author_icon")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_author_icon")
                                            else ""
                                        ),
                                    )

                                    new_author_url = discord.ui.TextInput(
                                        label="Enter the new author url",
                                        placeholder="Enter the new author url",
                                        required=False,
                                        style=discord.TextStyle.short,
                                        row=2,
                                        default=fetch_line(
                                            cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_author_url")
                                            if cache.welcomer_settings.get(
                                                str(ctx.guild.id), {}
                                            ).get("welcome_embed_author_url")
                                            else ""
                                        ),
                                    )

                                    async def on_submit(
                                        self, interaction: discord.Interaction
                                    ):

                                        try:

                                            if ctx.author.id != interaction.user.id:

                                                return await interaction.response.send_message(
                                                    embed=discord.Embed(
                                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                            await interaction.response.defer()

                                            welcomer_cache = (
                                                cache.welcomer_settings.get(
                                                    str(ctx.guild.id), {}
                                                )
                                            )

                                            new_author = self.new_author.value

                                            new_author_icon = self.new_author_icon.value

                                            new_author_url = self.new_author_url.value

                                            if new_author_icon and not check_image_url(
                                                new_author_icon
                                            ):

                                                temp_message = await interaction.followup.send(
                                                    embed=discord.Embed(
                                                        description="ลิงก์รูปภาพไม่ถูกต้อง",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                                await asyncio.sleep(5)

                                                try:

                                                    await temp_message.delete()

                                                except Exception:
                                                    pass

                                                return

                                            if new_author_url and not check_image_url(
                                                new_author_url
                                            ):

                                                temp_message = await interaction.followup.send(
                                                    embed=discord.Embed(
                                                        description="ลิงก์รูปภาพไม่ถูกต้อง",
                                                        color=color.red,
                                                    ),
                                                    ephemeral=True,
                                                )

                                                await asyncio.sleep(5)

                                                try:

                                                    await temp_message.delete()

                                                except Exception:
                                                    pass

                                                return

                                            await storage.welcomer_settings.update(
                                                id=welcomer_cache.get("id"),
                                                guild_id=ctx.guild.id,
                                                welcome_embed_author=new_author,
                                                welcome_embed_author_icon=new_author_icon,
                                                welcome_embed_author_url=new_author_url,
                                            )

                                            await interaction.message.edit(
                                                embed=await get_embed_edit_embed(),
                                                view=await get_embed_edit_view(),
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                            )

                                except Exception as e:

                                    logger.error(
                                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                    )

                            await interaction.response.send_modal(edit_author_modal())

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    async def back_button_callback(interaction: discord.Interaction):

                        try:

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            await interaction.response.defer()

                            await interaction.message.edit(
                                embed=await get_embed(), view=await get_view()
                            )

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                            )

                    embed = await get_embed_edit_embed()

                    view = await get_embed_edit_view()

                    await interaction.message.edit(embed=embed, view=view)

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            embed = await get_embed()

            view = await get_view()

            message = await ctx.send(embed=embed, view=view)

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(view=None)

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @commands.hybrid_group(
        name="autorole",
        help="ตั้งค่ายศอัตโนมัติสำหรับเซิร์ฟเวอร์ของคุณ",
        aliases=["autoroles"],
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def autorole(self, ctx):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):

                return

            await self.command_flow.send_group_help(
                ctx,
                title="คำสั่ง Autorole",
                description="นี่คือคำสั่ง Autorole",
                accent_color=color.green,
                footer_text="SkylineBOT | Skyline Development",
                include_options_hint=True,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @autorole.command(
        name="setup",
        help="ตั้งค่าการตั้งค่ายศอัตโนมัติสำหรับเซิร์ฟเวอร์ของคุณ",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def autorole_settings(self, ctx):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):

                return

            await self.welcomer_repo.ensure_settings(ctx.guild.id)

            async def get_embed():

                welcomer_cache = await self._get_welcomer_cache(ctx.guild.id)

                embed = discord.Embed(
                    title="ตั้งค่า Autorole",
                    description="ตั้งค่า Autorole สำหรับเซิร์ฟเวอร์ของคุณ",
                    color=color.green if welcomer_cache.get("autorole") else color.red,
                )

                embed.description += f"\n\n**Status:** {self.bot.emoji.ENABLED if welcomer_cache.get('autorole') else self.bot.emoji.DISABLED}"

                embed.description += f"\n**Limit:** `{welcomer_cache.get('autoroles_limit') or 'ไม่จำกัด'}`"

                autoroles = parse_json_list(welcomer_cache.get("autoroles", []))
                embed.description += f"\n**Roles:** {', '.join([role.mention for role in ctx.guild.roles if str(role.id) in autoroles]) if autoroles else 'No roles set'}"

                embed.description += "```prolog\n Any role with administrator permissions will not be given to the New Member.```"

                _gid = getattr(getattr(ctx, "guild", None), "id", None)

                embed.set_footer(
                    text=f"{i18n.tr('requested_by', _gid)} {ctx.author}",
                    icon_url=ctx.author.display_avatar.url,
                )

                embed.set_thumbnail(
                    url=(
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    )
                )

                return embed

            timeout_time = 200

            cancled = False

            def reset_timeout(timeout: int = 200):

                nonlocal timeout_time

                timeout_time = timeout

            async def get_view(disabled=False):

                try:

                    reset_timeout()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    view = discord.ui.View(timeout=200)

                    enable_disable_button = discord.ui.Button(
                        label=(
                            "Click To Enable"
                            if not welcomer_cache.get("autorole")
                            else "Click To Disable"
                        ),
                        style=(
                            discord.ButtonStyle.green
                            if not welcomer_cache.get("autorole")
                            else discord.ButtonStyle.gray
                        ),
                        emoji=(
                            self.bot.emoji.ENABLED
                            if not welcomer_cache.get("autorole")
                            else self.bot.emoji.DISABLED
                        ),
                        row=0,
                    )

                    autoroles_sorted = parse_json_list(
                        welcomer_cache.get("autoroles", [])
                    )

                    autoroles_sorted = (
                        autoroles_sorted[
                            : int(welcomer_cache.get("autoroles_limit", 1) or 1)
                        ]
                        if welcomer_cache.get("autoroles_limit", 1) != 0
                        else autoroles_sorted
                    )

                    roles_select = discord.ui.RoleSelect(
                        placeholder=f"Select the roles to set as autorole",
                        min_values=1,
                        max_values=(
                            int(welcomer_cache.get("autoroles_limit", 1) or 1)
                            if welcomer_cache.get("autoroles_limit", 1) != 0
                            else 25
                        ),
                        default_values=[
                            discord.Object(id=int(role))
                            for role in autoroles_sorted
                            if str(role).isdigit()
                        ],
                        row=1,
                    )

                    cancle_button = discord.ui.Button(
                        label="ปิดเมนู",
                        style=discord.ButtonStyle.gray,
                        emoji=self.bot.emoji.CANCLED,
                        row=2,
                    )

                    enable_disable_button.callback = (
                        lambda i: enable_disable_button_callback(i)
                    )

                    roles_select.callback = lambda i: roles_select_callback(i)

                    cancle_button.callback = lambda i: cancle_button_callback(i)

                    view.add_item(enable_disable_button)

                    view.add_item(roles_select)

                    view.add_item(cancle_button)

                    if disabled:

                        for item in view.children:

                            item.disabled = True

                    return view

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

                    return None

            async def enable_disable_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    await storage.welcomer_settings.update(
                        id=welcomer_cache.get("id"),
                        guild_id=ctx.guild.id,
                        autorole=not welcomer_cache.get("autorole"),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def roles_select_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    roles = interaction.data["values"]

                    await storage.welcomer_settings.update(
                        id=welcomer_cache.get("id"),
                        guild_id=ctx.guild.id,
                        autoroles=json.dumps(roles),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    nonlocal cancled

                    cancled = True

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            embed = await get_embed()

            view = await get_view()

            message = await ctx.send(embed=embed, view=view)

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @autorole.command(
        name="set",
        help="ตั้งยศสำหรับแจกอัตโนมัติให้สมาชิกใหม่",
        with_app_command=True,
    )
    @app_commands.describe(role="Role to auto-give when new members join")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def autorole_set(self, ctx, role: discord.Role):

        try:
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return

            await self.welcomer_repo.ensure_settings(ctx.guild.id)
            welcomer_cache = await self._get_welcomer_cache(ctx.guild.id)
            if not welcomer_cache:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่สามารถโหลดการตั้งค่า Autorole ได้",
                        color=color.red,
                    )
                )

            if role.permissions.administrator:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่สามารถตั้งยศที่มีสิทธิ์ Administrator เป็น Autorole ได้",
                        color=color.red,
                    )
                )

            me = getattr(ctx.guild, "me", None)
            if me and int(me.top_role.position) <= int(role.position):
                return await ctx.send(
                    embed=discord.Embed(
                        description="ยศบอทต้องสูงกว่ายศที่ต้องการตั้ง Autorole",
                        color=color.red,
                    )
                )

            current_roles = [
                str(role_id)
                for role_id in parse_json_list(welcomer_cache.get("autoroles", []))
                if str(role_id).isdigit()
            ]
            current_roles = [role_id for role_id in current_roles if role_id != str(role.id)]
            current_roles.insert(0, str(role.id))

            try:
                limit = int(welcomer_cache.get("autoroles_limit", 1) or 1)
            except Exception:
                limit = 1
            if limit != 0:
                current_roles = current_roles[: max(1, limit)]

            await self.welcomer_repo.update_settings(
                ctx.guild.id,
                autorole=True,
                autoroles=json.dumps(current_roles),
            )

            enabled_roles_text = ", ".join(
                role_obj.mention
                for role_obj in ctx.guild.roles
                if str(role_obj.id) in current_roles
            ) or role.mention

            await ctx.send(
                embed=discord.Embed(
                    title="อัปเดตบทบาทอัตโนมัติแล้ว",
                    description=(
                        f"Status: {self.bot.emoji.ENABLED}\n"
                        f"Primary role: {role.mention}\n"
                        f"Active roles: {enabled_roles_text}"
                    ),
                    color=color.green,
                )
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_group(
        name="autonick",
        help="ตั้งค่าชื่อเล่นอัตโนมัติสำหรับเซิร์ฟเวอร์ของคุณ",
        aliases=["autonickname"],
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def autonick(self, ctx):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):

                return

            await self.command_flow.send_group_help(
                ctx,
                title="คำสั่ง AutoNick",
                description="นี่คือคำสั่ง AutoNick",
                accent_color=color.green,
                footer_text="SkylineBOT | Skyline Development",
                include_options_hint=True,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @autonick.command(
        name="setup",
        help="ตั้งค่าการตั้งค่าชื่อเล่นอัตโนมัติสำหรับเซิร์ฟเวอร์ของคุณ",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def autonick_settings(self, ctx):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):

                return

            await self.welcomer_repo.ensure_settings(ctx.guild.id)

            async def get_embed():

                welcomer_cache = await self._get_welcomer_cache(ctx.guild.id)

                embed = discord.Embed(
                    title="ตั้งค่า AutoNick",
                    description="ตั้งค่า AutoNick สำหรับเซิร์ฟเวอร์ของคุณ",
                    color=color.green if welcomer_cache.get("autonick") else color.red,
                )

                embed.description += f"\n\n**Status:** {self.bot.emoji.ENABLED if welcomer_cache.get('autonick') else self.bot.emoji.DISABLED}"

                embed.description += f"\n**Format:** `{welcomer_cache.get('autonick_format') or 'No format set'}`"

                embed.description += "\n\n**Variables:**\n```\n{user} - The user's name\n{tag} - The user's tag\n{guild} - The server name\n{members} - The server member count\n```"

                _gid = getattr(getattr(ctx, "guild", None), "id", None)

                embed.set_footer(
                    text=f"{i18n.tr('requested_by', _gid)} {ctx.author}",
                    icon_url=ctx.author.display_avatar.url,
                )

                embed.set_thumbnail(
                    url=(
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    )
                )

                return embed

            timeout_time = 200

            cancled = False

            def reset_timeout(timeout: int = 200):

                nonlocal timeout_time

                timeout_time = timeout

            async def get_view(disabled=False):

                try:

                    reset_timeout()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    view = discord.ui.View(timeout=200)

                    enable_disable_button = discord.ui.Button(
                        label=(
                            "Click To Enable"
                            if not welcomer_cache.get("autonick")
                            else "Click To Disable"
                        ),
                        style=(
                            discord.ButtonStyle.green
                            if not welcomer_cache.get("autonick")
                            else discord.ButtonStyle.gray
                        ),
                        emoji=(
                            self.bot.emoji.ENABLED
                            if not welcomer_cache.get("autonick")
                            else self.bot.emoji.DISABLED
                        ),
                        row=0,
                    )

                    format_inpuT_BUTTON = discord.ui.Button(
                        label="Set Format",
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.SET,
                        row=0,
                    )

                    cancle_button = discord.ui.Button(
                        label="ปิดเมนู",
                        style=discord.ButtonStyle.gray,
                        emoji=self.bot.emoji.CANCLED,
                        row=1,
                    )

                    enable_disable_button.callback = (
                        lambda i: enable_disable_button_callback(i)
                    )

                    format_inpuT_BUTTON.callback = (
                        lambda i: format_inpuT_BUTTON_callback(i)
                    )

                    cancle_button.callback = lambda i: cancle_button_callback(i)

                    view.add_item(enable_disable_button)

                    view.add_item(format_inpuT_BUTTON)

                    view.add_item(cancle_button)

                    if disabled:

                        for item in view.children:

                            item.disabled = True

                    return view

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

                    return None

            async def enable_disable_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    await storage.welcomer_settings.update(
                        id=welcomer_cache.get("id"),
                        guild_id=ctx.guild.id,
                        autonick=not welcomer_cache.get("autonick"),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def format_inpuT_BUTTON_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    class set_format_modal(discord.ui.Modal, title="กำหนดรูปแบบ"):

                        new_format = discord.ui.TextInput(
                            label="Enter the new format",
                            placeholder="Enter the new format",
                            row=0,
                            default=fetch_line(
                                cache.welcomer_settings.get(str(ctx.guild.id), {}).get(
                                    "autonick_format"
                                )
                                if cache.welcomer_settings.get(
                                    str(ctx.guild.id), {}
                                ).get("autonick_format")
                                else ""
                            ),
                        )

                        async def on_submit(self, interaction: discord.Interaction):

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            await interaction.response.defer()

                            welcomer_cache = cache.welcomer_settings.get(
                                str(ctx.guild.id), {}
                            )

                            await storage.welcomer_settings.update(
                                id=welcomer_cache.get("id"),
                                guild_id=ctx.guild.id,
                                autonick_format=self.new_format.value,
                            )

                            await interaction.message.edit(
                                embed=await get_embed(), view=await get_view()
                            )

                    await interaction.response.send_modal(set_format_modal())

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    nonlocal cancled

                    cancled = True

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            embed = await get_embed()

            view = await get_view()

            guilds_cache = cache.guilds.get(str(ctx.guild.id), {})

            if guilds_cache.get("subscription") == "free":

                view = discord.ui.View(timeout=200)

                buy_premium_to_use_button = discord.ui.Button(
                    label="Buy Premium To Use this feature",
                    style=discord.ButtonStyle.url,
                    url=SUBSCRIBE_PLAN_URL,
                    emoji=self.bot.emoji.PREMIUM,
                    disabled=False,
                )

                view.add_item(buy_premium_to_use_button)

            message = await ctx.send(embed=embed, view=view)

            if guilds_cache.get("subscription") == "free":

                return

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_group(
        name="greet",
        help="ตั้งค่าห้องและข้อความทักทายสำหรับเซิร์ฟเวอร์ของคุณ",
        aliases=["greeting"],
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def greet(self, ctx):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):

                return

            await self.command_flow.send_group_help(
                ctx,
                title="คำสั่ง Greet",
                description="นี่คือคำสั่ง Greet",
                accent_color=color.green,
                footer_text="SkylineBOT | Skyline Development",
                include_options_hint=True,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @greet.command(
        name="settings",
        help="ตั้งค่าระบบทักทายสำหรับเซิร์ฟเวอร์ของคุณ",
        aliases=["setting"],
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def greet_settings(self, ctx: commands.Context):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):

                return

            await self.welcomer_repo.ensure_settings(ctx.guild.id)

            async def get_embed():

                welcomer_cache = await self._get_welcomer_cache(ctx.guild.id)

                embed = discord.Embed(
                    title="ตั้งค่า Greet",
                    description="ตั้งค่า Greet สำหรับเซิร์ฟเวอร์ของคุณ",
                    color=color.green if welcomer_cache.get("greet") else color.red,
                )

                embed.description += f"\n\n**These are the self.bot.variables you can use in your message:**\n```fix\n{self.variables_text}```"

                embed.add_field(
                    name="Status",
                    value=f"{self.bot.emoji.ENABLED_BUNDLE if welcomer_cache.get('greet') else self.bot.emoji.DISABLED_BUNDLE}",
                    inline=True,
                )

                embed.add_field(
                    name="Channel",
                    value=(
                        ", ".join(
                            [
                                f"<#{greet_channel}>"
                                for greet_channel in parse_json_list(
                                    welcomer_cache.get("greet_channels", "[]")
                                )
                            ]
                        )
                        if parse_json_list(welcomer_cache.get("greet_channels", "[]"))
                        else "`No channel set`"
                    ),
                    inline=True,
                )

                embed.add_field(
                    name="Delete After",
                    value=f"`{welcomer_cache.get('greet_delete_after') or 'No delete after set'}sec`",
                    inline=True,
                )

                embed.add_field(
                    name="Message",
                    value=f"`{welcomer_cache.get('greet_message') or 'No message set'}`",
                    inline=False,
                )

                _gid = getattr(getattr(ctx, "guild", None), "id", None)

                embed.set_footer(
                    text=f"{i18n.tr('requested_by', _gid)} {ctx.author}",
                    icon_url=ctx.author.display_avatar.url,
                )

                embed.set_thumbnail(
                    url=(
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    )
                )

                return embed

            timeout_time = 200

            cancled = False

            def reset_timeout(timeout: int = 200):

                nonlocal timeout_time

                timeout_time = timeout

            async def get_view(disabled=False):

                try:

                    reset_timeout()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    view = discord.ui.View(timeout=200)

                    enable_disable_button = discord.ui.Button(
                        label=(
                            "Click To Enable"
                            if not welcomer_cache.get("greet")
                            else "Click To Disable"
                        ),
                        style=(
                            discord.ButtonStyle.green
                            if not welcomer_cache.get("greet")
                            else discord.ButtonStyle.gray
                        ),
                        emoji=(
                            self.bot.emoji.ENABLED
                            if not welcomer_cache.get("greet")
                            else self.bot.emoji.DISABLED
                        ),
                        row=0,
                    )

                    message_button = discord.ui.Button(
                        label="Set Message",
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.MESSAGE,
                        row=0,
                    )

                    set_delete_after_button = discord.ui.Button(
                        label="Set Delete After",
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.DELETE,
                        row=1,
                    )

                    cancle_button = discord.ui.Button(
                        label="ปิดเมนู",
                        style=discord.ButtonStyle.gray,
                        emoji=self.bot.emoji.CANCLED,
                        row=1,
                    )

                    guilds_subscription = cache.guilds.get(str(ctx.guild.id), {}).get(
                        "subscription", "free"
                    )

                    if guilds_subscription == "free":

                        greet_channel_limit = 5

                    elif guilds_subscription == "silver_guild_preminum":

                        greet_channel_limit = 7

                    elif guilds_subscription == "golden_guild_premium":

                        greet_channel_limit = 10

                    elif guilds_subscription in {"diamond_guild_premium", "permanent_guild_premium", "lifetime_guild_premium"}:

                        greet_channel_limit = 15

                    else:

                        greet_channel_limit = 5

                    greet_channels_values = parse_json_list(
                        welcomer_cache.get("greet_channels", "[]")
                    )

                    if len(greet_channels_values) > greet_channel_limit:

                        # delete from last

                        json_greet_channels = list(greet_channels_values)

                        json_greet_channels = json_greet_channels[:greet_channel_limit]

                        await storage.welcomer_settings.update(
                            id=welcomer_cache.get("id"),
                            guild_id=ctx.guild.id,
                            greet_channels=json.dumps(json_greet_channels),
                        )

                        welcomer_cache = cache.welcomer_settings.get(
                            str(ctx.guild.id), {}
                        )

                    channel_select = discord.ui.ChannelSelect(
                        placeholder="Select the channel to set as greet channel",
                        min_values=1,
                        max_values=greet_channel_limit,
                        row=2,
                        channel_types=[discord.ChannelType.text],
                        default_values=(
                            [
                                ctx.guild.get_channel(int(greet_channel))
                                for greet_channel in parse_json_list(
                                    welcomer_cache.get("greet_channels", "[]")
                                )
                                if str(greet_channel).isdigit()
                            ]
                            if parse_json_list(welcomer_cache.get("greet_channels", "[]"))
                            else []
                        ),
                    )

                    enable_disable_button.callback = (
                        lambda i: enable_disable_button_callback(i)
                    )

                    channel_select.callback = lambda i: channel_select_callback(i)

                    message_button.callback = lambda i: message_button_callback(i)

                    set_delete_after_button.callback = (
                        lambda i: set_delete_after_button_callback(i)
                    )

                    cancle_button.callback = lambda i: cancle_button_callback(i)

                    view.add_item(enable_disable_button)

                    view.add_item(channel_select)

                    view.add_item(message_button)

                    view.add_item(set_delete_after_button)

                    view.add_item(cancle_button)

                    if disabled:

                        for item in view.children:

                            item.disabled = True

                    return view

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

                    return None

            async def set_delete_after_button_callback(
                interaction: discord.Interaction,
            ):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    class set_delete_after_modal(
                        discord.ui.Modal, title="ตั้งค่าลบหลัง"
                    ):

                        new_delete_after = discord.ui.TextInput(
                            label="Enter the new delete after time",
                            placeholder="Enter the new delete after time",
                            required=False,
                            style=discord.TextStyle.short,
                            row=0,
                            default=fetch_line(
                                cache.welcomer_settings.get(str(ctx.guild.id), {}).get(
                                    "greet_delete_after"
                                )
                                if cache.welcomer_settings.get(
                                    str(ctx.guild.id), {}
                                ).get("greet_delete_after")
                                else ""
                            ),
                        )

                        async def on_submit(self, interaction: discord.Interaction):

                            try:

                                if ctx.author.id != interaction.user.id:

                                    return await interaction.response.send_message(
                                        embed=discord.Embed(
                                            description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                            color=color.red,
                                        ),
                                        ephemeral=True,
                                    )

                                try:

                                    new_delete_after = int(self.new_delete_after.value)

                                except Exception:
                                    return await interaction.response.send_message(
                                        embed=discord.Embed(
                                            description="ตัวเลขไม่ถูกต้อง",
                                            color=color.red,
                                        ),
                                        ephemeral=True,
                                        delete_after=5,
                                    )

                                if new_delete_after > 60:

                                    return await interaction.response.send_message(
                                        embed=discord.Embed(
                                            description="ตัวเลขต้องน้อยกว่า 60",
                                            color=color.red,
                                        ),
                                        ephemeral=True,
                                        delete_after=5,
                                    )

                                await interaction.response.defer()

                                welcomer_cache = cache.welcomer_settings.get(
                                    str(ctx.guild.id), {}
                                )

                                await storage.welcomer_settings.update(
                                    id=welcomer_cache.get("id"),
                                    guild_id=ctx.guild.id,
                                    greet_delete_after=new_delete_after,
                                )

                                await interaction.message.edit(
                                    embed=await get_embed(), view=await get_view()
                                )

                            except Exception as e:

                                logger.error(
                                    f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                )

                    await interaction.response.send_modal(set_delete_after_modal())

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            async def enable_disable_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    await storage.welcomer_settings.update(
                        id=welcomer_cache.get("id"),
                        guild_id=ctx.guild.id,
                        greet=not welcomer_cache.get("greet"),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def message_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    class set_message_modal(discord.ui.Modal, title="ตั้งค่าข้อความ"):

                        new_message = discord.ui.TextInput(
                            label="Enter the new message",
                            placeholder="Enter the new message",
                            row=0,
                            style=discord.TextStyle.long,
                            default=fetch_line(
                                cache.welcomer_settings.get(str(ctx.guild.id), {}).get(
                                    "greet_message"
                                )
                                if cache.welcomer_settings.get(
                                    str(ctx.guild.id), {}
                                ).get("greet_message")
                                else ""
                            ),
                        )

                        async def on_submit(self, interaction: discord.Interaction):

                            if ctx.author.id != interaction.user.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                )

                            await interaction.response.defer()

                            welcomer_cache = cache.welcomer_settings.get(
                                str(ctx.guild.id), {}
                            )

                            await storage.welcomer_settings.update(
                                id=welcomer_cache.get("id"),
                                guild_id=ctx.guild.id,
                                greet_message=self.new_message.value,
                            )

                            await interaction.message.edit(
                                embed=await get_embed(), view=await get_view()
                            )

                    await interaction.response.send_modal(set_message_modal())

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def channel_select_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    welcomer_cache = cache.welcomer_settings.get(str(ctx.guild.id), {})

                    channel = interaction.data["values"]

                    await storage.welcomer_settings.update(
                        id=welcomer_cache.get("id"),
                        guild_id=ctx.guild.id,
                        greet_channels=json.dumps(
                            [int(channel) for channel in channel]
                        ),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if ctx.author.id != interaction.user.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    nonlocal cancled

                    cancled = True

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            embed = await get_embed()

            view = await get_view()

            message = await ctx.send(embed=embed, view=view)

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )







