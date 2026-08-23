from __future__ import annotations

import json
import os
import secrets
import time
import datetime
from pathlib import Path
from typing import Any
import psutil

_bot = None
_sessions: dict[str, dict[str, Any]] = {}
_oauth_states: dict[str, dict[str, Any] | float] = {}
_discord_service_state: dict[str, Any] = {
    "level": "unknown",
    "message": "กำลังตรวจสอบสถานะ Discord",
    "status_code": None,
    "retry_after": None,
    "attempt": 0,
    "updated_at": 0.0,
    "pid": None,
    "pid_started_at": None,
    "source": "memory",
    "snapshot": {
        "bot": {},
        "guilds": [],
        "updated_at": 0.0,
    },
}
_last_discord_state_persist_at = 0.0
_last_discord_state_persist_signature = ""


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(str(raw).strip())
    except Exception:
        return float(default)


_DISCORD_STATE_PERSIST_MIN_INTERVAL_SECONDS = max(
    5.0,
    min(_float_env("DISCORD_RUNTIME_STATE_PERSIST_MIN_INTERVAL_SECONDS", 30.0), 600.0),
)


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


def _resolve_runtime_components() -> tuple[bool, bool]:
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
    return bool(run_web), bool(run_bot)


def _discord_state_file() -> Path:
    raw = str(os.getenv("DISCORD_RUNTIME_STATE_FILE", "") or "").strip()
    if raw:
        path = Path(raw)
    else:
        # Keep runtime state outside the repository by default so it doesn't
        # interfere with Git workflows across main machine / VPS.
        local_appdata = str(os.getenv("LOCALAPPDATA", "") or "").strip()
        if local_appdata:
            path = Path(local_appdata) / "SkylineBOT" / "runtime" / "discord_service_state.json"
        else:
            temp_dir = str(os.getenv("TEMP", "") or "").strip()
            if temp_dir:
                path = Path(temp_dir) / "SkylineBOT" / "runtime" / "discord_service_state.json"
            else:
                path = Path.home() / ".skylinebot" / "runtime" / "discord_service_state.json"
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[2]
        path = project_root / path
    return path


def _can_persist_discord_state() -> bool:
    persist_enabled = _bool_env("DISCORD_RUNTIME_STATE_PERSIST", True)
    if not persist_enabled:
        return False
    _run_web, run_bot = _resolve_runtime_components()
    return bool(run_bot)


def _write_persisted_discord_state(state: dict[str, Any]) -> None:
    try:
        path = _discord_state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception:
        pass


def _discord_state_persist_signature(state: dict[str, Any]) -> str:
    src = state if isinstance(state, dict) else {}
    parts = (
        str(src.get("level") or "").strip().lower(),
        str(src.get("message") or "").strip(),
        str(src.get("status_code") or ""),
        str(src.get("retry_after") or ""),
        str(src.get("attempt") or ""),
        str(src.get("pid") or ""),
        str(src.get("pid_started_at") or ""),
    )
    return "|".join(parts)


def _persist_discord_state_if_needed(state: dict[str, Any], *, force: bool = False) -> None:
    global _last_discord_state_persist_at, _last_discord_state_persist_signature
    if not _can_persist_discord_state():
        return
    payload = dict(state or {})
    payload["source"] = "persisted"
    signature = _discord_state_persist_signature(payload)
    now = time.monotonic()
    should_write = force or (signature != _last_discord_state_persist_signature)
    if not should_write:
        should_write = (now - float(_last_discord_state_persist_at)) >= _DISCORD_STATE_PERSIST_MIN_INTERVAL_SECONDS
    if not should_write:
        return
    _write_persisted_discord_state(payload)
    _last_discord_state_persist_at = now
    _last_discord_state_persist_signature = signature


def _read_persisted_discord_state() -> dict[str, Any] | None:
    if not _bool_env("DISCORD_RUNTIME_STATE_PERSIST", True):
        return None
    try:
        path = _discord_state_file()
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _safe_positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed <= 0:
        return None
    return parsed


def _current_process_started_at() -> float | None:
    try:
        proc = psutil.Process(int(os.getpid()))
        return _safe_positive_float(proc.create_time())
    except Exception:
        return None


def _extract_state_pid(value: Any) -> int | None:
    try:
        if isinstance(value, int):
            return int(value) if int(value) > 0 else None
        raw = str(value or "").strip()
        if raw.isdigit():
            parsed = int(raw)
            return parsed if parsed > 0 else None
    except Exception:
        return None
    return None


def _is_runtime_writer_alive(state: dict[str, Any] | None) -> bool:
    if not isinstance(state, dict):
        return False
    pid = _extract_state_pid(state.get("pid"))
    expected_started_at = _safe_positive_float(state.get("pid_started_at"))
    if pid is None:
        return False
    try:
        proc = psutil.Process(pid)
        status = str(proc.status() or "").strip().lower()
        if not bool(proc.is_running()) or status == "zombie":
            return False
        actual_started_at = _safe_positive_float(proc.create_time())
        if actual_started_at is None:
            return False
        # Preferred check: writer start-time fingerprint (strong against PID reuse).
        if expected_started_at is not None:
            # Tolerate tiny precision drift between persisted and runtime values.
            return abs(actual_started_at - expected_started_at) <= 2.5

        # Backward-compatible fallback for older state writers that did not persist
        # pid_started_at. To avoid false positives from PID reuse, require a fresh
        # heartbeat timestamp.
        updated_at = _safe_positive_float(state.get("updated_at"))
        if updated_at is None:
            return False
        age_seconds = max(0.0, float(time.time()) - updated_at)
        return age_seconds <= 90.0
    except Exception:
        return False


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _normalize_presence_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("status."):
        raw = raw.split(".", 1)[1].strip()
    if raw in {"online", "idle", "dnd", "offline", "invisible", "streaming"}:
        return raw
    return "offline"


def _normalize_activity_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("activitytype."):
        raw = raw.split(".", 1)[1].strip()
    return raw


def _sanitize_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:limit]


def _normalize_runtime_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    bot_src = src.get("bot") if isinstance(src.get("bot"), dict) else {}
    guilds_src = src.get("guilds") if isinstance(src.get("guilds"), list) else []

    bot_payload = {
        "id": str(bot_src.get("id") or "").strip(),
        "name": str(bot_src.get("name") or "").strip(),
        "display_name": str(bot_src.get("display_name") or bot_src.get("name") or "").strip(),
        "avatar_url": str(bot_src.get("avatar_url") or "").strip(),
        "created_at_ts": _to_int(bot_src.get("created_at_ts"), 0),
        "guild_count": _to_int(bot_src.get("guild_count"), 0),
        "member_count": _to_int(bot_src.get("member_count"), 0),
        "shard_total": _to_int(bot_src.get("shard_total"), 0),
        "shard_connected": _to_int(bot_src.get("shard_connected"), 0),
    }

    guild_payloads: list[dict[str, Any]] = []
    for row in guilds_src[:200]:
        if not isinstance(row, dict):
            continue
        guild_id_text = str(row.get("id") or "").strip()
        if not guild_id_text.isdigit():
            continue
        channels_src = row.get("channels") if isinstance(row.get("channels"), list) else []
        roles_src = row.get("roles") if isinstance(row.get("roles"), list) else []
        members_src = row.get("members") if isinstance(row.get("members"), list) else []

        channels: list[dict[str, Any]] = []
        for item in channels_src[:1500]:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id") or "").strip()
            if not cid.isdigit():
                continue
            channels.append(
                {
                    "id": cid,
                    "name": str(item.get("name") or "").strip() or f"channel-{cid}",
                    "type": str(item.get("type") or "").strip().lower() or "text",
                    "position": _to_int(item.get("position"), 0),
                    "category_position": _to_int(item.get("category_position"), 0),
                }
            )

        roles: list[dict[str, Any]] = []
        for item in roles_src[:500]:
            if not isinstance(item, dict):
                continue
            rid = str(item.get("id") or "").strip()
            if not rid.isdigit():
                continue
            roles.append(
                {
                    "id": rid,
                    "name": str(item.get("name") or "").strip() or f"role-{rid}",
                    "position": _to_int(item.get("position"), 0),
                    "color_value": max(0, _to_int(item.get("color_value"), 0)),
                    "is_default": _to_bool(item.get("is_default"), False),
                    "managed": _to_bool(item.get("managed"), False),
                    "permissions_admin": _to_bool(item.get("permissions_admin"), False),
                }
            )

        members: list[dict[str, Any]] = []
        for item in members_src[:3000]:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id") or "").strip()
            if not mid.isdigit():
                continue
            activities_src = item.get("activities") if isinstance(item.get("activities"), list) else []
            activities: list[dict[str, str]] = []
            for activity_item in activities_src[:5]:
                if not isinstance(activity_item, dict):
                    continue
                activity_type = _normalize_activity_type(activity_item.get("type"))
                activity_name = _sanitize_text(activity_item.get("name"), limit=120)
                activity_state = _sanitize_text(activity_item.get("state"), limit=140)
                activity_details = _sanitize_text(activity_item.get("details"), limit=140)
                activity_emoji = _sanitize_text(activity_item.get("emoji"), limit=64)
                if not (
                    activity_type
                    or activity_name
                    or activity_state
                    or activity_details
                    or activity_emoji
                ):
                    continue
                activities.append(
                    {
                        "type": activity_type,
                        "name": activity_name,
                        "state": activity_state,
                        "details": activity_details,
                        "emoji": activity_emoji,
                    }
                )
            members.append(
                {
                    "id": mid,
                    "name": str(item.get("name") or "").strip() or f"user-{mid}",
                    "display_name": str(item.get("display_name") or item.get("name") or "").strip(),
                    "bot": _to_bool(item.get("bot"), False),
                    "status": _normalize_presence_status(item.get("status")),
                    "avatar_url": _sanitize_text(item.get("avatar_url"), limit=700),
                    "activities": activities,
                }
            )

        guild_payloads.append(
            {
                "id": guild_id_text,
                "name": str(row.get("name") or f"Guild {guild_id_text}").strip() or f"Guild {guild_id_text}",
                "icon_url": str(row.get("icon_url") or "").strip(),
                "member_count": max(0, _to_int(row.get("member_count"), 0)),
                "owner_id": max(0, _to_int(row.get("owner_id"), 0)),
                "channels": channels,
                "roles": roles,
                "members": members,
                "me": {
                    "id": str((row.get("me") or {}).get("id") or bot_payload.get("id") or "").strip(),
                    "top_role_position": _to_int((row.get("me") or {}).get("top_role_position"), 0),
                    "guild_permissions_manage_roles": _to_bool((row.get("me") or {}).get("guild_permissions_manage_roles"), False),
                },
            }
        )

    return {
        "bot": bot_payload,
        "guilds": guild_payloads,
        "updated_at": float(src.get("updated_at") or time.time()),
    }


def _discord_default_avatar_url(user_id: str | int | None) -> str:
    try:
        uid = int(str(user_id or "0").strip() or 0)
    except Exception:
        uid = 0
    index = (uid >> 22) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{index}.png"


class _ProxyAsset:
    def __init__(self, url: str):
        self.url = str(url or "").strip()

    def __str__(self) -> str:
        return self.url


class _ProxyColor:
    def __init__(self, value: int):
        self.value = max(0, int(value or 0))

    def __str__(self) -> str:
        return f"#{self.value:06X}"


class _ProxyRolePermissions:
    def __init__(self, *, administrator: bool = False):
        self.administrator = bool(administrator)


class _ProxyGuildPermissions:
    def __init__(self, *, manage_roles: bool = False):
        self.manage_roles = bool(manage_roles)
        # discord.Permissions.manage_roles bit (1 << 28)
        self.value = 268435456 if self.manage_roles else 0


class _ProxyRole:
    def __init__(self, payload: dict[str, Any]):
        self.id = _to_int(payload.get("id"), 0)
        self.name = str(payload.get("name") or f"role-{self.id}")
        self.position = _to_int(payload.get("position"), 0)
        self.color = _ProxyColor(_to_int(payload.get("color_value"), 0))
        self.managed = _to_bool(payload.get("managed"), False)
        self.permissions = _ProxyRolePermissions(
            administrator=_to_bool(payload.get("permissions_admin"), False)
        )
        self._is_default = _to_bool(payload.get("is_default"), False)

    def is_default(self) -> bool:
        return self._is_default

    def __le__(self, other: Any) -> bool:
        try:
            return int(self.position) <= int(getattr(other, "position", -1))
        except Exception:
            return False

    def __lt__(self, other: Any) -> bool:
        try:
            return int(self.position) < int(getattr(other, "position", -1))
        except Exception:
            return False

    async def edit(self, *args, **kwargs):
        raise RuntimeError("Remote bot snapshot is read-only")

    async def delete(self, *args, **kwargs):
        raise RuntimeError("Remote bot snapshot is read-only")


