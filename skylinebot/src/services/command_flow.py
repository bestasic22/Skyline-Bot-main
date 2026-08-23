from __future__ import annotations

from typing import Iterable

import discord
from discord.ext import commands


class CommandFlow:
    """Reusable helpers for cog command entrypoints."""

    def __init__(self, bot):
        self.bot = bot

    def build_group_help_embed(
        self,
        ctx: commands.Context,
        *,
        title: str,
        description: str,
        accent_color: discord.Color | int,
        footer_text: str | None = None,
        include_options_hint: bool = False,
    ) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=accent_color)

        lines = self._format_group_commands(ctx)
        if lines:
            embed.add_field(name="Commands", value="\n".join(lines), inline=False)

        if include_options_hint:
            embed.add_field(
                name="Tip",
                value="Use slash command autocomplete to discover arguments quickly.",
                inline=False,
            )

        if footer_text:
            icon_url = None
            if getattr(self.bot, "user", None):
                icon_url = self.bot.user.display_avatar.url
            embed.set_footer(text=footer_text, icon_url=icon_url)

        return embed

    async def send_group_help(
        self,
        ctx: commands.Context,
        *,
        title: str,
        description: str,
        accent_color: discord.Color | int,
        footer_text: str | None = None,
        include_options_hint: bool = False,
    ):
        embed = self.build_group_help_embed(
            ctx,
            title=title,
            description=description,
            accent_color=accent_color,
            footer_text=footer_text,
            include_options_hint=include_options_hint,
        )
        return await ctx.send(embed=embed)

    def _format_group_commands(self, ctx: commands.Context) -> list[str]:
        command = getattr(ctx, "command", None)
        if command is None:
            return []

        prefix = getattr(getattr(self.bot, "BotConfig", None), "PREFIX", "!")
        commands_iter: Iterable = getattr(command, "commands", [])
        if commands_iter:
            return [
                f"`{prefix}{command.name} {child.name}` - {child.help or 'No description'}"
                for child in sorted(commands_iter, key=lambda item: item.name)
            ]

        return [f"`{prefix}{command.name}` - {command.help or 'No description'}"]
