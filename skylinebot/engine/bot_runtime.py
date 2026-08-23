import discord
from discord.ext import commands
import inspect
import datetime
import json
import os
import re

from skylinebot.config import config
BotConfig = config.BotConfigClass()

from skylinebot.memory.cache import cache

from skylinebot.style import color
from skylinebot.console.logging import logger
from skylinebot.utils import i18n

from storage import guilds_log as guilds_log_db
import storage
from skylinebot.style import emoji,urls
import importlib
import asyncio
import wavelink
from collections import defaultdict
import time
import traceback

def get_function_args(func):
    signature = inspect.signature(func)
    return [param.name for param in signature.parameters.values()]


OWNERBOT_RUNTIME_CONFIG_KEY = "ownerbot_runtime_settings"
SCREENING_CATEGORY_CONFIG_KEY_PREFIX = "screening_categories_v1_guild_"
_LOG_CATEGORY_CACHE_TTL_SECONDS = 20
_LOG_CATEGORY_CONFIG_CACHE = {}
_EMPTY_SLASH_DESCRIPTION_VALUES = {"", ".", "..", "...", "-", "_", "n/a", "none"}
_COMMAND_ACCESS_REFRESH_TTL_SECONDS = 5.0
_COMMAND_ACCESS_REFRESH_RETRY_SECONDS = 15.0
GUILD_COMMAND_DISABLED_MESSAGE = (
    "คำสั่งนี้ถูกปิดการใช้งานบนเซิฟนี้ หากคิดว่าระบบเกิดความผิดพลาดกรุณาติดต่อผู้พัฒนา"
)
OWNERBOT_GLOBAL_COMMAND_DISABLED_MESSAGE = (
    "คำสั่งนี้ถูกปิดการใช้งานจากผู้พัฒนาบอท โปรดติดตามประกาศจากทางผู้พัฒนา"
)
DEFAULT_ESSENTIAL_SLASH_CHAT_COMMANDS = frozenset(
    {
        "help",
        "ping",
        "aihealth",
        "invite",
        "support",
        "supportserver",
        "supportbot",
        "supportbotsetup",
        "mod",
        "ownerbot",
        "userinfo",
        "serverinfo",
        "avatar",
        "banner",
        "botinfo",
        "profile",
        "stats",
        "membercount",
        "prefix",
        "afk",
        "report",
        "birthday",
        "relationship",
        "vote",
        "noprefix",
        "automod",
        "antinuke",
        "whitelist",
        "aichat",
        "antispam",
        "antibadwords",
        "antilink",
        "autoresponder",
        "alerts",
        "nsfw",
        "delete",
        "ban",
        "kick",
        "unban",
        "lock",
        "unlock",
        "hide",
        "unhide",
        "role",
        "mediachannel",
        "promote",
        "ticket",
        "welcome",
        "greet",
        "leaver",
        "autorole",
        "autonick",
        "color",
        "colors",
        "giveaway",
        "level",
        "economy",
        "shop",
        "music",
        "vcmove",
        "vcmoveall",
        "funroom",
        "fancy",
        "slots",
        "coinflip",
        "dice",
        "rps",
        "xo",
        "chess",
        "redeem",
        "premium",
        "plan",
        "setup",
        "photoroom",
        "photourl",
        "vccontrol",
        "ocr",
        "verify",
        "reaction_roles",
        "serverstats",
        "donate",
    }
)
DEFAULT_ESSENTIAL_SLASH_CONTEXT_COMMANDS = frozenset(
    {
        "user info",
        "user avatar",
        "user rank",
        "user level",
        "user actions",
        "message info",
        "quote message",
    }
)
SLASH_PROFILE_CHAT_COMMANDS = {
    "admin": frozenset(
        {
            "help",
            "ping",
            "aihealth",
            "support",
            "supportserver",
            "supportbot",
            "supportbotsetup",
            "mod",
            "prefix",
            "delete",
            "automod",
            "antinuke",
            "whitelist",
            "aichat",
            "antispam",
            "antibadwords",
            "antilink",
            "autoresponder",
            "alerts",
            "nsfw",
            "ban",
            "kick",
            "unban",
            "lock",
            "unlock",
            "hide",
            "unhide",
            "role",
            "mediachannel",
            "promote",
            "ticket",
            "welcome",
            "greet",
            "leaver",
            "autorole",
            "autonick",
            "color",
            "colors",
            "report",
            "birthday",
            "reaction_roles",
            "serverstats",
            "plan",
            "setup",
            "photoroom",
            "photourl",
        }
    ),
    "music": frozenset(
        {
            "help",
            "ping",
            "aihealth",
            "support",
            "supportserver",
            "supportbot",
            "prefix",
            "music",
            "vcmove",
            "vcmoveall",
        }
    ),
    "economy": frozenset(
        {
            "help",
            "ping",
            "aihealth",
            "support",
            "supportserver",
            "supportbot",
            "prefix",
            "economy",
            "redeem",
        }
    ),
}
SLASH_PROFILE_CONTEXT_COMMANDS = {
    "admin": frozenset(DEFAULT_ESSENTIAL_SLASH_CONTEXT_COMMANDS),
    "music": frozenset({"user info", "user avatar", "message info"}),
    "economy": frozenset({"user info", "user avatar", "user level", "user rank"}),
}


def _parse_ownerbot_id_list(raw_value):
    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(v or "").strip() for v in raw_value]
    else:
        candidates = str(raw_value or "").replace("\n", ",").split(",")
    out = []
    for item in candidates:
        guild_id = str(item or "").strip()
        if not guild_id or not guild_id.isdigit() or guild_id in out:
            continue
        out.append(guild_id)
    return out


def _parse_ownerbot_command_list(raw_value):
    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(v or "").strip().lower() for v in raw_value]
    else:
        candidates = str(raw_value or "").replace("\n", ",").split(",")
    out = []
    for item in candidates:
        name = str(item or "").strip().lower()
        if name.startswith("/"):
            name = name[1:].strip()
        if not name or name in out:
            continue
        out.append(name)
    return out


def _normalize_slash_name(raw_value):
    name = str(raw_value or "").strip().lower()
    if name.startswith("/"):
        name = name[1:].strip()
    return name


def _parse_slash_name_set(raw_value):
    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(v or "") for v in raw_value]
    else:
        candidates = str(raw_value or "").replace("\n", ",").split(",")
    out = set()
    for item in candidates:
        normalized = _normalize_slash_name(item)
        if not normalized:
            continue
        out.add(normalized)
    return out


def _parse_slash_profile_list(raw_value):
    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(v or "") for v in raw_value]
    else:
        candidates = str(raw_value or "").replace("\n", ",").split(",")
    out = []
    for item in candidates:
        profile = _normalize_slash_name(item)
        if not profile or profile in out:
            continue
        out.append(profile)
    return out


def _collect_slash_profile_allowlists(profile_names):
    chat = set()
    context = set()
    unknown = []
    for profile in list(profile_names or []):
        name = str(profile or "").strip().lower()
        if not name:
            continue
        chat_rows = SLASH_PROFILE_CHAT_COMMANDS.get(name)
        context_rows = SLASH_PROFILE_CONTEXT_COMMANDS.get(name)
        if chat_rows is None and context_rows is None:
            unknown.append(name)
            continue
        chat.update(chat_rows or set())
        context.update(context_rows or set())
    return chat, context, unknown


OWNERBOT_AI_PROVIDERS = {"ollama", "openai", "google", "opentyphoon", "chindax", "aiforthai", "cloudflare", "thaillm"}


