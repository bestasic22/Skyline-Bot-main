from discord.ext import commands
import wavelink
import traceback, sys
import os
import time

from skylinebot.console.logging import logger
from skylinebot.config.config import users as users_config

from skylinebot.engine.bot_runtime import AutoShardedBot
import asyncio
import requests
from skylinebot.style import color

import discord
from skylinebot.utils import i18n

from skylinebot.src.startup import giveaways
from skylinebot.src.startup import j2c_controller
class ready(commands.Cog):
    def __init__(self, bot):
        self.bot:AutoShardedBot = bot
        self._activity_task: asyncio.Task | None = None
        self._startup_task: asyncio.Task | None = None
        self._startup_sequence_done: bool = bool(
            getattr(self.bot, "_ready_startup_sequence_done", False)
        )
        self._startup_sequence_lock: asyncio.Lock = asyncio.Lock()
        self._presence_refresh_event: asyncio.Event = asyncio.Event()
        self._tree_synced_once: bool = bool(getattr(self.bot, "_ready_tree_synced_once", False))
        self._gateway_log_mode: str = self._resolve_gateway_log_mode()
        self._gateway_log_cooldown_seconds: float = self._resolve_gateway_log_cooldown_seconds()
        self._gateway_ready_log_cooldown_seconds: float = (
            self._resolve_gateway_ready_log_cooldown_seconds()
        )
        self._gateway_startup_disconnect_grace_seconds: float = (
            self._resolve_gateway_startup_disconnect_grace_seconds()
        )
        self._gateway_started_at_monotonic: float = time.monotonic()
        self._gateway_log_last_emit_at: dict[str, float] = {}
        self._gateway_log_policy_reported: bool = bool(
            getattr(self.bot, "_ready_gateway_log_policy_reported", False)
        )
        self._startup_summary_reported: bool = bool(
            getattr(self.bot, "_ready_startup_summary_reported", False)
        )
        self._override_message_index: int = 0

    @staticmethod
    def _bool_env(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return bool(default)
        value = str(raw).strip().lower()
        if value in {"1", "true", "yes", "on", "y"}:
            return True
        if value in {"0", "false", "no", "off", "n"}:
            return False
        return bool(default)

    def _resolve_gateway_log_mode(self) -> str:
        raw = str(
            os.getenv(
                "DISCORD_GATEWAY_LOG_MODE",
                getattr(self.bot.BotConfig, "DISCORD_GATEWAY_LOG_MODE", "shard"),
            )
            or "shard"
        ).strip().lower()
        if raw in {"off", "none"}:
            return "off"
        if raw in {"global", "shard", "both"}:
            return raw
        return "shard"

    def _resolve_gateway_log_cooldown_seconds(self) -> float:
        raw = str(
            os.getenv(
                "DISCORD_GATEWAY_LOG_COOLDOWN_SECONDS",
                getattr(self.bot.BotConfig, "DISCORD_GATEWAY_LOG_COOLDOWN_SECONDS", 45),
            )
            or "45"
        ).strip()
        try:
            value = float(raw)
        except Exception:
            value = 45.0
        return max(0.0, min(value, 600.0))

    def _resolve_gateway_ready_log_cooldown_seconds(self) -> float:
        raw = str(
            os.getenv(
                "DISCORD_GATEWAY_READY_LOG_COOLDOWN_SECONDS",
                getattr(self.bot.BotConfig, "DISCORD_GATEWAY_READY_LOG_COOLDOWN_SECONDS", 180),
            )
            or "180"
        ).strip()
        try:
            value = float(raw)
        except Exception:
            value = 180.0
        return max(0.0, min(value, 3600.0))

    def _resolve_gateway_startup_disconnect_grace_seconds(self) -> float:
        raw = str(
            os.getenv(
                "DISCORD_GATEWAY_STARTUP_DISCONNECT_GRACE_SECONDS",
                getattr(
                    self.bot.BotConfig,
                    "DISCORD_GATEWAY_STARTUP_DISCONNECT_GRACE_SECONDS",
                    45,
                ),
            )
            or "45"
        ).strip()
        try:
            value = float(raw)
        except Exception:
            value = 45.0
        return max(0.0, min(value, 600.0))

    def _is_startup_transient_shard_disconnect(self) -> bool:
        if self.bot.is_ready():
            return False
        elapsed = max(0.0, float(time.monotonic()) - self._gateway_started_at_monotonic)
        return elapsed <= float(self._gateway_startup_disconnect_grace_seconds)

    def _is_gateway_log_scope_enabled(self, scope: str) -> bool:
        mode = self._gateway_log_mode
        if mode == "off":
            return False
        if mode == "both":
            return True
        if mode == "global":
            return scope == "global"
        return scope == "shard"

    def _should_emit_gateway_log(self, key: str, *, cooldown_seconds: float | None = None) -> bool:
        now = float(time.monotonic())
        cooldown = (
            float(cooldown_seconds)
            if isinstance(cooldown_seconds, (int, float))
            else float(self._gateway_log_cooldown_seconds)
        )
        cooldown = max(0.0, cooldown)
        last = self._gateway_log_last_emit_at.get(key)
        if isinstance(last, (int, float)) and (now - float(last)) < cooldown:
            return False
        self._gateway_log_last_emit_at[key] = now
        return True

    async def _emit_gateway_log(
        self,
        *,
        scope: str,
        event_name: str,
        message: str,
        embed_color,
        logger_method: str,
        shard_id: int | None = None,
        cooldown_seconds: float | None = None,
    ) -> None:
        if not self._is_gateway_log_scope_enabled(scope):
            return
        key_suffix = f"shard:{int(shard_id)}" if shard_id is not None else "global"
        cooldown_key = f"{scope}:{event_name}:{key_suffix}"
        if not self._should_emit_gateway_log(cooldown_key, cooldown_seconds=cooldown_seconds):
            return
        await self.send_shard_log(message, embed_color=embed_color)
        if logger_method == "warning":
            logger.warning(message)
        elif logger_method == "error":
            logger.error(message)
        elif logger_method == "success":
            logger.success(message)
        elif logger_method == "system":
            logger.system(message)
        else:
            logger.info(message)

    def _resolve_runtime_components(self) -> tuple[bool, bool]:
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
        run_web = self._bool_env("RUN_WEB", run_web)
        run_bot = self._bool_env("RUN_BOT", run_bot)
        return bool(run_web), bool(run_bot)

    def _dashboard_probe_urls(self) -> list[str]:
        host = str(getattr(self.bot.BotConfig, "WEB_HOST", "127.0.0.1") or "127.0.0.1").strip()
        host = host.strip("[]")
        base_hosts: list[str]
        if host in {"", "0.0.0.0", "::", "*"}:
            base_hosts = ["127.0.0.1", "localhost"]
        else:
            base_hosts = [host]
            if host.lower() not in {"127.0.0.1", "localhost", "::1"}:
                base_hosts.extend(["127.0.0.1", "localhost"])

        unique_hosts: list[str] = []
        seen_hosts: set[str] = set()
        for item in base_hosts:
            key = str(item or "").strip().lower()
            if not key or key in seen_hosts:
                continue
            seen_hosts.add(key)
            unique_hosts.append(str(item).strip())

        port = int(getattr(self.bot.BotConfig, "WEB_PORT", 25572) or 25572)
        use_https = bool(getattr(self.bot.BotConfig, "WEB_SSL_ENABLED", False))
        schemes = ["https", "http"] if use_https else ["http"]
        probe_paths = ["/dashboard/runtime/discord", "/"]

        urls: list[str] = []
        for scheme in schemes:
            for probe_host in unique_hosts:
                for path in probe_paths:
                    urls.append(f"{scheme}://{probe_host}:{port}{path}")
        return urls

    def _is_web_runtime_online(self) -> bool:
        dashboard_enabled = bool(getattr(self.bot.BotConfig, "DASHBOARD_ENABLED", True))
        if not dashboard_enabled:
            return False
        probe_urls = self._dashboard_probe_urls()
        for url in probe_urls:
            verify_ssl = True
            url_lower = url.lower()
            if (
                url_lower.startswith("https://127.0.0.1")
                or url_lower.startswith("https://localhost")
                or url_lower.startswith("https://[::1]")
                or url_lower.startswith("https://::1")
            ):
                verify_ssl = False
            try:
                response = requests.get(url, timeout=2.5, verify=verify_ssl)
                if 200 <= int(response.status_code) < 500:
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _normalize_ownerbot_status_override_level(raw_value: object) -> str:
        level = str(raw_value or "auto").strip().lower()
        if level in {"live", "ok", "running"}:
            return "online"
        if level in {"stream", "starting", "reloading", "reload"}:
            return "idle"
        if level in {"ded", "maintenance", "error", "err"}:
            return "dnd"
        if level not in {"auto", "online", "idle", "dnd", "offline"}:
            return "auto"
        return level

    @staticmethod
    def _normalize_ownerbot_status_override_activity(raw_value: object) -> str:
        activity = str(raw_value or "auto").strip().lower()
        if activity == "custom":
            return "watching"
        if activity not in {"auto", "playing", "streaming", "listening", "watching", "competing"}:
            return "auto"
        return activity

    @staticmethod
    def _normalize_presence_activity_text(raw_value: object, *, limit: int = 120) -> str:
        text = " ".join(str(raw_value or "").strip().split())
        if not text:
            return ""
        return text[: int(limit)]

    @classmethod
    def _parse_override_messages(cls, raw_value: object, *, limit: int = 12) -> list[str]:
        items = raw_value if isinstance(raw_value, list) else str(raw_value or "").splitlines()
        out: list[str] = []
        for item in items:
            text = cls._normalize_presence_activity_text(item, limit=120)
            if not text:
                continue
            out.append(text)
            if len(out) >= int(limit):
                break
        return out

    def _next_override_message(self, messages: list[str]) -> str:
        if not isinstance(messages, list) or not messages:
            return ""
        index = int(self._override_message_index or 0) % len(messages)
        self._override_message_index = (index + 1) % len(messages)
        return str(messages[index] or "")

    async def _ownerbot_presence_override(self) -> tuple[str, str, list[str]]:
        level = "auto"
        activity = "auto"
        messages: list[str] = []
        if not hasattr(self.bot, "_load_ownerbot_runtime_settings"):
            return level, activity, messages
        try:
            settings = await self.bot._load_ownerbot_runtime_settings()
        except Exception:
            settings = {}
        if not isinstance(settings, dict):
            return level, activity, messages
        level = self._normalize_ownerbot_status_override_level(
            settings.get("dashboard_status_override_level")
        )
        activity = self._normalize_ownerbot_status_override_activity(
            settings.get("dashboard_status_override_activity")
        )
        messages = self._parse_override_messages(settings.get("dashboard_status_override_messages"))
        if not messages:
            messages = self._parse_override_messages(settings.get("dashboard_status_override_message"))
        return level, activity, messages

    async def _ownerbot_rich_presence_mode(self) -> str:
        if not hasattr(self.bot, "_load_ownerbot_runtime_settings"):
            return "off"
        try:
            settings = await self.bot._load_ownerbot_runtime_settings()
        except Exception:
            return "off"
        mode = str((settings or {}).get("rich_presence_mode") or "off").strip().lower()
        if mode not in {"off", "voice", "always"}:
            mode = "off"
        return mode

    def _is_human_in_bot_voice_channel(self) -> bool:
        for voice_client in list(getattr(self.bot, "voice_clients", []) or []):
            channel = getattr(voice_client, "channel", None)
            if channel is None:
                continue
            members = list(getattr(channel, "members", []) or [])
            if any(not bool(getattr(member, "bot", False)) for member in members):
                return True
        return False

    def _build_rich_presence_activity(self):
        servers = self._online_guild_count()
        users = self._guild_user_count()
        return discord.Activity(
            type=discord.ActivityType.listening,
            name="/help",
            details=f"{servers} servers online",
            state=f"{users} users connected",
        )

    @staticmethod
    def _build_activity_by_type(activity_type: str, text: str):
        if not text:
            return None
        if activity_type == "playing":
            return discord.Game(name=text)
        if activity_type == "streaming":
            return discord.Streaming(name=text, url="https://www.twitch.tv/discord")
        if activity_type == "listening":
            return discord.Activity(type=discord.ActivityType.listening, name=text)
        if activity_type == "competing":
            return discord.Activity(type=discord.ActivityType.competing, name=text)
        return discord.Activity(type=discord.ActivityType.watching, name=text)

    @staticmethod
    def _build_override_presence(
        override_level: str,
        override_activity: str,
        override_message: str,
    ):
        level = str(override_level or "online").strip().lower()
        activity_type = str(override_activity or "auto").strip().lower()
        message_text = str(override_message or "").strip()
        if activity_type not in {"auto", "playing", "streaming", "listening", "watching", "competing"}:
            activity_type = "auto"

        default_text_map = {
            "idle": "Bot is idle",
            "dnd": "Do not disturb",
            "offline": "",
            "online": "",
            "auto": "",
        }

        if not message_text:
            message_text = default_text_map.get(level, "")
        if message_text:
            message_text = message_text[:120]

        if activity_type == "auto":
            activity_type = "watching"

        if level == "offline":
            return discord.Status.invisible, None

        if level == "idle":
            status = discord.Status.idle
        elif level == "dnd":
            status = discord.Status.dnd
        else:
            status = discord.Status.online

        if level == "online" and not message_text:
            if activity_type == "auto":
                return status, None
            message_text = "SkylineBot"

        activity_obj = ready._build_activity_by_type(activity_type, message_text)
        if activity_obj is None and message_text:
            activity_obj = discord.Activity(type=discord.ActivityType.watching, name=message_text)
        return status, activity_obj

    def _online_guild_count(self) -> int:
        return sum(
            1
            for guild in list(getattr(self.bot, "guilds", []) or [])
            if not bool(getattr(guild, "unavailable", False))
        )

    def _guild_user_count(self) -> int:
        total = 0
        for guild in list(getattr(self.bot, "guilds", []) or []):
            if bool(getattr(guild, "unavailable", False)):
                continue
            member_count = getattr(guild, "member_count", None)
            if isinstance(member_count, int) and member_count > 0:
                total += member_count
        return max(0, total)

    def _uptime_days_hours_minutes(self) -> tuple[int, int, int]:
        started_at = getattr(self.bot, "start_time", None)
        if hasattr(started_at, "timestamp"):
            try:
                started_at_ts = float(started_at.timestamp())
            except Exception:
                started_at_ts = float(time.time())
        else:
            started_at_ts = float(time.time())
        elapsed = max(0, int(time.time() - started_at_ts))
        days = elapsed // 86400
        hours = (elapsed % 86400) // 3600
        minutes = (elapsed % 3600) // 60
        return days, hours, minutes

    def _presence_servers_users_text(self) -> str:
        servers = self._online_guild_count()
        users = self._guild_user_count()
        return f"{servers} servers {users} users"

    def _presence_uptime_text(self) -> str:
        days, hours, minutes = self._uptime_days_hours_minutes()
        return f"Online {days} วัน {hours} ชั่วโมง {minutes} นาที"

    def _ensure_task(self, attr_name: str, coroutine_factory):
        task = getattr(self, attr_name, None)
        if isinstance(task, asyncio.Task) and not task.done():
            return task
        new_task = asyncio.create_task(coroutine_factory())
        setattr(self, attr_name, new_task)
        return new_task

    def request_presence_refresh(self) -> None:
        """Wake the presence loop so dashboard changes apply immediately."""
        try:
            self._presence_refresh_event.set()
        except Exception:
            pass

    def _priority_slash_sync_guild_ids(self) -> list[int]:
        raw_values: list[str] = []
        for env_name in ("SLASH_SYNC_GUILD_IDS", "SUPPORT_GUILD_ID"):
            raw = str(os.getenv(env_name, "")).strip()
            if not raw:
                continue
            raw_values.extend(raw.replace("\n", ",").split(","))
        ids: list[int] = []
        for item in raw_values:
            text = str(item or "").strip()
            if not text.isdigit():
                continue
            gid = int(text)
            if gid not in ids:
                ids.append(gid)
        return ids

    def _is_guild_mirror_enabled(self) -> bool:
        raw = str(os.getenv("SLASH_MIRROR_GLOBAL_TO_GUILD", "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    async def _sync_application_commands(self) -> bool:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if self.bot.is_closed():
                return False
            try:
                global_synced = await self.bot.tree.sync()
                logger.system(
                    f"Application Commands (Tree) Synced | global={len(global_synced)}"
                )

                mirror_global_to_guild = self._is_guild_mirror_enabled()
                avoid_duplicate_sources = str(os.getenv("SLASH_AVOID_DUPLICATE_COMMANDS", "1")).strip().lower() not in {"0", "false", "no", "off"}
                mirror_disabled_by_guard = False
                if mirror_global_to_guild and avoid_duplicate_sources:
                    logger.warning(
                        "SLASH_MIRROR_GLOBAL_TO_GUILD is enabled but dedupe guard is active; "
                        "guild mirror copy is disabled to prevent duplicate slash command listings. "
                        "Set SLASH_AVOID_DUPLICATE_COMMANDS=0 to force mirror copy."
                    )
                    mirror_global_to_guild = False
                    mirror_disabled_by_guard = True
                for guild_id in self._priority_slash_sync_guild_ids():
                    guild = self.bot.get_guild(int(guild_id))
                    if guild is None:
                        continue
                    try:
                        if mirror_global_to_guild:
                            self.bot.tree.clear_commands(guild=guild)
                            self.bot.tree.copy_global_to(guild=guild)
                            guild_synced = await self.bot.tree.sync(guild=guild)
                            logger.system(
                                f"Application Commands (Tree) Synced | guild={guild.id} count={len(guild_synced)} mirror={mirror_global_to_guild}"
                            )
                        elif mirror_disabled_by_guard:
                            self.bot.tree.clear_commands(guild=guild)
                            guild_synced = await self.bot.tree.sync(guild=guild)
                            logger.system(
                                f"Application Commands (Tree) Guild Cleanup | guild={guild.id} count={len(guild_synced)} mirror={mirror_global_to_guild} guard=dedupe"
                            )
                        else:
                            logger.system(
                                f"Application Commands (Tree) Guild Mirror Skipped | guild={guild.id} mirror={mirror_global_to_guild}"
                            )
                    except Exception as guild_sync_error:
                        logger.warning(
                            f"Guild slash sync failed ({guild.id}): {guild_sync_error}"
                        )

                filtered = list(getattr(self.bot, "_slash_filtered_commands", []) or [])
                overflow = list(getattr(self.bot, "_slash_overflow_commands", []) or [])
                mode = str(getattr(self.bot, "_slash_command_mode", "essential")).strip().lower()
                if filtered:
                    logger.warning(
                        f"Slash filtered by mode={mode} ({len(filtered)}): "
                        f"{', '.join(filtered[:20])}{' ...' if len(filtered) > 20 else ''}"
                    )
                if overflow:
                    logger.warning(
                        f"Slash overflow skipped ({len(overflow)}): "
                        f"{', '.join(overflow[:20])}{' ...' if len(overflow) > 20 else ''}"
                    )
                return True
            except Exception as sync_error:
                error_text = str(sync_error).lower()
                transient = (
                    isinstance(sync_error, (discord.ConnectionClosed, ConnectionResetError, asyncio.TimeoutError, OSError))
                    or "cannot write to closing transport" in error_text
                    or "session is closed" in error_text
                    or "connection reset" in error_text
                )
                if transient and attempt < max_attempts:
                    await asyncio.sleep(2 * attempt)
                    continue
                logger.error(
                    f"Failed to sync application commands (attempt {attempt}/{max_attempts}): {sync_error}"
                )
                return False
        return False

    async def _sync_application_commands_once(self) -> None:
        if self._tree_synced_once or bool(
            getattr(self.bot, "_ready_tree_synced_once", False)
        ):
            self._tree_synced_once = True
            return
        synced = await self._sync_application_commands()
        if synced:
            self._tree_synced_once = True
            setattr(self.bot, "_ready_tree_synced_once", True)


        
    @commands.Cog.listener(name="on_ready")
    async def on_ready(self):
        try:
            if not self._startup_summary_reported:
                logger.startup_summary(self.bot)
                if self.bot.BotConfig.DASHBOARD_ENABLED:
                    logger.web_startup_summary(self.bot)
                self._startup_summary_reported = True
                setattr(self.bot, "_ready_startup_summary_reported", True)
            if not self._gateway_log_policy_reported:
                logger.system(
                    "Discord gateway log policy -> "
                    f"mode={self._gateway_log_mode}, cooldown={self._gateway_log_cooldown_seconds:.0f}s, "
                    f"startup_disconnect_grace={self._gateway_startup_disconnect_grace_seconds:.0f}s"
                )
                self._gateway_log_policy_reported = True
                setattr(self.bot, "_ready_gateway_log_policy_reported", True)
            if self._should_emit_gateway_log("ready:connected:global", cooldown_seconds=180.0):
                logger.success(f"Connected as {self.bot.user}")
            self._ensure_task("_activity_task", lambda: self.activity())
            if not self._startup_sequence_done and not bool(
                getattr(self.bot, "_ready_startup_sequence_done", False)
            ):
                self._ensure_task("_startup_task", lambda: self._run_ready_startups_once())
            i18n.apply_app_command_localizations(self.bot)
            if not self._tree_synced_once:
                self._ensure_task(
                    "_tree_sync_task",
                    lambda: self._sync_application_commands_once(),
                )
            # Load developers
            dev_ids = users_config.developer
            if isinstance(dev_ids, (int, str)):
                dev_ids = [dev_ids]
            
            self.bot.developers = []
            for dev_id in dev_ids:
                try:
                    user = self.bot.get_user(int(dev_id))
                    if user is None:
                        user = await self.bot.fetch_user(int(dev_id))
                    self.bot.developers.append(user)
                except Exception:
                    pass
            
            if self.bot.developers:
                self.bot.developer = self.bot.developers[0]
            else:
                self.bot.developer = self.bot.user
                self.bot.developers = [self.bot.user]

            current_developer_count = len(self.bot.developers)
            previous_developer_count = int(
                getattr(self.bot, "_ready_last_developer_count", -1)
            )
            if current_developer_count != previous_developer_count:
                logger.system(f"Found {current_developer_count} Authorized Developers")
                setattr(self.bot, "_ready_last_developer_count", current_developer_count)

        except Exception as e:
            logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    async def _run_ready_startups_once(self):
        if self._startup_sequence_done or bool(
            getattr(self.bot, "_ready_startup_sequence_done", False)
        ):
            self._startup_sequence_done = True
            return
        async with self._startup_sequence_lock:
            if self._startup_sequence_done or bool(
                getattr(self.bot, "_ready_startup_sequence_done", False)
            ):
                self._startup_sequence_done = True
                return
            await self.on_ready_startups()
            self._startup_sequence_done = True
            setattr(self.bot, "_ready_startup_sequence_done", True)
    
    async def on_ready_startups(self):
        try:
            asyncio.create_task(giveaways.resume_active_giveaway(self.bot))
        except Exception:
            pass
        logger.cog("Active Giveaways Resumed")
        try:
            asyncio.create_task(j2c_controller.resume_j2c_controllers(self.bot))
        except Exception:
            pass
        logger.cog("J2C Controllers Resumed")

        

    async def activity(self):
        await self.bot.wait_until_ready()

        activities = [
            lambda: discord.Activity(type=discord.ActivityType.listening, name="/help"),
            lambda: discord.Activity(type=discord.ActivityType.watching, name=self._presence_servers_users_text()),
            lambda: discord.Activity(type=discord.ActivityType.watching, name=self._presence_uptime_text()),
            lambda: discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.bot.commands)} commands"),
            lambda: discord.Activity(type=discord.ActivityType.watching, name=getattr(self.bot.urls, "WEBSITE", "Website")),
        ]

        index = 0
        while not self.bot.is_closed():
            try:
                if not self.bot.is_ready():
                    await asyncio.sleep(2)
                    continue
                rich_presence_mode = await self._ownerbot_rich_presence_mode()
                rich_presence_enabled = (
                    rich_presence_mode == "always"
                    or (
                        rich_presence_mode == "voice"
                        and self._is_human_in_bot_voice_channel()
                    )
                )
                override_level, override_activity, override_messages = await self._ownerbot_presence_override()
                if override_level != "auto":
                    override_message = self._next_override_message(override_messages)
                    status, activity = self._build_override_presence(
                        override_level=override_level,
                        override_activity=override_activity,
                        override_message=override_message,
                    )
                    if activity is None and override_level == "online":
                        activity = activities[index % len(activities)]()
                        index += 1
                else:
                    web_online = await asyncio.to_thread(self._is_web_runtime_online)
                    if web_online:
                        status = discord.Status.online
                        if rich_presence_enabled:
                            activity = self._build_rich_presence_activity()
                        else:
                            activity = activities[index % len(activities)]()
                            index += 1
                    else:
                        status = discord.Status.dnd
                        activity = discord.Activity(
                            type=discord.ActivityType.watching,
                            name="Website Offline",
                        )
                await self.bot.change_presence(status=status, activity=activity)
                # logger.system(f"Presence Updated -> {activity.type.name} {activity.name}")
                try:
                    await asyncio.wait_for(self._presence_refresh_event.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass
                finally:
                    self._presence_refresh_event.clear()

            except discord.ConnectionClosed:
                logger.warning("การเชื่อมต่อ Discord หลุด กำลังพยายามเชื่อมต่อใหม่...")
                await asyncio.sleep(10)

            except Exception as e:
                error_text = str(e).lower()
                if "cannot write to closing transport" in error_text:
                    await asyncio.sleep(5)
                    continue
                tb = traceback.extract_tb(sys.exc_info()[2])[-1]
                logger.error(f"Error in {__file__}, line {tb.lineno}: {e}")
                await asyncio.sleep(60) 



    async def send_shard_log(self, msg, embed_color=color.green):
        try:
            shards_log_webhook = self.bot.channels.shards_log_webhook
            if shards_log_webhook:
                embed = discord.Embed(description=f"{msg}", color=embed_color)
                await asyncio.to_thread(
                    requests.post,
                    shards_log_webhook,
                    json={"embeds": [embed.to_dict()]},
                    timeout=3,
                )
            else:
                # No webhook configured, silence warning
                pass
        except Exception as e:
            logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

    @commands.Cog.listener()
    async def on_disconnect(self):
        await self._emit_gateway_log(
            scope="global",
            event_name="disconnect",
            message="บอทถูกตัดการเชื่อมต่อจาก Discord",
            embed_color=color.red,
            logger_method="warning",
        )

    @commands.Cog.listener()
    async def on_resumed(self):
        await self._emit_gateway_log(
            scope="global",
            event_name="resumed",
            message="บอทเชื่อมต่อ Discord กลับมาแล้ว",
            embed_color=color.orange,
            logger_method="info",
        )

    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id):
        await self._emit_gateway_log(
            scope="shard",
            event_name="ready",
            message=f"Shard {shard_id} is ready",
            embed_color=color.green,
            logger_method="info",
            shard_id=shard_id,
            cooldown_seconds=self._gateway_ready_log_cooldown_seconds,
        )

    @commands.Cog.listener()
    async def on_shard_disconnect(self, shard_id):
        if self._is_startup_transient_shard_disconnect():
            await self._emit_gateway_log(
                scope="shard",
                event_name="disconnect_startup",
                message=f"Shard {shard_id} disconnected during startup",
                embed_color=color.orange,
                logger_method="info",
                shard_id=shard_id,
            )
            return
        await self._emit_gateway_log(
            scope="shard",
            event_name="disconnect",
            message=f"Shard {shard_id} is disconnected",
            embed_color=color.red,
            logger_method="warning",
            shard_id=shard_id,
        )

    @commands.Cog.listener()
    async def on_shard_resumed(self, shard_id):
        await self._emit_gateway_log(
            scope="shard",
            event_name="resumed",
            message=f"Shard {shard_id} is resumed",
            embed_color=color.orange,
            logger_method="info",
            shard_id=shard_id,
        )
    
    # event when a cog is loaded
    @commands.Cog.listener()
    async def on_cog_load(self, cog):
        logger.info(f"Cog {cog.qualified_name} loaded")
