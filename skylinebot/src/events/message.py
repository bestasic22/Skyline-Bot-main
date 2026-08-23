import discord


from discord.ext import commands


import storage.afk


from skylinebot.console.logging import logger


from skylinebot.memory.cache import cache


from skylinebot.style import color


from skylinebot.utils import pings
from skylinebot.utils import i18n


from collections import defaultdict, deque
from typing import Any


import time


import re


import json
import hashlib
import html as html_lib


from skylinebot.src.checks import checks


from skylinebot.config.config import BotConfigClass


BotConfig = BotConfigClass()
PROMOTE_COOLDOWN_SECONDS = 12 * 3600
PROMOTE_ALLOWED_ATTACHMENT_DOMAINS: tuple[str, ...] = (
    "discord.com",
    "discord.gg",
    "cdn.discordapp.com",
    "media.discordapp.net",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "twitch.tv",
    "x.com",
    "twitter.com",
    "facebook.com",
    "fb.watch",
    "github.com",
    "raw.githubusercontent.com",
    "imgur.com",
    "i.imgur.com",
)
PROMOTE_ALLOWED_ATTACHMENT_EXTENSIONS: tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".jfif", ".pjp", ".pjpeg",
    ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".avif",
    ".mp4", ".webm", ".mov", ".mp3", ".wav", ".pdf",
)
PROMOTE_DEFAULT_ALLOWED_DOMAINS: tuple[str, ...] = ("skylinebot.xyz",)
PROMOTE_DEFAULT_BLOCKED_WORDS: tuple[str, ...] = (
    "ควย",
    "เหี้ย",
    "สัส",
    "fuck",
    "shit",
    "bitch",
    "พนัน",
    "บาคาร่า",
    "สล็อต",
    "คาสิโน",
    "หวยใต้ดิน",
    "ยาเสพติด",
    "ปืนเถื่อน",
    "หนังโป๊",
    "porn",
)
PROMOTE_HARD_BLOCK_WORDS: tuple[str, ...] = (
    "free nitro",
    "steam gift 100%",
    "airdrop wallet",
    "wallet connect",
    "seed phrase",
    "recovery phrase",
    "private key",
)
PROMOTE_GAMBLING_BLOCK_WORDS: tuple[str, ...] = (
    "พนัน",
    "เว็บพนัน",
    "บาคาร่า",
    "บาคาร่่า",
    "สล็อต",
    "คาสิโน",
    "เว็บตรง",
    "แทงบอล",
    "หวย",
    "bet",
    "sportsbook",
    "casino",
    "slot",
    "pgslot",
    "ufabet",
    "1xbet",
    "betflix",
)
PROMOTE_IMAGE_FLAG_CATEGORY_THRESHOLDS: dict[str, float] = {
    "sexual": 0.55,
    "sexual/minors": 0.05,
    "violence": 0.85,
    "violence/graphic": 0.45,
    "illicit": 0.68,
    "illicit/violent": 0.45,
}
PROMOTE_SAVED_LIMITS_BY_PLAN: dict[str, int] = {
    "free": 0,
    "silver": 1,
    "golden": 2,
    "diamond": 5,
    "permanent": 8,
}
PROMOTE_URL_RE = re.compile(r"((?:https?://|discord\.gg/|discord\.com/invite/)[^\s<>()]+)", re.I)
PROMOTE_OWNER_REVIEW_CHANNEL_ID = 1506097612804198511
PROMOTE_OWNER_POLICY_CONFIG_KEY = "promote_owner_policy_v1"
PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY = "promote_suspended_guilds_v1"
EXTRA_PROTECTION_CONFIG_KEY_PREFIX = "extra_protection_v1_guild_"
NSFW_GUARD_CONFIG_KEY_PREFIX = "nsfw_guard_v1_guild_"
HONEYPOT_CONFIG_KEY_PREFIX = "honeypot_v1_guild_"
EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY = "allowlist_only"
EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST = "all_except_allowlist"
EXTRA_PROTECTION_IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
    ".heic",
    ".heif",
)
EXTRA_PROTECTION_SCAM_PATTERNS: tuple[str, ...] = (
    "discord.gift/",
    "steamcommunity.com/gift",
    "grabify",
    "iplogger",
    "walletconnect",
    "wallet-connect",
    "airdrop",
    "seed phrase",
    "private key",
    "token logger",
)
EXTRA_PROTECTION_DEFAULT_VIRUS_KEYWORDS: tuple[str, ...] = (
    "token grabber",
    "token logger",
    "account stealer",
    "steal token",
    "malware",
    "ransomware",
    "keylogger",
    "backdoor",
)
EXTRA_PROTECTION_DISCORD_INVITE_RE = re.compile(
    r"(discord\.gg\/[A-Za-z0-9-]+|discord(?:app)?\.com\/invite\/[A-Za-z0-9-]+)",
    re.I,
)


import traceback, sys


import asyncio


import storage
import storage.promote_channels
import storage.promote_web_queue
import storage.bot_plan_subscriptions
import storage.ai_memories
import storage.dashboard_config


import datetime
import os
import mimetypes
import io
import aiohttp
import random
import ipaddress
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, quote, urlparse, urljoin


from skylinebot.engine.bot_runtime import AutoShardedBot
import skylinebot.src.modules.dashboard_activity as dashboard_activity

try:
    from openai import AsyncOpenAI
except Exception:
    AsyncOpenAI = None


check_for_owner_first_time_message_in_guild_cache = (
    {}
)  # guild_id: [owner_id1,owner_id2]

DEFAULT_AI_SYSTEM_PROMPT = (
    "You are SkylineBOT, a friendly Discord assistant. "
    "Persona: male assistant voice with a kind, playful, cute style when appropriate. "
    "Default identity is male; keep it consistent, but keep tone warm and natural. "
    "When replying in Thai, you may use polite particles naturally such as ครับ, คับ, ค้าบ. "
    "If user explicitly asks for playful wording (including use of 'ค่ะ'), you may adapt gently without changing your core male identity. "
    "If user asks you to be female, do not respond harshly; respond softly that you are male, then continue helping in a cute/friendly tone. "
    "Do not output mixed malformed forms like 'ครับ/ค่ะ', 'ค่ะ/ครับ', or 'ผม/ครับค่ะ'. "
    "Primary behavior: be warm, approachable, and practical. "
    "Language policy: respond in Thai or English only; never output Chinese or other languages. "
    "If the user writes Thai, reply in natural Thai. If the user writes English, reply in English. "
    "Do not translate or alter URLs, commands, code, usernames, or technical tokens. "
    "Keep Discord OAuth scope exactly as: bot applications.commands. "
    "Official SkylineBOT website exists; for website questions, provide direct links when available. "
    "You may answer both server-related and general questions. "
    "If you are unsure, say so briefly and still provide best-effort guidance. "
    "Response style should vary naturally: sometimes concise, sometimes bullets, sometimes step-by-step, based on user intent. "
    "Never provide malware, token grabber, phishing, account theft, or bypass instructions. Refuse briefly and offer safe help. "
    "Always prioritize correctness, clarity, and user benefit."
)


def _normalize_promote_plan_tier(raw_value: Any) -> str:
    normalized = str(raw_value or "free").strip().lower().replace(" ", "_")
    mapping = {
        "free": "free",
        "basic": "free",
        "silver": "silver",
        "silver_guild_preminum": "silver",
        "silver_guild_premium": "silver",
        "premium_silver": "silver",
        "gold": "golden",
        "gole": "golden",
        "golden": "golden",
        "golden_guild_premium": "golden",
        "gole_guild_premium": "golden",
        "pro": "golden",
        "diamond": "diamond",
        "diamond_guild_premium": "diamond",
        "permanent": "permanent",
        "lifetime": "permanent",
        "forever": "permanent",
        "perm": "permanent",
        "permanent_guild_premium": "permanent",
        "lifetime_guild_premium": "permanent",
        "permanent_guild_preminum": "permanent",
        "lifetime_guild_preminum": "permanent",
        "ultra": "diamond",
    }
    return mapping.get(normalized, "free")


def _promote_saved_limit_for_plan(raw_plan: Any) -> int:
    tier = _normalize_promote_plan_tier(raw_plan)
    return int(PROMOTE_SAVED_LIMITS_BY_PLAN.get(tier, 0))


def _plan_rank_local(raw_plan: Any) -> int:
    rank_table = {"free": 0, "silver": 1, "golden": 2, "diamond": 3, "permanent": 4}
    normalized = _normalize_promote_plan_tier(raw_plan)
    return int(rank_table.get(normalized, 0))


def _is_plan_at_least_local(raw_plan: Any, target_tier: str) -> bool:
    return _plan_rank_local(raw_plan) >= _plan_rank_local(target_tier)


def _coerce_utc_datetime_local(raw_value: Any) -> datetime.datetime | None:
    if not raw_value:
        return None
    if isinstance(raw_value, datetime.datetime):
        return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
    if isinstance(raw_value, (int, float)):
        try:
            ts_value = float(raw_value)
            if ts_value > 10_000_000_000:
                ts_value /= 1000.0
            return datetime.datetime.fromtimestamp(ts_value, tz=datetime.timezone.utc)
        except Exception:
            return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        if text.isdigit():
            ts_value = float(text)
            if ts_value > 10_000_000_000:
                ts_value /= 1000.0
            return datetime.datetime.fromtimestamp(ts_value, tz=datetime.timezone.utc)
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def _default_honeypot_settings_local() -> dict[str, Any]:
    return {
        "enabled": False,
        "channel_id": "",
        "timeout_seconds": 604800,
        "delete_message": True,
        "status_edit_cooldown_seconds": 120,
        "status_message_id": "",
        "deleted_message_count": 0,
        "timeout_count": 0,
        "kick_count": 0,
        "ban_count": 0,
    }


def _normalize_honeypot_settings_local(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_honeypot_settings_local()

    def _safe_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on", "enabled", "enable"}:
            return True
        if text in {"0", "false", "no", "off", "disabled", "disable"}:
            return False
        return default

    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(str(value).strip())
        except Exception:
            parsed = int(default)
        return max(minimum, min(maximum, parsed))

    def _safe_id(value: Any) -> str:
        text = str(value or "").strip()
        return text if text.isdigit() else ""

    out["enabled"] = _safe_bool(src.get("enabled"), out["enabled"])
    out["channel_id"] = _safe_id(src.get("channel_id"))
    out["timeout_seconds"] = _safe_int(src.get("timeout_seconds"), out["timeout_seconds"], 60, 2_419_200)
    out["delete_message"] = _safe_bool(src.get("delete_message"), out["delete_message"])
    out["status_edit_cooldown_seconds"] = _safe_int(
        src.get("status_edit_cooldown_seconds"),
        out["status_edit_cooldown_seconds"],
        120,
        300,
    )
    out["status_message_id"] = _safe_id(src.get("status_message_id"))
    out["deleted_message_count"] = _safe_int(src.get("deleted_message_count"), 0, 0, 1_000_000_000)
    out["timeout_count"] = _safe_int(src.get("timeout_count"), 0, 0, 1_000_000_000)
    out["kick_count"] = _safe_int(src.get("kick_count"), 0, 0, 1_000_000_000)
    out["ban_count"] = _safe_int(src.get("ban_count"), 0, 0, 1_000_000_000)
    return out


def _is_allowed_discord_invite_url_local(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    normalized = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if host in {"discord.gg", "www.discord.gg"}:
        return bool(path and path != "/")
    if host in {"discord.com", "www.discord.com"}:
        return path.startswith("/invite/")
    return False


def _is_safe_public_host_local(host: str) -> bool:
    value = str(host or "").strip().lower()
    if not value:
        return False
    if value in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        ip = ipaddress.ip_address(value)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
    except Exception:
        pass
    return True


def _promote_attachment_allowed_domains_local() -> tuple[str, ...]:
    domains: list[str] = list(PROMOTE_ALLOWED_ATTACHMENT_DOMAINS)
    configured_base = str(getattr(BotConfig, "DASHBOARD_BASE_URL", "") or "").strip()
    if configured_base:
        try:
            parsed = urlparse(configured_base if "://" in configured_base else f"https://{configured_base}")
            host = str(parsed.hostname or "").strip().lower()
            if host and host not in domains:
                domains.append(host)
        except Exception:
            pass
    return tuple(domains)


def _normalize_promote_attachment_url_local(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    normalized = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if not _is_safe_public_host_local(host):
        return ""
    path_lower = (parsed.path or "").lower()
    has_allowed_ext = any(path_lower.endswith(ext) for ext in PROMOTE_ALLOWED_ATTACHMENT_EXTENSIONS)
    is_allowed_domain = any(host == d or host.endswith(f".{d}") for d in _promote_attachment_allowed_domains_local())
    if not (has_allowed_ext or is_allowed_domain):
        return ""
    canonical_base = f"{parsed.scheme.lower()}://{(parsed.netloc or host).lower()}{parsed.path or ''}"
    if host in {"cdn.discordapp.com", "media.discordapp.net"} and path_lower.startswith("/attachments/"):
        # Keep signed params (`ex/is/hm`) for Discord CDN attachments.
        # Removing them can make the media URL invalid and show a blank embed image box.
        if parsed.query:
            return f"{canonical_base}?{parsed.query}"
        return canonical_base
    if parsed.query:
        return f"{canonical_base}?{parsed.query}"
    return canonical_base


def _promote_unique_tokens_local(items: list[str], *, limit: int = 50) -> list[str]:
    unique: list[str] = []
    for item in items:
        token = str(item or "").strip()
        if not token or token in unique:
            continue
        unique.append(token)
        if len(unique) >= max(1, int(limit)):
            break
    return unique


def _promote_split_tokens_local(raw: Any) -> list[str]:
    if isinstance(raw, (list, tuple, set)):
        return [str(item or "") for item in raw]
    return re.split(r"[\n\r,|]+", str(raw or ""))


def _normalize_promote_domain_token_local(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    if "://" in token:
        parsed = urlparse(token)
        token = (parsed.hostname or "").strip().lower()
    else:
        token = token.split("/", 1)[0].strip().lower()
    if token.startswith("www."):
        token = token[4:]
    if ":" in token:
        token = token.split(":", 1)[0].strip()
    if not token or token.endswith("."):
        return ""
    if not _is_safe_public_host_local(token):
        return ""
    if not re.fullmatch(r"[a-z0-9.-]+", token):
        return ""
    return token


def _normalize_promote_allowed_domains_local(raw: Any, *, limit: int = 30) -> list[str]:
    values: list[str] = []
    for item in _promote_split_tokens_local(raw):
        normalized = _normalize_promote_domain_token_local(item)
        if normalized:
            values.append(normalized)
    return _promote_unique_tokens_local(values, limit=limit)


def _normalize_promote_allowed_urls_local(raw: Any, *, limit: int = 30) -> list[str]:
    values: list[str] = []
    for item in _promote_split_tokens_local(raw):
        normalized = _normalize_promote_candidate_url_local(item)
        if not normalized:
            continue
        parsed = urlparse(normalized)
        path = (parsed.path or "/").rstrip("/") or "/"
        values.append(f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}")
    return _promote_unique_tokens_local(values, limit=limit)


def _normalize_promote_blocked_words_local(raw: Any, *, limit: int = 260) -> list[str]:
    words: list[str] = []
    for item in _promote_split_tokens_local(raw):
        token = str(item or "").strip().lower()
        if not token:
            continue
        if len(token) > 64:
            token = token[:64]
        words.append(token)
    return _promote_unique_tokens_local(words, limit=limit)


def _promote_merge_blocked_words_local(*sources: Any) -> list[str]:
    merged: list[str] = []
    for source in sources:
        normalized = _normalize_promote_blocked_words_local(source)
        for token in normalized:
            if token and token not in merged:
                merged.append(token)
    return merged[:260]


def _default_promote_owner_policy_local() -> dict[str, list[str]]:
    return {
        "allowed_domains": [],
        "allowed_urls": [],
        "blocked_words": [],
        "blocked_domains": [],
        "blocked_urls": [],
    }


def _promote_owner_policy_from_raw_local(raw_value: Any) -> dict[str, list[str]]:
    parsed: dict[str, Any] = {}
    if isinstance(raw_value, dict):
        parsed = raw_value
    elif isinstance(raw_value, str):
        text = str(raw_value or "").strip()
        if text:
            try:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    parsed = decoded
            except Exception:
                parsed = {}
    defaults = _default_promote_owner_policy_local()
    return {
        "allowed_domains": _normalize_promote_allowed_domains_local(parsed.get("allowed_domains", defaults["allowed_domains"])),
        "allowed_urls": _normalize_promote_allowed_urls_local(parsed.get("allowed_urls", defaults["allowed_urls"])),
        "blocked_words": _normalize_promote_blocked_words_local(parsed.get("blocked_words", defaults["blocked_words"])),
        "blocked_domains": _normalize_promote_allowed_domains_local(parsed.get("blocked_domains", defaults["blocked_domains"])),
        "blocked_urls": _normalize_promote_allowed_urls_local(parsed.get("blocked_urls", defaults["blocked_urls"])),
    }


async def _promote_owner_policy_load_local() -> dict[str, list[str]]:
    row = await storage.dashboard_config.get(config_key=PROMOTE_OWNER_POLICY_CONFIG_KEY) or {}
    raw_value = row.get("config_value") if isinstance(row, dict) else ""
    return _promote_owner_policy_from_raw_local(raw_value)


def _normalize_promote_candidate_url_local(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    normalized = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").strip().lower()
    if not host or not _is_safe_public_host_local(host):
        return ""
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    out = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    if parsed.query:
        out = f"{out}?{parsed.query}"
    return out


def _promote_allowed_targets_local(allowed_domains: Any, allowed_urls: Any) -> tuple[list[str], list[str]]:
    merged_domains = _promote_unique_tokens_local(
        [
            *[_normalize_promote_domain_token_local(item) for item in list(PROMOTE_DEFAULT_ALLOWED_DOMAINS)],
            *_normalize_promote_allowed_domains_local(allowed_domains),
        ],
        limit=60,
    )
    url_targets = _normalize_promote_allowed_urls_local(allowed_urls)
    return merged_domains, url_targets


def _promote_blocked_targets_local(blocked_domains: Any, blocked_urls: Any) -> tuple[list[str], list[str]]:
    domains = _normalize_promote_allowed_domains_local(blocked_domains)
    urls = _normalize_promote_allowed_urls_local(blocked_urls)
    return domains, urls


def _is_allowed_promote_custom_url_local(url: str, allowed_domains: Any, allowed_urls: Any) -> bool:
    normalized = _normalize_promote_candidate_url_local(url)
    if not normalized:
        return False
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    domain_targets, url_targets = _promote_allowed_targets_local(allowed_domains, allowed_urls)
    for domain in domain_targets:
        if host == domain or host.endswith(f".{domain}"):
            return True
    normalized_base = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{(parsed.path or '/').rstrip('/') or '/'}"
    for prefix in url_targets:
        trimmed = prefix.rstrip("/")
        if normalized_base == prefix or normalized_base == trimmed:
            return True
        if normalized_base.startswith(f"{trimmed}/"):
            return True
    return False


def _is_blocked_promote_custom_url_local(url: str, blocked_domains: Any, blocked_urls: Any) -> bool:
    normalized = _normalize_promote_candidate_url_local(url)
    if not normalized:
        return False
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    domain_targets, url_targets = _promote_blocked_targets_local(blocked_domains, blocked_urls)
    for domain in domain_targets:
        if host == domain or host.endswith(f".{domain}"):
            return True
    normalized_base = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{(parsed.path or '/').rstrip('/') or '/'}"
    for prefix in url_targets:
        trimmed = prefix.rstrip("/")
        if normalized_base == prefix or normalized_base == trimmed:
            return True
        if normalized_base.startswith(f"{trimmed}/"):
            return True
    return False


def _promote_allowed_hint_local(allowed_domains: Any, allowed_urls: Any) -> str:
    domain_targets, url_targets = _promote_allowed_targets_local(allowed_domains, allowed_urls)
    domains_text = ", ".join(domain_targets[:10]) if domain_targets else "-"
    if url_targets:
        urls_text = ", ".join(url_targets[:6])
        return f"Allowed domains: {domains_text} | Allowed URL prefixes: {urls_text}"
    return f"Allowed domains: {domains_text}"


def _promote_blocked_hint_local(blocked_domains: Any, blocked_urls: Any) -> str:
    domain_targets, url_targets = _promote_blocked_targets_local(blocked_domains, blocked_urls)
    domains_text = ", ".join(domain_targets[:10]) if domain_targets else "-"
    if url_targets:
        urls_text = ", ".join(url_targets[:6])
        return f"Blocked domains: {domains_text} | Blocked URL prefixes: {urls_text}"
    return f"Blocked domains: {domains_text}"


def _promote_extract_urls(text: str) -> list[str]:
    content = str(text or "")
    urls: list[str] = []
    for match in PROMOTE_URL_RE.finditer(content):
        raw = str(match.group(1) or "").strip()
        if not raw:
            continue
        cleaned = raw.rstrip(".,!?)]}>")
        urls.append(cleaned)
    deduped: list[str] = []
    for item in urls:
        if item not in deduped:
            deduped.append(item)
    return deduped[:8]


def _promote_find_blocked_urls_local(
    urls: list[str],
    *,
    blocked_domains: Any,
    blocked_urls: Any,
) -> list[str]:
    blocked_hits: list[str] = []
    for raw_url in urls:
        candidate = str(raw_url or "").strip()
        if not candidate:
            continue
        if _is_blocked_promote_custom_url_local(candidate, blocked_domains, blocked_urls):
            blocked_hits.append(candidate)
    deduped: list[str] = []
    for item in blocked_hits:
        if item in deduped:
            continue
        deduped.append(item)
    return deduped[:8]


def _validate_promote_content_local(content: str, blocked_words: list[str]) -> tuple[bool, str]:
    lowered = str(content or "").strip().lower()
    if not lowered:
        return True, ""
    compacted = re.sub(r"[^a-z0-9\u0E00-\u0E7F]+", "", lowered)
    for word in blocked_words:
        token = str(word or "").strip().lower()
        if not token:
            continue
        if token in lowered:
            return False, f"blocked word: {token}"
        compact_token = re.sub(r"[^a-z0-9\u0E00-\u0E7F]+", "", token)
        if compact_token and len(compact_token) >= 3 and compact_token in compacted:
            return False, f"blocked word: {token}"
    for hard in PROMOTE_HARD_BLOCK_WORDS:
        token = str(hard or "").strip().lower()
        if not token:
            continue
        if token in lowered:
            return False, f"blocked phrase: {token}"
        compact_token = re.sub(r"[^a-z0-9\u0E00-\u0E7F]+", "", token)
        if compact_token and len(compact_token) >= 4 and compact_token in compacted:
            return False, f"blocked phrase: {token}"
    return True, ""


def _promote_suspension_map_from_raw_local(raw_value: Any) -> dict[str, dict[str, str]]:
    parsed: dict[str, Any] = {}
    if isinstance(raw_value, dict):
        parsed = raw_value
    elif isinstance(raw_value, str):
        text = str(raw_value or "").strip()
        if text:
            try:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    parsed = decoded
            except Exception:
                parsed = {}
    out: dict[str, dict[str, str]] = {}
    for key, value in parsed.items():
        try:
            guild_id = int(str(key or "").strip())
        except Exception:
            guild_id = 0
        if guild_id <= 0:
            continue
        row = value if isinstance(value, dict) else {}
        out[str(guild_id)] = {
            "note": str(row.get("note") or "").strip()[:600],
            "by_name": str(row.get("by_name") or "").strip()[:120],
            "updated_at": str(row.get("updated_at") or "").strip()[:64],
        }
    return out


async def _promote_suspension_map_load_local() -> dict[str, dict[str, str]]:
    row = await storage.dashboard_config.get(config_key=PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY) or {}
    raw_value = row.get("config_value") if isinstance(row, dict) else ""
    return _promote_suspension_map_from_raw_local(raw_value)


async def _promote_suspension_map_save_local(payload: dict[str, dict[str, str]]) -> None:
    safe_payload = _promote_suspension_map_from_raw_local(payload)
    encoded = json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"))
    existing = await storage.dashboard_config.get(config_key=PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY)
    if existing:
        await storage.dashboard_config.update(id=existing.get("id"), config_value=encoded)
    else:
        await storage.dashboard_config.insert(
            config_key=PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY,
            config_value=encoded,
        )


def _promote_suspension_reason_local(guild_id: int, suspension_map: dict[str, dict[str, str]]) -> str:
    row = suspension_map.get(str(int(guild_id or 0))) if isinstance(suspension_map, dict) else None
    if not isinstance(row, dict):
        return ""
    note = str(row.get("note") or "").strip()
    by_name = str(row.get("by_name") or "").strip()
    if note and by_name:
        return f"กิลด์นี้ถูกระงับการโปรโมทโดย {by_name}: {note}"
    if note:
        return f"กิลด์นี้ถูกระงับการโปรโมท: {note}"
    if by_name:
        return f"กิลด์นี้ถูกระงับการโปรโมทโดย {by_name}"
    return "กิลด์นี้ถูกระงับการโปรโมทโดย OwnerBOT"


def _default_extra_protection_settings_local() -> dict[str, Any]:
    return {
        "enabled": False,
        "block_bot_add_enabled": True,
        "block_bot_add_armed_at_ts": 0,
        "bot_add_whitelist_user_ids": [],
        "bot_add_whitelist_bot_ids": [],
        "anti_spam_enabled": True,
        "spam_message_limit": 7,
        "spam_window_seconds": 12,
        "anti_mass_mention_enabled": True,
        "mass_mention_limit": 5,
        "delete_discord_invite_enabled": False,
        "delete_scam_links_enabled": True,
        "anti_virus_keywords_enabled": True,
        "custom_virus_keywords": [],
        "detect_nsfw_image_enabled": False,
        "detect_nsfw_image_mode": EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
        "detect_nsfw_image_threshold": 0.72,
        "delete_action": "warn",
        "timeout_seconds": 300,
    }


def _normalize_extra_protection_settings_local(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_extra_protection_settings_local()

    def _to_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on", "enabled", "enable"}:
            return True
        if text in {"0", "false", "no", "off", "disabled", "disable"}:
            return False
        return bool(default)

    def _to_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            number = int(str(value).strip())
        except Exception:
            number = int(default)
        return max(minimum, min(maximum, number))

    def _to_float(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            number = float(str(value).strip())
        except Exception:
            number = float(default)
        if number < minimum:
            return float(minimum)
        if number > maximum:
            return float(maximum)
        return float(number)

    def _to_unix_ts(value: Any) -> int:
        if isinstance(value, datetime.datetime):
            parsed = value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
            return max(0, int(parsed.timestamp()))
        try:
            number = int(float(str(value).strip()))
        except Exception:
            return 0
        return max(0, number)

    def _to_id_list(raw_value: Any, *, limit: int = 120) -> list[str]:
        if isinstance(raw_value, (list, tuple, set)):
            candidates = [str(item or "").strip() for item in raw_value]
        else:
            text = str(raw_value or "").strip()
            if not text:
                candidates = []
            else:
                try:
                    decoded = json.loads(text)
                except Exception:
                    decoded = None
                if isinstance(decoded, list):
                    candidates = [str(item or "").strip() for item in decoded]
                else:
                    candidates = [item.strip() for item in re.split(r"[\s,\n\r]+", text)]
        values: list[str] = []
        for item in candidates:
            if item.isdigit() and item not in values:
                values.append(item)
            if len(values) >= limit:
                break
        return values

    def _to_keywords(raw_value: Any, *, limit: int = 50) -> list[str]:
        if isinstance(raw_value, (list, tuple, set)):
            candidates = [str(item or "").strip().lower() for item in raw_value]
        else:
            text = str(raw_value or "").strip()
            if not text:
                candidates = []
            else:
                candidates = [item.strip().lower() for item in re.split(r"[\n\r,]+", text)]
        values: list[str] = []
        for item in candidates:
            if not item or item in values:
                continue
            values.append(item[:80])
            if len(values) >= limit:
                break
        return values

    out["enabled"] = _to_bool(src.get("enabled"), out["enabled"])
    out["block_bot_add_enabled"] = _to_bool(src.get("block_bot_add_enabled"), out["block_bot_add_enabled"])
    out["block_bot_add_armed_at_ts"] = _to_unix_ts(src.get("block_bot_add_armed_at_ts"))
    out["bot_add_whitelist_user_ids"] = _to_id_list(src.get("bot_add_whitelist_user_ids"))
    out["bot_add_whitelist_bot_ids"] = _to_id_list(src.get("bot_add_whitelist_bot_ids"))
    out["anti_spam_enabled"] = _to_bool(src.get("anti_spam_enabled"), out["anti_spam_enabled"])
    out["spam_message_limit"] = _to_int(src.get("spam_message_limit"), out["spam_message_limit"], 3, 30)
    out["spam_window_seconds"] = _to_int(src.get("spam_window_seconds"), out["spam_window_seconds"], 3, 180)
    out["anti_mass_mention_enabled"] = _to_bool(src.get("anti_mass_mention_enabled"), out["anti_mass_mention_enabled"])
    out["mass_mention_limit"] = _to_int(src.get("mass_mention_limit"), out["mass_mention_limit"], 2, 30)
    out["delete_discord_invite_enabled"] = _to_bool(
        src.get("delete_discord_invite_enabled"), out["delete_discord_invite_enabled"]
    )
    out["delete_scam_links_enabled"] = _to_bool(src.get("delete_scam_links_enabled"), out["delete_scam_links_enabled"])
    out["anti_virus_keywords_enabled"] = _to_bool(
        src.get("anti_virus_keywords_enabled"), out["anti_virus_keywords_enabled"]
    )
    out["custom_virus_keywords"] = _to_keywords(src.get("custom_virus_keywords"))
    out["detect_nsfw_image_enabled"] = _to_bool(
        src.get("detect_nsfw_image_enabled"),
        out["detect_nsfw_image_enabled"],
    )
    nsfw_mode = str(
        src.get("detect_nsfw_image_mode")
        or out["detect_nsfw_image_mode"]
    ).strip().lower()
    if nsfw_mode not in {
        EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
        EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST,
    }:
        nsfw_mode = out["detect_nsfw_image_mode"]
    out["detect_nsfw_image_mode"] = nsfw_mode
    out["detect_nsfw_image_threshold"] = _to_float(
        src.get("detect_nsfw_image_threshold"),
        float(out["detect_nsfw_image_threshold"]),
        0.05,
        0.995,
    )
    action = str(src.get("delete_action") or out["delete_action"]).strip().lower()
    if action not in {"none", "warn", "mute", "kick", "ban"}:
        action = out["delete_action"]
    out["delete_action"] = action
    out["timeout_seconds"] = _to_int(src.get("timeout_seconds"), out["timeout_seconds"], 30, 86400)
    return out


def _default_nsfw_guard_settings_local() -> dict[str, Any]:
    return {
        "enabled": False,
        "allowed_channel_ids": [],
        "allowed_role_ids": [],
        "log_channel_id": "",
        "block_dm": True,
        "require_discord_nsfw_channel": True,
        "strict_mode": False,
    }


def _normalize_nsfw_guard_settings_local(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_nsfw_guard_settings_local()

    def _to_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on", "enable", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disable", "disabled"}:
            return False
        return bool(default)

    def _to_id_list(raw_value: Any, *, limit: int = 120) -> list[str]:
        if isinstance(raw_value, (list, tuple, set)):
            candidates = [str(item or "").strip() for item in raw_value]
        else:
            text = str(raw_value or "").strip()
            if not text:
                candidates = []
            else:
                try:
                    decoded = json.loads(text)
                except Exception:
                    decoded = None
                if isinstance(decoded, list):
                    candidates = [str(item or "").strip() for item in decoded]
                else:
                    candidates = [item.strip() for item in re.split(r"[\s,\n\r]+", text)]
        values: list[str] = []
        for item in candidates:
            if item.isdigit() and item not in values:
                values.append(item)
            if len(values) >= limit:
                break
        return values

    out["enabled"] = _to_bool(src.get("enabled"), out["enabled"])
    out["allowed_channel_ids"] = _to_id_list(src.get("allowed_channel_ids"))
    out["allowed_role_ids"] = _to_id_list(src.get("allowed_role_ids"))
    log_channel_id = str(src.get("log_channel_id") or "").strip()
    out["log_channel_id"] = log_channel_id if log_channel_id.isdigit() else ""
    out["block_dm"] = _to_bool(src.get("block_dm"), out["block_dm"])
    out["require_discord_nsfw_channel"] = _to_bool(
        src.get("require_discord_nsfw_channel"),
        out["require_discord_nsfw_channel"],
    )
    out["strict_mode"] = _to_bool(src.get("strict_mode"), out["strict_mode"])
    return out

class message(commands.Cog):
    MUSIC_SETUP_SELF_BOT_DELETE_DELAY_SECONDS = 15
    MUSIC_SETUP_OTHER_BOT_DELETE_DELAY_SECONDS = 10

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        self.user_messages = defaultdict(lambda: defaultdict(int))

        self.user_last_message_time = defaultdict(lambda: time.time())

        self.user_message_counts = defaultdict(int)

        self.user_message_timestamps = defaultdict(float)

        self.MusicCog = self.bot.get_cog("Music")
        self.promote_queue = asyncio.Queue()
        self.promote_pending_keys: set[str] = set()
        self.promote_worker_task = asyncio.create_task(self.promote_queue_worker())
        self.promote_web_queue_worker_task = asyncio.create_task(self.promote_web_queue_worker())
        self.ai_chat_usage = defaultdict(lambda: defaultdict(list))
        self.ai_thinking_messages = [
            "กำลังคิดคำตอบให้อยู่ครับ..."
        ]
        self.ai_config_warned_guilds = set()
        self.ai_quota_block_until = defaultdict(float)
        self.ai_quota_notice_until = defaultdict(float)
        self.ai_notice_cooldowns = defaultdict(float)
        self.ai_log_cooldowns = defaultdict(float)
        self.ai_provider_retry_cooldowns = defaultdict(float)
        self.ai_provider = str(os.getenv("AI_PROVIDER", "opentyphoon")).strip().lower()
        if self.ai_provider not in {
            "openai",
            "ollama",
            "google",
            "opentyphoon",
            "chindax",
            "aiforthai",
            "cloudflare",
            "thaillm",
        }:
            self.ai_provider = "opentyphoon"
        self.openai_api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        self.openai_model = str(os.getenv("OPENAI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        self.ollama_model = str(os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b-instruct")).strip() or "qwen2.5:0.5b-instruct"
        self.ollama_api_key = str(os.getenv("OLLAMA_API_KEY", "")).strip()
        self.google_model = str(os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")).strip() or "gemini-2.0-flash"
        self.opentyphoon_api_key = str(os.getenv("OPENTYPHOON_API_KEY", "")).strip()
        self.opentyphoon_model = (
            str(os.getenv("OPENTYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct")).strip()
            or "typhoon-v2.5-30b-a3b-instruct"
        )
        self.chindax_api_key = str(os.getenv("CHINDAX_API_KEY", "")).strip()
        self.chindax_model = (
            str(os.getenv("CHINDAX_MODEL", "accounts/fireworks/models/gpt-oss-20b")).strip()
            or "accounts/fireworks/models/gpt-oss-20b"
        )
        self.aiforthai_api_key = str(os.getenv("AIFORTHAI_API_KEY", "")).strip()
        self.aiforthai_model = str(os.getenv("AIFORTHAI_MODEL", "aiforthai-chat")).strip() or "aiforthai-chat"
        self.cloudflare_account_id = str(os.getenv("CLOUDFLARE_ACCOUNT_ID", "")).strip()
        self.cloudflare_api_key = str(
            os.getenv("CLOUDFLARE_API_TOKEN", "") or os.getenv("CLOUDFLARE_API_KEY", "")
        ).strip()
        self.cloudflare_model = (
            str(os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.1-8b-instruct")).strip()
            or "@cf/meta/llama-3.1-8b-instruct"
        )
        self.thaillm_api_key = str(os.getenv("THAILLM_API_KEY", "")).strip()
        self.thaillm_model = (
            str(os.getenv("THAILLM_MODEL", "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2")).strip()
            or "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2"
        )
        self.ai_model = self.openai_model
        if self.ai_provider == "ollama":
            self.ai_model = self.ollama_model
        elif self.ai_provider == "google":
            self.ai_model = self.google_model
        elif self.ai_provider == "opentyphoon":
            self.ai_model = self.opentyphoon_model
        elif self.ai_provider == "chindax":
            self.ai_model = self.chindax_model
        elif self.ai_provider == "aiforthai":
            self.ai_model = self.aiforthai_model
        elif self.ai_provider == "cloudflare":
            self.ai_model = self.cloudflare_model
        elif self.ai_provider == "thaillm":
            self.ai_model = self.thaillm_model
        self.ollama_base_url = str(
            os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ).strip().rstrip("/")
        self.google_base_url = str(
            os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        ).strip().rstrip("/")
        self.opentyphoon_base_url = str(
            os.getenv("OPENTYPHOON_BASE_URL", "https://api.opentyphoon.ai/v1")
        ).strip().rstrip("/")
        self.chindax_base_url = str(
            os.getenv("CHINDAX_BASE_URL", "https://chindax.iapp.co.th/api")
        ).strip().rstrip("/")
        self.chindax_alt_base_url = str(
            os.getenv("CHINDAX_ALT_BASE_URL", "https://chindax.iapp.co.th")
        ).strip().rstrip("/")
        self.chindax_chat_completions_path = str(
            os.getenv("CHINDAX_CHAT_COMPLETIONS_PATH", "/chat/completions")
        ).strip() or "/chat/completions"
        self.chindax_endpoint_candidates_raw = str(
            os.getenv(
                "CHINDAX_ENDPOINT_CANDIDATES",
                "/chat/completions,/api/chat/completions,/v1/chat/completions",
            )
        ).strip()
        self.chindax_auth_header = str(
            os.getenv("CHINDAX_AUTH_HEADER", "Authorization")
        ).strip() or "Authorization"
        self.chindax_auth_scheme = str(
            os.getenv("CHINDAX_AUTH_SCHEME", "Bearer")
        ).strip()
        self.chindax_model_candidates_raw = str(
            os.getenv(
                "CHINDAX_MODEL_CANDIDATES",
                "accounts/fireworks/models/gpt-oss-20b,accounts/fireworks/models/gpt-oss-120b,Qwen/Qwen3-14B",
            )
        ).strip()
        self.chindax_force_provider_fallback = str(
            os.getenv("CHINDAX_FORCE_PROVIDER_FALLBACK", "1") or "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.aiforthai_base_url = str(
            os.getenv("AIFORTHAI_BASE_URL", "https://api.aiforthai.in.th")
        ).strip().rstrip("/")
        self.aiforthai_alt_base_url = str(
            os.getenv("AIFORTHAI_ALT_BASE_URL", "https://aiforthai.in.th/api/v1/provider")
        ).strip().rstrip("/")
        self.aiforthai_chat_completions_path = str(
            os.getenv("AIFORTHAI_CHAT_COMPLETIONS_PATH", "/chat/completions")
        ).strip() or "/chat/completions"
        self.aiforthai_endpoint_candidates_raw = str(
            os.getenv(
                "AIFORTHAI_ENDPOINT_CANDIDATES",
                "/chat/completions,/v1/chat/completions,/api/v1/chat/completions,/api/v1/provider/chat/completions",
            )
        ).strip()
        self.aiforthai_api_key_header = str(
            os.getenv("AIFORTHAI_API_KEY_HEADER", "Apikey")
        ).strip() or "Apikey"
        self.aiforthai_use_bearer_auth = str(
            os.getenv("AIFORTHAI_USE_BEARER_AUTH", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.aiforthai_force_provider_fallback = str(
            os.getenv("AIFORTHAI_FORCE_PROVIDER_FALLBACK", "1") or "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.cloudflare_base_url = str(os.getenv("CLOUDFLARE_BASE_URL", "")).strip().rstrip("/")
        if not self.cloudflare_base_url and self.cloudflare_account_id:
            self.cloudflare_base_url = (
                f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/v1"
            )
        self.cloudflare_chat_completions_path = str(
            os.getenv("CLOUDFLARE_CHAT_COMPLETIONS_PATH", "/chat/completions")
        ).strip() or "/chat/completions"
        self.cloudflare_endpoint_candidates_raw = str(
            os.getenv("CLOUDFLARE_ENDPOINT_CANDIDATES", "/chat/completions,/v1/chat/completions")
        ).strip()
        self.cloudflare_auth_header = str(
            os.getenv("CLOUDFLARE_AUTH_HEADER", "Authorization")
        ).strip() or "Authorization"
        self.cloudflare_auth_scheme = str(
            os.getenv("CLOUDFLARE_AUTH_SCHEME", "Bearer")
        ).strip() or "Bearer"
        self.cloudflare_model_candidates_raw = str(
            os.getenv(
                "CLOUDFLARE_MODEL_CANDIDATES",
                "@cf/meta/llama-3.1-8b-instruct,@cf/meta/llama-3.1-8b-instruct-fast,@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
            )
        ).strip()
        self.cloudflare_force_provider_fallback = str(
            os.getenv("CLOUDFLARE_FORCE_PROVIDER_FALLBACK", "1") or "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.thaillm_base_url = str(
            os.getenv("THAILLM_BASE_URL", "http://thaillm.or.th/api")
        ).strip().rstrip("/")
        self.thaillm_alt_base_url = str(
            os.getenv("THAILLM_ALT_BASE_URL", "https://openthaigpt.aieat.or.th")
        ).strip().rstrip("/")
        self.thaillm_chat_completions_path = str(
            os.getenv("THAILLM_CHAT_COMPLETIONS_PATH", "/v1/chat/completions")
        ).strip() or "/v1/chat/completions"
        self.thaillm_endpoint_candidates_raw = str(
            os.getenv(
                "THAILLM_ENDPOINT_CANDIDATES",
                "/v1/chat/completions,/chat/completions,/api/v1/chat/completions,/api/chat/completions,/{model_key}/v1/chat/completions",
            )
        ).strip()
        self.thaillm_auth_header = str(
            os.getenv("THAILLM_AUTH_HEADER", "Authorization")
        ).strip() or "Authorization"
        self.thaillm_auth_scheme = str(
            os.getenv("THAILLM_AUTH_SCHEME", "Bearer")
        ).strip() or "Bearer"
        self.thaillm_consumer_id = str(
            os.getenv("THAILLM_CONSUMER_ID", "")
        ).strip()
        self.thaillm_consumer_id_header = str(
            os.getenv("THAILLM_CONSUMER_ID_HEADER", "x-consumer-id")
        ).strip() or "x-consumer-id"
        self.thaillm_model_candidates_raw = str(
            os.getenv(
                "THAILLM_MODEL_CANDIDATES",
                "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2,Pathumma-ThaiLLM-qwen3-8b-think-3.0.0,Typhoon-S-ThaiLLM-8B-Instruct,THaLLE-0.2-ThaiLLM-8B-fa",
            )
        ).strip()
        self.thaillm_force_provider_fallback = str(
            os.getenv("THAILLM_FORCE_PROVIDER_FALLBACK", "1") or "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.google_api_key = str(
            os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        ).strip()
        self.ai_base_system_prompt = str(
            os.getenv("AI_CHAT_SYSTEM_PROMPT", DEFAULT_AI_SYSTEM_PROMPT)
        ).strip()
        self.ai_client = None
        self.ollama_model_catalog_cache: list[str] = []
        self.ollama_model_catalog_cache_expires_at: float = 0.0
        self.ollama_model_catalog_ttl_seconds: float = 600.0
        self.ai_command_reference_cache = ""
        self.ai_command_reference_updated_at = 0.0
        self.ai_command_reference_ttl = 600.0
        self.ai_command_records_cache: list[dict[str, str]] = []
        self.ai_command_records_updated_at = 0.0
        self.ai_site_knowledge_records: list[dict[str, str]] = []
        self.ai_site_knowledge_updated_at: float = 0.0
        self.ai_site_knowledge_refresh_lock = asyncio.Lock()
        self.ai_site_knowledge_refresh_task: asyncio.Task[Any] | None = None
        self.ai_site_base_url = str(
            os.getenv("AI_SITE_KNOWLEDGE_BASE_URL", "https://skylinebot.xyz")
        ).strip().rstrip("/")
        self.ai_site_knowledge_ttl_seconds = max(
            600.0, float(os.getenv("AI_SITE_KNOWLEDGE_TTL_SECONDS", "21600") or 21600)
        )
        self.ai_site_knowledge_max_pages = max(
            20, int(os.getenv("AI_SITE_KNOWLEDGE_MAX_PAGES", "200") or 200)
        )
        self.ai_site_knowledge_max_chars = max(
            12000, int(os.getenv("AI_SITE_KNOWLEDGE_MAX_CHARS", "90000") or 90000)
        )
        self.ai_response_embed_enabled = str(
            os.getenv("AI_RESPONSE_ENABLE_EMBED", "1") or "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.ai_response_reaction_enabled = str(
            os.getenv("AI_RESPONSE_ENABLE_REACTIONS", "1") or "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.ai_response_embed_default_color = str(
            os.getenv("AI_RESPONSE_EMBED_DEFAULT_COLOR", "#6b8cff") or "#6b8cff"
        ).strip()
        self.ai_response_default_reactions_raw = str(
            os.getenv("AI_RESPONSE_DEFAULT_REACTIONS", "✅") or "✅"
        ).strip()
        try:
            self.ai_max_reply_chars = max(
                1200, min(12000, int(os.getenv("AI_MAX_REPLY_CHARS", "5600") or 5600))
            )
        except Exception:
            self.ai_max_reply_chars = 5600
        self.ai_force_full_context = str(
            os.getenv("AI_FORCE_FULL_CONTEXT", "0") or "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        try:
            self.ai_full_context_command_limit = max(
                80, min(1000, int(os.getenv("AI_FULL_CONTEXT_COMMAND_LIMIT", "420") or 420))
            )
        except Exception:
            self.ai_full_context_command_limit = 420
        try:
            self.ai_full_context_site_limit = max(
                6, min(80, int(os.getenv("AI_FULL_CONTEXT_SITE_LIMIT", "24") or 24))
            )
        except Exception:
            self.ai_full_context_site_limit = 24
        try:
            self.ai_history_context_turns = max(
                4, min(18, int(os.getenv("AI_HISTORY_CONTEXT_TURNS", "8") or 8))
            )
        except Exception:
            self.ai_history_context_turns = 8
        self.ai_history_by_channel = defaultdict(lambda: deque(maxlen=18))
        self.ai_fallback_providers = self._resolve_ai_fallback_providers()
        self.ai_generation_locks = defaultdict(asyncio.Lock)
        self.ai_request_semaphore = asyncio.Semaphore(
            max(1, int(os.getenv("AI_MAX_CONCURRENT_REQUESTS", "1") or 1))
        )
        self.ai_channel_last_reply_at = defaultdict(float)
        try:
            self.ai_channel_min_reply_interval_seconds = max(
                0.0, float(os.getenv("AI_MIN_REPLY_INTERVAL_SECONDS", "3.0") or 3.0)
            )
        except Exception:
            self.ai_channel_min_reply_interval_seconds = 3.0
        self.ai_music_intercept_enabled = str(
            os.getenv("AI_MUSIC_INTERCEPT_ENABLED", "0") or "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.ai_quick_reply_enabled = str(
            os.getenv("AI_QUICK_REPLY_ENABLED", "0") or "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.ai_skip_ollama_when_music_active = str(
            os.getenv("AI_SKIP_OLLAMA_WHEN_MUSIC_ACTIVE", "1") or "1"
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.ai_request_timeout_seconds = max(
            20, int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "50") or 50)
        )
        self.extra_protection_settings_cache: dict[str, dict[str, Any]] = {}
        self.extra_protection_settings_expire: dict[str, float] = {}
        self.extra_protection_cache_ttl_seconds: float = 20.0
        self.extra_protection_spam_buckets: dict[str, deque[float]] = defaultdict(deque)
        self.extra_protection_action_cooldown: dict[str, float] = {}
        self.nsfw_guard_settings_cache: dict[str, dict[str, Any]] = {}
        self.nsfw_guard_settings_expire: dict[str, float] = {}
        self.nsfw_guard_cache_ttl_seconds: float = 20.0
        self.nsfw_image_moderation_provider = str(
            os.getenv("NSFW_IMAGE_MODERATION_PROVIDER", "aiforthai")
        ).strip().lower() or "aiforthai"
        if self.nsfw_image_moderation_provider not in {"openai", "aiforthai"}:
            self.nsfw_image_moderation_provider = "aiforthai"
        self.nsfw_image_moderation_model = str(
            os.getenv("NSFW_IMAGE_MODERATION_MODEL", "omni-moderation-latest")
        ).strip() or "omni-moderation-latest"
        self.nsfw_aiforthai_violent_endpoint = str(
            os.getenv(
                "AIFORTHAI_IMAGE_MODERATION_ENDPOINT",
                os.getenv("AIFORTHAI_VIOLENT_ENDPOINT", os.getenv("AIFORTHAI_NSFW_ENDPOINT", "https://api.aiforthai.in.th/violent")),
            )
        ).strip()
        self.nsfw_aiforthai_violent_fallback_endpoint = str(
            os.getenv("AIFORTHAI_IMAGE_MODERATION_FALLBACK_ENDPOINT", "https://api.aiforthai.in.th/nsfw")
        ).strip()
        self.nsfw_aiforthai_api_key_header = str(
            os.getenv("AIFORTHAI_API_KEY_HEADER", str(self.aiforthai_api_key_header or "Apikey"))
        ).strip() or "Apikey"
        self.nsfw_aiforthai_use_bearer_auth = str(
            os.getenv("AIFORTHAI_USE_BEARER_AUTH", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        try:
            self.nsfw_aiforthai_violent_threshold = max(
                0.05,
                min(0.995, float(os.getenv("AIFORTHAI_VIOLENT_THRESHOLD", "0.72") or 0.72)),
            )
        except Exception:
            self.nsfw_aiforthai_violent_threshold = 0.72
        self.promote_image_ocr_supplement_enabled = str(
            os.getenv("PROMOTE_IMAGE_OCR_SUPPLEMENT_ENABLED", "1")
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.promote_image_ocr_space_url = str(
            os.getenv("OCR_SPACE_API_URL", "https://api.ocr.space/parse/image")
        ).strip()
        self.promote_image_ocr_space_key = str(
            os.getenv("OCR_SPACE_API_KEY", "helloworld")
        ).strip() or "helloworld"
        self.promote_image_ocr_space_lang = str(
            os.getenv("OCR_SPACE_LANG", "auto")
        ).strip().lower() or "auto"
        self.promote_image_moderation_fail_open = str(
            os.getenv("PROMOTE_IMAGE_MODERATION_FAIL_OPEN", "0")
        ).strip().lower() not in {"0", "false", "off", "no"}
        self.promote_local_skin_guard_enabled = str(
            os.getenv("PROMOTE_LOCAL_SKIN_GUARD_ENABLED", "1")
        ).strip().lower() not in {"0", "false", "off", "no"}
        try:
            self.promote_local_skin_ratio_threshold = max(
                0.20,
                min(0.80, float(os.getenv("PROMOTE_LOCAL_SKIN_RATIO_THRESHOLD", "0.38") or 0.38)),
            )
        except Exception:
            self.promote_local_skin_ratio_threshold = 0.38
        try:
            self.promote_local_center_skin_ratio_threshold = max(
                0.20,
                min(0.90, float(os.getenv("PROMOTE_LOCAL_CENTER_SKIN_RATIO_THRESHOLD", "0.44") or 0.44)),
            )
        except Exception:
            self.promote_local_center_skin_ratio_threshold = 0.44
        try:
            self.promote_local_extreme_skin_ratio_threshold = max(
                0.25,
                min(0.95, float(os.getenv("PROMOTE_LOCAL_EXTREME_SKIN_RATIO_THRESHOLD", "0.52") or 0.52)),
            )
        except Exception:
            self.promote_local_extreme_skin_ratio_threshold = 0.52
        try:
            self.nsfw_image_moderation_timeout_seconds = max(
                5,
                int(os.getenv("NSFW_IMAGE_MODERATION_TIMEOUT_SECONDS", "18") or 18),
            )
        except Exception:
            self.nsfw_image_moderation_timeout_seconds = 18
        try:
            self.nsfw_image_moderation_cache_ttl_seconds = max(
                60.0,
                float(os.getenv("NSFW_IMAGE_MODERATION_CACHE_TTL_SECONDS", "21600") or 21600),
            )
        except Exception:
            self.nsfw_image_moderation_cache_ttl_seconds = 21600.0
        self.nsfw_image_moderation_cache: dict[str, dict[str, Any]] = {}
        self.nsfw_image_moderation_error_notice_until: dict[int, float] = defaultdict(float)
        self.promote_image_moderation_backoff_until: dict[str, float] = {}
        self.promote_image_moderation_notice_until: dict[str, float] = defaultdict(float)
        self.honeypot_settings_cache: dict[str, dict[str, Any]] = {}
        self.honeypot_settings_expire: dict[str, float] = {}
        self.honeypot_cache_ttl_seconds: float = 12.0
        self.honeypot_config_locks: dict[str, asyncio.Lock] = {}
        self.honeypot_action_cooldown: dict[str, float] = {}
        self.honeypot_embed_last_edit_at: dict[int, float] = {}
        self.honeypot_embed_pending_rows: dict[int, dict[str, Any]] = {}
        self.honeypot_embed_pending_tasks: dict[int, asyncio.Task[Any]] = {}

        if self.ai_provider == "openai" and AsyncOpenAI and self.openai_api_key:
            self.ai_client = AsyncOpenAI(api_key=self.openai_api_key)

        self._kickoff_ai_site_knowledge_refresh()

    def cog_unload(self):
        try:
            if self.promote_worker_task and not self.promote_worker_task.done():
                self.promote_worker_task.cancel()
        except Exception:
            pass
        try:
            if self.promote_web_queue_worker_task and not self.promote_web_queue_worker_task.done():
                self.promote_web_queue_worker_task.cancel()
        except Exception:
            pass
        try:
            if self.ai_site_knowledge_refresh_task and not self.ai_site_knowledge_refresh_task.done():
                self.ai_site_knowledge_refresh_task.cancel()
        except Exception:
            pass
        try:
            for task in list(self.honeypot_embed_pending_tasks.values()):
                if task and not task.done():
                    task.cancel()
            self.honeypot_embed_pending_tasks.clear()
            self.honeypot_embed_pending_rows.clear()
        except Exception:
            pass

    @staticmethod
    def _extra_protection_config_key(guild_id: int) -> str:
        return f"{EXTRA_PROTECTION_CONFIG_KEY_PREFIX}{int(guild_id)}"

    @staticmethod
    def _nsfw_guard_config_key(guild_id: int) -> str:
        return f"{NSFW_GUARD_CONFIG_KEY_PREFIX}{int(guild_id)}"

    async def _get_extra_protection_settings(self, guild_id: int) -> dict[str, Any]:
        cache_key = str(guild_id)
        now_ts = time.time()
        cached = self.extra_protection_settings_cache.get(cache_key)
        expire_at = float(self.extra_protection_settings_expire.get(cache_key, 0.0) or 0.0)
        if cached is not None and now_ts < expire_at:
            return cached

        settings = _default_extra_protection_settings_local()
        try:
            row = await storage.dashboard_config.get(
                config_key=self._extra_protection_config_key(guild_id)
            )
            if row and isinstance(row, dict):
                raw_value = str(row.get("config_value") or "").strip()
                if raw_value:
                    decoded = json.loads(raw_value)
                    if isinstance(decoded, dict):
                        settings = _normalize_extra_protection_settings_local(decoded)
        except Exception:
            settings = _default_extra_protection_settings_local()

        self.extra_protection_settings_cache[cache_key] = settings
        self.extra_protection_settings_expire[cache_key] = now_ts + self.extra_protection_cache_ttl_seconds
        return settings

    async def _get_nsfw_guard_settings(self, guild_id: int) -> dict[str, Any]:
        cache_key = str(guild_id)
        now_ts = time.time()
        cached = self.nsfw_guard_settings_cache.get(cache_key)
        expire_at = float(self.nsfw_guard_settings_expire.get(cache_key, 0.0) or 0.0)
        if cached is not None and now_ts < expire_at:
            return cached

        settings = _default_nsfw_guard_settings_local()
        try:
            row = await storage.dashboard_config.get(
                config_key=self._nsfw_guard_config_key(guild_id)
            )
            if row and isinstance(row, dict):
                raw_value = str(row.get("config_value") or "").strip()
                if raw_value:
                    decoded = json.loads(raw_value)
                    if isinstance(decoded, dict):
                        settings = _normalize_nsfw_guard_settings_local(decoded)
        except Exception:
            settings = _default_nsfw_guard_settings_local()

        self.nsfw_guard_settings_cache[cache_key] = settings
        self.nsfw_guard_settings_expire[cache_key] = now_ts + self.nsfw_guard_cache_ttl_seconds
        return settings

    @staticmethod
    def _should_check_nsfw_image_in_channel(
        *,
        channel_id: int,
        mode: str,
        allowlist_channel_ids: set[str],
    ) -> bool:
        id_text = str(int(channel_id))
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode == EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST:
            return id_text not in allowlist_channel_ids
        if not allowlist_channel_ids:
            return False
        return id_text in allowlist_channel_ids

    @staticmethod
    def _extract_message_image_urls(message: discord.Message, *, limit: int = 4) -> list[str]:
        urls: list[str] = []

        def _append_url(raw_url: Any) -> None:
            candidate = str(raw_url or "").strip()
            if not candidate:
                return
            if not candidate.startswith(("http://", "https://")):
                return
            if candidate in urls:
                return
            urls.append(candidate)

        for attachment in list(getattr(message, "attachments", []) or []):
            content_type = str(getattr(attachment, "content_type", "") or "").strip().lower()
            filename = str(getattr(attachment, "filename", "") or "").strip().lower()
            if not (
                content_type.startswith("image/")
                or any(filename.endswith(ext) for ext in EXTRA_PROTECTION_IMAGE_EXTENSIONS)
            ):
                continue
            _append_url(getattr(attachment, "url", ""))
            if len(urls) >= limit:
                return urls[:limit]

        for embed in list(getattr(message, "embeds", []) or []):
            embed_image = getattr(getattr(embed, "image", None), "url", None)
            embed_thumb = getattr(getattr(embed, "thumbnail", None), "url", None)
            _append_url(embed_image)
            if len(urls) >= limit:
                return urls[:limit]
            _append_url(embed_thumb)
            if len(urls) >= limit:
                return urls[:limit]
        return urls[:limit]

    def _nsfw_image_cached_result(self, image_url: str) -> dict[str, Any] | None:
        cache_key = hashlib.sha256(str(image_url or "").encode("utf-8")).hexdigest()
        row = self.nsfw_image_moderation_cache.get(cache_key)
        if not isinstance(row, dict):
            return None
        expire_at = float(row.get("expire_at", 0.0) or 0.0)
        if time.time() >= expire_at:
            self.nsfw_image_moderation_cache.pop(cache_key, None)
            return None
        result = row.get("result")
        return dict(result) if isinstance(result, dict) else None

    def _set_nsfw_image_cached_result(self, image_url: str, result: dict[str, Any]) -> None:
        cache_key = hashlib.sha256(str(image_url or "").encode("utf-8")).hexdigest()
        self.nsfw_image_moderation_cache[cache_key] = {
            "expire_at": time.time() + self.nsfw_image_moderation_cache_ttl_seconds,
            "result": dict(result or {}),
        }

    @staticmethod
    def _promote_moderation_image_filename(image_url: str, content_type: str) -> str:
        link = str(image_url or "").strip()
        content_type_text = str(content_type or "").strip().lower()
        parsed = urlparse(link)
        base_name = os.path.basename(str(parsed.path or "").strip())
        base_name = base_name.split("?", 1)[0].strip()
        if base_name and "." in base_name:
            return base_name[:80]
        guessed_ext = mimetypes.guess_extension(content_type_text or "") or ""
        safe_ext = guessed_ext if guessed_ext.startswith(".") else ""
        if safe_ext in {".jpe"}:
            safe_ext = ".jpg"
        if not safe_ext:
            safe_ext = ".png"
        return f"image{safe_ext}"

    @staticmethod
    def _sanitize_discord_attachment_filename(filename: str, *, fallback: str = "image.png") -> str:
        raw = os.path.basename(str(filename or "").strip())
        if not raw or raw in {".", ".."}:
            raw = str(fallback or "image.png").strip() or "image.png"
        normalized = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
        normalized = re.sub(r"_+", "_", normalized).strip("._") or "image"
        if "." not in normalized:
            fallback_ext = os.path.splitext(str(fallback or "image.png"))[1] or ".png"
            normalized = f"{normalized}{fallback_ext}"
        if len(normalized) > 96:
            head, ext = os.path.splitext(normalized)
            normalized = f"{head[: max(1, 96 - len(ext))]}{ext}"
        return normalized

    @staticmethod
    def _is_discord_cdn_attachment_url(url: str) -> bool:
        parsed = urlparse(str(url or "").strip())
        host = str(parsed.hostname or "").strip().lower()
        path_text = str(parsed.path or "").strip().lower()
        return host in {"cdn.discordapp.com", "media.discordapp.net"} and path_text.startswith("/attachments/")

    @staticmethod
    def _is_aiforthai_violent_endpoint(endpoint: str) -> bool:
        parsed = urlparse(str(endpoint or "").strip())
        path_text = str(parsed.path or "").strip().lower()
        return bool(path_text.endswith("/violent") or "/violent/" in path_text or path_text.endswith("violent"))

    @staticmethod
    def _is_image_moderation_rate_limited_error(error_text: str) -> bool:
        text = str(error_text or "").strip().lower()
        if not text:
            return False
        return (
            "http_429" in text
            or " 429" in text
            or "status=429" in text
            or "rate limit" in text
            or "too many requests" in text
        )

    @staticmethod
    def _is_image_moderation_transient_error(error_text: str) -> bool:
        text = str(error_text or "").strip().lower()
        if not text:
            return False
        transient_tokens = (
            "clientpayloaderror",
            "serverdisconnectederror",
            "clientconnectorerror",
            "connectionreseterror",
            "timeout",
            "payload_error",
            "response_read_failed",
            "request_failed",
            "temporarily unavailable",
            "service unavailable",
            "http_500",
            "http_502",
            "http_503",
            "http_504",
        )
        return any(token in text for token in transient_tokens)

    def _promote_image_notice_allowed(self, key: str, *, cooldown_seconds: float = 90.0) -> bool:
        notice_key = str(key or "").strip()
        if not notice_key:
            return True
        now_ts = time.time()
        notice_until = float(self.promote_image_moderation_notice_until.get(notice_key, 0.0) or 0.0)
        if now_ts < notice_until:
            return False
        self.promote_image_moderation_notice_until[notice_key] = now_ts + max(5.0, float(cooldown_seconds))
        return True

    @staticmethod
    def _coerce_unit_score(raw_value: Any) -> float:
        try:
            value = float(raw_value)
        except Exception:
            return 0.0
        if value < 0.0:
            return 0.0
        if value <= 1.0:
            return value
        if value <= 100.0:
            return value / 100.0
        return 1.0

    @staticmethod
    def _coerce_bool_flag(raw_value: Any) -> bool:
        if isinstance(raw_value, bool):
            return raw_value
        text = str(raw_value or "").strip().lower()
        return text in {"1", "true", "yes", "on", "y"}

    @classmethod
    def _extract_aiforthai_violent_signal(
        cls, payload: Any
    ) -> tuple[float, bool, float, bool, bool, bool]:
        violent_scores: list[float] = []
        sexual_scores: list[float] = []
        violent_flagged = False
        sexual_flagged = False
        generic_flagged = False
        recognized_signal = False
        violent_tokens = ("violent", "violence", "gore", "blood", "weapon", "fight")
        sexual_tokens = (
            "sexual",
            "nudity",
            "nude",
            "nsfw",
            "unsafe",
            "porn",
            "pornographic",
            "explicit",
            "erotic",
            "hentai",
            "adult",
            "boob",
            "breast",
            "nipple",
            "genital",
            "vagina",
            "penis",
            "ass",
            "butt",
            "sexy",
            "xxx",
            "r18",
            "18+",
            "อนาจาร",
            "โป๊",
            "เปลือย",
        )

        def _mark_score(
            *,
            key_text: str,
            value: Any,
            violent_context: bool = False,
            sexual_context: bool = False,
        ) -> None:
            nonlocal violent_flagged, sexual_flagged, recognized_signal
            key_lower = str(key_text or "").lower()
            is_violent = violent_context or any(token in key_lower for token in violent_tokens)
            is_sexual = sexual_context or any(token in key_lower for token in sexual_tokens)
            if is_violent or is_sexual:
                recognized_signal = True
            score = cls._coerce_unit_score(value)
            if score <= 0.0:
                return
            if is_violent:
                violent_scores.append(score)
                if score >= 0.72:
                    violent_flagged = True
            if is_sexual:
                sexual_scores.append(score)
                if score >= 0.72:
                    sexual_flagged = True

        def _visit(node: Any, *, violent_context: bool = False, sexual_context: bool = False) -> None:
            nonlocal violent_flagged, sexual_flagged, generic_flagged, recognized_signal
            if isinstance(node, dict):
                labels: list[str] = []
                for raw_key, raw_value in node.items():
                    key = str(raw_key or "")
                    key_lower = key.strip().lower()
                    if key_lower in {"label", "class", "prediction", "category", "name", "tag"}:
                        labels.append(str(raw_value or "").strip().lower())
                    if key_lower in {"flagged", "unsafe", "blocked"} and cls._coerce_bool_flag(raw_value):
                        generic_flagged = True
                    if any(token in key_lower for token in violent_tokens) and cls._coerce_bool_flag(raw_value):
                        recognized_signal = True
                        violent_flagged = True
                    if any(token in key_lower for token in sexual_tokens) and cls._coerce_bool_flag(raw_value):
                        recognized_signal = True
                        sexual_flagged = True
                    if key_lower in {"class", "classification", "category", "label", "name", "tag"}:
                        label_value = str(raw_value or "").strip().lower()
                        if any(token in label_value for token in sexual_tokens):
                            recognized_signal = True
                            sexual_flagged = True
                        if any(token in label_value for token in violent_tokens):
                            recognized_signal = True
                            violent_flagged = True
                    _mark_score(
                        key_text=key_lower,
                        value=raw_value,
                        violent_context=violent_context,
                        sexual_context=sexual_context,
                    )

                label_text = " ".join(labels)
                label_violent = any(token in label_text for token in violent_tokens)
                label_sexual = any(token in label_text for token in sexual_tokens)
                if label_violent or label_sexual:
                    recognized_signal = True
                for score_key in ("score", "confidence", "probability", "value", "percent", "pct"):
                    if score_key in node:
                        _mark_score(
                            key_text=score_key,
                            value=node.get(score_key),
                            violent_context=violent_context or label_violent,
                            sexual_context=sexual_context or label_sexual,
                        )
                        if not (violent_context or label_violent or sexual_context or label_sexual):
                            fallback_score = cls._coerce_unit_score(node.get(score_key))
                            if fallback_score > 0.0:
                                recognized_signal = True

                next_violent = violent_context or label_violent or any(
                    token in str(key or "").strip().lower()
                    for key in node.keys()
                    for token in violent_tokens
                )
                next_sexual = sexual_context or label_sexual or any(
                    token in str(key or "").strip().lower()
                    for key in node.keys()
                    for token in sexual_tokens
                )
                for value in node.values():
                    if isinstance(value, (dict, list, tuple)):
                        _visit(value, violent_context=next_violent, sexual_context=next_sexual)
                return
            if isinstance(node, (list, tuple)):
                for value in node:
                    _visit(value, violent_context=violent_context, sexual_context=sexual_context)

        _visit(payload)
        violent_score = max(violent_scores) if violent_scores else 0.0
        sexual_score = max(sexual_scores) if sexual_scores else 0.0
        return violent_score, violent_flagged, sexual_score, sexual_flagged, generic_flagged, recognized_signal

    async def _download_image_bytes_for_moderation(
        self,
        image_url: str,
        *,
        max_bytes: int = 5 * 1024 * 1024,
    ) -> tuple[bytes, str]:
        link = str(image_url or "").strip()
        if not link.startswith(("http://", "https://")):
            return b"", ""
        timeout = aiohttp.ClientTimeout(total=max(8, self.nsfw_image_moderation_timeout_seconds))
        headers = {
            "User-Agent": "SkylineBOT/1.0 (+https://skylinebot.xyz)",
            "Accept": "image/*,*/*;q=0.8",
        }
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(link) as response:
                    if response.status >= 400:
                        return b"", ""
                    content_type = str(response.headers.get("Content-Type", "") or "").split(";")[0].strip().lower()
                    payload = await response.read()
        except Exception:
            return b"", ""
        if not payload:
            return b"", ""
        if len(payload) > max_bytes:
            return b"", content_type
        if not content_type.startswith("image/"):
            content_type = "application/octet-stream"
        return bytes(payload), content_type

    @staticmethod
    def _promote_is_skin_pixel_local(
        r: int,
        g: int,
        b: int,
        cb: int,
        cr: int,
    ) -> bool:
        rgb_rule = (
            r > 95
            and g > 40
            and b > 20
            and (max(r, g, b) - min(r, g, b) > 15)
            and abs(r - g) > 15
            and r > g
            and r > b
        )
        ycbcr_rule = 77 <= cb <= 127 and 133 <= cr <= 173
        return bool((rgb_rule and ycbcr_rule) or (ycbcr_rule and r > 40 and g > 20 and b > 15))

    @classmethod
    def _promote_skin_ratios_from_image_bytes_local(cls, image_payload: bytes) -> tuple[float, float]:
        try:
            from PIL import Image
        except Exception:
            return 0.0, 0.0
        if not image_payload:
            return 0.0, 0.0
        try:
            with Image.open(io.BytesIO(image_payload)) as image_obj:
                rgb_image = image_obj.convert("RGB")
        except Exception:
            return 0.0, 0.0
        try:
            resample = getattr(getattr(Image, "Resampling", Image), "BILINEAR", Image.BILINEAR)
            if max(rgb_image.size) > 256:
                rgb_image.thumbnail((256, 256), resample)
        except Exception:
            pass
        ycbcr_image = rgb_image.convert("YCbCr")
        width, height = rgb_image.size
        total = int(width * height)
        if total <= 0:
            return 0.0, 0.0

        x_min = int(width * 0.25)
        x_max = int(width * 0.75)
        y_min = int(height * 0.25)
        y_max = int(height * 0.75)
        center_total = max(1, int((x_max - x_min) * (y_max - y_min)))

        rgb_pixels = rgb_image.load()
        ycbcr_pixels = ycbcr_image.load()
        skin_pixels = 0
        center_skin_pixels = 0
        for y in range(height):
            for x in range(width):
                r, g, b = rgb_pixels[x, y]
                _yy, cb, cr = ycbcr_pixels[x, y]
                if not cls._promote_is_skin_pixel_local(int(r), int(g), int(b), int(cb), int(cr)):
                    continue
                skin_pixels += 1
                if x_min <= x < x_max and y_min <= y < y_max:
                    center_skin_pixels += 1

        skin_ratio = float(skin_pixels) / float(total)
        center_skin_ratio = float(center_skin_pixels) / float(center_total)
        return max(0.0, min(1.0, skin_ratio)), max(0.0, min(1.0, center_skin_ratio))

    async def _promote_local_image_guard(self, image_url: str) -> tuple[bool, str]:
        if not self.promote_local_skin_guard_enabled:
            return False, ""
        payload, _content_type = await self._download_image_bytes_for_moderation(
            image_url,
            max_bytes=8 * 1024 * 1024,
        )
        if not payload:
            return False, ""
        skin_ratio, center_skin_ratio = self._promote_skin_ratios_from_image_bytes_local(payload)
        if skin_ratio <= 0.0 and center_skin_ratio <= 0.0:
            return False, ""
        if skin_ratio >= float(self.promote_local_extreme_skin_ratio_threshold):
            return (
                True,
                (
                    "ตรวจเชิงโครงสร้างภาพ: ผิวหนังมากผิดปกติ "
                    f"(rule=extreme_skin, skin_ratio={skin_ratio:.2f}, "
                    f"threshold={float(self.promote_local_extreme_skin_ratio_threshold):.2f}, "
                    f"center_skin_ratio={center_skin_ratio:.2f})"
                ),
            )
        if (
            skin_ratio >= float(self.promote_local_skin_ratio_threshold)
            and center_skin_ratio >= float(self.promote_local_center_skin_ratio_threshold)
        ):
            return (
                True,
                (
                    "ตรวจเชิงโครงสร้างภาพ: สัดส่วนผิวหนังสูงทั้งภาพและกลางภาพ "
                    f"(rule=skin_and_center, skin_ratio={skin_ratio:.2f}, "
                    f"skin_threshold={float(self.promote_local_skin_ratio_threshold):.2f}, "
                    f"center_skin_ratio={center_skin_ratio:.2f}, "
                    f"center_threshold={float(self.promote_local_center_skin_ratio_threshold):.2f})"
                ),
            )
        return False, ""

    async def _moderate_image_url_aiforthai(self, image_url: str) -> dict[str, Any]:
        cached = self._nsfw_image_cached_result(image_url)
        if cached is not None:
            return cached
        api_key = str(self.aiforthai_api_key or "").strip()
        if not api_key:
            return {
                "ok": False,
                "provider": "aiforthai",
                "error": "missing_aiforthai_api_key",
            }
        endpoint_candidates_raw = [
            str(self.nsfw_aiforthai_violent_endpoint or "").strip(),
            str(self.nsfw_aiforthai_violent_fallback_endpoint or "").strip(),
            str(os.getenv("AIFORTHAI_VIOLENT_ENDPOINT", "") or "").strip(),
            str(os.getenv("AIFORTHAI_NSFW_ENDPOINT", "") or "").strip(),
            "https://api.aiforthai.in.th/violent",
            "https://api.aiforthai.in.th/nsfw",
        ]
        endpoint_candidates: list[str] = []
        for item in endpoint_candidates_raw:
            if not item.startswith(("http://", "https://")):
                continue
            if item in endpoint_candidates:
                continue
            endpoint_candidates.append(item)
        endpoint_candidates = sorted(
            endpoint_candidates,
            key=lambda value: 1 if self._is_aiforthai_violent_endpoint(value) else 0,
        )
        if not endpoint_candidates:
            return {
                "ok": False,
                "provider": "aiforthai",
                "error": "invalid_aiforthai_endpoint",
            }

        headers = {
            "User-Agent": "SkylineBOT/1.0 (+https://skylinebot.xyz)",
            "Accept": "application/json",
        }
        if self.nsfw_aiforthai_use_bearer_auth:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers[str(self.nsfw_aiforthai_api_key_header or "Apikey")] = api_key

        timeout = aiohttp.ClientTimeout(total=self.nsfw_image_moderation_timeout_seconds)
        image_payload, image_content_type = await self._download_image_bytes_for_moderation(image_url)
        if not image_payload:
            return {
                "ok": False,
                "provider": "aiforthai",
                "error": "image_fetch_failed",
            }
        image_file_name = self._promote_moderation_image_filename(image_url, image_content_type)
        multipart_request_candidates: list[dict[str, Any]] = []
        if image_payload:
            for file_field_name in ("file", "image", "img", "upload"):
                multipart_request_candidates.append(
                    {
                        "kind": "multipart",
                        "file_field": file_field_name,
                        "file_name": image_file_name,
                        "payload": image_payload,
                        "content_type": image_content_type or "application/octet-stream",
                    }
                )
        url_request_candidates: list[dict[str, Any]] = [
            {"kind": "json", "value": {"url": image_url}},
            {"kind": "json", "value": {"image_url": image_url}},
            {"kind": "json", "value": {"image": image_url}},
            {"kind": "form", "value": {"url": image_url}},
            {"kind": "form", "value": {"image_url": image_url}},
        ]

        def _parse_retry_after_seconds(raw_text: str, headers_map: Any) -> int:
            retry_after_raw = ""
            if hasattr(headers_map, "get"):
                retry_after_raw = str(headers_map.get("Retry-After", "") or "").strip()
            if retry_after_raw:
                try:
                    retry_after_value = int(float(retry_after_raw))
                    if retry_after_value > 0:
                        return retry_after_value
                except Exception:
                    pass
            try:
                parsed_payload = json.loads(raw_text)
            except Exception:
                parsed_payload = {}
            if isinstance(parsed_payload, dict):
                for key in ("retry_after", "retryAfter", "retry"):
                    try:
                        value = int(float(parsed_payload.get(key, 0) or 0))
                        if value > 0:
                            return value
                    except Exception:
                        continue
            return 0

        raw = ""
        decoded: Any = {}
        http_error = ""
        request_ok = False
        used_endpoint = ""
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                for endpoint in endpoint_candidates:
                    endpoint_candidates_for_request: list[dict[str, Any]] = []
                    if self._is_aiforthai_violent_endpoint(endpoint):
                        if not multipart_request_candidates:
                            continue
                        endpoint_candidates_for_request.extend(multipart_request_candidates)
                    else:
                        endpoint_candidates_for_request.extend(multipart_request_candidates)
                        endpoint_candidates_for_request.extend(url_request_candidates)
                    for candidate in endpoint_candidates_for_request:
                        kind = str(candidate.get("kind") or "").strip().lower()
                        if kind == "multipart":
                            form = aiohttp.FormData()
                            form.add_field(
                                str(candidate.get("file_field") or "file"),
                                candidate.get("payload") or b"",
                                filename=str(candidate.get("file_name") or image_file_name),
                                content_type=str(candidate.get("content_type") or "application/octet-stream"),
                            )
                            request_args: dict[str, Any] = {"data": form}
                        elif kind == "form":
                            request_args = {"data": candidate.get("value") or {}}
                        else:
                            request_args = {"json": candidate.get("value") or {}}
                        try:
                            async with session.post(endpoint, **request_args) as response:
                                try:
                                    raw = await response.text()
                                except aiohttp.ClientPayloadError as payload_error:
                                    http_error = f"{endpoint} payload_error:{type(payload_error).__name__}"
                                    continue
                                except Exception as read_error:
                                    http_error = f"{endpoint} response_read_failed:{type(read_error).__name__}"
                                    continue
                                if response.status in {401, 403}:
                                    return {
                                        "ok": False,
                                        "provider": "aiforthai",
                                        "error": f"http_{response.status}:{raw[:180]}",
                                    }
                                if response.status == 429:
                                    retry_after_seconds = _parse_retry_after_seconds(raw, getattr(response, "headers", None))
                                    if retry_after_seconds <= 0:
                                        retry_after_seconds = 60
                                    return {
                                        "ok": False,
                                        "provider": "aiforthai",
                                        "error": f"{endpoint} http_429:{raw[:180]}",
                                        "rate_limited": True,
                                        "retry_after": retry_after_seconds,
                                    }
                                if response.status >= 400:
                                    http_error = f"{endpoint} http_{response.status}:{raw[:180]}"
                                    continue
                                request_ok = True
                                used_endpoint = endpoint
                                try:
                                    decoded = json.loads(raw)
                                except Exception:
                                    decoded = {}
                                break
                        except (aiohttp.ClientError, asyncio.TimeoutError) as request_error:
                            http_error = f"{endpoint} request_failed:{type(request_error).__name__}"
                            continue
                    if request_ok:
                        break
        except Exception as error:
            return {
                "ok": False,
                "provider": "aiforthai",
                "error": f"request_failed:{type(error).__name__}",
            }

        if not request_ok:
            return {
                "ok": False,
                "provider": "aiforthai",
                "error": http_error or "request_failed",
            }
        if not isinstance(decoded, dict):
            if http_error:
                return {
                    "ok": False,
                    "provider": "aiforthai",
                    "error": http_error,
                }
            return {
                "ok": False,
                "provider": "aiforthai",
                "error": "invalid_json",
            }

        violent_score, violent_flagged, sexual_score, sexual_flagged, generic_flagged, recognized_signal = (
            self._extract_aiforthai_violent_signal(decoded)
        )
        if not recognized_signal and not bool(decoded):
            return {
                "ok": False,
                "provider": "aiforthai",
                "error": "unsupported_response",
            }
        category_snapshot = {
            "sexual": sexual_score,
            "sexual/minors": 0.0,
            "violence": violent_score,
            "violence/graphic": violent_score,
            "illicit": 0.0,
            "illicit/violent": violent_score,
            "self-harm": 0.0,
            "self-harm/intent": 0.0,
            "self-harm/instructions": 0.0,
            "hate": 0.0,
            "hate/threatening": 0.0,
            "harassment": 0.0,
            "harassment/threatening": 0.0,
        }
        category_flags = {
            "sexual": sexual_flagged,
            "sexual/minors": False,
            "violence": violent_flagged or violent_score >= self.nsfw_aiforthai_violent_threshold,
            "violence/graphic": violent_flagged or violent_score >= self.nsfw_aiforthai_violent_threshold,
            "illicit": False,
            "illicit/violent": violent_flagged or violent_score >= self.nsfw_aiforthai_violent_threshold,
            "self-harm": False,
            "self-harm/intent": False,
            "self-harm/instructions": False,
            "hate": False,
            "hate/threatening": False,
            "harassment": False,
            "harassment/threatening": False,
        }
        result = {
            "ok": True,
            "provider": "aiforthai",
            "model": str(decoded.get("model") or "aiforthai-violent"),
            "flagged": bool(generic_flagged)
            or bool(violent_flagged)
            or violent_score >= self.nsfw_aiforthai_violent_threshold,
            "sexual_flagged": bool(sexual_flagged),
            "sexual_score": float(sexual_score),
            "violence_score": float(violent_score),
            "category_scores": category_snapshot,
            "category_flags": category_flags,
            "endpoint": used_endpoint,
            "raw_response": decoded,
        }
        self._set_nsfw_image_cached_result(image_url, result)
        return result

    async def _moderate_image_url(self, image_url: str) -> dict[str, Any]:
        provider = str(self.nsfw_image_moderation_provider or "").strip().lower()
        if provider == "openai":
            return await self._moderate_image_url_openai(image_url)
        return await self._moderate_image_url_aiforthai(image_url)

    async def _ocr_text_from_image_url(self, image_url: str) -> str:
        if not self.promote_image_ocr_supplement_enabled:
            return ""
        endpoint = str(self.promote_image_ocr_space_url or "").strip()
        if not endpoint.startswith(("http://", "https://")):
            return ""
        timeout = aiohttp.ClientTimeout(total=max(8, self.nsfw_image_moderation_timeout_seconds + 6))
        primary_lang = str(self.promote_image_ocr_space_lang or "auto").strip().lower() or "auto"
        language_candidates: list[str] = []
        for lang in (primary_lang, "tha", "auto", "eng"):
            value = str(lang or "").strip().lower()
            if not value or value in language_candidates:
                continue
            language_candidates.append(value)

        def _extract_payload_text(payload: Any) -> str:
            if not isinstance(payload, dict):
                return ""
            parsed_results = payload.get("ParsedResults")
            if not isinstance(parsed_results, list):
                return ""
            chunks: list[str] = []
            for item in parsed_results:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("ParsedText") or "").strip()
                if text:
                    chunks.append(text)
            return "\n".join(chunks).strip()[:6000]

        async def _post_ocr_form(
            session: aiohttp.ClientSession,
            *,
            language: str,
            image_url_value: str = "",
            image_payload: bytes = b"",
            image_content_type: str = "application/octet-stream",
            image_filename: str = "ocr_input.png",
        ) -> str:
            form = aiohttp.FormData()
            form.add_field("apikey", self.promote_image_ocr_space_key or "helloworld")
            form.add_field("language", language)
            form.add_field("OCREngine", "2")
            form.add_field("isOverlayRequired", "false")
            form.add_field("scale", "true")
            if image_payload:
                form.add_field(
                    "file",
                    image_payload,
                    filename=image_filename,
                    content_type=image_content_type or "application/octet-stream",
                )
            else:
                form.add_field("url", image_url_value)
            try:
                async with session.post(endpoint, data=form) as response:
                    if response.status >= 400:
                        return ""
                    try:
                        payload = await response.json(content_type=None)
                    except Exception:
                        return ""
            except Exception:
                return ""
            return _extract_payload_text(payload)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for language in language_candidates:
                    extracted = await _post_ocr_form(
                        session,
                        language=language,
                        image_url_value=image_url,
                    )
                    if extracted:
                        return extracted
                image_payload, image_content_type = await self._download_image_bytes_for_moderation(
                    image_url,
                    max_bytes=8 * 1024 * 1024,
                )
                if not image_payload:
                    return ""
                image_filename = self._promote_moderation_image_filename(image_url, image_content_type)
                for language in language_candidates:
                    extracted = await _post_ocr_form(
                        session,
                        language=language,
                        image_payload=image_payload,
                        image_content_type=image_content_type,
                        image_filename=image_filename,
                    )
                    if extracted:
                        return extracted
        except Exception:
            return ""
        return ""

    def _promote_ocr_violation_reason(self, ocr_text: str, *, blocked_words: list[str] | None = None) -> str:
        text = str(ocr_text or "").strip()
        if not text:
            return ""
        blocked_word_pool = _promote_merge_blocked_words_local(
            PROMOTE_DEFAULT_BLOCKED_WORDS,
            blocked_words or [],
            PROMOTE_GAMBLING_BLOCK_WORDS,
        )
        content_ok, content_reason = _validate_promote_content_local(text, blocked_word_pool)
        if not content_ok:
            return f"ข้อความในรูปเข้าข่ายคำต้องห้าม ({content_reason})"
        lowered = text.lower()
        for token in list(EXTRA_PROTECTION_SCAM_PATTERNS) + list(EXTRA_PROTECTION_DEFAULT_VIRUS_KEYWORDS):
            probe = str(token or "").strip().lower()
            if probe and probe in lowered:
                return f"ข้อความในรูปเข้าข่ายหลอกลวง/มัลแวร์ ({probe})"
        return ""

    async def _moderate_image_url_openai(self, image_url: str) -> dict[str, Any]:
        cached = self._nsfw_image_cached_result(image_url)
        if cached is not None:
            return cached
        if not self.openai_api_key:
            return {
                "ok": False,
                "provider": "openai",
                "error": "missing_openai_api_key",
            }

        endpoint = "https://api.openai.com/v1/moderations"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SkylineBOT/1.0 (+https://skylinebot.xyz)",
        }
        payload = {
            "model": self.nsfw_image_moderation_model,
            "input": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                }
            ],
        }
        timeout = aiohttp.ClientTimeout(total=self.nsfw_image_moderation_timeout_seconds)
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.post(endpoint, json=payload) as response:
                    raw = await response.text()
                    if response.status >= 400:
                        return {
                            "ok": False,
                            "provider": "openai",
                            "error": f"http_{response.status}:{raw[:180]}",
                        }
        except Exception as error:
            return {
                "ok": False,
                "provider": "openai",
                "error": f"request_failed:{type(error).__name__}",
            }

        try:
            decoded = json.loads(raw)
        except Exception:
            return {
                "ok": False,
                "provider": "openai",
                "error": "invalid_json",
            }

        results = decoded.get("results") if isinstance(decoded, dict) else None
        first_result = results[0] if isinstance(results, list) and results else {}
        categories = first_result.get("categories") if isinstance(first_result, dict) else {}
        category_scores = first_result.get("category_scores") if isinstance(first_result, dict) else {}

        def _score(key: str) -> float:
            try:
                return float((category_scores or {}).get(key, 0.0) or 0.0)
            except Exception:
                return 0.0

        def _flag(key: str) -> bool:
            try:
                return bool((categories or {}).get(key))
            except Exception:
                return False

        sexual_score = max(_score("sexual"), _score("sexual/minors"))
        sexual_flagged = _flag("sexual") or _flag("sexual/minors")
        category_snapshot = {
            "sexual": _score("sexual"),
            "sexual/minors": _score("sexual/minors"),
            "violence": _score("violence"),
            "violence/graphic": _score("violence/graphic"),
            "illicit": _score("illicit"),
            "illicit/violent": _score("illicit/violent"),
            "self-harm": _score("self-harm"),
            "self-harm/intent": _score("self-harm/intent"),
            "self-harm/instructions": _score("self-harm/instructions"),
            "hate": _score("hate"),
            "hate/threatening": _score("hate/threatening"),
            "harassment": _score("harassment"),
            "harassment/threatening": _score("harassment/threatening"),
        }
        category_flags = {
            key: _flag(key)
            for key in category_snapshot.keys()
        }
        result = {
            "ok": True,
            "provider": "openai",
            "model": str(decoded.get("model") or self.nsfw_image_moderation_model),
            "flagged": bool(first_result.get("flagged")) or sexual_flagged,
            "sexual_flagged": sexual_flagged,
            "sexual_score": sexual_score,
            "category_scores": category_snapshot,
            "category_flags": category_flags,
        }
        self._set_nsfw_image_cached_result(image_url, result)
        return result

    async def _check_nsfw_image_message(
        self,
        message: discord.Message,
        *,
        settings: dict[str, Any],
    ) -> bool:
        if not settings.get("detect_nsfw_image_enabled"):
            return False
        image_urls = self._extract_message_image_urls(message)
        if not image_urls:
            return False

        nsfw_settings = await self._get_nsfw_guard_settings(message.guild.id)
        allowlist_channel_ids = {
            str(item)
            for item in list(nsfw_settings.get("allowed_channel_ids") or [])
            if str(item).isdigit()
        }
        scan_mode = str(
            settings.get("detect_nsfw_image_mode")
            or EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY
        ).strip().lower()
        if scan_mode not in {
            EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY,
            EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALL_EXCEPT_ALLOWLIST,
        }:
            scan_mode = EXTRA_PROTECTION_NSFW_IMAGE_MODE_ALLOWLIST_ONLY

        if not self._should_check_nsfw_image_in_channel(
            channel_id=message.channel.id,
            mode=scan_mode,
            allowlist_channel_ids=allowlist_channel_ids,
        ):
            return False

        try:
            threshold = float(settings.get("detect_nsfw_image_threshold") or 0.72)
        except Exception:
            threshold = 0.72
        threshold = max(0.05, min(0.995, threshold))

        for image_url in image_urls:
            moderation_result = await self._moderate_image_url(image_url)
            if not moderation_result.get("ok"):
                now_ts = time.time()
                notice_until = float(
                    self.nsfw_image_moderation_error_notice_until.get(message.guild.id, 0.0) or 0.0
                )
                if now_ts >= notice_until:
                    self.nsfw_image_moderation_error_notice_until[message.guild.id] = now_ts + 120.0
                    logger.warning(
                        f"NSFW image moderation skipped in guild {message.guild.id}: "
                        f"{moderation_result.get('error', 'unknown_error')}"
                    )
                continue

            sexual_score = float(moderation_result.get("sexual_score", 0.0) or 0.0)
            violence_score = float(moderation_result.get("violence_score", 0.0) or 0.0)
            provider = str(moderation_result.get("provider") or "").strip().lower()
            if provider == "aiforthai":
                is_flagged = bool(moderation_result.get("flagged")) or violence_score >= self.nsfw_aiforthai_violent_threshold
                score_for_notice = violence_score
            else:
                is_flagged = bool(moderation_result.get("sexual_flagged")) or sexual_score >= threshold
                score_for_notice = sexual_score
            if not is_flagged:
                continue
            return await self._extra_protection_apply_action(
                message,
                settings=settings,
                reason=f"Unsafe image detected (score={score_for_notice:.2f})",
            )
        return False

    def _promote_image_violation_reason(self, moderation_result: dict[str, Any]) -> str:
        if not moderation_result.get("ok"):
            return "ระบบตรวจรูปภาพไม่พร้อมใช้งาน"
        category_scores = moderation_result.get("category_scores")
        if not isinstance(category_scores, dict):
            category_scores = {}
        category_flags = moderation_result.get("category_flags")
        if not isinstance(category_flags, dict):
            category_flags = {}
        provider = str(moderation_result.get("provider") or "unknown").strip().lower() or "unknown"
        model_name = str(moderation_result.get("model") or "").strip()

        for key, threshold in PROMOTE_IMAGE_FLAG_CATEGORY_THRESHOLDS.items():
            score = 0.0
            try:
                score = float(category_scores.get(key, 0.0) or 0.0)
            except Exception:
                score = 0.0
            flagged = bool(category_flags.get(key))
            if flagged or score >= float(threshold):
                trigger_text = "flag" if flagged else "score"
                provider_detail = f"provider={provider}" + (f", model={model_name}" if model_name else "")
                score_detail = f"score={score:.2f}, threshold={float(threshold):.2f}"
                if key in {"sexual", "sexual/minors"}:
                    return (
                        "ไม่ผ่าน: ตรวจพบเนื้อหาโป๊/18+ "
                        f"(category={key}, trigger={trigger_text}, {score_detail}, {provider_detail})"
                    )
                if key in {"illicit", "illicit/violent"}:
                    return (
                        "ไม่ผ่าน: ตรวจพบเนื้อหาผิดกฎหมาย/ผิดนโยบาย "
                        f"(category={key}, trigger={trigger_text}, {score_detail}, {provider_detail})"
                    )
                if key in {"violence", "violence/graphic"}:
                    return (
                        "ไม่ผ่าน: ตรวจพบเนื้อหาความรุนแรง "
                        f"(category={key}, trigger={trigger_text}, {score_detail}, {provider_detail})"
                    )
                return (
                    "ไม่ผ่าน: ตรวจพบเนื้อหาต้องห้าม "
                    f"(category={key}, trigger={trigger_text}, {score_detail}, {provider_detail})"
                )

        if moderation_result.get("flagged"):
            provider_detail = f"provider={provider}" + (f", model={model_name}" if model_name else "")
            return f"ไม่ผ่าน: ระบบจัดว่าภาพไม่ปลอดภัย (trigger=flagged, {provider_detail})"
        return ""

    async def scan_promote_image_urls(
        self,
        guild_id: int,
        image_urls: list[str],
        *,
        source: str = "discord",
        blocked_words: list[str] | None = None,
    ) -> tuple[bool, str]:
        def _scan_unavailable(reason: str) -> tuple[bool, str]:
            text_reason = str(reason or "ระบบตรวจรูปภาพยังไม่พร้อมใช้งาน").strip() or "ระบบตรวจรูปภาพยังไม่พร้อมใช้งาน"
            notice_key = f"promote_unavailable_block:{int(guild_id)}:{str(source or 'unknown').strip().lower()}"
            if self._promote_image_notice_allowed(notice_key, cooldown_seconds=60.0):
                logger.warning(
                    "Promote image moderation unavailable -> block | "
                    f"guild={guild_id} source={source} reason={text_reason}"
                )
            return False, text_reason

        urls: list[str] = []
        for raw in list(image_urls or [])[:4]:
            link = str(raw or "").strip()
            if not link or link in urls:
                continue
            if not link.startswith(("http://", "https://")):
                continue
            urls.append(link)
        if not urls:
            return True, ""
        provider = str(self.nsfw_image_moderation_provider or "").strip().lower()
        if provider == "openai":
            if not self.openai_api_key:
                return _scan_unavailable("ยังไม่ได้ตั้งค่า OPENAI_API_KEY สำหรับตรวจรูปภาพ")
        elif provider == "aiforthai":
            if not self.aiforthai_api_key:
                return _scan_unavailable("ยังไม่ได้ตั้งค่า AIFORTHAI_API_KEY สำหรับตรวจรูปภาพ")
        else:
            return _scan_unavailable("ระบบตรวจรูปภาพยังไม่พร้อมใช้งาน")
        provider_backoff_key = f"{provider}:{int(guild_id)}"
        now_ts = time.time()
        provider_backoff_until = float(self.promote_image_moderation_backoff_until.get(provider_backoff_key, 0.0) or 0.0)
        if now_ts < provider_backoff_until:
            wait_seconds = max(1, int(provider_backoff_until - now_ts))
            return _scan_unavailable(f"ระบบตรวจรูปภาพมีคิวหนาแน่นชั่วคราว กรุณาลองใหม่อีกครั้งใน {wait_seconds} วินาที")

        for image_url in urls:
            image_label = os.path.basename(urlsplit(str(image_url or "").strip()).path) or "unknown_image"
            try:
                moderation_result = await self._moderate_image_url(image_url)
            except Exception as error:
                failure_log_key = (
                    f"promote_exception:{int(guild_id)}:{str(source or 'unknown').strip().lower()}:{provider}"
                )
                if self._promote_image_notice_allowed(failure_log_key, cooldown_seconds=45.0):
                    logger.warning(
                        "Promote image moderation exception | "
                        f"guild={guild_id} source={source} provider={provider} "
                        f"error={type(error).__name__}: {str(error)[:160]}"
                    )
                return _scan_unavailable("ระบบตรวจรูปภาพขัดข้องชั่วคราว กรุณาลองใหม่")
            if not moderation_result.get("ok"):
                error_text = str(moderation_result.get("error", "unknown_error") or "unknown_error").strip()
                if error_text == "image_fetch_failed":
                    return _scan_unavailable("ไม่สามารถโหลดรูปจากลิงก์ต้นทางได้ กรุณาอัปโหลดใหม่อีกครั้ง")
                retry_after_seconds = 0
                try:
                    retry_after_seconds = int(float(moderation_result.get("retry_after", 0) or 0))
                except Exception:
                    retry_after_seconds = 0
                is_rate_limited = bool(moderation_result.get("rate_limited")) or self._is_image_moderation_rate_limited_error(error_text)
                if is_rate_limited:
                    if retry_after_seconds <= 0:
                        retry_after_seconds = 60
                    retry_after_seconds = max(15, min(600, retry_after_seconds))
                    self.promote_image_moderation_backoff_until[provider_backoff_key] = max(
                        float(self.promote_image_moderation_backoff_until.get(provider_backoff_key, 0.0) or 0.0),
                        time.time() + retry_after_seconds,
                    )
                    rate_limit_log_key = (
                        f"promote_rate_limit:{int(guild_id)}:{str(source or 'unknown').strip().lower()}:{provider}"
                    )
                    if self._promote_image_notice_allowed(rate_limit_log_key, cooldown_seconds=60.0):
                        logger.warning(
                            "Promote image moderation rate limited | "
                            f"guild={guild_id} source={source} provider={provider} retry_after={retry_after_seconds}s "
                            f"error={error_text}"
                        )
                    return _scan_unavailable(
                        f"ระบบตรวจรูปภาพมีคิวหนาแน่นชั่วคราว กรุณาลองใหม่อีกครั้งใน {retry_after_seconds} วินาที"
                    )
                is_transient = self._is_image_moderation_transient_error(error_text)
                if is_transient:
                    retry_after_seconds = max(10, min(180, retry_after_seconds or 25))
                    self.promote_image_moderation_backoff_until[provider_backoff_key] = max(
                        float(self.promote_image_moderation_backoff_until.get(provider_backoff_key, 0.0) or 0.0),
                        time.time() + retry_after_seconds,
                    )
                    transient_log_key = (
                        f"promote_transient:{int(guild_id)}:{str(source or 'unknown').strip().lower()}:{provider}"
                    )
                    if self._promote_image_notice_allowed(transient_log_key, cooldown_seconds=45.0):
                        logger.warning(
                            "Promote image moderation transient failure | "
                            f"guild={guild_id} source={source} provider={provider} retry_after={retry_after_seconds}s "
                            f"error={error_text}"
                        )
                    return _scan_unavailable(
                        f"ระบบตรวจรูปภาพขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้งใน {retry_after_seconds} วินาที"
                    )
                failure_log_key = f"promote_failed:{int(guild_id)}:{str(source or 'unknown').strip().lower()}:{provider}"
                if self._promote_image_notice_allowed(failure_log_key, cooldown_seconds=60.0):
                    logger.warning(
                        "Promote image moderation failed | "
                        f"guild={guild_id} source={source} provider={provider} error={error_text}"
                    )
                return _scan_unavailable("ระบบตรวจรูปภาพขัดข้องชั่วคราว กรุณาลองใหม่")
            violation_reason = self._promote_image_violation_reason(moderation_result)
            if violation_reason:
                return False, f"{violation_reason}\nไฟล์ที่พบปัญหา: {image_label}"
            skin_guard_blocked, skin_guard_reason = await self._promote_local_image_guard(image_url)
            if skin_guard_blocked:
                detailed_reason = skin_guard_reason or "ตรวจเชิงโครงสร้างภาพพบความเสี่ยงสูง"
                return False, f"ไม่ผ่าน: {detailed_reason}\nไฟล์ที่พบปัญหา: {image_label}"
            ocr_text = await self._ocr_text_from_image_url(image_url)
            ocr_violation_reason = self._promote_ocr_violation_reason(
                ocr_text,
                blocked_words=blocked_words,
            )
            if ocr_violation_reason:
                return False, f"{ocr_violation_reason}\nไฟล์ที่พบปัญหา: {image_label}"
        return True, ""

    async def _extra_protection_apply_action(
        self,
        message: discord.Message,
        *,
        settings: dict[str, Any],
        reason: str,
    ) -> bool:
        action = str(settings.get("delete_action") or "warn").strip().lower()
        timeout_seconds = int(settings.get("timeout_seconds") or 300)
        key = f"{message.guild.id}:{message.author.id}:{reason}:{action}"
        now_ts = time.time()
        if now_ts - float(self.extra_protection_action_cooldown.get(key, 0.0) or 0.0) < 5:
            return True
        self.extra_protection_action_cooldown[key] = now_ts

        try:
            await message.delete()
        except Exception:
            pass

        if action == "none":
            return True
        if action == "warn":
            try:
                await message.channel.send(
                    embed=discord.Embed(
                        description=f"{message.author.mention} warning: {reason}",
                        color=color.orange,
                    ),
                    delete_after=8,
                )
            except Exception:
                pass
            return True
        if action == "mute":
            try:
                await message.author.timeout(
                    datetime.timedelta(seconds=max(30, timeout_seconds)),
                    reason=f"Extra Protection: {reason}",
                )
            except Exception as error:
                logger.warning(f"ExtraProtection mute failed in {message.guild.name}: {error}")
            return True
        if action == "kick":
            try:
                await message.guild.kick(message.author, reason=f"Extra Protection: {reason}")
            except Exception as error:
                logger.warning(f"ExtraProtection kick failed in {message.guild.name}: {error}")
            return True
        if action == "ban":
            try:
                await message.guild.ban(message.author, reason=f"Extra Protection: {reason}")
            except Exception as error:
                logger.warning(f"ExtraProtection ban failed in {message.guild.name}: {error}")
            return True
        return True

    async def check_extra_protection(self, message: discord.Message) -> bool:
        if message.author.bot or not message.guild:
            return False
        settings = await self._get_extra_protection_settings(message.guild.id)
        if not settings.get("enabled"):
            return False

        if await checks.check_is_owner_raw(message.author, message.guild):
            return False
        if message.author.guild_permissions.administrator:
            return False
        if message.author.guild_permissions.manage_guild:
            return False
        if message.author.guild_permissions.manage_messages:
            return False

        content = str(message.content or "")
        content_lower = content.lower()

        if settings.get("anti_spam_enabled"):
            bucket_key = f"{message.guild.id}:{message.author.id}"
            bucket = self.extra_protection_spam_buckets[bucket_key]
            now_ts = time.time()
            window_seconds = int(settings.get("spam_window_seconds") or 12)
            while bucket and (now_ts - float(bucket[0])) > window_seconds:
                bucket.popleft()
            bucket.append(now_ts)
            if len(bucket) >= int(settings.get("spam_message_limit") or 7):
                return await self._extra_protection_apply_action(
                    message,
                    settings=settings,
                    reason=f"Spam burst ({len(bucket)}/{int(settings.get('spam_message_limit') or 7)})",
                )

        if settings.get("anti_mass_mention_enabled"):
            mention_total = len(message.mentions) + len(message.role_mentions)
            if mention_total >= int(settings.get("mass_mention_limit") or 5):
                return await self._extra_protection_apply_action(
                    message,
                    settings=settings,
                    reason=f"Mass mention ({mention_total})",
                )

        if settings.get("delete_discord_invite_enabled"):
            if EXTRA_PROTECTION_DISCORD_INVITE_RE.search(content):
                return await self._extra_protection_apply_action(
                    message,
                    settings=settings,
                    reason="Discord invite links are blocked",
                )

        if settings.get("delete_scam_links_enabled"):
            urls = _promote_extract_urls(content)
            for raw_url in urls:
                url_lower = str(raw_url or "").lower()
                if any(pattern in url_lower for pattern in EXTRA_PROTECTION_SCAM_PATTERNS):
                    return await self._extra_protection_apply_action(
                        message,
                        settings=settings,
                        reason="Scam/phishing link pattern detected",
                    )

        if settings.get("anti_virus_keywords_enabled"):
            custom_keywords = [
                str(item or "").strip().lower()
                for item in settings.get("custom_virus_keywords", [])
                if str(item or "").strip()
            ]
            keyword_pool = list(EXTRA_PROTECTION_DEFAULT_VIRUS_KEYWORDS) + custom_keywords
            for keyword in keyword_pool:
                if keyword and keyword in content_lower:
                    return await self._extra_protection_apply_action(
                        message,
                        settings=settings,
                        reason=f"Blocked keyword: {keyword}",
                    )

        nsfw_image_detected = await self._check_nsfw_image_message(
            message,
            settings=settings,
        )
        if nsfw_image_detected:
            return True
        return False

    @staticmethod
    def _honeypot_config_key(guild_id: int) -> str:
        return f"{HONEYPOT_CONFIG_KEY_PREFIX}{int(guild_id)}"

    def _get_honeypot_config_lock(self, guild_id: int) -> asyncio.Lock:
        key = str(int(guild_id))
        lock = self.honeypot_config_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self.honeypot_config_locks[key] = lock
        return lock

    async def _get_honeypot_settings(
        self,
        guild_id: int,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        cache_key = str(int(guild_id))
        now_ts = time.time()
        cached = self.honeypot_settings_cache.get(cache_key)
        expire_at = float(self.honeypot_settings_expire.get(cache_key, 0.0) or 0.0)
        if (not force_refresh) and cached is not None and now_ts < expire_at:
            return cached

        settings = _default_honeypot_settings_local()
        try:
            row = await storage.dashboard_config.get(
                config_key=self._honeypot_config_key(guild_id)
            )
            if row and isinstance(row, dict):
                raw_value = str(row.get("config_value") or "").strip()
                if raw_value:
                    decoded = json.loads(raw_value)
                    if isinstance(decoded, dict):
                        settings = _normalize_honeypot_settings_local(decoded)
        except Exception:
            settings = _default_honeypot_settings_local()

        self.honeypot_settings_cache[cache_key] = settings
        self.honeypot_settings_expire[cache_key] = now_ts + self.honeypot_cache_ttl_seconds
        return settings

    async def _save_honeypot_settings(
        self,
        guild_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = _normalize_honeypot_settings_local(payload)
        encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        async with self._get_honeypot_config_lock(guild_id):
            existing = None
            try:
                existing = await storage.dashboard_config.get(
                    config_key=self._honeypot_config_key(guild_id)
                )
            except Exception:
                existing = None
            if existing:
                await storage.dashboard_config.update(
                    id=existing["id"],
                    config_value=encoded,
                )
            else:
                await storage.dashboard_config.insert(
                    config_key=self._honeypot_config_key(guild_id),
                    config_value=encoded,
                )
            cache_key = str(int(guild_id))
            self.honeypot_settings_cache[cache_key] = normalized
            self.honeypot_settings_expire[cache_key] = time.time() + self.honeypot_cache_ttl_seconds
        return normalized

    async def _increment_honeypot_stats(
        self,
        guild_id: int,
        *,
        deleted_messages: int = 0,
        timeouts: int = 0,
        kicks: int = 0,
        bans: int = 0,
    ) -> dict[str, Any]:
        async with self._get_honeypot_config_lock(guild_id):
            current = await self._get_honeypot_settings(guild_id, force_refresh=True)
            merged = dict(current)
            merged["deleted_message_count"] = max(
                0,
                int(merged.get("deleted_message_count") or 0) + max(0, int(deleted_messages or 0)),
            )
            merged["timeout_count"] = max(
                0,
                int(merged.get("timeout_count") or 0) + max(0, int(timeouts or 0)),
            )
            merged["kick_count"] = max(
                0,
                int(merged.get("kick_count") or 0) + max(0, int(kicks or 0)),
            )
            merged["ban_count"] = max(
                0,
                int(merged.get("ban_count") or 0) + max(0, int(bans or 0)),
            )
            normalized = _normalize_honeypot_settings_local(merged)
            encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
            existing = None
            try:
                existing = await storage.dashboard_config.get(
                    config_key=self._honeypot_config_key(guild_id)
                )
            except Exception:
                existing = None
            if existing:
                await storage.dashboard_config.update(
                    id=existing["id"],
                    config_value=encoded,
                )
            else:
                await storage.dashboard_config.insert(
                    config_key=self._honeypot_config_key(guild_id),
                    config_value=encoded,
                )
            cache_key = str(int(guild_id))
            self.honeypot_settings_cache[cache_key] = normalized
            self.honeypot_settings_expire[cache_key] = time.time() + self.honeypot_cache_ttl_seconds
            return normalized

    def _honeypot_action_total(self, settings: dict[str, Any] | None) -> int:
        payload = settings if isinstance(settings, dict) else {}
        return (
            max(0, int(payload.get("timeout_count") or 0))
            + max(0, int(payload.get("kick_count") or 0))
            + max(0, int(payload.get("ban_count") or 0))
        )

    def _honeypot_timeout_days(self, settings: dict[str, Any] | None) -> int:
        payload = settings if isinstance(settings, dict) else {}
        seconds = max(60, int(payload.get("timeout_seconds") or 604800))
        return max(1, seconds // 86400)

    def _honeypot_embed_edit_cooldown_seconds(self, settings: dict[str, Any] | None) -> int:
        payload = settings if isinstance(settings, dict) else {}
        try:
            return max(
                120,
                min(300, int(payload.get("status_edit_cooldown_seconds") or 120)),
            )
        except Exception:
            return 120

    def _honeypot_plan_allows(self, guild_id: int) -> bool:
        guild_plan = cache.guilds.get(str(guild_id), {}).get("subscription", "free")
        return _is_plan_at_least_local(guild_plan, "golden")

    async def _member_has_honeypot_bypass(self, member: discord.Member) -> bool:
        member_id = int(getattr(member, "id", 0) or 0)
        if member_id <= 0:
            return False
        if self.bot.user and member_id == int(self.bot.user.id):
            return True
        guild_obj = getattr(member, "guild", None)
        owner_id = int(getattr(guild_obj, "owner_id", 0) or 0) if guild_obj else 0
        if owner_id > 0 and member_id == owner_id:
            return True
        try:
            if guild_obj and await checks.check_is_owner_raw(member, guild_obj):
                return True
        except Exception:
            pass
        perms = getattr(member, "guild_permissions", None)
        if perms and bool(
            perms.administrator
            or perms.manage_guild
            or perms.manage_channels
            or perms.manage_messages
            or perms.kick_members
            or perms.ban_members
            or perms.moderate_members
        ):
            return True
        return False

    async def _send_honeypot_enabled_embed(
        self,
        *,
        channel: discord.TextChannel,
        guild: discord.Guild,
        settings: dict[str, Any],
        actor: discord.abc.User | None = None,
    ) -> bool:
        payload = _normalize_honeypot_settings_local(settings)
        timeout_days = self._honeypot_timeout_days(payload)
        action_total = self._honeypot_action_total(payload)
        deleted_total = max(0, int(payload.get("deleted_message_count") or 0))
        timeout_total = max(0, int(payload.get("timeout_count") or 0))
        kick_total = max(0, int(payload.get("kick_count") or 0))
        ban_total = max(0, int(payload.get("ban_count") or 0))
        cooldown_minutes = max(
            2,
            min(5, int(self._honeypot_embed_edit_cooldown_seconds(payload) // 60)),
        )
        embed = discord.Embed(
            title="Honeypot Protection Active",
            description=(
                f"Channel: {channel.mention}\n"
                f"Timeout: **{timeout_days} day(s)**\n"
                f"Delete message: **{'On' if bool(payload.get('delete_message', True)) else 'Off'}**\n"
                f"Embed edit cooldown: **{cooldown_minutes} minute(s)**"
            ),
            color=color.red,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Action Stats",
            value=(
                f"Triggered: `{action_total}`\n"
                f"Deleted Messages: `{deleted_total}`\n"
                f"Timeout: `{timeout_total}` | Kick: `{kick_total}` | Ban: `{ban_total}`"
            ),
            inline=False,
        )
        if actor is not None:
            embed.set_footer(text=f"Configured by {actor.display_name} - SkylineBOT Honeypot")
        else:
            embed.set_footer(text="Auto-updated from honeypot action - SkylineBOT Honeypot")

        status_message = None
        status_message_id = str(payload.get("status_message_id") or "").strip()
        if status_message_id.isdigit():
            try:
                status_message = await channel.fetch_message(int(status_message_id))
            except Exception:
                status_message = None

        if status_message is not None:
            try:
                await status_message.edit(embed=embed)
                return True
            except Exception:
                status_message = None

        try:
            status_message = await channel.send(embed=embed)
        except Exception:
            return False

        try:
            await status_message.pin(reason=f"Honeypot status for guild {guild.id}")
        except Exception:
            pass

        if str(payload.get("status_message_id") or "") != str(status_message.id):
            merged = dict(payload)
            merged["status_message_id"] = str(status_message.id)
            try:
                await self._save_honeypot_settings(int(guild.id), merged)
            except Exception:
                pass
        return True

    async def _schedule_honeypot_embed_refresh(
        self,
        *,
        channel: discord.TextChannel,
        guild: discord.Guild,
        settings: dict[str, Any],
    ) -> None:
        guild_id = int(guild.id)
        payload = _normalize_honeypot_settings_local(settings)
        cooldown_seconds = self._honeypot_embed_edit_cooldown_seconds(payload)
        now_monotonic = time.monotonic()
        last_edit_monotonic = float(self.honeypot_embed_last_edit_at.get(guild_id, 0.0) or 0.0)
        wait_seconds = float(cooldown_seconds) - (now_monotonic - last_edit_monotonic)

        if wait_seconds <= 0:
            updated = await self._send_honeypot_enabled_embed(
                channel=channel,
                guild=guild,
                settings=payload,
                actor=None,
            )
            if updated:
                self.honeypot_embed_last_edit_at[guild_id] = time.monotonic()
            self.honeypot_embed_pending_rows.pop(guild_id, None)
            return

        delayed_payload = dict(payload)
        delayed_payload["channel_id"] = str(channel.id)
        self.honeypot_embed_pending_rows[guild_id] = delayed_payload
        existing_task = self.honeypot_embed_pending_tasks.get(guild_id)
        if existing_task and not existing_task.done():
            return

        async def _flush_delayed(delay_seconds: float) -> None:
            try:
                await asyncio.sleep(max(0.0, float(delay_seconds)))
                latest_payload = self.honeypot_embed_pending_rows.pop(guild_id, delayed_payload)
                latest_channel_id = str(latest_payload.get("channel_id") or "").strip()
                target_channel = guild.get_channel(int(latest_channel_id)) if latest_channel_id.isdigit() else channel
                if not isinstance(target_channel, discord.TextChannel):
                    return
                updated = await self._send_honeypot_enabled_embed(
                    channel=target_channel,
                    guild=guild,
                    settings=latest_payload,
                    actor=None,
                )
                if updated:
                    self.honeypot_embed_last_edit_at[guild_id] = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning(f"Honeypot delayed embed refresh failed in {guild.name}: {error}")
            finally:
                current_task = asyncio.current_task()
                if self.honeypot_embed_pending_tasks.get(guild_id) is current_task:
                    self.honeypot_embed_pending_tasks.pop(guild_id, None)

        self.honeypot_embed_pending_tasks[guild_id] = asyncio.create_task(_flush_delayed(wait_seconds))

    async def check_honeypot(self, message: discord.Message) -> bool:
        if message.guild is None:
            return False
        if not self._honeypot_plan_allows(int(message.guild.id)):
            return False

        settings = await self._get_honeypot_settings(int(message.guild.id))
        if not bool(settings.get("enabled")):
            return False
        configured_channel_id = str(settings.get("channel_id") or "").strip()
        if not configured_channel_id.isdigit():
            return False
        if int(message.channel.id) != int(configured_channel_id):
            return False

        member_obj = message.author if isinstance(message.author, discord.Member) else None
        if member_obj is not None and await self._member_has_honeypot_bypass(member_obj):
            return False

        actor_id = int(getattr(message.author, "id", 0) or 0)
        cooldown_key = f"{message.guild.id}:{actor_id}"
        now_ts = time.time()
        if actor_id > 0:
            last_action_ts = float(self.honeypot_action_cooldown.get(cooldown_key, 0.0) or 0.0)
            if (now_ts - last_action_ts) < 8.0:
                try:
                    if bool(settings.get("delete_message", True)):
                        await message.delete()
                except Exception:
                    pass
                return True
            self.honeypot_action_cooldown[cooldown_key] = now_ts

        deleted_message_count = 0
        if bool(settings.get("delete_message", True)):
            try:
                await message.delete()
                deleted_message_count = 1
            except Exception:
                pass

        timeout_seconds = max(60, int(settings.get("timeout_seconds") or 604800))
        timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=timeout_seconds)
        timeout_count = 0
        kick_count = 0
        ban_count = 0

        if member_obj is not None:
            try:
                await member_obj.timeout(
                    timeout_until,
                    reason="Honeypot: sent message in restricted anti-spam channel",
                )
                timeout_count = 1
            except Exception:
                try:
                    await message.guild.kick(
                        member_obj,
                        reason="Honeypot: timeout failed while handling restricted anti-spam channel",
                    )
                    kick_count = 1
                except Exception:
                    try:
                        await message.guild.ban(
                            member_obj,
                            reason="Honeypot: timeout+kick failed while handling restricted anti-spam channel",
                        )
                        ban_count = 1
                    except Exception:
                        pass
        else:
            try:
                await message.guild.ban(
                    message.author,
                    reason="Honeypot: unknown sender sent message in restricted anti-spam channel",
                )
                ban_count = 1
            except Exception:
                pass

        updated_settings = settings
        try:
            updated_settings = await self._increment_honeypot_stats(
                int(message.guild.id),
                deleted_messages=deleted_message_count,
                timeouts=timeout_count,
                kicks=kick_count,
                bans=ban_count,
            )
        except Exception as error:
            logger.warning(f"Honeypot stats update failed in {message.guild.name}: {error}")

        if isinstance(message.channel, discord.TextChannel):
            try:
                await self._schedule_honeypot_embed_refresh(
                    channel=message.channel,
                    guild=message.guild,
                    settings=updated_settings,
                )
            except Exception as error:
                logger.warning(f"Honeypot embed refresh failed in {message.guild.name}: {error}")
        return True

    def _promote_plan_tier_from_cache(self, guild_id: int) -> str:
        raw_plan = cache.guilds.get(str(guild_id), {}).get("subscription", "free")
        return _normalize_promote_plan_tier(raw_plan)

    async def _promote_plan_tier(self, guild_id: int) -> str:
        cached_tier = self._promote_plan_tier_from_cache(guild_id)
        try:
            subscription_row = await storage.bot_plan_subscriptions.get(guild_id=int(guild_id)) or {}
        except Exception:
            subscription_row = {}
        if not isinstance(subscription_row, dict):
            return cached_tier

        row_plan = _normalize_promote_plan_tier(subscription_row.get("current_plan"))
        row_status = str(subscription_row.get("status") or "").strip().lower()
        row_end = _coerce_utc_datetime_local(subscription_row.get("current_period_end"))
        if row_plan == "permanent":
            return "permanent"
        if row_plan != "free":
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if row_status in {"active", "grace", "awaiting_payment", "paused"}:
                if row_end is None or row_end > now_utc:
                    return row_plan
            elif row_end and row_end > now_utc:
                return row_plan
        return cached_tier

    def _promote_saved_messages(self, promote_data: dict[str, Any]) -> list[dict[str, Any]]:
        raw_items = promote_data.get("saved_messages") if isinstance(promote_data, dict) else []
        if not isinstance(raw_items, list):
            return []
        rows: list[dict[str, Any]] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            try:
                row_id = int(raw.get("id"))
            except Exception:
                continue
            attachments = raw.get("attachments")
            if not isinstance(attachments, list):
                attachments = []
            rows.append(
                {
                    "id": row_id,
                    "name": str(raw.get("name") or f"บันทึก #{row_id}")[:80],
                    "content": str(raw.get("content") or "")[:1800],
                    "attachments": [str(item).strip() for item in attachments if str(item).strip()][:5],
                    "invite_url": str(raw.get("invite_url") or "").strip() or None,
                    "created_by": str(raw.get("created_by") or "").strip(),
                    "created_at": int(raw.get("created_at") or int(time.time())),
                }
            )
        rows.sort(key=lambda row: int(row.get("id") or 0))
        return rows

    def _promote_extract_content_links(
        self,
        content: str,
        *,
        allowed_domains: list[str],
        allowed_urls: list[str],
        allow_unrestricted: bool = False,
    ) -> tuple[list[str], list[str]]:
        valid_urls: list[str] = []
        invalid_urls: list[str] = []
        for url in _promote_extract_urls(content):
            candidate = url if "://" in url else f"https://{url}"
            if _is_allowed_discord_invite_url_local(url) or _is_allowed_discord_invite_url_local(candidate):
                valid_urls.append(candidate)
                continue
            normalized = _normalize_promote_attachment_url_local(url)
            if normalized:
                valid_urls.append(normalized)
                continue
            if allow_unrestricted:
                normalized_custom = _normalize_promote_candidate_url_local(candidate) or ""
                if normalized_custom:
                    valid_urls.append(normalized_custom)
                    continue
                invalid_urls.append(url)
                continue
            if _is_allowed_promote_custom_url_local(candidate, allowed_domains, allowed_urls):
                normalized_custom = _normalize_promote_candidate_url_local(candidate) or candidate
                valid_urls.append(normalized_custom)
                continue
            invalid_urls.append(url)
        return valid_urls, invalid_urls

    def _promote_is_image_url(self, url: str) -> bool:
        clean_url = str(url or "").strip().lower().split("?", 1)[0].split("#", 1)[0]
        if not clean_url:
            return False
        if "/dashboard/assets/db/" in clean_url:
            return True
        return clean_url.endswith(
            (
                ".png",
                ".jpg",
                ".jpeg",
                ".jfif",
                ".pjp",
                ".pjpeg",
                ".gif",
                ".webp",
                ".bmp",
                ".tiff",
                ".tif",
                ".heic",
                ".heif",
                ".avif",
            )
        )

    def _promote_invite_code(self, url: str | None) -> str:
        raw = str(url or "").strip()
        if not raw:
            return ""
        normalized = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").lower()
        path_parts = [part for part in (parsed.path or "").split("/") if part]
        if host in {"discord.gg", "www.discord.gg"} and path_parts:
            return path_parts[0].lower()
        if host in {"discord.com", "www.discord.com"} and len(path_parts) >= 2 and path_parts[0].lower() == "invite":
            return path_parts[1].lower()
        return ""

    def _promote_pick_image_attachment(self, attachments: list[str], content: str) -> str | None:
        for link in attachments:
            if self._promote_is_image_url(link):
                return link
        for link in _promote_extract_urls(content):
            normalized = _normalize_promote_attachment_url_local(link) or (link if "://" in link else f"https://{link}")
            if self._promote_is_image_url(normalized):
                return normalized
        return None

    def _build_promote_queue_key(self, payload: dict[str, Any]) -> str:
        invite_code = self._promote_invite_code(str(payload.get("invite_url") or ""))
        if not invite_code:
            for link in _promote_extract_urls(str(payload.get("content") or "")):
                invite_code = self._promote_invite_code(link)
                if invite_code:
                    break
        if invite_code:
            return f"invite:{invite_code}"

        try:
            guild_id = int(payload.get("guild_id") or 0)
        except Exception:
            guild_id = 0
        content = " ".join(str(payload.get("content") or "").strip().split()).lower()
        attachments = sorted(
            {
                str(item).strip().lower()
                for item in list(payload.get("attachments") or [])[:5]
                if str(item).strip()
            }
        )
        base = f"{guild_id}|{content}|{'|'.join(attachments)}"
        digest = hashlib.sha1(base.encode("utf-8")).hexdigest()
        return f"payload:{digest}"

    def _promote_queue_delay_seconds(self, queue_size: int) -> float:
        pending = max(0, int(queue_size))
        if pending <= 8:
            return 0.0
        if pending <= 15:
            return random.uniform(20.0, 40.0)
        return random.uniform(60.0, 120.0)

    def _prepare_promote_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            guild_id = int(payload.get("guild_id") or 0)
        except Exception:
            guild_id = 0
        content = str(payload.get("content") or "").strip()[:1800]
        guild_obj = self.bot.get_guild(guild_id) if guild_id > 0 else None
        allowed_domains = _normalize_promote_allowed_domains_local(payload.get("allowed_domains") or [])
        allowed_urls = _normalize_promote_allowed_urls_local(payload.get("allowed_urls") or [])
        blocked_words = _normalize_promote_blocked_words_local(payload.get("blocked_words") or [])
        blocked_domains = _normalize_promote_allowed_domains_local(payload.get("blocked_domains") or [])
        blocked_urls = _normalize_promote_allowed_urls_local(payload.get("blocked_urls") or [])
        ownerbot_unrestricted = bool(payload.get("ownerbot_unrestricted"))
        invite_raw = str(payload.get("invite_url") or "").strip()
        invite_url: str | None = None
        if invite_raw and _is_allowed_discord_invite_url_local(invite_raw):
            invite_url = invite_raw if "://" in invite_raw else f"https://{invite_raw}"
        elif invite_raw:
            if ownerbot_unrestricted:
                invite_url = _normalize_promote_candidate_url_local(invite_raw) or None
            elif _is_allowed_promote_custom_url_local(invite_raw, allowed_domains, allowed_urls):
                invite_url = _normalize_promote_candidate_url_local(invite_raw) or None
        source_origin = str(payload.get("source_origin") or "").strip().lower()
        if source_origin not in {"web", "discord"}:
            source_origin = "unknown"
        try:
            source_channel_id = int(payload.get("source_channel_id") or 0)
        except Exception:
            source_channel_id = 0
        source_channel_name = str(payload.get("source_channel_name") or "").strip()[:140]
        author_label = str(payload.get("author_mention") or "Unknown").strip()[:180]
        author_name = str(payload.get("author_name") or "").strip()[:120]
        if not author_name:
            author_name = author_label
        guild_name = str(payload.get("guild_name") or "").strip()[:160]
        if not guild_name:
            guild_name = str(getattr(guild_obj, "name", "") or "").strip()[:160]
        if not guild_name:
            guild_name = f"Guild {guild_id}" if guild_id > 0 else "Unknown Guild"

        normalized_attachments: list[str] = []
        for raw in list(payload.get("attachments") or [])[:8]:
            candidate = str(raw or "").strip()
            if not candidate:
                continue
            normalized = _normalize_promote_attachment_url_local(candidate)
            if not normalized:
                continue
            if normalized in normalized_attachments:
                continue
            normalized_attachments.append(normalized)
            if len(normalized_attachments) >= 5:
                break

        prepared = {
            "guild_id": guild_id,
            "author_id": payload.get("author_id"),
            "author_name": author_name,
            "author_mention": author_label,
            "content": content,
            "attachments": normalized_attachments,
            "invite_url": invite_url,
            "content_links": _promote_extract_urls(content),
            "source_origin": source_origin,
            "source_channel_id": source_channel_id,
            "source_channel_name": source_channel_name,
            "guild_name": guild_name,
            "allowed_domains": allowed_domains,
            "allowed_urls": allowed_urls,
            "blocked_words": blocked_words,
            "blocked_domains": blocked_domains,
            "blocked_urls": blocked_urls,
            "ownerbot_unrestricted": ownerbot_unrestricted,
        }
        prepared["queue_key"] = self._build_promote_queue_key(prepared)
        return prepared

    async def _validate_prepared_promote_job(self, prepared: dict[str, Any]) -> tuple[bool, str, str]:
        try:
            guild_id = int(prepared.get("guild_id") or 0)
        except Exception:
            guild_id = 0
        if guild_id <= 0:
            return False, "ไม่พบกิลด์ปลายทาง", ""

        try:
            promote_config = await storage.promote_channels.get(guild_id=guild_id) or {}
        except Exception:
            promote_config = cache.promote_channels.get(str(guild_id), {}) or {}
        if not promote_config:
            return False, "ยังไม่ได้เปิดใช้งานระบบโปรโมตสำหรับกิลด์นี้", ""
        if not promote_config.get("submit_channel_id") or not promote_config.get("public_channel_id"):
            return False, "ยังไม่ได้ตั้งค่าห้องโปรโมตครบถ้วน", ""
        if not bool(promote_config.get("enabled", True)):
            return False, "ระบบโปรโมตถูกปิดใช้งานอยู่", ""

        try:
            suspension_map = await _promote_suspension_map_load_local()
        except Exception:
            suspension_map = {}
        suspension_reason = _promote_suspension_reason_local(guild_id, suspension_map)
        if suspension_reason:
            return False, suspension_reason, ""

        try:
            owner_policy = await _promote_owner_policy_load_local()
        except Exception:
            owner_policy = _default_promote_owner_policy_local()
        if not isinstance(owner_policy, dict):
            owner_policy = _default_promote_owner_policy_local()
        ownerbot_unrestricted = bool(prepared.get("ownerbot_unrestricted"))

        allowed_domains = _normalize_promote_allowed_domains_local(owner_policy.get("allowed_domains") or [])
        allowed_urls = _normalize_promote_allowed_urls_local(owner_policy.get("allowed_urls") or [])
        blocked_domains = _normalize_promote_allowed_domains_local(owner_policy.get("blocked_domains") or [])
        blocked_urls = _normalize_promote_allowed_urls_local(owner_policy.get("blocked_urls") or [])

        automod_data = cache.automod.get(str(guild_id), {}) or {}
        automod_words = automod_data.get("antibadwords_words", [])
        if isinstance(automod_words, str):
            try:
                automod_words = json.loads(automod_words)
            except Exception:
                automod_words = []
        blocked_word_pool = _promote_merge_blocked_words_local(
            PROMOTE_DEFAULT_BLOCKED_WORDS,
            automod_words,
            owner_policy.get("blocked_words") or [],
        )

        content = str(prepared.get("content") or "").strip()
        content_ok, content_reason = _validate_promote_content_local(content, blocked_word_pool)
        if not content_ok:
            return False, f"{i18n.tr('promote_badword_blocked', guild_id)} ({content_reason})", ""

        _content_links, invalid_content_links = self._promote_extract_content_links(
            content,
            allowed_domains=allowed_domains,
            allowed_urls=allowed_urls,
            allow_unrestricted=ownerbot_unrestricted,
        )
        if invalid_content_links:
            return False, f"ลิงก์ในข้อความไม่อยู่ใน allowlist: {invalid_content_links[0]}", ""

        if not ownerbot_unrestricted:
            blocked_links = _promote_find_blocked_urls_local(
                [
                    *list(prepared.get("attachments") or []),
                    *list(prepared.get("content_links") or []),
                    *([str(prepared.get('invite_url') or '').strip()] if str(prepared.get("invite_url") or "").strip() else []),
                ],
                blocked_domains=blocked_domains,
                blocked_urls=blocked_urls,
            )
            if blocked_links:
                return False, f"พบบล็อกลิงก์ต้องห้าม: {blocked_links[0]}", ""

        image_urls: list[str] = []
        for link in [*list(prepared.get("attachments") or []), *list(prepared.get("content_links") or [])]:
            candidate = str(link or "").strip()
            if not candidate or candidate in image_urls:
                continue
            if not self._promote_is_image_url(candidate):
                continue
            image_urls.append(candidate)
            if len(image_urls) >= 4:
                break
        image_ok, image_reason = await self.scan_promote_image_urls(
            guild_id,
            image_urls,
            source=str(prepared.get("source_origin") or "unknown"),
            blocked_words=blocked_word_pool,
        )
        if not image_ok:
            return False, image_reason or "รูปภาพไม่ผ่านการตรวจสอบความปลอดภัย", ""
        image_scan_warning = ""
        if image_reason:
            normalized = str(image_reason).strip()
            if normalized.lower().startswith("warn:"):
                image_scan_warning = normalized.split(":", 1)[1].strip()

        return True, "", image_scan_warning

    async def enqueue_promote_job(self, payload: dict[str, Any]) -> tuple[bool, int, str]:
        prepared = self._prepare_promote_job(payload or {})
        policy_ok, policy_reason, policy_warning = await self._validate_prepared_promote_job(prepared)
        if not policy_ok:
            return False, self.promote_queue.qsize(), f"policy_blocked:{policy_reason}"
        queue_key = str(prepared.get("queue_key") or "").strip()
        if queue_key and queue_key in self.promote_pending_keys:
            return False, self.promote_queue.qsize(), "duplicate"
        if queue_key:
            self.promote_pending_keys.add(queue_key)
        await self.promote_queue.put(prepared)
        try:
            try:
                history_author_id = int(prepared.get("author_id") or 0)
            except Exception:
                history_author_id = 0
            history_row = await storage.promote_history.insert(
                guild_id=int(prepared.get("guild_id") or 0),
                guild_name=str(prepared.get("guild_name") or "")[:160],
                source_origin=str(prepared.get("source_origin") or "unknown")[:20],
                source_channel_id=int(prepared.get("source_channel_id") or 0),
                source_channel_name=str(prepared.get("source_channel_name") or "")[:140],
                author_id=history_author_id,
                author_name=str(prepared.get("author_name") or "")[:120],
                author_label=str(prepared.get("author_mention") or "")[:180],
                content=str(prepared.get("content") or "")[:1800],
                invite_url=str(prepared.get("invite_url") or "")[:600],
                queue_key=str(prepared.get("queue_key") or "")[:120],
                attachments=list(prepared.get("attachments") or [])[:5],
                content_links=list(prepared.get("content_links") or [])[:8],
                status="queued",
            )
            if isinstance(history_row, dict):
                prepared["history_id"] = int(history_row.get("id") or 0)
                if int(prepared.get("history_id") or 0) > 0:
                    await self._promote_send_owner_review_card(
                        history_id=int(prepared.get("history_id") or 0)
                    )
        except Exception as error:
            logger.warning(f"Promote history insert failed: {error}")
        if policy_warning:
            return True, self.promote_queue.qsize(), f"queued_warn:{policy_warning}"
        return True, self.promote_queue.qsize(), "queued"

    def get_promote_queue_snapshot(self, *, limit: int = 25) -> dict[str, Any]:
        safe_limit = max(1, min(100, int(limit or 25)))
        try:
            raw_queue = list(getattr(self.promote_queue, "_queue", []))
        except Exception:
            raw_queue = []

        total_jobs = len(raw_queue)
        guild_counts: dict[int, int] = {}
        queue_rows: list[dict[str, Any]] = []
        for index, job in enumerate(raw_queue[:safe_limit], start=1):
            if not isinstance(job, dict):
                continue
            try:
                guild_id = int(job.get("guild_id") or 0)
            except Exception:
                guild_id = 0
            guild_counts[guild_id] = int(guild_counts.get(guild_id, 0)) + 1
            guild_obj = self.bot.get_guild(guild_id) if guild_id else None
            guild_name = getattr(guild_obj, "name", None) or (f"Guild {guild_id}" if guild_id else "Unknown Guild")
            content_preview = " ".join(str(job.get("content") or "").strip().split())
            if len(content_preview) > 88:
                content_preview = content_preview[:85].rstrip() + "..."
            queue_rows.append(
                {
                    "position": index,
                    "guild_id": guild_id,
                    "guild_name": guild_name,
                    "author": str(job.get("author_mention") or "Unknown"),
                    "content_preview": content_preview or "-",
                }
            )

        guild_rows: list[dict[str, Any]] = []
        for guild_id, count in sorted(guild_counts.items(), key=lambda item: (-int(item[1]), int(item[0]))):
            guild_obj = self.bot.get_guild(guild_id) if guild_id else None
            guild_name = getattr(guild_obj, "name", None) or (f"Guild {guild_id}" if guild_id else "Unknown Guild")
            guild_rows.append(
                {
                    "guild_id": guild_id,
                    "guild_name": guild_name,
                    "count": int(count),
                }
            )

        return {
            "total_jobs": total_jobs,
            "unique_guilds": len(guild_rows),
            "pending_keys": len(self.promote_pending_keys),
            "queue_rows": queue_rows,
            "guild_rows": guild_rows,
        }

    async def promote_web_queue_worker(self):
        while not self.bot.is_closed():
            try:
                rows = await storage.promote_web_queue.gets(status="pending")
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.warning(
                    "Promote web queue load failed | "
                    f"error={type(error).__name__}: {str(error)[:180]}"
                )
                await asyncio.sleep(5)
                continue

            pending_rows = list(rows or [])
            if not pending_rows:
                await asyncio.sleep(2)
                continue

            for row in pending_rows[:25]:
                row_id = int(row.get("id") or 0) if str(row.get("id") or "").isdigit() else 0
                if row_id <= 0:
                    continue
                attempts = int(row.get("attempts") or 0)
                payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
                if not payload:
                    try:
                        await storage.promote_web_queue.update(
                            id=row_id,
                            status="failed",
                            attempts=max(1, attempts),
                            error="payload_missing",
                            updated_at=datetime.datetime.now(datetime.timezone.utc),
                        )
                    except Exception:
                        pass
                    continue

                try:
                    queued, _queue_size, queue_status = await self.enqueue_promote_job(payload)
                    status_text = str(queue_status or "").strip().lower()
                    new_status = "dispatched"
                    error_text = ""
                    next_attempts = attempts + 1

                    if queued:
                        new_status = "dispatched"
                    elif status_text == "duplicate":
                        new_status = "duplicate"
                    elif status_text.startswith("policy_blocked:"):
                        new_status = "blocked"
                        error_text = status_text.split(":", 1)[1].strip()
                    else:
                        if next_attempts >= 5:
                            new_status = "failed"
                            error_text = status_text or "enqueue_failed"
                        else:
                            new_status = "pending"
                            error_text = status_text or "retry_pending"

                    await storage.promote_web_queue.update(
                        id=row_id,
                        status=new_status,
                        attempts=next_attempts,
                        error=error_text[:300],
                        updated_at=datetime.datetime.now(datetime.timezone.utc),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    next_attempts = attempts + 1
                    try:
                        await storage.promote_web_queue.update(
                            id=row_id,
                            status=("failed" if next_attempts >= 5 else "pending"),
                            attempts=next_attempts,
                            error=f"{type(error).__name__}: {str(error)[:220]}",
                            updated_at=datetime.datetime.now(datetime.timezone.utc),
                        )
                    except Exception:
                        pass
                    logger.warning(
                        "Promote web queue dispatch failed | "
                        f"row={row_id} guild={payload.get('guild_id')} "
                        f"error={type(error).__name__}: {str(error)[:180]}"
                    )

            await asyncio.sleep(1.5)

    async def _promote_owner_can_manage(self, interaction: discord.Interaction) -> bool:
        user = getattr(interaction, "user", None)
        guild = getattr(interaction, "guild", None)
        try:
            if user and getattr(getattr(user, "guild_permissions", None), "administrator", False):
                return True
        except Exception:
            pass
        try:
            return bool(await checks.check_is_owner_raw(user, guild))
        except Exception:
            return False

    def _promote_owner_review_embed(self, row: dict[str, Any], *, suspension_reason: str = "") -> discord.Embed:
        history_id = int(row.get("id") or 0)
        guild_id = int(row.get("guild_id") or 0)
        guild_name = str(row.get("guild_name") or f"Guild {guild_id}").strip() or f"Guild {guild_id}"
        source_origin = str(row.get("source_origin") or "unknown").strip().lower()
        source_label = "Discord" if source_origin == "discord" else ("Web" if source_origin == "web" else "Unknown")
        source_channel_name = str(row.get("source_channel_name") or "").strip() or "-"
        source_channel_id = int(row.get("source_channel_id") or 0)
        author_label = str(row.get("author_label") or row.get("author_name") or "Unknown").strip()
        content = str(row.get("content") or "").strip()
        owner_note = str(row.get("owner_note") or "").strip()
        hidden = bool(row.get("hidden"))

        description = owner_note if hidden and owner_note else (content[:3800] if content else "-")
        embed = discord.Embed(
            title=f"Promote Review #{history_id}",
            description=description,
            color=(discord.Color.orange() if hidden else discord.Color.blurple()),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        status_text = str(row.get("status") or "unknown").strip()
        if hidden:
            status_text = f"{status_text} | hidden"
        if suspension_reason:
            status_text = f"{status_text} | suspended"
        embed.add_field(name="Status", value=status_text[:1024] or "-", inline=False)
        embed.add_field(name="Guild", value=f"{guild_name}\n`{guild_id or '-'}`", inline=True)
        embed.add_field(name="Author", value=(author_label[:1024] or "Unknown"), inline=True)
        embed.add_field(
            name="Source",
            value=f"{source_label}\n{source_channel_name} ({source_channel_id or '-'})",
            inline=False,
        )
        if owner_note:
            embed.add_field(name="Owner Note", value=owner_note[:1024], inline=False)
        if suspension_reason:
            embed.add_field(name="Suspension", value=suspension_reason[:1024], inline=False)

        invite_url = str(row.get("invite_url") or "").strip()
        content_links = [str(item).strip() for item in list(row.get("content_links") or []) if str(item).strip()]
        attachments = [str(item).strip() for item in list(row.get("attachments") or []) if str(item).strip()]
        links: list[str] = []
        if invite_url:
            links.append(invite_url)
        for link in [*content_links, *attachments]:
            if link and link not in links:
                links.append(link)
        if links and not hidden:
            embed.add_field(
                name="Links",
                value="\n".join(links[:6])[:1024],
                inline=False,
            )
        if not hidden:
            image_url = self._promote_pick_image_attachment(attachments, content)
            if image_url:
                embed.set_image(url=image_url)
        embed.set_footer(text=f"History ID {history_id}")
        return embed

    def _build_promote_owner_review_view(self, history_id: int, guild_id: int) -> discord.ui.View:
        cog = self

        class _OwnerEditModal(discord.ui.Modal, title="Edit Promote"):
            content = discord.ui.TextInput(
                label="Content",
                style=discord.TextStyle.paragraph,
                max_length=1800,
                required=True,
            )
            note = discord.ui.TextInput(
                label="Owner Note (optional)",
                style=discord.TextStyle.paragraph,
                max_length=600,
                required=False,
            )

            def __init__(self, *, current_content: str, current_note: str):
                super().__init__(timeout=300)
                self.content.default = str(current_content or "")[:1800]
                self.note.default = str(current_note or "")[:600]

            async def on_submit(self, interaction: discord.Interaction):
                if not await cog._promote_owner_can_manage(interaction):
                    await interaction.response.send_message("OwnerBOT only", ephemeral=True)
                    return
                actor_id = int(getattr(interaction.user, "id", 0) or 0)
                actor_name = str(getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "OwnerBOT")).strip()[:120]
                await storage.promote_history.update(
                    id=history_id,
                    content=str(self.content.value or "").strip()[:1800],
                    hidden=False,
                    owner_note=str(self.note.value or "").strip()[:600],
                    owner_action_by_id=actor_id,
                    owner_action_by_name=actor_name,
                    owner_action_at=datetime.datetime.now(datetime.timezone.utc),
                )
                await cog._promote_sync_owner_review_card_by_history_id(history_id)
                await interaction.response.send_message("Updated promote history", ephemeral=True)

        class _OwnerHideModal(discord.ui.Modal, title="Hide Promote Content"):
            note = discord.ui.TextInput(
                label="Owner Note",
                style=discord.TextStyle.paragraph,
                max_length=600,
                required=True,
            )

            def __init__(self, *, current_note: str):
                super().__init__(timeout=300)
                self.note.default = str(current_note or "")[:600]

            async def on_submit(self, interaction: discord.Interaction):
                if not await cog._promote_owner_can_manage(interaction):
                    await interaction.response.send_message("OwnerBOT only", ephemeral=True)
                    return
                actor_id = int(getattr(interaction.user, "id", 0) or 0)
                actor_name = str(getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "OwnerBOT")).strip()[:120]
                await storage.promote_history.update(
                    id=history_id,
                    hidden=True,
                    owner_note=str(self.note.value or "").strip()[:600],
                    owner_action_by_id=actor_id,
                    owner_action_by_name=actor_name,
                    owner_action_at=datetime.datetime.now(datetime.timezone.utc),
                )
                await cog._promote_sync_owner_review_card_by_history_id(history_id)
                await interaction.response.send_message("Hidden promote content", ephemeral=True)

        view = discord.ui.View(timeout=86400)

        async def _load_row() -> dict[str, Any]:
            row = await storage.promote_history.get(id=history_id)
            return row if isinstance(row, dict) else {}

        edit_button = discord.ui.Button(label="Edit", style=discord.ButtonStyle.primary)
        hide_button = discord.ui.Button(label="Hide + Note", style=discord.ButtonStyle.secondary)
        unhide_button = discord.ui.Button(label="Unhide", style=discord.ButtonStyle.secondary)
        suspend_button = discord.ui.Button(label="Suspend Toggle", style=discord.ButtonStyle.danger)
        delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger)

        async def _edit_callback(interaction: discord.Interaction):
            if not await cog._promote_owner_can_manage(interaction):
                await interaction.response.send_message("OwnerBOT only", ephemeral=True)
                return
            row = await _load_row()
            await interaction.response.send_modal(
                _OwnerEditModal(
                    current_content=str(row.get("content") or ""),
                    current_note=str(row.get("owner_note") or ""),
                )
            )

        async def _hide_callback(interaction: discord.Interaction):
            if not await cog._promote_owner_can_manage(interaction):
                await interaction.response.send_message("OwnerBOT only", ephemeral=True)
                return
            row = await _load_row()
            await interaction.response.send_modal(
                _OwnerHideModal(current_note=str(row.get("owner_note") or ""))
            )

        async def _unhide_callback(interaction: discord.Interaction):
            if not await cog._promote_owner_can_manage(interaction):
                await interaction.response.send_message("OwnerBOT only", ephemeral=True)
                return
            actor_id = int(getattr(interaction.user, "id", 0) or 0)
            actor_name = str(getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "OwnerBOT")).strip()[:120]
            await storage.promote_history.update(
                id=history_id,
                hidden=False,
                owner_action_by_id=actor_id,
                owner_action_by_name=actor_name,
                owner_action_at=datetime.datetime.now(datetime.timezone.utc),
            )
            await cog._promote_sync_owner_review_card_by_history_id(history_id)
            await interaction.response.send_message("Unhidden promote content", ephemeral=True)

        async def _suspend_callback(interaction: discord.Interaction):
            if not await cog._promote_owner_can_manage(interaction):
                await interaction.response.send_message("OwnerBOT only", ephemeral=True)
                return
            actor_name = str(getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "OwnerBOT")).strip()[:120]
            row = await _load_row()
            guild_id_local = int(row.get("guild_id") or guild_id or 0)
            if guild_id_local <= 0:
                await interaction.response.send_message("Guild id not found", ephemeral=True)
                return
            suspension_map = await _promote_suspension_map_load_local()
            key = str(guild_id_local)
            note = str(row.get("owner_note") or "").strip()[:600]
            if key in suspension_map:
                suspension_map.pop(key, None)
                action_text = f"Unsuspended guild {guild_id_local}"
            else:
                suspension_map[key] = {
                    "note": note,
                    "by_name": actor_name,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                action_text = f"Suspended guild {guild_id_local}"
            await _promote_suspension_map_save_local(suspension_map)
            await cog._promote_sync_owner_review_card_by_history_id(history_id)
            await interaction.response.send_message(action_text, ephemeral=True)

        async def _delete_callback(interaction: discord.Interaction):
            if not await cog._promote_owner_can_manage(interaction):
                await interaction.response.send_message("OwnerBOT only", ephemeral=True)
                return
            actor_name = str(getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "OwnerBOT")).strip()[:120]
            row = await _load_row()
            if not row:
                await interaction.response.send_message("Promote history not found", ephemeral=True)
                return
            await storage.promote_history.delete(id=history_id)
            await cog._promote_sync_owner_review_card_by_history_id(
                history_id,
                deleted=True,
                deleted_snapshot=row,
                deleted_by=actor_name,
            )
            await interaction.response.send_message("Deleted promote history", ephemeral=True)

        edit_button.callback = _edit_callback
        hide_button.callback = _hide_callback
        unhide_button.callback = _unhide_callback
        suspend_button.callback = _suspend_callback
        delete_button.callback = _delete_callback

        view.add_item(edit_button)
        view.add_item(hide_button)
        view.add_item(unhide_button)
        view.add_item(suspend_button)
        view.add_item(delete_button)
        return view

    async def _promote_sync_owner_review_card_by_history_id(
        self,
        history_id: int,
        *,
        deleted: bool = False,
        deleted_snapshot: dict[str, Any] | None = None,
        deleted_by: str = "",
    ) -> None:
        row = deleted_snapshot if deleted else await storage.promote_history.get(id=history_id)
        if not isinstance(row, dict):
            return
        channel_id = int(row.get("owner_channel_id") or 0)
        message_id = int(row.get("owner_message_id") or 0)
        if channel_id <= 0 or message_id <= 0:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return
        try:
            review_message = await channel.fetch_message(message_id)
        except Exception:
            return

        if deleted:
            try:
                await review_message.edit(
                    embed=discord.Embed(
                        title=f"Promote Review #{history_id}",
                        description=f"Deleted by {deleted_by or 'OwnerBOT'}",
                        color=discord.Color.red(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    ),
                    view=None,
                )
            except Exception:
                return
            return

        suspension_map = await _promote_suspension_map_load_local()
        suspension_reason = _promote_suspension_reason_local(int(row.get("guild_id") or 0), suspension_map)
        embed = self._promote_owner_review_embed(row, suspension_reason=suspension_reason)
        view = self._build_promote_owner_review_view(history_id, int(row.get("guild_id") or 0))
        try:
            await review_message.edit(embed=embed, view=view)
        except Exception:
            return

    async def _promote_send_owner_review_card(self, *, history_id: int) -> None:
        if history_id <= 0:
            return
        row = await storage.promote_history.get(id=history_id)
        if not isinstance(row, dict):
            return
        existing_owner_channel_id = int(row.get("owner_channel_id") or 0)
        existing_owner_message_id = int(row.get("owner_message_id") or 0)
        if existing_owner_channel_id > 0 and existing_owner_message_id > 0:
            await self._promote_sync_owner_review_card_by_history_id(history_id)
            return

        channel_id = int(PROMOTE_OWNER_REVIEW_CHANNEL_ID or 0)
        if channel_id <= 0:
            return
        review_channel = self.bot.get_channel(channel_id)
        if not review_channel:
            try:
                review_channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return
        if not review_channel:
            return
        suspension_map = await _promote_suspension_map_load_local()
        suspension_reason = _promote_suspension_reason_local(int(row.get("guild_id") or 0), suspension_map)
        embed = self._promote_owner_review_embed(row, suspension_reason=suspension_reason)
        view = self._build_promote_owner_review_view(history_id, int(row.get("guild_id") or 0))
        try:
            sent = await review_channel.send(embed=embed, view=view)
        except Exception:
            return
        try:
            await storage.promote_history.update(
                id=history_id,
                owner_channel_id=int(getattr(review_channel, "id", 0) or 0),
                owner_message_id=int(getattr(sent, "id", 0) or 0),
            )
        except Exception:
            return

    async def _save_promote_template(
        self,
        *,
        promote_data: dict[str, Any],
        guild_id: int,
        user_id: int,
        content: str,
        attachments: list[str],
        invite_url: str | None,
        name: str,
    ) -> tuple[bool, str]:
        tier = await self._promote_plan_tier(guild_id)
        limit = _promote_saved_limit_for_plan(tier)
        if limit <= 0:
            return False, "แพ็กเกจ Free ยังบันทึกโปรโมตไม่ได้"

        saved = self._promote_saved_messages(promote_data)
        if len(saved) >= limit:
            return False, f"ลิมิตรายการบันทึกเต็มแล้ว ({len(saved)}/{limit})"

        next_id = (max((int(item.get("id") or 0) for item in saved), default=0) + 1) if saved else 1
        final_name = str(name or "").strip()[:80] or f"บันทึก #{next_id}"
        saved.append(
            {
                "id": next_id,
                "name": final_name,
                "content": str(content or "")[:1800],
                "attachments": [str(item).strip() for item in (attachments or []) if str(item).strip()][:5],
                "invite_url": str(invite_url or "").strip() or None,
                "created_by": str(user_id),
                "created_at": int(time.time()),
            }
        )
        await storage.promote_channels.update(id=promote_data.get("id"), saved_messages=saved)
        promote_data["saved_messages"] = saved
        return True, f"บันทึกโปรโมตแล้ว: `{final_name}` ({len(saved)}/{limit})"

    async def check_for_afk(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        try:

            if message.author.bot:

                return

            if not message.guild:

                return

            global_afk = cache.afk.get("global", {}).get(str(message.author.id), {})

            if global_afk:

                await storage.afk.delete(user_id=message.author.id)

                created_at: datetime.datetime = global_afk.get("created_at")

                embed = discord.Embed(
                    description=f"**You are no longer Globally AFK**", color=color.green
                )

                was_afk_for_seconds = (
                    datetime.datetime.now(tz=datetime.timezone.utc) - created_at
                ).total_seconds()

                def fetch_seconds(seconds):

                    hours, remainder = divmod(seconds, 3600)

                    minutes, seconds = divmod(remainder, 60)

                    return int(hours), int(minutes), int(seconds)

                hours, minutes, seconds = fetch_seconds(was_afk_for_seconds)

                was_afk_for = ""

                if hours:

                    was_afk_for += f"{hours} hours "

                if minutes:

                    was_afk_for += f"{minutes} minutes "

                if seconds:

                    was_afk_for += f"{seconds} seconds "

                embed.set_footer(
                    text=f"Was afk for: {was_afk_for}",
                )

                await message.reply(embed=embed)

            guild_afk = (
                cache.afk.get("guilds", {})
                .get(str(message.guild.id), {})
                .get(str(message.author.id), {})
            )

            if guild_afk:

                await storage.afk.delete(
                    guild_id=message.guild.id, user_id=message.author.id
                )

                created_at: datetime.datetime = guild_afk.get("created_at").astimezone()

                embed = discord.Embed(
                    description=f"**You are no longer AFK in this server**",
                    color=color.green,
                )

                was_afk_for_seconds = (
                    datetime.datetime.now().astimezone() - created_at
                ).total_seconds()

                def fetch_seconds(seconds):

                    hours, remainder = divmod(seconds, 3600)

                    minutes, seconds = divmod(remainder, 60)

                    return int(hours), int(minutes), int(seconds)

                hours, minutes, seconds = fetch_seconds(was_afk_for_seconds)

                was_afk_for = ""

                if hours:

                    was_afk_for += f"{hours} hours "

                if minutes:

                    was_afk_for += f"{minutes} minutes "

                if seconds:

                    was_afk_for += f"{seconds} seconds "

                embed.set_footer(
                    text=f"Was afk for: {was_afk_for}",
                )

                await message.reply(embed=embed)

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    async def promote_queue_worker(self):
        while not self.bot.is_closed():
            job = await self.promote_queue.get()
            queue_key = str(job.get("queue_key") or "").strip()
            history_id = int(job.get("history_id") or 0) if isinstance(job, dict) else 0
            try:
                promote_rows = await storage.promote_channels.get_all()
                source_guild = self.bot.get_guild(job.get("guild_id"))
                source_name = source_guild.name if source_guild else f"Guild {job.get('guild_id')}"
                source_icon = None
                if source_guild and source_guild.icon:
                    source_icon = source_guild.icon.url
                target_guild_ids: set[int] = set()
                target_channel_ids: set[int] = set()
                dispatch_count = 0
                attachments = list(job.get("attachments") or [])
                content = str(job.get("content") or "")
                image_attachment = self._promote_pick_image_attachment(attachments, content)
                invite_url = str(job.get("invite_url") or "").strip() or None
                embed_image_url = image_attachment
                embed_image_payload = b""
                embed_image_filename = ""
                if image_attachment:
                    embed_image_payload, embed_image_content_type = await self._download_image_bytes_for_moderation(
                        image_attachment,
                        max_bytes=8 * 1024 * 1024,
                    )
                    if embed_image_payload:
                        embed_image_filename = self._promote_moderation_image_filename(
                            image_attachment,
                            embed_image_content_type,
                        )
                        embed_image_filename = self._sanitize_discord_attachment_filename(
                            embed_image_filename,
                            fallback="promote_image.png",
                        )
                        embed_image_url = f"attachment://{embed_image_filename}"
                    elif self._is_discord_cdn_attachment_url(image_attachment):
                        embed_image_url = None

                for row in promote_rows:
                    public_channel_id = row.get("public_channel_id")
                    if not public_channel_id:
                        continue
                    channel = self.bot.get_channel(int(public_channel_id))
                    if not channel:
                        continue
                    target_guild_id = getattr(getattr(channel, "guild", None), "id", None)
                    embed = discord.Embed(
                        title=i18n.tr("promote_broadcast_title", target_guild_id),
                        description=content[:1800] or "-",
                        color=color.blue,
                        timestamp=datetime.datetime.now(datetime.timezone.utc),
                    )
                    embed.add_field(
                        name=i18n.tr("promote_broadcast_from", target_guild_id),
                        value=source_name,
                        inline=False,
                    )
                    embed.add_field(
                        name=i18n.tr("promote_broadcast_author", target_guild_id),
                        value=job.get("author_mention", "Unknown"),
                        inline=True,
                    )
                    if attachments:
                        non_image_attachments = [a for a in attachments if a != image_attachment]
                        if non_image_attachments:
                            embed.add_field(
                                name=i18n.tr("promote_broadcast_attachments", target_guild_id),
                                value="\n".join(non_image_attachments[:5]),
                                inline=False,
                            )

                    if source_icon:
                        embed.set_thumbnail(url=source_icon)
                    if embed_image_url:
                        embed.set_image(url=embed_image_url)
                    embed.set_footer(
                        text=i18n.tr("promote_broadcast_footer", target_guild_id),
                        icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
                    )

                    view = discord.ui.View(timeout=600)
                    if invite_url:
                        view.add_item(
                            discord.ui.Button(
                                label=i18n.tr("promote_btn_open_server", target_guild_id),
                                style=discord.ButtonStyle.link,
                                url=invite_url,
                            )
                        )
                        copy_invite_button = discord.ui.Button(
                            label=i18n.tr("promote_btn_copy_invite", target_guild_id),
                            style=discord.ButtonStyle.secondary,
                        )

                        async def copy_invite_callback(interaction: discord.Interaction, _invite=invite_url, _gid=target_guild_id):
                            try:
                                await interaction.response.send_message(
                                    i18n.tr("promote_copy_invite_reply", _gid, invite=_invite),
                                    ephemeral=True,
                                )
                            except Exception:
                                pass

                        copy_invite_button.callback = copy_invite_callback
                        view.add_item(copy_invite_button)

                    view.add_item(
                        discord.ui.Button(
                            label=i18n.tr("promote_btn_invite_bot", target_guild_id),
                            style=discord.ButtonStyle.link,
                            url=self.bot.urls.INVITE,
                        )
                    )
                    view.add_item(
                        discord.ui.Button(
                            label=i18n.tr("promote_btn_support", target_guild_id),
                            style=discord.ButtonStyle.link,
                            url=self.bot.urls.SUPPORT_SERVER,
                        )
                    )
                    view.add_item(
                        discord.ui.Button(
                            label=i18n.tr("promote_btn_vote", target_guild_id),
                            style=discord.ButtonStyle.link,
                            url=self.bot.urls.VOTE,
                        )
                    )

                    try:
                        send_kwargs: dict[str, Any] = {
                            "embed": discord.Embed.from_dict(embed.to_dict()),
                            "view": view,
                        }
                        if embed_image_payload and embed_image_filename:
                            send_kwargs["file"] = discord.File(
                                io.BytesIO(embed_image_payload),
                                filename=embed_image_filename,
                            )
                        await channel.send(**send_kwargs)
                    except Exception:
                        continue
                    dispatch_count += 1
                    if target_guild_id:
                        target_guild_ids.add(int(target_guild_id))
                    try:
                        target_channel_ids.add(int(getattr(channel, "id", 0) or 0))
                    except Exception:
                        pass
                    await asyncio.sleep(0.25)

                if history_id > 0:
                    await storage.promote_history.update(
                        id=history_id,
                        status="dispatched",
                        dispatch_count=int(dispatch_count),
                        target_guild_count=len(target_guild_ids),
                        target_guild_ids=sorted([gid for gid in target_guild_ids if int(gid) > 0])[:300],
                        target_channel_ids=sorted([cid for cid in target_channel_ids if int(cid) > 0])[:500],
                        dispatched_at=datetime.datetime.now(datetime.timezone.utc),
                    )
                    await self._promote_send_owner_review_card(history_id=history_id)

                pending_jobs = self.promote_queue.qsize()
                delay_seconds = self._promote_queue_delay_seconds(pending_jobs)
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if history_id > 0:
                    try:
                        await storage.promote_history.update(
                            id=history_id,
                            status="failed",
                            dispatched_at=datetime.datetime.now(datetime.timezone.utc),
                        )
                        await self._promote_send_owner_review_card(history_id=history_id)
                    except Exception:
                        pass
                logger.error(
                    f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                )
            finally:
                if queue_key:
                    self.promote_pending_keys.discard(queue_key)
                self.promote_queue.task_done()

    async def promote_message_module(self, message: discord.Message):
        if message.author.bot:
            return False
        if not message.guild:
            return False

        cached_promote_data = cache.promote_channels.get(str(message.guild.id), {}) or {}
        try:
            promote_data = await storage.promote_channels.get(guild_id=message.guild.id)
        except Exception as error:
            logger.warning(
                "Promote config load failed from storage; fallback to cache | "
                f"guild={message.guild.id} error={type(error).__name__}: {str(error)[:180]}"
            )
            promote_data = cached_promote_data
        if not promote_data and cached_promote_data:
            promote_data = cached_promote_data
        if not promote_data:
            return False
        if not bool(promote_data.get("enabled", True)):
            return False

        submit_channel_id = promote_data.get("submit_channel_id")
        try:
            submit_channel_id = int(submit_channel_id) if submit_channel_id else None
        except (TypeError, ValueError):
            submit_channel_id = None

        message_channel_id = int(getattr(message.channel, "id", 0) or 0)
        parent_channel_id = int(
            getattr(getattr(message.channel, "parent", None), "id", 0) or 0
        )
        if (
            not submit_channel_id
            or (
                message_channel_id != int(submit_channel_id)
                and parent_channel_id != int(submit_channel_id)
            )
        ):
            if int(submit_channel_id or 0) > 0 and (
                message.author.guild_permissions.administrator
                or message.author.guild_permissions.manage_guild
            ):
                logger.info(
                    "Promote ignored due to submit channel mismatch | "
                    f"guild={message.guild.id} expected={int(submit_channel_id)} "
                    f"actual={message_channel_id} parent={parent_channel_id} "
                    f"author={message.author.id}"
                )
            return False

        bot_member = message.guild.me or message.guild.get_member(getattr(self.bot.user, "id", 0))
        if not bot_member:
            return False
        channel_perms = message.channel.permissions_for(bot_member)
        channel_type = str(getattr(message.channel, "type", "") or "").lower()
        is_thread_channel = channel_type in {"public_thread", "private_thread", "news_thread"}
        can_send_messages = bool(getattr(channel_perms, "send_messages", False))
        if is_thread_channel:
            can_send_messages = can_send_messages or bool(
                getattr(channel_perms, "send_messages_in_threads", False)
            )
        if not getattr(channel_perms, "view_channel", False):
            return False
        if not can_send_messages:
            logger.warning(
                "Promote submit channel missing send permission | "
                f"guild={message.guild.id} channel={message.channel.id} "
                f"type={channel_type} send_messages={getattr(channel_perms, 'send_messages', None)} "
                f"send_messages_in_threads={getattr(channel_perms, 'send_messages_in_threads', None)}"
            )
            return False
        if not getattr(channel_perms, "embed_links", False):
            is_th = i18n.guild_lang(message.guild.id) == "th"
            try:
                await message.channel.send(
                    (
                        "บอทไม่มีสิทธิ์ `Embed Links` ในห้องนี้ กรุณาแก้สิทธิ์ แล้วรัน `/promote setup` ใหม่"
                        if is_th
                        else "Bot is missing `Embed Links` permission in this channel. Please fix permissions, then run `/promote setup` again."
                    ),
                    delete_after=10,
                )
            except Exception:
                pass
            return True

        try:
            suspension_map = await _promote_suspension_map_load_local()
        except Exception:
            suspension_map = {}
        suspension_reason = _promote_suspension_reason_local(message.guild.id, suspension_map)
        if suspension_reason:
            try:
                await message.delete()
            except Exception:
                pass
            await message.channel.send(
                embed=discord.Embed(
                    description=suspension_reason,
                    color=color.red,
                ),
                delete_after=10,
            )
            return True

        is_owner_sender = bool(await checks.check_is_owner_raw(message.author, message.guild))
        ownerbot_unrestricted = is_owner_sender
        is_admin_sender = (
            message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_guild
            or is_owner_sender
        )
        if not is_admin_sender:
            try:
                await message.delete()
            except Exception:
                pass
            await message.channel.send(
                embed=discord.Embed(
                    description=i18n.tr("promote_only_admin_send", message.guild.id),
                    color=color.red,
                ),
                delete_after=8,
            )
            return True

        content = str(message.content or "").strip()
        automod_data = cache.automod.get(str(message.guild.id), {}) or {}
        automod_words = automod_data.get("antibadwords_words", [])
        if isinstance(automod_words, str):
            try:
                automod_words = json.loads(automod_words)
            except Exception:
                automod_words = []
        try:
            owner_policy = await _promote_owner_policy_load_local()
        except Exception:
            owner_policy = _default_promote_owner_policy_local()
        if not isinstance(owner_policy, dict):
            owner_policy = _default_promote_owner_policy_local()
        blocked_words_cfg = _normalize_promote_blocked_words_local(owner_policy.get("blocked_words") or [])
        blocked_word_pool = _promote_merge_blocked_words_local(
            PROMOTE_DEFAULT_BLOCKED_WORDS,
            automod_words,
            blocked_words_cfg,
        )
        content_ok, _content_reason = _validate_promote_content_local(content, blocked_word_pool)
        if not content_ok:
            try:
                await message.delete()
            except Exception:
                pass
            await message.channel.send(
                embed=discord.Embed(
                    description=i18n.tr("promote_badword_blocked", message.guild.id),
                    color=color.red,
                ),
                delete_after=8,
            )
            return True

        plan_tier = await self._promote_plan_tier(message.guild.id)
        can_use_rich_media = ownerbot_unrestricted or (plan_tier != "free")
        allowed_domains_cfg = _normalize_promote_allowed_domains_local(owner_policy.get("allowed_domains") or [])
        allowed_urls_cfg = _normalize_promote_allowed_urls_local(owner_policy.get("allowed_urls") or [])
        allowed_url_hint = _promote_allowed_hint_local(allowed_domains_cfg, allowed_urls_cfg)
        blocked_domains_cfg = _normalize_promote_allowed_domains_local(owner_policy.get("blocked_domains") or [])
        blocked_urls_cfg = _normalize_promote_allowed_urls_local(owner_policy.get("blocked_urls") or [])
        blocked_url_hint = _promote_blocked_hint_local(blocked_domains_cfg, blocked_urls_cfg)

        normalized_attachments: list[str] = []
        normalized_attachment_objects: dict[str, discord.Attachment] = {}
        invalid_attachments: list[str] = []
        for attachment in list(message.attachments or [])[:5]:
            raw_candidates = [
                str(getattr(attachment, "proxy_url", "") or "").strip(),
                str(getattr(attachment, "url", "") or "").strip(),
            ]
            normalized = ""
            for raw_url in raw_candidates:
                if not raw_url:
                    continue
                normalized = _normalize_promote_attachment_url_local(raw_url)
                if normalized:
                    break
            if normalized:
                if normalized not in normalized_attachments:
                    normalized_attachments.append(normalized)
                normalized_attachment_objects[normalized] = attachment
            else:
                fallback_url = raw_candidates[1] if len(raw_candidates) > 1 else ""
                invalid_attachments.append(fallback_url or (raw_candidates[0] if raw_candidates else ""))

        content_links, invalid_content_links = self._promote_extract_content_links(
            content,
            allowed_domains=allowed_domains_cfg,
            allowed_urls=allowed_urls_cfg,
            allow_unrestricted=ownerbot_unrestricted,
        )

        if invalid_attachments or invalid_content_links:
            await message.channel.send(
                embed=discord.Embed(
                    description="ลิงก์หรือไฟล์แนบบางรายการไม่ผ่านการตรวจสอบ โปรดแก้ไขก่อนส่งโปรโมต",
                    color=color.red,
                ),
                delete_after=8,
            )
            await message.channel.send(
                embed=discord.Embed(
                    description=allowed_url_hint,
                    color=color.yellow,
                ),
                delete_after=8,
            )
            return True

        if not ownerbot_unrestricted:
            blocked_links = _promote_find_blocked_urls_local(
                [
                    *normalized_attachments,
                    *content_links,
                ],
                blocked_domains=blocked_domains_cfg,
                blocked_urls=blocked_urls_cfg,
            )
            if blocked_links:
                try:
                    await message.delete()
                except Exception:
                    pass
                await message.channel.send(
                    embed=discord.Embed(
                        description=f"พบบล็อกลิงก์ต้องห้าม: {blocked_links[0]}",
                        color=color.red,
                    ),
                    delete_after=8,
                )
                await message.channel.send(
                    embed=discord.Embed(
                        description=blocked_url_hint,
                        color=color.yellow,
                    ),
                    delete_after=8,
                )
                return True

        if not can_use_rich_media and (normalized_attachments or content_links):
            await message.channel.send(
                embed=discord.Embed(
                    description="แพ็กเกจ Free ส่งโปรโมตได้เฉพาะข้อความ ห้ามลิงก์และรูปภาพ",
                    color=color.red,
                ),
                delete_after=10,
            )
            return True

        if not content and not normalized_attachments:
            await message.channel.send(
                embed=discord.Embed(
                    description=i18n.tr("promote_require_content", message.guild.id),
                    color=color.red,
                ),
                delete_after=8,
            )
            return True

        image_urls: list[str] = []
        for link in [*normalized_attachments, *content_links]:
            candidate = str(link or "").strip()
            if not candidate or candidate in image_urls:
                continue
            if not self._promote_is_image_url(candidate):
                continue
            image_urls.append(candidate)
            if len(image_urls) >= 4:
                break
        image_ok, image_reason = await self.scan_promote_image_urls(
            message.guild.id,
            image_urls,
            source="discord",
            blocked_words=blocked_word_pool,
        )
        image_scan_status_label = "ผ่าน"
        image_scan_status_detail = "ระบบตรวจรูปภาพทำงานปกติ"
        if not image_urls:
            image_scan_status_label = "ไม่มีรูปให้ตรวจ"
            image_scan_status_detail = "ข้อความนี้ไม่มีไฟล์ภาพที่ต้องตรวจ"
        if not image_ok:
            try:
                await message.delete()
            except Exception:
                pass
            fail_reason = str(image_reason or "รูปภาพไม่ผ่านการตรวจสอบความปลอดภัย").strip()
            await message.channel.send(
                embed=discord.Embed(
                    description=f"สถานะตรวจภาพ: ไม่ผ่าน\nเหตุผล: {fail_reason}",
                    color=color.red,
                ),
                delete_after=10,
            )
            return True
        if image_reason:
            normalized_image_reason = str(image_reason).strip()
            if normalized_image_reason.lower().startswith("warn:"):
                scan_warning_text = normalized_image_reason.split(":", 1)[1].strip()
                if scan_warning_text:
                    image_scan_status_label = "ผ่านแบบอนุโลม"
                    image_scan_status_detail = scan_warning_text
                    await message.channel.send(
                        embed=discord.Embed(
                            description=(
                                "ระบบตรวจรูปภาพมีปัญหาชั่วคราว ระบบจะอนุญาตให้ส่งครั้งนี้\n"
                                f"รายละเอียด: {scan_warning_text}"
                            ),
                            color=color.yellow,
                        ),
                        delete_after=12,
                    )

        cooldown_seconds = int(promote_data.get("cooldown_seconds") or PROMOTE_COOLDOWN_SECONDS)
        cooldowns = dict(promote_data.get("cooldowns") or {})
        now_ts = int(time.time())
        user_key = str(message.author.id)
        last_post = int(cooldowns.get(user_key, 0) or 0)
        if (not ownerbot_unrestricted) and (now_ts - last_post < cooldown_seconds):
            retry_at = now_ts + (cooldown_seconds - (now_ts - last_post))
            await message.channel.send(
                embed=discord.Embed(
                    description=i18n.tr("promote_retry_after", message.guild.id, retry=f"<t:{retry_at}:R>"),
                    color=color.red,
                ),
                delete_after=8,
            )
            return True

        invite_candidates = [url for url in content_links if _is_allowed_discord_invite_url_local(url)]
        preview_invite = invite_candidates[0] if invite_candidates else None

        preview_embed = discord.Embed(
            title="พรีวิวข้อความโปรโมต",
            description=content[:1800] if content else "-",
            color=color.blue,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        preview_embed.add_field(name="ผู้ส่ง", value=message.author.mention, inline=True)
        preview_embed.add_field(name="แพ็กเกจ", value=plan_tier.capitalize(), inline=True)
        preview_embed.add_field(name="โหมดสื่อ", value=("รองรับลิงก์/รูปภาพ" if can_use_rich_media else "ข้อความล้วน"), inline=True)
        preview_embed.add_field(
            name="สถานะตรวจภาพ",
            value=f"{image_scan_status_label}\n{image_scan_status_detail}",
            inline=False,
        )
        preview_embed_file: discord.File | None = None
        if normalized_attachments:
            preview_embed.add_field(
                name="ไฟล์แนบ",
                value="\n".join(normalized_attachments[:5]),
                inline=False,
            )
            image_attachment = next(
                (
                    link
                    for link in normalized_attachments
                    if self._promote_is_image_url(link)
                ),
                None,
            )
            if image_attachment:
                preview_image_url = image_attachment
                source_attachment = normalized_attachment_objects.get(image_attachment)
                if source_attachment:
                    try:
                        preview_embed_file = await source_attachment.to_file(use_cached=True)
                    except TypeError:
                        preview_embed_file = await source_attachment.to_file()
                    except Exception:
                        preview_embed_file = None
                    if preview_embed_file:
                        preview_filename = str(getattr(preview_embed_file, "filename", "") or "").strip()
                        if not preview_filename:
                            preview_filename = self._promote_moderation_image_filename(
                                image_attachment,
                                str(getattr(source_attachment, "content_type", "") or ""),
                            )
                        preview_filename = self._sanitize_discord_attachment_filename(
                            preview_filename,
                            fallback="promote_preview.png",
                        )
                        preview_embed_file.filename = preview_filename
                        preview_image_url = f"attachment://{preview_filename}"
                if not preview_embed_file:
                    preview_image_payload, preview_image_content_type = await self._download_image_bytes_for_moderation(
                        image_attachment,
                        max_bytes=8 * 1024 * 1024,
                    )
                    if preview_image_payload:
                        preview_filename = self._promote_moderation_image_filename(
                            image_attachment,
                            preview_image_content_type,
                        )
                        preview_filename = self._sanitize_discord_attachment_filename(
                            preview_filename,
                            fallback="promote_preview.png",
                        )
                        preview_embed_file = discord.File(
                            io.BytesIO(preview_image_payload),
                            filename=preview_filename,
                        )
                        preview_image_url = f"attachment://{preview_filename}"
                if preview_embed_file or not self._is_discord_cdn_attachment_url(preview_image_url):
                    preview_embed.set_image(url=preview_image_url)
        if preview_invite:
            preview_embed.add_field(name="ลิงก์เชิญ", value=preview_invite, inline=False)
        preview_embed.set_footer(text="กดปุ่มด้านล่างเพื่อ ส่ง / ยกเลิก / บันทึก")

        class _PromoteSaveModal(discord.ui.Modal, title="บันทึกโปรโมต"):
            template_name = discord.ui.TextInput(
                label="ชื่อบันทึก",
                placeholder="เช่น โปรโมตรอบค่ำ",
                max_length=80,
                required=False,
            )

            def __init__(self, *, cog: "message", promote_row: dict[str, Any], payload: dict[str, Any], actor_id: int):
                super().__init__(timeout=180)
                self._cog = cog
                self._promote_row = promote_row
                self._payload = payload
                self._actor_id = actor_id

            async def on_submit(self, interaction: discord.Interaction):
                if int(getattr(interaction.user, "id", 0) or 0) != int(self._actor_id):
                    await interaction.response.send_message("รายการนี้ไม่ใช่ของคุณ", ephemeral=True)
                    return
                ok, save_message = await self._cog._save_promote_template(
                    promote_data=self._promote_row,
                    guild_id=int(self._payload.get("guild_id") or 0),
                    user_id=int(self._actor_id),
                    content=str(self._payload.get("content") or ""),
                    attachments=list(self._payload.get("attachments") or []),
                    invite_url=str(self._payload.get("invite_url") or "").strip() or None,
                    name=str(self.template_name.value or "").strip(),
                )
                await interaction.response.send_message(
                    save_message,
                    ephemeral=True,
                )

        class _PromoteConfirmView(discord.ui.View):
            def __init__(self, *, cog: "message", promote_row: dict[str, Any], payload: dict[str, Any], actor_id: int):
                super().__init__(timeout=180)
                self._cog = cog
                self._promote_row = promote_row
                self._payload = payload
                self._actor_id = actor_id
                self._done = False
                self.preview_message: discord.Message | None = None

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if int(getattr(interaction.user, "id", 0) or 0) == int(self._actor_id):
                    return True
                await interaction.response.send_message("เฉพาะผู้ส่งคำขอนี้เท่านั้นที่กดปุ่มได้", ephemeral=True)
                return False

            def _lock(self):
                self._done = True
                for child in self.children:
                    try:
                        child.disabled = True
                    except Exception:
                        pass

            async def _auto_invite(self, interaction: discord.Interaction) -> str | None:
                try:
                    guild_obj = interaction.guild
                    channel_obj = interaction.channel
                    me = getattr(guild_obj, "me", None) if guild_obj else None
                    if guild_obj and channel_obj and me and channel_obj.permissions_for(me).create_instant_invite:
                        invite = await channel_obj.create_invite(
                            max_age=86400,
                            max_uses=0,
                            unique=False,
                            reason=f"Promote relay invite requested by {interaction.user}",
                        )
                        return invite.url
                except Exception:
                    return None
                return None

            @discord.ui.button(label="ส่งโปรโมต", style=discord.ButtonStyle.success)
            async def send_now(self, interaction: discord.Interaction, button: discord.ui.Button):
                async def _notify_ephemeral(text: str) -> None:
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(str(text or ""), ephemeral=True)
                        else:
                            await interaction.response.send_message(str(text or ""), ephemeral=True)
                    except Exception:
                        pass

                async def _finalize_preview(embed: discord.Embed) -> None:
                    target_message = self.preview_message or interaction.message
                    await target_message.edit(embed=embed, view=self)

                if self._done:
                    await _notify_ephemeral("รายการนี้ถูกดำเนินการแล้ว")
                    return
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()
                except Exception:
                    pass

                try:
                    latest = await storage.promote_channels.get(guild_id=int(self._payload.get("guild_id") or 0)) or self._promote_row
                    cooldowns_latest = dict(latest.get("cooldowns") or {})
                    cooldown_sec = int(latest.get("cooldown_seconds") or PROMOTE_COOLDOWN_SECONDS)
                    now_local = int(time.time())
                    key = str(self._actor_id)
                    last_local = int(cooldowns_latest.get(key, 0) or 0)
                    bypass_cooldown = bool(self._payload.get("ownerbot_unrestricted"))
                    if (not bypass_cooldown) and (now_local - last_local < cooldown_sec):
                        retry_at = now_local + (cooldown_sec - (now_local - last_local))
                        await _notify_ephemeral(
                            i18n.tr("promote_retry_after", int(self._payload.get("guild_id") or 0), retry=f"<t:{retry_at}:R>")
                        )
                        return

                    invite_url = str(self._payload.get("invite_url") or "").strip() or None
                    if not invite_url:
                        invite_url = await self._auto_invite(interaction)

                    if not bypass_cooldown:
                        cooldowns_latest[key] = now_local
                        await storage.promote_channels.update(id=latest.get("id"), cooldowns=cooldowns_latest)

                    queued, queue_size, queue_status = await self._cog.enqueue_promote_job(
                        {
                            "guild_id": int(self._payload.get("guild_id") or 0),
                            "author_id": int(self._actor_id),
                            "author_name": str(self._payload.get("author_name") or interaction.user.display_name or interaction.user.name),
                            "author_mention": str(self._payload.get("author_mention") or interaction.user.mention),
                            "content": str(self._payload.get("content") or ""),
                            "attachments": list(self._payload.get("attachments") or []),
                            "invite_url": invite_url,
                            "source_origin": str(self._payload.get("source_origin") or "discord"),
                            "source_channel_id": int(self._payload.get("source_channel_id") or 0),
                            "source_channel_name": str(self._payload.get("source_channel_name") or ""),
                            "guild_name": str(self._payload.get("guild_name") or ""),
                            "allowed_domains": list(self._payload.get("allowed_domains") or []),
                            "allowed_urls": list(self._payload.get("allowed_urls") or []),
                            "blocked_words": list(self._payload.get("blocked_words") or []),
                            "blocked_domains": list(self._payload.get("blocked_domains") or []),
                            "blocked_urls": list(self._payload.get("blocked_urls") or []),
                            "ownerbot_unrestricted": bool(self._payload.get("ownerbot_unrestricted")),
                        }
                    )
                    if not queued and queue_status == "duplicate":
                        done_embed = discord.Embed(
                            description="มีข้อความโปรโมตลิงก์เดียวกันอยู่ในคิวแล้ว ระบบจะส่งเพียงครั้งเดียว",
                            color=color.yellow,
                        )
                        self._lock()
                        await _finalize_preview(done_embed)
                        return
                    if not queued and str(queue_status or "").startswith("policy_blocked:"):
                        reason = str(queue_status).split(":", 1)[1].strip() or "โปรโมตถูกบล็อกตามนโยบายความปลอดภัย"
                        done_embed = discord.Embed(
                            description=reason,
                            color=color.red,
                        )
                        self._lock()
                        await _finalize_preview(done_embed)
                        return
                    if not queued:
                        done_embed = discord.Embed(
                            description="ส่งโปรโมตไม่สำเร็จชั่วคราว กรุณาลองใหม่",
                            color=color.red,
                        )
                        self._lock()
                        await _finalize_preview(done_embed)
                        return
                    queue_warning = ""
                    if str(queue_status or "").startswith("queued_warn:"):
                        queue_warning = str(queue_status).split(":", 1)[1].strip()
                    done_embed = discord.Embed(
                        description=(
                            f"{self._cog.bot.emoji.SUCCESS} {i18n.tr('promote_queued_success', int(self._payload.get('guild_id') or 0))} "
                            f"{i18n.tr('promote_queue_position', int(self._payload.get('guild_id') or 0))}: `{queue_size}`"
                        ),
                        color=color.green,
                    )
                    if queue_warning:
                        done_embed.add_field(
                            name="สถานะการตรวจรูปภาพ",
                            value=f"ส่งได้ แต่ระบบตรวจรูปภาพไม่พร้อมบางส่วน: {queue_warning}",
                            inline=False,
                        )
                    self._lock()
                    await _finalize_preview(done_embed)
                except Exception as error:
                    logger.warning(
                        "Promote send button failed | "
                        f"guild={int(self._payload.get('guild_id') or 0)} "
                        f"user={int(self._actor_id)} "
                        f"error={type(error).__name__}: {str(error)[:180]}"
                    )
                    await _notify_ephemeral("ส่งโปรโมตไม่สำเร็จชั่วคราว กรุณาลองใหม่อีกครั้ง")

            @discord.ui.button(label="บันทึก", style=discord.ButtonStyle.primary)
            async def save_now(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self._done:
                    await interaction.response.send_message("รายการนี้ถูกดำเนินการแล้ว", ephemeral=True)
                    return
                await interaction.response.send_modal(
                    _PromoteSaveModal(
                        cog=self._cog,
                        promote_row=self._promote_row,
                        payload=self._payload,
                        actor_id=self._actor_id,
                    )
                )

            @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary)
            async def cancel_now(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self._done:
                    await interaction.response.send_message("รายการนี้ถูกดำเนินการแล้ว", ephemeral=True)
                    return
                cancel_embed = discord.Embed(
                    description="ยกเลิกการส่งโปรโมตแล้ว",
                    color=color.red,
                )
                self._lock()
                await interaction.response.edit_message(embed=cancel_embed, view=self)

            async def on_timeout(self):
                if self._done:
                    return
                self._lock()
                if self.preview_message:
                    try:
                        timeout_embed = discord.Embed(
                            description="หมดเวลายืนยันแล้ว โปรดส่งข้อความใหม่หากต้องการโปรโมต",
                            color=color.red,
                        )
                        await self.preview_message.edit(embed=timeout_embed, view=self)
                    except Exception:
                        pass

        payload = {
            "guild_id": message.guild.id,
            "author_id": message.author.id,
            "author_name": str(message.author.display_name or message.author.name),
            "author_mention": message.author.mention,
            "content": content,
            "attachments": normalized_attachments[:5],
            "invite_url": preview_invite,
            "source_origin": "discord",
            "source_channel_id": int(getattr(message.channel, "id", 0) or 0),
            "source_channel_name": str(getattr(message.channel, "name", "") or ""),
            "guild_name": str(getattr(message.guild, "name", "") or ""),
            "allowed_domains": allowed_domains_cfg,
            "allowed_urls": allowed_urls_cfg,
            "blocked_words": blocked_words_cfg,
            "blocked_domains": blocked_domains_cfg,
            "blocked_urls": blocked_urls_cfg,
            "ownerbot_unrestricted": ownerbot_unrestricted,
        }
        view = _PromoteConfirmView(
            cog=self,
            promote_row=promote_data,
            payload=payload,
            actor_id=message.author.id,
        )

        send_kwargs: dict[str, Any] = {
            "embed": preview_embed,
            "view": view,
        }
        if preview_embed_file:
            send_kwargs["file"] = preview_embed_file
        preview_message = await message.channel.send(**send_kwargs)
        view.preview_message = preview_message
        try:
            await message.delete()
        except Exception:
            pass
        return True

    async def check_afk_user_mention(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        try:

            if not message.mentions:

                return

            for user in message.mentions:

                if user.bot:

                    return

                global_afk = cache.afk.get("global", {}).get(str(user.id), {})

                if global_afk:

                    await storage.afk.update(
                        id=global_afk.get("id"),
                        user_id=user.id,
                        mentioned=global_afk.get("mentioned", 0) + 1,
                    )

                    created_at: datetime.datetime = global_afk.get("created_at")

                    text = f"**{user.display_name}** is Globally AFK: {global_afk.get('reason','`Without reason`')} - <t:{int(created_at.timestamp())}:R>"

                    await message.reply(content=text)

                guild_afk = (
                    cache.afk.get("guilds", {})
                    .get(str(message.guild.id), {})
                    .get(str(user.id), {})
                )

                if guild_afk:

                    await storage.afk.update(
                        id=guild_afk.get("id"),
                        guild_id=message.guild.id,
                        user_id=user.id,
                        mentioned=guild_afk.get("mentioned", 0) + 1,
                    )

                    created_at: datetime.datetime = guild_afk.get("created_at")

                    text = f"**{user.display_name}** is AFK in this server: {guild_afk.get('reason','`Without reason`')} - <t:{int(created_at.timestamp())}:R>"

                    await message.reply(content=text)

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    async def check_for_bot_mention(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        if message.content == self.bot.user.mention:

            DEFAULT_PREFIX = BotConfig.PREFIX

            guild_cache = cache.guilds.get(str(message.guild.id), {})

            guild_prefix = guild_cache.get("prefix", DEFAULT_PREFIX)

            embed = discord.Embed(
                title=f"Hi {message.author.display_name}!",
                color=color.aqua,
                description=(
                    f"> ใช้ `{guild_prefix}help` เพื่อรับรายการคำสั่งทั้งหมด\n"
                    f"> หากต้องการความช่วยเหลือในการตั้งค่าหรือแก้ไขปัญหา โปรดไปที่ศูนย์สนับสนุนของ SkylineBOT\n\n"
                ),
            )

            embed.set_footer(
                text="SkylineBOT - Skyline Development",
                icon_url=self.bot.user.display_avatar.url,
            )

            view = discord.ui.View()

            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.url,
                    label="เชิญบอท",
                    url=self.bot.urls.INVITE,
                    row=0,
                )
            )

            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.url,
                    label="Support Server",
                    url=self.bot.urls.SUPPORT_SERVER,
                    row=0,
                )
            )

            await message.reply(embed=embed, view=view)

    def _refresh_ai_command_reference(self, limit: int = 80) -> str:
        now = time.time()
        if (
            self.ai_command_reference_cache
            and now - self.ai_command_reference_updated_at < self.ai_command_reference_ttl
        ):
            return self.ai_command_reference_cache

        try:
            command_lines = []
            seen = set()
            for command in self.bot.walk_commands():
                if getattr(command, "hidden", False):
                    continue
                qualified_name = str(getattr(command, "qualified_name", "") or "").strip()
                if not qualified_name or qualified_name in seen:
                    continue
                seen.add(qualified_name)
                help_text = str(getattr(command, "help", "") or "").strip()
                if help_text.startswith("i18n:"):
                    help_text = ""
                line = f"- {qualified_name}"
                if help_text:
                    line += f": {help_text[:90]}"
                command_lines.append(line)

            command_lines = sorted(command_lines)[: max(10, int(limit))]
            self.ai_command_reference_cache = "\n".join(command_lines)
            self.ai_command_reference_updated_at = now
        except Exception:
            self.ai_command_reference_cache = ""
            self.ai_command_reference_updated_at = now

        return self.ai_command_reference_cache

    @staticmethod
    def _tokenize_search_terms(text: str) -> list[str]:
        normalized = str(text or "").strip().lower()
        if not normalized:
            return []
        tokens = re.findall(r"[a-zA-Z\u0E00-\u0E7F0-9_/-]+", normalized)
        if not tokens:
            return []
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "to",
            "for",
            "of",
            "in",
            "on",
            "at",
            "with",
            "is",
            "are",
            "be",
            "it",
            "this",
            "that",
            "what",
            "which",
            "how",
            "why",
            "ได้",
            "ครับ",
            "ค่ะ",
            "คับ",
            "หน่อย",
            "ช่วย",
            "คือ",
            "และ",
            "หรือ",
            "ของ",
            "ที่",
            "ไป",
            "มา",
            "ให้",
            "ยังไง",
            "อย่างไร",
            "เว็บ",
            "เว็บไซต์",
            "bot",
            "บอท",
            "skylinebot",
            "skyline",
        }
        ordered: list[str] = []
        seen = set()
        for token in tokens:
            value = str(token or "").strip().lower()
            if len(value) < 2:
                continue
            if value in stopwords:
                continue
            if value.isdigit() and len(value) < 3:
                continue
            if value not in seen:
                seen.add(value)
                ordered.append(value)
            # Also split path-like terms to improve long query matching.
            if "/" in value or "-" in value:
                for part in re.split(r"[/_-]+", value):
                    part_value = str(part or "").strip().lower()
                    if len(part_value) < 2 or part_value in stopwords or part_value.isdigit():
                        continue
                    if part_value in seen:
                        continue
                    seen.add(part_value)
                    ordered.append(part_value)
        return ordered

    @staticmethod
    def _is_website_intent_text(text: str) -> bool:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return False
        tokens = (
            "เว็บ",
            "website",
            "site",
            "page",
            "pages",
            "commands",
            "คำสั่ง",
            "หน้า",
            "dashboard",
            "pricing",
            "contact",
            "docs",
            "documentation",
            "guide",
            "manual",
            "setup",
            "วิธีใช้",
            "tag",
            "tags",
            "terms",
            "privacy",
            "policy",
            "report",
            "status",
            "invite",
            "redeem",
            "premium",
            "wallet",
            "leaderboard",
            "plan",
            "subscribe",
        )
        return any(token in lowered for token in tokens)

    def _official_site_links_catalog(self, guild_id: int | None = None) -> list[dict[str, Any]]:
        base = str(self.ai_site_base_url or "https://skylinebot.xyz").strip().rstrip("/")
        status_public = str(
            os.getenv("SUPPORT_STATUS_PUBLIC_URL", "https://status.skylinebot.xyz")
            or "https://status.skylinebot.xyz"
        ).strip().rstrip("/")
        support_url = str(getattr(getattr(self.bot, "urls", None), "SUPPORT_SERVER", "") or "").strip()
        if not support_url:
            support_url = "https://discord.gg/6g294K6KMp"
        guild_tail = str(int(guild_id)) if guild_id else "....."
        return [
            {"title": "Commands", "url": f"{base}/commands", "tokens": ("command", "commands", "คำสั่ง", "help"), "priority": 120},
            {"title": "Docs", "url": f"{base}/docs", "tokens": ("docs", "documentation", "คู่มือ", "วิธีใช้", "manual", "guide"), "priority": 118},
            {"title": "Tags", "url": f"{base}/tags", "tokens": ("tag", "tags", "แท็ก"), "priority": 116},
            {"title": "Support Server", "url": support_url, "tokens": ("support", "discord support", "ติดต่อทีมงาน", "support server", "ขอความช่วยเหลือ"), "priority": 115},
            {"title": "Terms of Service", "url": f"{base}/terms-of-service", "tokens": ("terms", "tos", "เงื่อนไข", "ข้อตกลง"), "priority": 114},
            {"title": "Privacy Policy", "url": f"{base}/privacy-policy", "tokens": ("privacy", "policy", "ความเป็นส่วนตัว"), "priority": 113},
            {"title": "Report", "url": f"{base}/report", "tokens": ("report", "รายงาน", "แจ้งปัญหา"), "priority": 112},
            {"title": "Main Status", "url": f"{base}/status", "tokens": ("status", "สถานะ", "ล่มไหม", "down"), "priority": 111},
            {"title": "Public Status", "url": status_public, "tokens": ("status", "uptime", "incident", "สถานะ"), "priority": 110},
            {"title": "Invite Bot", "url": f"{base}/invitebot", "tokens": ("invitebot", "เชิญบอท", "เพิ่มบอท"), "priority": 109},
            {"title": "Invite", "url": f"{base}/invite", "tokens": ("invite", "เชิญ", "เพิ่ม"), "priority": 108},
            {"title": "Redeem", "url": f"{base}/redeem", "tokens": ("redeem", "โค้ด", "คูปอง"), "priority": 107},
            {"title": "Subscribe Plan", "url": f"{base}/subscribe-plan", "tokens": ("subscribe", "plan", "แพลน", "ราคา", "สมัคร"), "priority": 106},
            {"title": "Leaderboard", "url": f"{base}/leaderboard", "tokens": ("leaderboard", "อันดับ", "top"), "priority": 105},
            {"title": "Premium", "url": f"{base}/premium", "tokens": ("premium", "พรีเมียม"), "priority": 104},
            {"title": "Wallet", "url": f"{base}/wallet", "tokens": ("wallet", "กระเป๋า", "เงิน"), "priority": 103},
            {"title": "Profile Settings", "url": f"{base}/dashboard/SetingProfileUser", "tokens": ("profile", "setting profile", "โปรไฟล์"), "priority": 102},
            {"title": "Topup History", "url": f"{base}/dashboard/setting-profile-user/topup-history", "tokens": ("topup", "เติมเงิน", "ประวัติเติม"), "priority": 101},
            {"title": "Premium History", "url": f"{base}/dashboard/setting-profile-user/premium-history", "tokens": ("premium history", "ประวัติพรีเมียม"), "priority": 100},
            {"title": "Guild Dashboard", "url": f"{base}/dashboard/guild/{guild_tail}", "tokens": ("dashboard guild", "กิลด์", "guild setting", "เซิร์ฟเวอร์"), "priority": 99},
        ]

    def _rank_official_site_links(
        self,
        query_text: str,
        *,
        guild_id: int | None = None,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        query = str(query_text or "").strip().lower()
        catalog = self._official_site_links_catalog(guild_id)
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in catalog:
            score = int(item.get("priority") or 0)
            title = str(item.get("title") or "").strip().lower()
            url = str(item.get("url") or "").strip().lower()
            for token in list(item.get("tokens") or []):
                token_text = str(token or "").strip().lower()
                if token_text and token_text in query:
                    score += 40
            if title and title in query:
                score += 24
            if url and url in query:
                score += 60
            if "/dashboard/guild/" in url and "guild" in query:
                score += 15
            if score <= 0:
                continue
            scored.append((score, item))
        if not query:
            scored = [(int(item.get("priority") or 0), item) for item in catalog]
        scored.sort(key=lambda row: (-row[0], -int(row[1].get("priority") or 0), str(row[1].get("url") or "")))
        selected = [item for _, item in scored[: max(1, int(limit))]]
        if selected:
            return selected
        return catalog[: max(1, int(limit))]

    def _build_official_site_links_summary(
        self,
        query_text: str,
        *,
        guild_id: int | None = None,
        limit: int = 6,
    ) -> list[str]:
        rows = self._rank_official_site_links(query_text, guild_id=guild_id, limit=limit)
        lines: list[str] = []
        for row in rows:
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            if not title or not url:
                continue
            lines.append(f"{title}: {url}")
        return lines

    def _refresh_ai_command_records(self, limit: int = 1000) -> list[dict[str, str]]:
        now = time.time()
        if (
            self.ai_command_records_cache
            and now - self.ai_command_records_updated_at < self.ai_command_reference_ttl
        ):
            return list(self.ai_command_records_cache)

        records: list[dict[str, str]] = []
        seen = set()
        try:
            for command in self.bot.walk_commands():
                if getattr(command, "hidden", False):
                    continue
                qualified_name = str(getattr(command, "qualified_name", "") or "").strip()
                if not qualified_name or qualified_name in seen:
                    continue
                seen.add(qualified_name)
                help_text = str(getattr(command, "help", "") or "").strip()
                if help_text.startswith("i18n:"):
                    help_text = ""
                aliases = list(getattr(command, "aliases", []) or [])
                aliases_text = ", ".join(
                    [str(alias).strip() for alias in aliases if str(alias).strip()]
                )[:180]
                records.append(
                    {
                        "name": qualified_name,
                        "help": help_text[:220],
                        "aliases": aliases_text,
                    }
                )
                if len(records) >= max(50, int(limit)):
                    break
        except Exception:
            records = []

        records.sort(key=lambda row: row.get("name", ""))
        self.ai_command_records_cache = list(records)
        self.ai_command_records_updated_at = now
        return list(records)

    def _build_command_reference_for_prompt(
        self, user_content: str, prefix: str, *, limit: int = 80
    ) -> str:
        records = self._refresh_ai_command_records(limit=1000)
        if not records:
            return ""

        terms = self._tokenize_search_terms(user_content)
        selected: list[dict[str, str]] = []
        if terms:
            scored: list[tuple[int, dict[str, str]]] = []
            for row in records:
                haystack = (
                    f"{row.get('name', '')} {row.get('help', '')} {row.get('aliases', '')}"
                ).lower()
                score = sum(1 for term in terms if term in haystack)
                if score <= 0:
                    continue
                scored.append((score, row))
            scored.sort(key=lambda item: (-item[0], str(item[1].get("name", ""))))
            selected = [row for _, row in scored[: max(10, int(limit))]]

        if not selected:
            selected = records[: max(20, int(limit))]

        lines = []
        if int(limit) >= 400:
            char_budget = 50000
        elif int(limit) >= 200:
            char_budget = 28000
        elif int(limit) >= 120:
            char_budget = 12000
        else:
            char_budget = 7000
        used_chars = 0
        for row in selected:
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            help_text = str(row.get("help", "")).strip()
            aliases_text = str(row.get("aliases", "")).strip()
            line = f"- {prefix}{name} / /{name}"
            if aliases_text:
                line += f" | aliases: {aliases_text}"
            if help_text:
                line += f" | help: {help_text}"
            line = line[:320]
            if used_chars + len(line) > char_budget and lines:
                break
            lines.append(line)
            used_chars += len(line)
        if not lines:
            return ""
        return (
            f"Live command registry ({len(records)} commands loaded from runtime):\n"
            + "\n".join(lines[: max(10, int(limit))])
        )

    def _normalize_site_url_for_knowledge(self, raw_url: str) -> str:
        raw = str(raw_url or "").strip()
        if not raw:
            return ""
        base = str(self.ai_site_base_url or "").strip().rstrip("/")
        if not base:
            return ""
        candidate = urljoin(f"{base}/", raw)
        parsed = urlparse(candidate)
        base_parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"}:
            return ""
        if str(parsed.netloc or "").strip().lower() != str(base_parsed.netloc or "").strip().lower():
            return ""
        path = str(parsed.path or "/").strip() or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"

    @staticmethod
    def _strip_html_for_knowledge(html_text: str, *, limit: int = 1800) -> str:
        source = str(html_text or "")
        if not source:
            return ""
        cleaned = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", source)
        cleaned = re.sub(r"(?is)<br\s*/?>", "\n", cleaned)
        cleaned = re.sub(r"(?is)</(p|div|section|article|h1|h2|h3|h4|h5|h6|li|tr|td)>", "\n", cleaned)
        cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
        cleaned = html_lib.unescape(cleaned)
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
        cleaned = re.sub(r"\n{2,}", "\n", cleaned)
        cleaned = cleaned.strip()
        return cleaned[: max(200, int(limit))]

    def _extract_site_links_from_html(self, html_text: str) -> list[str]:
        source = str(html_text or "")
        if not source:
            return []
        raw_links = re.findall(
            r"""(?is)href\s*=\s*["']([^"'#]+)["']""",
            source,
        )
        resolved: list[str] = []
        seen = set()
        for raw in raw_links:
            normalized = self._normalize_site_url_for_knowledge(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            resolved.append(normalized)
        return resolved

    def _build_site_page_record(self, url: str, html_text: str) -> dict[str, str] | None:
        source = str(html_text or "")
        if not source:
            return None
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", source)
        h1_match = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", source)
        title_text = self._strip_html_for_knowledge(title_match.group(1) if title_match else "", limit=160)
        h1_text = self._strip_html_for_knowledge(h1_match.group(1) if h1_match else "", limit=180)
        snippet = self._strip_html_for_knowledge(source, limit=1200)
        if not snippet:
            return None
        parsed = urlparse(url)
        path = str(parsed.path or "/")
        page_title = title_text or h1_text or path
        return {
            "url": str(url).strip(),
            "path": path,
            "title": page_title[:180],
            "snippet": snippet[:1200],
        }

    async def _refresh_ai_site_knowledge(self, *, force: bool = False) -> None:
        now = time.time()
        if (
            not force
            and self.ai_site_knowledge_records
            and (now - self.ai_site_knowledge_updated_at) < float(self.ai_site_knowledge_ttl_seconds or 21600.0)
        ):
            return

        async with self.ai_site_knowledge_refresh_lock:
            now = time.time()
            if (
                not force
                and self.ai_site_knowledge_records
                and (now - self.ai_site_knowledge_updated_at) < float(self.ai_site_knowledge_ttl_seconds or 21600.0)
            ):
                return

            base = self._normalize_site_url_for_knowledge(self.ai_site_base_url)
            if not base:
                return

            queue = deque()
            seeded = [
                base,
                self._normalize_site_url_for_knowledge(f"{base}/commands"),
                self._normalize_site_url_for_knowledge(f"{base}/dashboard"),
                self._normalize_site_url_for_knowledge(f"{base}/pricing"),
                self._normalize_site_url_for_knowledge("https://niceshopallforme.web.app/contact"),
            ]
            for item in seeded:
                if item:
                    queue.append(item)

            sitemap_url = self._normalize_site_url_for_knowledge(f"{base}/sitemap.xml")
            if sitemap_url:
                queue.appendleft(sitemap_url)

            visited = set()
            records: list[dict[str, str]] = []
            time_started = time.monotonic()
            max_pages = max(20, int(self.ai_site_knowledge_max_pages or 200))
            hard_timeout_seconds = 28.0
            timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=8)
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": "SkylineBOT-AI-Knowledge/1.0",
            }

            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    while (
                        queue
                        and len(visited) < max_pages
                        and (time.monotonic() - time_started) < hard_timeout_seconds
                    ):
                        url = str(queue.popleft() or "").strip()
                        if not url or url in visited:
                            continue
                        visited.add(url)

                        body_text = ""
                        content_type = ""
                        try:
                            async with session.get(url, allow_redirects=True) as response:
                                if response.status >= 400:
                                    continue
                                content_type = str(response.headers.get("Content-Type") or "").lower()
                                body_text = await response.text(errors="ignore")
                        except Exception:
                            continue

                        if not body_text:
                            continue

                        is_sitemap = (
                            url.endswith("/sitemap.xml")
                            or "<urlset" in body_text[:500].lower()
                            or "application/xml" in content_type
                        )
                        if is_sitemap:
                            for loc in re.findall(r"(?is)<loc>(.*?)</loc>", body_text):
                                candidate = self._normalize_site_url_for_knowledge(loc)
                                if candidate and candidate not in visited:
                                    queue.append(candidate)
                            continue

                        if "text/html" not in content_type and "<html" not in body_text[:1000].lower():
                            continue

                        record = self._build_site_page_record(url, body_text)
                        if record:
                            records.append(record)

                        for link in self._extract_site_links_from_html(body_text):
                            if link in visited:
                                continue
                            queue.append(link)
            except Exception:
                pass

            compact: list[dict[str, str]] = []
            seen_urls = set()
            char_budget = max(12000, int(self.ai_site_knowledge_max_chars or 90000))
            used_chars = 0
            for record in records:
                url = str(record.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                line_len = len(str(record.get("title") or "")) + len(str(record.get("snippet") or ""))
                if used_chars + line_len > char_budget and compact:
                    break
                compact.append(record)
                seen_urls.add(url)
                used_chars += line_len

            if compact:
                self.ai_site_knowledge_records = compact
                self.ai_site_knowledge_updated_at = time.time()

    def _kickoff_ai_site_knowledge_refresh(self) -> None:
        task = self.ai_site_knowledge_refresh_task
        if task and not task.done():
            return
        try:
            self.ai_site_knowledge_refresh_task = asyncio.create_task(
                self._refresh_ai_site_knowledge(force=False)
            )
            self.ai_site_knowledge_refresh_task.add_done_callback(self._on_ai_task_done)
        except Exception:
            self.ai_site_knowledge_refresh_task = None

    def _rank_site_records_for_query(
        self, query_text: str, *, limit: int = 10
    ) -> list[tuple[int, dict[str, str]]]:
        records = list(self.ai_site_knowledge_records or [])
        if not records:
            return []
        terms = self._tokenize_search_terms(query_text)
        if not terms:
            weighted: list[tuple[int, dict[str, str]]] = []
            for row in records[: max(3, int(limit))]:
                base_score = 10
                path = str(row.get("path") or "").lower()
                if path in {"/commands", "/dashboard", "/contact", "/pricing"}:
                    base_score += 20
                weighted.append((base_score, row))
            return weighted

        scored: list[tuple[int, dict[str, str]]] = []
        query_text_normalized = str(query_text or "").strip().lower()
        intent_boost_tokens = {
            "/commands": ("command", "commands", "คำสั่ง", "วิธีใช้", "help"),
            "/dashboard": ("dashboard", "ownerbot", "แผง", "ตั้งค่า", "settings", "admin"),
            "/pricing": ("pricing", "plan", "plans", "แพลน", "ราคา"),
            "/contact": ("contact", "support", "ติดต่อ", "ticket", "ช่วยเหลือ"),
        }
        for row in records:
            path = str(row.get("path") or "").lower()
            title = str(row.get("title") or "").lower()
            snippet = str(row.get("snippet") or "").lower()
            haystack = f"{path} {title} {snippet}"
            score = 0
            for term in terms:
                if term in title:
                    score += 8
                if term in path:
                    score += 6
                if term in snippet:
                    score += 2
            if query_text_normalized and query_text_normalized in snippet:
                score += 18
            elif query_text_normalized and query_text_normalized in title:
                score += 22
            if any(token in path for token in ("/commands", "/dashboard", "/pricing", "/contact")):
                score += 2
            for anchor_path, anchor_terms in intent_boost_tokens.items():
                if anchor_path in path and any(term in query_text_normalized for term in anchor_terms):
                    score += 14
            if score <= 0:
                continue
            scored.append((score, row))
        scored.sort(
            key=lambda item: (
                -item[0],
                len(str(item[1].get("path") or "")),
                str(item[1].get("path") or ""),
            )
        )
        return scored[: max(3, int(limit))]

    def _select_site_records_for_query(
        self, query_text: str, *, limit: int = 8
    ) -> list[dict[str, str]]:
        ranked = self._rank_site_records_for_query(query_text, limit=limit)
        if not ranked:
            return []
        return [row for _, row in ranked[: max(3, int(limit))]]

    def _build_site_reference_for_prompt(
        self,
        query_text: str,
        *,
        force_full: bool = False,
        limit: int | None = None,
    ) -> str:
        effective_limit = max(4, int(limit or (24 if force_full else 10)))
        official_limit = max(6, min(24, effective_limit))
        official_lines = self._build_official_site_links_summary(query_text, limit=official_limit)
        official_block = ""
        if official_lines:
            official_block = "Official SkylineBOT links (high priority):\n" + "\n".join(
                [f"- {line}" for line in official_lines]
            )
        if not self.ai_site_knowledge_records:
            self._kickoff_ai_site_knowledge_refresh()
            base = str(self.ai_site_base_url or "https://skylinebot.xyz").rstrip("/")
            baseline = (
                "Official SkylineBOT URLs (baseline):\n"
                f"- Home: {base}\n"
                f"- Commands: {base}/commands\n"
                f"- Dashboard: {base}/dashboard\n"
                "- Contact: https://niceshopallforme.web.app/contact\n"
                f"- Pricing: {base}/pricing"
            )
            if official_block:
                return baseline + "\n\n" + official_block
            return baseline

        now = time.time()
        if (
            now - float(self.ai_site_knowledge_updated_at or 0.0)
            > float(self.ai_site_knowledge_ttl_seconds or 21600.0)
        ):
            self._kickoff_ai_site_knowledge_refresh()

        ranked_rows = self._rank_site_records_for_query(query_text, limit=effective_limit)
        if not ranked_rows:
            fallback_rows = list(self.ai_site_knowledge_records[: max(5, effective_limit // 2)])
            ranked_rows = [(1, row) for row in fallback_rows]
        if not ranked_rows:
            return ""

        lines: list[str] = []
        for score, row in ranked_rows:
            title = str(row.get("title") or "").strip() or str(row.get("path") or "/")
            url = str(row.get("url") or "").strip()
            snippet = str(row.get("snippet") or "").strip()
            if not url:
                continue
            snippet_limit = 240 if force_full else 180
            lines.append(f"- score={score} | {title} | {url} | {snippet[:snippet_limit]}")
        if not lines:
            return ""
        snapshot = (
            "Website knowledge snapshot (SkylineBOT official pages; ranked for current question):\n"
            + "\n".join(lines)
            + "\nWhen answering website/page questions, cite exact URL(s) from this ranked list."
        )
        if official_block:
            return official_block + "\n\n" + snapshot
        return snapshot

    def _build_ranked_site_links_summary(self, query_text: str, *, limit: int = 3) -> list[str]:
        lines: list[str] = []
        seen_urls: set[str] = set()

        official_lines = self._build_official_site_links_summary(query_text, limit=max(1, int(limit)))
        for line in official_lines:
            parts = line.split(": ", 1)
            if len(parts) != 2:
                continue
            url = str(parts[1]).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            lines.append(f"{line} (official)")

        ranked_rows = self._rank_site_records_for_query(query_text, limit=max(2, int(limit)))
        for score, row in ranked_rows[: max(1, int(limit))]:
            url = str((row or {}).get("url") or "").strip()
            title = str((row or {}).get("title") or (row or {}).get("path") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            lines.append(f"{title}: {url} (score {score})")
            if len(lines) >= max(1, int(limit)):
                break
        return lines[: max(1, int(limit))]

    def _inject_ranked_links_into_reply(self, reply_text: str, user_text: str) -> str:
        raw_reply = str(reply_text or "").strip()
        if not raw_reply:
            return raw_reply
        if not self._is_website_intent_text(user_text):
            return raw_reply
        deny_site_pattern = re.compile(
            r"(ยังไม่มีเว็บไซต์|ไม่มีเว็บไซต์(เป็นทางการ)?|no official website|does not have (an )?official website)",
            flags=re.IGNORECASE,
        )
        if deny_site_pattern.search(raw_reply):
            base = str(self.ai_site_base_url or "https://skylinebot.xyz").strip().rstrip("/")
            corrected = (
                f"มีเว็บไซต์อย่างเป็นทางการครับ: {base}\n"
                f"- Commands: {base}/commands\n"
                f"- Dashboard: {base}/dashboard\n"
                "- Contact: https://niceshopallforme.web.app/contact"
            )
            return corrected[: int(getattr(self, "ai_max_reply_chars", 5600) or 5600)]
        links = self._build_ranked_site_links_summary(user_text, limit=3)
        if not links:
            return raw_reply
        if re.search(r"https?://\S+", raw_reply, flags=re.IGNORECASE):
            # Keep original answer, but still add official references if they are not present.
            existing_urls = set(re.findall(r"https?://\S+", raw_reply, flags=re.IGNORECASE))
            filtered_links = [line for line in links if not any(url in line for url in existing_urls)]
            if not filtered_links:
                return raw_reply
            links = filtered_links
        appendix = "\n\nอ้างอิงหน้าเว็บที่เกี่ยวข้อง:\n" + "\n".join(
            [f"- {line}" for line in links]
        )
        merged = f"{raw_reply}{appendix}"
        return merged[: int(getattr(self, "ai_max_reply_chars", 5600) or 5600)]

    async def _add_ai_references_followup(
        self, message: discord.Message, user_text: str
    ) -> None:
        if not self._is_website_intent_text(user_text):
            return
        lines = self._build_ranked_site_links_summary(user_text, limit=3)
        if not lines:
            return
        try:
            await message.channel.send(
                embed=discord.Embed(
                    title="SkylineBOT Web References",
                    description="\n".join([f"- {line}" for line in lines])[:3900],
                    color=self._parse_color_hex_to_int(
                        self.ai_response_embed_default_color, fallback=0x6B8CFF
                    ),
                ),
                delete_after=45,
            )
        except Exception:
            return

    @staticmethod
    def _is_restricted_channel_name(name: str) -> bool:
        lowered = str(name or "").strip().lower()
        if not lowered:
            return False
        restricted_keywords = (
            "staff",
            "admin",
            "moderator",
            "mod-",
            "audit",
            "log",
            "private",
            "internal",
            "owner",
            "developer",
            "dev-",
            "console",
            "billing-admin",
        )
        return any(token in lowered for token in restricted_keywords)

    def _build_guild_channel_reference_for_prompt(
        self, message: discord.Message, *, full_context: bool = False
    ) -> str:
        guild = getattr(message, "guild", None)
        author = getattr(message, "author", None)
        if not guild or not isinstance(author, discord.Member):
            return ""

        category_limit = 120 if full_context else 60
        per_category_channel_limit = 20 if full_context else 8
        category_line_max_chars = 900 if full_context else 420
        uncategorized_limit = 40 if full_context else 12
        restricted_limit = 50 if full_context else 18
        output_line_limit = 80 if full_context else 28

        category_lines: list[str] = []
        uncategorized_lines: list[str] = []
        restricted_lines: list[str] = []

        categories = sorted(
            list(getattr(guild, "categories", []) or []),
            key=lambda c: getattr(c, "position", 0),
        )
        for category in categories[:category_limit]:
            visible_channels: list[str] = []
            for ch in list(getattr(category, "channels", []) or []):
                try:
                    perms = ch.permissions_for(author)
                    if not bool(getattr(perms, "view_channel", False)):
                        continue
                except Exception:
                    continue
                channel_name = str(getattr(ch, "name", "") or "").strip()
                if not channel_name:
                    continue
                channel_id = str(getattr(ch, "id", "") or "").strip()
                channel_mention = f"<#{channel_id}>" if channel_id.isdigit() else f"#{channel_name}"
                kind = getattr(ch, "type", None)
                kind_text = str(kind).split(".")[-1] if kind is not None else "channel"
                purpose = ""
                topic = self._safe_profile_text(getattr(ch, "topic", ""), 80, default="")
                if topic:
                    purpose = f" ({topic})"
                visible_channels.append(f"{channel_mention} [{kind_text}] ({channel_name}){purpose}"[:140])
                if self._is_restricted_channel_name(channel_name) or self._is_restricted_channel_name(
                    getattr(category, "name", "")
                ):
                    restricted_lines.append(f"{category.name}/{channel_name}")
            if visible_channels:
                category_name = str(getattr(category, "name", "") or "Uncategorized").strip()
                category_lines.append(
                    (f"- {category_name}: " + " | ".join(visible_channels[:per_category_channel_limit]))[
                        :category_line_max_chars
                    ]
                )

        for ch in list(getattr(guild, "text_channels", []) or [])[:120]:
            if getattr(ch, "category", None) is not None:
                continue
            try:
                perms = ch.permissions_for(author)
                if not bool(getattr(perms, "view_channel", False)):
                    continue
            except Exception:
                continue
            name = str(getattr(ch, "name", "") or "").strip()
            if not name:
                continue
            ch_id = str(getattr(ch, "id", "") or "").strip()
            mention = f"<#{ch_id}>" if ch_id.isdigit() else f"#{name}"
            uncategorized_lines.append(f"{mention} ({name})")

        out_lines: list[str] = []
        out_lines.append("Visible guild channel map for this user:")
        out_lines.extend(category_lines[:18])
        if uncategorized_lines:
            out_lines.append("- Uncategorized: " + " | ".join(uncategorized_lines[:uncategorized_limit]))
        if restricted_lines:
            out_lines.append(
                "Restricted/staff-like channels (avoid directing general users there): "
                + ", ".join(restricted_lines[:restricted_limit])
            )
        return "\n".join(out_lines[:output_line_limit])

    def _find_related_commands(self, text: str, limit: int = 8) -> list[str]:
        normalized = str(text or "").strip().lower()
        if not normalized:
            return []

        words = [word for word in re.findall(r"[a-zA-Z\u0E00-\u0E7F0-9_]+", normalized) if len(word) >= 2]
        if not words:
            return []

        hits = []
        seen = set()
        for command in self.bot.walk_commands():
            if getattr(command, "hidden", False):
                continue
            qualified_name = str(getattr(command, "qualified_name", "") or "").strip()
            if not qualified_name:
                continue
            haystack = f"{qualified_name} {str(getattr(command, 'help', '') or '')}".lower()
            score = sum(1 for word in words if word in haystack)
            if score <= 0:
                continue
            if qualified_name in seen:
                continue
            seen.add(qualified_name)
            hits.append((score, qualified_name))

        hits.sort(key=lambda item: (-item[0], item[1]))
        return [name for _, name in hits[:limit]]

    def _is_command_help_query(self, text: str) -> bool:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return False
        keywords = [
            "คำสั่ง",
            "command",
            "commands",
            "ใช้ยังไง",
            "วิธีใช้",
            "setup",
            "config",
            "ตั้งค่า",
            "ticket",
            "music",
            "welcomer",
            "automod",
            "antinuke",
            "aichat",
            "promote",
            "invite",
            "เชิญบอท",
        ]
        return any(keyword in lowered for keyword in keywords)

    def _format_existing_commands(self, prefix: str, commands_list: list[str]) -> list[str]:
        formatted = []
        for command_name in commands_list:
            if self.bot.get_command(command_name):
                formatted.append(f"`{prefix}{command_name}` / `/{command_name}`")
        return formatted

    def _build_detailed_manual(self, topic: str, prefix: str) -> str | None:
        topic = str(topic or "").strip().lower()

        if topic == "ticket":
            commands_list = self._format_existing_commands(
                prefix, ["ticket", "ticket setup"]
            )
            commands_text = "\n".join([f"- {item}" for item in commands_list]) or "- `ticket`"
            return (
                "SkylineBOT Ticket Manual\n"
                "1) Make sure you have `Administrator` permission (or the required bot setup permissions).\n"
                "2) Open ticket setup and run these commands:\n"
                f"{commands_text}\n"
                "3) In setup, configure support role, category, and ticket panel channel.\n"
                "4) Test by opening one ticket and then close/manage it to verify permissions.\n"
                "5) If panel does not appear, check bot permissions: `View Channel` and `Send Messages`."
            )

        if topic == "music":
            commands_list = self._format_existing_commands(
                prefix, ["music", "music setup", "music reset", "play"]
            )
            commands_text = "\n".join([f"- {item}" for item in commands_list]) or "- `music`"
            return (
                "SkylineBOT Music Manual\n"
                "1) Run setup commands:\n"
                f"{commands_text}\n"
                "2) Use `music setup` once to create request/voice channels.\n"
                "3) Join a voice channel and use `play <song>` or `/play`.\n"
                "4) Use `music reset` to clear current music setup.\n"
                "5) If playback fails, check Lavalink and bot `Connect/Speak` permissions."
            )

        if topic == "aichat":
            commands_list = self._format_existing_commands(
                prefix, ["aichat", "aichat setting", "aichat remove"]
            )
            commands_text = "\n".join([f"- {item}" for item in commands_list]) or "- `aichat`"
            return (
                "SkylineBOT AI Chat Manual\n"
                "1) Configure AI channels first:\n"
                f"{commands_text}\n"
                "2) After setup, the bot responds only in configured channels.\n"
                "3) This setup uses local Ollama; if Ollama is down, replies will fail.\n"
                "4) Use `aichat remove` to disable AI chat in the server.\n"
                "5) Use `aichat setting` to update channel configuration."
            )

        if topic == "automod":
            commands_list = self._format_existing_commands(
                prefix, ["automod", "antispam", "antilink", "antibadwords"]
            )
            commands_text = "\n".join([f"- {item}" for item in commands_list]) or "- `automod`"
            return (
                "SkylineBOT AutoMod Manual\n"
                "1) Open the `automod` menu first and choose the needed module:\n"
                f"{commands_text}\n"
                "2) Start with AntiSpam to reduce flood/duplicate messages.\n"
                "3) Enable AntiLink and AntiBadWords based on your server policy.\n"
                "4) Test with a secondary account before full rollout.\n"
                "5) If too strict, tune thresholds and whitelist trusted roles/channels."
            )

        if topic == "antinuke":
            commands_list = self._format_existing_commands(
                prefix, ["antinuke", "whitelist"]
            )
            commands_text = "\n".join([f"- {item}" for item in commands_list]) or "- `antinuke`"
            return (
                "SkylineBOT AntiNuke Manual\n"
                "1) Enable AntiNuke and configure core commands:\n"
                f"{commands_text}\n"
                "2) Choose punishment actions carefully (warn/kick/ban/mute).\n"
                "3) Add trusted admins to whitelist before enabling strict protection.\n"
                "4) Simulate risky actions in a test environment first.\n"
                "5) Keep audit/log channels enabled for incident review."
            )

        if topic == "welcomer":
            commands_list = self._format_existing_commands(
                prefix, ["welcomer", "welcome", "autorole", "autonick", "greet"]
            )
            commands_text = "\n".join([f"- {item}" for item in commands_list]) or "- `welcomer`"
            return (
                "SkylineBOT Welcomer Manual\n"
                "1) Open `welcomer` and select the welcome mode:\n"
                f"{commands_text}\n"
                "2) Set welcome channel, message, and mention behavior.\n"
                "3) For autorole, ensure bot role is above target roles.\n"
                "4) Test with a secondary account join/leave flow.\n"
                "5) If messages do not send, check `Send Messages` and `Embed Links`."
            )

        if topic == "promote":
            commands_list = self._format_existing_commands(
                prefix, ["promote", "promote setup", "promote delead"]
            )
            commands_text = "\n".join([f"- {item}" for item in commands_list]) or "- `promote`"
            return (
                "SkylineBOT Promote Manual\n"
                "1) Configure submit/public channels first:\n"
                f"{commands_text}\n"
                "2) Post announcements in submit channel for admin review.\n"
                "3) Approved posts are distributed to configured public channels.\n"
                "4) Cooldown is applied automatically to reduce spam.\n"
                "5) Use `promote delead` to disable/reset promotion flow."
            )

        return None

    def _contains_cjk(self, text: str) -> bool:
        return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", str(text or "")))

    @staticmethod
    def _looks_like_translation_or_quote_request(text: str) -> bool:
        raw = str(text or "")
        lowered = raw.lower()
        translation_tokens = (
            "แปล",
            "translate",
            "translation",
            "ถอดความ",
            "meaning",
        )
        asks_translation = any(token in lowered for token in translation_tokens)
        if not asks_translation:
            return False
        quoted_like = (
            '"' in raw
            or "'" in raw
            or "```" in raw
            or "“" in raw
            or "”" in raw
            or "\n" in raw
        )
        return quoted_like

    def _is_malicious_request(self, text: str) -> bool:
        lowered = str(text or "").lower()
        if self._looks_like_translation_or_quote_request(text):
            return False

        safe_context_tokens = (
            "ป้องกัน",
            "ป้องกันยังไง",
            "security",
            "secure",
            "how to protect",
            "วิธีป้องกัน",
        )
        if any(token in lowered for token in safe_context_tokens):
            return False

        blocked_keywords = [
            "token grabber", "tokengrabber", "grab token", "stealer", "cookie logger",
            "ดักโทเคน", "ขโมยโทเคน", "ขโมย token", "แฮกบัญชี", "ขโมยรหัส", "phishing",
            "bypass 2fa", "credential theft", "malware", "ransomware",
        ]
        if not any(keyword in lowered for keyword in blocked_keywords):
            return False

        action_tokens = (
            "ทำ",
            "สร้าง",
            "เขียน",
            "สอน",
            "วิธี",
            "how to",
            "make",
            "build",
            "code",
            "script",
            "bypass",
            "steal",
            "hack",
        )
        return any(token in lowered for token in action_tokens)

    def _safe_refusal_text(self, content: str) -> str:
        if re.search(r"[ก-๙]", str(content or "")):
            return "ขอโทษครับ ผมไม่สามารถช่วยเรื่องขโมยโทเคน/แฮก/มัลแวร์ได้ แต่ช่วยแนะนำการป้องกันบัญชีและความปลอดภัยเซิร์ฟเวอร์แทนได้ครับ"
        return "Sorry, I can't help with token theft, hacking, phishing, or malware. I can help with account/server security instead."

    def _sanitize_discord_oauth_links(self, text: str) -> str:
        source = str(text or "")
        if not source:
            return source

        def _fix_url(match: re.Match) -> str:
            raw_url = match.group(0)
            try:
                parsed = urlsplit(raw_url)
                if parsed.netloc.lower() != "discord.com" or parsed.path != "/oauth2/authorize":
                    return raw_url
                pairs = parse_qsl(parsed.query, keep_blank_values=True)
                normalized = []
                client_id_value = ""
                permissions_value = ""
                for key, value in pairs:
                    key_text = str(key or "").strip().lower()
                    value_text = str(value or "").strip()
                    if key_text == "client_id" and value_text:
                        client_id_value = value_text
                    elif key_text == "permissions" and value_text:
                        permissions_value = value_text
                    elif key_text in {"scope", "integration", "integration_type"}:
                        continue
                if not client_id_value:
                    client_id_value = str(getattr(self.bot.user, "id", "") or "")
                if not permissions_value:
                    permissions_value = "8"
                if client_id_value:
                    normalized.append(("client_id", client_id_value))
                normalized.append(("permissions", permissions_value))
                normalized.append(("scope", "bot applications.commands"))
                fixed_query = urlencode(normalized)
                return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, fixed_query, parsed.fragment))
            except Exception:
                return raw_url

        # Avoid swallowing trailing ')' from markdown links.
        return re.sub(r"https://discord\.com/oauth2/authorize\?[^\s\)]+", _fix_url, source)

    @staticmethod
    def _repair_markdown_links(text: str) -> str:
        source = str(text or "")
        if not source:
            return source
        fixed = source
        # Simplify redundant self-referential markdown links.
        fixed = re.sub(
            r"\[(https?://[^\]\s]+)\]\(\1\)",
            r"\1",
            fixed,
            flags=re.IGNORECASE,
        )
        # Repair missing closing ')' for markdown URLs that end the line.
        fixed_lines: list[str] = []
        for line in fixed.split("\n"):
            repaired = re.sub(
                r"\[([^\]]+)\]\((https?://[^\s\)]+)\s*$",
                r"[\1](\2)",
                line,
                flags=re.IGNORECASE,
            )
            fixed_lines.append(repaired)
        return "\n".join(fixed_lines)

    def _log_ai_reply_anomaly(
        self,
        message: discord.Message | None,
        source: str,
        reason: str,
        raw_reply: str,
        normalized_reply: str = "",
        user_content: str = "",
    ) -> None:
        try:
            guild_id = getattr(getattr(message, "guild", None), "id", None) if message else None
            channel_id = getattr(getattr(message, "channel", None), "id", None) if message else None
            user_id = getattr(getattr(message, "author", None), "id", None) if message else None
            user_preview = re.sub(r"\s+", " ", str(user_content or "")).strip()[:220]
            raw_preview = re.sub(r"\s+", " ", str(raw_reply or "")).strip()[:320]
            normalized_preview = re.sub(r"\s+", " ", str(normalized_reply or "")).strip()[:320]
            log_message = (
                "AI reply anomaly | "
                f"source={source} | reason={reason} | guild={guild_id} | channel={channel_id} | user={user_id} | "
                f"user_input='{user_preview}' | raw_reply='{raw_preview}' | normalized_reply='{normalized_preview}'"
            )
            reasons_set = {item.strip() for item in str(reason or "").split(",") if item.strip()}
            low_noise_reasons = {
                "oauth_scope_sanitized",
                "markdown_links_repaired",
                "table_rewritten_for_discord",
                "reply_truncated",
                "polite_style_normalized",
            }
            high_signal_reasons = {
                "contains_cjk",
                "translated_scope_detected",
                "reasoning_block_removed",
            }
            if reasons_set == {"polite_style_normalized"}:
                logger.debug(log_message)
            elif reasons_set and reasons_set.issubset(low_noise_reasons):
                logger.info(log_message)
            elif reasons_set & high_signal_reasons:
                logger.warning(log_message)
            else:
                logger.info(log_message)
        except Exception:
            pass

    @staticmethod
    def _is_discord_rate_limit_error(error: Exception) -> bool:
        if not isinstance(error, discord.HTTPException):
            return False
        status = getattr(error, "status", None)
        code = getattr(error, "code", None)
        text = str(getattr(error, "text", "") or "").lower()
        return (
            status == 429
            or code in {20028, 20029, 40062}
            or "rate limit" in text
            or "too many requests" in text
        )

    @staticmethod
    def _parse_color_hex_to_int(raw_color: str, fallback: int = 0x6B8CFF) -> int:
        text = str(raw_color or "").strip()
        if not text:
            return int(fallback)
        lowered = text.lower()
        named = {
            "red": 0xED4245,
            "green": 0x57F287,
            "blue": 0x3498DB,
            "orange": 0xF39C12,
            "yellow": 0xF1C40F,
            "purple": 0x9B59B6,
            "pink": 0xE91E63,
            "aqua": 0x1ABC9C,
            "gray": 0x95A5A6,
        }
        if lowered in named:
            return int(named[lowered])
        cleaned = text.lstrip("#").strip()
        if cleaned.lower().startswith("0x"):
            cleaned = cleaned[2:]
        if not re.fullmatch(r"[0-9a-fA-F]{6}", cleaned):
            return int(fallback)
        try:
            return int(cleaned, 16)
        except Exception:
            return int(fallback)

    @staticmethod
    def _wants_embed_response(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        if not lowered:
            return False
        keywords = (
            "embed",
            "emded",
            "เอ็มเบด",
            "ส่งเป็นการ์ด",
            "rich message",
            "card message",
        )
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _wants_reaction_response(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        if not lowered:
            return False
        keywords = (
            "reaction",
            "react",
            "รีแอค",
            "รีแอคชั่น",
            "ใส่อิโมจิ",
            "เพิ่มรีเอค",
        )
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _extract_reaction_tokens(raw_text: str, limit: int = 4) -> list[str]:
        text = str(raw_text or "").strip()
        if not text:
            return []
        custom = re.findall(r"<a?:[A-Za-z0-9_]{2,32}:\d{15,22}>", text)
        unicode_emoji = re.findall(r"[\U0001F1E6-\U0001FAFF\u2600-\u27BF]", text)
        ordered: list[str] = []
        seen = set()
        for token in [*custom, *unicode_emoji]:
            value = str(token or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
            if len(ordered) >= max(1, int(limit)):
                break
        return ordered

    def _parse_ai_reply_payload(self, reply_text: str, user_text: str) -> dict[str, Any]:
        raw = str(reply_text or "").strip()
        working = raw

        def _extract_tag(tag: str) -> str:
            nonlocal working
            pattern = re.compile(rf"\[{tag}\s*:\s*(.*?)\]", re.IGNORECASE | re.DOTALL)
            match = pattern.search(working)
            if not match:
                return ""
            value = str(match.group(1) or "").strip()
            working = pattern.sub("", working, count=1)
            return value

        embed_title = _extract_tag("EMBED_TITLE")
        embed_desc = _extract_tag("EMBED_DESC") or _extract_tag("EMBED_DESCRIPTION")
        embed_color = _extract_tag("EMBED_COLOR")
        reaction_tag = _extract_tag("REACTIONS")

        cleaned_text = re.sub(r"\n{3,}", "\n\n", working).strip()
        wants_embed = self.ai_response_embed_enabled and (
            bool(embed_title or embed_desc) or self._wants_embed_response(user_text)
        )
        wants_react = self.ai_response_reaction_enabled and (
            bool(reaction_tag) or self._wants_reaction_response(user_text)
        )

        payload: dict[str, Any] = {
            "content": cleaned_text,
            "embed": None,
            "reactions": [],
        }

        if wants_embed:
            color_int = self._parse_color_hex_to_int(
                embed_color or self.ai_response_embed_default_color,
                fallback=0x6B8CFF,
            )
            title = str(embed_title or "SkylineBOT AI").strip()[:256]
            description = str(embed_desc or cleaned_text or "").strip()[:4000]
            if description:
                payload["embed"] = {
                    "title": title,
                    "description": description,
                    "color": color_int,
                }
                payload["content"] = ""

        reaction_source = reaction_tag
        if not reaction_source and wants_react:
            reaction_source = self.ai_response_default_reactions_raw or "✅"
        if reaction_source:
            payload["reactions"] = self._extract_reaction_tokens(reaction_source, limit=4)

        return payload

    @staticmethod
    def _split_text_for_discord(text: str, *, limit: int = 1850, max_chunks: int = 6) -> list[str]:
        raw = str(text or "").strip()
        if not raw:
            return []
        max_len = max(400, int(limit))
        max_parts = max(1, int(max_chunks))
        chunks: list[str] = []
        remaining = raw
        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break
            candidate = remaining[:max_len]
            cut = max(
                candidate.rfind("\n\n"),
                candidate.rfind("\n"),
                candidate.rfind(". "),
                candidate.rfind("! "),
                candidate.rfind("? "),
                candidate.rfind(" "),
            )
            if cut < int(max_len * 0.55):
                cut = max_len
            chunk = remaining[:cut].strip()
            if not chunk:
                chunk = remaining[:max_len].strip()
                cut = max_len
            chunks.append(chunk)
            remaining = remaining[cut:].lstrip()
            if len(chunks) >= max_parts and remaining:
                chunks[-1] = chunks[-1].rstrip() + "\n\n... (ตัดข้อความส่วนเกินเพื่อไม่ให้ยาวเกินไป)"
                break
        return chunks

    async def _safe_ai_reply_payload(
        self,
        message: discord.Message,
        payload: dict[str, Any],
    ) -> bool:
        content = str((payload or {}).get("content") or "").strip()
        embed_data = (payload or {}).get("embed") if isinstance(payload, dict) else None
        reactions = list((payload or {}).get("reactions") or []) if isinstance(payload, dict) else []

        embed_obj = None
        if isinstance(embed_data, dict):
            desc = str(embed_data.get("description") or "").strip()
            title = str(embed_data.get("title") or "").strip()
            if desc:
                embed_obj = discord.Embed(
                    title=title[:256] if title else discord.Embed.Empty,
                    description=desc[:4000],
                    color=int(embed_data.get("color") or 0x6B8CFF),
                )

        if not content and embed_obj is None:
            return False

        try:
            sent_message = None
            if embed_obj is not None:
                sent_message = await message.reply(
                    content if content else None,
                    embed=embed_obj,
                    mention_author=False,
                )
            else:
                chunks = self._split_text_for_discord(content, limit=1850, max_chunks=8)
                if not chunks:
                    return False
                first_chunk = chunks[0]
                sent_message = await message.reply(
                    first_chunk,
                    mention_author=False,
                )
                for extra_chunk in chunks[1:]:
                    try:
                        await message.channel.send(extra_chunk)
                    except Exception:
                        break
            if sent_message and reactions:
                for emoji in reactions[:4]:
                    try:
                        await sent_message.add_reaction(str(emoji))
                    except Exception:
                        continue
            return True
        except discord.HTTPException as error:
            if self._is_discord_rate_limit_error(error):
                logger.warning(
                    "AI reply payload skipped due to Discord rate limit | "
                    f"guild={getattr(getattr(message, 'guild', None), 'id', 'unknown')} "
                    f"channel={getattr(getattr(message, 'channel', None), 'id', 'unknown')} "
                    f"status={getattr(error, 'status', None)} code={getattr(error, 'code', None)}"
                )
            else:
                logger.warning(
                    "AI reply payload skipped due to Discord HTTP error | "
                    f"guild={getattr(getattr(message, 'guild', None), 'id', 'unknown')} "
                    f"channel={getattr(getattr(message, 'channel', None), 'id', 'unknown')} "
                    f"status={getattr(error, 'status', None)} code={getattr(error, 'code', None)}"
                )
            return False
        except Exception:
            return False

    async def _safe_ai_reply(self, message: discord.Message, content: str) -> bool:
        payload = self._parse_ai_reply_payload(str(content or "").strip(), "")
        return await self._safe_ai_reply_payload(message, payload)

    async def _safe_ai_reply_smart(
        self, message: discord.Message, content: str, *, user_text: str
    ) -> bool:
        payload = self._parse_ai_reply_payload(str(content or "").strip(), str(user_text or ""))
        return await self._safe_ai_reply_payload(message, payload)

    async def _safe_ai_notice(
        self,
        message: discord.Message,
        *,
        description: str,
        embed_color: int,
        delete_after: int = 15,
        throttle_key: str | None = None,
        throttle_seconds: int = 300,
    ) -> bool:
        guild_id = getattr(getattr(message, "guild", None), "id", None)
        if throttle_key and guild_id is not None:
            key = (int(guild_id), str(throttle_key))
            now = time.time()
            if now < self.ai_notice_cooldowns[key]:
                return False
            self.ai_notice_cooldowns[key] = now + max(int(throttle_seconds), 1)

        try:
            await message.channel.send(
                embed=discord.Embed(description=description, color=embed_color),
                delete_after=delete_after,
            )
            return True
        except discord.HTTPException as error:
            if self._is_discord_rate_limit_error(error):
                logger.warning(
                    "AI notice skipped due to Discord rate limit | "
                    f"guild={guild_id} channel={getattr(getattr(message, 'channel', None), 'id', 'unknown')} "
                    f"status={getattr(error, 'status', None)} code={getattr(error, 'code', None)}"
                )
            else:
                logger.warning(
                    "AI notice skipped due to Discord HTTP error | "
                    f"guild={guild_id} channel={getattr(getattr(message, 'channel', None), 'id', 'unknown')} "
                    f"status={getattr(error, 'status', None)} code={getattr(error, 'code', None)}"
                )
            return False
        except Exception:
            return False

    @asynccontextmanager
    async def _safe_typing(self, message: discord.Message):
        typing_ctx = None
        entered = False
        try:
            typing_ctx = message.channel.typing()
            await typing_ctx.__aenter__()
            entered = True
        except discord.HTTPException as error:
            if self._is_discord_rate_limit_error(error):
                logger.warning(
                    "Typing indicator skipped due to Discord rate limit | "
                    f"guild={getattr(getattr(message, 'guild', None), 'id', 'unknown')} "
                    f"channel={getattr(getattr(message, 'channel', None), 'id', 'unknown')} "
                    f"status={getattr(error, 'status', None)} code={getattr(error, 'code', None)}"
                )
            else:
                logger.warning(
                    "Typing indicator failed | "
                    f"guild={getattr(getattr(message, 'guild', None), 'id', 'unknown')} "
                    f"channel={getattr(getattr(message, 'channel', None), 'id', 'unknown')} "
                    f"status={getattr(error, 'status', None)} code={getattr(error, 'code', None)}"
                )
        except Exception:
            pass

        try:
            yield
        finally:
            if entered and typing_ctx is not None:
                try:
                    await typing_ctx.__aexit__(None, None, None)
                except Exception:
                    pass

    @staticmethod
    def _guild_has_active_music(guild: discord.Guild | None) -> bool:
        if guild is None:
            return False
        vc = getattr(guild, "voice_client", None)
        if vc is None:
            return False
        return bool(
            getattr(vc, "playing", False)
            or getattr(vc, "paused", False)
            or getattr(vc, "current", None) is not None
        )

    @staticmethod
    def _is_music_setup_channel(guild_id: int, channel_id: int) -> bool:
        music_data = cache.music.get(str(guild_id), {})
        setup_channel_id = music_data.get("music_setup_channel_id")
        try:
            return int(setup_channel_id or 0) == int(channel_id)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _music_pending_pick_message_ids(
        music_cog: commands.Cog | None,
        guild_id: int,
        channel_id: int,
    ) -> set[int]:
        message_ids: set[int] = set()
        if music_cog is None:
            return message_ids
        try:
            pending_map = getattr(music_cog, "_pending_track_picks", {}) or {}
            for (entry_guild_id, entry_channel_id, _entry_user_id), payload in list(
                pending_map.items()
            ):
                if int(entry_guild_id) != int(guild_id):
                    continue
                if int(entry_channel_id) != int(channel_id):
                    continue
                for key in ("prompt_message_id", "gate_message_id"):
                    try:
                        message_id = int((payload or {}).get(key) or 0)
                    except (TypeError, ValueError):
                        message_id = 0
                    if message_id > 0:
                        message_ids.add(message_id)
        except Exception:
            pass
        return message_ids

    def _is_direct_ai_message_to_bot(self, message: discord.Message) -> bool:
        bot_user = getattr(self.bot, "user", None)
        if not bot_user:
            return False

        try:
            if bot_user.mentioned_in(message):
                return True
        except Exception:
            pass

        try:
            reference = getattr(message, "reference", None)
            if reference is None:
                return False
            resolved = getattr(reference, "resolved", None)
            resolved_author_id = getattr(getattr(resolved, "author", None), "id", None)
            if resolved_author_id and int(resolved_author_id) == int(bot_user.id):
                return True
            cached_reply = getattr(reference, "cached_message", None)
            cached_author_id = getattr(getattr(cached_reply, "author", None), "id", None)
            if cached_author_id and int(cached_author_id) == int(bot_user.id):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _ai_reply_chance(ai_data: dict[str, Any]) -> int:
        try:
            chance = int((ai_data or {}).get("reply_chance") or 100)
        except Exception:
            chance = 100
        return max(1, min(100, chance))

    @staticmethod
    def _on_ai_task_done(task: asyncio.Task) -> None:
        try:
            error = task.exception()
        except asyncio.CancelledError:
            return
        except Exception:
            return
        if error:
            logger.error(
                f"AI background task failed: {type(error).__name__}: {str(error)[:220]}"
            )

    def _detect_manual_topic(self, lowered_text: str) -> str | None:
        text = str(lowered_text or "")
        topic_keywords: dict[str, tuple[str, ...]] = {
            "music": ("music", "เพลง", "play", "queue", "lavalink"),
            "ticket": ("ticket", "ทิกเก็ต"),
            "aichat": ("aichat", "ai chat", "แชต ai", "แชท ai"),
            "automod": ("automod", "antispam", "antilink", "antibadwords"),
            "antinuke": ("antinuke", "whitelist"),
            "welcomer": ("welcomer", "welcome", "autorole", "autonick"),
            "promote": ("promote", "โปรโมท"),
        }
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                return topic
        return None

    def _collect_command_names_for_roots(
        self,
        roots: list[str] | tuple[str, ...],
        *,
        limit: int = 20,
    ) -> list[str]:
        root_tokens = [str(root or "").strip().lower() for root in list(roots or []) if str(root or "").strip()]
        if not root_tokens:
            return []
        records = self._refresh_ai_command_records(limit=1400)
        matched: list[str] = []
        seen = set()
        for row in records:
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            lowered = name.lower()
            if not any(lowered == root or lowered.startswith(f"{root} ") for root in root_tokens):
                continue
            if name in seen:
                continue
            seen.add(name)
            matched.append(name)
            if len(matched) >= max(4, int(limit)):
                break
        matched.sort(key=lambda value: (value.count(" "), value))
        return matched[: max(4, int(limit))]

    @staticmethod
    def _format_prefixed_command_lines(prefix: str, command_names: list[str], *, limit: int = 10) -> str:
        safe_prefix = str(prefix or "!").strip() or "!"
        rows: list[str] = []
        for name in list(command_names or [])[: max(1, int(limit))]:
            cmd = str(name or "").strip()
            if not cmd:
                continue
            rows.append(f"- `{safe_prefix}{cmd}` / `/{cmd}`")
        return "\n".join(rows)

    @staticmethod
    def _to_channel_mention(raw_channel_id: Any) -> str:
        try:
            channel_id = int(str(raw_channel_id or "").strip())
        except (TypeError, ValueError):
            return ""
        if channel_id <= 0:
            return ""
        return f"<#{channel_id}>"

    def _resolve_music_setup_mentions(self, guild_id: int) -> tuple[str, str]:
        music_data = cache.music.get(str(guild_id), {}) or {}
        request_mention = self._to_channel_mention(music_data.get("music_setup_channel_id"))
        voice_mention = self._to_channel_mention(
            music_data.get("music_setup_voice_channel_id") or music_data.get("music_voice_channel_id")
        )
        return request_mention, voice_mention

    def _build_ai_music_room_guidance_text(self, guild_id: int, guild_prefix: str) -> str:
        prefix_text = str(guild_prefix or BotConfig.PREFIX).strip() or "!"
        request_mention, voice_mention = self._resolve_music_setup_mentions(guild_id)
        if request_mention and voice_mention:
            return (
                "ห้อง AI ไม่รับคำสั่งเพลงผ่านระบบ AI ครับ\n"
                f"ถ้าต้องการเปิดเพลง ให้พิมพ์ที่ {request_mention}\n"
                f"และเข้าไปรอในห้องเสียง {voice_mention}\n"
                f"คำสั่งที่ใช้: `{prefix_text}play <ชื่อเพลง>` หรือ `/play`"
            )
        if request_mention:
            return (
                "ห้อง AI ไม่รับคำสั่งเพลงผ่านระบบ AI ครับ\n"
                f"ให้ไปพิมพ์ที่ {request_mention} ด้วย `{prefix_text}play <ชื่อเพลง>` หรือ `/play`\n"
                f"ถ้ายังไม่มีห้องเสียงเพลง ให้แอดมินตั้งค่า `{prefix_text}music setup` ก่อนครับ"
            )
        return (
            "ห้อง AI ไม่รับคำสั่งเพลงผ่านระบบ AI ครับ\n"
            f"ให้แอดมินตั้งค่าห้องเพลงก่อนด้วย `{prefix_text}music setup` หรือ `/music setup`\n"
            "แล้วค่อยใช้คำสั่งเพลงในห้องที่บอทตั้งค่าไว้ครับ"
        )

    def _resolve_music_setup_channels(
        self, guild: discord.Guild | None
    ) -> tuple[discord.TextChannel | None, discord.abc.GuildChannel | None]:
        if guild is None:
            return None, None
        music_data = cache.music.get(str(guild.id), {}) or {}
        try:
            request_channel_id = int(music_data.get("music_setup_channel_id") or 0)
        except (TypeError, ValueError):
            request_channel_id = 0
        try:
            voice_channel_id = int(
                (music_data.get("music_setup_voice_channel_id") or music_data.get("music_voice_channel_id"))
                or 0
            )
        except (TypeError, ValueError):
            voice_channel_id = 0

        request_channel = (
            guild.get_channel(request_channel_id)
            if request_channel_id > 0
            else None
        )
        voice_channel = (
            guild.get_channel(voice_channel_id)
            if voice_channel_id > 0
            else None
        )
        if request_channel is not None and not isinstance(request_channel, discord.TextChannel):
            request_channel = None
        return request_channel, voice_channel

    @staticmethod
    def _build_ai_music_suggestion_queries(text: str) -> list[str]:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return ["Blackbeans - Pink", "Three Man Down - ฝนตกไหม", "Jeff Satur - Dum Dum"]

        keyword_map: list[tuple[tuple[str, ...], list[str]]] = [
            (
                ("lofi", "ชิล", "chill", "ทำงาน", "อ่านหนังสือ"),
                [
                    "Lofi Girl beats to relax/study to",
                    "NONT TANONT - โต๊ะริม (lofi remix)",
                    "YENTED - ลืมไปแล้วว่าลืมยังไง",
                ],
            ),
            (
                ("kpop", "เคป็อป", "เกาหลี"),
                [
                    "NewJeans - Super Shy",
                    "LE SSERAFIM - PERFECT NIGHT",
                    "IVE - I AM",
                ],
            ),
            (
                ("jpop", "เจป็อป", "ญี่ปุ่น", "anime", "อนิเมะ"),
                [
                    "YOASOBI - Idol",
                    "Ado - Show",
                    "Official HIGE DANDism - Subtitle",
                ],
            ),
            (
                ("อกหัก", "เศร้า", "sad"),
                [
                    "Tilly Birds - คิด(แต่ไม่)ถึง",
                    "Musketeers - ของขวัญ",
                    "Anatomy Rabbit - ธรรมดาแสนพิเศษ",
                ],
            ),
        ]
        for keywords, queries in keyword_map:
            if any(keyword in lowered for keyword in keywords):
                return list(queries)
        return ["Blackbeans - Pink", "Three Man Down - ฝนตกไหม", "Tilly Birds - เพื่อนเล่น ไม่เล่นเพื่อน"]

    @staticmethod
    def _is_ai_music_recommend_intent(text: str) -> bool:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return False
        translation_tokens = (
            "ภาษาอังกฤษ",
            "อังกฤษว่า",
            "english",
            "พูดยังไง",
            "พูดว่า",
            "เรียกว่าอะไร",
            "how to say",
            "say in english",
            "what to say",
        )
        if any(token in lowered for token in translation_tokens):
            return False
        direct_tokens = (
            "แนะนำเพลง",
            "เพลงอะไรดี",
            "มีเพลงอะไร",
            "หาเพลงฟัง",
            "ขอเพลง",
            "หาเพลง",
            "เพลงแนว",
            "song recommendation",
            "recommend song",
            "recommend music",
        )
        if any(token in lowered for token in direct_tokens):
            return True
        if re.search(r"(เพลง.*แนะนำ|แนะนำ.*เพลง)", lowered):
            return True
        if re.match(r"^(?:ช่วย\s*)?(?:ขอ|หา)\s*เพลง", lowered):
            return True
        return bool(re.match(r"^(?:เพลง|song)\s+แนว", lowered))

    @staticmethod
    def _is_music_phrase_translation_query(text: str) -> bool:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return False
        translation_tokens = (
            "ภาษาอังกฤษ",
            "อังกฤษว่า",
            "english",
            "พูดยังไง",
            "พูดว่า",
            "เรียกว่าอะไร",
            "how to say",
            "say in english",
            "what to say",
        )
        music_tokens = (
            "ขอเพลง",
            "เพลง",
            "เล่นเพลง",
            "เปิดเพลง",
            "request song",
            "recommend song",
            "song",
        )
        return any(token in lowered for token in translation_tokens) and any(
            token in lowered for token in music_tokens
        )

    @staticmethod
    def _is_non_specific_music_query(query: str) -> bool:
        lowered = str(query or "").strip().lower()
        if not lowered:
            return True
        lowered = re.sub(r"\s+", " ", lowered).strip()
        compact = re.sub(r"[\s`\"'“”‘’\[\]\(\)\.,!?？！:;~\-_/]+", "", lowered)
        fillers = {
            "หน่อย",
            "ที",
            "ทีนะ",
            "ทีครับ",
            "ทีคับ",
            "หน่อยครับ",
            "หน่อยคับ",
            "ได้ไหม",
            "ได้มั้ย",
            "ได้มะ",
            "ได้ปะ",
            "ได้ไหมครับ",
            "ได้ไหมคะ",
            "ไหม",
            "มั้ย",
            "มะ",
            "ปะ",
            "ครับ",
            "คับ",
            "ค้าบ",
            "นะ",
            "น้า",
        }
        if compact in fillers:
            return True
        if re.fullmatch(r"(?:ได้)?(?:ไหม|มั้ย|มะ|ปะ)(?:ครับ|คับ|ค้าบ|คะ)?", compact):
            return True
        if compact in {"เพลง", "song", "music"}:
            return True
        return False

    @staticmethod
    def _normalize_ai_music_text(text: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        replacements = (
            ("เปืด", "เปิด"),
            ("คเนหา", "ค้นหา"),
            ("ค้นห", "ค้นหา"),
            ("ขอ เพลง", "ขอเพลง"),
            ("หา เพลง", "หาเพลง"),
            ("เล่น เพลง", "เล่นเพลง"),
            ("เปิด เพลง", "เปิดเพลง"),
            ("ค้นหา เพลง", "ค้นหาเพลง"),
        )
        for source, target in replacements:
            normalized = normalized.replace(source, target)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _parse_ai_music_recommend_intent(self, text: str) -> tuple[bool, str]:
        raw = str(text or "").strip()
        if not raw:
            return False, ""
        lines = [
            self._normalize_ai_music_text(line)
            for line in re.split(r"[\r\n]+", raw)
            if str(line or "").strip()
        ]
        if not lines:
            lines = [self._normalize_ai_music_text(raw)]

        patterns = (
            r"^(?:ช่วย\s*)?(?:ขอ|หา|ค้นหา)\s*เพลง\s*(.*)$",
            r"^(?:ช่วย\s*)?(?:recommend|find)\s*(?:a|some)?\s*song(?:s)?\s*(.*)$",
            r"^(?:เพลง|song)\s*แนว\s*(.*)$",
        )
        for line in lines:
            lowered = str(line or "").strip().lower()
            if not lowered:
                continue
            if self._is_music_phrase_translation_query(lowered):
                return False, ""
            for pattern in patterns:
                matched = re.match(pattern, line, flags=re.IGNORECASE)
                if not matched:
                    continue
                query = str(matched.group(1) or "").strip()
                if query:
                    query = query.strip("`\"'“”‘’[]() ")
                    query = re.sub(r"\s+", " ", query).strip()
                    if self._is_non_specific_music_query(query):
                        query = ""
                return True, query
            if self._is_ai_music_recommend_intent(lowered):
                return True, ""
        return False, ""

    def _looks_like_music_action_text(self, text: str) -> bool:
        lowered = self._normalize_ai_music_text(text).lower()
        if not lowered:
            return False
        tokens = (
            "เปิดเพลง",
            "เล่นเพลง",
            "ขอเพลง",
            "หาเพลง",
            "ค้นหาเพลง",
            "ค้นเพลง",
            "song",
            "play ",
            "/play",
        )
        return any(token in lowered for token in tokens)

    @staticmethod
    def _parse_ai_music_recommendation_list(raw_text: str, *, limit: int = 3) -> list[str]:
        text = str(raw_text or "").strip()
        if not text:
            return []
        max_items = max(1, min(6, int(limit or 3)))
        candidates: list[str] = []

        # Prefer strict JSON if model follows the format.
        json_candidates: list[str] = []
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows = payload.get("songs")
                if isinstance(rows, list):
                    for item in rows:
                        value = str(item or "").strip()
                        if value:
                            json_candidates.append(value)
            elif isinstance(payload, list):
                for item in payload:
                    value = str(item or "").strip()
                    if value:
                        json_candidates.append(value)
        except Exception:
            pass

        if json_candidates:
            dedup = []
            seen = set()
            for row in json_candidates:
                normalized = re.sub(r"\s+", " ", row).strip("`\"' ")
                if not normalized or normalized.lower() in seen:
                    continue
                seen.add(normalized.lower())
                dedup.append(normalized)
                if len(dedup) >= max_items:
                    break
            return dedup

        # Fallback: parse line-based bullets/numbered list.
        for line in text.splitlines():
            row = str(line or "").strip()
            if not row:
                continue
            row = re.sub(r"^[\-\*\•\d\)\.\s🎵🎶]+", "", row).strip()
            row = row.strip("`\"' ")
            if not row:
                continue
            lowered = row.lower()
            if any(token in lowered for token in ("เพลงแนะนำ", "ลองฟัง", "คำอธิบาย", "แนวเพลง")):
                continue
            if len(row) < 3 or len(row) > 90:
                continue
            candidates.append(re.sub(r"\s+", " ", row))
            if len(candidates) >= max_items:
                break

        dedup = []
        seen = set()
        for row in candidates:
            key = row.lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(row)
            if len(dedup) >= max_items:
                break
        return dedup

    async def _ask_ai_music_recommendations(
        self,
        user_text: str,
        *,
        limit: int = 3,
    ) -> list[str]:
        max_items = max(1, min(5, int(limit or 3)))
        system_prompt = (
            "You are a music recommendation assistant for Discord users.\n"
            "Return recommendations as JSON only.\n"
            "Required format: {\"songs\": [\"Artist - Song\", \"Artist - Song\", \"Artist - Song\"]}\n"
            f"Rules: return exactly {max_items} songs, no markdown, no explanations."
        )
        user_prompt = (
            "แนะนำเพลงให้ผู้ใช้จากข้อความนี้:\n"
            f"{str(user_text or '').strip()[:400]}\n\n"
            "เงื่อนไข:\n"
            "- เน้นเพลงที่น่าฟังจริงและค้นหาเจอง่าย\n"
            "- ตอบเป็น JSON ตาม format เท่านั้น"
        )
        messages_payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            reply_text = await asyncio.wait_for(
                self.ask_ai_model(
                    user_prompt,
                    system_prompt,
                    messages_payload=messages_payload,
                ),
                timeout=14,
            )
            parsed = self._parse_ai_music_recommendation_list(reply_text, limit=max_items)
            if parsed:
                return parsed[:max_items]
        except Exception:
            pass
        return self._build_ai_music_suggestion_queries(user_text)[:max_items]

    @staticmethod
    def _list_ai_joinable_voice_channels(
        guild: discord.Guild | None,
        member: discord.Member | None,
        *,
        limit: int = 12,
    ) -> list[discord.abc.GuildChannel]:
        if guild is None or member is None:
            return []
        me = getattr(guild, "me", None)
        if me is None:
            return []
        channels: list[discord.abc.GuildChannel] = []
        for channel in list(getattr(guild, "voice_channels", []) or []):
            try:
                user_perms = channel.permissions_for(member)
                bot_perms = channel.permissions_for(me)
            except Exception:
                continue
            if not bool(getattr(user_perms, "connect", False)):
                continue
            if not (
                bool(getattr(bot_perms, "view_channel", False))
                and bool(getattr(bot_perms, "connect", False))
                and bool(getattr(bot_perms, "speak", False))
            ):
                continue
            channels.append(channel)
            if len(channels) >= max(1, int(limit)):
                break
        return channels

    async def _dispatch_ai_music_query_to_setup_channel(
        self,
        source_message: discord.Message,
        *,
        request_channel: discord.TextChannel,
        query: str,
    ) -> tuple[bool, str]:
        music_cog = self.bot.get_cog("Music")
        if music_cog is None:
            return False, "ตอนนี้โมดูลเพลงยังไม่พร้อมใช้งานครับ"
        safe_query = str(query or "").strip()
        if not safe_query:
            return False, "ไม่พบคำค้นหาเพลงครับ"
        if self._is_non_specific_music_query(safe_query):
            return False, "ขอชื่อเพลง/ลิงก์เพิ่มอีกนิดครับ เพื่อเปิดเพลงได้ตรงใจมากขึ้น"

        try:
            access_fn = getattr(music_cog, "_music_access_for_actor", None)
            if callable(access_fn):
                allowed, denied_text = access_fn(
                    guild=getattr(source_message, "guild", None),
                    actor=getattr(source_message, "author", None),
                    channel_id=int(getattr(request_channel, "id", 0) or 0),
                )
                if not allowed:
                    return False, str(denied_text or "คุณยังไม่มีสิทธิ์ใช้งานคำสั่งเพลงในห้องนี้ครับ")
        except Exception:
            pass

        class _AiMusicProxyMessage:
            def __init__(
                self,
                *,
                base_message: discord.Message,
                target_channel: discord.TextChannel,
                content: str,
            ) -> None:
                self.guild = base_message.guild
                self.author = base_message.author
                self.channel = target_channel
                self.content = content
                self.id = int(getattr(base_message, "id", 0) or 0)
                self.attachments = []
                self.embeds = []
                self.components = []

            async def delete(self, *args, **kwargs):
                return

        proxy_message = _AiMusicProxyMessage(
            base_message=source_message,
            target_channel=request_channel,
            content=safe_query,
        )
        try:
            await music_cog.music_setup_function(proxy_message)
            return True, ""
        except Exception as error:
            logger.warning(
                "AI setup-music dispatch failed | "
                f"guild={getattr(getattr(source_message, 'guild', None), 'id', 'unknown')} "
                f"channel={getattr(getattr(source_message, 'channel', None), 'id', 'unknown')} "
                f"user={getattr(getattr(source_message, 'author', None), 'id', 'unknown')} "
                f"query={safe_query!r} error={type(error).__name__}: {str(error)[:180]}"
            )
            return False, "ส่งคำขอไปห้องเพลงไม่สำเร็จ ลองอีกครั้งในอีกครู่ครับ"

    async def _send_ai_music_quickplay_panel(
        self,
        message: discord.Message,
        *,
        guild_prefix: str,
        query: str,
        user_text: str,
    ) -> bool:
        guild = getattr(message, "guild", None)
        if guild is None:
            return False
        member = guild.get_member(getattr(message.author, "id", 0))
        if member is None:
            member = getattr(message, "author", None)

        setup_request_channel, setup_voice_channel = self._resolve_music_setup_channels(guild)
        setup_request_mention = (
            self._to_channel_mention(getattr(setup_request_channel, "id", 0))
            if setup_request_channel is not None
            else ""
        )
        setup_voice_mention = (
            self._to_channel_mention(getattr(setup_voice_channel, "id", 0))
            if setup_voice_channel is not None
            else ""
        )
        query_text = str(query or "").strip()
        recommended_queries = await self._ask_ai_music_recommendations(user_text, limit=3)
        if not query_text:
            queries = list(recommended_queries or [])
        else:
            queries = [query_text] + [
                row
                for row in list(recommended_queries or [])
                if str(row).strip().lower() != query_text.lower()
            ]
        queries = [str(row).strip() for row in queries if str(row).strip()][:3]
        if not queries:
            queries = ["Blackbeans - Pink"]

        joinable_voice_channels = self._list_ai_joinable_voice_channels(
            guild,
            member if isinstance(member, discord.Member) else None,
            limit=12,
        )
        listed_voice_mentions = [self._to_channel_mention(ch.id) for ch in joinable_voice_channels[:8]]
        current_voice = getattr(getattr(member, "voice", None), "channel", None)

        info_lines: list[str] = []
        if setup_voice_channel is not None and setup_request_channel is not None:
            info_lines.append(
                f"เซิร์ฟนี้มีห้องเพลงประจำแล้ว: คำขอเพลง {setup_request_mention} และห้องเสียง {setup_voice_mention}"
            )
            info_lines.append("กดปุ่มด้านล่างเพื่อเล่นได้เลย บอทจะเข้าห้องเสียงประจำให้อัตโนมัติครับ")
        elif current_voice is not None:
            info_lines.append(f"ตอนนี้คุณอยู่ที่ {self._to_channel_mention(current_voice.id)} แล้ว")
            info_lines.append("กดปุ่มด้านล่างเพื่อเล่นเพลงได้ทันทีครับ")
        else:
            info_lines.append("ยังไม่เจอว่าคุณอยู่ห้องเสียงตอนนี้ครับ")
            info_lines.append("ให้เลือก/เข้าห้องเสียงก่อน แล้วค่อยกดปุ่มเล่นเพลงครับ")
            if listed_voice_mentions:
                info_lines.append("ห้องที่คุณเข้าได้ตอนนี้: " + ", ".join(listed_voice_mentions))

        prompt_embed = discord.Embed(
            title="AI Music Quick Play",
            description=(
                f"คำค้นล่าสุด: `{queries[0]}`\n\n"
                + "\n".join([f"- {line}" for line in info_lines])
            ),
            color=color.blue,
        )
        prompt_embed.set_footer(
            text=(
                f"หรือใช้คำสั่ง {str(guild_prefix or '!').strip() or '!'}play <ชื่อเพลง> /play ได้เช่นกัน"
            )
        )

        class _AiMusicQuickPlayView(discord.ui.View):
            def __init__(
                self,
                *,
                cog: "message",
                origin_message: discord.Message,
                actor_id: int,
                query_rows: list[str],
                setup_request_channel_obj: discord.TextChannel | None,
                setup_voice_channel_obj: discord.abc.GuildChannel | None,
                joinable_channels: list[discord.abc.GuildChannel],
            ) -> None:
                super().__init__(timeout=240)
                self._cog = cog
                self._origin_message = origin_message
                self._actor_id = int(actor_id or 0)
                self._query_rows = list(query_rows or [])
                self._setup_request_channel_obj = setup_request_channel_obj
                self._setup_voice_channel_obj = setup_voice_channel_obj
                self._joinable_channels = list(joinable_channels or [])
                self._selected_voice_channel_id: int = 0
                self._build_items()

            def _build_items(self) -> None:
                for index, row in enumerate(self._query_rows[:3]):
                    label = row if len(row) <= 60 else f"{row[:57]}..."
                    button = discord.ui.Button(
                        label=label,
                        style=discord.ButtonStyle.primary if index == 0 else discord.ButtonStyle.secondary,
                        emoji="▶️",
                        row=0,
                    )

                    async def _play_callback(interaction: discord.Interaction, music_query: str = row):
                        await self._on_play_button(interaction, music_query)

                    button.callback = _play_callback
                    self.add_item(button)

                if self._setup_voice_channel_obj is not None:
                    return

                options: list[discord.SelectOption] = []
                for channel in self._joinable_channels[:12]:
                    options.append(
                        discord.SelectOption(
                            label=str(getattr(channel, "name", "voice"))[:100],
                            value=str(getattr(channel, "id", 0)),
                            description=f"สมาชิกในห้อง: {len(getattr(channel, 'members', []) or [])}",
                        )
                    )
                if not options:
                    return

                select = discord.ui.Select(
                    placeholder="เลือกห้องเสียงที่จะเข้า (ถ้ายังไม่อยู่ห้อง)",
                    options=options,
                    min_values=1,
                    max_values=1,
                    row=1,
                )

                async def _select_callback(interaction: discord.Interaction):
                    if int(getattr(interaction.user, "id", 0) or 0) != self._actor_id:
                        await interaction.response.send_message(
                            "เมนูนี้เป็นของคนที่สั่งเพลงคนแรกครับ",
                            ephemeral=True,
                        )
                        return
                    try:
                        self._selected_voice_channel_id = int(select.values[0])
                    except Exception:
                        self._selected_voice_channel_id = 0
                    if self._selected_voice_channel_id > 0:
                        await interaction.response.send_message(
                            f"เลือกห้องไว้แล้ว: <#{self._selected_voice_channel_id}> แล้วเข้าห้องนี้ก่อนกดปุ่มเล่นครับ",
                            ephemeral=True,
                        )
                    else:
                        await interaction.response.send_message(
                            "ยังเลือกห้องไม่สำเร็จ ลองใหม่อีกครั้งครับ",
                            ephemeral=True,
                        )

                select.callback = _select_callback
                self.add_item(select)

            async def _on_play_button(self, interaction: discord.Interaction, music_query: str) -> None:
                async def _send_feedback(text: str) -> None:
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(str(text or ""), ephemeral=True)
                        else:
                            await interaction.response.send_message(str(text or ""), ephemeral=True)
                    except Exception:
                        pass

                if int(getattr(interaction.user, "id", 0) or 0) != self._actor_id:
                    await _send_feedback(
                        "ปุ่มนี้เป็นของคนที่สั่งเพลงคนแรกครับ",
                    )
                    return

                if not music_query:
                    await _send_feedback("ไม่พบคำค้นหาเพลงครับ")
                    return

                if self._cog._is_non_specific_music_query(music_query):
                    await _send_feedback("ยังไม่มีชื่อเพลงชัดเจนครับ ลองใส่ชื่อเพลงหรือศิลปินเพิ่มอีกนิด")
                    return

                if self._setup_request_channel_obj is not None and self._setup_voice_channel_obj is not None:
                    try:
                        if not interaction.response.is_done():
                            await interaction.response.defer(ephemeral=True, thinking=True)
                    except Exception:
                        pass
                    ok, error_text = await self._cog._dispatch_ai_music_query_to_setup_channel(
                        self._origin_message,
                        request_channel=self._setup_request_channel_obj,
                        query=music_query,
                    )
                    if not ok:
                        await _send_feedback(error_text or "ส่งคำขอเพลงไม่สำเร็จครับ")
                        return
                    await _send_feedback(
                        (
                            f"ส่งคำขอเพลงแล้ว: `{music_query}`\n"
                            f"- ห้องขอเพลง: <#{self._setup_request_channel_obj.id}>\n"
                            f"- ห้องเสียงประจำ: <#{self._setup_voice_channel_obj.id}>"
                        )
                    )
                    return

                guild_obj = interaction.guild
                member_obj = None
                if guild_obj is not None:
                    member_obj = guild_obj.get_member(int(getattr(interaction.user, "id", 0) or 0))
                if member_obj is None:
                    member_obj = getattr(interaction, "user", None)

                current_voice = getattr(getattr(member_obj, "voice", None), "channel", None)
                if current_voice is None:
                    target_hint = (
                        f"<#{self._selected_voice_channel_id}>"
                        if self._selected_voice_channel_id > 0
                        else "ห้องเสียงที่คุณต้องการ"
                    )
                    await _send_feedback(f"ให้เข้าห้องเสียงก่อนครับ เช่น {target_hint} แล้วค่อยกดปุ่มเล่นอีกครั้ง")
                    return

                if (
                    self._selected_voice_channel_id > 0
                    and int(getattr(current_voice, "id", 0) or 0) != self._selected_voice_channel_id
                ):
                    await _send_feedback(
                        f"ตอนนี้คุณยังไม่ได้อยู่ห้องที่เลือกไว้ (<#{self._selected_voice_channel_id}>) ครับ"
                    )
                    return

                music_cog = self._cog.bot.get_cog("Music")
                if music_cog is None:
                    await _send_feedback("ตอนนี้โมดูลเพลงยังไม่พร้อมใช้งานครับ")
                    return

                try:
                    try:
                        if not interaction.response.is_done():
                            await interaction.response.defer(ephemeral=True, thinking=True)
                    except Exception:
                        pass
                    ctx = await self._cog.bot.get_context(self._origin_message)
                    await ctx.invoke(getattr(music_cog, "play"), search=music_query)
                    await _send_feedback(f"รับทราบครับ กำลังเปิด `{music_query}` ให้แล้ว")
                except Exception as error:
                    logger.warning(
                        "AI quick-play button failed | "
                        f"guild={getattr(guild_obj, 'id', 'unknown')} "
                        f"user={getattr(getattr(interaction, 'user', None), 'id', 'unknown')} "
                        f"query={music_query!r} error={type(error).__name__}: {str(error)[:180]}"
                    )
                    await _send_feedback(
                        "ลองเปิดเพลงให้แล้ว แต่ยังไม่สำเร็จครับ เช็กสิทธิ์ Connect/Speak แล้วลองอีกครั้งครับ"
                    )

            async def on_timeout(self):
                for child in self.children:
                    try:
                        child.disabled = True
                    except Exception:
                        pass

        view = _AiMusicQuickPlayView(
            cog=self,
            origin_message=message,
            actor_id=getattr(message.author, "id", 0),
            query_rows=queries,
            setup_request_channel_obj=setup_request_channel,
            setup_voice_channel_obj=setup_voice_channel,
            joinable_channels=joinable_voice_channels,
        )
        try:
            await message.reply(embed=prompt_embed, view=view, mention_author=False)
            return True
        except Exception:
            fallback_text = (
                "สั่งเพลงผ่าน AI chat ได้ครับ\n"
                + "\n".join([f"- ลองพิมพ์: `เล่นเพลง {row}`" for row in queries[:2]])
            )
            await self._safe_ai_reply_smart(
                message,
                fallback_text,
                user_text=user_text,
            )
            return True

    def _parse_ai_music_play_intent(self, text: str) -> tuple[bool, str]:
        raw = str(text or "").strip()
        if not raw:
            return False, ""

        lines = [
            self._normalize_ai_music_text(line)
            for line in re.split(r"[\r\n]+", raw)
            if str(line or "").strip()
        ]
        if not lines:
            lines = [self._normalize_ai_music_text(raw)]

        patterns = (
            r"^(?:ช่วย\s*)?(?:เปิด\s*เพลง|เล่น\s*เพลง)(?:\s*(?:ให้)?(?:หน่อย|ที|ทีนะ|ได้ไหม|ได้มั้ย|ได้มะ|ได้ปะ|ไหม|มั้ย|มะ|ปะ|ครับ|คับ|ค้าบ))*\s*(?::|-|–)?\s*(.*)$",
            r"^(?:/)?play\s+(.+)$",
            r"^(?:/)?p\s+(.+)$",
        )
        for line in lines:
            for pattern in patterns:
                matched = re.match(pattern, line, flags=re.IGNORECASE)
                if not matched:
                    continue
                query = str(matched.group(1) or "").strip()
                if query:
                    query = query.strip("`\"'“”‘’[]() ")
                    query = re.sub(r"\s+", " ", query).strip()
                if self._is_non_specific_music_query(query):
                    query = ""
                return True, query
        return False, ""

    async def _maybe_execute_ai_music_play_intent(
        self,
        message: discord.Message,
        *,
        content: str,
        guild_prefix: str,
    ) -> bool:
        # Keep translation/help-language requests in normal AI flow.
        if self._is_music_phrase_translation_query(content):
            return False

        play_intent_detected, _query = self._parse_ai_music_play_intent(content)
        recommend_intent_detected, _recommend_query = self._parse_ai_music_recommend_intent(
            content
        )
        if not (
            play_intent_detected
            or recommend_intent_detected
            or self._looks_like_music_action_text(content)
        ):
            return False

        guidance = self._build_ai_music_room_guidance_text(
            getattr(getattr(message, "guild", None), "id", 0),
            str(guild_prefix or BotConfig.PREFIX),
        )
        await self._safe_ai_reply_smart(
            message,
            guidance,
            user_text=content,
        )
        return True

    @staticmethod
    def _looks_like_existence_question(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip()
        if not text:
            return False
        signals = (
            "มีไหม",
            "มีมั้ย",
            "มีมัย",
            "มีเปล่า",
            "มีปะ",
            "มีไหมครับ",
            "มีไหมคะ",
            "มีรึเปล่า",
            "มีน่ะ",
            "มีนะ",
            "ไหม",
            "หรือเปล่า",
        )
        if any(token in text for token in signals):
            return True
        return len(text) <= 28 and text.startswith("มี")

    @staticmethod
    def _contains_roleplay_hint(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        if any(token in text for token in ("roleplay", "โรลเพล", "โรเพล", "โรลเพลย์", "โรลเพย์")):
            return True
        return bool(re.search(r"\brp\b", text))

    @staticmethod
    def _contains_economy_hint(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        if re.search(r"(?:^|\s)(?:!|/)?economy(?:\s|$)", text):
            return True
        tokens = (
            "economy",
            "เศรษฐกิจ",
            "ระบบ economy",
            "เศรษฐกิจบอท",
            "บอทเศรษฐกิจ",
            "เงินในบอท",
            "เหรียญบอท",
        )
        return any(token in text for token in tokens)

    @staticmethod
    def _contains_shop_hint(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        tokens = ("shop", "ร้านค้า", "สโตร์", "buy", "ซื้อไอเท็ม")
        return any(token in text for token in tokens)

    @staticmethod
    def _is_short_casual_text(lowered_text: str) -> bool:
        compact = re.sub(r"\s+", "", str(lowered_text or "").strip().lower())
        if not compact:
            return False
        if len(compact) > 14:
            return False
        casual_tokens = {
            "เคร",
            "โอเค",
            "ok",
            "okay",
            "เริส",
            "เริสสส",
            "หา",
            "หาา",
            "หาาาา",
            "อ๋อ",
            "อ่อ",
            "ค้าบ",
            "คับ",
            "ครับ",
            "เยี่ยม",
            "แจ่ม",
        }
        return compact in casual_tokens

    @staticmethod
    def _contains_bug_report_hint(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        direct_tokens = (
            "รายงานบั๊ก",
            "รายงานบัก",
            "แจ้งบั๊ก",
            "แจ้งบัก",
            "bug report",
            "report bug",
            "แจ้งปัญหา",
            "report issue",
            "ส่งบั๊ก",
            "ส่งบัก",
        )
        if any(token in text for token in direct_tokens):
            return True
        return ("รายงาน" in text or "แจ้ง" in text) and any(
            token in text for token in ("bug", "บั๊ก", "บัก", "issue", "ปัญหา")
        )

    def _resolve_support_guild(self) -> discord.Guild | None:
        candidate_ids: list[int] = []
        for key in ("SUPPORT_GUILD_ID", "SUPPORT_HOME_GUILD_ID"):
            raw = str(os.getenv(key, "") or "").strip()
            if not raw:
                continue
            try:
                guild_id = int(raw)
            except (TypeError, ValueError):
                continue
            if guild_id > 0 and guild_id not in candidate_ids:
                candidate_ids.append(guild_id)

        for guild_id in candidate_ids:
            guild = self.bot.get_guild(guild_id)
            if guild is not None:
                return guild
        return None

    def _recommend_support_channels(self, *, topic: str, limit: int = 3) -> list[str]:
        guild = self._resolve_support_guild()
        if guild is None:
            return []

        topic_key = str(topic or "").strip().lower()
        if topic_key == "report":
            preferred_tokens = (
                "report",
                "bug",
                "issue",
                "แจ้งปัญหา",
                "รายงาน",
                "ticket",
                "support",
                "ช่วยเหลือ",
            )
        else:
            preferred_tokens = ("support", "help", "ticket", "contact", "ติดต่อ", "ช่วยเหลือ")

        blocked_tokens = (
            "ประกาศ",
            "announce",
            "announcement",
            "news",
            "อัปเดต",
            "update",
        )

        scored: list[tuple[int, str]] = []
        default_role = getattr(guild, "default_role", None)
        for channel in list(getattr(guild, "text_channels", []) or []):
            name = str(getattr(channel, "name", "") or "").strip()
            if not name:
                continue
            lowered_name = name.lower()
            if any(token in lowered_name for token in blocked_tokens):
                continue
            if self._is_restricted_channel_name(lowered_name):
                continue
            try:
                if default_role and not bool(channel.permissions_for(default_role).view_channel):
                    continue
            except Exception:
                continue

            score = 0
            for token in preferred_tokens:
                token_text = str(token or "").strip().lower()
                if token_text and token_text in lowered_name:
                    score += 20
            topic_text = str(getattr(channel, "topic", "") or "").strip().lower()
            for token in preferred_tokens:
                token_text = str(token or "").strip().lower()
                if token_text and token_text in topic_text:
                    score += 8
            if score <= 0:
                continue
            scored.append((score, f"#{name}"))

        scored.sort(key=lambda row: (-row[0], row[1]))
        out: list[str] = []
        seen = set()
        for _, name in scored:
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
            if len(out) >= max(1, int(limit)):
                break
        return out

    def _build_bug_report_quick_reply(self, website_base: str) -> str:
        support_url = str(getattr(getattr(self.bot, "urls", None), "SUPPORT_SERVER", "") or "").strip()
        if not support_url:
            support_url = "https://discord.gg/6g294K6KMp"

        recommended_channels = self._recommend_support_channels(topic="report", limit=3)
        channels_text = ""
        if recommended_channels:
            channels_text = "- ห้องที่แนะนำใน Support Server: " + ", ".join(recommended_channels) + "\n"

        return (
            "รายงานบั๊กได้เลยครับ ใช้ช่องทางนี้จะถึงทีมไวสุด:\n"
            f"- Report Form: {website_base}/report\n"
            "- Contact: https://niceshopallforme.web.app/contact\n"
            f"- Support Server: {support_url}\n"
            f"{channels_text}"
            "\n"
            "ข้อมูลที่ควรส่ง:\n"
            "1) ปัญหาที่เจอ + คำสั่งที่ใช้\n"
            "2) เวลาเกิดปัญหา\n"
            "3) ภาพ/คลิปประกอบ (ถ้ามี)\n"
            "4) Guild/Channel ที่เกิดปัญหา\n"
            "\n"
            "หมายเหตุ: ไม่ต้องส่งรายงานในห้องประกาศครับ ให้ส่งในช่อง support/report หรือลิงก์ด้านบนแทน"
        )

    @staticmethod
    def _contains_contact_team_hint(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        tokens = (
            "ติดต่อทีมงาน",
            "ติดต่อแอดมิน",
            "ติดต่อ admin",
            "ติดต่อทีม",
            "ซัพพอร์ต",
            "support",
            "helpdesk",
            "แจ้งปัญหา",
            "report issue",
        )
        return any(token in text for token in tokens)

    @staticmethod
    def _contains_invite_bot_hint(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        tokens = (
            "เพิ่มบอท",
            "เชิญบอท",
            "invite bot",
            "add bot",
            "เพิ่มยังไง",
            "เพิ่มบอทยังไง",
            "invite skylinebot",
        )
        return any(token in text for token in tokens)

    @staticmethod
    def _contains_rules_hint(lowered_text: str) -> bool:
        text = str(lowered_text or "").strip().lower()
        if not text:
            return False
        tokens = (
            "ขอกฎ",
            "กฎ",
            "ระเบียบ",
            "rules",
            "rule",
            "server rule",
            "guild rule",
        )
        return any(token in text for token in tokens)

    def _find_visible_rule_channel_mentions(
        self,
        message: discord.Message,
        *,
        limit: int = 3,
    ) -> list[str]:
        guild = getattr(message, "guild", None)
        author = getattr(message, "author", None)
        if not guild or not isinstance(author, discord.Member):
            return []

        keywords = ("rule", "rules", "กฎ", "ระเบียบ")
        scored: list[tuple[int, str]] = []
        for channel in list(getattr(guild, "text_channels", []) or []):
            try:
                perms = channel.permissions_for(author)
                if not bool(getattr(perms, "view_channel", False)):
                    continue
            except Exception:
                continue

            name = str(getattr(channel, "name", "") or "").strip()
            if not name:
                continue
            lowered_name = name.lower()
            if self._is_restricted_channel_name(lowered_name):
                continue
            if not any(token in lowered_name for token in keywords):
                continue

            topic = str(getattr(channel, "topic", "") or "").strip().lower()
            score = 0
            for token in keywords:
                if token in lowered_name:
                    score += 10
                if token in topic:
                    score += 4
            if score <= 0:
                continue
            scored.append((score, f"<#{int(getattr(channel, 'id', 0) or 0)}>"))

        scored.sort(key=lambda row: (-row[0], row[1]))
        out: list[str] = []
        seen = set()
        for _, mention in scored:
            if mention in seen:
                continue
            seen.add(mention)
            out.append(mention)
            if len(out) >= max(1, int(limit)):
                break
        return out

    def _build_rules_quick_reply(self, message: discord.Message, website_base: str) -> str:
        rule_channels = self._find_visible_rule_channel_mentions(message, limit=3)
        if rule_channels:
            return (
                "ข้อมูลกฎเซิร์ฟเวอร์ ต้องอ้างอิงจากห้องกฎของกิลด์โดยตรงครับ\n"
                f"- ห้องกฎที่พบ: {', '.join(rule_channels)}\n"
                "- ผมจะไม่แต่งกฎเอง ถ้าในห้องนั้นไม่มีข้อความให้ถือว่ายังไม่ประกาศกฎครับ\n\n"
                "นโยบายการใช้ SkylineBOT:\n"
                f"- Terms: {website_base}/terms-of-service\n"
                f"- Privacy: {website_base}/privacy-policy"
            )
        return (
            "ตอนนี้ผมยังไม่พบห้องกฎที่คุณมองเห็นในกิลด์นี้ครับ\n"
            "- ผมจะไม่แต่งกฎเอง\n"
            "- ถ้าต้องการกฎเซิร์ฟเวอร์ ให้แอดมินสร้าง/ปักหมุดในห้อง Rules ก่อนครับ\n\n"
            "นโยบายการใช้ SkylineBOT:\n"
            f"- Terms: {website_base}/terms-of-service\n"
            f"- Privacy: {website_base}/privacy-policy"
        )

    def _build_runtime_command_catalog_reply(self, prefix: str, *, max_items: int = 220) -> str:
        records = self._refresh_ai_command_records(limit=2400)
        if not records:
            return "ตอนนี้ยังโหลด command registry ไม่สำเร็จครับ ลองใหม่อีกครั้งในอีกครู่"

        total = len(records)
        base_url = str(self.ai_site_base_url or "https://skylinebot.xyz").strip().rstrip("/")

        roots_map: dict[str, list[str]] = defaultdict(list)
        for row in records:
            full_name = str(row.get("name") or "").strip()
            if not full_name:
                continue
            root = full_name.split(" ", 1)[0].strip().lower()
            if not root:
                continue
            roots_map[root].append(full_name)

        preferred_roots = [
            ("Music", "play"),
            ("AI", "aichat"),
            ("Economy", "economy"),
            ("Shop", "shop"),
            ("Roleplay", "rp"),
            ("Moderation", "automod"),
            ("Tickets", "ticket"),
            ("Utilities", "help"),
        ]

        lines: list[str] = []
        for label, root in preferred_roots:
            rows = list(roots_map.get(root, []))
            if not rows:
                continue
            rows.sort(key=lambda value: (value.count(" "), value))
            examples = rows[:3]
            rendered = ", ".join([f"`{prefix}{item}`" for item in examples])
            lines.append(f"- {label}: {rendered}")
            if len(lines) >= 8:
                break

        summary = (
            f"ตอนนี้บอทมีคำสั่งจาก runtime ประมาณ `{total}` คำสั่งครับ\n"
            "สรุปหมวดหลัก:\n"
            + ("\n".join(lines) if lines else "- ใช้ `!help` เพื่อดูรายการคำสั่ง")
            + "\n\n"
            "ดูรายการเต็มและค้นหาทีละหมวดได้ที่:\n"
            f"- Commands: {base_url}/commands\n"
            f"- Docs: {base_url}/docs\n"
            f"- ใน Discord: `{prefix}help` หรือ `{prefix}help <command>`"
        )
        return summary

    def _rewrite_markdown_table_blocks(self, text: str) -> str:
        raw = str(text or "")
        if "|" not in raw:
            return raw
        lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out: list[str] = []
        index = 0
        changed = False
        while index < len(lines):
            line = lines[index]
            if line.count("|") < 2:
                out.append(line)
                index += 1
                continue
            block: list[str] = []
            while index < len(lines) and lines[index].count("|") >= 2:
                block.append(lines[index])
                index += 1
            if len(block) < 3:
                out.extend(block)
                continue
            bullet_rows: list[str] = []
            first_data_row_seen = False
            for row in block:
                stripped = str(row).strip()
                if not stripped:
                    continue
                if re.fullmatch(r"[\s|:\-]+", stripped):
                    continue
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                if len(cells) < 2:
                    continue
                col1 = str(cells[0] or "").strip()
                col2 = str(cells[1] or "").strip()
                if not col1 or not col2:
                    continue
                if not first_data_row_seen:
                    # Most markdown tables start with a header row; skip it for Discord readability.
                    first_data_row_seen = True
                    continue
                if col1.lower() in {"คำสั่ง", "command", "model", "provider", "หมวด", "category"}:
                    continue
                bullet_rows.append(f"- `{col1}`: {col2}")
            if bullet_rows:
                changed = True
                out.extend(bullet_rows[:18])
            else:
                out.extend(block)
        if not changed:
            return raw
        return "\n".join(out)

    def _build_bot_specific_reply(self, message: discord.Message, content: str) -> str | None:
        text = str(content or "").strip()
        if self._is_malicious_request(text):
            return self._safe_refusal_text(text)

        lowered = text.lower()
        prefix = cache.guilds.get(str(message.guild.id), {}).get("prefix", BotConfig.PREFIX)
        website_base = str(self.ai_site_base_url or "https://skylinebot.xyz").strip().rstrip("/")

        if self._is_short_casual_text(lowered):
            return "รับทราบครับ ถ้ามีอะไรให้ช่วยต่อ พิมพ์มาได้เลยครับ"

        if self._contains_rules_hint(lowered):
            return self._build_rules_quick_reply(message, website_base)

        if self._is_music_phrase_translation_query(text):
            return (
                "ถ้าจะขอเพลงจาก AI เป็นภาษาอังกฤษ ใช้ได้แบบนี้ครับ:\n"
                "- `Can you recommend a song?`\n"
                "- `Can you recommend some songs?`\n"
                "- `Please recommend songs for me.`\n"
                "- ถ้าจะให้เปิดเลย: `Play Blackbeans - Pink.`"
            )

        if self._contains_bug_report_hint(lowered):
            return self._build_bug_report_quick_reply(website_base)

        if "!ttl" in lowered:
            return (
                "ใช้คำสั่ง `!ttl` ได้เลยครับ (alias ของ `!tts`)\n"
                "ตัวอย่าง: `!ttl th สวัสดีครับ` หรือ `!tts en hello everyone`"
            )

        if self._contains_invite_bot_hint(lowered):
            invite_url = str(getattr(getattr(self.bot, "urls", None), "INVITE", "") or "").strip()
            if not invite_url:
                invite_url = (
                    "https://discord.com/oauth2/authorize?"
                    "client_id=1484505852449787944&permissions=8&scope=bot+applications.commands"
                )
            return (
                "เพิ่มบอทได้จากลิงก์นี้ครับ:\n"
                f"{invite_url}\n\n"
                "ขั้นตอนสั้น ๆ:\n"
                "1) เปิดลิงก์แล้วเลือกเซิร์ฟเวอร์\n"
                "2) อนุญาตสิทธิ์ที่จำเป็น\n"
                "3) ใช้ `!help` หรือ `/help` เพื่อตรวจว่าบอทพร้อมใช้งาน"
            )

        if self._contains_contact_team_hint(lowered):
            support_url = str(getattr(getattr(self.bot, "urls", None), "SUPPORT_SERVER", "") or "").strip()
            if not support_url:
                support_url = "https://discord.gg/6g294K6KMp"
            return (
                "ติดต่อทีมงานได้จากช่องทางทางการนี้ครับ:\n"
                f"- Discord Support Server: {support_url}\n"
                "- Contact Form: https://niceshopallforme.web.app/contact\n"
                f"- Report: {website_base}/report\n\n"
                "หมายเหตุ: ให้ติดต่อผ่านเซิร์ฟเวอร์ซัพพอร์ตทางการ ไม่อ้างอิงชื่อห้องจากกิลด์อื่นครับ"
            )

        if any(token in lowered for token in ("คำสั่งบอททั้งหมด", "คำสั่งทั้งหมด", "all commands", "commands ทั้งหมด")):
            return self._build_runtime_command_catalog_reply(prefix, max_items=260)
        if "คำสั่ง" in lowered and any(token in lowered for token in ("ไม่ครบ", "ยังไม่ครบ", "ไม่หมด")):
            return self._build_runtime_command_catalog_reply(prefix, max_items=320)

        if lowered in {"ต่อ", "ต่อหน่อย", "ต่อดิ", "ต่อครับ", "ต่อคับ", "continue"}:
            return (
                f"ได้ครับ ถ้าต้องการรายการคำสั่งทั้งหมดแบบไล่ครบ ให้ใช้ `{prefix}help` "
                f"หรือดูที่ {website_base}/commands ครับ"
            )

        if (
            any(token in lowered for token in ("ai", "เอไอ"))
            and any(token in lowered for token in ("เพลง", "play", "เปิดผ่าน"))
            and not self._is_music_phrase_translation_query(text)
            and self.ai_music_intercept_enabled
        ):
            return self._build_ai_music_room_guidance_text(
                message.guild.id,
                str(prefix or BotConfig.PREFIX),
            )

        if self._is_website_intent_text(text):
            lines = self._build_official_site_links_summary(
                text,
                guild_id=getattr(getattr(message, "guild", None), "id", None),
                limit=6,
            )
            if lines:
                return (
                    "สรุปหน้าเว็บที่เกี่ยวข้อง:\n"
                    + "\n".join([f"- {line}" for line in lines])
                    + "\n\nหากต้องการรายละเอียดเชิงลึก ให้เปิดจากลิงก์ตรงด้านบนได้เลยครับ\n"
                    "หมายเหตุ: ล็อกอินผ่าน Discord OAuth ปกติเท่านั้น ไม่ต้องใช้หรือส่ง Discord Token ครับ"
                )
            return (
                "มีครับ ใช้งานเว็บทางการได้ที่:\n"
                f"- Home: {website_base}\n"
                f"- Commands: {website_base}/commands\n"
                f"- Docs: {website_base}/docs"
            )

        if (
            any(token in lowered for token in ("ทำบอท", "สร้างบอท", "เขียนบอท"))
            and any(token in lowered for token in ("ยาก", "ยากไหม", "ยากมั้ย", "ยากม่ะ", "ยากไหมครับ", "ยากไหมคะ"))
        ):
            return (
                "ไม่ยากมากครับ ถ้าเริ่มจากฟีเจอร์พื้นฐาน\n"
                "เริ่มแบบเร็ว:\n"
                "1) ใช้ Python + `discord.py`\n"
                "2) ทำคำสั่งพื้นฐาน `ping`, `help`\n"
                "3) ค่อยเพิ่มระบบที่ต้องการทีละส่วน\n"
                "ถ้าต้องการ ผมช่วยวางโครงบอทเริ่มต้นให้ได้เลยครับ"
            )

        if (
            ("ห้อง" in lowered or "channel" in lowered)
            and any(token in lowered for token in ("เพลง", "music", "play"))
            and self.ai_music_intercept_enabled
        ):
            request_mention, voice_mention = self._resolve_music_setup_mentions(message.guild.id)
            if request_mention and voice_mention:
                return (
                    f"ห้องสั่งเพลงคือ {request_mention} ครับ\n"
                    f"แล้วให้เข้า/ฟังในห้องเสียง {voice_mention}\n"
                    f"ลองใช้ `{prefix}play <ชื่อเพลง>` หรือ `/play` ได้เลยครับ"
                )
            if request_mention:
                return (
                    f"ห้องสั่งเพลงคือ {request_mention} ครับ\n"
                    f"ถ้ายังไม่มีห้องเสียงคู่กัน ให้รัน `{prefix}music setup` ก่อนครับ"
                )
            return (
                "ยังไม่เจอการตั้งค่าห้องเพลงของเซิร์ฟนี้ครับ\n"
                f"ให้แอดมินรัน `{prefix}music setup` หรือ `/music setup` ก่อน แล้วบอทจะสร้างห้องสั่งเพลงให้อัตโนมัติครับ"
            )

        if self._contains_roleplay_hint(lowered) and (
            self._looks_like_existence_question(lowered) or len(lowered) <= 32
        ):
            rp_commands = self._collect_command_names_for_roots(["rp"], limit=10)
            if rp_commands:
                return (
                    "มีระบบ Roleplay ครับ\n"
                    "คำสั่งหลักที่ใช้บ่อย:\n"
                    f"{self._format_prefixed_command_lines(prefix, rp_commands, limit=6)}"
                )
            return "ตอนนี้ไม่พบคำสั่ง Roleplay (`rp`) ใน runtime ของบอทครับ"

        if self._contains_economy_hint(lowered):
            economy_commands = self._collect_command_names_for_roots(["economy"], limit=22)
            if economy_commands:
                return (
                    "ระบบ Economy มีครับ\n"
                    "คำสั่งหลักที่ใช้บ่อย:\n"
                    f"{self._format_prefixed_command_lines(prefix, economy_commands, limit=10)}"
                )
            if self._looks_like_existence_question(lowered):
                return "ตอนนี้ไม่พบคำสั่ง Economy ใน runtime ของบอทครับ"

        if self._contains_shop_hint(lowered):
            shop_commands = self._collect_command_names_for_roots(["shop"], limit=16)
            if shop_commands:
                return (
                    "มีระบบร้านค้าครับ\n"
                    "คำสั่งหลักที่ใช้บ่อย:\n"
                    f"{self._format_prefixed_command_lines(prefix, shop_commands, limit=10)}"
                )
            if self._looks_like_existence_question(lowered):
                return "ตอนนี้ไม่พบคำสั่งร้านค้า (`shop`) ใน runtime ของบอทครับ"

        if any(token in lowered for token in ("ระบบจัดการบอท", "จัดการบอท", "คำสั่งหลัก", "มีคำสั่งอะไร")):
            summary_blocks: list[str] = []
            for title, roots in [
                ("Moderation", ["automod", "antispam", "antilink", "antibadwords", "antinuke"]),
                ("Music", ["music", "play"]),
                ("Economy", ["economy"]),
                ("Roleplay", ["rp"]),
                ("AI Chat", ["aichat"]),
            ]:
                names = self._collect_command_names_for_roots(roots, limit=3)
                if not names:
                    continue
                lines = self._format_prefixed_command_lines(prefix, names, limit=3)
                summary_blocks.append(f"**{title}**\n{lines}")
            if summary_blocks:
                return "หมวดคำสั่งหลักของบอท:\n" + "\n\n".join(summary_blocks[:6])

        if self._is_command_help_query(text):
            related = self._find_related_commands(text, limit=12)
            if related:
                return (
                    "คำสั่งที่เกี่ยวข้องจาก runtime:\n"
                    + self._format_prefixed_command_lines(prefix, related, limit=12)
                )

        return None

    def _get_ai_history_key(self, message: discord.Message) -> str:
        return f"{message.guild.id}:{message.channel.id}"

    def _append_ai_history(self, message: discord.Message, role: str, content: str) -> None:
        text = str(content or "").strip()
        if not text:
            return
        key = self._get_ai_history_key(message)
        history = self.ai_history_by_channel[key]
        history.append(
            {
                "role": role,
                "content": text[:1400],
            }
        )

    def _build_ai_messages(
        self, message: discord.Message, system_prompt: str, current_user_content: str
    ) -> list[dict[str, str]]:
        key = self._get_ai_history_key(message)
        history_window = max(4, min(18, int(getattr(self, "ai_history_context_turns", 8) or 8)))
        history = list(self.ai_history_by_channel[key])[-history_window:]
        messages_payload = [{"role": "system", "content": system_prompt}]

        if history:
            messages_payload.extend(history)

        # Fallback if caller forgot to push user content into history.
        if not history or history[-1].get("role") != "user":
            messages_payload.append(
                {
                    "role": "user",
                    "content": str(current_user_content or "").strip()[:1400],
                }
            )

        return messages_payload

    @staticmethod
    def _allow_soft_feminine_particles(user_content: str) -> bool:
        lowered = str(user_content or "").strip().lower()
        if not lowered:
            return False
        tokens = (
            "พูดค่ะ",
            "ใช้ค่ะ",
            "ลงท้ายค่ะ",
            "คุยแบบอ้อน",
            "อ้อน",
            "cute",
            "playful",
            "เทอค้าบ",
            "ค้าบว่าไงค่ะ",
            "คุยเป็นกันเอง",
        )
        return any(token in lowered for token in tokens)

    @staticmethod
    def _clip_reply_on_boundary(text: str, limit: int = 1900) -> str:
        raw = str(text or "").strip()
        max_len = max(120, int(limit))
        if len(raw) <= max_len:
            return raw
        clipped = raw[:max_len]
        boundary_candidates = [
            clipped.rfind("\n\n"),
            clipped.rfind("\n"),
            clipped.rfind(". "),
            clipped.rfind("! "),
            clipped.rfind("? "),
            clipped.rfind("。"),
            clipped.rfind("ครับ "),
            clipped.rfind("ค่ะ "),
        ]
        cut_idx = max(boundary_candidates)
        if cut_idx >= int(max_len * 0.7):
            clipped = clipped[:cut_idx].rstrip()
        return clipped.rstrip() + "..."

    def _normalize_ai_reply_style(
        self,
        text: str,
        message: discord.Message | None = None,
        user_content: str = "",
        source: str = "ai_model",
    ) -> str:
        raw_reply = str(text or "").strip()
        if not raw_reply:
            return raw_reply

        reasons: list[str] = []
        reply = raw_reply

        if self._contains_cjk(reply):
            reasons.append("contains_cjk")
            reply = "ขออภัยครับ ผมจะตอบเฉพาะภาษาไทยหรืออังกฤษเท่านั้น"

        if re.search(r"(scope=บอท|applications\.คำสั่ง)", raw_reply, flags=re.IGNORECASE):
            reasons.append("translated_scope_detected")

        sanitized = self._sanitize_discord_oauth_links(reply)
        if sanitized != reply:
            reasons.append("oauth_scope_sanitized")
        reply = sanitized

        markdown_repaired = self._repair_markdown_links(reply)
        if markdown_repaired != reply:
            reasons.append("markdown_links_repaired")
        reply = markdown_repaired

        table_rewritten = self._rewrite_markdown_table_blocks(reply)
        if table_rewritten != reply:
            reasons.append("table_rewritten_for_discord")
            reply = table_rewritten

        if re.search(r"<think>", reply, flags=re.IGNORECASE):
            trimmed = reply
            parts_after_close = re.split(r"</think>", trimmed, maxsplit=1, flags=re.IGNORECASE)
            if len(parts_after_close) == 2 and str(parts_after_close[1]).strip():
                trimmed = str(parts_after_close[1]).strip()
            else:
                trimmed = re.sub(r"^\s*<think>\s*", "", trimmed, flags=re.IGNORECASE)
                trimmed = re.sub(r"</?think>", "", trimmed, flags=re.IGNORECASE)
            if trimmed != reply:
                reasons.append("reasoning_block_removed")
                reply = trimmed

        # Keep Thai polite style consistent; prevent mixed patterns like "ครับ/ค่ะ".
        polite_normalized = reply
        polite_normalized = re.sub(r"ผม\s*/\s*ครับ\s*ค่ะ", "ผมครับ", polite_normalized)
        polite_normalized = re.sub(r"ผม\s*/\s*ครับ", "ผมครับ", polite_normalized)
        polite_normalized = re.sub(r"ครับ\s*/\s*ค่ะ", "ครับ", polite_normalized)
        polite_normalized = re.sub(r"ค่ะ\s*/\s*ครับ", "ค่ะ", polite_normalized)
        polite_normalized = polite_normalized.replace("ครับค่ะ", "ครับ")
        polite_normalized = polite_normalized.replace("ค่ะครับ", "ค่ะ")
        if not self._allow_soft_feminine_particles(user_content):
            polite_normalized = polite_normalized.replace("ขออภัยค่ะ", "ขออภัยครับ")
            polite_normalized = polite_normalized.replace("ขอโทษค่ะ", "ขอโทษครับ")
        if polite_normalized != reply:
            reasons.append("polite_style_normalized")
        reply = polite_normalized

        multiline = str(reply or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t]+$", "", line) for line in multiline.split("\n")]
        normalized = "\n".join(lines)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        normalized = re.sub(r"[ \t]{2,}", " ", normalized)
        clip_limit = max(1200, int(getattr(self, "ai_max_reply_chars", 5600) or 5600))
        if len(normalized) > clip_limit:
            reasons.append("reply_truncated")
        normalized = self._clip_reply_on_boundary(normalized, clip_limit)

        if reasons:
            self._log_ai_reply_anomaly(
                message=message,
                source=source,
                reason=",".join(dict.fromkeys(reasons)),
                raw_reply=raw_reply,
                normalized_reply=normalized,
                user_content=user_content,
            )

        return normalized

    async def _effective_ai_model(self) -> str:
        fallback = str(self.ai_model or "").strip()
        if hasattr(self.bot, "ownerbot_runtime_ai_model"):
            try:
                resolved = await self.bot.ownerbot_runtime_ai_model(fallback=fallback)
                resolved_text = str(resolved or "").strip()
                if resolved_text:
                    return resolved_text
            except Exception:
                pass
        if fallback:
            return fallback
        if self.ai_provider == "openai":
            return "gpt-4o-mini"
        if self.ai_provider == "google":
            return "gemini-2.0-flash"
        if self.ai_provider == "opentyphoon":
            return "typhoon-v2.5-30b-a3b-instruct"
        if self.ai_provider == "chindax":
            return "accounts/fireworks/models/gpt-oss-20b"
        if self.ai_provider == "aiforthai":
            return "aiforthai-chat"
        if self.ai_provider == "cloudflare":
            return "@cf/meta/llama-3.1-8b-instruct"
        if self.ai_provider == "thaillm":
            return "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2"
        return "typhoon-v2.5-30b-a3b-instruct"

    @staticmethod
    def _google_normalize_model_name(raw_model: str) -> str:
        model = str(raw_model or "").strip()
        if model.lower().startswith("models/"):
            model = model.split("/", 1)[1].strip()
        return model

    def _google_model_fallbacks(self, preferred_model: str) -> list[str]:
        candidates = [
            self._google_normalize_model_name(preferred_model),
            self._google_normalize_model_name(self.google_model),
            "gemini-2.0-flash",
            "gemini-flash-latest",
            "gemini-2.5-flash",
        ]
        resolved: list[str] = []
        for row in candidates:
            name = str(row or "").strip()
            if not name or name in resolved:
                continue
            resolved.append(name)
        return resolved

    def _provider_default_model(self, provider: str) -> str:
        normalized = str(provider or "").strip().lower()
        if normalized == "openai":
            return str(self.openai_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
        if normalized == "google":
            return str(self.google_model or "gemini-2.0-flash").strip() or "gemini-2.0-flash"
        if normalized == "opentyphoon":
            return (
                str(self.opentyphoon_model or "typhoon-v2.5-30b-a3b-instruct").strip()
                or "typhoon-v2.5-30b-a3b-instruct"
            )
        if normalized == "chindax":
            return (
                str(self.chindax_model or "accounts/fireworks/models/gpt-oss-20b").strip()
                or "accounts/fireworks/models/gpt-oss-20b"
            )
        if normalized == "aiforthai":
            return str(self.aiforthai_model or "aiforthai-chat").strip() or "aiforthai-chat"
        if normalized == "cloudflare":
            return (
                str(self.cloudflare_model or "@cf/meta/llama-3.1-8b-instruct").strip()
                or "@cf/meta/llama-3.1-8b-instruct"
            )
        if normalized == "thaillm":
            return (
                str(self.thaillm_model or "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2").strip()
                or "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2"
            )
        ollama_model = str(self.ollama_model or "qwen2.5:0.5b-instruct").strip() or "qwen2.5:0.5b-instruct"
        if self._is_ollama_cloud_host() and ollama_model.lower().startswith("qwen2.5:"):
            return "gpt-oss:20b"
        return ollama_model

    def _resolve_ai_fallback_providers(self) -> tuple[str, ...]:
        allowed = {"openai", "ollama", "google", "opentyphoon", "chindax", "aiforthai", "cloudflare", "thaillm"}
        raw = str(os.getenv("AI_FALLBACK_PROVIDERS", "") or "").strip()
        ordered: list[str] = []
        if raw:
            for token in raw.split(","):
                name = str(token or "").strip().lower()
                if name in allowed and name not in ordered:
                    ordered.append(name)
        if not ordered:
            ordered = ["opentyphoon", "cloudflare", "thaillm", "openai", "google", "chindax", "aiforthai", "ollama"]
        return tuple(ordered)

    def _fallback_chain_for_provider(self, current_provider: str) -> list[str]:
        current = str(current_provider or "").strip().lower()
        chain: list[str] = []
        for provider in self.ai_fallback_providers:
            if provider == current:
                continue
            if provider not in chain:
                chain.append(provider)
        return chain

    def _provider_is_configured(self, provider: str) -> bool:
        normalized = str(provider or "").strip().lower()
        if normalized == "google":
            return bool(self.google_api_key)
        if normalized == "openai":
            return bool(AsyncOpenAI and self.openai_api_key)
        if normalized == "opentyphoon":
            return bool(self.opentyphoon_api_key and self.opentyphoon_base_url)
        if normalized == "chindax":
            return bool(self.chindax_api_key and self.chindax_base_url)
        if normalized == "aiforthai":
            return bool(self.aiforthai_api_key and self.aiforthai_base_url)
        if normalized == "cloudflare":
            return bool(self.cloudflare_api_key and self.cloudflare_base_url)
        if normalized == "thaillm":
            return bool(self.thaillm_api_key and self.thaillm_base_url)
        return True

    def _ensure_openai_client(self):
        if self.ai_client is not None:
            return self.ai_client
        if not AsyncOpenAI or not self.openai_api_key:
            return None
        try:
            self.ai_client = AsyncOpenAI(api_key=self.openai_api_key)
        except Exception:
            return None
        return self.ai_client

    @staticmethod
    def _is_google_quota_like_error(error_text: str) -> bool:
        text = str(error_text or "").strip().lower()
        return (
            "resource_exhausted" in text
            or "quota" in text
            or "rate limit" in text
            or "429" in text
        )

    @staticmethod
    def _safe_profile_text(value: Any, limit: int = 120, default: str = "-") -> str:
        text = str(value or "").strip()
        if not text:
            return default
        return text[: max(8, int(limit))]

    @staticmethod
    def _discord_ts(dt: Any) -> str:
        if not dt:
            return "-"
        try:
            return f"<t:{int(dt.timestamp())}:R>"
        except Exception:
            return "-"

    def _pick_ai_response_style_hint(self, user_content: str) -> str:
        text = str(user_content or "").strip().lower()
        if not text:
            return "friendly concise answer (2-4 lines)."

        howto_keywords = ("ยังไง", "วิธี", "how", "setup", "config", "step", "ทำไง")
        compare_keywords = ("ต่าง", "compare", "vs", "เลือก", "ไหนดี", "better")
        list_keywords = ("list", "สรุป", "รวบรวม", "ทั้งหมด")
        creative_keywords = ("คิดชื่อ", "เขียน", "แต่ง", "creative", "caption", "bio")

        if any(keyword in text for keyword in howto_keywords):
            return "step-by-step with numbered list and practical checks."
        if any(keyword in text for keyword in compare_keywords):
            return "short comparison with pros/cons and recommendation."
        if any(keyword in text for keyword in list_keywords):
            return "organized bullet list with clear categories."
        if any(keyword in text for keyword in creative_keywords):
            return "playful and creative while still useful and safe."

        return random.choice(
            [
                "friendly concise answer (2-4 lines).",
                "short bullets for quick scanning.",
                "compact explanation with one concrete example.",
                "brief answer + optional next-step suggestion.",
            ]
        )

    async def build_ai_system_prompt(
        self,
        message: discord.Message,
        user_content: str = "",
        ai_model: str | None = None,
        ai_provider: str | None = None,
    ) -> str:
        bot_user = getattr(self.bot, "user", None)
        bot_name = (
            self._safe_profile_text(getattr(bot_user, "display_name", ""), 80, default="")
            or self._safe_profile_text(getattr(getattr(self.bot, "BotConfig", BotConfig), "NAME", ""), 80, default="")
            or "SkylineBOT"
        )
        bot_id = str(getattr(bot_user, "id", "") or "-")
        bot_created = self._discord_ts(getattr(bot_user, "created_at", None))
        guild_name = self._safe_profile_text(getattr(getattr(message, "guild", None), "name", ""), 100)
        guild_id = str(getattr(getattr(message, "guild", None), "id", "") or "-")
        channel_name = self._safe_profile_text(getattr(getattr(message, "channel", None), "name", ""), 90)
        channel_id = str(getattr(getattr(message, "channel", None), "id", "") or "-")
        prefix = cache.guilds.get(str(message.guild.id), {}).get("prefix", BotConfig.PREFIX)

        author = getattr(message, "author", None)
        user_name = self._safe_profile_text(getattr(author, "display_name", ""), 80)
        user_username = self._safe_profile_text(getattr(author, "name", ""), 80)
        user_id = str(getattr(author, "id", "") or "-")
        user_mention = self._safe_profile_text(getattr(author, "mention", ""), 120)
        user_created = self._discord_ts(getattr(author, "created_at", None))
        user_joined = self._discord_ts(getattr(author, "joined_at", None))

        user_roles: list[str] = []
        user_top_role = "-"
        try:
            if isinstance(author, discord.Member):
                role_names: list[str] = []
                for role in list(getattr(author, "roles", []) or []):
                    try:
                        if role.is_default():
                            continue
                    except Exception:
                        pass
                    role_name = self._safe_profile_text(getattr(role, "name", ""), 40, default="")
                    if role_name:
                        role_names.append(role_name)
                user_roles = role_names[-10:]
                user_top_role = self._safe_profile_text(
                    getattr(getattr(author, "top_role", None), "name", ""), 50
                )
        except Exception:
            pass
        user_roles_text = ", ".join(user_roles) if user_roles else "-"

        guild_member_count = int(getattr(getattr(message, "guild", None), "member_count", 0) or 0)
        guild_role_count = len(list(getattr(getattr(message, "guild", None), "roles", []) or []))
        guild_text_channel_count = len(list(getattr(getattr(message, "guild", None), "text_channels", []) or []))
        guild_voice_channel_count = len(list(getattr(getattr(message, "guild", None), "voice_channels", []) or []))
        guild_emoji_count = len(list(getattr(getattr(message, "guild", None), "emojis", []) or []))

        model_for_prompt = str(ai_model or "").strip() or await self._effective_ai_model()
        provider_for_prompt = str(ai_provider or self.ai_provider or "opentyphoon").strip().lower()
        bot_guild_count = len(list(getattr(self.bot, "guilds", []) or []))
        loaded_cogs_count = len(list(getattr(self.bot, "cogs", {}) or {}))
        latency_ms = 0
        try:
            latency_ms = max(0, int(float(getattr(self.bot, "latency", 0.0) or 0.0) * 1000))
        except Exception:
            latency_ms = 0

        # Load long-term memories
        user_memory_data = await storage.ai_memories.get(target_id=message.author.id, type="user")
        guild_memory_data = await storage.ai_memories.get(target_id=message.guild.id, type="guild")
        user_memory = self._safe_profile_text((user_memory_data or {}).get("memory", ""), 700, default="None")
        guild_memory = self._safe_profile_text((guild_memory_data or {}).get("memory", ""), 700, default="None")
        lowered_user_text = str(user_content or "").strip().lower()
        full_context_mode = bool(
            self.ai_force_full_context
            or any(
                token in lowered_user_text
                for token in (
                    "ข้อมูลทั้งหมด",
                    "ทั้งหมดก่อนตอบ",
                    "รู้ให้หมด",
                    "ส่งข้อมูลทั้งหมด",
                    "all data",
                    "full context",
                    "everything before reply",
                )
            )
        )

        style_hint = self._pick_ai_response_style_hint(user_content)
        official_website_url = str(self.ai_site_base_url or "https://skylinebot.xyz").strip().rstrip("/")
        runtime_context = (
            "Runtime context (trusted facts):\n"
            f"- assistant_name: {bot_name}\n"
            f"- bot_id: {bot_id}\n"
            f"- bot_created_at: {bot_created}\n"
            f"- ai_provider: {provider_for_prompt}\n"
            f"- ai_model: {model_for_prompt}\n"
            f"- full_context_mode: {'on' if full_context_mode else 'off'}\n"
            f"- bot_latency_ms: {latency_ms}\n"
            f"- bot_guild_count: {bot_guild_count}\n"
            f"- loaded_cogs_count: {loaded_cogs_count}\n"
            f"- invite_url: {self.bot.urls.INVITE}\n"
            f"- support_url: {self.bot.urls.SUPPORT_SERVER}\n"
            f"- vote_url: {self.bot.urls.VOTE}\n"
            f"- official_website_url: {official_website_url}\n"
            f"- official_commands_url: {official_website_url}/commands\n"
            f"- official_dashboard_url: {official_website_url}/dashboard\n"
            "- official_contact_url: https://niceshopallforme.web.app/contact\n"
            f"- official_pricing_url: {official_website_url}/pricing\n"
            f"- guild_name: {guild_name}\n"
            f"- guild_id: {guild_id}\n"
            f"- guild_member_count: {guild_member_count}\n"
            f"- guild_text_channels: {guild_text_channel_count}\n"
            f"- guild_voice_channels: {guild_voice_channel_count}\n"
            f"- guild_role_count: {guild_role_count}\n"
            f"- guild_emoji_count: {guild_emoji_count}\n"
            f"- channel_name: {channel_name}\n"
            f"- channel_id: {channel_id}\n"
            f"- command_prefix: {prefix}\n"
            f"- user_display_name: {user_name}\n"
            f"- user_username: {user_username}\n"
            f"- user_id: {user_id}\n"
            f"- user_mention: {user_mention}\n"
            f"- user_account_age: {user_created}\n"
            f"- user_joined_guild: {user_joined}\n"
            f"- user_top_role: {user_top_role}\n"
            f"- user_roles: {user_roles_text}\n"
            f"- user_memory_persistent: {user_memory}\n"
            f"- guild_memory_persistent: {guild_memory}\n"
            "Use these facts when relevant. Never invent unknown facts; if unknown, say unknown."
        )

        behavior_context = (
            "Conversation behavior:\n"
            f"- Tone: friendly and natural.\n"
            f"- Style for this reply: {style_hint}\n"
            "- If user asks for commands, use command registry data in this prompt first.\n"
            "- If user asks whether a feature/command exists, verify against provided command list before answering.\n"
            "- For support/server/page questions, use website snapshot + guild channel map from this prompt.\n"
            "- When referring to Discord channels in this guild, prefer channel mentions like <#channel_id>.\n"
            "- For contacting SkylineBOT team, prefer official support links (support_url/contact/report) instead of local guild channels.\n"
            "- Never direct users to announcement/news channels for bug reports; route to support/report channels or official report/contact URLs.\n"
            "- For server rules requests, never invent rule details; only reference visible rule channels or say unknown.\n"
            "- For website-existence questions, answer that official website exists and provide direct link(s).\n"
            "- If answer would be long (especially full command lists/policies), give concise summary first and direct user to exact official URL(s).\n"
            "- Never answer with fixed canned list if the live registry is available.\n"
            "- Do not output `<think>` blocks or hidden reasoning; return final answer only.\n"
            "- Do not claim pricing/free/credits as absolute unless explicitly present in trusted context; otherwise say unknown and point to pricing/contact URL.\n"
            "- Keep male identity, but if user asks for playful/cute wording, you may use softer particles naturally while staying respectful.\n"
            "- For short casual Thai messages like 'เคร', 'โอเค', 'อืม', respond naturally without saying you do not understand.\n"
            "- Discord does not render Markdown tables well; use bullets or numbered lists instead of table syntax.\n"
            "- If user asks for embed output, you may include these optional tags:\n"
            "  [EMBED_TITLE: ...] [EMBED_DESC: ...] [EMBED_COLOR: #6b8cff]\n"
            "- If user asks for reactions, you may include: [REACTIONS: ✅ 👍]\n"
            "- Keep those tags short and use at most 4 reactions.\n"
            "- If question is general (not about bot), still help with best-effort practical answer.\n"
            "- If unsafe request appears, refuse briefly and redirect to safe alternative.\n"
            "- Keep response easy to read and useful first.\n"
            "- If information is missing from trusted context, clearly say what is unknown instead of guessing."
        )

        memory_write_context = (
            "Long-term memory write protocol (optional):\n"
            "- Only when user shares stable preferences/facts, append exactly one tag:\n"
            "  [SAVE_USER_MEMORY: short fact]\n"
            "- For server-wide stable rules, append exactly one tag:\n"
            "  [SAVE_GUILD_MEMORY: short server rule]\n"
            "- Never store secrets, passwords, tokens, private keys, or sensitive personal data."
        )

        command_limit = 90
        if full_context_mode:
            command_limit = int(self.ai_full_context_command_limit or 420)
        elif any(token in lowered_user_text for token in ("ทั้งหมด", "all command", "all commands", "ทุกคำสั่ง", "600")):
            command_limit = 220
        command_reference = ""
        command_intent_tokens = (
            "คำสั่ง",
            "command",
            "commands",
            "help",
            "มีไหม",
            "มีมั้ย",
            "วิธีใช้",
            "ใช้งานยังไง",
            "ตั้งค่า",
            "setup",
            "economy",
            "music",
            "aichat",
            "automod",
            "antinuke",
            "roleplay",
            "rp",
            "โรเพล",
            "โรลเพล",
        )
        include_command_reference = full_context_mode or self._is_command_help_query(user_content) or any(
            token in lowered_user_text for token in command_intent_tokens
        )
        if include_command_reference:
            command_reference = self._build_command_reference_for_prompt(
                user_content, prefix, limit=command_limit
            )
        guild_channel_reference = self._build_guild_channel_reference_for_prompt(
            message, full_context=full_context_mode
        )
        site_reference = self._build_site_reference_for_prompt(
            user_content,
            force_full=full_context_mode,
            limit=(self.ai_full_context_site_limit if full_context_mode else 10),
        )

        prompt = (
            f"{self.ai_base_system_prompt}\n\n"
            f"{runtime_context}\n\n"
            f"{behavior_context}\n\n"
            f"{memory_write_context}"
        )
        if command_reference:
            prompt += f"\n\n{command_reference}"
        if guild_channel_reference:
            prompt += f"\n\n{guild_channel_reference}"
        if site_reference:
            prompt += f"\n\n{site_reference}"
        return prompt

    @staticmethod
    def _normalize_endpoint_path(path: str) -> str:
        raw = str(path or "").strip()
        if not raw:
            return "/chat/completions"
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        if not raw.startswith("/"):
            raw = f"/{raw}"
        return raw

    def _build_api_endpoint(self, base_url: str, endpoint_path: str) -> str:
        path = self._normalize_endpoint_path(endpoint_path)
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{str(base_url or '').rstrip('/')}{path}"

    @staticmethod
    def _parse_csv_values(raw_text: str) -> list[str]:
        text = str(raw_text or "").strip()
        if not text:
            return []
        parts = [str(item).strip() for item in text.split(",")]
        return [item for item in parts if item]

    @staticmethod
    def _is_non_grpc_route_error(error_text: str) -> bool:
        text = str(error_text or "").strip().lower()
        if not text:
            return False
        return (
            "non-grpc request matched gRPC route".lower() in text
            or ("http api error 415" in text and "grpc" in text)
        )

    @staticmethod
    def _is_http_status_like_error(error_text: str, statuses: tuple[int, ...]) -> bool:
        text = str(error_text or "").strip().lower()
        if not text:
            return False
        for status in statuses:
            if f"http api error {int(status)}" in text:
                return True
        return False

    @staticmethod
    def _is_chindax_model_not_found_error(error_text: str) -> bool:
        text = str(error_text or "").strip().lower()
        if not text:
            return False
        return "model not found" in text

    @staticmethod
    def _is_model_not_found_error(error_text: str) -> bool:
        text = str(error_text or "").strip().lower()
        if not text:
            return False
        return "model not found" in text or ("not found" in text and "model" in text)

    def _build_chindax_endpoint_candidates(self) -> list[tuple[str, str, str, str]]:
        base_candidates = []
        for base in [
            self.chindax_base_url,
            self.chindax_alt_base_url,
            "https://chindax.iapp.co.th/api",
            "https://chindax.iapp.co.th/v1",
            "https://chindax.iapp.co.th",
        ]:
            value = str(base or "").strip().rstrip("/")
            if value and value not in base_candidates:
                base_candidates.append(value)

        path_candidates = []
        for path in [
            self.chindax_chat_completions_path,
            *self._parse_csv_values(self.chindax_endpoint_candidates_raw),
            "/api/chat/completions",
            "/chat/completions",
            "/v1/chat/completions",
        ]:
            normalized = self._normalize_endpoint_path(path)
            if normalized and normalized not in path_candidates:
                path_candidates.append(normalized)

        auth_candidates = []
        configured_auth = (
            str(self.chindax_auth_header or "Authorization").strip() or "Authorization",
            str(self.chindax_auth_scheme or "Bearer").strip() or "Bearer",
        )
        for auth_header, auth_scheme in [
            configured_auth,
            ("Authorization", "Bearer"),
        ]:
            key = (str(auth_header).strip() or "Authorization", str(auth_scheme).strip())
            if key not in auth_candidates:
                auth_candidates.append(key)

        candidates: list[tuple[str, str, str, str]] = []
        for base in base_candidates:
            for path in path_candidates:
                for auth_header, auth_scheme in auth_candidates:
                    row = (base, path, auth_header, auth_scheme)
                    if row not in candidates:
                        candidates.append(row)

        configured_row = (
            str(self.chindax_base_url or "").strip().rstrip("/"),
            self._normalize_endpoint_path(self.chindax_chat_completions_path),
            str(self.chindax_auth_header or "Authorization").strip() or "Authorization",
            str(self.chindax_auth_scheme or "Bearer").strip() or "Bearer",
        )
        prioritized = [configured_row] if configured_row not in candidates else []
        prioritized.extend(candidates)
        return prioritized

    def _chindax_model_fallbacks(self, preferred_model: str) -> list[str]:
        candidates = [
            str(preferred_model or "").strip(),
            str(self.chindax_model or "").strip(),
            *self._parse_csv_values(self.chindax_model_candidates_raw),
            "accounts/fireworks/models/gpt-oss-20b",
            "accounts/fireworks/models/gpt-oss-120b",
            "Qwen/Qwen3-14B",
        ]
        resolved: list[str] = []
        for row in candidates:
            name = str(row or "").strip()
            if not name or name in resolved:
                continue
            resolved.append(name)
        return resolved

    def _log_ai_event_once(
        self,
        *,
        key: str,
        message: str,
        level: str = "warning",
        cooldown_seconds: int = 180,
    ) -> None:
        log_key = str(key or "").strip()
        if not log_key:
            log_key = "ai_event"
        now = time.time()
        expires_at = float(self.ai_log_cooldowns[log_key] or 0.0)
        if now < expires_at:
            return
        self.ai_log_cooldowns[log_key] = now + max(1, int(cooldown_seconds))
        if str(level or "").strip().lower() == "info":
            logger.info(str(message or ""))
            return
        logger.warning(str(message or ""))

    def _is_provider_retry_blocked(self, key: str) -> bool:
        cooldown_key = str(key or "").strip()
        if not cooldown_key:
            return False
        return time.time() < float(self.ai_provider_retry_cooldowns[cooldown_key] or 0.0)

    def _set_provider_retry_block(self, key: str, seconds: int) -> None:
        cooldown_key = str(key or "").strip()
        if not cooldown_key:
            return
        self.ai_provider_retry_cooldowns[cooldown_key] = time.time() + max(1, int(seconds))

    async def _ask_chindax_model(
        self,
        *,
        model: str,
        messages_payload: list[dict[str, str]],
    ) -> str:
        if not self.chindax_api_key:
            return ""
        if self._is_provider_retry_blocked("chindax_endpoint_resolution"):
            raise RuntimeError("ChindaX endpoint resolution is cooling down; using fallback provider.")

        last_error: Exception | None = None
        attempt_errors: list[str] = []
        max_attempts = 24
        attempted = 0
        for base_url, endpoint_path, auth_header, auth_scheme in self._build_chindax_endpoint_candidates():
            for candidate_model in self._chindax_model_fallbacks(model):
                attempted += 1
                if attempted > max_attempts:
                    break
                try:
                    return await self._ask_openai_compatible_http(
                        base_url=base_url,
                        endpoint_path=endpoint_path,
                        api_key=self.chindax_api_key,
                        model=candidate_model,
                        messages_payload=messages_payload,
                        auth_header=auth_header,
                        auth_scheme=auth_scheme,
                        request_timeout_seconds=self.ai_request_timeout_seconds,
                    )
                except Exception as error:
                    last_error = error
                    error_text = str(error or "").strip()
                    attempt_errors.append(
                        f"{base_url}{self._normalize_endpoint_path(endpoint_path)} | {candidate_model} | {auth_header}"
                    )
                    if len(attempt_errors) > 6:
                        attempt_errors = attempt_errors[-6:]
                    recoverable = self._is_http_status_like_error(
                        error_text, (400, 401, 403, 404, 405, 415, 429)
                    )
                    if not recoverable:
                        raise
                    if self._is_chindax_model_not_found_error(error_text):
                        continue
                    break
            if attempted > max_attempts:
                break

        if last_error:
            self._set_provider_retry_block("chindax_endpoint_resolution", 90)
            raise RuntimeError(
                "ChindaX endpoint/model resolution failed after multiple attempts: "
                + " | ".join(attempt_errors[:4])
                + f" | last_error={str(last_error)[:220]}"
            )
        return ""

    def _build_cloudflare_endpoint_candidates(self) -> list[tuple[str, str, str, str]]:
        account_base = ""
        if self.cloudflare_account_id:
            account_base = f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/v1"

        base_candidates = []
        for base in [
            self.cloudflare_base_url,
            account_base,
            "https://api.cloudflare.com/client/v4/accounts",
        ]:
            value = str(base or "").strip().rstrip("/")
            if value and value not in base_candidates:
                base_candidates.append(value)

        path_candidates = []
        for path in [
            self.cloudflare_chat_completions_path,
            *self._parse_csv_values(self.cloudflare_endpoint_candidates_raw),
            "/chat/completions",
            "/v1/chat/completions",
        ]:
            normalized = self._normalize_endpoint_path(path)
            if normalized and normalized not in path_candidates:
                path_candidates.append(normalized)

        auth_candidates = []
        configured_auth = (
            str(self.cloudflare_auth_header or "Authorization").strip() or "Authorization",
            str(self.cloudflare_auth_scheme or "Bearer").strip() or "Bearer",
        )
        for auth_header, auth_scheme in [
            configured_auth,
            ("Authorization", "Bearer"),
        ]:
            key = (str(auth_header).strip() or "Authorization", str(auth_scheme).strip())
            if key not in auth_candidates:
                auth_candidates.append(key)

        candidates: list[tuple[str, str, str, str]] = []
        for base in base_candidates:
            for path in path_candidates:
                for auth_header, auth_scheme in auth_candidates:
                    row = (base, path, auth_header, auth_scheme)
                    if row not in candidates:
                        candidates.append(row)

        configured_row = (
            str(self.cloudflare_base_url or "").strip().rstrip("/"),
            self._normalize_endpoint_path(self.cloudflare_chat_completions_path),
            str(self.cloudflare_auth_header or "Authorization").strip() or "Authorization",
            str(self.cloudflare_auth_scheme or "Bearer").strip() or "Bearer",
        )
        prioritized = [configured_row] if configured_row not in candidates else []
        prioritized.extend(candidates)
        return prioritized

    def _cloudflare_model_fallbacks(self, preferred_model: str) -> list[str]:
        candidates = [
            str(preferred_model or "").strip(),
            str(self.cloudflare_model or "").strip(),
            *self._parse_csv_values(self.cloudflare_model_candidates_raw),
            "@cf/meta/llama-3.1-8b-instruct",
            "@cf/meta/llama-3.1-8b-instruct-fast",
            "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
        ]
        resolved: list[str] = []
        for row in candidates:
            name = str(row or "").strip()
            if not name or name in resolved:
                continue
            resolved.append(name)
        return resolved

    async def _ask_cloudflare_model(
        self,
        *,
        model: str,
        messages_payload: list[dict[str, str]],
    ) -> str:
        if not self.cloudflare_api_key:
            return ""
        if self._is_provider_retry_blocked("cloudflare_endpoint_resolution"):
            raise RuntimeError("Cloudflare endpoint resolution is cooling down; using fallback provider.")

        last_error: Exception | None = None
        attempt_errors: list[str] = []
        max_attempts = 24
        attempted = 0
        for base_url, endpoint_path, auth_header, auth_scheme in self._build_cloudflare_endpoint_candidates():
            for candidate_model in self._cloudflare_model_fallbacks(model):
                attempted += 1
                if attempted > max_attempts:
                    break
                try:
                    return await self._ask_openai_compatible_http(
                        base_url=base_url,
                        endpoint_path=endpoint_path,
                        api_key=self.cloudflare_api_key,
                        model=candidate_model,
                        messages_payload=messages_payload,
                        auth_header=auth_header,
                        auth_scheme=auth_scheme,
                        request_timeout_seconds=self.ai_request_timeout_seconds,
                    )
                except Exception as error:
                    last_error = error
                    error_text = str(error or "").strip()
                    attempt_errors.append(
                        f"{base_url}{self._normalize_endpoint_path(endpoint_path)} | {candidate_model} | {auth_header}"
                    )
                    if len(attempt_errors) > 6:
                        attempt_errors = attempt_errors[-6:]
                    recoverable = self._is_http_status_like_error(
                        error_text, (400, 401, 403, 404, 405, 415, 429)
                    )
                    if not recoverable:
                        raise
                    if self._is_model_not_found_error(error_text):
                        continue
                    break
            if attempted > max_attempts:
                break

        if last_error:
            self._set_provider_retry_block("cloudflare_endpoint_resolution", 90)
            raise RuntimeError(
                "Cloudflare endpoint/model resolution failed after multiple attempts: "
                + " | ".join(attempt_errors[:4])
                + f" | last_error={str(last_error)[:220]}"
            )
        return ""

    def _build_thaillm_endpoint_candidates(self) -> list[tuple[str, str, str, str]]:
        base_candidates = []
        for base in [
            self.thaillm_base_url,
            self.thaillm_alt_base_url,
            "http://thaillm.or.th/api",
            "https://thaillm.or.th/api",
            "https://playground.thaillm.or.th/api/v1",
            "https://openthaigpt.aieat.or.th",
            "https://api.opentyphoon.ai/v1",
        ]:
            value = str(base or "").strip().rstrip("/")
            if value and value not in base_candidates:
                base_candidates.append(value)

        path_candidates = []
        for path in [
            self.thaillm_chat_completions_path,
            *self._parse_csv_values(self.thaillm_endpoint_candidates_raw),
            "/v1/chat/completions",
            "/chat/completions",
            "/api/v1/chat/completions",
            "/api/chat/completions",
            "/{model_key}/v1/chat/completions",
        ]:
            normalized = self._normalize_endpoint_path(path)
            if normalized and normalized not in path_candidates:
                path_candidates.append(normalized)

        auth_candidates = []
        configured_auth = (
            str(self.thaillm_auth_header or "Authorization").strip() or "Authorization",
            str(self.thaillm_auth_scheme or "Bearer").strip() or "Bearer",
        )
        for auth_header, auth_scheme in [
            configured_auth,
            ("Authorization", "Bearer"),
            ("x-api-key", ""),
            ("Apikey", ""),
            ("apikey", ""),
        ]:
            key = (str(auth_header).strip() or "Authorization", str(auth_scheme).strip())
            if key not in auth_candidates:
                auth_candidates.append(key)

        candidates: list[tuple[str, str, str, str]] = []
        for base in base_candidates:
            for path in path_candidates:
                for auth_header, auth_scheme in auth_candidates:
                    row = (base, path, auth_header, auth_scheme)
                    if row not in candidates:
                        candidates.append(row)

        configured_row = (
            str(self.thaillm_base_url or "").strip().rstrip("/"),
            self._normalize_endpoint_path(self.thaillm_chat_completions_path),
            str(self.thaillm_auth_header or "Authorization").strip() or "Authorization",
            str(self.thaillm_auth_scheme or "Bearer").strip() or "Bearer",
        )
        prioritized = [configured_row] if configured_row not in candidates else []
        prioritized.extend(candidates)
        return prioritized

    @staticmethod
    def _thaillm_model_key(raw_model: str) -> str:
        value = str(raw_model or "").strip().lower()
        if not value:
            return "openthaigpt"
        alias_map = {
            "openthaigpt-thaillm-8b-instruct-v7.2": "openthaigpt",
            "openthaigpt": "openthaigpt",
            "pathumma-thaillm-qwen3-8b-think-3.0.0": "pathumma",
            "pathumma": "pathumma",
            "typhoon-s-thaillm-8b-instruct": "typhoon",
            "typhoon": "typhoon",
            "thalle-0.2-thaillm-8b-fa": "thalle",
            "thalle": "thalle",
            "kbtg": "thalle",
        }
        if value in alias_map:
            return alias_map[value]
        return re.sub(r"[^a-z0-9]+", "", value) or "openthaigpt"

    def _resolve_thaillm_endpoint_and_payload_model(
        self,
        endpoint_path: str,
        model: str,
    ) -> tuple[str, str]:
        path = str(endpoint_path or "").strip() or "/v1/chat/completions"
        payload_model = str(model or "").strip()
        if "{model_key}" in path:
            model_key = self._thaillm_model_key(model)
            path = path.replace("{model_key}", model_key)
            payload_model = "/model"
        return self._normalize_endpoint_path(path), payload_model

    def _thaillm_model_fallbacks(self, preferred_model: str) -> list[str]:
        candidates = [
            str(preferred_model or "").strip(),
            str(self.thaillm_model or "").strip(),
            *self._parse_csv_values(self.thaillm_model_candidates_raw),
            "openthaigpt",
            "pathumma",
            "typhoon",
            "thalle",
            "kbtg",
            "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2",
            "Pathumma-ThaiLLM-qwen3-8b-think-3.0.0",
            "Typhoon-S-ThaiLLM-8B-Instruct",
            "THaLLE-0.2-ThaiLLM-8B-fa",
        ]
        resolved: list[str] = []
        for row in candidates:
            name = str(row or "").strip()
            if not name or name in resolved:
                continue
            resolved.append(name)
        return resolved

    async def _ask_thaillm_model(
        self,
        *,
        model: str,
        messages_payload: list[dict[str, str]],
    ) -> str:
        if not self.thaillm_api_key:
            return ""
        if self._is_provider_retry_blocked("thaillm_endpoint_resolution"):
            raise RuntimeError("ThaiLLM endpoint resolution is cooling down; using fallback provider.")

        last_error: Exception | None = None
        attempt_errors: list[str] = []
        max_attempts = 28
        attempted = 0
        extra_headers: dict[str, str] = {}
        if self.thaillm_consumer_id:
            extra_headers[self.thaillm_consumer_id_header] = self.thaillm_consumer_id
        for base_url, endpoint_path, auth_header, auth_scheme in self._build_thaillm_endpoint_candidates():
            for candidate_model in self._thaillm_model_fallbacks(model):
                attempted += 1
                if attempted > max_attempts:
                    break
                resolved_endpoint_path, payload_model = self._resolve_thaillm_endpoint_and_payload_model(
                    endpoint_path,
                    candidate_model,
                )
                try:
                    return await self._ask_openai_compatible_http(
                        base_url=base_url,
                        endpoint_path=resolved_endpoint_path,
                        api_key=self.thaillm_api_key,
                        model=payload_model,
                        messages_payload=messages_payload,
                        auth_header=auth_header,
                        auth_scheme=auth_scheme,
                        extra_headers=extra_headers,
                        request_timeout_seconds=self.ai_request_timeout_seconds,
                    )
                except Exception as error:
                    last_error = error
                    error_text = str(error or "").strip()
                    attempt_errors.append(
                        f"{base_url}{resolved_endpoint_path} | {candidate_model} | {auth_header}"
                    )
                    if len(attempt_errors) > 6:
                        attempt_errors = attempt_errors[-6:]
                    recoverable = self._is_http_status_like_error(
                        error_text, (400, 401, 403, 404, 405, 415, 429)
                    )
                    if not recoverable:
                        raise
                    if self._is_model_not_found_error(error_text):
                        continue
                    break
            if attempted > max_attempts:
                break

        if last_error:
            self._set_provider_retry_block("thaillm_endpoint_resolution", 120)
            raise RuntimeError(
                "ThaiLLM endpoint/model resolution failed after multiple attempts: "
                + " | ".join(attempt_errors[:4])
                + f" | last_error={str(last_error)[:220]}"
            )
        return ""

    def _build_aiforthai_endpoint_candidates(self) -> list[tuple[str, str, str, str]]:
        base_candidates = []
        for base in [
            self.aiforthai_base_url,
            self.aiforthai_alt_base_url,
            "https://aiforthai.in.th/api/v1/provider",
            "https://api.aiforthai.in.th",
            "https://api.aiforthai.in.th/v1",
        ]:
            value = str(base or "").strip().rstrip("/")
            if value and value not in base_candidates:
                base_candidates.append(value)

        path_candidates = []
        for path in [
            self.aiforthai_chat_completions_path,
            *self._parse_csv_values(self.aiforthai_endpoint_candidates_raw),
        ]:
            normalized = self._normalize_endpoint_path(path)
            if normalized and normalized not in path_candidates:
                path_candidates.append(normalized)

        auth_candidates = []
        configured_auth = (
            str(self.aiforthai_api_key_header or "Apikey").strip() or "Apikey",
            "Bearer" if self.aiforthai_use_bearer_auth else "",
        )
        for auth_header, auth_scheme in [
            configured_auth,
            ("Apikey", ""),
            ("x-api-key", ""),
            ("Authorization", "Bearer"),
        ]:
            key = (str(auth_header).strip() or "Authorization", str(auth_scheme).strip())
            if key not in auth_candidates:
                auth_candidates.append(key)

        candidates: list[tuple[str, str, str, str]] = []
        for base in base_candidates:
            for path in path_candidates:
                for auth_header, auth_scheme in auth_candidates:
                    row = (base, path, auth_header, auth_scheme)
                    if row not in candidates:
                        candidates.append(row)

        configured_row = (
            str(self.aiforthai_base_url or "").strip().rstrip("/"),
            self._normalize_endpoint_path(self.aiforthai_chat_completions_path),
            str(self.aiforthai_api_key_header or "Apikey").strip() or "Apikey",
            "Bearer" if self.aiforthai_use_bearer_auth else "",
        )
        prioritized = [configured_row] if configured_row not in candidates else []
        prioritized.extend(candidates)
        return prioritized

    async def _ask_aiforthai_model(
        self,
        *,
        model: str,
        messages_payload: list[dict[str, str]],
    ) -> str:
        if not self.aiforthai_api_key:
            return ""
        if self._is_provider_retry_blocked("aiforthai_endpoint_resolution"):
            raise RuntimeError("AI FOR THAI endpoint resolution is cooling down; using fallback provider.")

        last_error: Exception | None = None
        attempt_errors: list[str] = []
        max_attempts = 12
        attempted = 0
        for base_url, endpoint_path, auth_header, auth_scheme in self._build_aiforthai_endpoint_candidates():
            attempted += 1
            if attempted > max_attempts:
                break
            try:
                return await self._ask_openai_compatible_http(
                    base_url=base_url,
                    endpoint_path=endpoint_path,
                    api_key=self.aiforthai_api_key,
                    model=model,
                    messages_payload=messages_payload,
                    auth_header=auth_header,
                    auth_scheme=auth_scheme,
                    request_timeout_seconds=self.ai_request_timeout_seconds,
                )
            except Exception as error:
                last_error = error
                error_text = str(error or "").strip()
                attempt_errors.append(
                    f"{base_url}{self._normalize_endpoint_path(endpoint_path)} | {auth_header}"
                )
                if len(attempt_errors) > 5:
                    attempt_errors = attempt_errors[-5:]
                recoverable = (
                    self._is_non_grpc_route_error(error_text)
                    or self._is_http_status_like_error(error_text, (401, 403, 404, 405, 415, 429))
                )
                if not recoverable:
                    raise
                continue

        if last_error:
            self._set_provider_retry_block("aiforthai_endpoint_resolution", 120)
            raise RuntimeError(
                "AI FOR THAI endpoint resolution failed after multiple attempts: "
                + " | ".join(attempt_errors[:4])
                + f" | last_error={str(last_error)[:220]}"
            )
        return ""

    def _is_ollama_cloud_host(self) -> bool:
        base = str(self.ollama_base_url or "").strip().lower()
        return base.startswith("https://ollama.com")

    async def _fetch_ollama_model_catalog(self, *, force: bool = False) -> list[str]:
        if not self._is_ollama_cloud_host():
            return []
        now = time.time()
        if (
            not force
            and self.ollama_model_catalog_cache
            and now < float(self.ollama_model_catalog_cache_expires_at or 0.0)
        ):
            return list(self.ollama_model_catalog_cache)
        if not self.ollama_api_key:
            return []

        base_url = str(self.ollama_base_url or "").strip().rstrip("/")
        endpoint = (
            f"{base_url}/tags"
            if base_url.lower().endswith("/api")
            else f"{base_url}/api/tags"
        )
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {
            "Authorization": f"Bearer {self.ollama_api_key}",
            "Accept": "application/json",
        }
        names: list[str] = []
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(endpoint, headers=headers) as response:
                    if response.status != 200:
                        return []
                    data = await response.json(content_type=None)
            models = (data or {}).get("models") if isinstance(data, dict) else []
            for row in list(models or []):
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                if not name or name in names:
                    continue
                names.append(name)
        except Exception:
            return []

        self.ollama_model_catalog_cache = list(names)
        self.ollama_model_catalog_cache_expires_at = now + float(self.ollama_model_catalog_ttl_seconds or 600.0)
        return list(names)

    async def _resolve_ollama_cloud_model(self, preferred_model: str) -> str:
        preferred = str(preferred_model or "").strip()
        catalog = await self._fetch_ollama_model_catalog()
        if not catalog:
            return preferred or "gpt-oss:20b"
        lower_to_name = {str(name).strip().lower(): str(name).strip() for name in catalog}
        direct_match = lower_to_name.get(preferred.lower()) if preferred else None
        if direct_match:
            return direct_match

        candidates = [
            "gpt-oss:20b",
            "gpt-oss:120b",
            "gemma3:4b",
            "gemma3:12b",
            "gemma3:27b",
        ]
        for candidate in candidates:
            resolved = lower_to_name.get(candidate.lower())
            if resolved:
                return resolved
        return str(catalog[0] or preferred or "gpt-oss:20b").strip() or "gpt-oss:20b"

    @staticmethod
    def _extract_text_from_ai_payload(data: Any) -> str:
        def _extract(node: Any) -> str:
            if isinstance(node, str):
                return node.strip()
            if isinstance(node, list):
                for item in node:
                    nested_text = _extract(item)
                    if nested_text:
                        return nested_text
                return ""
            if not isinstance(node, dict):
                return ""

            choices = node.get("choices")
            if isinstance(choices, list) and choices:
                first_choice = choices[0] if isinstance(choices[0], dict) else {}
                message_obj = first_choice.get("message") if isinstance(first_choice, dict) else {}
                content = ""
                if isinstance(message_obj, dict):
                    content = str(message_obj.get("content") or "").strip()
                if content:
                    return content
                text = str(first_choice.get("text") or "").strip() if isinstance(first_choice, dict) else ""
                if text:
                    return text

            message_obj = node.get("message")
            if isinstance(message_obj, dict):
                content = str(message_obj.get("content") or "").strip()
                if content:
                    return content

            for key in ("output_text", "text", "response", "answer"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            for nested_key in ("result", "data", "output", "response", "message"):
                nested_value = node.get(nested_key)
                nested_text = _extract(nested_value)
                if nested_text:
                    return nested_text
            return ""

        return _extract(data)

    async def _ask_openai_compatible_http(
        self,
        *,
        base_url: str,
        endpoint_path: str,
        api_key: str,
        model: str,
        messages_payload: list[dict[str, str]],
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        extra_headers: dict[str, str] | None = None,
        request_timeout_seconds: int = 180,
    ) -> str:
        endpoint = self._build_api_endpoint(base_url, endpoint_path)
        timeout = aiohttp.ClientTimeout(total=max(10, int(request_timeout_seconds)))
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            token_value = str(api_key)
            scheme = str(auth_scheme or "").strip()
            if scheme:
                token_value = f"{scheme} {token_value}"
            headers[str(auth_header or "Authorization")] = token_value
        if isinstance(extra_headers, dict):
            for header_name, header_value in extra_headers.items():
                key = str(header_name or "").strip()
                value = str(header_value or "").strip()
                if not key or not value:
                    continue
                headers[key] = value

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages_payload,
            "max_tokens": 450,
            "temperature": 0.35,
            "top_p": 0.9,
            "stream": False,
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(
                        f"HTTP API error {response.status} from {endpoint}: {str(body or '')[:250]}"
                    )
                data = await response.json(content_type=None)

        text = self._extract_text_from_ai_payload(data)
        clip_limit = max(1200, int(getattr(self, "ai_max_reply_chars", 5600) or 5600))
        return str(text or "").strip()[:clip_limit]

    async def _ask_ai_model_with_provider(
        self,
        content: str,
        system_prompt: str,
        messages_payload: list[dict[str, str]] | None = None,
        *,
        provider: str,
        ai_model: str | None = None,
    ) -> str:
        messages_payload = messages_payload or [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]
        provider_name = str(provider or "").strip().lower()
        if provider_name not in {
            "openai",
            "ollama",
            "google",
            "opentyphoon",
            "chindax",
            "aiforthai",
            "cloudflare",
            "thaillm",
        }:
            provider_name = self.ai_provider
        model_to_use = str(ai_model or "").strip() or self._provider_default_model(provider_name)

        if provider_name == "ollama":
            timeout = aiohttp.ClientTimeout(total=180)
            is_cloud_host = self._is_ollama_cloud_host()
            if is_cloud_host:
                resolved_cloud_model = await self._resolve_ollama_cloud_model(model_to_use)
                if resolved_cloud_model:
                    model_to_use = resolved_cloud_model
            payload = {
                "model": model_to_use,
                "messages": messages_payload,
                "stream": False,
                "options": {"temperature": 0.35, "top_p": 0.9},
            }
            base_url = str(self.ollama_base_url or "").strip().rstrip("/")
            endpoint = (
                f"{base_url}/chat"
                if base_url.lower().endswith("/api")
                else f"{base_url}/api/chat"
            )
            headers = {}
            if self.ollama_api_key:
                headers["Authorization"] = f"Bearer {self.ollama_api_key}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    endpoint, json=payload, headers=headers
                ) as response:
                    if response.status != 200:
                        body = await response.text()
                        error_text = str(body or "").strip().lower()
                        model_not_found = (
                            response.status == 404
                            and "not found" in error_text
                            and "model" in error_text
                        )
                        if model_not_found and is_cloud_host:
                            fallback_model = await self._resolve_ollama_cloud_model("")
                            if fallback_model and fallback_model != str(payload.get("model") or "").strip():
                                payload["model"] = fallback_model
                                async with session.post(endpoint, json=payload, headers=headers) as retry_response:
                                    if retry_response.status == 200:
                                        data = await retry_response.json(content_type=None)
                                        text = str(((data.get("message") or {}).get("content") or "")).strip()
                                        logger.warning(
                                            f"Ollama cloud model fallback | from={model_to_use} | to={fallback_model}"
                                        )
                                        clip_limit = max(1200, int(getattr(self, "ai_max_reply_chars", 5600) or 5600))
                                        return text[:clip_limit]
                                    retry_body = await retry_response.text()
                                    raise RuntimeError(
                                        f"Ollama API error {retry_response.status}: {str(retry_body or '')[:250]}"
                                    )
                        raise RuntimeError(
                            f"Ollama API error {response.status}: {body[:250]}"
                        )
                    data = await response.json(content_type=None)
            text = str(((data.get("message") or {}).get("content") or "")).strip()
            clip_limit = max(1200, int(getattr(self, "ai_max_reply_chars", 5600) or 5600))
            return text[:clip_limit]

        if provider_name == "google":
            if not self.google_api_key:
                return ""

            timeout = aiohttp.ClientTimeout(total=180)
            system_lines = []
            google_contents = []
            for row in list(messages_payload or []):
                role = str((row or {}).get("role") or "user").strip().lower()
                text = str((row or {}).get("content") or "").strip()
                if not text:
                    continue
                if role == "system":
                    system_lines.append(text)
                    continue
                google_role = "model" if role == "assistant" else "user"
                google_contents.append(
                    {
                        "role": google_role,
                        "parts": [{"text": text[:4000]}],
                    }
                )
            if not google_contents:
                google_contents = [{"role": "user", "parts": [{"text": str(content or "").strip()[:4000]}]}]

            payload: dict[str, Any] = {
                "contents": google_contents,
                "generationConfig": {
                    "temperature": 0.35,
                    "topP": 0.9,
                    "maxOutputTokens": 450,
                },
            }
            if system_lines:
                payload["systemInstruction"] = {
                    "parts": [{"text": "\n\n".join(system_lines)[:8000]}]
                }

            data = {}
            last_error_text = ""
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for candidate_model in self._google_model_fallbacks(model_to_use):
                    model_escaped = quote(candidate_model, safe="")
                    endpoint = (
                        f"{self.google_base_url}/models/{model_escaped}:generateContent"
                        f"?key={self.google_api_key}"
                    )
                    async with session.post(endpoint, json=payload) as response:
                        if response.status == 200:
                            data = await response.json(content_type=None)
                            model_to_use = candidate_model
                            break
                        body = await response.text()
                        error_body = str(body or "").strip()
                        last_error_text = f"Google Gemini API error {response.status}: {error_body[:250]}"
                        lower_body = error_body.lower()
                        model_not_found = (
                            response.status == 404
                            and ("model is not found" in lower_body or "not found" in lower_body)
                        )
                        if model_not_found:
                            continue
                        raise RuntimeError(last_error_text)
                if not data:
                    raise RuntimeError(last_error_text or "Google Gemini API error: no available model")

            parts = []
            for candidate in list((data or {}).get("candidates") or []):
                content_obj = candidate.get("content") if isinstance(candidate, dict) else {}
                for part in list((content_obj or {}).get("parts") or []):
                    text = str((part or {}).get("text") or "").strip()
                    if text:
                        parts.append(text)
                if parts:
                    break
            text = "\n".join(parts).strip()
            clip_limit = max(1200, int(getattr(self, "ai_max_reply_chars", 5600) or 5600))
            return text[:clip_limit]

        if provider_name == "opentyphoon":
            if not self.opentyphoon_api_key:
                return ""
            return await self._ask_openai_compatible_http(
                base_url=self.opentyphoon_base_url,
                endpoint_path="/chat/completions",
                api_key=self.opentyphoon_api_key,
                model=model_to_use,
                messages_payload=messages_payload,
                auth_header="Authorization",
                auth_scheme="Bearer",
                request_timeout_seconds=self.ai_request_timeout_seconds,
            )

        if provider_name == "chindax":
            return await self._ask_chindax_model(
                model=model_to_use,
                messages_payload=messages_payload,
            )

        if provider_name == "aiforthai":
            return await self._ask_aiforthai_model(
                model=model_to_use,
                messages_payload=messages_payload,
            )

        if provider_name == "cloudflare":
            return await self._ask_cloudflare_model(
                model=model_to_use,
                messages_payload=messages_payload,
            )

        if provider_name == "thaillm":
            return await self._ask_thaillm_model(
                model=model_to_use,
                messages_payload=messages_payload,
            )

        openai_client = self._ensure_openai_client()
        if not openai_client:
            return ""

        response = await openai_client.chat.completions.create(
            model=model_to_use,
            messages=messages_payload,
            max_tokens=450,
            temperature=0.35,
        )
        text = (response.choices[0].message.content or "").strip()
        clip_limit = max(1200, int(getattr(self, "ai_max_reply_chars", 5600) or 5600))
        return text[:clip_limit]

    async def ask_ai_model(
        self,
        content: str,
        system_prompt: str,
        messages_payload: list[dict[str, str]] | None = None,
        *,
        ai_model: str | None = None,
        provider: str | None = None,
    ) -> str:
        messages_payload = messages_payload or [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]
        allowed_providers = {
            "openai",
            "ollama",
            "google",
            "opentyphoon",
            "chindax",
            "aiforthai",
            "cloudflare",
            "thaillm",
        }
        primary_provider = str(provider or self.ai_provider or "").strip().lower()
        if primary_provider not in allowed_providers:
            primary_provider = "ollama"

        if provider is None and hasattr(self.bot, "ownerbot_runtime_ai_provider"):
            try:
                runtime_provider = await self.bot.ownerbot_runtime_ai_provider(
                    fallback=primary_provider
                )
                runtime_provider_text = str(runtime_provider or "").strip().lower()
                if runtime_provider_text in allowed_providers:
                    primary_provider = runtime_provider_text
            except Exception:
                pass

        primary_model = str(ai_model or "").strip()
        if not primary_model and hasattr(self.bot, "ownerbot_runtime_ai_model"):
            try:
                runtime_model = await self.bot.ownerbot_runtime_ai_model(
                    fallback=self._provider_default_model(primary_provider)
                )
                runtime_model_text = str(runtime_model or "").strip()
                if runtime_model_text:
                    primary_model = runtime_model_text
            except Exception:
                pass

        if not primary_model:
            primary_model = self._provider_default_model(primary_provider)

        try:
            return await self._ask_ai_model_with_provider(
                content,
                system_prompt,
                messages_payload,
                provider=primary_provider,
                ai_model=primary_model,
            )
        except Exception as primary_error:
            primary_error_text = str(primary_error or "")
            if primary_provider == "google" and self._is_google_quota_like_error(primary_error_text):
                fallback_errors: list[str] = []
                for fallback_provider in self._fallback_chain_for_provider(primary_provider):
                    if not self._provider_is_configured(fallback_provider):
                        continue
                    fallback_model = self._provider_default_model(fallback_provider)
                    try:
                        reply = await self._ask_ai_model_with_provider(
                            content,
                            system_prompt,
                            messages_payload,
                            provider=fallback_provider,
                            ai_model=fallback_model,
                        )
                    except Exception as fallback_error:
                        fallback_errors.append(
                            f"{fallback_provider}:{type(fallback_error).__name__}:{str(fallback_error)[:120]}"
                        )
                        continue
                    if str(reply or "").strip():
                        self._log_ai_event_once(
                            key=f"ai_fallback_google_to_{fallback_provider}",
                            message=(
                                "AI provider fallback activated | "
                                f"from=google | to={fallback_provider} | "
                                f"prompt_len={len(str(content or ''))}"
                            ),
                            level="warning",
                            cooldown_seconds=240,
                        )
                        return reply
                if fallback_errors:
                    self._log_ai_event_once(
                        key="ai_fallback_google_failed",
                        message=(
                            "AI provider fallback failed after Google quota | "
                            f"errors={' | '.join(fallback_errors[:3])}"
                        ),
                        level="warning",
                        cooldown_seconds=240,
                    )
            if primary_provider == "aiforthai" and self.aiforthai_force_provider_fallback:
                fallback_errors: list[str] = []
                for fallback_provider in self._fallback_chain_for_provider(primary_provider):
                    if fallback_provider == primary_provider:
                        continue
                    if not self._provider_is_configured(fallback_provider):
                        continue
                    fallback_model = self._provider_default_model(fallback_provider)
                    try:
                        reply = await self._ask_ai_model_with_provider(
                            content,
                            system_prompt,
                            messages_payload,
                            provider=fallback_provider,
                            ai_model=fallback_model,
                        )
                    except Exception as fallback_error:
                        fallback_errors.append(
                            f"{fallback_provider}:{type(fallback_error).__name__}:{str(fallback_error)[:120]}"
                        )
                        continue
                    if str(reply or "").strip():
                        self._log_ai_event_once(
                            key=f"ai_fallback_aiforthai_to_{fallback_provider}",
                            message=(
                                "AI provider fallback activated | "
                                f"from=aiforthai | to={fallback_provider} | "
                                f"prompt_len={len(str(content or ''))} | cause={primary_error_text[:160]}"
                            ),
                            level="info",
                            cooldown_seconds=180,
                        )
                        return reply
                if fallback_errors:
                    self._log_ai_event_once(
                        key="ai_fallback_aiforthai_failed",
                        message=(
                            "AI provider fallback failed after AI FOR THAI error | "
                            f"errors={' | '.join(fallback_errors[:3])}"
                        ),
                        level="warning",
                        cooldown_seconds=240,
                    )
            if primary_provider == "chindax" and self.chindax_force_provider_fallback:
                fallback_errors: list[str] = []
                for fallback_provider in self._fallback_chain_for_provider(primary_provider):
                    if fallback_provider == primary_provider:
                        continue
                    if not self._provider_is_configured(fallback_provider):
                        continue
                    fallback_model = self._provider_default_model(fallback_provider)
                    try:
                        reply = await self._ask_ai_model_with_provider(
                            content,
                            system_prompt,
                            messages_payload,
                            provider=fallback_provider,
                            ai_model=fallback_model,
                        )
                    except Exception as fallback_error:
                        fallback_errors.append(
                            f"{fallback_provider}:{type(fallback_error).__name__}:{str(fallback_error)[:120]}"
                        )
                        continue
                    if str(reply or "").strip():
                        self._log_ai_event_once(
                            key=f"ai_fallback_chindax_to_{fallback_provider}",
                            message=(
                                "AI provider fallback activated | "
                                f"from=chindax | to={fallback_provider} | "
                                f"prompt_len={len(str(content or ''))} | cause={primary_error_text[:160]}"
                            ),
                            level="info",
                            cooldown_seconds=180,
                        )
                        return reply
                if fallback_errors:
                    self._log_ai_event_once(
                        key="ai_fallback_chindax_failed",
                        message=(
                            "AI provider fallback failed after ChindaX error | "
                            f"errors={' | '.join(fallback_errors[:3])}"
                        ),
                        level="warning",
                        cooldown_seconds=240,
                    )
            if primary_provider == "cloudflare" and self.cloudflare_force_provider_fallback:
                fallback_errors: list[str] = []
                for fallback_provider in self._fallback_chain_for_provider(primary_provider):
                    if fallback_provider == primary_provider:
                        continue
                    if not self._provider_is_configured(fallback_provider):
                        continue
                    fallback_model = self._provider_default_model(fallback_provider)
                    try:
                        reply = await self._ask_ai_model_with_provider(
                            content,
                            system_prompt,
                            messages_payload,
                            provider=fallback_provider,
                            ai_model=fallback_model,
                        )
                    except Exception as fallback_error:
                        fallback_errors.append(
                            f"{fallback_provider}:{type(fallback_error).__name__}:{str(fallback_error)[:120]}"
                        )
                        continue
                    if str(reply or "").strip():
                        self._log_ai_event_once(
                            key=f"ai_fallback_cloudflare_to_{fallback_provider}",
                            message=(
                                "AI provider fallback activated | "
                                f"from=cloudflare | to={fallback_provider} | "
                                f"prompt_len={len(str(content or ''))} | cause={primary_error_text[:160]}"
                            ),
                            level="info",
                            cooldown_seconds=180,
                        )
                        return reply
                if fallback_errors:
                    self._log_ai_event_once(
                        key="ai_fallback_cloudflare_failed",
                        message=(
                            "AI provider fallback failed after Cloudflare error | "
                            f"errors={' | '.join(fallback_errors[:3])}"
                        ),
                        level="warning",
                        cooldown_seconds=240,
                    )
            if primary_provider == "thaillm" and self.thaillm_force_provider_fallback:
                fallback_errors: list[str] = []
                for fallback_provider in self._fallback_chain_for_provider(primary_provider):
                    if fallback_provider == primary_provider:
                        continue
                    if not self._provider_is_configured(fallback_provider):
                        continue
                    fallback_model = self._provider_default_model(fallback_provider)
                    try:
                        reply = await self._ask_ai_model_with_provider(
                            content,
                            system_prompt,
                            messages_payload,
                            provider=fallback_provider,
                            ai_model=fallback_model,
                        )
                    except Exception as fallback_error:
                        fallback_errors.append(
                            f"{fallback_provider}:{type(fallback_error).__name__}:{str(fallback_error)[:120]}"
                        )
                        continue
                    if str(reply or "").strip():
                        self._log_ai_event_once(
                            key=f"ai_fallback_thaillm_to_{fallback_provider}",
                            message=(
                                "AI provider fallback activated | "
                                f"from=thaillm | to={fallback_provider} | "
                                f"prompt_len={len(str(content or ''))} | cause={primary_error_text[:160]}"
                            ),
                            level="info",
                            cooldown_seconds=180,
                        )
                        return reply
                if fallback_errors:
                    self._log_ai_event_once(
                        key="ai_fallback_thaillm_failed",
                        message=(
                            "AI provider fallback failed after ThaiLLM error | "
                            f"errors={' | '.join(fallback_errors[:3])}"
                        ),
                        level="warning",
                        cooldown_seconds=240,
                    )
            raise

    async def ai_chat_module(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        ai_data = cache.ai_chat_channels.get(str(message.guild.id), {})

        if not ai_data:

            return

        channel_id = ai_data.get("channel_id")
        try:
            channel_id = int(channel_id) if channel_id else None
        except (TypeError, ValueError):
            channel_id = None

        if not channel_id or message.channel.id != channel_id:

            return

        if self._is_music_setup_channel(message.guild.id, message.channel.id):
            # Never process AI in music setup channel; this channel should stay low-latency.
            return

        content = str(message.content or "").strip()
        if not content:
            return
        if content == self.bot.user.mention:
            return

        guild_prefix = cache.guilds.get(str(message.guild.id), {}).get(
            "prefix", BotConfig.PREFIX
        )
        if content.startswith(guild_prefix):
            return

        # Allow natural-language music play in AI chat (e.g. "เปิดเพลง ...", "play ...")
        # without requiring explicit prefix command.
        if self.ai_music_intercept_enabled:
            if await self._maybe_execute_ai_music_play_intent(
                message,
                content=content,
                guild_prefix=str(guild_prefix or BotConfig.PREFIX),
            ):
                return

        is_direct_to_bot = self._is_direct_ai_message_to_bot(message)
        reply_chance = self._ai_reply_chance(ai_data)
        now = time.time()
        channel_key = f"{message.guild.id}:{message.channel.id}"

        if (
            not is_direct_to_bot
            and reply_chance < 100
            and random.randint(1, 100) > reply_chance
        ):
            return

        min_interval = float(self.ai_channel_min_reply_interval_seconds or 0.0)
        if not is_direct_to_bot and min_interval > 0:
            last_reply_at = float(self.ai_channel_last_reply_at.get(channel_key, 0.0) or 0.0)
            if now - last_reply_at < min_interval:
                return

        allowed_providers = {
            "openai",
            "ollama",
            "google",
            "opentyphoon",
            "chindax",
            "aiforthai",
            "cloudflare",
            "thaillm",
        }
        requested_provider = str(self.ai_provider or "opentyphoon").strip().lower()
        if requested_provider not in allowed_providers:
            requested_provider = "opentyphoon"
        if hasattr(self.bot, "ownerbot_runtime_ai_provider"):
            try:
                runtime_provider = await self.bot.ownerbot_runtime_ai_provider(fallback=requested_provider)
                runtime_provider_text = str(runtime_provider or "").strip().lower()
                if runtime_provider_text in allowed_providers:
                    requested_provider = runtime_provider_text
            except Exception:
                pass
        effective_ai_model = str(self._provider_default_model(requested_provider) or "").strip()
        runtime_model_fallback = self._provider_default_model(requested_provider)
        if hasattr(self.bot, "ownerbot_runtime_ai_model"):
            try:
                runtime_model = await self.bot.ownerbot_runtime_ai_model(fallback=runtime_model_fallback)
                runtime_model_text = str(runtime_model or "").strip()
                if runtime_model_text:
                    effective_ai_model = runtime_model_text
            except Exception:
                pass

        # Music-safe mode: when music is active and AI is local Ollama, move to configured
        # cloud fallback first to reduce CPU/RAM pressure and avoid playback stutter.
        if requested_provider == "ollama" and self._guild_has_active_music(message.guild):
            rerouted = False
            for candidate in self._fallback_chain_for_provider("ollama"):
                if candidate == "ollama" or not self._provider_is_configured(candidate):
                    continue
                requested_provider = candidate
                effective_ai_model = self._provider_default_model(candidate)
                rerouted = True
                logger.info(
                    f"AI music-safe routing | guild={message.guild.id} | from=ollama | to={candidate}"
                )
                break
            if not rerouted and self.ai_skip_ollama_when_music_active:
                await self._safe_ai_notice(
                    message,
                    description=(
                        "ระบบ AI ถูกพักชั่วคราวระหว่างเล่นเพลง เพื่อลดภาระ VPS และกันเพลงกระตุกครับ "
                        "(พิมพ์ mention บอทอีกครั้งหลังเพลงหยุดเพื่อใช้งานต่อ)"
                    ),
                    embed_color=color.orange,
                    delete_after=10,
                    throttle_key="ai_paused_music_active",
                    throttle_seconds=20,
                )
                return

        quick_reply = None
        if self.ai_quick_reply_enabled:
            quick_reply = self._build_bot_specific_reply(message, content)
        if quick_reply:
            quick_reply = self._normalize_ai_reply_style(
                quick_reply,
                message=message,
                user_content=content,
                source="quick_reply",
            )
            quick_reply = self._inject_ranked_links_into_reply(quick_reply, content)
            self.ai_channel_last_reply_at[channel_key] = now
            self._append_ai_history(message, "user", content)
            self._append_ai_history(message, "assistant", quick_reply)
            await self._safe_ai_reply_smart(message, quick_reply, user_text=content)
            await self._add_ai_references_followup(message, content)
            return

        cooldown_seconds = 8
        max_requests = 3
        if requested_provider == "openai" and now < self.ai_quota_block_until[message.guild.id]:
            if now >= self.ai_quota_notice_until[message.guild.id]:
                self.ai_quota_notice_until[message.guild.id] = now + 300
                await self._safe_ai_notice(
                    message,
                    description="AI chat is temporarily unavailable due to OpenAI quota/billing limits.",
                    embed_color=color.orange,
                    delete_after=15,
                    throttle_key="openai_quota_paused",
                    throttle_seconds=300,
                )
            return

        guild_usage = self.ai_chat_usage[str(message.guild.id)]
        user_usage = [
            timestamp
            for timestamp in guild_usage[message.author.id]
            if now - timestamp < cooldown_seconds
        ]
        guild_usage[message.author.id] = user_usage
        if len(user_usage) >= max_requests:
            return
        guild_usage[message.author.id].append(now)

        if requested_provider == "openai" and not self._ensure_openai_client():
            if message.guild.id not in self.ai_config_warned_guilds:
                self.ai_config_warned_guilds.add(message.guild.id)
                await self._safe_ai_notice(
                    message,
                    description="AI chat is set, but `OPENAI_API_KEY` is missing on the bot host.",
                    embed_color=color.red,
                    delete_after=15,
                    throttle_key="openai_api_key_missing",
                    throttle_seconds=1800,
                )
            return

        if requested_provider == "ollama":
            ollama_base = str(self.ollama_base_url or "").strip().lower()
            ollama_remote = ollama_base.startswith("https://ollama.com")
            if ollama_remote and not self.ollama_api_key:
                if message.guild.id not in self.ai_config_warned_guilds:
                    self.ai_config_warned_guilds.add(message.guild.id)
                    await self._safe_ai_notice(
                        message,
                        description=(
                            "AI chat is set to Ollama Cloud, but `OLLAMA_API_KEY` is missing on the bot host."
                        ),
                        embed_color=color.red,
                        delete_after=15,
                        throttle_key="ollama_api_key_missing",
                        throttle_seconds=1800,
                    )
                return

        if requested_provider == "google" and not self.google_api_key:
            if message.guild.id not in self.ai_config_warned_guilds:
                self.ai_config_warned_guilds.add(message.guild.id)
                await self._safe_ai_notice(
                    message,
                    description="AI chat is set to Google, but `GOOGLE_API_KEY` is missing on the bot host.",
                    embed_color=color.red,
                    delete_after=15,
                    throttle_key="google_api_key_missing",
                    throttle_seconds=1800,
                )
            return

        if requested_provider == "opentyphoon" and not self.opentyphoon_api_key:
            if message.guild.id not in self.ai_config_warned_guilds:
                self.ai_config_warned_guilds.add(message.guild.id)
                await self._safe_ai_notice(
                    message,
                    description="AI chat is set to OpenTyphoon, but `OPENTYPHOON_API_KEY` is missing on the bot host.",
                    embed_color=color.red,
                    delete_after=15,
                    throttle_key="opentyphoon_api_key_missing",
                    throttle_seconds=1800,
                )
            return

        if requested_provider == "chindax" and not self.chindax_api_key:
            if message.guild.id not in self.ai_config_warned_guilds:
                self.ai_config_warned_guilds.add(message.guild.id)
                await self._safe_ai_notice(
                    message,
                    description="AI chat is set to ChindaX, but `CHINDAX_API_KEY` is missing on the bot host.",
                    embed_color=color.red,
                    delete_after=15,
                    throttle_key="chindax_api_key_missing",
                    throttle_seconds=1800,
                )
            return

        if requested_provider == "aiforthai" and not self.aiforthai_api_key:
            if message.guild.id not in self.ai_config_warned_guilds:
                self.ai_config_warned_guilds.add(message.guild.id)
                await self._safe_ai_notice(
                    message,
                    description="AI chat is set to AI FOR THAI, but `AIFORTHAI_API_KEY` is missing on the bot host.",
                    embed_color=color.red,
                    delete_after=15,
                    throttle_key="aiforthai_api_key_missing",
                    throttle_seconds=1800,
                )
            return

        if requested_provider == "cloudflare" and not self.cloudflare_api_key:
            if message.guild.id not in self.ai_config_warned_guilds:
                self.ai_config_warned_guilds.add(message.guild.id)
                await self._safe_ai_notice(
                    message,
                    description="AI chat is set to Cloudflare, but `CLOUDFLARE_API_TOKEN` is missing on the bot host.",
                    embed_color=color.red,
                    delete_after=15,
                    throttle_key="cloudflare_api_key_missing",
                    throttle_seconds=1800,
                )
            return

        if requested_provider == "thaillm" and not self.thaillm_api_key:
            if message.guild.id not in self.ai_config_warned_guilds:
                self.ai_config_warned_guilds.add(message.guild.id)
                await self._safe_ai_notice(
                    message,
                    description="AI chat is set to ThaiLLM, but `THAILLM_API_KEY` is missing on the bot host.",
                    embed_color=color.red,
                    delete_after=15,
                    throttle_key="thaillm_api_key_missing",
                    throttle_seconds=1800,
                )
            return

        generation_lock = self.ai_generation_locks[message.guild.id]
        if generation_lock.locked():
            if is_direct_to_bot:
                await self._safe_ai_notice(
                    message,
                    description="AI กำลังประมวลผลคำถามก่อนหน้าอยู่ครับ ลองส่งใหม่อีกครั้งในอีกครู่",
                    embed_color=color.orange,
                    delete_after=6,
                    throttle_key="ai_busy_generation",
                    throttle_seconds=4,
                )
            return

        try:
            async with self.ai_request_semaphore:
                async with generation_lock:
                    self.ai_channel_last_reply_at[channel_key] = time.time()
                    self._append_ai_history(message, "user", content)
                    if not effective_ai_model:
                        if requested_provider == self.ai_provider:
                            effective_ai_model = await self._effective_ai_model()
                        else:
                            effective_ai_model = self._provider_default_model(requested_provider)
                    if not effective_ai_model:
                        effective_ai_model = self._provider_default_model(requested_provider)

                    async with self._safe_typing(message):
                        system_prompt = await self.build_ai_system_prompt(
                            message,
                            content,
                            ai_model=effective_ai_model,
                            ai_provider=requested_provider,
                        )
                        messages_payload = self._build_ai_messages(message, system_prompt, content)
                        reply_text = await asyncio.wait_for(
                            self.ask_ai_model(
                                content,
                                system_prompt,
                                messages_payload,
                                ai_model=effective_ai_model,
                                provider=requested_provider,
                            ),
                            timeout=float(self.ai_request_timeout_seconds),
                        )
            
            if not reply_text:
                return

            # Process Memory Saving
            user_mem_match = re.search(r"\[SAVE_USER_MEMORY:\s*(.*?)\]", reply_text)
            if user_mem_match:
                new_mem = user_mem_match.group(1).strip()
                if new_mem:
                    existing = await storage.ai_memories.get(target_id=message.author.id, type="user")
                    if existing:
                        await storage.ai_memories.update(id=existing["id"], memory=new_mem, updated_at=time.strftime('%Y-%m-%d %H:%M:%S'))
                    else:
                        await storage.ai_memories.insert(target_id=message.author.id, type="user", memory=new_mem)
                reply_text = re.sub(r"\[SAVE_USER_MEMORY:.*?\]", "", reply_text).strip()

            guild_mem_match = re.search(r"\[SAVE_GUILD_MEMORY:\s*(.*?)\]", reply_text)
            if guild_mem_match:
                new_mem = guild_mem_match.group(1).strip()
                if new_mem:
                    existing = await storage.ai_memories.get(target_id=message.guild.id, type="guild")
                    if existing:
                        await storage.ai_memories.update(id=existing["id"], memory=new_mem, updated_at=time.strftime('%Y-%m-%d %H:%M:%S'))
                    else:
                        await storage.ai_memories.insert(target_id=message.guild.id, type="guild", memory=new_mem)
                reply_text = re.sub(r"\[SAVE_GUILD_MEMORY:.*?\]", "", reply_text).strip()

            reply_text = self._normalize_ai_reply_style(
                reply_text,
                message=message,
                user_content=content,
                source="ai_model",
            )
            reply_text = self._inject_ranked_links_into_reply(reply_text, content)
            self._append_ai_history(message, "assistant", reply_text)
            await self._safe_ai_reply_smart(message, reply_text, user_text=content)
            await self._add_ai_references_followup(message, content)
        except Exception as e:
            error_text_raw = str(e or "").strip()
            error_text = error_text_raw.lower()
            error_kind = type(e).__name__
            quota_exceeded = (
                "insufficient_quota" in error_text
                or "exceeded your current quota" in error_text
            )
            if requested_provider == "openai" and quota_exceeded:
                block_seconds = 1800
                self.ai_quota_block_until[message.guild.id] = time.time() + block_seconds
                self.ai_quota_notice_until[message.guild.id] = time.time() + 300
                await self._safe_ai_notice(
                    message,
                    description="AI chat paused: OpenAI quota is insufficient. Please check billing/credits and try again later.",
                    embed_color=color.red,
                    delete_after=20,
                    throttle_key="openai_quota_exceeded",
                    throttle_seconds=300,
                )
                logger.warning(
                    f"AI chat quota exceeded for guild {message.guild.id}; paused for {block_seconds} seconds."
                )
                return

            if requested_provider == "ollama":
                unauthorized_like = (
                    "ollama api error 401" in error_text
                    or "ollama api error 403" in error_text
                    or ("unauthorized" in error_text and "ollama" in error_text)
                )
                if unauthorized_like:
                    if message.guild.id not in self.ai_config_warned_guilds:
                        self.ai_config_warned_guilds.add(message.guild.id)
                        await self._safe_ai_notice(
                            message,
                            description=(
                                "Ollama API key is invalid/expired or missing. "
                                "Please check `OLLAMA_API_KEY` in `.env`."
                            ),
                            embed_color=color.red,
                            delete_after=20,
                            throttle_key="ollama_api_key_invalid",
                            throttle_seconds=900,
                        )
                    return

                timeout_like = isinstance(e, (asyncio.TimeoutError, TimeoutError)) or (
                    "timeout" in error_text
                )
                if timeout_like:
                    await self._safe_ai_notice(
                        message,
                        description="Skyline AI took too long to respond. Please retry with a shorter prompt.",
                        embed_color=color.orange,
                        delete_after=12,
                        throttle_key="ollama_timeout",
                        throttle_seconds=45,
                    )
                    logger.warning(
                        f"AI ollama timeout in guild {message.guild.id} | model={effective_ai_model} | type={error_kind}"
                    )
                    return

                memory_like = (
                    "requires more system memory" in error_text
                    or "system memory" in error_text and "available" in error_text
                    or "out of memory" in error_text
                )
                if memory_like:
                    is_cloud_host = self._is_ollama_cloud_host()
                    if message.guild.id not in self.ai_config_warned_guilds:
                        self.ai_config_warned_guilds.add(message.guild.id)
                        await self._safe_ai_notice(
                            message,
                            description=(
                                (
                                    "Ollama Cloud returned model-capacity error.\n"
                                    f"Current model: `{effective_ai_model}`\n"
                                    "Please switch to a lighter cloud model in OwnerBOT Runtime "
                                    "(for example `gpt-oss:20b`)."
                                )
                                if is_cloud_host
                                else (
                                    "AI local model is too large for current VPS RAM.\n"
                                    f"Current model: `{effective_ai_model}`\n"
                                    "Use a smaller model and restart the bot, for example:\n"
                                    "`ollama pull qwen2.5:0.5b-instruct`\n"
                                    "Then set `OLLAMA_MODEL=qwen2.5:0.5b-instruct` in `.env`."
                                )
                            ),
                            embed_color=color.orange,
                            delete_after=25,
                            throttle_key="ollama_memory_low",
                            throttle_seconds=1800,
                        )
                    logger.warning(
                        f"AI ollama memory insufficient in guild {message.guild.id} | model={effective_ai_model} | type={error_kind} | error={error_text_raw}"
                    )
                    return

                if message.guild.id not in self.ai_config_warned_guilds:
                    self.ai_config_warned_guilds.add(message.guild.id)
                    is_cloud_host = self._is_ollama_cloud_host()
                    await self._safe_ai_notice(
                        message,
                        description=(
                            (
                                "Ollama Cloud API is unreachable or model is unavailable. "
                                "Please check `OLLAMA_API_KEY`, `OLLAMA_BASE_URL`, and `OLLAMA_MODEL` in `.env`."
                            )
                            if is_cloud_host
                            else (
                                "AI local server is unreachable. Start Ollama first: "
                                "`ollama serve` and pull model with `ollama pull "
                                f"{effective_ai_model}`"
                            )
                        ),
                        embed_color=color.red,
                        delete_after=20,
                        throttle_key="ollama_unreachable",
                        throttle_seconds=1800,
                    )

            if requested_provider == "google":
                quota_like = (
                    "resource_exhausted" in error_text
                    or "quota" in error_text
                    or "rate limit" in error_text
                    or "429" in error_text
                )
                if quota_like:
                    await self._safe_ai_notice(
                        message,
                        description="Google AI rate/quota limit reached. Please try again later.",
                        embed_color=color.orange,
                        delete_after=15,
                        throttle_key="google_quota_exceeded",
                        throttle_seconds=300,
                    )
                    return

                if message.guild.id not in self.ai_config_warned_guilds:
                    self.ai_config_warned_guilds.add(message.guild.id)
                    await self._safe_ai_notice(
                        message,
                        description="Google AI is unreachable or misconfigured. Check `GOOGLE_API_KEY` and `GOOGLE_MODEL`.",
                        embed_color=color.red,
                        delete_after=20,
                        throttle_key="google_unreachable",
                        throttle_seconds=900,
                    )

            if requested_provider in {"opentyphoon", "chindax", "aiforthai", "cloudflare", "thaillm"}:
                if requested_provider == "aiforthai" and self._is_non_grpc_route_error(error_text):
                    await self._safe_ai_notice(
                        message,
                        description=(
                            "AI FOR THAI endpoint ตอบกลับแบบ gRPC (HTTP 415) ระบบสลับเส้นทางให้อัตโนมัติแล้ว "
                            "หากยังไม่สำเร็จ แนะนำตั้งค่า `AIFORTHAI_ALT_BASE_URL` ใน `.env` "
                            "เช่น `https://aiforthai.in.th/api/v1/provider`"
                        ),
                        embed_color=color.orange,
                        delete_after=18,
                        throttle_key="aiforthai_non_grpc_route",
                        throttle_seconds=180,
                    )
                    return

                if requested_provider == "thaillm" and self._is_http_status_like_error(error_text, (404, 405)):
                    await self._safe_ai_notice(
                        message,
                        description=(
                            "ThaiLLM endpoint ไม่รองรับเส้นทางเดิม ระบบพยายามสลับ endpoint อัตโนมัติแล้ว "
                            "แนะนำตรวจ `.env`: `THAILLM_BASE_URL` และ `THAILLM_CHAT_COMPLETIONS_PATH`"
                        ),
                        embed_color=color.orange,
                        delete_after=18,
                        throttle_key="thaillm_endpoint_mismatch",
                        throttle_seconds=180,
                    )
                    return

                if requested_provider == "chindax" and self._is_http_status_like_error(error_text, (404, 405)):
                    await self._safe_ai_notice(
                        message,
                        description=(
                            "ChindaX endpoint ไม่รองรับเส้นทางเดิม ระบบพยายามสลับ endpoint อัตโนมัติแล้ว "
                            "แนะนำตรวจ `.env`: `CHINDAX_BASE_URL=https://chindax.iapp.co.th/api` "
                            "และตั้ง `CHINDAX_MODEL` เป็นรุ่นที่มีใน `/api/models`"
                        ),
                        embed_color=color.orange,
                        delete_after=18,
                        throttle_key="chindax_endpoint_mismatch",
                        throttle_seconds=180,
                    )
                    return

                if requested_provider == "cloudflare" and self._is_http_status_like_error(error_text, (401, 403)):
                    await self._safe_ai_notice(
                        message,
                        description=(
                            "Cloudflare authentication failed. ตรวจ `CLOUDFLARE_API_TOKEN` "
                            "และสิทธิ์ token สำหรับ Workers AI/OpenAI-compatible endpoint."
                        ),
                        embed_color=color.orange,
                        delete_after=18,
                        throttle_key="cloudflare_auth_failed",
                        throttle_seconds=180,
                    )
                    return

                quota_like = (
                    "resource_exhausted" in error_text
                    or "insufficient_quota" in error_text
                    or "quota" in error_text
                    or "rate limit" in error_text
                    or "429" in error_text
                )
                if quota_like:
                    await self._safe_ai_notice(
                        message,
                        description=(
                            f"{requested_provider} rate/quota limit reached. "
                            "Please check billing/limits and try again later."
                        ),
                        embed_color=color.orange,
                        delete_after=15,
                        throttle_key=f"{requested_provider}_quota_exceeded",
                        throttle_seconds=300,
                    )
                    return

                if message.guild.id not in self.ai_config_warned_guilds:
                    self.ai_config_warned_guilds.add(message.guild.id)
                    await self._safe_ai_notice(
                        message,
                        description=(
                            f"{requested_provider} API is unreachable or misconfigured. "
                            "Please verify API key, base URL, and model in `.env`."
                        ),
                        embed_color=color.red,
                        delete_after=20,
                        throttle_key=f"{requested_provider}_unreachable",
                        throttle_seconds=900,
                    )

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: "
                f"{error_kind}: {error_text_raw or repr(e)} | provider={requested_provider} | model={effective_ai_model}"
            )

    async def antispam_punishment(
        self, message: discord.Message, data: dict, delete_limit: int = 5
    ):

        try:

            PUNISHMENT = data.get("antispam_punishment", "warn")

            PUNISHMENT_DURATION = data.get("antispam_punishment_duration", 0)

            try:

                asyncio.create_task(
                    message.channel.purge(
                        limit=delete_limit, check=lambda m: m.author == message.author
                    )
                )

            except Exception:
                pass

            if PUNISHMENT == "warn":

                await message.reply(
                    embed=discord.Embed(
                        description=f"**{message.author} has been warned for spamming**",
                        color=color.red,
                    )
                )

            elif PUNISHMENT == "mute":

                await message.channel.send(
                    embed=discord.Embed(
                        description=f"**{message.author} has been muted for spamming**",
                        color=color.red,
                    )
                )

                # timed_out_until must be an aware datetime. Consider using discord.utils.utcnow() or datetime.datetime.now().astimezone() for local time.

                await message.author.edit(
                    timed_out_until=datetime.datetime.now().astimezone()
                    + datetime.timedelta(seconds=PUNISHMENT_DURATION)
                )

            elif PUNISHMENT == "kick":

                await message.channel.send(
                    embed=discord.Embed(
                        description=f"**{message.author} has been kicked for spamming**",
                        color=color.red,
                    )
                )

                await message.author.kick(reason="Spamming")

            elif PUNISHMENT == "ban":

                await message.channel.send(
                    embed=discord.Embed(
                        description=f"**{message.author} has been banned for spamming**",
                        color=color.red,
                    )
                )

                await message.author.ban(reason="Spamming")

            elif PUNISHMENT == "tempban":

                await message.channel.send(
                    embed=discord.Embed(
                        description=f"**{message.author} has been banned for spamming**",
                        color=color.red,
                    )
                )

                await message.author.ban(
                    reason="Spamming", delete_message_days=PUNISHMENT_DURATION
                )

            return True

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            return False

    async def antiduplicate_module(self, message: discord.Message, data: dict):

        logger.debug("Checking for duplicate messages")

        try:

            MESSAGE_THRESHOLD = data.get("antispam_max_messages", 5)

            CLEANUP_INTERVAL = data.get("antispam_max_interval", 10)

            def check_message(user_id, message_content):

                current_time = time.time()

                # Cleanup old messages

                if (
                    current_time - self.user_last_message_time[user_id]
                    > CLEANUP_INTERVAL
                ):

                    self.user_messages[user_id] = defaultdict(int)

                    self.user_last_message_time[user_id] = current_time

                # Update message count

                self.user_messages[user_id][message_content] += 1

                # Check for spam

                if self.user_messages[user_id][message_content] >= MESSAGE_THRESHOLD:

                    return True  # Spam detected

                return False  # No spam

            if check_message(message.author.id, message.content):

                if await self.antispam_punishment(
                    message, data, delete_limit=MESSAGE_THRESHOLD
                ):

                    return True

                return True

            return False

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            return False

    async def antispam_module(self, message: discord.Message, data: dict):

        logger.debug("Checking for spam messages")

        try:

            MESSAGE_THRESHOLD = data.get("antispam_max_messages", 5)

            CLEANUP_INTERVAL = data.get("antispam_max_interval", 10)

            user_id = message.author.id

            current_time = time.time()

            # Initialize or reset user message count if the interval has passed

            if current_time - self.user_message_timestamps[user_id] > CLEANUP_INTERVAL:

                self.user_message_counts[user_id] = 0

                self.user_message_timestamps[user_id] = current_time

            # Increment message count for the user

            self.user_message_counts[user_id] += 1

            # Check for spam

            if self.user_message_counts[user_id] >= MESSAGE_THRESHOLD:

                if await self.antispam_punishment(
                    message, data, delete_limit=MESSAGE_THRESHOLD
                ):

                    return True

                return True

            return False

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            return False

    async def anti_mass_mentions(self, message: discord.Message, data: dict):

        logger.debug("Checking for mass mentions")

        try:

            MENTION_THRESHOLD = data.get("antispam_max_mentions", 5)

            if len(message.mentions) + len(message.role_mentions) >= MENTION_THRESHOLD:

                if await self.antispam_punishment(message, data, delete_limit=1):

                    return True

                return True

            return False

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            return False

    async def anti_mass_emojis(self, message: discord.Message, data: dict):

        logger.debug("Checking for mass emojis")

        try:

            EMOJI_THRESHOLD = data.get("antispam_max_emojis", 5)

            emoji_count = len(re.findall(r"<a?:\w+:\d+>", message.content))

            if emoji_count >= EMOJI_THRESHOLD:

                if await self.antispam_punishment(message, data, delete_limit=1):

                    return True

                return True

            return False

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            return False

    async def anti_mass_caps(self, message: discord.Message, data: dict):

        logger.debug("Checking for mass caps")

        try:

            CAPS_THRESHOLD = data.get(
                "antispam_max_caps", 50
            )  # percentage of uppercase letters

            def uppercase_percentage(message: str) -> float:

                total_chars = len(message)

                if total_chars == 0:

                    return 0

                uppercase_chars = sum(1 for c in message if c.isupper())

                return (uppercase_chars / total_chars) * 100

            # check if many CAPITAL letters in same word

            if len(message.content) >= 8:

                if uppercase_percentage(message.content) >= CAPS_THRESHOLD:

                    if await self.antispam_punishment(message, data, delete_limit=1):

                        return True

                    return True

            return False

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            return False

    async def check_automod(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        try:

            if message.author == self.bot.user:
                return

            guild_cache = cache.automod.get(str(message.guild.id), {})

            if not guild_cache:

                return

            if not guild_cache.get("antispam_enabled", False):
                return

            if await checks.check_is_owner_raw(message.author, message.guild):
                return

            if message.author.guild_permissions.administrator:
                return

            if message.author.guild_permissions.manage_messages:
                return

            if message.author.guild_permissions.manage_guild:
                return

            if message.author.guild_permissions.manage_roles:
                return

            if message.author.guild_permissions.manage_channels:
                return

            def _normalize_whitelist_ids(raw_value: Any) -> set[int]:
                values: Any = raw_value
                if isinstance(values, str):
                    text = values.strip()
                    if not text:
                        return set()
                    try:
                        values = json.loads(text)
                    except Exception:
                        values = re.split(r"[\s,\n\r]+", text)
                if not isinstance(values, (list, tuple, set)):
                    return set()
                normalized: set[int] = set()
                for item in values:
                    try:
                        normalized.add(int(str(item).strip()))
                    except Exception:
                        continue
                return normalized

            whitelist_roles = _normalize_whitelist_ids(
                guild_cache.get("antispam_whitelist_roles", [])
            )
            whitelist_channels = _normalize_whitelist_ids(
                guild_cache.get("antispam_whitelist_channels", [])
            )

            if message.channel.id in whitelist_channels:
                return

            if any(role.id in whitelist_roles for role in message.author.roles):
                return

            if await self.antiduplicate_module(message, guild_cache):

                return logger.info("Detected spam message, deleted and warned user")

            elif await self.antispam_module(message, guild_cache):

                return logger.info("Detected spam message, deleted and warned user")

            elif await self.anti_mass_mentions(message, guild_cache):

                return logger.info("Detected mass mentions, deleted and warned user")

            elif await self.anti_mass_emojis(message, guild_cache):

                return logger.info("Detected mass emojis, deleted and warned user")

            elif await self.anti_mass_caps(message, guild_cache):

                return logger.info("Detected mass caps, deleted and warned user")

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    role_command_usage = {}

    async def custom_role_command(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        try:

            custom_roles_cache = cache.custom_roles.get(str(message.guild.id), {})

            custom_roles_permissions_cache = cache.custom_roles_permissions.get(
                str(message.guild.id), {}
            )

            if not custom_roles_cache:

                return

            content_tokens = str(message.content or "").strip().split()
            if not content_tokens:

                return

            command_name = content_tokens[0].lower()

            # if first word of content in custom_roles_cache

            if not custom_roles_cache.get(command_name):

                return

            # example of custom_roles_command: vip @user or id

            target_member_id: int | None = None
            if message.mentions:
                target_member_id = int(message.mentions[0].id)
            elif len(content_tokens) > 1:
                target_raw = (
                    content_tokens[1]
                    .replace("<@", "")
                    .replace(">", "")
                    .replace("!", "")
                    .strip()
                )
                if target_raw.isdigit():
                    target_member_id = int(target_raw)

            if not target_member_id:

                return await message.reply(
                    embed=discord.Embed(
                        description=f"**Usage:** `{command_name} @member` or `{command_name} member_id`",
                        color=color.red,
                    ),
                    delete_after=10,
                )

            member = (
                await message.guild.fetch_member(target_member_id)
                if target_member_id
                else None
            )

            if not member:

                return logger.error(f"Member not found for custom role command")

            if not await checks.check_is_owner_raw(member, message.guild):

                if not custom_roles_permissions_cache:

                    return logger.warning(
                        f"Custom roles permissions not found for guild {message.guild.id}"
                    )

                if not any(
                    role.id == custom_roles_permissions_cache.get("required_role_id")
                    for role in message.author.roles
                ):

                    return logger.error(
                        f"User does not have required role to use custom role command"
                    )

            guilds_subscription = cache.guilds.get(str(message.guild.id), {}).get(
                "subscription", "free"
            )

            if guilds_subscription == "free":

                customrole_limit = 5

            elif guilds_subscription == "silver_guild_preminum":

                customrole_limit = 10

            elif guilds_subscription == "golden_guild_premium":

                customrole_limit = 15

            elif guilds_subscription in {"diamond_guild_premium", "permanent_guild_premium", "lifetime_guild_premium"}:

                customrole_limit = 20

            else:

                customrole_limit = 5

            if len(custom_roles_cache) > customrole_limit:

                return await message.reply(
                    embed=discord.Embed(
                        description=f"**Your guild has reached the limit of {customrole_limit} custom roles\nYou need to delete {len(custom_roles_cache) - customrole_limit} custom roles to use this command**",
                        color=color.red,
                    ),
                    delete_after=10,
                )

            # Get the user ID

            user_id = message.author.id

            current_time = time.time()

            # Initialize usage data for the user if not present

            if user_id not in self.role_command_usage:

                self.role_command_usage[user_id] = []

            cooldown = 10

            # Filter out timestamps older than 60 seconds

            self.role_command_usage[user_id] = [
                timestamp
                for timestamp in self.role_command_usage[user_id]
                if current_time - timestamp < cooldown
            ]

            # Check if the user has already used the command twice in the last 60 seconds

            if len(self.role_command_usage[user_id]) >= 2:

                # calculate retry time

                retry_after = cooldown - (
                    current_time - self.role_command_usage[user_id][0]
                )

                return await message.reply(
                    embed=discord.Embed(
                        description=f"**You are on cooldown for using the custom role command. Please try again <t:{int(current_time + retry_after)}:R>**",
                        color=color.red,
                    ),
                    delete_after=retry_after,
                )

            # Add the current usage timestamp

            self.role_command_usage[user_id].append(current_time)

            custom_role_data = custom_roles_cache.get(command_name)

            role = message.guild.get_role(custom_role_data.get("role_id"))

            if not role:

                return logger.error(
                    f"Role with id {custom_role_data.get('role_id')} not found for custom role {custom_role_data.get('name')}"
                )

            if role.permissions.administrator:

                return await message.reply(
                    embed=discord.Embed(
                        description=f"Role {role.mention} has administrator permissions and cannot be added as a custom role",
                        color=color.red,
                    )
                )

            if role in member.roles:

                await member.remove_roles(role)

                await message.reply(
                    embed=discord.Embed(
                        description=f"**Role {role.mention} has been removed from {member.mention}**",
                        color=color.red,
                    )
                )

            else:

                await member.add_roles(role)

                await message.reply(
                    embed=discord.Embed(
                        description=f"**Role {role.mention} has been added to {member.mention}**",
                        color=color.green,
                    )
                )

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    async def check_media_channel(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        try:

            if message.author == self.bot.user:

                return

            if message.author.bot:

                return

            if message.author.guild_permissions.administrator:

                return

            if message.author.guild_permissions.manage_guild:

                return

            if await checks.check_is_owner_raw(message.author, message.guild):

                return

            media_channels_cache = cache.media_channels.get(str(message.guild.id), {})

            if not media_channels_cache:

                return

            if str(message.channel.id) in media_channels_cache:

                if message.attachments:

                    return

                if message.embeds:

                    return

                await message.delete()

                await message.channel.send(
                    embed=discord.Embed(
                        description=f"**You can only send images, videos or embeds in this channel**",
                        color=color.red,
                    ),
                    delete_after=5,
                )

                return logger.info(
                    f"Deleted message from {message.author} in media channel"
                )

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    auto_responder_usage = {}

    async def auto_responder(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        try:

            if message.author == self.bot.user:

                return

            ai_data = cache.ai_chat_channels.get(str(message.guild.id), {})
            ai_channel_id = ai_data.get("channel_id")
            try:
                ai_channel_id = int(ai_channel_id) if ai_channel_id else None
            except (TypeError, ValueError):
                ai_channel_id = None
            if ai_channel_id and int(message.channel.id) == int(ai_channel_id):
                # Keep AI channel focused on model replies, not exact-match auto responses.
                return

            cooldown = 10

            user_id = message.author.id

            current_time = time.time()

            if user_id not in self.auto_responder_usage:

                self.auto_responder_usage[user_id] = []

            self.auto_responder_usage[user_id] = [
                timestamp
                for timestamp in self.auto_responder_usage[user_id]
                if current_time - timestamp < cooldown
            ]

            if len(self.auto_responder_usage[user_id]) >= 2:

                retry_after = cooldown - (
                    current_time - self.auto_responder_usage[user_id][0]
                )

                return

            self.auto_responder_usage[user_id].append(current_time)

            auto_responder_cache = cache.auto_responder.get(str(message.guild.id), {})

            if not auto_responder_cache:

                return

            response_data = auto_responder_cache.get(message.content.lower(), None)

            if not response_data:

                return

            # if response_data.get('delete_original',False):

            #     await message.delete()

            try:

                await message.reply(
                    response_data.get("response", "No Response Content")
                )

            except Exception:
                pass

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    async def anti_channel_create_module(self, channel: discord.abc.GuildChannel):

        try:

            anti_nuke_cache = self.bot.cache.antinuke_settings.get(
                str(channel.guild.id)
            )

            if not anti_nuke_cache:

                return

            if not anti_nuke_cache.get("enabled"):

                return

            if not anti_nuke_cache.get("anti_channel_create"):

                return

            async def check_entry():

                async for entry in channel.guild.audit_logs(
                    limit=1, action=discord.AuditLogAction.channel_create
                ):

                    if entry.target.id == channel.id:

                        return entry

            entry = await check_entry()

            if entry:

                creator = entry.user

                if creator == self.bot.user:

                    return logger.warning(
                        f"Channel {channel.name} was created by the bot in {channel.guild.name}"
                    )

            else:

                return logger.warning(
                    f"Channel {channel.name} was created by the bot in {channel.guild.name}"
                )

            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(
                str(channel.guild.id), {}
            ).get(str(creator.id), {})

            if anti_nuke_bypass_cache:

                if anti_nuke_bypass_cache.get("anti_channel_create"):

                    return logger.warning(
                        f"User {creator} is bypassed from anti channel create in {channel.guild.name}"
                    )

            if creator.top_role.position >= channel.guild.me.top_role.position:

                return logger.warning(
                    f"User {creator} has higher or equal role than the bot in {channel.guild.name}"
                )

            if await checks.check_is_owner_raw(creator, channel.guild):

                return logger.warning(
                    f"User {creator} is the owner of the guild in {channel.guild.name}"
                )

            if str(channel.guild.id) not in self.create_channel_timeouts:

                self.create_channel_timeouts[str(channel.guild.id)] = {}

            if str(creator.id) not in self.create_channel_timeouts.get(
                str(channel.guild.id)
            ):

                self.create_channel_timeouts[str(channel.guild.id)][str(creator.id)] = {
                    "count": 0,
                    "created_at": datetime.datetime.now(),
                }

            self.create_channel_timeouts[str(channel.guild.id)][str(creator.id)][
                "count"
            ] += 1

            self.create_channel_timeouts[str(channel.guild.id)][str(creator.id)][
                "created_at"
            ] = datetime.datetime.now()

            if str(channel.guild.id) in self.create_channel_timeouts:

                if self.create_channel_timeouts.get(str(channel.guild.id)):

                    if self.create_channel_timeouts.get(str(channel.guild.id), {}).get(
                        str(creator.id)
                    ):

                        if self.create_channel_timeouts.get(
                            str(channel.guild.id), {}
                        ).get(str(creator.id), {}).get("count") >= anti_nuke_cache.get(
                            "anti_channel_create_limit", 1
                        ) and self.create_channel_timeouts.get(
                            str(channel.guild.id), {}
                        ).get(
                            str(creator.id), {}
                        ).get(
                            "created_at"
                        ) >= (
                            datetime.datetime.now() - datetime.timedelta(seconds=60)
                        ):

                            # getting action for the user

                            action = anti_nuke_cache.get(
                                "anti_channel_create_punishment"
                            )

                            async def send_notify_to_user(
                                user: discord.Member, embed: discord.Embed
                            ):

                                try:

                                    await user.send(embed=embed)

                                except Exception:
                                    logger.warning(
                                        f"Could not send message to {user} in {channel.guild.name}"
                                    )

                            if action == "ban":

                                try:

                                    embed = discord.Embed(
                                        title="You have been banned",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Channel Create\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(
                                        url=(
                                            channel.guild.icon.url
                                            if channel.guild.icon
                                            else None
                                        )
                                    )

                                    asyncio.create_task(
                                        send_notify_to_user(creator, embed)
                                    )

                                except Exception:
                                    pass

                                try:

                                    embed = discord.Embed(
                                        title="User Banned",
                                        description=f"**__User__**: {creator.mention}\n**__ID__**: `{creator.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Channel Create\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(url=creator.display_avatar.url)

                                    await channel.guild.ban(
                                        creator,
                                        reason="Banned by Antinuke System: Anti Channel Create",
                                    )

                                    await self.bot.antinuke_log.send(
                                        guild=channel.guild,
                                        embed=embed,
                                        type="antinuke",
                                    )

                                except Exception as e:

                                    logger.error(
                                        f"Error in on_guild_channel_create.anti_channel_create_module: {e}"
                                    )

                            elif action == "kick":

                                try:

                                    embed = discord.Embed(
                                        title="You have been kicked",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Channel Create\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(
                                        url=(
                                            channel.guild.icon.url
                                            if channel.guild.icon
                                            else None
                                        )
                                    )

                                    asyncio.create_task(
                                        send_notify_to_user(creator, embed)
                                    )

                                except Exception:
                                    pass

                                try:

                                    embed = discord.Embed(
                                        title="User Kicked",
                                        description=f"**__User__**: {creator.mention}\n**__ID__**: `{creator.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Channel Create\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(url=creator.display_avatar.url)

                                    await channel.guild.kick(
                                        creator,
                                        reason="Kicked by Antinuke System: Anti Channel Create",
                                    )

                                    await self.bot.antinuke_log.send(
                                        guild=channel.guild,
                                        embed=embed,
                                        type="antinuke",
                                    )

                                except Exception as e:

                                    logger.error(
                                        f"Error in on_guild_channel_create.anti_channel_create_module: {e}"
                                    )

                            elif action == "warn":

                                try:

                                    embed = discord.Embed(
                                        title="You have been warned",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Channel Create\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(
                                        url=(
                                            channel.guild.icon.url
                                            if channel.guild.icon
                                            else None
                                        )
                                    )

                                    asyncio.create_task(
                                        send_notify_to_user(creator, embed)
                                    )

                                except Exception:
                                    pass

                                try:

                                    embed = discord.Embed(
                                        title="User Warned",
                                        description=f"**__User__**: {creator.mention}\n**__ID__**: `{creator.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Channel Create\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(url=creator.display_avatar.url)

                                    await self.bot.antinuke_log.send(
                                        guild=channel.guild,
                                        embed=embed,
                                        type="antinuke",
                                    )

                                except Exception as e:

                                    logger.error(
                                        f"Error in on_guild_channel_create.anti_channel_create_module: {e}"
                                    )

                            elif action == "mute":

                                try:

                                    embed = discord.Embed(
                                        title="You have been muted",
                                        description=f"**__Guild:__ `{channel.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Channel Create\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(
                                        url=(
                                            channel.guild.icon.url
                                            if channel.guild.icon
                                            else None
                                        )
                                    )

                                    asyncio.create_task(
                                        send_notify_to_user(creator, embed)
                                    )

                                except Exception:
                                    pass

                                try:

                                    embed = discord.Embed(
                                        title="User Muted",
                                        description=f"**__User__**: {creator.mention}\n**__ID__**: `{creator.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Channel Create\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red,
                                    )

                                    embed.set_footer(
                                        text=f"Antinuke System",
                                        icon_url=self.bot.user.display_avatar.url,
                                    )

                                    embed.set_thumbnail(url=creator.display_avatar.url)

                                    try:

                                        # remove all roles from the user

                                        await creator.edit(
                                            roles=[],
                                            reason="Muted by Antinuke System: Anti Channel Create",
                                        )

                                    except Exception as e:

                                        logger.error(
                                            f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                                        )

                                    await creator.timeout(
                                        datetime.timedelta(days=1),
                                        reason="Muted by Antinuke System: Anti Channel Create",
                                    )

                                    await self.bot.antinuke_log.send(
                                        guild=channel.guild,
                                        embed=embed,
                                        type="antinuke",
                                    )

                                except Exception as e:

                                    logger.error(
                                        f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                                    )

                            else:

                                return logger.warning(
                                    f"การดำเนินการไม่ถูกต้อง {action} in {channel.guild.name}"
                                )

                            if action != "warn":

                                # reset the timeout

                                if (
                                    str(channel.guild.id)
                                    in self.create_channel_timeouts
                                ):

                                    if str(
                                        creator.id
                                    ) in self.create_channel_timeouts.get(
                                        str(channel.guild.id)
                                    ):

                                        self.create_channel_timeouts[
                                            str(channel.guild.id)
                                        ][str(creator.id)] = {
                                            "count": 0,
                                            "created_at": datetime.datetime.now(),
                                        }

                            return

        except Exception as e:

            logger.error(
                f"Error in on_guild_channel_create.anti_channel_create_module: {e}"
            )

    anti_channel_delete_timeouts = {}

    async def anti_everyone_mention_module(self, message: discord.Message):

        if message.author.bot:

            return

        if not message.guild:

            return

        try:

            anti_nuke_cache = self.bot.cache.antinuke_settings.get(
                str(message.guild.id)
            )

            if not anti_nuke_cache:

                return

            if not anti_nuke_cache.get("enabled"):

                return

            if not anti_nuke_cache.get("anti_everyone_mention"):
                return

            if "@everyone" in message.content or "@here" in message.content:

                if message.author == self.bot.user:

                    return

                anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(
                    str(message.guild.id), {}
                ).get(str(message.author.id), {})

                if anti_nuke_bypass_cache:

                    if anti_nuke_bypass_cache.get("anti_everyone_mention"):
                        return

                if (
                    message.author.top_role.position
                    >= message.guild.me.top_role.position
                ):
                    return

                if await checks.check_is_owner_raw(message.author, message.guild):
                    return

                if str(message.guild.id) not in self.anti_channel_delete_timeouts:

                    self.anti_channel_delete_timeouts[str(message.guild.id)] = {}

                if str(message.author.id) not in self.anti_channel_delete_timeouts.get(
                    str(message.guild.id)
                ):

                    self.anti_channel_delete_timeouts[str(message.guild.id)][
                        str(message.author.id)
                    ] = {"count": 0, "created_at": datetime.datetime.now()}

                self.anti_channel_delete_timeouts[str(message.guild.id)][
                    str(message.author.id)
                ]["count"] += 1

                self.anti_channel_delete_timeouts[str(message.guild.id)][
                    str(message.author.id)
                ]["created_at"] = datetime.datetime.now()

                if str(message.guild.id) in self.anti_channel_delete_timeouts:

                    if self.anti_channel_delete_timeouts.get(str(message.guild.id)):

                        if self.anti_channel_delete_timeouts.get(
                            str(message.guild.id), {}
                        ).get(str(message.author.id)):

                            if self.anti_channel_delete_timeouts.get(
                                str(message.guild.id), {}
                            ).get(str(message.author.id), {}).get(
                                "count"
                            ) >= anti_nuke_cache.get(
                                "anti_everyone_mention_limit", 1
                            ) and self.anti_channel_delete_timeouts.get(
                                str(message.guild.id), {}
                            ).get(
                                str(message.author.id), {}
                            ).get(
                                "created_at"
                            ) >= (
                                datetime.datetime.now() - datetime.timedelta(seconds=60)
                            ):

                                # getting action for the user

                                action = anti_nuke_cache.get(
                                    "anti_everyone_mention_punishment"
                                )

                                async def send_notify_to_user(
                                    user: discord.Member, embed: discord.Embed
                                ):

                                    try:

                                        await user.send(embed=embed)

                                    except Exception:
                                        logger.warning(
                                            f"Could not send message to {user} in {message.guild.name}"
                                        )

                                await message.delete()

                                if action == "ban":

                                    try:

                                        embed = discord.Embed(
                                            title="You have been banned",
                                            description=f"**__Guild:__ `{message.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Everyone Mention\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=(
                                                message.guild.icon.url
                                                if message.guild.icon
                                                else None
                                            )
                                        )

                                        asyncio.create_task(
                                            send_notify_to_user(message.author, embed)
                                        )

                                    except Exception:
                                        pass

                                    try:

                                        embed = discord.Embed(
                                            title="User Banned",
                                            description=f"**__User__**: {message.author.mention}\n**__ID__**: `{message.author.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Everyone Mention\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=message.author.display_avatar.url
                                        )

                                        await message.guild.ban(
                                            message.author,
                                            reason="Banned by Antinuke System: Anti Everyone Mention",
                                        )

                                        await self.bot.antinuke_log.send(
                                            guild=message.guild,
                                            embed=embed,
                                            type="antinuke",
                                        )

                                    except Exception as e:

                                        logger.error(
                                            f"Error in on_message.anti_everyone_mention_module: {e}"
                                        )

                                elif action == "kick":

                                    try:

                                        embed = discord.Embed(
                                            title="You have been kicked",
                                            description=f"**__Guild:__ `{message.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Everyone Mention\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=(
                                                message.guild.icon.url
                                                if message.guild.icon
                                                else None
                                            )
                                        )

                                        asyncio.create_task(
                                            send_notify_to_user(message.author, embed)
                                        )

                                    except Exception:
                                        pass

                                    try:

                                        embed = discord.Embed(
                                            title="User Kicked",
                                            description=f"**__User__**: {message.author.mention}\n**__ID__**: `{message.author.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Everyone Mention\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=message.author.display_avatar.url
                                        )

                                        await message.guild.kick(
                                            message.author,
                                            reason="Kicked by Antinuke System: Anti Everyone Mention",
                                        )

                                        await self.bot.antinuke_log.send(
                                            guild=message.guild,
                                            embed=embed,
                                            type="antinuke",
                                        )

                                    except Exception as e:

                                        logger.error(
                                            f"Error in on_message.anti_everyone_mention_module: {e}"
                                        )

                                elif action == "warn":

                                    try:

                                        embed = discord.Embed(
                                            title="You have been warned",
                                            description=f"**__Guild:__ `{message.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Everyone Mention\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=(
                                                message.guild.icon.url
                                                if message.guild.icon
                                                else None
                                            )
                                        )

                                        asyncio.create_task(
                                            send_notify_to_user(message.author, embed)
                                        )

                                    except Exception:
                                        pass

                                    try:

                                        embed = discord.Embed(
                                            title="User Warned",
                                            description=f"**__User__**: {message.author.mention}\n**__ID__**: `{message.author.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Everyone Mention\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=message.author.display_avatar.url
                                        )

                                        await self.bot.antinuke_log.send(
                                            guild=message.guild,
                                            embed=embed,
                                            type="antinuke",
                                        )

                                    except Exception as e:

                                        logger.error(
                                            f"Error in on_message.anti_everyone_mention_module: {e}"
                                        )

                                elif action == "mute":

                                    try:

                                        embed = discord.Embed(
                                            title="You have been muted",
                                            description=f"**__Guild:__ `{message.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Everyone Mention\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=(
                                                message.guild.icon.url
                                                if message.guild.icon
                                                else None
                                            )
                                        )

                                        asyncio.create_task(
                                            send_notify_to_user(message.author, embed)
                                        )

                                    except Exception:
                                        pass

                                    try:

                                        embed = discord.Embed(
                                            title="User Muted",
                                            description=f"**__User__**: {message.author.mention}\n**__ID__**: `{message.author.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Everyone Mention\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                            color=color.red,
                                        )

                                        embed.set_footer(
                                            text=f"Antinuke System",
                                            icon_url=self.bot.user.display_avatar.url,
                                        )

                                        embed.set_thumbnail(
                                            url=message.author.display_avatar.url
                                        )

                                        has_adminstrator = (
                                            message.author.guild_permissions.administrator
                                        )

                                        try:

                                            # remove all roles from the user

                                            await message.author.edit(
                                                roles=[],
                                                reason="Muted by Antinuke System: Anti Everyone Mention",
                                            )

                                        except Exception as e:

                                            logger.error(
                                                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                                            )

                                        mute_time = (
                                            datetime.timedelta(days=1)
                                            if has_adminstrator
                                            else datetime.timedelta(minutes=5)
                                        )

                                        await message.author.timeout(
                                            mute_time,
                                            reason="Muted by Antinuke System: Anti Everyone Mention",
                                        )

                                        await self.bot.antinuke_log.send(
                                            guild=message.guild,
                                            embed=embed,
                                            type="antinuke",
                                        )

                                    except Exception as e:

                                        logger.error(
                                            f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                                        )

                                else:

                                    logger.warning(
                                        f"การดำเนินการไม่ถูกต้อง {action} in {message.guild.name}"
                                    )

                                    return

                                if action != "warn":

                                    # reset the timeout

                                    if (
                                        str(message.guild.id)
                                        in self.anti_channel_delete_timeouts
                                    ):

                                        if str(
                                            message.author.id
                                        ) in self.anti_channel_delete_timeouts.get(
                                            str(message.guild.id)
                                        ):

                                            self.anti_channel_delete_timeouts[
                                                str(message.guild.id)
                                            ][str(message.author.id)] = {
                                                "count": 0,
                                                "created_at": datetime.datetime.now(),
                                            }

                                return True

        except Exception as e:

            logger.error(f"Error in on_message.anti_everyone_mention_module: {e}")

    async def check_for_owner_first_time_message_in_guild(
        self, message: discord.Message
    ):

        if message.author.bot:

            return

        if not message.guild:

            return

        global check_for_owner_first_time_message_in_guild_cache

        try:

            if message.author.id in self.bot.cache.owners:

                if (
                    message.guild.id
                    not in check_for_owner_first_time_message_in_guild_cache
                ):

                    check_for_owner_first_time_message_in_guild_cache[
                        message.guild.id
                    ] = []

                if (
                    message.author.id
                    not in check_for_owner_first_time_message_in_guild_cache.get(
                        message.guild.id, []
                    )
                ):

                    check_for_owner_first_time_message_in_guild_cache[
                        message.guild.id
                    ].append(message.author.id)

                    await message.reply(
                        content=f"**Hello Boss!**\n**Welcome to {message.guild.name}**",
                        delete_after=30,
                    )

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if not message.guild:
            if bool(getattr(message, "_support_dm_handled", False)):
                return
            if message.author and message.author.bot:
                return
            try:
                setattr(message, "_support_dm_handled", True)
            except Exception:
                pass
            try:
                enterprise_ops = self.bot.get_cog("EnterpriseOps")
                if enterprise_ops is not None:
                    try:
                        if await enterprise_ops._relay_dm_support_message(message):
                            return
                    except Exception as relay_error:
                        logger.error(
                            f"Support DM relay fallback failed for user {getattr(message.author, 'id', 0)}: {relay_error}"
                        )
                    try:
                        prompted = await enterprise_ops._prompt_dm_support_confirmation(message)
                    except Exception as prompt_error:
                        logger.error(
                            f"Support DM prompt fallback failed for user {getattr(message.author, 'id', 0)}: {prompt_error}"
                        )
                        prompted = False
                    if not prompted and hasattr(message.channel, "send"):
                        try:
                            await message.channel.send(
                                "Support system is temporarily unavailable. Please try again in a moment."
                            )
                        except Exception:
                            pass
                elif hasattr(message.channel, "send"):
                    try:
                        await message.channel.send(
                            "Support system is temporarily unavailable. Please try again in a moment."
                        )
                    except Exception:
                        pass
            except Exception:
                pass

            return

        if message.author and message.author.bot:
            # Keep music setup channel clean even for bot-authored messages.
            # This needs to run before the global bot-message early return.
            try:
                await self.music_channel_module(message)
            except Exception:
                pass

            if self.bot.user and int(message.author.id) == int(self.bot.user.id):
                return
            try:
                honeypot_detected = await self.check_honeypot(message)
                if honeypot_detected:
                    return logger.info("Honeypot detected and handled")
            except Exception:
                pass

            return

        try:

            asyncio.create_task(dashboard_activity.record_message(message.guild.id))

        except Exception:

            pass

        try:

            antinuke_detection = await self.anti_everyone_mention_module(message)

            if antinuke_detection:

                return logger.info("Antinuke detected")

        except Exception:
            pass

        try:

            await self.check_for_afk(message)

        except Exception:
            pass

        try:

            automod_detected = await self.check_automod(message)

            if automod_detected:

                return logger.debug("Automod detected spam message")

        except Exception:
            pass

        try:
            honeypot_detected = await self.check_honeypot(message)
            if honeypot_detected:
                return logger.debug("Honeypot detected and handled")
        except Exception:
            pass

        try:
            extra_protection_detected = await self.check_extra_protection(message)
            if extra_protection_detected:
                return logger.debug("Extra protection detected and handled")
        except Exception:
            pass

        try:

            await self.check_afk_user_mention(message)

        except Exception:
            pass

        try:

            await self.check_for_bot_mention(message)

        except Exception:
            pass

        try:

            await self.check_for_owner_first_time_message_in_guild(message)

        except Exception:
            pass

        try:

            await self.custom_role_command(message)

        except Exception:
            pass

        try:

            if await self.check_media_channel(message):

                return logger.info("Media channel detected")

        except Exception:
            pass

        try:

            if await self.promote_message_module(message):

                return

        except Exception as promote_error:

            logger.error(
                "Promote module failed in on_message | "
                f"guild={getattr(getattr(message, 'guild', None), 'id', 'unknown')} "
                f"channel={getattr(getattr(message, 'channel', None), 'id', 'unknown')} "
                f"author={getattr(getattr(message, 'author', None), 'id', 'unknown')} "
                f"message={getattr(message, 'id', 'unknown')} "
                f"error={type(promote_error).__name__}: {promote_error}"
            )

        try:

            ai_task = asyncio.create_task(self.ai_chat_module(message))
            ai_task.add_done_callback(self._on_ai_task_done)

        except Exception:
            pass

        try:

            await self.auto_responder(message)

        except Exception:
            pass

        try:

            await self.music_channel_module(message)

        except Exception:
            pass

    async def music_channel_module(self, message: discord.Message):

        try:
            music_cog = self.bot.get_cog("Music")
            if music_cog and await music_cog.handle_pending_track_pick_message(message):
                return

            music_data = cache.music.get(str(message.guild.id), {})

            setup_channel_id = music_data.get("music_setup_channel_id")
            try:
                setup_channel_id = int(setup_channel_id) if setup_channel_id else None
            except (TypeError, ValueError):
                setup_channel_id = None

            if not setup_channel_id:

                return

            if message.channel.id != setup_channel_id:

                return

            if message.author == self.bot.user:
                controller_message_ids: set[int] = set()
                current_message_id = int(getattr(message, "id", 0) or 0)
                try:
                    cached_controller_message_id = int(
                        music_data.get("music_setup_message_id") or 0
                    )
                    if cached_controller_message_id > 0:
                        controller_message_ids.add(cached_controller_message_id)
                except (TypeError, ValueError):
                    pass

                try:
                    if music_cog is not None:
                        manual_map = getattr(
                            music_cog, "manual_controller_data", {}
                        ) or {}
                        manual_message = manual_map.get(str(message.guild.id))
                        manual_message_id = int(
                            getattr(manual_message, "id", 0) or 0
                        )
                        if manual_message_id > 0:
                            controller_message_ids.add(manual_message_id)
                except Exception:
                    pass

                if current_message_id in controller_message_ids:
                    return

                pending_pick_message_ids = self._music_pending_pick_message_ids(
                    music_cog,
                    message.guild.id,
                    message.channel.id,
                )
                if current_message_id in pending_pick_message_ids:
                    return

                # Keep interactive components (controller/selectors/buttons) so they can
                # live for their own timeout/delete_after settings.
                try:
                    if len(list(getattr(message, "components", []) or [])) > 0:
                        return
                except Exception:
                    pass

                try:
                    await message.delete(
                        delay=self.MUSIC_SETUP_SELF_BOT_DELETE_DELAY_SECONDS
                    )
                except Exception:
                    pass
                return

            if message.author.bot:

                try:
                    await message.delete(
                        delay=self.MUSIC_SETUP_OTHER_BOT_DELETE_DELAY_SECONDS
                    )
                except Exception:
                    pass
                return

            if not music_cog:
                return logger.warning("Music cog is not loaded yet.")
            await music_cog.music_setup_function(message)

        except Exception as e:

            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )
