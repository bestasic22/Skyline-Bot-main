import discord


from discord.ext import commands


import wavelink


from skylinebot.src.checks import checks


import storage.guilds


import storage.music


from skylinebot.console.logging import logger


from skylinebot.style import color


import traceback, sys


import asyncio


from skylinebot.engine.bot_runtime import AutoShardedBot

from skylinebot.workflows.ui import create_music_controller_image
from skylinebot.utils import i18n
from skylinebot.utils import music_playlists as user_music_playlists
from skylinebot.utils.music_access import (
    evaluate_music_access,
    is_member_admin_like,
)


import datetime
from pathlib import Path
from io import BytesIO
from typing import Callable


import storage


import re
import os
from skylinebot.bridge import lavalink as lavalink_bridge

INVALID_NODE_EXCEPTION = getattr(wavelink.exceptions, "InvalidNodeException", Exception)
CHANNEL_TIMEOUT_EXCEPTION = getattr(
    wavelink.exceptions, "ChannelTimeoutException", TimeoutError
)


def is_link(text):

    # Define a regex pattern to match URLs

    pattern = re.compile(
        r"^(https?:\/\/)?"  # Match the protocol (http or https)
        r"((([A-Za-z0-9-]+\.)+[A-Za-z]{2,})|"  # Match domain (e.g. example.com)
        r"((\d{1,3}\.){3}\d{1,3}))"  # Match IP address (e.g. 192.168.0.1)
        r"(:\d+)?(\/\S*)?$",  # Optional port and resource path
        re.IGNORECASE,
    )

    return re.match(pattern, text) is not None


def convert_ms_to_beautiful_time(ms: int):

    try:

        seconds = ms // 1000

        minutes, seconds = divmod(seconds, 60)

        hours, minutes = divmod(minutes, 60)

        days, hours = divmod(hours, 24)

        weeks, days = divmod(days, 7)

        months, weeks = divmod(weeks, 4)

        time = ""

        if months:

            time += f"{months}M "

        if weeks:

            time += f"{weeks}W "

        if days:

            time += f"{days}D "

        if hours:

            time += f"{hours}h "

        if minutes:

            time += f"{minutes}m "

        if seconds:

            time += f"{seconds}s"

        return time.strip() or "0s"

    except Exception as e:

        logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

        return "Unknown"


class SkylineBOTMusicControllerView(discord.ui.LayoutView):

    def __init__(
        self,
        cog: "Music",
        guild: discord.Guild,
        player: wavelink.Player | None,
        artwork_media: str,
        interactive: bool = True,
    ) -> None:

        super().__init__(timeout=None if interactive else 180)

        self.cog = cog

        self.guild = guild

        self.player = player

        self.interactive = interactive and player is not None

        self.artwork_media = artwork_media

        self._build()

    def _build(self) -> None:

        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(f"# 🎶 {self.cog.t(self.guild.id, 'music_title')}")
        )

        track_uri: str | None = None
        show_gallery = False

        if self.player and self.player.current:
            current = self.player.current
            track_uri = getattr(current, "uri", None)
            container.add_item(
                discord.ui.TextDisplay(
                    f"## 🎵 {self.cog._truncate_track_text(current.title, 80)}"
                )
            )
            container.add_item(
                discord.ui.TextDisplay(self.cog._build_track_info_block(self.player))
            )
            gallery = discord.ui.MediaGallery()
            gallery.add_item(media=self.artwork_media, description="ภาพปกเพลง")
            container.add_item(gallery)

        else:
            show_gallery = True

            container.add_item(
                discord.ui.TextDisplay(
                    f"## 🎧 {self.cog.t(self.guild.id, 'music_nothing_playing')}"
                )
            )

            container.add_item(
                discord.ui.TextDisplay(
                    f"-# {self.cog.t(self.guild.id, 'music_drop_song')}"
                )
            )

        if show_gallery:
            gallery = discord.ui.MediaGallery()
            gallery.add_item(media=self.artwork_media, description="ภาพปกเพลง")
            container.add_item(gallery)

        container.add_item(discord.ui.Separator())

        container.add_item(
            discord.ui.TextDisplay(self.cog._build_queue_summary(self.player))
        )

        row1 = discord.ui.ActionRow()

        volume_down_button = discord.ui.Button(
            label=self.cog.t(self.guild.id, "music_btn_volume_down"),
            style=discord.ButtonStyle.secondary,
            emoji="🔉",
            disabled=not self.interactive,
        )

        pause_button = discord.ui.Button(
            label=(
                self.cog.t(self.guild.id, "music_btn_resume")
                if self.player and self.player.paused
                else self.cog.t(self.guild.id, "music_btn_pause")
            ),
            style=(
                discord.ButtonStyle.success
                if self.player and self.player.paused
                else discord.ButtonStyle.primary
            ),
            emoji="⏯️",
            disabled=not self.interactive,
        )

        skip_button = discord.ui.Button(
            label=self.cog.t(self.guild.id, "music_btn_skip"),
            style=discord.ButtonStyle.secondary,
            emoji="⏭️",
            disabled=not self.interactive,
        )
        rewind_button = discord.ui.Button(
            label="-10s",
            style=discord.ButtonStyle.secondary,
            emoji="⏪",
            disabled=not self.interactive,
        )

        volume_up_button = discord.ui.Button(
            label=self.cog.t(self.guild.id, "music_btn_volume_up"),
            style=discord.ButtonStyle.secondary,
            emoji="🔊",
            disabled=not self.interactive,
        )

        autoplay_button = discord.ui.Button(
            label=(
                self.cog.t(self.guild.id, "music_btn_autoplay_on")
                if self.player and self.player.autoplay != wavelink.AutoPlayMode.disabled
                else self.cog.t(self.guild.id, "music_btn_autoplay_off")
            ),
            style=(
                discord.ButtonStyle.success
                if self.player
                and self.player.autoplay != wavelink.AutoPlayMode.disabled
                else discord.ButtonStyle.secondary
            ),
            emoji="🔁",
            disabled=not self.interactive,
        )

        if self.interactive:
            volume_down_button.callback = self.cog.volume_down_button_callback
            pause_button.callback = self.cog.pause_resume_button_callback
            skip_button.callback = self.cog.skip_button_callback
            rewind_button.callback = self.cog.rewind_button_callback
            volume_up_button.callback = self.cog.volume_up_button_callback
            autoplay_button.callback = self.cog.autoplay_toggle_callback

        row1.add_item(volume_down_button)
        row1.add_item(pause_button)
        row1.add_item(rewind_button)
        row1.add_item(skip_button)
        row1.add_item(volume_up_button)

        container.add_item(row1)

        row2 = discord.ui.ActionRow()

        queue_button = discord.ui.Button(
            label=self.cog.t(self.guild.id, "music_btn_queue"),
            style=discord.ButtonStyle.secondary,
            emoji="📜",
            disabled=not self.interactive,
        )

        lyrics_button = discord.ui.Button(
            label=self.cog.t(self.guild.id, "music_btn_lyrics"),
            style=discord.ButtonStyle.secondary,
            emoji="📝",
            disabled=not self.interactive,
        )

        loop_button = discord.ui.Button(
            label=(
                self.cog.t(self.guild.id, "music_btn_loop_on")
                if self.player and self.player.queue.mode == wavelink.QueueMode.loop
                else self.cog.t(self.guild.id, "music_btn_loop_off")
            ),
            style=(
                discord.ButtonStyle.success
                if self.player and self.player.queue.mode == wavelink.QueueMode.loop
                else discord.ButtonStyle.secondary
            ),
            emoji="🔂",
            disabled=not self.interactive,
        )

        shuffle_button = discord.ui.Button(
            label=self.cog.t(self.guild.id, "music_btn_shuffle"),
            style=discord.ButtonStyle.secondary,
            emoji="🔀",
            disabled=not self.interactive,
        )

        stop_button = discord.ui.Button(
            label=self.cog.t(self.guild.id, "music_btn_stop"),
            style=discord.ButtonStyle.danger,
            emoji="⏹️",
            disabled=not self.interactive,
        )
        forward_button = discord.ui.Button(
            label="+10s",
            style=discord.ButtonStyle.secondary,
            emoji="⏩",
            disabled=not self.interactive,
        )

        if self.interactive:
            queue_button.callback = self.cog.queue_button_callback
            lyrics_button.callback = self.cog.lyrics_button_callback
            loop_button.callback = self.cog.loop_toggle_callback
            shuffle_button.callback = self.cog.shuffle_button_callback
            stop_button.callback = self.cog.stop_button_callback
            forward_button.callback = self.cog.forward_button_callback

        row2.add_item(queue_button)
        row2.add_item(lyrics_button)
        row2.add_item(loop_button)
        row2.add_item(forward_button)
        row2.add_item(stop_button)

        container.add_item(row2)

        row3 = discord.ui.ActionRow()
        save_button = discord.ui.Button(
            label="Save",
            style=discord.ButtonStyle.secondary,
            emoji="💾",
            disabled=not self.interactive,
        )
        my_playlist_button = discord.ui.Button(
            label="My Playlist",
            style=discord.ButtonStyle.primary,
            emoji="🎼",
            disabled=False,
        )
        if self.interactive:
            save_button.callback = self.cog.save_current_to_playlist_button_callback
        my_playlist_button.callback = (
            self.cog.open_user_playlist_picker_button_callback
        )
        row3.add_item(shuffle_button)
        row3.add_item(autoplay_button)
        row3.add_item(save_button)
        row3.add_item(my_playlist_button)
        container.add_item(row3)

        playlist_options = self.cog._playlist_select_options(self.guild.id)
        if playlist_options:
            playlist_select = discord.ui.Select(
                placeholder="🎼 เลือกเพลย์ลิสต์อัตโนมัติ",
                min_values=1,
                max_values=1,
                options=playlist_options,
                disabled=not self.interactive,
            )
            if self.interactive:
                playlist_select.callback = self.cog.playlist_select_callback
            playlist_row = discord.ui.ActionRow()
            playlist_row.add_item(playlist_select)
            container.add_item(playlist_row)

        dashboard_music_url = self.cog._guild_music_dashboard_url(self.guild.id)
        if self.cog._is_valid_button_url(track_uri) or self.cog._is_valid_button_url(
            dashboard_music_url
        ):
            link_row = discord.ui.ActionRow()
            if self.cog._is_valid_button_url(track_uri):
                link_button = discord.ui.Button(
                    label=self.cog.t(self.guild.id, "music_btn_open_original"),
                    style=discord.ButtonStyle.link,
                    url=track_uri,
                    emoji="🔗",
                )
                link_row.add_item(link_button)
            if self.cog._is_valid_button_url(dashboard_music_url):
                dashboard_button = discord.ui.Button(
                    label="เว็บเพลงกิลด์นี้",
                    style=discord.ButtonStyle.link,
                    url=dashboard_music_url,
                    emoji="🌐",
                )
                link_row.add_item(dashboard_button)
            container.add_item(link_row)

        self.add_item(container)



