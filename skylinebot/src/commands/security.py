import discord


from discord.ext import commands


import traceback, sys


from skylinebot.src.checks import checks


from skylinebot.console.logging import logger


from skylinebot.style import color


import asyncio


from skylinebot.engine.bot_runtime import AutoShardedBot


from skylinebot.src.services import AntiNukeService, CommandFlow, SecurityService


class Security(commands.Cog):

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        class CogInfo:

            name = "Security"

            category = "Main"

            description = "Security commands"

            hidden = False

            emoji = self.bot.emoji.SECURITY

        self.cog_info = CogInfo
        self.command_flow = CommandFlow(bot)
        self.antinuke_service = AntiNukeService(bot)
        self.security_service = SecurityService(bot)

    async def _require_owner(self, ctx: commands.Context) -> bool:
        return await checks.check_is_owner(ctx, notify=True)

    async def _require_manage_guild(self, ctx: commands.Context) -> bool:
        return await checks.check_is_moderator_permissions(ctx, "manage_guild")

    async def _require_extra_owner_manager(self, ctx: commands.Context) -> bool:
        if ctx.author == ctx.guild.owner or checks.check_is_owner_predicate(ctx):
            return True
        await ctx.send(
            embed=discord.Embed(
                description="คุณต้องเป็นเจ้าของเซิร์ฟเวอร์จึงจะจัดการเจ้าของเพิ่มเติมได้",
                color=color.red,
            ),
            delete_after=10,
        )
        return False

    def _security_error_embed(self, description: str) -> discord.Embed:
        return discord.Embed(
            description=f"{self.bot.emoji.ERROR} : {description}",
            color=color.red,
        )

    @commands.hybrid_group(
        name="antinuke",
        with_app_command=True,
        help="เปิด/ปิดระบบป้องกันแอนตินุก",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.guild)
    async def antinuke_command(self, ctx: commands.Context, option: str = None):

        try:

            if not await self._require_manage_guild(ctx):

                return

            await self.command_flow.send_group_help(
                ctx,
                title="คำสั่ง AntiNuke",
                description="สิ่งเหล่านี้คือการควบคุม Anti-Nuke สำหรับเซิร์ฟเวอร์นี้",
                accent_color=color.green,
                footer_text="SkylineBOT • Skyline Development",
                include_options_hint=True,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @antinuke_command.command(
        name="enable", help="เปิดระบบป้องกันแอนตินุก", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.guild)
    async def antinuke_command_enable(self, ctx: commands.Context):

        try:

            if not await self._require_owner(ctx):

                return

            cache_antinuke_settings = await self.antinuke_service.ensure_settings(
                ctx.guild.id
            )

            if cache_antinuke_settings.get("enabled"):

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.WARNING} : Anti-Nuke system is already enabled",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            await self.antinuke_service.set_enabled(ctx.guild.id, True)

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.SUCCESS} : Anti-Nuke system has been enabled",
                    color=color.green,
                ),
                delete_after=30,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @antinuke_command.command(
        name="disable", help="ปิดระบบป้องกันแอนตินุก", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.guild)
    async def antinuke_command_disable(self, ctx: commands.Context):

        try:

            if not await self._require_owner(ctx):

                return

            cache_antinuke_settings = await self.antinuke_service.ensure_settings(
                ctx.guild.id
            )

            if not cache_antinuke_settings.get("enabled"):

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.WARNING} : Anti-Nuke system is already disabled",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            await self.antinuke_service.set_enabled(ctx.guild.id, False)

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.SUCCESS} : Anti-Nuke system has been disabled",
                    color=color.green,
                ),
                delete_after=30,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @antinuke_command.command(
        name="settings", help="แก้ไขการตั้งค่าแอนตินุก", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    async def antinuke_command_settings(self, ctx: commands.Context):

        try:

            if not await self._require_owner(ctx):

                return

            setup_cog = self.bot.get_command("setup").cog

            await setup_cog.AntiNuke_Module(ctx)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.ERROR} : An error occurred while trying to setup Anti-Nuke settings",
                    color=color.red,
                ),
                delete_after=10,
            )

    @commands.hybrid_group(
        name="whitelist",
        with_app_command=True,
        help="เพิ่มผู้ใช้เข้าไวท์ลิสต์ระบบแอนตินุก",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.guild)
    async def whitelist_command(self, ctx: commands.Context):

        try:

            if not await self._require_owner(ctx):

                return

            await self.command_flow.send_group_help(
                ctx,
                title="คำสั่ง Whitelist ต่อต้าน Nuke",
                description="เพิ่มผู้ใช้เข้าไวท์ลิสต์ระบบแอนตินุก",
                accent_color=color.purple,
                footer_text="SkylineBOT • Skyline Development",
                include_options_hint=True,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @whitelist_command.command(
        name="add", help="เพิ่มผู้ใช้เข้าไวท์ลิสต์", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=60, type=commands.BucketType.guild)
    async def whitelist_command_add(
        self, ctx: commands.Context, member: discord.Member
    ):

        try:

            if not await self._require_owner(ctx):

                return

            if not member:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"Please provide a member to whitelist",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            cache_antinuke_whitelist = self.security_service.get_whitelist_cache(
                ctx.guild.id
            )

            if (
                self.security_service.whitelist_count(ctx.guild.id)
                >= self.security_service.WHITELIST_LIMIT
            ):

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.ERROR} : You can only whitelist {self.security_service.WHITELIST_LIMIT} users",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            if str(member.id) in cache_antinuke_whitelist:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.WARNING} : User is already whitelisted",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            await self.security_service.add_whitelist_user(ctx.guild.id, member.id)

            await self.whitelist_command_edit(ctx, member)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @whitelist_command.command(
        name="delete", help="ลบผู้ใช้ออกจากไวท์ลิสต์", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.guild)
    async def whitelist_command_delete(
        self, ctx: commands.Context, member: discord.Member
    ):

        try:

            if not await self._require_owner(ctx):

                return

            if not member:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"Please provide a member to whitelist",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            cache_antinuke_whitelist = self.security_service.get_whitelist_cache(
                ctx.guild.id
            )

            if str(member.id) not in cache_antinuke_whitelist:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.WARNING} : User is not whitelisted",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            await self.security_service.remove_whitelist_user(ctx.guild.id, member.id)

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.SUCCESS} : User has been removed from whitelist",
                    color=color.green,
                ),
                delete_after=30,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @whitelist_command.command(
        name="edit", help="แก้ไขการตั้งค่าไวท์ลิสต์ของผู้ใช้", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.guild)
    async def whitelist_command_edit(
        self, ctx: commands.Context, member: discord.Member
    ):

        try:

            if not await self._require_owner(ctx):

                return

            if not member:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"Please provide a member to whitelist",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            cache_antinuke_whitelist = self.security_service.get_whitelist_user(
                ctx.guild.id, member.id
            )

            if not cache_antinuke_whitelist:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ANTINUKE} : {self.bot.emoji.WARNING} : User is not whitelisted",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            whitelist_variabled = self.security_service.whitelist_rule_keys

            async def get_embed():

                cache_antinuke_whitelist = (
                    self.security_service.get_whitelist_user(ctx.guild.id, member.id)
                    or {}
                )

                embed = discord.Embed(
                    title=f"{self.bot.emoji.ANTINUKE} Anti-Nuke Whitelist Settings",
                    description=f"Whitelist Settings for {member.mention}\n\n",
                    color=color.purple,
                )

                embed.set_thumbnail(url=member.display_avatar.url)

                embed.set_footer(text="Be sure while giving whitelist settings to user")

                for variable in whitelist_variabled:

                    embed.description += f"{self.bot.emoji.ENABLED_BUNDLE if cache_antinuke_whitelist.get(variable) else self.bot.emoji.DISABLED_BUNDLE} : {variable.replace('_',' ').title()}\n"

                return embed

            timeout_time = 300

            cancled = False

            def reset_timeout(timeout=300):

                nonlocal timeout_time

                timeout_time = timeout

            async def get_view(disable=False):

                cache_antinuke_whitelist = (
                    self.security_service.get_whitelist_user(ctx.guild.id, member.id)
                    or {}
                )

                view = discord.ui.View(timeout=300)

                reset_timeout()

                click_to_enable_all_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    label="Enable All ✅",
                    emoji=self.bot.emoji.SUCCESS,
                    custom_id="enable_all",
                    disabled=(
                        True
                        if all(
                            cache_antinuke_whitelist.get(variable)
                            for variable in whitelist_variabled
                        )
                        else False
                    ),
                )

                click_to_enable_all_button.callback = (
                    lambda i: click_to_enable_all_button_callback(i)
                )

                click_to_disable_all_button = discord.ui.Button(
                    style=discord.ButtonStyle.danger,
                    label="Disable All ⛔",
                    emoji=self.bot.emoji.FAILED,
                    custom_id="disable_all",
                    disabled=(
                        True
                        if all(
                            not cache_antinuke_whitelist.get(variable)
                            for variable in whitelist_variabled
                        )
                        else False
                    ),
                )

                click_to_disable_all_button.callback = (
                    lambda i: click_to_disable_all_button_callback(i)
                )

                edit_select = discord.ui.Select(
                    placeholder="Select A Setting To Edit",
                    min_values=1,
                    max_values=1,
                    options=(
                        [
                            discord.SelectOption(
                                label=variable.replace("_", " ").title(),
                                value=variable,
                                emoji=(
                                    self.bot.emoji.SUCCESS
                                    if cache_antinuke_whitelist.get(variable)
                                    else self.bot.emoji.FAILED
                                ),
                                description=(
                                    f"Click to Disable This Permission"
                                    if cache_antinuke_whitelist.get(variable)
                                    else f"Click to Enable This Permission"
                                ),
                            )
                            for variable in whitelist_variabled
                        ]
                        if len(whitelist_variabled) > 0
                        else [
                            discord.SelectOption(
                                label="No Setting Found", value="no_setting_found"
                            )
                        ]
                    ),
                    disabled=True if len(cache_antinuke_whitelist) == 0 else False,
                )

                edit_select.callback = lambda i: edit_select_callback(i)

                cancle_button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="ปิดเมนู",
                    emoji=self.bot.emoji.CANCLED,
                    custom_id="cancle",
                )

                cancle_button.callback = lambda i: cancle_button_callback(i)

                view.add_item(click_to_enable_all_button)

                view.add_item(click_to_disable_all_button)

                view.add_item(edit_select)

                view.add_item(cancle_button)

                if disable:

                    for item in view.children:

                        item.disabled = True

                return view

            async def click_to_enable_all_button_callback(
                interaction: discord.Interaction,
            ):

                try:

                    if interaction.user.id != ctx.author.id:

                        await interaction.response.send_message(
                            embed=self._security_error_embed(
                                "You are not allowed to use this button"
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                        return

                    await interaction.response.defer()

                    await self.security_service.set_all_whitelist_permissions(
                        ctx.guild.id,
                        member.id,
                        enabled=True,
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

                    await interaction.response.send_message(
                        embed=self._security_error_embed(
                            "An error occurred while trying to enable all whitelist settings"
                        ),
                        ephemeral=True,
                        delete_after=10,
                    )

            async def click_to_disable_all_button_callback(
                interaction: discord.Interaction,
            ):

                try:

                    if interaction.user.id != ctx.author.id:

                        await interaction.response.send_message(
                            embed=self._security_error_embed(
                                "You are not allowed to use this button"
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                        return

                    await interaction.response.defer()

                    await self.security_service.set_all_whitelist_permissions(
                        ctx.guild.id,
                        member.id,
                        enabled=False,
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

                    await interaction.response.send_message(
                        embed=self._security_error_embed(
                            "An error occurred while trying to disable all whitelist settings"
                        ),
                        ephemeral=True,
                        delete_after=10,
                    )

            async def edit_select_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        await interaction.response.send_message(
                            embed=self._security_error_embed(
                                "You are not allowed to use this button"
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                        return

                    await interaction.response.defer()

                    variable = interaction.data["values"][0]

                    if variable not in whitelist_variabled:

                        await interaction.followup.send(
                            embed=self._security_error_embed("Invalid Setting"),
                            ephemeral=True,
                            delete_after=10,
                        )

                        return

                    await self.security_service.toggle_whitelist_permission(
                        ctx.guild.id,
                        member.id,
                        variable,
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

                    await interaction.response.send_message(
                        embed=self._security_error_embed(
                            "An error occurred while trying to edit whitelist settings"
                        ),
                        ephemeral=True,
                        delete_after=10,
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                nonlocal cancled

                if interaction.user.id != ctx.author.id:

                    await interaction.response.send_message(
                        embed=self._security_error_embed(
                            "You are not allowed to use this button"
                        ),
                        ephemeral=True,
                        delete_after=10,
                    )

                    return

                await interaction.response.defer()

                cancled = True

                await interaction.message.edit(
                    embed=await get_embed(), view=await get_view(disable=True)
                )

            embed = await get_embed()

            view = await get_view()

            message = await ctx.send(embed=embed, view=view)

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(view=await get_view(disable=True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @whitelist_command.command(
        name="list", help="แสดงรายการผู้ใช้ไวท์ลิสต์ทั้งหมด", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=60, type=commands.BucketType.guild)
    async def whitelist_command_list(self, ctx: commands.Context):

        if not await self._require_owner(ctx):

            return

        async def home_embed():

            cache_antinuke_whitelist = self.security_service.get_whitelist_cache(
                ctx.guild.id
            )

            embed = discord.Embed(
                title=f"{self.bot.emoji.ANTINUKE} Anti-Nuke Whitelist",
                color=color.purple,
            )

            embed.set_footer(text="Be sure to whitelist only trusted users")

            if len(cache_antinuke_whitelist) == 0:

                embed.description = "No user is whitelisted"

                return embed

            else:

                description = ""

                for user_id in cache_antinuke_whitelist:

                    user = ctx.guild.get_member(int(user_id))

                    description += (
                        f"{self.bot.emoji.USER} : "
                        + (user.mention if user else f"Unknown User ({user_id})")
                        + "\n"
                    )

                embed.description = description

                return embed

        timeout_time = 300

        cancled = False

        def reset_timeout(timeout=300):

            nonlocal timeout_time

            timeout_time = timeout

        async def home_view(disable=False):

            cache_antinuke_whitelist = self.security_service.get_whitelist_cache(
                ctx.guild.id
            )

            reset_timeout()

            view = discord.ui.View(timeout=300)

            add_user_button = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="Add User ✨",
                emoji=self.bot.emoji.CREATE,
                custom_id="add_user",
            )

            delete_user_button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Remove User",
                emoji=self.bot.emoji.DELETE,
                custom_id="delete_user",
            )

            options = [
                discord.SelectOption(
                    label=f"{user.display_name if (user := ctx.guild.get_member(int(user_id))) else f'Unknown User ({user_id})'}",
                    value=str(user_id),
                    emoji=self.bot.emoji.USER,
                    description=f"Select this user to edit whitelist settings",
                )
                for user_id in cache_antinuke_whitelist.keys()
            ]

            edit_user_settings_button = discord.ui.Select(
                placeholder="Select A Whitelisted User To Edit",
                min_values=1,
                max_values=1,
                options=(
                    options
                    if len(options) > 0
                    else [
                        discord.SelectOption(
                            label="No User Found", value="no_user_found"
                        )
                    ]
                ),
                disabled=True if len(cache_antinuke_whitelist) == 0 else False,
            )

            add_user_button.callback = lambda i: add_user_button_callback(i)

            delete_user_button.callback = lambda i: delete_user_button_callback(i)

            edit_user_settings_button.callback = (
                lambda i: edit_user_settings_button_callback(i)
            )

            cancle_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="ปิดเมนู",
                emoji=self.bot.emoji.CANCLED,
                custom_id="cancle",
            )

            cancle_button.callback = lambda i: cancle_button_callback(i)

            view.add_item(add_user_button)

            view.add_item(delete_user_button)

            view.add_item(edit_user_settings_button)

            view.add_item(cancle_button)

            if disable:

                for item in view.children:

                    item.disabled = True

            return view

        async def edit_user_settings_button_callback(interaction: discord.Interaction):

            try:

                if interaction.user.id != ctx.author.id:

                    await interaction.response.send_message(
                        embed=discord.Embed(
                            description=f"{self.bot.emoji.ERROR} : You are not allowed to use this button",
                            color=color.red,
                        ),
                        ephemeral=True,
                        delete_after=10,
                    )

                    return

                await interaction.response.defer()

                user_id = int(interaction.data["values"][0])

                nonlocal cancled

                cancled = True

                await interaction.message.delete()

                member = await ctx.guild.fetch_member(int(user_id))

                if not member:

                    await ctx.send(
                        embed=discord.Embed(
                            description=f"ไม่พบผู้ใช้", color=color.red
                        ),
                        delete_after=10,
                    )

                    return

                await self.whitelist_command_edit(ctx, member)

            except Exception as e:

                logger.error(
                    f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                )

                await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} : An error occurred while trying to edit user whitelist settings",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

        async def cancle_button_callback(interaction: discord.Interaction):

            nonlocal cancled

            if interaction.user.id != ctx.author.id:

                await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} : You are not allowed to use this button",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

                return

            await interaction.response.defer()

            cancled = True

            await interaction.message.edit(
                embed=await home_embed(), view=await home_view(disable=True)
            )

        async def delete_user_button_callback(interaction: discord.Interaction):

            cache_antinuke_whitelist = self.security_service.get_whitelist_cache(
                ctx.guild.id
            )

            if interaction.user.id != ctx.author.id:

                await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} : You are not allowed to use this button",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

                return

            await interaction.response.defer()

            try:

                view = discord.ui.View(timeout=300)

                reset_timeout()

                select_user_select = discord.ui.Select(
                    placeholder=(
                        "Select A User To Delete"
                        if len(cache_antinuke_whitelist) > 0
                        else "No User To Delete"
                    ),
                    min_values=1,
                    max_values=1,
                    options=(
                        [
                            discord.SelectOption(
                                label=f"{user.display_name if (user := ctx.guild.get_member(int(user_id))) else f'Unknown User ({user_id})'}",
                                value=str(user_id),
                                emoji=self.bot.emoji.USER,
                                description=f"Select this user to delete from whitelist",
                            )
                            for user_id in cache_antinuke_whitelist.keys()
                        ]
                        if len(cache_antinuke_whitelist) > 0
                        else [
                            discord.SelectOption(
                                label="No User Found", value="no_user_found"
                            )
                        ]
                    ),
                    row=0,
                    disabled=True if len(cache_antinuke_whitelist) == 0 else False,
                )

                async def delete_user_select_callback(interaction: discord.Interaction):

                    try:

                        user_id = int(interaction.data["values"][0])

                        if str(user_id) not in cache_antinuke_whitelist:

                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=f"{self.bot.emoji.ERROR} : User is not whitelisted",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                            return

                        await interaction.response.defer()

                        await self.security_service.remove_whitelist_user(
                            ctx.guild.id, user_id
                        )

                        await interaction.message.edit(
                            embed=await home_embed(), view=await home_view()
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                        await interaction.response.send_message(
                            embed=discord.Embed(
                                description=f"{self.bot.emoji.ERROR} : An error occurred while trying to delete user from whitelist",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                select_user_select.callback = lambda i: delete_user_select_callback(i)

                async def back_button_callback(interaction: discord.Interaction):

                    try:

                        if interaction.user.id != ctx.author.id:

                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=f"{self.bot.emoji.ERROR} : You are not allowed to use this button",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                            return

                        await interaction.response.edit_message(
                            embed=await home_embed(), view=await home_view()
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                        )

                        await interaction.response.send_message(
                            embed=discord.Embed(
                                description=f"{self.bot.emoji.ERROR} : An error occurred while trying to go back",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                back_button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="Back Menu",
                    emoji=self.bot.emoji.BACK,
                    custom_id="back",
                    row=1,
                )

                back_button.callback = lambda i: back_button_callback(i)

                view.add_item(select_user_select)

                view.add_item(back_button)

                await interaction.message.edit(view=view)

            except Exception as e:

                logger.error(
                    f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                )

                await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} : An error occurred while trying to delete user from whitelist",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

        async def add_user_button_callback(interaction: discord.Interaction):

            try:

                if interaction.user.id != ctx.author.id:

                    await interaction.response.send_message(
                        embed=discord.Embed(
                            description=f"{self.bot.emoji.ERROR} : You are not allowed to use this button",
                            color=color.red,
                        ),
                        ephemeral=True,
                        delete_after=10,
                    )

                    return

                await interaction.response.defer()

                view = discord.ui.View(timeout=300)

                reset_timeout()

                async def user_select_callback(interaction: discord.Interaction):

                    cache_antinuke_whitelist = (
                        self.security_service.get_whitelist_cache(ctx.guild.id)
                    )

                    try:

                        user_id = int(interaction.data["values"][0])

                        if str(user_id) in cache_antinuke_whitelist:

                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=f"{self.bot.emoji.ERROR} : User is already whitelisted",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                            return

                        await interaction.response.defer()

                        await self.security_service.add_whitelist_user(
                            ctx.guild.id, int(user_id)
                        )

                        await interaction.message.edit(
                            embed=await home_embed(), view=await home_view()
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                        await interaction.response.send_message(
                            embed=discord.Embed(
                                description=f"{self.bot.emoji.ERROR} : An error occurred while trying to add user to whitelist",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                users_select = discord.ui.UserSelect(
                    placeholder="Select A User To Whitelist",
                    min_values=1,
                    max_values=1,
                    row=0,
                )

                users_select.callback = lambda i: user_select_callback(i)

                view.add_item(users_select)

                async def back_button_callback(interaction: discord.Interaction):

                    try:

                        if interaction.user.id != ctx.author.id:

                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    description=f"{self.bot.emoji.ERROR} : You are not allowed to use this button",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                            return

                        await interaction.response.edit_message(
                            embed=await home_embed(), view=await home_view()
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                        await interaction.response.send_message(
                            embed=discord.Embed(
                                description=f"{self.bot.emoji.ERROR} : An error occurred while trying to go back",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                back_button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="Back Menu",
                    emoji=self.bot.emoji.BACK,
                    custom_id="back",
                    row=1,
                )

                back_button.callback = lambda i: back_button_callback(i)

                view.add_item(back_button)

                await interaction.message.edit(view=view)

            except Exception as e:

                logger.error(
                    f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                )

                await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} : An error occurred while trying to add user to whitelist",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

        embed = await home_embed()

        view = await home_view()

        message = await ctx.send(embed=embed, view=view)

        while not cancled:

            timeout_time -= 1

            if timeout_time <= 0:

                await message.edit(view=None)

                break

            await asyncio.sleep(1)

    @commands.hybrid_group(
        name="extraowner",
        help="จัดการเจ้าของเสริมในเซิร์ฟเวอร์",
        invoke_without_command=True,
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.guild)
    async def extra_owner_command(self, ctx: commands.Context):

        try:

            if not await self._require_extra_owner_manager(ctx):

                return

            await self.command_flow.send_group_help(
                ctx,
                title="คำสั่งพิเศษของเจ้าของ",
                description="ต่อไปนี้เป็นคำสั่งในการจัดการเจ้าของเพิ่มเติม",
                accent_color=color.random_color(),
                include_options_hint=True,
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in extra owner command: {e}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @extra_owner_command.command(
        name="add", help="เพิ่มเจ้าของเสริม", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def extra_owner_add_command(
        self, ctx: commands.Context, member: discord.Member
    ):

        try:

            if not await self._require_extra_owner_manager(ctx):
                return

            if member == ctx.guild.owner:

                await ctx.send(
                    embed=discord.Embed(
                        description="คุณไม่สามารถเพิ่มเจ้าของเซิร์ฟเวอร์เป็นเจ้าของเสริมได้",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            if member.bot:

                await ctx.send(
                    embed=discord.Embed(
                        description="คุณไม่สามารถเพิ่มบอทเป็นเจ้าของเสริมได้",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            guilds_cache = await self.security_service.ensure_guild_record(ctx.guild.id)

            if not guilds_cache:

                await ctx.send(
                    embed=discord.Embed(
                        description="เกิดข้อผิดพลาดขณะประมวลผลคำสั่ง",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            extra_owner_ids = self.security_service.parse_extra_owner_ids(guilds_cache)

            guilds_subscription = guilds_cache.get("subscription", "free")
            extra_owner_limit = self.security_service.extra_owner_limit_for(
                guilds_subscription
            )

            if len(extra_owner_ids) >= extra_owner_limit:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"Extra owners limit reached. You can only have {extra_owner_limit} extra owners",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            if str(member.id) in extra_owner_ids:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{member.mention} is already an extra owner",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            extra_owner_ids.append(str(member.id))

            await self.security_service.save_extra_owner_ids(
                guilds_cache, extra_owner_ids
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"{member.mention} has been added as an extra owner",
                    color=color.green,
                )
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in extra owner add command: {e}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @extra_owner_command.command(
        name="remove", help="ลบเจ้าของเสริม", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def extra_owner_remove_command(
        self, ctx: commands.Context, member: discord.Member
    ):

        try:

            if not await self._require_extra_owner_manager(ctx):
                return

            guilds_cache = await self.security_service.ensure_guild_record(ctx.guild.id)

            extra_owner_ids = self.security_service.parse_extra_owner_ids(guilds_cache)

            if str(member.id) not in extra_owner_ids:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"{member.mention} is not an extra owner",
                        color=color.red,
                    ),
                    delete_after=10,
                )

                return

            extra_owner_ids.remove(str(member.id))

            await self.security_service.save_extra_owner_ids(
                guilds_cache, extra_owner_ids
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"{member.mention} has been removed as an extra owner",
                    color=color.green,
                )
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in extra owner remove command: {e}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @extra_owner_command.command(
        name="list", help="แสดงรายการเจ้าของเสริม", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.guild)
    async def extra_owner_list_command(self, ctx: commands.Context):

        try:

            if not await self._require_extra_owner_manager(ctx):
                return

            guilds_cache = await self.security_service.ensure_guild_record(ctx.guild.id)

            extra_owner_ids = self.security_service.parse_extra_owner_ids(guilds_cache)

            if not extra_owner_ids:

                await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีการเพิ่มเจ้าของเพิ่มเติม", color=color.red
                    ),
                    delete_after=10,
                )

                return

            embed = discord.Embed(
                description="นี่คือเจ้าของเซิร์ฟเวอร์เพิ่มเติม",
                color=color.random_color(),
            )

            embed.set_author(
                name=ctx.guild.name,
                icon_url=(
                    ctx.guild.icon.url
                    if ctx.guild.icon
                    else self.bot.user.display_avatar.url
                ),
            )

            embed.set_thumbnail(
                url=(
                    ctx.guild.icon.url
                    if ctx.guild.icon
                    else self.bot.user.display_avatar.url
                )
            )

            for index, extra_owner_id in enumerate(extra_owner_ids):

                member = ctx.guild.get_member(int(extra_owner_id))

                if member:

                    embed.description += f"\n{index+1}. {member.mention}"

            embed.set_footer(text=f"Total extra owners: {len(extra_owner_ids)}")

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in extra owner list command: {e}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )






