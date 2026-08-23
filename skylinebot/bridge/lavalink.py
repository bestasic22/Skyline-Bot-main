import asyncio
import logging
import os
import time
import traceback

import wavelink

from skylinebot.console.logging import logger


class _WavelinkConnectSpamFilter(logging.Filter):
    """Reduce repeated connect/reconnect warnings from wavelink logger."""

    def __init__(self, min_interval_sec: float = 90.0):
        super().__init__()
        self._min_interval_sec = max(float(min_interval_sec or 90.0), 1.0)
        self._last_emit_at: dict[str, float] = {}
        self._suppressed: dict[str, int] = {}

    @staticmethod
    def _is_noisy_message(text: str) -> bool:
        lower = text.lower()
        return (
            "unexpected error occurred while connecting node" in lower
            or "unable to successfully connect/reconnect to lavalink after" in lower
        )

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = str(record.getMessage() or "")
        except Exception:
            return True

        if not self._is_noisy_message(message):
            return True

        now = time.monotonic()
        key = message
        last_emit = self._last_emit_at.get(key, 0.0)
        if (now - last_emit) < self._min_interval_sec:
            self._suppressed[key] = int(self._suppressed.get(key, 0)) + 1
            return False

        suppressed = int(self._suppressed.pop(key, 0))
        if suppressed > 0:
            record.msg = f"{message} | suppressed={suppressed}"
            record.args = ()
        self._last_emit_at[key] = now
        return True


def _resolve_logger_level() -> int:
    raw_level = str(os.getenv("WAVELINK_LOG_LEVEL", "WARNING") or "WARNING").strip().upper()
    return int(getattr(logging, raw_level, logging.WARNING))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return True
    if value in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(str(os.getenv(name, str(default)) or str(default)).strip())
    except Exception:
        parsed = int(default)
    parsed = max(min_value, parsed)
    parsed = min(max_value, parsed)
    return parsed


_LOG_REPEAT_LAST_AT: dict[str, float] = {}
_LOG_REPEAT_SUPPRESSED: dict[str, int] = {}


def _warning_throttled(key: str, message: str, *, min_interval_sec: float = 60.0) -> None:
    interval = max(float(min_interval_sec or 60.0), 1.0)
    now = time.monotonic()
    last_at = _LOG_REPEAT_LAST_AT.get(key, 0.0)
    if (now - last_at) >= interval:
        suppressed = int(_LOG_REPEAT_SUPPRESSED.pop(key, 0))
        suffix = f" | suppressed={suppressed}" if suppressed > 0 else ""
        logger.warning(f"{message}{suffix}")
        _LOG_REPEAT_LAST_AT[key] = now
        return
    _LOG_REPEAT_SUPPRESSED[key] = int(_LOG_REPEAT_SUPPRESSED.get(key, 0)) + 1


_CONNECT_SPAM_FILTER = _WavelinkConnectSpamFilter(
    min_interval_sec=float(_env_int("LAVALINK_SPAM_LOG_INTERVAL_SEC", 90, 5, 900))
)
_WAVELINK_LOG_LEVEL = _resolve_logger_level()

for _logger_name in ("wavelink", "wavelink.websocket", "wavelink.player", "wavelink.node"):
    _target_logger = logging.getLogger(_logger_name)
    _target_logger.setLevel(_WAVELINK_LOG_LEVEL)
    for _flt in list(_target_logger.filters):
        if isinstance(_flt, _WavelinkConnectSpamFilter):
            _target_logger.removeFilter(_flt)
    _target_logger.addFilter(_CONNECT_SPAM_FILTER)

logging.getLogger("discord.voice_state").setLevel(logging.WARNING)


# Monkey-patch wavelink.Player._dispatch_voice_update to surface the silent
# LavalinkException that causes wavelink.Player.connect to time out.
_original_dispatch = wavelink.Player._dispatch_voice_update


def _root_cause_hint(error: Exception) -> str:
    text = str(error).lower()
    if "semaphore timeout" in text:
        return "remote_node_network_connectivity (not local event logic)"
    return "unknown_or_node_side_failure"


async def _patched_dispatch(self) -> None:
    guild_id = getattr(getattr(self, "guild", None), "id", None)
    voice = getattr(self, "_voice_state", {}).get("voice", {})
    session_id = voice.get("session_id")
    token = voice.get("token")
    endpoint = voice.get("endpoint")
    if not session_id or not token or not endpoint:
        return await _original_dispatch(self)

    channel_id = getattr(getattr(self, "channel", None), "id", None)
    voice_payload = {"sessionId": session_id, "token": token, "endpoint": endpoint}
    if channel_id is not None:
        voice_payload["channelId"] = str(channel_id)
    request = {"voice": voice_payload}
    node_uri = getattr(self.node, "uri", "?")
    try:
        await self.node._update_player(self.guild.id, data=request)
    except Exception as exc:
        exc_data = getattr(exc, "data", None) or getattr(exc, "_data", None)
        cause_hint = _root_cause_hint(exc)
        logger.error(
            f"[lavalink_dispatch] voice update rejected | guild={guild_id} channel={channel_id} node={node_uri} "
            f"| error={type(exc).__name__}: {exc} | root_cause_hint={cause_hint} | exc_data={exc_data}\n"
            f"{traceback.format_exc()}"
        )
        try:
            await self.disconnect()
        except Exception:
            pass
        return
    else:
        self._connection_event.set()


wavelink.Player._dispatch_voice_update = _patched_dispatch


running = False
_last_connect_started_at = 0.0
_node_lock = asyncio.Lock()
_HEALTH_TASK_ATTR = "_skylinebot_lavalink_health_task"


def _uri(host: str, port: int, secure: bool) -> str:
    return f"{'https' if secure else 'http'}://{host}:{port}/"


def _iter_pool_nodes() -> list:
    nodes_obj = getattr(wavelink.Pool, "nodes", None) or {}
    if isinstance(nodes_obj, dict):
        return list(nodes_obj.values())
    try:
        return list(nodes_obj)
    except Exception:
        return []


def _node_status_name(node) -> str:
    status = getattr(node, "status", None)
    return str(getattr(status, "name", status or "")).strip().upper()


def _has_node_with_status(*status_names: str) -> bool:
    expected = {str(name).strip().upper() for name in status_names if str(name).strip()}
    if not expected:
        return False
    for node in _iter_pool_nodes():
        if _node_status_name(node) in expected:
            return True
    return False


def _has_connected_node() -> bool:
    try:
        wavelink.Pool.get_node()
        return True
    except Exception:
        pass

    return _has_node_with_status("CONNECTED")


def _has_connecting_node() -> bool:
    return _has_node_with_status("CONNECTING")


async def _wait_for_connected_node(timeout_sec: float, poll_interval_sec: float = 0.25) -> bool:
    if _has_connected_node():
        return True
    timeout = max(float(timeout_sec or 0.0), 0.0)
    if timeout <= 0:
        return False

    poll_interval = max(float(poll_interval_sec or 0.25), 0.1)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _has_connected_node():
            return True
        if not _node_lock.locked() and not _has_connecting_node():
            break
        await asyncio.sleep(poll_interval)
    return _has_connected_node()


def _resolve_node_configs() -> list[tuple[str, str, int, str, bool]]:
    return [
        (
            "primary-local",
            os.getenv("LAVALINK_HOST_1", "127.0.0.1"),
            int(os.getenv("LAVALINK_PORT_1", "2333")),
            os.getenv("LAVALINK_PASSWORD_1", "youshallnotpass"),
            os.getenv("LAVALINK_SECURE_1", "false").lower() == "true",
        ),
        (
            "fallback-oracle-sg",
            os.getenv("LAVALINK_HOST_2", ""),
            int(os.getenv("LAVALINK_PORT_2", "25582")),
            os.getenv("LAVALINK_PASSWORD_2", ""),
            os.getenv("LAVALINK_SECURE_2", "false").lower() == "true",
        ),
    ]


