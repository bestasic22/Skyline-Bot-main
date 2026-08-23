import discord


from discord.ext import commands


import asyncio


import os, sys


from io import BytesIO


import traceback, sys


import wavelink


import datetime


import discord.http


from skylinebot.src.checks import checks


import storage.ban_data


import storage.redeem_codes


import storage.users


from skylinebot.console.logging import logger


from skylinebot.style import color


from skylinebot.utils import pings


from skylinebot.workflows.cache import load_cache


from skylinebot.console.generator import generate_redeem_code


from skylinebot.utils.directory_tree_builder import generate_directory_tree_string_split_text


import storage


import traceback, sys


from io import StringIO


import textwrap


from contextlib import redirect_stdout


from skylinebot.engine.bot_runtime import AutoShardedBot


from skylinebot.config.config import Types


from skylinebot.style import emoji
from skylinebot.utils import i18n
from skylinebot.src.services import CommandFlow

try:
    from skylinebot.surface.runtime import set_discord_service_state as _set_discord_service_state
except Exception:
    def _set_discord_service_state(**_kwargs):
        return None


redeem_code_types = Types.redeem_code_types


from skylinebot.workflows.subscription_actions import change_guild_subscription, change_user_subscription


def get_formatted_balance(balance: int) -> str:

    # Format balance with suffixes like 1m, 1k, 1b with max 1 decimal if needed

    if balance >= 1_000_000_000:

        formatted = balance / 1_000_000_000

        suffix = "b"

    elif balance >= 1_000_000:

        formatted = balance / 1_000_000

        suffix = "m"

    elif balance >= 1_000:

        formatted = balance / 1_000

        suffix = "k"

    else:

        return str(balance)

    # Check if the decimal part is zero

    if formatted.is_integer():

        return f"{int(formatted)}{suffix}"

    else:

        return f"{formatted:.1f}{suffix}"