class _ProxyCategory:
    def __init__(self, position: int):
        self.position = _to_int(position, 0)


class _ProxyChannelPermissions:
    def __init__(
        self,
        *,
        view_channel: bool = True,
        send_messages: bool = True,
        read_message_history: bool = True,
        attach_files: bool = True,
        embed_links: bool = True,
        use_external_emojis: bool = True,
        create_instant_invite: bool = True,
        manage_channels: bool = False,
        manage_messages: bool = False,
    ):
        self.view_channel = bool(view_channel)
        self.send_messages = bool(send_messages)
        self.read_message_history = bool(read_message_history)
        self.attach_files = bool(attach_files)
        self.embed_links = bool(embed_links)
        self.use_external_emojis = bool(use_external_emojis)
        self.create_instant_invite = bool(create_instant_invite)
        self.manage_channels = bool(manage_channels)
        self.manage_messages = bool(manage_messages)


class _ProxyChannel:
    def __init__(self, payload: dict[str, Any]):
        self.id = _to_int(payload.get("id"), 0)
        self.name = str(payload.get("name") or f"channel-{self.id}")
        self.type = str(payload.get("type") or "text").strip().lower() or "text"
        self.position = _to_int(payload.get("position"), 0)
        category_position = _to_int(payload.get("category_position"), 0)
        self.category = _ProxyCategory(category_position) if category_position > 0 else None
        self.mention = f"<#{self.id}>" if self.id > 0 else "#unknown"

    def permissions_for(self, _member: Any) -> _ProxyChannelPermissions:
        # Snapshot mode cannot resolve channel overwrites accurately.
        # Return permissive defaults for read-only dashboard rendering flows.
        return _ProxyChannelPermissions()

    async def send(self, *args, **kwargs):
        raise RuntimeError("Remote bot snapshot is read-only")

    async def edit(self, *args, **kwargs):
        raise RuntimeError("Remote bot snapshot is read-only")

    async def delete(self, *args, **kwargs):
        raise RuntimeError("Remote bot snapshot is read-only")


class _ProxyActivity:
    def __init__(self, payload: dict[str, Any]):
        self.type = _normalize_activity_type(payload.get("type"))
        self.name = _sanitize_text(payload.get("name"), limit=120)
        self.state = _sanitize_text(payload.get("state"), limit=140)
        self.details = _sanitize_text(payload.get("details"), limit=140)
        emoji_text = _sanitize_text(payload.get("emoji"), limit=64)
        self.emoji = emoji_text or None


class _ProxyMember:
    def __init__(self, payload: dict[str, Any], *, top_role: _ProxyRole | None = None, manage_roles: bool = False):
        self.id = _to_int(payload.get("id"), 0)
        self.name = str(payload.get("name") or f"user-{self.id}")
        self.display_name = str(payload.get("display_name") or self.name)
        self.bot = _to_bool(payload.get("bot"), False)
        self.status = _normalize_presence_status(payload.get("status"))
        self.activities = [
            _ProxyActivity(item)
            for item in list(payload.get("activities") or [])
            if isinstance(item, dict)
        ]
        self.mention = f"<@{self.id}>" if self.id > 0 else "@unknown"
        fallback_avatar = _discord_default_avatar_url(str(self.id or 0))
        avatar_url = _sanitize_text(payload.get("avatar_url"), limit=700) or fallback_avatar
        self.display_avatar = _ProxyAsset(avatar_url)
        self.avatar = _ProxyAsset(avatar_url)
        self.guild_permissions = _ProxyGuildPermissions(manage_roles=manage_roles)
        self.top_role = top_role or _ProxyRole(
            {
                "id": 0,
                "name": "@everyone",
                "position": 0,
                "color_value": 0,
                "is_default": True,
                "managed": False,
                "permissions_admin": False,
            }
        )

    async def edit(self, *args, **kwargs):
        raise RuntimeError("Remote bot snapshot is read-only")