class Music(commands.Cog):

    CONTROLLER_COOLDOWN_SECONDS = 1.5
    IDLE_DISCONNECT_SECONDS = 300
    SEARCH_PICK_LIMIT = 10
    SEEK_STEP_MS = 10_000
    PENDING_PICK_TTL_SECONDS = 240
    USER_PLAYLIST_LIMIT = user_music_playlists.MAX_USER_PLAYLISTS
    USER_PLAYLIST_ITEM_LIMIT = user_music_playlists.MAX_ITEMS_PER_PLAYLIST
    PLAYLIST_CATALOG: dict[str, dict[str, object]] = {
        "thai_pop": {
            "label": "Thai Pop",
            "emoji": "🇹🇭",
            "queries": [
                "Tilly Birds เพื่อนเล่น ไม่เล่นเพื่อน",
                "MILLI - สุดปัง",
                "Three Man Down ฝนตกไหม",
                "Billkin กีดกัน",
                "BOWKYLION ลงใจ",
            ],
        },
        "chill": {
            "label": "Chill Mix",
            "emoji": "🌙",
            "queries": [
                "chill hits playlist",
                "LANY Malibu Nights",
                "RINI My Favourite Clothes",
                "HONNE Day 1",
                "Daniel Caesar Best Part",
            ],
        },
        "lofi": {
            "label": "Lo-Fi Study",
            "emoji": "📚",
            "queries": [
                "lofi hip hop beats to relax/study to",
                "j'san alone by your side",
                "idealism both of us",
                "Aso Seasons",
                "Nymano Solitude",
            ],
        },
        "edm": {
            "label": "EDM Party",
            "emoji": "🎉",
            "queries": [
                "Martin Garrix Animals",
                "Alan Walker Faded",
                "The Chainsmokers Closer",
                "Avicii Wake Me Up",
                "David Guetta Titanium",
            ],
        },
    }

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        class CogInfo:

            name = "Music"

            category = "Main"

            description = "Music commands"

            hidden = False

            emoji = self.bot.emoji.MUSIC 

        self.cog_info = CogInfo
        self._voice_presence_task: asyncio.Task | None = None
        self._pending_pick_cleanup_task: asyncio.Task | None = None
        self._voice_connect_retry_after: dict[int, float] = {}
        self._voice_connecting_guilds: set[int] = set()
        self._voice_connect_started_at: dict[int, float] = {}
        self._pending_track_picks: dict[tuple[int, int, int], dict] = {}
        self._controller_channel_missing_warned_at: dict[int, float] = {}
        self._controller_channel_missing_suppressed: dict[int, int] = {}
        self._controller_channel_missing_log_cooldown_seconds: int = 180

    def _music_policy_for_guild(self, guild_id: int) -> dict:
        return self.bot.cache.music.get(str(guild_id), {}) or {}

    def _music_access_for_actor(
        self,
        *,
        guild: discord.Guild | None,
        actor: discord.Member | discord.User | None,
        channel_id: int | None,
    ) -> tuple[bool, str]:
        if guild is None or actor is None:
            return False, "ไม่พบข้อมูลกิลด์หรือผู้ใช้"

        actor_id = int(getattr(actor, "id", 0) or 0)
        role_ids: list[int] = []
        for role in list(getattr(actor, "roles", []) or []):
            try:
                role_id = int(getattr(role, "id", 0) or 0)
            except Exception:
                role_id = 0
            if role_id > 0:
                role_ids.append(role_id)

        is_owner = bool(actor_id and int(getattr(guild, "owner_id", 0) or 0) == actor_id)
        is_admin = is_member_admin_like(actor)
        return evaluate_music_access(
            self._music_policy_for_guild(guild.id),
            actor_user_id=actor_id,
            actor_role_ids=role_ids,
            actor_channel_id=channel_id,
            is_owner=is_owner,
            is_admin=is_admin,
        )

    async def _ensure_music_access_ctx(self, ctx: commands.Context) -> bool:
        allowed, message = self._music_access_for_actor(
            guild=getattr(ctx, "guild", None),
            actor=getattr(ctx, "author", None),
            channel_id=int(getattr(getattr(ctx, "channel", None), "id", 0) or 0),
        )
        if allowed:
            return True
        await ctx.reply(f"{self.bot.emoji.ERROR} | {message}", delete_after=10)
        return False

    async def _ensure_music_access_interaction(
        self, interaction: discord.Interaction
    ) -> bool:
        allowed, message = self._music_access_for_actor(
            guild=getattr(interaction, "guild", None),
            actor=getattr(interaction, "user", None),
            channel_id=int(getattr(interaction, "channel_id", 0) or 0),
        )
        if allowed:
            return True

        embed = discord.Embed(description=message, color=color.red)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embed, ephemeral=True, delete_after=8
                )
            else:
                await interaction.response.send_message(
                    embed=embed, ephemeral=True, delete_after=8
                )
        except Exception:
            pass
        return False

    async def _ensure_music_access_message(self, message: discord.Message) -> bool:
        allowed, denied_message = self._music_access_for_actor(
            guild=getattr(message, "guild", None),
            actor=getattr(message, "author", None),
            channel_id=int(getattr(getattr(message, "channel", None), "id", 0) or 0),
        )
        if allowed:
            return True
        await message.channel.send(
            f"{self.bot.emoji.ERROR} | {denied_message}",
            delete_after=8,
        )
        return False

    async def _safe_ctx_defer(self, ctx: commands.Context, ephemeral: bool = False):
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return
        if interaction.response.is_done():
            return
        try:
            await ctx.defer(ephemeral=ephemeral)
        except (discord.NotFound, discord.InteractionResponded):
            return
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                return
            raise

    async def _connect_with_node_retry(
        self, destination: discord.VoiceChannel, timeout: int = 25
    ) -> wavelink.Player:

        async def _ensure_connected_node() -> None:
            for _ in range(6):
                try:
                    wavelink.Pool.get_node()
                    return
                except INVALID_NODE_EXCEPTION:
                    try:
                        await lavalink_bridge.on_node(self.bot)
                    except Exception:
                        logger.error(
                            f"Failed to reconnect Lavalink node: {traceback.format_exc()}"
                        )
                    await asyncio.sleep(1.5)
            raise INVALID_NODE_EXCEPTION("No connected Lavalink node available.")

        async def _reconnect_lavalink_node(reason: str):
            logger.warning(
                f"[music_setup] {reason} while connecting to {destination.id}; reconnecting Lavalink and retrying"
            )
            try:
                await lavalink_bridge.on_node(self.bot)
            except Exception:
                logger.error(
                    f"Failed to reconnect Lavalink node: {traceback.format_exc()}"
                )
            await asyncio.sleep(2)

        await _ensure_connected_node()

        try:
            return await destination.connect(
                cls=wavelink.Player,
                timeout=timeout,
                self_deaf=True,
            )
        except INVALID_NODE_EXCEPTION:
            await _reconnect_lavalink_node("InvalidNodeException")
            await _ensure_connected_node()
            existing_vc = getattr(destination.guild, "voice_client", None)
            if existing_vc and getattr(existing_vc, "connected", False):
                return existing_vc
            return await destination.connect(
                cls=wavelink.Player,
                timeout=timeout,
                self_deaf=True,
            )
        except CHANNEL_TIMEOUT_EXCEPTION:
            await _reconnect_lavalink_node("ChannelTimeoutException")
            await _ensure_connected_node()
            existing_vc = getattr(destination.guild, "voice_client", None)
            if existing_vc and getattr(existing_vc, "connected", False):
                return existing_vc
            return await destination.connect(
                cls=wavelink.Player,
                timeout=timeout,
                self_deaf=True,
            )
        except discord.ClientException as e:
            if "Already connected to a voice channel" in str(e):
                existing_vc = getattr(destination.guild, "voice_client", None)
                if existing_vc and getattr(existing_vc, "connected", False):
                    return existing_vc
            raise

    def cog_unload(self):
        if self._voice_presence_task and not self._voice_presence_task.done():
            self._voice_presence_task.cancel()
        if self._pending_pick_cleanup_task and not self._pending_pick_cleanup_task.done():
            self._pending_pick_cleanup_task.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._voice_presence_task and not self._voice_presence_task.done():
            pass
        else:
            self._voice_presence_task = asyncio.create_task(self._voice_presence_loop())
        if self._pending_pick_cleanup_task and not self._pending_pick_cleanup_task.done():
            return
        self._pending_pick_cleanup_task = asyncio.create_task(
            self._pending_pick_cleanup_loop()
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        try:
            if not member or member.bot:
                return
            if before.channel and after.channel and before.channel.id == after.channel.id:
                return

            guild = getattr(member, "guild", None)
            if not guild:
                return
            guild_id = int(guild.id)
            user_id = int(member.id)

            pending_entries = [
                payload
                for (entry_guild_id, _channel_id, entry_user_id), payload in list(self._pending_track_picks.items())
                if int(entry_guild_id) == guild_id and int(entry_user_id) == user_id
            ]
            if not pending_entries:
                return

            current_channel_id = self._as_int(getattr(after.channel, "id", None))
            should_clear = False
            for payload in pending_entries:
                required_channel_id = self._as_int(payload.get("required_voice_channel_id"))
                if required_channel_id is None:
                    required_channel_id = self._as_int(
                        getattr(getattr(getattr(guild, "voice_client", None), "channel", None), "id", None)
                    )
                if required_channel_id is not None and current_channel_id != required_channel_id:
                    should_clear = True
                    break
                if required_channel_id is None and current_channel_id is None:
                    should_clear = True
                    break
            if not should_clear:
                return

            await self._clear_pending_track_picks_for_user(
                guild_id,
                user_id,
                reason=f"{self.bot.emoji.ERROR} | ยกเลิกรายการเลือกเพลง (ออกจากห้องเสียง)",
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    def _persistent_voice_enabled(self, guild_id: int) -> bool:
        return False

    def _connect_lock_stale(self, guild_id: int, stale_after: int = 35) -> bool:
        started_at = self._voice_connect_started_at.get(guild_id)
        if not started_at:
            return False
        return (datetime.datetime.now().timestamp() - started_at) >= stale_after

    def _set_connecting(self, guild_id: int) -> None:
        self._voice_connecting_guilds.add(guild_id)
        self._voice_connect_started_at[guild_id] = datetime.datetime.now().timestamp()

    def _clear_connecting(self, guild_id: int) -> None:
        self._voice_connecting_guilds.discard(guild_id)
        self._voice_connect_started_at.pop(guild_id, None)

    def _apply_inactive_timeout(self, vc: wavelink.Player, guild_id: int) -> None:
        vc.inactive_timeout = self.IDLE_DISCONNECT_SECONDS

    def _queued_track_count(self, vc: wavelink.Player | None) -> int:
        if not vc:
            return 0
        try:
            return len(getattr(vc, "queue", []) or [])
        except Exception:
            return 0

    def _has_active_voice_session(self, vc: wavelink.Player | None) -> bool:
        if not vc:
            return False
        if getattr(vc, "current", None):
            return True
        if bool(getattr(vc, "playing", False)) or bool(getattr(vc, "paused", False)):
            return True
        return self._queued_track_count(vc) > 0

    def _voice_busy_wait_message(self, vc: wavelink.Player | None) -> str:
        if not vc:
            return f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง"
        channel = getattr(vc, "channel", None)
        channel_label = channel.mention if channel else "`ไม่ทราบห้อง`"
        queue_count = self._queued_track_count(vc)
        remaining_count = queue_count + (1 if getattr(vc, "current", None) else 0)
        return (
            f"{self.bot.emoji.ERROR} | บอทกำลังใช้งานอยู่ที่ห้อง {channel_label}\n"
            f"กรุณารอบอทเล่นเพลงจบก่อนจึงจะทำตามคำขอของคุณ\n"
            f"เหลือเพลงอีก `{remaining_count}` เพลง (คิวรอ `{queue_count}` เพลง)"
        )

    def _selection_key(self, guild_id: int, channel_id: int, user_id: int) -> tuple[int, int, int]:
        return (int(guild_id), int(channel_id), int(user_id))

    def _cleanup_pending_track_picks(self) -> None:
        now = datetime.datetime.now().timestamp()
        stale_entries = [
            (key, payload)
            for key, payload in self._pending_track_picks.items()
            if float(payload.get("expires_at", 0)) <= now
        ]
        if not stale_entries:
            return
        for key, _payload in stale_entries:
            self._pending_track_picks.pop(key, None)
        for (_guild_id, channel_id, _user_id), payload in stale_entries:
            try:
                asyncio.create_task(
                    self._cleanup_track_pick_messages_by_channel_id(channel_id, payload)
                )
            except Exception:
                pass

    async def _prune_stale_track_picks(self) -> None:
        now = datetime.datetime.now().timestamp()
        stale_entries: list[tuple[tuple[int, int, int], dict]] = []
        for key, payload in list(self._pending_track_picks.items()):
            if float(payload.get("expires_at", 0)) <= now:
                stale_entries.append((key, payload))
        if not stale_entries:
            return
        for key, _payload in stale_entries:
            self._pending_track_picks.pop(key, None)
        for (_guild_id, channel_id, _user_id), payload in stale_entries:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                continue
            await self._cleanup_track_pick_messages(channel, payload)

    async def _cleanup_track_pick_messages_by_channel_id(
        self,
        channel_id: int,
        payload: dict | None,
    ) -> None:
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return
        await self._cleanup_track_pick_messages(channel, payload)

    def _remember_track_pick(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        *,
        query: str,
        tracks: list,
        mode: str = "await_pick",
        prompt_message_id: int | None = None,
        gate_message_id: int | None = None,
        required_voice_channel_id: int | None = None,
    ) -> None:
        self._cleanup_pending_track_picks()
        key = self._selection_key(guild_id, channel_id, user_id)
        self._pending_track_picks[key] = {
            "query": query,
            "tracks": tracks[: self.SEARCH_PICK_LIMIT],
            "mode": mode,
            "prompt_message_id": prompt_message_id,
            "gate_message_id": gate_message_id,
            "required_voice_channel_id": self._as_int(required_voice_channel_id),
            "expires_at": datetime.datetime.now().timestamp() + self.PENDING_PICK_TTL_SECONDS,
        }

    def _pop_track_pick(self, guild_id: int, channel_id: int, user_id: int) -> dict | None:
        self._cleanup_pending_track_picks()
        key = self._selection_key(guild_id, channel_id, user_id)
        return self._pending_track_picks.pop(key, None)

    def _peek_track_pick(self, guild_id: int, channel_id: int, user_id: int) -> dict | None:
        self._cleanup_pending_track_picks()
        key = self._selection_key(guild_id, channel_id, user_id)
        return self._pending_track_picks.get(key)

    async def _delete_channel_message(self, channel: discord.abc.Messageable, message_id: int | None) -> None:
        msg_id = self._as_int(message_id)
        if not channel or not msg_id:
            return
        try:
            partial = channel.get_partial_message(int(msg_id))
            await partial.delete()
        except Exception:
            pass

    async def _cleanup_track_pick_messages(
        self,
        channel: discord.abc.Messageable,
        payload: dict | None,
    ) -> None:
        if not payload:
            return
        message_ids = {
            self._as_int(payload.get("prompt_message_id")),
            self._as_int(payload.get("gate_message_id")),
        }
        for message_id in message_ids:
            await self._delete_channel_message(channel, message_id)

    async def _pop_track_pick_with_cleanup(
        self,
        guild_id: int,
        channel: discord.abc.Messageable,
        user_id: int,
    ) -> dict | None:
        payload = self._pop_track_pick(guild_id, channel.id, user_id)
        await self._cleanup_track_pick_messages(channel, payload)
        return payload

    async def _clear_pending_track_picks_for_user(
        self,
        guild_id: int,
        user_id: int,
        *,
        reason: str | None = None,
    ) -> int:
        guild_id = int(guild_id)
        user_id = int(user_id)
        entries = [
            (key, payload)
            for key, payload in list(self._pending_track_picks.items())
            if int(key[0]) == guild_id and int(key[2]) == user_id
        ]
        if not entries:
            return 0

        notified_channels: set[int] = set()
        for (entry_guild_id, channel_id, entry_user_id), payload in entries:
            self._pending_track_picks.pop((entry_guild_id, channel_id, entry_user_id), None)
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                continue
            await self._cleanup_track_pick_messages(channel, payload)
            if reason and int(channel_id) not in notified_channels:
                try:
                    await channel.send(reason, delete_after=6)
                except Exception:
                    pass
                notified_channels.add(int(channel_id))
        return len(entries)

    async def handle_pending_track_pick_message(self, message: discord.Message) -> bool:
        guild = getattr(message, "guild", None)
        if not guild:
            return False
        author = getattr(message, "author", None)
        if not author or getattr(author, "bot", False):
            return False

        guild_id = int(guild.id)
        pending_pick = self._peek_track_pick(guild_id, message.channel.id, author.id)
        if not pending_pick:
            return False

        pending_tracks = list(pending_pick.get("tracks", []))
        if not pending_tracks:
            await self._pop_track_pick_with_cleanup(guild_id, message.channel, author.id)
            return False

        pending_mode = str(pending_pick.get("mode") or "await_pick").strip().lower()
        search_text = (message.content or "").strip()
        picks, parse_error = self._parse_pick_input(search_text, len(pending_tracks))

        if pending_mode != "await_pick":
            if picks == []:
                await self._pop_track_pick_with_cleanup(guild_id, message.channel, author.id)
                await message.channel.send(
                    f"{self.bot.emoji.SUCCESS} | ยกเลิกการเลือกเพลงแล้ว",
                    delete_after=6,
                )
                return True
            if picks is not None or parse_error != "not_selection":
                await message.channel.send(
                    f"{self.bot.emoji.ERROR} | กดปุ่ม `เพลงไม่ตรงกับที่ต้องการ` ก่อน",
                    delete_after=6,
                )
                return True
            await self._pop_track_pick_with_cleanup(guild_id, message.channel, author.id)
            return False

        if picks == []:
            await self._pop_track_pick_with_cleanup(guild_id, message.channel, author.id)
            await message.channel.send(
                f"{self.bot.emoji.SUCCESS} | ยกเลิกการเลือกเพลงแล้ว",
                delete_after=6,
            )
            return True

        if picks is None:
            if parse_error != "not_selection":
                await message.channel.send(
                    f"{self.bot.emoji.ERROR} | รูปแบบไม่ถูกต้อง (เช่น `1`, `1 3 5`, `1-4`)",
                    delete_after=8,
                )
                return True
            await self._pop_track_pick_with_cleanup(guild_id, message.channel, author.id)
            return False

        vc: wavelink.Player | None = getattr(guild, "voice_client", None)
        if not vc or not getattr(vc, "connected", False):
            await self._pop_track_pick_with_cleanup(guild_id, message.channel, author.id)
            await message.channel.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่อยู่ห้องเสียง",
                delete_after=6,
            )
            return True

        if not getattr(author, "voice", None) or getattr(author.voice, "channel", None) != getattr(vc, "channel", None):
            await self._clear_pending_track_picks_for_user(
                guild_id,
                author.id,
                reason=f"{self.bot.emoji.ERROR} | ยกเลิกรายการเลือกเพลง (คุณไม่ได้อยู่ห้องเดียวกับบอท)",
            )
            return True

        pending_query = str(pending_pick.get("query") or "").strip()
        picked_set = set(picks)
        remaining_tracks = [
            track
            for index, track in enumerate(pending_tracks, start=1)
            if index not in picked_set
        ]
        await self._pop_track_pick_with_cleanup(guild_id, message.channel, author.id)

        selected_tracks = [pending_tracks[index - 1] for index in picks]
        guilds_subscription = self.bot.cache.guilds.get(str(guild_id), {}).get("subscription", "free")
        default_volume = (
            80
            if guilds_subscription == "free"
            else self.bot.cache.music.get(str(guild_id), {}).get("default_volume", 80)
        )
        changed_titles, skipped_count = await self._apply_tracks_to_player(
            vc=vc,
            tracks=selected_tracks,
            requester=author,
            default_volume=default_volume,
        )
        if not changed_titles:
            await message.channel.send(
                f"{self.bot.emoji.ERROR} | {self._queue_full_message_for_guild(guild_id)}",
                delete_after=8,
            )
            return True

        await self.send_music_controls(
            guild,
            update_attachments=True,
            command_channel=message.channel,
        )
        summary = (
            f"{self.bot.emoji.SUCCESS} | เพิ่มเพลงแล้ว {len(changed_titles)} เพลง"
            if len(changed_titles) > 1
            else f"{self.bot.emoji.SUCCESS} | เพิ่มเพลงแล้ว: {changed_titles[0]}"
        )
        if skipped_count:
            summary += f" (ข้าม {skipped_count} เพลง เพราะคิวเต็ม)"
        if remaining_tracks:
            required_voice_channel_id = self._as_int(
                getattr(getattr(vc, "channel", None), "id", None)
            )
            await self._send_track_pick_prompt(
                guild=guild,
                channel=message.channel,
                guild_id=guild_id,
                user_id=author.id,
                query=pending_query or search_text,
                tracks=remaining_tracks,
                required_voice_channel_id=required_voice_channel_id,
            )
        await message.channel.send(summary, delete_after=8)
        return True

    def _build_progress_bar(self, position_ms: int, duration_ms: int, width: int = 14) -> str:
        safe_duration = max(int(duration_ms or 0), 1)
        safe_position = max(0, min(int(position_ms or 0), safe_duration))
        pointer = int((safe_position / safe_duration) * width)
        pointer = max(0, min(pointer, width - 1))
        bar = []
        for idx in range(width):
            bar.append("🔘" if idx == pointer else "▬")
        return "".join(bar)

    def _build_visual_progress_bar(self, position_ms: int, duration_ms: int, width: int = 30) -> str:
        safe_width = max(int(width or 0), 8)
        safe_duration = max(int(duration_ms or 0), 1)
        safe_position = max(0, min(int(position_ms or 0), safe_duration))
        ratio = safe_position / safe_duration
        filled = int(ratio * safe_width)
        filled = max(0, min(filled, safe_width))
        return ("▰" * filled) + ("▱" * (safe_width - filled))

    def _build_now_playing_card_lines(
        self,
        player: wavelink.Player | None,
    ) -> tuple[str, str, str, str]:
        if not player or not player.current:
            return ("Unknown", "Unknown", "▱" * 30, "`0s    0s`")

        track = player.current
        title = self._truncate_track_text(getattr(track, "title", None) or "Unknown", 62)
        author = self._truncate_track_text(getattr(track, "author", None) or "Unknown", 42)

        duration_ms = max(int(getattr(track, "length", 0) or 0), 0)
        current_ms = max(int(getattr(player, "position", 0) or 0), 0)
        if duration_ms > 0:
            current_ms = min(current_ms, duration_ms)

        progress_line = self._build_visual_progress_bar(current_ms, duration_ms, width=30)
        current_label = convert_ms_to_beautiful_time(current_ms)
        duration_label = convert_ms_to_beautiful_time(duration_ms)
        gap_size = max(4, 34 - len(current_label) - len(duration_label))
        time_line = f"`{current_label}{' ' * gap_size}{duration_label}`"
        return (title, author, progress_line, time_line)

    def _build_track_pick_embed(
        self,
        guild: discord.Guild,
        query: str,
        tracks: list,
    ) -> discord.Embed:
        lines: list[str] = []
        for index, track in enumerate(tracks[: self.SEARCH_PICK_LIMIT], start=1):
            title = self._truncate_track_text(getattr(track, "title", "Unknown"), 60)
            author = self._truncate_track_text(getattr(track, "author", "Unknown"), 30)
            length = convert_ms_to_beautiful_time(getattr(track, "length", 0) or 0)
            lines.append(f"`{index:>2}` {title} • {author} • `{length}`")
        description = (
            f"คำค้นหา: **{query}**\n\n"
            + "\n".join(lines)
            + "\n\nเลือกเพลงจากเมนู Dropdown ด้านล่าง (เลือกได้หลายเพลง)"
        )
        return self._music_embed(
            guild,
            "เลือกเพลงก่อนเล่น",
            description,
            tone="info",
            footer=f"หมดเวลา {self.PENDING_PICK_TTL_SECONDS} วิ",
        )

    def _track_pick_select_options(self, tracks: list) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        for index, track in enumerate(tracks[: self.SEARCH_PICK_LIMIT], start=1):
            title = self._truncate_track_text(getattr(track, "title", "Unknown"), 80)
            author = self._truncate_track_text(getattr(track, "author", "Unknown"), 45)
            length = convert_ms_to_beautiful_time(getattr(track, "length", 0) or 0)
            options.append(
                discord.SelectOption(
                    label=f"#{index} {title}"[:100],
                    value=str(index - 1),
                    description=f"{author} • {length}"[:100],
                    emoji="🎵",
                )
            )
        return options

    def _build_track_pick_view(
        self,
        *,
        guild_id: int,
        channel_id: int,
        user_id: int,
        timeout: float,
    ) -> discord.ui.View | None:
        pending_pick = self._peek_track_pick(guild_id, channel_id, user_id)
        pending_tracks = list((pending_pick or {}).get("tracks") or [])
        options = self._track_pick_select_options(pending_tracks)
        if not options:
            return None

        view = discord.ui.View(timeout=timeout)
        pick_select = discord.ui.Select(
            placeholder="เลือกเพลงที่ต้องการเพิ่ม (เลือกได้หลายเพลง)"[:100],
            min_values=1,
            max_values=min(len(options), 25),
            options=options,
        )

        async def pick_select_callback(interaction: discord.Interaction):
            try:
                if int(interaction.user.id) != int(user_id):
                    return await interaction.response.send_message(
                        "เมนูนี้ใช้ได้เฉพาะคนที่ค้นหาเพลงเท่านั้น",
                        ephemeral=True,
                        delete_after=6,
                    )

                current_pending = self._peek_track_pick(guild_id, channel_id, user_id)
                if not current_pending:
                    return await interaction.response.send_message(
                        "หมดเวลาแล้ว ค้นหาเพลงใหม่อีกครั้ง",
                        ephemeral=True,
                        delete_after=6,
                    )

                guild = interaction.guild
                channel = interaction.channel
                if not guild:
                    self._pop_track_pick(guild_id, channel_id, user_id)
                    return await interaction.response.send_message(
                        "ไม่พบข้อมูลกิลด์",
                        ephemeral=True,
                        delete_after=6,
                    )
                if not channel:
                    self._pop_track_pick(guild_id, channel_id, user_id)
                    return await interaction.response.send_message(
                        "ไม่พบข้อมูลกิลด์",
                        ephemeral=True,
                        delete_after=6,
                    )

                vc: wavelink.Player | None = getattr(guild, "voice_client", None)
                if not vc or not getattr(vc, "connected", False):
                    await self._pop_track_pick_with_cleanup(guild_id, channel, user_id)
                    return await interaction.response.send_message(
                        f"{self.bot.emoji.ERROR} | บอทยังไม่อยู่ห้องเสียง",
                        ephemeral=True,
                        delete_after=6,
                    )

                required_voice_channel_id = self._as_int(
                    current_pending.get("required_voice_channel_id")
                )
                user_voice_channel_id = self._as_int(
                    getattr(
                        getattr(
                            getattr(interaction.user, "voice", None),
                            "channel",
                            None,
                        ),
                        "id",
                        None,
                    )
                )
                if required_voice_channel_id and user_voice_channel_id != required_voice_channel_id:
                    await self._clear_pending_track_picks_for_user(
                        guild_id,
                        user_id,
                        reason=f"{self.bot.emoji.ERROR} | ยกเลิกรายการเลือกเพลง (คุณไม่ได้อยู่ห้องเดียวกับบอท)",
                    )
                    return await interaction.response.send_message(
                        "คุณต้องอยู่ห้องเดียวกับบอทก่อนจึงจะเลือกเพลงได้",
                        ephemeral=True,
                        delete_after=6,
                    )

                values = list((interaction.data or {}).get("values") or [])
                pending_tracks = list(current_pending.get("tracks") or [])
                picked_indexes: list[int] = []
                seen_indexes: set[int] = set()
                for raw_value in values:
                    try:
                        parsed_index = int(raw_value)
                    except (TypeError, ValueError):
                        continue
                    if parsed_index < 0 or parsed_index >= len(pending_tracks):
                        continue
                    if parsed_index in seen_indexes:
                        continue
                    seen_indexes.add(parsed_index)
                    picked_indexes.append(parsed_index)

                if not picked_indexes:
                    return await interaction.response.send_message(
                        "เลือกเพลงไม่ถูกต้อง",
                        ephemeral=True,
                        delete_after=6,
                    )

                if not await self._safe_defer_interaction(interaction):
                    return

                await self._pop_track_pick_with_cleanup(guild_id, channel, user_id)

                selected_tracks = [pending_tracks[index] for index in picked_indexes]
                guilds_subscription = self.bot.cache.guilds.get(str(guild_id), {}).get(
                    "subscription",
                    "free",
                )
                default_volume = (
                    80
                    if guilds_subscription == "free"
                    else self.bot.cache.music.get(str(guild_id), {}).get("default_volume", 80)
                )
                changed_titles, skipped_count = await self._apply_tracks_to_player(
                    vc=vc,
                    tracks=selected_tracks,
                    requester=interaction.user,
                    default_volume=default_volume,
                )
                if not changed_titles:
                    return await interaction.followup.send(
                        f"{self.bot.emoji.ERROR} | {self._queue_full_message_for_guild(guild_id)}",
                        ephemeral=True,
                        delete_after=8,
                    )

                await self.send_music_controls(
                    guild,
                    update_attachments=True,
                    command_channel=channel,
                )
                summary = (
                    f"{self.bot.emoji.SUCCESS} | เพิ่มเพลงแล้ว {len(changed_titles)} เพลง"
                    if len(changed_titles) > 1
                    else f"{self.bot.emoji.SUCCESS} | เพิ่มเพลงแล้ว: {changed_titles[0]}"
                )
                if skipped_count:
                    summary += f" (ข้าม {skipped_count} เพลง เพราะคิวเต็ม)"
                unselected_count = max(0, len(pending_tracks) - len(picked_indexes))
                if unselected_count:
                    summary += f" (ยังไม่ได้เลือก {unselected_count} เพลง)"
                await interaction.followup.send(
                    summary,
                    ephemeral=True,
                    delete_after=10,
                )
            except Exception:
                logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

        pick_select.callback = pick_select_callback
        view.add_item(pick_select)
        return view

    async def _send_track_pick_prompt(
        self,
        *,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        guild_id: int,
        user_id: int,
        query: str,
        tracks: list,
        gate_message_id: int | None = None,
        required_voice_channel_id: int | None = None,
    ) -> None:
        # Remember first so the dropdown callback can always read the pending payload.
        self._remember_track_pick(
            guild_id,
            channel.id,
            user_id,
            query=query,
            tracks=tracks,
            mode="await_pick",
            gate_message_id=gate_message_id,
            required_voice_channel_id=required_voice_channel_id,
        )
        view = self._build_track_pick_view(
            guild_id=guild_id,
            channel_id=channel.id,
            user_id=user_id,
            timeout=float(self.PENDING_PICK_TTL_SECONDS),
        )
        send_kwargs = {
            "embed": self._build_track_pick_embed(guild, query, tracks),
            "delete_after": self.PENDING_PICK_TTL_SECONDS,
        }
        if view is not None:
            send_kwargs["view"] = view
        prompt = await channel.send(**send_kwargs)
        self._remember_track_pick(
            guild_id,
            channel.id,
            user_id,
            query=query,
            tracks=tracks,
            mode="await_pick",
            prompt_message_id=getattr(prompt, "id", None),
            gate_message_id=gate_message_id,
            required_voice_channel_id=required_voice_channel_id,
        )

    def _parse_pick_input(self, raw: str, max_index: int) -> tuple[list[int] | None, str | None]:
        text = (raw or "").strip().lower()
        if not text:
            return None, "empty"
        if text in {"cancel", "ยกเลิก", "c"}:
            return [], None
        if not re.fullmatch(r"[0-9,\s\-]+", text):
            return None, "not_selection"
        picks: list[int] = []
        seen = set()
        for token in [part for part in re.split(r"[\s,]+", text) if part]:
            if "-" in token:
                left, right = token.split("-", 1)
                if not left.isdigit() or not right.isdigit():
                    return None, "format"
                start, end = int(left), int(right)
                if start < 1 or end < 1:
                    return None, "range"
                step = 1 if end >= start else -1
                for value in range(start, end + step, step):
                    if value > max_index:
                        return None, "out_of_range"
                    if value not in seen:
                        seen.add(value)
                        picks.append(value)
            else:
                if not token.isdigit():
                    return None, "format"
                value = int(token)
                if value < 1 or value > max_index:
                    return None, "out_of_range"
                if value not in seen:
                    seen.add(value)
                    picks.append(value)
        if not picks:
            return None, "empty"
        return picks, None

    def _music_queue_limit_for_guild(self, guild_id: int | None) -> int:
        if not guild_id:
            return 15
        subscription = str(
            self.bot.cache.guilds.get(str(guild_id), {}).get("subscription", "free")
            or "free"
        ).strip().lower()
        if subscription in {"diamond_guild_premium", "permanent_guild_premium", "lifetime_guild_premium"}:
            return 99
        if subscription == "golden_guild_premium":
            return 60
        if subscription in {"silver_guild_preminum", "silver_guild_premium"}:
            return 30
        return 15

    def _queue_full_message_for_guild(self, guild_id: int | None) -> str:
        queue_limit = self._music_queue_limit_for_guild(guild_id)
        return f"คิวเต็มแล้ว (เพิ่มได้สูงสุด {queue_limit} เพลง)"

    def _music_playlist_limits_for_guild(self, guild_id: int | None) -> tuple[int, int]:
        subscription = "free"
        if guild_id:
            subscription = str(
                self.bot.cache.guilds.get(str(guild_id), {}).get("subscription", "free")
                or "free"
            ).strip().lower()

        plan_tier = "free"
        if subscription in {"permanent_guild_premium", "lifetime_guild_premium"}:
            plan_tier = "permanent"
        elif subscription in {"diamond_guild_premium"}:
            plan_tier = "diamond"
        elif subscription in {"golden_guild_premium", "gole_guild_premium"}:
            plan_tier = "golden"
        elif subscription in {"silver_guild_preminum", "silver_guild_premium"}:
            plan_tier = "silver"

        playlist_limits: dict[str, tuple[int, int]] = {
            "free": (5, 25),
            "silver": (10, 35),
            "golden": (15, 45),
            "diamond": (20, 50),
            "permanent": (25, 50),
        }
        max_playlists, max_items = playlist_limits.get(plan_tier, playlist_limits["free"])
        return (
            max(1, min(int(max_playlists), int(self.USER_PLAYLIST_LIMIT))),
            max(1, min(int(max_items), int(self.USER_PLAYLIST_ITEM_LIMIT))),
        )

    async def _user_playlist_quota_text(self, user_id: int, guild_id: int | None = None) -> str:
        playlists = await user_music_playlists.list_user_playlists(int(user_id))
        max_playlists, _ = self._music_playlist_limits_for_guild(guild_id)
        used = len(playlists)
        remain = max(0, max_playlists - used)
        return f"Playlist quota: {used}/{max_playlists} (remaining {remain})"

    def _playlist_entry_line(self, entry: dict, index: int) -> str:
        value = self._truncate_track_text(str(entry.get("value") or "Unknown"), 90)
        kind = str(entry.get("kind") or "query").strip().lower()
        icon = "🔗" if kind == "url" else "🎵"
        return f"`{index:>2}` {icon} {value}"

    async def _resolve_playlist_entries_to_tracks(
        self,
        entries: list[dict[str, object]],
        *,
        max_tracks: int = 120,
    ) -> tuple[list[wavelink.Playable], list[str]]:
        resolved: list[wavelink.Playable] = []
        skipped: list[str] = []
        for entry in list(entries or []):
            value = str(entry.get("value") or "").strip()
            if not value:
                continue
            entry_kind = str(entry.get("kind") or "query").strip().lower()
            result = await self._search_tracks(value)
            if not result:
                skipped.append(value)
                continue

            picked_tracks: list[wavelink.Playable] = []
            if entry_kind == "url" and "list=" in value.lower():
                picked_tracks = list(result[:25])
            else:
                picked_tracks = [result[0]]

            for track in picked_tracks:
                resolved.append(track)
                if len(resolved) >= max_tracks:
                    return resolved, skipped

        return resolved, skipped

    async def _connect_voice_for_ctx(
        self, ctx: commands.Context
    ) -> wavelink.Player | None:
        if not getattr(ctx.author, "voice", None) or not getattr(
            ctx.author.voice, "channel", None
        ):
            await ctx.reply(
                f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                delete_after=8,
            )
            return None

        destination = ctx.author.voice.channel
        if not ctx.guild.voice_client:
            vc = await self._connect_with_node_retry(destination, timeout=60)
            self._apply_inactive_timeout(vc, ctx.guild.id)
        else:
            vc = ctx.guild.voice_client
            self._apply_inactive_timeout(vc, ctx.guild.id)
            if vc.channel.id != destination.id:
                if not self._has_active_voice_session(vc):
                    await vc.move_to(destination)
                else:
                    await ctx.reply(
                        self._voice_busy_wait_message(vc),
                        delete_after=12,
                    )
                    return None

        if ctx.author.voice.channel.id != vc.channel.id:
            await ctx.reply(
                f"{self.bot.emoji.ERROR} | คุณต้องอยู่ห้องเสียงเดียวกับบอท",
                delete_after=8,
            )
            return None
        return vc

    async def _playlist_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[discord.app_commands.Choice[str]]:
        try:
            user = getattr(interaction, "user", None)
            user_id = int(getattr(user, "id", 0) or 0)
            if user_id <= 0:
                return []
            guild_id = int(getattr(getattr(interaction, "guild", None), "id", 0) or 0)
            _max_playlists, max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)

            rows = await user_music_playlists.list_user_playlists(user_id)
            lookup = str(current or "").strip().casefold()
            choices: list[discord.app_commands.Choice[str]] = []
            for row in list(rows or []):
                name = str(row.get("name") or "").strip()
                slug = str(row.get("slug") or "").strip()
                if not slug and not name:
                    continue
                if lookup:
                    joined = f"{name} {slug}".casefold()
                    if lookup not in joined:
                        continue
                item_count = len(list(row.get("items") or []))
                label = (
                    f"{name or slug} "
                    f"({item_count}/{max_items_per_playlist})"
                ).strip()
                value = (slug or name or "playlist").strip()
                if not value:
                    continue
                choices.append(
                    discord.app_commands.Choice(
                        name=label[:100],
                        value=value[:100],
                    )
                )
                if len(choices) >= 25:
                    break
            return choices
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")
            return []

    async def _apply_tracks_to_player(
        self,
        *,
        vc: wavelink.Player,
        tracks: list,
        requester,
        default_volume: int,
    ) -> tuple[list[str], int]:
        played_or_added: list[str] = []
        skipped = 0
        guild_id = self._as_int(getattr(getattr(vc, "guild", None), "id", None))
        queue_limit = self._music_queue_limit_for_guild(guild_id)
        for track in tracks:
            try:
                track.requester = requester
            except Exception:
                pass
            if not getattr(vc, "current", None) and not played_or_added:
                await vc.play(track, volume=max(0, min(100, int(default_volume or 80))))
                played_or_added.append(getattr(track, "title", "Unknown"))
                continue
            if len(vc.queue) >= queue_limit:
                skipped += 1
                continue
            await vc.queue.put_wait(track)
            played_or_added.append(getattr(track, "title", "Unknown"))
        return played_or_added, skipped

    async def _search_tracks(self, query: str) -> list[wavelink.Playable]:
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            return []

        # Try source-aware search first, then fallback to direct resolver.
        # URL queries benefit from direct resolver while text queries benefit
        # from explicit YouTube-first ordering.
        attempts: list[tuple[str, dict[str, object]]] = []
        if is_link(cleaned_query):
            attempts.append(("direct", {}))
            attempts.append(("youtube", {"source": wavelink.TrackSource.YouTube}))
        else:
            attempts.append(("youtube", {"source": wavelink.TrackSource.YouTube}))
            attempts.append(("direct", {}))

        for mode, kwargs in attempts:
            try:
                result = await wavelink.Playable.search(cleaned_query, **kwargs)
            except Exception as search_error:
                logger.warning(
                    f"[music_search] search failed | mode={mode} query={cleaned_query!r} "
                    f"| error={type(search_error).__name__}: {search_error}"
                )
                continue
            if result:
                return result
        return []

    async def _seek_relative(self, vc: wavelink.Player, delta_ms: int) -> int:
        track = getattr(vc, "current", None)
        if not track:
            raise RuntimeError("No active track")
        length_ms = max(int(getattr(track, "length", 0) or 0), 0)
        current_ms = max(int(getattr(vc, "position", 0) or 0), 0)
        next_ms = max(0, current_ms + int(delta_ms))
        if length_ms > 0:
            next_ms = min(next_ms, max(0, length_ms - 1500))
        await vc.seek(next_ms)
        return next_ms

    def _parse_seek_input(self, value: str) -> int | None:
        text = (value or "").strip()
        if not text:
            return None
        if re.fullmatch(r"[+-]?\d+", text):
            return int(text) * 1000
        if ":" in text:
            parts = text.split(":")
            if not all(part.isdigit() for part in parts):
                return None
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                return (minutes * 60 + seconds) * 1000
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return (hours * 3600 + minutes * 60 + seconds) * 1000
        return None

    async def _voice_presence_loop(self):
        await self.bot.wait_until_ready()
        # Initial delay so we don't race against in-flight connect() calls.
        await asyncio.sleep(30)
        while not self.bot.is_closed():
            try:
                for guild_id, music_data in list(self.bot.cache.music.items()):
                    voice_channel_id = self._as_int(
                        music_data.get("music_setup_voice_channel_id")
                    )
                    if not voice_channel_id:
                        continue
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue
                    if guild.id in self._voice_connecting_guilds and self._connect_lock_stale(guild.id):
                        self._clear_connecting(guild.id)
                    if guild.id in self._voice_connecting_guilds:
                        continue
                    vc: wavelink.Player | None = guild.voice_client
                    if vc and not getattr(vc, "connected", False):
                        try:
                            await vc.disconnect()
                        except Exception:
                            pass
                        vc = None
                    if vc is None:
                        continue

                    # Auto-leave only when there are no human listeners.
                    # Idle disconnects are handled by wavelink inactive_timeout.
                    listeners = [m for m in (vc.channel.members if vc.channel else []) if not m.bot]
                    if not listeners:
                        try:
                            await vc.disconnect()
                        except Exception:
                            pass
                        await self.send_music_controls(guild, end=True)
            except Exception:
                logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")
            await asyncio.sleep(30)

    async def _pending_pick_cleanup_loop(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)
        while not self.bot.is_closed():
            try:
                await self._prune_stale_track_picks()
            except Exception:
                logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")
            await asyncio.sleep(15)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        try:
            player = getattr(payload, "player", None)
            guild = getattr(getattr(player, "guild", None), "id", None)
            if not player or not player.guild:
                return
            await self.send_music_controls(
                player.guild,
                update_attachments=True,
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        try:
            player = getattr(payload, "player", None)
            if not player or not player.guild:
                return
            # Give player state a brief moment to settle. Another listener may
            # already move to the next track before this callback runs.
            await asyncio.sleep(0.25)

            vc: wavelink.Player | None = player.guild.voice_client
            if not vc:
                await self.send_music_controls(player.guild, end=True)
                return

            if getattr(vc, "current", None):
                await self.send_music_controls(
                    player.guild,
                    update_attachments=True,
                )
                return

            has_next = bool(vc.queue) or vc.autoplay != wavelink.AutoPlayMode.disabled
            if has_next:
                # Transitional gap between tracks: wait for track_start/player_update
                # to render the next track instead of flashing idle state.
                return

            await self.send_music_controls(player.guild, end=True)
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    def _as_int(self, value):
        try:
            if value in (None, "", "None"):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def t(self, guild_id: int | None, key: str, **kwargs):
        return i18n.tr(key, guild_id=guild_id, **kwargs)

    def _theme_color(self, tone: str = "info"):
        palette = {
            "info": getattr(color, "blue", discord.Color.blurple()),
            "success": getattr(color, "green", discord.Color.green()),
            "warning": getattr(color, "yellow", discord.Color.gold()),
            "danger": getattr(color, "red", discord.Color.red()),
            "accent": getattr(color, "purple", discord.Color.purple()),
        }
        return palette.get(tone, palette["info"])

    def _music_embed(
        self,
        guild: discord.Guild | None,
        title: str,
        description: str,
        tone: str = "info",
        footer: str | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=self._theme_color(tone),
            timestamp=discord.utils.utcnow(),
        )
        if guild is not None:
            embed.set_author(
                name=guild.name,
                icon_url=(guild.icon.url if guild.icon else self.bot.user.display_avatar.url),
            )
        embed.set_footer(
            text=footer or "SkylineBOT Music",
            icon_url=self.bot.user.display_avatar.url,
        )
        return embed

    @commands.hybrid_command(
        name="play",
        aliases=["p"],
        help="เล่นเพลงในห้องเสียง",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def play(self, ctx: commands.Context, *, search: str):

        try:
            if not await self._ensure_music_access_ctx(ctx):
                return

            if ctx.interaction:

                await self._safe_ctx_defer(ctx)

            search = str(search or "").strip()
            if not self._is_meaningful_music_query(search):
                return await ctx.reply(
                    f"{self.bot.emoji.ERROR} | กรุณาใส่คำค้นหาเพลงที่ชัดเจน",
                    delete_after=8,
                )

            music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

            if music_data:

                if music_data.get("music_setup_channel_id", None) and music_data.get("music_setup_voice_channel_id", None):

                    # send to use the setuped channel to play music

                    embed = discord.Embed(
                        description=f"Send anything in the channel <#{music_data.get('music_setup_channel_id',None)}> to play music.",
                        color=color.red,
                    )

                    embed.set_author(
                        name=ctx.guild.name,
                        icon_url=(
                            ctx.guild.icon.url
                            if ctx.guild.icon
                            else self.bot.user.display_avatar.url
                        ),
                        url=self.bot.urls.WEBSITE,
                    )

                    embed.set_footer(
                        text=f"Use /resetmusic to reset the setup of music"
                    )

                    return await ctx.reply(embed=embed)

            # Check if the user is in a voice channel

            if not ctx.author.voice:

                await ctx.reply(
                    "คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้"
                )

                return

            try:

                # Check if the user is in a voice channel

                if not ctx.author.voice:

                    return await ctx.reply(
                        f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                        delete_after=10,
                    )

                destination = ctx.author.voice.channel

                # Connect to the voice channel if not already connected

                if not ctx.guild.voice_client:

                    vc: wavelink.Player = await self._connect_with_node_retry(
                        destination, timeout=60
                    )

                    self._apply_inactive_timeout(vc, ctx.guild.id)

                else:

                    vc: wavelink.Player = ctx.guild.voice_client

                    self._apply_inactive_timeout(vc, ctx.guild.id)

                    # if the bot is another vc and not playing anything then move to the new vc

                    if vc.channel.id != destination.id:

                        if not self._has_active_voice_session(vc):

                            await vc.move_to(destination)

                        else:

                            return await ctx.reply(
                                self._voice_busy_wait_message(vc),
                                delete_after=14,
                            )

                if ctx.author.voice.channel.id != vc.channel.id:

                    return await ctx.reply(
                        f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                        delete_after=10,
                    )

                users_no_prefix_subscription = self.bot.cache.users.get(
                    str(ctx.author.id), {}
                ).get("no_prefix_subscription", None)

                guilds_subscription = self.bot.cache.guilds.get(
                    str(ctx.guild.id), {}
                ).get("subscription", "free")

                if not users_no_prefix_subscription and guilds_subscription == "free":

                    if is_link(search):

                        return await ctx.reply(
                            embed=discord.Embed(
                                description="แพ็กเกจฟรียังไม่รองรับการเล่นเพลงผ่านลิงก์",
                                color=color.red,
                            ),
                            view=discord.ui.View().add_item(
                                discord.ui.Button(
                                    label="อัปเกรดพรีเมียม",
                                    style=discord.ButtonStyle.url,
                                    url=self.bot.urls.SUPPORT_SERVER,
                                    emoji=self.bot.emoji.SUPPORT,
                                )
                            ),
                        )

                result = await self._search_tracks(search)

                if not result:

                    return await ctx.reply(
                        f"{self.bot.emoji.ERROR} | ไม่พบเพลงที่ค้นหา ลองพิมพ์ชื่อเต็มขึ้น หรือส่งลิงก์เพลงโดยตรง",
                        delete_after=12,
                    )

                if guilds_subscription == "free":

                    default_volume = 80

                else:

                    default_volume = self.bot.cache.music.get(
                        str(ctx.guild.id), {}
                    ).get("default_volume", 80)

                if len(result) > 1 and not is_link(search):
                    candidates = list(result[: self.SEARCH_PICK_LIMIT])
                    required_voice_channel_id = self._as_int(
                        getattr(getattr(vc, "channel", None), "id", None)
                    )
                    track = candidates[0]
                    changed_titles, skipped_count = await self._apply_tracks_to_player(
                        vc=vc,
                        tracks=[track],
                        requester=ctx.author,
                        default_volume=default_volume,
                    )
                    if not changed_titles:
                        return await ctx.reply(
                            f"{self.bot.emoji.LIMIT} | {self._queue_full_message_for_guild(ctx.guild.id)}",
                            delete_after=10,
                        )

                    await self.send_music_controls(
                        ctx.guild,
                        update_attachments=True,
                        command_channel=ctx.channel,
                    )

                    result_msg = f"{self.bot.emoji.SUCCESS} | เพิ่มเพลงแล้ว: {changed_titles[0]}"
                    if skipped_count:
                        result_msg += f" (ข้าม {skipped_count} เพลง เพราะคิวเต็ม)"
                    await ctx.reply(result_msg)

                    top_track = candidates[0]
                    top_title = self._truncate_track_text(getattr(top_track, "title", "Unknown"), 70)
                    top_author = self._truncate_track_text(getattr(top_track, "author", "Unknown"), 40)
                    top_length = convert_ms_to_beautiful_time(getattr(top_track, "length", 0) or 0)
                    gate_embed = self._music_embed(
                        ctx.guild,
                        "พบผลลัพธ์หลายเพลง",
                        (
                            f"คำค้นหา: **{search}**\n"
                            f"เพลงแนะนำอันดับแรก: **{top_title}** • {top_author} • `{top_length}`\n\n"
                            "กำลังเล่นเพลงแนะนำให้แล้ว ถ้าเพลงนี้ไม่ตรงกับที่ต้องการ ให้กดปุ่มด้านล่างเพื่อเปิดรายการเลือกเพลง"
                        ),
                        tone="info",
                        footer=f"หมดเวลา {self.PENDING_PICK_TTL_SECONDS} วิ",
                    )
                    gate_view = discord.ui.View(timeout=self.PENDING_PICK_TTL_SECONDS)
                    open_picker_button = discord.ui.Button(
                        label="เพลงไม่ตรงกับที่ต้องการ",
                        style=discord.ButtonStyle.secondary,
                        emoji="🎯",
                    )

                    async def open_picker_callback(interaction: discord.Interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message(
                                "ปุ่มนี้ใช้ได้เฉพาะคนที่พิมพ์ค้นหาเพลงเท่านั้น",
                                ephemeral=True,
                                delete_after=6,
                            )

                        current_pending = self._peek_track_pick(
                            ctx.guild.id, ctx.channel.id, ctx.author.id
                        )
                        if not current_pending:
                            return await interaction.response.send_message(
                                "หมดเวลาแล้ว พิมพ์ /play ใหม่",
                                ephemeral=True,
                                delete_after=5,
                            )

                        await interaction.response.defer()

                        await self._send_track_pick_prompt(
                            guild=ctx.guild,
                            channel=ctx.channel,
                            guild_id=ctx.guild.id,
                            user_id=ctx.author.id,
                            query=search,
                            tracks=candidates,
                            gate_message_id=getattr(interaction.message, "id", None),
                            required_voice_channel_id=required_voice_channel_id,
                        )
                        try:
                            await interaction.message.delete()
                        except Exception:
                            pass

                    open_picker_button.callback = open_picker_callback
                    gate_view.add_item(open_picker_button)

                    gate_message = await ctx.channel.send(
                        embed=gate_embed,
                        view=gate_view,
                        delete_after=self.PENDING_PICK_TTL_SECONDS,
                    )
                    self._remember_track_pick(
                        ctx.guild.id,
                        ctx.channel.id,
                        ctx.author.id,
                        query=search,
                        tracks=candidates,
                        mode="await_button",
                        gate_message_id=gate_message.id,
                        required_voice_channel_id=required_voice_channel_id,
                    )
                    return

                tracks_to_apply = (
                    list(result) if is_link(search) and len(result) > 1 else [result[0]]
                )
                changed_titles, skipped_count = await self._apply_tracks_to_player(
                    vc=vc,
                    tracks=tracks_to_apply,
                    requester=ctx.author,
                    default_volume=default_volume,
                )
                if not changed_titles:
                    return await ctx.reply(
                        f"{self.bot.emoji.LIMIT} | {self._queue_full_message_for_guild(ctx.guild.id)}",
                        delete_after=10,
                    )

                await self.send_music_controls(
                    ctx.guild,
                    update_attachments=True,
                    command_channel=ctx.channel,
                )

                first_title = changed_titles[0]
                if len(tracks_to_apply) > 1:
                    result_msg = (
                        f"{self.bot.emoji.CREATE} | Added playlist to queue: "
                        f"{len(changed_titles)} track(s)"
                    )
                elif vc.current and getattr(vc.current, "title", None) == first_title:
                    result_msg = f"{self.bot.emoji.PLAYING} | กำลังเล่น: {first_title}"
                else:
                    result_msg = f"{self.bot.emoji.CREATE} | เพิ่มเข้าคิวแล้ว: {first_title}"

                if skipped_count:
                    result_msg += f" (ข้าม {skipped_count} เพลง เพราะคิวเต็ม)"
                await ctx.reply(result_msg)

            except (TimeoutError, CHANNEL_TIMEOUT_EXCEPTION):

                return await ctx.reply(
                    embed=discord.Embed(
                        description="บอทใช้เวลานานเกินไปในการเข้าห้องเสียง\nกรุณาลองใหม่อีกครั้งหลังเปลี่ยน Region ห้องเสียง",
                        color=color.red,
                    ),
                    delete_after=10,
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    music_controller_view_timeout_data = {}  # {guild_id: datetime.datetime}

    async def _validate_controller_interaction(self, interaction: discord.Interaction):
        if not await self._ensure_music_access_interaction(interaction):
            return None

        vc: wavelink.Player = interaction.guild.voice_client

        if not vc:

            await interaction.response.send_message(
                embed=discord.Embed(
                    description="ตัวเล่นเพลงออฟไลน์อยู่ตอนนี้", color=color.red
                ),
                ephemeral=True,
                delete_after=8,
            )

            return None

        if not interaction.user.voice:

            await interaction.response.send_message(
                embed=discord.Embed(
                    description="เข้าห้องเสียงก่อนจึงจะใช้แผงควบคุมนี้ได้",
                    color=color.red,
                ),
                ephemeral=True,
                delete_after=8,
            )

            return None

        if vc.channel != interaction.user.voice.channel:

            await interaction.response.send_message(
                embed=discord.Embed(
                    description="คุณต้องอยู่ห้องเสียงเดียวกับ SkylineBOT",
                    color=color.red,
                ),
                ephemeral=True,
                delete_after=8,
            )

            return None

        last_used = self.music_controller_view_timeout_data.get(interaction.guild.id)

        if last_used and datetime.datetime.now() - last_used < datetime.timedelta(
            seconds=self.CONTROLLER_COOLDOWN_SECONDS
        ):

            await interaction.response.send_message(
                embed=discord.Embed(
                    description="กำลังรีเฟรชแผงควบคุม โปรดลองอีกครั้งในอีกสักครู่",
                    color=color.red,
                ),
                ephemeral=True,
                delete_after=4,
            )

            return None

        self.music_controller_view_timeout_data[interaction.guild.id] = (
            datetime.datetime.now()
        )

        return vc

    async def _send_controller_toast(
        self, interaction: discord.Interaction, message: str
    ):

        try:

            await interaction.followup.send(message, ephemeral=True)

        except Exception:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def _safe_defer_interaction(self, interaction: discord.Interaction) -> bool:

        try:

            if interaction.response.is_done():

                return True

            await interaction.response.defer()

            return True

        except (discord.NotFound, discord.HTTPException):

            return False

    def _truncate_track_text(self, text: str, limit: int) -> str:

        if not text:

            return "Unknown"

        return text if len(text) <= limit else f"{text[:limit - 3]}..."

    def _is_meaningful_music_query(self, query: str) -> bool:
        text = str(query or "").strip()
        if not text:
            return False
        # Reject symbol-only inputs such as "|" or "..." which often map to noisy results.
        return bool(re.search(r"[A-Za-z0-9\u0E00-\u0E7F]", text))

    def _is_command_like_message(self, content: str) -> bool:
        text = str(content or "").strip()
        if not text:
            return False

        raw_prefix = getattr(getattr(self.bot, "BotConfig", None), "PREFIX", None)
        prefixes: list[str] = []
        if isinstance(raw_prefix, str) and raw_prefix.strip():
            prefixes.append(raw_prefix.strip())
        elif isinstance(raw_prefix, (list, tuple, set)):
            for item in list(raw_prefix):
                part = str(item or "").strip()
                if part:
                    prefixes.append(part)
        if not prefixes:
            prefixes.append("!")

        bot_user = getattr(self.bot, "user", None)
        if bot_user is not None:
            mention_id = int(getattr(bot_user, "id", 0) or 0)
            if mention_id > 0:
                prefixes.append(f"<@{mention_id}>")
                prefixes.append(f"<@!{mention_id}>")

        lowered = text.lower()
        if lowered.startswith("/"):
            return True
        return any(text.startswith(prefix) for prefix in prefixes)

    def _resolve_track_requester(self, track) -> str | None:
        if not track:
            return None
        for attr in ("requester", "_requester", "requester_mention"):
            value = getattr(track, attr, None)
            if isinstance(value, str) and value:
                return value
            if value is not None and not isinstance(value, str):
                # discord.Member/User
                mention = getattr(value, "mention", None)
                if mention:
                    return mention
                name = getattr(value, "display_name", None) or getattr(value, "name", None)
                if name:
                    return name
        extras = getattr(track, "extras", None)
        if extras is not None:
            for attr in ("requester", "requester_mention"):
                try:
                    value = getattr(extras, attr, None)
                except Exception:
                    value = None
                if isinstance(value, str) and value:
                    return value
        return None

    def _build_track_info_block(self, player: wavelink.Player | None) -> str:
        if not player or not player.current:
            return ""
        track = player.current
        guild_id = getattr(getattr(player, "guild", None), "id", None)

        author = self._truncate_track_text(getattr(track, "author", None) or "Unknown", 60)
        current_position_ms = max(int(getattr(player, "position", 0) or 0), 0)
        total_length_ms = max(int(getattr(track, "length", 0) or 0), 0)
        safe_position_ms = (
            min(current_position_ms, total_length_ms) if total_length_ms > 0 else current_position_ms
        )
        duration = (
            convert_ms_to_beautiful_time(total_length_ms) if total_length_ms > 0 else "LIVE"
        )
        position = convert_ms_to_beautiful_time(safe_position_ms)
        remaining_ms = max(total_length_ms - safe_position_ms, 0) if total_length_ms > 0 else 0
        remaining_display = (
            convert_ms_to_beautiful_time(remaining_ms) if total_length_ms > 0 else "ไม่ทราบ"
        )
        progress_percent = (
            f"{int((safe_position_ms / total_length_ms) * 100)}%"
            if total_length_ms > 0
            else "LIVE"
        )
        progress_bar = self._build_progress_bar(safe_position_ms, total_length_ms)
        source = (getattr(track, "source", None) or "unknown").lower()
        requester = self._resolve_track_requester(track) or "—"
        queue_size = len(self._queue_items(player))
        autoplay_label = (
            "เปิด"
            if getattr(player, "autoplay", wavelink.AutoPlayMode.disabled)
            != wavelink.AutoPlayMode.disabled
            else "ปิด"
        )

        loop_mode = getattr(getattr(player, "queue", None), "mode", None)
        if loop_mode == wavelink.QueueMode.loop:
            loop_label = self.t(guild_id, "music_info_loop_track")
        elif loop_mode == wavelink.QueueMode.loop_all:
            loop_label = self.t(guild_id, "music_info_loop_queue")
        else:
            loop_label = self.t(guild_id, "music_info_loop_none")

        if player.paused:
            status_emoji = "⏸️"
            status_text = self.t(guild_id, "music_status_paused")
        else:
            status_emoji = "🟢"
            status_text = self.t(guild_id, "music_status_playing")

        try:
            seekable_attr = getattr(track, "is_seekable", None)
            if seekable_attr is None:
                seekable_attr = getattr(track, "seekable", True)
        except Exception:
            seekable_attr = True
        seekable_label = (
            self.t(guild_id, "music_info_seekable_yes")
            if seekable_attr
            else self.t(guild_id, "music_info_seekable_no")
        )

        lines: list[str] = []
        lines.append(
            f"🎤 **{self.t(guild_id, 'music_info_artist')}:** {author}  •  "
            f"**{self.t(guild_id, 'music_info_duration')}:** `{position} / {duration}`"
        )
        lines.append(f"`{progress_bar}`")
        lines.append(
            f"⏱️ **เวลาเล่น:** `{position}` • **เวลาเพลง:** `{duration}` • **เวลาคงเหลือ:** `{remaining_display}`"
        )
        lines.append(f"📈 **ความคืบหน้า:** `{progress_percent}`")
        lines.append(
            f"🌐 **{self.t(guild_id, 'music_info_source')}:** {source}  •  "
            f"**{self.t(guild_id, 'music_info_quality')}:** {self.t(guild_id, 'music_info_quality_hd')}"
        )
        lines.append(f"🙋 **{self.t(guild_id, 'music_info_requested_by')}:** {requester}")
        lines.append("")
        lines.append(
            f"📍 **{self.t(guild_id, 'music_info_queue_position')}:** "
            f"{self.t(guild_id, 'music_info_now_playing')}"
        )
        lines.append(
            f"🔊 **{self.t(guild_id, 'music_info_volume')}:** {getattr(player, 'volume', 0)}%"
        )
        lines.append(f"🔁 **{self.t(guild_id, 'music_info_loop')}:** {loop_label}")
        lines.append(
            f"📶 **{self.t(guild_id, 'music_info_status')}:** {status_emoji} {status_text}"
        )
        lines.append(f"🧾 **เพลงในคิว:** `{queue_size}` • **AutoPlay:** `{autoplay_label}`")
        lines.append("")
        lines.append(f"📊 **{self.t(guild_id, 'music_info_track_stats')}**")
        lines.append(
            f"**{self.t(guild_id, 'music_info_bitrate')}:** "
            f"{self.t(guild_id, 'music_info_bitrate_hq')}"
        )
        lines.append(
            f"**{self.t(guild_id, 'music_info_seekable')}:** {seekable_label}  •  "
            f"**{self.t(guild_id, 'music_info_platform')}:** {source}"
        )
        return "\n".join(lines)

    def _build_queue_summary(self, player: wavelink.Player | None) -> str:

        if not player or not player.current:

            return "**📜 คิวเพลง**\n-# ยังไม่มีเซสชันเพลงที่กำลังทำงานอยู่ตอนนี้"

        lines = [
            "**📜 คิวเพลง**",
            f"**กำลังเล่นตอนนี้** - `{self._truncate_track_text(player.current.title, 52)}`",
        ]

        queue_items = list(player.queue)

        if queue_items:

            for index, track in enumerate(queue_items[:3], start=1):

                lines.append(
                    f"**ถัดไป {index}** - `{self._truncate_track_text(track.title, 44)}` - `{convert_ms_to_beautiful_time(track.length)}`"
                )

            if len(queue_items) > 3:

                lines.append(f"-# มีอีก {len(queue_items) - 3} เพลงรออยู่ในคิว")

        else:

            lines.append("-# คิวเพลงว่างอยู่ตอนนี้")

        return "\n".join(lines)

    def _queue_items(self, vc: wavelink.Player | None) -> list[wavelink.Playable]:

        if not vc:

            return []

        try:

            return list(getattr(vc, "queue", []) or [])

        except Exception:

            return []

    def _queue_track_line(self, track: wavelink.Playable, index: int) -> str:

        title = self._truncate_track_text(
            getattr(track, "title", None) or "Unknown", 62
        )
        length = convert_ms_to_beautiful_time(getattr(track, "length", 0) or 0)
        return f"`#{index}` `{title}` `{length}`"

    def _build_full_queue_embed(
        self, guild: discord.Guild, vc: wavelink.Player
    ) -> discord.Embed:

        guild_id = getattr(guild, "id", None)
        queue_items = self._queue_items(vc)
        current = getattr(vc, "current", None)

        embed = discord.Embed(
            title=f"📜 {self.t(guild_id, 'music_btn_queue')}",
            color=self._theme_color("accent"),
        )

        header_lines: list[str] = []

        if current is not None:

            status_key = (
                "music_status_paused"
                if getattr(vc, "paused", False)
                else "music_status_playing"
            )
            header_lines.append(
                f"**▶ {self.t(guild_id, status_key)}** — "
                f"`{self._truncate_track_text(getattr(current, 'title', '') or 'Unknown', 60)}` "
                f"`{convert_ms_to_beautiful_time(getattr(current, 'length', 0) or 0)}`"
            )

        if not queue_items:

            if header_lines:

                header_lines.append("")

            header_lines.append(self.t(guild_id, "music_queue_empty"))
            embed.description = "\n".join(header_lines)
            return embed

        total_duration = 0
        for track in queue_items:
            total_duration += int(getattr(track, "length", 0) or 0)

        if header_lines:

            header_lines.append("")

        header_lines.append(f"**คิวทั้งหมด:** `{len(queue_items)}` เพลง")
        header_lines.append(
            f"-# เวลารวมคิว: `{convert_ms_to_beautiful_time(total_duration)}`"
        )
        embed.description = "\n".join(header_lines)

        line_groups: list[list[str]] = []
        current_group: list[str] = []
        current_group_length = 0

        for index, track in enumerate(queue_items, start=1):
            line = self._queue_track_line(track, index)
            projected = current_group_length + len(line) + 1
            if current_group and projected > 1000:
                line_groups.append(current_group)
                current_group = [line]
                current_group_length = len(line) + 1
            else:
                current_group.append(line)
                current_group_length = projected

        if current_group:
            line_groups.append(current_group)

        max_queue_fields = 24
        shown_count = 0
        shown_groups = line_groups[:max_queue_fields]

        for page_index, group in enumerate(shown_groups, start=1):
            shown_count += len(group)
            field_name = "รายการคิวเพลง"
            if len(line_groups) > 1:
                field_name = f"รายการคิวเพลง ({page_index}/{len(line_groups)})"
            embed.add_field(name=field_name, value="\n".join(group), inline=False)

        hidden_count = max(0, len(queue_items) - shown_count)
        if hidden_count > 0 and len(embed.fields) < 25:
            embed.add_field(
                name="แสดงไม่ครบ",
                value=f"-# ยังมีอีก `{hidden_count}` เพลงที่ไม่ได้แสดงเพราะเกินลิมิตข้อความ",
                inline=False,
            )

        return embed

    async def _queue_delete_at(self, queue_obj, index: int) -> None:

        result = queue_obj.delete(index)
        if asyncio.iscoroutine(result):
            await result

    async def _queue_play_index_now(
        self, vc: wavelink.Player, queue_index: int
    ) -> tuple[bool, str]:

        queue_obj = getattr(vc, "queue", None)
        if queue_obj is None:
            return False, "ไม่พบคิวเพลง"

        queue_items = self._queue_items(vc)
        if not queue_items:
            return False, self.t(getattr(getattr(vc, "guild", None), "id", None), "music_queue_empty")

        if queue_index < 0 or queue_index >= len(queue_items):
            return False, "เลือกเพลงไม่ถูกต้อง"

        selected_track = queue_items.pop(queue_index)

        try:
            queue_obj.clear()
            for item in queue_items:
                await queue_obj.put_wait(item)
        except Exception:
            return False, "ไม่สามารถจัดการคิวเพลงได้"

        try:
            base_volume = int(getattr(vc, "volume", 0) or 0) or 80
            await vc.play(selected_track, volume=max(0, min(100, base_volume)))
        except Exception:
            try:
                if hasattr(queue_obj, "put_at"):
                    put_result = queue_obj.put_at(0, selected_track)
                    if asyncio.iscoroutine(put_result):
                        await put_result
                else:
                    rebuilt_queue = [selected_track, *list(queue_obj or [])]
                    queue_obj.clear()
                    for item in rebuilt_queue:
                        await queue_obj.put_wait(item)
            except Exception:
                pass
            return False, "สั่งเล่นเพลงจากคิวไม่สำเร็จ"

        track_title = self._truncate_track_text(
            getattr(selected_track, "title", None) or "Unknown", 70
        )
        return True, f"กำลังสลับไปเล่น: `{track_title}`"

    def _queue_select_options(
        self,
        queue_items: list[wavelink.Playable],
        *,
        page: int = 0,
        page_size: int = 25,
    ) -> tuple[list[discord.SelectOption], int, int]:

        total_items = len(queue_items)
        safe_page_size = max(1, int(page_size or 25))
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size)
        page_index = max(0, min(int(page or 0), total_pages - 1))
        start_index = page_index * safe_page_size
        end_index = start_index + safe_page_size

        options: list[discord.SelectOption] = []

        for absolute_index, track in enumerate(
            queue_items[start_index:end_index], start=start_index
        ):
            title = self._truncate_track_text(
                getattr(track, "title", None) or "Unknown", 80
            )
            duration = convert_ms_to_beautiful_time(getattr(track, "length", 0) or 0)
            label = f"#{absolute_index + 1} {title}"[:100]
            description = f"ความยาว {duration}"[:100]
            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(absolute_index),
                    description=description,
                    emoji="🎵",
                )
            )

        return options, page_index, total_pages

    def _build_queue_pick_view(
        self,
        guild: discord.Guild,
        vc: wavelink.Player,
        *,
        owner_user_id: int | None,
        enforce_voice_channel: bool,
        page: int = 0,
        timeout: float = 120.0,
    ) -> discord.ui.View | None:

        queue_items = self._queue_items(vc)
        if not queue_items:
            return None

        options, page_index, total_pages = self._queue_select_options(
            queue_items, page=page
        )
        if not options:
            return None

        placeholder = "เลือกเพลงในคิวเพื่อเล่นทันที"
        if len(queue_items) > 25:
            placeholder = (
                f"เลือกเพลงเพื่อเล่นทันที "
                f"(หน้า {page_index + 1}/{total_pages} • รวม {len(queue_items)} เพลง)"
            )

        view = discord.ui.View(timeout=timeout)
        queue_select = discord.ui.Select(
            placeholder=placeholder[:100],
            min_values=1,
            max_values=1,
            options=options,
        )

        async def _assert_queue_view_permission(
            interaction: discord.Interaction,
        ) -> bool:
            try:
                if owner_user_id is not None and int(interaction.user.id) != int(
                    owner_user_id
                ):
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            description="คุณไม่สามารถใช้เมนูนี้ได้",
                            color=color.red,
                        ),
                        ephemeral=True,
                        delete_after=8,
                    )
                    return False

                if enforce_voice_channel:
                    if (
                        not getattr(interaction.user, "voice", None)
                        or not interaction.user.voice.channel
                    ):
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้เมนูนี้ได้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=8,
                        )
                        return False
                    bot_channel = getattr(vc, "channel", None)
                    if bot_channel and interaction.user.voice.channel != bot_channel:
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณต้องอยู่ห้องเสียงเดียวกับบอท",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=8,
                        )
                        return False
                return True
            except Exception:
                return False

        async def queue_select_callback(interaction: discord.Interaction):

            try:
                if not await _assert_queue_view_permission(interaction):
                    return

                values = list((interaction.data or {}).get("values") or [])
                if not values:
                    return await interaction.response.send_message(
                        embed=discord.Embed(
                            description="เลือกเพลงไม่ถูกต้อง",
                            color=color.red,
                        ),
                        ephemeral=True,
                        delete_after=8,
                    )

                try:
                    queue_index = int(values[0])
                except (TypeError, ValueError):
                    queue_index = -1

                if not await self._safe_defer_interaction(interaction):
                    return

                ok, result_message = await self._queue_play_index_now(vc, queue_index)

                updated_embed = self._build_full_queue_embed(guild, vc)
                updated_view = self._build_queue_pick_view(
                    guild=guild,
                    vc=vc,
                    owner_user_id=owner_user_id,
                    enforce_voice_channel=enforce_voice_channel,
                    page=page_index,
                    timeout=timeout,
                )

                try:
                    if interaction.message:
                        await interaction.message.edit(
                            embed=updated_embed,
                            view=updated_view,
                        )
                except Exception:
                    try:
                        await interaction.edit_original_response(
                            embed=updated_embed,
                            view=updated_view,
                        )
                    except Exception:
                        pass

                await interaction.followup.send(
                    result_message,
                    ephemeral=True,
                    delete_after=8 if ok else 10,
                )

                if ok:
                    await self.send_music_controls(guild, update_attachments=True)

            except Exception:

                logger.error(
                    f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}"
                )

        queue_select.callback = queue_select_callback
        view.add_item(queue_select)

        if total_pages > 1:
            prev_button = discord.ui.Button(
                label="ก่อนหน้า",
                style=discord.ButtonStyle.secondary,
                emoji="◀️",
                disabled=page_index <= 0,
            )
            page_button = discord.ui.Button(
                label=f"หน้า {page_index + 1}/{total_pages}",
                style=discord.ButtonStyle.primary,
                disabled=True,
            )
            next_button = discord.ui.Button(
                label="ถัดไป",
                style=discord.ButtonStyle.secondary,
                emoji="▶️",
                disabled=page_index >= (total_pages - 1),
            )

            async def _change_page(interaction: discord.Interaction, target_page: int):
                if not await _assert_queue_view_permission(interaction):
                    return
                if not await self._safe_defer_interaction(interaction):
                    return
                updated_embed = self._build_full_queue_embed(guild, vc)
                updated_view = self._build_queue_pick_view(
                    guild=guild,
                    vc=vc,
                    owner_user_id=owner_user_id,
                    enforce_voice_channel=enforce_voice_channel,
                    page=target_page,
                    timeout=timeout,
                )
                try:
                    if interaction.message:
                        await interaction.message.edit(
                            embed=updated_embed,
                            view=updated_view,
                        )
                        return
                except Exception:
                    pass
                try:
                    await interaction.edit_original_response(
                        embed=updated_embed,
                        view=updated_view,
                    )
                except Exception:
                    pass

            async def prev_button_callback(interaction: discord.Interaction):
                await _change_page(interaction, max(0, page_index - 1))

            async def next_button_callback(interaction: discord.Interaction):
                await _change_page(interaction, min(total_pages - 1, page_index + 1))

            prev_button.callback = prev_button_callback
            next_button.callback = next_button_callback
            view.add_item(prev_button)
            view.add_item(page_button)
            view.add_item(next_button)

        return view

    def _playlist_select_options(self, guild_id: int | None = None) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        for key, payload in self.PLAYLIST_CATALOG.items():
            label = str(payload.get("label") or key).strip()[:100]
            emoji = str(payload.get("emoji") or "🎵").strip() or "🎵"
            options.append(
                discord.SelectOption(
                    label=label,
                    value=key,
                    description=f"เล่นอัตโนมัติแบบวนซ้ำ ({label})",
                    emoji=emoji,
                )
            )
        return options[:25]

    def _user_playlist_picker_options(
        self,
        rows: list[dict[str, object]],
        *,
        max_items_per_playlist: int | None = None,
    ) -> list[discord.SelectOption]:
        limit_value = int(max_items_per_playlist or self.USER_PLAYLIST_ITEM_LIMIT)
        options: list[discord.SelectOption] = []
        for row in list(rows or [])[:25]:
            slug = str(row.get("slug") or "").strip()
            name = str(row.get("name") or slug or "Playlist").strip()
            items = list(row.get("items") or [])
            item_count = len(items)
            value = (slug or str(row.get("id") or name)).strip()
            if not value:
                continue
            options.append(
                discord.SelectOption(
                    label=name[:100],
                    value=value[:100],
                    description=f"{item_count}/{limit_value} เพลง",
                    emoji="🎵",
                )
            )
        return options

    def _playlist_entry_preview_text(self, entry: dict[str, object] | None, *, limit: int = 76) -> str:
        if not isinstance(entry, dict):
            return "Unknown"
        value = str(entry.get("value") or "").strip()
        if not value:
            return "Unknown"
        # Shorten raw URLs so dropdown descriptions stay readable.
        if is_link(value):
            value = value.replace("https://", "").replace("http://", "")
        return self._truncate_track_text(value, limit)

    def _playlist_load_count_options(
        self, entries_or_total: list[dict[str, object]] | int
    ) -> list[discord.SelectOption]:
        entry_rows = (
            list(entries_or_total or [])
            if isinstance(entries_or_total, list)
            else []
        )
        total = (
            max(1, len(entry_rows))
            if entry_rows
            else max(1, int(entries_or_total or 1))
        )
        max_numeric = min(total, 25)

        options: list[discord.SelectOption] = []
        for amount in range(1, max_numeric + 1):
            preview_text = ""
            if entry_rows:
                first_entry = entry_rows[0]
                last_entry = entry_rows[min(amount - 1, len(entry_rows) - 1)]
                first_preview = self._playlist_entry_preview_text(first_entry, limit=32)
                last_preview = self._playlist_entry_preview_text(last_entry, limit=32)
                if amount <= 1 or first_preview == last_preview:
                    preview_text = f"เพลง: {first_preview}"
                else:
                    preview_text = f"แรก: {first_preview} • ท้าย: {last_preview}"
            description_text = preview_text or f"เพิ่ม {amount} เพลงแรกจากเพลย์ลิสต์"
            options.append(
                discord.SelectOption(
                    label=f"{amount} เพลง",
                    value=str(amount),
                    description=self._truncate_track_text(description_text, 100),
                    emoji="🎼",
                )
            )

        # Discord จำกัด select options สูงสุด 25 รายการ
        # ต้องการให้เลือกจำนวนแบบละเอียดทีละเลข 1-25
        return options[:25]

    def _is_playlist_url_entry_blocked_for_user_in_guild(
        self,
        *,
        guild_id: int,
        user_id: int,
        entries: list[dict[str, object]],
    ) -> bool:
        guild_subscription = str(
            self.bot.cache.guilds.get(str(guild_id), {}).get("subscription", "free")
            or "free"
        ).strip().lower()
        user_no_prefix_subscription = self.bot.cache.users.get(str(user_id), {}).get(
            "no_prefix_subscription", None
        )
        if guild_subscription != "free" or user_no_prefix_subscription:
            return False
        return any(
            str(item.get("kind") or "").strip().lower() == "url"
            for item in list(entries or [])
            if isinstance(item, dict)
        )

    async def _apply_playlist_entries_to_player(
        self,
        *,
        vc: wavelink.Player,
        guild_id: int,
        requester: discord.Member | discord.User,
        entries: list[dict[str, object]],
    ) -> tuple[list[str], int, int]:
        tracks, unresolved_items = await self._resolve_playlist_entries_to_tracks(entries)
        if not tracks:
            return [], len(unresolved_items), 0

        guild_subscription = str(
            self.bot.cache.guilds.get(str(guild_id), {}).get("subscription", "free")
            or "free"
        ).strip().lower()
        default_volume = (
            80
            if guild_subscription == "free"
            else self.bot.cache.music.get(str(guild_id), {}).get("default_volume", 80)
        )
        changed_titles, skipped_count = await self._apply_tracks_to_player(
            vc=vc,
            tracks=tracks,
            requester=requester,
            default_volume=default_volume,
        )
        return changed_titles, len(unresolved_items), skipped_count

    async def _build_playlist_tracks(self, playlist_key: str) -> list[wavelink.Playable]:
        payload = self.PLAYLIST_CATALOG.get(str(playlist_key or "").strip())
        if not payload:
            return []
        queries = payload.get("queries") or []
        if not isinstance(queries, list):
            return []
        tracks: list[wavelink.Playable] = []
        for raw_query in queries[:12]:
            query = str(raw_query or "").strip()
            if not query:
                continue
            try:
                result = await self._search_tracks(query)
            except Exception:
                continue
            if result:
                tracks.append(result[0])
        return tracks

    async def playlist_select_callback(self, interaction: discord.Interaction):
        try:
            vc = await self._validate_controller_interaction(interaction)
            if not vc:
                return

            values = []
            try:
                values = list((interaction.data or {}).get("values") or [])
            except Exception:
                values = []
            playlist_key = str(values[0] if values else "").strip()
            playlist_meta = self.PLAYLIST_CATALOG.get(playlist_key)
            if not playlist_meta:
                return await interaction.response.send_message(
                    "ไม่พบเพลย์ลิสต์ที่เลือก", ephemeral=True, delete_after=8
                )

            await interaction.response.defer()

            tracks = await self._build_playlist_tracks(playlist_key)
            if not tracks:
                return await self._send_controller_toast(
                    interaction, "ไม่พบเพลงในเพลย์ลิสต์ที่เลือก"
                )

            default_volume = int(
                self.bot.cache.music.get(str(interaction.guild.id), {}).get(
                    "default_volume", 80
                )
                or 80
            )
            changed_titles, skipped_count = await self._apply_tracks_to_player(
                vc=vc,
                tracks=tracks,
                requester=interaction.user,
                default_volume=default_volume,
            )
            if not changed_titles:
                return await self._send_controller_toast(
                    interaction,
                    f"{self._queue_full_message_for_guild(getattr(interaction.guild, 'id', None))} ไม่สามารถเพิ่มเพลย์ลิสต์ได้",
                )

            try:
                queue_obj = getattr(vc, "queue", None)
                if queue_obj is not None and hasattr(queue_obj, "mode"):
                    if hasattr(wavelink.QueueMode, "loop_all"):
                        queue_obj.mode = wavelink.QueueMode.loop_all
                    else:
                        queue_obj.mode = wavelink.QueueMode.loop
            except Exception:
                pass

            try:
                if getattr(vc, "autoplay", None) == wavelink.AutoPlayMode.disabled:
                    vc.autoplay = wavelink.AutoPlayMode.enabled
            except Exception:
                pass

            await self.send_music_controls(interaction.guild, update_attachments=True)
            playlist_name = str(playlist_meta.get("label") or playlist_key)
            message = f"เพิ่มเพลย์ลิสต์แล้ว: {playlist_name} ({len(changed_titles)} เพลง)"
            if skipped_count:
                message += f" | ข้าม {skipped_count} เพลงเพราะคิวเต็ม"
            await self._send_controller_toast(interaction, message)
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def _resolve_controller_message(
        self, guild: discord.Guild, command_channel: discord.TextChannel | None
    ):

        music_data = self.bot.cache.music.get(str(guild.id), {})

        controller_message = self.manual_controller_data.get(str(guild.id))

        target_channel = command_channel

        setup_channel_id = self._as_int(music_data.get("music_setup_channel_id"))
        setup_message_id = self._as_int(music_data.get("music_setup_message_id"))

        if setup_channel_id:

            target_channel = guild.get_channel(setup_channel_id)

            if target_channel:

                if setup_message_id:
                    try:

                        controller_message = await target_channel.fetch_message(
                            setup_message_id
                        )

                    except Exception:
                        # Fallback to in-memory pointer when DB id is stale or
                        # not yet synced during burst updates.
                        controller_message = self.manual_controller_data.get(
                            str(guild.id)
                        )

        return target_channel, controller_message, music_data

    def _should_replace_controller_message_on_edit_error(
        self, error: discord.HTTPException
    ) -> bool:
        # Do NOT replace on normal rate limit (429), otherwise we create
        # duplicate controller messages. Replace only on hard edit cap.
        code = getattr(error, "code", None)
        return code == 30046

    def _is_transient_controller_network_error(self, error: Exception) -> bool:
        if isinstance(error, (ConnectionResetError, TimeoutError, asyncio.TimeoutError, OSError)):
            return True
        if isinstance(error, RuntimeError):
            text = str(error).strip().lower()
            if "session is closed" in text or "connector is closed" in text:
                return True
        error_module = str(getattr(type(error), "__module__", "") or "").lower()
        error_name = str(getattr(type(error), "__name__", "") or "").lower()
        if error_module.startswith("aiohttp") and "client" in error_name:
            return True
        text = f"{type(error).__name__}: {error}".lower()
        transient_markers = (
            "session is closed",
            "connector is closed",
            "winerror 64",
            "network name is no longer available",
            "connection reset",
            "broken pipe",
            "server disconnected",
            "temporarily unavailable",
        )
        return any(marker in text for marker in transient_markers)

    def _is_discord_http_session_closed(self) -> bool:
        try:
            if bool(getattr(self.bot, "is_closed", lambda: False)()):
                return True
        except Exception:
            pass
        http_client = getattr(self.bot, "http", None)
        session = getattr(http_client, "_HTTPClient__session", None)
        return bool(getattr(session, "closed", False))

    def _build_safe_google_search_url(self, query: str) -> str:
        from urllib.parse import quote_plus

        base_url = "https://www.google.com/search?q="
        # Keep margin below Discord's 512-char button URL cap.
        max_url_len = 480

        safe_query = (query or "lyrics").strip() or "lyrics"
        encoded_query = quote_plus(safe_query)

        while safe_query and (len(base_url) + len(encoded_query)) > max_url_len:
            safe_query = safe_query[:-1].rstrip()
            encoded_query = quote_plus(safe_query)

        if not safe_query:
            safe_query = "lyrics"
            encoded_query = quote_plus(safe_query)

        return f"{base_url}{encoded_query}"

    def _guild_music_dashboard_url(self, guild_id: int | None) -> str:
        base_url = str(
            getattr(getattr(self.bot, "urls", None), "WEBSITE", "")
            or getattr(getattr(self.bot, "BotConfig", None), "DASHBOARD_BASE_URL", "")
            or ""
        ).strip()
        if not base_url:
            return ""
        if "://" not in base_url:
            base_url = f"https://{base_url}"
        base_url = base_url.rstrip("/")
        if guild_id is None:
            return f"{base_url}/dashboard"
        return f"{base_url}/dashboard/music/{int(guild_id)}"

    def _music_static_image_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "photos" / "music.png"

    def _music_static_attachment_name(self) -> str:
        return "music.png"

    def _music_static_attachment_url(self) -> str:
        return f"attachment://{self._music_static_attachment_name()}"

    def _music_dynamic_attachment_name(self) -> str:
        return "music_controller.png"

    def _music_dynamic_attachment_url(self) -> str:
        return f"attachment://{self._music_dynamic_attachment_name()}"

    def _sticky_controller_banner_enabled(self) -> bool:
        raw = str(os.getenv("MUSIC_CONTROLLER_STICKY_BANNER", "1") or "").strip().lower()
        return raw not in {"0", "false", "off", "no"}

    def _music_static_file(self) -> discord.File | None:
        image_path = self._music_static_image_path()
        if image_path.is_file():
            return discord.File(
                str(image_path),
                filename=self._music_static_attachment_name(),
            )
        return None

    def _resolve_controller_artwork(
        self,
        preferred_url: str | None = None,
    ) -> tuple[str, bool]:
        candidate = str(preferred_url or "").strip()
        if self._is_valid_button_url(candidate):
            return candidate, False

        if self._music_static_image_path().is_file():
            return self._music_static_attachment_url(), True

        default_banner = str(self.bot.urls.DEFAULT_MUSIC_BANNER).strip()
        if self._is_valid_button_url(default_banner):
            return default_banner, False

        return (
            "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?"
            "auto=format&fit=crop&w=1280&q=80",
            False,
        )

    def _build_player_controller_artwork(
        self, player: wavelink.Player
    ) -> tuple[str, Callable[[], discord.File | None]]:
        current_track = getattr(player, "current", None)
        thumbnail_source_raw = (
            getattr(current_track, "artwork", None)
            or getattr(current_track, "thumbnail", None)
            or self.bot.urls.DEFAULT_MUSIC_BANNER
        )
        thumbnail_source = str(thumbnail_source_raw or "").strip()

        render_source = thumbnail_source
        if not str(render_source).startswith(("http://", "https://")):
            render_source = str(self.bot.urls.DEFAULT_MUSIC_BANNER or "").strip()

        queue_obj = getattr(player, "queue", None)
        try:
            queue_size = len(queue_obj) if queue_obj is not None else 0
        except Exception:
            queue_size = 0

        try:
            music_controller_image = create_music_controller_image(
                music_thumbnail_url=render_source,
                music_title=str(getattr(current_track, "title", "Unknown") or "Unknown"),
                music_author=str(getattr(current_track, "author", "Unknown") or "Unknown"),
                music_album=getattr(getattr(current_track, "album", None), "name", "Single"),
                music_duration=int(getattr(current_track, "length", 0) or 0),
                current_position=max(0, int(getattr(player, "position", 0) or 0)),
                volume=int(getattr(player, "volume", 100) or 100),
                queue_size=queue_size,
                is_paused=bool(getattr(player, "paused", False)),
                autoplay_enabled=getattr(player, "autoplay", None)
                != wavelink.AutoPlayMode.disabled,
                loop_enabled=getattr(getattr(player, "queue", None), "mode", None)
                == wavelink.QueueMode.loop,
            )
            if music_controller_image:
                image_bytes = music_controller_image.getvalue()
                if image_bytes:
                    def _dynamic_attachment_factory() -> discord.File:
                        return discord.File(
                            BytesIO(image_bytes),
                            filename=self._music_dynamic_attachment_name(),
                        )

                    return self._music_dynamic_attachment_url(), _dynamic_attachment_factory
        except Exception:
            logger.error(f"Traceback: {traceback.format_exc()}")

        artwork_media, use_local_attachment = self._resolve_controller_artwork(
            thumbnail_source
        )
        if use_local_attachment:
            def _static_attachment_factory() -> discord.File | None:
                return self._music_static_file()

            return artwork_media, _static_attachment_factory

        return artwork_media, (lambda: None)

    def _build_player_controller_artwork_light(
        self, player: wavelink.Player
    ) -> tuple[str, Callable[[], discord.File | None]]:
        current_track = getattr(player, "current", None)
        thumbnail_source = (
            getattr(current_track, "artwork", None)
            or getattr(current_track, "thumbnail", None)
            or self.bot.urls.DEFAULT_MUSIC_BANNER
        )
        artwork_media, use_local_attachment = self._resolve_controller_artwork(
            str(thumbnail_source or "").strip()
        )
        if use_local_attachment:
            return artwork_media, (lambda: self._music_static_file())
        return artwork_media, (lambda: None)

    def _is_valid_button_url(self, value: str | None) -> bool:
        return (
            isinstance(value, str)
            and value.startswith(("http://", "https://"))
            and len(value) <= 512
        )

    async def select_filter_callback(self, interaction: discord.Interaction):

        try:

            vc: wavelink.Player = interaction.guild.voice_client

            if not vc:

                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description="บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

            if not interaction.user.voice:

                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description="คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้ปุ่มนี้ได้",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

            if vc.channel != interaction.user.voice.channel:

                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description="คุณต้องอยู่ห้องเสียงเดียวกับบอทก่อนจึงจะใช้ปุ่มนี้ได้",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

            # Rate limiting

            if self.music_controller_view_timeout_data.get(
                interaction.guild.id, None
            ) and datetime.datetime.now() - self.music_controller_view_timeout_data[
                interaction.guild.id
            ] < datetime.timedelta(
                seconds=10
            ):

                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.TIME} | Clicking too fast.",
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

            self.music_controller_view_timeout_data[interaction.guild.id] = (
                datetime.datetime.now()
            )

            if not await self._safe_defer_interaction(interaction):

                return

            # Get the selected filter

            selected_filter = interaction.data["values"][0]

            if selected_filter == "none":

                await vc.set_filters(None, seek=True)

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await interaction.followup.send(
                    f"{self.bot.emoji.SUCCESS} | Filter has been removed."
                )

            else:

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await interaction.followup.send(
                    f"{self.bot.emoji.SUCCESS} | Filter has been set to {selected_filter}."
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def volume_down_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if vc.volume <= 0:

                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description="ระดับเสียงต่ำสุดอยู่แล้ว", color=color.red
                    ),
                    ephemeral=True,
                    delete_after=6,
                )

            if not await self._safe_defer_interaction(interaction):

                return

            await vc.set_volume(max(0, vc.volume - 10))

            await self.send_music_controls(interaction.guild, update_attachments=True)

            await self._send_controller_toast(
                interaction, f"ตั้งระดับเสียงเป็น `{vc.volume}%`."
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def stop_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            vc.queue.clear()

            await vc.stop()

            await vc.disconnect()

            await self.send_music_controls(interaction.guild, end=True)

            await self._send_controller_toast(interaction, "หยุดเล่นเพลงแล้ว")

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def pause_resume_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            if vc.paused:

                await vc.pause(False)

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await self._send_controller_toast(interaction, "เล่นเพลงต่อแล้ว")

            else:

                await vc.pause(True)

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await self._send_controller_toast(interaction, "พักเพลงแล้ว")

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def skip_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            if vc.queue or vc.autoplay != wavelink.AutoPlayMode.disabled:

                await vc.skip(force=True)

                await self._send_controller_toast(interaction, "ข้ามเพลงปัจจุบันแล้ว")

            else:

                await self._send_controller_toast(
                    interaction, "ไม่มีเพลงถัดไปในคิวให้ข้ามได้"
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def rewind_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            new_position = await self._seek_relative(vc, -self.SEEK_STEP_MS)

            await self.send_music_controls(interaction.guild, update_attachments=True)

            await self._send_controller_toast(
                interaction,
                f"ย้อนกลับ 10 วินาที (`{convert_ms_to_beautiful_time(new_position)}`)",
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def forward_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            new_position = await self._seek_relative(vc, self.SEEK_STEP_MS)

            await self.send_music_controls(interaction.guild, update_attachments=True)

            await self._send_controller_toast(
                interaction,
                f"ข้ามไปข้างหน้า 10 วินาที (`{convert_ms_to_beautiful_time(new_position)}`)",
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def volume_up_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if vc.volume >= 100:

                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description="ระดับเสียงสูงสุดอยู่แล้ว", color=color.red
                    ),
                    ephemeral=True,
                    delete_after=6,
                )

            if not await self._safe_defer_interaction(interaction):

                return

            await vc.set_volume(min(100, vc.volume + 10))

            await self.send_music_controls(interaction.guild, update_attachments=True)

            await self._send_controller_toast(
                interaction, f"ตั้งระดับเสียงเป็น `{vc.volume}%`."
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def loop_toggle_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            if vc.queue.mode == wavelink.QueueMode.loop:

                vc.queue.mode = wavelink.QueueMode.normal

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await self._send_controller_toast(interaction, "ปิดโหมดวนซ้ำแล้ว")

            else:

                vc.queue.mode = wavelink.QueueMode.loop

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await self._send_controller_toast(interaction, "เปิดโหมดวนซ้ำแล้ว")

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def autoplay_toggle_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            if vc.autoplay == wavelink.AutoPlayMode.disabled:

                vc.autoplay = wavelink.AutoPlayMode.enabled

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await self._send_controller_toast(interaction, "เปิดเล่นอัตโนมัติแล้ว")

            else:

                vc.autoplay = wavelink.AutoPlayMode.disabled

                await self.send_music_controls(
                    interaction.guild, update_attachments=True
                )

                await self._send_controller_toast(interaction, "ปิดเล่นอัตโนมัติแล้ว")

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def save_current_to_playlist_button_callback(
        self, interaction: discord.Interaction
    ):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            if not await self._safe_defer_interaction(interaction):

                return

            current_track = getattr(vc, "current", None)
            if not current_track:
                return await self._send_controller_toast(
                    interaction, "ไม่มีเพลงที่กำลังเล่นให้บันทึก"
                )
            guild_id = int(getattr(getattr(interaction, "guild", None), "id", 0) or 0)
            max_playlists, max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)

            target_row = await user_music_playlists.get_user_playlist(
                interaction.user.id, "favorites"
            )
            if not target_row:
                _, _, target_row = await user_music_playlists.create_user_playlist(
                    interaction.user.id,
                    "favorites",
                    max_playlists=max_playlists,
                )
            if not target_row:
                return await self._send_controller_toast(
                    interaction, "สร้างเพลย์ลิสต์ favorites ไม่สำเร็จ"
                )

            track_uri = str(getattr(current_track, "uri", "") or "").strip()
            if not is_link(track_uri):
                track_uri = (
                    f"{getattr(current_track, 'title', 'Unknown')} "
                    f"{getattr(current_track, 'author', '')}"
                ).strip()

            ok, message, updated = await user_music_playlists.add_item_to_playlist(
                interaction.user.id,
                target_row.get("slug"),
                track_uri,
                max_items_per_playlist=max_items_per_playlist,
            )
            if updated:
                message += (
                    f" ({len(list(updated.get('items') or []))}"
                    f"/{max_items_per_playlist})"
                )
            await self._send_controller_toast(interaction, message if ok else f"⚠️ {message}")

        except Exception:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def open_user_playlist_picker_button_callback(
        self, interaction: discord.Interaction
    ):
        try:
            if not await self._ensure_music_access_interaction(interaction):
                return

            guild = getattr(interaction, "guild", None)
            user = getattr(interaction, "user", None)
            guild_id = int(getattr(guild, "id", 0) or 0)
            user_id = int(getattr(user, "id", 0) or 0)
            if guild_id <= 0 or user_id <= 0:
                return await interaction.response.send_message(
                    "ไม่พบข้อมูลกิลด์หรือผู้ใช้",
                    ephemeral=True,
                    delete_after=6,
                )

            rows = await user_music_playlists.list_user_playlists(user_id)
            if not rows:
                return await interaction.response.send_message(
                    (
                        "ยังไม่มีเพลย์ลิสต์ส่วนตัว\n"
                        "ใช้ `/music playlist_create` เพื่อสร้างก่อน"
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

            _max_playlists, max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)
            options = self._user_playlist_picker_options(
                rows,
                max_items_per_playlist=max_items_per_playlist,
            )
            if not options:
                return await interaction.response.send_message(
                    "ไม่พบเพลย์ลิสต์ที่ใช้ได้",
                    ephemeral=True,
                    delete_after=8,
                )

            intro_embed = self._music_embed(
                guild,
                "เลือกเพลย์ลิสต์ส่วนตัว",
                "ขั้นตอนที่ 1/2: เลือกเพลย์ลิสต์ของคุณจากรายการด้านล่าง",
                tone="accent",
                footer="Playlist Picker",
            )
            intro_embed.add_field(
                name="รายการ",
                value=f"พบเพลย์ลิสต์ `{len(options)}` รายการ",
                inline=False,
            )

            picker_view = discord.ui.View(timeout=120)
            playlist_select = discord.ui.Select(
                placeholder="🎼 เลือกเพลย์ลิสต์ของคุณ",
                min_values=1,
                max_values=1,
                options=options,
            )

            async def playlist_select_callback(select_interaction: discord.Interaction):
                if int(getattr(select_interaction.user, "id", 0) or 0) != user_id:
                    return await select_interaction.response.send_message(
                        "เมนูนี้เป็นของคนที่กดปุ่มเท่านั้น",
                        ephemeral=True,
                        delete_after=6,
                    )

                selected_values = list((select_interaction.data or {}).get("values") or [])
                selected_key = str(selected_values[0] if selected_values else "").strip()
                selected_row = await user_music_playlists.get_user_playlist(
                    user_id, selected_key
                )
                if not selected_row:
                    return await select_interaction.response.send_message(
                        "ไม่พบเพลย์ลิสต์ที่เลือก",
                        ephemeral=True,
                        delete_after=8,
                    )

                entries = list(selected_row.get("items") or [])
                if not entries:
                    return await select_interaction.response.send_message(
                        "เพลย์ลิสต์นี้ยังไม่มีเพลง",
                        ephemeral=True,
                        delete_after=8,
                    )

                count_options = self._playlist_load_count_options(entries)
                count_view = discord.ui.View(timeout=120)
                count_select = discord.ui.Select(
                    placeholder="🎛️ เลือกจำนวนเพลงที่ต้องการเพิ่ม",
                    min_values=1,
                    max_values=1,
                    options=count_options,
                )

                async def submit_playlist_entries(
                    count_interaction: discord.Interaction,
                    selected_entries: list[dict[str, object]],
                ):
                    async def _send_soft_voice_warning(
                        title: str,
                        description: str,
                        *,
                        delete_after: int = 10,
                    ):
                        warning_embed = self._music_embed(
                            guild,
                            title,
                            description,
                            tone="warning",
                            footer="Playlist Picker",
                        )
                        return await count_interaction.response.send_message(
                            embed=warning_embed,
                            ephemeral=True,
                            delete_after=delete_after,
                        )

                    if int(getattr(count_interaction.user, "id", 0) or 0) != user_id:
                        return await count_interaction.response.send_message(
                            "เมนูนี้เป็นของคนที่กดปุ่มเท่านั้น",
                            ephemeral=True,
                            delete_after=6,
                        )

                    if not await self._ensure_music_access_interaction(count_interaction):
                        return

                    current_vc: wavelink.Player | None = getattr(
                        getattr(count_interaction, "guild", None), "voice_client", None
                    )
                    if not current_vc or not getattr(current_vc, "connected", False):
                        return await _send_soft_voice_warning(
                            "ยังเพิ่มเพลงเข้าคิวไม่ได้ตอนนี้",
                            (
                                "บอทยังไม่ได้เชื่อมต่อห้องเสียง\n"
                                "คุณยังเลือกเพลย์ลิสต์ได้ตามปกติ และค่อยกดเล่นใหม่หลังบอทเข้าห้องเสียง"
                            ),
                            delete_after=12,
                        )
                    if not getattr(count_interaction.user, "voice", None):
                        return await _send_soft_voice_warning(
                            "อีกนิดเดียวก็เล่นได้แล้ว",
                            "คุณต้องเข้าห้องเสียงก่อน แล้วกดเลือกจำนวนเพลงเพื่อเพิ่มเข้าคิวอีกครั้ง",
                            delete_after=12,
                        )
                    user_voice_channel = getattr(count_interaction.user.voice, "channel", None)
                    bot_voice_channel = getattr(current_vc, "channel", None)
                    if user_voice_channel != bot_voice_channel:
                        bot_channel_mention = (
                            getattr(bot_voice_channel, "mention", None) or "ห้องเสียงของบอท"
                        )
                        return await _send_soft_voice_warning(
                            "ยังเพิ่มเพลงไม่ได้ในตอนนี้",
                            (
                                "คุณต้องอยู่ห้องเสียงเดียวกับบอทก่อน\n"
                                f"ตอนนี้บอทอยู่ที่ {bot_channel_mention}"
                            ),
                            delete_after=12,
                        )

                    selected_entries = list(selected_entries or [])
                    if not selected_entries:
                        return await count_interaction.response.send_message(
                            "ไม่พบเพลงที่เลือกจากเพลย์ลิสต์",
                            ephemeral=True,
                            delete_after=8,
                        )

                    if self._is_playlist_url_entry_blocked_for_user_in_guild(
                        guild_id=guild_id,
                        user_id=user_id,
                        entries=selected_entries,
                    ):
                        return await count_interaction.response.send_message(
                            embed=discord.Embed(
                                description="แพ็กเกจฟรียังไม่รองรับการเล่นเพลงผ่านลิงก์",
                                color=color.red,
                            ),
                            view=discord.ui.View().add_item(
                                discord.ui.Button(
                                    label="อัปเกรดพรีเมียม",
                                    style=discord.ButtonStyle.url,
                                    url=self.bot.urls.SUPPORT_SERVER,
                                    emoji=self.bot.emoji.SUPPORT,
                                )
                            ),
                            ephemeral=True,
                            delete_after=12,
                        )

                    try:
                        await count_interaction.response.defer(ephemeral=True)
                    except Exception:
                        return

                    changed_titles, unresolved_count, skipped_count = (
                        await self._apply_playlist_entries_to_player(
                            vc=current_vc,
                            guild_id=guild_id,
                            requester=count_interaction.user,
                            entries=selected_entries,
                        )
                    )
                    if not changed_titles:
                        message = (
                            f"{self.bot.emoji.LIMIT} | {self._queue_full_message_for_guild(guild_id)}"
                            if unresolved_count <= 0
                            else f"{self.bot.emoji.ERROR} | ไม่พบเพลงที่เล่นได้จากเพลย์ลิสต์ที่เลือก (ข้าม {unresolved_count} รายการ)"
                        )
                        return await count_interaction.followup.send(
                            message,
                            ephemeral=True,
                            delete_after=10,
                        )

                    await self.send_music_controls(
                        count_interaction.guild,
                        update_attachments=True,
                    )
                    await user_music_playlists.mark_playlist_used(
                        user_id, selected_row.get("slug")
                    )

                    success_embed = self._music_embed(
                        guild,
                        "เพิ่มเพลงจากเพลย์ลิสต์สำเร็จ",
                        (
                            f"เพลย์ลิสต์: **{selected_row.get('name')}**\n"
                            f"เพิ่มเข้าเล่น: `{len(changed_titles)}` เพลง"
                        ),
                        tone="success",
                        footer="Playlist Picker",
                    )
                    if unresolved_count:
                        success_embed.add_field(
                            name="ข้ามเพราะหาไม่เจอ",
                            value=str(unresolved_count),
                            inline=True,
                        )
                    if skipped_count:
                        success_embed.add_field(
                            name="ข้ามเพราะคิวเต็ม",
                            value=str(skipped_count),
                            inline=True,
                        )

                    try:
                        await count_interaction.edit_original_response(
                            embed=success_embed,
                            view=None,
                        )
                    except Exception:
                        await count_interaction.followup.send(
                            f"{self.bot.emoji.SUCCESS} | เพิ่มเพลงจากเพลย์ลิสต์แล้ว `{len(changed_titles)}` เพลง",
                            ephemeral=True,
                            delete_after=10,
                        )

                async def count_select_callback(count_interaction: discord.Interaction):
                    chosen_values = list((count_interaction.data or {}).get("values") or [])
                    amount_raw = str(chosen_values[0] if chosen_values else "1").strip().lower()
                    try:
                        chosen_count = max(1, int(amount_raw))
                    except Exception:
                        chosen_count = 1
                    selected_entries = entries[: min(chosen_count, len(entries))]
                    await submit_playlist_entries(count_interaction, selected_entries)

                async def count_all_callback(all_interaction: discord.Interaction):
                    await submit_playlist_entries(all_interaction, entries)

                count_select.callback = count_select_callback
                count_view.add_item(count_select)
                count_all_button = discord.ui.Button(
                    label="ทั้งหมด",
                    style=discord.ButtonStyle.primary,
                    emoji="📚",
                )
                count_all_button.callback = count_all_callback
                count_view.add_item(count_all_button)

                step2_embed = self._music_embed(
                    guild,
                    "เลือกจำนวนเพลง",
                    (
                        "ขั้นตอนที่ 2/2: เลือกจำนวนเพลงที่ต้องการเพิ่ม\n"
                        "ใช้ปุ่ม `ทั้งหมด` เพื่อเพิ่มทุกเพลงในครั้งเดียว\n"
                        f"เพลย์ลิสต์: **{selected_row.get('name')}** "
                        f"({len(entries)} เพลง)"
                    ),
                    tone="info",
                    footer="Playlist Picker",
                )
                await select_interaction.response.edit_message(
                    embed=step2_embed,
                    view=count_view,
                )

            playlist_select.callback = playlist_select_callback
            picker_view.add_item(playlist_select)
            await interaction.response.send_message(
                embed=intro_embed,
                view=picker_view,
                ephemeral=True,
                delete_after=120,
            )
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def set_volume_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:

                return

            class set_volume_modal(discord.ui.Modal, title="ตั้งระดับเสียง"):

                new_volume_field = discord.ui.TextInput(
                    label="Volume",
                    min_length=1,
                    max_length=3,
                    required=True,
                    default=str(vc.volume),
                    placeholder="Volume (0-100)",
                    style=discord.TextStyle.short,
                )

                bot = self.bot

                send_music_controls = self.send_music_controls

                async def on_submit(self, interaction: discord.Interaction):

                    try:

                        vc: wavelink.Player = interaction.guild.voice_client

                        if not vc:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        if not interaction.user.voice:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้ปุ่มนี้ได้",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        if vc.channel != interaction.user.voice.channel:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="คุณต้องอยู่ห้องเสียงเดียวกับบอทก่อนจึงจะใช้ปุ่มนี้ได้",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        try:

                            volume = int(self.new_volume_field.value)

                        except Exception:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="ค่าระดับเสียงไม่ถูกต้อง", color=color.red
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        if not 0 <= volume <= 100:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="ระดับเสียงต้องอยู่ระหว่าง 0 ถึง 100",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        await interaction.response.defer()

                        await vc.set_volume(volume)

                        await self.send_music_controls(
                            interaction.guild, update_attachments=True
                        )

                        await interaction.followup.send(
                            f"ตั้งระดับเสียงเป็น `{volume}%`.", ephemeral=True
                        )

                    except Exception:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}"
                        )

            await interaction.response.send_modal(set_volume_modal())

        except Exception:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def queue_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:
                return

            embed = self._build_full_queue_embed(interaction.guild, vc)
            view = self._build_queue_pick_view(
                guild=interaction.guild,
                vc=vc,
                owner_user_id=interaction.user.id,
                enforce_voice_channel=True,
                timeout=120,
            )

            send_kwargs = {
                "embed": embed,
                "ephemeral": True,
                "delete_after": 120,
            }
            if view is not None:
                send_kwargs["view"] = view
            await interaction.response.send_message(
                **send_kwargs,
            )

        except Exception:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def lyrics_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:
                return

            current = getattr(vc, "current", None)

            if current is None:
                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description=self.t(interaction.guild.id, "music_nothing_playing"),
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=10,
                )

            raw_query = f"{getattr(current, 'title', '')} {getattr(current, 'author', '')} lyrics".strip()
            search_url = self._build_safe_google_search_url(raw_query)

            embed = discord.Embed(
                title=f"📝 {self.t(interaction.guild.id, 'music_btn_lyrics')}",
                description=(
                    f"{self.t(interaction.guild.id, 'music_lyrics_unsupported')}\n\n"
                    f"**🎵 {self._truncate_track_text(current.title, 70)}**\n"
                    f"-# {self._truncate_track_text(getattr(current, 'author', '') or 'Unknown', 60)}"
                ),
                color=color.blue if hasattr(color, "blue") else discord.Color.blue(),
            )

            view = discord.ui.View(timeout=60)
            if self._is_valid_button_url(search_url):
                view.add_item(
                    discord.ui.Button(
                        label="ค้นหาบน Google",
                        style=discord.ButtonStyle.link,
                        url=search_url,
                        emoji="🔎",
                    )
                )

            track_uri = getattr(current, "uri", None)
            if self._is_valid_button_url(track_uri):
                view.add_item(
                    discord.ui.Button(
                        label=self.t(interaction.guild.id, "music_btn_open_original"),
                        style=discord.ButtonStyle.link,
                        url=track_uri,
                        emoji="🔗",
                    )
                )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True, delete_after=60
            )

        except Exception:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def shuffle_button_callback(self, interaction: discord.Interaction):

        try:

            vc = await self._validate_controller_interaction(interaction)

            if not vc:
                return

            queue_obj = getattr(vc, "queue", None)
            queue_items = list(queue_obj or [])

            if not queue_items:
                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description=self.t(interaction.guild.id, "music_shuffle_empty"),
                        color=color.red,
                    ),
                    ephemeral=True,
                    delete_after=8,
                )

            await interaction.response.defer()

            try:
                queue_obj.shuffle()
            except Exception:
                # Fallback: rebuild queue with shuffled list
                import random
                random.shuffle(queue_items)
                try:
                    queue_obj.clear()
                    for track in queue_items:
                        await queue_obj.put_wait(track)
                except Exception:
                    logger.error(f"Shuffle fallback failed: {traceback.format_exc()}")

            await self.send_music_controls(interaction.guild, update_attachments=True)

            await self._send_controller_toast(
                interaction, self.t(interaction.guild.id, "music_shuffle_done")
            )

        except Exception:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    manual_controller_data = (
        {}
    )  # {guild_id: discord.Message}  # Store the controller message for each guild
    controller_update_locks: dict[str, asyncio.Lock] = {}

    def _get_controller_update_lock(self, guild_id: int) -> asyncio.Lock:
        key = str(guild_id)
        lock = self.controller_update_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self.controller_update_locks[key] = lock
        return lock

    def _mark_controller_channel_resolved(self, guild_id: int) -> None:
        self._controller_channel_missing_warned_at.pop(guild_id, None)
        self._controller_channel_missing_suppressed.pop(guild_id, None)

    def _warn_missing_controller_channel(self, guild: discord.Guild) -> None:
        guild_id = int(getattr(guild, "id", 0) or 0)
        now_ts = datetime.datetime.now().timestamp()
        last_warned_at = float(
            self._controller_channel_missing_warned_at.get(guild_id, 0.0) or 0.0
        )
        cooldown = max(30, int(self._controller_channel_missing_log_cooldown_seconds))

        if now_ts - last_warned_at >= cooldown:
            suppressed = int(
                self._controller_channel_missing_suppressed.get(guild_id, 0) or 0
            )
            suffix = (
                f" (suppressed {suppressed} repeats during cooldown)"
                if suppressed > 0
                else ""
            )
            logger.warning(f"Music controller channel missing for {guild.name}{suffix}")
            self._controller_channel_missing_warned_at[guild_id] = now_ts
            self._controller_channel_missing_suppressed[guild_id] = 0
            return

        self._controller_channel_missing_suppressed[guild_id] = (
            int(self._controller_channel_missing_suppressed.get(guild_id, 0) or 0) + 1
        )

    async def _try_delete_controller_message(self, message: discord.Message | None):
        if message is None:
            return
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            return
        except discord.HTTPException as delete_error:
            logger.warning(
                f"[music_setup] Failed to delete stale controller message "
                f"(status={getattr(delete_error, 'status', None)} code={getattr(delete_error, 'code', None)})"
            )

    async def send_music_controls(
        self,
        guild: discord.Guild,
        update_attachments: bool = False,
        end: bool = False,
        command_channel: discord.TextChannel = None,
    ):
        if self._is_discord_http_session_closed():
            return

        lock = self._get_controller_update_lock(guild.id)
        await lock.acquire()

        try:

            target_channel, controller_message, music_data = (
                await self._resolve_controller_message(guild, command_channel)
            )

            vc: wavelink.Player | None = guild.voice_client

            if end or not vc or not vc.current:
                idle_artwork_media, idle_use_local_attachment = (
                    self._resolve_controller_artwork()
                )

                idle_view = SkylineBOTMusicControllerView(
                    cog=self,
                    guild=guild,
                    player=None,
                    artwork_media=idle_artwork_media,
                    interactive=False,
                )

                if controller_message:

                    try:
                        edit_kwargs: dict[str, object] = {
                            "view": idle_view,
                            "attachments": [],
                        }
                        if idle_use_local_attachment:
                            idle_file = self._music_static_file()
                            if idle_file is not None:
                                edit_kwargs["attachments"] = [idle_file]
                        await controller_message.edit(**edit_kwargs)
                    except discord.NotFound:
                        controller_message = None

                    except discord.HTTPException as edit_error:
                        if self._should_replace_controller_message_on_edit_error(
                            edit_error
                        ):
                            logger.warning(
                                f"[music_setup] Controller idle message reached edit cap for guild {guild.id}; sending a new controller message"
                            )
                            await self._try_delete_controller_message(
                                controller_message
                            )
                            controller_message = None
                        else:
                            logger.warning(
                                f"[music_setup] Skip idle controller edit for guild {guild.id} "
                                f"(status={getattr(edit_error, 'status', None)} code={getattr(edit_error, 'code', None)})"
                            )
                            return
                    except Exception as edit_error:
                        if self._is_transient_controller_network_error(edit_error):
                            logger.warning(
                                f"[music_setup] Temporary network error while editing idle controller for guild {guild.id} "
                                f"({type(edit_error).__name__}: {edit_error})"
                            )
                            return
                        raise

                if controller_message is None and target_channel:

                    try:
                        send_kwargs: dict[str, object] = {"view": idle_view}
                        if idle_use_local_attachment:
                            idle_file = self._music_static_file()
                            if idle_file is not None:
                                send_kwargs["file"] = idle_file
                        controller_message = await target_channel.send(**send_kwargs)
                    except Exception as send_error:
                        if self._is_transient_controller_network_error(send_error):
                            logger.warning(
                                f"[music_setup] Temporary network error while sending idle controller for guild {guild.id} "
                                f"({type(send_error).__name__}: {send_error})"
                            )
                            return
                        raise
                    self.manual_controller_data[str(guild.id)] = controller_message

                if music_data.get("music_setup_channel_id") and controller_message:
                    current_message_id = self._as_int(music_data.get("music_setup_message_id"))
                    if current_message_id != controller_message.id:
                        await storage.music.update(
                            id=music_data.get("id"),
                            music_setup_message_id=controller_message.id,
                        )

                elif str(guild.id) in self.manual_controller_data:

                    del self.manual_controller_data[str(guild.id)]

                if target_channel or controller_message:
                    self._mark_controller_channel_resolved(guild.id)

                return

            should_render_dynamic_attachment = bool(
                update_attachments
                or controller_message is None
                or self._sticky_controller_banner_enabled()
            )
            if should_render_dynamic_attachment:
                artwork_media, attachment_factory = self._build_player_controller_artwork(vc)
            else:
                artwork_media, attachment_factory = self._build_player_controller_artwork_light(vc)
            needs_attachment = str(artwork_media).startswith("attachment://")

            view = SkylineBOTMusicControllerView(
                cog=self,
                guild=guild,
                player=vc,
                artwork_media=artwork_media,
                interactive=True,
            )

            if not target_channel:

                target_channel = command_channel

            if not target_channel and controller_message:

                target_channel = controller_message.channel

            if not target_channel:

                self._warn_missing_controller_channel(guild)

                return

            self._mark_controller_channel_resolved(guild.id)

            if not controller_message:

                try:
                    send_kwargs: dict[str, object] = {"view": view}
                    initial_attachment = attachment_factory()
                    if initial_attachment is not None:
                        send_kwargs["file"] = initial_attachment
                    controller_message = await target_channel.send(**send_kwargs)
                except Exception as send_error:
                    if self._is_transient_controller_network_error(send_error):
                        logger.warning(
                            f"[music_setup] Temporary network error while sending controller for guild {guild.id} "
                            f"({type(send_error).__name__}: {send_error})"
                        )
                        return
                    raise
                self.manual_controller_data[str(guild.id)] = controller_message

            else:

                try:
                    edit_kwargs: dict[str, object] = {"view": view}
                    refreshed_attachment = attachment_factory()
                    if update_attachments or needs_attachment:
                        edit_kwargs["attachments"] = (
                            [refreshed_attachment]
                            if refreshed_attachment is not None
                            else []
                        )
                    await controller_message.edit(**edit_kwargs)
                except discord.NotFound:
                    try:
                        send_kwargs: dict[str, object] = {"view": view}
                        replaced_attachment = attachment_factory()
                        if replaced_attachment is not None:
                            send_kwargs["file"] = replaced_attachment
                        controller_message = await target_channel.send(**send_kwargs)
                    except Exception as send_error:
                        if self._is_transient_controller_network_error(send_error):
                            logger.warning(
                                f"[music_setup] Temporary network error while replacing controller for guild {guild.id} "
                                f"({type(send_error).__name__}: {send_error})"
                            )
                            return
                        raise

                except discord.HTTPException as edit_error:
                    if self._should_replace_controller_message_on_edit_error(edit_error):
                        logger.warning(
                            f"[music_setup] Controller message reached edit cap for guild {guild.id}; sending a new controller message"
                        )
                        stale_controller_message = controller_message
                        try:
                            send_kwargs: dict[str, object] = {"view": view}
                            replaced_attachment = attachment_factory()
                            if replaced_attachment is not None:
                                send_kwargs["file"] = replaced_attachment
                            controller_message = await target_channel.send(**send_kwargs)
                        except Exception as send_error:
                            if self._is_transient_controller_network_error(send_error):
                                logger.warning(
                                    f"[music_setup] Temporary network error while replacing controller for guild {guild.id} "
                                    f"({type(send_error).__name__}: {send_error})"
                                )
                                return
                            raise
                        await self._try_delete_controller_message(
                            stale_controller_message
                        )
                        self.manual_controller_data[str(guild.id)] = controller_message
                    else:
                        # Keep single-message strategy: skip this update when
                        # Discord rejects rapid edits (429), don't send a new one.
                        logger.warning(
                            f"[music_setup] Skip controller edit for guild {guild.id} "
                            f"(status={getattr(edit_error, 'status', None)} code={getattr(edit_error, 'code', None)})"
                        )
                        return
                except Exception as edit_error:
                    if self._is_transient_controller_network_error(edit_error):
                        logger.warning(
                            f"[music_setup] Temporary network error while editing controller for guild {guild.id} "
                            f"({type(edit_error).__name__}: {edit_error})"
                        )
                        return
                    raise

            if music_data.get("music_setup_channel_id"):
                current_message_id = self._as_int(music_data.get("music_setup_message_id"))
                if current_message_id != controller_message.id:
                    await storage.music.update(
                        id=music_data.get("id"),
                        music_setup_message_id=controller_message.id,
                    )

            else:

                self.manual_controller_data[str(guild.id)] = controller_message

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")
        finally:
            if lock.locked():
                lock.release()

    @commands.Cog.listener(name="on_message")
    async def on_message(self, message: discord.Message):

        if message.channel.id in [1289263302152552458]:

            pass

            # await self.play_music(message.guild,message.content,message.author,message.channel)

    @commands.hybrid_command(
        name="pause", help="หยุดเพลงชั่วคราว", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def pause(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        if vc:

            if ctx.interaction:

                await self._safe_ctx_defer(ctx)

            if not ctx.author.voice:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                    delete_after=10,
                )

            if vc.channel != ctx.author.voice.channel:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                    delete_after=10,
                )

            if vc.paused:

                await ctx.send("เพลงถูกพักอยู่แล้ว")

                return

            await vc.pause(True)

            await self.send_music_controls(ctx.guild)

            await ctx.reply(f"{self.bot.emoji.PAUSED} | พักเพลงแล้ว")

        else:

            await ctx.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                delete_after=10,
            )

    @commands.hybrid_command(
        name="resume", help="เล่นเพลงต่อ", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def resume(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        if vc:

            if ctx.interaction:

                await self._safe_ctx_defer(ctx)

            if not ctx.author.voice:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                    delete_after=10,
                )

            if vc.channel != ctx.author.voice.channel:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                    delete_after=10,
                )

            if not vc.paused:

                await ctx.send("เพลงกำลังเล่นอยู่แล้ว")

                return

            await vc.pause(False)

            await self.send_music_controls(ctx.guild)

            await ctx.reply(f"{self.bot.emoji.PLAYING} | เล่นเพลงต่อแล้ว")

        else:

            await ctx.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                delete_after=10,
            )

    @commands.hybrid_command(name="skip", help="ข้ามเพลงปัจจุบัน", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def skip(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        # Check if the user is in a voice channel

        if not ctx.author.voice:

            return await ctx.send(
                f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                delete_after=10,
            )

        # Check if the bot is in a voice channel

        if not vc:

            return await ctx.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                delete_after=10,
            )

        # Check if the bot and user are in the same voice channel

        if vc and vc.channel != ctx.author.voice.channel:

            return await ctx.send(
                f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                delete_after=10,
            )

        if ctx.interaction:

            await self._safe_ctx_defer(ctx)

        # Check if there is a track currently playing or paused

        if vc.playing or vc.paused:

            # Skip the current track

            if hasattr(vc, "skip"):
                await vc.skip(force=True)
            else:
                await vc.stop()  # fallback for older player objects

            await ctx.reply(f"{self.bot.emoji.SUCCESS} | ข้ามเพลงปัจจุบันแล้ว")

        else:

            await ctx.send(
                f"{self.bot.emoji.ERROR} | ยังไม่มีเพลงที่กำลังเล่นหรือพักอยู่",
                delete_after=10,
            )

    @commands.hybrid_command(
        name="loop", help="วนเพลงปัจจุบัน", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def loop(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        if not vc:

            return await ctx.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                delete_after=10,
            )

        # Check if the user is in a voice channel

        if not ctx.author.voice:

            return await ctx.send(
                f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                delete_after=10,
            )

        # Check if the bot and user are in the same voice channel

        if vc.channel != ctx.author.voice.channel:

            return await ctx.send(
                f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                delete_after=10,
            )

        if ctx.interaction:

            await self._safe_ctx_defer(ctx)

        # Toggle loop mode between 'normal' and 'loop'

        if vc.queue.mode == wavelink.QueueMode.loop:

            vc.queue.mode = wavelink.QueueMode.normal

            await ctx.reply(f"{self.bot.emoji.SUCCESS} | ปิดการวนซ้ำแล้ว")

        else:

            vc.queue.mode = wavelink.QueueMode.loop

            await ctx.reply(f"{self.bot.emoji.SUCCESS} | เปิดการวนซ้ำแล้ว")

    @commands.hybrid_command(
        name="queue",
        aliases=["q", "tracks", "track"],
        help="แสดงคิวเพลง",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def queue(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        try:

            vc: wavelink.Player = ctx.guild.voice_client

            if not vc:

                await ctx.send(
                    f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                    delete_after=10,
                )
                return

            if ctx.interaction:

                await self._safe_ctx_defer(ctx)

            embed = self._build_full_queue_embed(ctx.guild, vc)
            view = self._build_queue_pick_view(
                guild=ctx.guild,
                vc=vc,
                owner_user_id=ctx.author.id,
                enforce_voice_channel=True,
                timeout=120,
            )

            send_kwargs = {"embed": embed}
            if view is not None:
                send_kwargs["view"] = view
            await ctx.send(**send_kwargs)

        except Exception as e:

            logger.error(f"Traceback: {traceback.format_exc()}")

    @commands.hybrid_command(
        name="volume",
        aliases=["vol", "v"],
        help="ดูหรือปรับระดับเสียง",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def volume(self, ctx: commands.Context, volume: int = None):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        if vc:

            if ctx.interaction:

                await self._safe_ctx_defer(ctx)

            if not ctx.author.voice:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                    delete_after=10,
                )

            if vc.channel != ctx.author.voice.channel:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                    delete_after=10,
                )

            if not volume:

                await ctx.send(f"ระดับเสียงปัจจุบัน: {vc.volume}")

            else:

                if volume < 0 or volume > 100:

                    return await ctx.send(
                        f"{self.bot.emoji.LIMIT} | ระดับเสียงต้องอยู่ระหว่าง 0 ถึง 100",
                        delete_after=10,
                    )

                await vc.set_volume(volume)

                filled_blocks = volume // 10

                empty_blocks = 10 - filled_blocks

                text = "█" * filled_blocks + "░" * empty_blocks

                await ctx.reply(f"`{text}`")

                await self.send_music_controls(ctx.guild, update_attachments=True)

        else:

            await ctx.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                delete_after=10,
            )

    @commands.hybrid_command(
        name="seek",
        aliases=["jump", "ff", "rw"],
        help="เลื่อนเวลาเพลง เช่น 90, +10, -10, 1:30",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=20, type=commands.BucketType.user)
    async def seek(self, ctx: commands.Context, *, position: str):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        if not vc or not getattr(vc, "current", None):
            return await ctx.send(
                f"{self.bot.emoji.ERROR} | ยังไม่มีเพลงที่กำลังเล่นอยู่",
                delete_after=10,
            )

        if not ctx.author.voice:
            return await ctx.send(
                f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                delete_after=10,
            )

        if vc.channel != ctx.author.voice.channel:
            return await ctx.send(
                f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                delete_after=10,
            )

        if ctx.interaction:
            await self._safe_ctx_defer(ctx)

        delta_or_absolute = self._parse_seek_input(position)
        if delta_or_absolute is None:
            return await ctx.reply(
                f"{self.bot.emoji.ERROR} | รูปแบบไม่ถูกต้อง ตัวอย่าง: `90`, `+10`, `-10`, `1:30`",
                delete_after=12,
            )

        target_ms = int(delta_or_absolute)
        if str(position).strip().startswith(("+", "-")):
            target_ms = max(
                0,
                min(
                    int(getattr(vc.current, "length", 0) or 0),
                    int(getattr(vc, "position", 0) or 0) + target_ms,
                ),
            )
        else:
            target_ms = max(0, target_ms)
            length_ms = int(getattr(vc.current, "length", 0) or 0)
            if length_ms > 0:
                target_ms = min(target_ms, max(0, length_ms - 1000))

        await vc.seek(target_ms)
        await self.send_music_controls(ctx.guild, update_attachments=True)
        await ctx.reply(
            f"{self.bot.emoji.SUCCESS} | เลื่อนไปที่ `{convert_ms_to_beautiful_time(target_ms)}` แล้ว"
        )

    @commands.hybrid_command(
        name="stop",
        help="หยุดเพลงและให้บอทออกจากห้องเสียง",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def stop(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        manually_disconnected = False

        if ctx.interaction:

            await self._safe_ctx_defer(ctx)

        if not vc:

            try:

                # Check if the bot is connected to a voice channel

                if ctx.guild.me.voice:

                    await ctx.guild.me.move_to(None)

                    manually_disconnected = True

            except Exception as e:

                logger.error(f"ข้อผิดพลาด in file {__file__}: {e}")

        if vc:

            if not ctx.author.voice:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                    delete_after=10,
                )

            if vc.channel != ctx.author.voice.channel:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                    delete_after=10,
                )

            vc.queue.clear()

            await vc.stop()

            try:

                await ctx.send(
                    f"{self.bot.emoji.STOP} | หยุดเพลงแล้ว", delete_after=10
                )

            except Exception as e:

                logger.error(f"ข้อผิดพลาด in file {__file__}: {e}")

            await vc.disconnect()

            await self.send_music_controls(ctx.guild, end=True)

        elif manually_disconnected:

            await ctx.send(
                f"{self.bot.emoji.SUCCESS} | The bot has been disconnected.",
                delete_after=10,
            )

        elif not vc and not manually_disconnected:

            await ctx.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                delete_after=10,
            )

    @commands.hybrid_command(
        name="current",
        aliases=["nowplaying"],
        help="แสดงเพลงที่กำลังเล่นอยู่",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def current(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        if vc:

            if ctx.interaction:

                await self._safe_ctx_defer(ctx)

            if not vc.current:

                await ctx.send("ยังไม่มีเพลงที่กำลังเล่น")

                return

            await ctx.send(
                f"**{self.bot.emoji.PLAYING} : {vc.current.title}** __by__ `{vc.current.author}`"
            )

        else:

            await ctx.send(
                "บอทยังไม่ได้เชื่อมต่อห้องเสียง", delete_after=10
            )

    # autoplay

    @commands.hybrid_command(
        name="autoplay", help="เปิดหรือปิดโหมดเล่นอัตโนมัติ", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def autoplay(self, ctx: commands.Context):
        if not await self._ensure_music_access_ctx(ctx):
            return

        vc: wavelink.Player = ctx.guild.voice_client

        if vc:

            if ctx.interaction:

                await self._safe_ctx_defer(ctx)

            if not ctx.author.voice:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้คำสั่งนี้ได้",
                    delete_after=10,
                )

            if vc.channel != ctx.author.voice.channel:

                return await ctx.send(
                    f"{self.bot.emoji.ERROR} | You need to be in the same voice channel as the bot to use this command.",
                    delete_after=10,
                )

            if vc.autoplay == wavelink.AutoPlayMode.disabled:

                vc.autoplay = wavelink.AutoPlayMode.enabled

                await ctx.reply(
                    f"{self.bot.emoji.SUCCESS} | เปิดเล่นต่ออัตโนมัติแล้ว"
                )

            else:

                vc.autoplay = wavelink.AutoPlayMode.disabled

                await ctx.reply(
                    f"{self.bot.emoji.SUCCESS} | ปิดเล่นต่ออัตโนมัติแล้ว"
                )

        else:

            await ctx.send(
                f"{self.bot.emoji.ERROR} | บอทยังไม่ได้เชื่อมต่อห้องเสียง",
                delete_after=10,
            )

    async def music_setup_function(self, message: discord.Message):

        try:
            if not await self._ensure_music_access_message(message):
                return

            # this cuntion will work like play command

            logger.debug(
                f"[music_setup] STEP 1 received | guild={message.guild.id}({message.guild.name}) "
                f"author={message.author.id}({message.author}) channel={message.channel.id} "
                f"content={message.content!r}"
            )

            try:

                await message.delete()

            except Exception:
                logger.warning(
                    f"Failed to delete the message in {message.guild.name} for music function"
                )

            music_data = self.bot.cache.music.get(str(message.guild.id), {})
            configured_voice_channel = None
            configured_voice_channel_id = self._as_int(
                music_data.get("music_setup_voice_channel_id")
            )
            if configured_voice_channel_id:
                configured_voice_channel = message.guild.get_channel(
                    configured_voice_channel_id
                )

            logger.debug(
                f"[music_setup] STEP 2 voice config | configured_voice_channel_id={configured_voice_channel_id} "
                f"resolved={'yes' if configured_voice_channel else 'no'} "
                f"author_voice={getattr(getattr(message.author, 'voice', None), 'channel', None)}"
            )

            destination = configured_voice_channel
            if destination is None:
                if not message.author.voice:
                    logger.debug("[music_setup] STEP 2a abort | author not in a voice channel")
                    return await message.channel.send(
                        f"{self.bot.emoji.ERROR} | {self.t(message.guild.id, 'music_err_need_voice')}",
                        delete_after=10,
                    )
                destination = message.author.voice.channel

                # destination = ctx.author.voice.channel

                # # Connect to the voice channel if not already connected

                # if not ctx.guild.voice_client:

                #     vc: wavelink.Player = await destination.connect(cls=wavelink.Player,timeout=60)

                #     vc.inactive_timeout = 10

                # else:

                #     vc: wavelink.Player = ctx.guild.voice_client

                #     # if the bot is another vc and not playing anything then move to the new vc

                #     if vc.channel.id != destination.id:

                #         if not vc.current:

                #             await vc.move_to(destination)

                #         else:

                #             return await ctx.reply(f"{self.bot.emoji.ERROR} | The bot is already playing in another voice channel.",delete_after=10)

            logger.debug(
                f"[music_setup] STEP 3 destination | channel={destination.id}({destination.name}) "
                f"existing_vc={'yes' if message.guild.voice_client else 'no'}"
            )

            if message.guild.id in self._voice_connecting_guilds and self._connect_lock_stale(message.guild.id):
                self._clear_connecting(message.guild.id)

            if message.guild.id in self._voice_connecting_guilds:
                logger.debug(
                    f"[music_setup] STEP 3 wait | connect already in progress for guild={message.guild.id}"
                )
                for _ in range(8):
                    await asyncio.sleep(1)
                    if message.guild.id not in self._voice_connecting_guilds:
                        break
                if message.guild.id in self._voice_connecting_guilds:
                    return await message.channel.send(
                        f"{self.bot.emoji.ERROR} | Voice connection is already in progress. Please wait a few seconds and try again.",
                        delete_after=8,
                    )

            # Pre-flight permission / capacity check so we don't wait 60s for a Discord-silent failure.
            me = message.guild.me
            perms = destination.permissions_for(me)
            missing = [
                name
                for name, ok in (
                    ("view_channel", perms.view_channel),
                    ("connect", perms.connect),
                    ("speak", perms.speak),
                )
                if not ok
            ]
            user_limit = getattr(destination, "user_limit", 0) or 0
            members_count = len(getattr(destination, "members", []) or [])
            channel_full = (
                user_limit
                and members_count >= user_limit
                and not perms.move_members
                and not perms.administrator
            )
            logger.debug(
                f"[music_setup] STEP 3.perms | channel={destination.id} "
                f"view={perms.view_channel} connect={perms.connect} speak={perms.speak} "
                f"move_members={perms.move_members} admin={perms.administrator} "
                f"members={members_count}/{user_limit} missing={missing} full={bool(channel_full)} "
                f"rtc_region={getattr(destination, 'rtc_region', None)}"
            )
            if missing:
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | I'm missing **{', '.join(missing)}** permission(s) on `{destination.name}`. Grant them and try again.",
                    delete_after=15,
                )
            if channel_full:
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | `{destination.name}` is full ({members_count}/{user_limit}). Increase the user limit or grant me Move Members.",
                    delete_after=15,
                )

            if not message.guild.voice_client:

                try:
                    preferred_region = os.getenv("MUSIC_RTC_REGION", "rotterdam")
                    current_region = getattr(destination, "rtc_region", None)
                    if preferred_region and current_region != preferred_region:
                        try:
                            await destination.edit(rtc_region=preferred_region)
                            logger.debug(
                                f"[music_setup] STEP 3.region | channel={destination.id} "
                                f"set rtc_region={preferred_region} (was {current_region})"
                            )
                        except Exception as e:
                            logger.warning(
                                f"[music_setup] STEP 3.region failed | err={type(e).__name__}: {e}"
                            )
                    logger.debug(
                        f"[music_setup] STEP 3a connecting | channel={destination.id} timeout=25"
                    )
                    self._set_connecting(message.guild.id)
                    try:
                        vc: wavelink.Player = await self._connect_with_node_retry(
                            destination, timeout=25
                        )
                    finally:
                        self._clear_connecting(message.guild.id)
                    logger.debug(
                        f"[music_setup] STEP 3b connected | connected={getattr(vc, 'connected', None)} "
                        f"channel={getattr(getattr(vc, 'channel', None), 'id', None)}"
                    )
                except CHANNEL_TIMEOUT_EXCEPTION as e:
                    self._clear_connecting(message.guild.id)
                    logger.error(
                        f"[music_setup] STEP 3b CONNECT TIMEOUT | guild={message.guild.id} "
                        f"channel={destination.id}({destination.name}) err={e!r}"
                    )
                    self._voice_connect_retry_after[message.guild.id] = (
                        datetime.datetime.now().timestamp() + 120
                    )
                    return await message.channel.send(
                        f"{self.bot.emoji.ERROR} | I could not join `{destination.name}`. Please check Connect/Speak permissions and channel region, then try again.",
                        delete_after=10,
                    )
                except Exception as e:
                    self._clear_connecting(message.guild.id)
                    logger.error(
                        f"[music_setup] STEP 3b CONNECT FAILED | guild={message.guild.id} "
                        f"channel={destination.id}({destination.name}) err={type(e).__name__}: {e}\n"
                        f"{traceback.format_exc()}"
                    )
                    return await message.channel.send(
                        f"{self.bot.emoji.ERROR} | I could not join `{destination.name}`. ({type(e).__name__})",
                        delete_after=10,
                    )
                self._apply_inactive_timeout(vc, message.guild.id)
                self._voice_connect_retry_after.pop(message.guild.id, None)

            else:

                vc: wavelink.Player = message.guild.voice_client

                self._apply_inactive_timeout(vc, message.guild.id)

                if vc.channel != destination:

                    if not self._has_active_voice_session(vc):
                        logger.debug(
                            f"[music_setup] STEP 3c moving | from={vc.channel.id} to={destination.id}"
                        )
                        await vc.move_to(destination)

                    else:

                        logger.debug(
                            "[music_setup] STEP 3c abort | bot already playing in another vc"
                        )
                        return await message.channel.send(
                            self._voice_busy_wait_message(vc),
                            delete_after=8,
                        )

            if not vc.connected:

                logger.warning(
                    f"[music_setup] STEP 3d not connected after connect | guild={message.guild.id}"
                )
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | {self.t(message.guild.id, 'music_err_connect_failed')}",
                    delete_after=5,
                )

            guild_id = getattr(getattr(message, "guild", None), "id", None)
            if guild_id is None:
                return
            await self._prune_stale_track_picks()
            search = (message.content or "").strip()

            if self._is_command_like_message(search):
                logger.debug("[music_setup] STEP 4 abort | command-like message ignored")
                return

            if not search:

                logger.debug("[music_setup] STEP 4 abort | empty search query")
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | กรุณาใส่คำค้นหาเพลง",
                    delete_after=5,
                )
            if not self._is_meaningful_music_query(search):
                logger.debug("[music_setup] STEP 4 abort | symbol-only search query")
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | กรุณาใส่คำค้นหาเพลงที่ชัดเจน",
                    delete_after=5,
                )

            users_no_prefix_subscription = self.bot.cache.users.get(
                str(message.author.id), {}
            ).get("no_prefix_subscription", None)

            guilds_subscription = self.bot.cache.guilds.get(
                str(guild_id), {}
            ).get("subscription", "free")

            if await self.handle_pending_track_pick_message(message):
                return

            if not users_no_prefix_subscription and guilds_subscription == "free":

                if is_link(search):

                    return await message.channel.send(
                        embed=discord.Embed(
                            description="แพ็กเกจฟรียังไม่รองรับการเล่นเพลงผ่านลิงก์",
                            color=color.red,
                        ),
                        view=discord.ui.View().add_item(
                            discord.ui.Button(
                                label="อัปเกรดพรีเมียม",
                                style=discord.ButtonStyle.url,
                                url=self.bot.urls.SUPPORT_SERVER,
                                emoji=self.bot.emoji.SUPPORT,
                            )
                        ),
                        delete_after=12,
                    )

            logger.debug(
                f"[music_setup] STEP 4 searching | query={search!r} strategy=adaptive"
            )
            try:
                result = await self._search_tracks(search)
            except Exception as e:
                logger.error(
                    f"[music_setup] STEP 4 SEARCH ERROR | query={search!r} "
                    f"err={type(e).__name__}: {e}\n{traceback.format_exc()}"
                )
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | ค้นหาไม่สำเร็จ ({type(e).__name__}).",
                    delete_after=5,
                )

            logger.debug(
                f"[music_setup] STEP 4b search results | count={len(result) if result else 0} "
                f"first_title={getattr(result[0], 'title', None) if result else None}"
            )

            if not result:
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | ไม่พบเพลงที่ค้นหา ลองพิมพ์ชื่อเต็มขึ้น หรือส่งลิงก์เพลงโดยตรง",
                    delete_after=8,
                )

            tracks_to_apply = (
                list(result) if is_link(search) and len(result) > 1 else [result[0]]
            )
            default_volume = (
                80
                if guilds_subscription == "free"
                else self.bot.cache.music.get(str(guild_id), {}).get("default_volume", 80)
            )
            changed_titles, skipped_count = await self._apply_tracks_to_player(
                vc=vc,
                tracks=tracks_to_apply,
                requester=message.author,
                default_volume=default_volume,
            )
            if not changed_titles:
                logger.debug("[music_setup] STEP 5 queue full")
                return await message.channel.send(
                    f"{self.bot.emoji.ERROR} | {self._queue_full_message_for_guild(guild_id)}",
                    delete_after=8,
                )

            await self.send_music_controls(
                message.guild,
                update_attachments=True,
                command_channel=message.channel,
            )
            summary = f"{self.bot.emoji.SUCCESS} | เพิ่มเพลงแล้ว: {changed_titles[0]}"
            if skipped_count:
                summary += f" (ข้าม {skipped_count} เพลง เพราะคิวเต็ม)"
            await message.channel.send(summary, delete_after=6)

            if len(result) > 1 and not is_link(search):
                candidates = list(result[: self.SEARCH_PICK_LIMIT])
                top_track = candidates[0]
                top_title = self._truncate_track_text(getattr(top_track, "title", "Unknown"), 70)
                top_author = self._truncate_track_text(getattr(top_track, "author", "Unknown"), 40)
                top_length = convert_ms_to_beautiful_time(getattr(top_track, "length", 0) or 0)
                gate_embed = self._music_embed(
                    message.guild,
                    "พบผลลัพธ์หลายเพลง",
                    (
                        f"คำค้นหา: **{search}**\n"
                        f"เพลงแนะนำอันดับแรก: **{top_title}** • {top_author} • `{top_length}`\n\n"
                        "กำลังเล่นเพลงแนะนำให้แล้ว ถ้าเพลงนี้ไม่ตรงกับที่ต้องการ ให้กดปุ่มด้านล่างเพื่อเปิดรายการเลือกเพลง"
                    ),
                    tone="info",
                    footer=f"หมดเวลา {self.PENDING_PICK_TTL_SECONDS} วิ",
                )
                gate_view = discord.ui.View(timeout=self.PENDING_PICK_TTL_SECONDS)
                required_voice_channel_id = self._as_int(
                    getattr(getattr(vc, "channel", None), "id", None)
                )
                open_picker_button = discord.ui.Button(
                    label="เพลงไม่ตรงกับที่ต้องการ",
                    style=discord.ButtonStyle.secondary,
                    emoji="🎯",
                )

                async def open_picker_callback(interaction: discord.Interaction):
                    if interaction.user.id != message.author.id:
                        return await interaction.response.send_message(
                            "ปุ่มนี้ใช้ได้เฉพาะคนที่พิมพ์ค้นหาเพลงเท่านั้น",
                            ephemeral=True,
                            delete_after=6,
                        )

                    current_pending = self._peek_track_pick(
                        guild_id, message.channel.id, message.author.id
                    )
                    if not current_pending:
                        return await interaction.response.send_message(
                            "หมดเวลาแล้ว พิมพ์ชื่อเพลงใหม่",
                            ephemeral=True,
                            delete_after=5,
                        )

                    await interaction.response.defer()

                    await self._send_track_pick_prompt(
                        guild=message.guild,
                        channel=message.channel,
                        guild_id=guild_id,
                        user_id=message.author.id,
                        query=search,
                        tracks=candidates,
                        gate_message_id=getattr(interaction.message, "id", None),
                        required_voice_channel_id=required_voice_channel_id,
                    )
                    try:
                        await interaction.message.delete()
                    except Exception:
                        pass

                open_picker_button.callback = open_picker_callback
                gate_view.add_item(open_picker_button)

                gate_message = await message.channel.send(
                    embed=gate_embed,
                    view=gate_view,
                    delete_after=self.PENDING_PICK_TTL_SECONDS,
                )
                self._remember_track_pick(
                    guild_id,
                    message.channel.id,
                    message.author.id,
                    query=search,
                    tracks=candidates,
                    mode="await_button",
                    gate_message_id=gate_message.id,
                    required_voice_channel_id=required_voice_channel_id,
                )
                return

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_group(
        name="music",
        help="คำสั่งที่เกี่ยวข้องกับระบบเพลง",
        invoke_without_command=True,
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=60, type=commands.BucketType.user)
    async def music_group(self, ctx: commands.Context):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "administrator"):

                return

            embed = discord.Embed(
                title="คำสั่งตั้งค่าระบบเพลง",
                description=f"รายการคำสั่งที่ใช้งานได้\n\n",
                color=color.green,
            )

            if hasattr(ctx.command, "commands"):

                for command in ctx.command.commands:

                    embed.description += f"**`{self.bot.BotConfig.PREFIX}{ctx.command.name} {command.name}` - {command.help}**\n"

            else:

                embed.description += f"**`{self.bot.BotConfig.PREFIX}{ctx.command.name}` - {ctx.command.help}**\n"

            embed.set_footer(
                text=f"SkylineBOT • Skyline Development",
                icon_url=self.bot.user.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @music_group.command(
        name="setup", help="ตั้งค่าห้องรับคำขอเพลงและห้องเสียงเป้าหมาย", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    async def music_setup(self, ctx: commands.Context):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "administrator"):

                return

            if ctx.interaction and not ctx.interaction.response.is_done():
                await self._safe_ctx_defer(ctx, ephemeral=True)

            music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

            if not music_data:

                await storage.music.insert(guild_id=ctx.guild.id)

                music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

            music_setup_image_path = (
                Path(__file__).resolve().parents[2] / "photos" / "music.png"
            )
            has_music_setup_image = music_setup_image_path.is_file()

            if music_data.get("music_setup_channel_id", None) and music_data.get("music_setup_voice_channel_id", None):

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | ตั้งค่าเพลงไว้แล้ว\nRequest Channel: <#{music_data.get('music_setup_channel_id')}>\nVoice Channel: <#{music_data.get('music_setup_voice_channel_id')}>",
                        color=color.red,
                    ).set_footer(
                        text=f"Use /music reset to reset music setup.",
                        icon_url=self.bot.user.display_avatar.url,
                    ),
                    delete_after=10,
                )

            waiting_message = await ctx.send(
                f"{self.bot.emoji.LOADING} | Creating music request + voice channels..."
            )

            try:

                music_setup_channel = await ctx.guild.create_text_channel(
                    name="music-requests"
                )
                music_voice_channel = await ctx.guild.create_voice_channel(
                    name="Music Room"
                )

            except Exception:
                logger.error(f"Traceback: {traceback.format_exc()}")

                if not ctx.interaction:

                    return await waiting_message.edit(
                        content=f"{self.bot.emoji.ERROR} | Failed to create music setup channels.",
                        delete_after=10,
                    )

                else:

                    return await ctx.send(
                        f"{self.bot.emoji.ERROR} | Failed to create music setup channels."
                    )

            await storage.music.update(
                id=music_data.get("id"),
                music_setup_channel_id=music_setup_channel.id,
                music_setup_voice_channel_id=music_voice_channel.id,
            )

            await waiting_message.edit(
                content=f"{self.bot.emoji.SUCCESS} | Music setup created.\nRequest Channel: <#{music_setup_channel.id}>\nVoice Channel: <#{music_voice_channel.id}>"
            )

            await self.send_music_controls(
                ctx.guild,
                end=True,
                command_channel=music_setup_channel,
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @music_group.command(
        name="reset", help="รีเซ็ตห้องรับคำขอเพลงและห้องเสียงเป้าหมาย", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    async def music_reset(self, ctx: commands.Context):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "administrator"):

                return

            if ctx.interaction and not ctx.interaction.response.is_done():
                await self._safe_ctx_defer(ctx, ephemeral=True)

            music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

            if not music_data:

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | ยังไม่ได้ตั้งค่าระบบเพลง",
                        color=color.red,
                    ).set_footer(
                        text=f"Use /music setup to setup music channels.",
                        icon_url=self.bot.user.display_avatar.url,
                    ),
                    delete_after=10,
                )

            if not music_data.get("music_setup_channel_id", None) and not music_data.get("music_setup_voice_channel_id", None):

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"{self.bot.emoji.ERROR} | ยังไม่ได้ตั้งค่าระบบเพลง",
                        color=color.red,
                    ).set_footer(
                        text=f"Use /music setup to setup music channels.",
                        icon_url=self.bot.user.display_avatar.url,
                    ),
                    delete_after=10,
                )

            waiting_message = await ctx.send(
                f"{self.bot.emoji.LOADING} | Deleting music setup channels..."
            )

            try:

                music_setup_channel = ctx.guild.get_channel(
                    music_data.get("music_setup_channel_id")
                )
                music_voice_channel = ctx.guild.get_channel(
                    music_data.get("music_setup_voice_channel_id")
                )

                if music_setup_channel:

                    await music_setup_channel.delete()
                if music_voice_channel:
                    await music_voice_channel.delete()
            except Exception:
                logger.error(f"Traceback: {traceback.format_exc()}")

                if not ctx.interaction:

                    return await waiting_message.edit(
                        content=f"{self.bot.emoji.ERROR} | Failed to delete music setup channels.",
                        delete_after=10,
                    )

                else:

                    return await ctx.send(
                        f"{self.bot.emoji.ERROR} | Failed to delete music setup channels."
                    )

            await storage.music.update(
                id=music_data.get("id"),
                music_setup_channel_id="",
                music_setup_voice_channel_id="",
            )

            await waiting_message.edit(
                content=f"{self.bot.emoji.SUCCESS} | Music setup channels have been deleted."
            )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @music_group.command(
        name="settings",
        help="แสดงการตั้งค่าระบบเพลง",
        with_app_command=True,
        aliases=["config", "setting"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=60, type=commands.BucketType.guild)
    async def music_settings(self, ctx: commands.Context):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "administrator"):

                return

            if ctx.interaction and not ctx.interaction.response.is_done():
                try:
                    await self._safe_ctx_defer(ctx, ephemeral=True)
                except discord.InteractionResponded:
                    pass

            music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

            if not music_data:

                await storage.music.insert(guild_id=ctx.guild.id)

                music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

            music_setup_image_path = (
                Path(__file__).resolve().parents[2] / "photos" / "music.png"
            )

            async def get_embed():

                music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

                embed = discord.Embed(
                    title="🎛️ ตั้งค่าระบบเพลง",
                    description="ปรับแต่งห้องเพลง ปุ่มควบคุม และการเล่นอัตโนมัติสำหรับเซิร์ฟเวอร์นี้",
                    color=color.green,
                )

                embed.add_field(
                    name="🔊 ระดับเสียงเริ่มต้น",
                    value=f"`{music_data.get('default_volume',80) if music_data.get('default_volume') else '80'}`",
                    inline=True,
                )

                embed.add_field(
                    name="💬 ห้องคำสั่งเพลง",
                    value=(
                        f"<#{music_data.get('music_setup_channel_id')}>"
                        if music_data.get("music_setup_channel_id")
                        else "`ยังไม่ได้ตั้งค่าห้องข้อความ`"
                    ),
                    inline=True,
                )

                embed.add_field(
                    name="🎙️ ห้องเสียงเป้าหมาย",
                    value=(
                        f"<#{music_data.get('music_setup_voice_channel_id')}>"
                        if music_data.get("music_setup_voice_channel_id")
                        else "`ยังไม่ได้ตั้งค่าห้องเสียง`"
                    ),
                    inline=True,
                )

                setup_mode_enabled = bool(
                    music_data.get("music_setup_channel_id")
                    and music_data.get("music_setup_voice_channel_id")
                )
                embed.add_field(
                    name="🧩 โหมดห้องเพลง",
                    value=(
                        f"{self.bot.emoji.ENABLED} `เปิดใช้งาน (ใช้เฉพาะห้องที่ตั้งไว้)`"
                        if setup_mode_enabled
                        else f"{self.bot.emoji.DISABLED} `ปิดอยู่ (ใช้คำสั่งได้ทุกห้อง)`"
                    ),
                    inline=True,
                )

                autoplay_enabled = bool(music_data.get("default_autoplay", False))
                embed.add_field(
                    name="🔁 เล่นอัตโนมัติ",
                    value=(
                        f"{self.bot.emoji.ENABLED} `เปิดใช้งาน`"
                        if autoplay_enabled
                        else f"{self.bot.emoji.DISABLED} `ปิดใช้งาน`"
                    ),
                    inline=True,
                )

                embed.set_footer(
                    text=f"เรียกดูโดย {ctx.author}",
                    icon_url=ctx.author.display_avatar.url,
                )

                embed.set_author(
                    name=ctx.guild.name,
                    icon_url=(
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    ),
                    url=self.bot.urls.WEBSITE,
                )

                embed.set_thumbnail(
                    url=(
                        "attachment://music.png"
                        if music_setup_image_path.is_file()
                        else (
                            ctx.guild.icon.url
                            if ctx.guild.icon
                            else self.bot.user.display_avatar.url
                        )
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

                    music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

                    view = discord.ui.View(timeout=200)

                    default_volume_button = discord.ui.Button(
                        label="ระดับเสียงเริ่มต้น",
                        style=discord.ButtonStyle.primary,
                        emoji=self.bot.emoji.MASTER_VOLUME,
                        row=0,
                    )

                    autoplay_enabled = bool(music_data.get("default_autoplay", False))
                    autoplay_toggle_button = discord.ui.Button(
                        label=(
                            "เล่นอัตโนมัติ: ปิด"
                            if autoplay_enabled
                            else "เล่นอัตโนมัติ: เปิด"
                        ),
                        style=(
                            discord.ButtonStyle.danger
                            if autoplay_enabled
                            else discord.ButtonStyle.success
                        ),
                        emoji=(
                            self.bot.emoji.DISABLED
                            if autoplay_enabled
                            else self.bot.emoji.ENABLED
                        ),
                        row=0,
                    )

                    setup_mode_enabled = bool(
                        music_data.get("music_setup_channel_id")
                        and music_data.get("music_setup_voice_channel_id")
                    )
                    setup_mode_toggle_button = discord.ui.Button(
                        label=(
                            "โหมดห้องเพลง: ปิด"
                            if setup_mode_enabled
                            else "โหมดห้องเพลง: เปิด"
                        ),
                        style=(
                            discord.ButtonStyle.danger
                            if setup_mode_enabled
                            else discord.ButtonStyle.success
                        ),
                        emoji=(
                            self.bot.emoji.DISABLED
                            if setup_mode_enabled
                            else self.bot.emoji.ENABLED
                        ),
                        row=0,
                    )

                    music_channels = []

                    if music_data.get("music_setup_channel_id"):

                        try:

                            music_channel = ctx.guild.get_channel(
                                self._as_int(music_data.get("music_setup_channel_id"))
                            )

                            if music_channel:

                                music_channels.append(music_channel)

                        except Exception:
                            logger.error(f"Traceback: {traceback.format_exc()}")

                    music_channel_Select = discord.ui.ChannelSelect(
                        placeholder="เลือกห้องข้อความสำหรับรับคำสั่งเพลง",
                        min_values=1,
                        max_values=1,
                        row=1,
                        channel_types=[discord.ChannelType.text],
                        default_values=music_channels if music_channels else None,
                    )

                    voice_channels = []

                    if music_data.get("music_setup_voice_channel_id"):

                        try:

                            music_voice_channel = ctx.guild.get_channel(
                                self._as_int(
                                    music_data.get("music_setup_voice_channel_id")
                                )
                            )

                            if music_voice_channel:

                                voice_channels.append(music_voice_channel)

                        except Exception:
                            logger.error(f"Traceback: {traceback.format_exc()}")

                    music_voice_Select = discord.ui.ChannelSelect(
                        placeholder="เลือกห้องเสียงที่จะให้บอทเข้าประจำ",
                        min_values=1,
                        max_values=1,
                        row=2,
                        channel_types=[discord.ChannelType.voice],
                        default_values=voice_channels if voice_channels else None,
                    )

                    cancle_button = discord.ui.Button(
                        label="ปิดเมนู",
                        style=discord.ButtonStyle.gray,
                        emoji=self.bot.emoji.CANCLED,
                        row=0,
                    )

                    default_volume_button.callback = (
                        lambda i: default_volume_button_callback(i)
                    )
                    autoplay_toggle_button.callback = (
                        lambda i: autoplay_toggle_button_callback(i)
                    )
                    setup_mode_toggle_button.callback = (
                        lambda i: setup_mode_toggle_button_callback(i)
                    )

                    music_channel_Select.callback = (
                        lambda i: music_channel_Select_callback(i)
                    )
                    music_voice_Select.callback = (
                        lambda i: music_voice_Select_callback(i)
                    )

                    cancle_button.callback = lambda i: cancle_button_callback(i)

                    view.add_item(default_volume_button)
                    view.add_item(autoplay_toggle_button)
                    view.add_item(setup_mode_toggle_button)

                    view.add_item(music_channel_Select)
                    view.add_item(music_voice_Select)

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

            async def safe_update_settings_message(
                interaction: discord.Interaction, disabled: bool = False
            ):

                try:
                    for attempt in range(3):
                        try:
                            await interaction.message.edit(
                                embed=await get_embed(), view=await get_view(disabled=disabled)
                            )
                            return True
                        except discord.NotFound:
                            return False
                        except discord.HTTPException as e:
                            if e.status == 503 and attempt < 2:
                                await asyncio.sleep(1.2)
                                continue
                            raise
                except Exception as e:
                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )
                    try:
                        await interaction.followup.send(
                            embed=discord.Embed(
                                description="Discord API ใช้งานไม่ได้ชั่วคราว กรุณาลองใหม่อีกครั้งในอีกไม่กี่วินาที",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )
                    except Exception:
                        pass
                    return False

            async def default_volume_button_callback(interaction: discord.Interaction):

                try:

                    owner_id = getattr(ctx.author, "id", None)
                    actor_id = getattr(interaction.user, "id", None)
                    if owner_id is None or actor_id != owner_id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="ปุ่มนี้ใช้ได้เฉพาะคนที่เปิดเมนูนี้เท่านั้น",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    guild_id = (
                        interaction.guild.id
                        if interaction.guild
                        else (ctx.guild.id if ctx.guild else None)
                    )
                    if guild_id is None:
                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คำสั่งนี้ใช้ได้เฉพาะภายในเซิร์ฟเวอร์เท่านั้น",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )
                    guilds_subscription = self.bot.cache.guilds.get(
                        str(guild_id), {}
                    ).get("subscription", "free")

                    if guilds_subscription == "free":

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="แพ็กเกจฟรียังไม่สามารถเปลี่ยนระดับเสียงเริ่มต้นได้",
                                color=color.red,
                            ),
                            view=discord.ui.View().add_item(
                                discord.ui.Button(
                                    label="อัปเกรดพรีเมียม",
                                    style=discord.ButtonStyle.link,
                                    url=self.bot.urls.SUPPORT_SERVER,
                                    emoji=self.bot.emoji.SUPPORT,
                                )
                            ),
                            ephemeral=True,
                        )

                    class set_default_volume_modal(
                        discord.ui.Modal, title="ตั้งค่าระดับเสียงเริ่มต้น"
                    ):

                        new_volume = discord.ui.TextInput(
                            label="กรอกระดับเสียงใหม่",
                            placeholder="ใส่ค่า 1 - 100",
                            required=True,
                            style=discord.TextStyle.short,
                            row=0,
                            default=str(
                                self.bot.cache.music.get(str(guild_id), {}).get(
                                    "default_volume", 80
                                )
                                if self.bot.cache.music.get(str(guild_id), {}).get(
                                    "default_volume"
                                )
                                else "80"
                            ),
                        )

                        bot = self.bot

                        async def on_submit(self, interaction: discord.Interaction):

                            try:

                                owner_id = getattr(ctx.author, "id", None)
                                actor_id = getattr(interaction.user, "id", None)
                                if owner_id is None or actor_id != owner_id:

                                    return await interaction.response.send_message(
                                        embed=discord.Embed(
                                            description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                            color=color.red,
                                        ),
                                        ephemeral=True,
                                    )

                                try:

                                    new_volume = int(self.new_volume.value)

                                except Exception:
                                    return await interaction.response.send_message(
                                        embed=discord.Embed(
                                            description="ตัวเลขไม่ถูกต้อง",
                                            color=color.red,
                                        ),
                                        ephemeral=True,
                                        delete_after=5,
                                    )

                                if 0 < new_volume > 100:

                                    return await interaction.response.send_message(
                                        embed=discord.Embed(
                                            description="ตัวเลขต้องอยู่ระหว่าง 0 ถึง 100",
                                            color=color.red,
                                        ),
                                        ephemeral=True,
                                        delete_after=5,
                                    )

                                await interaction.response.defer()

                                music_data = self.bot.cache.music.get(str(guild_id), {})

                                print(f"Updating the default volume to {new_volume}")

                                await storage.music.update(
                                    id=music_data.get("id"),
                                    guild_id=guild_id,
                                    default_volume=new_volume,
                                )

                                print(f"Updated the default volume to {new_volume}")

                                await safe_update_settings_message(interaction)

                            except Exception as e:

                                logger.error(
                                    f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info())[0][1]}: {e}"
                                )

                    await interaction.response.send_modal(set_default_volume_modal())

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def music_channel_Select_callback(interaction: discord.Interaction):

                try:

                    owner_id = getattr(ctx.author, "id", None)
                    actor_id = getattr(interaction.user, "id", None)
                    if owner_id is None or actor_id != owner_id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    music_data = self.bot.cache.music.get(str(ctx.guild.id), {})
                    previous_channel_id = self._as_int(
                        music_data.get("music_setup_channel_id")
                    )
                    previous_message_id = self._as_int(
                        music_data.get("music_setup_message_id")
                    )

                    channel = interaction.data["values"]
                    selected_channel_id = self._as_int(channel[0]) if channel else None
                    if selected_channel_id is None:
                        return await interaction.followup.send(
                            embed=discord.Embed(
                                description="เลือกห้องข้อความไม่ถูกต้อง",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await storage.music.update(
                        id=music_data.get("id"),
                        guild_id=ctx.guild.id,
                        music_setup_channel_id=selected_channel_id,
                        music_setup_message_id=None,
                    )

                    # Remove old controller message from previous request channel
                    if (
                        previous_channel_id
                        and previous_message_id
                        and previous_channel_id != selected_channel_id
                    ):
                        old_channel = ctx.guild.get_channel(previous_channel_id)
                        if old_channel:
                            try:
                                old_message = await old_channel.fetch_message(
                                    previous_message_id
                                )
                                await old_message.delete()
                            except Exception:
                                pass

                    await self.send_music_controls(
                        ctx.guild,
                        end=True,
                        command_channel=ctx.guild.get_channel(selected_channel_id),
                    )

                    await safe_update_settings_message(interaction)

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def setup_mode_toggle_button_callback(interaction: discord.Interaction):

                try:

                    owner_id = getattr(ctx.author, "id", None)
                    actor_id = getattr(interaction.user, "id", None)
                    if owner_id is None or actor_id != owner_id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    music_data = self.bot.cache.music.get(str(ctx.guild.id), {})
                    setup_mode_enabled = bool(
                        music_data.get("music_setup_channel_id")
                        and music_data.get("music_setup_voice_channel_id")
                    )

                    if setup_mode_enabled:
                        previous_channel_id = self._as_int(
                            music_data.get("music_setup_channel_id")
                        )
                        previous_message_id = self._as_int(
                            music_data.get("music_setup_message_id")
                        )

                        await storage.music.update(
                            id=music_data.get("id"),
                            guild_id=ctx.guild.id,
                            music_setup_channel_id="",
                            music_setup_voice_channel_id="",
                            music_setup_message_id=None,
                        )

                        if previous_channel_id and previous_message_id:
                            old_channel = ctx.guild.get_channel(previous_channel_id)
                            if old_channel:
                                try:
                                    old_message = await old_channel.fetch_message(
                                        previous_message_id
                                    )
                                    await old_message.delete()
                                except Exception:
                                    pass

                        await safe_update_settings_message(interaction)

                        await interaction.followup.send(
                            embed=discord.Embed(
                                description="ปิดโหมดตั้งค่าห้องเพลงแล้ว บอทจะรับคำขอเพลงได้ทุกห้อง",
                                color=color.green,
                            ),
                            ephemeral=True,
                        )
                    else:
                        setup_channel_id = self._as_int(
                            music_data.get("music_setup_channel_id")
                        )
                        setup_voice_channel_id = self._as_int(
                            music_data.get("music_setup_voice_channel_id")
                        )

                        if not setup_channel_id or not setup_voice_channel_id:
                            return await interaction.followup.send(
                                embed=discord.Embed(
                                    description="กรุณาเลือกทั้งห้องข้อความรับคำขอ และห้องเสียงเป้าหมายก่อน",
                                    color=color.red,
                                ),
                                ephemeral=True,
                            )

                        setup_channel = ctx.guild.get_channel(setup_channel_id)
                        if isinstance(setup_channel, discord.TextChannel):
                            await self.send_music_controls(
                                ctx.guild,
                                end=True,
                                command_channel=setup_channel,
                            )

                        await safe_update_settings_message(interaction)

                        await interaction.followup.send(
                            embed=discord.Embed(
                                description="เปิดโหมดตั้งค่าห้องเพลงแล้ว ระบบจะรับคำขอเพลงจากห้องที่ตั้งค่าไว้",
                                color=color.green,
                            ),
                            ephemeral=True,
                        )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def autoplay_toggle_button_callback(interaction: discord.Interaction):

                try:

                    owner_id = getattr(ctx.author, "id", None)
                    actor_id = getattr(interaction.user, "id", None)
                    if owner_id is None or actor_id != owner_id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    music_data = self.bot.cache.music.get(str(ctx.guild.id), {})
                    new_autoplay_state = not bool(
                        music_data.get("default_autoplay", False)
                    )

                    await storage.music.update(
                        id=music_data.get("id"),
                        guild_id=ctx.guild.id,
                        default_autoplay=new_autoplay_state,
                    )

                    await safe_update_settings_message(interaction)

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def music_voice_Select_callback(interaction: discord.Interaction):

                try:

                    owner_id = getattr(ctx.author, "id", None)
                    actor_id = getattr(interaction.user, "id", None)
                    if owner_id is None or actor_id != owner_id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์กดปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await interaction.response.defer()

                    music_data = self.bot.cache.music.get(str(ctx.guild.id), {})

                    channel = interaction.data["values"]
                    selected_channel_id = self._as_int(channel[0]) if channel else None
                    if selected_channel_id is None:
                        return await interaction.followup.send(
                            embed=discord.Embed(
                                description="เลือกห้องเสียงไม่ถูกต้อง",
                                color=color.red,
                            ),
                            ephemeral=True,
                        )

                    await storage.music.update(
                        id=music_data.get("id"),
                        guild_id=ctx.guild.id,
                        music_setup_voice_channel_id=selected_channel_id,
                    )

                    await safe_update_settings_message(interaction)

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    owner_id = getattr(ctx.author, "id", None)
                    actor_id = getattr(interaction.user, "id", None)
                    if owner_id is None or actor_id != owner_id:

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

                    await safe_update_settings_message(interaction, disabled=True)

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            embed = await get_embed()

            view = await get_view()

            send_kwargs = {"embed": embed, "view": view}
            if music_setup_image_path.is_file():
                send_kwargs["file"] = discord.File(
                    str(music_setup_image_path), filename="music.png"
                )

            message = await ctx.send(**send_kwargs)

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(
                        embed=await get_embed(), view=await get_view(disabled=True)
                    )

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @music_group.command(
        name="playlist_create",
        help="สร้างเพลย์ลิสต์ส่วนตัว (โควตาตามแพลน)",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(name="ชื่อเพลย์ลิสต์ (เช่น fav, chill, workout)")
    async def music_playlist_create(self, ctx: commands.Context, *, name: str):
        if not await self._ensure_music_access_ctx(ctx):
            return
        if ctx.interaction and not ctx.interaction.response.is_done():
            await self._safe_ctx_defer(ctx)
        guild_id = int(getattr(getattr(ctx, "guild", None), "id", 0) or 0)
        max_playlists, _max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)

        ok, message, playlist = await user_music_playlists.create_user_playlist(
            ctx.author.id,
            name,
            max_playlists=max_playlists,
        )
        quota = await self._user_playlist_quota_text(ctx.author.id, guild_id)
        details = message
        if playlist:
            details += (
                f"\nName: **{playlist.get('name')}**"
                f"\nSlug: `{playlist.get('slug')}`"
            )
        details += f"\n\n{quota}"
        await ctx.reply(
            embed=self._music_embed(
                ctx.guild,
                "Playlist Create",
                details,
                tone="success" if ok else "warning",
            ),
            delete_after=14 if ok else 18,
        )

    @music_group.command(
        name="playlist_list",
        help="ดูรายการเพลย์ลิสต์ของคุณ และดูเพลงภายในเพลย์ลิสต์",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(
        playlist="ระบุ slug หรือชื่อเพลย์ลิสต์เพื่อดูรายการเพลง (ไม่ใส่ = ดูทั้งหมด)"
    )
    @discord.app_commands.autocomplete(playlist=_playlist_name_autocomplete)
    async def music_playlist_list(
        self, ctx: commands.Context, *, playlist: str | None = None
    ):
        if not await self._ensure_music_access_ctx(ctx):
            return
        if ctx.interaction and not ctx.interaction.response.is_done():
            await self._safe_ctx_defer(ctx)
        guild_id = int(getattr(getattr(ctx, "guild", None), "id", 0) or 0)
        _max_playlists, max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)

        if playlist:
            row = await user_music_playlists.get_user_playlist(ctx.author.id, playlist)
            if not row:
                return await ctx.reply(
                    f"{self.bot.emoji.ERROR} | Playlist not found.",
                    delete_after=10,
                )
            entries = list(row.get("items") or [])
            if not entries:
                details = (
                    f"Playlist: **{row.get('name')}** (`{row.get('slug')}`)\n"
                    f"This playlist is empty."
                )
            else:
                lines = [
                    self._playlist_entry_line(entry, index)
                    for index, entry in enumerate(entries[:30], start=1)
                ]
                extra = ""
                if len(entries) > 30:
                    extra = f"\n... and {len(entries) - 30} more item(s)."
                details = (
                    f"Playlist: **{row.get('name')}** (`{row.get('slug')}`)\n"
                    f"Items: {len(entries)}/{max_items_per_playlist}\n\n"
                    + "\n".join(lines)
                    + extra
                )
            return await ctx.reply(
                embed=self._music_embed(ctx.guild, "Playlist Items", details, tone="info")
            )

        rows = await user_music_playlists.list_user_playlists(ctx.author.id)
        quota = await self._user_playlist_quota_text(ctx.author.id, guild_id)
        if not rows:
            return await ctx.reply(
                embed=self._music_embed(
                    ctx.guild,
                    "Your Playlists",
                    "You have no playlist yet.\nUse `/music playlist_create` first.\n\n"
                    + quota,
                    tone="warning",
                ),
                delete_after=12,
            )

        lines: list[str] = []
        for row in rows[: self.USER_PLAYLIST_LIMIT]:
            items = list(row.get("items") or [])
            lines.append(
                f"`{row.get('slug')}` • **{row.get('name')}** "
                f"({len(items)}/{max_items_per_playlist})"
            )
        details = "\n".join(lines) + f"\n\n{quota}"
        await ctx.reply(
            embed=self._music_embed(ctx.guild, "Your Playlists", details, tone="info")
        )

    @music_group.command(
        name="playlist_add",
        help="Add a song or URL to your personal playlist (เพิ่มเพลงหรือ URL ลงเพลย์ลิสต์ส่วนตัว)",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=8, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(
        playlist="slug หรือชื่อเพลย์ลิสต์",
        item="ชื่อเพลง, URL เพลง, หรือ URL playlist YouTube",
    )
    @discord.app_commands.autocomplete(playlist=_playlist_name_autocomplete)
    async def music_playlist_add(
        self, ctx: commands.Context, playlist: str, *, item: str
    ):
        if not await self._ensure_music_access_ctx(ctx):
            return
        if ctx.interaction and not ctx.interaction.response.is_done():
            await self._safe_ctx_defer(ctx)
        guild_id = int(getattr(getattr(ctx, "guild", None), "id", 0) or 0)
        _max_playlists, max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)

        ok, message, row = await user_music_playlists.add_item_to_playlist(
            ctx.author.id,
            playlist,
            item,
            max_items_per_playlist=max_items_per_playlist,
        )
        details = message
        if row:
            details += (
                f"\nPlaylist: **{row.get('name')}** (`{row.get('slug')}`)"
                f"\nItems: {len(list(row.get('items') or []))}/{max_items_per_playlist}"
            )
        details += f"\n\n{await self._user_playlist_quota_text(ctx.author.id, guild_id)}"
        await ctx.reply(
            embed=self._music_embed(
                ctx.guild,
                "Playlist Add",
                details,
                tone="success" if ok else "warning",
            ),
            delete_after=16 if not ok else 12,
        )

    @music_group.command(
        name="playlist_remove",
        help="ลบเพลงจากเพลย์ลิสต์ด้วยลำดับ เช่น 1, 1 3 5, 1-4",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(
        playlist="slug หรือชื่อเพลย์ลิสต์",
        indexes="ตัวอย่าง: 1, 2 4 5, 1-3",
    )
    @discord.app_commands.autocomplete(playlist=_playlist_name_autocomplete)
    async def music_playlist_remove(
        self, ctx: commands.Context, playlist: str, *, indexes: str
    ):
        if not await self._ensure_music_access_ctx(ctx):
            return
        if ctx.interaction and not ctx.interaction.response.is_done():
            await self._safe_ctx_defer(ctx)
        guild_id = int(getattr(getattr(ctx, "guild", None), "id", 0) or 0)
        _max_playlists, max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)

        row = await user_music_playlists.get_user_playlist(ctx.author.id, playlist)
        if not row:
            return await ctx.reply(
                f"{self.bot.emoji.ERROR} | Playlist not found.",
                delete_after=10,
            )
        entries = list(row.get("items") or [])
        if not entries:
            return await ctx.reply(
                f"{self.bot.emoji.ERROR} | Playlist is empty.",
                delete_after=8,
            )
        picks, parse_error = self._parse_pick_input(indexes, len(entries))
        if picks is None:
            if parse_error == "out_of_range":
                return await ctx.reply(
                    f"{self.bot.emoji.ERROR} | Index out of range.",
                    delete_after=8,
                )
            return await ctx.reply(
                f"{self.bot.emoji.ERROR} | Invalid format. Example: `1`, `1 3 5`, `1-4`",
                delete_after=10,
            )
        if picks == []:
            return await ctx.reply(
                f"{self.bot.emoji.SUCCESS} | Cancelled.",
                delete_after=6,
            )

        ok, message, updated_row, _removed_count = (
            await user_music_playlists.remove_items_from_playlist(
                ctx.author.id, playlist, picks
            )
        )
        details = message
        if updated_row:
            details += (
                f"\nPlaylist: **{updated_row.get('name')}** (`{updated_row.get('slug')}`)"
                f"\nItems left: {len(list(updated_row.get('items') or []))}/{max_items_per_playlist}"
            )
        await ctx.reply(
            embed=self._music_embed(
                ctx.guild,
                "Playlist Remove",
                details,
                tone="success" if ok else "warning",
            ),
            delete_after=14 if not ok else 10,
        )

    @music_group.command(
        name="playlist_delete",
        help="ลบเพลย์ลิสต์ส่วนตัว",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(playlist="slug หรือชื่อเพลย์ลิสต์")
    @discord.app_commands.autocomplete(playlist=_playlist_name_autocomplete)
    async def music_playlist_delete(self, ctx: commands.Context, *, playlist: str):
        if not await self._ensure_music_access_ctx(ctx):
            return
        if ctx.interaction and not ctx.interaction.response.is_done():
            await self._safe_ctx_defer(ctx)
        guild_id = int(getattr(getattr(ctx, "guild", None), "id", 0) or 0)

        ok, message = await user_music_playlists.delete_user_playlist(
            ctx.author.id, playlist
        )
        await ctx.reply(
            embed=self._music_embed(
                ctx.guild,
                "Playlist Delete",
                f"{message}\n\n{await self._user_playlist_quota_text(ctx.author.id, guild_id)}",
                tone="success" if ok else "warning",
            ),
            delete_after=12 if not ok else 8,
        )

    @music_group.command(
        name="playlist_play",
        help="เล่นเพลงจากเพลย์ลิสต์ของคุณ (ทั้งลิสต์หรือเลือกบางเพลง)",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(
        playlist="slug หรือชื่อเพลย์ลิสต์",
        mode="all หรือ selected",
        picks="ใส่เฉพาะตอน mode=selected เช่น 1, 1 3 5, 1-4",
    )
    @discord.app_commands.choices(
        mode=[
            discord.app_commands.Choice(name="all (ทั้งเพลย์ลิสต์)", value="all"),
            discord.app_commands.Choice(
                name="selected (เลือกเฉพาะบางเพลง)", value="selected"
            ),
        ]
    )
    @discord.app_commands.autocomplete(playlist=_playlist_name_autocomplete)
    async def music_playlist_play(
        self,
        ctx: commands.Context,
        playlist: str,
        mode: str = "all",
        *,
        picks: str = "",
    ):
        async def _reply_safe(*args, **kwargs):
            try:
                return await ctx.reply(*args, **kwargs)
            except (discord.NotFound, discord.HTTPException) as send_error:
                if getattr(send_error, "code", None) not in {10008, 10062}:
                    raise

                logger.warning(
                    "playlist_play reply fallback triggered "
                    f"(guild={getattr(getattr(ctx, 'guild', None), 'id', 'unknown')} "
                    f"user={getattr(getattr(ctx, 'author', None), 'id', 'unknown')} "
                    f"code={getattr(send_error, 'code', None)})"
                )

                channel = getattr(ctx, "channel", None)
                if channel is None:
                    return None

                fallback_kwargs = dict(kwargs)
                fallback_kwargs.pop("reference", None)
                fallback_kwargs.pop("mention_author", None)
                fallback_kwargs.pop("ephemeral", None)
                try:
                    return await channel.send(*args, **fallback_kwargs)
                except Exception:
                    logger.warning(
                        "playlist_play fallback channel.send failed: "
                        f"{traceback.format_exc()}"
                    )
                    return None

        if not await self._ensure_music_access_ctx(ctx):
            return
        if ctx.interaction and not ctx.interaction.response.is_done():
            await self._safe_ctx_defer(ctx)

        row = await user_music_playlists.get_user_playlist(ctx.author.id, playlist)
        if not row:
            return await _reply_safe(
                f"{self.bot.emoji.ERROR} | Playlist not found.",
                delete_after=10,
            )

        entries = list(row.get("items") or [])
        if not entries:
            return await _reply_safe(
                f"{self.bot.emoji.ERROR} | Playlist is empty.",
                delete_after=8,
            )

        selected_entries = entries
        mode_text = str(mode or "all").strip().lower()
        if mode_text in {"selected", "select", "pick", "choice"}:
            parsed, parse_error = self._parse_pick_input(picks, len(entries))
            if parsed is None:
                if parse_error == "out_of_range":
                    return await _reply_safe(
                        f"{self.bot.emoji.ERROR} | Index out of range.",
                        delete_after=8,
                    )
                return await _reply_safe(
                    f"{self.bot.emoji.ERROR} | Please provide picks like `1`, `1 3`, `1-4`.",
                    delete_after=10,
                )
            if parsed == []:
                return await _reply_safe(
                    f"{self.bot.emoji.SUCCESS} | Cancelled.",
                    delete_after=6,
                )
            selected_entries = [entries[index - 1] for index in parsed]

        guilds_subscription = self.bot.cache.guilds.get(str(ctx.guild.id), {}).get(
            "subscription", "free"
        )
        users_no_prefix_subscription = self.bot.cache.users.get(
            str(ctx.author.id), {}
        ).get("no_prefix_subscription", None)
        if guilds_subscription == "free" and not users_no_prefix_subscription:
            if any(
                str(item.get("kind") or "").strip().lower() == "url"
                for item in selected_entries
            ):
                return await _reply_safe(
                    embed=discord.Embed(
                        description="แพ็กเกจฟรียังไม่รองรับการเล่นเพลงผ่านลิงก์",
                        color=color.red,
                    ),
                    view=discord.ui.View().add_item(
                        discord.ui.Button(
                            label="อัปเกรดพรีเมียม",
                            style=discord.ButtonStyle.url,
                            url=self.bot.urls.SUPPORT_SERVER,
                            emoji=self.bot.emoji.SUPPORT,
                        )
                    ),
                )

        vc = await self._connect_voice_for_ctx(ctx)
        if not vc:
            return

        tracks, unresolved_items = await self._resolve_playlist_entries_to_tracks(
            selected_entries
        )
        if not tracks:
            unresolved_summary = ""
            if unresolved_items:
                unresolved_summary = f"\nUnresolved item(s): {len(unresolved_items)}"
            return await _reply_safe(
                f"{self.bot.emoji.ERROR} | ไม่พบเพลงจากเพลย์ลิสต์ที่เลือก{unresolved_summary}",
                delete_after=12,
            )

        default_volume = (
            80
            if guilds_subscription == "free"
            else self.bot.cache.music.get(str(ctx.guild.id), {}).get(
                "default_volume", 80
            )
        )
        changed_titles, skipped_count = await self._apply_tracks_to_player(
            vc=vc,
            tracks=tracks,
            requester=ctx.author,
            default_volume=default_volume,
        )
        if not changed_titles:
            return await _reply_safe(
                f"{self.bot.emoji.LIMIT} | {self._queue_full_message_for_guild(ctx.guild.id)}",
                delete_after=10,
            )

        await self.send_music_controls(
            ctx.guild,
            update_attachments=True,
            command_channel=ctx.channel,
        )
        await user_music_playlists.mark_playlist_used(ctx.author.id, row.get("slug"))

        unresolved_count = len(unresolved_items)
        summary = (
            f"{self.bot.emoji.SUCCESS} | Added {len(changed_titles)} track(s) from playlist **{row.get('name')}**."
        )
        if unresolved_count:
            summary += f" Unresolved: {unresolved_count} item(s)."
        if skipped_count:
            summary += f" Queue full skipped: {skipped_count} track(s)."
        await _reply_safe(summary, delete_after=14)

    @music_group.command(
        name="playlist_savecurrent",
        help="บันทึกเพลงที่กำลังเล่นลงเพลย์ลิสต์ (ไม่ใส่ชื่อ = รายการโปรด)",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=6, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(
        playlist="slug หรือชื่อเพลย์ลิสต์ (เว้นว่างเพื่อใช้รายการโปรด)"
    )
    @discord.app_commands.autocomplete(playlist=_playlist_name_autocomplete)
    async def music_playlist_savecurrent(
        self, ctx: commands.Context, *, playlist: str | None = None
    ):
        if not await self._ensure_music_access_ctx(ctx):
            return
        if ctx.interaction and not ctx.interaction.response.is_done():
            await self._safe_ctx_defer(ctx)
        guild_id = int(getattr(getattr(ctx, "guild", None), "id", 0) or 0)
        max_playlists, max_items_per_playlist = self._music_playlist_limits_for_guild(guild_id)

        vc: wavelink.Player | None = getattr(ctx.guild, "voice_client", None)
        current_track = getattr(vc, "current", None) if vc else None
        if not current_track:
            return await ctx.reply(
                f"{self.bot.emoji.ERROR} | No active track to save.",
                delete_after=8,
            )

        target_playlist_key = str(playlist or "").strip() or "favorites"
        target_row = await user_music_playlists.get_user_playlist(
            ctx.author.id, target_playlist_key
        )
        if not target_row:
            _, _, target_row = await user_music_playlists.create_user_playlist(
                ctx.author.id,
                target_playlist_key,
                max_playlists=max_playlists,
            )
        if not target_row:
            return await ctx.reply(
                f"{self.bot.emoji.ERROR} | Could not prepare playlist.",
                delete_after=8,
            )

        track_uri = str(getattr(current_track, "uri", "") or "").strip()
        if not is_link(track_uri):
            track_uri = (
                f"{getattr(current_track, 'title', 'Unknown')} "
                f"{getattr(current_track, 'author', '')}"
            ).strip()
        ok, message, updated = await user_music_playlists.add_item_to_playlist(
            ctx.author.id,
            target_row.get("slug"),
            track_uri,
            max_items_per_playlist=max_items_per_playlist,
        )
        details = message
        if updated:
            details += (
                f"\nPlaylist: **{updated.get('name')}** (`{updated.get('slug')}`)"
                f"\nItems: {len(list(updated.get('items') or []))}/{max_items_per_playlist}"
            )
        await ctx.reply(
            embed=self._music_embed(
                ctx.guild,
                "Playlist Save Current",
                details,
                tone="success" if ok else "warning",
            ),
            delete_after=12 if ok else 14,
        )

    # ── Player subcommands under /music ──────────────────────────────

    @music_group.command(
        name="play", help="เล่นเพลงในห้องเสียง", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(search="Song name or URL to play")
    async def music_play(self, ctx: commands.Context, *, search: str):
        await ctx.invoke(self.play, search=search)

    @music_group.command(
        name="pause", help="หยุดเพลงชั่วคราว", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_pause(self, ctx: commands.Context):
        await ctx.invoke(self.pause)

    @music_group.command(
        name="resume", help="เล่นเพลงต่อ", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_resume(self, ctx: commands.Context):
        await ctx.invoke(self.resume)

    @music_group.command(
        name="skip", help="ข้ามเพลงปัจจุบัน", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_skip(self, ctx: commands.Context):
        await ctx.invoke(self.skip)

    @music_group.command(
        name="loop", help="วนเพลงปัจจุบัน", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_loop(self, ctx: commands.Context):
        await ctx.invoke(self.loop)

    @music_group.command(
        name="queue", help="แสดงคิวเพลง", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_queue(self, ctx: commands.Context):
        await ctx.invoke(self.queue)

    @music_group.command(
        name="seek", help="เลื่อนเวลาเพลง เช่น 90, +10, -10, 1:30", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=20, type=commands.BucketType.user)
    @discord.app_commands.describe(position="ตัวอย่าง: 90, +10, -10, 1:30")
    async def music_seek(self, ctx: commands.Context, *, position: str):
        await ctx.invoke(self.seek, position=position)

    @music_group.command(
        name="volume", help="ดูหรือปรับระดับเสียง", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    @discord.app_commands.describe(volume="Volume level (0-100)")
    async def music_volume(self, ctx: commands.Context, volume: int = None):
        await ctx.invoke(self.volume, volume=volume)

    @music_group.command(
        name="stop", help="หยุดเพลงและตัดการเชื่อมต่อบอท", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_stop(self, ctx: commands.Context):
        await ctx.invoke(self.stop)

    @music_group.command(
        name="current", help="แสดงเพลงที่กำลังเล่นอยู่", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_current(self, ctx: commands.Context):
        await ctx.invoke(self.current)

    @music_group.command(
        name="autoplay", help="เปิดหรือปิดโหมดเล่นอัตโนมัติ", with_app_command=True
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=30, type=commands.BucketType.user)
    async def music_autoplay(self, ctx: commands.Context):
        await ctx.invoke(self.autoplay)
