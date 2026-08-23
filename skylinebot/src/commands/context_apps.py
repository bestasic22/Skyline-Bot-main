import datetime

import discord
from discord import app_commands
from discord.ext import commands

import storage.economy_wallets as economy_wallets_db
import storage.levels_users as levels_users_db
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color


def _fmt_ts(dt_obj) -> str:
    if not dt_obj:
        return "-"
    try:
        return f"<t:{int(dt_obj.timestamp())}:F> (<t:{int(dt_obj.timestamp())}:R>)"
    except Exception:
        return "-"


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


class UserQuickActionsView(discord.ui.View):
    def __init__(
        self,
        *,
        cog: "ContextApps",
        actor_user_id: int,
        guild_id: int,
        target_user_id: int,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.actor_user_id = int(actor_user_id)
        self.guild_id = int(guild_id)
        self.target_user_id = int(target_user_id)

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_user_id:
            await self.cog._send_ephemeral(
                interaction,
                content="Only the command caller can use these buttons.",
            )
            return False
        if not interaction.guild or interaction.guild.id != self.guild_id:
            await self.cog._send_ephemeral(
                interaction,
                content="This action can only be used in the same server.",
            )
            return False
        return True

    async def _target_member(self, interaction: discord.Interaction) -> discord.Member | None:
        if not await self._guard(interaction):
            return None
        member = interaction.guild.get_member(self.target_user_id) if interaction.guild else None
        if member is None:
            await self.cog._send_ephemeral(interaction, content="Target user is no longer in this server.")
            return None
        return member

    @discord.ui.button(label="Rank", style=discord.ButtonStyle.secondary, emoji="🏅", row=0)
    async def rank_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_rank_menu(interaction, member)

    @discord.ui.button(label="Level", style=discord.ButtonStyle.secondary, emoji="📈", row=0)
    async def level_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_level_menu(interaction, member)

    @discord.ui.button(label="Balance", style=discord.ButtonStyle.secondary, emoji="💰", row=0)
    async def balance_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_balance_menu(interaction, member)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, emoji="🔨", row=1)
    async def ban_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_ban_menu(interaction, member)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, emoji="👢", row=1)
    async def kick_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_kick_menu(interaction, member)

    @discord.ui.button(label="Mute 10m", style=discord.ButtonStyle.primary, emoji="🔇", row=1)
    async def mute_10m_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_mute_10m_menu(interaction, member)

    @discord.ui.button(label="Mute 1h", style=discord.ButtonStyle.primary, emoji="🕐", row=2)
    async def mute_1h_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_mute_1h_menu(interaction, member)

    @discord.ui.button(label="Unmute", style=discord.ButtonStyle.success, emoji="🔊", row=2)
    async def unmute_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = await self._target_member(interaction)
        if member is None:
            return
        await self.cog.user_unmute_menu(interaction, member)


