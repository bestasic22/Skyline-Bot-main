import asyncio
import errno
import socket
import subprocess
import traceback
import json
import time
import os
import datetime
import tempfile
import warnings

import discord
import discord.http
import uvicorn

from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.console.logging import logger
from skylinebot.config.config import BotConfigClass

BotConfig = BotConfigClass()
bot = AutoShardedBot()
_BOT_RUNTIME_LOCK_SOCKET: socket.socket | None = None
_BOT_RUNTIME_LOCK_FILE = None


def _configure_windows_event_loop_policy() -> None:
    if os.name != "nt":
        return
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
                message=r".*WindowsSelectorEventLoopPolicy.*",
            )
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
                message=r".*get_event_loop_policy.*",
            )
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
                message=r".*set_event_loop_policy.*",
            )
            policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
            if policy_cls is None:
                return
            try:
                current_policy = asyncio.get_event_loop_policy()
                if isinstance(current_policy, policy_cls):
                    return
            except Exception:
                pass
            # Selector policy is generally more stable with discord gateway SSL on Windows.
            asyncio.set_event_loop_policy(policy_cls())
    except Exception:
        pass


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


def _is_test_machine() -> bool:
    return _bool_env("TEST_MACHINE", False)


def _force_discord_runtime() -> bool:
    return _bool_env("FORCE_DISCORD_RUNTIME", False)


def _allow_discord_runtime_on_test() -> bool:
    if _force_discord_runtime():
        return True
    return _bool_env("ALLOW_DISCORD_RUNTIME_ON_TEST", False)


def _resolve_runtime_components() -> tuple[bool, bool]:
    """
    Returns (run_web, run_bot).
    Env:
      - RUN_COMPONENTS=all|web|bot|none
      - RUN_WEB=true|false
      - RUN_BOT=true|false
    """
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

    run_web = _bool_env("RUN_WEB", run_web)
    run_bot = _bool_env("RUN_BOT", run_bot)

    if _is_test_machine() and run_bot and not _allow_discord_runtime_on_test():
        logger.warning(
            "TEST_MACHINE=true detected: Discord runtime blocked on this machine. "
            "Set ALLOW_DISCORD_RUNTIME_ON_TEST=true or FORCE_DISCORD_RUNTIME=true "
            "only when you intentionally run Discord runtime on this machine."
        )
        run_bot = False
        if not run_web:
            run_web = True
            logger.info("Switching runtime to web-only mode on TEST_MACHINE.")

    if not run_web and not run_bot:
        if _is_test_machine() and not _allow_discord_runtime_on_test():
            logger.warning("No runtime components enabled; fallback to web-only mode on TEST_MACHINE.")
            run_web = True
        else:
            logger.warning("No runtime components enabled; fallback to bot-only mode.")
            run_bot = True

    return run_web, run_bot


def _is_dashboard_port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in str(host or "") else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, int(port)))
            return True
        except OSError as error:
            if error.errno in (errno.EADDRINUSE, 10048):
                return False
            return True


def _resolve_bot_lock_socket() -> tuple[str, int]:
    host = str(os.getenv("BOT_RUNTIME_LOCK_HOST", "127.0.0.1") or "127.0.0.1").strip()
    raw_port = str(os.getenv("BOT_RUNTIME_LOCK_PORT", "38472") or "38472").strip()
    try:
        port = int(raw_port)
    except Exception:
        port = 38472
    port = max(1025, min(port, 65535))
    return host, port


def _resolve_bot_lock_file() -> str:
    raw_path = str(os.getenv("BOT_RUNTIME_LOCK_FILE", "") or "").strip()
    if raw_path:
        return raw_path
    return os.path.join(tempfile.gettempdir(), "skylinebot-main-runtime.lock")


def _acquire_bot_file_lock() -> bool:
    global _BOT_RUNTIME_LOCK_FILE
    if _BOT_RUNTIME_LOCK_FILE is not None:
        return True

    lock_path = _resolve_bot_lock_file()
    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        try:
            os.makedirs(lock_dir, exist_ok=True)
        except Exception:
            pass

    try:
        lock_file = open(lock_path, "a+", encoding="utf-8")
    except Exception:
        return True

    try:
        lock_file.seek(0)
        lock_file.write("\0")
        lock_file.flush()
        lock_file.seek(0)

        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        _BOT_RUNTIME_LOCK_FILE = lock_file
        return True
    except OSError:
        try:
            lock_file.close()
        except Exception:
            pass
        return False
    except Exception:
        try:
            lock_file.close()
        except Exception:
            pass
        return True