async def _connect_nodes(bot, *, quiet: bool = False, trigger: str = "startup") -> int:
    node_retries = max(1, int(os.getenv("LAVALINK_NODE_RETRIES", "5")))
    connect_attempts = max(1, int(os.getenv("LAVALINK_CONNECT_ATTEMPTS", "3")))
    connect_backoff = max(1, int(os.getenv("LAVALINK_CONNECT_BACKOFF_SEC", "3")))
    fail_log_interval = float(_env_int("LAVALINK_CONNECT_FAIL_LOG_INTERVAL_SEC", 90, 5, 900))
    connected_count = 0

    for label, host, port, password, secure in _resolve_node_configs():
        if not host:
            continue
        if not password:
            if not quiet:
                logger.warning(
                    f"Skipping Lavalink {label} node because password is empty (set LAVALINK_PASSWORD_2 if you want to enable it)."
                )
            continue
        uri = _uri(host, port, secure)
        connected = False
        for attempt in range(1, connect_attempts + 1):
            node = wavelink.Node(uri=uri, password=password, retries=node_retries)
            try:
                await wavelink.Pool.connect(nodes=[node], client=bot)
                connected_count += 1
                connected = True
                if not quiet:
                    logger.info(f"[lavalink_connect] connected | node={label} uri={uri}")
                break
            except Exception as error:
                cause_hint = _root_cause_hint(error)
                message = (
                    f"[lavalink_connect] failed | node={label} uri={uri} "
                    f"| attempt={attempt}/{connect_attempts} node_retries={node_retries} "
                    f"| error={type(error).__name__}: {error} | root_cause_hint={cause_hint}"
                )
                if quiet:
                    _warning_throttled(
                        f"lavalink_connect_failed:{trigger}:{label}",
                        message,
                        min_interval_sec=fail_log_interval,
                    )
                else:
                    logger.warning(message)
                if attempt < connect_attempts:
                    await asyncio.sleep(connect_backoff * attempt)
        if not connected and not quiet:
            logger.warning(
                f"[lavalink_connect] node unavailable after retries | node={label} uri={uri} "
                f"| attempts={connect_attempts}"
            )

    return int(connected_count)


def _get_health_task(bot) -> asyncio.Task | None:
    task = getattr(bot, _HEALTH_TASK_ATTR, None)
    if isinstance(task, asyncio.Task):
        return task
    return None


def _ensure_health_task(bot) -> None:
    if not _env_bool("LAVALINK_HEALTHCHECK_ENABLED", True):
        return
    task = _get_health_task(bot)
    if task and not task.done():
        return

    async def _runner():
        await _lavalink_health_loop(bot)

    new_task = asyncio.create_task(_runner(), name="lavalink_healthcheck")

    def _done(_task: asyncio.Task) -> None:
        current = getattr(bot, _HEALTH_TASK_ATTR, None)
        if current is _task:
            setattr(bot, _HEALTH_TASK_ATTR, None)
        try:
            _task.result()
        except asyncio.CancelledError:
            pass
        except Exception as error:
            _warning_throttled(
                "lavalink_health_task_crash",
                f"[lavalink_health] healthcheck task crashed: {type(error).__name__}: {error}",
                min_interval_sec=60,
            )

    new_task.add_done_callback(_done)
    setattr(bot, _HEALTH_TASK_ATTR, new_task)