class ContextApps(commands.Cog):
    """User/Message context menu commands shown in right-click Apps menu."""

    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._registered: list[app_commands.ContextMenu] = []
        self._register_context_commands()

    def _register_context_commands(self) -> None:
        items = [
            app_commands.ContextMenu(name="User Info", callback=self.user_info_menu),
            app_commands.ContextMenu(name="User Avatar", callback=self.user_avatar_menu),
            app_commands.ContextMenu(name="User Rank", callback=self.user_rank_menu),
            app_commands.ContextMenu(name="User Level", callback=self.user_level_menu),
            app_commands.ContextMenu(name="User Actions", callback=self.user_actions_menu),
            app_commands.ContextMenu(name="Message Info", callback=self.message_info_menu),
            app_commands.ContextMenu(name="Quote Message", callback=self.quote_message_menu),
        ]
        for item in items:
            self.bot.tree.add_command(item, override=True)
            self._registered.append(item)

    async def _send_ephemeral(
        self,
        interaction: discord.Interaction,
        *,
        content: str | None = None,
        embed: discord.Embed | None = None,
        view: discord.ui.View | None = None,
    ) -> None:
        kwargs: dict[str, object] = {"ephemeral": True}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)

    async def _defer_ephemeral(self, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

    async def _resolve_target_member(
        self,
        interaction: discord.Interaction,
        user: discord.Member | discord.User,
    ) -> discord.Member | None:
        guild = interaction.guild
        if guild is None:
            await self._send_ephemeral(interaction, content="This command can only be used in a server.")
            return None
        if isinstance(user, discord.Member):
            return user
        member = guild.get_member(user.id)
        if member is None:
            await self._send_ephemeral(interaction, content="User is not in this server.")
            return None
        return member

    async def _actor_has_permission(self, interaction: discord.Interaction, permission_name: str) -> bool:
        guild = interaction.guild
        actor = interaction.user if isinstance(interaction.user, discord.Member) else None
        if guild is None or actor is None:
            await self._send_ephemeral(interaction, content="This command can only be used in a server.")
            return False
        if checks.check_is_admin_predicate(actor):
            return True
        if await checks.check_is_owner_raw(actor, guild):
            return True
        if actor.guild_permissions.administrator:
            return True
        if hasattr(actor.guild_permissions, permission_name):
            if getattr(actor.guild_permissions, permission_name):
                return True
        await self._send_ephemeral(interaction, content="You do not have enough permissions.")
        return False

    async def _ensure_bot_permission(self, interaction: discord.Interaction, permission_name: str) -> bool:
        guild = interaction.guild
        bot_member = guild.me if guild else None
        if guild is None or bot_member is None:
            await self._send_ephemeral(interaction, content="Bot state is not ready for this server yet.")
            return False
        if not hasattr(bot_member.guild_permissions, permission_name):
            return True
        if getattr(bot_member.guild_permissions, permission_name):
            return True
        await self._send_ephemeral(
            interaction,
            content=f"บอทไม่มีสิทธิ์ที่จำเป็น: `{permission_name}`",
        )
        return False

    async def _ensure_target_is_moderatable(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        *,
        action_label: str,
    ) -> bool:
        guild = interaction.guild
        actor = interaction.user if isinstance(interaction.user, discord.Member) else None
        bot_member = guild.me if guild else None

        if guild is None or actor is None or bot_member is None:
            await self._send_ephemeral(interaction, content="This command can only be used in a server.")
            return False

        try:
            actor = await guild.fetch_member(actor.id)
        except Exception:
            actor = guild.get_member(actor.id) or actor

        try:
            target = await guild.fetch_member(target.id)
        except Exception:
            target = guild.get_member(target.id) or target

        try:
            bot_user_id = getattr(getattr(self.bot, "user", None), "id", 0)
            if bot_user_id:
                bot_member = await guild.fetch_member(bot_user_id)
            else:
                bot_member = guild.me or bot_member
        except Exception:
            bot_member = guild.me or guild.get_member(getattr(getattr(self.bot, "user", None), "id", 0)) or bot_member

        if target == actor:
            await self._send_ephemeral(interaction, content=f"You cannot `{action_label}` yourself.")
            return False
        if target == bot_member:
            await self._send_ephemeral(interaction, content=f"You cannot `{action_label}` the bot.")
            return False
        if target == guild.owner:
            await self._send_ephemeral(interaction, content=f"You cannot `{action_label}` the server owner.")
            return False
        if actor != guild.owner and actor.top_role <= target.top_role:
            await self._send_ephemeral(
                interaction,
                content="ยศของคุณไม่สูงพอสำหรับการดำเนินการนี้",
            )
            return False
        if bot_member.top_role <= target.top_role:
            bot_role = f"{bot_member.top_role.name} ({bot_member.top_role.position})"
            target_role = f"{target.top_role.name} ({target.top_role.position})"
            await self._send_ephemeral(
                interaction,
                content=(
                    "บอทไม่สามารถแบนหรือเตะสมาชิกนี้ได้ เพราะยศบอทต้องสูงกว่าเป้าหมาย\n"
                    f"ยศบอท: `{bot_role}` | ยศเป้าหมาย: `{target_role}`\n"
                    "วิธีแก้: ไปที่ Server Settings > Roles แล้วเลื่อนยศบอทให้อยู่สูงกว่าเป้าหมาย"
                ),
            )
            return False
        return True

    async def _build_rank_info(self, guild: discord.Guild, member: discord.Member) -> tuple[int, int, int]:
        row = await levels_users_db.get(guild_id=guild.id, user_id=member.id)
        total_xp = _safe_int((row or {}).get("total_xp"), 0)
        level = _safe_int((row or {}).get("level"), 0)

        rows = await levels_users_db.gets(guild_id=guild.id)
        ranked = sorted(rows or [], key=lambda item: _safe_int(item.get("total_xp"), 0), reverse=True)
        rank = 0
        for index, item in enumerate(ranked, start=1):
            if _safe_int(item.get("user_id"), 0) == member.id:
                rank = index
                break
        if rank <= 0:
            rank = len(ranked) + 1
        return rank, level, total_xp

    async def _moderation_action_common(
        self,
        interaction: discord.Interaction,
        user: discord.Member | discord.User,
        *,
        required_permission: str,
        action_label: str,
    ) -> discord.Member | None:
        target = await self._resolve_target_member(interaction, user)
        if target is None:
            return None
        if not await self._actor_has_permission(interaction, required_permission):
            return None
        if not await self._ensure_bot_permission(interaction, required_permission):
            return None
        if not await self._ensure_target_is_moderatable(
            interaction,
            target,
            action_label=action_label,
        ):
            return None
        return target

    def cog_unload(self) -> None:
        for item in self._registered:
            try:
                self.bot.tree.remove_command(item.name, type=item.type)
            except Exception:
                pass
        self._registered.clear()

    async def user_info_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        guild = interaction.guild
        member = user if isinstance(user, discord.Member) else None
        if guild and member is None:
            member = guild.get_member(user.id)

        embed = discord.Embed(
            title="ข้อมูลผู้ใช้",
            color=color.blue,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=f"{user.mention}\n`{user}`", inline=True)
        embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="Bot", value="Yes" if user.bot else "No", inline=True)
        embed.add_field(name="Account Created", value=_fmt_ts(user.created_at), inline=False)

        if member:
            embed.add_field(name="Joined Server", value=_fmt_ts(member.joined_at), inline=False)
            top_role = getattr(member, "top_role", None)
            roles_count = max(len(getattr(member, "roles", []) or []) - 1, 0)
            embed.add_field(
                name="Top Role",
                value=top_role.mention if top_role and top_role != guild.default_role else "-",
                inline=True,
            )
            embed.add_field(name="Role Count", value=f"`{roles_count}`", inline=True)
            embed.add_field(name="Nickname", value=member.display_name or "-", inline=True)

        await self._send_ephemeral(interaction, embed=embed)

    async def user_avatar_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        guild = interaction.guild
        member = user if isinstance(user, discord.Member) else None
        if guild and member is None:
            member = guild.get_member(user.id)

        embed = discord.Embed(
            title=f"Avatar - {user}",
            color=color.blue,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(
            name="Display Avatar",
            value=f"[Open]({user.display_avatar.url})",
            inline=False,
        )
        if member and getattr(member, "guild_avatar", None):
            embed.add_field(
                name="Server Avatar",
                value=f"[Open]({member.guild_avatar.url})",
                inline=False,
            )

        await self._send_ephemeral(interaction, embed=embed)

    async def user_rank_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        member = await self._resolve_target_member(interaction, user)
        if member is None:
            return
        rank, level, total_xp = await self._build_rank_info(member.guild, member)
        embed = discord.Embed(
            title=f"Rank - {member.display_name}",
            description=(
                f"Rank: **#{rank}**\n"
                f"Level: **{level}**\n"
                f"Total XP: **{total_xp:,}**"
            ),
            color=color.green,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_ephemeral(interaction, embed=embed)

    async def user_level_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        member = await self._resolve_target_member(interaction, user)
        if member is None:
            return
        row = await levels_users_db.get(guild_id=member.guild.id, user_id=member.id) or {}
        rank, level, total_xp = await self._build_rank_info(member.guild, member)
        embed = discord.Embed(
            title=f"Level Detail - {member.display_name}",
            color=color.blue,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Rank", value=f"`#{rank}`", inline=True)
        embed.add_field(name="Level", value=f"`{level}`", inline=True)
        embed.add_field(name="Total XP", value=f"`{total_xp:,}`", inline=True)
        embed.add_field(name="Text XP", value=f"`{_safe_int(row.get('text_xp'), 0):,}`", inline=True)
        embed.add_field(name="Voice XP", value=f"`{_safe_int(row.get('voice_xp'), 0):,}`", inline=True)
        embed.add_field(name="Command XP", value=f"`{_safe_int(row.get('command_xp'), 0):,}`", inline=True)
        embed.add_field(name="Reaction XP", value=f"`{_safe_int(row.get('reaction_xp'), 0):,}`", inline=True)
        await self._send_ephemeral(interaction, embed=embed)

    async def user_actions_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        target = await self._resolve_target_member(interaction, user)
        if target is None:
            return
        guild = interaction.guild
        if guild is None:
            await self._send_ephemeral(interaction, content="This command can only be used in a server.")
            return
        embed = discord.Embed(
            title=f"Quick Actions - {target.display_name}",
            description="ใช้ปุ่มด้านล่างเพื่อการกลั่นกรองและเครื่องมือผู้ใช้ที่รวดเร็ว",
            color=color.blue,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        view = UserQuickActionsView(
            cog=self,
            actor_user_id=interaction.user.id,
            guild_id=guild.id,
            target_user_id=target.id,
        )
        await self._send_ephemeral(interaction, embed=embed, view=view)

    async def user_balance_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        member = await self._resolve_target_member(interaction, user)
        if member is None:
            return
        wallet = await economy_wallets_db.get(guild_id=member.guild.id, user_id=member.id) or {}
        cash = _safe_int(wallet.get("cash"), 0)
        bank = _safe_int(wallet.get("bank"), 0)
        total = cash + bank
        embed = discord.Embed(
            title=f"Balance - {member.display_name}",
            color=color.aqua,
            timestamp=discord.utils.utcnow(),
            description=(
                f"Cash: **{cash:,}**\n"
                f"Bank: **{bank:,}**\n"
                f"Total: **{total:,}**"
            ),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_ephemeral(interaction, embed=embed)

    async def user_ban_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        target = await self._moderation_action_common(
            interaction,
            user,
            required_permission="ban_members",
            action_label="ban",
        )
        if target is None:
            return
        actor = interaction.user
        reason = f"Banned via Apps context menu by {actor} ({actor.id})"
        await self._defer_ephemeral(interaction)
        try:
            await target.ban(reason=reason)
        except discord.Forbidden:
            await self._send_ephemeral(
                interaction,
                content=(
                    "บอทไม่สามารถแบนสมาชิกนี้ได้ เพราะยศบอทต่ำกว่าหรือสิทธิ์ไม่พอ\n"
                    "ให้เลื่อนยศบอทขึ้น และเปิดสิทธิ์ `Ban Members` ก่อน"
                ),
            )
            return
        except Exception as exc:
            await self._send_ephemeral(interaction, content=f"Failed to ban user: `{exc}`")
            return
        embed = discord.Embed(
            title="สมาชิกถูกแบน",
            description=f"{target.mention} has been banned.",
            color=color.red,
            timestamp=discord.utils.utcnow(),
        )
        await self._send_ephemeral(interaction, embed=embed)

    async def user_kick_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        target = await self._moderation_action_common(
            interaction,
            user,
            required_permission="kick_members",
            action_label="kick",
        )
        if target is None:
            return
        actor = interaction.user
        reason = f"Kicked via Apps context menu by {actor} ({actor.id})"
        await self._defer_ephemeral(interaction)
        try:
            await target.kick(reason=reason)
        except discord.Forbidden:
            await self._send_ephemeral(
                interaction,
                content=(
                    "บอทไม่สามารถเตะสมาชิกนี้ได้ เพราะยศบอทต่ำกว่าหรือสิทธิ์ไม่พอ\n"
                    "ให้เลื่อนยศบอทขึ้น และเปิดสิทธิ์ `Kick Members` ก่อน"
                ),
            )
            return
        except Exception as exc:
            await self._send_ephemeral(interaction, content=f"Failed to kick user: `{exc}`")
            return
        embed = discord.Embed(
            title="สมาชิกถูกเตะ",
            description=f"{target.mention} has been kicked.",
            color=color.orange,
            timestamp=discord.utils.utcnow(),
        )
        await self._send_ephemeral(interaction, embed=embed)

    async def _timeout_member(
        self,
        interaction: discord.Interaction,
        user: discord.Member | discord.User,
        *,
        seconds: int,
        label: str,
    ):
        target = await self._moderation_action_common(
            interaction,
            user,
            required_permission="moderate_members",
            action_label="mute",
        )
        if target is None:
            return
        if target.is_timed_out():
            await self._send_ephemeral(interaction, content=f"{target.mention} is already muted.")
            return
        actor = interaction.user
        reason = f"Muted ({label}) via Apps context menu by {actor} ({actor.id})"
        await self._defer_ephemeral(interaction)
        try:
            await target.timeout(datetime.timedelta(seconds=max(1, int(seconds))), reason=reason)
        except Exception as exc:
            await self._send_ephemeral(interaction, content=f"Failed to mute user: `{exc}`")
            return
        embed = discord.Embed(
            title=f"Member Muted ({label})",
            description=f"{target.mention} has been muted.",
            color=color.yellow,
            timestamp=discord.utils.utcnow(),
        )
        await self._send_ephemeral(interaction, embed=embed)

    async def user_mute_10m_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        await self._timeout_member(interaction, user, seconds=600, label="10m")

    async def user_mute_1h_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        await self._timeout_member(interaction, user, seconds=3600, label="1h")

    async def user_unmute_menu(
        self, interaction: discord.Interaction, user: discord.Member | discord.User
    ):
        target = await self._moderation_action_common(
            interaction,
            user,
            required_permission="moderate_members",
            action_label="unmute",
        )
        if target is None:
            return
        if not target.is_timed_out():
            await self._send_ephemeral(interaction, content=f"{target.mention} is not muted.")
            return
        actor = interaction.user
        reason = f"Unmuted via Apps context menu by {actor} ({actor.id})"
        await self._defer_ephemeral(interaction)
        try:
            await target.timeout(None, reason=reason)
        except Exception as exc:
            await self._send_ephemeral(interaction, content=f"Failed to unmute user: `{exc}`")
            return
        embed = discord.Embed(
            title="สมาชิกเปิดเสียงแล้ว",
            description=f"{target.mention} has been unmuted.",
            color=color.green,
            timestamp=discord.utils.utcnow(),
        )
        await self._send_ephemeral(interaction, embed=embed)

    async def message_info_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        content = str(message.content or "").strip()
        content_preview = content[:800] if content else "-"

        embed = discord.Embed(
            title="ข้อมูลข้อความ",
            color=color.blue,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Author", value=f"{message.author.mention}\n`{message.author}`", inline=True)
        embed.add_field(name="Message ID", value=f"`{message.id}`", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Created", value=_fmt_ts(message.created_at), inline=False)
        embed.add_field(name="Attachments", value=f"`{len(message.attachments)}`", inline=True)
        embed.add_field(name="Embeds", value=f"`{len(message.embeds)}`", inline=True)
        embed.add_field(name="Jump Link", value=f"[Open Message]({message.jump_url})", inline=True)
        embed.add_field(name="Content", value=content_preview, inline=False)

        await self._send_ephemeral(interaction, embed=embed)

    async def quote_message_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        content = str(message.content or "").strip()
        if not content and message.attachments:
            content = "[Attachment only]"
        if not content:
            content = "[No text content]"

        embed = discord.Embed(
            description=content[:1900],
            color=color.blue,
            timestamp=message.created_at or discord.utils.utcnow(),
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Source", value=f"{message.channel.mention} | [Jump]({message.jump_url})", inline=False)
        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join([f"[{a.filename}]({a.url})" for a in message.attachments[:5]]),
                inline=False,
            )

        await self._send_ephemeral(interaction, embed=embed)


async def setup(bot: AutoShardedBot):
    await bot.add_cog(ContextApps(bot))


