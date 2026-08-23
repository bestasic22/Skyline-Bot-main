from __future__ import annotations

import datetime
import io
import json
import os
import re
from typing import Any, Literal

import discord
import httpx
from discord import app_commands
from discord.ext import commands

import storage.rp_permissions as rp_permissions_db
import storage.rp_settings as rp_settings_db
from skylinebot.bridge.storage import get_collection
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.memory.cache import cache
from skylinebot.src.checks import checks
from skylinebot.src.services.ops_hub_service import OpsHubService
from skylinebot.src.services.welcomer_repository import WelcomerRepository
from skylinebot.style import color
from skylinebot.utils import fancy_text


FANCY_WRAPPER_PREFIX = "₊˚꒰"
FANCY_WRAPPER_SUFFIX = "꒱ ₊"
FANCY_WRAPPER_END = "✧꒷₊˚"
MAX_DISCORD_NAME = 100
MAX_TEXT_CHANNELS_PER_CREATE = 120
FREE_GUILDSTYLE_CREATE_LIMIT = 2
DEFAULT_GUILD_CHANNEL_LIMIT = 500
DEFAULT_GUILD_ROLE_LIMIT = 250

ROLEPLAY_PERMISSION_DEFAULTS: dict[str, str] = {
    "save_settings": "admin",
    "apply_preset": "admin",
    "manage_permissions": "owner",
    "add_scenario": "gm",
    "delete_scenario": "gm",
    "start_event": "gm",
    "end_event": "gm",
    "manage_scheduler": "admin",
    "manage_economy_guard": "admin",
    "import_config": "admin",
    "export_config": "gm",
    "view_audit": "gm",
    "rollback": "owner",
}

ROOM_PERMISSION_ATTRS: dict[str, str] = {
    "view": "view_channel",
    "send": "send_messages",
    "history": "read_message_history",
    "connect": "connect",
    "speak": "speak",
    "manage_messages": "manage_messages",
}

CUSTOM_CATEGORY_ALIAS_TO_SLUG: dict[str, str] = {
    "info": "information",
    "information": "information",
    "\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25": "information",
    "community": "community",
    "\u0e0a\u0e38\u0e21\u0e0a\u0e19": "community",
    "shop": "shop",
    "store": "shop",
    "\u0e23\u0e49\u0e32\u0e19\u0e04\u0e49\u0e32": "shop",
    "support": "support",
}

CUSTOM_TEXT_ALIAS_TO_SLUG: dict[str, str] = {
    "rules": "rules",
    "rule": "rules",
    "\u0e01\u0e0e": "rules",
    "\u0e01\u0e0f": "rules",
    "announcements": "announcements",
    "announcement": "announcements",
    "\u0e1b\u0e23\u0e30\u0e01\u0e32\u0e28": "announcements",
    "verify": "verify",
    "\u0e22\u0e37\u0e19\u0e22\u0e31\u0e19": "verify",
    "general": "general-chat",
    "general chat": "general-chat",
    "chat": "general-chat",
    "\u0e2b\u0e49\u0e2d\u0e07\u0e04\u0e38\u0e22": "general-chat",
    "\u0e04\u0e38\u0e22\u0e17\u0e31\u0e48\u0e27\u0e44\u0e1b": "general-chat",
}

CUSTOM_VOICE_ALIAS_TO_SLUG: dict[str, str] = {
    "general": "general-vc",
    "general vc": "general-vc",
    "lobby": "lobby-vc",
    "support": "support-vc",
    "\u0e2b\u0e49\u0e2d\u0e07\u0e1e\u0e39\u0e14\u0e04\u0e38\u0e22": "general-vc",
    "\u0e2b\u0e49\u0e2d\u0e07\u0e04\u0e38\u0e22": "general-vc",
}

KEYWORD_EMOJI_MAP: list[tuple[tuple[str, ...], str]] = [
    (("rule", "rules", "กฎ"), "📃"),
    (("announce", "news", "ประกาศ"), "📢"),
    (("verify", "ยืนยัน"), "✅"),
    (("faq", "help", "support", "ช่วยเหลือ"), "🛟"),
    (("chat", "talk", "general", "คุย"), "💬"),
    (("media", "photo", "video", "รูป"), "🖼️"),
    (("bot", "command", "คำสั่ง"), "🤖"),
    (("ticket", "แจ้งปัญหา"), "🎫"),
    (("music", "song", "เพลง"), "🎵"),
    (("voice", "vc", "เสียง"), "🎙️"),
    (("game", "เล่นเกม"), "🎮"),
    (("shop", "store", "ขายของ"), "🛒"),
    (("donate", "tip", "สนับสนุน"), "💰"),
    (("giveaway", "แจก", "reward"), "🎁"),
    (("log", "audit", "บันทึก"), "🧾"),
    (("staff", "admin", "ทีมงาน"), "🛡️"),
    (("welcome", "join", "ต้อนรับ"), "👋"),
    (("leave", "goodbye", "ลา"), "🚪"),
]


ENHANCED_KEYWORD_EMOJI_MAP: list[tuple[tuple[str, ...], str]] = [
    (("rule", "rules", "law", "กฎ", "กติกา"), "📜"),
    (("announce", "announcement", "news", "update", "ประกาศ"), "📢"),
    (("verify", "verified", "authentication", "ยืนยัน"), "✅"),
    (("guide", "wiki", "manual", "howto", "faq", "help"), "📘"),
    (("support", "assist", "ticket", "report", "contact"), "🎫"),
    (("chat", "talk", "general", "community", "discussion", "คุย"), "💬"),
    (("media", "photo", "video", "clip", "image", "รูป"), "🖼️"),
    (("voice", "vc", "call", "meeting", "เสียง"), "🎙️"),
    (("music", "song", "radio", "เพลง"), "🎵"),
    (("bot", "command", "commands", "cmd", "คำสั่ง"), "🤖"),
    (("game", "gaming", "rank", "ranking", "squad", "เล่นเกม"), "🎮"),
    (("shop", "store", "market", "order", "cart", "ขายของ"), "🛒"),
    (("payment", "wallet", "donate", "tip", "coins", "finance"), "💰"),
    (("giveaway", "reward", "prize", "แจก"), "🎁"),
    (("log", "audit", "history", "บันทึก"), "🧾"),
    (("staff", "admin", "mod", "moderator", "ทีมงาน"), "🛡️"),
    (("welcome", "join", "hello", "ต้อนรับ"), "👋"),
    (("leave", "goodbye", "bye", "ลา"), "🚪"),
    (("city", "town", "plaza", "street"), "🏙️"),
    (("hospital", "medical", "clinic", "emergency", "pharmacy"), "🏥"),
    (("school", "class", "exam", "student", "homework"), "🏫"),
    (("kingdom", "royal", "throne", "war-room"), "👑"),
    (("country", "nation", "parliament", "embassy"), "🏛️"),
    (("residence", "house", "home", "housing", "neighborhood"), "🏠"),
    (("jobs", "career", "quest"), "🧭"),
    (("transport", "travel", "hub", "station", "border"), "🚉"),
]
GUILDSTYLE_FALLBACK_EMOJI = "💬"
THAIMOJI_ENDPOINT = str(os.getenv("THAIMOJI_ENDPOINT", "https://api.aiforthai.in.th/emoji") or "").strip()
THAIMOJI_API_KEY = str(
    os.getenv("THAIMOJI_API_KEY", os.getenv("AIFORTHAI_EMOJI_API_KEY", os.getenv("AIFORTHAI_API_KEY", "")))
).strip()
THAIMOJI_SCORE_FLOOR = 0.30
THAIMOJI_CLASS_EMOJI_MAP: dict[str, str] = {
    "0": "🙂",
    "1": "😔",
    "2": "😠",
    "3": "😨",
    "4": "😲",
    "5": "🤢",
    "6": "🤩",
    "7": "😴",
    "8": "😅",
    "9": "😊",
    "10": "😐",
    "11": "🤔",
    "12": "😭",
    "13": "🙏",
    "14": "🤝",
    "15": "🎉",
    "16": "💪",
    "17": "💬",
    "18": "📣",
    "19": "✅",
    "20": "✨",
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return float(default)


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_id_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        src = raw
    else:
        text = str(raw or "").strip()
        if not text:
            return []
        try:
            decoded = json.loads(text)
            if isinstance(decoded, list):
                src = decoded
            else:
                src = [text]
        except Exception:
            src = re.split(r"[\s,]+", text)

    out: list[str] = []
    for item in src:
        value = str(item or "").strip()
        if value.isdigit() and value not in out:
            out.append(value)
    return out


def _keyword_emoji(name: str) -> str:
    lowered = str(name or "").strip().lower()
    if not lowered:
        return GUILDSTYLE_FALLBACK_EMOJI
    priority_keywords: list[tuple[tuple[str, ...], str]] = [
        (("city", "town", "plaza", "street"), "🏙️"),
        (("hospital", "medical", "clinic", "emergency", "pharmacy"), "🏥"),
        (("school", "class", "exam", "student", "homework"), "🏫"),
        (("kingdom", "royal", "throne", "war-room"), "👑"),
        (("country", "nation", "parliament", "embassy"), "🏛️"),
        (("residence", "house", "home", "housing", "neighborhood"), "🏠"),
        (("jobs", "career", "quest"), "🧭"),
        (("transport", "travel", "hub", "station", "border"), "🚉"),
    ]
    for words, emoji in priority_keywords:
        if any(word in lowered for word in words):
            return emoji
    for words, emoji in ENHANCED_KEYWORD_EMOJI_MAP:
        if any(word in lowered for word in words):
            return emoji
    for words, emoji in KEYWORD_EMOJI_MAP:
        if any(word in lowered for word in words):
            return emoji
    return GUILDSTYLE_FALLBACK_EMOJI


def _thaimoji_best_match(payload: Any) -> tuple[str, float] | None:
    if not isinstance(payload, dict):
        return None
    best_class = ""
    best_score = 0.0
    for raw_key, raw_value in payload.items():
        class_key = str(raw_key or "").strip()
        if not class_key.isdigit():
            continue
        score = _safe_float(raw_value, 0.0)
        if score > best_score:
            best_class = class_key
            best_score = score
    if not best_class:
        return None
    return best_class, best_score


def _normalize_emoji_prompt_text(raw_name: str) -> str:
    text = str(raw_name or "").strip().replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:160]


