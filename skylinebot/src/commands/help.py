# help.py

import discord
from discord.ext import commands
from discord import ui
from typing import Any
import inspect

from skylinebot.src.checks import checks

from skylinebot.style import color
import traceback, sys

from skylinebot.console.logging import logger

from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.utils import i18n


class CogInfo:
    def __init__(self, name, category, description, hidden, emoji):
        self.name = name
        self.category = category
        self.description = description
        self.hidden = hidden
        self.emoji = emoji


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot
        self.cog_info = CogInfo(
            name="Help",
            category="Extra",
            description="คำสั่งช่วยเหลือ",
            hidden=False,
            emoji=self.bot.emoji.HELP,
        )
        self.all_app_commands = None

    @commands.hybrid_command(
        name="help",
        with_app_command=True,
        help="แสดงคำสั่งทั้งหมดของบอท",
        aliases=["h"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=10, per=60, type=commands.BucketType.user)
    async def help(self, ctx: commands.Context):
        try:
            # Instantly acknowledge slash commands to prevent Discord 3s timeout
            if ctx.interaction and not ctx.interaction.response.is_done():
                try:
                    await ctx.interaction.response.defer()
                except Exception:
                    pass

            if self.all_app_commands is None:
                self.all_app_commands = list(self.bot.tree.get_commands())
            
            try:
                view = HomeView(self.bot, ctx, self.all_app_commands)
                view.message = await ctx.send(view=view)
            except Exception as layout_err:
                logger.warning(f"LayoutView fallback activated in help command: {layout_err}")
                # Fallback to standard Embed & View to guarantee successful response
                embed = discord.Embed(
                    title=f"⚡ {self.bot.user.display_name} Help Menu",
                    description=(
                        f"คำนำหน้าเซิร์ฟเวอร์: `{self.bot.config.PREFIX if hasattr(self.bot, 'config') else '::'}`\n"
                        f"จำนวนคำสั่งทั้งหมด: `{len(self.all_app_commands)}` คำสั่ง\n\n"
                        f"🌐 ดูคำสั่งทั้งหมดบนเว็บ: [skylinebot.xyz/commands](https://skylinebot.xyz/commands)\n"
                        f"💎 ดูแพ็กเกจพรีเมียม: [skylinebot.xyz/premium](https://skylinebot.xyz/premium)"
                    ),
                    color=0x8b5cf6
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user.display_avatar else None)
                embed.set_footer(text=f"© {discord.utils.utcnow().year} SkylineBOT — V. 2.5.0")
                await ctx.send(embed=embed)
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )
            try:
                await ctx.send("❌ ไม่สามารถเปิดเมนูช่วยเหลือได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง")
            except Exception:
                pass


