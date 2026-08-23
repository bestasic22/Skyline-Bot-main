from __future__ import annotations

import discord

from skylinebot.style import color


class VoicePanelPresenter:
    """Encapsulates voice-channel panel representation and region options."""

    def __init__(self, bot):
        self.bot = bot

    async def build_embed(self, channel: discord.VoiceChannel) -> discord.Embed:
        embed = discord.Embed(title="แผงควบคุมห้องเสียง", color=color.white)

        embed.add_field(name="Channel:", value=channel.mention, inline=True)
        embed.add_field(
            name="Users Limit:",
            value=f"`{channel.user_limit if channel.user_limit != 0 else 'ไม่จำกัด'}`",
            inline=True,
        )
        embed.add_field(name="", value="", inline=False)
        embed.add_field(name="Bitrate:", value=f"`{channel.bitrate / 1000}kbps`", inline=True)
        embed.add_field(name="Slowmode:", value=f"`{channel.slowmode_delay}s`", inline=True)
        embed.add_field(name="NSFW:", value=f"`{channel.is_nsfw()}`", inline=True)
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="Video Quality Mode:",
            value=f"`{channel.video_quality_mode.name}`",
            inline=True,
        )
        embed.add_field(
            name="Region:",
            value=f"`{channel.rtc_region if channel.rtc_region else 'Automatic'}`",
            inline=True,
        )
        embed.add_field(
            name="Created At:",
            value=f"<t:{int(channel.created_at.timestamp())}:F>",
            inline=True,
        )
        embed.set_footer(text=f"Channel ID: {channel.id}")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        return embed

    def build_region_options(self, channel: discord.VoiceChannel) -> list[discord.SelectOption]:
        def is_default(region: str | None) -> bool:
            return channel.rtc_region == region

        return [
            discord.SelectOption(
                label="Automatic",
                value="Automatic",
                emoji="🌐",
                default=channel.rtc_region is None,
            ),
            discord.SelectOption(label="US East", value="us-east", emoji="🌐", default=is_default("us-east")),
            discord.SelectOption(label="US West", value="us-west", emoji="🇺🇸", default=is_default("us-west")),
            discord.SelectOption(label="US South", value="us-south", emoji="🇺🇸", default=is_default("us-south")),
            discord.SelectOption(label="US Central", value="us-central", emoji="🇺🇸", default=is_default("us-central")),
            discord.SelectOption(label="Singapore", value="singapore", emoji="🇸🇬", default=is_default("singapore")),
            discord.SelectOption(label="South Africa", value="south-africa", emoji="🇿🇦", default=is_default("south-africa")),
            discord.SelectOption(label="South Korea", value="south-korea", emoji="🇰🇷", default=is_default("south-korea")),
            discord.SelectOption(label="Sydney", value="sydney", emoji="🇦🇺", default=is_default("sydney")),
            discord.SelectOption(label="Brazil", value="brazil", emoji="🇧🇷", default=is_default("brazil")),
            discord.SelectOption(label="Hong Kong", value="hong-kong", emoji="🇭🇰", default=is_default("hong-kong")),
            discord.SelectOption(label="Russia", value="russia", emoji="🇷🇺", default=is_default("russia")),
            discord.SelectOption(label="Europe", value="europe", emoji="🇪🇺", default=is_default("europe")),
            discord.SelectOption(label="Japan", value="japan", emoji="🇯🇵", default=is_default("japan")),
            discord.SelectOption(label="India", value="india", emoji="🇮🇳", default=is_default("india")),
        ]
