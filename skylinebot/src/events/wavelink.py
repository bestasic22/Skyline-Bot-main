from discord.ext import commands
import wavelink
import traceback, sys
import datetime

from skylinebot.console.logging import logger
from skylinebot.config.config import users as users_config

from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.memory.cache import cache
import asyncio
import requests
from skylinebot.style import color
import json

import discord

from skylinebot.src.startup import giveaways
from skylinebot.src.startup import j2c_controller
class Wavelink(commands.Cog):
    def __init__(self, bot):
        self.bot:AutoShardedBot = bot
        self._controller_refresh_times: dict[int, datetime.datetime] = {}
        self._controller_refresh_tasks: dict[int, asyncio.Task] = {}
        self._queue_advance_locks: dict[int, asyncio.Lock] = {}
        self._voice_state_events: dict[int, int] = {}
        self._voice_server_events: dict[int, int] = {}
        self._pending_voice_state: dict[int, dict] = {}
        self._pending_voice_server: dict[int, dict] = {}
        self._last_cipher_alert_at: dict[int, float] = {}
        self._last_cipher_recovery_at: dict[int, float] = {}

    def _queue_advance_lock(self, guild_id: int) -> asyncio.Lock:
        lock = self._queue_advance_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._queue_advance_locks[guild_id] = lock
        return lock

    def _track_end_reason_text(self, payload: object) -> str:
        reason = getattr(payload, "reason", "")
        if hasattr(reason, "value"):
            reason = getattr(reason, "value", "")
        return str(reason or "").strip()

    def _track_end_should_start_next(self, reason_text: str) -> bool:
        normalized = reason_text.lower()
        return normalized in {"finished", "loadfailed", "load_failed"}

    def _exception_summary_text(self, exception: object) -> str:
        try:
            if isinstance(exception, dict):
                message = str(exception.get("message") or "").strip()
                cause = str(exception.get("cause") or "").strip()
                severity = str(exception.get("severity") or "").strip()
                parts = [p for p in (severity, message, cause) if p]
                if parts:
                    return " | ".join(parts)
            return str(exception or "").strip()
        except Exception:
            return "unknown exception"

    def _is_youtube_cipher_failure(self, exception: object) -> bool:
        raw = self._exception_summary_text(exception).lower()
        return (
            "scriptextractionexception" in raw
            or ("must find sig function" in raw and "youtube" in raw)
            or ("cipher" in raw and "youtube" in raw)
        )

    def _is_youtube_access_failure(self, exception: object) -> bool:
        raw = self._exception_summary_text(exception).lower()
        return (
            "all clients failed to load the item" in raw
            or "requires login" in raw
            or "video is not available" in raw
            or "invalid status code for player api response: 400" in raw
            or "dev.lavalink.youtube.allclientsfailedexception" in raw
        )

    def _short_exception_reason(self, exception: object) -> str:
        text = self._exception_summary_text(exception)
        if not text:
            return "unknown"
        one_line = " ".join(str(text).split())
        if len(one_line) <= 220:
            return one_line
        return f"{one_line[:217]}..."

    async def _resolve_music_notify_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        try:
            music_data = cache.music.get(str(guild.id), {})
            channel_id = music_data.get("music_setup_channel_id")
            if channel_id:
                try:
                    channel = guild.get_channel(int(channel_id))
                except (TypeError, ValueError):
                    channel = None
                if isinstance(channel, discord.TextChannel):
                    perms = channel.permissions_for(guild.me)
                    if perms.send_messages and perms.view_channel:
                        return channel
        except Exception:
            pass

        try:
            for channel in guild.text_channels:
                perms = channel.permissions_for(guild.me)
                if perms.send_messages and perms.view_channel:
                    return channel
        except Exception:
            return None
        return None

    async def _queue_soundcloud_recovery(
        self, player: wavelink.Player, failed_track: wavelink.Playable | None
    ) -> tuple[bool, str]:
        guild = getattr(player, "guild", None)
        if guild is None:
            return False, ""

        now_ts = datetime.datetime.now().timestamp()
        last_try = self._last_cipher_recovery_at.get(guild.id, 0.0)
        if now_ts - last_try < 20:
            return False, ""
        self._last_cipher_recovery_at[guild.id] = now_ts

        query = ""
        try:
            query = str(getattr(failed_track, "title", "") or "").strip()
        except Exception:
            query = ""
        if not query:
            return False, ""

        try:
            result = await wavelink.Playable.search(
                query, source=wavelink.TrackSource.SoundCloud
            )
        except Exception as error:
            logger.warning(
                f"[music_recovery] SoundCloud fallback search failed in {guild.name}: "
                f"{type(error).__name__}: {error}"
            )
            return False, ""

        if not result:
            return False, ""

        fallback_track = result[0]
        try:
            requester = getattr(failed_track, "requester", None)
            if requester is not None:
                fallback_track.requester = requester
        except Exception:
            pass

        try:
            # Put at the front so on_wavelink_track_end picks it immediately.
            player.queue.put_at(0, fallback_track)
        except Exception:
            try:
                await player.queue.put_wait(fallback_track)
            except Exception as error:
                logger.warning(
                    f"[music_recovery] Failed to queue SoundCloud fallback in {guild.name}: "
                    f"{type(error).__name__}: {error}"
                )
                return False, ""

        return True, str(getattr(fallback_track, "title", "") or "")

    def _stop_controller_refresh_task(self, guild_id: int) -> None:
        task = self._controller_refresh_tasks.pop(guild_id, None)
        if task and not task.done():
            task.cancel()

    def _ensure_controller_refresh_task(self, guild_id: int) -> None:
        existing = self._controller_refresh_tasks.get(guild_id)
        if existing and not existing.done():
            return
        self._controller_refresh_tasks[guild_id] = asyncio.create_task(
            self._controller_refresh_loop(guild_id)
        )

    def _persistent_voice_enabled(self, guild_id: int) -> bool:
        music_data = cache.music.get(str(guild_id), {})
        channel_id = music_data.get("music_setup_voice_channel_id")
        try:
            return bool(channel_id and int(channel_id))
        except (TypeError, ValueError):
            return False

    async def _controller_refresh_loop(self, guild_id: int) -> None:
        try:
            while True:
                await asyncio.sleep(12)
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    break
                player = guild.voice_client
                if not player or not getattr(player, "current", None):
                    break
                music_cog = self.bot.get_cog("Music")
                if not music_cog:
                    break
                self._controller_refresh_times[guild_id] = datetime.datetime.now(datetime.timezone.utc)
                await music_cog.send_music_controls(guild=guild, update_attachments=False)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error(f"Error in controller refresh loop: {traceback.format_exc()}")
        finally:
            self._controller_refresh_tasks.pop(guild_id, None)

    async def _handle_voice_socket_payload(self, payload: dict):
        try:
            if not isinstance(payload, dict):
                return
            t = payload.get("t")
            if t not in {"VOICE_STATE_UPDATE", "VOICE_SERVER_UPDATE"}:
                return

            data = payload.get("d") or {}
            guild_id = data.get("guild_id")
            if guild_id is None:
                return

            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return

            if t == "VOICE_STATE_UPDATE":
                self._voice_state_events[guild.id] = (
                    self._voice_state_events.get(guild.id, 0) + 1
                )
            else:
                self._voice_server_events[guild.id] = (
                    self._voice_server_events.get(guild.id, 0) + 1
                )

            player = guild.voice_client
            if not player or not isinstance(player, wavelink.Player):
                if t == "VOICE_SERVER_UPDATE":
                    self._pending_voice_server[guild.id] = data
                else:
                    user_id = (data.get("user_id") or "")
                    if str(user_id) == str(self.bot.user.id):
                        self._pending_voice_state[guild.id] = data
                return

            self._pending_voice_server.pop(guild.id, None)
            self._pending_voice_state.pop(guild.id, None)
        except Exception:
            logger.error(f"Error in on_socket_response voice forwarding: {traceback.format_exc()}")

    @commands.Cog.listener()
    async def on_socket_response(self, payload: dict):
        await self._handle_voice_socket_payload(payload)

    @commands.Cog.listener()
    async def on_socket_raw_receive(self, msg):
        try:
            if isinstance(msg, bytes):
                msg = msg.decode("utf-8", errors="ignore")
            if not isinstance(msg, str):
                return
            payload = json.loads(msg)
        except Exception:
            return
        await self._handle_voice_socket_payload(payload)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        logger.info(f"Node {payload.node.uri} is ready!")

    @commands.Cog.listener()
    async def on_wavelink_node_closed(self, node: wavelink.Node, disconnected: list[wavelink.Player]):
        logger.warning(f"Node {node.uri} has been closed and cleaned-up. Disconnected players: {len(disconnected)}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        guild = getattr(payload.player, "guild", None)
        if guild:
            self._ensure_controller_refresh_task(guild.id)
            logger.info(f"Track {payload.track} has started playing on player {guild.name}")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        player = getattr(payload, "player", None)
        guild = getattr(player, "guild", None)
        track = getattr(payload, "track", None)
        exception_obj = getattr(payload, "exception", None)
        summary = self._exception_summary_text(exception_obj)
        short_reason = self._short_exception_reason(exception_obj)
        guild_name = getattr(guild, "name", "Unknown Guild")
        track_name = getattr(track, "title", None) or str(track or "Unknown")

        if self._is_youtube_cipher_failure(exception_obj):
            logger.warning(
                f"[music] YouTube cipher extraction failed in {guild_name} | "
                f"track={track_name} | {summary}"
            )

            recovered = False
            recovered_title = ""
            if isinstance(player, wavelink.Player):
                recovered, recovered_title = await self._queue_soundcloud_recovery(player, track)

            if guild:
                now_ts = datetime.datetime.now().timestamp()
                last_alert = self._last_cipher_alert_at.get(guild.id, 0.0)
                if now_ts - last_alert >= 30:
                    self._last_cipher_alert_at[guild.id] = now_ts
                    notify_channel = await self._resolve_music_notify_channel(guild)
                    if notify_channel:
                        if recovered and recovered_title:
                            message = (
                                "⚠️ ระบบเล่นเพลงจาก YouTube ขัดข้องชั่วคราว (YouTube cipher เปลี่ยนฝั่งต้นทาง)\n"
                                f"ผมได้สลับคิวไป SoundCloud อัตโนมัติ: **{recovered_title}**"
                            )
                        else:
                            message = (
                                "⚠️ ระบบเล่นเพลงจาก YouTube ขัดข้องชั่วคราว (YouTube cipher เปลี่ยนฝั่งต้นทาง)\n"
                                "กรุณาอัปเดตปลั๊กอิน youtube ของ Lavalink แล้วลองใหม่อีกครั้ง"
                            )
                        try:
                            await notify_channel.send(message)
                        except Exception:
                            pass
            return

        if self._is_youtube_access_failure(exception_obj):
            logger.warning(
                f"[music] YouTube source rejected track in {guild_name} | "
                f"track={track_name} | reason={short_reason}"
            )

            recovered = False
            recovered_title = ""
            if isinstance(player, wavelink.Player):
                recovered, recovered_title = await self._queue_soundcloud_recovery(player, track)

            if guild:
                now_ts = datetime.datetime.now().timestamp()
                last_alert = self._last_cipher_alert_at.get(guild.id, 0.0)
                if now_ts - last_alert >= 30:
                    self._last_cipher_alert_at[guild.id] = now_ts
                    notify_channel = await self._resolve_music_notify_channel(guild)
                    if notify_channel:
                        if recovered and recovered_title:
                            message = (
                                "⚠️ เพลงนี้ไม่สามารถเล่นจาก YouTube ได้ในขณะนี้ "
                                "(ต้องล็อกอิน/ถูกจำกัด/ไม่พร้อมใช้งาน)\n"
                                f"ผมสลับคิวไปเพลงสำรองอัตโนมัติ: **{recovered_title}**"
                            )
                        else:
                            message = (
                                "⚠️ เพลงนี้ไม่สามารถเล่นจาก YouTube ได้ในขณะนี้ "
                                "(ต้องล็อกอิน/ถูกจำกัด/ไม่พร้อมใช้งาน)\n"
                                "ระบบจะข้ามไปเพลงถัดไปอัตโนมัติ"
                            )
                        try:
                            await notify_channel.send(message)
                        except Exception:
                            pass
            return

        logger.error(
            f"An exception occurred while playing track {track_name} on player {guild_name}: {summary}"
        )

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        logger.error(f"Track {payload.track} got stuck on player {payload.player.guild.name}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        try:
            player = payload.player
            guild = getattr(player, "guild", None)
            if not player or not guild:
                return
            reason_text = self._track_end_reason_text(payload)
            reason_display = reason_text or "unknown"
            logger.info(
                f"Track end event received for track: {payload.track.title if payload.track else 'Unknown'} | "
                f"reason={reason_display}"
            )

            self._stop_controller_refresh_task(guild.id)
            
            MusicCog = self.bot.get_cog("Music")
            if not MusicCog:
                return logger.error("ไม่พบ Music cog จึงไม่สามารถอัปเดตตัวควบคุมเพลงได้")

            if not self._track_end_should_start_next(reason_text):
                # Do not force-advance queue for end reasons that Lavalink marks
                # as not eligible to start the next track (e.g. replaced/stopped/cleanup).
                if guild.voice_client:
                    await MusicCog.send_music_controls(guild=guild, update_attachments=True)
                return

            if player.autoplay != wavelink.AutoPlayMode.disabled:
                for i in range(5):
                    if player.current:
                        break
                    await asyncio.sleep(1)
                if guild.voice_client:
                    return await MusicCog.send_music_controls(guild=guild, update_attachments=True)
                return

            # Check if the queue is empty
            if player.queue.is_empty and not player.queue.mode == wavelink.QueueMode.loop:
                # If the queue is empty but the player is still playing, log it
                if player.current:
                    logger.info(f"Queue is empty, but the player is still playing {player.current.title}")
                    return

                # Keep the player in voice until inactive_timeout elapses.
                # This avoids frequent join/leave churn between song requests.
                logger.info(
                    f"Queue is empty in {guild.name}. Waiting for inactive timeout before disconnect."
                )
                await MusicCog.send_music_controls(guild=guild, end=True)
            else:
                lock = self._queue_advance_lock(guild.id)
                async with lock:
                    try:
                        next_track = player.queue.get()
                    except wavelink.exceptions.QueueEmpty:
                        logger.info(
                            f"Queue became empty in {guild.name}. Waiting for inactive timeout before disconnect."
                        )
                        await MusicCog.send_music_controls(guild=guild, end=True)
                        return
                    await player.play(next_track)
                    logger.info(f"Playing next track: {next_track.title}")
                    await MusicCog.send_music_controls(guild=guild, update_attachments=True)
        except Exception as e:
            logger.error(f"Error in track end handler: {traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_wavelink_stats_update(self, payload: wavelink.StatsEventPayload):
        # logger.warning(f"WaveLink Stats updated: {payload.players} players total ({payload.playing} playing)")
        pass




    @commands.Cog.listener()
    async def on_wavelink_player_update(self, payload: wavelink.PlayerUpdateEventPayload):
        try:
            player = payload.player
            guild = getattr(player, "guild", None)
            if not player or not guild or not guild.voice_client or not player.current:
                return

            self._ensure_controller_refresh_task(guild.id)

            now = datetime.datetime.now(datetime.timezone.utc)
            last_refresh = self._controller_refresh_times.get(guild.id)
            if last_refresh and (now - last_refresh).total_seconds() < 10:
                return

            MusicCog = self.bot.get_cog("Music")
            if not MusicCog:
                return

            self._controller_refresh_times[guild.id] = now
            await MusicCog.send_music_controls(guild=guild, update_attachments=False)
        except Exception:
            logger.error(f"Error in player update handler: {traceback.format_exc()}")

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player) -> None:
        guild = getattr(player, "guild", None)
        if guild:
            self._stop_controller_refresh_task(guild.id)
        if getattr(player, "channel", None):
            await player.channel.send(f"The player has been inactive for `{player.inactive_timeout}` seconds. Goodbye!")
        try:
            await player.disconnect()
        except Exception:
            pass
        if guild:
            music_cog = self.bot.get_cog("Music")
            if music_cog:
                await music_cog.send_music_controls(guild=guild, end=True)