class Root(commands.Cog):

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        class CogInfo:

            name = "Root"

            category = "Extra"

            description = "คำสั่งรูท"

            hidden = True

            emoji = bot.emoji.ROOT

        self.cog_info = CogInfo
        self.command_flow = CommandFlow(bot)

    @commands.group(
        name="root", help="คำสั่งรูท", hidden=True, invoke_without_command=True
    )
    @checks.is_owner()
    async def root(self, ctx: commands.Context):

        try:

            await self.command_flow.send_group_help(
                ctx,
                title="คำสั่งรูท",
                description="นี่คือรายการคำสั่ง root",
                accent_color=color.blue,
                footer_text="SkylineBOT • Skyline Development",
                include_options_hint=True,
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @root.command(name="reload", help="รีโหลดยูนิตระบบทั้งหมด", hidden=True)
    async def reload(self, ctx: commands.Context, name: str = None):

        if not name:

            reloading_embed = discord.Embed(title="กำลังโหลดใหม่", color=color.orange)

            reloading_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            reloading_embed.set_footer(
                text="SkylineBOT • Skyline Development",
                icon_url=self.bot.user.display_avatar.url,
            )

            message = await ctx.send(embed=reloading_embed)

            commands_cogs = [
                cog
                for cog in self.bot.cogs.values()
                if hasattr(cog, "get_commands") and cog.get_commands()
            ]

            events_cogs = [
                cog
                for cog in self.bot.cogs.values()
                if hasattr(cog, "get_listeners") and cog.get_listeners()
            ]

            await self.bot.reload()

            await self.bot.reload_extension("skylinebot.src")

            commands_cogs_text = "\n".join(
                [str(cog.__class__.__name__).capitalize() for cog in commands_cogs]
            )

            events_cogs_text = "\n".join(
                [str(cog.__class__.__name__).capitalize() for cog in events_cogs]
            )

            reloading_embed.add_field(
                name="__Command Units:__",
                value=f"```prolog\n{commands_cogs_text}```",
                inline=True,
            )

            reloading_embed.add_field(
                name="__Event Units:__",
                value=f"```prolog\n{events_cogs_text}```",
                inline=True,
            )

            reloading_embed.title = "Successfully Reloaded SkylineBOT Src"

            reloading_embed.description = (
                f"\n\n**__Bot Ping:__** `{pings.bot(self.bot)}ms`"
            )

            reloading_embed.description += (
                f"\n**__Storage Ping:__** `{await pings.database()}ms`"
            )

            reloading_embed.description += f"\n**__Cache Ping:__** `{pings.cache()}ms`"

            reloading_embed.description += (
                f"\n\n**{self.bot.emoji.LOADING} กำลังโหลดใหม่ Tree**"
            )

            reloading_embed.set_footer(
                text="SkylineBOT • Skyline Development",
                icon_url=self.bot.user.display_avatar.url,
            )

            await message.edit(embed=reloading_embed)

            await self.bot.tree.sync()

            reloading_embed.description = reloading_embed.description.replace(
                f"\n\n**{self.bot.emoji.LOADING} กำลังโหลดใหม่ Tree**",
                f"\n\n**{self.bot.emoji.SUCCESS} Tree Synced**",
            )

            await message.edit(embed=reloading_embed)

        else:
            raw_type = str(name or "").strip().lower()
            normalized_type = raw_type.replace("-", "").replace("_", "").replace(" ", "")
            if normalized_type in {"cache", "c"}:
                reload_target = "cache"
            elif normalized_type in {"slash", "sl", "tree", "app", "apps", "salass"}:
                reload_target = "slash"
            else:
                return await ctx.send(
                    (
                        f"ประเภทไม่ถูกต้อง: `{name}`\n"
                        "ประเภทที่รองรับ: `cache` / `slash`\n"
                        "ตัวอย่าง: `root reload cache` หรือ `root reload slash`"
                    ),
                    delete_after=12,
                )

            reloading_embed = discord.Embed(
                title="กำลังโหลดใหม่",
                description=f"กำลังโหลดใหม่ {reload_target} data",
                color=color.yellow,
            )

            reloading_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            reloading_embed.set_footer(
                text=f"กำลังโหลดใหม่ requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )

            message = await ctx.send(embed=reloading_embed)

            if reload_target == "cache":

                await load_cache()

                reloading_embed.title = "Successfully Reloaded Cache"

                reloading_embed.description = f"Succesfully reloaded cache data.\n\n**Bot Ping:** `{pings.bot(self.bot)}ms`"

                await message.edit(embed=reloading_embed)
            elif reload_target == "slash":
                synced = await self.bot.tree.sync()
                reloading_embed.title = "Successfully Reloaded Slash Commands"
                reloading_embed.description = (
                    "Successfully synced slash command tree.\n\n"
                    f"**Total Synced:** `{len(synced)}`"
                )
                reloading_embed.color = color.green
                await message.edit(embed=reloading_embed)

            else:

                await message.edit(embed=reloading_embed)

    @root.command(name="restart", help="รีสตาร์ตบอท", hidden=True)
    @checks.is_owner()
    async def restart(self, ctx: commands.Context):

        confirmation_embed = discord.Embed(
            title=f"Need Confirmation",
            description=f"Do you want to restart the bot?",
            color=color.yellow,
        )

        confirmation_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        confirmation_embed.set_footer(
            text=f"Restart requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        view_timeout = 60

        cancled = False

        def get_view(disabled=False):

            view = discord.ui.View(timeout=60)

            yes_button = discord.ui.Button(
                label="Restart Now",
                style=discord.ButtonStyle.green,
                disabled=disabled,
                emoji="☑",
            )

            no_button = discord.ui.Button(
                label="Cancel Restart",
                style=discord.ButtonStyle.gray,
                disabled=disabled,
                emoji=self.bot.emoji.NO,
            )

            yes_button.callback = lambda i: yes_button_callback(i)

            no_button.callback = lambda i: no_button_callback(i)

            view.add_item(yes_button)

            view.add_item(no_button)

            return view

        async def yes_button_callback(interaction: discord.Interaction):

            if interaction.user.id != ctx.author.id:

                return await interaction.response.send_message(
                    "คุณไม่มีสิทธิ์ใช้ปุ่มนี้", ephemeral=True
                )

            nonlocal cancled

            cancled = True

            embed = discord.Embed(
                title="รีสตาร์ตแล้ว", description="รีสตาร์ตแล้ว the bot.", color=color.green
            )

            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            embed.set_footer(
                text=f"รีสตาร์ตแล้ว by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )

            await interaction.response.edit_message(embed=embed, view=None)

            def restart_bot():

                # Restart the bot

                os.execl(sys.executable, sys.executable, *sys.argv)

            restart_bot()

        async def no_button_callback(interaction: discord.Interaction):

            if interaction.user.id != ctx.author.id:

                return await interaction.response.send_message(
                    "คุณไม่มีสิทธิ์ใช้ปุ่มนี้", ephemeral=True
                )

            nonlocal cancled

            cancled = True

            embed = discord.Embed(
                title="ยกเลิกแล้ว", description="ยกเลิกแล้ว the restart.", color=color.red
            )

            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            embed.set_footer(
                text=f"Restart canceled by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )

            await interaction.response.edit_message(embed=embed, view=None)

        message = await ctx.send(embed=confirmation_embed, view=get_view())

        while True:

            if cancled:

                break

            if view_timeout <= 0:

                await message.edit(view=get_view(True))

                break

            view_timeout -= 1

            await asyncio.sleep(1)

    @root.command(
        name="shutdown",
        help="ปิดการทำงานบอท",
        hidden=True,
        aliases=["shut", "stop"],
    )
    @checks.is_owner()
    async def shutdown(self, ctx: commands.Context):
        await self._run_shutdown_flow(ctx)

    @root.command(name="logs", help="แสดงบันทึกล่าสุด 50 รายการ", hidden=True)
    @checks.is_owner()
    async def logs(self, ctx: commands.Context):

        log_folder = os.path.join(os.getcwd(), "logs")

        logs = [str(log) for log in os.listdir(log_folder)]

        logs = logs[-50:]

        logs_text = "\n".join(logs)

        logs_embed = discord.Embed(
            title="รายการล็อกล่าสุด 50 รายการ",
            description=f"```prolog\n{logs_text}```",
            color=color.blue,
        )

        logs_embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        logs_embed.set_footer(
            text=f"Logs requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=logs_embed)

    @root.command(name="log", help="แสดงเนื้อหาไฟล์บันทึก", hidden=True)
    @checks.is_owner()
    async def log(self, ctx: commands.Context, *, filename: str = None):

        try:

            if filename:

                file_path = f"logs/{filename}"

            else:

                file_path = logger.logging_file

                filename = os.path.basename(logger.logging_file)

            if not os.path.exists(file_path):

                return await ctx.reply(f"Log file `{filename}` doesn't exist.")

            # Check file size

            file_size = os.path.getsize(file_path)

            max_size = 25 * 1024 * 1024  # 8 MB

            if file_size > max_size:

                return await ctx.reply(
                    f"ไฟล์ `{filename}` มีขนาดใหญ่เกินอัปโหลด (สูงสุด 25 MB) กรุณาดาวน์โหลดไฟล์จากโฮสต์เพื่อดู"
                )

            # Read the file content into a BytesIO object

            with open(file_path, "rb") as file_data:

                file_bytes = BytesIO(file_data.read())

            # Reset the BytesIO cursor to the beginning of the stream

            file_bytes.seek(0)

            # Create a discord.File object using the BytesIO stream

            file = discord.File(fp=file_bytes, filename=filename)

            # Send the file in the response

            await ctx.send(file=file)

        except Exception as e:

            await ctx.send(f"ข้อผิดพลาด: {e}")

    @root.command(name="ping", help="แสดงค่าปิงทุกประเภท", hidden=True)
    @checks.is_owner()
    async def root_ping(self, ctx: commands.Context):

        try:

            # send ping snapshots for the bot runtime and surface endpoint

            message = await ctx.send(
                embed=discord.Embed(
                    title="กำลังวัดค่า Ping", description="กำลังวัดค่า Ping...", color=color.orange
                )
            )

            for i in range(10):

                try:

                    def get_shard_guilds_count(shard_id):

                        try:

                            return len(
                                [
                                    guild
                                    for guild in self.bot.guilds
                                    if guild.shard_id == int(shard_id)
                                ]
                            )

                        except Exception:
                            return 0

                    shards_text = "\n**__Shards Ping:__**\n"

                    shards_text += "\n".join(
                        [
                            f"**Shard {shard} Ping:** `{ping}ms` ({get_shard_guilds_count(shard)})"
                            for shard, ping in pings.shards(self.bot).items()
                        ]
                    )

                    embed = discord.Embed(
                        title="สถานะการตอบสนอง",
                        description=f"**Bot Ping:** `{pings.bot(self.bot)}ms`\n"
                        f"**Storage Ping:** `{await pings.storage()}ms`\n"
                        f"**Cache Ping:** `{pings.cache()}ms`\n"
                        f"**Surface Ping:** `{pings.surface()}ms`\n"
                        f"{shards_text}",
                        color=color.blue,
                    )

                    embed.set_footer(
                        text=f"Updated {i+1}/10" if i < 9 else "Finished",
                    )

                    await message.edit(embed=embed)

                    await asyncio.sleep(3)

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

        except Exception as e:

            await ctx.send(
                embed=discord.Embed(
                    description=f"An ข้อผิดพลาด occurred while pinging: {e}", color=color.red
                ),
                delete_after=10,
            )

    async def _defer_if_needed(self, ctx: commands.Context):
        interaction = getattr(ctx, "interaction", None)
        if interaction is None or interaction.response.is_done():
            return
        try:
            await ctx.defer()
        except (discord.NotFound, discord.InteractionResponded):
            return
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                return
            raise

    def _set_runtime_state(
        self,
        *,
        level: str,
        message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
        attempt: int | None = None,
    ) -> None:
        try:
            _set_discord_service_state(
                level=level,
                message=message,
                status_code=status_code,
                retry_after=retry_after,
                attempt=attempt,
            )
        except Exception:
            pass

    @staticmethod
    def _canonical_ownerbot_action(raw_action: str | None) -> str:
        normalized = str(raw_action or "").strip().lower()
        if normalized in {"start", "stast", "boot", "run"}:
            return "start"
        if normalized in {"shutdown", "stop", "off", "close"}:
            return "shutdown"
        if normalized in {"reload", "restart", "reboot"}:
            return "reload"
        return normalized

    @staticmethod
    def _ownerbot_bool_env(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return bool(default)
        value = str(raw).strip().lower()
        if value in {"1", "true", "yes", "on", "y"}:
            return True
        if value in {"0", "false", "no", "off", "n"}:
            return False
        return bool(default)

    def _ownerbot_runtime_flags(self) -> tuple[bool, bool]:
        mode = str(os.getenv("RUN_COMPONENTS", "all") or "").strip().lower()
        run_web = True
        run_bot = True
        if mode in {"web", "dashboard", "surface"}:
            run_web = True
            run_bot = False
        elif mode in {"bot", "discord"}:
            run_web = False
            run_bot = True
        elif mode in {"none", "off"}:
            run_web = False
            run_bot = False
        run_web = self._ownerbot_bool_env("RUN_WEB", run_web)
        run_bot = self._ownerbot_bool_env("RUN_BOT", run_bot)
        return run_web, run_bot

    async def _run_reload_web_flow(self, ctx: commands.Context):
        await self._defer_if_needed(ctx)
        run_web, _run_bot = self._ownerbot_runtime_flags()
        if not run_web or not bool(getattr(self.bot.BotConfig, "DASHBOARD_ENABLED", False)):
            return await ctx.send(
                embed=discord.Embed(
                    title="Web runtime ไม่ได้เปิดอยู่",
                    description="ไม่สามารถ reload web ได้ เพราะปิดไว้ด้วย RUN_COMPONENTS/RUN_WEB/DASHBOARD_ENABLED",
                    color=color.red,
                ),
                delete_after=12,
            )

        embed = discord.Embed(
            title="กำลังรีโหลด Web Runtime",
            description="ระบบจะรีสตาร์ต process เพื่อโหลดเว็บใหม่ (ถ้ารัน bot+web ร่วมกัน จะรีสตาร์ตทั้งคู่)",
            color=color.orange,
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)

        async def restart_web_task():
            await asyncio.sleep(0.9)
            try:
                if not self.bot.is_closed():
                    await self.bot.close()
            except Exception:
                pass
            os.execl(sys.executable, sys.executable, *sys.argv)

        asyncio.create_task(restart_web_task(), name="ownerbot_reload_web")

    async def _run_shutdown_web_flow(self, ctx: commands.Context):
        await self._defer_if_needed(ctx)
        run_web, _run_bot = self._ownerbot_runtime_flags()
        if not run_web or not bool(getattr(self.bot.BotConfig, "DASHBOARD_ENABLED", False)):
            return await ctx.send(
                embed=discord.Embed(
                    title="Web runtime ไม่ได้เปิดอยู่",
                    description="ไม่สามารถ shutdown web ได้ เพราะปิดไว้ด้วย RUN_COMPONENTS/RUN_WEB/DASHBOARD_ENABLED",
                    color=color.red,
                ),
                delete_after=12,
            )

        embed = discord.Embed(
            title="กำลังปิด Web Runtime",
            description="ระบบจะหยุด process ปัจจุบัน (ถ้ารัน bot+web ร่วมกัน จะหยุดทั้งคู่)",
            color=color.red,
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)

        async def shutdown_web_task():
            await asyncio.sleep(0.8)
            try:
                if not self.bot.is_closed():
                    await self.bot.close()
            except Exception:
                pass
            os._exit(0)

        asyncio.create_task(shutdown_web_task(), name="ownerbot_shutdown_web")

    async def _run_start_web_flow(self, ctx: commands.Context):
        await self._defer_if_needed(ctx)
        run_web, _run_bot = self._ownerbot_runtime_flags()
        if run_web and bool(getattr(self.bot.BotConfig, "DASHBOARD_ENABLED", False)):
            return await ctx.send(
                embed=discord.Embed(
                    title="Web runtime กำลังทำงานอยู่แล้ว",
                    description="ไม่ต้อง start ซ้ำ",
                    color=color.yellow,
                ),
                delete_after=10,
            )
        return await ctx.send(
            embed=discord.Embed(
                title="Web runtime ถูกปิดไว้",
                description="ต้องเปิด RUN_COMPONENTS/RUN_WEB/DASHBOARD_ENABLED แล้วรีสตาร์ต process ก่อน",
                color=color.red,
            ),
            delete_after=12,
        )

    async def _run_reload_bot_flow(self, ctx: commands.Context):
        try:
            await self._defer_if_needed(ctx)
            self._set_runtime_state(
                level="starting",
                message="OwnerBOT manage requested bot reload",
                attempt=0,
            )
            embed = discord.Embed(
                title="กำลังโหลดใหม่ Bot",
                description=f"{self.bot.emoji.LOADING} กำลังโหลดใหม่ source units...",
                color=color.orange,
            )
            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
            message = await ctx.send(embed=embed)

            await self.bot.reload()
            await self.bot.reload_extension("skylinebot.src")

            embed.title = "Reloaded Bot"
            embed.description = (
                f"{self.bot.emoji.SUCCESS} Reload completed\n"
                f"**Bot Ping:** `{pings.bot(self.bot)}ms`\n"
                f"**Storage Ping:** `{await pings.database()}ms`\n"
                f"**Cache Ping:** `{pings.cache()}ms`"
            )
            embed.color = color.green
            await message.edit(embed=embed)
            self._set_runtime_state(
                level="ok",
                message="OwnerBOT manage reload completed",
                attempt=0,
            )
        except Exception as e:
            self._set_runtime_state(
                level="degraded",
                message=f"OwnerBOT manage reload failed: {e}",
                attempt=0,
            )
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description=f"รีโหลดบอทไม่สำเร็จ: {e}",
                    color=color.red,
                ),
                delete_after=12,
            )

    async def _run_reload_slash_flow(
        self,
        ctx: commands.Context,
        *,
        reload_source: bool = True,
        scope: str = "current_guild",
        guild_id: str | None = None,
    ):
        try:
            await self._defer_if_needed(ctx)
            embed = discord.Embed(
                title="กำลังโหลดใหม่ Slash Commands",
                description=(
                    f"{self.bot.emoji.LOADING} Reloading source + syncing application command tree..."
                    if reload_source
                    else f"{self.bot.emoji.LOADING} Syncing application command tree..."
                ),
                color=color.orange,
            )
            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
            message = await ctx.send(embed=embed)

            if reload_source:
                await self.bot.reload()
                await self.bot.reload_extension("skylinebot.src")
                i18n.apply_app_command_localizations(self.bot)

            synced_rows, sync_scope_label = await self._sync_tree_for_scope(
                scope=scope,
                ctx_guild=ctx.guild,
                guild_id=guild_id,
            )

            filtered = list(getattr(self.bot, "_slash_filtered_commands", []) or [])
            overflow = list(getattr(self.bot, "_slash_overflow_commands", []) or [])
            command_mode = str(getattr(self.bot, "_slash_command_mode", "essential")).strip().lower()

            embed.title = "Reloaded Slash Commands"
            embed.description = (
                f"{self.bot.emoji.SUCCESS} Tree synced successfully\n"
                f"**Scope:** `{sync_scope_label}`\n"
                f"**Synced:** `{len(synced_rows)}`\n"
                f"**Mode:** `{command_mode}`\n"
                f"**Filtered by mode:** `{len(filtered)}`\n"
                f"**Overflow skipped (limit):** `{len(overflow)}`"
            )
            embed.color = color.green
            await message.edit(embed=embed)
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description=f"รีโหลดคำสั่งสแลชไม่สำเร็จ: {e}",
                    color=color.red,
                ),
                delete_after=12,
            )

    async def _run_start_flow(self, ctx: commands.Context):
        await self._defer_if_needed(ctx)
        if not self.bot.is_closed():
            self._set_runtime_state(
                level="ok",
                message="OwnerBOT start skipped: bot already running",
                attempt=0,
            )
            return await ctx.send(
                embed=discord.Embed(
                    title="บอทกำลังทำงานอยู่แล้ว",
                    description="ไม่ต้อง start ซ้ำตอนที่บอทยัง online",
                    color=color.yellow,
                ),
                delete_after=10,
            )

        self._set_runtime_state(
            level="starting",
            message="OwnerBOT start requested",
            attempt=0,
        )
        await ctx.send(
            embed=discord.Embed(
                title="กำลังเริ่มบอท",
                description="รับคำสั่ง start แล้ว กำลังเริ่มระบบบอท",
                color=color.yellow,
            )
        )

        async def start_task():
            await asyncio.sleep(0.6)
            token = str(getattr(self.bot.BotConfig, "TOKEN", "") or os.getenv("TOKEN", "")).strip()
            if not token:
                self._set_runtime_state(
                    level="degraded",
                    message="OwnerBOT start failed: TOKEN not configured",
                    attempt=0,
                )
                return
            try:
                await self.bot.start(token)
            except Exception as error:
                self._set_runtime_state(
                    level="degraded",
                    message=f"OwnerBOT start failed: {error}",
                    attempt=0,
                )
                logger.error(
                    f"ข้อผิดพลาด in file {__file__} while starting bot: {error}"
                )

        asyncio.create_task(start_task(), name="ownerbot_start")

    async def _sync_tree_for_scope(
        self,
        *,
        scope: str = "current_guild",
        ctx_guild: discord.Guild | None = None,
        guild_id: str | None = None,
    ) -> tuple[list, str]:
        selected_scope = str(scope or "current_guild").strip().lower()
        mirror_global_to_guild = str(os.getenv("SLASH_MIRROR_GLOBAL_TO_GUILD", "")).strip().lower() in {"1", "true", "yes", "on"}
        avoid_duplicate_sources = str(os.getenv("SLASH_AVOID_DUPLICATE_COMMANDS", "1")).strip().lower() not in {"0", "false", "no", "off"}
        mirror_guard_note = ""
        mirror_disabled_by_guard = False
        if mirror_global_to_guild and avoid_duplicate_sources:
            mirror_global_to_guild = False
            mirror_guard_note = " guard=dedupe"
            mirror_disabled_by_guard = True

        if selected_scope == "global":
            synced_rows = await self.bot.tree.sync()
            return synced_rows, "global"

        if selected_scope in {"current_guild", "guild", "current"}:
            if ctx_guild is None:
                raise ValueError("ไม่พบกิลด์ปัจจุบันสำหรับโหมด current_guild")
            target_guild = ctx_guild
            global_synced_count = 0
            if mirror_disabled_by_guard:
                global_synced_count = len(await self.bot.tree.sync())
            self.bot.tree.clear_commands(guild=target_guild)
            if mirror_global_to_guild:
                self.bot.tree.copy_global_to(guild=target_guild)
            synced_rows = await self.bot.tree.sync(guild=target_guild)
            sync_scope = f"current_guild ({target_guild.id}) mirror={mirror_global_to_guild}{mirror_guard_note}"
            if mirror_disabled_by_guard:
                sync_scope += f" global={global_synced_count}"
            return synced_rows, sync_scope

        if selected_scope in {"guild_id", "guildid", "id"}:
            gid_text = str(guild_id or "").strip()
            if not gid_text.isdigit():
                raise ValueError("guild_id ต้องเป็นตัวเลข")
            gid = int(gid_text)
            target_guild = self.bot.get_guild(gid) or discord.Object(id=gid)
            global_synced_count = 0
            if mirror_disabled_by_guard:
                global_synced_count = len(await self.bot.tree.sync())
            self.bot.tree.clear_commands(guild=target_guild)
            if mirror_global_to_guild:
                self.bot.tree.copy_global_to(guild=target_guild)
            synced_rows = await self.bot.tree.sync(guild=target_guild)
            sync_scope = f"guild_id ({gid}) mirror={mirror_global_to_guild}{mirror_guard_note}"
            if mirror_disabled_by_guard:
                sync_scope += f" global={global_synced_count}"
            return synced_rows, sync_scope

        raise ValueError("scope ไม่ถูกต้อง (รองรับ: current_guild, guild_id, global)")

    def _ownerbot_available_command_names(self) -> list[str]:
        names = []
        for command in self.bot.commands:
            command_name = str(getattr(command, "qualified_name", "") or "").strip().lower()
            if not command_name:
                continue
            root_name = command_name.split(" ", 1)[0]
            if root_name not in names:
                names.append(root_name)
        return sorted(names)

    async def _run_reload_command_flow(
        self,
        ctx: commands.Context,
        *,
        command_name: str | None = None,
        all_commands: bool = False,
        scope: str = "current_guild",
        guild_id: str | None = None,
    ):
        try:
            await self._defer_if_needed(ctx)
            embed = discord.Embed(
                title="กำลังรีโหลดคำสั่ง",
                description=f"{self.bot.emoji.LOADING} กำลังรีโหลดคำสั่ง...",
                color=color.orange,
            )
            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
            message = await ctx.send(embed=embed)

            normalized_name = str(command_name or "").strip().lower().lstrip("/")
            run_all = bool(all_commands or normalized_name in {"", "all", "*"})
            reloaded_target = ""

            if run_all:
                await self.bot.reload()
                await self.bot.reload_extension("skylinebot.src")
                reloaded_target = "all commands"
            else:
                command_obj = self.bot.get_command(normalized_name)
                if command_obj is None:
                    available = self._ownerbot_available_command_names()
                    sample = ", ".join(available[:20]) + (" ..." if len(available) > 20 else "")
                    raise ValueError(
                        f"ไม่พบคำสั่ง `{normalized_name}`\n"
                        f"ลองใช้ชื่อคำสั่งหลัก เช่น: {sample or '-'}"
                    )

                cog_obj = getattr(command_obj, "cog", None)
                module_name = str(getattr(cog_obj, "__module__", "") or "").strip()
                if not module_name.startswith("skylinebot.src.commands."):
                    raise ValueError(
                        f"คำสั่ง `{normalized_name}` ไม่ได้อยู่ในโมดูลคำสั่งมาตรฐาน ({module_name or 'unknown'})"
                    )

                try:
                    await self.bot.reload_extension(module_name)
                except commands.ExtensionNotLoaded:
                    await self.bot.reload_extension("skylinebot.src")
                reloaded_target = f"{normalized_name} ({module_name})"

            i18n.apply_app_command_localizations(self.bot)
            synced_rows, sync_scope_label = await self._sync_tree_for_scope(
                scope=scope,
                ctx_guild=ctx.guild,
                guild_id=guild_id,
            )

            embed.title = "Reloaded Command"
            embed.description = (
                f"{self.bot.emoji.SUCCESS} Reload completed\n"
                f"**Target:** `{reloaded_target}`\n"
                f"**Scope:** `{sync_scope_label}`\n"
                f"**Synced:** `{len(synced_rows)}`"
            )
            embed.color = color.green
            await message.edit(embed=embed)
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description=f"รีโหลดคำสั่งไม่สำเร็จ: {e}",
                    color=color.red,
                ),
                delete_after=14,
            )

    async def _run_shutdown_flow(self, ctx: commands.Context):
        self._set_runtime_state(
            level="stopped",
            message="OwnerBOT manage requested bot shutdown",
            attempt=0,
        )
        shutted_down_embed = discord.Embed(
            title="กำลังปิดระบบ", description="กำลังปิดการทำงานของบอท", color=color.red
        )

        shutted_down_embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        shutted_down_embed.set_footer(
            text=f"Shutdown requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=shutted_down_embed)

        async def shutdown_task():
            await asyncio.sleep(0.8)
            try:
                await self.bot.close()
            except Exception as error:
                logger.error(
                    f"ข้อผิดพลาด in file {__file__} while shutting down bot: {error}"
                )
                os._exit(0)

        asyncio.create_task(shutdown_task())

    @commands.hybrid_group(
        name="ownerbot",
        with_app_command=True,
        invoke_without_command=True,
        help="คำสั่งสำหรับเจ้าของบอท",
        hidden=True,
    )
    @checks.is_owner()
    async def ownerbot(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "ใช้ `/ownerbot manage` แล้วเลือก action/reload type/scope ได้ในคำสั่งเดียว"
            )

    async def _ownerbot_command_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        normalized = str(current or "").strip().lower()
        out = []
        for name in self._ownerbot_available_command_names():
            if normalized and normalized not in name:
                continue
            out.append(discord.app_commands.Choice(name=name, value=name))
            if len(out) >= 25:
                break
        return out

    @ownerbot.command(
        name="manage",
        with_app_command=True,
        help="Unified ownerbot control center for start/reload/shutdown (ศูนย์ควบคุม ownerbot แบบรวมสำหรับ start/reload/shutdown)",
    )
    @discord.app_commands.describe(
        action="ต้องการทำอะไร",
        target="เลือกเป้าหมายที่ต้องการควบคุม (bot หรือ web)",
        reload_type="ถ้าเลือก reload ให้เลือกประเภท",
        scope="ขอบเขตที่ต้องการ sync slash",
        guild_id="ระบุ guild id เมื่อเลือก scope = guild_id",
        command_name="ชื่อคำสั่งที่จะ reload (ใช้กับ reloadcommand)",
        all_commands="reload ทุกคำสั่ง (ใช้กับ reloadcommand)",
        confirm="ยืนยันการปิดบอท (ใช้กับ shutdown)",
    )
    @discord.app_commands.choices(
        action=[
            discord.app_commands.Choice(name="start", value="start"),
            discord.app_commands.Choice(name="reload", value="reload"),
            discord.app_commands.Choice(name="shutdown", value="shutdown"),
        ],
        target=[
            discord.app_commands.Choice(name="bot", value="bot"),
            discord.app_commands.Choice(name="web", value="web"),
        ],
        reload_type=[
            discord.app_commands.Choice(name="reloadbot", value="reloadbot"),
            discord.app_commands.Choice(name="slashcommand", value="slashcommand"),
            discord.app_commands.Choice(name="reloadcommand", value="reloadcommand"),
        ],
        scope=[
            discord.app_commands.Choice(name="current_guild", value="current_guild"),
            discord.app_commands.Choice(name="guild_id", value="guild_id"),
            discord.app_commands.Choice(name="global", value="global"),
        ],
    )
    @discord.app_commands.autocomplete(command_name=_ownerbot_command_name_autocomplete)
    @checks.is_owner()
    async def ownerbot_manage(
        self,
        ctx: commands.Context,
        action: str,
        target: str | None = "bot",
        reload_type: str | None = None,
        scope: str | None = "current_guild",
        guild_id: str | None = None,
        command_name: str | None = None,
        all_commands: bool = False,
        confirm: bool = False,
    ):
        action_name = self._canonical_ownerbot_action(action)
        target_name = str(target or "bot").strip().lower()
        reload_name = str(reload_type or "reloadbot").strip().lower()
        scope_name = str(scope or "current_guild").strip().lower()

        if target_name not in {"bot", "web"}:
            return await ctx.send(
                "target ไม่ถูกต้อง (รองรับ: bot, web)",
                delete_after=10,
            )

        if target_name == "web":
            if action_name == "start":
                return await self._run_start_web_flow(ctx)
            if action_name == "shutdown":
                if not confirm:
                    return await ctx.send(
                        "ยกเลิกการปิด web: โปรดตั้ง `confirm: true`",
                        delete_after=10,
                    )
                return await self._run_shutdown_web_flow(ctx)
            if action_name != "reload":
                return await ctx.send(
                    "action ไม่ถูกต้อง (รองรับ: start, reload, shutdown)",
                    delete_after=10,
                )
            return await self._run_reload_web_flow(ctx)

        if action_name == "start":
            return await self._run_start_flow(ctx)

        if action_name == "shutdown":
            if not confirm:
                return await ctx.send(
                    "ยกเลิกการปิดบอท: โปรดตั้ง `confirm: true`",
                    delete_after=10,
                )
            return await self._run_shutdown_flow(ctx)

        if action_name != "reload":
            return await ctx.send(
                "action ไม่ถูกต้อง (รองรับ: start, reload, shutdown)",
                delete_after=10,
            )

        if reload_name not in {"reloadbot", "slashcommand", "reloadcommand"}:
            return await ctx.send(
                "reload_type ไม่ถูกต้อง (รองรับ: reloadbot, slashcommand, reloadcommand)",
                delete_after=10,
            )

        if scope_name in {"guild_id", "guildid", "id"} and not str(guild_id or "").strip():
            return await ctx.send(
                "เมื่อใช้ scope=guild_id กรุณาระบุ guild_id",
                delete_after=10,
            )

        if reload_name == "reloadbot":
            return await self._run_reload_bot_flow(ctx)
        if reload_name == "slashcommand":
            return await self._run_reload_slash_flow(
                ctx,
                reload_source=False,
                scope=scope_name,
                guild_id=guild_id,
            )

        if not all_commands and not str(command_name or "").strip():
            return await ctx.send(
                "reloadcommand ต้องระบุ `command_name` หรือเปิด `all_commands=true`",
                delete_after=10,
            )
        return await self._run_reload_command_flow(
            ctx,
            command_name=command_name,
            all_commands=all_commands,
            scope=scope_name,
            guild_id=guild_id,
        )

    @ownerbot.command(name="reload", help="รีโหลดหน่วยซอร์สของบอท", with_app_command=False)
    @checks.is_owner()
    async def ownerbot_reload(self, ctx: commands.Context):
        await self._run_reload_bot_flow(ctx)

    @ownerbot.command(
        name="reloadslashcommand",
        help="รีโหลดโครงสร้างคำสั่งสแลช",
        with_app_command=False,
    )
    @checks.is_owner()
    async def ownerbot_reloadslashcommand(self, ctx: commands.Context):
        await self._run_reload_slash_flow(ctx, reload_source=False)

    @ownerbot.command(
        name="shutdown",
        help="Shutdown the bot; requires confirm=true (ปิดการทำงานบอท โดยต้องยืนยันด้วย confirm=true)",
        with_app_command=False,
    )
    @checks.is_owner()
    async def ownerbot_shutdown(self, ctx: commands.Context, confirm: bool):
        if not confirm:
            return await ctx.send(
                "ยกเลิกการปิดบอท: โปรดใช้ `confirm: true`",
                delete_after=8,
            )
        await self._run_shutdown_flow(ctx)

    @ownerbot.command(
        name="smoketest",
        with_app_command=True,
        help="Run i18n runtime smoke test for ctx.send / interaction.response / followup / reply / edit",
    )
    @checks.is_owner()
    async def ownerbot_smoketest(self, ctx: commands.Context):
        guild_id = getattr(getattr(ctx, "guild", None), "id", None)
        run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        results: list[str] = []

        def _ok(step: str) -> None:
            results.append(f"✅ {step}")

        def _skip(step: str, reason: str) -> None:
            results.append(f"⏭️ {step} ({reason})")

        def _fail(step: str, error: Exception) -> None:
            results.append(f"❌ {step} ({type(error).__name__}: {error})")

        interaction = getattr(ctx, "interaction", None)

        if interaction is not None:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"[SMOKE {run_id}] interaction.response.send_message | EN/TH probe: Please verify ระบบแปลอัตโนมัติ",
                        ephemeral=True,
                    )
                    _ok("interaction.response.send_message")
                else:
                    _skip("interaction.response.send_message", "already_done")
            except Exception as error:
                _fail("interaction.response.send_message", error)

            followup_msg = None
            try:
                followup_msg = await interaction.followup.send(
                    f"[SMOKE {run_id}] interaction.followup.send | EN/TH probe: โปรดยืนยัน localization wrapper",
                    wait=True,
                )
                _ok("interaction.followup.send")
            except Exception as error:
                _fail("interaction.followup.send", error)

            if followup_msg is not None:
                try:
                    await interaction.followup.edit_message(
                        followup_msg.id,
                        content=f"[SMOKE {run_id}] interaction.followup.edit_message | updated EN/TH probe",
                    )
                    _ok("interaction.followup.edit_message")
                except Exception as error:
                    _fail("interaction.followup.edit_message", error)
            else:
                _skip("interaction.followup.edit_message", "followup_send_failed")
        else:
            _skip("interaction.response.send_message", "prefix_mode")
            _skip("interaction.followup.send", "prefix_mode")
            _skip("interaction.followup.edit_message", "prefix_mode")

        try:
            msg = await ctx.send(
                f"[SMOKE {run_id}] ctx.send | EN/TH probe: Please check this message for runtime localization."
            )
            _ok("ctx.send")
        except Exception as error:
            _fail("ctx.send", error)
            msg = None

        reply_msg = None
        if msg is not None:
            try:
                reply_msg = await msg.reply(
                    f"[SMOKE {run_id}] message.reply | EN/TH probe: โปรดยืนยันว่า reply ถูกแปลตามภาษากิลด์"
                )
                _ok("message.reply")
            except Exception as error:
                _fail("message.reply", error)
        else:
            _skip("message.reply", "ctx_send_failed")

        if reply_msg is not None:
            try:
                await reply_msg.edit(
                    content=f"[SMOKE {run_id}] message.edit | updated EN/TH probe after reply"
                )
                _ok("message.edit")
            except Exception as error:
                _fail("message.edit", error)
        else:
            _skip("message.edit", "reply_failed")

        lang = i18n.guild_lang(guild_id) if guild_id else i18n.DEFAULT_LANG
        summary = "\n".join(f"- {line}" for line in results)
        await ctx.send(
            f"[SMOKE {run_id}] done | guild_lang={lang}\n{summary}"
        )

    @commands.hybrid_command(
        name="reloadbot",
        with_app_command=False,
        help="รีโหลดหน่วยซอร์สของบอท",
        hidden=True,
    )
    @checks.is_owner()
    async def reloadbot(self, ctx: commands.Context):
        await self._run_reload_bot_flow(ctx)

    @commands.hybrid_command(
        name="reloadsl",
        with_app_command=False,
        help="รีโหลดโครงสร้างคำสั่งสแลช",
        hidden=True,
    )
    @checks.is_owner()
    async def reloadsl(self, ctx: commands.Context):
        await self._run_reload_slash_flow(ctx, reload_source=False)

    @commands.hybrid_command(
        name="generate",
        with_app_command=True,
        description="สร้างโค้ดรีดีมได้หลายประเภท",
        help="สร้างโค้ดรีดีมได้หลายประเภท",
        hidden=True,
    )
    @checks.is_owner()
    async def generate(self, ctx: commands.Context):

        try:
            guild_id = getattr(getattr(ctx, "guild", None), "id", None)
            is_th = i18n.guild_lang(guild_id) == "th" if guild_id else False

            selected_code_type = None

            code_validity = None

            async def get_embed():

                embed = discord.Embed(
                    title=i18n.tr("Generate Redeem Code", guild_id), description="", color=color.blue
                )

                usage_line = "/generate"
                if getattr(self.bot, "BotConfig", None):
                    usage_line += f" | {self.bot.BotConfig.PREFIX}generate"
                command_desc = i18n.tr("cmd_generate_redeem_help", guild_id)
                if command_desc == "cmd_generate_redeem_help":
                    command_desc = (
                        "สร้างโค้ดรีดีมได้หลายประเภท" if is_th else "Generate different types of redeemable codes"
                    )
                embed.description += f"**{'คำสั่ง' if is_th else 'Command'}:** `{usage_line}`\n"
                embed.description += f"**{'คำอธิบาย' if is_th else 'Description'}:** `{command_desc}`\n"
                embed.description += f"**{i18n.tr('Selected Code Type:', guild_id)}** `{redeem_code_types[selected_code_type] if selected_code_type else i18n.tr('Undefined', guild_id)}`\n"

                # make code validity like 300 days

                # it will make it formated like 1 year 2 months 3 days

                if code_validity == 0:

                    code_validity_text = i18n.tr("ไม่จำกัด", guild_id)
                    code_expires_text = i18n.tr("ไม่จำกัด", guild_id)

                elif code_validity:

                    code_validity_text = f"{code_validity}{i18n.tr(' Days', guild_id)}"
                    code_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=code_validity)
                    code_expires_text = f"<t:{int(code_expires_at.timestamp())}:R>"

                else:

                    code_validity_text = i18n.tr("Not Set", guild_id)
                    code_expires_text = i18n.tr("Not Set", guild_id)

                embed.description += f"**{i18n.tr('Code Validity:', guild_id)}** `{code_validity_text}`\n"

                embed.description += f"**{i18n.tr('Code Expires:', guild_id)}** {code_expires_text}\n"

                embed.set_thumbnail(url=self.bot.user.display_avatar.url)

                embed.set_footer(
                    text=f"{i18n.tr('Generate Redeem Code requested by', guild_id)} {ctx.author}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            timeout_time = 120

            def reset_timeout(timeout: int = 120):

                nonlocal timeout_time

                timeout_time = timeout

            cancled = False

            async def get_view(disabled=False):

                reset_timeout()

                view = discord.ui.View(timeout=120)

                select_code_type = discord.ui.Select(
                    placeholder=i18n.tr("Select Redeem Code Type", guild_id),
                    options=[
                        discord.SelectOption(
                            label=value,
                            value=key,
                            emoji=self.bot.emoji.PREMIUM,
                            description=(
                                f"สร้าง {value}" if is_th else f"Generate {value} Redeem Code"
                            ),
                            default=True if key == selected_code_type else False,
                        )
                        for key, value in redeem_code_types.items()
                    ],
                    row=0,
                )

                select_code_type.callback = lambda i: select_code_type_callback(i)

                view.add_item(select_code_type)

                valid_for_days_button = discord.ui.Button(
                    label=i18n.tr("Set Code Validity", guild_id),
                    style=discord.ButtonStyle.gray,
                    emoji=self.bot.emoji.TIME,
                    row=1,
                )

                valid_for_days_button.callback = (
                    lambda i: valid_for_days_button_callback(i)
                )

                view.add_item(valid_for_days_button)

                generate_button = discord.ui.Button(
                    label=i18n.tr("Generate Redeem Code", guild_id),
                    style=discord.ButtonStyle.green,
                    emoji=self.bot.emoji.CREATE,
                    row=1,
                )

                generate_button.callback = lambda i: generate_button_callback(i)

                if code_validity == None or not selected_code_type:

                    generate_button.disabled = True

                view.add_item(generate_button)

                cancle_button = discord.ui.Button(
                    label=("ยกเลิก" if is_th else "Cancel"),
                    style=discord.ButtonStyle.gray,
                    emoji=self.bot.emoji.CANCLED,
                    row=2,
                )

                cancle_button.callback = lambda i: cancle_button_callback(i)

                view.add_item(cancle_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def select_code_type_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description=i18n.tr("You are not allowed to use this interaction", guild_id),
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal selected_code_type

                    selected_code_type = interaction.data["values"][0]

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def valid_for_days_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description=i18n.tr("You are not allowed to use this interaction", guild_id),
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    class code_validity_modal(
                        discord.ui.Modal, title=i18n.tr("Set Code Validity", guild_id)
                    ):

                        new_code_validity = discord.ui.TextInput(
                            label=i18n.tr("Enter Code Validity in Days", guild_id),
                            placeholder=i18n.tr("Enter Code Validity in Days", guild_id),
                            min_length=1,
                            required=True,
                            default=(
                                str(code_validity)
                                if (code_validity or code_validity == 0)
                                else "30"
                            ),
                        )

                        async def on_submit(self, interaction: discord.Interaction):

                            if interaction.user.id != ctx.author.id:

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description=i18n.tr("You are not allowed to use this interaction", guild_id),
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                    delete_after=10,
                                )

                            nonlocal code_validity

                            if (
                                not self.new_code_validity.value == ""
                                and not self.new_code_validity.value.isdigit()
                            ):

                                return await interaction.response.send_message(
                                    embed=discord.Embed(
                                        description=i18n.tr("ข้อมูลไม่ถูกต้อง กรุณาใส่ตัวเลขที่ถูกต้อง", guild_id),
                                        color=color.red,
                                    ),
                                    ephemeral=True,
                                    delete_after=10,
                                )

                            code_validity = int(
                                self.new_code_validity.value
                                if self.new_code_validity.value != ""
                                else 0
                            )

                            await interaction.response.edit_message(
                                embed=await get_embed(), view=await get_view()
                            )

                    await interaction.response.send_modal(code_validity_modal())

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def generate_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description=i18n.tr("You are not allowed to use this interaction", guild_id),
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.defer()

                    code = generate_redeem_code()
                    code_expires_at = (
                        None
                        if code_validity == 0
                        else datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=code_validity)
                    )

                    try:

                        await storage.redeem_codes.insert(
                            code=code,
                            code_type="subscription",
                            code_value=selected_code_type,
                            valid_for_days=(
                                None if code_validity == 0 else code_validity
                            ),
                            expires_at=(code_expires_at.isoformat() if code_expires_at else None),
                            claimed=False,
                            claimed_by=None,
                            claimed_at=None,
                        )

                        await interaction.followup.send(
                            embed=discord.Embed(
                                title=i18n.tr("Generated Redeem Code", guild_id),
                                description=f"**||```prolog\n{code}```||**",
                                color=color.green,
                            ),
                            ephemeral=True,
                        )

                        await interaction.message.delete()

                        try:

                            await interaction.user.send(
                                content=f"{i18n.tr('Redeem Code For', guild_id)} **`{redeem_code_types[selected_code_type]}`**",
                                embed=discord.Embed(
                                    title=i18n.tr("Generated Redeem Code", guild_id),
                                    description=f"**||```prolog\n{code}```||**",
                                    color=color.green,
                                ),
                            )

                        except Exception:
                            pass

                    except Exception as e:

                        await interaction.followup.send(
                            embed=discord.Embed(
                                description=f"{i18n.tr('Failed to generate redeem code', guild_id)}: {e}",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description=i18n.tr("You are not allowed to use this interaction", guild_id),
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view(True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                if timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                timeout_time -= 1

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.group(
        name="blacklist",
        help="จัดการบัญชีดำผู้ใช้/กิลด์",
        hidden=True,
        invoke_without_command=True,
    )
    @checks.is_owner()
    async def blacklist(self, ctx: commands.Context):

        try:

            embed = discord.Embed(
                title="คำสั่งแบล็กลิสต์",
                description="นี่คือรายการคำสั่งแบล็กลิสต์\n",
                color=color.blue,
            )

            if hasattr(ctx.command, "commands"):

                for command in ctx.command.commands:

                    embed.description += f"`{self.bot.BotConfig.PREFIX}{ctx.command.name} {command.name}` - {command.help}\n"

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @blacklist.group(
        name="user", help="บัญชีดำผู้ใช้", hidden=True, invoke_without_command=True
    )
    @checks.is_owner()
    async def blacklist_user(self, ctx: commands.Context):

        try:

            embed = discord.Embed(
                title="คำสั่งแบล็กลิสต์ผู้ใช้",
                description="นี่คือรายการคำสั่งแบล็กลิสต์ผู้ใช้\n",
                color=color.blue,
            )

            if hasattr(ctx.command, "commands"):

                for command in ctx.command.commands:

                    embed.description += f"`{self.bot.BotConfig.PREFIX}{ctx.command.parent.name} {ctx.command.name} {command.name}` - {command.help}\n"

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @blacklist_user.command(name="add", help="เพิ่มผู้ใช้เข้าบัญชีดำ", hidden=True)
    @checks.is_owner()
    async def blacklist_user_add(self, ctx: commands.Context, user: discord.User):

        try:

            if str(user.id) in self.bot.cache.ban_data.get("users", {}):

                return await ctx.send(f"User is already blacklisted.")

            await storage.ban_data.insert(
                user_id=user.id,
            )

            await ctx.send(f"User is blacklisted.")

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @blacklist_user.command(name="remove", help="ลบผู้ใช้ออกจากบัญชีดำ", hidden=True)
    @checks.is_owner()
    async def blacklist_user_remove(self, ctx: commands.Context, user: discord.User):

        try:

            if str(user.id) not in self.bot.cache.ban_data.get("users", {}):

                return await ctx.send(f"User is not blacklisted.")

            await storage.ban_data.delete(
                user_id=user.id,
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"User is unblacklisted.", color=color.green
                )
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @blacklist_user.command(name="list", help="แสดงรายการผู้ใช้บัญชีดำ", hidden=True)
    @checks.is_owner()
    async def blacklist_user_list(self, ctx: commands.Context):

        try:

            blacklisted_users = self.bot.cache.ban_data.get("users", {})

            if not blacklisted_users:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีผู้ใช้ที่ถูกแบล็กลิสต์", color=color.red
                    ),
                    delete_after=10,
                )

            blacklisted_users = list(blacklisted_users.keys())

            # make blacklisted_users 5 by 5 list

            blacklisted_users = [
                blacklisted_users[i : i + 5]
                for i in range(0, len(blacklisted_users), 5)
            ]

            current_page_index = 0

            view_timeout = 60

            cancled = False

            def reset_view_timeout():

                nonlocal view_timeout

                view_timeout = 60

            async def get_embed():

                nonlocal blacklisted_users, current_page_index

                embed = discord.Embed(
                    title="ผู้ใช้ที่ถูกแบล็กลิสต์", color=color.random_color()
                )

                embed.description = ", ".join(
                    [
                        f"<@{user_id}>"
                        for user_id in blacklisted_users[current_page_index]
                    ]
                )

                embed.set_footer(
                    text=f"Page {current_page_index+1}/{len(blacklisted_users)}"
                )

                return embed

            async def get_view(disabled=False):

                nonlocal view_timeout

                reset_view_timeout()

                view = discord.ui.View()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.danger,
                    emoji=self.bot.emoji.STOP,
                    row=0,
                    disabled=len(blacklisted_users) == 1,
                )

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(blacklisted_users) - 1,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout -= 1

                if view_timeout <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                embed=discord.Embed(
                    description="An ข้อผิดพลาด occurred while listing blacklisted users",
                    color=color.red,
                ),
                delete_after=10,
            )

    @blacklist.group(
        name="guild", help="บัญชีดำกิลด์", hidden=True, invoke_without_command=True
    )
    @checks.is_owner()
    async def blacklist_guild(self, ctx: commands.Context):

        try:

            embed = discord.Embed(
                title="คำสั่งแบล็กลิสต์กิลด์",
                description="นี่คือรายการคำสั่งแบล็กลิสต์กิลด์\n",
                color=color.blue,
            )

            if hasattr(ctx.command, "commands"):

                for command in ctx.command.commands:

                    embed.description += f"`{self.bot.BotConfig.PREFIX}{ctx.command.parent.name} {ctx.command.name} {command.name}` - {command.help}\n"

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @blacklist_guild.command(name="add", help="เพิ่มกิลด์เข้าบัญชีดำ", hidden=True)
    @checks.is_owner()
    async def blacklist_guild_add(self, ctx: commands.Context, guild: discord.Guild):

        try:

            if str(guild.id) in self.bot.cache.ban_data.get("guilds", {}):

                return await ctx.send(f"Guild is already blacklisted.")

            await storage.ban_data.insert(
                guild_id=guild.id,
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"Guild is blacklisted.", color=color.green
                )
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @blacklist_guild.command(name="remove", help="ลบกิลด์ออกจากบัญชีดำ", hidden=True)
    @checks.is_owner()
    async def blacklist_guild_remove(self, ctx: commands.Context, guild: discord.Guild):

        try:

            if str(guild.id) not in self.bot.cache.ban_data.get("guilds", {}):

                return await ctx.send(f"Guild is not blacklisted.")

            await storage.ban_data.delete(
                guild_id=guild.id,
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"Guild is unblacklisted.", color=color.green
                )
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @blacklist_guild.command(name="list", help="แสดงรายการกิลด์บัญชีดำ", hidden=True)
    @checks.is_owner()
    async def blacklist_guild_list(self, ctx: commands.Context):

        try:

            blacklisted_guilds = self.bot.cache.ban_data.get("guilds", {})

            if not blacklisted_guilds:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีกิลด์ที่ถูกแบล็กลิสต์", color=color.red
                    ),
                    delete_after=10,
                )

            blacklisted_guilds = list(blacklisted_guilds.keys())

            # make blacklisted_guilds 5 by 5 list

            blacklisted_guilds = [
                blacklisted_guilds[i : i + 5]
                for i in range(0, len(blacklisted_guilds), 5)
            ]

            current_page_index = 0

            view_timeout = 60

            cancled = False

            def reset_view_timeout():

                nonlocal view_timeout

                view_timeout = 60

            async def get_embed():

                nonlocal blacklisted_guilds, current_page_index

                embed = discord.Embed(
                    title="กิลด์ที่ถูกแบล็กลิสต์", color=color.random_color()
                )

                embed.description = ", ".join(
                    [
                        f"<@{guild_id}>"
                        for guild_id in blacklisted_guilds[current_page_index]
                    ]
                )

                embed.set_footer(
                    text=f"Page {current_page_index+1}/{len(blacklisted_guilds)}"
                )

                return embed

            async def get_view(disabled=False):

                nonlocal view_timeout

                reset_view_timeout()

                view = discord.ui.View()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.danger,
                    emoji=self.bot.emoji.STOP,
                    row=0,
                    disabled=len(blacklisted_guilds) == 1,
                )

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(blacklisted_guilds) - 1,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout -= 1

                if view_timeout <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                embed=discord.Embed(
                    description="An ข้อผิดพลาด occurred while listing blacklisted guilds",
                    color=color.red,
                ),
                delete_after=10,
            )

    @blacklist.command(name="list", help="แสดงรายการผู้ใช้และกิลด์ในบัญชีดำ", hidden=True)
    @checks.is_owner()
    async def blacklist_list(self, ctx: commands.Context):

        try:

            blacklisted_users = self.bot.cache.ban_data.get("users", {})

            blacklisted_guilds = self.bot.cache.ban_data.get("guilds", {})

            if not blacklisted_users and not blacklisted_guilds:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีผู้ใช้/กิลด์ที่ถูกแบล็กลิสต์", color=color.red
                    ),
                    delete_after=10,
                )

            blacklisted_users = list(blacklisted_users.keys())

            blacklisted_guilds = list(blacklisted_guilds.keys())

            # make blacklisted_users 5 by 5 list

            blacklisted_users = [
                blacklisted_users[i : i + 5]
                for i in range(0, len(blacklisted_users), 5)
            ]

            blacklisted_guilds = [
                blacklisted_guilds[i : i + 5]
                for i in range(0, len(blacklisted_guilds), 5)
            ]

            current_page_index = 0

            view_timeout = 60

            cancled = False

            def reset_view_timeout():

                nonlocal view_timeout

                view_timeout = 60

            async def get_embed():

                nonlocal blacklisted_users, blacklisted_guilds, current_page_index

                embed = discord.Embed(
                    title="ผู้ใช้ที่ถูกแบล็กลิสต์/Guilds", color=color.random_color()
                )

                embed.description = f"**Users:**\n"

                embed.description += ", ".join(
                    [
                        f"<@{user_id}>"
                        for user_id in blacklisted_users[current_page_index]
                    ]
                )

                embed.description += f"\n\n**Guilds:**\n"

                embed.description += ", ".join(
                    [
                        f"<@{guild_id}>"
                        for guild_id in blacklisted_guilds[current_page_index]
                    ]
                )

                embed.set_footer(
                    text=f"Page {current_page_index+1}/{len(blacklisted_users)}"
                )

                return embed

            async def get_view(disabled=False):

                nonlocal view_timeout

                reset_view_timeout()

                view = discord.ui.View()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.danger,
                    emoji=self.bot.emoji.STOP,
                    row=0,
                    disabled=len(blacklisted_users) == 1,
                )

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(blacklisted_users) - 1,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout -= 1

                if view_timeout <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                embed=discord.Embed(
                    description="An ข้อผิดพลาด occurred while listing blacklisted users/guilds",
                    color=color.red,
                ),
                delete_after=10,
            )

    @root.command(name="tree", help="แสดงโครงสร้างโค้ด", hidden=True)
    @checks.is_owner()
    async def tree(self, ctx: commands.Context):

        try:

            tree_string_chunks = generate_directory_tree_string_split_text(1950)

            for message in tree_string_chunks:

                await ctx.send(f"```prolog\n{message}```")

        except Exception as e:

            await ctx.send(f"ข้อผิดพลาด: {e}")

    @root.command(name="server", help="แสดงข้อมูลเซิร์ฟเวอร์", hidden=True)
    @checks.is_owner()
    async def server(self, ctx: commands.Context, guild: discord.Guild):

        try:

            if not guild:

                return await ctx.send(
                    embed=discord.Embed(description="ไม่พบกิลด์", color=color.red),
                    delete_after=10,
                )

            total_member_in_vc = 0

            for channel in guild.voice_channels:

                total_member_in_vc += len(
                    [member for member in channel.members if not member.bot]
                )

            embed = discord.Embed(title=f"Server Info", color=color.random_color())

            invite_text = (
                f"\n> Invite: [Click Here]({guild.vanity_url})"
                if guild.vanity_url
                else ""
            )

            members_in_vc_text = (
                f"\n> Members in VC: `{total_member_in_vc}`"
                if total_member_in_vc
                else ""
            )

            guild_subscription = str(
                self.bot.cache.guilds.get(str(guild.id), {}).get("subscription", "Free")
            ).capitalize()

            embed.add_field(
                name=f"{guild.name}",
                value=(
                    f"> Members: {len(guild.members)}\n"
                    f"> ID: {guild.id}\n"
                    f"> Has Admin: `{guild.me.guild_permissions.administrator}`\n"
                    f"> Subscription: `{guild_subscription}`"
                    f"{invite_text}"
                    f"{members_in_vc_text}"
                ),
                inline=True,
            )

            embed.set_thumbnail(
                url=guild.icon.url if guild.icon else guild.me.display_avatar.url
            )

            await ctx.send(embed=embed)

        except Exception as e:

            await ctx.send(f"ข้อผิดพลาด: {e}")

    @root.command(
        name="servers", help="แสดงรายชื่อเซิร์ฟเวอร์ที่บอทอยู่", hidden=True
    )
    @checks.is_owner()
    async def servers(self, ctx: commands.Context):

        try:

            # make guilds 5 by 5 list

            high_to_low = lambda x: len(x.members)

            guilds = sorted(self.bot.guilds, key=high_to_low, reverse=True)

            all_guilds = [guilds[i : i + 20] for i in range(0, len(guilds), 20)]

            current_page_index = 0

            view_timeout = 120

            cancled = False

            def reset_view_timeout():

                nonlocal view_timeout

                view_timeout = 120

            async def get_embed():

                embed = discord.Embed(
                    title=f"Total Servers ({len(guilds)})", color=color.random_color()
                )

                guilds_data = all_guilds[current_page_index]

                for guild in guilds_data:

                    total_member_in_vc = 0

                    for channel in guild.voice_channels:

                        total_member_in_vc += len(
                            [member for member in channel.members if not member.bot]
                        )

                    invite_text = (
                        f"\n> Invite: [Click Here]({guild.vanity_url})"
                        if guild.vanity_url
                        else ""
                    )

                    members_in_vc_text = (
                        f"\n> Members in VC: `{total_member_in_vc}`"
                        if total_member_in_vc
                        else ""
                    )

                    guild_subscription = str(
                        self.bot.cache.guilds.get(str(guild.id), {}).get(
                            "subscription", "Free"
                        )
                    ).capitalize()

                    embed.add_field(
                        name=f"{guild.name}",
                        value=(
                            f"> Members: {len(guild.members)}\n"
                            f"> ID: {guild.id}\n"
                            f"> Has Admin: `{guild.me.guild_permissions.administrator}`\n"
                            f"> Subscription: `{guild_subscription}`"
                            f"{invite_text}"
                            f"{members_in_vc_text}"
                        ),
                        inline=True,
                    )

                embed.set_footer(text=f"Page {current_page_index+1}/{len(all_guilds)}")

                return embed

            async def get_view(disabled=False):

                nonlocal view_timeout

                reset_view_timeout()

                view = discord.ui.View()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.danger,
                    emoji=self.bot.emoji.STOP,
                    row=0,
                    disabled=len(all_guilds) == 1,
                )

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(all_guilds) - 1,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout -= 1

                if view_timeout <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @root.command(
        name="leaveserver", help="ออกจากเซิร์ฟเวอร์", hidden=True, aliases=["leaveguild"]
    )
    @checks.is_owner()
    async def leaveserver(self, ctx: commands.Context, guild_id: int):

        try:

            guild = await self.bot.fetch_guild(guild_id)

            if not guild:

                return await ctx.send(
                    embed=discord.Embed(description="ไม่พบกิลด์", color=color.red),
                    delete_after=10,
                )

            await guild.leave()

            await ctx.send(
                embed=discord.Embed(
                    description=f"Left the server **{guild.name}**", color=color.green
                )
            )

        except Exception as e:

            await ctx.send(f"ข้อผิดพลาด: {e}")

    @root.command(
        name="serverinvite",
        help="สร้างลิงก์เชิญเซิร์ฟเวอร์",
        hidden=True,
        aliases=["serverinv", "serverlink"],
    )
    @checks.is_owner()
    async def serverinvite(self, ctx: commands.Context, guild_id: int):

        try:

            guild = await self.bot.fetch_guild(guild_id)

            if not guild:

                return await ctx.send(
                    embed=discord.Embed(description="ไม่พบกิลด์", color=color.red),
                    delete_after=10,
                )

            if not guild.vanity_url:

                channels = await guild.fetch_channels()

                channels = [
                    channel
                    for channel in channels
                    if isinstance(channel, discord.TextChannel)
                ]

                invite = await channels[0].create_invite()

                invite = invite.url

            else:

                invite = guild.vanity_url

            await ctx.send(
                embed=discord.Embed(
                    description=f"**{guild.name}** Invite: {invite}", color=color.green
                )
            )

        except Exception as e:

            await ctx.send(f"ข้อผิดพลาด: {e}")

    @root.command(
        name="python", help="รันโค้ดไพธอน", hidden=True, aliases=["py"]
    )
    @checks.is_owner()
    async def python(self, ctx: commands.Context, *, code: str):

        try:

            # Remove code block formatting

            code = code.replace("```", "").replace("py", "").strip()

            # Prepare the environment

            env = {
                "ctx": ctx,
                "bot": self.bot,
                "discord": discord,
                "commands": commands,
                "__import__": __import__,
            }

            # Capture the output

            stdout = StringIO()

            # Define the code execution

            exec_code = f'async def _exec(ctx):\n{textwrap.indent(code, "    ")}'

            # Compile and execute the code

            exec(exec_code, env)

            async def run_code():

                with redirect_stdout(stdout):

                    await env["_exec"](ctx)

            # Run the code with a timeout (max 5 seconds)

            await asyncio.wait_for(run_code(), timeout=5)

            # Output the result

            result = stdout.getvalue()

            if result:

                await ctx.send(f"```\n{result}\n```")

            else:

                await ctx.send("`No output.`")

        except asyncio.TimeoutError:

            await ctx.send("ข้อผิดพลาด: Code execution took too long (max 5s).")

        except Exception as e:

            await ctx.send(f"ข้อผิดพลาด: {e}")

    @root.command(
        name="emojis", help="แสดงรายการอีโมจิที่บอทมี", hidden=True
    )
    @checks.is_owner()
    async def emojis(self, ctx: commands.Context):

        try:

            from skylinebot.style import emoji

            # get all the variables from emoji.py

            emoji_vars = [var for var in dir(emoji) if not var.startswith("__")]

            # sort them by alphabetical order

            emoji_vars = sorted(emoji_vars)

            # make emoji_vars 5 by 5 list

            emoji_vars = [emoji_vars[i : i + 1] for i in range(0, len(emoji_vars), 1)]

            # make 20 by 20 emoji_vars

            sorted_emoji_vars = [
                emoji_vars[i : i + 20] for i in range(0, len(emoji_vars), 20)
            ]

            for emoji_vars in sorted_emoji_vars:

                # name it like emoji - emoji1 | emoji - emoji2 | emoji - emoji3

                emoji_vars = [
                    f" | ".join([f"{var} : {getattr(emoji,var)}" for var in emoji_var])
                    for emoji_var in emoji_vars
                ]

                await ctx.send(
                    embed=discord.Embed(
                        description="\n".join(emoji_vars), color=color.random_color()
                    )
                )

        except Exception as e:

            await ctx.send(f"ข้อผิดพลาด: {e}")

    @root.command(
        name="givebalance",
        help="เพิ่มยอดเงินให้ผู้ใช้",
        aliases=["givebal", "givecoins", "givecoin"],
        hidden=True,
    )
    @checks.is_owner()
    async def givebalance(self, ctx: commands.Context, user: discord.User, amount: int):

        try:

            message = await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.LOADING} Giving balance...",
                    color=color.orange,
                )
            )

            if amount < 0:

                return await message.edit(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | Amount cannot be negative",
                        color=color.red,
                    )
                )

            user_data = self.bot.cache.users.get(str(user.id), {})

            if not user_data:

                user_data = await storage.users.get(id=user.id)

            user_data = self.bot.cache.users.get(str(user.id), {})

            await storage.users.update(
                id=self.bot.cache.users.get(str(user.id), {}).get("id"),
                balance=self.bot.cache.users.get(str(user.id), {}).get("balance", 0)
                + amount,
            )

            await message.edit(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.SUCCESS} | {user.display_name} | Current Balance: `{get_formatted_balance(self.bot.cache.users.get(str(user.id),{}).get('balance',0))}`{self.bot.emoji.COIN}",
                    color=color.green,
                )
            )

        except Exception as e:

            await message.edit(
                embed=discord.Embed(description=f"ข้อผิดพลาด: {e}", color=color.red)
            )

    @root.command(
        name="removebalance",
        help="ลดยอดเงินของผู้ใช้",
        aliases=["removebal", "removecoins", "removecoin"],
        hidden=True,
    )
    @checks.is_owner()
    async def removebalance(
        self, ctx: commands.Context, user: discord.User, amount: int
    ):

        try:

            message = await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.LOADING} Removing balance...",
                    color=color.orange,
                )
            )

            if amount < 0:

                return await message.edit(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | Amount cannot be negative",
                        color=color.red,
                    )
                )

            user_data = self.bot.cache.users.get(str(user.id), {})

            if not user_data:

                user_data = await storage.users.get(id=user.id)

            user_data = self.bot.cache.users.get(str(user.id), {})

            await storage.users.update(
                id=self.bot.cache.users.get(str(user.id), {}).get("id"),
                balance=(
                    self.bot.cache.users.get(str(user.id), {}).get("balance", 0)
                    - amount
                    if self.bot.cache.users.get(str(user.id), {}).get("balance", 0)
                    - amount
                    >= 0
                    else 0
                ),
            )

            await message.edit(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.SUCCESS} | {user.display_name} | Current Balance: `{get_formatted_balance(self.bot.cache.users.get(str(user.id),{}).get('balance',0))}`{self.bot.emoji.COIN}",
                    color=color.green,
                )
            )

        except Exception as e:

            await message.edit(
                embed=discord.Embed(description=f"ข้อผิดพลาด: {e}", color=color.red)
            )

    @root.command(
        name="setbalance",
        help="ตั้งค่ายอดเงินของผู้ใช้",
        aliases=["setbal", "setcoins", "setcoin"],
        hidden=True,
    )
    @checks.is_owner()
    async def setbalance(self, ctx: commands.Context, user: discord.User, amount: int):

        try:

            message = await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.LOADING} Setting balance...",
                    color=color.orange,
                )
            )

            user_data = self.bot.cache.users.get(str(user.id), {})

            if not user_data:

                user_data = await storage.users.get(id=user.id)

            user_data = self.bot.cache.users.get(str(user.id), {})

            await storage.users.update(
                id=self.bot.cache.users.get(str(user.id), {}).get("id"),
                balance=amount if amount >= 0 else 0,
            )

            await message.edit(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.SUCCESS} | {user.display_name} | Current Balance: `{get_formatted_balance(self.bot.cache.users.get(str(user.id),{}).get('balance',0))}`{self.bot.emoji.COIN}",
                    color=color.green,
                )
            )

        except Exception as e:

            await message.edit(
                embed=discord.Embed(description=f"ข้อผิดพลาด: {e}", color=color.red)
            )

    # @root.command(

    #     name="shop",

    #     help="แสดงร้านค้าเพื่อแก้ไขไอเท็ม",

    #     hidden=True

    # )

    # @checks.is_owner()

    # async def root_shop(self, ctx:commands.Context):

    #     try:

    #         async def get_embed():

    #             shop_data = self.bot.cache.shop

    #             embed = discord.Embed(

    #                 title="Root Shop",

    #                 description="",

    #                 color=color.orange

    #             )

    #             embed.set_author(

    #                 name=self.bot.user.display_name,

    #                 icon_url=self.bot.user.display_avatar.url

    #             )

    #             embed.set_footer(

    #                 text=f"Requested by {ctx.author.display_name}",

    #                 icon_url=ctx.author.display_avatar.url

    #             )

    #             for item, data in shop_data.items():

    #                 embed.description += f"> **{item}** - {data['name']} - `{data['price']}`{self.bot.emoji.COIN}\n\n"

    #             return embed

    #         timeout_time = 600

    #         cancled = False

    #         def refresh_timeout_time():

    #             nonlocal timeout_time

    #             timeout_time = 600

    #         async def get_view(disabled=False):

    #             shop_data = self.bot.cache.shop

    #             view = discord.ui.View(timeout=600)

    #             refresh_timeout_time()

    #             add_item = discord.ui.Button(

    #                 style=discord.ButtonStyle.green,

    #                 label="Add Item",

    #                 emoji=self.bot.emoji.CREATE,

    #                 row=0

    #             )

    #             add_item.callback = lambda i: add_item_callback(i)

    #             view.add_item(add_item)

    #             remove_item = discord.ui.Button(

    #                 style=discord.ButtonStyle.red,

    #                 label="ลบไอเท็ม",

    #                 emoji=self.bot.emoji.DELETE,

    #                 row=0,

    #                 disabled=not shop_data

    #             )

    #             remove_item.callback = lambda i: remove_item_callback(i)

    #             view.add_item(remove_item)

    #             cancel = discord.ui.Button(

    #                 style=discord.ButtonStyle.gray,

    #                 label="Cancel",

    #                 emoji=self.bot.emoji.CANCLED,

    #                 row=0,

    #             )

    #             cancel.callback = lambda i: cancel_callback(i)

    #             view.add_item(cancel)

    #             select_to_edit = discord.ui.Select(

    #                 placeholder="Select an item to edit",

    #                 options=[discord.SelectOption(label=str(data.get('name',"Undefined")).capitalize(),value=item) for item,data in shop_data.items()] if shop_data else [],

    #                 min_values=1,

    #                 max_values=1,

    #                 row=1

    #             )

    #             select_to_edit.callback = lambda i: select_to_edit_callback(i)

    #             if shop_data:

    #                 view.add_item(select_to_edit)

    #             if disabled:

    #                 for item in view.children:

    #                     item.disabled = True

    #             return view

    #         async def cancel_callback(interaction:discord.Interaction):

    #             try:

    #                 if interaction.user.id != ctx.author.id:

    #                     return await interaction.response.send_message(embed=discord.Embed(description="คุณไม่มีสิทธิ์โต้ตอบกับข้อความนี้",color=color.red),ephemeral=True,delete_after=5)

    #                 nonlocal cancled

    #                 cancled = True

    #                 await interaction.response.edit_message(embed=await get_embed(),view=await get_view(disabled=True))

    #             except Exception as e:

    #                 logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #         async def add_item_callback(interaction:discord.Interaction):

    #             try:

    #                 if interaction.user.id != ctx.author.id:

    #                     return await interaction.response.send_message(embed=discord.Embed(description="คุณไม่มีสิทธิ์โต้ตอบกับข้อความนี้",color=color.red),ephemeral=True,delete_after=5)

    #                 class add_item_modal(discord.ui.Modal,title="Add New Item"):

    #                     new_item_name_field = discord.ui.TextInput(

    #                         placeholder="ใส่ชื่อไอเท็ม",

    #                         label="ชื่อไอเท็ม",

    #                         style=discord.TextStyle.short,

    #                         row=0

    #                     )

    #                     new_item_description_field = discord.ui.TextInput(

    #                         placeholder="ใส่รายละเอียดไอเท็ม",

    #                         label="รายละเอียดไอเท็ม",

    #                         style=discord.TextStyle.long,

    #                         row=1

    #                     )

    #                     new_item_price_field = discord.ui.TextInput(

    #                         placeholder="ใส่ราคาไอเท็ม",

    #                         label="ราคาไอเท็ม",

    #                         style=discord.TextStyle.short,

    #                         row=2

    #                     )

    #                     new_item_image_url_field = discord.ui.TextInput(

    #                         placeholder="ใส่ลิงก์รูปไอเท็ม",

    #                         label="ลิงก์รูปไอเท็ม",

    #                         style=discord.TextStyle.short,

    #                         required=False,

    #                         row=3

    #                     )

    #                     bot = self.bot

    #                     async def on_submit(self, interaction:discord.Interaction):

    #                         try:

    #                             new_item_name = self.new_item_name_field.value

    #                             new_item_description = self.new_item_description_field.value

    #                             new_item_price = self.new_item_price_field.value

    #                             new_item_image_url = self.new_item_image_url_field.value

    #                             shop_data = self.bot.cache.shop

    #                             def check_existing_item(name:str):

    #                                 for item in shop_data:

    #                                     if shop_data[item].get('name') == name:

    #                                         return True

    #                                 return False

    #                             if check_existing_item(new_item_name.lower()):

    #                                 return await interaction.response.send_message(embed=discord.Embed(description="An item with that name already exists",color=color.red),ephemeral=True,delete_after=5)

    #                             try:

    #                                 new_item_price = float(new_item_price)

    #                             except:

    #                                 return await interaction.response.send_message(embed=discord.Embed(description="ราคาที่ระบุไม่ถูกต้อง",color=color.red),ephemeral=True,delete_after=5)

    #                             await interaction.response.defer()

    #                             await storage.shop.insert(

    #                                 name=new_item_name.lower(),

    #                                 description=new_item_description,

    #                                 price=new_item_price,

    #                                 image_url=new_item_image_url

    #                             )

    #                             await interaction.message.edit(embed=await get_embed(),view=await get_view())

    #                             temp_message = await interaction.followup.send(embed=discord.Embed(description=f"Item {new_item_name} has been added",color=color.green),ephemeral=True)

    #                             await asyncio.sleep(5)

    #                             try:

    #                                 await temp_message.delete()

    #                             except:

    #                                 pass

    #                         except Exception as e:

    #                             logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #                             await interaction.response.send_message(embed=discord.Embed(description="An error occured",color=color.red),ephemeral=True,delete_after=5)

    #                 await interaction.response.send_modal(add_item_modal())

    #             except Exception as e:

    #                 logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #                 await interaction.response.send_message(embed=discord.Embed(description="An error occured",color=color.red),ephemeral=True,delete_after=5)

    #         async def remove_item_callback(interaction:discord.Interaction):

    #             try:

    #                 if interaction.user.id != ctx.author.id:

    #                     return await interaction.response.send_message(embed=discord.Embed(description="คุณไม่มีสิทธิ์โต้ตอบกับข้อความนี้",color=color.red),ephemeral=True,delete_after=5)

    #                 class remove_item_modal(discord.ui.Modal,title="ลบไอเท็ม"):

    #                     item_id_field = discord.ui.TextInput(

    #                         placeholder="Enter the item id",

    #                         label="Item ID",

    #                         style=discord.TextStyle.short,

    #                         row=0

    #                     )

    #                     bot = self.bot

    #                     async def on_submit(self, interaction:discord.Interaction):

    #                         try:

    #                             item_id = self.item_id_field.value

    #                             shop_data = self.bot.cache.shop

    #                             if item_id not in shop_data:

    #                                 return await interaction.response.send_message(embed=discord.Embed(description="ไม่พบไอเท็ม",color=color.red),ephemeral=True,delete_after=5)

    #                             await interaction.response.defer()

    #                             await storage.shop.delete(

    #                                 id=shop_data[item_id].get('id')

    #                             )

    #                             await interaction.message.edit(embed=await get_embed(),view=await get_view())

    #                             temp_message = await interaction.followup.send(embed=discord.Embed(description=f"Item {item_id} has been removed",color=color.green),ephemeral=True)

    #                             await asyncio.sleep(5)

    #                             try:

    #                                 await temp_message.delete()

    #                             except:

    #                                 pass

    #                         except Exception as e:

    #                             logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #                             await interaction.response.send_message(embed=discord.Embed(description="An error occured",color=color.red),ephemeral=True,delete_after=5)

    #                 await interaction.response.send_modal(remove_item_modal())

    #             except Exception as e:

    #                 logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #                 await interaction.response.send_message(embed=discord.Embed(description="An error occured",color=color.red),ephemeral=True,delete_after=5)

    #         async def select_to_edit_callback(interaction:discord.Interaction):

    #             try:

    #                 if interaction.user.id != ctx.author.id:

    #                     return await interaction.response.send_message(embed=discord.Embed(description="คุณไม่มีสิทธิ์โต้ตอบกับข้อความนี้",color=color.red),ephemeral=True,delete_after=5)

    #                 shop_data = self.bot.cache.shop

    #                 selected_item = interaction.data.get('values')[0]

    #                 selected_data = shop_data.get(selected_item)

    #                 if not selected_data:

    #                     return await interaction.response.send_message(embed=discord.Embed(description="ไม่พบไอเท็ม",color=color.red),ephemeral=True,delete_after=5)

    #                 class edit_item_modal(discord.ui.Modal,title="แก้ไขไอเท็ม"):

    #                     new_item_name_field = discord.ui.TextInput(

    #                         placeholder="ใส่ชื่อไอเท็ม",

    #                         label="ชื่อไอเท็ม",

    #                         style=discord.TextStyle.short,

    #                         row=0,

    #                         default=selected_data.get('name',"")

    #                     )

    #                     new_item_description_field = discord.ui.TextInput(

    #                         placeholder="ใส่รายละเอียดไอเท็ม",

    #                         label="รายละเอียดไอเท็ม",

    #                         style=discord.TextStyle.long,

    #                         row=1,

    #                         default=selected_data.get('description',"")

    #                     )

    #                     new_item_price_field = discord.ui.TextInput(

    #                         placeholder="ใส่ราคาไอเท็ม",

    #                         label="ราคาไอเท็ม",

    #                         style=discord.TextStyle.short,

    #                         row=2,

    #                         default=selected_data.get('price',"")

    #                     )

    #                     new_item_image_url_field = discord.ui.TextInput(

    #                         placeholder="ใส่ลิงก์รูปไอเท็ม",

    #                         label="ลิงก์รูปไอเท็ม",

    #                         style=discord.TextStyle.short,

    #                         required=False,

    #                         row=1,

    #                         default=selected_data.get('image_url',"")

    #                     )

    #                     bot = self.bot

    #                     async def on_submit(self, interaction:discord.Interaction):

    #                         try:

    #                             item_id = self.item_id_field.value

    #                             new_item_name = self.new_item_name_field.value

    #                             new_item_description = self.new_item_description_field.value

    #                             new_item_price = self.new_item_price_field.value

    #                             new_item_image_url = self.new_item_image_url_field.value

    #                             shop_data = self.bot.cache.shop

    #                             if item_id not in shop_data:

    #                                 return await interaction.response.send_message(embed=discord.Embed(description="ไม่พบไอเท็ม",color=color.red),ephemeral=True,delete_after=5)

    #                             try:

    #                                 new_item_price = float(new_item_price)

    #                             except:

    #                                 return await interaction.response.send_message(embed=discord.Embed(description="ราคาที่ระบุไม่ถูกต้อง",color=color.red),ephemeral=True,delete_after=5)

    #                             await interaction.response.defer()

    #                             await storage.shop.update(

    #                                 id=shop_data[item_id].get('id'),

    #                                 name=new_item_name.lower(),

    #                                 description=new_item_description,

    #                                 price=new_item_price,

    #                                 image_url=new_item_image_url

    #                             )

    #                             await interaction.message.edit(embed=await get_embed(),view=await get_view())

    #                             temp_message = await interaction.followup.send(embed=discord.Embed(description=f"Item {new_item_name} has been updated",color=color.green),ephemeral=True)

    #                             await asyncio.sleep(5)

    #                             try:

    #                                 await temp_message.delete()

    #                             except:

    #                                 pass

    #                         except Exception as e:

    #                             logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #                             await interaction.response.send_message(embed=discord.Embed(description="An error occured",color=color.red),ephemeral=True,delete_after=5)

    #                 await interaction.response.send_modal(edit_item_modal())

    #             except Exception as e:

    #                 logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #                 await interaction.response.send_message(embed=discord.Embed(description="An error occured",color=color.red),ephemeral=True,delete_after=5)

    #         message = await ctx.send(embed=await get_embed(),view=await get_view())

    #         while not cancled:

    #             try:

    #                 await asyncio.sleep(1)

    #                 if timeout_time <= 0:

    #                     await message.edit(view=await get_view(disabled=True))

    #                     break

    #                 timeout_time -= 1

    #             except Exception as e:

    #                 logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    #                 break

    #     except Exception as e:

    #         logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @root.command(
        name="lavalinks",
        aliases=["nodes"],
        help="Show all connected Lavalink nodes (ดูข้อมูลโหนด Lavalink ที่เชื่อมต่อทั้งหมด)",
        description="Show all connected Lavalink nodes (ดูข้อมูลโหนด Lavalink ที่เชื่อมต่อทั้งหมด)",
    )
    @checks.is_owner()
    async def lavalinks(self, ctx: commands.Context):

        try:

            all_nodes = wavelink.Pool.nodes

            if not all_nodes:

                return await ctx.send("No Lavalink nodes are connected.")

            # make a list of all nodes 5 by 5

            nodes_list = [
                list(all_nodes.values())[i : i + 5] for i in range(0, len(all_nodes), 5)
            ]

            current_page_index = 0

            async def get_embed():

                nodes = nodes_list[current_page_index]

                embed = discord.Embed(
                    title="โหนด Lavalink",
                    description=f"จำนวนโหนดทั้งหมด: {len(all_nodes)}",
                    color=color.blue,
                )

                embed.set_footer(
                    text=f"Page {current_page_index + 1}/{len(nodes_list)}"
                )

                embed.description += "\n\n"

                for node in nodes:

                    embed.description += f"**{node.uri}**\n"

                    embed.description += f"Status: {node.status.name}\n"

                    embed.description += f"Players: {len(node.players)}\n\n"

                return embed

            async def get_view():

                view = discord.ui.View(timeout=600)

                previous_button = discord.ui.Button(
                    label="หน้าก่อนหน้า",
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.PREVIOUS,
                    disabled=current_page_index == 0,
                )

                next_button = discord.ui.Button(
                    label="หน้าถัดไป",
                    style=discord.ButtonStyle.primary,
                    emoji=self.bot.emoji.NEXT,
                    disabled=current_page_index == len(nodes_list) - 1,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(next_button)

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่สามารถใช้ปุ่มนี้ได้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=5,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่สามารถใช้ปุ่มนี้ได้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=5,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                    )

            embed = await get_embed()

            view = await get_view()

            message = await ctx.send(embed=embed, view=view)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
            )

    @root.command(
        name="noprefixadd",
        aliases=["npadd", "npa", "SkylineBOT"],
        help="Add a user to no-prefix list (เพิ่มผู้ใช้ในรายการ no prefix)",
        description="Add a user to no-prefix list (เพิ่มผู้ใช้ในรายการ no prefix)",
        hidden=True,
    )
    @checks.is_owner()
    async def noprefixadd(
        self, ctx: commands.Context, user: discord.User, days: int = 0
    ):

        try:

            if days < 1:

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | Minimum days must be 1.",
                        color=color.red,
                    )
                )

            if not str(user.id) not in self.bot.cache.users:

                try:

                    await storage.users.insert(
                        user_id=user.id,
                    )

                except Exception:
                    pass

            if self.bot.cache.users.get(str(user.id), {}).get(
                "no_prefix_subscription", False
            ):

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | {user.display_name} is already has no prefix subscription.",
                        color=color.red,
                    )
                )

            await change_user_subscription(
                bot=self.bot,
                user_id=user.id,
                subscription="user_no_prefix",
                valid_for_days=days,
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.SUCCESS} | {user.display_name}'s received no prefix subscription for {days} days."
                )
            )

        except Exception as e:

            await ctx.send(
                embed=discord.Embed(description=f"ข้อผิดพลาด: {e}", color=color.red)
            )

    @root.command(
        name="noprefixremove",
        aliases=["npremove", "nprem", "nprm"],
        help="Remove a user from no-prefix list (ลบผู้ใช้ออกจากรายการ no prefix)",
        description="Remove a user from no-prefix list (ลบผู้ใช้ออกจากรายการ no prefix)",
        hidden=True,
    )
    @checks.is_owner()
    async def noprefixremove(self, ctx: commands.Context, user: discord.User):

        try:

            if not str(user.id) not in self.bot.cache.users:

                try:

                    await storage.users.insert(
                        user_id=user.id,
                    )

                except Exception:
                    pass

            if not self.bot.cache.users.get(str(user.id), {}).get(
                "no_prefix_subscription", False
            ):

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | {user.display_name} does not have no prefix subscription.",
                        color=color.red,
                    )
                )

            await change_user_subscription(
                bot=self.bot, user_id=user.id, subscription=None
            )

            await ctx.send(
                embed=discord.Embed(
                    description=f"{self.bot.emoji.SUCCESS} | {user.display_name}'s subscription has been changed to free."
                )
            )

        except Exception as e:

            await ctx.send(
                embed=discord.Embed(description=f"ข้อผิดพลาด: {e}", color=color.red)
            )

    @root.command(
        name="guildpremiumadd",
        aliases=["gpa", "gpadd"],
        help="Grant premium to a guild (เพิ่มพรีเมียมให้กิลด์)",
        description="เพิ่มพรีเมียมให้กิลด์",
        hidden=True,
    )
    @checks.is_owner()
    async def guildpremiumadd(
        self, ctx: commands.Context, guild_id: int, plan: str, days: int = 30
    ):
        try:
            if days < 0:
                return await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | Days must be 0 or greater.",
                        color=color.red,
                    )
                )

            normalized_plan = plan.strip().lower()
            plan_map = {
                "silver": "silver_guild_preminum",
                "silver_guild_preminum": "silver_guild_preminum",
                "gold": "golden_guild_premium",
                "gole": "golden_guild_premium",
                "golden": "golden_guild_premium",
                "golden_guild_premium": "golden_guild_premium",
                "gole_guild_premium": "golden_guild_premium",
                "diamond": "diamond_guild_premium",
                "diamond_guild_premium": "diamond_guild_premium",
                "permanent": "permanent_guild_premium",
                "lifetime": "permanent_guild_premium",
                "permanent_guild_premium": "permanent_guild_premium",
                "free": "free",
            }
            target_plan = plan_map.get(normalized_plan)
            if not target_plan:
                return await ctx.send(
                    embed=discord.Embed(
                        description=(
                            f"{self.bot.emoji.ERROR} | Invalid plan `{plan}`.\n"
                            "Use: `silver`, `gole`, `diamond`, `permanent`, or `free`."
                        ),
                        color=color.red,
                    )
                )

            await change_guild_subscription(
                bot=self.bot,
                guild_id=guild_id,
                subscription=target_plan,
                valid_for_days=(None if days == 0 else days),
            )

            await ctx.send(
                embed=discord.Embed(
                    description=(
                        f"{self.bot.emoji.SUCCESS} | Guild `{guild_id}` subscription updated to "
                        f"`{target_plan}` for `{days}` day(s)."
                    ),
                    color=color.green,
                )
            )
        except Exception as e:
            await ctx.send(
                embed=discord.Embed(description=f"ข้อผิดพลาด: {e}", color=color.red)
            )

    @root.command(
        name="guildpremiumremove",
        aliases=["gprm", "gpremove"],
        help="Remove premium from a guild (ลบพรีเมียมออกจากกิลด์)",
        description="ลบพรีเมียมออกจากกิลด์",
        hidden=True,
    )
    @checks.is_owner()
    async def guildpremiumremove(self, ctx: commands.Context, guild_id: int):
        try:
            await change_guild_subscription(
                bot=self.bot,
                guild_id=guild_id,
                subscription="free",
                valid_for_days=None,
            )
            await ctx.send(
                embed=discord.Embed(
                    description=(
                        f"{self.bot.emoji.SUCCESS} | Guild `{guild_id}` subscription changed to `free`."
                    ),
                    color=color.green,
                )
            )
        except Exception as e:
            await ctx.send(
                embed=discord.Embed(description=f"ข้อผิดพลาด: {e}", color=color.red)
            )








