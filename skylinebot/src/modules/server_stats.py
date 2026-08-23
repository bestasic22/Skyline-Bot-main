import asyncio
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from skylinebot.console.logging import logger
from skylinebot.memory.cache import cache
from storage import server_stats as db


class ServerStats(commands.Cog):
    serverstats_group = app_commands.Group(
        name="serverstats",
        description="Server stats commands",
    )

    def __init__(self, bot):
        self.bot = bot
        self._guild_locks: dict[int, asyncio.Lock] = {}
        self._last_update_at: dict[int, float] = {}
        self._min_update_interval_sec = 12.0

    async def cog_load(self):
        if not self.update_stats.is_running():
            self.update_stats.start()

    def cog_unload(self):
        if self.update_stats.is_running():
            self.update_stats.cancel()

    async def _wait_until_ready_safely(self) -> bool:
        while not self.bot.is_closed():
            # Avoid wait_until_ready() here because this cog can be loaded
            # before discord.py finishes client initialization.
            if getattr(self.bot, "user", None) is not None and self.bot.is_ready():
                return True
            await asyncio.sleep(1)
        return False

    async def _settings_for_guild(self, guild_id: int) -> dict:
        settings = cache.server_stats_cache.get(str(guild_id))
        if settings:
            return settings
        try:
            settings = await db.get(guild_id)
            if settings:
                cache.server_stats_cache[str(guild_id)] = settings
                return settings
        except Exception as error:
            logger.error(f"ServerStats load settings failed ({guild_id}): {error}")
        return {}

    @staticmethod
    def _safe_int(value: object) -> Optional[int]:
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        try:
            return int(raw)
        except Exception:
            return None

    async def _resolve_channel(self, guild: discord.Guild, channel_id: Optional[int]):
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        if channel:
            return channel
        try:
            channel = await self.bot.fetch_channel(channel_id)
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                return channel
        except Exception:
            return None
        return None

    @staticmethod
    def _is_transient_channel_update_error(error: Exception) -> bool:
        try:
            if int(getattr(error, "winerror", 0) or 0) == 10053:
                return True
        except Exception:
            pass
        try:
            if int(getattr(error, "errno", 0) or 0) == 10053:
                return True
        except Exception:
            pass
        text = str(error or "").lower()
        transient_markers = (
            "winerror 10053",
            "connection was aborted by the software in your host machine",
            "cannot write to closing transport",
            "connection reset by peer",
            "server disconnected",
        )
        return any(marker in text for marker in transient_markers)

    async def get_stat_count(
        self, guild: discord.Guild, stat_type: str, role_id: Optional[str] = None
    ) -> int:
        if stat_type == "total_members":
            return guild.member_count or 0
        if stat_type == "members":
            return sum(1 for m in guild.members if not m.bot)
        if stat_type == "bots":
            return sum(1 for m in guild.members if m.bot)
        if stat_type == "voice":
            return sum(len(vc.members) for vc in guild.voice_channels)
        if stat_type == "boosts":
            return guild.premium_subscription_count or 0
        if stat_type == "online":
            return sum(1 for m in guild.members if m.status == discord.Status.online)
        if stat_type == "idle":
            return sum(1 for m in guild.members if m.status == discord.Status.idle)
        if stat_type == "dnd":
            return sum(1 for m in guild.members if m.status == discord.Status.dnd)
        if stat_type == "offline":
            return sum(1 for m in guild.members if m.status == discord.Status.offline)
        if stat_type == "role" and role_id:
            role = guild.get_role(int(role_id))
            return len(role.members) if role else 0
        return 0

    async def _edit_channel_name_if_needed(
        self, *, guild: discord.Guild, channel_id: Optional[int], raw_format: str, count: int
    ):
        channel = await self._resolve_channel(guild, channel_id)
        if not channel:
            return
        fmt = str(raw_format or "{Count}")
        new_name = fmt.replace("{Count}", str(count)).replace("{count}", str(count)).strip()
        if not new_name:
            return
        if len(new_name) > 100:
            new_name = new_name[:100]
        if channel.name == new_name:
            return
        try:
            await channel.edit(name=new_name)
        except discord.Forbidden:
            logger.warning(
                f"ServerStats ไม่มีสิทธิ์เปลี่ยนชื่อห้อง | guild={guild.id} channel={channel.id}"
            )
        except Exception as error:
            if self._is_transient_channel_update_error(error):
                logger.warning(
                    "ServerStats transient channel update failure "
                    f"({guild.id}:{channel.id}): {error} | will_retry=next_cycle"
                )
            else:
                logger.error(
                    f"ServerStats update channel failed ({guild.id}:{channel.id}): {error}"
                )

    async def update_guild_stats(self, guild: discord.Guild, *, force: bool = False):
        if not guild:
            return
        lock = self._guild_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            last = self._last_update_at.get(guild.id, 0.0)
            if not force and (now - last) < self._min_update_interval_sec:
                return

            settings = await self._settings_for_guild(guild.id)
            if not settings or not settings.get("enabled"):
                self._last_update_at[guild.id] = now
                return

            for config in settings.get("stats_configs", []):
                try:
                    stat_type = str(config.get("type") or "").strip()
                    channel_id = self._safe_int(config.get("channel_id"))
                    if not stat_type or not channel_id:
                        continue
                    count = await self.get_stat_count(guild, stat_type)
                    await self._edit_channel_name_if_needed(
                        guild=guild,
                        channel_id=channel_id,
                        raw_format=str(config.get("format") or "{Count}"),
                        count=count,
                    )
                except Exception as error:
                    logger.error(f"ServerStats config error ({guild.id}): {error}")

            for role_stat in settings.get("role_stats", []):
                try:
                    role_id = str(role_stat.get("role_id") or "").strip()
                    channel_id = self._safe_int(role_stat.get("channel_id"))
                    if not role_id or not channel_id:
                        continue
                    count = await self.get_stat_count(guild, "role", role_id)
                    await self._edit_channel_name_if_needed(
                        guild=guild,
                        channel_id=channel_id,
                        raw_format=str(role_stat.get("format") or "{Count}"),
                        count=count,
                    )
                except Exception as error:
                    logger.error(f"ServerStats role config error ({guild.id}): {error}")

            self._last_update_at[guild.id] = time.monotonic()

    def _queue_update(self, guild: Optional[discord.Guild], *, force: bool = False):
        if not guild:
            return
        asyncio.create_task(self.update_guild_stats(guild, force=force))

    @tasks.loop(minutes=1)
    async def update_stats(self):
        for guild in self.bot.guilds:
            await self.update_guild_stats(guild)
            await asyncio.sleep(0.35)

    @update_stats.before_loop
    async def before_update_stats(self):
        await self._wait_until_ready_safely()

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            self._queue_update(guild, force=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        self._queue_update(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self._queue_update(member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot and after.bot:
            return
        if before.status != after.status or before.premium_since != after.premium_since:
            self._queue_update(after.guild)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.status != after.status:
            self._queue_update(after.guild)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            self._queue_update(member.guild)

    @serverstats_group.command(name="setup", description="ตั้งค่าช่องแสดงสถิติเซิร์ฟเวอร์")
    @app_commands.describe(
        type="ประเภทสถิติ (total_members, members, bots, voice, boosts, online, offline, dnd, idle)",
        channel="ช่องที่จะแสดง (แนะนำเป็นห้องเสียง)",
        format="รูปแบบข้อความ (ใช้ {Count} แทนจำนวน)",
    )
    @commands.has_permissions(administrator=True)
    async def stats_setup(
        self,
        interaction: discord.Interaction,
        type: str,
        channel: discord.VoiceChannel,
        format: str = "{Count}",
    ):
        guild_id = interaction.guild_id
        settings = await db.get(guild_id)

        if not settings:
            settings = await db.insert(guild_id=guild_id, enabled=True)

        configs = settings.get("stats_configs", [])
        found = False
        for cfg in configs:
            if cfg.get("type") == type:
                cfg["channel_id"] = str(channel.id)
                cfg["format"] = format
                found = True
                break

        if not found:
            configs.append({"type": type, "channel_id": str(channel.id), "format": format})

        await db.update(settings["id"], stats_configs=configs, enabled=True)
        await interaction.response.send_message(
            f"✅ ตั้งค่าช่องสถิติ `{type}` เรียบร้อยแล้ว!",
            ephemeral=True,
        )
        await self.update_guild_stats(interaction.guild, force=True)


async def setup(bot):
    await bot.add_cog(ServerStats(bot))