def _normalize_ownerbot_ai_provider(raw_value):
    provider = str(raw_value or "").strip().lower()
    if provider in OWNERBOT_AI_PROVIDERS:
        return provider
    return "opentyphoon"


def _default_ownerbot_ai_provider():
    return _normalize_ownerbot_ai_provider(os.getenv("AI_PROVIDER", "opentyphoon"))


def _default_ownerbot_ai_model(provider: str | None = None):
    provider = _normalize_ownerbot_ai_provider(provider or _default_ownerbot_ai_provider())
    if provider == "openai":
        model = str(os.getenv("OPENAI_MODEL", "gpt-4o-mini")).strip()
        return model or "gpt-4o-mini"
    if provider == "google":
        model = str(os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")).strip()
        return model or "gemini-2.0-flash"
    if provider == "opentyphoon":
        model = str(os.getenv("OPENTYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct")).strip()
        return model or "typhoon-v2.5-30b-a3b-instruct"
    if provider == "chindax":
        model = str(os.getenv("CHINDAX_MODEL", "accounts/fireworks/models/gpt-oss-20b")).strip()
        return model or "accounts/fireworks/models/gpt-oss-20b"
    if provider == "aiforthai":
        model = str(os.getenv("AIFORTHAI_MODEL", "aiforthai-chat")).strip()
        return model or "aiforthai-chat"
    if provider == "cloudflare":
        model = str(os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.1-8b-instruct")).strip()
        return model or "@cf/meta/llama-3.1-8b-instruct"
    if provider == "thaillm":
        model = str(os.getenv("THAILLM_MODEL", "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2")).strip()
        return model or "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2"
    model = str(os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b-instruct")).strip()
    return model or "qwen2.5:0.5b-instruct"


def _normalize_ownerbot_ai_model(raw_value, *, provider: str | None = None):
    fallback = _default_ownerbot_ai_model(provider=provider)
    model = str(raw_value or "").strip()
    if not model:
        return fallback
    if len(model) > 120:
        model = model[:120]
    if not re.match(r"^[A-Za-z0-9._:/-]+$", model):
        return fallback
    return model


def _default_ownerbot_runtime_settings():
    provider = _default_ownerbot_ai_provider()
    return {
        "global_command_response_enabled": True,
        "global_bot_response_enabled": True,
        "global_ai_provider": provider,
        "global_ai_model": _default_ownerbot_ai_model(provider=provider),
        "guild_mode": "all",
        "whitelist_guild_ids": [],
        "blacklist_guild_ids": [],
        "tester_enabled": False,
        "tester_guild_ids": [],
        "global_disabled_commands": [],
        "dashboard_status_override_level": "auto",
        "dashboard_status_override_activity": "auto",
        "dashboard_status_override_display": "auto",
        "dashboard_status_override_message": "",
        "dashboard_status_override_messages": [],
        "rich_presence_mode": "off",
    }


def _parse_ownerbot_override_messages(raw_value, *, limit: int = 12):
    items = raw_value if isinstance(raw_value, list) else str(raw_value or "").splitlines()
    out = []
    for item in items:
        text = " ".join(str(item or "").strip().split())
        if not text:
            continue
        text = text[:120]
        out.append(text)
        if len(out) >= int(limit):
            break
    return out


def _normalize_ownerbot_runtime_settings(payload):
    src = payload if isinstance(payload, dict) else {}
    mode = str(src.get("guild_mode") or "all").strip().lower()
    if mode not in {"all", "whitelist", "blacklist", "tester"}:
        mode = "all"
    data = _default_ownerbot_runtime_settings()
    data["global_command_response_enabled"] = bool(src.get("global_command_response_enabled", True))
    data["global_bot_response_enabled"] = bool(src.get("global_bot_response_enabled", True))
    data["global_ai_provider"] = _normalize_ownerbot_ai_provider(
        src.get("global_ai_provider") or data.get("global_ai_provider")
    )
    data["global_ai_model"] = _normalize_ownerbot_ai_model(
        src.get("global_ai_model"),
        provider=str(data.get("global_ai_provider") or "opentyphoon"),
    )
    data["guild_mode"] = mode
    data["whitelist_guild_ids"] = _parse_ownerbot_id_list(src.get("whitelist_guild_ids"))
    data["blacklist_guild_ids"] = _parse_ownerbot_id_list(src.get("blacklist_guild_ids"))
    data["tester_enabled"] = bool(src.get("tester_enabled", False))
    data["tester_guild_ids"] = _parse_ownerbot_id_list(src.get("tester_guild_ids"))
    data["global_disabled_commands"] = _parse_ownerbot_command_list(src.get("global_disabled_commands"))
    allowed_levels = {"auto", "online", "idle", "dnd", "offline"}
    allowed_activities = {"auto", "playing", "streaming", "listening", "watching", "competing"}
    non_auto_activities = allowed_activities - {"auto"}
    allowed_display_values = {"auto", "online", "idle", "dnd", "offline", "playing", "streaming", "listening", "watching", "competing"}
    legacy_level_map = {"live": "online", "stream": "idle", "ded": "dnd"}
    legacy_activity_map = {"custom": "watching"}

    override_level = str(src.get("dashboard_status_override_level") or "auto").strip().lower()
    override_level = legacy_level_map.get(override_level, override_level)
    if override_level not in allowed_levels:
        override_level = "auto"
    override_activity = str(src.get("dashboard_status_override_activity") or "auto").strip().lower()
    override_activity = legacy_activity_map.get(override_activity, override_activity)
    if override_activity not in allowed_activities:
        override_activity = "auto"
    if override_level == "auto" and override_activity in non_auto_activities:
        override_level = "online"
    override_display = str(src.get("dashboard_status_override_display") or "").strip().lower()
    if override_display not in allowed_display_values:
        if override_level == "auto" and override_activity == "auto":
            override_display = "auto"
        elif override_level in {"online", "idle", "dnd", "offline"}:
            if override_level == "online" and override_activity in non_auto_activities:
                override_display = override_activity
            else:
                override_display = override_level
        elif override_activity in non_auto_activities:
            override_display = override_activity
        else:
            override_display = "auto"
    override_message_text = str(src.get("dashboard_status_override_message") or "").strip()[:2000]
    override_messages = _parse_ownerbot_override_messages(src.get("dashboard_status_override_messages"))
    if not override_messages and override_message_text:
        override_messages = _parse_ownerbot_override_messages(override_message_text)
    data["dashboard_status_override_level"] = override_level
    data["dashboard_status_override_activity"] = override_activity
    data["dashboard_status_override_display"] = override_display
    data["dashboard_status_override_messages"] = override_messages
    data["dashboard_status_override_message"] = (
        override_message_text or "\n".join(override_messages)
    )[:2000]
    rich_presence_mode = str(src.get("rich_presence_mode") or "off").strip().lower()
    if rich_presence_mode not in {"off", "voice", "always"}:
        rich_presence_mode = "off"
    data["rich_presence_mode"] = rich_presence_mode
    return data


def _ownerbot_guild_block_reason(guild_id: int, settings: dict) -> str | None:
    gid = str(guild_id)
    mode = str(settings.get("guild_mode") or "all").strip().lower()
    whitelist = set(settings.get("whitelist_guild_ids") or [])
    blacklist = set(settings.get("blacklist_guild_ids") or [])
    tester_ids = set(settings.get("tester_guild_ids") or [])
    tester_enabled = bool(settings.get("tester_enabled"))

    if tester_enabled or mode == "tester":
        if gid not in tester_ids:
            return "tester_only"
        return None
    if mode == "whitelist":
        if gid not in whitelist:
            return "whitelist_only"
        return None
    if mode == "blacklist":
        if gid in blacklist:
            return "blacklist_blocked"
        return None
    return None


def _ownerbot_block_message(reason: str | None) -> str:
    messages = {
        "whitelist_only": "ระบบนี้รองรับเฉพาะ Whitelist Guild",
        "tester_only": "ระบบนี้รองรับเฉพาะ Server Tester Mode",
        "blacklist_blocked": "Server นี้ติด Blacklist Guild",
    }
    return messages.get(str(reason or ""), "เซิร์ฟเวอร์นี้ไม่ได้รับอนุญาตให้ใช้คำสั่ง")


def _ownerbot_is_developer_user(user_id: int | None) -> bool:
    try:
        return int(user_id or 0) in {int(dev_id) for dev_id in (cache.developer or [])}
    except Exception:
        return False


def _clean_error_text(error: Exception) -> str:
    text = str(error or "").strip()
    if not text:
        return ""
    return text[:400]


def _is_ignored_interaction_http_error(error: Exception) -> bool:
    ignored_codes = {10062, 10015, 10008}  # Unknown interaction / Unknown webhook / Unknown message
    visited_ids: set[int] = set()
    current = error
    while current is not None and id(current) not in visited_ids:
        visited_ids.add(id(current))
        if isinstance(current, (discord.NotFound, discord.HTTPException)):
            if getattr(current, "code", None) in ignored_codes:
                return True
        current = (
            getattr(current, "original", None)
            or getattr(current, "__cause__", None)
            or getattr(current, "__context__", None)
        )
    return False


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return True
    if value in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _env_float(name: str, default: float, *, min_value: float, max_value: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        parsed = float(str(raw).strip())
    except Exception:
        parsed = float(default)
    return max(float(min_value), min(float(parsed), float(max_value)))


def _ownerbot_app_check_timeout_seconds() -> float:
    return _env_float(
        "OWNERBOT_APP_CHECK_TIMEOUT_SECONDS",
        1.2,
        min_value=0.2,
        max_value=5.0,
    )


def _ownerbot_prefix_check_timeout_seconds() -> float:
    return _env_float(
        "OWNERBOT_PREFIX_CHECK_TIMEOUT_SECONDS",
        2.0,
        min_value=0.2,
        max_value=8.0,
    )


def _ownerbot_command_access_fetch_timeout_seconds() -> float:
    return _env_float(
        "OWNERBOT_COMMAND_ACCESS_FETCH_TIMEOUT_SECONDS",
        0.8,
        min_value=0.2,
        max_value=5.0,
    )


def _screening_categories_config_key(guild_id: int) -> str:
    return f"{SCREENING_CATEGORY_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _normalize_log_category_payload(payload):
    if not isinstance(payload, dict):
        return {}
    out = {}
    for key, row in payload.items():
        if not isinstance(row, dict):
            continue
        log_type = str(row.get("log_type") or "").strip().lower()
        if not log_type:
            continue
        enabled = bool(row.get("enabled"))
        channel_id = str(row.get("channel_id") or "").strip()
        if not channel_id.isdigit():
            channel_id = ""
        color_value = str(row.get("color") or "").strip()
        if color_value and not (len(color_value) == 7 and color_value.startswith("#")):
            color_value = ""
        out[str(key)] = {
            "log_type": log_type,
            "enabled": enabled,
            "channel_id": channel_id,
            "color": color_value,
        }
    return out


async def _get_log_category_config(guild_id: int) -> dict:
    now = time.time()
    cached = _LOG_CATEGORY_CONFIG_CACHE.get(int(guild_id))
    if cached and (now - float(cached.get("ts", 0))) <= _LOG_CATEGORY_CACHE_TTL_SECONDS:
        return cached.get("value") or {}
    payload = {}
    try:
        row = await storage.dashboard_config.get(config_key=_screening_categories_config_key(guild_id))
        raw_value = str((row or {}).get("config_value") or "").strip()
        if raw_value:
            decoded = json.loads(raw_value)
            if isinstance(decoded, dict):
                payload = _normalize_log_category_payload(decoded)
    except Exception:
        payload = {}
    _LOG_CATEGORY_CONFIG_CACHE[int(guild_id)] = {"ts": now, "value": payload}
    return payload


def _log_override_for_type(payload: dict, log_type: str):
    if not isinstance(payload, dict):
        return None
    rows = [row for row in payload.values() if isinstance(row, dict) and str(row.get("log_type") or "").strip().lower() == str(log_type).strip().lower()]
    if not rows:
        return None
    enabled_rows = [row for row in rows if bool(row.get("enabled"))]
    if not enabled_rows:
        return {"enabled": False, "channel_id": "", "color": ""}
    selected = enabled_rows[0]
    return {
        "enabled": True,
        "channel_id": str(selected.get("channel_id") or "").strip(),
        "color": str(selected.get("color") or "").strip(),
    }



class Log:
    def __init__(self, bot):
        self.bot = bot
        self.log_error_type = [type for type in get_function_args(guilds_log_db.get) if type not in ['guild_id', 'id', 'enabled', 'updated_at', 'created_at']]
        
        # Initialize timeout_data to track the number of logs sent per guild and their log queues
        self.timeout_data = defaultdict(lambda: {"count": 0, "last_log_time": 0, "queue": None})
    
    async def send(self, guild: discord.Guild, type: str, embed: discord.Embed = None, content: str = None):
        base_type = str(type or "").strip().lower()
        type = base_type + "_channel_id"
        guilds_log_cache = cache.guilds_log.get(str(guild.id))
        
        if not guilds_log_cache or not guilds_log_cache.get('enabled'):
            return
        
        if type not in self.log_error_type:
            return
        
        channel_id = guilds_log_cache.get(type)
        override_payload = await _get_log_category_config(guild.id)
        override = _log_override_for_type(override_payload, base_type)
        if override is not None:
            if not bool(override.get("enabled")):
                return
            override_channel_id = str(override.get("channel_id") or "").strip()
            if override_channel_id.isdigit():
                channel_id = int(override_channel_id)
            override_color = str(override.get("color") or "").strip()
        else:
            override_color = ""
        if not channel_id:
            return
        
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return
        
        if not embed and not content:
            return
        
        if not embed:
            embed = discord.Embed(
                title="บันทึกระบบ",
                description=content,
                color=color.red
            )
        if override_color and embed:
            try:
                embed.color = discord.Color(int(override_color.lstrip("#"), 16))
            except Exception:
                pass
        
        # Initialize the queue for the guild if it doesn't exist
        guild_data = self.timeout_data[guild.id]
        if guild_data["queue"] is None:
            guild_data["queue"] = asyncio.Queue()
            asyncio.create_task(self.process_queue(guild))  # Start a background task to process the queue
        
        # Add both the channel and the embed (log entry) to the queue
        await guild_data["queue"].put((channel, embed))
    
    async def process_queue(self, guild: discord.Guild):
        guild_data = self.timeout_data[guild.id]
        queue = guild_data["queue"]
        
        while True:
            # Fetch the next (channel, embed) tuple from the queue
            channel, embed = await queue.get()
            
            current_time = time.time()
            
            # Reset count if more than 60 seconds have passed since the last log
            if current_time - guild_data["last_log_time"] > 60:
                guild_data["count"] = 0
            
            # If more than 5 logs have been sent within 60 seconds, introduce a 5-second delay
            if guild_data["count"] >= 20:
                await asyncio.sleep(5)
            
            # Try to send the log
            try:
                await channel.send(embed=embed)
                guild_data["count"] += 1
                guild_data["last_log_time"] = current_time
            except Exception as e:
                logger.error(f"Error in Log.process_queue: {e}")
            
            # Mark the task as done
            queue.task_done()
    
    async def wait_for_all_queues(self):
        # Wait until all queues are empty before proceeding (useful for shutdowns or graceful exits)
        tasks = []
        for guild_id, guild_data in self.timeout_data.items():
            if guild_data["queue"] is not None:
                tasks.append(guild_data["queue"].join())
        await asyncio.gather(*tasks)


        
class antinuke_log:
    def __init__(self, bot):
        self.bot = bot
        self.log_error_type = [type for type in get_function_args(guilds_log_db.get) if type not in ['guild_id','id','enabled','updated_at','created_at']]
    
    async def send(self,guild:discord.Guild,type:str,embed:discord.Embed=None,content:str=None):
        type = type.lower()+ "_channel_id"
        guilds_log_cache = cache.guilds_log[str(guild.id)]
        if not guilds_log_cache.get('enabled'):
            return
        
        if type not in self.log_error_type:
            return
        

        channel_id = guilds_log_cache.get(type)

        if not channel_id:
            return
        
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return

        if not embed and not content:
            return
        if not embed:
            embed = discord.Embed(
                title="บันทึกระบบ",
                description=content,
                color=color.red
            )
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in Log.error: {e}")

class EmojiManager:
    def __init__(self, default_emoji="✨"):
        self.default_emoji = default_emoji
        self._fallback_map = {
            "SHIELD": "🛡️",
            "BOT": "🤖",
            "WRENCH": "⚙️",
            "MUSIC": "🎵",
            "GLOBE": "🌐",
            "USERS": "👥",
            "ROCKET": "🚀",
            "GIFT": "🎁",
            "TICKET": "🎫",
            "BELL": "🔔",
            "STAR": "⭐",
            "SETTINGS": "⚙️",
            "PREMIUM": "💎",
            "LOCK": "🔐",
            "VOLUME": "🔊",
            "LEVELING": "📈",
            "COUNTING": "🔢",
            "J2C": "🎙️",
            "AI": "🧠",
            "CUSTOMROLE": "🎭",
            "VERIFICATION": "🛡️",
            "ENCRYPTION": "🔐",
            "MINECRAFT": "⛏️",
            "BIRTHDAY": "🎂",
            "AUTOREACT": "💬",
            "AUTOMOD": "🤖",
            "MODERATION": "🛡️",
            "UTILITY": "🛠️",
            "GAMES": "🎮",
            "IGNORE": "🚫",
            "SERVER": "🏰",
            "VOICE": "🔊",
            "WELCOMER": "👋",
        }

    def __getattr__(self, item):
        val = getattr(emoji, item, None)
        if val:
            return val
        clean_item = str(item or "").upper().replace("SL_", "").replace("SL", "").strip()
        if clean_item in self._fallback_map:
            return self._fallback_map[clean_item]
        for k, v in self._fallback_map.items():
            if k in clean_item:
                return v
        return self.default_emoji


class SkylineCommandTree(discord.app_commands.CommandTree):
    @discord.utils.copy_doc(discord.app_commands.CommandTree.add_command)
    def add_command(self, command, /, *, guild=discord.utils.MISSING, guilds=discord.utils.MISSING, override=False):
        owner = getattr(self, "client", None)
        should_register = True
        if owner and hasattr(owner, "_should_register_tree_command"):
            try:
                should_register = bool(owner._should_register_tree_command(command))
            except Exception:
                should_register = True
        if not should_register:
            return
        try:
            return super().add_command(command, guild=guild, guilds=guilds, override=override)
        except discord.app_commands.errors.CommandLimitReached:
            if owner and hasattr(owner, "_handle_slash_overflow"):
                owner._handle_slash_overflow(command)
                return
            raise

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        owner = getattr(self, "client", None)
        if owner and hasattr(owner, "handle_app_command_error"):
            try:
                await owner.handle_app_command_error(interaction, error)
                return
            except Exception:
                logger.error(
                    f"App command error handler failed: {traceback.format_exc()}"
                )
        await super().on_error(interaction, error)


class AutoShardedBot(commands.AutoShardedBot):
    def __init__(self, *arg, **kwargs):
        i18n.patch_discord_context()
        super().__init__(command_prefix=self.get_prefix,
                        case_insensitive=True,
                        intents=discord.Intents.all(),
                        status=discord.Status.dnd,
                        strip_after_prefix=True,
                        sync_commands_debug=True,
                        sync_commands=True,
                        help_command=None,
                        tree_cls=SkylineCommandTree,
                        shard_count=BotConfig.SHARD_COUNT,
                        enable_debug_events=True,
                        allowed_mentions=discord.AllowedMentions(everyone=False,replied_user=False,roles=False)
                        )
        self.developer:discord.User = self.user
        self.developers: list[discord.User] = []

        self.log = Log(self)
        self.users_data = config.users
        self.emoji = emoji # EmojiManager()
        self.cache = cache
        self.BotConfig = BotConfig
        self.channels = config.channels
        self.storage = storage
        self.database = self.storage
        self.antinuke_log = antinuke_log(self)
        self.urls = urls
        self.variables = {
                        "{user}": "The user's name",
                        "{user.id}": "The user's id",
                        "{user.tag}": "The user's tag",
                        "{user.mention}": "The user's mention",
                        "{user.avatar}": "The user's avatar",
                        "{user.created_at}": "The user's account creation date",
                        "{user.joined_at}": "The user's join date",
                        "{guild}": "The server name",
                        "{server}": "The server name",
                        "{server.id}": "The server id",
                        "{server.icon}": "The server icon",
                        "{guild.id}": "The server id",
                        "{guild.icon}": "The server icon",
                        "{guild.owner}": "The server owner",
                        "{guild.owner.id}": "The server owner id",
                        "{channel}": "The current target channel mention",
                        "{channel.id}": "The current target channel id",
                        "{channel.name}": "The current target channel name",
                        "{channel.mention}": "The current target channel mention",
                        "{welcome.channel}": "The current welcome channel mention",
                        "{welcome.channel.id}": "The current welcome channel id",
                        "{welcome.channel.mention}": "The current welcome channel mention",
                        "{room}": "Alias of current target channel mention",
                        "{room.id}": "Alias of current target channel id",
                        "{time}": "The current time",
                        "{member.count}": "The server member count"
                    }
        self.VERSION = '1.0.0'
        self.start_time = datetime.datetime.now(tz=datetime.timezone.utc)
        self._ownerbot_runtime_settings = _default_ownerbot_runtime_settings()
        self._ownerbot_runtime_loaded_at = 0.0
        self._ownerbot_runtime_next_retry_at = 0.0
        self._ownerbot_runtime_last_warn_at = 0.0
        self._ownerbot_runtime_fetch_task: asyncio.Task | None = None
        self._command_access_next_refresh_at: dict[str, float] = {}
        self._command_access_last_warn_at = 0.0
        self._slash_overflow_commands: list[str] = []
        self._slash_filtered_commands: list[str] = []
        self._slash_profiles_active: list[str] = []
        self._slash_profiles_unknown: list[str] = []
        self._slash_group_only_mode = (
            str(os.getenv("SLASH_GROUP_ONLY_MODE", "1")).strip().lower()
            in {"1", "true", "yes", "on"}
        )
        mode = str(os.getenv("SLASH_COMMAND_MODE", "essential")).strip().lower()
        self._slash_command_mode = mode if mode in {"essential", "all"} else "essential"
        selected_profiles = _parse_slash_profile_list(
            os.getenv("SLASH_COMMAND_PROFILES", "")
        )
        profile_chat_allowlist, profile_context_allowlist, unknown_profiles = (
            _collect_slash_profile_allowlists(selected_profiles)
        )
        self._slash_profiles_unknown = list(unknown_profiles)
        if selected_profiles and profile_chat_allowlist:
            self._slash_chat_allowlist = set(profile_chat_allowlist)
            self._slash_context_allowlist = set(profile_context_allowlist)
            self._slash_profiles_active = [
                profile
                for profile in selected_profiles
                if profile not in self._slash_profiles_unknown
            ]
        else:
            self._slash_chat_allowlist = set(DEFAULT_ESSENTIAL_SLASH_CHAT_COMMANDS)
            self._slash_context_allowlist = set(DEFAULT_ESSENTIAL_SLASH_CONTEXT_COMMANDS)
        self._slash_chat_blocklist = _parse_slash_name_set(
            os.getenv("SLASH_COMMAND_BLOCKLIST", "")
        )
        self._slash_context_blocklist = _parse_slash_name_set(
            os.getenv("SLASH_CONTEXT_BLOCKLIST", "")
        )
        self._slash_chat_allowlist.update(
            _parse_slash_name_set(os.getenv("SLASH_COMMAND_ALLOWLIST", ""))
        )
        self._slash_chat_allowlist.difference_update(self._slash_chat_blocklist)
        self._slash_context_allowlist.update(
            _parse_slash_name_set(os.getenv("SLASH_CONTEXT_ALLOWLIST", ""))
        )
        self._slash_context_allowlist.difference_update(self._slash_context_blocklist)
        self.add_check(self._check_command_access)
        try:
            self.tree.add_check(self._check_app_command_access)
        except Exception:
            pass

    def _track_slash_filtered(self, name: str) -> None:
        normalized = str(name or "").strip()
        if not normalized or normalized in self._slash_filtered_commands:
            return
        self._slash_filtered_commands.append(normalized)

    def _describe_app_command(self, command: object) -> str:
        cmd_type = getattr(command, "type", discord.AppCommandType.chat_input)
        name = str(
            getattr(command, "qualified_name", None) or getattr(command, "name", "unknown")
        ).strip()
        if cmd_type == discord.AppCommandType.chat_input:
            return f"/{_normalize_slash_name(name)}"
        return f"{getattr(cmd_type, 'name', 'unknown')}:{name}"

    def _is_empty_slash_description(self, value: object) -> bool:
        if not isinstance(value, str):
            return True
        normalized = " ".join(value.split()).strip().lower()
        if not normalized:
            return True
        return normalized in _EMPTY_SLASH_DESCRIPTION_VALUES

    def _clip_slash_description(self, value: object) -> str:
        compact = " ".join(str(value or "").split()).strip()
        if not compact:
            return ""
        if len(compact) > 100:
            compact = compact[:100].rstrip()
        return compact

    def _fallback_slash_description(self, command_name: str) -> str:
        readable = re.sub(r"[_-]+", " ", str(command_name or "").strip())
        readable = " ".join(readable.split())
        if not readable:
            return "คำสั่งของบอท"
        return self._clip_slash_description(f"ใช้งานคำสั่ง {readable}") or "คำสั่งของบอท"

    def _resolve_hybrid_description_text(self, command: commands.Command, app_name: str) -> str:
        candidates = [
            getattr(command, "help", None),
            getattr(command, "brief", None),
            getattr(command, "description", None),
        ]
        callback = getattr(command, "callback", None)
        callback_doc = inspect.getdoc(callback) if callback else None
        if callback_doc:
            candidates.append(str(callback_doc).splitlines()[0])
        for raw in candidates:
            clipped = self._clip_slash_description(raw)
            if not self._is_empty_slash_description(clipped):
                return clipped
        return self._fallback_slash_description(app_name or getattr(command, "name", "command"))

    def _apply_hybrid_slash_descriptions(self, command: commands.Command, app_command: object) -> None:
        if command is None or app_command is None:
            return

        current_description = getattr(app_command, "description", None)
        if self._is_empty_slash_description(current_description):
            resolved = self._resolve_hybrid_description_text(
                command=command,
                app_name=str(getattr(app_command, "name", "") or ""),
            )
            try:
                setattr(app_command, "description", resolved)
            except Exception:
                pass

        children = getattr(command, "commands", None)
        ext_children: dict[str, commands.Command] = {}
        if isinstance(children, dict):
            ext_children = {
                str(name): child
                for name, child in children.items()
                if isinstance(child, commands.Command)
            }
        elif isinstance(children, (list, tuple)):
            ext_children = {
                str(getattr(child, "name", "")): child
                for child in children
                if isinstance(child, commands.Command)
            }

        app_children = getattr(app_command, "commands", None)
        if isinstance(app_children, dict):
            iterable = list(app_children.values())
        elif isinstance(app_children, (list, tuple)):
            iterable = list(app_children)
        else:
            iterable = []

        for child_app in iterable:
            child_name = str(getattr(child_app, "name", "") or "").strip()
            mapped = ext_children.get(child_name)
            if mapped is not None:
                self._apply_hybrid_slash_descriptions(mapped, child_app)
                continue
            if self._is_empty_slash_description(getattr(child_app, "description", None)):
                try:
                    setattr(child_app, "description", self._fallback_slash_description(child_name))
                except Exception:
                    pass

    def _should_register_chat_input_name(self, name: str) -> bool:
        normalized = _normalize_slash_name(name)
        if not normalized:
            return False
        if self._slash_command_mode == "all":
            return normalized not in self._slash_chat_blocklist
        return normalized in self._slash_chat_allowlist

    def _should_register_context_name(self, name: str) -> bool:
        normalized = _normalize_slash_name(name)
        if not normalized:
            return False
        if self._slash_command_mode == "all":
            return normalized not in self._slash_context_blocklist
        return normalized in self._slash_context_allowlist

    def _is_group_only_exempt_chat_input_name(self, name: str) -> bool:
        normalized = _normalize_slash_name(name)
        if not normalized:
            return False
        return normalized in self._slash_chat_allowlist

    def _should_register_tree_command(self, command: object) -> bool:
        cmd_type = getattr(command, "type", discord.AppCommandType.chat_input)
        name = str(getattr(command, "name", "") or "")
        if cmd_type == discord.AppCommandType.chat_input:
            if self._slash_group_only_mode:
                parent = getattr(command, "parent", None)
                is_top_level = parent is None
                is_group = isinstance(command, discord.app_commands.Group)
                if (
                    is_top_level
                    and not is_group
                    and not self._is_group_only_exempt_chat_input_name(name)
                ):
                    self._track_slash_filtered(self._describe_app_command(command))
                    return False
            allowed = self._should_register_chat_input_name(name)
            if not allowed:
                self._track_slash_filtered(self._describe_app_command(command))
            return allowed
        if cmd_type in {discord.AppCommandType.user, discord.AppCommandType.message}:
            allowed = self._should_register_context_name(name)
            if not allowed:
                self._track_slash_filtered(self._describe_app_command(command))
            return allowed
        return True

    def _should_register_hybrid_as_slash(self, command: commands.Command) -> bool:
        root = getattr(command, "root_parent", None)
        if (
            self._slash_group_only_mode
            and root is None
            and not isinstance(command, commands.HybridGroup)
            and not self._is_group_only_exempt_chat_input_name(
                str(getattr(command, "name", "") or "")
            )
        ):
            return False
        root_name = str(getattr(root, "name", None) or getattr(command, "name", "")).strip()
        return self._should_register_chat_input_name(root_name)

    def _handle_slash_overflow(self, command: object) -> None:
        command_name = self._describe_app_command(command)
        if command_name not in self._slash_overflow_commands:
            self._slash_overflow_commands.append(command_name)
        logger.warning(
            "จำนวนคำสั่ง Slash รวมแตะลิมิต (100) แล้ว "
            f"จึงข้ามการลงทะเบียน Slash: {command_name or 'ไม่ทราบชื่อคำสั่ง'}"
        )

    def _disable_hybrid_app_registration(self, command: commands.Command) -> None:
        try:
            command.with_app_command = False
        except Exception:
            pass
        try:
            if isinstance(command, commands.HybridGroup):
                # HybridGroup expects MISSING (not None) when app command is disabled.
                # Using None can crash in HybridGroup._fallback_command for prefix invocations.
                command.app_command = discord.utils.MISSING
            else:
                command.app_command = None
        except Exception:
            pass

    @discord.utils.copy_doc(commands.GroupMixin.add_command)
    def add_command(self, command: commands.Command, /) -> None:
        # Keep text commands always available. Slash command registration can fail
        # when global command limit is exceeded (100). In that case we gracefully
        # keep the command as prefix-only instead of aborting bot startup.
        commands.GroupMixin.add_command(self, command)
        if not isinstance(command, (commands.HybridCommand, commands.HybridGroup)):
            return

        app_command = getattr(command, "app_command", None)
        if not app_command:
            return
        self._apply_hybrid_slash_descriptions(command, app_command)

        if not self._should_register_hybrid_as_slash(command):
            qualified_name = str(
                getattr(command, "qualified_name", None) or getattr(command, "name", "unknown")
            ).strip()
            self._track_slash_filtered(f"/{_normalize_slash_name(qualified_name.split(' ', 1)[0])}")
            self._disable_hybrid_app_registration(command)
            return

        # Avoid recursion for app command groups, same as discord.py behavior.
        if command.cog is not None and getattr(command.cog, "__cog_is_app_commands_group__", False):
            return

        try:
            self.tree.add_command(app_command)
        except Exception as error:
            is_limit_error = isinstance(error, discord.app_commands.errors.CommandLimitReached)
            if not is_limit_error:
                raise
            qualified_name = str(
                getattr(command, "qualified_name", None) or getattr(command, "name", "unknown")
            ).strip()
            if qualified_name and qualified_name not in self._slash_overflow_commands:
                self._slash_overflow_commands.append(qualified_name)
            self._disable_hybrid_app_registration(command)
            logger.warning(
                "จำนวนคำสั่ง Slash รวมแตะลิมิต (100) แล้ว "
                f"จึงคงคำสั่งนี้เป็น prefix เท่านั้น: {qualified_name or 'ไม่ทราบชื่อคำสั่ง'}"
            )


    async def _refresh_ownerbot_runtime_settings(
        self,
        *,
        fetch_timeout: float,
        retry_cooldown: float,
        warn_cooldown: float,
        startup_warn_after: float,
    ) -> dict:
        now = time.time()
        data = _default_ownerbot_runtime_settings()
        try:
            config_row = await asyncio.wait_for(
                storage.dashboard_config.get(config_key=OWNERBOT_RUNTIME_CONFIG_KEY),
                timeout=fetch_timeout,
            )
            raw_value = str((config_row or {}).get("config_value") or "").strip()
            if raw_value:
                decoded = json.loads(raw_value)
                if isinstance(decoded, dict):
                    data = _normalize_ownerbot_runtime_settings(decoded)
            self._ownerbot_runtime_next_retry_at = 0.0
        except Exception as error:
            self._ownerbot_runtime_next_retry_at = now + retry_cooldown
            if (now - float(self._ownerbot_runtime_last_warn_at or 0.0)) >= warn_cooldown:
                self._ownerbot_runtime_last_warn_at = now
                try:
                    started_at = float(self.start_time.timestamp())
                except Exception:
                    started_at = now
                startup_age = max(0.0, now - started_at)
                is_timeout = isinstance(error, (TimeoutError, asyncio.TimeoutError))
                timeout_during_startup = is_timeout and startup_age < startup_warn_after
                message = (
                    "Ownerbot runtime settings fetch failed; using cached/default settings "
                    f"(retry in {retry_cooldown:.0f}s): {type(error).__name__}: {error}"
                )
                if timeout_during_startup:
                    logger.info(f"{message} | phase=startup_warmup")
                else:
                    logger.warning(message)
            data = self._ownerbot_runtime_settings or _default_ownerbot_runtime_settings()
        self._ownerbot_runtime_settings = data
        self._ownerbot_runtime_loaded_at = now
        return data

    def _schedule_ownerbot_runtime_refresh(
        self,
        *,
        fetch_timeout: float,
        retry_cooldown: float,
        warn_cooldown: float,
        startup_warn_after: float,
    ) -> None:
        current_task = self._ownerbot_runtime_fetch_task
        if isinstance(current_task, asyncio.Task) and not current_task.done():
            return

        async def _runner():
            try:
                await self._refresh_ownerbot_runtime_settings(
                    fetch_timeout=fetch_timeout,
                    retry_cooldown=retry_cooldown,
                    warn_cooldown=warn_cooldown,
                    startup_warn_after=startup_warn_after,
                )
            except Exception:
                pass
            finally:
                self._ownerbot_runtime_fetch_task = None

        try:
            self._ownerbot_runtime_fetch_task = asyncio.create_task(_runner())
        except Exception:
            self._ownerbot_runtime_fetch_task = None

    async def _load_ownerbot_runtime_settings(self, force: bool = False):
        now = time.time()
        try:
            startup_warn_after = float(
                os.getenv("OWNERBOT_RUNTIME_STARTUP_WARN_AFTER_SECONDS", "90") or 90
            )
        except Exception:
            startup_warn_after = 90.0
        startup_warn_after = max(0.0, min(startup_warn_after, 3600.0))
        try:
            fetch_timeout = float(
                os.getenv("OWNERBOT_RUNTIME_FETCH_TIMEOUT_SECONDS", "1.5") or 1.5
            )
        except Exception:
            fetch_timeout = 1.5
        fetch_timeout = max(0.2, min(fetch_timeout, 8.0))
        try:
            retry_cooldown = float(os.getenv("OWNERBOT_RUNTIME_RETRY_COOLDOWN_SECONDS", "30") or 30)
        except Exception:
            retry_cooldown = 30.0
        retry_cooldown = max(1.0, min(retry_cooldown, 300.0))
        try:
            warn_cooldown = float(os.getenv("OWNERBOT_RUNTIME_WARN_COOLDOWN_SECONDS", "180") or 180)
        except Exception:
            warn_cooldown = 180.0
        warn_cooldown = max(15.0, min(warn_cooldown, 3600.0))
        try:
            cache_ttl = float(
                os.getenv("OWNERBOT_RUNTIME_SETTINGS_CACHE_TTL_SECONDS", "30") or 30
            )
        except Exception:
            cache_ttl = 30.0
        cache_ttl = max(5.0, min(cache_ttl, 300.0))

        if not force and now < float(self._ownerbot_runtime_next_retry_at or 0.0):
            return self._ownerbot_runtime_settings
        if not force and (now - self._ownerbot_runtime_loaded_at) < cache_ttl:
            return self._ownerbot_runtime_settings

        if force:
            return await self._refresh_ownerbot_runtime_settings(
                fetch_timeout=fetch_timeout,
                retry_cooldown=retry_cooldown,
                warn_cooldown=warn_cooldown,
                startup_warn_after=startup_warn_after,
            )

        self._schedule_ownerbot_runtime_refresh(
            fetch_timeout=fetch_timeout,
            retry_cooldown=retry_cooldown,
            warn_cooldown=warn_cooldown,
            startup_warn_after=startup_warn_after,
        )
        return self._ownerbot_runtime_settings

    def _ownerbot_is_guild_allowed(self, guild_id: int, settings: dict) -> bool:
        return _ownerbot_guild_block_reason(guild_id, settings) is None

    def _is_command_disabled_by_name_set(self, command_name: str, disabled_names: set[str]) -> bool:
        normalized = str(command_name or "").strip().lower()
        if normalized.startswith("/"):
            normalized = normalized[1:].strip()
        normalized = " ".join(normalized.split())
        if not normalized:
            return False

        normalized_disabled = {
            " ".join(str(name or "").strip().lower().lstrip("/").split())
            for name in (disabled_names or set())
            if str(name or "").strip()
        }
        if not normalized_disabled:
            return False

        parts = normalized.split()
        command_chain = {" ".join(parts[:index]) for index in range(1, len(parts) + 1)}
        command_chain.add(parts[-1])
        if command_chain.intersection(normalized_disabled):
            return True

        if len(parts) == 1:
            leaf_name = parts[0]
            suffix = f" {leaf_name}"
            if any(" " in name and name.endswith(suffix) for name in normalized_disabled):
                return True

        return False

    def _ownerbot_is_command_allowed(self, command_name: str, settings: dict) -> bool:
        disabled = set(settings.get("global_disabled_commands") or [])
        return not self._is_command_disabled_by_name_set(command_name, disabled)

    async def _get_guild_command_access(self, guild_id: int) -> dict:
        guild_key = str(guild_id)
        now = time.monotonic()
        next_refresh_at = float(self._command_access_next_refresh_at.get(guild_key, 0.0))
        if now >= next_refresh_at:
            try:
                latest = await asyncio.wait_for(
                    storage.command_access.get(guild_id=guild_id),
                    timeout=_ownerbot_command_access_fetch_timeout_seconds(),
                )
                if latest:
                    cache.command_access[guild_key] = latest
                elif guild_key not in cache.command_access:
                    cache.command_access[guild_key] = {"guild_id": guild_id, "disabled_commands": []}
                self._command_access_next_refresh_at[guild_key] = (
                    now + _COMMAND_ACCESS_REFRESH_TTL_SECONDS
                )
            except Exception as error:
                self._command_access_next_refresh_at[guild_key] = (
                    now + _COMMAND_ACCESS_REFRESH_RETRY_SECONDS
                )
                if (now - float(self._command_access_last_warn_at or 0.0)) >= 30.0:
                    self._command_access_last_warn_at = now
                    logger.warning(
                        "Command access refresh failed; using cached data "
                        f"for guild {guild_id}: {type(error).__name__}: {error}"
                    )
        return cache.command_access.get(guild_key, {}) or {}

    async def ownerbot_runtime_allows_message(self, guild_id: int) -> bool:
        settings = await self._load_ownerbot_runtime_settings()
        if not bool(settings.get("global_bot_response_enabled", True)):
            return False
        return self._ownerbot_is_guild_allowed(guild_id, settings)

    async def ownerbot_runtime_ai_model(self, fallback: str | None = None) -> str:
        settings = await self._load_ownerbot_runtime_settings()
        provider = _normalize_ownerbot_ai_provider(settings.get("global_ai_provider"))
        model = _normalize_ownerbot_ai_model(
            settings.get("global_ai_model"),
            provider=provider,
        )
        if model:
            return model
        fallback_model = str(fallback or "").strip()
        return fallback_model or _default_ownerbot_ai_model(provider=provider)

    async def ownerbot_runtime_ai_provider(self, fallback: str | None = None) -> str:
        settings = await self._load_ownerbot_runtime_settings()
        provider = _normalize_ownerbot_ai_provider(settings.get("global_ai_provider"))
        if provider:
            return provider
        return _normalize_ownerbot_ai_provider(fallback)

    async def _check_command_access(self, ctx: commands.Context) -> bool:
        if not ctx.guild or not ctx.command:
            return True
        if _ownerbot_is_developer_user(getattr(ctx.author, "id", None)):
            return True
        if _env_flag("OWNERBOT_FORCE_ENABLE_COMMANDS", False):
            return True
        try:
            settings = await asyncio.wait_for(
                self._load_ownerbot_runtime_settings(),
                timeout=_ownerbot_prefix_check_timeout_seconds(),
            )
        except asyncio.TimeoutError:
            logger.warning(
                "OwnerBOT prefix access check timeout. Allowing command by fail-open policy."
            )
            return True
        except Exception as error:
            logger.warning(
                f"OwnerBOT prefix access check failed. Allowing command by fail-open policy: {type(error).__name__}: {error}"
            )
            return True
        if not bool(settings.get("global_command_response_enabled", True)):
            raise commands.CheckFailure("ระบบเจ้าของบอท: ปิดการตอบสนองคำสั่งชั่วคราว")
        reason = _ownerbot_guild_block_reason(ctx.guild.id, settings)
        if reason:
            raise commands.CheckFailure(_ownerbot_block_message(reason))

        qualified_name = str(getattr(ctx.command, "qualified_name", ctx.command.name) or "").strip().lower()
        if not self._ownerbot_is_command_allowed(qualified_name, settings):
            raise commands.CheckFailure(OWNERBOT_GLOBAL_COMMAND_DISABLED_MESSAGE)

        command_access = await self._get_guild_command_access(ctx.guild.id)
        disabled_commands = set(command_access.get("disabled_commands", []) or [])
        if self._is_command_disabled_by_name_set(qualified_name, disabled_commands):
            raise commands.CheckFailure(GUILD_COMMAND_DISABLED_MESSAGE)
        return True

    async def _check_app_command_access(self, interaction: discord.Interaction) -> bool:
        guild = getattr(interaction, "guild", None)
        command = getattr(interaction, "command", None)
        if not guild or not command:
            return True
        if _ownerbot_is_developer_user(getattr(getattr(interaction, "user", None), "id", None)):
            return True
        if _env_flag("OWNERBOT_FORCE_ENABLE_COMMANDS", False):
            return True
        try:
            settings = await asyncio.wait_for(
                self._load_ownerbot_runtime_settings(),
                timeout=_ownerbot_app_check_timeout_seconds(),
            )
        except asyncio.TimeoutError:
            logger.warning(
                "OwnerBOT app access check timeout. Allowing slash command by fail-open policy."
            )
            return True
        except Exception as error:
            logger.warning(
                f"OwnerBOT app access check failed. Allowing slash command by fail-open policy: {type(error).__name__}: {error}"
            )
            return True
        if not bool(settings.get("global_command_response_enabled", True)):
            if not interaction.response.is_done():
                await interaction.response.send_message("ระบบเจ้าของบอท: ปิดการตอบสนองคำสั่งชั่วคราว", ephemeral=True)
            return False
        reason = _ownerbot_guild_block_reason(guild.id, settings)
        if reason:
            if not interaction.response.is_done():
                await interaction.response.send_message(_ownerbot_block_message(reason), ephemeral=True)
            return False
        qualified_name = (getattr(command, "qualified_name", getattr(command, "name", "")) or "").strip().lower()
        if not self._ownerbot_is_command_allowed(qualified_name, settings):
            if not interaction.response.is_done():
                await interaction.response.send_message(OWNERBOT_GLOBAL_COMMAND_DISABLED_MESSAGE, ephemeral=True)
            return False

        command_access = await self._get_guild_command_access(guild.id)
        disabled_commands = set(command_access.get("disabled_commands", []) or [])
        if self._is_command_disabled_by_name_set(qualified_name, disabled_commands):
            if not interaction.response.is_done():
                await interaction.response.send_message(GUILD_COMMAND_DISABLED_MESSAGE, ephemeral=True)
            return False
        return True
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        if _is_ignored_interaction_http_error(error):
            logger.warning(
                f"Ignored expired interaction for command {getattr(ctx.command, 'qualified_name', ctx.command)} "
                f"(message_id={getattr(getattr(ctx, 'message', None), 'id', 'unknown')})"
            )
            return

        if isinstance(error, commands.CheckFailure):
            message = _clean_error_text(error)
            if message:
                try:
                    await ctx.send(embed=discord.Embed(description=message, color=color.red), delete_after=12)
                except Exception:
                    try:
                        await ctx.send(message[:1900], delete_after=12)
                    except Exception:
                        pass
            return
        # Ignore common errors that don't need logging
        if isinstance(error, (commands.CommandNotFound, commands.CommandOnCooldown, commands.MissingRequiredArgument)):
            return

        # Log to console
        logger.error(f"คำสั่ง Error: {ctx.command} - {ctx.author}: {error}")
        
        # Send to report channel
        channel = self.get_channel(self.channels.report_channel)
        if channel:
            try:
                embed = discord.Embed(
                    title="เกิดข้อผิดพลาดในคำสั่ง",
                    description=f"เกิดข้อผิดพลาดขณะรันคำสั่ง: `{ctx.command}`",
                    color=color.red,
                    timestamp=datetime.datetime.now(tz=datetime.timezone.utc)
                )
                embed.add_field(name="คำสั่ง", value=f"`{ctx.command}`", inline=True)
                embed.add_field(name="ผู้ใช้", value=f"{ctx.author}\n({ctx.author.id})", inline=True)
                embed.add_field(name="กิลด์", value=f"{ctx.guild.name}\n({ctx.guild.id})" if ctx.guild else "DMs", inline=True)
                
                # รายละเอียดข้อผิดพลาด formatting
                tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
                if len(tb) > 950:
                    tb = tb[:950] + "\n... [Truncated]"
                
                embed.add_field(name="รายละเอียดข้อผิดพลาด", value=f"```py\n{tb}\n```", inline=False)
                embed.set_footer(text=f"Shard {ctx.guild.shard_id}" if ctx.guild else "No Shard")
                
                await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send command error to Discord: {e}")

    async def _send_app_error_message(
        self,
        interaction: discord.Interaction,
        message: str,
        *,
        ephemeral: bool = True,
    ) -> None:
        text = str(message or "").strip()
        if not text:
            return
        payload = text[:1900]
        try:
            if interaction.response.is_done():
                await interaction.followup.send(payload, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(payload, ephemeral=ephemeral)
        except Exception:
            pass

    async def handle_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, discord.app_commands.CheckFailure):
            await self._send_app_error_message(
                interaction,
                _clean_error_text(error)
                or "ระบบปฏิเสธการใช้งานคำสั่งนี้ในตอนนี้",
                ephemeral=True,
            )
            return

        if isinstance(error, discord.app_commands.CommandOnCooldown):
            retry_after = float(getattr(error, "retry_after", 0.0) or 0.0)
            await self._send_app_error_message(
                interaction,
                f"คำสั่งนี้ติดคูลดาวน์ ลองใหม่อีกครั้งใน {retry_after:.1f} วินาที",
                ephemeral=True,
            )
            return

        if isinstance(error, discord.app_commands.TransformerError):
            await self._send_app_error_message(
                interaction,
                "รูปแบบข้อมูลไม่ถูกต้องสำหรับคำสั่งนี้ กรุณาตรวจสอบตัวเลือกแล้วลองอีกครั้ง",
                ephemeral=True,
            )
            return

        original_error = getattr(error, "original", error)
        command_name = (
            str(
                getattr(getattr(interaction, "command", None), "qualified_name", "")
                or getattr(getattr(interaction, "command", None), "name", "")
            ).strip()
            or "unknown"
        )
        guild_id = getattr(getattr(interaction, "guild", None), "id", None)
        user_id = getattr(getattr(interaction, "user", None), "id", None)
        logger.error(
            f"App command error: command=/{command_name} guild={guild_id} user={user_id} "
            f"type={type(original_error).__name__} detail={original_error}"
        )

        await self._send_app_error_message(
            interaction,
            "เกิดข้อผิดพลาดระหว่างประมวลผลคำสั่ง ลองใหม่อีกครั้ง",
            ephemeral=True,
        )

    async def on_error(self, event_method, *args, **kwargs):
        # Log to console
        logger.error(f"Event Error in {event_method}: {traceback.format_exc()}")
        
        # Send to report channel
        channel = self.get_channel(self.channels.report_channel)
        if channel:
            try:
                embed = discord.Embed(
                    title="เกิดข้อผิดพลาดในอีเวนต์",
                    description=f"เกิดข้อผิดพลาดในอีเวนต์: `{event_method}`",
                    color=color.red,
                    timestamp=datetime.datetime.now(tz=datetime.timezone.utc)
                )
                embed.add_field(name="เมธอดอีเวนต์", value=f"`{event_method}`", inline=False)
                
                tb = traceback.format_exc()
                if len(tb) > 950:
                    tb = tb[:950] + "\n... [Truncated]"
                
                embed.add_field(name="รายละเอียดข้อผิดพลาด", value=f"```py\n{tb}\n```", inline=False)
                
                await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send event error to Discord: {e}")
    


    
    async def reload(self):
        importlib.reload(config)
        importlib.reload(emoji)
        importlib.reload(urls)
        importlib.reload(storage)
        self.users_data = config.users
        self.channels = config.channels
        self.BotConfig = config.BotConfigClass()
        self.urls = urls
        self.emoji = EmojiManager()
        self.storage = storage
        self.database = self.storage



    
    async def get_prefix(self, message: discord.Message):
            default_prefix = str(BotConfig.PREFIX)
            if message.guild:
                guild_id = str(message.guild.id)                
                if cache.users.get(str(message.author.id),{}).get('no_prefix',False) == True and cache.users.get(str(message.author.id),{}).get('no_prefix_subscription',False) == True:
                    if guild_id in cache.guilds:
                        guild_cache = cache.guilds[guild_id]
                        prefix = guild_cache.get('prefix') or default_prefix or "!"
                        if prefix == ">":
                            prefix = "!"
                        return commands.when_mentioned_or(prefix, '')(self, message)
                    else:
                        return commands.when_mentioned_or(default_prefix, '')(self, message)
                else:
                    if guild_id in cache.guilds:
                        guild_cache = cache.guilds[guild_id]
                        prefix = guild_cache.get('prefix') or default_prefix or "!"
                        if prefix == ">":
                            prefix = "!"
                        return commands.when_mentioned_or(prefix)(self, message)
                    else:
                        return commands.when_mentioned_or(default_prefix)(self, message)
            else:
                return commands.when_mentioned_or(default_prefix)(self, message)