class BaseHelpView(ui.LayoutView):
    ENGLISH_ONLY_COMMANDS = {"automod", "antilink", "antibadwords", "antispam", "nsfw", "poll", "guildstyle"}
    COG_NAME_TH = {
        "security": "ความปลอดภัย",
        "nsfw": "คอนเทนต์ NSFW/Soft",
        "automod": "ออโต้มอด",
        "moderation": "การดูแลกิลด์",
        "ticket": "ทิกเก็ต",
        "welcomer": "ต้อนรับ",
        "music": "เพลง",
        "utils": "ยูทิลิตี้",
        "giveaway": "กิจกรรม",
        "help": "ช่วยเหลือ",
        "fun": "บันเทิงและเกม",
        "voice": "เสียง",
        "more": "ระบบเสริม",
        "backup": "สำรองข้อมูล",
        "birthday": "วันเกิด",
        "economy": "เศรษฐกิจ",
        "levels": "เลเวล",
        "personalnotes": "บันทึกส่วนตัว",
        "personalreminders": "เตือนความจำ",
        "shop": "ร้านค้ากิลด์",
        "poll": "โพลสำรวจ",
        "guildstyler": "จัดทรงกิลด์อัตโนมัติ",
        "enterpriseops": "ระบบองค์กรขั้นสูง",
        "root": "Root",
    }
    COG_EMOJI_FALLBACK = {
        "security": "🛡️",
        "nsfw": "🔞",
        "automod": "🤖",
        "moderation": "🧹",
        "ticket": "🎫",
        "welcomer": "👋",
        "music": "🎵",
        "utils": "⚙️",
        "giveaway": "🎉",
        "help": "❓",
        "fun": "🎮",
        "voice": "🎙️",
        "more": "📦",
        "backup": "💾",
        "birthday": "🎂",
        "economy": "💰",
        "levels": "📈",
        "personalnotes": "📝",
        "personalreminders": "⏰",
        "shop": "🛒",
        "poll": "📊",
        "guildstyler": "🧩",
        "enterpriseops": "🧭",
        "root": "🛠️",
    }
    EXCLUDED_HELP_COG_KEYS = {"root"}
    GUILD_ADMIN_PERMISSIONS = {
        "administrator",
        "manage_guild",
        "manage_channels",
        "manage_messages",
        "manage_roles",
        "manage_nicknames",
        "manage_emojis",
        "manage_webhooks",
        "ban_members",
        "kick_members",
        "move_members",
        "mute_members",
        "deafen_members",
        "moderate_members",
    }

    TH_TEXT = {
        "You are not allowed to use this interaction": "คุณไม่ได้รับอนุญาตให้ใช้การโต้ตอบนี้",
        "You are not Owner BOT": "คุณไม่ใช่ Owner BOT",
        "Help menu": "เมนูช่วยเหลือ",
        "Main": "หลัก",
        "Extra": "เสริม",
        "Owner": "เจ้าของบอท",
        "Select a category to view": "เลือกหมวดหมู่เพื่อดู",
        "Invite": "เชิญบอท",
        "ช่วยเหลือ": "ซัพพอร์ต",
        "All Commands": "คำสั่งทั้งหมด",
        "Category not found": "ไม่พบหมวด",
        "Commands": "คำสั่ง",
        "Select a command to view": "เลือกคำสั่งเพื่อดูรายละเอียด",
        "Command not found": "ไม่พบคำสั่ง",
        "Command": "คำสั่ง",
        "Primary Command": "คำสั่งหลัก",
        "Options": "ตัวเลือก",
        "Subcommands": "คำสั่งย่อย",
        "Back": "ย้อนกลับ",
    }

    def __init__(self, bot, ctx, all_app_commands, reported=False, timeout=900):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.ctx = ctx
        self.all_app_commands = all_app_commands
        self.reported = reported
        self.message: discord.Message = None

    def get_language(self) -> str:
        if not getattr(self.ctx, "guild", None):
            return "en"
        return i18n.guild_lang(self.ctx.guild.id)

    def tr(self, english: str, hindi: str | None = None) -> str:
        if self.get_language() == "th":
            return self.TH_TEXT.get(english, english)
        return english

    def should_keep_command_english(self, command_name: str | None) -> bool:
        if not isinstance(command_name, str) or not command_name:
            return False
        return command_name.casefold() in self.ENGLISH_ONLY_COMMANDS

    def _cog_key(self, cog) -> str:
        return str(getattr(getattr(cog, "cog_info", None), "name", "") or "").strip().lower()

    def _is_help_excluded_cog(self, cog) -> bool:
        return self._cog_key(cog) in self.EXCLUDED_HELP_COG_KEYS

    def cog_display_name(self, cog) -> str:
        name = str(getattr(getattr(cog, "cog_info", None), "name", "") or "Unknown")
        if self.get_language() == "th":
            return self.COG_NAME_TH.get(self._cog_key(cog), name)
        return name

    def cog_display_emoji(self, cog, prefer_unicode: bool = False) -> str:
        key = self._cog_key(cog)
        fallback = self.COG_EMOJI_FALLBACK.get(key, "📁")
        if prefer_unicode:
            return fallback or "📁"
        raw_emoji = str(getattr(getattr(cog, "cog_info", None), "emoji", "") or "").strip()
        if raw_emoji.startswith("<") and raw_emoji.endswith(">") and ":" in raw_emoji:
            return raw_emoji
        if raw_emoji and not raw_emoji.startswith(":"):
            return raw_emoji
        return fallback

    def cog_select_emoji(self, cog) -> str:
        emoji = self.cog_display_emoji(cog, prefer_unicode=True)
        emoji = str(emoji or "").strip()
        return emoji or "📁"

    def localize_text(self, text: str | None, force_english: bool = False) -> str:
        if not isinstance(text, str) or not text:
            return ""
        if force_english:
            return i18n.localize_command_text(text, None)
        guild_id = getattr(getattr(self.ctx, "guild", None), "id", None)
        return i18n.localize_command_text(text, guild_id)

    @staticmethod
    def _normalize_option_text(text: str | None) -> str:
        raw = str(text or "").strip()
        if not raw:
            return "-"
        return " ".join(raw.split())

    @classmethod
    def _clip_option_text(cls, text: str | None, max_len: int) -> str:
        normalized = cls._normalize_option_text(text)
        if len(normalized) <= max_len:
            return normalized
        if max_len <= 3:
            return normalized[:max_len]
        return normalized[: max_len - 3] + "..."

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=self.tr(
                        "You are not allowed to use this interaction",
                        "Aap is interaction ko use nahi kar sakte",
                    ),
                    color=color.red,
                ),
                ephemeral=True,
                delete_after=10,
            )
            return False
        return True

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: ui.Item[Any]
    ) -> None:
        logger.error(
            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {error}"
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "เกิดข้อผิดพลาดระหว่างเปิดเมนูคำสั่ง ลองอีกครั้ง",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "เกิดข้อผิดพลาดระหว่างเปิดเมนูคำสั่ง ลองอีกครั้ง",
                    ephemeral=True,
                )
        except Exception:
            pass

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

    def get_cogs(self):
        extra_cogs = []
        main_cogs = []
        hidden_cogs = []
        for cog_name in self.bot.cogs:
            cog = self.bot.get_cog(cog_name)
            if hasattr(cog, "cog_info") and cog.cog_info:
                if self._is_help_excluded_cog(cog):
                    continue
                if cog.cog_info.hidden:
                    hidden_cogs.append(cog)
                elif str(getattr(cog.cog_info, "category", "") or "").strip().lower() == "main":
                    main_cogs.append(cog)
                else:
                    # Keep help comprehensive: include non-main categories (extra/fun/economy/safety/other)
                    # in the visible list instead of dropping them.
                    extra_cogs.append(cog)
        return main_cogs, extra_cogs, hidden_cogs

    def _iter_visible_cog_commands(self, cog):
        for command in list(getattr(cog, "get_commands", lambda: [])() or []):
            if getattr(command, "hidden", False):
                continue
            yield command

    def _is_command_owner_only(self, command) -> bool:
        if self._cog_key(getattr(command, "cog", None)) == "root":
            return True
        for check_fn in list(getattr(command, "checks", []) or []):
            check_name = str(getattr(check_fn, "__name__", "") or "").strip().lower()
            check_qualname = str(getattr(check_fn, "__qualname__", "") or "").strip().lower()
            if "owner" in check_name or "owner" in check_qualname:
                return True
        try:
            source = inspect.getsource(getattr(command, "callback", None))
        except Exception:
            source = ""
        source_text = str(source or "").lower()
        return "checks.is_owner(" in source_text or "check_is_owner(" in source_text

    def _is_command_guild_admin_only(self, command) -> bool:
        if self._is_command_owner_only(command):
            return True

        for check_fn in list(getattr(command, "checks", []) or []):
            check_name = str(getattr(check_fn, "__name__", "") or "").strip().lower()
            check_qualname = str(getattr(check_fn, "__qualname__", "") or "").strip().lower()
            check_module = str(getattr(check_fn, "__module__", "") or "").strip().lower()

            if "has_permissions" in check_qualname:
                for closure_item in list(getattr(check_fn, "__closure__", None) or []):
                    cell_value = getattr(closure_item, "cell_contents", None)
                    if not isinstance(cell_value, dict):
                        continue
                    if any(str(name or "").strip().lower() in self.GUILD_ADMIN_PERMISSIONS for name in cell_value.keys()):
                        return True

            if "moderator" in check_name or "moderator" in check_qualname:
                return True
            if "administrator" in check_name or "administrator" in check_qualname:
                return True
            if check_module.endswith("checks.checks") and (
                "giveaway_permissions" in check_name
                or "is_admin" in check_name
            ):
                return True

        try:
            source = inspect.getsource(getattr(command, "callback", None))
        except Exception:
            source = ""
        source_text = str(source or "").lower()
        admin_tokens = (
            "check_is_moderator_permissions",
            "_require_manage_guild(",
            "check_for_giveaway_permissions(",
            "guild_permissions.administrator",
            "guild_permissions.manage_guild",
            "@commands.has_permissions",
        )
        return any(token in source_text for token in admin_tokens)

    def _command_access_level(self, command) -> str:
        if self._is_command_owner_only(command):
            return "owner"
        if self._is_command_guild_admin_only(command):
            return "admin"
        return "general"

    def _split_cog_commands_by_access(self, cog) -> tuple[list[Any], list[Any]]:
        general_commands: list[Any] = []
        admin_commands: list[Any] = []
        for command in self._iter_visible_cog_commands(cog):
            if self._command_access_level(command) == "general":
                general_commands.append(command)
            else:
                admin_commands.append(command)
        return general_commands, admin_commands

    def is_bot_owner(self) -> bool:
        return checks.check_is_owner_predicate(self.ctx)

    def get_all_commands_count(self):
        count = 0
        main_cogs, extra_cogs, owner_cogs = self.get_cogs()
        for cog in (main_cogs + extra_cogs + owner_cogs):
            count += sum(1 for _ in self._iter_visible_cog_commands(cog))
        return count


class HomeView(BaseHelpView):
    def __init__(self, bot, ctx, all_app_commands, reported=False):
        super().__init__(bot, ctx, all_app_commands, reported)
        container = ui.Container()
        container.add_item(
            ui.TextDisplay(
                f"# {self.bot.user.display_name}\n-# {self.tr('Help menu', 'Help menu')}"
            )
        )
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        prefix = self.bot.cache.guilds.get(str(self.ctx.guild.id), {}).get(
            "prefix", self.bot.BotConfig.PREFIX
        )
        if self.get_language() == "th":
            desc = (
                f"- คำนำหน้าของเซิร์ฟเวอร์คือ `{prefix}`\n"
                f"- จำนวนคำสั่งทั้งหมด: `{self.get_all_commands_count()}`\n"
                f"- [เชิญ SkylineBOT]({self.bot.urls.INVITE}) | "
                f"[เซิร์ฟเวอร์ซัพพอร์ต]({self.bot.urls.SUPPORT_SERVER}) | "
                f"[โหวตบอท]({self.bot.urls.VOTE})"
            )
        else:
            desc = (
                f"- Prefix for this server is `{prefix}`\n"
                f"- Total commands: `{self.get_all_commands_count()}`\n"
                f"- [Invite SkylineBOT]({self.bot.urls.INVITE}) | "
                f"[ช่วยเหลือ server]({self.bot.urls.SUPPORT_SERVER}) | "
                f"[โหวต me]({self.bot.urls.VOTE})"
            )
        container.add_item(ui.TextDisplay(desc))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        main_cogs, extra_cogs, owner_cogs = self.get_cogs()
        visible_cogs = main_cogs + extra_cogs
        if self.is_bot_owner():
            visible_cogs += owner_cogs

        general_cog_lines: list[str] = []
        admin_cog_lines: list[str] = []
        for cog in visible_cogs:
            general_commands, admin_commands = self._split_cog_commands_by_access(cog)
            if not general_commands and not admin_commands:
                continue
            if general_commands:
                general_cog_lines.append(
                    f"> **{self.cog_display_emoji(cog, prefer_unicode=True)} : {self.cog_display_name(cog)}** (`{len(general_commands)}`)"
                )
            if admin_commands:
                admin_cog_lines.append(
                    f"> **{self.cog_display_emoji(cog, prefer_unicode=True)} : {self.cog_display_name(cog)}** (`{len(admin_commands)}`)"
                )

        if general_cog_lines:
            container.add_item(
                ui.TextDisplay(
                    "### **__ทั่วไป (ทุกคนใช้ได้)__**\n" + "\n".join(general_cog_lines)
                )
            )
        if admin_cog_lines:
            container.add_item(
                ui.TextDisplay(
                    "### **__Admin กิลด์__**\n"
                    "-# ต้องมีสิทธิ์ดูแลเซิร์ฟเวอร์หรือสิทธิ์ตามที่คำสั่งกำหนด\n"
                    + "\n".join(admin_cog_lines)
                )
            )

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(
            ui.TextDisplay(
                f"## {self.tr('Select a category to view', 'Category select karein')}"
            )
        )
        category_cogs = visible_cogs
        cog_access_map: dict[Any, tuple[list[Any], list[Any]]] = {
            cog: self._split_cog_commands_by_access(cog) for cog in category_cogs
        }
        category_options = [
            discord.SelectOption(
                label=self._clip_option_text(self.cog_display_name(cog), 100),
                value=str(cog.cog_info.name or "").lower(),
                description=self._clip_option_text(
                    (
                        (
                            "Admin + General commands"
                            if cog_access_map.get(cog, ([], []))[0] and cog_access_map.get(cog, ([], []))[1]
                            else ("General commands" if cog_access_map.get(cog, ([], []))[0] else "Guild admin commands")
                        )
                        if self.get_language() != "th"
                        else (
                            "มีทั้งคำสั่งทั่วไปและคำสั่งแอดมิน"
                            if cog_access_map.get(cog, ([], []))[0] and cog_access_map.get(cog, ([], []))[1]
                            else ("คำสั่งทั่วไป" if cog_access_map.get(cog, ([], []))[0] else "คำสั่งแอดมินกิลด์")
                        )
                    ),
                    100,
                ),
                emoji=self.cog_select_emoji(cog),
            )
            for cog in category_cogs
            if getattr(cog, "cog_info", None) and getattr(cog.cog_info, "name", None)
        ]
        category_chunks = [
            category_options[i : i + 25] for i in range(0, len(category_options), 25)
        ] or [[]]
        for idx, chunk in enumerate(category_chunks, start=1):
            if not chunk:
                continue
            container.add_item(
                CategorySelectRow(
                    self,
                    options=chunk,
                    page_index=idx,
                    page_total=len(category_chunks),
                )
            )
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        button_row = ui.ActionRow()
        _guild_id = getattr(getattr(self.ctx, "guild", None), "id", None)
        button_row.add_item(AllCommandsButton("📚", guild_id=_guild_id))
        report_button = ReportButton("⚠️", self.bot, guild_id=_guild_id)
        if self.reported:
            report_button.disabled = True
        button_row.add_item(report_button)
        button_row.add_item(
            ui.Button(
                label=self.tr("Invite", "Invite"),
                style=discord.ButtonStyle.link,
                url=self.bot.urls.INVITE,
                emoji="➕",
            )
        )
        button_row.add_item(
            ui.Button(
                label=self.tr("ช่วยเหลือ", "ช่วยเหลือ"),
                style=discord.ButtonStyle.link,
                url=self.bot.urls.SUPPORT_SERVER,
                emoji="🛟",
            )
        )
        container.add_item(button_row)
        self.add_item(container)


class AllCommandsButton(ui.Button["BaseHelpView"]):
    def __init__(self, emoji, guild_id=None):
        super().__init__(
            label=i18n.tr("help_all_commands", guild_id), style=discord.ButtonStyle.green, emoji=emoji
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.interaction_check(interaction):
            return
        all_view = AllCommandsView(
            self.view.bot, self.view.ctx, self.view.all_app_commands, self.view.reported
        )
        all_view.message = interaction.message
        await interaction.response.edit_message(view=all_view)


class ReportButton(ui.Button["BaseHelpView"]):
    def __init__(self, emoji, bot, guild_id=None):
        super().__init__(label=i18n.tr("help_report", guild_id), style=discord.ButtonStyle.red, emoji=emoji)
        self.bot = bot
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.interaction_check(interaction):
            return
        modal = ReportModal(self.bot, self.guild_id)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.submitted:
            self.view.reported = True
            self.disabled = True
            await interaction.message.edit(view=self.view)


class ReportModal(ui.Modal):
    report_title_field = ui.Label(
        text="Report Title",
        component=ui.TextInput(
            placeholder="Report Title",
            required=True,
            style=discord.TextStyle.short,
        ),
    )
    report_description_field = ui.Label(
        text="Report Description",
        component=ui.TextInput(
            placeholder="Report Description",
            required=True,
            style=discord.TextStyle.long,
        ),
    )
    report_attachment_field = ui.Label(
        text="Report Attachment links",
        component=ui.TextInput(
            placeholder="Separate the links with comma",
            required=False,
            style=discord.TextStyle.long,
        ),
    )

    def __init__(self, bot, guild_id=None):
        super().__init__(title=i18n.tr("help_report_modal_title", guild_id))
        self.bot = bot
        self.guild_id = guild_id
        self.submitted = False
        self.report_title_field.text = i18n.tr("help_report_title_label", guild_id)
        self.report_title_field.component.placeholder = i18n.tr("help_report_title_label", guild_id)
        self.report_description_field.text = i18n.tr("help_report_desc_label", guild_id)
        self.report_description_field.component.placeholder = i18n.tr("help_report_desc_label", guild_id)
        self.report_attachment_field.text = i18n.tr("help_report_attach_label", guild_id)
        self.report_attachment_field.component.placeholder = i18n.tr("help_report_attach_placeholder", guild_id)

    async def on_submit(self, interaction: discord.Interaction):
        title = self.report_title_field.component.value
        description = self.report_description_field.component.value
        attachments = (
            self.report_attachment_field.component.value.split(",")
            if self.report_attachment_field.component.value
            else []
        )
        if not title or not description:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=i18n.tr("help_report_required", self.guild_id), color=color.red
                ),
                ephemeral=True,
                delete_after=10,
            )
        embed = discord.Embed(title=title, description=description, color=color.black)
        if attachments:
            embed.add_field(
                name=i18n.tr("help_report_attachments", self.guild_id), value="\n".join(attachments), inline=False
            )
        embed.set_footer(
            text=i18n.tr("help_reported_by", self.guild_id, user=interaction.user.display_name, id=interaction.user.id),
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_author(
            name=f"{interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        report_channel_id = int(
            getattr(
                self.bot.channels,
                "support_report_channel",
                self.bot.channels.report_channel,
            )
            or 0
        )
        channel = self.bot.get_channel(report_channel_id)
        if channel:
            await channel.send(embed=embed)
        else:
            logger.error(
                f"User report channel not found. Channel ID: {report_channel_id}"
            )
        await interaction.response.send_message(
            embed=discord.Embed(
                description=i18n.tr("help_report_success", self.guild_id), color=color.green
            ),
            ephemeral=True,
        )
        self.submitted = True
        self.stop()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        logger.error(
            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {error}"
        )


class CategorySelectRow(ui.ActionRow["HomeView"]):
    def __init__(
        self,
        view: HomeView,
        *,
        options: list[discord.SelectOption],
        page_index: int = 1,
        page_total: int = 1,
    ):
        super().__init__()
        placeholder = view.tr("Select a category to view", "Category select karein")
        if page_total > 1:
            placeholder = f"{placeholder} ({page_index}/{page_total})"
        select = ui.Select(
            placeholder=view._clip_option_text(placeholder, 150),
            options=options,
        )
        select.callback = self.select_category
        self.add_item(select)

    async def select_category(self, interaction: discord.Interaction):
        if not await self.view.interaction_check(interaction):
            return
        cog_name = interaction.data["values"][0]
        cog = None
        for name in self.view.bot.cogs:
            if name.lower() == cog_name:
                cog = self.view.bot.get_cog(name)
                break
        if not cog:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=self.view.tr("Category not found", "Category nahi mili"),
                    color=color.red,
                ),
                ephemeral=True,
                delete_after=10,
            )
        if getattr(cog, "cog_info", None) and cog.cog_info.hidden and not self.view.is_bot_owner():
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=self.view.tr("You are not Owner BOT", "You are not Owner BOT"),
                    color=color.red,
                ),
                ephemeral=True,
                delete_after=10,
            )
        category_view = CategoryView(
            self.view.bot,
            self.view.ctx,
            self.view.all_app_commands,
            cog,
            self.view.reported,
        )
        category_view.message = interaction.message
        await interaction.response.edit_message(view=category_view)


class AllCommandsView(BaseHelpView):
    def __init__(self, bot, ctx, all_app_commands, reported=False):
        super().__init__(bot, ctx, all_app_commands, reported)
        container = ui.Container()
        container.add_item(ui.TextDisplay(f"# {self.tr('All Commands', 'Sabhi Commands')}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        main_cogs, extra_cogs, owner_cogs = self.get_cogs()
        visible_cogs = main_cogs + extra_cogs
        if self.is_bot_owner():
            visible_cogs += owner_cogs

        general_blocks: list[str] = []
        admin_blocks: list[str] = []
        for cog in visible_cogs:
            general_commands, admin_commands = self._split_cog_commands_by_access(cog)
            if general_commands:
                general_blocks.append(
                    f"**{self.cog_display_emoji(cog, prefer_unicode=True)} {self.cog_display_name(cog)} [{len(general_commands)}]**\n"
                    + " | ".join([f"**`{command.name}`**" for command in general_commands])
                )
            if admin_commands:
                admin_blocks.append(
                    f"**{self.cog_display_emoji(cog, prefer_unicode=True)} {self.cog_display_name(cog)} [{len(admin_commands)}]**\n"
                    + " | ".join([f"**`{command.name}`**" for command in admin_commands])
                )

        if general_blocks:
            container.add_item(ui.TextDisplay("## ทั่วไป (ทุกคนใช้ได้)"))
            container.add_item(ui.TextDisplay("\n\n".join(general_blocks)))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        if admin_blocks:
            container.add_item(ui.TextDisplay("## Admin กิลด์"))
            container.add_item(
                ui.TextDisplay(
                    "-# ต้องมีสิทธิ์ตามคำสั่ง เช่น Manage Guild / Administrator\n\n"
                    + "\n\n".join(admin_blocks)
                )
            )
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        button_row = ui.ActionRow()
        button_row.add_item(BackButton())
        container.add_item(button_row)
        self.add_item(container)


class CategoryView(BaseHelpView):
    def __init__(self, bot, ctx, all_app_commands, cog, reported=False):
        super().__init__(bot, ctx, all_app_commands, reported)
        self.cog = cog
        container = ui.Container()
        desc = f"# {self.cog.cog_info.name} {self.tr('Commands', 'Commands')}\n"
        all_commands = list(self._iter_visible_cog_commands(self.cog))
        general_commands, admin_commands = self._split_cog_commands_by_access(self.cog)

        if general_commands:
            desc += "\n### ทั่วไป (ทุกคนใช้ได้)\n"
            chunks = [general_commands[i : i + 5] for i in range(0, len(general_commands), 5)]
            for chunk in chunks:
                desc += f"\n>  - {' | '.join([f'**`{command.name}`**' for command in chunk])}"

        if admin_commands:
            desc += "\n\n### Admin กิลด์\n"
            admin_chunks = [admin_commands[i : i + 5] for i in range(0, len(admin_commands), 5)]
            for chunk in admin_chunks:
                desc += f"\n>  - {' | '.join([f'**`{command.name}`**' for command in chunk])}"

        if not general_commands and not admin_commands:
            desc += "\n> - No commands available"
        container.add_item(ui.TextDisplay(desc))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
        container.add_item(
            ui.TextDisplay(
                self.tr("## Select a command to view", "## Command select karein")
            )
        )
        command_access_map = {command.name: self._command_access_level(command) for command in all_commands}
        command_options = [
            discord.SelectOption(
                label=self._clip_option_text(
                    f"{'🔒' if command_access_map.get(command.name) != 'general' else '🌐'} {command.name}",
                    100,
                ),
                value=command.name,
                description=self._clip_option_text(
                    (
                        f"{'Admin กิลด์ • ' if command_access_map.get(command.name) != 'general' else 'ทั่วไป • '}"
                        + self.localize_text(
                            command.help,
                            force_english=self.should_keep_command_english(command.name),
                        )
                    ),
                    100,
                ),
            )
            for command in all_commands
        ]
        option_chunks = [
            command_options[i : i + 25] for i in range(0, len(command_options), 25)
        ] or [[]]
        for idx, chunk in enumerate(option_chunks, start=1):
            if not chunk:
                continue
            container.add_item(
                CommandSelectRow(
                    self,
                    options=chunk,
                    page_index=idx,
                    page_total=len(option_chunks),
                )
            )
        button_row = ui.ActionRow()
        button_row.add_item(BackButton())
        container.add_item(button_row)
        self.add_item(container)


class CommandSelectRow(ui.ActionRow["CategoryView"]):
    def __init__(
        self,
        view: CategoryView,
        *,
        options: list[discord.SelectOption],
        page_index: int = 1,
        page_total: int = 1,
    ):
        super().__init__()
        placeholder = view.tr("Select a command to view", "Command select karein")
        if page_total > 1:
            placeholder = f"{placeholder} ({page_index}/{page_total})"
        select = ui.Select(
            placeholder=view._clip_option_text(placeholder, 150),
            options=options,
        )
        select.callback = self.select_command
        self.add_item(select)

    async def select_command(self, interaction: discord.Interaction):
        if not await self.view.interaction_check(interaction):
            return
        command_name = interaction.data["values"][0]
        command = None
        for cmd in self.view.cog.get_commands():
            if cmd.name == command_name:
                command = cmd
                break
        if not command:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=self.view.tr("Command not found", "Command nahi mili"),
                    color=color.red,
                ),
                ephemeral=True,
                delete_after=10,
            )
        command_view = CommandView(
            self.view.bot,
            self.view.ctx,
            self.view.all_app_commands,
            command,
            self.view.cog,
            self.view.reported,
        )
        command_view.message = interaction.message
        await interaction.response.edit_message(view=command_view)


class CommandView(BaseHelpView):
    def __init__(self, bot, ctx, all_app_commands, command, cog, reported=False):
        super().__init__(bot, ctx, all_app_commands, reported)
        self.command = command
        self.cog = cog
        container = ui.Container()
        force_english = self.should_keep_command_english(self.command.name)
        command_help = self.localize_text(self.command.help, force_english=force_english)
        desc = f"# {self.command.name.capitalize()} {self.tr('Command', 'Command')}\n{command_help}"
        app_command = next(
            (cmd for cmd in self.all_app_commands if cmd.name == self.command.name),
            None,
        )
        prefix = self.bot.BotConfig.PREFIX
        params = " ".join([f"<{arg}>" for arg in self.command.clean_params])
        if app_command:
            app_options = getattr(app_command, "options", None)
            if app_options is None:
                # Local app_commands.Command objects expose ``parameters`` while
                # commands returned by Discord's API expose ``options``.
                app_options = getattr(app_command, "parameters", ())
            if app_options:
                desc += (
                    f"\n\n**{self.tr('Primary Command', 'Main Command')}:** `/{app_command.name} {params}`"
                )
                desc += f"\n> Prefix: `{prefix}{app_command.name} {params}`"
                desc += f"\n\n**{self.tr('Options', 'Options')}:**\n"
                for option in app_options:
                    if force_english:
                        mention = f"/{app_command.name} {option.name}"
                    else:
                        mention = (
                            option.mention
                            if hasattr(option, "mention")
                            else f"{prefix}{self.command.name} {option.name}"
                        )
                    desc += f"\n> {mention}\n> {self.localize_text(option.description, force_english=force_english)}\n"
            else:
                if force_english:
                    mention = f"/{app_command.name}"
                else:
                    mention = (
                        app_command.mention
                        if hasattr(app_command, "mention")
                        else f"{prefix}{self.command.name}"
                    )
                desc += f"\n\n**{self.tr('Primary Command', 'Main Command')}:** {mention}"
                desc += f"\n> Prefix: `{prefix}{self.command.name}`"
        else:
            desc += f"\n\n**{self.tr('Primary Command', 'Main Command')}:** `{prefix}{self.command.name} {params}`"
            if isinstance(self.command, commands.Group):
                desc += f"\n\n**{self.tr('Subcommands', 'Subcommands')}:**\n"
                for subcommand in self.command.commands:
                    sub_params = " ".join(
                        [f"<{arg}>" for arg in subcommand.clean_params]
                    )
                    sub_force_english = force_english or self.should_keep_command_english(
                        subcommand.name
                    )
                    desc += f"\n> **`{prefix}{self.command.name} {subcommand.name} {sub_params}`** \n> {self.localize_text(subcommand.help, force_english=sub_force_english)}\n"
        container.add_item(ui.TextDisplay(desc))
        button_row = ui.ActionRow()
        button_row.add_item(BackButton())
        container.add_item(button_row)
        self.add_item(container)


class BackButton(ui.Button["BaseHelpView"]):
    def __init__(self):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
        )

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.interaction_check(interaction):
            return
        if isinstance(self.view, AllCommandsView) or isinstance(
            self.view, CategoryView
        ):
            home_view = HomeView(
                self.view.bot,
                self.view.ctx,
                self.view.all_app_commands,
                self.view.reported,
            )
            home_view.message = interaction.message
            await interaction.response.edit_message(view=home_view)
        elif isinstance(self.view, CommandView):
            category_view = CategoryView(
                self.view.bot,
                self.view.ctx,
                self.view.all_app_commands,
                self.view.cog,
                self.view.reported,
            )
            category_view.message = interaction.message
            await interaction.response.edit_message(view=category_view)


async def setup(bot: AutoShardedBot):
    await bot.add_cog(Help(bot))



