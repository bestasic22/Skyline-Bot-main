import discord
from discord.ext import commands
from discord.ui import LayoutView, Container, Section, TextDisplay, Separator, Thumbnail
from skylinebot.src.checks import checks
from skylinebot.config.config import BotConfigClass
BotConfig = BotConfigClass()

class MentionReply(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild and hasattr(self.bot, "ownerbot_runtime_allows_message"):
            try:
                if not await self.bot.ownerbot_runtime_allows_message(message.guild.id):
                    return
            except Exception:
                pass

        # Check if the bot was mentioned directly
        if message.content.strip() in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"):
            # Get prefix for this guild
            prefix = await self.bot.get_prefix(message)
            if isinstance(prefix, list):  # handle multiple prefixes
                prefix = prefix[0]
                
            # Create the display using Components V2
            section = Section(
                TextDisplay(
                    f"# **Hi, I'm {self.bot.user.name}**\n"
                    f"> ใช้คำสั่ง `/help`"
                ),
                accessory=Thumbnail(
                    media=discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url),
                    description="รูปโปรไฟล์บอท"
                ),
                id=1
            )

            container = Container(
                section,
                Separator(),
                TextDisplay("-# SkylineBOT - Skyline Development")
            )

            view = LayoutView(timeout=None)
            view.add_item(container)

            try:
                await message.channel.send(view=view)
            except discord.errors.Forbidden:
                print(f"Cannot send message to channel {message.channel.id}: Missing permissions")
            except Exception as e:
                print(f"ข้อผิดพลาด sending message to channel {message.channel.id}: {e}")

async def setup(bot):
    await bot.add_cog(MentionReply(bot))