async def _lavalink_health_loop(bot) -> None:
    check_interval = float(_env_int("LAVALINK_HEALTHCHECK_INTERVAL_SEC", 25, 5, 300))
    base_backoff = float(_env_int("LAVALINK_HEALTHCHECK_BASE_BACKOFF_SEC", 5, 1, 120))
    max_backoff = float(_env_int("LAVALINK_HEALTHCHECK_MAX_BACKOFF_SEC", 120, 10, 1800))
    startup_grace = float(_env_int("LAVALINK_HEALTHCHECK_STARTUP_GRACE_SEC", 12, 0, 300))
    connect_settle = float(_env_int("LAVALINK_HEALTHCHECK_CONNECT_SETTLE_SEC", 30, 1, 300))
    fail_log_interval = float(_env_int("LAVALINK_HEALTHCHECK_LOG_INTERVAL_SEC", 60, 5, 900))

    if startup_grace > 0:
        await asyncio.sleep(startup_grace)

    consecutive_failures = 0
    connecting_since: float | None = None
    while not bot.is_closed():
        try:
            if not bot.is_ready():
                await asyncio.sleep(2)
                continue

            if _has_connected_node():
                if consecutive_failures > 0:
                    logger.info("[lavalink_health] node connection recovered.")
                consecutive_failures = 0
                connecting_since = None
                await asyncio.sleep(check_interval)
                continue

            if _node_lock.locked() or _has_connecting_node():
                now = time.monotonic()
                if connecting_since is None:
                    connecting_since = now
                if (now - connecting_since) < connect_settle:
                    await asyncio.sleep(min(2.0, check_interval))
                    continue
                if _has_connected_node():
                    consecutive_failures = 0
                    connecting_since = None
                    await asyncio.sleep(check_interval)
                    continue
                _warning_throttled(
                    "lavalink_health_connecting_timeout",
                    f"[lavalink_health] node still connecting after {int(now - connecting_since)}s; forcing reconnect attempt",
                    min_interval_sec=fail_log_interval,
                )
                connecting_since = None
            else:
                connecting_since = None

            consecutive_failures += 1
            backoff = min(max_backoff, base_backoff * (2 ** (consecutive_failures - 1)))
            backoff = max(backoff, check_interval)

            _warning_throttled(
                "lavalink_health_missing_node",
                f"[lavalink_health] no connected node detected | failures={consecutive_failures} | retry_in={int(backoff)}s",
                min_interval_sec=fail_log_interval,
            )

            try:
                await on_node(bot, quiet=True, trigger="healthcheck")
                if _has_connected_node():
                    logger.info("[lavalink_health] reconnect successful.")
                    consecutive_failures = 0
                    await asyncio.sleep(check_interval)
                    continue
            except Exception as error:
                _warning_throttled(
                    "lavalink_health_reconnect_fail",
                    f"[lavalink_health] reconnect failed: {type(error).__name__}: {error}",
                    min_interval_sec=fail_log_interval,
                )

            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            _warning_throttled(
                "lavalink_health_loop_error",
                f"[lavalink_health] loop error: {type(error).__name__}: {error}",
                min_interval_sec=fail_log_interval,
            )
            await asyncio.sleep(max(5.0, check_interval))


async def on_node(bot, *, quiet: bool = False, trigger: str = "startup") -> int:
    global running, _last_connect_started_at
    _ensure_health_task(bot)

    async with _node_lock:
        while not bot.is_closed() and not bot.is_ready():
            await asyncio.sleep(1)
        if bot.is_closed():
            return 0

        if running:
            if _has_connected_node():
                if not quiet:
                    logger.info("[lavalink_connect] connection already active; skipped duplicate connect call")
                return 0
            if _has_connecting_node():
                handshake_stale_after = float(_env_int("LAVALINK_CONNECTING_STALE_SEC", 20, 3, 600))
                elapsed = max(0.0, time.monotonic() - float(_last_connect_started_at or 0.0))
                if elapsed < handshake_stale_after:
                    if not quiet:
                        logger.info("[lavalink_connect] node handshake in progress; skipped duplicate connect call")
                    return 0
                _warning_throttled(
                    "lavalink_connect_handshake_stale",
                    f"[lavalink_connect] node handshake exceeded {int(handshake_stale_after)}s; retrying clean reconnect",
                    min_interval_sec=20,
                )
            else:
                _warning_throttled(
                    "lavalink_stale_running_state",
                    "[lavalink_connect] stale running state detected; retrying clean reconnect",
                    min_interval_sec=20,
                )

        running = True
        _last_connect_started_at = time.monotonic()
        connected_count = await _connect_nodes(bot, quiet=quiet, trigger=trigger)
        if connected_count <= 0:
            running = False
            raise RuntimeError("Unable to connect to any Lavalink nodes")

        ready_wait_sec = float(_env_int("LAVALINK_CONNECT_READY_WAIT_SEC", 8, 0, 120))
        ready_observed = True
        if ready_wait_sec > 0 and not _has_connected_node():
            ready_observed = await _wait_for_connected_node(ready_wait_sec)

        if not quiet:
            if ready_observed:
                logger.info(f"[lavalink_connect] connected successfully | nodes={connected_count}")
            else:
                logger.info(
                    f"[lavalink_connect] connect request accepted | nodes={connected_count} | "
                    f"awaiting_node_ready<={int(ready_wait_sec)}s"
                )
        return connected_count