def _acquire_bot_runtime_lock() -> bool:
    global _BOT_RUNTIME_LOCK_SOCKET
    if _BOT_RUNTIME_LOCK_SOCKET is not None:
        return True

    if not _acquire_bot_file_lock():
        logger.separator()
        logger.error(
            "Duplicate bot runtime detected. Runtime lock file is already held by another process."
        )
        logger.warning("Stopping this process to prevent duplicated replies and slash timeouts.")
        logger.info("Keep only one bot process running (Scheduled Task or manual run, not both).")
        logger.separator()
        return False

    host, port = _resolve_bot_lock_socket()
    family = socket.AF_INET6 if ":" in host and host not in {"127.0.0.1", "localhost"} else socket.AF_INET
    lock_sock = socket.socket(family, socket.SOCK_STREAM)

    try:
        # Prevent multiple binds on Windows/Linux for singleton guard.
        lock_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    except Exception:
        pass
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            lock_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    except Exception:
        pass

    try:
        lock_sock.bind((host, int(port)))
        lock_sock.listen(1)
        _BOT_RUNTIME_LOCK_SOCKET = lock_sock
        return True
    except OSError as error:
        try:
            lock_sock.close()
        except Exception:
            pass
        if error.errno in (errno.EADDRINUSE, 10048, 10013):
            owner_pid = _find_port_listener_pid(port)
            owner_hint = _resolve_pid_hint(owner_pid)
            logger.separator()
            logger.error(
                f"Duplicate bot runtime detected. Lock {host}:{port} is already in use by {owner_hint}"
            )
            logger.warning("Stopping this process to prevent duplicated replies and slash timeouts.")
            logger.info("Keep only one bot process running (Scheduled Task or manual run, not both).")
            logger.separator()
            _release_bot_runtime_lock()
            return False
        raise


def _release_bot_runtime_lock() -> None:
    global _BOT_RUNTIME_LOCK_SOCKET, _BOT_RUNTIME_LOCK_FILE
    sock = _BOT_RUNTIME_LOCK_SOCKET
    _BOT_RUNTIME_LOCK_SOCKET = None
    if sock is not None:
        try:
            sock.close()
        except Exception:
            pass

    lock_file = _BOT_RUNTIME_LOCK_FILE
    _BOT_RUNTIME_LOCK_FILE = None
    if lock_file is not None:
        try:
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            lock_file.close()
        except Exception:
            pass


def _find_port_listener_pid(port: int) -> int | None:
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"], text=True, encoding="utf-8", errors="ignore"
        )
    except Exception:
        return None

    needle = f":{int(port)}"
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        cols = line.split()
        if len(cols) < 5:
            continue
        protocol, local_addr, _, state, pid = cols[0], cols[1], cols[2], cols[3], cols[4]
        if protocol.upper() != "TCP":
            continue
        if state.upper() != "LISTENING":
            continue
        if not local_addr.endswith(needle):
            continue
        try:
            return int(pid)
        except Exception:
            return None
    return None


def _resolve_pid_hint(pid: int | None) -> str:
    if not pid:
        return "unknown process"
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        for line in lines:
            if str(pid) in line and "Image Name" not in line:
                return line
    except Exception:
        pass
    return f"PID {pid}"


def _log_port_conflict_and_exit(host: str, port: int) -> None:
    pid = _find_port_listener_pid(port)
    owner = _resolve_pid_hint(pid)
    logger.separator()
    logger.error(
        f"Port conflict detected: {host}:{port} is already in use by {owner}"
    )
    logger.warning("SkylineBOT stopped to prevent duplicate instance startup.")
    logger.info("If you are using Git Bash, stop old process with:")
    if pid:
        logger.info(f"  taskkill /PID {pid} /F")
    else:
        logger.info("  taskkill /PID <PID> /F")
    logger.info("Then start again: python main.py")
    logger.separator()


def _extract_retry_after_from_http_error(error: discord.HTTPException) -> float:
    retry_after = None
    try:
        retry_after = error.response.headers.get("Retry-After")
    except Exception:
        retry_after = None

    if retry_after is not None:
        try:
            parsed = float(retry_after)
            if parsed > 0:
                return parsed
        except Exception:
            pass

    try:
        payload = json.loads(getattr(error, "text", "") or "{}")
        parsed = float(payload.get("retry_after", 0))
        if parsed > 0:
            return parsed
    except Exception:
        pass

    return 5.0


async def _cleanup_bot_start_resources(target_bot: AutoShardedBot) -> None:
    """Best-effort cleanup for failed startup attempts to avoid leaked aiohttp sessions."""
    try:
        http_client = getattr(target_bot, "http", None)
        if http_client is None:
            return

        session = getattr(http_client, "_HTTPClient__session", None)
        if session is not None and not session.closed:
            await session.close()

        try:
            http_client.clear()
        except Exception:
            pass

        try:
            connector = getattr(http_client, "connector", None)
            if connector is not None and connector is not discord.utils.MISSING and connector.closed:
                http_client.connector = discord.utils.MISSING
        except Exception:
            try:
                http_client.connector = discord.utils.MISSING
            except Exception:
                pass
    except Exception:
        pass