async def _keyword_emoji_ai(
    name: str,
    *,
    api_key: str | None = None,
    endpoint: str | None = None,
    cache: dict[str, str] | None = None,
    timeout_seconds: float = 2.8,
) -> str:
    fallback = _keyword_emoji(name)
    if fallback != GUILDSTYLE_FALLBACK_EMOJI:
        return fallback

    prompt = _normalize_emoji_prompt_text(name)
    if not prompt:
        return fallback
    if isinstance(cache, dict) and prompt in cache:
        return str(cache.get(prompt) or fallback)

    resolved_endpoint = str(endpoint or THAIMOJI_ENDPOINT or "").strip()
    resolved_key = str(api_key or THAIMOJI_API_KEY or "").strip()
    if not resolved_endpoint or not resolved_key:
        if isinstance(cache, dict):
            cache[prompt] = fallback
        return fallback

    headers = {
        "Apikey": resolved_key,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    params = {"text": prompt}
    timeout = httpx.Timeout(max(1.0, float(timeout_seconds or 2.8)))
    resolved = fallback
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(resolved_endpoint, params=params, headers=headers)
            response.raise_for_status()
            parsed = response.json()
        best = _thaimoji_best_match(parsed)
        if best:
            class_key, class_score = best
            if class_score >= THAIMOJI_SCORE_FLOOR:
                resolved = THAIMOJI_CLASS_EMOJI_MAP.get(class_key, fallback)
    except Exception:
        resolved = fallback

    if isinstance(cache, dict):
        cache[prompt] = resolved
    return resolved


def _title_case_from_slug(raw: str) -> str:
    text = str(raw or "").strip().replace("_", " ").replace("-", " ")
    if not text:
        return "Channel"
    return " ".join(part.capitalize() for part in text.split())


def _normalize_alias_key(raw: str) -> str:
    text = str(raw or "").strip().casefold()
    if not text:
        return ""
    text = text.replace("_", " ").replace("-", " ").replace("/", " ").replace("\\", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _alias_to_slug(
    raw: str,
    *,
    alias_map: dict[str, str],
    fallback_default: str,
) -> str:
    normalized = _normalize_alias_key(raw)
    if not normalized:
        return fallback_default
    compact = normalized.replace(" ", "")
    if normalized in alias_map:
        return alias_map[normalized]
    if compact in alias_map:
        return alias_map[compact]
    slug = normalized.replace(" ", "-")
    slug = re.sub(r"[^0-9a-z\u0E00-\u0E7F-]+", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or fallback_default


def _custom_category_slug(raw: str) -> str:
    return _alias_to_slug(
        raw,
        alias_map=CUSTOM_CATEGORY_ALIAS_TO_SLUG,
        fallback_default="category",
    )


def _custom_text_slug(raw: str) -> str:
    return _alias_to_slug(
        raw,
        alias_map=CUSTOM_TEXT_ALIAS_TO_SLUG,
        fallback_default="channel",
    )


def _custom_voice_slug(raw: str) -> str:
    token = str(raw or "").strip()
    token = re.sub(r"^(?:vc|voice)\s*[:#-]?\s*", "", token, flags=re.I)
    return _alias_to_slug(
        token,
        alias_map=CUSTOM_VOICE_ALIAS_TO_SLUG,
        fallback_default="voice-room",
    )


def _normalize_font_style_key(raw_value: Any, *, fallback: str = "bold") -> str:
    fallback_key = fancy_text.normalize_style_key(str(fallback or "bold"))
    style_raw = str(raw_value or "").strip()
    if not style_raw:
        return fallback_key
    if not fancy_text.is_known_style(style_raw):
        return fallback_key
    return fancy_text.normalize_style_key(style_raw)


def _guildstyle_font_style_rows() -> list[dict[str, str]]:
    rows = fancy_text.list_styles(sample_text="GuildStyle")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("id") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": key,
                "name": str(row.get("name") or key).strip() or key,
                "category": str(row.get("category") or "").strip().lower(),
            }
        )
    return out


def _fancy_wrap(name: str, emoji: str, font_style: str) -> str:
    plain = _title_case_from_slug(name)
    normalized_style = _normalize_font_style_key(font_style, fallback="bold")
    stylized = fancy_text.transform_text(plain, normalized_style)
    return f"{FANCY_WRAPPER_PREFIX}{emoji}{FANCY_WRAPPER_SUFFIX}{stylized}{FANCY_WRAPPER_END}"


def _trim_name(name: str, *, limit: int = MAX_DISCORD_NAME) -> str:
    clean = str(name or "").strip()
    if not clean:
        clean = "untitled"
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip()


class GuildStyler(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self.welcomer_repo = WelcomerRepository(bot)
        self.ops = OpsHubService(bot)

        class CogInfo:
            name = "GuildStyler"
            category = "Main"
            description = "Guild styling and auto setup commands"
            hidden = False
            emoji = "🧩"

        self.cog_info = CogInfo
        self._guildstyle_onboard_key = "onboard_flow"
        self._guildstyle_assets_key = "guildstyle_assets"
        self._guildstyle_layout_key = "guildstyle_layout"

    @staticmethod
    def _normalize_plan_tier(raw_value: Any) -> str:
        normalized = str(raw_value or "free").strip().lower().replace(" ", "_")
        mapping = {
            "free": "free",
            "basic": "free",
            "silver": "silver",
            "silver_guild_preminum": "silver",
            "silver_guild_premium": "silver",
            "gold": "golden",
            "gole": "golden",
            "golden": "golden",
            "golden_guild_premium": "golden",
            "diamond": "diamond",
            "diamond_guild_premium": "diamond",
            "permanent": "permanent",
            "lifetime": "permanent",
            "forever": "permanent",
            "permanent_guild_premium": "permanent",
            "lifetime_guild_premium": "permanent",
        }
        return mapping.get(normalized, "free")

    def _is_free_guild_plan(self, guild_id: int) -> bool:
        raw_subscription = (cache.guilds.get(str(int(guild_id)), {}) or {}).get("subscription", "free")
        return self._normalize_plan_tier(raw_subscription) == "free"

    async def _safe_ctx_defer(self, ctx: commands.Context, *, ephemeral: bool = False) -> bool:
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return False
        if interaction.response.is_done():
            return True
        try:
            await ctx.defer(ephemeral=ephemeral)
            return True
        except (discord.NotFound, discord.InteractionResponded):
            return False
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                return False
            raise

    async def _safe_ctx_send(self, ctx: commands.Context, content: str | None = None, **kwargs):
        try:
            if content is not None:
                return await ctx.send(content, **kwargs)
            return await ctx.send(**kwargs)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except discord.HTTPException as send_error:
            if getattr(send_error, "code", None) != 10062:
                raise

        channel = getattr(ctx, "channel", None)
        if channel is None:
            return None
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("ephemeral", None)
        if content is not None:
            return await channel.send(content, **fallback_kwargs)
        return await channel.send(**fallback_kwargs)

    @staticmethod
    def _theme_blueprint(theme: str) -> dict[str, Any]:
        selected = str(theme or "community").strip().lower()
        if selected == "roleplay":
            return {
                "categories": [
                    {
                        "name": "roleplay-information",
                        "emoji": "📚",
                        "text": ["rules", "announcements", "verify", "rp-guide", "rp-map-and-lore"],
                        "voice": [],
                    },
                    {
                        "name": "city",
                        "emoji": "🏙️",
                        "text": ["city-square-chat", "city-notice-board", "jobs-board", "market-chat", "transport-hub"],
                        "voice": ["city-plaza-1", "city-plaza-2", "city-plaza-3", "city-plaza-4", "city-plaza-5"],
                    },
                    {
                        "name": "hospital",
                        "emoji": "🏥",
                        "text": ["hospital-intake", "emergency-report", "medical-records", "pharmacy-log", "surgery-briefing"],
                        "voice": ["ward-1", "ward-2", "ward-3", "ward-4", "ward-5"],
                    },
                    {
                        "name": "school",
                        "emoji": "🏫",
                        "text": ["school-notice", "class-schedule", "homework-board", "exam-hall-chat", "student-council"],
                        "voice": ["class-science", "class-math", "class-english", "class-history", "class-art"],
                    },
                    {
                        "name": "kingdom",
                        "emoji": "👑",
                        "text": ["throne-room", "royal-law", "kingdom-diplomacy", "guard-command", "kingdom-quests"],
                        "voice": ["throne-hall", "royal-council", "war-room", "barracks-1", "barracks-2"],
                    },
                    {
                        "name": "country",
                        "emoji": "🏛️",
                        "text": ["country-news", "parliament-floor", "embassy-desk", "border-control", "citizen-services"],
                        "voice": ["parliament-hall", "embassy-room-1", "embassy-room-2", "national-briefing", "governor-office"],
                    },
                    {
                        "name": "residence",
                        "emoji": "🏠",
                        "text": ["neighborhood-chat", "housing-board", "family-stories", "community-market", "utility-requests"],
                        "voice": ["house-1", "house-2", "house-3", "house-4", "house-5"],
                    },
                ]
            }
        if selected == "shop":
            return {
                "categories": [
                    {"name": "information", "emoji": "📃", "text": ["rules", "announcements", "verify"], "voice": []},
                    {"name": "shop", "emoji": "🛒", "text": ["shop-menu", "new-order", "order-status", "review"], "voice": []},
                    {"name": "payment", "emoji": "💰", "text": ["donate", "payment-proof", "wallet-log"], "voice": []},
                    {"name": "support", "emoji": "🎫", "text": ["ticket", "faq", "contact-admin"], "voice": ["support-vc"]},
                    {"name": "community", "emoji": "💬", "text": ["general-chat", "media-share", "bot-commands"], "voice": ["general-vc"]},
                ]
            }
        if selected == "gaming":
            return {
                "categories": [
                    {"name": "information", "emoji": "📃", "text": ["rules", "announcements", "events"], "voice": []},
                    {"name": "lobby", "emoji": "🎮", "text": ["general-chat", "team-find", "clip-share"], "voice": ["lobby-vc", "squad-vc"]},
                    {"name": "ranking", "emoji": "🏆", "text": ["rank-chat", "challenge", "scoreboard"], "voice": []},
                    {"name": "support", "emoji": "🎫", "text": ["ticket", "report", "help"], "voice": ["support-vc"]},
                ]
            }
        return {
            "categories": [
                {"name": "information", "emoji": "📃", "text": ["rules", "announcements", "verify", "faq"], "voice": []},
                {"name": "community", "emoji": "💬", "text": ["general-chat", "media-share", "bot-commands"], "voice": ["general-vc"]},
                {"name": "support", "emoji": "🎫", "text": ["ticket", "questions", "contact-admin"], "voice": ["support-vc"]},
                {"name": "finance", "emoji": "💰", "text": ["donate", "shop", "giveaway"], "voice": []},
            ]
        }

    @staticmethod
    def _split_custom_items(raw: str) -> list[str]:
        text = str(raw or "").strip()
        if not text:
            return []
        parts = re.split(r"[,\n]+", text)
        out: list[str] = []
        seen: set[str] = set()
        for part in parts:
            item = str(part or "").strip()
            if not item:
                continue
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @classmethod
    def _parse_custom_blueprint(cls, custom_layout: str) -> tuple[dict[str, Any] | None, str | None]:
        raw = str(custom_layout or "").strip()
        if not raw:
            return None, "Custom layout is empty."

        categories: list[dict[str, Any]] = []
        blocks = [block.strip() for block in raw.split(";") if str(block).strip()]
        for block in blocks[:20]:
            if "=" in block:
                category_name_raw, channels_raw = block.split("=", 1)
            elif ":" in block:
                category_name_raw, channels_raw = block.split(":", 1)
            else:
                return None, f"Invalid block `{block}`. Use `category=text1,text2|voice1,voice2`."

            category_name = str(category_name_raw or "").strip()
            if not category_name:
                return None, "Category name cannot be empty."

            text_items: list[str] = []
            voice_items: list[str] = []

            if "|" in channels_raw:
                text_raw, voice_raw = channels_raw.split("|", 1)
                text_items = cls._split_custom_items(text_raw)
                voice_items = cls._split_custom_items(voice_raw)
            else:
                mixed_items = cls._split_custom_items(channels_raw)
                for token in mixed_items:
                    lowered = token.casefold()
                    if lowered.startswith(("vc:", "voice:", "#")):
                        voice_items.append(token.split(":", 1)[-1].lstrip("#").strip() or "voice-room")
                    else:
                        text_items.append(token)

            normalized_text = [_custom_text_slug(item) for item in text_items[:120]]
            normalized_voice = [_custom_voice_slug(item) for item in voice_items[:50]]
            normalized_text = [item for item in normalized_text if item]
            normalized_voice = [item for item in normalized_voice if item]
            if not normalized_text and not normalized_voice:
                continue

            categories.append(
                {
                    "name": _custom_category_slug(category_name),
                    "emoji": _keyword_emoji(category_name),
                    "text": normalized_text,
                    "voice": normalized_voice,
                }
            )

        if not categories:
            return None, "No valid categories found in custom layout."
        return {"categories": categories}, None

    async def _ensure_admin(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            await self._safe_ctx_send(ctx, "This command can only be used in a server.")
            return False
        is_allowed = await checks.check_is_moderator_permissions(
            ctx,
            "manage_guild",
            notify=False,
        )
        if is_allowed:
            return True
        await self._safe_ctx_send(
            ctx,
            embed=discord.Embed(
                description="คุณต้องมีสิทธิ์ `Manage Server` เพื่อใช้คำสั่งนี้",
                color=color.red,
            ),
        )
        return False

    @staticmethod
    def _bot_has_perms(guild: discord.Guild, *permission_names: str) -> tuple[bool, list[str]]:
        me = guild.me
        if me is None:
            return False, list(permission_names)
        missing = [name for name in permission_names if not getattr(me.guild_permissions, name, False)]
        return len(missing) == 0, missing

    @staticmethod
    def _font_style_autocomplete_choices(current: str) -> list[app_commands.Choice[str]]:
        query = str(current or "").strip().lower()
        rows = _guildstyle_font_style_rows()
        ranked: list[tuple[int, str, str]] = []
        for row in rows:
            key = str(row.get("id") or "").strip()
            if not key:
                continue
            label = str(row.get("name") or key).strip() or key
            haystack = f"{key} {label}".lower()
            if not query:
                score = 5
            elif key.startswith(query):
                score = 0
            elif f" {query}" in haystack:
                score = 1
            elif query in haystack:
                score = 2
            else:
                continue
            ranked.append((score, key, label))
        ranked.sort(key=lambda row: (row[0], row[1]))
        choices: list[app_commands.Choice[str]] = []
        for _, key, label in ranked[:25]:
            pretty = f"{key} ({label})"
            choices.append(app_commands.Choice(name=pretty[:100], value=key))
        return choices

    async def _create_category_if_missing(self, guild: discord.Guild, name: str, *, reason: str) -> tuple[discord.CategoryChannel | None, bool]:
        for category in guild.categories:
            if str(category.name) == str(name):
                return category, False
        try:
            created = await guild.create_category(name=name, reason=reason)
            return created, True
        except Exception:
            return None, False

    async def _create_text_channel_if_missing(
        self,
        guild: discord.Guild,
        *,
        category: discord.CategoryChannel | None,
        name: str,
        reason: str,
    ) -> tuple[discord.TextChannel | None, bool]:
        pool = list(category.text_channels) if category else list(guild.text_channels)
        existing = next((ch for ch in pool if str(ch.name) == str(name)), None)
        if existing is not None:
            return existing, False
        try:
            created = await guild.create_text_channel(name=name, category=category, reason=reason)
            return created, True
        except Exception:
            fallback = _trim_name(_title_case_from_slug(name).lower().replace(" ", "-"))
            fallback_existing = next((ch for ch in pool if str(ch.name) == fallback), None)
            if fallback_existing is not None:
                return fallback_existing, False
            try:
                created = await guild.create_text_channel(name=fallback, category=category, reason=reason)
                return created, True
            except Exception:
                refreshed_pool = list(category.text_channels) if category else list(guild.text_channels)
                matched = next((ch for ch in refreshed_pool if str(ch.name) in {str(name), fallback}), None)
                return matched, False

    async def _create_voice_channel_if_missing(
        self,
        guild: discord.Guild,
        *,
        category: discord.CategoryChannel | None,
        name: str,
        reason: str,
    ) -> tuple[discord.VoiceChannel | None, bool]:
        pool = list(category.voice_channels) if category else list(guild.voice_channels)
        existing = next((ch for ch in pool if str(ch.name) == str(name)), None)
        if existing is not None:
            return existing, False
        try:
            created = await guild.create_voice_channel(name=name, category=category, reason=reason)
            return created, True
        except Exception:
            fallback = _trim_name(_title_case_from_slug(name))
            fallback_existing = next((ch for ch in pool if str(ch.name) == fallback), None)
            if fallback_existing is not None:
                return fallback_existing, False
            try:
                created = await guild.create_voice_channel(name=fallback, category=category, reason=reason)
                return created, True
            except Exception:
                refreshed_pool = list(category.voice_channels) if category else list(guild.voice_channels)
                matched = next((ch for ch in refreshed_pool if str(ch.name) in {str(name), fallback}), None)
                return matched, False

    @staticmethod
    def _role_specs_for_theme(theme: str) -> list[tuple[str, str, discord.Colour]]:
        role_specs: list[tuple[str, str, discord.Colour]] = [
            ("owner", "👑", discord.Colour(0xFFD166)),
            ("admin", "🛡️", discord.Colour(0xEF476F)),
            ("moderator", "⚔️", discord.Colour(0x118AB2)),
            ("support", "🎫", discord.Colour(0x06D6A0)),
            ("verified", "✅", discord.Colour(0x2EC4B6)),
            ("vip", "✨", discord.Colour(0x9B5DE5)),
            ("booster", "💎", discord.Colour(0xF15BB5)),
            ("member", "👤", discord.Colour(0x8D99AE)),
        ]
        if str(theme or "").strip().lower() == "roleplay":
            role_specs.extend(
                [
                    ("gm", "GM", discord.Colour(0xF4A261)),
                    ("player", "PL", discord.Colour(0x5E60CE)),
                    ("citizen", "CT", discord.Colour(0x84A59D)),
                    ("doctor", "DR", discord.Colour(0x2A9D8F)),
                    ("teacher", "TC", discord.Colour(0x457B9D)),
                    ("police", "PD", discord.Colour(0x1D3557)),
                    ("merchant", "MC", discord.Colour(0xE9C46A)),
                    ("noble", "NB", discord.Colour(0x9D4EDD)),
                    ("king", "KG", discord.Colour(0xC1121F)),
                    ("queen", "QN", discord.Colour(0xB5179E)),
                ]
            )
        return role_specs

    async def _ensure_role_pack(
        self,
        guild: discord.Guild,
        *,
        font_style: str,
        reason: str,
        theme: str = "community",
    ) -> tuple[dict[str, discord.Role], int]:
        role_specs = self._role_specs_for_theme(theme)

        by_slug: dict[str, discord.Role] = {}
        created_count = 0
        existing_roles = list(guild.roles)

        for slug, emoji, role_color in role_specs:
            display_name = _trim_name(_fancy_wrap(slug, emoji, font_style))
            found = next((r for r in existing_roles if str(r.name) == display_name), None)
            if found is None:
                found = next((r for r in existing_roles if slug in str(r.name).lower()), None)
            if found is None:
                try:
                    found = await guild.create_role(
                        name=display_name,
                        color=role_color,
                        mentionable=False,
                        hoist=False,
                        reason=reason,
                    )
                    created_count += 1
                    existing_roles.append(found)
                except Exception:
                    found = None
            if found is not None:
                by_slug[slug] = found

        return by_slug, created_count

    async def _set_autorole(self, guild: discord.Guild, role: discord.Role) -> bool:
        settings = await self.welcomer_repo.ensure_settings(guild.id)
        if not settings:
            return False
        current = _parse_id_list(settings.get("autoroles", []))
        if str(role.id) not in current:
            current.insert(0, str(role.id))
        current = current[: max(1, _safe_int(settings.get("autoroles_limit"), 3))]
        await self.welcomer_repo.update_settings(
            guild.id,
            autorole=True,
            autoroles=json.dumps(current),
        )
        return True

    async def _sync_onboard_roles(self, guild: discord.Guild, roles_by_slug: dict[str, discord.Role]) -> None:
        verify_role = roles_by_slug.get("verified")
        member_role = roles_by_slug.get("member")
        if verify_role is None and member_role is None:
            return
        defaults = {"verify_role_id": 0, "member_role_id": 0}
        flow = await self.ops.get_config_data(guild.id, self._guildstyle_onboard_key, defaults)
        payload = dict(defaults)
        payload.update(flow or {})
        if verify_role is not None:
            payload["verify_role_id"] = int(verify_role.id)
        if member_role is not None:
            payload["member_role_id"] = int(member_role.id)
        await self.ops.set_config_data(guild.id, self._guildstyle_onboard_key, payload)

    @staticmethod
    def _unique_int_ids(values: Any) -> list[int]:
        source: list[Any]
        if isinstance(values, list):
            source = values
        else:
            source = _parse_id_list(values)
        out: list[int] = []
        seen: set[int] = set()
        for item in source:
            value = _safe_int(item, 0)
            if value <= 0 or value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out

    async def _get_guildstyle_assets_state(self, guild_id: int) -> dict[str, Any]:
        defaults = {
            "created_by_id": 0,
            "create_runs": 0,
            "category_ids": [],
            "text_channel_ids": [],
            "voice_channel_ids": [],
            "updated_at": "",
        }
        payload = await self.ops.get_config_data(guild_id, self._guildstyle_assets_key, defaults)
        out = dict(defaults)
        out.update(payload or {})
        out["created_by_id"] = _safe_int(out.get("created_by_id"), 0)
        out["create_runs"] = max(0, _safe_int(out.get("create_runs"), 0))
        out["category_ids"] = self._unique_int_ids(out.get("category_ids", []))
        out["text_channel_ids"] = self._unique_int_ids(out.get("text_channel_ids", []))
        out["voice_channel_ids"] = self._unique_int_ids(out.get("voice_channel_ids", []))
        return out

    async def _save_guildstyle_assets_state(
        self,
        guild_id: int,
        *,
        created_by_id: int,
        create_runs: int,
        category_ids: list[int],
        text_channel_ids: list[int],
        voice_channel_ids: list[int],
    ) -> dict[str, Any]:
        payload = {
            "created_by_id": max(0, int(created_by_id)),
            "create_runs": max(0, int(create_runs)),
            "category_ids": self._unique_int_ids(category_ids),
            "text_channel_ids": self._unique_int_ids(text_channel_ids),
            "voice_channel_ids": self._unique_int_ids(voice_channel_ids),
            "updated_at": self.ops.now_iso(),
        }
        await self.ops.set_config_data(guild_id, self._guildstyle_assets_key, payload)
        return payload

    @staticmethod
    def _normalize_layout_blueprint(payload: Any) -> dict[str, Any]:
        src = payload if isinstance(payload, dict) else {}
        out_categories: list[dict[str, Any]] = []
        for raw_category in list(src.get("categories") or [])[:20]:
            if not isinstance(raw_category, dict):
                continue
            raw_name = str(raw_category.get("name") or "").strip()
            if not raw_name:
                continue
            category_name = _custom_category_slug(raw_name)
            emoji = str(raw_category.get("emoji") or _keyword_emoji(category_name)).strip()[:16] or _keyword_emoji(category_name)

            text_seen: set[str] = set()
            text_items: list[str] = []
            for raw_text in list(raw_category.get("text") or [])[:MAX_TEXT_CHANNELS_PER_CREATE]:
                normalized = _custom_text_slug(str(raw_text or ""))
                if not normalized or normalized in text_seen:
                    continue
                text_seen.add(normalized)
                text_items.append(normalized)

            voice_seen: set[str] = set()
            voice_items: list[str] = []
            for raw_voice in list(raw_category.get("voice") or [])[:50]:
                normalized = _custom_voice_slug(str(raw_voice or ""))
                if not normalized or normalized in voice_seen:
                    continue
                voice_seen.add(normalized)
                voice_items.append(normalized)

            if not text_items and not voice_items:
                continue

            out_categories.append(
                {
                    "name": category_name,
                    "emoji": emoji,
                    "text": text_items,
                    "voice": voice_items,
                }
            )

        return {"categories": out_categories}

    async def _get_layout_state(self, guild_id: int) -> dict[str, Any]:
        defaults = {
            "version": 1,
            "theme": "roleplay",
            "font_style": "bold",
            "role_slugs": [],
            "blueprint": {"categories": []},
            "updated_at": "",
        }
        payload = await self.ops.get_config_data(guild_id, self._guildstyle_layout_key, defaults)
        out = dict(defaults)
        out.update(payload or {})
        theme = str(out.get("theme") or "roleplay").strip().lower()
        if theme not in {"community", "shop", "gaming", "roleplay", "custom"}:
            theme = "roleplay"
        font_style = _normalize_font_style_key(out.get("font_style"), fallback="bold")
        raw_role_slugs = out.get("role_slugs") if isinstance(out.get("role_slugs"), list) else []
        allowed_role_slugs = {slug for slug, _, _ in self._role_specs_for_theme(theme)}
        role_slugs: list[str] = []
        for raw_slug in raw_role_slugs:
            slug = str(raw_slug or "").strip().lower()
            if slug and slug in allowed_role_slugs and slug not in role_slugs:
                role_slugs.append(slug)
        if not role_slugs:
            role_slugs = [slug for slug, _, _ in self._role_specs_for_theme(theme)]
        blueprint = self._normalize_layout_blueprint(out.get("blueprint"))
        out["theme"] = theme
        out["font_style"] = font_style
        out["role_slugs"] = role_slugs
        out["blueprint"] = blueprint
        return out

    async def _save_layout_state(
        self,
        guild_id: int,
        *,
        theme: str,
        font_style: str,
        role_slugs: list[str],
        blueprint: dict[str, Any],
    ) -> dict[str, Any]:
        safe_theme = str(theme or "roleplay").strip().lower()
        if safe_theme not in {"community", "shop", "gaming", "roleplay", "custom"}:
            safe_theme = "roleplay"
        safe_font_style = _normalize_font_style_key(font_style, fallback="bold")
        allowed_role_slugs = {slug for slug, _, _ in self._role_specs_for_theme(safe_theme)}
        normalized_slugs: list[str] = []
        for raw_slug in list(role_slugs or []):
            slug = str(raw_slug or "").strip().lower()
            if slug and slug in allowed_role_slugs and slug not in normalized_slugs:
                normalized_slugs.append(slug)
        if not normalized_slugs:
            normalized_slugs = [slug for slug, _, _ in self._role_specs_for_theme(safe_theme)]
        normalized_blueprint = self._normalize_layout_blueprint(blueprint)
        payload = {
            "version": 1,
            "theme": safe_theme,
            "font_style": safe_font_style,
            "role_slugs": normalized_slugs,
            "blueprint": normalized_blueprint,
            "updated_at": self.ops.now_iso(),
        }
        await self.ops.set_config_data(guild_id, self._guildstyle_layout_key, payload)
        return payload

    async def _preflight_limit_check(
        self,
        guild: discord.Guild,
        *,
        theme: str,
        font_style: str,
        blueprint: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_theme = str(theme or "community").strip().lower()
        normalized_style = str(font_style or "bold").strip().lower()
        normalized_blueprint = self._normalize_layout_blueprint(blueprint)

        channel_limit = _safe_int(getattr(guild, "max_channels", 0), DEFAULT_GUILD_CHANNEL_LIMIT)
        if channel_limit <= 0:
            channel_limit = DEFAULT_GUILD_CHANNEL_LIMIT
        role_limit = _safe_int(getattr(guild, "max_roles", 0), DEFAULT_GUILD_ROLE_LIMIT)
        if role_limit <= 0:
            role_limit = DEFAULT_GUILD_ROLE_LIMIT

        missing_category_count = 0
        missing_text_count = 0
        missing_voice_count = 0
        existing_categories = {str(item.name): item for item in list(guild.categories)}

        for category_spec in normalized_blueprint.get("categories", []):
            category_name = _trim_name(
                _fancy_wrap(category_spec.get("name", "category"), category_spec.get("emoji", "C"), normalized_style)
            )
            category_obj = existing_categories.get(category_name)
            text_targets = list(category_spec.get("text", []))[:MAX_TEXT_CHANNELS_PER_CREATE]
            voice_targets = list(category_spec.get("voice", []))[:50]
            if category_obj is None:
                missing_category_count += 1
                missing_text_count += len(text_targets)
                missing_voice_count += len(voice_targets)
                continue

            existing_text_names = {str(ch.name) for ch in list(category_obj.text_channels)}
            existing_voice_names = {str(ch.name) for ch in list(category_obj.voice_channels)}
            for text_slug in text_targets:
                channel_name = _trim_name(_fancy_wrap(text_slug, _keyword_emoji(text_slug), normalized_style))
                if channel_name not in existing_text_names:
                    missing_text_count += 1
            for voice_slug in voice_targets:
                channel_name = _trim_name(_fancy_wrap(voice_slug, _keyword_emoji(voice_slug), normalized_style))
                if channel_name not in existing_voice_names:
                    missing_voice_count += 1

        missing_role_slugs: list[str] = []
        existing_roles = list(guild.roles)
        for role_slug, role_emoji, _ in self._role_specs_for_theme(normalized_theme):
            expected_name = _trim_name(_fancy_wrap(role_slug, role_emoji, normalized_style))
            found = next((role for role in existing_roles if str(role.name) == expected_name), None)
            if found is None:
                found = next((role for role in existing_roles if role_slug in str(role.name).lower()), None)
            if found is None:
                missing_role_slugs.append(role_slug)

        missing_channel_total = missing_category_count + missing_text_count + missing_voice_count
        projected_channel_total = len(guild.channels) + missing_channel_total
        projected_role_total = len(guild.roles) + len(missing_role_slugs)
        channel_over_limit_by = max(0, projected_channel_total - channel_limit)
        role_over_limit_by = max(0, projected_role_total - role_limit)
        ok = channel_over_limit_by <= 0 and role_over_limit_by <= 0

        return {
            "ok": ok,
            "channel_limit": channel_limit,
            "role_limit": role_limit,
            "current_channels": len(guild.channels),
            "current_roles": len(guild.roles),
            "missing_categories": missing_category_count,
            "missing_text": missing_text_count,
            "missing_voice": missing_voice_count,
            "missing_channels_total": missing_channel_total,
            "missing_roles_total": len(missing_role_slugs),
            "missing_role_slugs": missing_role_slugs,
            "projected_channels": projected_channel_total,
            "projected_roles": projected_role_total,
            "channel_over_limit_by": channel_over_limit_by,
            "role_over_limit_by": role_over_limit_by,
        }

    async def _auto_map_roleplay_permissions(
        self,
        guild: discord.Guild,
        *,
        roles_by_slug: dict[str, discord.Role],
    ) -> dict[str, Any]:
        gm_role = roles_by_slug.get("gm")
        player_role = roles_by_slug.get("player")
        if gm_role is None and player_role is None:
            return {"updated": False, "gm_role_id": 0, "player_role_id": 0}

        row = await rp_permissions_db.get(guild_id=guild.id) or {}
        gm_role_ids = [
            text
            for text in [str(item).strip() for item in list(row.get("gm_role_ids") or [])]
            if text.isdigit()
        ]
        player_role_ids = [
            text
            for text in [str(item).strip() for item in list(row.get("player_role_ids") or [])]
            if text.isdigit()
        ]
        action_levels_src = row.get("action_levels") if isinstance(row.get("action_levels"), dict) else {}
        action_levels: dict[str, str] = {}
        for action_key, fallback in ROLEPLAY_PERMISSION_DEFAULTS.items():
            level = str(action_levels_src.get(action_key) or fallback).strip().lower()
            if level not in {"owner", "admin", "gm", "player"}:
                level = fallback
            action_levels[action_key] = level

        changed = False
        if gm_role is not None:
            gm_role_id = str(int(gm_role.id))
            if gm_role_id not in gm_role_ids:
                gm_role_ids.append(gm_role_id)
                changed = True
        if player_role is not None:
            player_role_id = str(int(player_role.id))
            if player_role_id not in player_role_ids:
                player_role_ids.append(player_role_id)
                changed = True

        if row.get("id"):
            if changed or not action_levels_src:
                await rp_permissions_db.update(
                    id=row["id"],
                    gm_role_ids=gm_role_ids,
                    player_role_ids=player_role_ids,
                    action_levels=action_levels,
                    updated_at=_now_utc(),
                )
                changed = True
        else:
            await rp_permissions_db.insert(
                guild_id=guild.id,
                gm_role_ids=gm_role_ids,
                player_role_ids=player_role_ids,
                action_levels=action_levels,
                updated_at=_now_utc(),
            )
            changed = True

        return {
            "updated": changed,
            "gm_role_id": int(gm_role.id) if gm_role is not None else 0,
            "player_role_id": int(player_role.id) if player_role is not None else 0,
        }

    async def _auto_bind_roleplay_channels(
        self,
        guild: discord.Guild,
        *,
        text_channels_by_slug: dict[str, discord.TextChannel],
    ) -> dict[str, Any]:
        def _pick_channel(*slugs: str) -> discord.TextChannel | None:
            for raw_slug in slugs:
                key = str(raw_slug or "").strip().lower()
                if not key:
                    continue
                target = text_channels_by_slug.get(key)
                if isinstance(target, discord.TextChannel):
                    return target
            return None

        announce_channel = _pick_channel("announcements", "country-news", "city-notice-board")
        verify_channel = _pick_channel("verify")
        event_channel = _pick_channel("jobs-board", "kingdom-quests", "events")
        if event_channel is None:
            event_channel = announce_channel or verify_channel
        notify_channel = announce_channel or event_channel or verify_channel

        rp_settings_row = await rp_settings_db.get(guild_id=guild.id) or {}
        event_channel_id = str(int(event_channel.id)) if event_channel is not None else None
        if rp_settings_row.get("id"):
            await rp_settings_db.update(
                id=rp_settings_row["id"],
                event_announce_channel_id=event_channel_id,
                schedule_notify_on_start=True,
                schedule_notify_on_end=True,
                updated_at=_now_utc(),
            )
        else:
            await rp_settings_db.insert(
                guild_id=guild.id,
                enabled=True,
                event_announce_channel_id=event_channel_id,
                schedule_notify_on_start=True,
                schedule_notify_on_end=True,
                updated_at=_now_utc(),
            )

        try:
            guilds_col = await get_collection("guilds")
            existing_doc = await guilds_col.find_one({"guild_id": guild.id}, {"verify_settings_fallback": 1, "_id": 0})
            verify_payload = (
                existing_doc.get("verify_settings_fallback")
                if isinstance(existing_doc, dict) and isinstance(existing_doc.get("verify_settings_fallback"), dict)
                else {}
            )
            next_payload = dict(verify_payload)
            if verify_channel is not None:
                next_payload["verify_channel_id"] = str(int(verify_channel.id))
                next_payload["verify_panel_channel_id"] = str(int(verify_channel.id))
            if notify_channel is not None:
                next_payload["notify_channel_id"] = str(int(notify_channel.id))
            if next_payload != verify_payload:
                await guilds_col.update_one(
                    {"guild_id": guild.id},
                    {"$set": {"verify_settings_fallback": next_payload}},
                    upsert=True,
                )
        except Exception:
            pass

        return {
            "announce_channel_id": int(announce_channel.id) if announce_channel is not None else 0,
            "verify_channel_id": int(verify_channel.id) if verify_channel is not None else 0,
            "event_channel_id": int(event_channel.id) if event_channel is not None else 0,
        }

    async def _apply_blueprint_to_guild(
        self,
        guild: discord.Guild,
        *,
        theme: str,
        font_style: str,
        setup_autorole: bool,
        setup_permissions: bool,
        blueprint: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        normalized_theme = str(theme or "community").strip().lower()
        normalized_style = str(font_style or "bold").strip().lower()
        normalized_blueprint = self._normalize_layout_blueprint(blueprint)
        roles_by_slug, created_roles = await self._ensure_role_pack(
            guild,
            font_style=normalized_style,
            reason=reason,
            theme=normalized_theme,
        )
        await self._sync_onboard_roles(guild, roles_by_slug)

        created_categories = 0
        created_text = 0
        created_voice = 0
        permission_updates = 0
        created_category_ids: list[int] = []
        created_text_ids: list[int] = []
        created_voice_ids: list[int] = []
        text_channels_by_slug: dict[str, discord.TextChannel] = {}

        for category_spec in list(normalized_blueprint.get("categories", []))[:20]:
            category_name = _trim_name(
                _fancy_wrap(category_spec.get("name", "category"), category_spec.get("emoji", "C"), normalized_style)
            )
            category_obj, created_flag = await self._create_category_if_missing(
                guild,
                category_name,
                reason=reason,
            )
            if category_obj is None:
                continue
            if created_flag:
                created_categories += 1
                created_category_ids.append(int(category_obj.id))

            for text_name in list(category_spec.get("text", []))[:MAX_TEXT_CHANNELS_PER_CREATE]:
                text_emoji = _keyword_emoji(text_name)
                channel_name = _trim_name(_fancy_wrap(text_name, text_emoji, normalized_style))
                text_channel_obj, text_created = await self._create_text_channel_if_missing(
                    guild,
                    category=category_obj,
                    name=channel_name,
                    reason=reason,
                )
                if isinstance(text_channel_obj, discord.TextChannel):
                    text_channels_by_slug.setdefault(str(text_name).strip().lower(), text_channel_obj)
                if text_created:
                    created_text += 1
                    if text_channel_obj is not None:
                        created_text_ids.append(int(text_channel_obj.id))
                if setup_permissions and text_channel_obj is not None:
                    permission_updates += await self._apply_default_room_access(
                        channel=text_channel_obj,
                        channel_slug=text_name,
                        roles_by_slug=roles_by_slug,
                        reason=reason,
                    )

            for voice_name in list(category_spec.get("voice", []))[:50]:
                voice_emoji = _keyword_emoji(voice_name)
                channel_name = _trim_name(_fancy_wrap(voice_name, voice_emoji, normalized_style))
                voice_channel_obj, voice_created = await self._create_voice_channel_if_missing(
                    guild,
                    category=category_obj,
                    name=channel_name,
                    reason=reason,
                )
                if voice_created:
                    created_voice += 1
                    if voice_channel_obj is not None:
                        created_voice_ids.append(int(voice_channel_obj.id))
                if setup_permissions and voice_channel_obj is not None:
                    permission_updates += await self._apply_default_room_access(
                        channel=voice_channel_obj,
                        channel_slug=voice_name,
                        roles_by_slug=roles_by_slug,
                        reason=reason,
                    )

        autorole_result = "skip"
        if setup_autorole:
            member_role = roles_by_slug.get("member")
            if member_role is not None:
                autorole_result = "ok" if await self._set_autorole(guild, member_role) else "fail"
            else:
                autorole_result = "no_member_role"

        rp_permission_sync = {"updated": False, "gm_role_id": 0, "player_role_id": 0}
        auto_bind_result = {"announce_channel_id": 0, "verify_channel_id": 0, "event_channel_id": 0}
        if normalized_theme == "roleplay":
            rp_permission_sync = await self._auto_map_roleplay_permissions(
                guild,
                roles_by_slug=roles_by_slug,
            )
            auto_bind_result = await self._auto_bind_roleplay_channels(
                guild,
                text_channels_by_slug=text_channels_by_slug,
            )

        return {
            "theme": normalized_theme,
            "font_style": normalized_style,
            "blueprint": normalized_blueprint,
            "roles_by_slug": roles_by_slug,
            "created_roles": created_roles,
            "created_categories": created_categories,
            "created_text": created_text,
            "created_voice": created_voice,
            "permission_updates": permission_updates,
            "created_category_ids": created_category_ids,
            "created_text_ids": created_text_ids,
            "created_voice_ids": created_voice_ids,
            "autorole_result": autorole_result,
            "rp_permission_sync": rp_permission_sync,
            "auto_bind_result": auto_bind_result,
        }

    async def apply_roleplay_theme_from_dashboard(
        self,
        guild: discord.Guild,
        *,
        actor_label: str,
        font_style: str = "bold",
        setup_autorole: bool = True,
        setup_permissions: bool = True,
    ) -> dict[str, Any]:
        return await self.apply_theme_from_dashboard(
            guild,
            actor_label=actor_label,
            theme="roleplay",
            font_style=font_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
        )

    async def apply_theme_from_dashboard(
        self,
        guild: discord.Guild,
        *,
        actor_label: str,
        theme: str = "roleplay",
        font_style: str = "bold",
        setup_autorole: bool = True,
        setup_permissions: bool = True,
    ) -> dict[str, Any]:
        selected_theme = str(theme or "roleplay").strip().lower()
        if selected_theme not in {"community", "shop", "gaming", "roleplay"}:
            selected_theme = "roleplay"
        assets_state = await self._get_guildstyle_assets_state(guild.id)
        create_runs = max(0, _safe_int(assets_state.get("create_runs"), 0))
        is_free_plan = self._is_free_guild_plan(guild.id)
        if is_free_plan and create_runs >= FREE_GUILDSTYLE_CREATE_LIMIT:
            return {
                "ok": False,
                "limit_reached": True,
                "create_runs": create_runs,
                "max_runs": FREE_GUILDSTYLE_CREATE_LIMIT,
            }

        blueprint = self._theme_blueprint(selected_theme)
        preflight = await self._preflight_limit_check(
            guild,
            theme=selected_theme,
            font_style=font_style,
            blueprint=blueprint,
        )
        if not preflight.get("ok"):
            return {"ok": False, "error": preflight}
        result = await self._apply_blueprint_to_guild(
            guild,
            theme=selected_theme,
            font_style=font_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
            blueprint=blueprint,
            reason=f"GuildStyle dashboard apply by {actor_label}",
        )
        await self._save_guildstyle_assets_state(
            guild.id,
            created_by_id=0,
            create_runs=create_runs + 1,
            category_ids=list(result.get("created_category_ids") or []),
            text_channel_ids=list(result.get("created_text_ids") or []),
            voice_channel_ids=list(result.get("created_voice_ids") or []),
        )
        await self._save_layout_state(
            guild.id,
            theme=selected_theme,
            font_style=font_style,
            role_slugs=[slug for slug, _, _ in self._role_specs_for_theme(selected_theme)],
            blueprint=blueprint,
        )
        return {
            "ok": True,
            "result": result,
            "create_runs": create_runs + 1,
            "is_free_plan": is_free_plan,
            "theme": selected_theme,
        }

    @staticmethod
    def _find_role_by_keywords(guild: discord.Guild, *keywords: str) -> discord.Role | None:
        needle = [str(item or "").strip().casefold() for item in keywords if str(item or "").strip()]
        if not needle:
            return None
        for role in sorted(guild.roles, key=lambda item: item.position, reverse=True):
            if role.is_default():
                continue
            lowered = str(role.name or "").strip().casefold()
            if not lowered:
                continue
            if any(token in lowered for token in needle):
                return role
        return None

    @staticmethod
    def _collect_staff_roles(guild: discord.Guild) -> list[discord.Role]:
        staff_roles: list[discord.Role] = []
        seen_ids: set[int] = set()
        for role in sorted(guild.roles, key=lambda item: item.position, reverse=True):
            if role.is_default():
                continue
            perms = role.permissions
            if not (
                perms.administrator
                or perms.manage_guild
                or perms.manage_channels
                or perms.manage_roles
                or perms.kick_members
                or perms.ban_members
                or perms.moderate_members
            ):
                continue
            if role.id in seen_ids:
                continue
            seen_ids.add(role.id)
            staff_roles.append(role)
        return staff_roles

    async def _resolve_verified_role(self, guild: discord.Guild) -> discord.Role | None:
        defaults = {"verify_role_id": 0, "member_role_id": 0}
        flow = await self.ops.get_config_data(guild.id, self._guildstyle_onboard_key, defaults)
        verify_role_id = _safe_int((flow or {}).get("verify_role_id"), 0)
        member_role_id = _safe_int((flow or {}).get("member_role_id"), 0)
        for role_id in [verify_role_id, member_role_id]:
            if role_id <= 0:
                continue
            role_obj = guild.get_role(role_id)
            if role_obj is not None:
                return role_obj

        settings = await self.welcomer_repo.get_settings(guild.id)
        for role_id_text in _parse_id_list((settings or {}).get("autoroles", [])):
            role_obj = guild.get_role(_safe_int(role_id_text, 0))
            if role_obj is not None:
                return role_obj

        return self._find_role_by_keywords(guild, "verified", "verify", "member", "ยืนยัน", "สมาชิก")

    async def _apply_channel_overwrite(
        self,
        *,
        channel: discord.abc.GuildChannel,
        target: discord.Role,
        patch: dict[str, bool | None],
        reason: str,
    ) -> bool:
        overwrite = channel.overwrites_for(target)
        changed = False
        for perm_name, perm_value in patch.items():
            current = getattr(overwrite, perm_name, None)
            if current == perm_value:
                continue
            setattr(overwrite, perm_name, perm_value)
            changed = True
        if not changed:
            return False
        try:
            await channel.set_permissions(target, overwrite=overwrite, reason=reason)
            return True
        except Exception:
            return False

    async def _apply_room_permission_preset(
        self,
        *,
        channel: discord.abc.GuildChannel,
        preset: str,
        verified_role: discord.Role | None,
        staff_roles: list[discord.Role],
        reason: str,
    ) -> int:
        preset_key = str(preset or "").strip().casefold()
        everyone_role = channel.guild.default_role
        changed_count = 0

        everyone_patch: dict[str, bool | None]
        verified_patch: dict[str, bool | None]
        staff_patch: dict[str, bool | None]

        if isinstance(channel, discord.TextChannel):
            if preset_key == "public":
                everyone_patch = {"view_channel": True, "send_messages": True, "read_message_history": True, "add_reactions": True}
                verified_patch = dict(everyone_patch)
            elif preset_key == "locked":
                everyone_patch = {"view_channel": True, "send_messages": False, "read_message_history": True, "add_reactions": False}
                verified_patch = dict(everyone_patch)
            elif preset_key == "staff-only":
                everyone_patch = {"view_channel": False, "send_messages": False, "read_message_history": False, "add_reactions": False}
                verified_patch = dict(everyone_patch)
            else:
                everyone_patch = {"view_channel": False, "send_messages": False, "read_message_history": False, "add_reactions": False}
                verified_patch = {"view_channel": True, "send_messages": True, "read_message_history": True, "add_reactions": True}
            staff_patch = {
                "view_channel": True,
                "send_messages": True,
                "read_message_history": True,
                "add_reactions": True,
                "manage_messages": True,
            }
        elif isinstance(channel, discord.VoiceChannel):
            if preset_key == "public":
                everyone_patch = {"view_channel": True, "connect": True, "speak": True}
                verified_patch = dict(everyone_patch)
            elif preset_key == "locked":
                everyone_patch = {"view_channel": True, "connect": False, "speak": False}
                verified_patch = dict(everyone_patch)
            elif preset_key == "staff-only":
                everyone_patch = {"view_channel": False, "connect": False, "speak": False}
                verified_patch = dict(everyone_patch)
            else:
                everyone_patch = {"view_channel": False, "connect": False, "speak": False}
                verified_patch = {"view_channel": True, "connect": True, "speak": True}
            staff_patch = {
                "view_channel": True,
                "connect": True,
                "speak": True,
                "manage_channels": True,
            }
        elif isinstance(channel, discord.CategoryChannel):
            if preset_key == "public":
                everyone_patch = {"view_channel": True, "send_messages": True, "read_message_history": True, "connect": True, "speak": True}
                verified_patch = dict(everyone_patch)
            elif preset_key == "locked":
                everyone_patch = {"view_channel": True, "send_messages": False, "read_message_history": True, "connect": False, "speak": False}
                verified_patch = dict(everyone_patch)
            elif preset_key == "staff-only":
                everyone_patch = {"view_channel": False, "send_messages": False, "read_message_history": False, "connect": False, "speak": False}
                verified_patch = dict(everyone_patch)
            else:
                everyone_patch = {"view_channel": False, "send_messages": False, "read_message_history": False, "connect": False, "speak": False}
                verified_patch = {"view_channel": True, "send_messages": True, "read_message_history": True, "connect": True, "speak": True}
            staff_patch = {
                "view_channel": True,
                "send_messages": True,
                "read_message_history": True,
                "connect": True,
                "speak": True,
                "manage_channels": True,
                "manage_messages": True,
            }
        else:
            return 0

        changed_count += int(
            await self._apply_channel_overwrite(
                channel=channel,
                target=everyone_role,
                patch=everyone_patch,
                reason=reason,
            )
        )

        if verified_role is not None:
            changed_count += int(
                await self._apply_channel_overwrite(
                    channel=channel,
                    target=verified_role,
                    patch=verified_patch,
                    reason=reason,
                )
            )

        for staff_role in staff_roles:
            changed_count += int(
                await self._apply_channel_overwrite(
                    channel=channel,
                    target=staff_role,
                    patch=staff_patch,
                    reason=reason,
                )
            )
        return changed_count

    async def _apply_default_room_access(
        self,
        *,
        channel: discord.abc.GuildChannel,
        channel_slug: str,
        roles_by_slug: dict[str, discord.Role],
        reason: str,
    ) -> int:
        everyone = channel.guild.default_role
        verified_role = roles_by_slug.get("verified") or roles_by_slug.get("member")
        support_role = roles_by_slug.get("support")
        staff_roles = [
            roles_by_slug.get("owner"),
            roles_by_slug.get("admin"),
            roles_by_slug.get("moderator"),
            roles_by_slug.get("gm"),
            roles_by_slug.get("support"),
        ]
        staff_roles = [role for role in staff_roles if role is not None]
        slug = str(channel_slug or "").strip().casefold()
        changed_count = 0

        if isinstance(channel, discord.TextChannel):
            if slug == "verify":
                changed_count += int(
                    await self._apply_channel_overwrite(
                        channel=channel,
                        target=everyone,
                        patch={
                            "view_channel": True,
                            "send_messages": True,
                            "read_message_history": True,
                            "add_reactions": True,
                        },
                        reason=reason,
                    )
                )
                if verified_role is not None:
                    changed_count += int(
                        await self._apply_channel_overwrite(
                            channel=channel,
                            target=verified_role,
                            patch={
                                "view_channel": True,
                                "send_messages": False,
                                "read_message_history": True,
                                "add_reactions": False,
                            },
                            reason=reason,
                        )
                    )
            elif slug in {"rules", "announcements", "faq"}:
                changed_count += int(
                    await self._apply_channel_overwrite(
                        channel=channel,
                        target=everyone,
                        patch={
                            "view_channel": True,
                            "send_messages": False,
                            "read_message_history": True,
                            "add_reactions": False,
                        },
                        reason=reason,
                    )
                )
                if verified_role is not None:
                    changed_count += int(
                        await self._apply_channel_overwrite(
                            channel=channel,
                            target=verified_role,
                            patch={
                                "view_channel": True,
                                "send_messages": False,
                                "read_message_history": True,
                                "add_reactions": False,
                            },
                            reason=reason,
                        )
                    )
            else:
                changed_count += int(
                    await self._apply_channel_overwrite(
                        channel=channel,
                        target=everyone,
                        patch={
                            "view_channel": False,
                            "send_messages": False,
                            "read_message_history": False,
                            "add_reactions": False,
                        },
                        reason=reason,
                    )
                )
                if verified_role is not None:
                    changed_count += int(
                        await self._apply_channel_overwrite(
                            channel=channel,
                            target=verified_role,
                            patch={
                                "view_channel": True,
                                "send_messages": True,
                                "read_message_history": True,
                                "add_reactions": True,
                            },
                            reason=reason,
                        )
                    )

            for staff_role in staff_roles:
                changed_count += int(
                    await self._apply_channel_overwrite(
                        channel=channel,
                        target=staff_role,
                        patch={
                            "view_channel": True,
                            "send_messages": True,
                            "read_message_history": True,
                            "manage_messages": True,
                            "add_reactions": True,
                        },
                        reason=reason,
                    )
                )

        if isinstance(channel, discord.VoiceChannel):
            changed_count += int(
                await self._apply_channel_overwrite(
                    channel=channel,
                    target=everyone,
                    patch={
                        "view_channel": False,
                        "connect": False,
                        "speak": False,
                    },
                    reason=reason,
                )
            )
            if verified_role is not None:
                changed_count += int(
                    await self._apply_channel_overwrite(
                        channel=channel,
                        target=verified_role,
                        patch={
                            "view_channel": True,
                            "connect": True,
                            "speak": True,
                        },
                        reason=reason,
                    )
                )
            if support_role is not None and slug.startswith("support"):
                changed_count += int(
                    await self._apply_channel_overwrite(
                        channel=channel,
                        target=support_role,
                        patch={
                            "view_channel": True,
                            "connect": True,
                            "speak": True,
                        },
                        reason=reason,
                    )
                )
            for staff_role in staff_roles:
                changed_count += int(
                    await self._apply_channel_overwrite(
                        channel=channel,
                        target=staff_role,
                        patch={
                            "view_channel": True,
                            "connect": True,
                            "speak": True,
                            "manage_channels": True,
                        },
                        reason=reason,
                    )
                )
        return changed_count

    @staticmethod
    def _find_verify_text_channel(guild: discord.Guild) -> discord.TextChannel | None:
        for text_channel in guild.text_channels:
            lowered = str(text_channel.name or "").strip().casefold()
            if "verify" in lowered or "ยืนยัน" in lowered:
                return text_channel
        return None

    @commands.hybrid_group(
        name="guildstyle",
        with_app_command=True,
        invoke_without_command=True,
        help="สร้างและตกแต่งห้องและยศของกิลด์อัตโนมัติ",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=20, type=commands.BucketType.user)
    async def guildstyle(self, ctx: commands.Context):
        embed = discord.Embed(
            title="GuildStyle Commands (ไทย)",
            color=color.blue,
            description=(
                "`/guildstyle theme` - quick theme setup (dashboard style) (ไทย)\n"
                "`/guildstyle roplay` - quick roleplay theme setup\n"
                "`/guildstyle create` - create channels + roles + default room permissions\n"
                "`/guildstyle repair` - fill missing roleplay rooms/roles without overriding existing\n"
                "`/guildstyle roles` - create/update role pack only\n"
                "`/guildstyle decorate` - decorate existing channel/category names\n"
                "`/guildstyle layoutexport` - export room/role layout JSON\n"
                "`/guildstyle layoutimport` - import room/role layout JSON\n"
                "`/autorole setup` - open autorole toggle/setup menu\n"
                "`/autorole set` - set autorole target directly\n"
                "`/guildstyle verifyfix` - fix verify channel + verified role mapping\n"
                "`/guildstyle roomperm` - set view/send/connect permission per room\n"
                "`/guildstyle roompreset` - apply public/locked/staff-only/verified-only\n"
                "`/guildstyle roomperms` - inspect room access map\n"
                "`/guildstyle delete` - delete rooms created by latest guildstyle setup"
            ),
        )
        embed.add_field(
            name="Custom Layout",
            value=(
                "`category=text1,text2|voice1,voice2;category2=text3,text4`\n"
                "Example: `info=rules,announcements,verify|lobby-vc;shop=shop-menu,new-order|support-vc`\n"
                "Thai alias: `ข้อมูล=กฎ,ประกาศ|ห้องพูดคุย`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Plan Limit",
            value=(
                f"Free: `/guildstyle create` ได้สูงสุด **{FREE_GUILDSTYLE_CREATE_LIMIT}** ครั้ง\n"
                "Premium: ใช้งานได้ไม่จำกัด"
            ),
            inline=False,
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="create",
        help="สร้างหมวดหมู่ ห้อง และยศแบบตกแต่งจากพรีเซ็ตหรือเลย์เอาต์กำหนดเอง",
    )
    @app_commands.describe(
        theme="community | shop | gaming | roleplay | custom",
        font_style="font style key from /personalizer (e.g. bold, monospace, double_struck)",
        setup_autorole="Enable auto role for new members using Member role",
        setup_permissions="Apply default room permissions by role map",
        custom_layout="Required when theme=custom. Format: category=text1,text2|voice1,voice2;category2=text3 (supports Thai aliases)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=45, type=commands.BucketType.guild)
    async def guildstyle_create(
        self,
        ctx: commands.Context,
        theme: Literal["community", "shop", "gaming", "roleplay", "custom"] = "community",
        font_style: str = "bold",
        setup_autorole: bool = True,
        setup_permissions: bool = True,
        custom_layout: str | None = None,
    ):
        deferred = await self._safe_ctx_defer(ctx)
        if getattr(ctx, "interaction", None) is not None and not deferred:
            await self._safe_ctx_send(
                ctx,
                "Interaction expired before processing started. Please run `/guildstyle create` again.",
            )
            return
        if not await self._ensure_admin(ctx):
            return

        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_channels", "manage_roles")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`"
            )
        font_style = _normalize_font_style_key(font_style, fallback="bold")

        assets_state = await self._get_guildstyle_assets_state(ctx.guild.id)
        create_runs = max(0, _safe_int(assets_state.get("create_runs"), 0))
        is_free_plan = self._is_free_guild_plan(ctx.guild.id)
        if is_free_plan and create_runs >= FREE_GUILDSTYLE_CREATE_LIMIT:
            return await self._safe_ctx_send(
                ctx,
                embed=discord.Embed(
                    title="GuildStyle Limit Reached (ไทย)",
                    description=(
                        f"Free plan can run `/guildstyle create` up to **{FREE_GUILDSTYLE_CREATE_LIMIT}** times.\n"
                        f"Used: **{create_runs}/{FREE_GUILDSTYLE_CREATE_LIMIT}**\n"
                        "Remaining: **0**\n"
                        "Upgrade to a premium plan for unlimited usage."
                    ),
                    color=color.orange,
                ),
            )

        if str(theme).strip().lower() == "custom":
            blueprint, parse_error = self._parse_custom_blueprint(str(custom_layout or ""))
            if parse_error:
                return await self._safe_ctx_send(
                    ctx,
                    "Custom theme parse failed.\n"
                    f"Reason: {parse_error}\n\n"
                    "Format:\n"
                    "`category=text1,text2|voice1,voice2;category2=text3,text4`\n"
                    "Example:\n"
                    "`info=rules,announcements,verify|lobby-vc;shop=shop-menu,new-order|support-vc`\n"
                    "Thai alias example:\n"
                    "`ทั่วไป=แชท,ประกาศ|ห้องพูดคุย`"
                )
        else:
            blueprint = self._theme_blueprint(theme)

        preflight = await self._preflight_limit_check(
            ctx.guild,
            theme=theme,
            font_style=font_style,
            blueprint=blueprint,
        )
        if not preflight.get("ok"):
            missing_roles = ", ".join(preflight.get("missing_role_slugs", [])[:8]) or "-"
            return await self._safe_ctx_send(
                ctx,
                embed=discord.Embed(
                    title="GuildStyle Preflight Blocked (ไทย)",
                    color=color.red,
                    description=(
                        f"Theme: `{theme}` | Font: `{font_style}`\n"
                        f"Current channels: **{preflight.get('current_channels', 0)} / {preflight.get('channel_limit', 0)}**\n"
                        f"Need extra channels: **{preflight.get('missing_channels_total', 0)}** "
                        f"(category {preflight.get('missing_categories', 0)}, text {preflight.get('missing_text', 0)}, voice {preflight.get('missing_voice', 0)})\n"
                        f"Projected channels: **{preflight.get('projected_channels', 0)}** "
                        f"(over by **{preflight.get('channel_over_limit_by', 0)}**)\n"
                        f"Current roles: **{preflight.get('current_roles', 0)} / {preflight.get('role_limit', 0)}**\n"
                        f"Need extra roles: **{preflight.get('missing_roles_total', 0)}**\n"
                        f"Projected roles: **{preflight.get('projected_roles', 0)}** "
                        f"(over by **{preflight.get('role_over_limit_by', 0)}**)\n"
                        f"Missing role pack sample: `{missing_roles}`"
                    ),
                ),
            )

        reason = f"GuildStyle auto create by {ctx.author} ({ctx.author.id})"
        apply_result = await self._apply_blueprint_to_guild(
            ctx.guild,
            theme=theme,
            font_style=font_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
            blueprint=blueprint,
            reason=reason,
        )

        roles_by_slug = apply_result["roles_by_slug"]
        created_roles = int(apply_result["created_roles"])
        created_categories = int(apply_result["created_categories"])
        created_text = int(apply_result["created_text"])
        created_voice = int(apply_result["created_voice"])
        permission_updates = int(apply_result["permission_updates"])
        autorole_result = str(apply_result["autorole_result"])
        created_category_ids = list(apply_result["created_category_ids"])
        created_text_ids = list(apply_result["created_text_ids"])
        created_voice_ids = list(apply_result["created_voice_ids"])
        rp_permission_sync = apply_result.get("rp_permission_sync", {})
        auto_bind_result = apply_result.get("auto_bind_result", {})

        next_create_runs = create_runs + 1
        await self._save_guildstyle_assets_state(
            ctx.guild.id,
            created_by_id=int(ctx.author.id),
            create_runs=next_create_runs,
            category_ids=created_category_ids,
            text_channel_ids=created_text_ids,
            voice_channel_ids=created_voice_ids,
        )
        await self._save_layout_state(
            ctx.guild.id,
            theme=str(theme),
            font_style=str(font_style),
            role_slugs=[slug for slug, _, _ in self._role_specs_for_theme(str(theme))],
            blueprint=blueprint,
        )

        embed = discord.Embed(
            title="GuildStyle Setup Completed (ไทย)",
            color=color.green,
            description=(
                f"Theme: `{theme}` | Font: `{font_style}`\n"
                f"Categories created: **{created_categories}**\n"
                f"Text channels created: **{created_text}**\n"
                f"Voice channels created: **{created_voice}**\n"
                f"Roles created: **{created_roles}**\n"
                f"Autorole setup: **{autorole_result}**\n"
                f"Permission updates: **{permission_updates}**"
            ),
        )
        if is_free_plan:
            usage_text = (
                f"Used: **{next_create_runs}/{FREE_GUILDSTYLE_CREATE_LIMIT}**\n"
                f"Remaining: **{max(0, FREE_GUILDSTYLE_CREATE_LIMIT - next_create_runs)}**"
            )
        else:
            usage_text = (
                f"Used: **{next_create_runs}**\n"
                "Remaining: **Unlimited**"
            )
        embed.add_field(name="Create Usage", value=usage_text, inline=False)
        verified_role = roles_by_slug.get("verified")
        member_role = roles_by_slug.get("member")
        if verified_role or member_role:
            embed.add_field(
                name="Verification Mapping",
                value=(
                    f"Verified role: {verified_role.mention if verified_role else 'missing'}\n"
                    f"Member role: {member_role.mention if member_role else 'missing'}"
                ),
                inline=False,
            )
        if str(theme).strip().lower() == "roleplay":
            embed.add_field(
                name="Roleplay Auto Bind",
                value=(
                    f"RP permission sync: **{'yes' if rp_permission_sync.get('updated') else 'no'}**\n"
                    f"GM role id: `{int(rp_permission_sync.get('gm_role_id') or 0)}`\n"
                    f"Player role id: `{int(rp_permission_sync.get('player_role_id') or 0)}`\n"
                    f"Announce channel id: `{int(auto_bind_result.get('announce_channel_id') or 0)}`\n"
                    f"Verify channel id: `{int(auto_bind_result.get('verify_channel_id') or 0)}`\n"
                    f"Event channel id: `{int(auto_bind_result.get('event_channel_id') or 0)}`"
                ),
                inline=False,
            )
        if setup_permissions:
            embed.add_field(
                name="Default Access",
                value=(
                    "- `verify`: everyone can view/send\n"
                    "- `rules/announcements/faq`: read-only\n"
                    "- other rooms: verified + staff access"
                ),
                inline=False,
            )
        embed.add_field(
            name="Extendable Setup",
            value=(
                "Admins can add more channels/roles anytime.\n"
                "Running `/guildstyle create` again will only fill missing items."
            ),
            inline=False,
        )
        embed.add_field(
            name="Delete Guard",
            value=(
                f"Only {ctx.author.mention} can run `/guildstyle delete` "
                "for rooms created in this setup snapshot."
            ),
            inline=False,
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="theme",
        help="ตั้งค่าธีมแบบด่วน (กระบวนการเดียวกันกับคำสั่งสร้าง)",
    )
    @app_commands.describe(
        theme="community | shop | gaming | roleplay",
        font_style="font style key from /personalizer (e.g. bold, monospace, double_struck)",
        setup_autorole="Enable auto role for new members using Member role",
        setup_permissions="Apply default room permissions by role map",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=45, type=commands.BucketType.guild)
    async def guildstyle_theme(
        self,
        ctx: commands.Context,
        theme: Literal["community", "shop", "gaming", "roleplay"] = "community",
        font_style: str = "bold",
        setup_autorole: bool = True,
        setup_permissions: bool = True,
    ):
        await self.guildstyle_create(
            ctx,
            theme=theme,
            font_style=font_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
            custom_layout=None,
        )

    @guildstyle.command(
        name="roplay",
        help="ตั้งค่าโหมดโรลเพลย์ของ GuildStyle แบบด่วน",
    )
    @app_commands.describe(
        font_style="font style key from /personalizer (e.g. bold, monospace, double_struck)",
        setup_autorole="Enable auto role for new members using Member role",
        setup_permissions="Apply default room permissions by role map",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=45, type=commands.BucketType.guild)
    async def guildstyle_roplay(
        self,
        ctx: commands.Context,
        font_style: str = "bold",
        setup_autorole: bool = True,
        setup_permissions: bool = True,
    ):
        await self.guildstyle_create(
            ctx,
            theme="roleplay",
            font_style=font_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
            custom_layout=None,
        )

    @guildstyle.command(
        name="roleplay",
        help="คำสั่งทางลัดของ /guildstyle roplay",
    )
    @app_commands.describe(
        font_style="font style key from /personalizer (e.g. bold, monospace, double_struck)",
        setup_autorole="Enable auto role for new members using Member role",
        setup_permissions="Apply default room permissions by role map",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=45, type=commands.BucketType.guild)
    async def guildstyle_roleplay(
        self,
        ctx: commands.Context,
        font_style: str = "bold",
        setup_autorole: bool = True,
        setup_permissions: bool = True,
    ):
        await self.guildstyle_roplay(
            ctx,
            font_style=font_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
        )

    @guildstyle_create.autocomplete("font_style")
    async def guildstyle_create_font_style_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _ = interaction
        return self._font_style_autocomplete_choices(current)

    @guildstyle_theme.autocomplete("font_style")
    async def guildstyle_theme_font_style_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _ = interaction
        return self._font_style_autocomplete_choices(current)

    @guildstyle_roplay.autocomplete("font_style")
    async def guildstyle_roplay_font_style_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _ = interaction
        return self._font_style_autocomplete_choices(current)

    @guildstyle_roleplay.autocomplete("font_style")
    async def guildstyle_roleplay_font_style_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _ = interaction
        return self._font_style_autocomplete_choices(current)

    @guildstyle.command(
        name="repair",
        help="ซ่อมการตั้งค่าโรลเพลย์โดยสร้างเฉพาะห้องหรือยศที่ขาด",
    )
    @app_commands.describe(
        theme="roleplay",
        font_style="font style key from /personalizer (e.g. bold, monospace, double_struck)",
        setup_autorole="Enable auto role for new members using Member role",
        setup_permissions="Apply default room permissions by role map",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=35, type=commands.BucketType.guild)
    async def guildstyle_repair(
        self,
        ctx: commands.Context,
        theme: Literal["roleplay"] = "roleplay",
        font_style: str = "bold",
        setup_autorole: bool = True,
        setup_permissions: bool = True,
    ):
        deferred = await self._safe_ctx_defer(ctx)
        if getattr(ctx, "interaction", None) is not None and not deferred:
            await self._safe_ctx_send(
                ctx,
                "Interaction expired before processing started. Please run `/guildstyle repair` again.",
            )
            return
        if not await self._ensure_admin(ctx):
            return
        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_channels", "manage_roles")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`"
            )
        font_style = _normalize_font_style_key(font_style, fallback="bold")

        blueprint = self._theme_blueprint(theme)
        preflight = await self._preflight_limit_check(
            ctx.guild,
            theme=theme,
            font_style=font_style,
            blueprint=blueprint,
        )
        if not preflight.get("ok"):
            return await self._safe_ctx_send(
                ctx,
                embed=discord.Embed(
                    title="GuildStyle Repair Blocked (ไทย)",
                    color=color.red,
                    description=(
                        f"Repair needs extra channels **{preflight.get('missing_channels_total', 0)}** "
                        f"and extra roles **{preflight.get('missing_roles_total', 0)}**, "
                        "but current guild limits are not enough."
                    ),
                ),
            )

        reason = f"GuildStyle repair by {ctx.author} ({ctx.author.id})"
        apply_result = await self._apply_blueprint_to_guild(
            ctx.guild,
            theme=theme,
            font_style=font_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
            blueprint=blueprint,
            reason=reason,
        )

        previous_state = await self._get_guildstyle_assets_state(ctx.guild.id)
        await self._save_guildstyle_assets_state(
            ctx.guild.id,
            created_by_id=int(ctx.author.id),
            create_runs=max(0, _safe_int(previous_state.get("create_runs"), 0)),
            category_ids=list(apply_result.get("created_category_ids") or []),
            text_channel_ids=list(apply_result.get("created_text_ids") or []),
            voice_channel_ids=list(apply_result.get("created_voice_ids") or []),
        )
        await self._save_layout_state(
            ctx.guild.id,
            theme=str(theme),
            font_style=str(font_style),
            role_slugs=[slug for slug, _, _ in self._role_specs_for_theme(str(theme))],
            blueprint=blueprint,
        )

        rp_permission_sync = apply_result.get("rp_permission_sync", {})
        auto_bind_result = apply_result.get("auto_bind_result", {})
        embed = discord.Embed(
            title="GuildStyle Repair Completed (ไทย)",
            color=color.green,
            description=(
                f"Theme: `{theme}` | Font: `{font_style}`\n"
                f"Missing categories created: **{int(apply_result.get('created_categories') or 0)}**\n"
                f"Missing text channels created: **{int(apply_result.get('created_text') or 0)}**\n"
                f"Missing voice channels created: **{int(apply_result.get('created_voice') or 0)}**\n"
                f"Missing roles created: **{int(apply_result.get('created_roles') or 0)}**\n"
                f"Permission updates: **{int(apply_result.get('permission_updates') or 0)}**"
            ),
        )
        embed.add_field(
            name="Roleplay Auto Bind",
            value=(
                f"RP permission sync: **{'yes' if rp_permission_sync.get('updated') else 'no'}**\n"
                f"GM role id: `{int(rp_permission_sync.get('gm_role_id') or 0)}`\n"
                f"Player role id: `{int(rp_permission_sync.get('player_role_id') or 0)}`\n"
                f"Announce channel id: `{int(auto_bind_result.get('announce_channel_id') or 0)}`\n"
                f"Verify channel id: `{int(auto_bind_result.get('verify_channel_id') or 0)}`\n"
                f"Event channel id: `{int(auto_bind_result.get('event_channel_id') or 0)}`"
            ),
            inline=False,
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="roles",
        help="สร้างหรืออัปเดตเฉพาะชุดยศ GuildStyle",
    )
    @app_commands.describe(
        font_style="font style key from /personalizer (e.g. bold, monospace, double_struck)",
        setup_autorole="Enable auto role for new members using Member role",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=30, type=commands.BucketType.guild)
    async def guildstyle_roles(
        self,
        ctx: commands.Context,
        font_style: str = "bold",
        setup_autorole: bool = True,
    ):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return
        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_roles")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`"
            )
        font_style = _normalize_font_style_key(font_style, fallback="bold")

        reason = f"GuildStyle role pack by {ctx.author} ({ctx.author.id})"
        roles_by_slug, created_roles = await self._ensure_role_pack(
            ctx.guild, font_style=font_style, reason=reason
        )
        await self._sync_onboard_roles(ctx.guild, roles_by_slug)

        autorole_result = "skip"
        if setup_autorole:
            member_role = roles_by_slug.get("member")
            if member_role is not None:
                autorole_result = "ok" if await self._set_autorole(ctx.guild, member_role) else "fail"
            else:
                autorole_result = "no_member_role"

        embed = discord.Embed(
            title="GuildStyle Role Pack (ไทย)",
            color=color.green,
            description=(
                f"Created: **{created_roles}** role(s)\n"
                f"Autorole: **{autorole_result}**"
            ),
        )
        verify_role = roles_by_slug.get("verified")
        member_role = roles_by_slug.get("member")
        embed.add_field(
            name="Verification Mapping",
            value=(
                f"Verified role: {verify_role.mention if verify_role else 'missing'}\n"
                f"Member role: {member_role.mention if member_role else 'missing'}"
            ),
            inline=False,
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle_repair.autocomplete("font_style")
    async def guildstyle_repair_font_style_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _ = interaction
        return self._font_style_autocomplete_choices(current)

    @guildstyle_roles.autocomplete("font_style")
    async def guildstyle_roles_font_style_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _ = interaction
        return self._font_style_autocomplete_choices(current)

    @guildstyle.command(
        name="layoutexport",
        help="ส่งออกเลย์เอาต์ห้องและยศ GuildStyle เป็น JSON",
    )
    @app_commands.describe(theme="roleplay | community | shop | gaming")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=20, type=commands.BucketType.guild)
    async def guildstyle_layoutexport(
        self,
        ctx: commands.Context,
        theme: Literal["roleplay", "community", "shop", "gaming"] = "roleplay",
    ):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return

        requested_theme = str(theme or "roleplay").strip().lower()
        saved = await self._get_layout_state(ctx.guild.id)
        saved_blueprint = saved.get("blueprint") if isinstance(saved.get("blueprint"), dict) else {}
        if str(saved.get("theme") or "").strip().lower() == requested_theme and list(saved_blueprint.get("categories") or []):
            export_theme = requested_theme
            export_style = str(saved.get("font_style") or "bold")
            export_blueprint = saved_blueprint
            role_slugs = list(saved.get("role_slugs") or [])
        else:
            export_theme = requested_theme
            export_style = "bold"
            export_blueprint = self._normalize_layout_blueprint(self._theme_blueprint(requested_theme))
            role_slugs = [slug for slug, _, _ in self._role_specs_for_theme(requested_theme)]

        payload = {
            "version": 1,
            "theme": export_theme,
            "font_style": export_style,
            "role_slugs": role_slugs,
            "blueprint": export_blueprint,
            "guild_id": int(ctx.guild.id),
            "guild_name": str(ctx.guild.name),
            "exported_by_id": int(ctx.author.id),
            "exported_at": _now_utc().isoformat(),
        }
        file_name = f"guildstyle_layout_{int(ctx.guild.id)}_{export_theme}.json"
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        await self._safe_ctx_send(
            ctx,
            content=f"Exported layout `{export_theme}` successfully.",
            file=discord.File(fp=io.BytesIO(data), filename=file_name),
        )

    @guildstyle.command(
        name="layoutimport",
        help="นำเข้า JSON เลย์เอาต์ห้องและยศ GuildStyle และนำไปใช้",
    )
    @app_commands.describe(
        layout_file="JSON file from /guildstyle layoutexport",
        layout_json="Paste JSON payload directly (optional)",
        setup_autorole="Enable auto role for new members using Member role",
        setup_permissions="Apply default room permissions by role map",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=45, type=commands.BucketType.guild)
    async def guildstyle_layoutimport(
        self,
        ctx: commands.Context,
        layout_file: discord.Attachment | None = None,
        layout_json: str | None = None,
        setup_autorole: bool = True,
        setup_permissions: bool = True,
    ):
        deferred = await self._safe_ctx_defer(ctx)
        if getattr(ctx, "interaction", None) is not None and not deferred:
            await self._safe_ctx_send(
                ctx,
                "Interaction expired before processing started. Please run `/guildstyle layoutimport` again.",
            )
            return
        if not await self._ensure_admin(ctx):
            return
        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_channels", "manage_roles")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`"
            )

        raw_payload = str(layout_json or "").strip()
        if not raw_payload and layout_file is not None:
            try:
                file_bytes = await layout_file.read()
                raw_payload = file_bytes.decode("utf-8", errors="ignore").strip()
            except Exception:
                raw_payload = ""
        if not raw_payload:
            attachments = list(getattr(getattr(ctx, "message", None), "attachments", []) or [])
            if attachments:
                try:
                    file_bytes = await attachments[0].read()
                    raw_payload = file_bytes.decode("utf-8", errors="ignore").strip()
                except Exception:
                    raw_payload = ""
        if not raw_payload:
            return await self._safe_ctx_send(
                ctx,
                "Please upload a JSON layout file or provide `layout_json` payload.",
            )

        try:
            parsed = json.loads(raw_payload)
        except Exception:
            return await self._safe_ctx_send(ctx, "Invalid JSON payload.")
        if not isinstance(parsed, dict):
            return await self._safe_ctx_send(ctx, "Invalid layout format. Root JSON must be an object.")

        parsed_theme = str(parsed.get("theme") or "roleplay").strip().lower()
        if parsed_theme not in {"community", "shop", "gaming", "roleplay", "custom"}:
            parsed_theme = "roleplay"
        parsed_style = _normalize_font_style_key(parsed.get("font_style"), fallback="bold")

        source_blueprint = parsed.get("blueprint") if isinstance(parsed.get("blueprint"), dict) else parsed
        blueprint = self._normalize_layout_blueprint(source_blueprint)
        if not list(blueprint.get("categories") or []):
            return await self._safe_ctx_send(ctx, "Layout has no valid categories/channels to import.")

        preflight = await self._preflight_limit_check(
            ctx.guild,
            theme=parsed_theme,
            font_style=parsed_style,
            blueprint=blueprint,
        )
        if not preflight.get("ok"):
            return await self._safe_ctx_send(
                ctx,
                embed=discord.Embed(
                    title="GuildStyle Import Blocked (ไทย)",
                    color=color.red,
                    description=(
                        f"Import needs extra channels **{preflight.get('missing_channels_total', 0)}** "
                        f"and extra roles **{preflight.get('missing_roles_total', 0)}**, "
                        "but current guild limits are not enough."
                    ),
                ),
            )

        reason = f"GuildStyle layout import by {ctx.author} ({ctx.author.id})"
        apply_result = await self._apply_blueprint_to_guild(
            ctx.guild,
            theme=parsed_theme,
            font_style=parsed_style,
            setup_autorole=setup_autorole,
            setup_permissions=setup_permissions,
            blueprint=blueprint,
            reason=reason,
        )

        parsed_role_slugs: list[str] = []
        for raw_slug in list(parsed.get("role_slugs") or []):
            slug = str(raw_slug or "").strip().lower()
            if slug and slug not in parsed_role_slugs:
                parsed_role_slugs.append(slug)
        if not parsed_role_slugs:
            parsed_role_slugs = [slug for slug, _, _ in self._role_specs_for_theme(parsed_theme)]

        previous_state = await self._get_guildstyle_assets_state(ctx.guild.id)
        await self._save_guildstyle_assets_state(
            ctx.guild.id,
            created_by_id=int(ctx.author.id),
            create_runs=max(0, _safe_int(previous_state.get("create_runs"), 0)),
            category_ids=list(apply_result.get("created_category_ids") or []),
            text_channel_ids=list(apply_result.get("created_text_ids") or []),
            voice_channel_ids=list(apply_result.get("created_voice_ids") or []),
        )
        await self._save_layout_state(
            ctx.guild.id,
            theme=parsed_theme,
            font_style=parsed_style,
            role_slugs=parsed_role_slugs,
            blueprint=blueprint,
        )

        embed = discord.Embed(
            title="GuildStyle Layout Imported (ไทย)",
            color=color.green,
            description=(
                f"Theme: `{parsed_theme}` | Font: `{parsed_style}`\n"
                f"Categories created: **{int(apply_result.get('created_categories') or 0)}**\n"
                f"Text channels created: **{int(apply_result.get('created_text') or 0)}**\n"
                f"Voice channels created: **{int(apply_result.get('created_voice') or 0)}**\n"
                f"Roles created: **{int(apply_result.get('created_roles') or 0)}**"
            ),
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="verifyfix",
        help="ซ่อมการผูกช่องยืนยันกับบทบาทยืนยันพร้อมสิทธิ์",
    )
    @app_commands.describe(
        channel="Verification text channel (optional, auto-detect if omitted)",
        verified_role="Verified role to use (optional, auto-create if omitted)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=20, type=commands.BucketType.guild)
    async def guildstyle_verifyfix(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        verified_role: discord.Role | None = None,
    ):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return
        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_channels", "manage_roles")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`",
            )

        reason = f"GuildStyle verify fix by {ctx.author} ({ctx.author.id})"
        roles_by_slug, _ = await self._ensure_role_pack(ctx.guild, font_style="normal", reason=reason)
        if verified_role is None:
            verified_role = roles_by_slug.get("verified")
        else:
            roles_by_slug["verified"] = verified_role
        if verified_role is None:
            return await self._safe_ctx_send(ctx, "Unable to resolve/create a verified role.")

        verify_channel = channel or self._find_verify_text_channel(ctx.guild)
        if verify_channel is None:
            return await self._safe_ctx_send(
                ctx,
                "No verify channel found. Create one first (for example channel name including `verify`).",
            )

        changed = await self._apply_default_room_access(
            channel=verify_channel,
            channel_slug="verify",
            roles_by_slug=roles_by_slug,
            reason=reason,
        )
        await self._sync_onboard_roles(ctx.guild, roles_by_slug)

        embed = discord.Embed(
            title="Verify Setup Fixed (ไทย)",
            color=color.green,
            description=(
                f"Verify channel: {verify_channel.mention}\n"
                f"Verified role: {verified_role.mention}\n"
                f"Permission updates: **{changed}**"
            ),
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="roomperm",
        help="ตั้งค่า permission overwrite ของยศในห้องที่ระบุ",
    )
    @app_commands.describe(
        channel="Room to update",
        role="Role to apply permission overwrite",
        permission="view | send | history | connect | speak | manage_messages",
        state="allow | deny | clear",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=20, type=commands.BucketType.guild)
    async def guildstyle_roomperm(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel,
        role: discord.Role,
        permission: Literal["view", "send", "history", "connect", "speak", "manage_messages"],
        state: Literal["allow", "deny", "clear"] = "allow",
    ):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return

        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
            return await self._safe_ctx_send(ctx, "Only text/voice/category channels are supported.")

        permission_attr = ROOM_PERMISSION_ATTRS.get(str(permission).strip().lower())
        if not permission_attr:
            return await self._safe_ctx_send(ctx, f"Unknown permission key: `{permission}`")

        state_norm = str(state).strip().lower()
        new_value: bool | None
        if state_norm == "allow":
            new_value = True
        elif state_norm == "deny":
            new_value = False
        else:
            new_value = None

        changed = await self._apply_channel_overwrite(
            channel=channel,
            target=role,
            patch={permission_attr: new_value},
            reason=f"GuildStyle room permission by {ctx.author} ({ctx.author.id})",
        )

        state_label = "cleared" if new_value is None else ("allowed" if new_value else "denied")
        embed = discord.Embed(
            title="Room Permission Updated (ไทย)",
            color=color.green if changed else color.orange,
            description=(
                f"Channel: {channel.mention if hasattr(channel, 'mention') else channel.name}\n"
                f"Role: {role.mention}\n"
                f"Permission: `{permission_attr}` -> **{state_label}**\n"
                f"Changed: **{'yes' if changed else 'no'}**"
            ),
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="roompreset",
        help="ใช้พรีเซ็ตสิทธิ์สำเร็จรูปกับห้อง",
    )
    @app_commands.describe(
        channel="Room to apply preset permission",
        preset="public | locked | staff-only | verified-only",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=20, type=commands.BucketType.guild)
    async def guildstyle_roompreset(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel,
        preset: Literal["public", "locked", "staff-only", "verified-only"] = "verified-only",
    ):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return

        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
            return await self._safe_ctx_send(ctx, "Only text/voice/category channels are supported.")

        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_channels")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`",
            )

        verified_role = await self._resolve_verified_role(ctx.guild)
        preset_key = str(preset).strip().lower()
        if preset_key == "verified-only" and verified_role is None:
            return await self._safe_ctx_send(
                ctx,
                "Unable to resolve verified/member role. Run `/guildstyle roles` or `/guildstyle verifyfix` first.",
            )

        staff_roles = self._collect_staff_roles(ctx.guild)
        reason = f"GuildStyle room preset by {ctx.author} ({ctx.author.id})"
        changed = await self._apply_room_permission_preset(
            channel=channel,
            preset=preset_key,
            verified_role=verified_role,
            staff_roles=staff_roles,
            reason=reason,
        )

        embed = discord.Embed(
            title="Room Preset Applied (ไทย)",
            color=color.green if changed > 0 else color.orange,
            description=(
                f"Channel: {channel.mention if hasattr(channel, 'mention') else channel.name}\n"
                f"Preset: **{preset_key}**\n"
                f"Verified role: {verified_role.mention if verified_role else 'not found'}\n"
                f"Staff role targets: **{len(staff_roles)}**\n"
                f"Permission updates: **{changed}**"
            ),
        )
        embed.add_field(
            name="Preset Meanings",
            value=(
                "`public`: everyone can use room\n"
                "`locked`: everyone can view but cannot send/connect\n"
                "`staff-only`: hidden for members, staff-only access\n"
                "`verified-only`: verified + staff access"
            ),
            inline=False,
        )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="delete",
        help="ลบห้องที่สร้างจากสแนปช็อต GuildStyle ล่าสุด",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=45, type=commands.BucketType.guild)
    async def guildstyle_delete(self, ctx: commands.Context):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return

        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_channels")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`",
            )

        state = await self._get_guildstyle_assets_state(ctx.guild.id)
        created_by_id = _safe_int(state.get("created_by_id"), 0)
        category_ids = self._unique_int_ids(state.get("category_ids", []))
        text_ids = self._unique_int_ids(state.get("text_channel_ids", []))
        voice_ids = self._unique_int_ids(state.get("voice_channel_ids", []))
        tracked_total = len(category_ids) + len(text_ids) + len(voice_ids)

        if created_by_id <= 0 or tracked_total <= 0:
            return await self._safe_ctx_send(
                ctx,
                "No GuildStyle-created room snapshot found. Run `/guildstyle create` first.",
            )
        if int(ctx.author.id) != created_by_id:
            return await self._safe_ctx_send(
                ctx,
                f"Only setup creator <@{created_by_id}> can delete these rooms.",
            )

        deleted_count = 0
        missing_count = 0
        failed_count = 0
        reason = f"GuildStyle delete by {ctx.author} ({ctx.author.id})"

        for channel_id in voice_ids + text_ids:
            channel_obj = ctx.guild.get_channel(int(channel_id))
            if channel_obj is None:
                missing_count += 1
                continue
            if not isinstance(channel_obj, (discord.TextChannel, discord.VoiceChannel)):
                missing_count += 1
                continue
            try:
                await channel_obj.delete(reason=reason)
                deleted_count += 1
            except Exception:
                failed_count += 1

        for channel_id in category_ids:
            category_obj = ctx.guild.get_channel(int(channel_id))
            if category_obj is None:
                missing_count += 1
                continue
            if not isinstance(category_obj, discord.CategoryChannel):
                missing_count += 1
                continue
            try:
                await category_obj.delete(reason=reason)
                deleted_count += 1
            except Exception:
                failed_count += 1

        remaining_category_ids = [
            channel_id
            for channel_id in category_ids
            if isinstance(ctx.guild.get_channel(int(channel_id)), discord.CategoryChannel)
        ]
        remaining_text_ids = [
            channel_id
            for channel_id in text_ids
            if isinstance(ctx.guild.get_channel(int(channel_id)), discord.TextChannel)
        ]
        remaining_voice_ids = [
            channel_id
            for channel_id in voice_ids
            if isinstance(ctx.guild.get_channel(int(channel_id)), discord.VoiceChannel)
        ]
        remaining_total = len(remaining_category_ids) + len(remaining_text_ids) + len(remaining_voice_ids)

        await self._save_guildstyle_assets_state(
            ctx.guild.id,
            created_by_id=(created_by_id if remaining_total > 0 else 0),
            create_runs=max(0, _safe_int(state.get("create_runs"), 0)),
            category_ids=remaining_category_ids,
            text_channel_ids=remaining_text_ids,
            voice_channel_ids=remaining_voice_ids,
        )

        embed = discord.Embed(
            title="GuildStyle Delete Completed (ไทย)",
            color=color.green if failed_count == 0 else color.orange,
            description=(
                f"Deleted: **{deleted_count}**\n"
                f"Missing/Already removed: **{missing_count}**\n"
                f"Failed: **{failed_count}**\n"
                f"Remaining tracked rooms: **{remaining_total}**"
            ),
        )
        if failed_count > 0:
            embed.add_field(
                name="Note",
                value="Some categories may still contain channels, or the bot may lack permission to delete them.",
                inline=False,
            )
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="roomperms",
        help="ตรวจสอบตาราง permission overwrite ของยศในห้อง",
    )
    @app_commands.describe(channel="Room to inspect")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=20, type=commands.BucketType.guild)
    async def guildstyle_roomperms(self, ctx: commands.Context, channel: discord.abc.GuildChannel):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return

        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
            return await self._safe_ctx_send(ctx, "Only text/voice/category channels are supported.")

        def _state_label(value: bool | None) -> str:
            if value is True:
                return "allow"
            if value is False:
                return "deny"
            return "inherit"

        lines: list[str] = []
        for target, overwrite in channel.overwrites.items():
            if not isinstance(target, discord.Role):
                continue
            view_state = _state_label(overwrite.view_channel)
            send_state = _state_label(overwrite.send_messages)
            history_state = _state_label(overwrite.read_message_history)
            connect_state = _state_label(overwrite.connect)
            speak_state = _state_label(overwrite.speak)
            if all(item == "inherit" for item in [view_state, send_state, history_state, connect_state, speak_state]):
                continue
            lines.append(
                f"{target.mention}: view={view_state}, send={send_state}, history={history_state}, connect={connect_state}, speak={speak_state}"
            )

        embed = discord.Embed(
            title="Room Access Matrix (ไทย)",
            color=color.blue,
            description=f"Channel: {channel.mention if hasattr(channel, 'mention') else channel.name}",
        )
        embed.add_field(
            name="Role Overwrites",
            value=("\n".join(lines[:20]) if lines else "No explicit role overwrites."),
            inline=False,
        )
        if len(lines) > 20:
            embed.set_footer(text=f"...and {len(lines) - 20} more role overwrite(s)")
        await self._safe_ctx_send(ctx, embed=embed)

    @guildstyle.command(
        name="decorate",
        help="เปลี่ยนชื่อห้องหรือหมวดหมู่ที่มีอยู่ด้วยสไตล์ GuildStyle",
    )
    @app_commands.describe(
        scope="channels | categories | both",
        font_style="font style key from /personalizer (e.g. bold, monospace, double_struck)",
        apply="If false, show preview only. If true, rename immediately.",
        limit="Max items to process",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=30, type=commands.BucketType.guild)
    async def guildstyle_decorate(
        self,
        ctx: commands.Context,
        scope: Literal["channels", "categories", "both"] = "both",
        font_style: str = "bold",
        apply: bool = False,
        limit: int = 30,
    ):
        await self._safe_ctx_defer(ctx)
        if not await self._ensure_admin(ctx):
            return
        has_perms, missing = self._bot_has_perms(ctx.guild, "manage_channels")
        if not has_perms:
            return await self._safe_ctx_send(
                ctx,
                f"I need permissions before setup: `{', '.join(missing)}`"
            )
        font_style = _normalize_font_style_key(font_style, fallback="bold")

        max_items = max(1, min(int(limit), 100))
        candidates: list[discord.abc.GuildChannel] = []

        if scope in {"categories", "both"}:
            candidates.extend(list(ctx.guild.categories))
        if scope in {"channels", "both"}:
            candidates.extend(list(ctx.guild.text_channels))
            candidates.extend(list(ctx.guild.voice_channels))

        plans: list[tuple[discord.abc.GuildChannel, str]] = []
        for item in candidates:
            current = str(getattr(item, "name", "") or "").strip()
            if not current:
                continue
            if current.startswith(FANCY_WRAPPER_PREFIX):
                continue
            emoji = _keyword_emoji(current)
            target = _trim_name(_fancy_wrap(current, emoji, font_style))
            if target == current:
                continue
            plans.append((item, target))
            if len(plans) >= max_items:
                break

        if not plans:
            return await self._safe_ctx_send(
                ctx,
                embed=discord.Embed(
                    title="GuildStyle Decorate (ไทย)",
                    description="ไม่พบห้องหรือหมวดหมู่ที่ตรงสำหรับการตกแต่ง",
                    color=color.orange,
                ),
            )

        if not apply:
            preview_lines = [f"`{old.name}` -> `{new}`" for old, new in plans[:20]]
            more = "" if len(plans) <= 20 else f"\n...and {len(plans) - 20} more"
            return await self._safe_ctx_send(
                ctx,
                embed=discord.Embed(
                    title="GuildStyle Decorate Preview (ไทย)",
                    description=(
                        "Preview only (nothing renamed yet):\n"
                        + "\n".join(preview_lines)
                        + more
                        + "\n\nRun again with `apply:true` to rename."
                    ),
                    color=color.blue,
                ),
            )

        renamed = 0
        failed = 0
        reason = f"GuildStyle decorate by {ctx.author} ({ctx.author.id})"
        for channel_obj, target_name in plans:
            try:
                await channel_obj.edit(name=target_name, reason=reason)
                renamed += 1
            except Exception:
                failed += 1

        await self._safe_ctx_send(
            ctx,
            embed=discord.Embed(
                title="GuildStyle Decorate Completed (ไทย)",
                description=f"Renamed: **{renamed}**\nFailed: **{failed}**",
                color=color.green if failed == 0 else color.orange,
            ),
        )

    @guildstyle_decorate.autocomplete("font_style")
    async def guildstyle_decorate_font_style_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _ = interaction
        return self._font_style_autocomplete_choices(current)