class _ProxyGuild:
    def __init__(self, payload: dict[str, Any]):
        self.id = _to_int(payload.get("id"), 0)
        self.name = str(payload.get("name") or f"Guild {self.id}")
        self.member_count = max(0, _to_int(payload.get("member_count"), 0))
        self.owner_id = max(0, _to_int(payload.get("owner_id"), 0))
        icon_url = str(payload.get("icon_url") or "").strip()
        self.icon = _ProxyAsset(icon_url) if icon_url else None
        self.voice_client = None

        self.channels = [_ProxyChannel(item) for item in list(payload.get("channels") or []) if isinstance(item, dict)]
        self.text_channels = [item for item in self.channels if str(getattr(item, "type", "")) in {"text", "news", "forum"}]
        self.voice_channels = [item for item in self.channels if str(getattr(item, "type", "")) in {"voice", "stage_voice"}]
        self.roles = [_ProxyRole(item) for item in list(payload.get("roles") or []) if isinstance(item, dict)]
        self.default_role = next((role for role in self.roles if bool(role.is_default())), None)
        if self.default_role is None:
            self.default_role = _ProxyRole(
                {
                    "id": 0,
                    "name": "@everyone",
                    "position": 0,
                    "color_value": 0,
                    "is_default": True,
                    "managed": False,
                    "permissions_admin": False,
                }
            )
        self.members = [_ProxyMember(item) for item in list(payload.get("members") or []) if isinstance(item, dict)]

        me_payload = payload.get("me") if isinstance(payload.get("me"), dict) else {}
        me_top_role_position = _to_int(me_payload.get("top_role_position"), 0)
        me_manage_roles = _to_bool(me_payload.get("guild_permissions_manage_roles"), False)
        me_top_role = _ProxyRole(
            {
                "id": 0,
                "name": "bot-top-role",
                "position": me_top_role_position,
                "color_value": 0,
                "is_default": False,
                "managed": False,
                "permissions_admin": False,
            }
        )
        self.me = _ProxyMember(
            {"id": me_payload.get("id"), "name": "SkylineBOT", "display_name": "SkylineBOT", "bot": True},
            top_role=me_top_role,
            manage_roles=me_manage_roles,
        )

    def get_channel(self, channel_id: int | str) -> _ProxyChannel | None:
        target = _to_int(channel_id, 0)
        if target <= 0:
            return None
        for channel in self.channels:
            if int(getattr(channel, "id", 0)) == target:
                return channel
        return None

    def get_role(self, role_id: int | str) -> _ProxyRole | None:
        target = _to_int(role_id, 0)
        if target <= 0:
            return None
        for role in self.roles:
            if int(getattr(role, "id", 0)) == target:
                return role
        return None

    def get_member(self, user_id: int | str) -> _ProxyMember | None:
        target = _to_int(user_id, 0)
        if target <= 0:
            return None
        for member in self.members:
            if int(getattr(member, "id", 0)) == target:
                return member
        return None

    async def fetch_member(self, user_id: int | str) -> _ProxyMember | None:
        return self.get_member(user_id)

    async def create_role(self, *args, **kwargs):
        raise RuntimeError("Remote bot snapshot is read-only")


class _ProxyBotUser:
    def __init__(self, payload: dict[str, Any]):
        self.id = _to_int(payload.get("id"), 0)
        self.name = str(payload.get("name") or "SkylineBOT")
        self.display_name = str(payload.get("display_name") or self.name)
        avatar_url = str(payload.get("avatar_url") or "").strip()
        self.display_avatar = _ProxyAsset(avatar_url) if avatar_url else None
        self.avatar = _ProxyAsset(avatar_url) if avatar_url else None
        created_at_ts = _to_int(payload.get("created_at_ts"), 0)
        if created_at_ts > 0:
            self.created_at = datetime.datetime.fromtimestamp(created_at_ts, tz=datetime.timezone.utc)
        else:
            self.created_at = datetime.datetime.now(tz=datetime.timezone.utc)