async def _send_app_interaction_message_safe(
    interaction: discord.Interaction,
    message: str,
    *,
    ephemeral: bool = True,
) -> None:
    ignored_error_codes = {10062, 10015}  # Unknown interaction / Unknown webhook
    if interaction.is_expired():
        return
    if interaction.response.is_done():
        try:
            await interaction.followup.send(message, ephemeral=ephemeral)
        except discord.NotFound as error:
            if getattr(error, "code", None) in ignored_error_codes:
                return
            raise
        except discord.HTTPException as error:
            if getattr(error, "code", None) in ignored_error_codes:
                return
            raise
        return

    try:
        await interaction.response.send_message(message, ephemeral=ephemeral)
    except discord.NotFound as error:
        if getattr(error, "code", None) in ignored_error_codes:
            return
        raise
    except discord.HTTPException as error:
        code = getattr(error, "code", None)
        if code in ignored_error_codes:
            return
        if code != 40060:  # Interaction already acknowledged
            raise
        try:
            await interaction.followup.send(message, ephemeral=ephemeral)
        except discord.HTTPException as follow_error:
            if getattr(follow_error, "code", None) in ignored_error_codes:
                return
            raise


def _install_main_app_command_error_handler() -> None:
    if getattr(bot, "_main_app_command_error_handler_installed", False):
        return

    async def _on_main_app_command_error(
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        try:
            if isinstance(error, discord.app_commands.CheckFailure):
                msg = str(error).strip() or "You cannot use this command."
                await _send_app_interaction_message_safe(interaction, msg, ephemeral=True)
                return
            if isinstance(error, discord.app_commands.CommandOnCooldown):
                msg = "Command is on cooldown. Please try again shortly."
                await _send_app_interaction_message_safe(interaction, msg, ephemeral=True)
                return
            if isinstance(error, discord.app_commands.MissingPermissions):
                msg = "You do not have permission to use this command."
                await _send_app_interaction_message_safe(interaction, msg, ephemeral=True)
                return

            logger.error(f"Unhandled slash command error: {type(error).__name__}: {error}")
            await _send_app_interaction_message_safe(
                interaction,
                "An error occurred while processing this slash command. Please try again.",
                ephemeral=True,
            )
        except Exception:
            logger.error(f"Slash error handler failure: {traceback.format_exc()}")

    bot.tree.on_error = _on_main_app_command_error
    setattr(bot, "_main_app_command_error_handler_installed", True)


async def main():
    try:
        run_web, run_bot = _resolve_runtime_components()
        logger.info(
            f"Runtime components => web={run_web}, bot={run_bot}, dashboard_enabled={BotConfig.DASHBOARD_ENABLED}"
        )
        if run_bot:
            if not _acquire_bot_runtime_lock():
                return

        if run_web and BotConfig.DASHBOARD_ENABLED:
            if not _is_dashboard_port_available(BotConfig.WEB_HOST, BotConfig.WEB_PORT):
                _log_port_conflict_and_exit(BotConfig.WEB_HOST, BotConfig.WEB_PORT)
                return

        from skylinebot.workflows.bootstrap import prepare_runtime
        from skylinebot.workflows.ui_enhancer import patch_discord_ui
        from skylinebot.surface import server as surface_server
        from skylinebot.surface import runtime as surface_runtime
        from skylinebot.style.sync_emojis import run_sync

        allow_degraded_web_start = _bool_env("WEB_ALLOW_DEGRADED_START", True)
        runtime_ready = True

        patch_discord_ui()
        try:
            await prepare_runtime()
        except Exception as error:
            runtime_ready = False
            if run_web and allow_degraded_web_start:
                run_bot = False
                logger.warning(
                    "Runtime bootstrap failed (storage/cache unavailable). "
                    "Starting web in degraded mode with bot disabled."
                )
                logger.warning(f"Bootstrap error: {error}")
            else:
                raise

        if run_bot:
            surface_server.bind_bot(bot)
        if runtime_ready and run_bot:
            surface_runtime.set_discord_service_state(
                level="starting",
                message="กำลังเชื่อมต่อ Discord API...",
                attempt=0,
            )
        elif runtime_ready and not run_bot:
            surface_runtime.set_discord_service_state(
                level="stopped",
                message="Discord runtime is disabled by RUN_COMPONENTS/RUN_BOT",
                attempt=0,
            )
        else:
            surface_runtime.set_discord_service_state(
                level="degraded",
                message="Database unavailable. Web dashboard started in degraded mode.",
                attempt=0,
            )

        async def _mark_discord_ready(*_args):
            surface_runtime.set_discord_service_state(
                level="ok",
                message="Discord พร้อมใช้งาน",
                attempt=0,
            )

        async def _mark_discord_resumed(*_args):
            surface_runtime.set_discord_service_state(
                level="ok",
                message="Discord กลับมาพร้อมใช้งาน",
                attempt=0,
            )

        async def _mark_discord_disconnect(*_args):
            surface_runtime.set_discord_service_state(
                level="degraded",
                message="การเชื่อมต่อ Discord ขาดหายชั่วคราว",
            )

        if run_bot:
            _install_main_app_command_error_handler()
            bot.add_listener(_mark_discord_ready, "on_ready")
            bot.add_listener(_mark_discord_resumed, "on_resumed")
            bot.add_listener(_mark_discord_disconnect, "on_disconnect")
            await bot.load_extension("skylinebot.src")

        tasks = []

        async def start_bot():
            retry_backoff = 5.0
            attempt = 0
            try:
                while True:
                    attempt += 1
                    try:
                        surface_runtime.set_discord_service_state(
                            level="starting",
                            message="กำลังเชื่อมต่อ Discord API...",
                            attempt=attempt,
                        )
                        await bot.start(BotConfig.TOKEN, reconnect=True)
                        return
                    except KeyboardInterrupt:
                        logger.error("Bot has been stopped")
                        surface_runtime.set_discord_service_state(
                            level="stopped",
                            message="บอทถูกหยุดการทำงาน",
                            attempt=attempt,
                        )
                        return
                    except discord.LoginFailure as error:
                        logger.error(f"Login failed. {error}")
                        surface_runtime.set_discord_service_state(
                            level="auth_error",
                            message="Discord ปฏิเสธการยืนยันตัวตนบอท (ตรวจสอบ TOKEN)",
                            status_code=401,
                            attempt=attempt,
                        )
                        await _cleanup_bot_start_resources(bot)
                        return
                    except discord.RateLimited as error:
                        retry_after = max(float(getattr(error, "retry_after", 5.0) or 5.0), 1.0)
                        logger.warning(
                            f"Discord rate limit while starting bot (attempt {attempt}). "
                            f"Retrying in {retry_after:.1f}s"
                        )
                        surface_runtime.set_discord_service_state(
                            level="degraded",
                            message=f"Discord จำกัดการเรียกใช้งานชั่วคราว (retry in {retry_after:.1f}s)",
                            status_code=429,
                            retry_after=retry_after,
                            attempt=attempt,
                        )
                        await _cleanup_bot_start_resources(bot)
                        await asyncio.sleep(retry_after)
                        retry_backoff = min(max(retry_after * 2, retry_backoff), 60.0)
                    except discord.HTTPException as error:
                        status = getattr(error, "status", None)
                        if status == 401:
                            logger.error("Discord rejected token (HTTP 401). Please check TOKEN in .env")
                            surface_runtime.set_discord_service_state(
                                level="auth_error",
                                message="Discord ปฏิเสธ TOKEN (HTTP 401)",
                                status_code=401,
                                attempt=attempt,
                            )
                            await _cleanup_bot_start_resources(bot)
                            return

                        retry_after = max(_extract_retry_after_from_http_error(error), 1.0)
                        logger.warning(
                            f"Discord API error while starting bot (HTTP {status or 'unknown'}, attempt {attempt}). "
                            f"Retrying in {retry_after:.1f}s"
                        )
                        if isinstance(status, int) and status >= 500:
                            level = "outage"
                            state_message = (
                                f"Discord ไม่พร้อมใช้งานชั่วคราว (HTTP {status})"
                            )
                        elif status == 429:
                            level = "degraded"
                            state_message = "Discord จำกัดการเรียกใช้งานชั่วคราว (HTTP 429)"
                        else:
                            level = "degraded"
                            state_message = f"เกิดปัญหาการเชื่อมต่อ Discord (HTTP {status or 'unknown'})"
                        surface_runtime.set_discord_service_state(
                            level=level,
                            message=state_message,
                            status_code=status if isinstance(status, int) else None,
                            retry_after=retry_after,
                            attempt=attempt,
                        )
                        await _cleanup_bot_start_resources(bot)
                        await asyncio.sleep(retry_after)
                        retry_backoff = min(max(retry_after * 2, retry_backoff), 60.0)
                    except OSError as error:
                        logger.warning(
                            f"Network error while starting bot (attempt {attempt}): {error}. "
                            f"Retrying in {retry_backoff:.1f}s"
                        )
                        surface_runtime.set_discord_service_state(
                            level="outage",
                            message="เชื่อมต่อ Discord ไม่สำเร็จเนื่องจากปัญหาเครือข่าย",
                            retry_after=retry_backoff,
                            attempt=attempt,
                        )
                        await _cleanup_bot_start_resources(bot)
                        await asyncio.sleep(retry_backoff)
                        retry_backoff = min(retry_backoff * 2, 60.0)
                    except Exception:
                        logger.error(
                            f"Unexpected startup error. Retrying in {retry_backoff:.1f}s\n"
                            f"{traceback.format_exc()}"
                        )
                        surface_runtime.set_discord_service_state(
                            level="degraded",
                            message="เกิดข้อผิดพลาดขณะเชื่อมต่อ Discord กำลังลองใหม่",
                            retry_after=retry_backoff,
                            attempt=attempt,
                        )
                        await _cleanup_bot_start_resources(bot)
                        await asyncio.sleep(retry_backoff)
                        retry_backoff = min(retry_backoff * 2, 60.0)
            except Exception:
                logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

        async def start_delayed_emoji_sync():
            if not BotConfig.SYNC_EMOJIS:
                logger.info("EmojiSync is currently disabled via config.")
                return

            try:
                delay_seconds = max(float(getattr(BotConfig, "SYNC_EMOJIS_START_DELAY_SECONDS", 45.0)), 0.0)
            except Exception:
                delay_seconds = 45.0

            try:
                should_wait_ready = bool(getattr(BotConfig, "SYNC_EMOJIS_AFTER_READY", True))
            except Exception:
                should_wait_ready = True

            try:
                if should_wait_ready:
                    logger.info(
                        f"EmojiSync scheduled after bot is ready (+{delay_seconds:.0f}s delay)."
                    )
                    while not bot.is_closed():
                        if getattr(bot, "user", None) is not None and bot.is_ready():
                            break
                        await asyncio.sleep(1)
                    if bot.is_closed():
                        return
                    if delay_seconds > 0:
                        await asyncio.sleep(delay_seconds)
                elif delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)

                logger.separator()
                await asyncio.to_thread(run_sync)
                logger.separator()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning(f"EmojiSync background task skipped due to startup error: {error}")

        async def discord_runtime_heartbeat():
            def _resolve_snapshot_mode() -> str:
                raw_mode = str(os.getenv("DISCORD_RUNTIME_SNAPSHOT_MODE", "full") or "").strip().lower()
                if raw_mode in {"off", "none", "disabled", "0", "false"}:
                    return "off"
                if raw_mode in {"full", "detail", "detailed"}:
                    return "full"
                return "summary"

            def _build_runtime_snapshot_summary(
                guilds: list[object],
                *,
                bot_user: object,
                shard_total: int,
                shard_connected: int,
                member_count_total: int,
            ) -> dict[str, object]:
                bot_created_at = getattr(bot_user, "created_at", None)
                if isinstance(bot_created_at, datetime.datetime):
                    bot_created_ts = int(bot_created_at.timestamp())
                else:
                    bot_created_ts = 0

                guild_rows: list[dict[str, object]] = []
                for guild in guilds:
                    me_member = getattr(guild, "me", None)
                    me_top_role = getattr(me_member, "top_role", None)
                    me_permissions = getattr(me_member, "guild_permissions", None)
                    guild_rows.append(
                        {
                            "id": str(getattr(guild, "id", "") or ""),
                            "name": str(getattr(guild, "name", "") or ""),
                            "icon_url": str(getattr(getattr(guild, "icon", None), "url", "") or ""),
                            "member_count": int(getattr(guild, "member_count", 0) or 0),
                            "owner_id": int(getattr(guild, "owner_id", 0) or 0),
                            "channels": [],
                            "roles": [],
                            "members": [],
                            "me": {
                                "id": str(getattr(me_member, "id", "") or ""),
                                "top_role_position": int(getattr(me_top_role, "position", 0) or 0),
                                "guild_permissions_manage_roles": bool(
                                    getattr(me_permissions, "manage_roles", False)
                                ),
                            },
                        }
                    )

                return {
                    "bot": {
                        "id": str(getattr(bot_user, "id", "") or ""),
                        "name": str(getattr(bot_user, "name", "") or ""),
                        "display_name": str(
                            getattr(bot_user, "display_name", "") or getattr(bot_user, "name", "") or ""
                        ),
                        "avatar_url": str(
                            getattr(getattr(bot_user, "display_avatar", None), "url", "")
                            or getattr(getattr(bot_user, "avatar", None), "url", "")
                            or ""
                        ),
                        "created_at_ts": bot_created_ts,
                        "guild_count": len(guilds),
                        "member_count": member_count_total,
                        "shard_total": shard_total,
                        "shard_connected": shard_connected,
                    },
                    "guilds": guild_rows,
                    "updated_at": float(time.time()),
                }

            def _build_runtime_snapshot_full(
                guilds: list[object],
                *,
                bot_user: object,
                shard_total: int,
                shard_connected: int,
                member_count_total: int,
            ) -> dict[str, object]:
                def _normalized_member_status(member_obj: object) -> str:
                    status_raw = str(getattr(member_obj, "status", "offline") or "offline").strip().lower()
                    if status_raw.startswith("status."):
                        status_raw = status_raw.split(".", 1)[1].strip()
                    if status_raw in {"online", "idle", "dnd", "offline", "invisible"}:
                        return status_raw
                    return "offline"

                def _activity_type_name(activity_obj: object) -> str:
                    raw_type = getattr(activity_obj, "type", None)
                    type_name = str(getattr(raw_type, "name", "") or "").strip().lower()
                    if type_name:
                        return type_name
                    fallback = str(raw_type or "").strip().lower()
                    if fallback.startswith("activitytype."):
                        fallback = fallback.split(".", 1)[1].strip()
                    return fallback

                def _compact_activity(activity_obj: object) -> dict[str, str] | None:
                    activity_type = _activity_type_name(activity_obj)
                    activity_name = str(getattr(activity_obj, "name", "") or "").strip()[:120]
                    activity_state = str(getattr(activity_obj, "state", "") or "").strip()[:140]
                    activity_details = str(getattr(activity_obj, "details", "") or "").strip()[:140]
                    activity_emoji = str(getattr(activity_obj, "emoji", "") or "").strip()[:64]
                    if not (
                        activity_type
                        or activity_name
                        or activity_state
                        or activity_details
                        or activity_emoji
                    ):
                        return None
                    return {
                        "type": activity_type,
                        "name": activity_name,
                        "state": activity_state,
                        "details": activity_details,
                        "emoji": activity_emoji,
                    }

                guild_rows: list[dict[str, object]] = []
                for guild in guilds:
                    channels_payload: list[dict[str, object]] = []
                    for channel in list(getattr(guild, "channels", []) or [])[:1500]:
                        category = getattr(channel, "category", None)
                        category_position = int(getattr(category, "position", 0) or 0) if category else 0
                        channels_payload.append(
                            {
                                "id": str(getattr(channel, "id", "") or ""),
                                "name": str(getattr(channel, "name", "") or ""),
                                "type": str(getattr(channel, "type", "") or "").lower(),
                                "position": int(getattr(channel, "position", 0) or 0),
                                "category_position": category_position,
                            }
                        )

                    roles_payload: list[dict[str, object]] = []
                    for role in list(getattr(guild, "roles", []) or [])[:500]:
                        role_permissions = getattr(role, "permissions", None)
                        roles_payload.append(
                            {
                                "id": str(getattr(role, "id", "") or ""),
                                "name": str(getattr(role, "name", "") or ""),
                                "position": int(getattr(role, "position", 0) or 0),
                                "color_value": int(getattr(getattr(role, "color", None), "value", 0) or 0),
                                "is_default": bool(getattr(role, "is_default", lambda: False)()),
                                "managed": bool(getattr(role, "managed", False)),
                                "permissions_admin": bool(getattr(role_permissions, "administrator", False)),
                            }
                        )

                    members_payload: list[dict[str, object]] = []
                    for member in list(getattr(guild, "members", []) or [])[:3000]:
                        avatar_url = str(
                            getattr(getattr(member, "display_avatar", None), "url", "")
                            or getattr(getattr(member, "avatar", None), "url", "")
                            or ""
                        )
                        activities_payload: list[dict[str, str]] = []
                        for activity in list(getattr(member, "activities", []) or [])[:5]:
                            compact = _compact_activity(activity)
                            if compact is not None:
                                activities_payload.append(compact)
                        members_payload.append(
                            {
                                "id": str(getattr(member, "id", "") or ""),
                                "name": str(getattr(member, "name", "") or ""),
                                "display_name": str(
                                    getattr(member, "display_name", "") or getattr(member, "name", "") or ""
                                ),
                                "bot": bool(getattr(member, "bot", False)),
                                "status": _normalized_member_status(member),
                                "avatar_url": avatar_url,
                                "activities": activities_payload,
                            }
                        )

                    me_member = getattr(guild, "me", None)
                    me_top_role = getattr(me_member, "top_role", None)
                    me_permissions = getattr(me_member, "guild_permissions", None)
                    guild_rows.append(
                        {
                            "id": str(getattr(guild, "id", "") or ""),
                            "name": str(getattr(guild, "name", "") or ""),
                            "icon_url": str(getattr(getattr(guild, "icon", None), "url", "") or ""),
                            "member_count": int(getattr(guild, "member_count", 0) or 0),
                            "owner_id": int(getattr(guild, "owner_id", 0) or 0),
                            "channels": channels_payload,
                            "roles": roles_payload,
                            "members": members_payload,
                            "me": {
                                "id": str(getattr(me_member, "id", "") or ""),
                                "top_role_position": int(getattr(me_top_role, "position", 0) or 0),
                                "guild_permissions_manage_roles": bool(
                                    getattr(me_permissions, "manage_roles", False)
                                ),
                            },
                        }
                    )

                bot_created_at = getattr(bot_user, "created_at", None)
                if isinstance(bot_created_at, datetime.datetime):
                    bot_created_ts = int(bot_created_at.timestamp())
                else:
                    bot_created_ts = 0

                return {
                    "bot": {
                        "id": str(getattr(bot_user, "id", "") or ""),
                        "name": str(getattr(bot_user, "name", "") or ""),
                        "display_name": str(
                            getattr(bot_user, "display_name", "") or getattr(bot_user, "name", "") or ""
                        ),
                        "avatar_url": str(
                            getattr(getattr(bot_user, "display_avatar", None), "url", "")
                            or getattr(getattr(bot_user, "avatar", None), "url", "")
                            or ""
                        ),
                        "created_at_ts": bot_created_ts,
                        "guild_count": len(guilds),
                        "member_count": member_count_total,
                        "shard_total": shard_total,
                        "shard_connected": shard_connected,
                    },
                    "guilds": guild_rows,
                    "updated_at": float(time.time()),
                }

            try:
                raw_interval = str(os.getenv("DISCORD_RUNTIME_HEARTBEAT_SECONDS", "20") or "20").strip()
                try:
                    interval_seconds = int(float(raw_interval))
                except Exception:
                    interval_seconds = 20
                # Keep heartbeat in the requested 15-30s band.
                interval_seconds = max(15, min(interval_seconds, 30))

                raw_snapshot_refresh = str(
                    os.getenv("DISCORD_RUNTIME_SNAPSHOT_REFRESH_SECONDS", "180") or "180"
                ).strip()
                try:
                    snapshot_refresh_seconds = int(float(raw_snapshot_refresh))
                except Exception:
                    snapshot_refresh_seconds = 180
                snapshot_refresh_seconds = max(30, min(snapshot_refresh_seconds, 3600))
                snapshot_mode = _resolve_snapshot_mode()
                last_snapshot_refresh_at = 0.0

                await asyncio.sleep(5)
                while True:
                    try:
                        if bot.is_closed():
                            surface_runtime.set_discord_service_state(
                                level="stopped",
                                message="Discord runtime stopped",
                                attempt=0,
                            )
                            return

                        bot_user = getattr(bot, "user", None)
                        if not bot_user:
                            # Startup/auth phase: preserve state from startup loop.
                            await asyncio.sleep(interval_seconds)
                            continue

                        if bot.is_ready():
                            guilds = list(getattr(bot, "guilds", []) or [])
                            guild_count = len(guilds)
                            member_count = sum(int(getattr(guild, "member_count", 0) or 0) for guild in guilds)
                            shard_map = dict(getattr(bot, "shards", {}) or {})
                            shard_total = len(shard_map)
                            shard_connected = sum(
                                1
                                for shard in shard_map.values()
                                if not bool(getattr(shard, "is_closed", lambda: True)())
                            )
                            heartbeat_message = (
                                f"Discord online | guilds={guild_count} users={member_count} "
                                f"shards={shard_connected}/{shard_total}"
                            )
                            runtime_snapshot: dict[str, object] | None = None
                            now_mono = time.monotonic()
                            should_refresh_snapshot = False
                            if snapshot_mode == "summary":
                                should_refresh_snapshot = True
                            elif snapshot_mode == "full":
                                should_refresh_snapshot = (
                                    last_snapshot_refresh_at <= 0.0
                                    or (now_mono - last_snapshot_refresh_at) >= snapshot_refresh_seconds
                                )

                            if should_refresh_snapshot:
                                bot_user_live = getattr(bot, "user", None)
                                if snapshot_mode == "full":
                                    runtime_snapshot = _build_runtime_snapshot_full(
                                        guilds,
                                        bot_user=bot_user_live,
                                        shard_total=shard_total,
                                        shard_connected=shard_connected,
                                        member_count_total=member_count,
                                    )
                                else:
                                    runtime_snapshot = _build_runtime_snapshot_summary(
                                        guilds,
                                        bot_user=bot_user_live,
                                        shard_total=shard_total,
                                        shard_connected=shard_connected,
                                        member_count_total=member_count,
                                    )
                                last_snapshot_refresh_at = now_mono

                            surface_runtime.set_discord_service_state(
                                level="ok",
                                message=heartbeat_message,
                                attempt=0,
                                snapshot=runtime_snapshot,
                            )
                        else:
                            surface_runtime.set_discord_service_state(
                                level="degraded",
                                message="Discord reconnecting / waiting for ready",
                                attempt=0,
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as heartbeat_error:
                        logger.warning(f"Discord runtime heartbeat warning: {heartbeat_error}")
                    await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning(f"Discord runtime heartbeat stopped unexpectedly: {error}")

        async def start_web():
            try:
                import logging
                import re
                class EndpointFilter(logging.Filter):
                    def __init__(self) -> None:
                        super().__init__()
                        self._first_ok_seen: set[str] = set()
                        self._last_allow_at: dict[str, float] = {}
                        self._allow_interval_seconds = 300.0
                        self._noisy_paths = {
                            "/",
                            "/dashboard",
                            "/dashboard/status",
                            "/dashboard/runtime/discord",
                        }

                    @staticmethod
                    def _parse_access_log(message: str) -> tuple[str, int] | None:
                        match = re.search(r'"[A-Z]+\s+([^"\s]+)\s+HTTP/[^"]+"\s+(\d{3})', message)
                        if not match:
                            return None
                        raw_path = str(match.group(1) or "").strip()
                        status_code = int(match.group(2))
                        path = raw_path.split("?", 1)[0].strip() or "/"
                        return path, status_code

                    def filter(self, record: logging.LogRecord) -> bool:
                        message = record.getMessage()
                        if "/live" in message:
                            return False

                        parsed = self._parse_access_log(message)
                        if parsed is None:
                            return True

                        path, status_code = parsed
                        if path not in self._noisy_paths:
                            return True

                        # Keep errors visible at all times.
                        if status_code >= 400:
                            return True

                        # Only suppress repetitive success/redirect logs.
                        if status_code < 200 or status_code >= 400:
                            return True

                        key = f"{path}:{status_code}"
                        now = time.monotonic()
                        if key not in self._first_ok_seen:
                            self._first_ok_seen.add(key)
                            self._last_allow_at[key] = now
                            return True

                        last = self._last_allow_at.get(key, 0.0)
                        if (now - last) >= self._allow_interval_seconds:
                            self._last_allow_at[key] = now
                            return True

                        return False
                 
                logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

                ssl_kwargs: dict[str, object] = {}
                if bool(getattr(BotConfig, "WEB_SSL_ENABLED", False)):
                    certfile = str(getattr(BotConfig, "WEB_SSL_CERTFILE", "") or "").strip()
                    keyfile = str(getattr(BotConfig, "WEB_SSL_KEYFILE", "") or "").strip()
                    if certfile and keyfile:
                        ssl_kwargs["ssl_certfile"] = certfile
                        ssl_kwargs["ssl_keyfile"] = keyfile
                        key_password = str(getattr(BotConfig, "WEB_SSL_KEYFILE_PASSWORD", "") or "").strip()
                        if key_password:
                            ssl_kwargs["ssl_keyfile_password"] = key_password
                        ca_certs = str(getattr(BotConfig, "WEB_SSL_CA_CERTS", "") or "").strip()
                        if ca_certs:
                            ssl_kwargs["ssl_ca_certs"] = ca_certs
                        logger.info(
                            f"HTTPS mode enabled for dashboard ({BotConfig.WEB_HOST}:{BotConfig.WEB_PORT})"
                        )
                        if int(BotConfig.WEB_PORT) != 443:
                            logger.warning(
                                f"WEB_SSL_ENABLED=True but WEB_PORT={BotConfig.WEB_PORT} (recommended: 443)"
                            )
                    else:
                        logger.warning(
                            "WEB_SSL_ENABLED=True but WEB_SSL_CERTFILE/WEB_SSL_KEYFILE not configured; using HTTP mode"
                        )

                web_config = uvicorn.Config(
                    surface_server.app,
                    host=BotConfig.WEB_HOST,
                    port=BotConfig.WEB_PORT,
                    access_log=False,
                    **ssl_kwargs,
                )
                server = uvicorn.Server(web_config)
                await server.serve()
            except Exception:
                logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

        if run_web:
            if BotConfig.DASHBOARD_ENABLED:
                try:
                    tasks.append(asyncio.create_task(start_web()))
                except Exception:
                    logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
            else:
                logger.info("\033[1;31mDashboard is disabled via config.\033[0m")
        else:
            logger.info("Web dashboard runtime is disabled via RUN_COMPONENTS/RUN_WEB.")

        if run_bot:
            try:
                tasks.append(asyncio.create_task(start_bot()))
            except Exception:
                logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
            try:
                tasks.append(asyncio.create_task(discord_runtime_heartbeat()))
            except Exception:
                logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
            try:
                tasks.append(asyncio.create_task(start_delayed_emoji_sync()))
            except Exception:
                logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
        else:
            logger.info("Discord bot runtime is disabled via RUN_COMPONENTS/RUN_BOT.")

        if not tasks:
            logger.warning("No active tasks were scheduled. Exiting.")
            return

        await asyncio.gather(*tasks)
    except Exception:
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
    finally:
        _release_bot_runtime_lock()


if __name__ == "__main__":
    _configure_windows_event_loop_policy()
    asyncio.run(main())