class _RuntimeBotProxy:
    def __init__(self, snapshot: dict[str, Any]):
        payload = _normalize_runtime_snapshot(snapshot)
        self._snapshot = payload
        bot_payload = payload.get("bot") if isinstance(payload.get("bot"), dict) else {}
        self.user = _ProxyBotUser(bot_payload)
        self.guilds = [_ProxyGuild(item) for item in list(payload.get("guilds") or []) if isinstance(item, dict)]
        self.start_time = None
        self.latency = 0.0
        self.shards = {}

    def get_guild(self, guild_id: int | str) -> _ProxyGuild | None:
        target = _to_int(guild_id, 0)
        if target <= 0:
            return None
        for guild in self.guilds:
            if int(getattr(guild, "id", 0)) == target:
                return guild
        return None

    def get_channel(self, channel_id: int | str) -> _ProxyChannel | None:
        target = _to_int(channel_id, 0)
        if target <= 0:
            return None
        for guild in self.guilds:
            channel = guild.get_channel(target)
            if channel is not None:
                return channel
        return None

    def get_cog(self, name: str) -> None:
        return None

    def get_user(self, user_id: int | str) -> _ProxyMember | None:
        target = _to_int(user_id, 0)
        if target <= 0:
            return None
        for guild in self.guilds:
            member = guild.get_member(target)
            if member is not None:
                return member
        return None

    async def fetch_user(self, user_id: int | str) -> _ProxyMember | None:
        return self.get_user(user_id)

    async def fetch_channel(self, channel_id: int | str) -> _ProxyChannel | None:
        return self.get_channel(channel_id)

    def is_ready(self) -> bool:
        return True

    def is_closed(self) -> bool:
        return False


def bind_bot(bot) -> None:
    global _bot
    _bot = bot


def get_bot():
    if _bot is not None:
        if getattr(_bot, "user", None) is not None:
            return _bot
        _run_web, run_bot = _resolve_runtime_components()
        if run_bot:
            # Keep local object during startup in bot runtime process.
            return _bot
    persisted_state = _read_persisted_discord_state()
    if not isinstance(persisted_state, dict):
        return None
    _run_web, run_bot = _resolve_runtime_components()
    if not run_bot and not _is_runtime_writer_alive(persisted_state):
        return None
    snapshot = persisted_state.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    snapshot_bot = snapshot.get("bot") if isinstance(snapshot.get("bot"), dict) else {}
    guilds = snapshot.get("guilds") if isinstance(snapshot.get("guilds"), list) else []
    has_bot_identity = bool(str(snapshot_bot.get("id") or "").strip())
    if not guilds and not has_bot_identity:
        return None
    try:
        return _RuntimeBotProxy(snapshot)
    except Exception:
        return None


def set_discord_service_state(
    *,
    level: str,
    message: str,
    status_code: int | None = None,
    retry_after: float | None = None,
    attempt: int | None = None,
    snapshot: dict[str, Any] | None = None,
    persist: bool = True,
) -> None:
    _discord_service_state["level"] = str(level or "unknown").strip().lower() or "unknown"
    _discord_service_state["message"] = str(message or "").strip()
    _discord_service_state["status_code"] = status_code if isinstance(status_code, int) else None
    _discord_service_state["retry_after"] = (
        float(retry_after) if isinstance(retry_after, (int, float)) else None
    )
    _discord_service_state["attempt"] = int(attempt) if isinstance(attempt, int) and attempt >= 0 else 0
    _discord_service_state["updated_at"] = float(time.time())
    _discord_service_state["pid"] = int(os.getpid())
    _discord_service_state["pid_started_at"] = _current_process_started_at()
    _discord_service_state["source"] = "memory"
    if isinstance(snapshot, dict):
        _discord_service_state["snapshot"] = _normalize_runtime_snapshot(snapshot)
    elif "snapshot" not in _discord_service_state:
        _discord_service_state["snapshot"] = {"bot": {}, "guilds": [], "updated_at": 0.0}
    if persist:
        _persist_discord_state_if_needed(_discord_service_state)


def _live_discord_state_from_bound_bot() -> dict[str, Any] | None:
    bot = _bot
    if bot is None:
        return None

    try:
        bot_closed = bool(getattr(bot, "is_closed", lambda: False)())
    except Exception:
        bot_closed = True
    bot_user = getattr(bot, "user", None)
    try:
        bot_ready = bool(getattr(bot, "is_ready", lambda: False)())
    except Exception:
        bot_ready = False

    if bot_closed:
        level = "stopped"
        message = "Discord runtime is not active (bot is closed)"
    elif bot_user is None:
        level = "starting"
        message = "Discord runtime is starting"
    elif bot_ready:
        level = "ok"
        message = "Discord runtime is online"
    else:
        level = "starting"
        message = "Discord runtime is connecting"

    snapshot_payload = _discord_service_state.get("snapshot")
    if not isinstance(snapshot_payload, dict):
        snapshot_payload = {"bot": {}, "guilds": [], "updated_at": 0.0}

    return {
        "level": level,
        "message": message,
        "status_code": None,
        "retry_after": None,
        "attempt": 0,
        "updated_at": float(time.time()),
        "pid": int(os.getpid()),
        "pid_started_at": _current_process_started_at(),
        "source": "memory",
        "snapshot": snapshot_payload,
    }


def get_discord_service_state(*, include_snapshot: bool = True) -> dict[str, Any]:
    local_state = dict(_discord_service_state)
    persisted_state = _read_persisted_discord_state()
    _run_web, run_bot = _resolve_runtime_components()
    state = local_state
    if run_bot:
        if (
            isinstance(persisted_state, dict)
            and float(persisted_state.get("updated_at") or 0.0)
            > float(local_state.get("updated_at") or 0.0)
        ):
            state = dict(persisted_state)
    else:
        if isinstance(persisted_state, dict):
            state = dict(persisted_state)

    if run_bot:
        live_state = _live_discord_state_from_bound_bot()
        if isinstance(live_state, dict):
            state_level = str(state.get("level") or "").strip().lower()
            live_level = str(live_state.get("level") or "").strip().lower()
            state_pid = _extract_state_pid(state.get("pid"))
            live_pid = _extract_state_pid(live_state.get("pid"))
            state_updated_at = _safe_positive_float(state.get("updated_at"))
            state_age_seconds = (
                max(0.0, float(time.time()) - state_updated_at)
                if isinstance(state_updated_at, float)
                else 9999.0
            )
            replace_with_live = bool(
                state_pid != live_pid
                or not _is_runtime_writer_alive(state)
                or state_level in {"unknown", "outage", "auth_error"}
                or (live_level == "ok" and state_level != "ok" and state_age_seconds >= 3.0)
            )
            if replace_with_live:
                _discord_service_state.update(live_state)
                state = dict(_discord_service_state)
                _persist_discord_state_if_needed(state)
    if not state.get("pid"):
        state["pid"] = None
    pid_started_at = _safe_positive_float(state.get("pid_started_at"))
    state["pid_started_at"] = pid_started_at
    if not run_bot and not _is_runtime_writer_alive(state):
        state["level"] = "stopped"
        state["message"] = "Discord runtime is not active (web-only mode)"
        state["status_code"] = None
        state["retry_after"] = None
        state["attempt"] = 0
        state["updated_at"] = float(time.time())
        state["pid"] = None
        state["pid_started_at"] = None
        state["source"] = "memory"
    if include_snapshot:
        state_snapshot = _normalize_runtime_snapshot(state.get("snapshot") if isinstance(state, dict) else None)
        state["snapshot"] = state_snapshot
    else:
        state.pop("snapshot", None)
    state["source"] = str(state.get("source") or "memory")
    state["is_outage"] = bool(state.get("level") == "outage")
    return state


def create_session(payload: dict[str, Any]) -> str:
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = payload
    return session_id


def get_session(session_id: str | None) -> dict[str, Any] | None:
    if not session_id:
        return None
    return _sessions.get(session_id)


def destroy_session(session_id: str | None) -> None:
    if session_id:
        _sessions.pop(session_id, None)


def create_oauth_state(payload: dict[str, Any] | None = None) -> str:
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {
        "created_at": time.time(),
        "payload": dict(payload or {}),
    }
    return state


def consume_oauth_state(state: str | None) -> dict[str, Any] | None:
    if not state:
        return None
    raw_entry = _oauth_states.pop(state, None)
    if raw_entry is None:
        return None

    if isinstance(raw_entry, dict):
        created_at = float(raw_entry.get("created_at") or 0)
        payload = raw_entry.get("payload") or {}
        payload = payload if isinstance(payload, dict) else {}
    else:
        # Backward-compatible fallback for old state entries.
        created_at = float(raw_entry)
        payload = {}

    if (time.time() - created_at) >= 600:
        return None
    return payload
