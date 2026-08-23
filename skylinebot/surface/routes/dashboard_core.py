from __future__ import annotations

import datetime
import asyncio
import bisect
import html
import hashlib
import io
import ipaddress
import json
import mimetypes
import os
import random
import re
import secrets
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import storage
import wavelink
import discord
import psutil
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from skylinebot.src.modules import ticket_panel
from skylinebot.src.modules.donate import DonateSlipReviewView, publish_donate_panel_message
import skylinebot.src.modules.dashboard_activity as dashboard_activity
from skylinebot.console.logging import logger
from skylinebot.utils import i18n

from skylinebot.config.config import BotConfigClass, Types, users
from skylinebot.console.generator import generate_redeem_code
from skylinebot.bridge.storage import get_collection
from skylinebot.memory.cache import cache
from skylinebot.style import urls as style_urls
from skylinebot.workflows.subscription_actions import change_guild_subscription, change_user_subscription
from skylinebot.workflows import billing as _billing_workflow
from skylinebot.workflows import shop as _shop_workflow
from skylinebot.surface.runtime import (
    bind_bot,
    consume_oauth_state,
    create_oauth_state,
    create_session,
    destroy_session,
    get_bot,
    get_discord_service_state,
    get_session,
)
from skylinebot.surface import guild_growth
from skylinebot.surface.routes.dashboard_helpers import limits_utils as _dashboard_limits_utils
from skylinebot.surface.routes.dashboard_helpers import plan_utils as _dashboard_plan_utils
from skylinebot.surface.routes.dashboard_helpers import render_utils as _dashboard_render_utils
from skylinebot.surface.routes.dashboard_helpers import status_ui_utils as _dashboard_status_ui_utils
from skylinebot.surface.routes.dashboard_helpers import social_utils as _dashboard_social_utils
from skylinebot.surface.routes.dashboard_helpers import promote_utils as _dashboard_promote_utils
from skylinebot.surface.routes.dashboard_helpers import donate_utils as _dashboard_donate_utils
from skylinebot.surface.routes.dashboard_domains import (
    commands as _dashboard_commands_domain,
    localization as _dashboard_localization_domain,
    ownerbot as _dashboard_ownerbot_domain,
    overview as _dashboard_overview_domain,
    runtime as _dashboard_runtime_domain,
    security as _dashboard_security_domain,
    utils as _dashboard_utils_domain,
)

# Backward-compatible aliases used by split dashboard tab modules.
c = cache
g = guild_growth

def item(value: Any) -> Any:
    return value

BOT_CONFIG = BotConfigClass()
SESSION_COOKIE = "SkylineBOT_surface_session"
DASHBOARD_ACCESS_MODE_SESSION_KEY = "dashboard_access_mode"
DEFAULT_DASHBOARD_ACCESS_MODE = "guild"
OWNERBOT_DASHBOARD_ACCESS_MODE = "bot"
DISCORD_API = "https://discord.com/api/v10"
ADMINISTRATOR = 0x8
MANAGE_GUILD = 0x20
LOGS_DIR = Path(__file__).resolve().parents[3] / "logs"
DONATE_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "donate"
VERIFY_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "verify"
WELCOME_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "welcome"
STARBOARD_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "starboard"
EMBED_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "embed"
PROMOTE_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "promote"
TRANSCRIPTS_DIR = Path(__file__).resolve().parents[3] / "transcripts"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
DASHBOARD_LAYOUT_TEMPLATE_PATH = TEMPLATES_DIR / "dashboard_layout.html"
_DASHBOARD_LAYOUT_TEMPLATE_CACHE: str | None = None
_DASHBOARD_RENDER_HELPERS = _dashboard_render_utils.DashboardRenderHelpers(
    layout_template_path=DASHBOARD_LAYOUT_TEMPLATE_PATH,
    page_template_dir=TEMPLATES_DIR / "dashboard_pages",
)

PREMIUM_COMMAND_PREFIXES: tuple[str, ...] = (
    "music settings",
    "customrole add",
    "autoresponder add",
    "setup antinuke custom",
)
SUBSCRIBE_PLAN_PATH = "/subscribe-plan"
FOOTER_BRAND_NAME = "SkylineBOT"
FOOTER_TEAM_NAME = "Skyline Team"
CONTACT_EXTERNAL_URL = str(style_urls.CONTACT or "https://niceshopallforme.web.app/contact").strip()


def _global_copyright_text() -> str:
    current_year = datetime.datetime.now().year
    return f"© {current_year} {FOOTER_BRAND_NAME} • {FOOTER_TEAM_NAME}"

FALLBACK_HERO_IMAGE = "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&fm=webp&w=960&q=62"
FALLBACK_TICKET_IMAGE = "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&fm=webp&w=720&q=60"
FALLBACK_SECURITY_IMAGE = "https://images.unsplash.com/photo-1563013544-824ae1b704d3?auto=format&fit=crop&fm=webp&w=720&q=60"
FALLBACK_GIVEAWAY_IMAGE = "https://images.unsplash.com/photo-1515169067868-5387ec356754?auto=format&fit=crop&fm=webp&w=720&q=60"
TRUEMONEY_GIFT_LINK_RE = re.compile(r"^https?://gift\.truemoney\.com/campaign/\?v=[A-Za-z0-9_-]{8,}$", re.I)
DONATEBOT_DISCORD_ID_RE = re.compile(r"^\d{15,22}$")
DONATEBOT_TOP_DONOR_SCAN_LIMIT = 3500

PREMIUM_FEATURE_ROWS: list[tuple[str, str, str, str, str]] = [
    ("เล่นเพลงผ่านลิงก์", "ไม่มี", "มี", "มี", "มี"),
    ("ปรับระดับเสียงเริ่มต้น", "ไม่มี", "มี", "มี", "มี"),
    ("จำนวนบทบาทที่กำหนดเอง", "5", "10", "15", "20"),
    ("จำนวน Auto Responder", "5", "10", "15", "20"),
    ("จำนวนบทบาทต้อนรับอัตโนมัติ", "3", "5", "10", "15"),
    ("โหมด Anti-Nuke ขั้นสูง (Custom)", "ไม่มี", "มี", "มี", "มี"),
    ("ระดับการซัพพอร์ต", "มาตรฐาน", "รวดเร็ว", "เร่งด่วน", "เร่งด่วนสูงสุด"),
]

PREMIUM_COMMAND_ROWS: list[tuple[str, str, str, str, str]] = [
    ("/play", "มี", "มี", "มี", "มี"),
    ("/queue", "มี", "มี", "มี", "มี"),
    ("/music settings", "ดูได้อย่างเดียว", "ใช้งานเต็มรูปแบบ", "ใช้งานเต็มรูปแบบ", "ใช้งานเต็มรูปแบบ"),
    ("/customrole add", "5 บทบาท", "10 บทบาท", "15 บทบาท", "20 บทบาท"),
    ("/autoresponder add", "5 รายการ", "10 รายการ", "15 รายการ", "20 รายการ"),
    ("/setup antinuke custom", "ไม่มี", "มี", "มี", "มี"),
    ("/premium server", "มี", "มี", "มี", "มี"),
    ("/redeem", "มี", "มี", "มี", "มี"),
]

PREMIUM_PLAN_CARDS: list[dict[str, str]] = [
    {
        "title": "Free",
        "price": "ฟรี / เดือน",
        "desc": "เหมาะสำหรับชุมชนที่เพิ่งเริ่ม",
    },
    {
        "title": "Silver",
        "price": "40 บาท / เดือน",
        "desc": "เพิ่มขีดจำกัดสำคัญและปลดล็อกการควบคุมขั้นสูง",
    },
    {
        "title": "Gole",
        "price": "120 บาท / เดือน",
        "desc": "เหมาะกับเซิร์ฟเวอร์ที่ใช้งานหนักและต้องการความเสถียร",
    },
    {
        "title": "Diamond",
        "price": "250 บาท / เดือน",
        "desc": "ขีดจำกัดสูงสุดและสิทธิ์ครบทุกระบบ",
    },
    {
        "title": "Permanent",
        "price": "500 บาท / ถาวร",
        "desc": "สิทธิ์ครบทุกระบบ รวมฟีเจอร์พรีเมียมใหม่ในอนาคต",
    },
]

DONATION_SUPPORT_ROWS: list[tuple[str, str, str, str, str]] = [
    ("จำนวนการรับโดเนต", "30 ครั้ง", "70 ครั้ง", "200 ครั้ง", "ไม่จำกัด"),
    ("ระบบพร้อมเพย์/ธนาคาร", "มี", "มี", "มี", "มี"),
    ("ปิดโฆษณา", "ไม่มี", "มี", "มี", "มี"),
    ("แชต AI", "10 ครั้ง", "20 ครั้ง", "50 ครั้ง", "ไม่จำกัด"),
    ("ราคา / เดือน", "ฟรี", "40 บาท", "120 บาท", "250 บาท"),
]

PLAN_ORDER: tuple[str, ...] = ("free", "silver", "golden", "diamond", "permanent")
PLAN_DISPLAY_NAMES: dict[str, str] = {
    "free": "Free",
    "silver": "Silver",
    "golden": "Gole",
    "diamond": "Diamond",
    "permanent": "Permanent",
}
PLAN_COLORS: dict[str, str] = {
    "free": "#a9b7da",
    "silver": "#6b8cff",
    "golden": "#ffb347",
    "diamond": "#ffcc33",
    "permanent": "#ff8ae2",
}
MUSIC_IDLE_IMAGE_PATH = Path(__file__).resolve().parents[2] / "photos" / "music.png"
MUSIC_IDLE_IMAGE_ROUTE = "/dashboard/assets/music-idle"

REPORT_CHALLENGE_TTL = 600
REPORT_CHALLENGES: dict[str, tuple[str, float]] = {}
REPORT_RATE_LIMIT_WINDOW = 120
REPORT_RATE_LIMIT_MAX = 4
REPORT_RATE_LIMIT: dict[str, list[float]] = {}
_LANDING_PLAN_PRICING_SNAPSHOT_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "snapshot": None,
}


def _env_float(name: str, default: float) -> float:
    try:
        raw = os.getenv(name, str(default))
        return float(raw if raw is not None else default)
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name, str(default))
        return int(raw if raw is not None else default)
    except Exception:
        return int(default)


_RECENT_LOGS_CACHE_TTL_SECONDS = max(
    1.0,
    _env_float("DASHBOARD_RECENT_LOGS_CACHE_TTL_SECONDS", 3.0),
)
_RECENT_LOGS_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "value": [],
}
_LIVE_OPTIONS_CACHE_TTL_SECONDS = max(
    2.0,
    _env_float("DASHBOARD_LIVE_OPTIONS_CACHE_TTL_SECONDS", 20.0),
)
_LIVE_OPTIONS_CACHE: dict[str, dict[str, Any]] = {}
_DASHBOARD_MEMBER_PERMISSION_CACHE_TTL_SECONDS = max(
    3.0,
    _env_float("DASHBOARD_MEMBER_PERMISSION_CACHE_TTL_SECONDS", 45.0),
)
_DASHBOARD_MEMBER_PERMISSION_FETCH_BUDGET = max(
    0,
    _env_int("DASHBOARD_MEMBER_PERMISSION_FETCH_BUDGET", 2),
)
_DASHBOARD_MEMBER_PERMISSION_CACHE: dict[tuple[int, int], tuple[float, int]] = {}
DASHBOARD_CONFIG_CACHE: dict[str, str] = {}
TRUSTED_ORDER_CONFIG_KEY = "trusted_server_order"
OWNERBOT_RUNTIME_CONFIG_KEY = "ownerbot_runtime_settings"
OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY = "ownerbot_upload_channels_v1"
OWNERBOT_PAYMENT_PROVIDER_CONFIG_KEY = "ownerbot_payment_provider_settings_v1"
PROMOTE_OWNER_POLICY_CONFIG_KEY = "promote_owner_policy_v1"
PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY = "promote_suspended_guilds_v1"
OWNERBOT_PAYMENT_PROVIDER_TYPES: tuple[str, ...] = ("promptpay", "bank", "gateway", "truemoney", "stripe")
OWNERBOT_BANK_VERIFICATION_MODES: tuple[str, ...] = ("manual_slip", "webhook_auto")
OWNERBOT_UPLOAD_TARGETS: tuple[str, ...] = (
    "promote_attachment",
    "embed_messages_asset",
    "starboard_asset",
    "welcome_asset",
    "donate_asset",
    "verify_asset",
    "color_sets_asset",
    "photo_asset",
)
OWNERBOT_UPLOAD_TARGET_LABELS: dict[str, str] = {
    "promote_attachment": "Promote - รูปโปรโมต",
    "embed_messages_asset": "Embed Messages - รูปแนบ",
    "starboard_asset": "Starboard - รูป Embed",
    "welcome_asset": "Welcome/Leaver - รูป Embed",
    "donate_asset": "Donate - รูประบบโดเนต",
    "verify_asset": "Verify - รูปหลักฐาน",
    "color_sets_asset": "Color Sets - รูปการ์ด",
    "photo_asset": "PhotoRoom - รูปแปลงลิงก์",
}
OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS: dict[str, str] = {
    "promote_attachment": "upload-promote",
    "embed_messages_asset": "upload-embed",
    "starboard_asset": "upload-starboard",
    "welcome_asset": "upload-welcome",
    "donate_asset": "upload-donate",
    "verify_asset": "upload-verify",
    "color_sets_asset": "upload-colors",
    "photo_asset": "upload-photo",
}
OWNERBOT_HIDEABLE_TABS: tuple[str, ...] = (
    "overview",
    "server_settings",
    "embed_messages",
    "premium_receive",
    "tools",
    "welcome_center",
    "auto_reply_center",
    "economy",
    "roleplay",
    "guildstyle_studio",
    "levels",
    "autoroles",
    "colors",
    "reaction_roles",
    "starboard",
    "temp_channels",
    "join_to_create",
    "temp_links",
    "statistics_plus",
    "screening",
    "screening_categories",
    "automation",
    "anti_raid",
    "extra_protection",
    "alerts_twitch",
    "alerts_youtube",
    "alerts_tiktok",
    "alerts_github",
    "alerts_facebook",
    "control_panel",
    "audit_logs",
    "logs",
    "security",
    "moderation",
    "welcome",
    "leaver",
    "ocr",
    "verify",
    "voice_randomizer",
    "aichat",
    "media",
    "autoresponder",
    "customrole",
    "music",
    "promote",
    "commands",
    "tickets",
    "shop",
    "giveaways",
    "server_stats",
    "donate",
    "alerts",
)
OWNERBOT_HIDEABLE_TAB_LABELS: dict[str, str] = {
    "overview": "ภาพรวม",
    "server_settings": "ตั้งค่าเซิร์ฟเวอร์",
    "embed_messages": "ข้อความแบบ Embed",
    "premium_receive": "รับพรีเมียม",
    "tools": "เครื่องมือ",
    "welcome_center": "การต้อนรับ",
    "auto_reply_center": "ตัวตอบกลับอัตโนมัติ",
    "economy": "Economy",
    "roleplay": "Roleplay",
    "guildstyle_studio": "Theme guildstyle",
    "levels": "ระบบเลเวล",
    "autoroles": "บทบาทอัตโนมัติ",
    "colors": "สี",
    "reaction_roles": "รีแอ็กชันเพื่อรับบทบาท",
    "starboard": "Starboard",
    "temp_channels": "ช่องชั่วคราว",
    "join_to_create": "Join To Create VC",
    "temp_links": "ลิงก์ชั่วคราว",
    "statistics_plus": "Statistics",
    "screening": "การคัดกรอง",
    "screening_categories": "หมวดหมู่",
    "automation": "การจัดการอัตโนมัติ",
    "anti_raid": "Anti-Raid",
    "extra_protection": "ระบบป้องกันพิเศษ",
    "alerts_twitch": "Twitch",
    "alerts_youtube": "YouTube",
    "alerts_tiktok": "TikTok",
    "alerts_github": "GitHub",
    "alerts_facebook": "Facebook",
    "control_panel": "แผงควบคุม",
    "audit_logs": "ตรวจสอบบันทึก",
    "logs": "บันทึกเหตุการณ์",
    "security": "ความปลอดภัย",
    "moderation": "ดูแลแชต",
    "welcome": "ต้อนรับ",
    "leaver": "ลาจาก",
    "ocr": "สแกนรูปภาพ",
    "verify": "ยืนยันตัวตน",
    "voice_randomizer": "สุ่มห้องเสียง",
    "aichat": "แชต AI",
    "media": "คลังสื่อ",
    "autoresponder": "ตอบกลับอัตโนมัติ",
    "customrole": "ยศส่วนตัว",
    "music": "เพลง",
    "promote": "โปรโมต",
    "commands": "คำสั่ง",
    "tickets": "Tickets",
    "shop": "Guild Shop",
    "giveaways": "กิจกรรมแจกของ",
    "server_stats": "สถิติเซิร์ฟเวอร์",
    "donate": "โดเนต",
    "alerts": "แจ้งเตือนโซเชียล",
}

# Tabs that require paid plan to access.
# If the current guild plan is lower than required tier, dashboard should show pricing locked page.
DASHBOARD_TAB_REQUIRED_PLAN: dict[str, str] = {
    "levels": "silver",
    "temp_links": "silver",
    "statistics_plus": "silver",
    "server_stats": "silver",
    "anti_raid": "silver",
    "extra_protection": "silver",
    "alerts": "silver",
    "alerts_twitch": "silver",
    "alerts_youtube": "silver",
    "alerts_tiktok": "silver",
    "alerts_github": "silver",
    "alerts_facebook": "silver",
    "donate": "free",
}
DASHBOARD_TAB_REQUIRED_PLAN_TIERS: tuple[str, ...] = ("free", "silver", "golden", "diamond", "permanent")
DASHBOARD_TAB_NEW_BADGES_DEFAULT: tuple[str, ...] = (
    "alerts_twitch",
    "alerts_youtube",
    "alerts_tiktok",
    "alerts_github",
    "alerts_facebook",
)
DEVELOPER_SOCIAL_LINKS_CONFIG_KEY = "developer_social_links"
GIVEAWAY_DASHBOARD_SETTINGS_KEY = "giveaway_dashboard_settings"
SCREENING_CATEGORY_CONFIG_KEY_PREFIX = "screening_categories_v1_guild_"
OWNERBOT_AI_MODEL_RAM_GUIDE: tuple[dict[str, str], ...] = (
    {
        "provider": "ollama",
        "value": "qwen2.5:0.5b-instruct",
        "label": "qwen2.5:0.5b-instruct (แนะนำสำหรับ VPS แรมต่ำ)",
        "min_ram": "~0.8 GB+",
        "model_size": "398 MB",
        "source": "https://ollama.com/library/qwen2.5",
    },
    {
        "provider": "ollama",
        "value": "qwen2.5:1.5b-instruct",
        "label": "qwen2.5:1.5b-instruct (สมดุล)",
        "min_ram": "~1.6 GB+",
        "model_size": "986 MB",
        "source": "https://ollama.com/library/qwen2.5",
    },
    {
        "provider": "ollama",
        "value": "qwen2.5:3b-instruct",
        "label": "qwen2.5:3b-instruct (คุณภาพสูงขึ้น)",
        "min_ram": "~2.7 GB+",
        "model_size": "1.9 GB",
        "source": "https://ollama.com/library/qwen2.5",
    },
    {
        "provider": "ollama",
        "value": "qwen2.5:7b-instruct",
        "label": "qwen2.5:7b-instruct (หนัก)",
        "min_ram": "~6.0 GB+",
        "model_size": "4.7 GB",
        "source": "https://ollama.com/library/qwen2.5",
    },
    {
        "provider": "openai",
        "value": "gpt-4o-mini",
        "label": "gpt-4o-mini",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://platform.openai.com/docs/models",
    },
    {
        "provider": "google",
        "value": "gemini-2.0-flash",
        "label": "gemini-2.0-flash",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://ai.google.dev/gemini-api/docs/models",
    },
    {
        "provider": "opentyphoon",
        "value": "typhoon-v2.5-30b-a3b-instruct",
        "label": "typhoon-v2.5-30b-a3b-instruct",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://playground.opentyphoon.ai/",
    },
    {
        "provider": "chindax",
        "value": "accounts/fireworks/models/gpt-oss-20b",
        "label": "accounts/fireworks/models/gpt-oss-20b",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://chindax.iapp.co.th/",
    },
    {
        "provider": "chindax",
        "value": "accounts/fireworks/models/gpt-oss-120b",
        "label": "accounts/fireworks/models/gpt-oss-120b",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://chindax.iapp.co.th/",
    },
    {
        "provider": "aiforthai",
        "value": "aiforthai-chat",
        "label": "aiforthai-chat",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://aiforthai.in.th/",
    },
    {
        "provider": "cloudflare",
        "value": "@cf/meta/llama-3.1-8b-instruct",
        "label": "@cf/meta/llama-3.1-8b-instruct",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/",
    },
    {
        "provider": "thaillm",
        "value": "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2",
        "label": "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://thaillm.or.th/",
    },
    {
        "provider": "thaillm",
        "value": "Pathumma-ThaiLLM-qwen3-8b-think-3.0.0",
        "label": "Pathumma-ThaiLLM-qwen3-8b-think-3.0.0",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://thaillm.or.th/",
    },
    {
        "provider": "thaillm",
        "value": "Typhoon-S-ThaiLLM-8B-Instruct",
        "label": "Typhoon-S-ThaiLLM-8B-Instruct",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://thaillm.or.th/",
    },
    {
        "provider": "thaillm",
        "value": "THaLLE-0.2-ThaiLLM-8B-fa",
        "label": "THaLLE-0.2-ThaiLLM-8B-fa",
        "min_ram": "~0.5 GB+",
        "model_size": "Cloud API",
        "source": "https://thaillm.or.th/",
    },
)
COLOR_SETS_CONFIG_KEY_PREFIX = "probot_colors_v1_guild_"
REACTION_ROLES_CONFIG_KEY_PREFIX = "probot_reaction_roles_v1_guild_"
STARBOARD_CONFIG_KEY_PREFIX = "probot_starboard_v1_guild_"
EMBED_MESSAGES_CONFIG_KEY_PREFIX = "probot_embed_messages_v1_guild_"
VOICE_RANDOMIZER_CONFIG_KEY_PREFIX = "probot_voice_randomizer_v1_guild_"
TEMP_CHANNELS_CONFIG_KEY_PREFIX = "probot_temp_channels_v1_guild_"
TEMP_LINKS_CONFIG_KEY_PREFIX = "probot_temp_links_v1_guild_"
LEVELS_CONFIG_KEY_PREFIX = "probot_levels_v1_guild_"
EXTRA_PROTECTION_CONFIG_KEY_PREFIX = "extra_protection_v1_guild_"
HONEYPOT_CONFIG_KEY_PREFIX = "honeypot_v1_guild_"
DASHBOARD_AUDIT_CONFIG_KEY_PREFIX = "dashboard_audit_v1_guild_"
PROMOTE_COOLDOWN_SECONDS = 12 * 3600
PROMOTE_COOLDOWN_HOURS = 12
REDEEM_CODE_TYPES: dict[str, str] = dict(getattr(Types, "redeem_code_types", {}) or {})
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
PROMOTE_HARD_BLOCK_WORDS: tuple[str, ...] = (
    "free nitro",
    "steam gift 100%",
    "airdrop wallet",
    "wallet connect",
    "seed phrase",
    "recovery phrase",
    "private key",
)
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
PROMOTE_IMAGE_FLAG_CATEGORY_THRESHOLDS: dict[str, float] = {
    "sexual": 0.72,
    "sexual/minors": 0.05,
    "violence": 0.85,
    "violence/graphic": 0.45,
    "illicit": 0.68,
    "illicit/violent": 0.45,
}

DEFAULT_TRUSTED_SERVER_ORDER = [
    "SkyLine&Music BOT SUPPORT",
    "SkyLineBOT",
    "Skyline Music Users",
    "SkylineBOT Premium",
    "SkylineBOT Free",
    "Moderator Lab",
    "Giveaway Hub",
    "Support Desk Thailand",
]
# Keep landing payload bounded so first-page render remains fast on large bots.
DEFAULT_DASHBOARD_TRUSTED_SERVER_MAX_ENTRIES = 24
LANDING_PLAN_PRICING_CACHE_TTL_SECONDS = 45

SOCIAL_PLATFORM_KEYS: tuple[str, ...] = (
    "discord",
    "youtube",
    "tiktok",
    "instagram",
    "facebook",
    "x",
    "profile",
)
SOCIAL_PLATFORM_LABELS: dict[str, str] = {
    "discord": "Discord",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "IG",
    "facebook": "FB",
    "x": "X",
    "profile": "Web Profile",
}
SOCIAL_PLATFORM_DEFAULT_ICONS: dict[str, str] = {
    "discord": "💬",
    "youtube": "▶️",
    "tiktok": "♪",
    "instagram": "📸",
    "facebook": "📘",
    "x": "✖️",
    "profile": "🌐",
}
SOCIAL_PLATFORM_ICON_CLASSES: dict[str, str] = {
    "discord": "bi bi-discord",
    "youtube": "bi bi-youtube",
    "tiktok": "bi bi-tiktok",
    "instagram": "bi bi-instagram",
    "facebook": "bi bi-facebook",
    "x": "bi bi-twitter-x",
    "profile": "bi bi-globe2",
}
SOCIAL_PLATFORM_ALLOWED_HOSTS: dict[str, tuple[str, ...]] = {
    "discord": ("discord.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "tiktok": ("tiktok.com",),
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com", "fb.watch"),
    "x": ("x.com", "twitter.com"),
}

SCREENING_CATEGORY_ITEMS: list[dict[str, Any]] = [
    {"key": "member_ban", "label": "แบนสมาชิก", "log_type": "member_ban"},
    {"key": "member_timeout", "label": "หมดเวลา (ให้ / ลบ)", "log_type": "member_update"},
    {"key": "channel_create", "label": "สร้างช่อง", "log_type": "channel_create"},
    {"key": "thread_create", "label": "สร้างเธรด", "log_type": "channel_create"},
    {"key": "role_create", "label": "สร้างบทบาท", "log_type": "role_create"},
    {"key": "channel_delete", "label": "ลบช่อง", "log_type": "channel_delete"},
    {"key": "thread_delete", "label": "ลบเธรด", "log_type": "channel_delete"},
    {"key": "message_delete", "label": "ลบข้อความ", "log_type": "message_delete"},
    {"key": "role_delete", "label": "ลบบทบาท", "log_type": "role_delete"},
    {"key": "message_edit", "label": "แก้ไขข้อความ", "log_type": "message_edit"},
    {"key": "member_kick", "label": "เตะสมาชิก", "log_type": "member_kick"},
    {"key": "member_voice_move_p2", "label": "สมาชิกย้ายไปช่องเสียง", "log_type": "voice_state_update"},
    {"key": "member_voice_leave_p2", "label": "สมาชิกออกจากช่องเสียง", "log_type": "voice_state_update"},
    {"key": "member_join", "label": "สมาชิกเข้า", "log_type": "member_join"},
    {"key": "member_leave", "label": "สมาชิกออก", "log_type": "member_leave"},
    {"key": "member_nick_update", "label": "เปลี่ยนชื่อ", "log_type": "member_update"},
    {"key": "moderation_command", "label": "ใช้คำสั่งการคัดกรอง", "log_type": "antinuke"},
    {"key": "role_add", "label": "ให้บทบาท", "log_type": "member_update"},
    {"key": "role_remove", "label": "ลบบทบาท", "log_type": "member_update"},
    {"key": "invite_change", "label": "คำเชิญของเซิร์ฟเวอร์", "log_type": "invite_create"},
    {"key": "member_unban", "label": "ปลดแบนสมาชิก", "log_type": "member_unban"},
    {"key": "channel_update", "label": "อัปเดตช่อง", "log_type": "channel_update"},
    {"key": "thread_update", "label": "อัปเดตเธรด", "log_type": "channel_update"},
    {"key": "channel_perm_update", "label": "อัปเดตสิทธิ์ของช่อง", "log_type": "channel_update"},
    {"key": "role_update", "label": "อัปเดตบทบาท", "log_type": "role_update"},
    {"key": "guild_update", "label": "อัปเดตเซิร์ฟเวอร์", "log_type": "guild_update"},
    {"key": "voice_join", "label": "สมาชิกเข้าร่วมช่องเสียง", "log_type": "voice_state_update"},
    {"key": "voice_leave", "label": "สมาชิกออกจากช่องเสียง", "log_type": "voice_state_update"},
    {"key": "voice_status", "label": "สถานะเสียง (ปิด/ไม่ปิด)", "log_type": "voice_state_update"},
    {"key": "voice_switch", "label": "สมาชิกสลับห้องเสียง", "log_type": "voice_state_update"},
]

SCREENING_CATEGORY_DEFAULT_COLORS: dict[str, str] = {
    "member_ban": "#ef4444",
    "member_update": "#f59e0b",
    "channel_create": "#22c55e",
    "channel_delete": "#ef4444",
    "message_delete": "#f97316",
    "message_edit": "#0ea5e9",
    "role_create": "#14b8a6",
    "role_delete": "#ef4444",
    "member_kick": "#fb7185",
    "member_join": "#22c55e",
    "member_leave": "#ef4444",
    "invite_create": "#a78bfa",
    "member_unban": "#22c55e",
    "channel_update": "#38bdf8",
    "role_update": "#22d3ee",
    "guild_update": "#c084fc",
    "voice_state_update": "#60a5fa",
    "antinuke": "#f43f5e",
}

SCREENING_CATEGORY_PLAN_LIMITS_BY_TIER: dict[str, int] = {
    "free": 3,
    "silver": 10,
    "golden": 15,
    "diamond": 30,
    "permanent": 30,
}


def _screening_categories_plan_cap(plan_tier: str) -> int:
    tier = _normalize_plan_tier(plan_tier)
    return int(SCREENING_CATEGORY_PLAN_LIMITS_BY_TIER.get(tier, 3))


def _normalize_social_url(value: Any) -> str:
    return _dashboard_social_utils.normalize_social_url(
        value,
        clean_text_fn=_clean_text,
        allowed_hosts=(
            "discord.com",
            "youtube.com",
            "youtu.be",
            "tiktok.com",
            "instagram.com",
            "facebook.com",
            "fb.com",
            "fb.watch",
            "x.com",
            "twitter.com",
            "github.com",
            "gitlab.com",
            "notion.site",
            "linktr.ee",
            "bio.site",
            "beacons.ai",
            "medium.com",
            "dev.to",
            "skylinebot.xyz",
        ),
    )


def _normalize_social_url_for_platform(value: Any, platform: str) -> str:
    platform_key = str(platform or "").strip().lower()
    raw = _clean_text(value).strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    if platform_key == "profile":
        return raw
    allowed_hosts = SOCIAL_PLATFORM_ALLOWED_HOSTS.get(platform_key)
    if not allowed_hosts:
        return ""
    if not any(host == item or host.endswith(f".{item}") for item in allowed_hosts):
        return ""
    return raw


def _normalize_social_icon(value: Any, platform: str) -> str:
    return _dashboard_social_utils.normalize_social_icon(
        value,
        platform,
        clean_text_fn=_clean_text,
        default_icons=SOCIAL_PLATFORM_DEFAULT_ICONS,
    )


def _developer_social_links_from_system() -> dict[str, dict[str, dict[str, str]]]:
    return _dashboard_social_utils.developer_social_links_from_system(
        raw_cache=DASHBOARD_CONFIG_CACHE.get(DEVELOPER_SOCIAL_LINKS_CONFIG_KEY, ""),
        raw_runtime=DASHBOARD_CONFIG_CACHE.get(OWNERBOT_RUNTIME_CONFIG_KEY, ""),
        env_payload=os.getenv("DEVELOPER_SOCIAL_LINKS", ""),
        parse_developer_social_links_fn=_parse_developer_social_links,
        json_loads_fn=json.loads,
    )


def _developer_social_url(dev_payload: dict[str, Any], platform: str, fallback: str = "") -> str:
    return _dashboard_social_utils.developer_social_url(
        dev_payload,
        platform,
        fallback=fallback,
        normalize_social_url_fn=_normalize_social_url,
        normalize_social_url_for_platform_fn=_normalize_social_url_for_platform,
    )


def _developer_social_icon(dev_payload: dict[str, Any], platform: str) -> str:
    return _dashboard_social_utils.developer_social_icon(
        dev_payload,
        platform,
        normalize_social_icon_fn=_normalize_social_icon,
        default_icons=SOCIAL_PLATFORM_DEFAULT_ICONS,
    )


def _clean_text(value: Any) -> str:
    text = str(value or "")
    try:
        repaired = text.encode("latin1").decode("utf-8")
        if repaired and repaired != text:
            text = repaired
    except Exception:
        pass
    # Some legacy values were stored as UTF-8 bytes misread via cp874.
    # Repair only when control-byte artifacts are present to avoid harming valid Thai text.
    if any("\u0080" <= ch <= "\u009f" for ch in text):
        try:
            reverse_map = getattr(_clean_text, "_cp874_reverse_map", None)
            if reverse_map is None:
                reverse_map = {}
                for b in range(256):
                    mapped = bytes([b]).decode("cp874", errors="ignore")
                    if mapped:
                        reverse_map[mapped] = b
                setattr(_clean_text, "_cp874_reverse_map", reverse_map)
            raw_bytes = bytearray()
            for ch in text:
                byte_value = reverse_map.get(ch)
                if byte_value is not None:
                    raw_bytes.append(byte_value)
                elif ord(ch) <= 255:
                    raw_bytes.append(ord(ch))
                else:
                    raw_bytes.extend(ch.encode("utf-8", errors="ignore"))
            repaired_cp874 = raw_bytes.decode("utf-8", errors="ignore")
            if repaired_cp874 and repaired_cp874 != text:
                before_ctrl = sum(1 for c in text if "\u0080" <= c <= "\u009f")
                after_ctrl = sum(1 for c in repaired_cp874 if "\u0080" <= c <= "\u009f")
                if after_ctrl <= before_ctrl:
                    text = repaired_cp874
        except Exception:
            pass
    mojibake_symbols = {
        b"\xe2\x80\xa2".decode("latin1"): "-",
        b"\xe2\x80\xa6".decode("latin1"): "...",
        b"\xe2\x9c\x85".decode("latin1"): "✅",
        b"\xe2\x9d\x8c".decode("latin1"): "❌",
        b"\xf0\x9f\x91\x8b".decode("latin1"): "👋",
        b"\xf0\x9f\x93\xa3".decode("latin1"): "📣",
    }
    cp874_mojibake_symbols = {
        b"\xe2\x80\xa2".decode("cp874", errors="ignore"): "-",
        b"\xe2\x80\xa6".decode("cp874", errors="ignore"): "...",
        b"\xe2\x80\x93".decode("cp874", errors="ignore"): "-",
        b"\xe2\x80\x94".decode("cp874", errors="ignore"): "-",
    }
    replacements = {
        **mojibake_symbols,
        **cp874_mojibake_symbols,
        "\u2705": "✅",
        "\u274c": "❌",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return " ".join(text.split())


def _is_allowed_discord_invite_url(url: str) -> bool:
    raw = _clean_text(url).strip()
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


def _is_safe_public_host(host: str) -> bool:
    return _dashboard_promote_utils.is_safe_public_host(host)


def _promote_attachment_allowed_domains() -> tuple[str, ...]:
    domains: list[str] = list(PROMOTE_ALLOWED_ATTACHMENT_DOMAINS)
    configured_base = _normalize_dashboard_base_url(getattr(BOT_CONFIG, "DASHBOARD_BASE_URL", "") or "")
    if configured_base:
        try:
            parsed = urlparse(configured_base)
            host = str(parsed.hostname or "").strip().lower()
            if host and host not in domains:
                domains.append(host)
        except Exception:
            pass
    return tuple(domains)


def _normalize_promote_attachment_url(url: str) -> str:
    return _dashboard_promote_utils.normalize_promote_attachment_url(
        url,
        clean_text_fn=_clean_text,
        allowed_extensions=PROMOTE_ALLOWED_ATTACHMENT_EXTENSIONS,
        allowed_domains=_promote_attachment_allowed_domains(),
    )


def _normalize_promote_allowed_domains(raw: Any) -> list[str]:
    return _dashboard_promote_utils.normalize_promote_allowed_domains(
        raw,
        clean_text_fn=_clean_text,
    )


def _normalize_promote_allowed_urls(raw: Any) -> list[str]:
    return _dashboard_promote_utils.normalize_promote_allowed_urls(
        raw,
        clean_text_fn=_clean_text,
    )


def _normalize_promote_blocked_words(raw: Any) -> list[str]:
    return _dashboard_promote_utils.normalize_promote_blocked_words(
        raw,
        clean_text_fn=_clean_text,
    )


def _normalize_promote_candidate_url(url: str) -> str:
    return _dashboard_promote_utils.normalize_promote_candidate_url(
        url,
        clean_text_fn=_clean_text,
    )


def _promote_default_allowed_domains() -> list[str]:
    return _dashboard_promote_utils.promote_default_allowed_domains()


def _promote_allowed_url_targets(allowed_domains: Any, allowed_urls: Any) -> tuple[list[str], list[str]]:
    return _dashboard_promote_utils.promote_allowed_url_targets(
        allowed_domains,
        allowed_urls,
        clean_text_fn=_clean_text,
    )


def _promote_blocked_url_targets(blocked_domains: Any, blocked_urls: Any) -> tuple[list[str], list[str]]:
    return _dashboard_promote_utils.promote_blocked_url_targets(
        blocked_domains,
        blocked_urls,
        clean_text_fn=_clean_text,
    )


def _is_allowed_promote_custom_url(url: str, allowed_domains: Any, allowed_urls: Any) -> bool:
    return _dashboard_promote_utils.is_allowed_promote_custom_url(
        url,
        allowed_domains=allowed_domains,
        allowed_urls=allowed_urls,
        clean_text_fn=_clean_text,
    )


def _is_blocked_promote_custom_url(url: str, blocked_domains: Any, blocked_urls: Any) -> bool:
    return _dashboard_promote_utils.is_blocked_promote_custom_url(
        url,
        blocked_domains=blocked_domains,
        blocked_urls=blocked_urls,
        clean_text_fn=_clean_text,
    )


def _promote_preview_script() -> str:
    return _dashboard_promote_utils.promote_preview_script()


def _default_ownerbot_promote_policy() -> dict[str, list[str]]:
    return {
        "allowed_domains": [],
        "allowed_urls": [],
        "blocked_words": [],
        "blocked_domains": [],
        "blocked_urls": [],
    }


def _ownerbot_promote_policy_from_raw(raw_value: Any) -> dict[str, list[str]]:
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
    defaults = _default_ownerbot_promote_policy()
    return {
        "allowed_domains": _normalize_promote_allowed_domains(parsed.get("allowed_domains", defaults["allowed_domains"])),
        "allowed_urls": _normalize_promote_allowed_urls(parsed.get("allowed_urls", defaults["allowed_urls"])),
        "blocked_words": _normalize_promote_blocked_words(parsed.get("blocked_words", defaults["blocked_words"])),
        "blocked_domains": _normalize_promote_allowed_domains(parsed.get("blocked_domains", defaults["blocked_domains"])),
        "blocked_urls": _normalize_promote_allowed_urls(parsed.get("blocked_urls", defaults["blocked_urls"])),
    }


def _ownerbot_promote_policy_from_db() -> dict[str, list[str]]:
    raw_value = DASHBOARD_CONFIG_CACHE.get(PROMOTE_OWNER_POLICY_CONFIG_KEY, "")
    return _ownerbot_promote_policy_from_raw(raw_value)


def _promote_suspension_map_from_raw(raw_value: Any) -> dict[str, dict[str, str]]:
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


def _promote_suspension_map_from_db() -> dict[str, dict[str, str]]:
    raw_value = DASHBOARD_CONFIG_CACHE.get(PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY, "")
    return _promote_suspension_map_from_raw(raw_value)


def _promote_suspension_reason(guild_id: int, suspension_map: dict[str, dict[str, str]]) -> str:
    row = suspension_map.get(str(int(guild_id or 0))) if isinstance(suspension_map, dict) else None
    if not isinstance(row, dict):
        return ""
    note = str(row.get("note") or "").strip()
    by_name = str(row.get("by_name") or "").strip()
    if note and by_name:
        return f"กิลด์นี้ถูกระงับการใช้งาน Promote โดย {by_name}: {note}"
    if note:
        return f"กิลด์นี้ถูกระงับการใช้งาน Promote: {note}"
    if by_name:
        return f"กิลด์นี้ถูกระงับการใช้งาน Promote โดย {by_name}"
    return "กิลด์นี้ถูกระงับการใช้งาน Promote โดย OwnerBOT"


def _format_ms(ms: int | float | None) -> str:
    return _dashboard_utils_domain.format_ms(ms)


def _discord_default_avatar_url(seed: Any) -> str:
    seed_text = str(seed or "").strip()
    index = 0
    if seed_text.isdigit():
        try:
            index = (int(seed_text) >> 22) % 6
        except Exception:
            index = 0
    elif seed_text:
        index = sum(ord(ch) for ch in seed_text) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{index}.png"


def _discord_avatar_url(user_id: Any, avatar_hash: Any, *, size: int = 256) -> str:
    uid = str(user_id or "").strip()
    raw_hash = str(avatar_hash or "").strip()
    if not uid or not raw_hash:
        return _discord_default_avatar_url(uid or "0")
    ext = "gif" if raw_hash.startswith("a_") else "png"
    safe_size = max(64, min(1024, int(size or 256)))
    return f"https://cdn.discordapp.com/avatars/{uid}/{raw_hash}.{ext}?size={safe_size}"


def _discord_banner_url(user_id: Any, banner_hash: Any, *, size: int = 1024) -> str:
    uid = str(user_id or "").strip()
    raw_hash = str(banner_hash or "").strip()
    if not uid or not raw_hash:
        return ""
    ext = "gif" if raw_hash.startswith("a_") else "png"
    safe_size = max(256, min(4096, int(size or 1024)))
    return f"https://cdn.discordapp.com/banners/{uid}/{raw_hash}.{ext}?size={safe_size}"


def _resolve_dashboard_user_status(user_id: int | None) -> tuple[str, str]:
    if not user_id:
        return "offline", "ออฟไลน์"
    labels = {
        "online": "ออนไลน์",
        "idle": "ไม่อยู่",
        "dnd": "ห้ามรบกวน",
        "offline": "ออฟไลน์",
        "streaming": "สตรีม",
    }
    try:
        bot = get_bot()
        for guild in list(getattr(bot, "guilds", []) or []):
            member = guild.get_member(int(user_id))
            if not member:
                continue
            status_raw = str(getattr(member, "status", "offline") or "offline").lower()
            if status_raw in {"online", "idle", "dnd", "offline"}:
                return status_raw, labels.get(status_raw, "ออฟไลน์")
            acts = list(getattr(member, "activities", []) or [])
            if any(str(getattr(act, "type", "")).lower().endswith("streaming") for act in acts):
                return "streaming", labels["streaming"]
            return "offline", labels["offline"]
    except Exception:
        pass
    return "offline", labels["offline"]


def _discord_snowflake_created_at_text(user_id: Any) -> str:
    try:
        snowflake = int(str(user_id or "").strip())
        created_at = discord.utils.snowflake_time(snowflake)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
        local_tz = datetime.timezone(datetime.timedelta(hours=7))
        return created_at.astimezone(local_tz).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "-"


async def _load_dashboard_user_profile(session: dict[str, Any]) -> dict[str, Any]:
    user = dict((session or {}).get("user") or {})
    user_id = str(user.get("id") or "").strip()
    access_token = str((session or {}).get("access_token") or "").strip()
    api_user: dict[str, Any] = {}
    if access_token:
        try:
            payload = await _discord_api_request(f"{DISCORD_API}/users/@me", access_token)
            if isinstance(payload, dict):
                api_user = payload
        except Exception:
            api_user = {}

    merged_id = str(api_user.get("id") or user_id).strip()
    merged_username = str(api_user.get("username") or user.get("username") or "Discord User").strip() or "Discord User"
    merged_global_name = str(api_user.get("global_name") or user.get("global_name") or "").strip()
    merged_discriminator = str(api_user.get("discriminator") or "").strip()
    avatar_hash = str(api_user.get("avatar") or "").strip()
    banner_hash = str(api_user.get("banner") or "").strip()

    avatar_url = (
        _discord_avatar_url(merged_id, avatar_hash, size=320)
        if avatar_hash
        else str(user.get("avatar_url") or "").strip()
    )
    if not avatar_url:
        avatar_url = _discord_default_avatar_url(merged_id or "0")
    banner_url = _discord_banner_url(merged_id, banner_hash, size=2048)

    status_key, status_label = _resolve_dashboard_user_status(int(merged_id) if merged_id.isdigit() else None)
    accent_color_raw = api_user.get("accent_color")
    accent_hex = ""
    if isinstance(accent_color_raw, int) and accent_color_raw > 0:
        accent_hex = f"#{accent_color_raw:06x}"

    user_tag = f"@{merged_username}"
    if merged_discriminator and merged_discriminator not in {"0", "0000"}:
        user_tag = f"{merged_username}#{merged_discriminator}"

    try:
        login_ts = int((session or {}).get("created_at") or int(time.time()))
    except Exception:
        login_ts = int(time.time())

    return {
        "id": merged_id,
        "username": merged_username,
        "global_name": merged_global_name,
        "display_name": merged_global_name or merged_username,
        "tag": user_tag,
        "status_key": status_key,
        "status_label": status_label,
        "avatar_url": avatar_url,
        "banner_url": banner_url,
        "accent_hex": accent_hex or "#4a78ff",
        "created_at_text": _discord_snowflake_created_at_text(merged_id),
        "dashboard_login_at": _format_datetime_th(
            datetime.datetime.fromtimestamp(
                login_ts,
                tz=datetime.timezone.utc,
            ).astimezone(datetime.timezone(datetime.timedelta(hours=7)))
        ),
    }


def _guild_icon(guild) -> str:
    if getattr(guild, "icon", None):
        return guild.icon.url
    return _discord_default_avatar_url(getattr(guild, "id", "0"))


def _preview_bot_identity() -> tuple[str, str]:
    bot = get_bot()
    bot_user = getattr(bot, "user", None)
    bot_name = str(getattr(bot_user, "name", "") or getattr(BOT_CONFIG, "NAME", "") or "ThunderGod")
    
    avatar_url = ""
    if bot_user:
        disp_avatar = getattr(bot_user, "display_avatar", None)
        if disp_avatar and getattr(disp_avatar, "url", None):
            avatar_url = str(disp_avatar.url).strip()
        if not avatar_url or avatar_url.lower() == "none":
            raw_avatar = getattr(bot_user, "avatar", None)
            if raw_avatar and getattr(raw_avatar, "url", None):
                avatar_url = str(raw_avatar.url).strip()

    if not avatar_url or avatar_url.lower() == "none":
        avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"

    return _escape(bot_name), _escape(avatar_url)


def _preview_member_identity(session: dict[str, Any] | None) -> tuple[str, str]:
    user = (session or {}).get("user") or {}
    member_name = str(
        user.get("global_name")
        or user.get("username")
        or user.get("name")
        or "member"
    ).strip() or "member"
    member_avatar = str(user.get("avatar_url") or "").strip() or "https://cdn.discordapp.com/embed/avatars/1.png"
    return _escape(member_name), _escape(member_avatar)


def _first_env_value(*keys: str) -> str:
    return _dashboard_utils_domain.first_env_value(*keys)


def _with_cache_bust(url: Any, *, bucket_seconds: int = 300) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    if value.startswith("data:"):
        return value
    bucket = max(1, int(bucket_seconds))
    token = int(time.time() // bucket)
    if "#" in value:
        base, fragment = value.split("#", 1)
    else:
        base, fragment = value, ""
    sep = "&" if "?" in base else "?"
    out = f"{base}{sep}v={token}"
    if fragment:
        out = f"{out}#{fragment}"
    return out


def _request_client_ip(request: Request) -> str:
    try:
        forwarded = str(request.headers.get("x-forwarded-for") or "").strip()
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            if candidate:
                return candidate[:120]
    except Exception:
        pass
    try:
        real_ip = str(request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip[:120]
    except Exception:
        pass
    try:
        host = str(getattr(getattr(request, "client", None), "host", "") or "").strip()
        if host:
            return host[:120]
    except Exception:
        pass
    return "unknown"


async def _append_donatebot_verify_log(
    *,
    request: Request,
    session: dict[str, Any] | None,
    gift_link: str,
    donor_name: str,
    donor_discord_id: str = "",
    donor_avatar_url: str = "",
    donor_source: str = "unknown",
    amount: int,
    verify_status: str,
    verify_note: str,
) -> None:
    user = (session or {}).get("user") or {}
    user_id = _session_user_id(session)
    username = _clean_text(user.get("username") or user.get("name") or "").strip()[:80]
    global_name = _clean_text(user.get("global_name") or "").strip()[:80]
    requester_avatar_url = str(user.get("avatar_url") or "").strip()[:1600]
    amount_value = max(0, int(amount or 0))
    donor_id_text = str(donor_discord_id or "").strip()
    if not DONATEBOT_DISCORD_ID_RE.match(donor_id_text):
        donor_id_text = ""
    donor_avatar_text = str(donor_avatar_url or "").strip()
    donor_avatar_is_data = donor_avatar_text.startswith("data:image/")
    donor_avatar_is_http = donor_avatar_text.startswith("https://") or donor_avatar_text.startswith("http://")
    if donor_avatar_text and not (donor_avatar_is_data or donor_avatar_is_http):
        donor_avatar_text = ""
    if donor_avatar_text:
        donor_avatar_text = donor_avatar_text[:220000] if donor_avatar_is_data else donor_avatar_text[:1600]
    donor_source_text = _clean_text(donor_source).strip().lower()[:30] or "unknown"
    try:
        await storage.donatebot_verify_logs.insert(
            source="dashboard_donatebot_verify",
            verify_status=_normalize_donate_slip_status(verify_status),
            verify_note=_clean_text(verify_note).strip()[:500],
            gift_link=str(gift_link or "").strip()[:700],
            donor_name=_clean_text(donor_name).strip()[:80],
            donor_discord_id=donor_id_text,
            donor_avatar_url=donor_avatar_text,
            donor_source=donor_source_text,
            amount=amount_value,
            requester_user_id=user_id,
            requester_username=username,
            requester_global_name=global_name,
            requester_avatar_url=requester_avatar_url,
            requester_is_admin=_is_dashboard_admin(session),
            requester_ip=_request_client_ip(request),
            checked_at=datetime.datetime.now(tz=datetime.timezone.utc),
        )
    except Exception:
        # Logging should never block donate verification flow.
        pass


async def _fetch_donatebot_verify_logs(
    *,
    status_filter: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 60,
) -> tuple[list[dict[str, Any]], int, int]:
    status_key = _normalize_donate_slip_status_filter(status_filter)
    q_text = _clean_text(keyword).strip()[:120]
    safe_page_size = max(10, min(200, int(page_size)))
    safe_page = max(1, int(page))

    query: dict[str, Any] = {}
    if status_key:
        query["verify_status"] = status_key
    if q_text:
        regex_value = re.escape(q_text)
        query["$or"] = [
            {"gift_link": {"$regex": regex_value, "$options": "i"}},
            {"donor_name": {"$regex": regex_value, "$options": "i"}},
            {"donor_discord_id": {"$regex": regex_value, "$options": "i"}},
            {"requester_username": {"$regex": regex_value, "$options": "i"}},
            {"requester_global_name": {"$regex": regex_value, "$options": "i"}},
            {"requester_ip": {"$regex": regex_value, "$options": "i"}},
            {"verify_note": {"$regex": regex_value, "$options": "i"}},
        ]

    collection_name = getattr(
        storage.donatebot_verify_logs,
        "COLLECTION_NAME",
        getattr(storage.donatebot_verify_logs, "CollectionName", "donatebot_verify_logs"),
    )
    collection = await get_collection(collection_name)
    total_count = int(await collection.count_documents(query))
    if total_count <= 0:
        return [], 0, 1

    total_pages = max(1, (total_count + safe_page_size - 1) // safe_page_size)
    safe_page = max(1, min(safe_page, total_pages))
    skip = (safe_page - 1) * safe_page_size
    cursor = collection.find(query).sort([("checked_at", -1), ("id", -1)]).skip(skip).limit(safe_page_size)
    rows = await cursor.to_list(length=safe_page_size)
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            copy = dict(row)
            copy.pop("_id", None)
            cleaned.append(copy)
    return cleaned, total_count, safe_page


def _donatebot_default_avatar_url(seed_value: Any) -> str:
    seed_text = str(seed_value or "0")
    token = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    index = int(token[:2], 16) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{index}.png"


def _donatebot_safe_avatar_url(raw_url: Any, *, seed_value: Any) -> str:
    value = str(raw_url or "").strip()
    if value.startswith("data:image/"):
        return value[:220000]
    if value.startswith("https://") or value.startswith("http://"):
        return value[:1600]
    return _donatebot_default_avatar_url(seed_value)


def _donatebot_display_name(row: dict[str, Any]) -> str:
    donor_name = _clean_text(row.get("donor_name") or "").strip()[:80]
    if donor_name:
        return donor_name
    donor_id = str(row.get("donor_discord_id") or "").strip()
    if DONATEBOT_DISCORD_ID_RE.match(donor_id):
        return f"User {donor_id}"
    requester_name = _clean_text(
        row.get("requester_global_name")
        or row.get("requester_username")
        or ""
    ).strip()[:80]
    if requester_name:
        return requester_name
    return "Unknown donor"


def _donatebot_identity_key(row: dict[str, Any], *, fallback_index: int) -> str:
    donor_id = str(row.get("donor_discord_id") or "").strip()
    if DONATEBOT_DISCORD_ID_RE.match(donor_id):
        return f"discord:{donor_id}"

    requester_user_id = str(row.get("requester_user_id") or "").strip()
    if DONATEBOT_DISCORD_ID_RE.match(requester_user_id):
        return f"discord:{requester_user_id}"

    donor_name = _clean_text(row.get("donor_name") or "").strip().lower()[:80]
    if donor_name:
        return f"name:{donor_name}"
    return f"log:{fallback_index}:{int(row.get('id') or 0)}"


async def _fetch_donatebot_top_donors(
    *,
    limit: int = 10,
    max_scan: int = DONATEBOT_TOP_DONOR_SCAN_LIMIT,
) -> list[dict[str, Any]]:
    safe_limit = max(3, min(50, int(limit or 10)))
    safe_scan = max(120, min(12000, int(max_scan or DONATEBOT_TOP_DONOR_SCAN_LIMIT)))
    collection_name = getattr(
        storage.donatebot_verify_logs,
        "COLLECTION_NAME",
        getattr(storage.donatebot_verify_logs, "CollectionName", "donatebot_verify_logs"),
    )
    try:
        collection = await get_collection(collection_name)
        query = {
            "verify_status": "approved",
            "amount": {"$gt": 0},
        }
        rows = await (
            collection.find(query)
            .sort([("checked_at", -1), ("id", -1)])
            .limit(safe_scan)
            .to_list(length=safe_scan)
        )
    except Exception:
        return []

    grouped: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        try:
            amount_value = max(0, int(row.get("amount") or 0))
        except Exception:
            amount_value = 0
        if amount_value <= 0:
            continue

        identity_key = _donatebot_identity_key(row, fallback_index=index)
        current = grouped.get(identity_key)
        if current is None:
            donor_discord_id = str(row.get("donor_discord_id") or "").strip()
            if not DONATEBOT_DISCORD_ID_RE.match(donor_discord_id):
                donor_discord_id = str(row.get("requester_user_id") or "").strip()
                if not DONATEBOT_DISCORD_ID_RE.match(donor_discord_id):
                    donor_discord_id = ""
            current = {
                "identity_key": identity_key,
                "donor_discord_id": donor_discord_id,
                "display_name": _donatebot_display_name(row),
                "avatar_url": _donatebot_safe_avatar_url(
                    row.get("donor_avatar_url") or row.get("requester_avatar_url"),
                    seed_value=donor_discord_id or identity_key,
                ),
                "amount_total": 0,
                "verify_count": 0,
                "latest_checked_at": row.get("checked_at"),
            }
            grouped[identity_key] = current
        current["amount_total"] = int(current.get("amount_total") or 0) + amount_value
        current["verify_count"] = int(current.get("verify_count") or 0) + 1

    ranking = sorted(
        grouped.values(),
        key=lambda item: (
            int(item.get("amount_total") or 0),
            int(item.get("verify_count") or 0),
            str(item.get("display_name") or ""),
        ),
        reverse=True,
    )

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(ranking[:safe_limit], start=1):
        out.append(
            {
                **row,
                "rank": idx,
            }
        )
    return out


def _bool_from_form(data: dict[str, str], key: str) -> bool:
    return _dashboard_utils_domain.bool_from_form(data, key)


def _int_from_form(data: dict[str, str], key: str, default: int, minimum: int, maximum: int) -> int:
    return _dashboard_utils_domain.int_from_form(data, key, default, minimum, maximum)


def _is_atlas_collection_limit_error(error: Exception) -> bool:
    text = str(error or "").lower()
    return (
        "cannot create a new collection" in text and "500 collections" in text
    ) or ("atlaserror" in text and "8000" in text)


def _normalize_donate_slip_status(raw: Any) -> str:
    return _dashboard_donate_utils.normalize_donate_slip_status(raw)


def _normalize_donate_slip_status_filter(raw: Any) -> str:
    return _dashboard_donate_utils.normalize_donate_slip_status_filter(raw)


def _donate_slip_status_label(status: str) -> str:
    return _dashboard_donate_utils.donate_slip_status_label(status)


def _normalize_donate_slip_log(raw: dict[str, Any]) -> dict[str, Any]:
    return _dashboard_donate_utils.normalize_donate_slip_log(raw)


async def _get_donate_slip_logs(guild_id: int, *, limit: int = 120) -> list[dict[str, Any]]:
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"donate_slip_logs": 1, "_id": 0})
        raw_logs = (doc or {}).get("donate_slip_logs")
        if not isinstance(raw_logs, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw_logs:
            if not isinstance(item, dict):
                continue
            out.append(_normalize_donate_slip_log(item))
        out.sort(key=lambda entry: str(entry.get("created_at") or ""), reverse=True)
        return out[: max(1, min(limit, 300))]
    except Exception:
        return []


async def _append_donate_slip_log(guild_id: int, payload: dict[str, Any], *, keep_limit: int = 200) -> dict[str, Any] | None:
    normalized = _normalize_donate_slip_log(payload)
    try:
        current = await _get_donate_slip_logs(guild_id, limit=keep_limit)
        merged = [normalized]
        seen_ids = {normalized["slip_id"]}
        for row in current:
            sid = str(row.get("slip_id") or "")
            if not sid or sid in seen_ids:
                continue
            merged.append(row)
            seen_ids.add(sid)
            if len(merged) >= keep_limit:
                break
        guilds_col = await get_collection("guilds")
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"donate_slip_logs": merged}},
            upsert=True,
        )
        return normalized
    except Exception:
        return None


async def _update_donate_slip_log_status(
    guild_id: int,
    slip_id: str,
    status: str,
    *,
    reviewer_id: str = "",
    reviewer_name: str = "",
) -> bool:
    target_status = _normalize_donate_slip_status(status)
    target_id = str(slip_id or "").strip()
    if not target_id:
        return False
    try:
        current = await _get_donate_slip_logs(guild_id, limit=300)
        changed = False
        now_iso = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        merged: list[dict[str, Any]] = []
        for row in current:
            if str(row.get("slip_id") or "") == target_id:
                row["status"] = target_status
                row["reviewed_at"] = now_iso
                row["reviewed_by_id"] = str(reviewer_id or "")
                row["reviewed_by_name"] = str(reviewer_name or "")[:120]
                changed = True
            merged.append(_normalize_donate_slip_log(row))
        if not changed:
            return False
        guilds_col = await get_collection("guilds")
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"donate_slip_logs": merged[:200]}},
            upsert=True,
        )
        return True
    except Exception:
        return False


def _safe_upload_name(filename: str | None) -> str:
    raw = str(filename or "").strip()
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", raw) or "upload.png"
    ext = Path(cleaned).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        ext = ".png"
    return f"{uuid.uuid4().hex}{ext}"


def _normalize_alert_entry(entry: dict[str, Any], default_channel: str | None = None) -> dict[str, str] | None:
    source_url = str(entry.get("source_url") or "").strip()
    description = str(entry.get("description") or "").strip()[:400]
    button_text = str(entry.get("button_text") or "ดูรายละเอียด").strip()[:45]
    channel_id = str(entry.get("channel_id") or default_channel or "").strip()
    if not source_url:
        return None
    if channel_id and not channel_id.isdigit():
        channel_id = ""
    return {
        "source_url": source_url[:300],
        "description": description,
        "button_text": button_text,
        "channel_id": channel_id,
    }


def _normalize_alert_entries(raw_entries: Any, *, default_channel: str | None = None, max_items: int = 60) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(raw_entries, (list, tuple)):
        iterable = raw_entries
    elif isinstance(raw_entries, str):
        iterable = [{"source_url": part.strip()} for part in re.split(r"[\n,]+", raw_entries) if part.strip()]
    else:
        iterable = []
    for item in iterable:
        if isinstance(item, str):
            item = {"source_url": item}
        if not isinstance(item, dict):
            continue
        normalized = _normalize_alert_entry(item, default_channel=default_channel)
        if not normalized:
            continue
        duplicate = any(
            prev["source_url"].lower() == normalized["source_url"].lower()
            and prev["channel_id"] == normalized["channel_id"]
            for prev in out
        )
        if duplicate:
            continue
        out.append(normalized)
        if len(out) >= max_items:
            break
    return out


def _default_alerts_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "notify_channel_id": None,
        "mention_role_ids": [],
        "cooldown_seconds": 60,
        "platforms": {
            "twitch": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "tiktok": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "github": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "youtube": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "facebook": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
        },
    }


def _default_verify_pages() -> list[dict[str, Any]]:
    return [
        {
            "title": "แบบฟอร์มยืนยันตัวตน",
            "items": [
                {
                    "label": "ชื่อ-นามสกุล",
                    "placeholder": "กรอกชื่อของคุณ",
                    "description": "ใช้สำหรับยืนยันข้อมูลผู้ใช้",
                    "input_type": "short",
                }
            ],
        }
    ]
def _normalize_verify_pages(
    raw_pages: Any,
    *,
    max_pages: int = 5,
    max_items_per_page: int = 12,
    title_max_length: int = 45,
) -> list[dict[str, Any]]:
    max_pages = max(1, min(int(max_pages or 1), 20))
    max_items_per_page = max(1, min(int(max_items_per_page or 1), 30))
    title_max_length = max(8, min(int(title_max_length or 45), 120))

    pages: list[dict[str, Any]] = []
    iterable = raw_pages if isinstance(raw_pages, list) else []
    for page in iterable:
        if not isinstance(page, dict):
            continue
        title = str(page.get("title") or "").strip()[:title_max_length] or "แบบฟอร์มยืนยันตัวตน"
        raw_items = page.get("items")
        if not isinstance(raw_items, list):
            raw_items = []
        items: list[dict[str, str]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()[:45]
            placeholder = str(item.get("placeholder") or "").strip()[:45]
            description = str(item.get("description") or "").strip()[:45]
            input_type = str(item.get("input_type") or "short").strip().lower()
            if input_type not in {"short", "paragraph"}:
                input_type = "short"
            if not label and not placeholder and not description:
                continue
            items.append(
                {
                    "label": label or "ข้อความ",
                    "placeholder": placeholder,
                    "description": description,
                    "input_type": input_type,
                }
            )
            if len(items) >= max_items_per_page:
                break
        if not items:
            items = [
                {
                    "label": "ข้อความ",
                    "placeholder": "",
                    "description": "",
                    "input_type": "short",
                }
            ]
        pages.append({"title": title, "items": items})
        if len(pages) >= max_pages:
            break

    return pages or _default_verify_pages()


def _normalize_verify_role_ids(raw_value: Any, *, max_items: int = 20) -> list[str]:
    values: list[str] = []
    if isinstance(raw_value, str):
        candidates = re.split(r"[\s,]+", raw_value)
    elif isinstance(raw_value, (list, tuple, set)):
        candidates = [str(item or "").strip() for item in raw_value]
    else:
        candidates = [str(raw_value or "").strip()]

    for candidate in candidates:
        role_id = str(candidate or "").strip()
        if not role_id.isdigit():
            continue
        if role_id in values:
            continue
        values.append(role_id)
        if len(values) >= max_items:
            break
    return values


def _verify_button_style(value: Any) -> discord.ButtonStyle:
    mapping = {
        "green": discord.ButtonStyle.green,
        "blurple": discord.ButtonStyle.blurple,
        "red": discord.ButtonStyle.red,
        "gray": discord.ButtonStyle.gray,
    }
    key = str(value or "green").strip().lower()
    return mapping.get(key, discord.ButtonStyle.green)


def _parse_datetime_local(value: str | None) -> datetime.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _safe_parse_datetime(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return _parse_datetime_local(raw)


def _format_datetime_display(value: Any) -> str:
    dt = _safe_parse_datetime(value)
    if not isinstance(dt, datetime.datetime):
        return "-"
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


def _format_datetime_local(value: Any) -> str:
    if not isinstance(value, datetime.datetime):
        return ""
    try:
        return value.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return ""


def _format_datetime_th(value: Any) -> str:
    if not isinstance(value, datetime.datetime):
        return "-"
    try:
        return value.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


def _format_duration_th(seconds: int) -> str:
    total = max(0, int(seconds or 0))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} ชั่วโมง")
    if minutes:
        parts.append(f"{minutes} นาที")
    if secs or not parts:
        parts.append(f"{secs} วินาที")
    return " ".join(parts)


def _format_audit_timestamp_th(ts: Any) -> str:
    try:
        raw = int(ts or 0)
    except Exception:
        return "-"
    if raw <= 0:
        return "-"
    tz_bkk = datetime.timezone(datetime.timedelta(hours=7))
    dt = datetime.datetime.fromtimestamp(raw, tz=tz_bkk)
    period = "ก่อนเที่ยง" if dt.hour < 12 else "หลังเที่ยง"
    hour_text = str(dt.hour)
    return f"{dt.strftime('%d/%m/%Y')} {hour_text}:{dt.strftime('%M:%S')} {period}"


def _find_redeem_code_data(raw_code: str | None) -> dict[str, Any] | None:
    code = str(raw_code or "").strip()
    if not code:
        return None
    if code in cache.redeem_codes:
        return cache.redeem_codes.get(code)
    lowered = code.lower()
    for existing_code, payload in (cache.redeem_codes or {}).items():
        if str(existing_code).strip().lower() == lowered:
            return payload
    return None


def _normalize_subscription_code(raw_plan: str | None) -> str | None:
    normalized = str(raw_plan or "").strip().lower()
    mapping = {
        "free": "free",
        "silver": "silver_guild_preminum",
        "silver_guild_preminum": "silver_guild_preminum",
        "silver_guild_premium": "silver_guild_preminum",
        "gold": "golden_guild_premium",
        "gole": "golden_guild_premium",
        "golden": "golden_guild_premium",
        "golden_guild_premium": "golden_guild_premium",
        "gole_guild_premium": "golden_guild_premium",
        "diamond": "diamond_guild_premium",
        "diamond_guild_premium": "diamond_guild_premium",
        "permanent": "permanent_guild_premium",
        "lifetime": "permanent_guild_premium",
        "permanent_guild_premium": "permanent_guild_premium",
        "lifetime_guild_premium": "permanent_guild_premium",
    }
    return mapping.get(normalized)


def _premium_table_plan_tiers() -> tuple[str, ...]:
    return tuple(PLAN_ORDER)


def _premium_table_header_row(
    first_column_label: str,
    *,
    first_column_i18n: str | None = None,
    with_i18n: bool = False,
) -> str:
    first_i18n_attr = f' data-i18n="{_escape(first_column_i18n)}"' if (with_i18n and first_column_i18n) else ""
    plan_headers = []
    for tier in _premium_table_plan_tiers():
        label = _plan_display_name(tier)
        i18n_attr = f' data-i18n="plan_{_escape(tier)}"' if with_i18n else ""
        plan_headers.append(f"<th{i18n_attr}>{_escape(label)}</th>")
    return f"<tr><th{first_i18n_attr}>{_escape(first_column_label)}</th>{''.join(plan_headers)}</tr>"


def _premium_row_from_plan_values(
    row_label: str,
    values_by_tier: dict[str, Any],
    *,
    tiers: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    selected_tiers = tiers or _premium_table_plan_tiers()
    return (row_label, *(str(values_by_tier.get(tier, "-")) for tier in selected_tiers))


def _premium_table_rows(
    rows: list[tuple[str, ...]],
    prefix: str,
    *,
    allow_html: bool = False,
    with_i18n: bool = True,
) -> str:
    tiers = _premium_table_plan_tiers()
    rendered_rows: list[str] = []
    for index, row in enumerate(rows):
        if not row:
            continue
        row_label = str(row[0] or "-")
        plan_values = list(row[1:])
        row_name_i18n = f' data-i18n="{prefix}_row_{index}_name"' if with_i18n else ""
        cells = [f"<td{row_name_i18n}>{_escape(row_label)}</td>"]
        for tier_index, tier in enumerate(tiers):
            cell_value = plan_values[tier_index] if tier_index < len(plan_values) else "-"
            cell_markup = str(cell_value if allow_html else _escape(cell_value))
            cell_i18n = f' data-i18n="{prefix}_row_{index}_{tier}"' if with_i18n else ""
            cells.append(f"<td{cell_i18n}>{cell_markup}</td>")
        rendered_rows.append(f"<tr>{''.join(cells)}</tr>")
    return "".join(rendered_rows)


def _plan_enabled_text(required_tier: str, plan_tier: str) -> str:
    return "มี" if _plan_rank(plan_tier) >= _plan_rank(required_tier) else "ไม่มี"


def _plan_punishment_label(allowed: set[str]) -> str:
    if "ban" in allowed:
        return "Mute / Kick / Ban"
    if "kick" in allowed:
        return "Mute / Kick"
    return "Mute"


def _safe_price_float(raw_value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(raw_value)
    except Exception:
        parsed = float(default)
    if parsed < 0:
        parsed = 0.0
    if parsed > 1_000_000:
        parsed = 1_000_000.0
    return round(float(parsed), 2)


def _pricing_quote_from_snapshot(plan_key: str, pricing_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    key = str(plan_key or "free").strip().lower() or "free"
    snapshot = pricing_snapshot if isinstance(pricing_snapshot, dict) else {}
    quotes = snapshot.get("quotes") if isinstance(snapshot.get("quotes"), dict) else {}
    source_quote = quotes.get(key) if isinstance(quotes.get(key), dict) else {}

    if key == _billing_workflow.USER_APP_PLAN_CODE:
        fallback_quote = _billing_workflow.build_user_app_price_quote()
    else:
        fallback_quote = _billing_workflow.build_plan_price_quote(key)
    src = source_quote if isinstance(source_quote, dict) else {}

    base_price = _safe_price_float(src.get("base_price"), _safe_price_float(fallback_quote.get("base_price"), 0.0))
    final_price = _safe_price_float(src.get("final_price"), base_price)
    if final_price > base_price:
        final_price = base_price
    discount_percent = _safe_price_float(src.get("discount_percent"), 0.0)
    promo_active = bool(src.get("promo_active")) and base_price > final_price and discount_percent > 0.0
    if not promo_active:
        discount_percent = 0.0

    merged = dict(fallback_quote)
    merged.update(src)
    merged["key"] = key
    merged["plan_tier"] = str(merged.get("plan_tier") or key).strip().lower() or key
    merged["base_price"] = round(base_price, 2)
    merged["final_price"] = round(final_price, 2)
    merged["discount_percent"] = round(discount_percent, 2)
    merged["promo_active"] = bool(promo_active)
    return merged


def _price_period_suffix(plan_key: str, *, period_style: str = "month") -> str:
    key = str(plan_key or "free").strip().lower()
    if key == "free":
        return " / ตลอดชีพ"
    if key == "permanent":
        return " / ถาวร"
    if period_style == "days":
        return f" / {_billing_workflow.PLAN_DURATION_DAYS} วัน"
    return " / เดือน"


def _price_discount_percent_text(raw_value: Any) -> str:
    percent = _safe_price_float(raw_value, 0.0)
    if abs(percent - round(percent)) < 0.01:
        return f"{int(round(percent))}%"
    return f"{percent:.2f}%"


def _price_text_from_quote(quote: dict[str, Any], *, period_style: str = "month") -> str:
    key = str(quote.get("key") or quote.get("plan_tier") or "free").strip().lower()
    base_price = _safe_price_float(quote.get("base_price"), 0.0)
    final_price = _safe_price_float(quote.get("final_price"), base_price)
    suffix = _price_period_suffix(key, period_style=period_style)
    promo_active = bool(quote.get("promo_active")) and base_price > final_price
    if key == "free" and not promo_active:
        return f"ฟรี{suffix}"
    if promo_active:
        new_price = "ฟรี" if final_price <= 0 else f"{final_price:,.2f} บาท"
        return f"{base_price:,.2f} บาท -> {new_price}{suffix} (ลด {_price_discount_percent_text(quote.get('discount_percent'))})"
    if final_price <= 0:
        return f"ฟรี{suffix}"
    return f"{final_price:,.2f} บาท{suffix}"


def _price_html_from_quote(quote: dict[str, Any], *, period_style: str = "month") -> str:
    key = str(quote.get("key") or quote.get("plan_tier") or "free").strip().lower()
    base_price = _safe_price_float(quote.get("base_price"), 0.0)
    final_price = _safe_price_float(quote.get("final_price"), base_price)
    suffix = _price_period_suffix(key, period_style=period_style)
    promo_active = bool(quote.get("promo_active")) and base_price > final_price
    if key == "free" and not promo_active:
        return f'<span style="font-weight:700;white-space:nowrap;">ฟรี</span><span style="opacity:.86;white-space:nowrap;">{_escape(suffix)}</span>'

    if promo_active:
        old_price_text = f"{base_price:,.2f} บาท"
        new_price_text = "ฟรี" if final_price <= 0 else f"{final_price:,.2f} บาท"
        discount_text = _price_discount_percent_text(quote.get("discount_percent"))
        return (
            f'<span style="text-decoration:line-through;opacity:.62;white-space:nowrap;">{_escape(old_price_text)}</span> '
            f'<span style="font-weight:800;white-space:nowrap;">{_escape(new_price_text)}</span>'
            f'<span style="opacity:.86;white-space:nowrap;">{_escape(suffix)}</span> '
            f'<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;'
            f'background:rgba(16,185,129,.18);border:1px solid rgba(16,185,129,.38);font-size:.72rem;'
            f'font-weight:700;white-space:nowrap;">ลด {_escape(discount_text)}</span>'
        )

    current_price_text = "ฟรี" if final_price <= 0 else f"{final_price:,.2f} บาท"
    return (
        f'<span style="font-weight:700;white-space:nowrap;">{_escape(current_price_text)}</span>'
        f'<span style="opacity:.86;white-space:nowrap;">{_escape(suffix)}</span>'
    )


def _premium_plan_cards_from_live_rules(pricing_snapshot: dict[str, Any] | None = None) -> list[dict[str, str]]:
    rows = [
        ("free", "Free", "เหมาะสำหรับชุมชนที่เพิ่งเริ่ม"),
        ("silver", "Silver", "ปลดล็อกระบบสำคัญและเพิ่มขีดจำกัดหลัก"),
        ("golden", "Gole", "เหมาะกับเซิร์ฟเวอร์ที่ใช้งานหนักและจริงจัง"),
        ("diamond", "Diamond", "ขีดจำกัดสูงสุดและสิทธิ์ครบทุกระบบ"),
        ("permanent", "Permanent", "สิทธิ์ครบทุกระบบ รวมฟีเจอร์พรีเมียมใหม่ในอนาคต"),
    ]
    cards: list[dict[str, str]] = []
    for key, title, desc in rows:
        quote = _pricing_quote_from_snapshot(key, pricing_snapshot)
        cards.append(
            {
                "title": title,
                "price": _price_text_from_quote(quote, period_style="month"),
                "price_html": _price_html_from_quote(quote, period_style="month"),
                "desc": desc,
            }
        )
    return cards

def _premium_feature_rows_from_live_rules() -> list[tuple[str, ...]]:
    tiers = _premium_table_plan_tiers()
    limits = {tier: _plan_limits_by_tier(tier) for tier in tiers}
    levels = {tier: _levels_plan_caps(tier) for tier in tiers}
    antinuke_punishments = {tier: _plan_punishment_label(_allowed_antinuke_punishments({"subscription": tier})) for tier in tiers}
    automod_punishments = {tier: _plan_punishment_label(_allowed_automod_punishments({"subscription": tier})) for tier in tiers}
    support_text = {
        "free": "ไม่มี",
        "silver": "มาตรฐาน",
        "golden": "รวดเร็ว",
        "diamond": "เร่งด่วนสูงสุด",
        "permanent": "เร่งด่วนสูงสุด",
    }
    return [
        _premium_row_from_plan_values("เล่นเพลงผ่านลิงก์", {tier: _plan_enabled_text("silver", tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("ปรับระดับเสียงเริ่มต้น", {tier: _plan_enabled_text("silver", tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("จำนวนบทบาทที่กำหนดเอง", {tier: str(limits[tier]["custom_roles"]) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("จำนวน Auto Responder", {tier: str(limits[tier]["auto_responders"]) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("จำนวนบทบาทต้อนรับอัตโนมัติ", {tier: str(limits[tier]["autoroles"]) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("จำนวนห้องสถิติ (Server Stats)", {tier: str(limits[tier]["server_stats_channels"]) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("โหมด Anti-Nuke ขั้นสูง (Custom)", {tier: _plan_enabled_text("silver", tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("บทลงโทษ Anti-Nuke สูงสุด", {tier: antinuke_punishments[tier] for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("โหมด AutoMod ขั้นสูง (Custom)", {tier: _plan_enabled_text("silver", tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("บทลงโทษ AutoMod สูงสุด", {tier: automod_punishments[tier] for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("ระบบเลเวล", {tier: ("มี" if levels[tier]["can_use"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("เลเวลจากเสียง", {tier: ("มี" if levels[tier]["voice_xp"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("เลเวลจากรีแอคชัน", {tier: ("มี" if levels[tier]["reaction_xp"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("จำนวนรางวัลเลเวลสูงสุด", {tier: str(levels[tier]["max_rewards"]) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("ระดับการซัพพอร์ต", {tier: support_text.get(tier, "-") for tier in tiers}, tiers=tiers),
    ]


def _premium_command_rows_from_live_rules() -> list[tuple[str, ...]]:
    tiers = _premium_table_plan_tiers()
    limits = {tier: _plan_limits_by_tier(tier) for tier in tiers}
    levels = {tier: _levels_plan_caps(tier) for tier in tiers}
    return [
        _premium_row_from_plan_values(
            "/music play",
            {tier: ("ค้นหา+ลิงก์" if _is_plan_at_least(tier, "silver") else "ค้นหาได้ (ลิงก์ไม่ได้)") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values("/music queue", {tier: "มี" for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values(
            "/music settings",
            {tier: ("แก้ไขได้" if _is_plan_at_least(tier, "silver") else "ดูได้อย่างเดียว") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values("/customrole add", {tier: f"{limits[tier]['custom_roles']} บทบาท" for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/autoresponder add", {tier: f"{limits[tier]['auto_responders']} รายการ" for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/setup antinuke custom", {tier: _plan_enabled_text("silver", tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/setup automod custom", {tier: _plan_enabled_text("silver", tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/levels", {tier: ("มี" if levels[tier]["can_use"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/levels source voice", {tier: ("มี" if levels[tier]["voice_xp"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/levels source reaction", {tier: ("มี" if levels[tier]["reaction_xp"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/premium server", {tier: "มี" for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("/redeem", {tier: "มี" for tier in tiers}, tiers=tiers),
    ]


def _donation_support_rows_from_live_rules(pricing_snapshot: dict[str, Any] | None = None) -> list[tuple[str, ...]]:
    tiers = _premium_table_plan_tiers()
    limits = {tier: _plan_limits_by_tier(tier) for tier in tiers}
    levels = {tier: _levels_plan_caps(tier) for tier in tiers}

    def _plan_price_label(plan_tier: str) -> str:
        normalized_tier = _normalize_plan_tier(plan_tier)
        quote = _pricing_quote_from_snapshot(normalized_tier, pricing_snapshot)
        return _price_html_from_quote(quote, period_style="days")

    return [
        _premium_row_from_plan_values("แพ็กเกจที่ได้รับ", {tier: _plan_display_name(tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("ราคาสนับสนุน", {tier: _plan_price_label(tier) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values(
            "ต่ออายุอัตโนมัติ",
            {
                tier: ("ไม่ต้องต่ออายุ" if tier == "free" else ("ปิด (ถาวร)" if tier == "permanent" else "เปิด"))
                for tier in tiers
            },
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "จำนวนสินค้า Shop สูงสุด",
            {tier: str(int(_shop_workflow.product_limit_for_plan(tier))) for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "ชำระด้วย TrueMoney Gift",
            {tier: ("มี" if _shop_workflow.is_shop_feature_allowed(tier, "payment_truemoney_gift") else "ไม่มี") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "ชำระด้วย SHIPOK / SlipOK",
            {tier: ("มี" if _shop_workflow.is_shop_feature_allowed(tier, "payment_shipok") else "ไม่มี") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "ตรวจสลิปอัตโนมัติ",
            {tier: ("มี" if _shop_workflow.is_shop_feature_allowed(tier, "auto_verify") else "ไม่มี") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "ส่งของอัตโนมัติ (Auto Delivery)",
            {tier: ("มี" if _shop_workflow.is_shop_feature_allowed(tier, "auto_delivery") else "ไม่มี") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "ส่งสินค้าแบบ DM/Text",
            {tier: ("มี" if _shop_workflow.is_shop_feature_allowed(tier, "delivery_dm_text") else "ไม่มี") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "ส่งสินค้าแบบ Role",
            {tier: ("มี" if _shop_workflow.is_shop_feature_allowed(tier, "delivery_role") else "ไม่มี") for tier in tiers},
            tiers=tiers,
        ),
        _premium_row_from_plan_values(
            "เปิด Ticket อัตโนมัติเมื่อส่งไม่สำเร็จ",
            {
                tier: (
                    "มี"
                    if _shop_workflow.is_shop_feature_allowed(tier, "auto_open_failed_delivery_ticket")
                    else "ไม่มี"
                )
                for tier in tiers
            },
            tiers=tiers,
        ),
        _premium_row_from_plan_values("ขีดจำกัด Custom Roles", {tier: str(limits[tier]["custom_roles"]) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("ขีดจำกัด Auto Responder", {tier: str(limits[tier]["auto_responders"]) for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("ระบบเลเวล", {tier: ("มี" if levels[tier]["can_use"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("เลเวลจากเสียง", {tier: ("มี" if levels[tier]["voice_xp"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("เลเวลจากรีแอคชัน", {tier: ("มี" if levels[tier]["reaction_xp"] else "ไม่มี") for tier in tiers}, tiers=tiers),
        _premium_row_from_plan_values("จำนวนรางวัลเลเวลสูงสุด", {tier: str(levels[tier]["max_rewards"]) for tier in tiers}, tiers=tiers),
    ]

def _premium_cards_markup(pricing_snapshot: dict[str, Any] | None = None) -> str:
    cards = []
    for card in _premium_plan_cards_from_live_rules(pricing_snapshot):
        price_markup = card.get("price_html") or _escape(str(card.get("price") or "-"))
        cards.append(
            "<div class=\"price-card\">"
            f"<h3>{_escape(card['title'])}</h3>"
            f"<p class=\"price\">{price_markup}</p>"
            f"<p>{_escape(card['desc'])}</p>"
            "</div>"
        )
    return "".join(cards)

def _parse_trusted_server_order(raw: str | None) -> list[str]:
    return _dashboard_utils_domain.parse_trusted_server_order(raw)


def _parse_guild_id_list(raw: str | None, *, max_items: int = 200) -> list[str]:
    return _dashboard_utils_domain.parse_guild_id_list(raw, max_items=max_items)


def _parse_command_name_list(raw: str | None, *, max_items: int = 400) -> list[str]:
    return _dashboard_utils_domain.parse_command_name_list(raw, max_items=max_items)


def _parse_tab_slug_list(raw: str | None, *, max_items: int = 100) -> list[str]:
    return _dashboard_utils_domain.parse_tab_slug_list(
        raw,
        allowed_tabs=OWNERBOT_HIDEABLE_TABS,
        max_items=max_items,
    )


def _parse_dashboard_tab_required_plan_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    allowed_tabs = set(OWNERBOT_HIDEABLE_TABS)
    out: dict[str, str] = {}
    for raw_slug, raw_tier in raw.items():
        slug = str(raw_slug or "").strip().lower()
        if not slug or slug not in allowed_tabs:
            continue
        tier = _normalize_plan_tier(raw_tier)
        if tier not in DASHBOARD_TAB_REQUIRED_PLAN_TIERS:
            tier = "free"
        # Donate dashboard must remain available on Free plan.
        if slug == "donate":
            tier = "free"
        out[slug] = tier
    return out


def _guild_growth_events(bot: Any) -> list[dict[str, int]]:
    if not bot:
        return []
    current_count = int(len(getattr(bot, "guilds", []) or []))
    current_ceiling = max(0, current_count)
    raw_events = guild_growth.get_history(current_count=current_count)
    events: list[dict[str, int]] = []
    for item in list(raw_events or []):
        try:
            ts = int(item.get("ts") or 0)
            count = max(0, int(item.get("count") or 0))
        except Exception:
            continue
        if ts <= 0:
            continue
        # Guard against stale/cross-instance snapshots stored in shared config.
        if current_ceiling > 0:
            count = min(count, current_ceiling)
        events.append({"ts": ts, "count": count})
    events.sort(key=lambda x: int(x["ts"]))
    normalized_events: list[dict[str, int]] = []
    for event in events:
        if normalized_events and int(normalized_events[-1]["ts"]) == int(event["ts"]):
            normalized_events[-1] = event
        else:
            normalized_events.append(event)

    join_times: list[datetime.datetime] = []
    for guild in list(getattr(bot, "guilds", []) or []):
        joined = getattr(getattr(guild, "me", None), "joined_at", None)
        if not isinstance(joined, datetime.datetime):
            continue
        if joined.tzinfo is None:
            joined = joined.replace(tzinfo=datetime.timezone.utc)
        join_times.append(joined.astimezone(datetime.timezone.utc))

    join_times.sort()
    rebuilt: list[dict[str, int]] = []
    running_count = 0
    for joined in join_times:
        running_count += 1
        rebuilt.append({"ts": int(joined.timestamp() * 1000), "count": running_count})

    # If saved history is too sparse (for example only latest snapshot),
    # merge with rebuilt join history so week/month/year/all periods are truly different.
    merged = rebuilt + normalized_events
    if not merged:
        now_ms = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)
        return [{"ts": now_ms, "count": current_count}]

    merged.sort(key=lambda x: int(x["ts"]))
    compact: list[dict[str, int]] = []
    for event in merged:
        if compact and int(compact[-1]["ts"]) == int(event["ts"]):
            compact[-1] = event
        else:
            compact.append(event)

    has_variation = len({int(item.get("count", 0)) for item in compact}) > 1
    if not has_variation and rebuilt:
        compact = rebuilt

    return compact


async def _landing_plan_pricing_snapshot_cached() -> dict[str, Any]:
    now = time.time()
    expires_at = float(_LANDING_PLAN_PRICING_SNAPSHOT_CACHE.get("expires_at") or 0.0)
    cached_snapshot = _LANDING_PLAN_PRICING_SNAPSHOT_CACHE.get("snapshot")
    if isinstance(cached_snapshot, dict) and expires_at > now:
        return cached_snapshot
    try:
        snapshot = await _billing_workflow.get_plan_pricing_snapshot()
    except Exception:
        snapshot = _billing_workflow.build_plan_pricing_snapshot_from_settings({})
    _LANDING_PLAN_PRICING_SNAPSHOT_CACHE["snapshot"] = snapshot
    _LANDING_PLAN_PRICING_SNAPSHOT_CACHE["expires_at"] = now + LANDING_PLAN_PRICING_CACHE_TTL_SECONDS
    return snapshot


def _invalidate_landing_plan_pricing_snapshot_cache() -> None:
    _LANDING_PLAN_PRICING_SNAPSHOT_CACHE["expires_at"] = 0.0
    _LANDING_PLAN_PRICING_SNAPSHOT_CACHE["snapshot"] = None


def _default_ownerbot_runtime_settings() -> dict[str, Any]:
    return _dashboard_ownerbot_domain.default_ownerbot_runtime_settings(
        ai_provider=os.getenv("AI_PROVIDER", "opentyphoon"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        google_model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b-instruct"),
        opentyphoon_model=os.getenv("OPENTYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct"),
        chindax_model=os.getenv("CHINDAX_MODEL", "accounts/fireworks/models/gpt-oss-20b"),
        aiforthai_model=os.getenv("AIFORTHAI_MODEL", "aiforthai-chat"),
        cloudflare_model=os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.1-8b-instruct"),
        thaillm_model=os.getenv("THAILLM_MODEL", "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2"),
        default_dashboard_tab_new_badges=DASHBOARD_TAB_NEW_BADGES_DEFAULT,
    )

def _normalize_ownerbot_runtime_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    return _dashboard_ownerbot_domain.normalize_ownerbot_runtime_settings(
        payload,
        default_factory=_default_ownerbot_runtime_settings,
        parse_guild_id_list=_parse_guild_id_list,
        parse_command_name_list=_parse_command_name_list,
        parse_tab_slug_list=_parse_tab_slug_list,
        parse_dashboard_tab_required_plan_map=_parse_dashboard_tab_required_plan_map,
        parse_developer_social_links=_parse_developer_social_links,
    )

def _ownerbot_runtime_from_db() -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(OWNERBOT_RUNTIME_CONFIG_KEY, "") or "").strip()
    return _dashboard_ownerbot_domain.ownerbot_runtime_from_cache(
        raw,
        default_factory=_default_ownerbot_runtime_settings,
        normalize_settings=_normalize_ownerbot_runtime_settings,
    )

def _default_ownerbot_upload_channel_settings() -> dict[str, Any]:
    return {
        "storage_guild_id": "",
        "channels": {key: "" for key in OWNERBOT_UPLOAD_TARGETS},
    }


def _normalize_ownerbot_upload_channel_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_ownerbot_upload_channel_settings()
    storage_guild_id = str(src.get("storage_guild_id") or "").strip()
    out["storage_guild_id"] = storage_guild_id if storage_guild_id.isdigit() else ""
    raw_channels = src.get("channels")
    channels_map = raw_channels if isinstance(raw_channels, dict) else {}
    for target in OWNERBOT_UPLOAD_TARGETS:
        raw_value = channels_map.get(target)
        if raw_value in (None, ""):
            raw_value = src.get(f"channel_{target}")
        if raw_value in (None, ""):
            raw_value = src.get(target)
        channel_id = str(raw_value or "").strip()
        out["channels"][target] = channel_id if channel_id.isdigit() else ""
    return out


def _ownerbot_upload_channel_settings_from_db() -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(OWNERBOT_UPLOAD_CHANNELS_CONFIG_KEY, "") or "").strip()
    if not raw:
        return _default_ownerbot_upload_channel_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_ownerbot_upload_channel_settings()
    return _normalize_ownerbot_upload_channel_settings(decoded if isinstance(decoded, dict) else {})


def _default_ownerbot_payment_provider_settings() -> dict[str, Any]:
    promptpay_number = (
        str(os.getenv("BOT_TOPUP_PROMPTPAY_NUMBER", "") or "").strip()
        or str(os.getenv("DONATEBOT_PROMPTPAY_NUMBER", "") or "").strip()
        or str(os.getenv("PROMPTPAY_NUMBER", "") or "").strip()
    )
    promptpay_account_name = str(
        os.getenv(
            "BOT_PROMPTPAY_ACCOUNT_NAME",
            os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NAME", ""),
        )
        or ""
    ).strip()
    truemoney_phone = (
        str(os.getenv("BOT_TOPUP_TRUEMONEY_PHONE", "") or "").strip()
        or str(os.getenv("DONATEBOT_TRUEMONEY_PHONE", "") or "").strip()
        or str(os.getenv("TRUEMONEY_PHONE", "") or "").strip()
        or "0889463459"
    )
    truemoney_gift_phone = str(os.getenv("BOT_TRUEMONEY_GIFT_PHONE", "") or "").strip()
    webhook_secret = str(os.getenv("BOT_PAYMENT_WEBHOOK_SECRET", "") or "").strip()
    bank_topup_verification_mode = str(os.getenv("BOT_BANK_TOPUP_VERIFICATION_MODE", "manual_slip") or "manual_slip").strip().lower()
    if bank_topup_verification_mode not in OWNERBOT_BANK_VERIFICATION_MODES:
        bank_topup_verification_mode = "manual_slip"
    bank_donate_verification_mode = str(
        os.getenv("BOT_BANK_DONATE_VERIFICATION_MODE", bank_topup_verification_mode) or bank_topup_verification_mode
    ).strip().lower()
    if bank_donate_verification_mode not in OWNERBOT_BANK_VERIFICATION_MODES:
        bank_donate_verification_mode = bank_topup_verification_mode
    return {
        "topup_provider": str(os.getenv("BOT_TOPUP_PROVIDER", "promptpay") or "promptpay").strip().lower(),
        "donate_provider": str(os.getenv("BOT_DONATE_PROVIDER", "promptpay") or "promptpay").strip().lower(),
        "enable_bank_provider": str(os.getenv("BOT_ENABLE_BANK_PROVIDER", "true") or "true").strip().lower() not in {"0", "false", "off", "no"},
        "enable_gateway_provider": str(os.getenv("BOT_ENABLE_GATEWAY_PROVIDER", "true") or "true").strip().lower() not in {"0", "false", "off", "no"},
        "enable_stripe_provider": str(os.getenv("BOT_ENABLE_STRIPE_PROVIDER", "true") or "true").strip().lower() not in {"0", "false", "off", "no"},
        "enable_truemoney_qr_provider": str(os.getenv("BOT_ENABLE_TRUEMONEY_QR_PROVIDER", "true") or "true").strip().lower() not in {"0", "false", "off", "no"},
        "promptpay_account_name": promptpay_account_name,
        "promptpay_number": promptpay_number,
        "truemoney_phone": truemoney_phone,
        "truemoney_gift_phone": truemoney_gift_phone,
        "truemoney_gift_url": str(os.getenv("BOT_TRUEMONEY_GIFT_URL", "") or "").strip(),
        "bank_topup_verification_mode": bank_topup_verification_mode,
        "bank_donate_verification_mode": bank_donate_verification_mode,
        "bank_name": str(os.getenv("BOT_PAYMENT_BANK_NAME", "") or "").strip(),
        "bank_account_name": str(os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NAME", "") or "").strip(),
        "bank_account_number": str(os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NUMBER", "") or "").strip(),
        "gateway_name": str(os.getenv("BOT_PAYMENT_GATEWAY_NAME", "") or "").strip(),
        "webhook_secret": webhook_secret,
        "gateway_webhook_secret": (
            str(os.getenv("BOT_PAYMENT_GATEWAY_WEBHOOK_SECRET", "") or "").strip()
            or webhook_secret
        ),
        "gateway_signature_header": (
            str(os.getenv("BOT_PAYMENT_GATEWAY_SIGNATURE_HEADER", "") or "").strip()
            or "x-gateway-signature"
        ),
        "gateway_signature_prefix": str(os.getenv("BOT_PAYMENT_GATEWAY_SIGNATURE_PREFIX", "") or "").strip(),
        "gateway_signature_algorithm": (
            str(os.getenv("BOT_PAYMENT_GATEWAY_SIGNATURE_ALGORITHM", "sha256") or "sha256").strip().lower()
        ),
        "gateway_metadata_session_key_field": (
            str(os.getenv("BOT_PAYMENT_GATEWAY_SESSION_FIELD", "metadata.session_key") or "metadata.session_key").strip()
        ),
        "stripe_secret_key": (
            str(os.getenv("BOT_STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY", "")) or "").strip()
        ),
        "stripe_publishable_key": (
            str(os.getenv("BOT_STRIPE_PUBLISHABLE_KEY", os.getenv("STRIPE_PUBLISHABLE_KEY", "")) or "").strip()
        ),
        "stripe_webhook_secret": (
            str(os.getenv("BOT_STRIPE_WEBHOOK_SECRET", "") or "").strip()
            or webhook_secret
        ),
        "stripe_signature_header": (
            str(os.getenv("BOT_STRIPE_SIGNATURE_HEADER", "stripe-signature") or "stripe-signature").strip().lower()
            or "stripe-signature"
        ),
        "stripe_signature_tolerance_seconds": str(
            os.getenv("BOT_STRIPE_SIGNATURE_TOLERANCE_SECONDS", "300") or "300"
        ).strip(),
        "stripe_api_base_url": (
            str(os.getenv("BOT_STRIPE_API_BASE_URL", "https://api.stripe.com") or "https://api.stripe.com").strip()
            or "https://api.stripe.com"
        ),
        "stripe_checkout_session_url": (
            str(
                os.getenv(
                    "BOT_STRIPE_CHECKOUT_SESSION_URL",
                    "https://api.stripe.com/v1/checkout/sessions",
                )
                or "https://api.stripe.com/v1/checkout/sessions"
            ).strip()
        ),
        "stripe_inquiry_url": (
            str(
                os.getenv(
                    "BOT_STRIPE_INQUIRY_URL",
                    "https://api.stripe.com/v1/checkout/sessions",
                )
                or "https://api.stripe.com/v1/checkout/sessions"
            ).strip()
        ),
        "stripe_success_url": str(os.getenv("BOT_STRIPE_SUCCESS_URL", "") or "").strip(),
        "stripe_cancel_url": str(os.getenv("BOT_STRIPE_CANCEL_URL", "") or "").strip(),
        "stripe_auto_verify": str(os.getenv("BOT_STRIPE_AUTO_VERIFY", "true") or "true").strip().lower() not in {"0", "false", "off", "no"},
        "truemoney_create_payment_url": str(os.getenv("BOT_TRUEMONEY_CREATE_PAYMENT_URL", "") or "").strip(),
        "truemoney_inquiry_url": str(os.getenv("BOT_TRUEMONEY_INQUIRY_URL", "") or "").strip(),
        "truemoney_api_key": str(os.getenv("BOT_TRUEMONEY_API_KEY", "") or "").strip(),
        "truemoney_api_secret": str(os.getenv("BOT_TRUEMONEY_API_SECRET", "") or "").strip(),
        "truemoney_bearer_token": str(os.getenv("BOT_TRUEMONEY_BEARER_TOKEN", "") or "").strip(),
        "truemoney_callback_url": str(os.getenv("BOT_TRUEMONEY_CALLBACK_URL", "") or "").strip(),
        "truemoney_webhook_secret": (
            str(os.getenv("BOT_TRUEMONEY_WEBHOOK_SECRET", "") or "").strip()
            or webhook_secret
        ),
        "truemoney_signature_header": (
            str(os.getenv("BOT_TRUEMONEY_SIGNATURE_HEADER", "x-truemoney-signature") or "x-truemoney-signature").strip().lower()
            or "x-truemoney-signature"
        ),
        "truemoney_signature_prefix": str(os.getenv("BOT_TRUEMONEY_SIGNATURE_PREFIX", "") or "").strip(),
        "truemoney_signature_algorithm": (
            str(os.getenv("BOT_TRUEMONEY_SIGNATURE_ALGORITHM", "sha256") or "sha256").strip().lower()
        ),
        "truemoney_amount_field": str(os.getenv("BOT_TRUEMONEY_AMOUNT_FIELD", "amount") or "amount").strip(),
        "truemoney_currency_field": str(os.getenv("BOT_TRUEMONEY_CURRENCY_FIELD", "currency") or "currency").strip(),
        "truemoney_reference_field": str(os.getenv("BOT_TRUEMONEY_REFERENCE_FIELD", "reference") or "reference").strip(),
        "truemoney_callback_field": str(os.getenv("BOT_TRUEMONEY_CALLBACK_FIELD", "callbackUrl") or "callbackUrl").strip(),
        "truemoney_qr_image_field": str(os.getenv("BOT_TRUEMONEY_QR_IMAGE_FIELD", "data.qrImageUrl") or "data.qrImageUrl").strip(),
        "truemoney_qr_code_field": str(os.getenv("BOT_TRUEMONEY_QR_CODE_FIELD", "data.qrRawData") or "data.qrRawData").strip(),
        "truemoney_payment_url_field": str(os.getenv("BOT_TRUEMONEY_PAYMENT_URL_FIELD", "data.paymentUrl") or "data.paymentUrl").strip(),
        "truemoney_reference_resp_field": str(os.getenv("BOT_TRUEMONEY_REFERENCE_RESP_FIELD", "data.orderId") or "data.orderId").strip(),
        "truemoney_transaction_id_field": str(os.getenv("BOT_TRUEMONEY_TRANSACTION_ID_FIELD", "data.transactionId") or "data.transactionId").strip(),
        "truemoney_inquiry_status_field": str(os.getenv("BOT_TRUEMONEY_INQUIRY_STATUS_FIELD", "data.status") or "data.status").strip(),
        "truemoney_paid_status_values": str(
            os.getenv("BOT_TRUEMONEY_PAID_STATUS_VALUES", "paid,success,completed,settled")
            or "paid,success,completed,settled"
        ).strip(),
        "truemoney_auto_verify": str(os.getenv("BOT_TRUEMONEY_AUTO_VERIFY", "true") or "true").strip().lower() not in {"0", "false", "off", "no"},
        "slipok_api_url": (
            str(
                os.getenv(
                    "BOT_SLIPOK_API_URL",
                    os.getenv("SLIPOK_API_URL", "https://api.slipok.com/api/line/apikey/1150"),
                )
                or "https://api.slipok.com/api/line/apikey/1150"
            ).strip()
            or "https://api.slipok.com/api/line/apikey/1150"
        ),
        "slipok_key": str(os.getenv("BOT_SLIPOK_KEY", os.getenv("SLIPOK_KEY", "")) or "").strip(),
        "slipcheck_verify_engine": str(os.getenv("BOT_SLIPCHECK_VERIFY_ENGINE", "slipok") or "slipok").strip().lower(),
        "slipcheck_expected_receiver_name": str(
            os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_NAME", os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NAME", "")) or ""
        ).strip(),
        "slipcheck_expected_receiver_first_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_FIRST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_receiver_last_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_LAST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_receiver_first_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_FIRST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_receiver_last_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_LAST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_receiver_bank": str(
            os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_BANK", os.getenv("BOT_PAYMENT_BANK_NAME", "")) or ""
        ).strip(),
        "slipcheck_expected_receiver_account": str(
            os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_ACCOUNT", os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NUMBER", "")) or ""
        ).strip(),
        "slipcheck_expected_sender_name": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_NAME", "") or "").strip(),
        "slipcheck_expected_sender_first_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_FIRST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_sender_last_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_LAST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_sender_first_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_FIRST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_sender_last_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_LAST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_sender_bank": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_BANK", "") or "").strip(),
        "slipcheck_expected_sender_account": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_ACCOUNT", "") or "").strip(),
        "slipcheck_expected_reference": str(os.getenv("BOT_SLIPCHECK_EXPECTED_REFERENCE", "") or "").strip(),
        "slipcheck_expected_qr_reference": str(os.getenv("BOT_SLIPCHECK_EXPECTED_QR_REFERENCE", "") or "").strip(),
        "slipcheck_max_age_minutes": str(os.getenv("BOT_SLIPCHECK_MAX_AGE_MINUTES", "1440") or "1440").strip(),
        "slipcheck_auto_approve_confidence": str(os.getenv("BOT_SLIPCHECK_AUTO_APPROVE_CONFIDENCE", "85") or "85").strip(),
        "slipcheck_manual_review_confidence": str(os.getenv("BOT_SLIPCHECK_MANUAL_REVIEW_CONFIDENCE", "55") or "55").strip(),
        "slipcheck_duplicate_window_hours": str(os.getenv("BOT_SLIPCHECK_DUPLICATE_WINDOW_HOURS", "72") or "72").strip(),
        "slipcheck_review_channel_id": str(os.getenv("BOT_SLIPCHECK_REVIEW_CHANNEL_ID", "") or "").strip(),
        "slipcheck_review_dm_user_ids": str(os.getenv("BOT_SLIPCHECK_REVIEW_DM_USER_IDS", "") or "").strip(),
        "slipcheck_low_confidence_route": str(
            os.getenv("BOT_SLIPCHECK_LOW_CONFIDENCE_ROUTE", "both") or "both"
        ).strip().lower(),
    }


def _normalize_ownerbot_payment_provider_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_ownerbot_payment_provider_settings()

    def _norm_provider(value: Any, fallback: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"stripe_checkout", "stripecheckout", "stp"}:
            normalized = "stripe"
        fallback_norm = str(fallback or "promptpay").strip().lower()
        if fallback_norm in {"stripe_checkout", "stripecheckout", "stp"}:
            fallback_norm = "stripe"
        if fallback_norm not in OWNERBOT_PAYMENT_PROVIDER_TYPES:
            fallback_norm = "promptpay"
        return normalized if normalized in OWNERBOT_PAYMENT_PROVIDER_TYPES else fallback_norm

    def _truthy(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if not text:
            return default
        if text in {"1", "true", "yes", "on", "y"}:
            return True
        if text in {"0", "false", "no", "off", "n"}:
            return False
        return default

    out["topup_provider"] = _norm_provider(src.get("topup_provider"), "promptpay")
    out["donate_provider"] = _norm_provider(src.get("donate_provider"), "promptpay")
    out["enable_bank_provider"] = _truthy(
        src.get("enable_bank_provider"),
        _truthy(out.get("enable_bank_provider"), True),
    )
    out["enable_gateway_provider"] = _truthy(
        src.get("enable_gateway_provider"),
        _truthy(out.get("enable_gateway_provider"), True),
    )
    out["enable_stripe_provider"] = _truthy(
        src.get("enable_stripe_provider"),
        _truthy(out.get("enable_stripe_provider"), True),
    )
    out["enable_truemoney_qr_provider"] = _truthy(
        src.get("enable_truemoney_qr_provider"),
        _truthy(out.get("enable_truemoney_qr_provider"), True),
    )
    bank_topup_mode = str(src.get("bank_topup_verification_mode") or out.get("bank_topup_verification_mode") or "manual_slip").strip().lower()
    out["bank_topup_verification_mode"] = (
        bank_topup_mode
        if bank_topup_mode in OWNERBOT_BANK_VERIFICATION_MODES
        else "manual_slip"
    )
    bank_donate_mode = str(src.get("bank_donate_verification_mode") or out.get("bank_donate_verification_mode") or out["bank_topup_verification_mode"]).strip().lower()
    out["bank_donate_verification_mode"] = (
        bank_donate_mode
        if bank_donate_mode in OWNERBOT_BANK_VERIFICATION_MODES
        else out["bank_topup_verification_mode"]
    )

    promptpay_number = "".join(ch for ch in str(src.get("promptpay_number") or out.get("promptpay_number") or "").strip() if ch.isdigit())
    out["promptpay_number"] = promptpay_number[:20]
    out["promptpay_account_name"] = str(
        src.get("promptpay_account_name")
        or out.get("promptpay_account_name")
        or ""
    ).strip()[:120]

    truemoney_phone = "".join(ch for ch in str(src.get("truemoney_phone") or out.get("truemoney_phone") or "").strip() if ch.isdigit())
    out["truemoney_phone"] = truemoney_phone[:20]
    truemoney_gift_phone = "".join(
        ch
        for ch in str(
            src.get("truemoney_gift_phone")
            or out.get("truemoney_gift_phone")
            or ""
        ).strip()
        if ch.isdigit()
    )[:20]
    out["truemoney_gift_phone"] = truemoney_gift_phone
    out["truemoney_gift_url"] = str(
        src.get("truemoney_gift_url")
        or out.get("truemoney_gift_url")
        or ""
    ).strip()[:500]

    out["bank_name"] = str(src.get("bank_name") or "").strip()[:120]
    out["bank_account_name"] = str(src.get("bank_account_name") or "").strip()[:120]
    out["bank_account_number"] = str(src.get("bank_account_number") or "").strip()[:80]
    out["gateway_name"] = str(src.get("gateway_name") or "").strip()[:120]

    out["webhook_secret"] = str(src.get("webhook_secret") or "").strip()[:240]
    out["gateway_webhook_secret"] = (
        str(src.get("gateway_webhook_secret") or "").strip()[:240]
        or out["webhook_secret"]
    )

    signature_header = str(src.get("gateway_signature_header") or "").strip().lower()
    out["gateway_signature_header"] = signature_header[:80] or "x-gateway-signature"
    out["gateway_signature_prefix"] = str(src.get("gateway_signature_prefix") or "").strip()[:24]

    algorithm = str(src.get("gateway_signature_algorithm") or "").strip().lower()
    out["gateway_signature_algorithm"] = algorithm if algorithm in {"sha256", "sha1", "md5"} else "sha256"

    session_field = str(src.get("gateway_metadata_session_key_field") or "").strip()[:120]
    out["gateway_metadata_session_key_field"] = session_field or "metadata.session_key"
    out["stripe_secret_key"] = str(src.get("stripe_secret_key") or out.get("stripe_secret_key") or "").strip()[:240]
    out["stripe_publishable_key"] = str(src.get("stripe_publishable_key") or out.get("stripe_publishable_key") or "").strip()[:240]
    out["stripe_webhook_secret"] = (
        str(src.get("stripe_webhook_secret") or out.get("stripe_webhook_secret") or "").strip()[:240]
        or out["webhook_secret"]
    )
    stripe_sig_header = str(src.get("stripe_signature_header") or out.get("stripe_signature_header") or "").strip().lower()
    out["stripe_signature_header"] = stripe_sig_header[:80] or "stripe-signature"
    stripe_tolerance_raw = str(
        src.get("stripe_signature_tolerance_seconds")
        or out.get("stripe_signature_tolerance_seconds")
        or "300"
    ).strip()
    try:
        stripe_tolerance = int(float(stripe_tolerance_raw or "300"))
    except Exception:
        stripe_tolerance = 300
    out["stripe_signature_tolerance_seconds"] = str(max(30, min(3600, stripe_tolerance)))
    out["stripe_api_base_url"] = str(src.get("stripe_api_base_url") or out.get("stripe_api_base_url") or "https://api.stripe.com").strip()[:280] or "https://api.stripe.com"
    out["stripe_checkout_session_url"] = str(
        src.get("stripe_checkout_session_url")
        or out.get("stripe_checkout_session_url")
        or "https://api.stripe.com/v1/checkout/sessions"
    ).strip()[:280] or "https://api.stripe.com/v1/checkout/sessions"
    out["stripe_inquiry_url"] = str(
        src.get("stripe_inquiry_url")
        or out.get("stripe_inquiry_url")
        or "https://api.stripe.com/v1/checkout/sessions"
    ).strip()[:280] or "https://api.stripe.com/v1/checkout/sessions"
    out["stripe_success_url"] = str(src.get("stripe_success_url") or out.get("stripe_success_url") or "").strip()[:255]
    out["stripe_cancel_url"] = str(src.get("stripe_cancel_url") or out.get("stripe_cancel_url") or "").strip()[:255]
    out["stripe_auto_verify"] = _truthy(
        src.get("stripe_auto_verify"),
        _truthy(out.get("stripe_auto_verify"), True),
    )
    out["truemoney_create_payment_url"] = str(
        src.get("truemoney_create_payment_url")
        or out.get("truemoney_create_payment_url")
        or ""
    ).strip()[:280]
    out["truemoney_inquiry_url"] = str(
        src.get("truemoney_inquiry_url")
        or out.get("truemoney_inquiry_url")
        or ""
    ).strip()[:280]
    out["truemoney_api_key"] = str(src.get("truemoney_api_key") or out.get("truemoney_api_key") or "").strip()[:120]
    out["truemoney_api_secret"] = str(src.get("truemoney_api_secret") or out.get("truemoney_api_secret") or "").strip()[:240]
    out["truemoney_bearer_token"] = str(src.get("truemoney_bearer_token") or out.get("truemoney_bearer_token") or "").strip()[:500]
    out["truemoney_callback_url"] = str(src.get("truemoney_callback_url") or out.get("truemoney_callback_url") or "").strip()[:255]
    out["truemoney_webhook_secret"] = (
        str(src.get("truemoney_webhook_secret") or out.get("truemoney_webhook_secret") or "").strip()[:240]
        or out["webhook_secret"]
    )
    tm_sig_header = str(src.get("truemoney_signature_header") or out.get("truemoney_signature_header") or "").strip().lower()
    out["truemoney_signature_header"] = tm_sig_header[:80] or "x-truemoney-signature"
    out["truemoney_signature_prefix"] = str(src.get("truemoney_signature_prefix") or out.get("truemoney_signature_prefix") or "").strip()[:24]
    tm_sig_algo = str(src.get("truemoney_signature_algorithm") or out.get("truemoney_signature_algorithm") or "").strip().lower()
    out["truemoney_signature_algorithm"] = tm_sig_algo if tm_sig_algo in {"sha256", "sha1", "md5"} else "sha256"
    out["truemoney_amount_field"] = str(src.get("truemoney_amount_field") or out.get("truemoney_amount_field") or "amount").strip()[:120] or "amount"
    out["truemoney_currency_field"] = str(src.get("truemoney_currency_field") or out.get("truemoney_currency_field") or "currency").strip()[:120] or "currency"
    out["truemoney_reference_field"] = str(src.get("truemoney_reference_field") or out.get("truemoney_reference_field") or "reference").strip()[:120] or "reference"
    out["truemoney_callback_field"] = str(src.get("truemoney_callback_field") or out.get("truemoney_callback_field") or "callbackUrl").strip()[:120] or "callbackUrl"
    out["truemoney_qr_image_field"] = str(src.get("truemoney_qr_image_field") or out.get("truemoney_qr_image_field") or "data.qrImageUrl").strip()[:120] or "data.qrImageUrl"
    out["truemoney_qr_code_field"] = str(src.get("truemoney_qr_code_field") or out.get("truemoney_qr_code_field") or "data.qrRawData").strip()[:120] or "data.qrRawData"
    out["truemoney_payment_url_field"] = str(src.get("truemoney_payment_url_field") or out.get("truemoney_payment_url_field") or "data.paymentUrl").strip()[:120] or "data.paymentUrl"
    out["truemoney_reference_resp_field"] = str(src.get("truemoney_reference_resp_field") or out.get("truemoney_reference_resp_field") or "data.orderId").strip()[:120] or "data.orderId"
    out["truemoney_transaction_id_field"] = str(src.get("truemoney_transaction_id_field") or out.get("truemoney_transaction_id_field") or "data.transactionId").strip()[:120] or "data.transactionId"
    out["truemoney_inquiry_status_field"] = str(src.get("truemoney_inquiry_status_field") or out.get("truemoney_inquiry_status_field") or "data.status").strip()[:120] or "data.status"
    out["truemoney_paid_status_values"] = str(
        src.get("truemoney_paid_status_values")
        or out.get("truemoney_paid_status_values")
        or "paid,success,completed,settled"
    ).strip()[:300] or "paid,success,completed,settled"
    out["truemoney_auto_verify"] = _truthy(
        src.get("truemoney_auto_verify"),
        _truthy(out.get("truemoney_auto_verify"), True),
    )
    out["slipok_api_url"] = str(
        src.get("slipok_api_url")
        or out.get("slipok_api_url")
        or "https://api.slipok.com/api/line/apikey/1150"
    ).strip()[:300] or "https://api.slipok.com/api/line/apikey/1150"
    out["slipok_key"] = str(src.get("slipok_key") or out.get("slipok_key") or "").strip()[:240]
    slip_engine = str(src.get("slipcheck_verify_engine") or out.get("slipcheck_verify_engine") or "slipok").strip().lower()
    if slip_engine in {"skylinebot", "skyline", "skyline_slip", "skylinebotslip", "internal", "ocr"}:
        out["slipcheck_verify_engine"] = "skylinebotslip"
    else:
        out["slipcheck_verify_engine"] = "slipok"
    out["slipcheck_expected_receiver_name"] = str(
        src.get("slipcheck_expected_receiver_name")
        or out.get("slipcheck_expected_receiver_name")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_receiver_first_name_th"] = str(
        src.get("slipcheck_expected_receiver_first_name_th")
        or out.get("slipcheck_expected_receiver_first_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_last_name_th"] = str(
        src.get("slipcheck_expected_receiver_last_name_th")
        or out.get("slipcheck_expected_receiver_last_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_first_name_en"] = str(
        src.get("slipcheck_expected_receiver_first_name_en")
        or out.get("slipcheck_expected_receiver_first_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_last_name_en"] = str(
        src.get("slipcheck_expected_receiver_last_name_en")
        or out.get("slipcheck_expected_receiver_last_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_bank"] = str(
        src.get("slipcheck_expected_receiver_bank")
        or out.get("slipcheck_expected_receiver_bank")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_receiver_account"] = "".join(
        ch for ch in str(
            src.get("slipcheck_expected_receiver_account")
            or out.get("slipcheck_expected_receiver_account")
            or ""
        )
        if ch.isdigit()
    )[:30]
    out["slipcheck_expected_sender_name"] = str(
        src.get("slipcheck_expected_sender_name")
        or out.get("slipcheck_expected_sender_name")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_sender_first_name_th"] = str(
        src.get("slipcheck_expected_sender_first_name_th")
        or out.get("slipcheck_expected_sender_first_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_last_name_th"] = str(
        src.get("slipcheck_expected_sender_last_name_th")
        or out.get("slipcheck_expected_sender_last_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_first_name_en"] = str(
        src.get("slipcheck_expected_sender_first_name_en")
        or out.get("slipcheck_expected_sender_first_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_last_name_en"] = str(
        src.get("slipcheck_expected_sender_last_name_en")
        or out.get("slipcheck_expected_sender_last_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_bank"] = str(
        src.get("slipcheck_expected_sender_bank")
        or out.get("slipcheck_expected_sender_bank")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_sender_account"] = "".join(
        ch for ch in str(
            src.get("slipcheck_expected_sender_account")
            or out.get("slipcheck_expected_sender_account")
            or ""
        )
        if ch.isdigit()
    )[:30]
    out["slipcheck_expected_reference"] = str(
        src.get("slipcheck_expected_reference")
        or out.get("slipcheck_expected_reference")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_qr_reference"] = str(
        src.get("slipcheck_expected_qr_reference")
        or out.get("slipcheck_expected_qr_reference")
        or ""
    ).strip()[:300]
    try:
        out["slipcheck_max_age_minutes"] = str(
            max(
                0,
                min(
                    60 * 24 * 30,
                    int(float(src.get("slipcheck_max_age_minutes") or out.get("slipcheck_max_age_minutes") or 1440)),
                ),
            )
        )
    except Exception:
        out["slipcheck_max_age_minutes"] = "1440"
    try:
        out["slipcheck_auto_approve_confidence"] = str(
            round(
                max(
                    50.0,
                    min(
                        100.0,
                        float(src.get("slipcheck_auto_approve_confidence") or out.get("slipcheck_auto_approve_confidence") or 85.0),
                    ),
                ),
                2,
            )
        )
    except Exception:
        out["slipcheck_auto_approve_confidence"] = "85"
    try:
        out["slipcheck_manual_review_confidence"] = str(
            round(
                max(
                    0.0,
                    min(
                        100.0,
                        float(src.get("slipcheck_manual_review_confidence") or out.get("slipcheck_manual_review_confidence") or 55.0),
                    ),
                ),
                2,
            )
        )
    except Exception:
        out["slipcheck_manual_review_confidence"] = "55"
    try:
        out["slipcheck_duplicate_window_hours"] = str(
            max(
                1,
                min(
                    24 * 90,
                    int(float(src.get("slipcheck_duplicate_window_hours") or out.get("slipcheck_duplicate_window_hours") or 72)),
                ),
            )
        )
    except Exception:
        out["slipcheck_duplicate_window_hours"] = "72"
    review_channel = str(src.get("slipcheck_review_channel_id") or out.get("slipcheck_review_channel_id") or "").strip()
    out["slipcheck_review_channel_id"] = review_channel if review_channel.isdigit() else ""
    dm_raw = str(src.get("slipcheck_review_dm_user_ids") or out.get("slipcheck_review_dm_user_ids") or "").strip()
    dm_ids: list[str] = []
    for token in re.split(r"[\s,;]+", dm_raw):
        token = str(token or "").strip()
        if not token.isdigit() or token in dm_ids:
            continue
        dm_ids.append(token)
        if len(dm_ids) >= 20:
            break
    out["slipcheck_review_dm_user_ids"] = ",".join(dm_ids)[:600]
    route_raw = str(
        src.get("slipcheck_low_confidence_route")
        or out.get("slipcheck_low_confidence_route")
        or "both"
    ).strip().lower()
    if route_raw in {"embed", "embed_channel", "channel", "room", "guild", "discord"}:
        out["slipcheck_low_confidence_route"] = "channel"
    elif route_raw in {"dm", "direct", "direct_message", "directmessage", "user_dm"}:
        out["slipcheck_low_confidence_route"] = "dm"
    else:
        out["slipcheck_low_confidence_route"] = "both"
    return out


def _ownerbot_payment_provider_settings_from_db() -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(OWNERBOT_PAYMENT_PROVIDER_CONFIG_KEY, "") or "").strip()
    if not raw:
        return _default_ownerbot_payment_provider_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_ownerbot_payment_provider_settings()
    return _normalize_ownerbot_payment_provider_settings(decoded if isinstance(decoded, dict) else {})


def _ownerbot_runtime_block_reason(guild_id: int, runtime_settings: dict[str, Any]) -> str | None:
    return _dashboard_ownerbot_domain.ownerbot_runtime_block_reason(guild_id, runtime_settings)

def _ownerbot_runtime_notice_from_state(state: dict[str, Any] | None) -> str | None:
    return _dashboard_ownerbot_domain.ownerbot_runtime_notice_from_state(
        state,
        block_message_fn=_ownerbot_runtime_block_message,
    )

def _ownerbot_hidden_dashboard_tabs(runtime_settings: dict[str, Any] | None) -> set[str]:
    return _dashboard_ownerbot_domain.ownerbot_hidden_dashboard_tabs(
        runtime_settings,
        parse_tab_slug_list=_parse_tab_slug_list,
    )

def _default_giveaway_dashboard_settings() -> dict[str, Any]:
    return {
        "default_channel_id": None,
        "default_duration": "1h",
        "default_winners": 1,
        "default_prize": "",
        "embed_title": "🎉 กิจกรรมแจกของ",
        "embed_description": "กดปุ่มเพื่อเข้าร่วมกิจกรรมลุ้นรางวัลได้เลย",
        "embed_color": "#6b8cff",
    }


def _giveaway_dashboard_config_key(guild_id: int) -> str:
    return f"{GIVEAWAY_DASHBOARD_SETTINGS_KEY}:{int(guild_id)}"


def _normalize_giveaway_dashboard_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_giveaway_dashboard_settings()
    channel_id = str(src.get("default_channel_id") or "").strip()
    out["default_channel_id"] = channel_id if channel_id.isdigit() else None
    out["default_duration"] = str(src.get("default_duration") or "1h").strip()[:32] or "1h"
    out["default_winners"] = _int_from_form({"v": str(src.get("default_winners") or "1")}, "v", 1, 1, 50)
    out["default_prize"] = str(src.get("default_prize") or "").strip()[:120]
    out["embed_title"] = str(src.get("embed_title") or "🎉 กิจกรรมแจกของ").strip()[:120] or "🎉 กิจกรรมแจกของ"
    out["embed_description"] = str(src.get("embed_description") or "กดปุ่มเพื่อเข้าร่วมกิจกรรมลุ้นรางวัลได้เลย").strip()[:1200]
    color_value = str(src.get("embed_color") or "#6b8cff").strip()
    if not re.match(r"^#[0-9A-Fa-f]{6}$", color_value):
        color_value = "#6b8cff"
    out["embed_color"] = color_value
    return out


def _giveaway_dashboard_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_giveaway_dashboard_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_giveaway_dashboard_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_giveaway_dashboard_settings()
    return _normalize_giveaway_dashboard_settings(decoded if isinstance(decoded, dict) else {})


def _screening_categories_config_key(guild_id: int) -> str:
    return f"{SCREENING_CATEGORY_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _default_screening_categories_settings() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in SCREENING_CATEGORY_ITEMS:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        log_type = str(item.get("log_type") or "").strip().lower()
        out[key] = {
            "enabled": False,
            "channel_id": "",
            "color": SCREENING_CATEGORY_DEFAULT_COLORS.get(log_type, "#6b8cff"),
            "log_type": log_type,
        }
    return out


def _normalize_screening_categories_settings(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_screening_categories_settings()
    for item in SCREENING_CATEGORY_ITEMS:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        raw_row = src.get(key)
        row = raw_row if isinstance(raw_row, dict) else {}
        log_type = str(item.get("log_type") or "").strip().lower()
        channel_id = str(row.get("channel_id") or "").strip()
        color = str(row.get("color") or out[key]["color"]).strip()
        if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
            color = out[key]["color"]
        out[key] = {
            "enabled": bool(row.get("enabled", False)),
            "channel_id": channel_id if channel_id.isdigit() else "",
            "color": color,
            "log_type": log_type,
        }
    return out


def _screening_categories_settings_from_db(guild_id: int) -> dict[str, dict[str, Any]]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_screening_categories_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_screening_categories_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_screening_categories_settings()
    return _normalize_screening_categories_settings(decoded if isinstance(decoded, dict) else {})


def _color_sets_config_key(guild_id: int) -> str:
    return f"{COLOR_SETS_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _reaction_roles_config_key(guild_id: int) -> str:
    return f"{REACTION_ROLES_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _starboard_config_key(guild_id: int) -> str:
    return f"{STARBOARD_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _embed_messages_config_key(guild_id: int) -> str:
    return f"{EMBED_MESSAGES_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _voice_randomizer_config_key(guild_id: int) -> str:
    return f"{VOICE_RANDOMIZER_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _temp_channels_config_key(guild_id: int) -> str:
    return f"{TEMP_CHANNELS_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _temp_links_config_key(guild_id: int) -> str:
    return f"{TEMP_LINKS_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _levels_config_key(guild_id: int) -> str:
    return f"{LEVELS_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _dashboard_editor_roles_config_key(guild_id: int) -> str:
    return f"dashboard_editor_roles_v1_guild_{int(guild_id)}"


def _normalize_dashboard_editor_role_ids(raw_value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(raw_value, list):
        candidates = raw_value
    elif isinstance(raw_value, tuple):
        candidates = list(raw_value)
    else:
        text_value = str(raw_value or "").strip()
        if not text_value:
            candidates = []
        else:
            try:
                decoded = json.loads(text_value)
            except Exception:
                decoded = None
            if isinstance(decoded, list):
                candidates = decoded
            else:
                candidates = [part.strip() for part in text_value.split(",")]

    seen: set[str] = set()
    for candidate in candidates:
        role_id = str(candidate or "").strip()
        if not role_id.isdigit() or role_id in seen:
            continue
        seen.add(role_id)
        values.append(role_id)
    return values


def _dashboard_editor_role_ids_from_db(guild_id: int) -> list[str]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_dashboard_editor_roles_config_key(guild_id), "") or "").strip()
    if not raw:
        return []
    return _normalize_dashboard_editor_role_ids(raw)


def _extra_protection_config_key(guild_id: int) -> str:
    return f"{EXTRA_PROTECTION_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _default_extra_protection_settings() -> dict[str, Any]:
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
        "detect_nsfw_image_mode": "allowlist_only",
        "detect_nsfw_image_threshold": 0.72,
        "delete_action": "warn",
        "timeout_seconds": 300,
    }


def _normalize_extra_protection_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_extra_protection_settings()

    def _safe_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on", "enabled", "enable"}:
            return True
        if text in {"0", "false", "no", "off", "disabled", "disable"}:
            return False
        return default

    def _safe_int(raw_value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(str(raw_value).strip())
        except Exception:
            value = int(default)
        return max(minimum, min(maximum, value))

    def _safe_float(raw_value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            value = float(str(raw_value).strip())
        except Exception:
            value = float(default)
        if value < minimum:
            return float(minimum)
        if value > maximum:
            return float(maximum)
        return float(value)

    def _safe_unix_ts(raw_value: Any) -> int:
        if isinstance(raw_value, datetime.datetime):
            parsed = raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
            return max(0, int(parsed.timestamp()))
        try:
            value = int(float(str(raw_value).strip()))
        except Exception:
            return 0
        return max(0, value)

    def _normalize_id_list(raw_value: Any, *, limit: int = 120) -> list[str]:
        if isinstance(raw_value, list):
            candidates = raw_value
        elif isinstance(raw_value, tuple):
            candidates = list(raw_value)
        elif isinstance(raw_value, set):
            candidates = list(raw_value)
        else:
            text = str(raw_value or "").strip()
            if not text:
                candidates = []
            else:
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None
                if isinstance(parsed, list):
                    candidates = parsed
                else:
                    candidates = re.split(r"[\s,\n\r]+", text)

        out_ids: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            value = str(candidate or "").strip()
            if not value.isdigit() or value in seen:
                continue
            seen.add(value)
            out_ids.append(value)
            if len(out_ids) >= limit:
                break
        return out_ids

    def _normalize_keyword_list(raw_value: Any, *, limit: int = 50) -> list[str]:
        if isinstance(raw_value, list):
            candidates = raw_value
        elif isinstance(raw_value, tuple):
            candidates = list(raw_value)
        else:
            text = str(raw_value or "").strip()
            candidates = re.split(r"[\n\r,]+", text) if text else []
        out_words: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            value = str(candidate or "").strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            out_words.append(value[:80])
            if len(out_words) >= limit:
                break
        return out_words

    out["enabled"] = _safe_bool(src.get("enabled"), out["enabled"])
    out["block_bot_add_enabled"] = _safe_bool(src.get("block_bot_add_enabled"), out["block_bot_add_enabled"])
    out["block_bot_add_armed_at_ts"] = _safe_unix_ts(src.get("block_bot_add_armed_at_ts"))
    out["bot_add_whitelist_user_ids"] = _normalize_id_list(src.get("bot_add_whitelist_user_ids"))
    out["bot_add_whitelist_bot_ids"] = _normalize_id_list(src.get("bot_add_whitelist_bot_ids"))
    out["anti_spam_enabled"] = _safe_bool(src.get("anti_spam_enabled"), out["anti_spam_enabled"])
    out["spam_message_limit"] = _safe_int(src.get("spam_message_limit"), out["spam_message_limit"], 3, 30)
    out["spam_window_seconds"] = _safe_int(src.get("spam_window_seconds"), out["spam_window_seconds"], 3, 180)
    out["anti_mass_mention_enabled"] = _safe_bool(src.get("anti_mass_mention_enabled"), out["anti_mass_mention_enabled"])
    out["mass_mention_limit"] = _safe_int(src.get("mass_mention_limit"), out["mass_mention_limit"], 2, 30)
    out["delete_discord_invite_enabled"] = _safe_bool(
        src.get("delete_discord_invite_enabled"), out["delete_discord_invite_enabled"]
    )
    out["delete_scam_links_enabled"] = _safe_bool(src.get("delete_scam_links_enabled"), out["delete_scam_links_enabled"])
    out["anti_virus_keywords_enabled"] = _safe_bool(
        src.get("anti_virus_keywords_enabled"), out["anti_virus_keywords_enabled"]
    )
    out["custom_virus_keywords"] = _normalize_keyword_list(src.get("custom_virus_keywords"))
    out["detect_nsfw_image_enabled"] = _safe_bool(
        src.get("detect_nsfw_image_enabled"),
        out["detect_nsfw_image_enabled"],
    )
    nsfw_mode = str(src.get("detect_nsfw_image_mode") or out["detect_nsfw_image_mode"]).strip().lower()
    if nsfw_mode not in {"allowlist_only", "all_except_allowlist"}:
        nsfw_mode = out["detect_nsfw_image_mode"]
    out["detect_nsfw_image_mode"] = nsfw_mode
    out["detect_nsfw_image_threshold"] = _safe_float(
        src.get("detect_nsfw_image_threshold"),
        float(out["detect_nsfw_image_threshold"]),
        0.05,
        0.995,
    )
    action = str(src.get("delete_action") or out["delete_action"]).strip().lower()
    if action not in {"none", "warn", "mute", "kick", "ban"}:
        action = out["delete_action"]
    out["delete_action"] = action
    out["timeout_seconds"] = _safe_int(src.get("timeout_seconds"), out["timeout_seconds"], 30, 86400)
    return out


def _extra_protection_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_extra_protection_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_extra_protection_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_extra_protection_settings()
    return _normalize_extra_protection_settings(decoded if isinstance(decoded, dict) else {})


def _honeypot_config_key(guild_id: int) -> str:
    return f"{HONEYPOT_CONFIG_KEY_PREFIX}{int(guild_id)}"


def _default_honeypot_settings() -> dict[str, Any]:
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


def _normalize_honeypot_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_honeypot_settings()

    def _safe_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on", "enabled", "enable"}:
            return True
        if text in {"0", "false", "no", "off", "disabled", "disable"}:
            return False
        return default

    def _safe_int(raw_value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(str(raw_value).strip())
        except Exception:
            value = int(default)
        return max(minimum, min(maximum, value))

    def _safe_id(raw_value: Any) -> str:
        value = str(raw_value or "").strip()
        return value if value.isdigit() else ""

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
    out["deleted_message_count"] = max(0, _safe_int(src.get("deleted_message_count"), 0, 0, 1_000_000_000))
    out["timeout_count"] = max(0, _safe_int(src.get("timeout_count"), 0, 0, 1_000_000_000))
    out["kick_count"] = max(0, _safe_int(src.get("kick_count"), 0, 0, 1_000_000_000))
    out["ban_count"] = max(0, _safe_int(src.get("ban_count"), 0, 0, 1_000_000_000))
    return out


def _honeypot_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_honeypot_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_honeypot_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_honeypot_settings()
    return _normalize_honeypot_settings(decoded if isinstance(decoded, dict) else {})


def _levels_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_levels_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_levels_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_levels_settings()
    return _normalize_levels_settings(decoded if isinstance(decoded, dict) else {})


def _default_economy_dashboard_settings() -> dict[str, Any]:
    return {
        "currency_symbol": "฿",
        "start_cash": 0,
        "start_bank": 0,
        "max_cash": 1_000_000_000,
        "max_bank": 1_000_000_000,
        "audit_channel_id": "",
        "command_work_enabled": True,
        "command_slut_enabled": False,
        "command_crime_enabled": False,
        "command_rob_enabled": False,
        "economy_channels_enabled": False,
        "economy_allow_all_channels": True,
        "economy_command_channels": [],
        "work_cooldown": 3600,
        "work_payout_min": 100,
        "work_payout_max": 300,
        "work_fail_rate": 0,
        "work_fine_type": "fixed",
        "work_fine_min": 0,
        "work_fine_max": 0,
        "slut_cooldown": 7200,
        "slut_payout_min": 120,
        "slut_payout_max": 450,
        "slut_fail_rate": 35,
        "slut_fine_type": "fixed",
        "slut_fine_min": 20,
        "slut_fine_max": 150,
        "crime_cooldown": 10800,
        "crime_payout_min": 180,
        "crime_payout_max": 750,
        "crime_fail_rate": 45,
        "crime_fine_type": "fixed",
        "crime_fine_min": 35,
        "crime_fine_max": 260,
        "rob_cooldown": 14400,
        "rob_payout_min": 300,
        "rob_payout_max": 1200,
        "rob_fail_rate": 60,
        "rob_fine_type": "percent",
        "rob_fine_min": 5,
        "rob_fine_max": 25,
        "role_income_enabled": False,
        "role_income_entries": [],
        "chat_money_enabled": False,
        "chat_money_min": 5,
        "chat_money_max": 15,
        "chat_money_cooldown": 60,
        "chat_money_channels": [],
        "items_enabled": False,
        "store_sell_rate": 50,
        "inventory_max_items": 250,
        "custom_replies_enabled": True,
        "work_replies": [],
        "slut_replies": [],
        "crime_replies": [],
        "rob_replies": [],
        "bet_min": 10,
        "bet_max": 100_000,
    }


def _normalize_economy_dashboard_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_economy_dashboard_settings()

    def _safe_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    raw_currency_symbol = str(src.get("currency_symbol") or out["currency_symbol"])
    raw_currency_symbol = raw_currency_symbol.replace("\uFFFD", "").replace("\r", "").replace("\n", "").strip()
    if re.fullmatch(r"<a?:[A-Za-z0-9_]{2,32}:\d{15,22}>", raw_currency_symbol):
        out["currency_symbol"] = raw_currency_symbol[:64]
    else:
        out["currency_symbol"] = raw_currency_symbol[:32] or "฿"
    for key, minimum, maximum in [
        ("start_cash", 0, 1_000_000_000_000),
        ("start_bank", 0, 1_000_000_000_000),
        ("max_cash", 0, 1_000_000_000_000),
        ("max_bank", 0, 1_000_000_000_000),
        ("work_cooldown", 10, 86400),
        ("work_payout_min", 1, 10_000_000),
        ("work_payout_max", 1, 10_000_000),
        ("work_fail_rate", 0, 100),
        ("work_fine_min", 0, 10_000_000),
        ("work_fine_max", 0, 10_000_000),
        ("slut_cooldown", 10, 86400),
        ("slut_payout_min", 1, 20_000_000),
        ("slut_payout_max", 1, 20_000_000),
        ("slut_fail_rate", 0, 100),
        ("slut_fine_min", 0, 20_000_000),
        ("slut_fine_max", 0, 20_000_000),
        ("crime_cooldown", 10, 86400),
        ("crime_payout_min", 1, 20_000_000),
        ("crime_payout_max", 1, 20_000_000),
        ("crime_fail_rate", 0, 100),
        ("crime_fine_min", 0, 20_000_000),
        ("crime_fine_max", 0, 20_000_000),
        ("rob_cooldown", 10, 86400),
        ("rob_payout_min", 1, 20_000_000),
        ("rob_payout_max", 1, 20_000_000),
        ("rob_fail_rate", 0, 100),
        ("rob_fine_min", 0, 100),
        ("rob_fine_max", 0, 100),
        ("chat_money_min", 0, 5000),
        ("chat_money_max", 0, 5000),
        ("chat_money_cooldown", 5, 3600),
        ("store_sell_rate", 0, 100),
        ("inventory_max_items", 1, 5000),
        ("bet_min", 1, 100_000_000),
        ("bet_max", 1, 100_000_000),
    ]:
        out[key] = _safe_int(src.get(key), int(out[key]), minimum, maximum)

    for key in [
        "command_work_enabled",
        "command_slut_enabled",
        "command_crime_enabled",
        "command_rob_enabled",
        "economy_channels_enabled",
        "economy_allow_all_channels",
        "role_income_enabled",
        "chat_money_enabled",
        "items_enabled",
        "custom_replies_enabled",
    ]:
        out[key] = _safe_bool(src.get(key), bool(out[key]))

    for key in ["work_fine_type", "slut_fine_type", "crime_fine_type", "rob_fine_type"]:
        value = str(src.get(key) or out[key]).strip().lower()
        out[key] = value if value in {"fixed", "percent"} else "fixed"

    if out["work_payout_max"] < out["work_payout_min"]:
        out["work_payout_max"] = out["work_payout_min"]
    if out["slut_payout_max"] < out["slut_payout_min"]:
        out["slut_payout_max"] = out["slut_payout_min"]
    if out["crime_payout_max"] < out["crime_payout_min"]:
        out["crime_payout_max"] = out["crime_payout_min"]
    if out["rob_payout_max"] < out["rob_payout_min"]:
        out["rob_payout_max"] = out["rob_payout_min"]
    if out["chat_money_max"] < out["chat_money_min"]:
        out["chat_money_max"] = out["chat_money_min"]
    if out["max_cash"] and out["max_cash"] < out["start_cash"]:
        out["max_cash"] = out["start_cash"]
    if out["max_bank"] and out["max_bank"] < out["start_bank"]:
        out["max_bank"] = out["start_bank"]

    channel_id = str(src.get("audit_channel_id") or "").strip()
    out["audit_channel_id"] = channel_id if channel_id.isdigit() else ""

    role_rows: list[dict[str, Any]] = []
    raw_roles = src.get("role_income_entries")
    if isinstance(raw_roles, list):
        for raw in raw_roles[:24]:
            row = raw if isinstance(raw, dict) else {}
            role_id = str(row.get("role_id") or "").strip()
            if not role_id.isdigit():
                continue
            row_channel_id = str(row.get("channel_id") or "").strip()
            role_rows.append(
                {
                    "role_id": role_id,
                    "amount": _safe_int(row.get("amount"), 0, 0, 10_000_000),
                    "cooldown": _safe_int(row.get("cooldown"), 3600, 10, 86400),
                    "channel_id": row_channel_id if row_channel_id.isdigit() else "",
                }
            )
    out["role_income_entries"] = role_rows

    raw_chat_channels = src.get("chat_money_channels")
    channels: list[str] = []
    if isinstance(raw_chat_channels, list):
        for item in raw_chat_channels[:80]:
            value = str(item or "").strip()
            if value.isdigit():
                channels.append(value)
    out["chat_money_channels"] = channels

    raw_cmd_channels = src.get("economy_command_channels")
    cmd_channels: list[str] = []
    if isinstance(raw_cmd_channels, list):
        for item in raw_cmd_channels[:120]:
            value = str(item or "").strip()
            if value.isdigit():
                cmd_channels.append(value)
    out["economy_command_channels"] = cmd_channels

    for key in ["work_replies", "slut_replies", "crime_replies", "rob_replies"]:
        raw_rows = src.get(key)
        rows: list[str] = []
        if isinstance(raw_rows, list):
            for value in raw_rows[:20]:
                text = str(value or "").strip()[:220]
                if text:
                    rows.append(text)
        out[key] = rows
    return out


def _default_roleplay_dashboard_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "preset_key": "modern_city",
        "allow_custom_config": True,
        "allow_custom_scenarios": True,
        "currency_symbol": "coin",
        "start_coins": 250,
        "start_xp": 0,
        "xp_per_level": 120,
        "daily_reward_min": 80,
        "daily_reward_max": 180,
        "story_min_length": 20,
        "story_cooldown_seconds": 300,
        "story_reward_min": 12,
        "story_reward_max": 40,
        "scenario_cooldown_seconds": 900,
        "event_reward_xp": 120,
        "event_reward_coins": 220,
        "event_announce_channel_id": None,
        "schedule_notify_on_start": True,
        "schedule_notify_on_end": True,
        "max_custom_scenarios": 30,
    }


def _normalize_roleplay_dashboard_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_roleplay_dashboard_settings()

    def _safe_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    out["preset_key"] = "modern_city"
    out["currency_symbol"] = str(src.get("currency_symbol") or out["currency_symbol"]).strip()[:12] or "coin"
    raw_announce_channel = str(src.get("event_announce_channel_id") or "").strip()
    out["event_announce_channel_id"] = raw_announce_channel if raw_announce_channel.isdigit() else None

    for key, minimum, maximum in [
        ("start_coins", 0, 2_000_000),
        ("start_xp", 0, 500_000),
        ("xp_per_level", 20, 10_000),
        ("daily_reward_min", 0, 200_000),
        ("daily_reward_max", 0, 300_000),
        ("story_min_length", 5, 2_000),
        ("story_cooldown_seconds", 0, 86_400),
        ("story_reward_min", 0, 100_000),
        ("story_reward_max", 0, 150_000),
        ("scenario_cooldown_seconds", 0, 86_400),
        ("event_reward_xp", 0, 250_000),
        ("event_reward_coins", 0, 250_000),
        ("max_custom_scenarios", 1, 200),
    ]:
        out[key] = _safe_int(src.get(key), int(out[key]), minimum, maximum)

    for key in ["enabled", "allow_custom_config", "allow_custom_scenarios", "schedule_notify_on_start", "schedule_notify_on_end"]:
        out[key] = _safe_bool(src.get(key), bool(out[key]))

    if out["daily_reward_max"] < out["daily_reward_min"]:
        out["daily_reward_max"] = out["daily_reward_min"]
    if out["story_reward_max"] < out["story_reward_min"]:
        out["story_reward_max"] = out["story_reward_min"]
    return out


def _normalize_color_hex(value: Any, default: str = "#6B8CFF") -> str:
    raw = str(value or "").strip()
    if re.match(r"^#[0-9A-Fa-f]{6}$", raw):
        return raw.upper()
    return str(default).upper()


def _collect_color_roles_for_ui(guild: discord.Guild | None) -> list[dict[str, Any]]:
    if guild is None:
        return []
    rows: list[dict[str, Any]] = []
    for role in guild.roles:
        name = str(getattr(role, "name", "") or "").strip()
        if not name.isdigit():
            continue
        if role.is_default():
            continue
        color_value = int(getattr(role.color, "value", 0) or 0)
        rows.append(
            {
                "id": str(role.id),
                "name": name,
                "color": f"#{color_value:06X}",
                "position": int(getattr(role, "position", 0) or 0),
            }
        )
    rows.sort(key=lambda item: int(item.get("name") or 0))
    return rows


def _default_reaction_roles_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "selection_mode": "single",
        "items": [],
    }


def _normalize_reaction_roles_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_reaction_roles_settings()
    out["enabled"] = bool(src.get("enabled", out["enabled"]))
    root_selection_mode = str(src.get("selection_mode") or out["selection_mode"]).strip().lower()
    out["selection_mode"] = root_selection_mode if root_selection_mode in {"single", "multiple"} else "single"
    raw_items = src.get("items")
    items: list[dict[str, Any]] = []

    def _normalize_option_row(raw_option: Any) -> dict[str, Any] | None:
        row = raw_option if isinstance(raw_option, dict) else {}
        role_id = str(row.get("role_id") or "").strip()
        if not role_id.isdigit():
            return None
        emoji_value = str(row.get("emoji") or "⭐").strip()[:64] or "⭐"
        return {
            "id": str(row.get("id") or uuid.uuid4().hex).strip()[:64] or uuid.uuid4().hex,
            "emoji": emoji_value,
            "role_id": role_id,
            "label": str(row.get("label") or "").strip()[:80],
            "description": str(row.get("description") or "").strip()[:160],
            "active": bool(row.get("active", True)),
        }

    if isinstance(raw_items, list):
        for raw_item in raw_items[:100]:
            row = raw_item if isinstance(raw_item, dict) else {}
            channel_id = str(row.get("channel_id") or "").strip()
            options: list[dict[str, Any]] = []
            raw_options = row.get("options")
            if isinstance(raw_options, list):
                for raw_option in raw_options[:100]:
                    normalized_option = _normalize_option_row(raw_option)
                    if normalized_option:
                        options.append(normalized_option)

            if not options:
                legacy_option = _normalize_option_row(
                    {
                        "id": row.get("option_id") or row.get("id"),
                        "emoji": row.get("emoji"),
                        "role_id": row.get("role_id"),
                        "label": row.get("label") or row.get("title"),
                        "description": row.get("description"),
                        "active": row.get("active", True),
                    }
                )
                if legacy_option:
                    options.append(legacy_option)

            if not options:
                continue

            row_selection_mode = str(row.get("selection_mode") or out["selection_mode"]).strip().lower()
            selection_mode_value = row_selection_mode if row_selection_mode in {"single", "multiple"} else out["selection_mode"]
            try:
                max_select_value = int(row.get("max_select") or (1 if selection_mode_value == "single" else 2))
            except Exception:
                max_select_value = 1 if selection_mode_value == "single" else 2
            max_select_value = max(1, min(25, max_select_value))
            if selection_mode_value == "single":
                max_select_value = 1

            items.append(
                {
                    "id": str(row.get("id") or uuid.uuid4().hex).strip()[:64] or uuid.uuid4().hex,
                    "title": str(row.get("title") or "Reaction Role").strip()[:80] or "Reaction Role",
                    "description": str(row.get("description") or "").strip()[:400],
                    "channel_id": channel_id if channel_id.isdigit() else "",
                    "style": str(row.get("style") or "button").strip().lower() if str(row.get("style") or "button").strip().lower() in {"button", "select"} else "button",
                    "mode": str(row.get("mode") or "toggle").strip().lower() if str(row.get("mode") or "toggle").strip().lower() in {"toggle", "give", "remove"} else "toggle",
                    "selection_mode": selection_mode_value,
                    "max_select": max_select_value,
                    "options": options,
                    "active": bool(row.get("active", True)),
                }
            )
    out["items"] = items
    return out


def _reaction_roles_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_reaction_roles_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_reaction_roles_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_reaction_roles_settings()
    return _normalize_reaction_roles_settings(decoded if isinstance(decoded, dict) else {})


def _normalize_starboard_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_starboard_settings()
    out["enabled"] = bool(src.get("enabled", out["enabled"]))
    out["active"] = bool(src.get("active", out["active"]))
    out["name"] = str(src.get("name") or out["name"]).strip()[:80] or out["name"]
    enabled_channel_id = str(src.get("enabled_channel_id") or "").strip()
    channel_id = str(src.get("channel_id") or "").strip()
    role_id = str(src.get("required_role_id") or "").strip()
    out["enabled_channel_id"] = enabled_channel_id if enabled_channel_id.isdigit() else ""
    out["channel_id"] = channel_id if channel_id.isdigit() else ""
    out["required_role_id"] = role_id if role_id.isdigit() else ""
    try:
        stars_limit = int(src.get("stars_limit") or out["stars_limit"])
    except Exception:
        stars_limit = out["stars_limit"]
    out["stars_limit"] = max(1, min(20, stars_limit))
    out["custom_emoji"] = str(src.get("custom_emoji") or out["custom_emoji"]).strip()[:64] or out["custom_emoji"]
    mode = str(src.get("message_mode") or out["message_mode"]).strip().lower()
    out["message_mode"] = mode if mode in {"text", "embed"} else "embed"
    out["message_template"] = str(src.get("message_template") or out["message_template"]).strip()[:400] or out["message_template"]
    out["embed_author_name"] = str(src.get("embed_author_name") or out["embed_author_name"]).strip()[:256]
    out["embed_author_url"] = str(src.get("embed_author_url") or out["embed_author_url"]).strip()[:600]
    out["embed_author_icon_url"] = str(src.get("embed_author_icon_url") or out["embed_author_icon_url"]).strip()[:600]
    out["embed_title"] = str(src.get("embed_title") or out["embed_title"]).strip()[:120] or out["embed_title"]
    out["embed_description"] = str(src.get("embed_description") or out["embed_description"]).strip()[:4000] or out["embed_description"]
    out["embed_thumbnail_url"] = str(src.get("embed_thumbnail_url") or out["embed_thumbnail_url"]).strip()[:600]
    out["embed_image_url"] = str(src.get("embed_image_url") or out["embed_image_url"]).strip()[:600]
    out["embed_footer_text"] = str(src.get("embed_footer_text") or out["embed_footer_text"]).strip()[:2048]
    out["embed_footer_icon_url"] = str(src.get("embed_footer_icon_url") or out["embed_footer_icon_url"]).strip()[:600]
    fields: list[dict[str, Any]] = []
    raw_fields = src.get("fields")
    if isinstance(raw_fields, list):
        for index, raw_field in enumerate(raw_fields[:25]):
            row = raw_field if isinstance(raw_field, dict) else {}
            name = str(row.get("name") or "").strip()[:256]
            value = str(row.get("value") or "").strip()[:1024]
            if not name and not value:
                continue
            fields.append(
                {
                    "id": str(row.get("id") or f"field_{index+1}_{uuid.uuid4().hex[:8]}").strip()[:64] or f"field_{index+1}_{uuid.uuid4().hex[:8]}",
                    "name": name or "หัวข้อ",
                    "value": value or "-",
                    "inline": bool(row.get("inline", False)),
                    "align": "center" if str(row.get("align") or "").strip().lower() == "center" else "left",
                }
            )
    out["fields"] = fields
    out["color"] = _normalize_color_hex(src.get("color"), out["color"])
    out["ignore_self_stars"] = bool(src.get("ignore_self_stars", out["ignore_self_stars"]))
    out["react_to_starboard_post"] = bool(src.get("react_to_starboard_post", out["react_to_starboard_post"]))
    return out


def _starboard_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_starboard_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_starboard_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_starboard_settings()
    return _normalize_starboard_settings(decoded if isinstance(decoded, dict) else {})


def _default_embed_messages_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "selected_id": "",
        "items": [],
    }


def _normalize_embed_message_item(raw: Any, index: int = 0) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {}
    raw_fields = row.get("fields")
    fields: list[dict[str, Any]] = []
    if isinstance(raw_fields, list):
        for field_index, field_raw in enumerate(raw_fields[:25]):
            field_row = field_raw if isinstance(field_raw, dict) else {}
            name = str(field_row.get("name") or "").strip()[:256]
            value = str(field_row.get("value") or "")[:1024]
            if not name and not value:
                continue
            fields.append(
                {
                    "id": str(field_row.get("id") or f"field_{field_index+1}_{uuid.uuid4().hex[:8]}").strip()[:64] or f"field_{field_index+1}_{uuid.uuid4().hex[:8]}",
                    "name": name or "หัวข้อ",
                    "value": value or "-",
                    "inline": bool(field_row.get("inline", False)),
                    "align": "center" if str(field_row.get("align") or "").strip().lower() == "center" else "left",
                }
            )
    raw_responses = row.get("responses")
    responses: list[dict[str, Any]] = []
    if isinstance(raw_responses, list):
        for response_index, response_raw in enumerate(raw_responses[:25]):
            responses.append(_normalize_embed_message_response(response_raw, response_index))
    return {
        "id": str(row.get("id") or f"embed_{index+1}_{uuid.uuid4().hex[:8]}").strip()[:64] or f"embed_{index+1}_{uuid.uuid4().hex[:8]}",
        "name": str(row.get("name") or f"new embed {index+1}").strip()[:90] or f"new embed {index+1}",
        "content": str(row.get("content") or "")[:4000],
        "color": _normalize_color_hex(row.get("color"), "#5865F2"),
        "author_name": str(row.get("author_name") or "").strip()[:256],
        "author_url": str(row.get("author_url") or "").strip()[:600],
        "author_icon_url": str(row.get("author_icon_url") or "").strip()[:600],
        "title": str(row.get("title") or "").strip()[:256],
        "description": str(row.get("description") or "")[:4000],
        "thumbnail_url": str(row.get("thumbnail_url") or "").strip()[:600],
        "image_url": str(row.get("image_url") or "").strip()[:600],
        "footer_text": str(row.get("footer_text") or "")[:2048],
        "footer_icon_url": str(row.get("footer_icon_url") or "").strip()[:600],
        "channel_id": str(row.get("channel_id") or "").strip() if str(row.get("channel_id") or "").strip().isdigit() else "",
        "enabled": bool(row.get("enabled", True)),
        "fields": fields,
        "responses": responses,
    }


def _normalize_embed_messages_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_embed_messages_settings()
    out["enabled"] = bool(src.get("enabled", out["enabled"]))
    raw_items = src.get("items")
    items: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for index, raw_item in enumerate(raw_items[:80]):
            items.append(_normalize_embed_message_item(raw_item, index))
    selected_id = str(src.get("selected_id") or "").strip()
    if items:
        valid_ids = {str(item.get("id") or "") for item in items}
        out["selected_id"] = selected_id if selected_id in valid_ids else str(items[0].get("id") or "")
    else:
        out["selected_id"] = ""
    out["items"] = items
    return out


def _embed_messages_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_embed_messages_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_embed_messages_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_embed_messages_settings()
    return _normalize_embed_messages_settings(decoded if isinstance(decoded, dict) else {})


def _normalize_voice_randomizer_category_ids(raw_value: Any, *, max_items: int = 25) -> list[str]:
    if isinstance(raw_value, list):
        source = raw_value
    elif isinstance(raw_value, tuple):
        source = list(raw_value)
    else:
        text = str(raw_value or "").strip()
        if not text:
            source = []
        else:
            try:
                decoded = json.loads(text)
            except Exception:
                decoded = None
            if isinstance(decoded, list):
                source = decoded
            else:
                source = text.replace(" ", ",").split(",")

    out: list[str] = []
    for item in source:
        value = str(item or "").strip()
        if not value.isdigit():
            continue
        if value in out:
            continue
        out.append(value)
        if len(out) >= max_items:
            break
    return out


def _default_voice_randomizer_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "panel_channel_id": "",
        "panel_message_id": "",
        "panel_message_channel_id": "",
        "allowed_category_ids": [],
        "default_category_id": "",
        "room_mode": "normal",
        "embed_title": "Voice Room Randomizer",
        "embed_description": "Pick a category and room mode, then press the button to move into a random voice room.",
        "embed_color": "#5865F2",
        "embed_footer": "",
        "embed_thumbnail_url": "",
        "embed_image_url": "",
        "category_placeholder": "Select category",
        "mode_placeholder": "Select room type",
        "button_label": "Random move me",
        "button_color": "green",
        "button_emoji": "",
    }


def _normalize_voice_randomizer_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_voice_randomizer_settings()

    def _safe_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    def _safe_id(value: Any) -> str:
        text = str(value or "").strip()
        return text if text.isdigit() else ""

    out["enabled"] = _safe_bool(src.get("enabled"), out["enabled"])
    out["panel_channel_id"] = _safe_id(src.get("panel_channel_id"))
    out["panel_message_id"] = _safe_id(src.get("panel_message_id"))
    out["panel_message_channel_id"] = _safe_id(src.get("panel_message_channel_id"))
    out["allowed_category_ids"] = _normalize_voice_randomizer_category_ids(src.get("allowed_category_ids"), max_items=25)

    default_category_id = _safe_id(src.get("default_category_id"))
    if out["allowed_category_ids"]:
        out["default_category_id"] = (
            default_category_id
            if default_category_id in out["allowed_category_ids"]
            else out["allowed_category_ids"][0]
        )
    else:
        out["default_category_id"] = default_category_id

    room_mode = str(src.get("room_mode") or out["room_mode"]).strip().lower()
    out["room_mode"] = room_mode if room_mode in {"normal", "occupied", "empty"} else "normal"

    out["embed_title"] = str(src.get("embed_title") or out["embed_title"]).strip()[:120] or out["embed_title"]
    out["embed_description"] = str(src.get("embed_description") or out["embed_description"]).strip()[:2000]
    out["embed_color"] = _normalize_color_hex(src.get("embed_color"), out["embed_color"])
    out["embed_footer"] = str(src.get("embed_footer") or "").strip()[:200]
    out["embed_thumbnail_url"] = str(src.get("embed_thumbnail_url") or "").strip()[:600]
    out["embed_image_url"] = str(src.get("embed_image_url") or "").strip()[:600]
    out["category_placeholder"] = str(src.get("category_placeholder") or out["category_placeholder"]).strip()[:100] or out["category_placeholder"]
    out["mode_placeholder"] = str(src.get("mode_placeholder") or out["mode_placeholder"]).strip()[:100] or out["mode_placeholder"]
    out["button_label"] = str(src.get("button_label") or out["button_label"]).strip()[:45] or out["button_label"]
    button_color = str(src.get("button_color") or out["button_color"]).strip().lower()
    if button_color not in {"green", "blurple", "red", "gray"}:
        button_color = out["button_color"]
    out["button_color"] = button_color
    out["button_emoji"] = str(src.get("button_emoji") or out["button_emoji"]).strip()[:64] or out["button_emoji"]
    return out


def _voice_randomizer_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_voice_randomizer_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_voice_randomizer_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_voice_randomizer_settings()
    return _normalize_voice_randomizer_settings(decoded if isinstance(decoded, dict) else {})


def _voice_randomizer_color_to_int(value: Any) -> int:
    try:
        return int(_normalize_color_hex(value, "#5865F2").lstrip("#"), 16)
    except Exception:
        return 0x5865F2


def _normalize_temp_channels_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_temp_channels_settings()

    def _safe_id(key: str) -> str:
        value = str(src.get(key) or "").strip()
        return value if value.isdigit() else ""

    def _safe_bool(key: str, default: bool) -> bool:
        value = src.get(key)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    def _safe_int(key: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(src.get(key, default) or default)
        except Exception:
            value = default
        return max(minimum, min(maximum, value))

    out["enabled"] = _safe_bool("enabled", out["enabled"])
    out["create_vc_category_id"] = _safe_id("create_vc_category_id")
    out["create_vc_channel_id"] = _safe_id("create_vc_channel_id")
    out["delete_delay_seconds"] = _safe_int("delete_delay_seconds", out["delete_delay_seconds"], 0, 3600)
    out["max_channels_per_user"] = _safe_int("max_channels_per_user", out["max_channels_per_user"], 1, 25)
    out["default_user_limit"] = _safe_int("default_user_limit", out["default_user_limit"], 0, 99)
    out["command_name"] = str(src.get("command_name") or out["command_name"]).strip()[:32] or out["command_name"]
    out["enable_role_id"] = _safe_id("enable_role_id")
    out["disable_role_id"] = _safe_id("disable_role_id")
    out["enabled_channel_id"] = _safe_id("enabled_channel_id")
    out["disabled_channel_id"] = _safe_id("disabled_channel_id")
    out["auto_delete_message"] = _safe_bool("auto_delete_message", out["auto_delete_message"])
    out["auto_delete_command"] = _safe_bool("auto_delete_command", out["auto_delete_command"])
    out["auto_delete_bot_reply"] = _safe_bool("auto_delete_bot_reply", out["auto_delete_bot_reply"])
    mode = str(src.get("interface_mode") or out["interface_mode"]).strip().lower()
    out["interface_mode"] = mode if mode in {"text", "embed"} else "embed"
    out["interface_content"] = str(src.get("interface_content") or out["interface_content"]).strip()[:4000]
    out["embed_color"] = _normalize_color_hex(src.get("embed_color"), out["embed_color"])
    out["embed_author_name"] = str(src.get("embed_author_name") or out["embed_author_name"]).strip()[:256]
    out["embed_author_url"] = str(src.get("embed_author_url") or out["embed_author_url"]).strip()[:600]
    out["embed_author_icon_url"] = str(src.get("embed_author_icon_url") or out["embed_author_icon_url"]).strip()[:600]
    out["embed_title"] = str(src.get("embed_title") or out["embed_title"]).strip()[:256] or out["embed_title"]
    out["embed_description"] = str(src.get("embed_description") or out["embed_description"]).strip()[:4000] or out["embed_description"]
    out["embed_thumbnail_url"] = str(src.get("embed_thumbnail_url") or out["embed_thumbnail_url"]).strip()[:600]
    out["embed_image_url"] = str(src.get("embed_image_url") or out["embed_image_url"]).strip()[:600]
    out["embed_footer_text"] = str(src.get("embed_footer_text") or out["embed_footer_text"]).strip()[:2048]
    out["embed_footer_icon_url"] = str(src.get("embed_footer_icon_url") or out["embed_footer_icon_url"]).strip()[:600]
    fields: list[dict[str, Any]] = []
    raw_fields = src.get("fields")
    if isinstance(raw_fields, list):
        for index, raw_field in enumerate(raw_fields[:25]):
            row = raw_field if isinstance(raw_field, dict) else {}
            name = str(row.get("name") or "").strip()[:256]
            value = str(row.get("value") or "").strip()[:1024]
            if not name and not value:
                continue
            fields.append(
                {
                    "id": str(row.get("id") or f"field_{index+1}_{uuid.uuid4().hex[:8]}").strip()[:64] or f"field_{index+1}_{uuid.uuid4().hex[:8]}",
                    "name": name or "หัวข้อ",
                    "value": value or "-",
                    "inline": bool(row.get("inline", False)),
                    "align": "center" if str(row.get("align") or "").strip().lower() == "center" else "left",
                }
            )
    out["fields"] = fields
    out["send_channel_id"] = _safe_id("send_channel_id")

    default_buttons = out.get("buttons", {})
    raw_buttons = src.get("buttons")
    normalized_buttons: dict[str, bool] = {}
    for key, default_value in default_buttons.items():
        parsed_value = default_value
        if isinstance(raw_buttons, dict):
            candidate = raw_buttons.get(key)
            if isinstance(candidate, bool):
                parsed_value = candidate
            elif candidate is not None:
                parsed_value = str(candidate).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}
        parsed_value = bool(src.get(f"btn_{key}", parsed_value)) if isinstance(src.get(f"btn_{key}"), bool) else (
            str(src.get(f"btn_{key}") or str(parsed_value)).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}
        )
        normalized_buttons[key] = parsed_value
    out["buttons"] = normalized_buttons
    return out


def _temp_channels_settings_from_db(guild_id: int, state: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_temp_channels_config_key(guild_id), "") or "").strip()
    decoded: dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                decoded = parsed
        except Exception:
            decoded = {}
    from_cache = _normalize_temp_channels_settings(decoded)
    j2c_row = {}
    if isinstance(state, dict):
        j2c_row = state.get("j2c_settings") or {}
    if not j2c_row:
        j2c_row = cache.j2c_settings.get(str(guild_id), {}) or {}
    if isinstance(j2c_row, dict) and j2c_row:
        from_cache["enabled"] = bool(j2c_row.get("enabled", from_cache.get("enabled")))
        create_vc_channel_id = str(j2c_row.get("create_vc_channel_id") or "").strip()
        create_vc_category_id = str(j2c_row.get("create_vc_category_id") or "").strip()
        if create_vc_channel_id.isdigit():
            from_cache["create_vc_channel_id"] = create_vc_channel_id
        if create_vc_category_id.isdigit():
            from_cache["create_vc_category_id"] = create_vc_category_id
    return from_cache


def _default_temp_links_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "channel_id": "",
        "max_uses": 1,
        "max_age_seconds": 3600,
        "temporary_membership": False,
        "unique_per_member": True,
        "history": [],
    }


def _normalize_temp_links_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_temp_links_settings()
    out["enabled"] = bool(src.get("enabled", out["enabled"]))
    channel_id = str(src.get("channel_id") or "").strip()
    out["channel_id"] = channel_id if channel_id.isdigit() else ""
    try:
        max_uses = int(src.get("max_uses") or out["max_uses"])
    except Exception:
        max_uses = out["max_uses"]
    out["max_uses"] = max(1, min(100, max_uses))
    try:
        max_age_seconds = int(src.get("max_age_seconds") or out["max_age_seconds"])
    except Exception:
        max_age_seconds = out["max_age_seconds"]
    out["max_age_seconds"] = max(60, min(7 * 24 * 3600, max_age_seconds))
    out["temporary_membership"] = bool(src.get("temporary_membership", out["temporary_membership"]))
    out["unique_per_member"] = bool(src.get("unique_per_member", out["unique_per_member"]))
    history: list[dict[str, Any]] = []
    raw_history = src.get("history")
    if isinstance(raw_history, list):
        for row in raw_history[:40]:
            item = row if isinstance(row, dict) else {}
            url = str(item.get("url") or "").strip()[:600]
            code = str(item.get("code") or "").strip()[:64]
            created_at = str(item.get("created_at") or "").strip()[:40]
            creator_id = str(item.get("creator_id") or "").strip()[:40]
            creator_name = str(item.get("creator_name") or "").strip()[:120]
            channel_id_row = str(item.get("channel_id") or "").strip()
            if channel_id_row and not channel_id_row.isdigit():
                channel_id_row = ""
            if not url:
                continue
            try:
                row_max_uses = int(item.get("max_uses") or out["max_uses"])
            except Exception:
                row_max_uses = out["max_uses"]
            try:
                row_max_age = int(item.get("max_age_seconds") or out["max_age_seconds"])
            except Exception:
                row_max_age = out["max_age_seconds"]
            history.append(
                {
                    "url": url,
                    "code": code,
                    "created_at": created_at,
                    "creator_id": creator_id,
                    "creator_name": creator_name,
                    "channel_id": channel_id_row,
                    "max_uses": max(1, min(100, row_max_uses)),
                    "max_age_seconds": max(60, min(7 * 24 * 3600, row_max_age)),
                    "temporary_membership": bool(item.get("temporary_membership", False)),
                }
            )
    out["history"] = history[:20]
    return out


def _temp_links_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_temp_links_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_temp_links_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_temp_links_settings()
    return _normalize_temp_links_settings(decoded if isinstance(decoded, dict) else {})


def _normalize_dashboard_audit_entries(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_items = payload if isinstance(payload, list) else []
    for item in raw_items[:500]:
        row = item if isinstance(item, dict) else {}
        ts = int(row.get("ts") or 0)
        user_id = str(row.get("user_id") or "").strip()
        if ts <= 0:
            continue
        rows.append(
            {
                "ts": ts,
                "user_id": user_id,
                "user_name": str(row.get("user_name") or "unknown").strip()[:90] or "unknown",
                "avatar_url": str(row.get("avatar_url") or "").strip()[:600],
                "action": str(row.get("action") or "updated").strip()[:120] or "updated",
                "target": str(row.get("target") or "").strip()[:120],
            }
        )
    rows.sort(key=lambda item: int(item.get("ts") or 0), reverse=True)
    return rows[:300]


def _dashboard_audit_entries_from_db(guild_id: int) -> list[dict[str, Any]]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_dashboard_audit_config_key(guild_id), "") or "").strip()
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
    except Exception:
        return []
    return _normalize_dashboard_audit_entries(decoded)


async def _append_dashboard_audit_event(
    guild_id: int,
    session: dict[str, Any] | None,
    action: str,
    *,
    target: str = "",
) -> None:
    try:
        user = (session or {}).get("user") if isinstance(session, dict) else {}
        user = user if isinstance(user, dict) else {}
        user_id = str(user.get("id") or "").strip()
        user_name = str(user.get("username") or user.get("global_name") or "unknown").strip()[:90] or "unknown"
        avatar_hash = str(user.get("avatar") or "").strip()
        avatar_url = ""
        if user_id and avatar_hash:
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size=64"
        event = {
            "ts": int(time.time()),
            "user_id": user_id,
            "user_name": user_name,
            "avatar_url": avatar_url,
            "action": str(action or "updated").strip()[:120] or "updated",
            "target": str(target or "").strip()[:120],
        }
        existing = _dashboard_audit_entries_from_db(guild_id)
        merged = _normalize_dashboard_audit_entries([event, *existing])
        await _set_dashboard_config_value(
            _dashboard_audit_config_key(guild_id),
            json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
        )
    except Exception:
        return


def _parse_duration_to_seconds_web(duration: str) -> int | None:
    raw = str(duration or "").strip().lower()
    if not raw:
        return None
    matches = re.findall(r"(\d+)\s*([smhd])", raw)
    if not matches:
        return None
    unit_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    total = 0
    consumed = ""
    for value, unit in matches:
        total += int(value) * unit_map[unit]
        consumed += f"{value}{unit}"
    normalized = re.sub(r"\s+", "", raw)
    if normalized != consumed:
        return None
    return total if total > 0 else None


def _trusted_order_from_db() -> list[str]:
    return _parse_trusted_server_order(DASHBOARD_CONFIG_CACHE.get(TRUSTED_ORDER_CONFIG_KEY, ""))


def _can_manage_music_settings(guild_state: dict[str, Any]) -> bool:
    return _plan_rank(guild_state.get("subscription", "free")) >= PLAN_ORDER.index("silver")


def _can_adjust_default_music_volume(guild_state: dict[str, Any]) -> bool:
    return _can_manage_music_settings(guild_state)


def _can_play_music_links(guild_state: dict[str, Any]) -> bool:
    return _plan_rank(guild_state.get("subscription", "free")) >= PLAN_ORDER.index("silver")
def _can_use_antinuke_custom(guild_state: dict[str, Any]) -> bool:
    return _is_plan_at_least(guild_state.get("subscription", "free"), "silver")


def _can_use_automod_custom(guild_state: dict[str, Any]) -> bool:
    return _is_plan_at_least(guild_state.get("subscription", "free"), "silver")


def _can_use_automod_diamond(guild_state: dict[str, Any]) -> bool:
    return _is_plan_at_least(guild_state.get("subscription", "free"), "diamond")


def _allowed_antinuke_punishments(guild_state: dict[str, Any]) -> set[str]:
    tier = _normalize_plan_tier(guild_state.get("subscription", "free"))
    if tier in {"diamond", "permanent"}:
        return {"mute", "kick", "ban"}
    if tier in {"silver", "golden"}:
        return {"mute", "kick"}
    return {"mute"}


def _allowed_automod_punishments(guild_state: dict[str, Any]) -> set[str]:
    tier = _normalize_plan_tier(guild_state.get("subscription", "free"))
    if tier in {"diamond", "permanent"}:
        return {"mute", "kick", "ban"}
    if tier in {"silver", "golden"}:
        return {"mute", "kick"}
    return {"mute"}
def _looks_like_music_url_query(query: str) -> bool:
    text = (query or "").strip().lower()
    if not text:
        return False
    if re.match(r"^(https?://|www\.)", text):
        return True
    host_hints = ("youtube.com/", "youtu.be/", "spotify.com/", "soundcloud.com/", "music.apple.com/")
    return any(hint in text for hint in host_hints)


def _channel_label(bot_guild: Any, channel_id: Any) -> str:
    if not channel_id:
        return "-"
    try:
        resolved = bot_guild.get_channel(int(channel_id)) if bot_guild else None
    except Exception:
        resolved = None
    if resolved:
        return f"#{resolved.name}" if str(getattr(resolved, "type", "")) in {"text", "news", "forum"} else str(resolved.name)
    return "-"


def _normalize_trusted_name(value: Any) -> str:
    raw = str(value or "").casefold().strip()
    return re.sub(r"[^a-z0-9ก-๙]+", "", raw)


def _support_guild_id_from_env() -> int | None:
    raw_value = os.getenv("SUPPORT_GUILD_ID") or os.getenv("SUPPORT_GUILD")
    if not raw_value:
        return None
    try:
        return int(str(raw_value).strip())
    except Exception:
        return None
def _trusted_server_entries(
    bot,
    fallback_icon: str,
    configured_order: list[str] | None = None,
) -> tuple[list[tuple[str, str, str, bool, bool, int]], list[tuple[str, str, str, bool, bool, int]]]:
    del fallback_icon
    env_order = _parse_trusted_server_order(os.getenv("DASHBOARD_TRUSTED_SERVER_ORDER", ""))
    preferred_order = configured_order or env_order or DEFAULT_TRUSTED_SERVER_ORDER
    deduped_preferred_order: list[str] = []
    seen_preferred: set[str] = set()
    for guild_name in preferred_order:
        normalized_name = str(guild_name).casefold().strip()
        if not normalized_name or normalized_name in seen_preferred:
            continue
        seen_preferred.add(normalized_name)
        deduped_preferred_order.append(str(guild_name).strip())

    support_guild_id = _support_guild_id_from_env()

    desc_by_name = {
        "slemusicbotsupport": "trusted_server_2_desc",
        "skylinemusicbotsupport": "trusted_server_2_desc",
        "skyline&musicbotsupport": "trusted_server_3_desc",
        "skylinemusicusers": "trusted_server_4_desc",
        "skylinebotpremium": "trusted_server_5_desc",
        "skylinebotfree": "trusted_server_5b_desc",
        "moderatorlab": "trusted_server_6_desc",
        "giveawayhub": "trusted_server_7_desc",
        "supportdeskthailand": "trusted_server_8_desc",
    }
    guilds = list(getattr(bot, "guilds", []) or [])
    support_guild = None
    if support_guild_id is not None:
        for guild in guilds:
            try:
                if int(getattr(guild, "id", 0) or 0) == support_guild_id:
                    support_guild = guild
                    break
            except Exception:
                continue
    if support_guild is not None:
        support_name = str(getattr(support_guild, "name", "")).strip()
        if support_name:
            normalized_support_name = support_name.casefold().strip()
            if normalized_support_name and normalized_support_name not in seen_preferred:
                seen_preferred.add(normalized_support_name)
                deduped_preferred_order.insert(0, support_name)
            desc_by_name[_normalize_trusted_name(support_name)] = "trusted_server_3_desc"

    lookup = {_normalize_trusted_name(getattr(guild, "name", "")): guild for guild in guilds}
    entries: list[tuple[str, str, str, bool, bool, int]] = []
    seen_entry_keys: set[str] = set()

    for guild_name in deduped_preferred_order:
        normalized_pref_name = _normalize_trusted_name(guild_name)
        found = lookup.get(normalized_pref_name)
        if not found:
            continue
        entry_key = str(getattr(found, "id", "")).strip() or str(getattr(found, "name", "")).casefold().strip()
        if not entry_key or entry_key in seen_entry_keys:
            continue
        seen_entry_keys.add(entry_key)
        if support_guild_id is not None and int(getattr(found, "id", 0) or 0) == support_guild_id:
            desc_key = "trusted_server_3_desc"
        else:
            desc_key = desc_by_name.get(
                normalized_pref_name,
                desc_by_name.get(_normalize_trusted_name(getattr(found, "name", "")), "trusted_server_real_desc"),
            )
        icon_url = getattr(getattr(found, "icon", None), "url", None) or _discord_default_avatar_url(
            getattr(found, "id", getattr(found, "name", "guild"))
        )
        guild_state = cache.guilds.get(str(getattr(found, "id", "")), {})
        is_premium = _looks_like_active_premium_from_state(guild_state)
        is_support = (
            support_guild_id is not None and int(getattr(found, "id", 0) or 0) == support_guild_id
        )
        member_count = max(0, int(getattr(found, "member_count", 0) or 0))
        entries.append((str(getattr(found, "name", guild_name)), str(icon_url), desc_key, is_premium, is_support, member_count))

    guilds.sort(key=lambda guild: int(getattr(guild, "member_count", 0) or 0), reverse=True)
    for guild in guilds:
        entry_key = str(getattr(guild, "id", "")).strip() or str(getattr(guild, "name", "")).casefold().strip()
        if not entry_key or entry_key in seen_entry_keys:
            continue
        seen_entry_keys.add(entry_key)
        name = str(getattr(guild, "name", "Skyline Community"))
        icon_url = getattr(getattr(guild, "icon", None), "url", None) or _discord_default_avatar_url(
            getattr(guild, "id", getattr(guild, "name", "guild"))
        )
        guild_state = cache.guilds.get(str(getattr(guild, "id", "")), {})
        is_premium = _looks_like_active_premium_from_state(guild_state)
        is_support = (
            support_guild_id is not None and int(getattr(guild, "id", 0) or 0) == support_guild_id
        )
        desc_key = "trusted_server_3_desc" if is_support else "trusted_server_real_desc"
        member_count = max(0, int(getattr(guild, "member_count", 0) or 0))
        entries.append((name, str(icon_url), desc_key, is_premium, is_support, member_count))

    all_entries = sorted(
        entries,
        key=lambda entry: (
            int(entry[5]),
            1 if entry[3] else 0,
        ),
        reverse=True,
    )

    max_entries: int = DEFAULT_DASHBOARD_TRUSTED_SERVER_MAX_ENTRIES
    raw_max_entries = str(os.getenv("DASHBOARD_TRUSTED_SERVER_MAX_ENTRIES", "")).strip()
    if raw_max_entries:
        try:
            parsed_max_entries = int(raw_max_entries)
            if parsed_max_entries > 0:
                max_entries = parsed_max_entries
        except Exception:
            max_entries = DEFAULT_DASHBOARD_TRUSTED_SERVER_MAX_ENTRIES

    if max_entries >= len(all_entries):
        return all_entries, all_entries

    support_entry = next((entry for entry in all_entries if entry[4]), None)
    candidate_entries = [
        entry for entry in all_entries
        if support_entry is None or entry != support_entry
    ]

    selected_entries: list[tuple[str, str, str, bool, bool, int]] = []
    if support_entry is not None:
        selected_entries.append(support_entry)

    remaining_slots = max(0, max_entries - len(selected_entries))
    if remaining_slots > 0:
        selected_entries.extend(candidate_entries[:remaining_slots])

    return selected_entries, all_entries


def _report_rate_limited(client_ip: str) -> tuple[bool, int]:
    now = time.time()
    history = [
        stamp for stamp in REPORT_RATE_LIMIT.get(client_ip, [])
        if now - stamp <= REPORT_RATE_LIMIT_WINDOW
    ]
    REPORT_RATE_LIMIT[client_ip] = history
    if len(history) >= REPORT_RATE_LIMIT_MAX:
        retry_after = max(1, int(REPORT_RATE_LIMIT_WINDOW - (now - history[0])))
        return True, retry_after
    history.append(now)
    REPORT_RATE_LIMIT[client_ip] = history
    return False, 0


def _report_channel_id_from_runtime(bot) -> int | None:
    bot_channels = getattr(bot, "channels", None)
    raw_id = getattr(bot_channels, "report_channel", None) if bot_channels else None
    if not raw_id:
        raw_id = os.getenv("REPORT_CHANNEL")
    if not raw_id:
        return None
    try:
        return int(raw_id)
    except Exception:
        return None


def _session_user_id(session: dict[str, Any] | None) -> int | None:
    return _dashboard_runtime_domain.session_user_id(session)

def _is_dashboard_admin(session: dict[str, Any] | None) -> bool:
    user_id = _session_user_id(session)
    if user_id is None:
        return False
    return user_id in set(cache.developer or [])


class _DashboardGuestSession(dict[str, Any]):
    """Language-only guest session that still behaves as unauthenticated."""

    def __bool__(self) -> bool:  # pragma: no cover - trivial branch
        return False


def _session_mapping(session: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(session, dict):
        return session
    return {}


def _normalize_dashboard_access_mode(raw_value: Any, *, is_admin: bool) -> str:
    mode = str(raw_value or "").strip().lower()
    if mode in {"ownerbot", "owner_bot", "bot", "admin", "developer"}:
        mode = OWNERBOT_DASHBOARD_ACCESS_MODE
    else:
        mode = DEFAULT_DASHBOARD_ACCESS_MODE
    if mode == OWNERBOT_DASHBOARD_ACCESS_MODE and not is_admin:
        return DEFAULT_DASHBOARD_ACCESS_MODE
    return mode


def _dashboard_access_mode_from_session(session: dict[str, Any] | None) -> str:
    is_admin = _is_dashboard_admin(session)
    raw_mode = (session or {}).get(DASHBOARD_ACCESS_MODE_SESSION_KEY)
    return _normalize_dashboard_access_mode(raw_mode, is_admin=is_admin)


def _dashboard_set_access_mode(session: dict[str, Any] | None, mode: Any) -> str:
    normalized = _normalize_dashboard_access_mode(mode, is_admin=_is_dashboard_admin(session))
    if isinstance(session, dict):
        if normalized == OWNERBOT_DASHBOARD_ACCESS_MODE:
            session[DASHBOARD_ACCESS_MODE_SESSION_KEY] = normalized
        else:
            session.pop(DASHBOARD_ACCESS_MODE_SESSION_KEY, None)
    return normalized


def _dashboard_ownerbot_mode_enabled(session: dict[str, Any] | None) -> bool:
    return bool(
        _is_dashboard_admin(session)
        and _dashboard_access_mode_from_session(session) == OWNERBOT_DASHBOARD_ACCESS_MODE
    )


async def _ensure_dashboard_config_cache() -> None:
    if DASHBOARD_CONFIG_CACHE:
        return
    try:
        rows = await storage.dashboard_config.get_all()
    except Exception:
        rows = []
    for row in rows:
        key = str(row.get("config_key") or "").strip()
        if key:
            DASHBOARD_CONFIG_CACHE[key] = str(row.get("config_value") or "")


async def _set_dashboard_config_value(config_key: str, config_value: str) -> None:
    await _ensure_dashboard_config_cache()
    writer = getattr(storage.dashboard_config, "set_config_value", None)
    if callable(writer):
        await writer(config_key=config_key, config_value=config_value)
    else:
        try:
            existing = await storage.dashboard_config.get(config_key=config_key)
        except Exception:
            existing = None
        if existing:
            await storage.dashboard_config.update(id=existing["id"], config_value=config_value)
        else:
            await storage.dashboard_config.insert(config_key=config_key, config_value=config_value)
    DASHBOARD_CONFIG_CACHE[config_key] = config_value


def _create_report_challenge() -> tuple[str, str]:
    charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    challenge_text = "".join(secrets.choice(charset) for _ in range(5))
    challenge_id = uuid.uuid4().hex
    REPORT_CHALLENGES[challenge_id] = (challenge_text, time.time() + REPORT_CHALLENGE_TTL)
    return challenge_id, challenge_text


def _validate_report_challenge(challenge_id: str, answer: str) -> bool:
    now = time.time()
    expired = [key for key, (_, expires_at) in REPORT_CHALLENGES.items() if expires_at < now]
    for key in expired:
        REPORT_CHALLENGES.pop(key, None)

    stored = REPORT_CHALLENGES.pop(challenge_id, None)
    if not stored:
        return False
    expected, expires_at = stored
    if expires_at < now:
        return False
    return (answer or "").strip().upper() == expected.upper()


def _session_from_request(request: Request) -> dict[str, Any] | None:
    session = _dashboard_runtime_domain.session_from_request(
        request,
        get_session_fn=get_session,
        session_cookie=SESSION_COOKIE,
    )
    route_lang = str(
        getattr(getattr(request, "state", None), "language_prefix", "") or ""
    ).strip().lower()
    cookie_lang = str((request.cookies or {}).get("skyline_lang") or "").strip().lower()
    resolved_lang = route_lang if route_lang in {"th", "en"} else cookie_lang
    if isinstance(session, dict):
        if resolved_lang in {"th", "en"}:
            session["language"] = resolved_lang
        return session
    if resolved_lang in {"th", "en"}:
        guest_session = _DashboardGuestSession()
        guest_session["language"] = resolved_lang
        return guest_session
    return session

def _dashboard_base_url_from_request(request: Request | None = None) -> str | None:
    return _dashboard_runtime_domain.dashboard_base_url_from_request(request)

def _normalize_dashboard_base_url(raw_value: Any) -> str | None:
    return _dashboard_runtime_domain.normalize_dashboard_base_url(raw_value)

def _dashboard_callback_url(
    request: Request | None = None,
    *,
    base_url_override: str | None = None,
) -> str:
    return _dashboard_runtime_domain.dashboard_callback_url(
        request=request,
        base_url_override=base_url_override,
        normalize_base_url_fn=_normalize_dashboard_base_url,
        configured_dashboard_base_url=BOT_CONFIG.DASHBOARD_BASE_URL,
        web_port=BOT_CONFIG.WEB_PORT,
    )

def _support_status_public_url() -> str:
    configured = str(os.getenv("SUPPORT_STATUS_PUBLIC_URL") or "").strip()
    normalized = _normalize_dashboard_base_url(configured)
    if normalized:
        return normalized

    base = _normalize_dashboard_base_url(BOT_CONFIG.DASHBOARD_BASE_URL)
    if not base:
        return "/status?view=service"

    try:
        parsed = urlparse(base)
    except Exception:
        return "/status?view=service"

    scheme = str(parsed.scheme or "http").strip().lower() or "http"
    host = str(parsed.hostname or "").strip()
    if not host:
        return "/status?view=service"

    raw_port = str(os.getenv("SUPPORT_STATUS_PUBLIC_PORT", "8890") or "8890").strip()
    try:
        status_port = max(1, int(raw_port))
    except Exception:
        status_port = 8890

    default_port = 443 if scheme == "https" else 80
    needs_port = status_port != default_port
    host_with_port = host
    if ":" in host and not host.startswith("["):
        host_with_port = f"[{host}]"
    if needs_port:
        host_with_port = f"{host_with_port}:{status_port}"

    return f"{scheme}://{host_with_port}"


def _bot_invite_url(guild_id: str | int | None = None) -> str:
    query_params: dict[str, str] = {
        "client_id": str(BOT_CONFIG.DISCORD_CLIENT_ID or "").strip(),
        "permissions": "8",
        "integration_type": "0",
        "scope": "bot applications.commands",
    }
    guild_id_str = str(guild_id or "").strip()
    if guild_id_str.isdigit():
        query_params["guild_id"] = guild_id_str
        query_params["disable_guild_select"] = "true"
    return f"https://discord.com/oauth2/authorize?{urlencode(query_params)}"


def _can_manage_guild(raw_guild: dict[str, Any]) -> bool:
    permissions = int(raw_guild.get("permissions", 0) or 0)
    return bool(raw_guild.get("owner")) or bool(permissions & ADMINISTRATOR) or bool(
        permissions & MANAGE_GUILD
    )


def _guild_permission_bits(raw_guild: dict[str, Any] | None) -> int:
    if not isinstance(raw_guild, dict):
        return 0
    try:
        return int(raw_guild.get("permissions", 0) or 0)
    except Exception:
        return 0


def _dashboard_guild_access_payload(
    *,
    is_owner: bool,
    permission_bits: int,
    ownerbot_mode: bool = False,
) -> dict[str, Any]:
    level = "authorized"
    source = "manage_guild"
    if ownerbot_mode:
        level = "ownerbot"
        source = "ownerbot_mode"
    elif is_owner:
        level = "owner"
        source = "owner"
    elif int(permission_bits or 0) & ADMINISTRATOR:
        level = "admin"
        source = "administrator"
    return {
        "_dashboard_access_level": level,
        "_dashboard_access_source": source,
        "_dashboard_permission_bits": int(permission_bits or 0),
    }


def _dashboard_access_visual_meta(access_level: Any, permission_bits: int = 0) -> dict[str, Any]:
    level = str(access_level or "").strip().lower()
    bits = int(permission_bits or 0)
    meta_map: dict[str, dict[str, str]] = {
        "owner": {
            "label": "ผู้สร้าง",
            "desc": "Server Owner",
            "icon": "fa-solid fa-crown",
            "accent": "owner",
        },
        "admin": {
            "label": "ผู้ดูแล",
            "desc": "Administrator access",
            "icon": "fa-solid fa-shield-halved",
            "accent": "admin",
        },
        "authorized": {
            "label": "ผู้ได้รับอนุญาต",
            "desc": "Manage Server access",
            "icon": "fa-solid fa-user-check",
            "accent": "authorized",
        },
        "ownerbot": {
            "label": "OwnerBOT",
            "desc": "Bot admin mode",
            "icon": "fa-solid fa-wand-magic-sparkles",
            "accent": "ownerbot",
        },
    }
    normalized_level = level if level in meta_map else "authorized"
    meta = dict(meta_map[normalized_level])

    scopes: list[str] = []
    if normalized_level == "owner":
        scopes.append("Owner")
    elif normalized_level in {"admin", "authorized"}:
        if bits & ADMINISTRATOR:
            scopes.append("Administrator")
        if bits & MANAGE_GUILD:
            scopes.append("Manage Server")
        if not scopes:
            scopes.append("Administrator" if normalized_level == "admin" else "Manage Server")
    elif normalized_level == "ownerbot":
        scopes.append("Bot Mode")

    meta["level"] = normalized_level
    meta["scopes"] = scopes
    return meta


def _dashboard_unicode_emoji_catalog() -> list[tuple[str, str]]:
    return [
        ("\U0001F4B0", "money cash"),
        ("\U0001F4B5", "bank note"),
        ("\U0001F4B8", "money fly"),
        ("\U0001FA99", "coin"),
        ("\U0001F48E", "diamond"),
        ("\u2705", "check pass"),
        ("\u274C", "cross fail"),
        ("\u26A0\uFE0F", "warning"),
        ("\U0001F525", "fire hot"),
        ("\u2B50", "star"),
        ("\u2728", "sparkles"),
        ("\U0001F680", "rocket"),
        ("\U0001F4C8", "chart up"),
        ("\U0001F4C9", "chart down"),
        ("\U0001F4CA", "bar chart"),
        ("\U0001F4E2", "announce"),
        ("\U0001F4E3", "loudspeaker"),
        ("\U0001F381", "gift"),
        ("\U0001F389", "party"),
        ("\U0001F3C6", "trophy win"),
        ("\U0001F3AF", "target"),
        ("\U0001F9FE", "receipt"),
        ("\U0001F4B3", "card"),
        ("\U0001F512", "lock"),
        ("\U0001F513", "unlock"),
        ("\U0001F6E1\uFE0F", "shield"),
        ("\U0001F9E0", "brain"),
        ("\u26A1", "zap"),
        ("\U0001F514", "bell"),
        ("\U0001F3B5", "music"),
        ("\U0001F9EA", "lab"),
        ("\U0001FA84", "magic"),
        ("\U0001F4CC", "pin"),
        ("\U0001F340", "luck"),
        ("\U0001F98A", "fox"),
        ("\U0001F433", "whale"),
        ("\U0001F438", "frog"),
        ("\U0001F60E", "cool"),
        ("\U0001F916", "bot"),
        ("\U0001F451", "crown"),
        ("\U0001F4AC", "chat"),
        ("\U0001F9E9", "puzzle"),
    ]


def _dashboard_emoji_picker_payload(
    session: dict[str, Any] | None,
    guilds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    bot_instance = get_bot()
    bot_guild_map: dict[str, Any] = {}
    if bot_instance:
        bot_guild_map = {
            str(getattr(item, "id", "") or ""): item
            for item in list(getattr(bot_instance, "guilds", []) or [])
            if str(getattr(item, "id", "") or "").strip()
        }

    raw_session_guilds = session.get("guilds") if isinstance(session, dict) else []
    raw_lookup: dict[str, dict[str, Any]] = {}
    if isinstance(raw_session_guilds, list):
        for raw_item in raw_session_guilds:
            if not isinstance(raw_item, dict):
                continue
            raw_id = str(raw_item.get("id") or "").strip()
            if not raw_id:
                continue
            raw_lookup[raw_id] = raw_item

    candidate_guilds: list[dict[str, str]] = []
    seen_guild_ids: set[str] = set()

    def _add_candidate(guild_id_value: Any, guild_name_value: Any) -> None:
        guild_id = str(guild_id_value or "").strip()
        if not guild_id or guild_id in seen_guild_ids:
            return
        seen_guild_ids.add(guild_id)
        guild_name = str(guild_name_value or f"Guild {guild_id}").strip() or f"Guild {guild_id}"
        candidate_guilds.append({"id": guild_id, "name": guild_name})

    if isinstance(raw_session_guilds, list):
        for raw_item in raw_session_guilds:
            if not isinstance(raw_item, dict):
                continue
            _add_candidate(raw_item.get("id"), raw_item.get("name"))

    if not candidate_guilds and isinstance(guilds, list):
        for raw_item in guilds:
            if not isinstance(raw_item, dict):
                continue
            _add_candidate(raw_item.get("id"), raw_item.get("name"))

    if not candidate_guilds and bot_guild_map:
        for guild_obj in list(bot_guild_map.values()):
            _add_candidate(getattr(guild_obj, "id", ""), getattr(guild_obj, "name", ""))

    candidate_guilds.sort(key=lambda item: str(item.get("name") or "").lower())

    custom_guilds: list[dict[str, Any]] = []
    total_custom_emojis = 0
    for guild_item in candidate_guilds:
        guild_id = str(guild_item.get("id") or "").strip()
        guild_name = str(guild_item.get("name") or f"Guild {guild_id}").strip() or f"Guild {guild_id}"
        guild_obj = bot_guild_map.get(guild_id)
        emoji_rows: list[dict[str, Any]] = []
        if guild_obj is not None:
            for emoji in list(getattr(guild_obj, "emojis", []) or []):
                emoji_id = str(getattr(emoji, "id", "") or "").strip()
                emoji_name = str(getattr(emoji, "name", "") or "").strip() or "emoji"
                if not emoji_id:
                    continue
                emoji_rows.append(
                    {
                        "id": emoji_id,
                        "name": emoji_name,
                        "animated": bool(getattr(emoji, "animated", False)),
                        "url": str(getattr(emoji, "url", "") or "").strip(),
                    }
                )
        else:
            raw_item = raw_lookup.get(guild_id)
            raw_emojis = raw_item.get("emojis") if isinstance(raw_item, dict) else []
            if isinstance(raw_emojis, list):
                for emoji in raw_emojis:
                    if not isinstance(emoji, dict):
                        continue
                    emoji_id = str(emoji.get("id") or "").strip()
                    emoji_name = str(emoji.get("name") or "").strip() or "emoji"
                    if not emoji_id:
                        continue
                    animated = bool(emoji.get("animated"))
                    ext = "gif" if animated else "png"
                    emoji_rows.append(
                        {
                            "id": emoji_id,
                            "name": emoji_name,
                            "animated": animated,
                            "url": f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?size=64&quality=lossless",
                        }
                    )
        total_custom_emojis += len(emoji_rows)
        custom_guilds.append(
            {
                "id": guild_id,
                "name": guild_name,
                "emoji_count": len(emoji_rows),
                "emojis": emoji_rows,
            }
        )

    unicode_emojis = [
        {"value": value, "aliases": aliases}
        for value, aliases in _dashboard_unicode_emoji_catalog()
    ]
    return {
        "custom_guilds": custom_guilds,
        "unicode_emojis": unicode_emojis,
        "custom_emoji_count": total_custom_emojis,
        "guild_count": len(custom_guilds),
    }


async def _resolve_guild_member_permission_bits(
    bot_guild: Any,
    user_id: int | None,
    *,
    allow_fetch: bool = True,
) -> int:
    if not bot_guild or not user_id:
        return 0
    guild_id = int(getattr(bot_guild, "id", 0) or 0)
    normalized_user_id = int(user_id or 0)
    if guild_id <= 0 or normalized_user_id <= 0:
        return 0

    cache_key = (guild_id, normalized_user_id)
    now_ts = time.monotonic()
    cached_entry = _DASHBOARD_MEMBER_PERMISSION_CACHE.get(cache_key)
    if cached_entry:
        expires_at, cached_bits = cached_entry
        if now_ts < float(expires_at or 0.0):
            return int(cached_bits or 0)

    member = None
    try:
        member = bot_guild.get_member(normalized_user_id)
    except Exception:
        member = None
    if member is None and allow_fetch:
        try:
            member = await bot_guild.fetch_member(normalized_user_id)
        except Exception:
            member = None
    if member is None:
        _DASHBOARD_MEMBER_PERMISSION_CACHE[cache_key] = (
            now_ts + min(12.0, _DASHBOARD_MEMBER_PERMISSION_CACHE_TTL_SECONDS),
            0,
        )
        return 0
    try:
        bits = int(getattr(getattr(member, "guild_permissions", None), "value", 0) or 0)
        _DASHBOARD_MEMBER_PERMISSION_CACHE[cache_key] = (
            now_ts + _DASHBOARD_MEMBER_PERMISSION_CACHE_TTL_SECONDS,
            bits,
        )
        return bits
    except Exception:
        _DASHBOARD_MEMBER_PERMISSION_CACHE[cache_key] = (
            now_ts + min(12.0, _DASHBOARD_MEMBER_PERMISSION_CACHE_TTL_SECONDS),
            0,
        )
        return 0


def _manageable_guilds(session: dict[str, Any]) -> list[dict[str, Any]]:
    bot = get_bot()
    if not bot:
        return []
    if _dashboard_ownerbot_mode_enabled(session):
        items: list[dict[str, Any]] = []
        for guild in list(getattr(bot, "guilds", []) or []):
            access_payload = _dashboard_guild_access_payload(
                is_owner=False,
                permission_bits=0,
                ownerbot_mode=True,
            )
            items.append(
                {
                    "id": str(guild.id),
                    "name": str(getattr(guild, "name", f"Guild {guild.id}") or f"Guild {guild.id}"),
                    "icon": _guild_icon(guild),
                    "members": int(getattr(guild, "member_count", 0) or 0),
                    "channels": len(getattr(guild, "channels", []) or []),
                    "roles": len(getattr(guild, "roles", []) or []),
                    "owner_id": int(getattr(guild, "owner_id", 0) or 0),
                    **access_payload,
                }
            )
        return sorted(items, key=lambda item: str(item.get("name") or "").lower())

    bot_guild_map = {str(guild.id): guild for guild in bot.guilds}
    user_id = _session_user_id(session)
    items = []
    for raw_guild in session.get("guilds", []):
        if not _can_manage_guild(raw_guild):
            continue
        guild = bot_guild_map.get(str(raw_guild.get("id")))
        if not guild:
            continue
        raw_permissions = _guild_permission_bits(raw_guild)
        is_owner = bool(raw_guild.get("owner"))
        if user_id is not None and int(getattr(guild, "owner_id", 0) or 0) == int(user_id):
            is_owner = True
        access_payload = _dashboard_guild_access_payload(
            is_owner=is_owner,
            permission_bits=raw_permissions,
        )
        items.append(
            {
                "id": str(guild.id),
                "name": guild.name,
                "icon": _guild_icon(guild),
                "members": guild.member_count or 0,
                "channels": len(guild.channels),
                "roles": len(guild.roles),
                "owner_id": guild.owner_id,
                **access_payload,
            }
        )
    return sorted(items, key=lambda item: item["name"].lower())


async def _manageable_guilds_live(session: dict[str, Any]) -> list[dict[str, Any]]:
    bot = get_bot()
    if not bot:
        return []
    if _dashboard_ownerbot_mode_enabled(session):
        return _manageable_guilds(session)

    user_id = _session_user_id(session)
    bot_guild_map = {str(guild.id): guild for guild in bot.guilds}
    items = []
    fetch_budget = _DASHBOARD_MEMBER_PERMISSION_FETCH_BUDGET
    for raw_guild in session.get("guilds", []):
        guild = bot_guild_map.get(str(raw_guild.get("id")))
        if not guild:
            continue
        raw_permissions = _guild_permission_bits(raw_guild)
        can_manage = _can_manage_guild(raw_guild)
        live_permissions = 0
        is_owner = bool(raw_guild.get("owner"))
        if not can_manage and user_id is not None:
            if int(getattr(guild, "owner_id", 0) or 0) == int(user_id):
                can_manage = True
                is_owner = True
            else:
                live_permissions = await _resolve_guild_member_permission_bits(
                    guild,
                    user_id,
                    allow_fetch=fetch_budget > 0,
                )
                if fetch_budget > 0:
                    fetch_budget -= 1
                can_manage = bool(live_permissions & ADMINISTRATOR) or bool(live_permissions & MANAGE_GUILD)
        if not can_manage:
            continue
        if user_id is not None and int(getattr(guild, "owner_id", 0) or 0) == int(user_id):
            is_owner = True
        effective_permissions = live_permissions or raw_permissions
        access_payload = _dashboard_guild_access_payload(
            is_owner=is_owner,
            permission_bits=effective_permissions,
        )
        items.append(
            {
                "id": str(guild.id),
                "name": guild.name,
                "icon": _guild_icon(guild),
                "members": guild.member_count or 0,
                "channels": len(guild.channels),
                "roles": len(guild.roles),
                "owner_id": guild.owner_id,
                **access_payload,
            }
        )
    return sorted(items, key=lambda item: item["name"].lower())


def _invite_candidate_guilds(session: dict[str, Any]) -> list[dict[str, str]]:
    bot = get_bot()
    if not bot:
        return []
    bot_guild_ids = {str(guild.id) for guild in bot.guilds}
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_guild in session.get("guilds", []):
        if not _can_manage_guild(raw_guild):
            continue
        guild_id = str(raw_guild.get("id") or "").strip()
        if not guild_id or guild_id in bot_guild_ids or guild_id in seen:
            continue
        seen.add(guild_id)
        guild_name = str(raw_guild.get("name") or f"Guild {guild_id}")
        icon_hash = str(raw_guild.get("icon") or "").strip()
        icon_url = (
            f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png?size=128"
            if icon_hash
            else "https://cdn.discordapp.com/embed/avatars/0.png"
        )
        items.append(
            {
                "id": guild_id,
                "name": guild_name,
                "icon": icon_url,
                "invite_url": _bot_invite_url(guild_id),
            }
        )
    return sorted(items, key=lambda item: item["name"].lower())


def _get_accessible_guild(session: dict[str, Any], guild_id: int):
    for guild in _manageable_guilds(session):
        if guild["id"] == str(guild_id):
            bot = get_bot()
            return guild, bot.get_guild(guild_id) if bot else None
    return None, None


async def _get_accessible_guild_live(session: dict[str, Any], guild_id: int):
    for guild in await _manageable_guilds_live(session):
        if guild["id"] == str(guild_id):
            bot = get_bot()
            return guild, bot.get_guild(guild_id) if bot else None
    return None, None


_DASHBOARD_STORAGE_ERROR_LAST_AT: dict[str, float] = {}


def _log_dashboard_storage_error(scope: str, guild_id: int, error: Exception, *, min_interval_sec: float = 45.0) -> None:
    key = f"{str(scope or 'unknown').strip().lower()}:{int(guild_id)}"
    now = time.monotonic()
    last_emit_at = float(_DASHBOARD_STORAGE_ERROR_LAST_AT.get(key, 0.0) or 0.0)
    if (now - last_emit_at) < max(5.0, float(min_interval_sec or 45.0)):
        return
    _DASHBOARD_STORAGE_ERROR_LAST_AT[key] = now
    logger.warning(
        f"[dashboard_storage] {scope} failed | guild={int(guild_id)} | "
        f"error={type(error).__name__}: {error}"
    )


async def _safe_get_or_insert(cache_namespace, storage_module, guild_id: int, **insert_kwargs):
    cached = cache_namespace.get(str(guild_id))
    if cached:
        return cached
    try:
        return await storage_module.insert(guild_id=guild_id, **insert_kwargs)
    except Exception as exc:
        # DuplicateKeyError or any race where the row already exists; fetch from cache/db.
        if "DuplicateKey" in type(exc).__name__ or "11000" in str(exc):
            existing = cache_namespace.get(str(guild_id))
            if existing:
                return existing
            try:
                return await storage_module.get(guild_id=guild_id)
            except Exception:
                return {}
        _log_dashboard_storage_error(
            f"{getattr(storage_module, '__name__', 'storage_module')}.insert",
            guild_id,
            exc,
        )
        fallback = cache_namespace.get(str(guild_id))
        if fallback:
            return fallback
        try:
            fetched = await storage_module.get(guild_id=guild_id)
            if fetched:
                return fetched
        except Exception:
            pass
        return {}


def _default_ticket_module_payload(guild_id: int) -> dict[str, Any]:
    return {
        "id": 0,
        "guild_id": int(guild_id),
        "ticket_module_id": 1,
        "enabled": False,
        "support_roles": [],
        "ticket_limit": 1,
        "open_ticket_category_id": None,
        "closed_ticket_category_id": None,
        "ticket_panel_channel_id": None,
        "ticket_panel_message_id": None,
        "ticket_panel_message_content": None,
        "ticket_panel_message_embed": {},
        "close_ticket_message_content": None,
        "close_ticket_message_embed": {},
    }


def _fallback_dashboard_state(guild_id: int, bot_guild) -> dict[str, Any]:
    ticket_modules_payload = cache.ticket_settings.get(str(guild_id), {})
    ticket_modules_list: list[dict[str, Any]] = []
    if isinstance(ticket_modules_payload, dict):
        ticket_modules_list = [row for row in ticket_modules_payload.values() if isinstance(row, dict)]
    elif isinstance(ticket_modules_payload, list):
        ticket_modules_list = [row for row in ticket_modules_payload if isinstance(row, dict)]
    if not ticket_modules_list:
        ticket_modules_list = [_default_ticket_module_payload(guild_id)]

    channels = []
    for channel in list(getattr(bot_guild, "channels", []) or []):
        channel_id = int(getattr(channel, "id", 0) or 0)
        if channel_id <= 0:
            continue
        channels.append(
            {
                "id": str(channel_id),
                "name": str(getattr(channel, "name", "") or ""),
                "type": str(getattr(channel, "type", "") or ""),
            }
        )

    roles = []
    for role in list(getattr(bot_guild, "roles", []) or []):
        if not hasattr(role, "is_default") or role.is_default():
            continue
        role_id = int(getattr(role, "id", 0) or 0)
        if role_id <= 0:
            continue
        roles.append(
            {
                "id": str(role_id),
                "name": str(getattr(role, "name", "") or ""),
                "color": str(getattr(role, "color", "") or ""),
            }
        )

    return {
        "guild": cache.guilds.get(str(guild_id), {}),
        "automod": cache.automod.get(str(guild_id), {}),
        "antinuke": cache.antinuke_settings.get(str(guild_id), {}),
        "j2c_settings": cache.j2c_settings.get(str(guild_id), {}),
        "music": cache.music.get(str(guild_id), {}),
        "command_access": cache.command_access.get(str(guild_id), {}),
        "giveaway_permissions": cache.giveaways_permissions.get(str(guild_id), {}),
        "welcomer": cache.welcomer_settings.get(str(guild_id), {}),
        "promote": cache.promote_channels.get(str(guild_id), {}),
        "ticket_modules": ticket_modules_list,
        "ticket_history": [],
        "image_ocr": cache.image_ocr_cache.get(str(guild_id), {}),
        "server_stats": cache.server_stats_cache.get(str(guild_id), {}),
        "economy_settings": {},
        "economy_audit": [],
        "shop_settings": {},
        "shop_products": [],
        "shop_orders": [],
        "levels_users": [],
        "rp_settings": _default_roleplay_dashboard_settings(),
        "rp_scenarios": [],
        "rp_event": {},
        "rp_characters_top": [],
        "rp_permissions": {},
        "rp_economy_guard": {},
        "rp_schedules": [],
        "rp_audit_logs": [],
        "rp_event_history": [],
        "rp_scenario_stats": [],
        "guildstyle_layout": {},
        "extra_protection": _extra_protection_settings_from_db(guild_id),
        "honeypot": _honeypot_settings_from_db(guild_id),
        "donate": cache.donate_settings_cache.get(str(guild_id), {}),
        "donate_slips": [],
        "alerts": _default_alerts_settings(),
        "verify": _normalize_verify_settings({}),
        "voice_randomizer": _voice_randomizer_settings_from_db(guild_id),
        "ai_chat": cache.ai_chat_channels.get(str(guild_id)) or {},
        "ai_memories": {},
        "auto_responder": [],
        "custom_roles": [],
        "custom_roles_permission": {},
        "media_channels": [],
        "channels": channels,
        "roles": roles,
    }


async def _ensure_guild_records(guild_id: int, bot_guild) -> dict[str, Any]:
    try:
        payload = await _ensure_guild_records_impl(guild_id, bot_guild)
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("dashboard_storage_degraded", False)
        payload.setdefault("dashboard_storage_error", "")
        return payload
    except Exception as error:
        _log_dashboard_storage_error("_ensure_guild_records", guild_id, error, min_interval_sec=25.0)
        fallback_payload = _fallback_dashboard_state(guild_id, bot_guild)
        fallback_payload["dashboard_storage_degraded"] = True
        fallback_payload["dashboard_storage_error"] = f"{type(error).__name__}: {error}"[:320]
        return fallback_payload


async def _ensure_guild_records_impl(guild_id: int, bot_guild) -> dict[str, Any]:
    guild_config = await _safe_get_or_insert(
        cache.guilds, storage.guilds, guild_id,
        owner_id=getattr(bot_guild, "owner_id", None),
        prefix=BOT_CONFIG.PREFIX,
        language="en",
        subscription="free",
    )
    automod_config = await _safe_get_or_insert(cache.automod, storage.automod, guild_id)
    antinuke_config = await _safe_get_or_insert(cache.antinuke_settings, storage.antinuke_settings, guild_id)
    j2c_settings_config = await _safe_get_or_insert(cache.j2c_settings, storage.j2c_settings, guild_id)
    music_config = await _safe_get_or_insert(cache.music, storage.music, guild_id)
    command_config = await _safe_get_or_insert(
        cache.command_access, storage.command_access, guild_id,
        disabled_commands=[],
    )
    giveaway_permissions = await _safe_get_or_insert(
        cache.giveaways_permissions, storage.giveaways_permissions, guild_id,
    )
    welcomer_config = await _safe_get_or_insert(
        cache.welcomer_settings, storage.welcomer_settings, guild_id,
    )
    try:
        promote_config = await storage.promote_channels.get(guild_id=guild_id) or {}
    except Exception:
        promote_config = {}
    if not promote_config:
        promote_config = cache.promote_channels.get(str(guild_id), {})
    ticket_modules = cache.ticket_settings.get(str(guild_id), {})
    if not ticket_modules:
        try:
            created_module = await storage.ticket_settings.insert(
                guild_id=guild_id,
                enabled=False,
                support_roles=[],
                ticket_limit=1,
                open_ticket_category_id=None,
                closed_ticket_category_id=None,
                ticket_panel_channel_id=None,
                ticket_panel_message_id=None,
                ticket_panel_message_content=None,
                ticket_panel_message_embed={},
                close_ticket_message_content=None,
                close_ticket_message_embed={},
            )
            if isinstance(created_module, dict):
                ticket_modules = {str(created_module.get("ticket_module_id") or 1): created_module}
        except Exception as error:
            _log_dashboard_storage_error("ticket_settings.insert", guild_id, error)
            ticket_modules = {}
    if not isinstance(ticket_modules, dict):
        ticket_modules = {}
    if not ticket_modules:
        ticket_modules = {str(1): _default_ticket_module_payload(guild_id)}
    try:
        ticket_history = await storage.tickets.gets(guild_id=guild_id) or []
    except Exception as error:
        _log_dashboard_storage_error("tickets.gets", guild_id, error)
        ticket_history = []
    server_stats_config = cache.server_stats_cache.get(str(guild_id)) or {}
    if not server_stats_config:
        try:
            server_stats_config = await storage.server_stats.get(guild_id=guild_id) or {}
        except Exception as error:
            if not _is_atlas_collection_limit_error(error):
                raise
            server_stats_config = {}
    if not server_stats_config:
        try:
            # Prefer creating a primary DB row when available to avoid
            # sticking to fallback/default payloads indefinitely.
            server_stats_config = await storage.server_stats.insert(guild_id=guild_id) or {}
        except Exception as error:
            if not _is_atlas_collection_limit_error(error):
                raise
            server_stats_config = {}
    if not server_stats_config:
        server_stats_config = await _get_server_stats_fallback(guild_id)

    image_ocr_config = cache.image_ocr_cache.get(str(guild_id)) or {}
    if not image_ocr_config:
        try:
            image_ocr_config = await storage.image_ocr_settings.get(guild_id=guild_id) or {}
        except Exception as error:
            if not _is_atlas_collection_limit_error(error):
                raise
            image_ocr_config = {}
    if not image_ocr_config:
        try:
            # Same approach as server stats: create a primary row first,
            # then fallback only when primary DB is unavailable.
            image_ocr_config = await storage.image_ocr_settings.insert(guild_id=guild_id) or {}
        except Exception as error:
            if not _is_atlas_collection_limit_error(error):
                raise
            image_ocr_config = {}
    if not image_ocr_config:
        image_ocr_config = await _get_image_ocr_fallback(guild_id)
    if isinstance(server_stats_config, dict):
        cache.server_stats_cache[str(guild_id)] = server_stats_config
    if isinstance(image_ocr_config, dict):
        cache.image_ocr_cache[str(guild_id)] = image_ocr_config

    donate_config = cache.donate_settings_cache.get(str(guild_id)) or {}
    if not donate_config:
        try:
            donate_config = await storage.donate_settings.get(guild_id=guild_id) or {}
        except Exception as error:
            _log_dashboard_storage_error("donate_settings.get", guild_id, error)
            donate_config = {}
    if not donate_config:
        donate_config = await _get_donate_fallback(guild_id) or {}
    if isinstance(donate_config, dict):
        cache.donate_settings_cache[str(guild_id)] = donate_config

    economy_settings = {}
    try:
        economy_settings = await storage.economy_settings.get(guild_id=guild_id) or {}
        if not economy_settings:
            await storage.economy_settings.insert(guild_id=guild_id)
            economy_settings = await storage.economy_settings.get(guild_id=guild_id) or {}
    except Exception:
        economy_settings = {}
    try:
        economy_audit_logs = await storage.economy_audit.gets(guild_id=guild_id) or []
    except Exception:
        economy_audit_logs = []
    economy_audit_logs = sorted(
        economy_audit_logs,
        key=lambda row: int(
            getattr(row.get("created_at"), "timestamp", lambda: 0)() if isinstance(row.get("created_at"), datetime.datetime) else 0
        ),
        reverse=True,
    )[:80]
    try:
        levels_rows = await storage.levels_users.gets(guild_id=guild_id) or []
    except Exception:
        levels_rows = []
    try:
        rp_settings = await storage.rp_settings.get(guild_id=guild_id) or {}
        if not rp_settings:
            await storage.rp_settings.insert(guild_id=guild_id)
            rp_settings = await storage.rp_settings.get(guild_id=guild_id) or {}
    except Exception:
        rp_settings = {}
    try:
        rp_scenarios = await storage.rp_scenarios.gets(guild_id=guild_id) or []
    except Exception:
        rp_scenarios = []
    rp_scenarios = sorted(
        [row for row in rp_scenarios if isinstance(row, dict)],
        key=lambda row: (
            0 if bool(row.get("is_preset")) else 1,
            str(row.get("name") or "").lower(),
        ),
    )[:240]
    try:
        rp_event = await storage.rp_events.get(guild_id=guild_id) or {}
    except Exception:
        rp_event = {}
    try:
        rp_characters_rows = await storage.rp_characters.gets(guild_id=guild_id) or []
    except Exception:
        rp_characters_rows = []
    rp_characters_top = sorted(
        [row for row in rp_characters_rows if isinstance(row, dict)],
        key=lambda row: int(row.get("xp") or 0),
        reverse=True,
    )[:120]
    try:
        rp_permissions = await storage.rp_permissions.get(guild_id=guild_id) or {}
        if not rp_permissions:
            await storage.rp_permissions.insert(guild_id=guild_id)
            rp_permissions = await storage.rp_permissions.get(guild_id=guild_id) or {}
    except Exception:
        rp_permissions = {}
    try:
        rp_economy_guard = await storage.rp_economy_guard.get(guild_id=guild_id) or {}
        if not rp_economy_guard:
            await storage.rp_economy_guard.insert(guild_id=guild_id)
            rp_economy_guard = await storage.rp_economy_guard.get(guild_id=guild_id) or {}
    except Exception:
        rp_economy_guard = {}
    try:
        rp_schedules = await storage.rp_schedules.gets(guild_id=guild_id) or []
    except Exception:
        rp_schedules = []
    rp_schedules = sorted(
        [row for row in rp_schedules if isinstance(row, dict)],
        key=lambda row: int(
            getattr(row.get("next_run_at"), "timestamp", lambda: 0)()
            if isinstance(row.get("next_run_at"), datetime.datetime)
            else 0
        ),
    )[:120]
    try:
        rp_audit_logs = await storage.rp_audit_logs.gets(guild_id=guild_id) or []
    except Exception:
        rp_audit_logs = []
    rp_audit_logs = sorted(
        [row for row in rp_audit_logs if isinstance(row, dict)],
        key=lambda row: int(
            getattr(row.get("created_at"), "timestamp", lambda: 0)()
            if isinstance(row.get("created_at"), datetime.datetime)
            else 0
        ),
        reverse=True,
    )[:120]
    try:
        rp_event_history = await storage.rp_event_history.gets(guild_id=guild_id) or []
    except Exception:
        rp_event_history = []
    rp_event_history = sorted(
        [row for row in rp_event_history if isinstance(row, dict)],
        key=lambda row: int(
            getattr(
                row.get("ended_at") if isinstance(row.get("ended_at"), datetime.datetime) else row.get("created_at"),
                "timestamp",
                lambda: 0,
            )()
            if isinstance(row.get("ended_at"), datetime.datetime) or isinstance(row.get("created_at"), datetime.datetime)
            else 0
        ),
        reverse=True,
    )[:180]
    try:
        rp_scenario_stats = await storage.rp_scenario_stats.gets(guild_id=guild_id) or []
    except Exception:
        rp_scenario_stats = []
    rp_scenario_stats = sorted(
        [row for row in rp_scenario_stats if isinstance(row, dict)],
        key=lambda row: (int(row.get("play_count") or 0), int(row.get("event_start_count") or 0)),
        reverse=True,
    )[:180]
    try:
        guildstyle_layout_row = await storage.ops_hub_records.get(
            guild_id=guild_id,
            kind="config",
            key="guildstyle_layout",
        ) or {}
    except Exception:
        guildstyle_layout_row = {}
    guildstyle_layout_payload = (
        guildstyle_layout_row.get("data")
        if isinstance(guildstyle_layout_row, dict)
        else {}
    )
    guildstyle_layout = (
        dict(guildstyle_layout_payload)
        if isinstance(guildstyle_layout_payload, dict)
        else {}
    )
    try:
        shop_settings = await storage.shop_settings.get(guild_id=guild_id) or {}
        if not shop_settings:
            await storage.shop_settings.insert(guild_id=guild_id)
            shop_settings = await storage.shop_settings.get(guild_id=guild_id) or {}
    except Exception:
        shop_settings = {}
    try:
        shop_products = await storage.shop_products.gets(guild_id=guild_id) or []
    except Exception:
        shop_products = []
    try:
        shop_orders = await storage.shop_orders.gets(guild_id=guild_id) or []
    except Exception:
        shop_orders = []
    shop_orders = sorted(
        shop_orders,
        key=lambda row: int(
            getattr(row.get("created_at"), "timestamp", lambda: 0)()
            if isinstance(row.get("created_at"), datetime.datetime)
            else 0
        ),
        reverse=True,
    )[:120]
    donate_slips = await _get_donate_slip_logs(guild_id)
    alerts_settings = await _get_alerts_fallback(guild_id)
    verify_settings = await _get_verify_fallback(guild_id)
    ai_chat_config = cache.ai_chat_channels.get(str(guild_id)) or {}
    if not ai_chat_config:
        try:
            ai_chat_config = await storage.ai_chat_channels.get(guild_id=guild_id) or {}
        except Exception as error:
            _log_dashboard_storage_error("ai_chat_channels.get", guild_id, error)
            ai_chat_config = {}
    try:
        ai_memories = await storage.ai_memories.get(target_id=guild_id, type="guild") or {}
    except Exception as error:
        _log_dashboard_storage_error("ai_memories.get", guild_id, error)
        ai_memories = {}
    try:
        auto_responder_rows = await storage.auto_responder.gets(guild_id=guild_id) or []
    except Exception as error:
        _log_dashboard_storage_error("auto_responder.gets", guild_id, error)
        auto_responder_rows = []
    try:
        custom_roles_rows = await storage.custom_roles.gets(guild_id=guild_id) or []
    except Exception as error:
        _log_dashboard_storage_error("custom_roles.gets", guild_id, error)
        custom_roles_rows = []
    try:
        custom_roles_permission = await storage.custom_roles_permissions.get(guild_id=guild_id) or {}
    except Exception as error:
        _log_dashboard_storage_error("custom_roles_permissions.get", guild_id, error)
        custom_roles_permission = {}
    try:
        media_channels_rows = await storage.media_channels.gets(guild_id=guild_id) or []
    except Exception as error:
        _log_dashboard_storage_error("media_channels.gets", guild_id, error)
        media_channels_rows = []
    ticket_modules_list = [row for row in list(ticket_modules.values()) if isinstance(row, dict)]
    if not ticket_modules_list:
        ticket_modules_list = [_default_ticket_module_payload(guild_id)]

    return {
        "guild": guild_config or cache.guilds.get(str(guild_id), {}),
        "automod": automod_config or cache.automod.get(str(guild_id), {}),
        "antinuke": antinuke_config or cache.antinuke_settings.get(str(guild_id), {}),
        "j2c_settings": j2c_settings_config or cache.j2c_settings.get(str(guild_id), {}),
        "music": music_config or cache.music.get(str(guild_id), {}),
        "command_access": command_config or cache.command_access.get(str(guild_id), {}),
        "giveaway_permissions": giveaway_permissions or cache.giveaways_permissions.get(str(guild_id), {}),
        "welcomer": welcomer_config or cache.welcomer_settings.get(str(guild_id), {}),
        "promote": promote_config,
        "ticket_modules": ticket_modules_list,
        "ticket_history": ticket_history,
        "image_ocr": image_ocr_config,
        "server_stats": server_stats_config,
        "economy_settings": economy_settings,
        "economy_audit": economy_audit_logs,
        "shop_settings": shop_settings,
        "shop_products": shop_products,
        "shop_orders": shop_orders,
        "levels_users": levels_rows,
        "rp_settings": rp_settings,
        "rp_scenarios": rp_scenarios,
        "rp_event": rp_event,
        "rp_characters_top": rp_characters_top,
        "rp_permissions": rp_permissions,
        "rp_economy_guard": rp_economy_guard,
        "rp_schedules": rp_schedules,
        "rp_audit_logs": rp_audit_logs,
        "rp_event_history": rp_event_history,
        "rp_scenario_stats": rp_scenario_stats,
        "guildstyle_layout": guildstyle_layout,
        "extra_protection": _extra_protection_settings_from_db(guild_id),
        "honeypot": _honeypot_settings_from_db(guild_id),
        "donate": donate_config,
        "donate_slips": donate_slips,
        "alerts": alerts_settings,
        "verify": verify_settings,
        "voice_randomizer": _voice_randomizer_settings_from_db(guild_id),
        "ai_chat": ai_chat_config,
        "ai_memories": ai_memories,
        "auto_responder": auto_responder_rows,
        "custom_roles": custom_roles_rows,
        "custom_roles_permission": custom_roles_permission,
        "media_channels": media_channels_rows,
        "channels": [{"id": str(c.id), "name": c.name, "type": str(c.type)} for c in bot_guild.channels],
        "roles": [{"id": str(r.id), "name": r.name, "color": str(r.color)} for r in bot_guild.roles if not r.is_default()],
    }


def _music_snapshot(bot_guild) -> dict[str, Any]:
    voice_client = getattr(bot_guild, "voice_client", None)
    current = getattr(voice_client, "current", None)
    if not voice_client or not current:
        return {
            "active": False,
            "title": "",
            "author": "",
            "uri": "",
            "artwork": MUSIC_IDLE_IMAGE_ROUTE,
            "position": "0s",
            "duration": "0s",
            "position_ms": 0,
            "duration_ms": 0,
            "queue_size": 0,
            "queue_titles": [],
            "queue_entries": [],
            "volume": 0,
            "paused": False,
            "autoplay": False,
            "loop": False,
            "channel": "-",
        }
    queue_items = list(getattr(voice_client, "queue", []))
    queue_entries = [
        {
            "index": index,
            "title": getattr(track, "title", "Unknown"),
            "duration": _format_ms(getattr(track, "length", 0)),
        }
        for index, track in enumerate(queue_items[:25], start=1)
    ]
    queue_mode = getattr(getattr(voice_client, "queue", None), "mode", None)
    artwork = getattr(current, "artwork", None) or getattr(current, "artwork_url", None) or style_urls.DEFAULT_MUSIC_BANNER
    return {
        "active": True,
        "title": current.title,
        "author": current.author,
        "uri": getattr(current, "uri", ""),
        "artwork": artwork,
        "position": _format_ms(getattr(voice_client, "position", 0)),
        "duration": _format_ms(getattr(current, "length", 0)),
        "position_ms": max(0, int(getattr(voice_client, "position", 0) or 0)),
        "duration_ms": max(0, int(getattr(current, "length", 0) or 0)),
        "queue_size": len(queue_items),
        "queue_titles": [getattr(track, "title", "Unknown") for track in queue_items[:5]],
        "queue_entries": queue_entries,
        "volume": getattr(voice_client, "volume", 0),
        "paused": getattr(voice_client, "paused", False),
        "autoplay": bool(getattr(voice_client, "autoplay", None) != wavelink.AutoPlayMode.disabled),
        "loop": bool(queue_mode == wavelink.QueueMode.loop),
        "channel": getattr(getattr(voice_client, "channel", None), "name", "Unknown"),
    }


def _active_music_client(bot_guild):
    voice_client = getattr(bot_guild, "voice_client", None)
    if not voice_client:
        return None
    if not getattr(voice_client, "connected", True):
        return None
    return voice_client


def _music_search_results_after_pick(
    tracks: list[Any],
    *,
    picked_index: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    shifted_tracks = list(tracks or [])
    delete_at = max(1, int(picked_index)) - 1
    if 0 <= delete_at < len(shifted_tracks):
        shifted_tracks.pop(delete_at)
    return _music_search_results_payload(shifted_tracks, limit=limit)


def _translate_category_th(category: str) -> str:
    return _dashboard_localization_domain.translate_category_th(
        category,
        i18n_module=i18n,
    )


def _localize_command(command: dict[str, Any], language: str = "en") -> dict[str, Any]:
    return _dashboard_localization_domain.localize_command(
        command,
        language=language,
        i18n_module=i18n,
        translate_brief_th_fn=_translate_brief_th,
        translate_category_th_fn=_translate_category_th,
    )


def _render_meter(label: str, value: int, maximum: int, tone: str = "blue") -> str:
    return _dashboard_status_ui_utils.render_meter(
        label,
        value,
        maximum,
        tone,
        escape_fn=_escape,
    )


def _guild_health(guild: dict[str, Any]) -> int:
    members_score = min(40, int((guild["members"] / 1500) * 40)) if guild["members"] else 0
    channels_score = min(30, int((guild["channels"] / 75) * 30)) if guild["channels"] else 0
    roles_score = min(30, int((guild["roles"] / 75) * 30)) if guild["roles"] else 0
    return members_score + channels_score + roles_score


def _chart_block(title: str, items: list[tuple[str, int, str]]) -> str:
    bars = []
    peak = max((item[1] for item in items), default=1)
    for label, value, tone in items:
        width = max(8, int((value / peak) * 100)) if peak else 8
        bars.append(
            '<div class="chart-row">'
            f'<span>{_escape(label)}</span>'
            f'<div class="chart-bar {tone}"><div class="chart-fill" style="width:{width}%"></div></div>'
            f'<strong>{value}</strong>'
            "</div>"
        )
    return f'<section class="panel"><h2>{_escape(title)}</h2><div class="chart-pack">{"".join(bars)}</div></section>'


def _recent_logs() -> list[str]:
    now_ts = time.monotonic()
    cached_rows = _RECENT_LOGS_CACHE.get("value")
    cached_expires_at = float(_RECENT_LOGS_CACHE.get("expires_at") or 0.0)
    if now_ts < cached_expires_at and isinstance(cached_rows, list) and cached_rows:
        return list(cached_rows)

    if not LOGS_DIR.exists():
        rows = ["ยังไม่พบโฟลเดอร์บันทึกล็อก"]
    else:
        log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)
        if not log_files:
            rows = ["ยังไม่พบไฟล์ล็อก"]
        else:
            content = log_files[0].read_text(encoding="utf-8", errors="ignore").splitlines()
            cleaned = [_clean_text(line) for line in content[-80:]]
            rows = cleaned or ["ไฟล์ล็อกล่าสุดยังว่างอยู่"]

    _RECENT_LOGS_CACHE["value"] = list(rows)
    _RECENT_LOGS_CACHE["expires_at"] = now_ts + _RECENT_LOGS_CACHE_TTL_SECONDS
    return rows


_BKK_TZ = datetime.timezone(datetime.timedelta(hours=7))


def _month_start_local(dt: datetime.datetime) -> datetime.datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month_local(dt: datetime.datetime, delta_months: int) -> datetime.datetime:
    base = _month_start_local(dt)
    month_index = (base.year * 12 + (base.month - 1)) + int(delta_months)
    year = month_index // 12
    month = (month_index % 12) + 1
    return base.replace(year=year, month=month, day=1)


def _axis_for_overview_period(
    period_key: str,
    now_local: datetime.datetime,
    history: list[dict[str, int]],
) -> tuple[list[int], int, list[str]]:
    period = str(period_key or "7d").strip().lower()
    current_hour = now_local.replace(minute=0, second=0, microsecond=0)
    current_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    current_month = _month_start_local(now_local)

    axis_local: list[datetime.datetime]
    end_local: datetime.datetime
    label_fmt: str

    if period == "today":
        axis_local = [current_day + datetime.timedelta(hours=index) for index in range(now_local.hour + 1)]
        end_local = current_hour + datetime.timedelta(hours=1)
        label_fmt = "hour"
    elif period == "7d":
        start_day = current_day - datetime.timedelta(days=6)
        axis_local = [start_day + datetime.timedelta(days=index) for index in range(7)]
        end_local = current_day + datetime.timedelta(days=1)
        label_fmt = "day"
    elif period == "1m":
        start_day = current_day - datetime.timedelta(days=29)
        axis_local = [start_day + datetime.timedelta(days=index) for index in range(30)]
        end_local = current_day + datetime.timedelta(days=1)
        label_fmt = "day"
    elif period == "1y":
        start_month = _shift_month_local(current_month, -11)
        axis_local = [_shift_month_local(start_month, index) for index in range(12)]
        end_local = _shift_month_local(current_month, 1)
        label_fmt = "month"
    else:
        history_local_ts: list[datetime.datetime] = []
        for row in history:
            try:
                ts_ms = int(row.get("ts") or 0)
            except Exception:
                ts_ms = 0
            if ts_ms > 0:
                history_local_ts.append(
                    datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc).astimezone(_BKK_TZ)
                )
        first_month = _month_start_local(min(history_local_ts)) if history_local_ts else current_month
        axis_local = []
        cursor = first_month
        hard_limit = 60
        while cursor <= current_month and len(axis_local) < hard_limit:
            axis_local.append(cursor)
            cursor = _shift_month_local(cursor, 1)
        if not axis_local:
            axis_local = [current_month]
        end_local = _shift_month_local(axis_local[-1], 1)
        label_fmt = "month"

    axis_ms = [
        int(slot.astimezone(datetime.timezone.utc).timestamp() * 1000)
        for slot in axis_local
    ]
    end_ms = int(end_local.astimezone(datetime.timezone.utc).timestamp() * 1000)

    labels: list[str] = []
    for slot in axis_local:
        if label_fmt == "hour":
            labels.append(slot.strftime("%H:%M"))
        elif label_fmt == "day":
            labels.append(slot.strftime("%d/%m"))
        else:
            labels.append(slot.strftime("%m/%y"))
    return axis_ms, end_ms, labels


def _overview_activity_periods(
    history: list[dict[str, int]],
    *,
    current_member_count: int,
) -> dict[str, dict[str, Any]]:
    now_local = datetime.datetime.now(tz=datetime.timezone.utc).astimezone(_BKK_TZ)
    periods = ("today", "7d", "1m", "1y", "all")
    output: dict[str, dict[str, Any]] = {}

    for period in periods:
        axis_ms, end_ms, labels = _axis_for_overview_period(period, now_local, history)
        points = len(axis_ms)
        joins = [0] * points
        leaves = [0] * points
        messages = [0] * points

        if points > 0:
            start_ms = axis_ms[0]
            for row in history:
                try:
                    ts_ms = int(row.get("ts") or 0)
                except Exception:
                    ts_ms = 0
                if ts_ms < start_ms or ts_ms >= end_ms:
                    continue
                idx = bisect.bisect_right(axis_ms, ts_ms) - 1
                if idx < 0 or idx >= points:
                    continue
                joins[idx] += max(0, int(row.get("joins") or 0))
                leaves[idx] += max(0, int(row.get("leaves") or 0))
                messages[idx] += max(0, int(row.get("messages") or 0))

        traffic = [int(joins[i] + leaves[i]) for i in range(points)]
        delta_members = [int(joins[i] - leaves[i]) for i in range(points)]
        total_delta = sum(delta_members)
        starting_members = max(0, int(current_member_count or 0) - total_delta)
        member_series: list[int] = []
        running_members = starting_members
        for delta in delta_members:
            running_members = max(0, running_members + int(delta))
            member_series.append(running_members)

        output[period] = {
            "labels": labels,
            "join_series": traffic,
            "member_series": member_series,
            "message_series": [int(value) for value in messages],
            "joins_total": int(sum(joins)),
            "leaves_total": int(sum(leaves)),
            "messages_total": int(sum(messages)),
        }

    return output


def _parse_moderation_log_rows(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in lines:
        lower = line.lower()
        action_key = ""
        action_label = ""
        if "ban" in lower:
            action_key = "ban"
            action_label = "แบน"
        elif "mute" in lower or "timeout" in lower:
            action_key = "mute"
            action_label = "ปิดเสียง"
        elif "warn" in lower or "warning" in lower:
            action_key = "warn"
            action_label = "เตือน"
        if not action_key:
            continue

        user_id_match = re.search(r"\b(\d{15,22})\b", line)
        user_id = user_id_match.group(1) if user_id_match else "-"
        hhmmss_match = re.search(r"\b(\d{2}:\d{2}:\d{2})\b", line)
        punished_at = hhmmss_match.group(1) if hhmmss_match else "-"
        by_match = re.search(r"\bby\s+([^\|\n]+)", line, flags=re.IGNORECASE)
        responsible = by_match.group(1).strip()[:80] if by_match else "ระบบอัตโนมัติ"
        rows.append(
            {
                "member": user_id,
                "action": action_label,
                "action_key": action_key,
                "responsible": responsible,
                "punish_time": "-",
                "remaining": "-",
                "punished_at": punished_at,
                "raw": line,
            }
        )
    return rows[:300]


def _music_extract_named_context(raw: str, key: str) -> str:
    pattern = rf"{re.escape(key)}\s*=\s*\d+\(([^)]+)\)"
    matched = re.search(pattern, raw, flags=re.IGNORECASE)
    if matched:
        return _clean_text(matched.group(1)).strip()
    pattern_fallback = rf"{re.escape(key)}\s*=\s*([^\|\s]+)"
    fallback = re.search(pattern_fallback, raw, flags=re.IGNORECASE)
    if fallback:
        return _clean_text(fallback.group(1)).strip()
    return ""


def _music_clean_event_text(raw: str, fallback: str = "-") -> str:
    value = _clean_text(raw).replace("\\n", " ").strip().strip("'\"")
    value = re.sub(r"\s+", " ", value)
    if not value:
        return fallback
    if not re.search(r"[A-Za-z0-9\u0E00-\u0E7F]", value):
        return fallback
    return value[:90]


def _music_event_timestamp(raw: str) -> str:
    matched = re.search(r"\b(\d{2}:\d{2}:\d{2})\b", raw)
    if matched:
        return matched.group(1)
    return "--:--:--"


def _music_event_summary(
    raw_line: str,
    *,
    guild_id: int | None = None,
    guild_name: str | None = None,
) -> str | None:
    raw = _clean_text(raw_line).strip()
    if not raw:
        return None
    line = re.sub(r"\s+", " ", raw.replace("\\n", " ")).strip()
    lower = line.lower()
    music_context = any(
        token in lower
        for token in (
            "music",
            "track",
            "player",
            "queue",
            "lavalink",
            "wavelink",
            "voice",
            "controller",
        )
    )
    network_context = any(
        token in lower
        for token in (
            "winerror 64",
            "clientoserror",
            "connectionreseterror",
            "temporary network error while",
            "network name is no longer available",
        )
    )

    if not music_context and not network_context:
        return None

    if guild_id:
        guild_token = f"guild={int(guild_id)}"
        if "guild=" in lower and guild_token not in lower:
            return None
    if guild_name:
        guild_name_lower = str(guild_name).strip().lower()
        if " player " in lower and guild_name_lower and guild_name_lower not in lower:
            return None

    timestamp = _music_event_timestamp(line)
    prefix = f"[{timestamp}] "

    if any(token in lower for token in ("traceback", " in file ", "site-packages", "line ")):
        if any(token in lower for token in ("winerror 64", "clientoserror", "connectionreseterror", "network name is no longer available")):
            return f"{prefix}ERR เครือข่ายไม่เสถียรขณะอัปเดตระบบเพลง (ระบบกำลังลองใหม่อัตโนมัติ)"
        return f"{prefix}ERR เกิดข้อผิดพลาดในระบบเพลง (ซ่อนรายละเอียดภายใน)"

    if "temporary network error while" in lower:
        return f"{prefix}WARN เครือข่ายไม่เสถียรขณะอัปเดตแผงควบคุมเพลง"

    if "[music_action]" in lower:
        actor = _music_clean_event_text(_music_extract_named_context(line, "actor"), "ผู้ใช้")
        channel = _music_clean_event_text(_music_extract_named_context(line, "channel"), "ห้องเสียง")
        action_match = re.search(r"action=([a-z_]+)", line, flags=re.IGNORECASE)
        action_key = str(action_match.group(1) if action_match else "").strip().lower()
        action_labels = {
            "pause_toggle": "เล่น/พักเพลง",
            "skip": "ข้ามเพลง",
            "previous": "เล่นเพลงก่อนหน้า",
            "seek_backward": "ย้อนเพลง 10 วินาที",
            "seek_forward": "เลื่อนเพลง 10 วินาที",
            "seek_to": "เลื่อนไปตำแหน่งที่เลือก",
            "loop_toggle": "สลับโหมดวนซ้ำ",
            "autoplay_toggle": "Autoplay toggle",
            "shuffle_queue": "Shuffle queue",
            "stop": "หยุดเพลงและให้บอทออกห้อง",
            "volume_up": "เพิ่มเสียง",
            "volume_down": "ลดเสียง",
            "set_volume": "ตั้งค่าระดับเสียง",
            "delete_queue": "ลบเพลงออกจากคิว",
            "move_queue_up": "เลื่อนคิวขึ้น",
            "move_queue_down": "เลื่อนคิวลง",
            "play_queue_now": "เล่นเพลงจากคิวทันที",
            "add_track": "เพิ่มเพลง",
            "add_track_at": "เพิ่มเพลงจากผลค้นหา",
            "add_playlist": "เพิ่มเพลย์ลิสต์",
        }
        action_label = action_labels.get(action_key, _music_clean_event_text(action_key.replace("_", " "), "ควบคุมเพลง"))
        return f"{prefix}{actor} ทำรายการ: {action_label} ที่ {channel}"

    if "track end event received for track:" in lower:
        matched = re.search(r"track end event received for track:\s*(.+)$", line, flags=re.IGNORECASE)
        title = _music_clean_event_text(matched.group(1) if matched else "", "ไม่ทราบชื่อเพลง")
        return f"{prefix}เพลงจบ: {title}"

    if "has started playing on player" in lower:
        matched = re.search(
            r"track\s+(.+?)\s+has started playing on player\s+(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        title = _music_clean_event_text(matched.group(1) if matched else "", "ไม่ทราบชื่อเพลง")
        player = _music_clean_event_text(matched.group(2) if matched else "", "")
        if player and player != "-":
            return f"{prefix}เริ่มเล่นเพลง: {title} ({player})"
        return f"{prefix}เริ่มเล่นเพลง: {title}"

    if "playing next track:" in lower:
        matched = re.search(r"playing next track:\s*(.+)$", line, flags=re.IGNORECASE)
        title = _music_clean_event_text(matched.group(1) if matched else "", "ไม่ทราบชื่อเพลง")
        return f"{prefix}เล่นเพลงถัดไป: {title}"

    if "queue is empty" in lower:
        return f"{prefix}คิวเพลงว่าง"

    if "disconnect" in lower and any(token in lower for token in ("voice", "player", "music")):
        return f"{prefix}บอทออกจากห้องเสียง"

    if "[lavalink_connect] connected successfully" in lower or ("node " in lower and " is ready" in lower):
        return f"{prefix}ระบบเพลงเชื่อมต่อสำเร็จ"

    if "[music_setup]" in lower and "step 1 received" in lower:
        actor = _music_clean_event_text(_music_extract_named_context(line, "author"), "ผู้ใช้")
        channel = _music_clean_event_text(_music_extract_named_context(line, "channel"), "ห้องข้อความ")
        query_match = re.search(r"content='([^']*)'", line, flags=re.IGNORECASE)
        query = _music_clean_event_text(query_match.group(1) if query_match else "", "")
        if query and query != "-":
            return f"{prefix}เริ่มคำขอเพลงโดย {actor} ที่ {channel} (ค้นหา: {query})"
        return f"{prefix}เริ่มคำขอเพลงโดย {actor} ที่ {channel}"

    if "[music_setup]" in lower and ("step 3a connecting" in lower or "step 3b connected" in lower):
        channel = _music_clean_event_text(_music_extract_named_context(line, "channel"), "")
        if "connected" in lower:
            return f"{prefix}บอทเข้าห้องเสียงสำเร็จ{f' ({channel})' if channel and channel != '-' else ''}"
        return f"{prefix}บอทกำลังเข้าห้องเสียง{f' ({channel})' if channel and channel != '-' else ''}"

    if "[music_setup]" in lower and "step 4 searching" in lower:
        query_match = re.search(r"query=([\"'])(.+?)\1", line, flags=re.IGNORECASE)
        query = _music_clean_event_text(query_match.group(2) if query_match else "", "")
        if query and query != "-":
            return f"{prefix}กำลังค้นหาเพลง: {query}"
        return f"{prefix}กำลังค้นหาเพลง"

    if "[music_setup]" in lower and "step 4b search results" in lower:
        count_match = re.search(r"count\s*=\s*(\d+)", line, flags=re.IGNORECASE)
        result_count = int(count_match.group(1)) if count_match else 0
        if result_count > 0:
            return f"{prefix}พบผลการค้นหา {result_count} รายการ"
        return f"{prefix}ไม่พบผลการค้นหาเพลง"

    if "[music_setup]" in lower and "step 5 queue full" in lower:
        return f"{prefix}เพิ่มเพลงไม่สำเร็จ: คิวเต็ม"

    if "[music_setup]" in lower:
        return None

    if any(token in lower for token in ("music", "track", "queue", "player", "lavalink")):
        if any(token in lower for token in ("c:\\", "site-packages", "traceback", " in file ")):
            return f"{prefix}ERR เกิดข้อผิดพลาดในระบบเพลง (ซ่อนรายละเอียดภายใน)"
        return None
    return None


def _music_log_lines(
    limit: int = 8,
    *,
    guild_id: int | None = None,
    guild_name: str | None = None,
) -> list[str]:
    lines = _recent_logs()
    events: list[str] = []
    for line in lines:
        expanded_parts = [line]
        if "\\n" in line:
            expanded_parts = [part for part in line.split("\\n") if str(part or "").strip()]
        for part in expanded_parts:
            summary = _music_event_summary(
                part,
                guild_id=guild_id,
                guild_name=guild_name,
            )
            if not summary:
                continue
            if events and events[-1] == summary:
                continue
            events.append(summary)
    safe_limit = max(1, int(limit or 8))
    return events[-safe_limit:] or ["ยังไม่มีกิจกรรมเพลงล่าสุด"]


def _live_payload(
    current_guild: dict[str, Any],
    bot_guild,
    state: dict[str, Any],
    *,
    tab: str | None = None,
) -> dict[str, Any]:
    normalized_tab = str(tab or "").strip().lower()
    if normalized_tab not in {"", "overview", "music", "logs"}:
        normalized_tab = ""

    include_overview = normalized_tab in {"", "overview"}
    include_music = normalized_tab in {"", "overview", "music"}
    include_music_logs = normalized_tab in {"", "overview", "music"}
    include_logs = normalized_tab in {"", "logs"}

    guild_id = None
    guild_name = ""
    try:
        guild_id = int(current_guild.get("id"))
    except Exception:
        guild_id = None
    try:
        guild_name = str(current_guild.get("name") or "").strip()
    except Exception:
        guild_name = ""

    payload: dict[str, Any] = {}
    if include_music:
        payload["music"] = _music_snapshot(bot_guild)
    if include_overview:
        metrics = _overview_metrics(current_guild, state, bot_guild)
        payload["overview"] = {
            "guild_health": _guild_health(current_guild),
            "security": metrics["security"],
            "moderation": metrics["moderation"],
        }
    if include_music_logs:
        payload["music_logs"] = _music_log_lines(guild_id=guild_id, guild_name=guild_name)
    if include_logs:
        payload["logs"] = _recent_logs()
    return payload


def _live_options_payload(bot_guild: Any, *, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = ""
    channel_count = 0
    role_count = 0
    if bot_guild:
        try:
            cache_key = str(int(getattr(bot_guild, "id", 0) or 0))
        except Exception:
            cache_key = ""
        try:
            channel_count = len(getattr(bot_guild, "channels", []) or [])
        except Exception:
            channel_count = 0
        try:
            role_count = len(getattr(bot_guild, "roles", []) or [])
        except Exception:
            role_count = 0

    now_ts = time.monotonic()
    if cache_key and not force_refresh:
        cached = _LIVE_OPTIONS_CACHE.get(cache_key) or {}
        cached_expires_at = float(cached.get("expires_at") or 0.0)
        if (
            now_ts < cached_expires_at
            and int(cached.get("channel_count") or -1) == channel_count
            and int(cached.get("role_count") or -1) == role_count
            and isinstance(cached.get("payload"), dict)
        ):
            return dict(cached["payload"])

    channels: list[dict[str, str]] = []
    roles: list[dict[str, str]] = []
    if bot_guild:
        sorted_channels = sorted(
            bot_guild.channels,
            key=lambda c: (
                getattr(getattr(c, "category", None), "position", -1),
                getattr(c, "position", 0),
                str(getattr(c, "name", "")).lower(),
            ),
        )
        for channel in sorted_channels:
            ctype = str(getattr(channel, "type", ""))
            channels.append(
                {
                    "id": str(channel.id),
                    "name": str(channel.name),
                    "type": ctype,
                }
            )
        sorted_roles = sorted(bot_guild.roles, key=lambda r: r.position, reverse=True)
        for role in sorted_roles:
            if role.is_default():
                continue
            roles.append(
                {
                    "id": str(role.id),
                    "name": str(role.name),
                }
            )
    signature_source = json.dumps({"channels": channels, "roles": roles}, ensure_ascii=False, separators=(",", ":"))
    signature = hashlib.md5(signature_source.encode("utf-8")).hexdigest()[:16]
    payload = {
        "channels": channels,
        "roles": roles,
        "signature": signature,
    }
    if cache_key:
        _LIVE_OPTIONS_CACHE[cache_key] = {
            "expires_at": now_ts + _LIVE_OPTIONS_CACHE_TTL_SECONDS,
            "channel_count": channel_count,
            "role_count": role_count,
            "payload": payload,
        }
        if len(_LIVE_OPTIONS_CACHE) > 400:
            stale_keys = [
                key
                for key, item in _LIVE_OPTIONS_CACHE.items()
                if float((item or {}).get("expires_at") or 0.0) <= now_ts
            ]
            for key in stale_keys[:200]:
                _LIVE_OPTIONS_CACHE.pop(key, None)
    return payload


def _status_tail_log_lines(limit: int = 500) -> list[str]:
    return _dashboard_overview_domain.status_tail_log_lines(
        limit=limit,
        logs_dir=LOGS_DIR,
        clean_text_fn=_clean_text,
    )


def _status_level_label(level: str) -> str:
    return _dashboard_overview_domain.status_level_label(level)

def _status_level_rank(level: str) -> int:
    return _dashboard_overview_domain.status_level_rank(level)

def _status_overall_level(levels: list[str]) -> str:
    return _dashboard_overview_domain.status_overall_level(levels)

def _format_uptime_seconds(total_seconds: int | float | None) -> str:
    return _dashboard_overview_domain.format_uptime_seconds(total_seconds)


def _status_extract_command_errors(log_lines: list[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    return _dashboard_overview_domain.status_extract_command_errors(
        log_lines,
        clean_text_fn=_clean_text,
    )

def _status_extract_incidents(log_lines: list[str], limit: int = 12) -> list[str]:
    return _dashboard_overview_domain.status_extract_incidents(
        log_lines,
        clean_text_fn=_clean_text,
        limit=limit,
    )

def _render_channel_select(
    name: str,
    bot_guild: Any,
    current_id: Any = None,
    placeholder: str = "เลือกช่อง...",
    filter_types: list[str] | None = None,
    disabled: bool = False,
) -> str:
    return _dashboard_status_ui_utils.render_channel_select(
        name,
        bot_guild,
        current_id,
        placeholder,
        filter_types=filter_types,
        disabled=disabled,
        escape_fn=_escape,
    )

def _render_multi_role_select(name: str, bot_guild: Any, current_ids: list[Any] = None) -> str:
    return _dashboard_status_ui_utils.render_multi_role_select(
        name,
        bot_guild,
        current_ids,
        escape_fn=_escape,
    )

def _parse_developer_social_links(value: Any) -> dict[str, dict[str, dict[str, str]]]:
    return _dashboard_social_utils.parse_developer_social_links(
        value,
        social_platform_keys=SOCIAL_PLATFORM_KEYS,
        normalize_social_url_fn=_normalize_social_url,
        normalize_social_url_for_platform_fn=_normalize_social_url_for_platform,
        normalize_social_icon_fn=_normalize_social_icon,
        json_loads_fn=json.loads,
    )


def _render_developer_social_icon(icon_value: Any, platform: str) -> str:
    platform_key = str(platform or "").strip().lower()
    normalized_icon = _normalize_social_icon(icon_value, platform_key)
    icon_lower = normalized_icon.lower()
    is_remote_icon = icon_lower.startswith("http://") or icon_lower.startswith("https://")
    is_relative_icon = normalized_icon.startswith("/") and not normalized_icon.startswith("//")
    if is_remote_icon or is_relative_icon:
        return _dashboard_social_utils.render_developer_social_icon(
            normalized_icon,
            platform,
            normalize_social_icon_fn=_normalize_social_icon,
            default_icons=SOCIAL_PLATFORM_DEFAULT_ICONS,
            social_labels=SOCIAL_PLATFORM_LABELS,
            escape_fn=_escape,
        )

    icon_class = SOCIAL_PLATFORM_ICON_CLASSES.get(platform_key, "")
    if icon_class:
        return f'<i class="{_escape(icon_class)}" aria-hidden="true"></i>'

    return _dashboard_social_utils.render_developer_social_icon(
        normalized_icon,
        platform,
        normalize_social_icon_fn=_normalize_social_icon,
        default_icons=SOCIAL_PLATFORM_DEFAULT_ICONS,
        social_labels=SOCIAL_PLATFORM_LABELS,
        escape_fn=_escape,
    )


def _validate_promote_content(content: str, blocked_words: list[str]) -> tuple[bool, str]:
    normalized = _normalize_promote_blocked_words(
        [
            *list(PROMOTE_DEFAULT_BLOCKED_WORDS),
            *(blocked_words or []),
        ]
    )
    return _dashboard_promote_utils.validate_promote_content(
        content,
        normalized,
        hard_block_words=PROMOTE_HARD_BLOCK_WORDS,
        clean_text_fn=_clean_text,
    )


async def _send_promote_feedback_to_discord(
    *,
    bot_guild: Any,
    submit_channel_id: Any,
    user_id: str,
    ok: bool,
    message: str,
) -> None:
    try:
        channel_id_int = int(str(submit_channel_id or "").strip())
    except Exception:
        return
    channel = bot_guild.get_channel(channel_id_int) if bot_guild else None
    if not channel:
        return
    tone = "[OK]" if ok else "[WARN]"
    try:
        await channel.send(f"{tone} <@{user_id}> {message}")
    except Exception:
        pass


def _normalize_http_url(raw: Any) -> str:
    return _dashboard_utils_domain.normalize_http_url(raw)


def _global_donatebot_settings() -> dict[str, str]:
    return _dashboard_donate_utils.global_donatebot_settings(
        first_env_value_fn=_first_env_value,
        normalize_http_url_fn=_normalize_http_url,
        support_server_url=style_urls.SUPPORT_SERVER,
    )


async def _verify_truemoney_gift_link(link: str) -> tuple[str, str]:
    normalized_link = str(link or "").strip()
    if not TRUEMONEY_GIFT_LINK_RE.match(normalized_link):
        return "rejected", "ลิงก์ของขวัญไม่ถูกต้อง (ตัวอย่าง gift.truemoney.com/campaign/?v=...)"
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.get(normalized_link)
        status_code = int(response.status_code)
        if 200 <= status_code < 400:
            return "approved", "ลิงก์ของขวัญใช้งานได้"
        if status_code in {404, 410}:
            return "rejected", "ลิงก์ของขวัญหมดอายุหรือไม่พบแล้ว"
        return "pending", f"ตรวจสอบลิงก์ได้รหัส {status_code} โปรดลองอีกครั้ง"
    except Exception:
        return "pending", "ไม่สามารถตรวจสอบลิงก์ได้ชั่วคราว กรุณาลองใหม่อีกครั้ง"


def _normalize_image_ocr_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload or {}

    keywords_raw = src.get("keywords")
    keywords: list[str] = []
    if isinstance(keywords_raw, list):
        keywords = [str(item).strip() for item in keywords_raw if str(item).strip()]
    if not keywords:
        keywords = ["Following", "Shared", "Subscribed"]

    try:
        required_count = int(
            src.get("required_image_count")
            if src.get("required_image_count") is not None
            else src.get("image_count", 1)
        )
    except (TypeError, ValueError):
        required_count = 1
    required_count = max(1, min(10, required_count))

    normalized: dict[str, Any] = {
        "enabled": bool(src.get("enabled")),
        "target_channel_id": (str(src.get("target_channel_id") or "").strip() or None),
        "admin_channel_id": (str(src.get("admin_channel_id") or "").strip() or None),
        "notification_channel_id": (str(src.get("notification_channel_id") or "").strip() or None),
        "webhook_url": (str(src.get("webhook_url") or "").strip() or None),
        "notify_embed_title": str(src.get("notify_embed_title") or "อัปเดตหลักฐานการติดตาม").strip()[:120],
        "notify_embed_description": str(
            src.get("notify_embed_description")
            or "คีย์เวิร์ด: {keywords}\nผู้ใช้: {user_mention}\nความคืบหน้า: {current_count}/{required_count}"
        ).strip()[:4000],
        "notify_embed_image_url": (str(src.get("notify_embed_image_url") or "").strip() or None),
        "required_image_count": required_count,
        "image_count": required_count,
        "reward_role_id": (str(src.get("reward_role_id") or "").strip() or None),
        "keywords": keywords,
    }
    if src.get("id") is not None:
        normalized["id"] = src.get("id")
    if src.get("guild_id") is not None:
        normalized["guild_id"] = src.get("guild_id")
    return normalized


async def _get_image_ocr_fallback(guild_id: int) -> dict[str, Any]:
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"image_ocr_settings_fallback": 1, "_id": 0})
        payload = (doc or {}).get("image_ocr_settings_fallback")
        if isinstance(payload, dict):
            normalized = _normalize_image_ocr_settings(payload)
            normalized["__fallback_source__"] = True
            return normalized
    except Exception:
        pass
    return _normalize_image_ocr_settings({})


async def _save_image_ocr_fallback(guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_image_ocr_settings({**(payload or {}), "guild_id": guild_id})
    try:
        guilds_col = await get_collection("guilds")
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"image_ocr_settings_fallback": normalized}},
            upsert=True,
        )
    except Exception:
        pass
    return normalized


async def _get_donate_fallback(guild_id: int) -> dict[str, Any] | None:
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"donate_settings_fallback": 1, "_id": 0})
        payload = (doc or {}).get("donate_settings_fallback")
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


async def _save_donate_fallback(guild_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    normalized = {
        "guild_id": guild_id,
        "enabled": bool(payload.get("enabled")),
        "donation_channel_id": payload.get("donation_channel_id"),
        "notification_channel_id": payload.get("notification_channel_id"),
        "reward_role_id": payload.get("reward_role_id"),
        "color": str(payload.get("color") or "#6b8cff"),
        "desc_discord": str(payload.get("desc_discord") or ""),
        "desc_web": str(payload.get("desc_web") or ""),
        "truemoney_phone": str(payload.get("truemoney_phone") or ""),
        "promptpay_number": str(payload.get("promptpay_number") or ""),
        "bank_name": str(payload.get("bank_name") or ""),
        "bank_account_number": str(payload.get("bank_account_number") or ""),
        "bank_account_name": str(payload.get("bank_account_name") or ""),
        "slipcheck_verify_engine": str(payload.get("slipcheck_verify_engine") or "slipok"),
        "slipok_api_url": str(payload.get("slipok_api_url") or "https://api.slipok.com/api/line/apikey/1150"),
        "slipok_key": str(payload.get("slipok_key") or ""),
        "slipcheck_expected_receiver_name": str(payload.get("slipcheck_expected_receiver_name") or ""),
        "slipcheck_expected_receiver_first_name_th": str(payload.get("slipcheck_expected_receiver_first_name_th") or ""),
        "slipcheck_expected_receiver_last_name_th": str(payload.get("slipcheck_expected_receiver_last_name_th") or ""),
        "slipcheck_expected_receiver_first_name_en": str(payload.get("slipcheck_expected_receiver_first_name_en") or ""),
        "slipcheck_expected_receiver_last_name_en": str(payload.get("slipcheck_expected_receiver_last_name_en") or ""),
        "slipcheck_expected_receiver_bank": str(payload.get("slipcheck_expected_receiver_bank") or ""),
        "slipcheck_expected_receiver_account": str(payload.get("slipcheck_expected_receiver_account") or ""),
        "slipcheck_expected_sender_name": str(payload.get("slipcheck_expected_sender_name") or ""),
        "slipcheck_expected_sender_first_name_th": str(payload.get("slipcheck_expected_sender_first_name_th") or ""),
        "slipcheck_expected_sender_last_name_th": str(payload.get("slipcheck_expected_sender_last_name_th") or ""),
        "slipcheck_expected_sender_first_name_en": str(payload.get("slipcheck_expected_sender_first_name_en") or ""),
        "slipcheck_expected_sender_last_name_en": str(payload.get("slipcheck_expected_sender_last_name_en") or ""),
        "slipcheck_expected_sender_bank": str(payload.get("slipcheck_expected_sender_bank") or ""),
        "slipcheck_expected_sender_account": str(payload.get("slipcheck_expected_sender_account") or ""),
        "slipcheck_expected_reference": str(payload.get("slipcheck_expected_reference") or ""),
        "slipcheck_expected_qr_reference": str(payload.get("slipcheck_expected_qr_reference") or ""),
        "slipcheck_max_age_minutes": int(payload.get("slipcheck_max_age_minutes") or 1440),
        "slipcheck_auto_approve_confidence": max(
            50.0,
            min(100.0, float(payload.get("slipcheck_auto_approve_confidence") or 85.0)),
        ),
        "slipcheck_manual_review_confidence": 0.0,
        "slipcheck_duplicate_window_hours": int(payload.get("slipcheck_duplicate_window_hours") or 72),
        "slipcheck_review_channel_id": str(payload.get("slipcheck_review_channel_id") or ""),
        "slipcheck_review_dm_user_ids": str(payload.get("slipcheck_review_dm_user_ids") or ""),
        "slipcheck_low_confidence_route": str(payload.get("slipcheck_low_confidence_route") or "both"),
        "goal_title": str(payload.get("goal_title") or "Donation Goal"),
        "goal_start_amount": int(payload.get("goal_start_amount") or 0),
        "goal_end_amount": int(payload.get("goal_end_amount") or 500),
        "goal_start_date": str(payload.get("goal_start_date") or ""),
        "image_url": str(payload.get("image_url") or ""),
        "methods_enabled": dict(payload.get("methods_enabled") or {}),
    }
    try:
        guilds_col = await get_collection("guilds")
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"donate_settings_fallback": normalized}},
            upsert=True,
        )
        return normalized
    except Exception:
        return None


def _donate_payment_method_label(method: Any) -> str:
    return _dashboard_donate_utils.donate_payment_method_label(method)


def _render_donate_slip_row_html(guild_id: int, row: dict[str, Any], *, with_actions: bool = True) -> str:
    return _dashboard_donate_utils.render_donate_slip_row_html(
        guild_id,
        row,
        with_actions=with_actions,
        normalize_donate_slip_status_fn=_normalize_donate_slip_status,
        donate_slip_status_label_fn=_donate_slip_status_label,
        format_datetime_display_fn=_format_datetime_display,
        safe_parse_datetime_fn=_safe_parse_datetime,
        escape_fn=_escape,
        donate_payment_method_label_fn=_donate_payment_method_label,
    )


def _extract_slipok_endpoint(api_url: str) -> str:
    value = str(api_url or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.isdigit():
        return f"https://api.slipok.com/api/line/apikey/{value}"
    return ""


async def _auto_verify_donate_evidence(
    *,
    settings: dict[str, Any],
    payment_method: str,
    amount: int,
    image_url: str = "",
    raw_bytes: bytes | None = None,
    filename: str = "slip.png",
    transfer_link: str = "",
) -> tuple[str, str]:
    method = str(payment_method or "").strip().lower()
    link = str(transfer_link or "").strip()
    engine_raw = str(settings.get("slipcheck_verify_engine") or "slipok").strip().lower()
    verify_engine = (
        "skylinebotslip"
        if engine_raw in {"skylinebot", "skyline", "skyline_slip", "skylinebotslip", "internal", "ocr"}
        else "slipok"
    )

    # TrueMoney gift link quick check.
    if method == "truemoney" and link:
        is_valid = bool(TRUEMONEY_GIFT_LINK_RE.match(link))
        if not is_valid:
            return "rejected", "TrueMoney gift link format is invalid."
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(link)
            if 200 <= int(response.status_code) < 400:
                return "approved", "TrueMoney gift link verified."
        except Exception:
            pass
        return "pending", "Gift link received and waiting for additional checks."

    methods_enabled = settings.get("methods_enabled") or {}
    if not methods_enabled.get("slipverify"):
        return "pending", "Slip verification is disabled."

    try:
        auto_approve_confidence = round(
            max(
                50.0,
                min(
                    100.0,
                    float(settings.get("slipcheck_auto_approve_confidence") or 85.0),
                ),
            ),
            2,
        )
    except Exception:
        auto_approve_confidence = 85.0

    verify_settings = {
        "slipcheck_verify_engine": verify_engine,
        "slipok_api_url": settings.get("slipok_api_url") or "",
        "slipok_key": settings.get("slipok_key") or "",
        "slipcheck_expected_receiver_name": settings.get("slipcheck_expected_receiver_name") or "",
        "slipcheck_expected_receiver_first_name_th": settings.get("slipcheck_expected_receiver_first_name_th") or "",
        "slipcheck_expected_receiver_last_name_th": settings.get("slipcheck_expected_receiver_last_name_th") or "",
        "slipcheck_expected_receiver_first_name_en": settings.get("slipcheck_expected_receiver_first_name_en") or "",
        "slipcheck_expected_receiver_last_name_en": settings.get("slipcheck_expected_receiver_last_name_en") or "",
        "slipcheck_expected_receiver_bank": settings.get("slipcheck_expected_receiver_bank") or "",
        "slipcheck_expected_receiver_account": settings.get("slipcheck_expected_receiver_account") or "",
        "slipcheck_expected_sender_name": settings.get("slipcheck_expected_sender_name") or "",
        "slipcheck_expected_sender_first_name_th": settings.get("slipcheck_expected_sender_first_name_th") or "",
        "slipcheck_expected_sender_last_name_th": settings.get("slipcheck_expected_sender_last_name_th") or "",
        "slipcheck_expected_sender_first_name_en": settings.get("slipcheck_expected_sender_first_name_en") or "",
        "slipcheck_expected_sender_last_name_en": settings.get("slipcheck_expected_sender_last_name_en") or "",
        "slipcheck_expected_sender_bank": settings.get("slipcheck_expected_sender_bank") or "",
        "slipcheck_expected_sender_account": settings.get("slipcheck_expected_sender_account") or "",
        "slipcheck_expected_reference": settings.get("slipcheck_expected_reference") or "",
        "slipcheck_expected_qr_reference": settings.get("slipcheck_expected_qr_reference") or "",
        "slipcheck_max_age_minutes": settings.get("slipcheck_max_age_minutes"),
        "slipcheck_auto_approve_confidence": auto_approve_confidence,
        "slipcheck_manual_review_confidence": 0.0,
        "slipcheck_duplicate_window_hours": settings.get("slipcheck_duplicate_window_hours"),
        "slipcheck_review_channel_id": settings.get("slipcheck_review_channel_id"),
        "slipcheck_review_dm_user_ids": settings.get("slipcheck_review_dm_user_ids"),
        "slipcheck_low_confidence_route": settings.get("slipcheck_low_confidence_route"),
    }

    try:
        if raw_bytes:
            endpoint = _extract_slipok_endpoint(verify_settings.get("slipok_api_url") or "")
            api_key = str(verify_settings.get("slipok_key") or "").strip()
            if not endpoint or not api_key:
                if verify_engine == "slipok":
                    return "pending", "SlipOK API URL/Key is not configured."
                return "pending", "SkylineBotSlip requires OCR input or SlipOK OCR API for image files."

            headers = {"x-authorization": api_key}
            payload: dict[str, Any] = {"log": "true"}
            if amount > 0:
                payload["amount"] = str(amount)
            files = {
                "files": (
                    _safe_upload_name(filename),
                    raw_bytes,
                    "image/png",
                )
            }
            async with httpx.AsyncClient(timeout=22.0) as client:
                response = await client.post(endpoint, headers=headers, data=payload, files=files)
            provider_payload = response.json() if response.content else {}
            if not isinstance(provider_payload, dict):
                provider_payload = {}
            if verify_engine == "slipok":
                provider_ok = bool(provider_payload.get("success")) and bool((provider_payload.get("data") or {}).get("success"))
                if not provider_ok:
                    provider_message = str((provider_payload.get("data") or {}).get("message") or provider_payload.get("message") or "").strip()
                    return "rejected", (provider_message or "SlipOK rejected this transfer slip.")[:500]
            local_settings = dict(verify_settings)
            local_settings["slipcheck_verify_engine"] = "skylinebotslip"
            local_settings["slipok_api_url"] = ""
            local_settings["slipok_key"] = ""
            detailed = await _billing_workflow._verify_slip_evidence_detailed(
                settings=local_settings,
                amount=float(amount or 0),
                slip_qr_payload=json.dumps(provider_payload, ensure_ascii=False),
                transfer_reference=link,
                session_row=None,
            )
        else:
            if not image_url and not link:
                return "pending", "No slip URL or transferable OCR payload was provided."
            detailed = await _billing_workflow._verify_slip_evidence_detailed(
                settings=verify_settings,
                amount=float(amount or 0),
                slip_url=image_url,
                slip_qr_payload="",
                transfer_reference=link,
                session_row=None,
            )
        status = str(detailed.get("status") or "pending")
        note = str(detailed.get("note") or "Slip verification pending.")
        confidence = float(detailed.get("confidence") or 0.0)
        matched_checks = int(detailed.get("matched_checks") or 0)
        total_checks = int(detailed.get("total_checks") or 0)

        checks = detailed.get("checks") if isinstance(detailed.get("checks"), list) else []
        check_labels: list[str] = []
        for check_row in checks[:8]:
            if not isinstance(check_row, dict):
                continue
            label = str(check_row.get("label") or check_row.get("key") or "-").strip()
            match_state = check_row.get("matched")
            if match_state is True:
                icon = "OK"
            elif match_state is False:
                icon = "NO"
            else:
                icon = "SKIP"
            check_labels.append(f"{icon} {label}")

        fields = detailed.get("fields") if isinstance(detailed.get("fields"), dict) else {}
        detected_values: list[str] = []
        for field_key, field_label in (
            ("sender_name", "Sender"),
            ("sender_bank", "SenderBank"),
            ("sender_account", "SenderAcct"),
            ("receiver_name", "Receiver"),
            ("receiver_bank", "ReceiverBank"),
            ("receiver_account", "ReceiverAcct"),
            ("reference", "Ref"),
            ("qr_reference", "QRRef"),
            ("datetime_iso", "DateTime"),
        ):
            field_value = str(fields.get(field_key) or "").strip()
            if not field_value:
                continue
            detected_values.append(f"{field_label}:{field_value[:40]}")

        duplicate_info = detailed.get("duplicate") if isinstance(detailed.get("duplicate"), dict) else {}
        duplicate_text = ""
        if bool(duplicate_info.get("is_duplicate")):
            duplicate_text = f"Duplicate:{str(duplicate_info.get('matched_session_key') or '-').strip()}"

        summary = f"{note} (match {matched_checks}/{total_checks}, {confidence:.2f}%)"
        found_summary = ", ".join(detected_values[:6]) if detected_values else "Detected: none"
        checks_summary = "; ".join(check_labels[:6]) if check_labels else "Checks: none"
        detail_parts = [summary, found_summary, checks_summary]
        if duplicate_text:
            detail_parts.append(duplicate_text)
        return status, " | ".join(part for part in detail_parts if part)[:900]
    except Exception:
        return "pending", "Automatic slip verification failed. Please review manually."


def _normalize_alerts_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = _default_alerts_settings()
    src = payload or {}
    merged["enabled"] = bool(src.get("enabled"))
    notify_channel_id = str(src.get("notify_channel_id") or "").strip()
    merged["notify_channel_id"] = notify_channel_id if notify_channel_id.isdigit() else None
    try:
        cooldown_raw = int(src.get("cooldown_seconds") or 60)
    except (TypeError, ValueError):
        cooldown_raw = 60
    merged["cooldown_seconds"] = max(10, min(3600, cooldown_raw))

    mention_role_ids: list[str] = []
    for role_id in src.get("mention_role_ids") or []:
        role_text = str(role_id or "").strip()
        if role_text.isdigit() and role_text not in mention_role_ids:
            mention_role_ids.append(role_text)
    merged["mention_role_ids"] = mention_role_ids

    platforms = src.get("platforms") if isinstance(src.get("platforms"), dict) else {}
    for platform_name in ("twitch", "tiktok", "github", "youtube", "facebook"):
        current = platforms.get(platform_name) if isinstance(platforms, dict) else None
        current = current if isinstance(current, dict) else {}
        merged["platforms"][platform_name]["enabled"] = bool(current.get("enabled"))
        raw_entries = current.get("entries")
        if raw_entries is None:
            raw_entries = current.get("sources", [])
        merged["platforms"][platform_name]["entries"] = _normalize_alert_entries(
            raw_entries, default_channel=merged["notify_channel_id"]
        )
        merged["platforms"][platform_name]["message_template"] = str(
            current.get("message_template") or "{platform}: {title} {url}"
        )[:300]
    return merged


async def _get_alerts_fallback(guild_id: int) -> dict[str, Any]:
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"alerts_settings_fallback": 1, "_id": 0})
        payload = (doc or {}).get("alerts_settings_fallback")
        if isinstance(payload, dict):
            return _normalize_alerts_settings(payload)
    except Exception:
        pass
    return _default_alerts_settings()


async def _save_alerts_fallback(guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_alerts_settings(payload)
    try:
        guilds_col = await get_collection("guilds")
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"alerts_settings_fallback": normalized}},
            upsert=True,
        )
    except Exception:
        pass
    return normalized


async def _run_alerts_platform_test(guild_id: int, platform: str, settings: dict[str, Any]) -> tuple[bool, str]:
    platform_key = str(platform or "").strip().lower()
    if platform_key not in {"twitch", "tiktok", "github", "youtube", "facebook"}:
        return False, "ไม่รองรับแพลตฟอร์มที่ระบุ"

    bot = get_bot()
    if not bot:
        return False, "ไม่พบบอทในระบบ"
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return False, "ไม่พบกิลด์ในบอท"

    alerts_cog = bot.get_cog("Alerts")
    if not alerts_cog:
        return False, "ไม่พบโมดูล Alerts ในบอ"

    fetch_items = getattr(alerts_cog, "_fetch_alert_items", None)
    send_alert = getattr(alerts_cog, "_send_alert_message", None)
    if not callable(fetch_items) or not callable(send_alert):
        return False, "โมดูล Alerts ไม่รองรับการทดสอบนี้"

    normalized = _normalize_alerts_settings(settings)
    platform_conf = (normalized.get("platforms") or {}).get(platform_key) or {}
    platform_label = str(
        (getattr(alerts_cog, "PLATFORM_LABELS", {}) or {}).get(platform_key)
        or platform_key.upper()
    )
    entries = list(platform_conf.get("entries") or [])
    if not entries:
        default_channel = str(normalized.get("notify_channel_id") or "").strip()
        if default_channel.isdigit():
            entries = [
                {
                    "source_url": "",
                    "description": f"ทดสอบการแจ้งเตือน {platform_label}",
                    "button_text": "ดูรายละเอียด",
                    "channel_id": default_channel,
                }
            ]
        else:
            return False, f"{platform_label} ยังไม่มีแหล่งข้อมูลที่ตั้งค่าไว้"

    mention_roles = [
        f"<@&{role_id}>"
        for role_id in (normalized.get("mention_role_ids") or [])
        if str(role_id).isdigit()
    ]
    mention_text = " ".join(mention_roles).strip()
    template = str(platform_conf.get("message_template") or "{platform}: {title} {url}")
    test_template = f"ทดสอบการแจ้งเตือน | {template}"
    default_channel = str(normalized.get("notify_channel_id") or "").strip()

    sent_count = 0
    checked_count = 0
    fallback_count = 0
    for entry in entries[:10]:
        source_url = str(entry.get("source_url") or "").strip()
        channel_id = str(entry.get("channel_id") or default_channel or "").strip()
        if not channel_id.isdigit():
            continue
        channel_obj = guild.get_channel(int(channel_id))
        if not channel_obj or not isinstance(channel_obj, (discord.TextChannel, discord.Thread)):
            continue

        checked_count += 1
        latest: dict[str, Any] = {}
        try:
            items = await fetch_items(platform_key, source_url) if source_url else []
        except Exception:
            items = []
        if items:
            preferred = next(
                (row for row in items if str(row.get("item_type") or "").strip().lower() == "live"),
                items[0],
            )
            latest = dict(preferred)
            latest_title = str(latest.get("title") or "").strip()
            latest["title"] = f"สด {platform_label}: {latest_title or 'ไม่มีชื่อเรื่อง'}"
        else:
            fallback_count += 1
            latest = {
                "id": f"manual-test:{platform_key}:{int(time.time())}",
                "item_type": "event",
                "title": f"ทดสอบการแจ้งเตือน {platform_label}",
                "url": source_url or "https://discord.com",
                "summary": "ข้อความนี้คือการทดสอบจากหน้าแดชบอร์ด",
            }
        try:
            await send_alert(
                channel=channel_obj,
                platform=platform_key,
                latest=latest,
                template=test_template,
                entry=entry,
                mention_text=mention_text,
            )
            sent_count += 1
        except Exception:
            continue
        if sent_count >= 3:
            break

    if sent_count > 0:
        if fallback_count > 0:
            return True, f"ส่งข้อความทดสอบ {platform_label} สำเร็จ {sent_count} รายการ (ใช้ข้อมูลจำลอง)"
        return True, f"ส่งข้อความทดสอบ {platform_label} สำเร็จ {sent_count} รายการ"
    if checked_count == 0:
        return False, f"{platform_label} ยังไม่มีห้องแจ้งเตือนที่ใช้งานได้"
    return False, f"ไม่สามารถส่งข้อความทดสอบ {platform_label} ได้ (ตรวจสอบสิทธิ์บอทและการตั้งค่าห้องอีกครั้ง)"


def _normalize_verify_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload or {}
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    enabled = _as_bool(src.get("enabled"))
    web_verify_enabled = _as_bool(src.get("web_verify_enabled"))
    if "web_verify_enabled" not in src:
        web_verify_enabled = enabled
    auto_role_enabled = _as_bool(src.get("auto_role_enabled"))
    web_verify_auto_role_enabled = _as_bool(src.get("web_verify_auto_role_enabled"))
    if "web_verify_auto_role_enabled" not in src:
        web_verify_auto_role_enabled = auto_role_enabled
    reward_role_ids = _normalize_verify_role_ids(src.get("reward_role_ids"))
    if not reward_role_ids:
        reward_role_ids = _normalize_verify_role_ids(src.get("reward_role_id"))
    remove_role_ids = _normalize_verify_role_ids(src.get("remove_role_ids"))
    web_verify_reward_role_ids = _normalize_verify_role_ids(src.get("web_verify_reward_role_ids"))
    if "web_verify_reward_role_ids" not in src:
        web_verify_reward_role_ids = list(reward_role_ids)
    web_verify_remove_role_ids = _normalize_verify_role_ids(src.get("web_verify_remove_role_ids"))
    if "web_verify_remove_role_ids" not in src:
        web_verify_remove_role_ids = list(remove_role_ids)
    reward_role_id = reward_role_ids[0] if reward_role_ids else ""

    verify_channel_id = str(src.get("verify_channel_id") or "").strip()
    if verify_channel_id and not verify_channel_id.isdigit():
        verify_channel_id = ""

    web_verify_channel_id = str(src.get("web_verify_channel_id") or "").strip()
    if not web_verify_channel_id:
        web_verify_channel_id = verify_channel_id
    if web_verify_channel_id and not web_verify_channel_id.isdigit():
        web_verify_channel_id = ""

    notify_channel_id = str(src.get("notify_channel_id") or "").strip()
    if notify_channel_id and not notify_channel_id.isdigit():
        notify_channel_id = ""
    web_verify_notify_channel_id = str(src.get("web_verify_notify_channel_id") or "").strip()
    if not web_verify_notify_channel_id:
        web_verify_notify_channel_id = notify_channel_id
    if web_verify_notify_channel_id and not web_verify_notify_channel_id.isdigit():
        web_verify_notify_channel_id = ""

    color = str(src.get("color") or "#39ff14").strip()
    if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
        color = "#39ff14"

    web_verify_color = str(src.get("web_verify_color") or "").strip()
    if not web_verify_color:
        web_verify_color = color
    if not re.match(r"^#[0-9A-Fa-f]{6}$", web_verify_color):
        web_verify_color = "#5865f2"

    button_color = str(src.get("button_color") or "green").strip().lower()
    if button_color not in {"green", "blurple", "red", "gray"}:
        button_color = "green"

    web_verify_button_color = str(src.get("web_verify_button_color") or "").strip().lower()
    if not web_verify_button_color:
        web_verify_button_color = button_color
    if web_verify_button_color not in {"green", "blurple", "red", "gray"}:
        web_verify_button_color = "green"

    button_label = str(src.get("button_label") or "ยืนยันตัวตน").strip()[:45] or "ยืนยันตัวตน"
    button_emoji = str(src.get("button_emoji") or "").strip()[:64]
    description = str(src.get("description") or "").strip()[:400]
    embed_title = str(src.get("embed_title") or "ยืนยันตัวตน").strip()[:120]
    embed_footer = str(src.get("embed_footer") or "").strip()[:200]
    embed_thumbnail_url = str(src.get("embed_thumbnail_url") or "").strip()[:500]
    embed_image_url = str(src.get("embed_image_url") or "").strip()[:500]

    web_verify_embed_title = str(src.get("web_verify_embed_title") or "").strip()[:120]
    if not web_verify_embed_title:
        web_verify_embed_title = "ยืนยันตัวตนผ่านเว็บ"
    web_verify_embed_description = str(src.get("web_verify_embed_description") or "").strip()[:400]
    if not web_verify_embed_description:
        web_verify_embed_description = "กดปุ่มด้านล่างเพื่อเปิดหน้า Web Verify"
    web_verify_embed_footer = str(src.get("web_verify_embed_footer") or "").strip()[:200]
    web_verify_embed_thumbnail_url = str(src.get("web_verify_embed_thumbnail_url") or "").strip()[:500]
    web_verify_embed_image_url = str(src.get("web_verify_embed_image_url") or "").strip()[:500]
    if not web_verify_embed_image_url:
        web_verify_embed_image_url = str(src.get("slip_image_url") or "").strip()[:500]
    slip_image_url = web_verify_embed_image_url

    web_verify_intro = str(src.get("web_verify_intro") or "กดปุ่มด้านล่างเพื่อยืนยันตัวตนผ่านเว็บ").strip()[:280]
    web_verify_success = str(src.get("web_verify_success") or "ยืนยันตัวตนสำเร็จแล้ว คุณสามารถกลับไปที่เซิร์ฟเวอร์ได้เลย").strip()[:280]
    web_verify_error = str(src.get("web_verify_error") or "ไม่สามารถยืนยันตัวตนได้ กรุณาลองใหม่อีกครั้ง").strip()[:280]
    web_verify_button_label = str(src.get("web_verify_button_label") or "ยืนยันตัวตนตอนนี้").strip()[:45] or "ยืนยันตัวตนตอนนี้"
    web_verify_button_emoji = str(src.get("web_verify_button_emoji") or "").strip()[:64]
    if not web_verify_button_emoji:
        web_verify_button_emoji = button_emoji
    web_back_button_label = str(src.get("web_back_button_label") or "กลับสู่ Server").strip()[:45] or "กลับสู่ Server"
    back_to_server_url = str(src.get("back_to_server_url") or "").strip()[:500]
    pages = _normalize_verify_pages(src.get("pages"))
    nickname_from_first_input = _as_bool(src.get("nickname_from_first_input"))
    verify_panel_message_id = str(src.get("verify_panel_message_id") or "").strip()
    if verify_panel_message_id and not verify_panel_message_id.isdigit():
        verify_panel_message_id = ""
    verify_panel_channel_id = str(src.get("verify_panel_channel_id") or "").strip()
    if verify_panel_channel_id and not verify_panel_channel_id.isdigit():
        verify_panel_channel_id = ""

    web_verify_panel_message_id = str(src.get("web_verify_panel_message_id") or "").strip()
    if web_verify_panel_message_id and not web_verify_panel_message_id.isdigit():
        web_verify_panel_message_id = ""
    web_verify_panel_channel_id = str(src.get("web_verify_panel_channel_id") or "").strip()
    if web_verify_panel_channel_id and not web_verify_panel_channel_id.isdigit():
        web_verify_panel_channel_id = ""

    return {
        "enabled": enabled,
        "web_verify_enabled": web_verify_enabled,
        "reward_role_id": reward_role_id or None,
        "reward_role_ids": reward_role_ids,
        "remove_role_ids": remove_role_ids,
        "web_verify_reward_role_ids": web_verify_reward_role_ids,
        "web_verify_remove_role_ids": web_verify_remove_role_ids,
        "color": color,
        "web_verify_color": web_verify_color,
        "description": description,
        "pages": pages,
        "verify_channel_id": verify_channel_id or None,
        "web_verify_channel_id": web_verify_channel_id or None,
        "notify_channel_id": notify_channel_id or None,
        "web_verify_notify_channel_id": web_verify_notify_channel_id or None,
        "auto_role_enabled": auto_role_enabled,
        "web_verify_auto_role_enabled": web_verify_auto_role_enabled,
        "nickname_from_first_input": nickname_from_first_input,
        "button_color": button_color,
        "button_label": button_label,
        "button_emoji": button_emoji,
        "slip_image_url": slip_image_url,
        "embed_title": embed_title,
        "embed_footer": embed_footer,
        "embed_thumbnail_url": embed_thumbnail_url,
        "embed_image_url": embed_image_url,
        "web_verify_embed_title": web_verify_embed_title,
        "web_verify_embed_description": web_verify_embed_description,
        "web_verify_embed_footer": web_verify_embed_footer,
        "web_verify_embed_thumbnail_url": web_verify_embed_thumbnail_url,
        "web_verify_embed_image_url": web_verify_embed_image_url,
        "web_verify_intro": web_verify_intro,
        "web_verify_success": web_verify_success,
        "web_verify_error": web_verify_error,
        "web_verify_button_label": web_verify_button_label,
        "web_verify_button_color": web_verify_button_color,
        "web_verify_button_emoji": web_verify_button_emoji,
        "web_back_button_label": web_back_button_label,
        "back_to_server_url": back_to_server_url,
        "verify_panel_message_id": verify_panel_message_id or None,
        "verify_panel_channel_id": verify_panel_channel_id or None,
        "web_verify_panel_message_id": web_verify_panel_message_id or None,
        "web_verify_panel_channel_id": web_verify_panel_channel_id or None,
    }


def _verify_color_to_int(value: Any) -> int:
    raw = str(value or "#39ff14").strip().lstrip("#")
    if not re.match(r"^[0-9A-Fa-f]{6}$", raw):
        raw = "39ff14"
    try:
        return int(raw, 16)
    except Exception:
        return 0x39FF14


def _message_has_button_custom_id(message: discord.Message, custom_id: str) -> bool:
    target = str(custom_id or "").strip()
    if not target:
        return False
    for row in list(getattr(message, "components", []) or []):
        children = getattr(row, "children", None)
        if children is None and isinstance(row, dict):
            children = row.get("components") or []
        for child in list(children or []):
            child_custom_id = str(getattr(child, "custom_id", "") or "")
            if not child_custom_id and isinstance(child, dict):
                child_custom_id = str(child.get("custom_id") or "")
            if child_custom_id == target:
                return True
    return False


async def _find_verify_panel_messages(
    channel: discord.TextChannel | discord.Thread,
    *,
    bot_user_id: int,
    custom_id: str,
    limit: int = 120,
) -> list[discord.Message]:
    found: list[discord.Message] = []
    try:
        async for message in channel.history(limit=limit):
            if int(getattr(message.author, "id", 0) or 0) != int(bot_user_id):
                continue
            if _message_has_button_custom_id(message, custom_id):
                found.append(message)
    except Exception:
        pass
    return found


def _build_verify_panel_view_with_callback(
    *,
    mode: str,
    label: str,
    color: Any,
    emoji: str = "",
) -> discord.ui.View:
    mode_key = str(mode or "verify").strip().lower()
    if mode_key not in {"verify", "web_verify"}:
        mode_key = "verify"

    safe_label = str(label or "").strip()[:45]
    if not safe_label:
        safe_label = "Verify Now" if mode_key == "web_verify" else "Verify"
    safe_emoji = str(emoji or "").strip()[:64]
    button_style = _verify_button_style(color)

    try:
        from skylinebot.src.modules.verify import VerifyStartView

        return VerifyStartView.build_single_button_view(
            mode=mode_key,
            label=safe_label,
            style=button_style,
            emoji=safe_emoji or None,
        )
    except Exception:
        view = discord.ui.View(timeout=None)
        button_kwargs: dict[str, Any] = {
            "label": safe_label,
            "style": button_style,
            "custom_id": "verify_start_web" if mode_key == "web_verify" else "verify_start",
        }
        if safe_emoji:
            button_kwargs["emoji"] = safe_emoji
        try:
            button = discord.ui.Button(**button_kwargs)
        except Exception:
            button_kwargs.pop("emoji", None)
            button = discord.ui.Button(**button_kwargs)

        async def _fallback_callback(interaction: discord.Interaction) -> None:
            target_mode = mode_key
            try:
                from skylinebot.src.modules.verify import VerifyStartView

                await VerifyStartView()._handle_start(interaction, mode=target_mode)
            except Exception:
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send("Verify system is not ready right now.", ephemeral=True)
                    else:
                        await interaction.response.send_message("Verify system is not ready right now.", ephemeral=True)
                except Exception:
                    pass

        button.callback = _fallback_callback
        view.add_item(button)
        return view


async def _publish_verify_panel_from_dashboard(
    guild_id: int, payload: dict[str, Any]
) -> tuple[bool, str, dict[str, Any]]:
    bot = get_bot()
    if not bot:
        return False, "ไม่พบบอทในระบบ", payload
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return False, "ไม่พบเซิร์ฟเวอร์ของบอท", payload

    verify_channel_id = str(payload.get("verify_channel_id") or "").strip()
    if not verify_channel_id.isdigit():
        return False, "ยังไม่ได้ตั้งค่าห้องยืนยันตัวตน", payload
    channel = guild.get_channel(int(verify_channel_id))
    if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False, "ไม่พบห้องยืนยันตัวตน หรือบอทไม่มีสิทธิ์ส่งข้อความ", payload

    embed = discord.Embed(
        title=str(payload.get("embed_title") or "ยืนยันตัวตน")[:120],
        description=str(payload.get("description") or "กดปุ่มด้านล่างเพื่อยืนยันตัวตน")[:4000],
        color=_verify_color_to_int(payload.get("color")),
    )
    thumb = str(payload.get("embed_thumbnail_url") or "").strip()
    image = str(payload.get("embed_image_url") or "").strip()
    footer = str(payload.get("embed_footer") or "").strip()
    if thumb:
        embed.set_thumbnail(url=thumb)
    if image:
        embed.set_image(url=image)
    if footer:
        embed.set_footer(text=footer[:200])
    embed.add_field(name="เซิร์ฟ", value=guild.name, inline=True)

    view = _build_verify_panel_view_with_callback(
        mode="verify",
        label=str(payload.get("button_label") or "Verify")[:45] or "Verify",
        color=payload.get("button_color"),
        emoji=str(payload.get("button_emoji") or "").strip()[:64],
    )
    panel_message_id = str(payload.get("verify_panel_message_id") or "").strip()
    panel_channel_id = str(payload.get("verify_panel_channel_id") or "").strip()
    existing_message: discord.Message | None = None
    existing_messages: list[discord.Message] = []

    if panel_message_id.isdigit() and panel_channel_id.isdigit():
        panel_channel = guild.get_channel(int(panel_channel_id))
        if panel_channel and isinstance(panel_channel, (discord.TextChannel, discord.Thread)):
            try:
                existing_message = await panel_channel.fetch_message(int(panel_message_id))
            except Exception:
                existing_message = None
            if (
                existing_message
                and int(getattr(existing_message.author, "id", 0) or 0) == int(getattr(bot.user, "id", 0) or 0)
                and _message_has_button_custom_id(existing_message, "verify_start")
            ):
                existing_messages.append(existing_message)

    if bot.user:
        scanned = await _find_verify_panel_messages(
            channel,
            bot_user_id=int(bot.user.id),
            custom_id="verify_start",
        )
        for message in scanned:
            if all(message.id != item.id for item in existing_messages):
                existing_messages.append(message)

    if panel_channel_id.isdigit() and int(panel_channel_id) != int(verify_channel_id) and bot.user:
        previous_channel = guild.get_channel(int(panel_channel_id))
        if previous_channel and isinstance(previous_channel, (discord.TextChannel, discord.Thread)):
            old_scanned = await _find_verify_panel_messages(
                previous_channel,
                bot_user_id=int(bot.user.id),
                custom_id="verify_start",
            )
            for message in old_scanned:
                if all(message.id != item.id for item in existing_messages):
                    existing_messages.append(message)

    target_messages = [msg for msg in existing_messages if int(getattr(msg.channel, "id", 0) or 0) == int(verify_channel_id)]
    edited_existing = False
    primary_message: discord.Message | None = None
    if target_messages:
        candidate = target_messages[0]
        try:
            await candidate.edit(embed=embed, view=view)
            primary_message = candidate
            edited_existing = True
        except Exception:
            primary_message = None

    if primary_message is None:
        primary_message = await channel.send(embed=embed, view=view)

    for message in existing_messages:
        if edited_existing and message.id == primary_message.id:
            continue
        try:
            await message.delete()
        except Exception:
            pass

    payload["verify_panel_message_id"] = str(primary_message.id)
    payload["verify_panel_channel_id"] = str(primary_message.channel.id)
    if edited_existing:
        return True, f"อัปเดตแผงยืนยันตัวตนที่ #{channel.name}", payload
    return True, f"ส่งแผงยืนยันตัวตนไปที่ #{channel.name}", payload


async def _publish_web_verify_panel_from_dashboard(
    guild_id: int, payload: dict[str, Any]
) -> tuple[bool, str, dict[str, Any]]:
    normalized = _normalize_verify_settings(payload)
    bot = get_bot()
    if not bot:
        return False, "ไม่พบบอทในระบบ", normalized
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return False, "ไม่พบเซิร์ฟเวอร์ของบอท", normalized

    verify_channel_id = str(normalized.get("web_verify_channel_id") or "").strip()
    if not verify_channel_id.isdigit():
        return False, "ยังไม่ได้ตั้งค่าห้อง Web Verify", normalized
    channel = guild.get_channel(int(verify_channel_id))
    if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False, "ไม่พบห้อง Web Verify หรือบอทไม่มีสิทธิ์ส่งข้อความ", normalized

    embed = discord.Embed(
        title=str(normalized.get("web_verify_embed_title") or "ยืนยันตัวตนผ่านเว็บ")[:120],
        description=str(normalized.get("web_verify_embed_description") or "กดปุ่มด้านล่างเพื่อเปิดหน้า Web Verify")[:4000],
        color=_verify_color_to_int(normalized.get("web_verify_color")),
    )
    thumb = str(normalized.get("web_verify_embed_thumbnail_url") or "").strip()
    image = str(normalized.get("web_verify_embed_image_url") or "").strip()
    footer = str(normalized.get("web_verify_embed_footer") or "").strip()
    if thumb:
        embed.set_thumbnail(url=thumb)
    if image:
        embed.set_image(url=image)
    if footer:
        embed.set_footer(text=footer[:200])
    embed.add_field(name="เซิร์ฟ", value=guild.name, inline=True)

    view = _build_verify_panel_view_with_callback(
        mode="web_verify",
        label=str(normalized.get("web_verify_button_label") or "Verify Now")[:45] or "Verify Now",
        color=normalized.get("web_verify_button_color"),
        emoji=str(normalized.get("web_verify_button_emoji") or "").strip()[:64],
    )
    panel_message_id = str(normalized.get("web_verify_panel_message_id") or "").strip()
    panel_channel_id = str(normalized.get("web_verify_panel_channel_id") or "").strip()
    existing_message: discord.Message | None = None
    existing_messages: list[discord.Message] = []

    if panel_message_id.isdigit() and panel_channel_id.isdigit():
        panel_channel = guild.get_channel(int(panel_channel_id))
        if panel_channel and isinstance(panel_channel, (discord.TextChannel, discord.Thread)):
            try:
                existing_message = await panel_channel.fetch_message(int(panel_message_id))
            except Exception:
                existing_message = None
            if (
                existing_message
                and int(getattr(existing_message.author, "id", 0) or 0) == int(getattr(bot.user, "id", 0) or 0)
                and _message_has_button_custom_id(existing_message, "verify_start_web")
            ):
                existing_messages.append(existing_message)

    if bot.user:
        scanned = await _find_verify_panel_messages(
            channel,
            bot_user_id=int(bot.user.id),
            custom_id="verify_start_web",
        )
        for message in scanned:
            if all(message.id != item.id for item in existing_messages):
                existing_messages.append(message)

    if panel_channel_id.isdigit() and int(panel_channel_id) != int(verify_channel_id) and bot.user:
        previous_channel = guild.get_channel(int(panel_channel_id))
        if previous_channel and isinstance(previous_channel, (discord.TextChannel, discord.Thread)):
            old_scanned = await _find_verify_panel_messages(
                previous_channel,
                bot_user_id=int(bot.user.id),
                custom_id="verify_start_web",
            )
            for message in old_scanned:
                if all(message.id != item.id for item in existing_messages):
                    existing_messages.append(message)

    target_messages = [msg for msg in existing_messages if int(getattr(msg.channel, "id", 0) or 0) == int(verify_channel_id)]
    edited_existing = False
    primary_message: discord.Message | None = None
    if target_messages:
        candidate = target_messages[0]
        try:
            await candidate.edit(embed=embed, view=view)
            primary_message = candidate
            edited_existing = True
        except Exception:
            primary_message = None

    if primary_message is None:
        primary_message = await channel.send(embed=embed, view=view)

    for message in existing_messages:
        if edited_existing and message.id == primary_message.id:
            continue
        try:
            await message.delete()
        except Exception:
            pass

    normalized["web_verify_panel_message_id"] = str(primary_message.id)
    normalized["web_verify_panel_channel_id"] = str(primary_message.channel.id)
    if edited_existing:
        return True, f"อัปเดตแผง Web Verify ที่ #{channel.name}", normalized
    return True, f"ส่งแผง Web Verify ไปที่ #{channel.name}", normalized


async def _get_verify_fallback(guild_id: int) -> dict[str, Any]:
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"verify_settings_fallback": 1, "_id": 0})
        payload = (doc or {}).get("verify_settings_fallback")
        if isinstance(payload, dict):
            return _normalize_verify_settings(payload)
    except Exception:
        pass
    return _normalize_verify_settings({})


async def _save_verify_fallback(guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_verify_settings(payload)
    try:
        guilds_col = await get_collection("guilds")
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"verify_settings_fallback": normalized}},
            upsert=True,
        )
    except Exception:
        pass
    return normalized


async def _publish_voice_randomizer_panel_from_dashboard(
    guild_id: int,
    payload: dict[str, Any],
) -> tuple[bool, str, dict[str, Any]]:
    normalized = _normalize_voice_randomizer_settings(payload)
    bot = get_bot()
    if not bot:
        return False, "Bot is not available.", normalized
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return False, "Guild not found on active bot.", normalized

    panel_channel_id = str(normalized.get("panel_channel_id") or "").strip()
    if not panel_channel_id.isdigit():
        return False, "Panel channel is not configured.", normalized

    channel = guild.get_channel(int(panel_channel_id))
    if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False, "Panel channel was not found or bot cannot send there.", normalized

    allowed_ids = {
        str(item)
        for item in (normalized.get("allowed_category_ids") or [])
        if str(item).isdigit()
    }
    voice_count_map: dict[int, int] = {}
    for voice_channel in list(getattr(guild, "voice_channels", []) or []):
        category_id = int(getattr(voice_channel, "category_id", 0) or 0)
        if category_id <= 0:
            continue
        voice_count_map[category_id] = voice_count_map.get(category_id, 0) + 1

    categories: list[discord.CategoryChannel] = []
    for category in sorted(list(getattr(guild, "categories", []) or []), key=lambda c: int(getattr(c, "position", 0) or 0)):
        cid = str(int(getattr(category, "id", 0) or 0))
        if not cid or cid == "0":
            continue
        if allowed_ids and cid not in allowed_ids:
            continue
        if voice_count_map.get(int(cid), 0) <= 0:
            continue
        categories.append(category)

    if not categories:
        return False, "No voice categories found in selected scope.", normalized

    categories = categories[:25]
    available_category_ids = {str(category.id) for category in categories}
    selected_default_category = str(normalized.get("default_category_id") or "").strip()
    if selected_default_category not in available_category_ids:
        selected_default_category = str(categories[0].id)
    normalized["default_category_id"] = selected_default_category
    if allowed_ids:
        normalized["allowed_category_ids"] = [
            str(category.id) for category in categories if str(category.id) in allowed_ids
        ]
    else:
        normalized["allowed_category_ids"] = []

    embed = discord.Embed(
        title=str(normalized.get("embed_title") or "Voice Room Randomizer")[:120],
        description=str(normalized.get("embed_description") or "").strip()[:4000],
        color=_voice_randomizer_color_to_int(normalized.get("embed_color")),
    )
    thumbnail_url = str(normalized.get("embed_thumbnail_url") or "").strip()
    image_url = str(normalized.get("embed_image_url") or "").strip()
    footer_text = str(normalized.get("embed_footer") or "").strip()
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if image_url:
        embed.set_image(url=image_url)
    if footer_text:
        embed.set_footer(text=footer_text[:200])

    category_options = [
        discord.SelectOption(
            label=str(category.name)[:100] or f"Category {index}",
            value=str(category.id),
            description=f"{voice_count_map.get(int(category.id), 0)} voice channels"[:100],
            default=str(category.id) == selected_default_category,
        )
        for index, category in enumerate(categories, start=1)
    ]
    mode_value = str(normalized.get("room_mode") or "normal").strip().lower()
    if mode_value not in {"normal", "occupied", "empty"}:
        mode_value = "normal"
    normalized["room_mode"] = mode_value
    mode_options = [
        discord.SelectOption(label="Normal room (all)", value="normal", default=mode_value == "normal"),
        discord.SelectOption(label="Room with users", value="occupied", default=mode_value == "occupied"),
        discord.SelectOption(label="Empty room", value="empty", default=mode_value == "empty"),
    ]

    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Select(
            custom_id="voice_randomizer:category",
            placeholder=str(normalized.get("category_placeholder") or "Select category")[:100],
            min_values=1,
            max_values=1,
            options=category_options,
            row=0,
        )
    )
    view.add_item(
        discord.ui.Select(
            custom_id="voice_randomizer:mode",
            placeholder=str(normalized.get("mode_placeholder") or "Select room type")[:100],
            min_values=1,
            max_values=1,
            options=mode_options,
            row=1,
        )
    )

    button_kwargs: dict[str, Any] = {
        "custom_id": "voice_randomizer:run",
        "label": str(normalized.get("button_label") or "Random move me")[:45] or "Random move me",
        "style": _verify_button_style(normalized.get("button_color")),
        "row": 2,
    }
    button_emoji = str(normalized.get("button_emoji") or "").strip()[:64]
    if button_emoji:
        try:
            parsed_emoji = discord.PartialEmoji.from_str(button_emoji)
            if parsed_emoji and (parsed_emoji.id or parsed_emoji.name):
                button_kwargs["emoji"] = parsed_emoji
            else:
                button_kwargs["emoji"] = button_emoji
        except Exception:
            button_kwargs["emoji"] = button_emoji
    try:
        view.add_item(discord.ui.Button(**button_kwargs))
    except Exception:
        button_kwargs.pop("emoji", None)
        view.add_item(discord.ui.Button(**button_kwargs))

    stored_message_id = str(normalized.get("panel_message_id") or "").strip()
    stored_message_channel_id = str(normalized.get("panel_message_channel_id") or "").strip()
    existing_message: discord.Message | None = None
    if stored_message_id.isdigit() and stored_message_channel_id.isdigit():
        old_channel = guild.get_channel(int(stored_message_channel_id))
        if old_channel and isinstance(old_channel, (discord.TextChannel, discord.Thread)):
            try:
                existing_message = await old_channel.fetch_message(int(stored_message_id))
            except Exception:
                existing_message = None

    if existing_message and existing_message.author.id == bot.user.id:
        if int(existing_message.channel.id) == int(panel_channel_id):
            await existing_message.edit(embed=embed, view=view)
            normalized["panel_message_id"] = str(existing_message.id)
            normalized["panel_message_channel_id"] = str(existing_message.channel.id)
            return True, f"Updated voice randomizer panel in #{channel.name}.", normalized
        try:
            await existing_message.delete()
        except Exception:
            pass

    sent_message = await channel.send(embed=embed, view=view)
    normalized["panel_message_id"] = str(sent_message.id)
    normalized["panel_message_channel_id"] = str(sent_message.channel.id)
    return True, f"Published voice randomizer panel in #{channel.name}.", normalized


def _normalize_server_stats_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload or {}
    enabled = bool(src.get("enabled"))
    raw_configs = src.get("stats_configs") if isinstance(src.get("stats_configs"), list) else []
    allowed_types = {
        "total_members", "members", "bots", "voice", "boosts",
        "online", "idle", "dnd", "offline",
    }
    stats_configs: list[dict[str, str]] = []
    for item in raw_configs:
        if not isinstance(item, dict):
            continue
        stat_type = str(item.get("type") or "").strip()
        channel_id = str(item.get("channel_id") or "").strip()
        fmt = str(item.get("format") or "").strip()
        if stat_type not in allowed_types:
            continue
        if channel_id and not channel_id.isdigit():
            channel_id = ""
        stats_configs.append(
            {
                "type": stat_type,
                "channel_id": channel_id,
                "format": fmt or "{Count}",
            }
        )
    category_name = str(src.get("category_name") or " สถิติเซิร์ฟ").strip()[:80] or " สถิติเซิร์ฟ"
    return {
        "enabled": enabled,
        "stats_configs": stats_configs,
        "category_name": category_name,
    }


async def _get_server_stats_fallback(guild_id: int) -> dict[str, Any]:
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"server_stats_fallback": 1, "_id": 0})
        payload = (doc or {}).get("server_stats_fallback")
        if isinstance(payload, dict):
            normalized = _normalize_server_stats_settings(payload)
            normalized["__fallback_source__"] = True
            return normalized
    except Exception:
        pass
    return _normalize_server_stats_settings({})


async def _save_server_stats_fallback(guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_server_stats_settings(payload)
    try:
        guilds_col = await get_collection("guilds")
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"server_stats_fallback": normalized}},
            upsert=True,
        )
    except Exception:
        pass
    return normalized


async def _parse_form(request: Request) -> dict[str, str]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            data: dict[str, str] = {}
            for key, value in form.multi_items():
                # Ignore file parts and keep text fields only.
                if hasattr(value, "filename"):
                    continue
                data[str(key)] = str(value)
            if data:
                return data
        except Exception:
            pass

    body = await request.body()
    if not body:
        return {}
    try:
        payload = body.decode("utf-8")
    except UnicodeDecodeError:
        payload = body.decode("utf-8", errors="ignore")
    parsed = parse_qs(payload, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def _ownerbot_runtime_block_message(reason_code: str | None) -> str:
    return _dashboard_ownerbot_domain.ownerbot_runtime_block_message(reason_code)

def _ownerbot_dashboard_tab_block_reason(
    *,
    session: dict[str, Any] | None,
    tab_slug: str,
    runtime_settings: dict[str, Any] | None = None,
) -> str | None:
    return _dashboard_ownerbot_domain.ownerbot_dashboard_tab_block_reason(
        session=session,
        tab_slug=tab_slug,
        runtime_settings=runtime_settings,
        is_dashboard_admin_fn=_is_dashboard_admin,
        ownerbot_runtime_from_db_fn=_ownerbot_runtime_from_db,
        ownerbot_hidden_tabs_fn=_ownerbot_hidden_dashboard_tabs,
    )

def _dashboard_audit_config_key(guild_id: int) -> str:
    return f"{DASHBOARD_AUDIT_CONFIG_KEY_PREFIX}{int(guild_id)}"
def _default_levels_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "notify_channel_id": "",
        "notify_message": " {user} อัปเลเวล {level} !",
        "notify_send_text": True,
        "notify_send_embed": False,
        "notify_send_image": False,
        "notify_embed_title": "Level up!",
        "notify_embed_description": "{user.mention} reached level {level} (XP {xp})",
        "notify_image_theme": "music",
        "notify_image_theme_url": "",
        "notify_image_layout_mode": "center_stack",
        "notify_image_avatar_position": "center",
        "notify_image_text_align": "center",
        "notify_image_font_style": "classic",
        "notify_image_top_text": "{user}",
        "notify_image_bottom_text": "Level {level}",
        "max_level": 120,
        "sources": {
            "text": True,
            "voice": False,
            "command": True,
            "reaction": False,
        },
        "text_xp_min": 8,
        "text_xp_max": 14,
        "text_cooldown": 45,
        "voice_xp_gain": 6,
        "voice_cooldown": 300,
        "command_xp_gain": 5,
        "command_cooldown": 120,
        "reaction_xp_gain": 2,
        "reaction_cooldown": 90,
        "reward_roles": [],
        "stack_reward_roles": False,
    }


def _normalize_levels_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_levels_settings()

    def _safe_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    out["enabled"] = _safe_bool(src.get("enabled"), out["enabled"])
    notify_channel_id = str(src.get("notify_channel_id") or "").strip()
    out["notify_channel_id"] = notify_channel_id if notify_channel_id.isdigit() else ""
    out["notify_message"] = str(src.get("notify_message") or out["notify_message"]).strip()[:800] or out["notify_message"]
    out["notify_send_text"] = _safe_bool(src.get("notify_send_text"), True)
    out["notify_send_embed"] = _safe_bool(src.get("notify_send_embed"), False)
    out["notify_send_image"] = _safe_bool(src.get("notify_send_image"), False)
    out["notify_embed_title"] = str(src.get("notify_embed_title") or out["notify_embed_title"]).strip()[:200]
    out["notify_embed_description"] = str(src.get("notify_embed_description") or out["notify_embed_description"]).strip()[:900]
    allowed_theme_keys = {"music", "security", "giveaway", "custom", "user", "guild"}
    notify_image_theme = str(src.get("notify_image_theme") or out["notify_image_theme"]).strip().lower()[:32]
    out["notify_image_theme"] = notify_image_theme if notify_image_theme in allowed_theme_keys else "music"
    out["notify_image_theme_url"] = str(src.get("notify_image_theme_url") or out["notify_image_theme_url"]).strip()[:1000]
    out["notify_image_layout_mode"] = str(src.get("notify_image_layout_mode") or out["notify_image_layout_mode"]).strip().lower()[:32] or "center_stack"
    out["notify_image_avatar_position"] = str(src.get("notify_image_avatar_position") or out["notify_image_avatar_position"]).strip().lower()[:32] or "center"
    out["notify_image_text_align"] = str(src.get("notify_image_text_align") or out["notify_image_text_align"]).strip().lower()[:32] or "center"
    allowed_font_styles = {"classic", "clean", "impact", "soft"}
    notify_image_font_style = str(src.get("notify_image_font_style") or out["notify_image_font_style"]).strip().lower()[:32]
    out["notify_image_font_style"] = notify_image_font_style if notify_image_font_style in allowed_font_styles else "classic"
    out["notify_image_top_text"] = str(src.get("notify_image_top_text") or out["notify_image_top_text"]).strip()[:240]
    out["notify_image_bottom_text"] = str(src.get("notify_image_bottom_text") or out["notify_image_bottom_text"]).strip()[:260]
    out["max_level"] = _safe_int(src.get("max_level"), out["max_level"], 5, 1000)

    raw_sources = src.get("sources")
    source_defaults = out.get("sources", {})
    source_result: dict[str, bool] = {}
    for key, default_value in source_defaults.items():
        source_value = default_value
        if isinstance(raw_sources, dict):
            source_value = _safe_bool(raw_sources.get(key), default_value)
        source_result[key] = _safe_bool(src.get(f"source_{key}"), source_value)
    out["sources"] = source_result

    out["text_xp_min"] = _safe_int(src.get("text_xp_min"), out["text_xp_min"], 0, 300)
    out["text_xp_max"] = _safe_int(src.get("text_xp_max"), out["text_xp_max"], out["text_xp_min"], 600)
    if out["text_xp_max"] < out["text_xp_min"]:
        out["text_xp_max"] = out["text_xp_min"]
    out["text_cooldown"] = _safe_int(src.get("text_cooldown"), out["text_cooldown"], 0, 3600)
    out["voice_xp_gain"] = _safe_int(src.get("voice_xp_gain"), out["voice_xp_gain"], 0, 200)
    out["voice_cooldown"] = _safe_int(src.get("voice_cooldown"), out["voice_cooldown"], 10, 3600)
    out["command_xp_gain"] = _safe_int(src.get("command_xp_gain"), out["command_xp_gain"], 0, 300)
    out["command_cooldown"] = _safe_int(src.get("command_cooldown"), out["command_cooldown"], 10, 3600)
    out["reaction_xp_gain"] = _safe_int(src.get("reaction_xp_gain"), out["reaction_xp_gain"], 0, 100)
    out["reaction_cooldown"] = _safe_int(src.get("reaction_cooldown"), out["reaction_cooldown"], 5, 3600)
    out["stack_reward_roles"] = _safe_bool(src.get("stack_reward_roles"), out["stack_reward_roles"])

    rewards: list[dict[str, Any]] = []
    raw_rewards = src.get("reward_roles")
    if isinstance(raw_rewards, list):
        for index, raw_row in enumerate(raw_rewards[:30]):
            row = raw_row if isinstance(raw_row, dict) else {}
            role_id = str(row.get("role_id") or "").strip()
            if not role_id.isdigit():
                continue
            level_value = _safe_int(row.get("level"), index + 1, 1, 1000)
            rewards.append(
                {
                    "id": str(row.get("id") or f"reward_{index+1}_{uuid.uuid4().hex[:8]}").strip()[:64]
                    or f"reward_{index+1}_{uuid.uuid4().hex[:8]}",
                    "level": level_value,
                    "role_id": role_id,
                }
            )
    rewards.sort(key=lambda item: int(item.get("level") or 0))
    out["reward_roles"] = rewards
    if not (out["notify_send_text"] or out["notify_send_embed"] or out["notify_send_image"]):
        out["notify_send_text"] = True
    return out


def _default_color_sets_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "command_color_enabled": True,
        "command_colors_enabled": True,
        "applied_set_id": "natural_lake",
        "list_name": "Color List",
        "shape_name": "circle",
        "background_style": "transparent",
        "background_image_url": "",
        "sets": [
            {"id": "monochrome", "name": "Monochrome", "enabled": True, "colors": ["#FFFFFF", "#F3F4F6", "#E5E7EB", "#D1D5DB", "#9CA3AF", "#6B7280", "#4B5563", "#374151", "#1F2937", "#111827", "#0B0F1A"]},
            {"id": "glow_sun", "name": "Glow Sun", "enabled": True, "colors": ["#FFF7CC", "#FFE799", "#FFD366", "#FFC233", "#FFB000", "#FF9A00", "#FF8A00", "#FF7A00", "#FF6A00", "#FF5A00", "#FF4A00", "#F97316", "#FB923C", "#FDBA74", "#FCD34D", "#FBBF24", "#F59E0B", "#D97706", "#B45309", "#92400E"]},
            {"id": "natural_lake", "name": "Natural Lake", "enabled": True, "colors": ["#D9F99D", "#BEF264", "#A3E635", "#86EFAC", "#4ADE80", "#34D399", "#2DD4BF", "#22C55E", "#16A34A", "#15803D"]},
            {"id": "tea_tree", "name": "Tea Tree", "enabled": True, "colors": ["#D9B99B", "#E8D0BA", "#F5E7DB", "#E5E7D8", "#C7C9B4", "#B6B39A", "#A59A84", "#94846E", "#7E6C57", "#665540"]},
            {"id": "forest_theme", "name": "Forest Theme", "enabled": True, "colors": ["#D1FAE5", "#A7F3D0", "#6EE7B7", "#34D399", "#10B981", "#059669", "#047857", "#065F46", "#064E3B", "#14532D", "#166534", "#15803D", "#16A34A", "#22C55E", "#4ADE80", "#86EFAC", "#BBF7D0"]},
            {"id": "violet_theme", "name": "Violet Theme", "enabled": True, "colors": ["#F3E8FF", "#E9D5FF", "#D8B4FE", "#C084FC", "#A855F7", "#9333EA", "#7E22CE", "#6B21A8", "#581C87", "#3B0764"]},
            {"id": "red_blood", "name": "Red Blood", "enabled": True, "colors": ["#FECACA", "#FCA5A5", "#F87171", "#EF4444", "#DC2626", "#B91C1C", "#991B1B", "#7F1D1D", "#660F1A", "#4C0519"]},
            {"id": "atlantic_ocean", "name": "Atlantic Ocean", "enabled": True, "colors": ["#E0F2FE", "#BAE6FD", "#7DD3FC", "#38BDF8", "#0EA5E9", "#0284C7", "#0369A1", "#075985", "#0C4A6E", "#082F49"]},
            {"id": "pinky_candy", "name": "Pinky Candy", "enabled": True, "colors": ["#FCE7F3", "#FBCFE8", "#F9A8D4", "#F472B6", "#EC4899", "#DB2777", "#BE185D", "#9D174D", "#831843", "#701A75", "#A21CAF", "#C026D3", "#E879F9"]},
            {"id": "safari", "name": "Safari", "enabled": True, "colors": ["#7C4700", "#8C5A12", "#9C6B2A", "#AD7C42", "#BE8E5A", "#CF9F72", "#E0B18A", "#F1C2A2", "#D6B37A", "#B5975A"]},
            {"id": "imperial", "name": "Imperial", "enabled": True, "colors": ["#FF4D4F", "#FF7A45", "#FFA940", "#FFC53D", "#FFD666", "#FAAD14", "#D48806", "#AD6800", "#874D00", "#613400"]},
        ],
    }


def _normalize_color_sets_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    def _safe_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    src = payload if isinstance(payload, dict) else {}
    out = _default_color_sets_settings()
    out["enabled"] = _safe_bool(src.get("enabled"), out["enabled"])
    out["command_color_enabled"] = _safe_bool(
        src.get("command_color_enabled"),
        out["command_color_enabled"],
    )
    out["command_colors_enabled"] = _safe_bool(
        src.get("command_colors_enabled"),
        out["command_colors_enabled"],
    )
    out["applied_set_id"] = str(src.get("applied_set_id") or out["applied_set_id"]).strip()[:64] or out["applied_set_id"]
    out["list_name"] = str(src.get("list_name") or out["list_name"]).strip()[:60] or out["list_name"]
    shape_name = str(src.get("shape_name") or out["shape_name"]).strip().lower()
    if shape_name not in {"circle", "square"}:
        shape_name = out["shape_name"]
    out["shape_name"] = shape_name

    background_style = str(src.get("background_style") or out["background_style"]).strip().lower()
    if background_style in {"โปร่งใส", "ความโปร่งใส", "none", "clear", "alpha"}:
        background_style = "transparent"
    elif background_style in {"ภาพกำหนดเอง", "ภาพ", "custom", "custom_image", "image"}:
        background_style = "custom image"
    if background_style not in {"transparent", "custom image"}:
        background_style = out["background_style"]
    out["background_style"] = background_style

    background_image_url = str(src.get("background_image_url") or "").strip()[:1000]
    if background_image_url and not re.match(r"^https?://", background_image_url, re.I):
        background_image_url = ""
    out["background_image_url"] = background_image_url
    raw_sets = src.get("sets")
    parsed_sets: list[dict[str, Any]] = []
    if isinstance(raw_sets, list):
        for index, raw_row in enumerate(raw_sets[:20]):
            row = raw_row if isinstance(raw_row, dict) else {}
            colors = row.get("colors")
            color_items: list[str] = []
            if isinstance(colors, list):
                for c in colors[:12]:
                    normalized = _normalize_color_hex(c, default="")
                    if normalized:
                        color_items.append(normalized)
            if not color_items:
                color_items = ["#6B8CFF"]
            parsed_sets.append(
                {
                    "id": str(row.get("id") or f"set_{index+1}").strip()[:64] or f"set_{index+1}",
                    "name": str(row.get("name") or f"ชุสี {index+1}").strip()[:50] or f"ชุสี {index+1}",
                    "enabled": _safe_bool(row.get("enabled"), True),
                    "colors": color_items,
                }
            )
    out["sets"] = parsed_sets or out["sets"]
    return out


def _color_sets_settings_from_db(guild_id: int) -> dict[str, Any]:
    raw = str(DASHBOARD_CONFIG_CACHE.get(_color_sets_config_key(guild_id), "") or "").strip()
    if not raw:
        return _default_color_sets_settings()
    try:
        decoded = json.loads(raw)
    except Exception:
        return _default_color_sets_settings()
    return _normalize_color_sets_settings(decoded if isinstance(decoded, dict) else {})


async def _apply_color_set_roles_to_guild(
    guild: discord.Guild | None,
    color_set: dict[str, Any],
) -> tuple[bool, str, list[str]]:
    if guild is None:
        return False, "บอทยังไม่อยู่ในเซิร์ฟเวอร์", []

    me = guild.me
    if me is None:
        return False, "ไม่พบบัญชีบอทในเซิร์ฟเวอร์", []
    if not me.guild_permissions.manage_roles:
        return False, "บอทยังไม่มีสิทธิ์ Manage Roles", []

    raw_colors = color_set.get("colors")
    if not isinstance(raw_colors, list):
        raw_colors = []
    colors = [_normalize_color_hex(c, default="") for c in raw_colors]
    colors = [c for c in colors if re.match(r"^#[0-9A-F]{6}$", c)]
    if not colors:
        return False, "ไม่พบสีที่ใช้งานได้ในชุดสี", []

    existing_roles_by_name: dict[str, discord.Role] = {
        str(role.name): role
        for role in guild.roles
        if str(role.name).isdigit() and not role.is_default()
    }
    created = 0
    updated = 0
    skipped = 0
    failed = 0
    created_role_ids: list[str] = []
    set_name = str(color_set.get("name") or "Color Set").strip()

    for index, hex_color in enumerate(colors, start=1):
        role_name = str(index)
        role_color = discord.Color(int(hex_color.lstrip("#"), 16))
        target_role = existing_roles_by_name.get(role_name)
        reason = f"Apply Color Set: {set_name} ({role_name})"

        if target_role:
            if target_role.managed or me.top_role <= target_role:
                skipped += 1
                continue
            if target_role.color.value == role_color.value:
                skipped += 1
                continue
            try:
                await target_role.edit(color=role_color, mentionable=False, hoist=False, reason=reason)
                updated += 1
            except Exception:
                failed += 1
            continue

        try:
            created_role = await guild.create_role(
                name=role_name,
                color=role_color,
                mentionable=False,
                hoist=False,
                reason=reason,
            )
            existing_roles_by_name[role_name] = created_role
            created += 1
            created_role_ids.append(str(created_role.id))
        except Exception:
            failed += 1

    ok = failed == 0
    summary = f"สร้าง {created} | อัปเดต {updated} | ข้าม {skipped} | ล้มเหลว {failed}"
    if failed > 0:
        return False, f"สร้างบทบาทสีบางส่วนไม่สำเร็จ ({summary})", created_role_ids
    return ok, f"สร้างบทบาทสีสำเร็จ ({summary})", created_role_ids


def _default_starboard_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "active": True,
        "name": "starboard",
        "enabled_channel_id": "",
        "channel_id": "",
        "required_role_id": "",
        "stars_limit": 3,
        "custom_emoji": "⭐",
        "message_mode": "embed",
        "message_template": "⭐ {author} | {content}",
        "embed_author_name": "",
        "embed_author_url": "",
        "embed_author_icon_url": "",
        "embed_title": "ข้อความาว",
        "embed_description": "{content}",
        "embed_thumbnail_url": "",
        "embed_image_url": "",
        "embed_footer_text": "",
        "embed_footer_icon_url": "",
        "fields": [],
        "color": "#6B8CFF",
        "ignore_self_stars": True,
        "react_to_starboard_post": False,
    }


def _normalize_embed_message_response(raw: Any, index: int = 0) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {}
    options: list[str] = []
    raw_options = row.get("options")
    if isinstance(raw_options, list):
        for opt in raw_options[:25]:
            text = str(opt or "").strip()[:90]
            if text:
                options.append(text)
    response_type = str(row.get("type") or "button").strip().lower()
    if response_type not in {"button", "select"}:
        response_type = "button"
    return {
        "id": str(row.get("id") or f"resp_{index+1}_{uuid.uuid4().hex[:8]}").strip()[:64] or f"resp_{index+1}_{uuid.uuid4().hex[:8]}",
        "type": response_type,
        "label": str(row.get("label") or "ตัวเลือก").strip()[:80] or "ตัวเลือก",
        "style": str(row.get("style") or "primary").strip().lower() if str(row.get("style") or "primary").strip().lower() in {"primary", "secondary", "success", "danger"} else "primary",
        "emoji": str(row.get("emoji") or "").strip()[:64],
        "options": options,
    }


def _default_temp_channels_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "create_vc_category_id": "",
        "create_vc_channel_id": "",
        "delete_delay_seconds": 3,
        "max_channels_per_user": 1,
        "default_user_limit": 0,
        "command_name": "สร้าง",
        "enable_role_id": "",
        "disable_role_id": "",
        "enabled_channel_id": "",
        "disabled_channel_id": "",
        "auto_delete_message": False,
        "auto_delete_command": False,
        "auto_delete_bot_reply": False,
        "interface_mode": "embed",
        "interface_content": "",
        "embed_color": "#5865F2",
        "embed_author_name": "",
        "embed_author_url": "",
        "embed_author_icon_url": "",
        "embed_title": "TempVoice Interface",
        "embed_description": "This interface can be used to manage temporary voice channels.\nMore options are available with /voice commands.",
        "embed_thumbnail_url": "",
        "embed_image_url": "",
        "embed_footer_text": "Press the buttons below to use the interface.",
        "embed_footer_icon_url": "",
        "fields": [],
        "send_channel_id": "",
        "buttons": {
            "name": True,
            "limit": True,
            "privacy": True,
            "chat": True,
            "trust": True,
            "untrust": True,
            "kick": True,
            "region": True,
            "block": True,
            "unblock": True,
            "claim": True,
            "transfer": True,
            "delete": True,
        },
    }


def _trusted_desc_text(desc_key: str, language: str = "th") -> str:
    text_map = {
        "th": {
            "trusted_server_1_desc": "กิลด์ใช้งานจริง",
            "trusted_server_2_desc": "ทีมทดสอบหลัก",
            "trusted_server_3_desc": "ระบบทิกเก็ตและซัพพอร์ต",
            "trusted_server_4_desc": "โฟกัสฟีเจอร์เพลง",
            "trusted_server_5_desc": "กลุ่มผู้ใช้งานแพ็กเกจพรีเมียม",
            "trusted_server_5b_desc": "กลุ่มผู้ใช้งานฟรีจริง",
            "trusted_server_6_desc": "ทดสอบระบบจัดการเซิร์ฟ",
            "trusted_server_7_desc": "กิจกรรมและการแจกของ",
            "trusted_server_8_desc": "ดูแลผู้ใช้และงานซัพพอร์ต",
            "trusted_server_real_desc": "คอมมูนิตี้ผู้ใช้งานจริง",
        },
        "en": {
            "trusted_server_1_desc": "Real production guild",
            "trusted_server_2_desc": "Primary testing team",
            "trusted_server_3_desc": "Tickets and support workflows",
            "trusted_server_4_desc": "Focused on music features",
            "trusted_server_5_desc": "Premium user community",
            "trusted_server_5b_desc": "Real free-user community",
            "trusted_server_6_desc": "Moderation system testing",
            "trusted_server_7_desc": "Events and giveaways",
            "trusted_server_8_desc": "User support and staff operations",
            "trusted_server_real_desc": "Real SkylineBOT community",
        },
    }
    selected = text_map.get(language, text_map["th"])
    return selected.get(desc_key) or text_map["th"].get(desc_key) or "คอมมูนิตี้ผู้ใช้งานจริง"
def _music_search_results_payload(tracks: list[Any], *, limit: int = 10) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, track in enumerate(tracks[:limit], start=1):
        payload.append(
            {
                "index": index,
                "title": _clean_text(getattr(track, "title", "Unknown")),
                "author": _clean_text(getattr(track, "author", "Unknown")),
                "duration": _format_ms(getattr(track, "length", 0)),
                "uri": _clean_text(getattr(track, "uri", "")),
            }
        )
    return payload


async def _handle_music_web_action(
    bot_guild,
    action: str,
    *,
    query: str = "",
    volume: int | None = None,
    queue_index: int | None = None,
    select_index: int | None = None,
    seek_ms: int | None = None,
    default_volume: int = 80,
    allow_link_playback: bool = True,
    queue_limit: int = 15,
) -> tuple[bool, str, dict[str, Any]]:
    voice_client = _active_music_client(bot_guild)
    if not voice_client:
        return False, "บอทยังไม่ได้เชื่อมห้องเสียงในกิลด์นี้", {}
    safe_queue_limit = max(1, min(99, int(queue_limit or 15)))

    try:
        if action == "pause_toggle":
            is_paused = bool(getattr(voice_client, "paused", False))
            await voice_client.pause(not is_paused)
            return True, ("เล่นเพลงต่อแล้ว" if is_paused else "พักเพลงแล้ว"), {}

        if action == "skip":
            queue = getattr(voice_client, "queue", [])
            autoplay = getattr(voice_client, "autoplay", None)
            if not queue and autoplay == wavelink.AutoPlayMode.disabled:
                return False, "ไม่มีเพลงถัดไปในคิว", {}
            await voice_client.skip(force=True)
            return True, "ข้ามเพลงแล้ว", {}

        if action == "previous":
            history = getattr(getattr(voice_client, "queue", None), "history", None)
            previous_track = None
            if history is not None:
                try:
                    history_items = list(history)
                    if history_items:
                        previous_track = history_items[-1]
                except Exception:
                    previous_track = None
            if previous_track is not None:
                current_volume = int(getattr(voice_client, "volume", default_volume) or default_volume)
                await voice_client.play(previous_track, volume=max(0, min(100, current_volume)))
                return True, "ย้อนกลับไปเพลงก่อนหน้าแล้ว", {}
            if getattr(voice_client, "current", None):
                await voice_client.seek(0)
                return True, "ย้อนเพลงปัจจุบันกลับไปจุดเริ่มต้นแล้ว", {}
            return False, "ไม่มีเพลงให้ย้อนกลับ", {}

        if action == "seek_backward":
            current = getattr(voice_client, "current", None)
            if not current:
                return False, "ยังไม่มีเพลงที่กำลังเล่น", {}
            current_ms = max(0, int(getattr(voice_client, "position", 0) or 0))
            target = max(0, current_ms - 10_000)
            await voice_client.seek(target)
            return True, f"ย้อนกลับ 10 วินาที ({_format_ms(target)})", {}

        if action == "seek_forward":
            current = getattr(voice_client, "current", None)
            if not current:
                return False, "ยังไม่มีเพลงที่กำลังเล่น", {}
            current_ms = max(0, int(getattr(voice_client, "position", 0) or 0))
            duration = max(0, int(getattr(current, "length", 0) or 0))
            target = current_ms + 10_000
            if duration > 0:
                target = min(target, max(0, duration - 1000))
            await voice_client.seek(target)
            return True, f"ข้ามไปข้างหน้า 10 วินาที ({_format_ms(target)})", {}

        if action == "seek_to":
            current = getattr(voice_client, "current", None)
            if not current:
                return False, "ยังไม่มีเพลงที่กำลังเล่น", {}
            if seek_ms is None:
                return False, "ไม่พบเวลาที่ต้องการเลื่อน", {}
            duration = max(0, int(getattr(current, "length", 0) or 0))
            target = max(0, int(seek_ms))
            if duration > 0:
                target = min(target, max(0, duration - 1000))
            await voice_client.seek(target)
            return True, f"เลื่อนไปที่ {_format_ms(target)} แล้ว", {}

        if action == "loop_toggle":
            queue_obj = getattr(voice_client, "queue", None)
            if queue_obj is None or not hasattr(queue_obj, "mode"):
                return False, "ไม่พบระบบคิวเพลง", {}
            if queue_obj.mode == wavelink.QueueMode.loop:
                queue_obj.mode = wavelink.QueueMode.normal
                return True, "ปิดโหมดวนซ้ำแล้ว", {}
            queue_obj.mode = wavelink.QueueMode.loop
            return True, "เปิดโหมดวนซ้ำแล้ว", {}

        if action == "stop":
            try:
                voice_client.queue.clear()
            except Exception:
                pass
            await voice_client.stop()
            await voice_client.disconnect()
            return True, "หยุดเพลงและออกจากห้องเสียงแล้ว", {}

        if action == "volume_up":
            current_volume = int(getattr(voice_client, "volume", 80) or 80)
            new_volume = min(100, current_volume + 10)
            await voice_client.set_volume(new_volume)
            return True, f"ปรับเสียงเป็น {new_volume}%", {}

        if action == "volume_down":
            current_volume = int(getattr(voice_client, "volume", 80) or 80)
            new_volume = max(0, current_volume - 10)
            await voice_client.set_volume(new_volume)
            return True, f"ปรับเสียงเป็น {new_volume}%", {}

        if action == "autoplay_toggle":
            current_autoplay = getattr(voice_client, "autoplay", None)
            if current_autoplay == wavelink.AutoPlayMode.disabled:
                voice_client.autoplay = wavelink.AutoPlayMode.enabled
                return True, "Autoplay enabled", {"autoplay": True}
            voice_client.autoplay = wavelink.AutoPlayMode.disabled
            return True, "Autoplay disabled", {"autoplay": False}

        if action == "shuffle_queue":
            queue_obj = getattr(voice_client, "queue", None)
            if queue_obj is None:
                return False, "Queue unavailable", {}
            queue_items = list(queue_obj or [])
            if len(queue_items) < 2:
                return False, "Need at least 2 tracks in queue", {}
            random.shuffle(queue_items)
            try:
                queue_obj.clear()
            except Exception:
                pass
            for queue_track in queue_items:
                await queue_obj.put_wait(queue_track)
            return True, f"Queue shuffled ({len(queue_items)} tracks)", {}

        if action == "set_volume":
            if volume is None:
                return False, "กรุณาระบุระดับเสียง", {}
            safe_volume = max(0, min(100, int(volume)))
            await voice_client.set_volume(safe_volume)
            return True, f"ตั้งระดับเสียงเป็น {safe_volume}%", {}

        if action == "delete_queue":
            if queue_index is None:
                return False, "ไม่พบลำดับเพลงที่ต้องการลบ", {}
            queue_obj = getattr(voice_client, "queue", None)
            if queue_obj is None:
                return False, "ไม่พบคิวเพลง", {}
            queue_items = list(queue_obj)
            delete_at = max(1, int(queue_index)) - 1
            if delete_at >= len(queue_items):
                return False, "ลำดับเพลงไม่ถูกต้อง", {}
            deleted_title = getattr(queue_items[delete_at], "title", "Unknown")
            queue_obj.delete(delete_at)
            return True, f"ลบเพลงออกจากคิวแล้ว: {deleted_title}", {}

        if action == "search_tracks":
            search_query = query.strip()
            if not search_query:
                return False, "กรุณาใส่ชื่อเพลงหรือ URL", {}
            if not re.search(r"[A-Za-z0-9\u0E00-\u0E7F]", search_query):
                return False, "กรุณาใส่คำค้นหาเพลงที่ชัดเจน", {}
            if not allow_link_playback and _looks_like_music_url_query(search_query):
                return False, "แพ็กเกจ Free ยังไม่รองรับการเล่นผ่านลิงก์", {}
            result = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTube)
            if not result:
                return False, "ไม่พบเพลงที่ค้นหา ลองพิมพ์ชื่อเต็มขึ้น หรือส่งลิงก์เพลงโดยตรง", {}
            return True, f"พบผลการค้นหา {min(len(result), 10)} เพลง", {
                "search_query": search_query,
                "search_results": _music_search_results_payload(list(result), limit=10),
            }

        if action == "add_track_at":
            search_query = query.strip()
            if not search_query:
                return False, "กรุณาใส่ชื่อเพลงหรือ URL", {}
            if not re.search(r"[A-Za-z0-9\u0E00-\u0E7F]", search_query):
                return False, "กรุณาใส่คำค้นหาเพลงที่ชัดเจน", {}
            if select_index is None:
                return False, "ไม่พบลำดับเพลงที่ต้องการเพิ่ม", {}
            if not allow_link_playback and _looks_like_music_url_query(search_query):
                return False, "แพ็กเกจ Free ยังไม่รองรับการเล่นผ่านลิงก์", {}
            result = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTube)
            if not result:
                return False, "ไม่พบเพลงที่ค้นหา", {}
            safe_index = max(1, int(select_index))
            if safe_index > min(len(result), 10):
                return False, "ลำดับเพลงไม่ถูกต้อง", {}
            track = result[safe_index - 1]
            shifted_results = _music_search_results_after_pick(
                list(result),
                picked_index=safe_index,
                limit=10,
            )
            extra_payload = {
                "search_query": search_query,
                "search_results": shifted_results,
            }
            if getattr(voice_client, "current", None):
                try:
                    current_queue_size = len(getattr(voice_client, "queue", []) or [])
                except Exception:
                    current_queue_size = 0
                if current_queue_size >= safe_queue_limit:
                    return False, f"คิวเต็มแล้ว (เพิ่มได้สูงสุด {safe_queue_limit} เพลง)", extra_payload
                await voice_client.queue.put_wait(track)
                return True, f"เพิ่มเข้าคิวแล้ว: {track.title}", extra_payload

            base_volume = int(getattr(voice_client, "volume", 0) or 0) or default_volume
            await voice_client.play(track, volume=max(0, min(100, base_volume)))
            return True, f"กำลังเล่น: {track.title}", extra_payload

        if action == "add_track":
            search_query = query.strip()
            if not search_query:
                return False, "กรุณาใส่ชื่อเพลงหรือ URL", {}
            if not re.search(r"[A-Za-z0-9\u0E00-\u0E7F]", search_query):
                return False, "กรุณาใส่คำค้นหาเพลงที่ชัดเจน", {}
            if not allow_link_playback and _looks_like_music_url_query(search_query):
                return False, "แพ็กเกจ Free ยังไม่รองรับการเล่นผ่านลิงก์", {}
            result = await wavelink.Playable.search(search_query, source=wavelink.TrackSource.YouTube)
            if not result:
                return False, "ไม่พบเพลงที่ค้นหา", {}
            track = result[0]
            if getattr(voice_client, "current", None):
                try:
                    current_queue_size = len(getattr(voice_client, "queue", []) or [])
                except Exception:
                    current_queue_size = 0
                if current_queue_size >= safe_queue_limit:
                    return False, f"คิวเต็มแล้ว (เพิ่มได้สูงสุด {safe_queue_limit} เพลง)", {}
                await voice_client.queue.put_wait(track)
                return True, f"เพิ่มเข้าคิวแล้ว: {track.title}", {}

            base_volume = int(getattr(voice_client, "volume", 0) or 0) or default_volume
            await voice_client.play(track, volume=max(0, min(100, base_volume)))
            return True, f"กำลังเล่น: {track.title}", {}

        return False, "ไม่รู้จักคำสั่งที่ส่งมา", {}
    except Exception as exc:
        return False, f"ทำรายการไม่สำเร็จ: {type(exc).__name__}", {}




def _translate_brief_th(name: str, brief: str) -> str:
    return _dashboard_localization_domain.translate_brief_th(
        name,
        brief,
        i18n_module=i18n,
        clean_text_fn=_clean_text,
    )


def _command_catalog(language: str = "en") -> list[dict[str, Any]]:
    return _dashboard_commands_domain.command_catalog(
        language=language,
        get_bot_fn=get_bot,
        clean_text_fn=_clean_text,
        localize_command_fn=_localize_command,
    )


def _status_runtime_mode(runtime_settings: dict[str, Any]) -> dict[str, Any]:
    return _dashboard_overview_domain.status_runtime_mode(runtime_settings)

def _status_lavalink_payload(bot_running: bool) -> dict[str, Any]:
    return _dashboard_overview_domain.status_lavalink_payload(
        bot_running=bot_running,
        wavelink_module=wavelink,
    )


async def _status_mongo_payload(timeout_seconds: float = 3.5) -> dict[str, Any]:
    return await _dashboard_overview_domain.status_mongo_payload(
        timeout_seconds=timeout_seconds,
        get_collection_fn=get_collection,
        clean_text_fn=_clean_text,
        asyncio_module=asyncio,
        time_module=time,
    )


async def _status_ai_payload(timeout_seconds: float = 5.0) -> dict[str, Any]:
    return await _dashboard_overview_domain.status_ai_payload(
        timeout_seconds=timeout_seconds,
        clean_text_fn=_clean_text,
        os_module=os,
        time_module=time,
        httpx_module=httpx,
    )


def _status_bot_payload(
    *,
    runtime_settings: dict[str, Any],
    command_error_count_by_module: dict[str, int],
    run_web_enabled: bool | None = None,
    run_bot_enabled: bool | None = None,
    dashboard_enabled: bool | None = None,
    external_discord_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _dashboard_overview_domain.status_bot_payload(
        runtime_settings=runtime_settings,
        command_error_count_by_module=command_error_count_by_module,
        get_bot_fn=get_bot,
        format_uptime_seconds_fn=_format_uptime_seconds,
        command_catalog_fn=_command_catalog,
        run_web_enabled=run_web_enabled,
        run_bot_enabled=run_bot_enabled,
        dashboard_enabled=dashboard_enabled,
        external_discord_state=external_discord_state,
    )


async def _build_system_status_payload(request: Request, *, status_view: str = "bot") -> dict[str, Any]:
    return await _dashboard_overview_domain.build_system_status_payload(
        request,
        status_view=status_view,
        ownerbot_runtime_from_db_fn=_ownerbot_runtime_from_db,
        status_runtime_mode_fn=_status_runtime_mode,
        status_tail_log_lines_fn=_status_tail_log_lines,
        status_extract_command_errors_fn=_status_extract_command_errors,
        status_extract_incidents_fn=_status_extract_incidents,
        status_bot_payload_fn=_status_bot_payload,
        get_discord_service_state_fn=get_discord_service_state,
        status_mongo_payload_fn=_status_mongo_payload,
        status_ai_payload_fn=_status_ai_payload,
        status_lavalink_payload_fn=_status_lavalink_payload,
        status_overall_level_fn=_status_overall_level,
        logs_dir=LOGS_DIR,
        clean_text_fn=_clean_text,
        bkk_tz=_BKK_TZ,
        psutil_module=psutil,
        os_module=os,
        time_module=time,
        datetime_module=datetime,
        asyncio_module=asyncio,
    )


def _render_system_status_page(
    *,
    session: dict[str, Any] | None,
    guilds: list[dict[str, Any]],
    payload: dict[str, Any],
    notice: str | None = None,
    status_view: str = "bot",
) -> str:
    return _dashboard_overview_domain.render_system_status_page(
        session=session,
        guilds=guilds,
        payload=payload,
        notice=notice,
        status_view=status_view,
        escape_fn=_escape,
        render_layout_fn=_render_layout,
        status_level_label_fn=_status_level_label,
        support_status_public_url_fn=_support_status_public_url,
    )


def _render_role_select(name: str, bot_guild: Any, current_id: Any = None, placeholder: str = "เลือกยศ...") -> str:
    return _dashboard_status_ui_utils.render_role_select(
        name,
        bot_guild,
        current_id,
        placeholder,
        escape_fn=_escape,
    )



def _payload_has_meaningful_values(payload: dict[str, Any], *, ignored_keys: set[str] | None = None) -> bool:
    ignored = ignored_keys or {"id", "_id", "guild_id", "created_at", "updated_at", "__fallback_source__"}
    for key, value in payload.items():
        if str(key) in ignored:
            continue
        if isinstance(value, str):
            if value.strip():
                return True
            continue
        if isinstance(value, (list, tuple, set, dict)):
            if len(value) > 0:
                return True
            continue
        if bool(value):
            return True
    return False


def _guild_db_fallback_modules(current_guild: dict[str, Any] | None) -> list[str]:
    if not isinstance(current_guild, dict):
        return []
    guild_id = str(current_guild.get("id") or "").strip()
    if not guild_id:
        return []

    module_payloads: list[tuple[str, Any]] = [
        ("Server Stats", cache.server_stats_cache.get(guild_id)),
        ("OCR", cache.image_ocr_cache.get(guild_id)),
        ("Donate", cache.donate_settings_cache.get(guild_id)),
    ]
    fallback_modules: list[str] = []
    for label, payload in module_payloads:
        if not isinstance(payload, dict):
            continue
        if payload.get("id"):
            continue
        # Only show fallback banner for modules that explicitly came from
        # guild fallback blobs (not merely default in-memory payloads).
        if label in {"Server Stats", "OCR"} and payload.get("__fallback_source__") is not True:
            continue
        if not _payload_has_meaningful_values(payload):
            continue
        fallback_modules.append(label)
    return fallback_modules


def _render_layout(
    *,
    title: str,
    body: str,
    session: dict[str, Any] | None,
    guilds: list[dict[str, Any]] | None = None,
    current_guild: dict[str, Any] | None = None,
    active_tab: str | None = None,
    notice: str | None = None,
    compact_music_user_view: bool = False,
    seo_path: str = "/dashboard",
    seo_image_path: str = "/dashboard/static/image_web_bot/giveaways_dashboard.webp",
) -> str:
    session_data = _session_mapping(session)
    user = session_data.get("user")
    bot_instance = get_bot()
    bot_user = getattr(bot_instance, "user", None)
    bot_display_name = str(getattr(bot_user, "name", "") or getattr(BOT_CONFIG, "NAME", "") or "SkylineBOT")
    bot_display_name_safe = _escape(bot_display_name)
    guild_count_val = len(getattr(bot_instance, "guilds", []) or [])
    bot_created_ts_ms = int(
        (
            getattr(bot_user, "created_at", None) or datetime.datetime.now(tz=datetime.timezone.utc)
        ).timestamp()
        * 1000
    )
    guild_growth_events_js = json.dumps(_guild_growth_events(bot_instance), ensure_ascii=False)
    bot_brand_avatar_raw = (
        getattr(getattr(getattr(bot_user, "display_avatar", None), "url", None), "__str__", lambda: "")()
        or getattr(getattr(bot_user, "avatar", None), "url", None)
        or style_urls.DEFAULT_MUSIC_BANNER
    )
    bot_brand_avatar = _escape(_with_cache_bust(bot_brand_avatar_raw, bucket_seconds=300))
    tab_visuals: dict[str, dict[str, str]] = {
        "overview": {
            "title": "ภาพรวมแดชบอร์ด",
            "desc": "ดูสถานะระบบ คำสั่งหลัก และทางลัดการตั้งค่าที่ใช้งานบ่อย",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "ภาพรวมระบบ",
        },
        "security": {
            "title": "ระบบความปลอดภัย",
            "desc": "ตั้งค่า Anti-Nuke และชั้นป้องกันสำคัญเพื่อปกป้องเซิร์ฟเวอร์",
            "image": style_urls.ANTINUKE,
            "tag": "ความปลอดภัย",
        },
        "moderation": {
            "title": "ระบบดูแลแชท",
            "desc": "ปรับระบบกรองสแปม ลิงก์ และคำไม่เหมาะสมให้เหมาะกับชุมชนของคุณ",
            "image": style_urls.ANTINUKE,
            "tag": "ดูแลแชท",
        },
        "music": {
            "title": "ศูนย์ควบคุมเพลง",
            "desc": "ติดตามเพลงที่กำลังเล่น คิวเพลง และควบคุมทุกอย่างจากแดชบอร์ดแบบเรียลไทม์",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "ระบบเพลง",
        },
        "commands": {
            "title": "ศูนย์จัดการคำสั่ง",
            "desc": "จัดการคำสั่งที่เปิดใช้งาน พร้อมค้นหาและเรียกใช้จากหน้าเดียว",
            "image": style_urls.GIVEAWAY,
            "tag": "ตารางคำสั่ง",
        },
        "logs": {
            "title": "บันทึกการทำงาน",
            "desc": "ติดตามกิจกรรมและเหตุการณ์สำคัญของระบบแบบย้อนหลัง",
            "image": style_urls.GIVEAWAY,
            "tag": "บันทึกระบบ",
        },
        "giveaways": {
            "title": "ศูนย์กิจกรรมแจกของ",
            "desc": "สร้าง ดูแล และสุ่มผู้ชนะกิจกรรมได้จากหน้าเดียว",
            "image": style_urls.GIVEAWAY,
            "tag": "กิจกรรม",
        },
        "tickets": {
            "title": "ศูนย์ทิกเก็ต",
            "desc": "ตั้งค่าระบบทิกเก็ต แผงเปิดเรื่อง และ workflow การซัพพอร์ต",
            "image": style_urls.TICKET,
            "tag": "ศูนย์ซัพพอร์ต",
        },
        "shop": {
            "title": "Guild Shop",
            "desc": "Manage products, payment methods, stock, and automatic delivery in one place.",
            "image": style_urls.GIVEAWAY,
            "tag": "Shop",
        },
        "welcomer": {
            "title": "ศูนย์ต้อนรับสมาชิก",
            "desc": "ออกแบบประสบการณ์ต้อนรับสมาชิกใหม่ด้วยข้อความ ยศ และการทักทายอัตโนมัติ",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "ต้อนรับ",
        },
        "welcome": {
            "title": "ข้อความต้อนรับ",
            "desc": "ตั้งค่าข้อความต้อนรับและการแสดงผลเมื่อสมาชิกใหม่เข้าร่วม",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "ข้อความต้อนรับ",
        },
        "leaver": {
            "title": "ข้อความออกจากเซิร์ฟเวอร์",
            "desc": "ตั้งค่าข้อความลาออก (Leaver) และรูปแบบ Embed ที่ต้องการ",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "โฟลว์ลาออก",
        },
        "promote": {
            "title": "โปรโมตเซิร์ฟ",
            "desc": "จัดการระบบส่งโปรโมตและห้องสาธารณะ พร้อมตัวกรองเนื้อหา",
            "image": style_urls.GIVEAWAY,
            "tag": "โปรโมต",
        },
        "ocr": {
            "title": "สแกนข้อความจากภาพ (OCR)",
            "desc": "ตรวจจับคีย์เวิร์ดจากรูปภาพอัตโนมัติ และแจ้งเตือนไปยังห้องที่กำหนด",
            "image": style_urls.SECURITY,
            "tag": "สแกนรูปภาพ",
        },
        "verify": {
            "title": "ยืนยันตัวตน (Verify)",
            "desc": "ตั้งค่าหน้ายืนยันตัวตน บทบาทรางวัล และฟอร์มเก็บข้อมูลผู้ใช้",
            "image": style_urls.SECURITY,
            "tag": "ยืนยันตัวตน",
        },
        "voice_randomizer": {
            "title": "สุ่มห้องเสียง (Voice Randomizer)",
            "desc": "สร้างแผง Embed ให้สมาชิกสุ่มย้ายเข้าห้องเสียง พร้อมเลือกหมวดหมู่และโหมดห้องได้ทันที",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "Voice",
        },
        "autoresponder": {
            "title": "ตอบกลับอัตโนมัติ (Auto Responder)",
            "desc": "สร้างคำตอบอัตโนมัติจากคีย์เวิร์ด พร้อมกำหนดเงื่อนไขและลำดับความสำคัญ",
            "image": style_urls.GIVEAWAY,
            "tag": "ระบบอัตโนมัติ",
        },
        "customrole": {
            "title": "ระบบยศที่กำหนดเอง (Custom Role)",
            "desc": "ให้สมาชิกเลือกหรือขอยศที่กำหนดได้ พร้อมข้อจำกัดตามแพ็กเกจ",
            "image": style_urls.ANTINUKE,
            "tag": "สิทธิ์สมาชิก",
        },
        "media": {
            "title": "ระบบคลังรูปภาพ/สื่อ (Media Only)",
            "desc": "บังคับให้ห้องแชทส่งได้เฉพาะรูปภาพหรือสื่อเท่านั้น ช่วยจัดระเบียบผลงานหรือรูปภาพ",
            "image": style_urls.SECURITY,
            "tag": "สื่อ",
        },
        "server_stats": {
            "title": "สถิติเซิร์ฟ (ServerStats)",
            "desc": "แสดงจำนวนสมาชิก บอท และสถานะต่างๆ ผ่านชื่อห้องแชทอัตโนมัติ",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "สถิติเซิร์ฟ",
        },
        "donate": {
            "title": "ระบบสนับสนุน (Donate)",
            "desc": "ตั้งค่าช่องทางการรับโดเนต และสิทธิพิเศษสำหรับผู้สนับสนุน",
            "image": style_urls.GIVEAWAY,
            "tag": "สนับสนุน",
        },
        "alerts": {
            "title": "แจ้งเตือนโซเชียล (Alerts)",
            "desc": "ติดตามการอัปเดตจาก Twitch, YouTube, TikTok, GitHub, Facebook และ X แบบอัตโนมัติ",
            "image": style_urls.GIVEAWAY,
            "tag": "โซเชียล",
        },
        "aichat": {
            "title": "แชต AI",
            "desc": "ตั้งค่าห้องแชต AI จัดการผู้ให้บริการ และบันทึกความจำ (AI Memories) ของบอท",
            "image": style_urls.DEFAULT_MUSIC_BANNER,
            "tag": "ผู้ช่วย AI",
        },
        "server_settings": {"title": "ตั้งค่าเซิร์ฟเวอร์", "desc": "จัดการค่าพื้นฐานของเซิร์ฟเวอร์และการทำงานหลักของบอท", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "ตั้งค่าเซิร์ฟ"},
        "embed_messages": {"title": "ข้อความแบบ Embed", "desc": "สร้าง/แก้ไข Embed และส่งไปยังห้องที่ต้องการ", "image": style_urls.GIVEAWAY, "tag": "Embed"},
        "premium_receive": {"title": "รับพรีเมียม", "desc": "จัดการแพ็กเกจพรีเมียมและสิทธิ์ของกิลด์", "image": style_urls.GIVEAWAY, "tag": "พรีเมียม"},
        "tools": {"title": "เครื่องมือเสริม", "desc": "รวมเครื่องมือจัดการระบบและงานแอดมินที่ใช้บ่อย", "image": style_urls.ANTINUKE, "tag": "เครื่องมือ"},
        "welcome_center": {"title": "ศูนย์ต้อนรับ", "desc": "รวมการตั้งค่าข้อความต้อนรับ บทบาท และการทักทายอัตโนมัติ", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "ต้อนรับ"},
        "auto_reply_center": {"title": "ศูนย์ตอบกลับอัตโนมัติ", "desc": "รวมการตั้งค่าคำสั่งตอบกลับตามคีย์เวิร์ดและเงื่อนไขต่าง ๆ", "image": style_urls.GIVEAWAY, "tag": "ตอบกลับอัตโนมัติ"},
        "economy": {"title": "Economy", "desc": "จัดการระบบเศรษฐกิจของเซิร์ฟ: income, store, audit และสถิติต่าง ๆ", "image": style_urls.GIVEAWAY, "tag": "เศรษฐกิจ"},
        "roleplay": {"title": "Roleplay", "desc": "ตั้งค่า preset, ตัวละคร, scenario และอีเวนต์ roleplay แบบคลิกเดียว", "image": style_urls.GIVEAWAY, "tag": "Roleplay"},
        "guildstyle_studio": {"title": "Theme guildstyle", "desc": "ตกแต่งธีมเซิร์ฟเวอร์ ปรับชื่อห้อง ยศ สี และสิทธิ์การมองเห็นแบบครบชุด", "image": style_urls.GIVEAWAY, "tag": "Theme"},
        "levels": {"title": "ระบบเลเวล", "desc": "กำหนด XP, รางวัลยศ และความเร็วการเติบโตของสมาชิก", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "เลเวล"},
        "autoroles": {"title": "ยศอัตโนมัติ", "desc": "กำหนดยศอัตโนมัติตามเงื่อนไขหรือเวลาเข้าร่วม", "image": style_urls.ANTINUKE, "tag": "ยศอัตโนมัติ"},
        "colors": {"title": "ระบบสี", "desc": "จัดการชุดสียศและบทบาทสีสำหรับสมาชิก", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "สี"},
        "reaction_roles": {"title": "Reaction Roles", "desc": "ตั้งค่ายศจากการกดรีแอคชันหรือเมนูเลือก", "image": style_urls.SECURITY, "tag": "Reaction Roles"},
        "starboard": {"title": "Starboard", "desc": "รวบรวมข้อความเด่นขึ้นกระดานดาวอัตโนมัติ", "image": style_urls.GIVEAWAY, "tag": "Starboard"},
        "temp_channels": {"title": "ช่องชั่วคราว", "desc": "สร้างและจัดการช่องชั่วคราวอัตโนมัติ", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "ชั่วคราว"},
        "join_to_create": {"title": "Join To Create VC", "desc": "ตั้งค่าห้อง Join To Create และแผงควบคุมห้องของผู้ใช้", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "J2C Voice"},
        "temp_links": {"title": "ลิงก์ชั่วคราว", "desc": "สร้างลิงก์ชั่วคราวแบบใช้ครั้งเดียวหรือกำหนดวันหมดอายุ", "image": style_urls.SECURITY, "tag": "ลิงก์"},
        "statistics_plus": {"title": "Statistics", "desc": "สรุปสถิติการใช้งานและกิจกรรมสำคัญของเซิร์ฟเวอร์", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "สถิติ"},
        "screening": {"title": "คัดกรองสมาชิก", "desc": "กำหนดขั้นตอนคัดกรองก่อนเข้าใช้งานเซิร์ฟเวอร์", "image": style_urls.SECURITY, "tag": "คัดกรอง"},
        "screening_categories": {"title": "หมวดคัดกรอง", "desc": "จัดการหมวดคำถามและฟอร์มคัดกรองสมาชิก", "image": style_urls.SECURITY, "tag": "หมวดคัดกรอง"},
        "automation": {"title": "ระบบอัตโนมัติ", "desc": "ตั้งค่า automation สำหรับเหตุการณ์และงานประจำ", "image": style_urls.ANTINUKE, "tag": "อัตโนมัติ"},
        "anti_raid": {"title": "Anti-Raid", "desc": "ป้องกันการบุกเซิร์ฟแบบเรียลไทม์", "image": style_urls.ANTINUKE, "tag": "พรีเมียม"},
        "extra_protection": {"title": "การป้องกันเพิ่มเติม", "desc": "เสริมมาตรการความปลอดภัยสำหรับเหตุการณ์ความเสี่ยง", "image": style_urls.ANTINUKE, "tag": "ป้องกัน"},
        "alerts_twitch": {"title": "Twitch Alerts", "desc": "ติดตามสตรีมหรือโพสต์ใหม่จาก Twitch", "image": style_urls.GIVEAWAY, "tag": "Twitch"},
        "alerts_youtube": {"title": "YouTube Alerts", "desc": "ติดตามวิดีโอหรือไลฟ์ใหม่จาก YouTube", "image": style_urls.GIVEAWAY, "tag": "YouTube"},
        "alerts_tiktok": {"title": "TikTok Alerts", "desc": "ติดตามวิดีโอหรือไลฟ์ใหม่จาก TikTok", "image": style_urls.GIVEAWAY, "tag": "TikTok"},
        "alerts_github": {"title": "GitHub Alerts", "desc": "ติดตามกิจกรรมของ repository บน GitHub", "image": style_urls.GIVEAWAY, "tag": "GitHub"},
        "alerts_facebook": {"title": "Facebook Alerts", "desc": "ติดตามโพสต์ใหม่จากเพจ Facebook", "image": style_urls.GIVEAWAY, "tag": "Facebook"},
        "control_panel": {"title": "แผงควบคุม", "desc": "ศูนย์รวมการควบคุมฟีเจอร์หลักของบอท", "image": style_urls.DEFAULT_MUSIC_BANNER, "tag": "แผงควบคุม"},
        "audit_logs": {"title": "บันทึกการตรวจสอบ", "desc": "ติดตามการเปลี่ยนแปลงการตั้งค่าและการกระทำของแอดมิน", "image": style_urls.GIVEAWAY, "tag": "Audit"},
    }
    for _tab_slug, _visual_payload in tab_visuals.items():
        if not isinstance(_visual_payload, dict):
            continue
        _fallback_image = str(_visual_payload.get("image") or style_urls.DEFAULT_MUSIC_BANNER)
        _visual_payload["image"] = style_urls.get_dashboard_tab_hero_image(_tab_slug, _fallback_image)

    guild_nav = ""
    server_rail = ""
    server_switcher_items_html = ""
    resolved_active_tab = str(active_tab or "")
    if guilds:
        rail_items: list[str] = []
        for guild in guilds:
            g_name = str(guild.get("name") or "Guild")
            g_icon = str(guild.get("icon") or "").strip() or _discord_default_avatar_url(guild.get("id", "0"))
            g_initial = _escape((g_name[:2] or "SV").upper())
            rail_items.append(
                f"""
                <a class="server-rail-item{' active' if current_guild and guild['id'] == current_guild['id'] else ''}" href="/dashboard/guild/{guild['id']}" title="{_escape(g_name)}">
                  <img src="{_escape(g_icon)}" alt="{_escape(g_name)}" onerror="this.style.display='none'; this.nextElementSibling.style.display='grid';">
                  <span class="server-rail-fallback">{g_initial}</span>
                </a>
                """
            )
        server_switcher_items_html = "".join(rail_items)
        server_rail = f'<aside class="server-rail">{"".join(rail_items)}</aside>'

    tab_nav = ""
    category_board = ""
    sidebar_nav = ""
    preferred_ui_lang = str(session_data.get("language") or "").strip().lower()
    server_lang = "th"
    if current_guild:
        active_slug = active_tab or "overview"
        active_slug_aliases = {
            "security": "server_settings",
            "moderation": "automation",
            "welcome": "welcome_center",
            "leaver": "welcome_center",
            "logs": "audit_logs",
            "temp_channels": "join_to_create",
        }
        active_slug = active_slug_aliases.get(active_slug, active_slug)
        resolved_active_tab = active_slug
        server_lang = str(
            cache.guilds.get(str(current_guild["id"]), {}).get("language", "th")
        ).lower()
        if server_lang not in {"th", "en"}:
            server_lang = "th"
        runtime_settings = _ownerbot_runtime_from_db()
        hidden_tabs = (
            set()
            if _is_dashboard_admin(session)
            else _ownerbot_hidden_dashboard_tabs(runtime_settings)
        )
        tabs = [
            ("overview", "tab_overview"),
            ("server_settings", "tab_server_settings"),
            ("embed_messages", "tab_embed_messages"),
            ("premium_receive", "tab_premium_receive"),
            ("welcome_center", "tab_welcome_center"),
            ("auto_reply_center", "tab_auto_reply_center"),
            ("economy", "tab_economy"),
            ("roleplay", "tab_roleplay"),
            ("guildstyle_studio", "tab_guildstyle_studio"),
            ("levels", "tab_levels"),
            ("autoroles", "tab_autoroles"),
            ("colors", "tab_colors"),
            ("reaction_roles", "tab_reaction_roles"),
            ("starboard", "tab_starboard"),
            ("join_to_create", "tab_join_to_create"),
            ("temp_links", "tab_temp_links"),
            ("statistics_plus", "tab_statistics_plus"),
            ("screening", "tab_screening"),
            ("screening_categories", "tab_screening_categories"),
            ("automation", "tab_automation"),
            ("anti_raid", "tab_anti_raid"),
            ("extra_protection", "tab_extra_protection"),
            ("alerts_twitch", "tab_alerts_twitch"),
            ("alerts_youtube", "tab_alerts_youtube"),
            ("alerts_tiktok", "tab_alerts_tiktok"),
            ("alerts_github", "tab_alerts_github"),
            ("alerts_facebook", "tab_alerts_facebook"),
            ("music", "tab_music"),
            ("promote", "tab_promote"),
            ("commands", "tab_commands"),
            ("tickets", "tab_tickets"),
            ("shop", "tab_shop"),
            ("giveaways", "tab_giveaways"),
            ("server_stats", "tab_server_stats"),
            ("donate", "tab_donate"),
            ("verify", "tab_verify"),
            ("voice_randomizer", "tab_voice_randomizer"),
            ("ocr", "tab_ocr"),
            ("aichat", "tab_aichat"),
            ("autoresponder", "tab_autoresponder"),
            ("customrole", "tab_customrole"),
            ("media", "tab_media"),
            ("control_panel", "tab_control_panel"),
            ("audit_logs", "tab_audit_logs"),
        ]
        tab_label_text = {
            "tab_overview": "ภาพรวม",
            "tab_server_settings": "ตั้งค่าเซิร์ฟเวอร์",
            "tab_embed_messages": "ข้อความแบบ Embed",
            "tab_premium_receive": "รับพรีมียม",
            "tab_tools": "เครื่องมือ",
            "tab_welcome_center": "ศูนย์ต้อนรับ",
            "tab_auto_reply_center": "ศูนย์ตอบกลับอัตโนมัติ",
            "tab_economy": "Economy",
            "tab_roleplay": "Roleplay",
            "tab_guildstyle_studio": "Theme guildstyle",
            "tab_levels": "เลเวล",
            "tab_autoroles": "ยศอัตโนมัติ",
            "tab_colors": "สี",
            "tab_reaction_roles": "Reaction Roles",
            "tab_starboard": "Starboard",
            "tab_temp_channels": "ช่องชั่วคราว",
            "tab_join_to_create": "Join To Create VC",
            "tab_temp_links": "ลิงก์ชั่วคราว",
            "tab_statistics_plus": "Statistics",
            "tab_screening": "คัดกรอง",
            "tab_screening_categories": "หมวดหมู่",
            "tab_automation": "ระบบอัตโนมัติ",
            "tab_anti_raid": "Anti-Raid",
            "tab_extra_protection": "การป้องกันเพิ่มเติม",
            "tab_alerts_twitch": "Twitch",
            "tab_alerts_youtube": "YouTube",
            "tab_alerts_tiktok": "TikTok",
            "tab_alerts_github": "GitHub",
            "tab_alerts_facebook": "Facebook",
            "tab_music": "เพลง",
            "tab_promote": "โปรโมต",
            "tab_commands": "คำสั่ง",
            "tab_tickets": "Tickets",
            "tab_shop": "Guild Shop",
            "tab_giveaways": "กิจกรรมแจกของ",
            "tab_server_stats": "สถิติเซิร์ฟ",
            "tab_donate": "โดเนท",
            "tab_verify": "ยืนยันตัวตน",
            "tab_voice_randomizer": "สุ่มห้องเสียง",
            "tab_ocr": "สแกนรูปภาพ",
            "tab_aichat": "แชต AI",
            "tab_autoresponder": "ตอบกลับอัตโนมัติ",
            "tab_customrole": "ยศพิเศษ",
            "tab_media": "คลังสื่อ",
            "tab_control_panel": "แผงควบคุม",
            "tab_audit_logs": "บันทึกตรวจสอบ",
        }
        sidebar_icons = {
            "overview": "🏠",
            "server_settings": "⚙️",
            "embed_messages": "🧾",
            "premium_receive": "👑",
            "tools": "🧰",
            "welcome_center": "👋",
            "auto_reply_center": "🗨️",
            "economy": "💵",
            "roleplay": "🎭",
            "guildstyle_studio": "🧱",
            "levels": "🏅",
            "autoroles": "🏷️",
            "colors": "🎨",
            "reaction_roles": "😄",
            "starboard": "⭐",
            "temp_channels": "🧊",
            "join_to_create": "🎙️",
            "temp_links": "🔗",
            "statistics_plus": "🧮",
            "screening": "🧪",
            "screening_categories": "🗂️",
            "automation": "🤖",
            "anti_raid": "🛡️",
            "extra_protection": "🚨",
            "alerts_twitch": "🟣",
            "alerts_youtube": "▶️",
            "alerts_tiktok": "🎵",
            "alerts_github": "🐙",
            "alerts_facebook": "📘",
            "music": "🎵",
            "promote": "📣",
            "commands": "⌨️",
            "tickets": "🎫",
            "shop": "🛒",
            "giveaways": "🎁",
            "server_stats": "📊",
            "donate": "💖",
            "verify": "✅",
            "voice_randomizer": "🎲",
            "ocr": "🔎",
            "aichat": "🤖",
            "autoresponder": "🔁",
            "customrole": "🎭",
            "media": "🖼️",
            "control_panel": "🧭",
            "audit_logs": "📜",
        }
        links = []
        category_cards = []
        tab_info_map: dict[str, dict[str, str]] = {}
        guild_data = cache.guilds.get(str(current_guild["id"]), {})
        if not isinstance(guild_data, dict):
            guild_data = {}
        plan_subscription = (
            current_guild.get("_plan_subscription", {})
            if isinstance(current_guild, dict)
            else {}
        )
        if not isinstance(plan_subscription, dict):
            plan_subscription = {}

        raw_sub = str(guild_data.get("subscription", "free"))
        cache_plan_tier = _normalize_plan_tier(raw_sub)
        row_plan_tier = _normalize_plan_tier(plan_subscription.get("current_plan", "free"))
        row_pending_plan_tier = _normalize_plan_tier(plan_subscription.get("pending_plan", "free"))
        row_status = str(plan_subscription.get("status") or "").strip().lower()

        plan_tier = cache_plan_tier
        if row_plan_tier == "permanent":
            plan_tier = "permanent"
        elif cache_plan_tier == "free" and row_plan_tier != "free":
            plan_tier = row_plan_tier
        if row_status == "free":
            plan_tier = "free"

        sub_type = _plan_display_name(plan_tier)
        sub_start = (
            plan_subscription.get("current_period_start")
            or plan_subscription.get("updated_at")
            or plan_subscription.get("created_at")
            or guild_data.get("subscription_start")
            or guild_data.get("subscription_started_at")
            or guild_data.get("subscription_created_at")
            or guild_data.get("premium_started_at")
            or guild_data.get("updated_at")
            or guild_data.get("created_at")
        )
        sub_end = plan_subscription.get("current_period_end") or guild_data.get("subscription_end")

        plan_color = PLAN_COLORS.get(plan_tier, PLAN_COLORS["free"])
        effective_plan_tier = plan_tier
        tab_required_plan_map = _dashboard_tab_required_plan_map(runtime_settings)
        tab_new_badges = _dashboard_tab_new_badges(runtime_settings)
        premium_tabs = {
            slug_key
            for slug_key, _label_key in tabs
            if str(tab_required_plan_map.get(slug_key, "free")).strip().lower() != "free"
        }

        def _subscription_is_expired(raw_value: Any) -> bool:
            if not raw_value:
                return False
            end_dt: datetime.datetime | None = None
            if isinstance(raw_value, datetime.datetime):
                end_dt = raw_value
            elif isinstance(raw_value, (int, float)):
                try:
                    ts_value = float(raw_value)
                    if ts_value > 10_000_000_000:
                        ts_value /= 1000.0
                    end_dt = datetime.datetime.fromtimestamp(ts_value, tz=datetime.timezone.utc)
                except Exception:
                    end_dt = None
            else:
                text_value = str(raw_value).strip()
                if text_value:
                    try:
                        if text_value.isdigit():
                            ts_value = float(text_value)
                            if ts_value > 10_000_000_000:
                                ts_value /= 1000.0
                            end_dt = datetime.datetime.fromtimestamp(ts_value, tz=datetime.timezone.utc)
                        else:
                            end_dt = datetime.datetime.fromisoformat(text_value.replace("Z", "+00:00"))
                    except Exception:
                        end_dt = None
            if end_dt is None:
                return False
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
            else:
                end_dt = end_dt.astimezone(datetime.timezone.utc)
            return end_dt <= datetime.datetime.now(tz=datetime.timezone.utc)

        if effective_plan_tier not in {"free", "permanent"} and _subscription_is_expired(sub_end):
            effective_plan_tier = "free"
        if _dashboard_ownerbot_mode_enabled(session):
            effective_plan_tier = "diamond"

        def is_locked(slug):
            if slug not in premium_tabs:
                return False
            required_tier = str(tab_required_plan_map.get(str(slug or "").strip().lower(), "free")).strip().lower() or "free"
            return not _is_plan_at_least(effective_plan_tier, required_tier)

        def _tab_badges_markup(slug: str, *, locked: bool) -> str:
            badges: list[str] = []
            if locked:
                badges.append('<span class="side-badge premium">พรีเมียม</span>')
            if slug in tab_new_badges:
                badges.append('<span class="side-badge new">ใหม่</span>')
            if not badges:
                return ""
            return " " + " ".join(badges)

        for slug, label_key in tabs:
            if slug in hidden_tabs:
                continue
            href = (
                f"/dashboard/guild/{current_guild['id']}"
                if slug == "overview"
                else f"/dashboard/guild/{current_guild['id']}/{slug}"
            )
            tab_info_map[slug] = {"label_key": label_key, "href": href}
            locked = is_locked(slug)
            display_label = tab_label_text.get(label_key, label_key)
            top_tab_badge = _tab_badges_markup(slug, locked=locked)
            
            links.append(
                f'<a class="tab{" active" if slug == active_slug else ""}{" locked" if locked else ""}" href="{href}" data-tab-slug="{slug}"><span data-i18n="{label_key}">{_escape(display_label)}</span>{top_tab_badge}</a>'
            )
            tab_style = tab_visuals.get(slug, tab_visuals["overview"])
            lock_badge = '<span class="lock-badge"> พรีเมียม</span>' if locked else ""
            category_cards.append(
                f'<a class="category-card{" active" if slug == active_slug else ""}{" locked" if locked else ""}" href="{href}">'
                f"<img data-fallback src=\"{_escape(tab_style['image'])}\" onerror=\"this.onerror=null;this.src='{_escape(FALLBACK_HERO_IMAGE)}';\" alt=\"{_escape(tab_style['title'])}\">"
                "<div>"
                f'{lock_badge}'
                f'<span class="category-card-badge">{sidebar_icons.get(slug) or "🧩"}</span>'
                f'<span class="category-card-tag">{_escape(tab_style["tag"])}</span>'
                f"<strong data-i18n=\"{label_key}\">{_escape(display_label)}</strong>"
                f"<span>{_escape(tab_style['desc'])}</span>"
                f'<span class="category-card-arrow">{"ปลดล็อกเมื่ออัปเกรด" if locked else "เปิดดูการตั้งค่า"}</span>'
                "</div>"
                "</a>"
            )
        tab_nav = f'<nav class="tabs">{"".join(links)}</nav>'
        category_board = f'<section class="category-board">{"".join(category_cards)}</section>'

        sidebar_groups = [
            ("ทั่วไป", ["overview", "server_settings", "embed_messages", "premium_receive"]),
            ("เครื่องมือ", ["economy", "roleplay", "guildstyle_studio", "music", "promote", "commands", "tickets", "shop", "giveaways", "server_stats", "donate", "verify", "voice_randomizer", "ocr", "aichat", "autoresponder", "customrole", "media"]),
            ("การตั้งค่าชุมชน", ["welcome_center", "auto_reply_center", "levels", "autoroles", "colors", "reaction_roles", "starboard", "join_to_create", "temp_links", "statistics_plus"]),
            ("ความปลอดภัย", ["screening", "screening_categories", "automation", "anti_raid", "extra_protection"]),
            ("โซเชียลแจ้งเตือน", ["alerts_twitch", "alerts_youtube", "alerts_tiktok", "alerts_github", "alerts_facebook"]),
            ("แผงควบคุม", ["control_panel", "audit_logs"]),
        ]
        group_blocks = []
        sidebar_group_icons = {
            "ทั่วไป": "🏠",
            "เครื่องมือ": "🧰",
            "การตั้งค่าชุมชน": "🏘️",
            "ความปลอดภัย": "🛡️",
            "โซเชียลแจ้งเตือน": "📣",
            "": "",
            "แผงควบคุม": "🧭",
        }
        for index, (group_key, slugs) in enumerate(sidebar_groups):
            rows = []
            has_active_in_group = False
            for slug in slugs:
                if slug not in tab_info_map:
                    continue
                data = tab_info_map[slug]
                label_key = data["label_key"]
                href = data["href"]
                display_label = tab_label_text.get(label_key, label_key)
                visual_data = tab_visuals.get(slug, tab_visuals["overview"])
                locked = is_locked(slug)
                if slug == active_slug:
                    has_active_in_group = True
                row_badges = _tab_badges_markup(slug, locked=locked)
                overview_aliases = "หน้าแรก home dashboard" if slug == "overview" else ""
                search_tokens = _escape(f"{display_label} {visual_data.get('tag', '')} {slug} {overview_aliases}".lower())
                rows.append(
                    f'<a class="side-link{" active" if slug == active_slug else ""}{" locked" if locked else ""}" href="{href}" data-tab-slug="{slug}" data-side-search="{search_tokens}">'
                    + f'<span class="side-icon">{sidebar_icons.get(slug) or "🧩"}</span>'
                    + '<span class="side-copy">'
                    + f'<strong><span data-i18n="{label_key}">{_escape(display_label)}</span>'
                    + row_badges
                    + "</strong>"
                    + f'<small>{_escape(visual_data["tag"])}</small>'
                    + "</span>"
                    + ('<span class="side-lock"></span>' if locked else "")
                    + "</a>"
                )
            if rows:
                is_open = "open" if (has_active_in_group or index == 0) else ""
                group_icon = sidebar_group_icons.get(group_key, "")
                group_blocks.append(
                    f'<details class="side-group" {is_open}>'
                    f'<summary><span class="side-group-title"><span class="side-group-icon">{group_icon}</span>{group_key}</span>'
                    f'<span class="side-group-count">{len(rows)}</span></summary>'
                    f'<div class="side-group-body">{"".join(rows)}</div></details>'
                )
        
        # Plan Card
        bkk_tz = datetime.timezone(datetime.timedelta(hours=7))

        def _coerce_subscription_datetime(raw_value: Any) -> datetime.datetime | None:
            if not raw_value:
                return None
            dt_value: datetime.datetime | None = None
            if isinstance(raw_value, datetime.datetime):
                dt_value = raw_value
            elif isinstance(raw_value, (int, float)):
                try:
                    unix_value = float(raw_value)
                    if unix_value > 10_000_000_000:
                        unix_value /= 1000.0
                    dt_value = datetime.datetime.fromtimestamp(unix_value, tz=datetime.timezone.utc)
                except Exception:
                    dt_value = None
            else:
                text_value = str(raw_value).strip()
                if not text_value:
                    return None
                try:
                    if text_value.isdigit():
                        unix_value = float(text_value)
                        if unix_value > 10_000_000_000:
                            unix_value /= 1000.0
                        dt_value = datetime.datetime.fromtimestamp(unix_value, tz=datetime.timezone.utc)
                    else:
                        dt_value = datetime.datetime.fromisoformat(text_value.replace("Z", "+00:00"))
                except Exception:
                    dt_value = None
            if dt_value is None:
                return None
            if dt_value.tzinfo is None:
                return dt_value.replace(tzinfo=datetime.timezone.utc)
            return dt_value.astimezone(datetime.timezone.utc)

        def _format_subscription_datetime(raw_value: Any) -> str:
            dt_value = _coerce_subscription_datetime(raw_value)
            if not dt_value:
                return "ไม่ระบุ"
            try:
                return dt_value.astimezone(bkk_tz).strftime("%d/%m/%Y %H:%M")
            except Exception:
                return "ไม่ระบุ"

        def _format_subscription_remaining(raw_value: Any) -> str:
            dt_value = _coerce_subscription_datetime(raw_value)
            if not dt_value:
                return "ไม่ระบุ"
            total_seconds = int((dt_value - datetime.datetime.now(tz=datetime.timezone.utc)).total_seconds())
            if total_seconds <= 0:
                return "หมดอายุแล้ว"
            days, rem = divmod(total_seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, _ = divmod(rem, 60)
            parts: list[str] = []
            if days > 0:
                parts.append(f"{days} วัน")
            if hours > 0:
                parts.append(f"{hours} ชั่วโมง")
            if days == 0 and minutes > 0:
                parts.append(f"{minutes} นาที")
            if not parts:
                return "น้อยกว่า 1 นาที"
            return " ".join(parts)

        sub_start_text = _format_subscription_datetime(sub_start)
        if plan_tier == "permanent":
            sub_end_text = "ถาวร"
            sub_remaining_text = "ไม่หมดอายุ"
        elif plan_tier == "free":
            sub_end_text = "-"
            sub_remaining_text = "ไม่หมดอายุ"
        else:
            sub_end_text = _format_subscription_datetime(sub_end)
            sub_remaining_text = _format_subscription_remaining(sub_end)
        pending_plan_note = ""
        if row_pending_plan_tier != "free":
            pending_plan_note = (
                f'<small style="color: var(--muted); display:block;">แผนที่รอดำเนินการ: '
                f'{_escape(_plan_display_name(row_pending_plan_tier))}</small>'
            )

        plan_card = f"""
        <div class="sidebar-plan" style="margin: 10px; padding: 15px; border-radius: 12px; background: rgba(255,255,255,0.03); border: 1px solid {plan_color}44;">
           <div style="display:flex; align-items:center; gap:10px;">
              <span style="font-size: 1.5em;">💎</span>
              <div>
                <strong style="color: {plan_color}; display:block;">Plan: {sub_type}</strong>
                <small style="color: var(--muted); display:block;">วันที่สมัคร: {sub_start_text}</small>
                <small style="color: var(--muted); display:block;">วันหมดอายุ: {sub_end_text}</small>
                <small style="color: var(--muted); display:block;">เหลืออีก: {sub_remaining_text}</small>
                {pending_plan_note}
              </div>
           </div>
        </div>
        """
        sidebar_nav = plan_card + "".join(group_blocks)

    render_language = preferred_ui_lang if preferred_ui_lang in {"th", "en"} else server_lang
    visual = tab_visuals.get(resolved_active_tab, {
        "title": f"แดชบอร์ด {bot_display_name}",
        "desc": "หน้าเว็บโฉมใหม่ แยกหมวดชัดเจน พร้อมการจัดการบอทแบบครบทุกระบบ",
        "image": style_urls.DEFAULT_MUSIC_BANNER,
        "tag": "Dashboard",
    })
    visual_image_source = str(visual.get("image") or style_urls.DEFAULT_MUSIC_BANNER)
    if current_guild and resolved_active_tab == "overview":
        guild_icon = str(current_guild.get("icon") or "").strip()
        if guild_icon:
            visual_image_source = guild_icon
    visual_image = _escape(visual_image_source)
    visual_fallback = _escape(FALLBACK_HERO_IMAGE)
    guild_name = _escape(current_guild["name"]) if current_guild else bot_display_name_safe
    sidebar_server_icon = ""
    if current_guild:
        raw_sidebar_icon = str(current_guild.get("icon") or "").strip()
        if not raw_sidebar_icon:
            raw_sidebar_icon = _discord_default_avatar_url(current_guild.get("id", "0"))
        sidebar_server_icon = _escape(raw_sidebar_icon)
    selected_server_name_html = guild_name if current_guild else bot_display_name_safe
    selected_server_icon_url = sidebar_server_icon if (current_guild and sidebar_server_icon) else bot_brand_avatar
    sidebar_access_html = ""
    if current_guild:
        access_level = str(current_guild.get("_dashboard_access_level") or "").strip().lower()
        access_bits = int(current_guild.get("_dashboard_permission_bits") or 0)
        current_guild_id = str(current_guild.get("id") or "").strip()
        current_user_id = _session_user_id(session)
        if not access_level and isinstance(session, dict):
            for raw_row in list(session.get("guilds", []) or []):
                if str(raw_row.get("id") or "").strip() != current_guild_id:
                    continue
                access_bits = _guild_permission_bits(raw_row)
                if bool(raw_row.get("owner")):
                    access_level = "owner"
                elif access_bits & ADMINISTRATOR:
                    access_level = "admin"
                elif access_bits & MANAGE_GUILD:
                    access_level = "authorized"
                break
        if not access_level and current_user_id is not None:
            if int(current_guild.get("owner_id", 0) or 0) == int(current_user_id):
                access_level = "owner"
        if not access_level:
            access_level = "ownerbot" if _dashboard_ownerbot_mode_enabled(session) else "authorized"

        access_meta = _dashboard_access_visual_meta(access_level, access_bits)
        access_scopes = [
            f'<span class="sidebar-access-scope">{_escape(scope_label)}</span>'
            for scope_label in list(access_meta.get("scopes") or [])
        ]
        access_scopes_html = (
            f'<div class="sidebar-access-scopes">{"".join(access_scopes)}</div>'
            if access_scopes
            else ""
        )
        sidebar_access_html = (
            f'<div class="sidebar-access-indicator sidebar-access-{_escape(access_meta["accent"])}">'
            f'<span class="sidebar-access-icon"><i class="{_escape(access_meta["icon"])}" aria-hidden="true"></i></span>'
            f'<span class="sidebar-access-copy"><strong>{_escape(access_meta["label"])}</strong>'
            f'<small>{_escape(access_meta["desc"])}</small></span>'
            "</div>"
            f"{access_scopes_html}"
        )
    user_display_name_raw = (
        str(user.get("username") or user.get("global_name") or "").strip()
        if isinstance(user, dict)
        else ""
    )
    profile_display_name = user_display_name_raw or bot_display_name
    profile_display_name_safe = _escape(profile_display_name)
    profile_avatar_raw = (
        str(user.get("avatar_url") or "").strip()
        if isinstance(user, dict)
        else ""
    ) or (
        str(getattr(getattr(bot_user, "display_avatar", None), "url", "")).strip()
        if bot_user
        else ""
    )
    if not profile_avatar_raw:
        profile_avatar_raw = _discord_default_avatar_url(user.get("id", "me") if isinstance(user, dict) else "me")
    profile_avatar_safe = _escape(profile_avatar_raw)
    profile_initial = _escape((profile_display_name[:1] or "U").upper())
    profile_home_href = "/dashboard/SetingProfileUser" if user else "/dashboard/login"
    server_switcher_profile_html = (
        f'<a class="group relative block h-12 w-12 overflow-hidden rounded-full border border-[#3f4147] bg-[#313338]" '
        f'href="{profile_home_href}" title="{profile_display_name_safe}">'
        f'<img class="h-full w-full object-cover" src="{profile_avatar_safe}" alt="{profile_display_name_safe}" '
        'loading="eager" decoding="async" fetchpriority="high" data-critical-img="1" '
        f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\';">'
        f'<span class="grid h-full w-full place-items-center text-sm font-semibold text-[#e3e5e8]" style="display:none;">{profile_initial}</span>'
        "</a>"
    )
    if not server_switcher_items_html:
        server_switcher_items_html = (
            '<div class="grid h-12 w-12 place-items-center rounded-full border border-dashed border-[#4b4f59] '
            'text-xs text-[#949ba4]">+</div>'
        )
    hero_tab_slug = re.sub(r"[^a-z0-9_-]+", "-", str(resolved_active_tab or "overview").lower()).strip("-") or "overview"
    page_hero = f"""
    <section class="page-hero page-hero-tab-{hero_tab_slug}">
      <div class="page-hero-copy">
        <span class="page-chip">{_escape(visual['tag'])}</span>
        <h1>{_escape(visual['title'])}</h1>
        <p>{_escape(visual['desc'])}</p>
        <div class="page-chip-row">
          <span class="mini-stat"><span data-i18n="page_chip_guild">กิลด์</span>: {guild_name}</span>
          <span class="mini-stat"><span data-i18n="page_chip_mode">โหมด</span>: <span data-i18n="page_chip_mode_live">จัดการสด</span></span>
        </div>
      </div>
      <div class="page-hero-media">
        <img src="{visual_image}" onerror="this.onerror=null;this.src='{visual_fallback}';" alt="{_escape(visual['title'])}">
      </div>
    </section>
    """

    nav_cluster = f'<section class="nav-cluster">{tab_nav}</section>' if tab_nav else ""
    compact_music_user_layout = bool(compact_music_user_view and current_guild)

    page_mode = (
        "music-user"
        if compact_music_user_layout
        else ("dashboard" if current_guild else ("guild-picker" if session else "landing"))
    )
    hide_global_page_hero_tabs = {"media"}
    if current_guild and resolved_active_tab in hide_global_page_hero_tabs:
        page_hero = ""
    if not current_guild:
        page_hero = ""
        category_board = ""
    elif compact_music_user_layout:
        page_hero = ""
        category_board = ""
        nav_cluster = ""
    discord_runtime = get_discord_service_state()
    discord_level = str((discord_runtime or {}).get("level") or "").strip().lower()
    status_code = (discord_runtime or {}).get("status_code")
    retry_after = (discord_runtime or {}).get("retry_after")
    retry_suffix = ""
    if isinstance(retry_after, (int, float)) and retry_after > 0:
        retry_suffix = f" ระบบกำลังลองเชื่อมต่อใหม่ใน {int(max(round(float(retry_after)), 1))} วินาที"
    status_suffix = f"HTTP {status_code}" if isinstance(status_code, int) else "HTTP ไม่ทราบรหัส"

    discord_runtime_notice = ""
    discord_notice_class = ""
    if discord_level in {"outage", "auth_error", "stopped"}:
        discord_notice_class = "notice-discord-outage"
        discord_runtime_notice = (
            f"Discord ล่มหรือเชื่อมต่อไม่ได้ ({status_suffix}) ตอนนี้บางฟีเจอร์จะใช้งานไม่ได้.{retry_suffix}"
        )
    elif discord_level in {"degraded", "starting"}:
        discord_notice_class = "notice-discord-degraded"
        discord_runtime_notice = (
            f"Discord กำลังมีปัญหา/จำกัดการเรียกใช้งาน ({status_suffix}) อาจช้า หรือใช้บางฟีเจอร์ไม่ได้ชั่วคราว.{retry_suffix}"
        )

    banner_blocks: list[str] = []
    if discord_runtime_notice:
        banner_blocks.append(
            f'<div class="notice {_escape(discord_notice_class)}" data-discord-runtime-banner="1">{_escape(discord_runtime_notice)}</div>'
        )
    fallback_modules = _guild_db_fallback_modules(current_guild)
    if fallback_modules:
        fallback_text = ", ".join(fallback_modules)
        fallback_notice = f"กำลังใช้ DB สำรอง: {fallback_text} ข้อมูลยังบันทึกได้ แต่การซิงก์แบบเรียลไทม์อาจล่าช้า"
        banner_blocks.append(
            f'<div class="notice notice-discord-degraded" data-db-fallback-banner="1">{_escape(fallback_notice)}</div>'
        )
    if notice:
        banner_blocks.append(
            f'<div class="notice" data-transient-notice="1">{_escape(_clean_text(notice))}</div>'
        )
    banner = "".join(banner_blocks)
    profile_subtitle = (
        str((user or {}).get("global_name") or (user or {}).get("username") or "Discord").strip()
        if isinstance(user, dict)
        else "Discord"
    ) or "Discord"
    topbar_account_dropdown_html = (
        (
            '<details class="topbar-account-menu">'
            '<summary class="topbar-account-trigger" role="button" aria-label="User account menu">'
            f'<span class="topbar-account-trigger-avatar"><img src="{profile_avatar_safe}" alt="{profile_display_name_safe}"></span>'
            f'<span class="topbar-account-trigger-name" data-no-auto-i18n="1">{profile_display_name_safe}</span>'
            '<i class="bi bi-chevron-down" aria-hidden="true"></i>'
            "</summary>"
            '<div class="topbar-account-dropdown" role="menu" aria-label="User account links">'
            '<div class="topbar-account-card">'
            f'<a class="topbar-account-card-main" href="/dashboard/SetingProfileUser" title="{profile_display_name_safe}" data-no-auto-i18n="1">'
            f'<span class="topbar-account-card-avatar"><img src="{profile_avatar_safe}" alt="{profile_display_name_safe}"></span>'
            '<span class="topbar-account-card-meta">'
            f'<strong data-no-auto-i18n="1">{profile_display_name_safe}</strong>'
            f'<span data-i18n="account_platform">{_escape(profile_subtitle)}</span>'
            "</span>"
            "</a>"
            '<a class="topbar-account-card-logout" href="/dashboard/logout" data-icon-key="logout">ออกจากระบบ</a>'
            "</div>"
            '<nav class="topbar-account-links" aria-label="User account links">'
            '<a class="topbar-account-link" href="/dashboard/SetingProfileUser" data-icon-key="profile">บัญชีผู้ใช้</a>'
            '<a class="topbar-account-link" href="/leaderboard" data-icon-key="leaderboard">Leaderboard</a>'
            '<a class="topbar-account-link" href="/wallet" data-icon-key="wallet">เติมเงิน</a>'
            '<a class="topbar-account-link" href="/subscribe-plan" data-icon-key="premium">เลือก plan</a>'
            '<a class="topbar-account-link" href="/dashboard/setting-profile-user/topup-history" data-icon-key="history">ประวัติการเติมเงิน</a>'
            '<a class="topbar-account-link" href="/dashboard/setting-profile-user/premium-history" data-icon-key="history">ประวัติพรีเมียม</a>'
            "</nav>"
            "</div>"
            "</details>"
        )
        if user
        else ""
    )
    account = topbar_account_dropdown_html
    ux_controls = (
        '<div class="ux-controls">'
        '<button class="ux-btn lang-toggle-btn" type="button" data-dashboard-action="toggle-lang" '
        'data-i18n="lang_btn" aria-label="Switch language" title="Switch language">'
        '<i class="bi bi-translate" aria-hidden="true"></i><span class="lang-toggle-label">EN</span></button>'
        '<button class="ux-btn theme-toggle-icon" type="button" data-dashboard-action="toggle-theme" '
        'aria-label="Toggle theme" title="Toggle theme"><i class="bi bi-moon-stars-fill" aria-hidden="true"></i></button>'
        "</div>"
    )
    topbar_nav = f"""
    <nav class="main-nav mega-nav">
      <div class="nav-item">
        <a class="nav-link" href="#plugins-catalog" data-i18n="nav_plugins">ปลั๊กอิน</a>
        <section class="mega-menu" aria-hidden="true">
          <div class="mega-inner">
            <div class="mega-columns">
              <div class="mega-col">
                <a class="mega-entry" href="/plugins/moderation"><strong data-i18n="plugin_mod"><span class="mega-entry-icon"></span>ระบบดูแลและความปลอดภัย</strong><span data-i18n="plugin_mod_desc">จัดการแชท ป้องกันสแปม และตั้งค่า Reaction Roles ได้ในที่เดียว</span></a>
                <a class="mega-entry" href="/plugins/utilities"><strong data-i18n="plugin_util"><span class="mega-entry-icon"></span>ยูทิลิตี้</strong><span data-i18n="plugin_util_desc">สร้าง Embed แปลงข้อมูล และใช้เครื่องมือแอดมินประจำวัน</span></a>
                <a class="mega-entry" href="/plugins/social-alerts"><strong data-i18n="plugin_social"><span class="mega-entry-icon"></span>โซเชียลแจ้งเตือน</strong><span data-i18n="plugin_social_desc">ติดตามอัปเดตจาก Twitch, YouTube, TikTok, GitHub, Facebook และ X</span></a>
                <a class="mega-entry" href="/plugins/games-fun"><strong data-i18n="plugin_fun"><span class="mega-entry-icon"></span>เกมและความสนุก</strong><span data-i18n="plugin_fun_desc">คำสั่งเกม มินิเกม และกิจกรรมเพิ่มสีสันให้ชุมชน</span></a>
              </div>
              <div class="mega-col">
                <a class="mega-entry" href="/personalizer"><strong data-i18n="plugin_personal"><span class="mega-entry-icon"></span>ปรับแต่งส่วนตัว</strong><span data-i18n="plugin_personal_desc">ปรับประสบการณ์และการแสดงผลให้เข้ากับเซิร์ฟเวอร์ของคุณ</span></a>
                <a class="mega-entry" href="/premium"><strong data-i18n="plugin_premium"><span class="mega-entry-icon"></span>แพ็กเกจพรีเมียม <em class="mega-entry-badge">HOT</em></strong><span data-i18n="plugin_premium_desc">ปลดล็อก Premium เพื่อเพิ่มขีดจำกัดและฟีเจอร์ขั้นสูงของ SkylineBOT</span></a>
              </div>
            </div>
            <aside class="mega-spotlight">
              <h4 data-i18n="spotlight_title">แนะนำ</h4>
              <div class="mega-spotlight-card">
                <img src="{_escape(style_urls.INDEX_NAV_PLUGINS_SPOTLIGHT_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_HERO_IMAGE)}';" alt="">
                <p data-i18n="spotlight_plugins_desc">รวมปลั๊กอินเด่นที่ช่วยให้การจัดการเซิร์ฟเวอร์เร็วและง่ายขึ้น</p>
              </div>
              <a href="/docs" data-i18n="all_tutorials">ดูคู่มือทั้งหมด</a>
            </aside>
          </div>
        </section>
      </div>
      <div class="nav-item">
        <a class="nav-link" href="#resources-hub" data-i18n="nav_resources">ทรัพยากร</a>
        <section class="mega-menu" aria-hidden="true">
          <div class="mega-inner">
            <div class="mega-columns">
              <div class="mega-col">
                <h4 data-i18n="support_title">ศูนย์ช่วยเหลือ</h4>
                <a class="mega-entry" href="/docs"><strong data-i18n="tutorials_title"><span class="mega-entry-icon"></span>คู่มือ</strong><span data-i18n="tutorials_desc">เรียนรู้การใช้งาน SkylineBOT บน Discord แบบทีละขั้น</span></a>
                <a class="mega-entry" href="/docs"><strong data-i18n="support_portal_title"><span class="mega-entry-icon"></span>พอร์ทัลซัพพอร์ต</strong><span data-i18n="support_portal_desc">ช่องทางช่วยเหลืออย่างเป็นทางการสำหรับปัญหาและคำถามต่าง ๆ</span></a>
                <a class="mega-entry" href="{_escape(style_urls.SUPPORT_SERVER)}" target="_blank" rel="noopener"><strong data-i18n="discord_server_title"><span class="mega-entry-icon"></span>เซิร์ฟเวอร์ซัพพอร์ต</strong><span data-i18n="discord_server_desc">เข้าร่วมเซิร์ฟเวอร์ Discord เพื่อรับความช่วยเหลือได้ทันที</span></a>
                <a class="mega-entry" href="{_escape(_support_status_public_url())}" target="_blank" rel="noopener"><strong><span class="mega-entry-icon"></span>SkyLineBOT Service Status</strong><span>ตรวจสอบสถานะบริการเว็บ/API และระบบที่เกี่ยวข้องแบบเรียลไทม์</span></a>
                <a class="mega-entry" href="/status?view=bot"><strong><span class="mega-entry-icon"></span>SkyLineBOT Status</strong><span>ดูสถานะบอท การเชื่อมต่อ Discord และเหตุการณ์ล่าสุด</span></a>
              </div>
              <div class="mega-col">
                <h4 data-i18n="company_title">เกี่ยวกับเรา</h4>
                <a class="mega-entry" href="/careers"><strong data-i18n="careers_title"><span class="mega-entry-icon"></span>ร่วมงานกับเรา</strong><span data-i18n="careers_desc">โอกาสทำงานสาย Discord และชุมชนกับ SkylineBOT</span></a>
                <a class="mega-entry" href="/report"><strong data-i18n="bug_bounty_title"><span class="mega-entry-icon"></span>Bug Bounty</strong><span data-i18n="bug_bounty_desc">รายงานช่องโหว่และช่วยยกระดับความปลอดภัยของระบบ</span></a>
                <a class="mega-entry" href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener"><strong data-i18n="contact_us_title"><span class="mega-entry-icon"></span>ติดต่อเรา</strong><span data-i18n="contact_us_desc">สอบถามข้อมูลหรือความร่วมมือกับทีมงาน</span></a>
                <a class="mega-entry" href="/report"><strong><span class="mega-entry-icon"></span>รายงานปัญหา</strong><span>แจ้งบั๊กหรือพฤติกรรมผิดปกติที่พบในระบบ</span></a>
              </div>
            </div>
            <aside class="mega-spotlight">
              <h4 data-i18n="spotlight_title">แนะนำ</h4>
              <div class="mega-spotlight-card">
                <img src="{_escape(style_urls.INDEX_NAV_RESOURCES_SPOTLIGHT_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_GIVEAWAY_IMAGE)}';" alt="กิจกรรมแจกของ">
                <p data-i18n="spotlight_resources_desc">อัปเดตบทความและคู่มือล่าสุด</p>
              </div>
              <a href="/docs" data-i18n="all_tutorials">ดูคู่มือทั้งหมด</a>
            </aside>
          </div>
        </section>
      </div>
    </nav>
    """
    premium_href = SUBSCRIBE_PLAN_PATH
    is_admin_user = _is_dashboard_admin(session)
    auth_cta = (
        '<a class="top-cta login" href="/dashboard/login" data-i18n="login_btn">เข้าสู่ระบบ Discord</a>'
        if not user
        else '<a class="top-cta login" href="/dashboard" data-i18n="dashboard_label">แดชบอร์ด</a>'
    )
    home_cta = (
        '<a class="top-cta login" href="/">หน้าแรก</a>'
        if user
        else ""
    )
    redeem_cta = (
        '<a class="top-cta login" href="/redeem">Redeem Code</a>'
        if user
        else ""
    )
    ownerbot_cta = (
        '<a class="top-cta premium" href="/dashboard/admin/ownerbot">OwnerBOT</a>'
        if user and is_admin_user
        else ""
    )
    owner_mode_ctas = ""
    if user and is_admin_user and current_guild:
        active_slug = str(active_tab or "overview").strip().lower() or "overview"
        if active_slug == "welcomer":
            active_slug = "welcome"
        next_path = (
            f"/dashboard/guild/{current_guild['id']}"
            if active_slug == "overview"
            else f"/dashboard/guild/{current_guild['id']}/{active_slug}"
        )
        current_mode = _dashboard_access_mode_from_session(session)
        owner_mode_ctas = (
            '<span class="topbar-mode-switch">'
            f'<a class="top-cta mode{" active" if current_mode == DEFAULT_DASHBOARD_ACCESS_MODE else ""}" '
            f'href="/dashboard/guild/{current_guild["id"]}/access/mode?mode={DEFAULT_DASHBOARD_ACCESS_MODE}&next={urlencode({"next": next_path}).split("=", 1)[1]}">Owner Guild</a>'
            f'<a class="top-cta mode{" active" if current_mode == OWNERBOT_DASHBOARD_ACCESS_MODE else ""}" '
            f'href="/dashboard/guild/{current_guild["id"]}/access/mode?mode={OWNERBOT_DASHBOARD_ACCESS_MODE}&next={urlencode({"next": next_path}).split("=", 1)[1]}">Owner BOT</a>'
            "</span>"
        )
    topbar_ctas = (
        '<div class="topbar-ctas">'
        f"{owner_mode_ctas}"
        f'<a class="top-cta premium" href="{premium_href}" data-i18n="premium_btn">พรีมียม</a>'
        f"{ownerbot_cta}"
        f"{redeem_cta}"
        f'{home_cta}'
        f'{auth_cta}'
        "</div>"
    )

    brand_home_href = "/"
    brand_markup = (
        f'<a class="brand" href="{brand_home_href}" data-page-search="หน้าแรก home index dashboard">'
        f'<img class="brand-badge" src="{bot_brand_avatar}" alt="{bot_display_name_safe}">'
        '<span class="brand-copy">'
        f'<strong>{bot_display_name_safe}</strong>'
        '<span data-i18n="dashboard_label">แดชบอร์ด</span>'
        '</span>'
        '</a>'
    )
    dashboard_top_actions = f'<div class="dashboard-top-actions">{topbar_ctas}</div>' if user else ""
    topbar_html = (
        f'''<header class="topbar topbar-dashboard">
      <div class="topbar-left">
        {brand_markup}
        <div class="dashboard-top-meta">
          <span class="dash-tag" data-no-auto-i18n="1">{guild_name}</span>
          <span class="dash-dot"></span>
          <span>{_escape(visual['title'])}</span>
        </div>
      </div>
      <div class="topbar-right">
        {dashboard_top_actions}
        {ux_controls}
        {account}
      </div>
    </header>'''
        if current_guild
        else f'''<header class="topbar topbar-landing">
      <div class="topbar-left">
        {brand_markup}
        {topbar_nav}
      </div>
      <div class="topbar-right">
        {ux_controls}
        {topbar_ctas}
        {account}
      </div>
    </header>'''
    )

    if current_guild and compact_music_user_layout:
        content_markup = f"""
        <section class="dashboard-shell dashboard-shell-compact">
          <section class="dashboard-main">
            {banner}
            {body}
          </section>
        </section>
        """
    else:
        content_markup = (
            f'''<section class="dashboard-shell{" with-rail" if server_rail else ""}">
      {server_rail}
      <aside class="layout-sidebar">
        <div class="sidebar-server">
          <img src="{sidebar_server_icon}" alt="{guild_name}" onerror="this.onerror=null;this.src='{_escape(_discord_default_avatar_url(current_guild['id'] if current_guild else '0'))}';">
          <div>
            <h3>เซิร์ฟเวอร์ปัจจุบัน</h3>
            <p data-no-auto-i18n="1">{guild_name}</p>
            {sidebar_access_html}
          </div>
        </div>
        <nav class="sidebar-nav">{sidebar_nav}</nav>
      </aside>
      <section class="dashboard-main">
        {banner}
        {page_hero}
        {body}
      </section>
    </section>'''
            if current_guild
            else f"{page_hero}{banner}{nav_cluster}{category_board}{body}"
        )
    sidebar_server_name_html = selected_server_name_html
    sidebar_server_icon_url = selected_server_icon_url
    language_actions_html = ""
    theme_actions_html = (
        '<button class="topbar-action-btn lang-toggle-btn" type="button" data-dashboard-action="toggle-lang" '
        'data-i18n="lang_btn" aria-label="Switch language" title="Switch language">'
        '<i class="bi bi-translate" aria-hidden="true"></i><span class="lang-toggle-label">EN</span></button>'
        '<button class="topbar-action-btn theme-toggle-btn icon-only" type="button" data-dashboard-action="toggle-theme" data-icon-key="theme" '
        'aria-label="Toggle theme" title="Toggle theme"><i class="bi bi-moon-stars-fill" aria-hidden="true"></i></button>'
    )
    if current_guild:
        guild_id_text = _escape(str(current_guild["id"]))
        guild_id_raw = str(current_guild["id"])
        guild_invite_url = _escape(_bot_invite_url(guild_id_raw))
        topbar_center_html = (
            f'<div class="inline-flex items-center gap-2">'
            f'<img class="h-7 w-7 rounded-full border border-[#3f4147] object-cover" src="{bot_brand_avatar}" alt="{bot_display_name_safe}">'
            f'<span class="text-sm font-semibold tracking-wide text-white">{bot_display_name_safe}</span>'
            f"</div>"
        )
        if compact_music_user_layout:
            topbar_actions_html = (
                f"{language_actions_html}"
                f"{theme_actions_html}"
                f'<a class="topbar-action-link" href="/dashboard/music/{guild_id_text}" data-icon-key="music" data-i18n="topbar_music">Music</a>'
                f"{topbar_account_dropdown_html}"
            )
        else:
            topbar_actions_html = (
                f"{language_actions_html}"
                f"{theme_actions_html}"
                '<a class="topbar-action-link" href="/dashboard" data-icon-key="dashboard" data-i18n="topbar_dashboard" data-page-search="หน้าหลัก หน้าแรก dashboard home">แดชบอร์ด</a>'
                '<a class="topbar-action-link" href="/status" data-icon-key="status" data-i18n="topbar_status">สถานะระบบ</a>'
                f'<a class="topbar-action-link" href="/dashboard/guild/{guild_id_text}/commands" data-icon-key="commands" data-i18n="topbar_commands">คำสั่ง</a>'
                '<a class="topbar-action-link" href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener" data-icon-key="contact" data-i18n="topbar_contact">ติดต่อ</a>'
                '<a class="topbar-action-link" href="/donate" data-icon-key="donatebot" data-i18n="topbar_donate">สนับสนุน</a>'
                f"{topbar_account_dropdown_html}"
            )
    else:
        topbar_center_html = (
            f'<div class="inline-flex items-center gap-2">'
            f'<img class="h-7 w-7 rounded-full border border-[#3f4147] object-cover" src="{bot_brand_avatar}" alt="{bot_display_name_safe}">'
            f'<span class="text-sm font-semibold tracking-wide text-white">{bot_display_name_safe}</span>'
            f"</div>"
        )
        topbar_actions_html = (
            f"{language_actions_html}"
            f"{theme_actions_html}"
            '<a class="topbar-action-link" href="/dashboard" data-icon-key="dashboard" data-i18n="topbar_dashboard" data-page-search="หน้าหลัก หน้าแรก dashboard home">แดชบอร์ด</a>'
            '<a class="topbar-action-link" href="/dashboard" data-icon-key="overview" data-i18n="topbar_overview">ภาพรวม</a>'
            '<a class="topbar-action-link" href="/status" data-icon-key="status" data-i18n="topbar_status">สถานะระบบ</a>'
            '<a class="topbar-action-link" href="/commands" data-icon-key="commands" data-i18n="topbar_commands">คำสั่ง</a>'
            f'<a class="topbar-action-link" href="{_escape(_bot_invite_url())}" target="_blank" rel="noopener" data-icon-key="invite" data-i18n="topbar_invite">เชิญบอท</a>'
            '<a class="topbar-action-link" href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener" data-icon-key="contact" data-i18n="topbar_contact">ติดต่อ</a>'
            '<a class="topbar-action-link" href="/donate" data-icon-key="donatebot" data-i18n="topbar_donate">สนับสนุน</a>'
            f"{topbar_account_dropdown_html}"
        )
    sidebar_menu_html = (
        ""
        if compact_music_user_layout
        else (
            sidebar_nav
            or (
                '<div class="rounded-md border border-[#3f4147] bg-[#1f2230] px-3 py-2 text-sm text-[#b5bac1]">'
                "เลือกเซิร์ฟเวอร์จากรายการด้านบนเพื่อเริ่มจัดการ"
                "</div>"
            )
        )
    )
    body_markup = str(body or "")
    if current_guild and not body_markup.strip():
        body_markup = """
        <section class="section-stack dashboard-detail-shell">
          <section class="panel">
            <div class="panel-header detail-page-hero detail-page-hero-auto">
              <div class="panel-title detail-page-hero-copy">
                <h2 data-icon-key="warning">โหลดหน้านี้ไม่สำเร็จ</h2>
                <p>กรุณารีเฟรชหน้าอีกครั้ง หากยังพบปัญหาให้ติดต่อทีมดูแลระบบ</p>
              </div>
            </div>
          </section>
        </section>
        """
    main_content_html = (
        (f"{banner}{body_markup}" if compact_music_user_layout else f"{banner}{page_hero}{body_markup}")
        if current_guild
        else f"{page_hero}{banner}{nav_cluster}{category_board}{body_markup}"
    )
    if compact_music_user_layout:
        server_switcher_profile_html = ""
        server_switcher_items_html = ""
    current_guild_id_text = str(current_guild.get("id") or "").strip() if isinstance(current_guild, dict) else ""
    emoji_picker_endpoint = (
        f"/dashboard/guild/{current_guild_id_text}/emoji-picker"
        if current_guild_id_text
        else ""
    )
    dashboard_bootstrap_json = json.dumps(
        {
            "defaultServerLang": render_language,
            "guildGrowthEvents": json.loads(guild_growth_events_js),
            "guildCount": guild_count_val,
            "botCreatedTsMs": bot_created_ts_ms,
            "guildId": str(current_guild.get("id")) if current_guild else "",
            "activeTab": resolved_active_tab,
            "pageMode": page_mode,
            "discordRuntime": discord_runtime,
            "emojiPicker": {
                "endpoint": emoji_picker_endpoint,
            },
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return _render_dashboard_layout_template(
        title_html=_escape(title),
        page_mode_html=_escape(page_mode),
        topbar_html=topbar_html,
        content_markup=content_markup,
        main_content_html=main_content_html,
        server_switcher_profile_html=server_switcher_profile_html,
        server_switcher_items_html=server_switcher_items_html,
        sidebar_server_name_html=sidebar_server_name_html,
        sidebar_server_icon_url=sidebar_server_icon_url,
        sidebar_server_access_html=sidebar_access_html,
        topbar_center_html=topbar_center_html,
        topbar_actions_html=topbar_actions_html,
        sidebar_menu_html=sidebar_menu_html,
        dashboard_bootstrap_json=dashboard_bootstrap_json,
        global_copyright_html=_escape(_global_copyright_text()),
        seo_path=seo_path,
        seo_image_path=seo_image_path,
        language=render_language,
    )


async def _render_login(
    notice: str | None = None,
    session: dict[str, Any] | None = None,
    *,
    seo_path: str = "/dashboard",
    seo_image_path: str = "",
) -> str:
    user = session.get("user") if session else None
    auth_ready = bool(BOT_CONFIG.DISCORD_CLIENT_ID and BOT_CONFIG.DISCORD_CLIENT_SECRET)
    if user:
        action = '<a class="primary-btn" href="/dashboard" data-i18n="back_dashboard">กลับหน้าแดชบอร์ด</a>'
    elif auth_ready:
        action = '<a class="primary-btn" href="/dashboard/login" data-i18n="login_btn">เข้าสู่ระบบ Discord</a>'
    else:
        action = "<div class='notice' data-i18n='login_notice'>ตั้งค่า `DISCORD_CLIENT_SECRET` ใน `.env` เพื่อเปิดใช้งานการล็อกอิน</div>"
    bot = get_bot()
    plan_pricing_snapshot = await _landing_plan_pricing_snapshot_cached()
    comparison_rows = _premium_table_rows(_premium_feature_rows_from_live_rules(), "premium_live")
    command_plan_table_rows = _premium_table_rows(_premium_command_rows_from_live_rules(), "command_plan_live")
    donation_plan_table_rows = _premium_table_rows(
        _donation_support_rows_from_live_rules(plan_pricing_snapshot),
        "donation_plan_live",
        allow_html=True,
    )
    comparison_table_header_row = _premium_table_header_row("ฟีเจอร์", first_column_i18n="th_feature", with_i18n=True)
    command_plan_table_header_row = _premium_table_header_row("คำสั่ง / สิทธิ์", first_column_i18n="th_command", with_i18n=True)
    donation_plan_table_header_row = _premium_table_header_row("รายละเอียดการสนับสนุน", with_i18n=False)
    pricing_cards = _premium_cards_markup(plan_pricing_snapshot)

    bot_name = _escape(getattr(getattr(bot, "user", None), "name", "") or getattr(BOT_CONFIG, "NAME", "") or "SkylineBOT")
    bot_id = _escape(getattr(getattr(bot, "user", None), "id", "N/A"))
    bot_avatar_url_raw = (
        getattr(getattr(getattr(bot, "user", None), "display_avatar", None), "url", "")
        or getattr(getattr(bot, "user", None), "avatar", "")
        or style_urls.DEFAULT_MUSIC_BANNER
    )
    bot_avatar_url = _escape(_with_cache_bust(bot_avatar_url_raw, bucket_seconds=300))
    trusted_order_db = _trusted_order_from_db()
    trusted_entries, trusted_entries_all = _trusted_server_entries(
        bot,
        _discord_default_avatar_url("trusted"),
        configured_order=trusted_order_db,
    )
    trusted_cards = []
    seen_trusted_names: set[str] = set()
    for index, (guild_name, image_url, desc_key, is_premium, is_support, _member_count) in enumerate(trusted_entries):
        normalized_name = str(guild_name).casefold().strip()
        if not normalized_name or normalized_name in seen_trusted_names:
            continue
        seen_trusted_names.add(normalized_name)
        badge_list: list[str] = []
        if is_premium:
            badge_list.append('<span class="premium-crown" title="Premium Guild">👑</span>')
        if is_support:
            badge_list.append('<span class="support-dev-badge" title="Support Guild">🧑‍💻</span>')
        badge_markup = f'<div class="trusted-card-badges">{"".join(badge_list)}</div>' if badge_list else ""
        card_class = "trusted-server-card"
        if is_premium:
            card_class += " premium"
        if is_support:
            card_class += " support"
        desc_text = _trusted_desc_text(desc_key, "th")
        fallback_image = _discord_default_avatar_url(guild_name or index)
        trusted_cards.append(
            f'<article class="{card_class}">'
            f'{badge_markup}'
            f'<img src="{_escape(str(image_url))}" loading="lazy" decoding="async" onerror="this.onerror=null;this.src=\'{_escape(fallback_image)}\';" alt="{_escape(guild_name)}">'
            f'<div><strong>{_escape(guild_name)}</strong><span data-i18n="{desc_key}">{_escape(desc_text)}</span></div>'
            '</article>'
        )
    trusted_cards_markup = "".join(trusted_cards)
    trusted_total_count = len(trusted_entries_all)
    trusted_premium_count = sum(1 for _, _, _, is_premium, _, _ in trusted_entries_all if is_premium)
    trusted_free_count = max(0, trusted_total_count - trusted_premium_count)
    # Real Stats
    guild_count_val = len(bot.guilds) if bot else 0
    user_count_val = sum(g.member_count for g in bot.guilds if g.member_count) if bot else 0
    guild_growth_events_js = json.dumps(_guild_growth_events(bot), ensure_ascii=False)
    
    # RAM Usage
    process = psutil.Process(os.getpid())
    ram_usage_val = process.memory_info().rss / (1024 * 1024) # MB
    
    # Uptime
    uptime_base = getattr(bot, "start_time", None)
    if not isinstance(uptime_base, datetime.datetime):
        uptime_base = datetime.datetime.now(tz=datetime.timezone.utc)
    if uptime_base.tzinfo is None:
        uptime_base = uptime_base.replace(tzinfo=datetime.timezone.utc)
    uptime = datetime.datetime.now(tz=datetime.timezone.utc) - uptime_base
    days = uptime.days
    hours, rem = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    runtime_polling_enabled = bool(user)
    uptime_str = f"{days} วัน {hours} ชั่วโมง {minutes} นาที {seconds} วินาที"

    # Dev status
    dev_members = []
    dev_ids = list(getattr(users, "developer", [870179991462236170, 767979794411028491]))
    status_labels = {
        "online": "ออนไลน์",
        "idle": "ไม่อยู่",
        "dnd": "ห้ามรบกวน",
        "offline": "ออฟไลน์",
        "streaming": "สตรีมมิ่ง"
    }
    status_priority = {
        "offline": 0,
        "invisible": 0,
        "idle": 1,
        "online": 2,
        "dnd": 3,
        "streaming": 4,
    }

    developer_social_links = _developer_social_links_from_system()
    default_social_links_raw = developer_social_links.get(
        _dashboard_social_utils.DEFAULT_DEVELOPER_SOCIAL_KEY,
        {},
    )
    if not isinstance(default_social_links_raw, dict):
        default_social_links_raw = {}
    developer_id_keys: list[str] = []
    for raw_dev_id in list(dev_ids or []):
        try:
            developer_id_keys.append(str(int(raw_dev_id)))
        except (TypeError, ValueError):
            continue
    has_multiple_developers = len(developer_id_keys) > 1
    has_targeted_social_links = any(
        isinstance(developer_social_links.get(dev_key), dict)
        and bool(developer_social_links.get(dev_key))
        for dev_key in developer_id_keys
    )
    # If there are multiple developers and at least one targeted mapping is configured,
    # stop auto-applying "__default__" links to every developer card.
    # This makes per-owner links truly separated.
    use_default_social_links = not (has_multiple_developers and has_targeted_social_links)

    def _presence_note_from_member(member: Any) -> str:
        activities = list(getattr(member, "activities", []) or [])
        for activity in activities:
            emoji_text = ""
            emoji_value = getattr(activity, "emoji", None)
            if emoji_value:
                emoji_text = str(emoji_value).strip()
            activity_type_raw = getattr(activity, "type", "")
            activity_type_text = str(getattr(activity_type_raw, "name", activity_type_raw) or "").strip().lower()
            if activity_type_text.startswith("activitytype."):
                activity_type_text = activity_type_text.split(".", 1)[1].strip()
            activity_name = str(getattr(activity, "name", "") or "").strip()
            activity_state = str(getattr(activity, "state", "") or "").strip()
            activity_details = str(getattr(activity, "details", "") or "").strip()
            if activity_type_text == "custom" and activity_state:
                candidate = activity_state
            elif activity_name.lower() == "custom status" and activity_state:
                candidate = activity_state
            else:
                candidate = activity_name or activity_state or activity_details
            if candidate:
                note = f"{emoji_text} {candidate}".strip()
                return note[:120]
        return ""

    for dev_id in dev_ids:
        try:
            dev_id = int(dev_id)
        except (TypeError, ValueError):
            continue
        status_raw = "offline"
        user_name = "Skyline Dev"
        handle = "@skyline"
        avatar = style_urls.DEFAULT_MUSIC_BANNER
        presence_note = ""
        
        if bot:
            try:
                # Avoid blocking landing-page render on external API calls.
                user = bot.get_user(dev_id)
                if user:
                    user_name = user.display_name or user.name
                    handle = f"@{user.name}"
                    avatar = str(
                        getattr(getattr(user, "display_avatar", None), "url", "")
                        or getattr(getattr(user, "avatar", None), "url", "")
                        or avatar
                    )
                    
                    # Read presence from every shared guild and keep the highest-priority one.
                    best_score = -1
                    for guild in bot.guilds:
                        member = guild.get_member(dev_id)
                        if not member:
                            continue
                        member_status = str(getattr(member, "status", "offline") or "offline").lower()
                        activities = list(getattr(member, "activities", []) or [])
                        has_streaming = False
                        for activity in activities:
                            activity_type_raw = getattr(activity, "type", None)
                            if activity_type_raw == discord.ActivityType.streaming:
                                has_streaming = True
                                break
                            activity_type_text = str(
                                getattr(activity_type_raw, "name", activity_type_raw) or ""
                            ).strip().lower()
                            if activity_type_text.startswith("activitytype."):
                                activity_type_text = activity_type_text.split(".", 1)[1].strip()
                            if activity_type_text == "streaming":
                                has_streaming = True
                                break
                        if has_streaming:
                            member_status = "streaming"
                        score = status_priority.get(member_status, 0)
                        if score >= best_score:
                            best_score = score
                            status_raw = member_status
                            candidate_note = _presence_note_from_member(member)
                            if candidate_note:
                                presence_note = candidate_note
                            if best_score >= 4:
                                break
            except Exception:
                pass
        
        status_label = status_labels.get(status_raw, "ออฟไลน์")
        if not presence_note:
            presence_note = f"สถานะล่าสุด: {status_label}"
        profile_url = f"https://discord.com/users/{dev_id}"
        social_links_raw = developer_social_links.get(str(dev_id), {})
        if not isinstance(social_links_raw, dict):
            social_links_raw = {}
        if use_default_social_links:
            social_links_merged = dict(default_social_links_raw)
            social_links_merged.update(social_links_raw)
        else:
            social_links_merged = dict(social_links_raw)
        avatar = _with_cache_bust(avatar, bucket_seconds=300)
        dev_members.append({
            "name": user_name,
            "handle": handle,
            "avatar": avatar,
            "status": status_raw,
            "status_label": status_label,
            "presence_note": presence_note,
            "profile_url": profile_url,
            "social_links": {
                "discord": _developer_social_url(social_links_raw, "discord", profile_url),
                "youtube": _developer_social_url(social_links_merged, "youtube", ""),
                "tiktok": _developer_social_url(social_links_merged, "tiktok", ""),
                "instagram": _developer_social_url(social_links_merged, "instagram", ""),
                "facebook": _developer_social_url(social_links_merged, "facebook", ""),
                "x": _developer_social_url(social_links_merged, "x", ""),
                "profile": _developer_social_url(social_links_merged, "profile", ""),
            },
            "social_icons": {
                "discord": _developer_social_icon(social_links_raw, "discord"),
                "youtube": _developer_social_icon(social_links_merged, "youtube"),
                "tiktok": _developer_social_icon(social_links_merged, "tiktok"),
                "instagram": _developer_social_icon(social_links_merged, "instagram"),
                "facebook": _developer_social_icon(social_links_merged, "facebook"),
                "x": _developer_social_icon(social_links_merged, "x"),
                "profile": _developer_social_icon(social_links_merged, "profile"),
            },
        })

    dev_cards = "".join(
        f'''<div class="dev-card">
          <span class="dev-role-tag">ผู้พัฒนาบอท</span>
          <div class="dev-avatar-wrap">
            <img class="dev-avatar" src="{dev['avatar']}" alt="{dev['name']}">
            <span class="dev-status status-{dev['status']}">{dev['status_label']}</span>
          </div>
          <div class="dev-info">
            <strong>{_escape(dev['name'])}</strong>
            <span>{_escape(dev['handle'])}</span>
          </div>
          <p class="dev-presence">{_escape(dev['presence_note'])}</p>
          <div class="dev-socials">
            <a class="dev-social" href="{_escape(dev['social_links']['discord'])}" target="_blank" rel="noopener" title="Discord">{_render_developer_social_icon(dev['social_icons']['discord'], 'discord')}</a>
            <a class="dev-social {'disabled' if not dev['social_links']['youtube'] else ''}" href="{_escape(dev['social_links']['youtube'] or '#')}" target="_blank" rel="noopener" title="YouTube">{_render_developer_social_icon(dev['social_icons']['youtube'], 'youtube')}</a>
            <a class="dev-social {'disabled' if not dev['social_links']['tiktok'] else ''}" href="{_escape(dev['social_links']['tiktok'] or '#')}" target="_blank" rel="noopener" title="TikTok">{_render_developer_social_icon(dev['social_icons']['tiktok'], 'tiktok')}</a>
            <a class="dev-social {'disabled' if not dev['social_links']['instagram'] else ''}" href="{_escape(dev['social_links']['instagram'] or '#')}" target="_blank" rel="noopener" title="Instagram">{_render_developer_social_icon(dev['social_icons']['instagram'], 'instagram')}</a>
            <a class="dev-social {'disabled' if not dev['social_links']['facebook'] else ''}" href="{_escape(dev['social_links']['facebook'] or '#')}" target="_blank" rel="noopener" title="Facebook">{_render_developer_social_icon(dev['social_icons']['facebook'], 'facebook')}</a>
            <a class="dev-social {'disabled' if not dev['social_links']['x'] else ''}" href="{_escape(dev['social_links']['x'] or '#')}" target="_blank" rel="noopener" title="X">{_render_developer_social_icon(dev['social_icons']['x'], 'x')}</a>
            <a class="dev-social {'disabled' if not dev['social_links']['profile'] else ''}" href="{_escape(dev['social_links']['profile'] or '#')}" target="_blank" rel="noopener" title="Web Profile">{_render_developer_social_icon(dev['social_icons']['profile'], 'profile')}</a>
          </div>
        </div>'''
        for dev in dev_members
    )

    guild_count = _escape(f"{guild_count_val:,}")
    user_count = _escape(f"{user_count_val:,}")
    ram_usage = _escape(f"{ram_usage_val:.2f}")
    uptime_anchor = getattr(bot, "start_time", None)
    if not isinstance(uptime_anchor, datetime.datetime):
        uptime_anchor = datetime.datetime.now(tz=datetime.timezone.utc)
    if uptime_anchor.tzinfo is None:
        uptime_anchor = uptime_anchor.replace(tzinfo=datetime.timezone.utc)

    discord_runtime = get_discord_service_state()
    runtime_level = str((discord_runtime or {}).get("level") or "unknown").strip().lower()
    runtime_message = str((discord_runtime or {}).get("message") or "").strip()
    runtime_updated_at = float((discord_runtime or {}).get("updated_at") or 0.0)
    runtime_level_text = runtime_level or "unknown"
    runtime_age = int(max(0, time.time() - runtime_updated_at)) if runtime_updated_at > 0 else None

    runtime_card_variant = "unknown"
    runtime_status_value = "UNKNOWN"
    runtime_status_label = "ยังไม่มีข้อมูล runtime"
    runtime_status_icon = "ℹ️"
    if runtime_level in {"ok", "online", "running"}:
        runtime_card_variant = "ok"
        runtime_status_value = "ONLINE"
        runtime_status_label = "บอททำงานปกติ"
        runtime_status_icon = "🟢"
    elif runtime_level in {"starting", "restart", "restarting", "reload", "reloading"}:
        runtime_card_variant = "loading"
        runtime_status_value = "RELOADING"
        runtime_status_label = "กำลังรีโหลด/เริ่มระบบ"
        runtime_status_icon = "🔄"
    elif runtime_level in {"stopped", "offline"}:
        runtime_card_variant = "off"
        runtime_status_value = "OFFLINE"
        runtime_status_label = "บอทถูกปิด"
        runtime_status_icon = "⛔"
    elif runtime_level in {"degraded", "outage", "auth_error", "error", "err"}:
        runtime_card_variant = "err"
        runtime_status_value = "ERR"
        runtime_status_label = "มีข้อผิดพลาดระบบ"
        runtime_status_icon = "⚠️"
    if runtime_message:
        runtime_status_label = runtime_message[:150]
    runtime_status_meta = "ยังไม่มีเวลาสถานะล่าสุด"
    if isinstance(runtime_age, int):
        runtime_days, runtime_rem = divmod(runtime_age, 24 * 3600)
        runtime_hours, runtime_rem = divmod(runtime_rem, 3600)
        runtime_minutes, runtime_seconds = divmod(runtime_rem, 60)
        runtime_status_meta = (
            f"อัปเดตล่าสุด {runtime_days} วัน {runtime_hours} ชั่วโมง "
            f"{runtime_minutes} นาที {runtime_seconds} วินาที ที่แล้ว"
        )

    uptime_public_url = _escape(_support_status_public_url() or "https://status.skylinebot.xyz")
    body = f"""
    <section class="section-stack dashboard-detail-shell page-index-shell">
    <section class="landing-hero-block">
      <div class="landing-hero-copy">
        <h1 data-i18n="hero_title">ยินดีต้อนรับสู่ {bot_name}</h1>
        <p data-i18n="hero_desc">แดชบอร์ด Discord สำหรับจัดการคำสั่ง ฟีเจอร์ และระบบอัตโนมัติในที่เดียว</p>
        <div class="auth-actions" style="justify-content:flex-start; margin-top:8px;">
          {action}
          <a class="ghost-btn" href="#index-pages-hub" data-i18n="refresh_btn">ดูฟีเจอร์</a>
        </div>
      </div>
      <div class="landing-hero-media">
        <img src="{bot_avatar_url}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_HERO_IMAGE)}';" alt="{bot_name} Hero">
      </div>
    </section>

    <section class="panel">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:12px;">
        <div>
          <h2 data-i18n="invitation_chart_title" data-icon-key="index_growth" style="margin:0;">แนวโน้มการเติบโตของเซิร์ฟเวอร์</h2>
          <p class="muted" style="margin:4px 0 0;">ข้อมูลสรุปย้อนหลังจากสถิติการเชิญบอท</p>
        </div>
        <div class="chart-period-tabs" id="chartPeriodTabs">
          <button class="chart-period-btn" data-period="week" onclick="switchChartPeriod('week',this)">สัปดาห์</button>
          <button class="chart-period-btn active" data-period="month" onclick="switchChartPeriod('month',this)">เดือน</button>
          <button class="chart-period-btn" data-period="year" onclick="switchChartPeriod('year',this)">ปี</button>
          <button class="chart-period-btn" data-period="all" onclick="switchChartPeriod('all',this)">ทั้งหมด</button>
        </div>
      </div>
      <div class="chart-container">
        <canvas id="invitationChart"></canvas>
      </div>
      <div style="margin-top:10px;display:flex;gap:20px;">
        <span class="mini-stat">จำนวนเซิร์ฟเวอร์: <strong id="currentGuildCount">{guild_count}</strong></span>
        <span class="mini-stat">จำนวนผู้ใช้: <strong>{user_count}</strong></span>
      </div>
    </section>

    <section class="panel">
      <h2 data-i18n="bot_status_title" data-icon-key="index_bot_status">สถานะบอท</h2>
      <p class="muted">สรุปตัวชี้วัดหลักของบอทแบบเรียลไทม์</p>
      <div class="stat-grid">
        <article class="stat-card bot-status-card">
          <span class="bot-status-icon" aria-hidden="true">🖥️</span>
          <strong class="bot-status-value">{guild_count}</strong>
          <span class="bot-status-label">เซิร์ฟเวอร์</span>
        </article>
        <article class="stat-card bot-status-card">
          <span class="bot-status-icon" aria-hidden="true">👥</span>
          <strong class="bot-status-value">{user_count}</strong>
          <span class="bot-status-label">ผู้ใช้</span>
        </article>
        <article class="stat-card bot-status-card">
          <span class="bot-status-icon" aria-hidden="true">💾</span>
          <strong class="bot-status-value">{ram_usage}MB</strong>
          <span class="bot-status-label">RAM</span>
        </article>
        <article class="stat-card bot-status-card">
          <span class="bot-status-icon" aria-hidden="true">⏱️</span>
          <strong class="bot-status-value" id="uptime-display" data-uptime-start="{_escape(uptime_anchor.isoformat())}">{uptime_str}</strong>
          <span class="bot-status-label">อัปไทม์</span>
        </article>
        <article
          class="stat-card bot-status-card bot-runtime-card bot-runtime-{runtime_card_variant}"
          id="botRuntimeCard"
          data-runtime-level="{_escape(runtime_level_text)}"
          data-runtime-message="{_escape(runtime_message)}"
          data-runtime-updated-at="{_escape(runtime_updated_at)}"
        >
          <span class="bot-status-icon" aria-hidden="true" id="botRuntimeIcon">{runtime_status_icon}</span>
          <strong class="bot-status-value" id="botRuntimeValue">{runtime_status_value}</strong>
          <span class="bot-status-label" id="botRuntimeLabel">{_escape(runtime_status_label)}</span>
          <small class="muted" id="botRuntimeMeta">{_escape(runtime_status_meta)}</small>
        </article>
      </div>
      <script>
        (function() {{
          const uptimeEl = document.getElementById('uptime-display');
          if (!uptimeEl) return;
          const startTime = new Date(uptimeEl.getAttribute('data-uptime-start')).getTime();
          const runtimeCard = document.getElementById('botRuntimeCard');
          const runtimeValue = document.getElementById('botRuntimeValue');
          const runtimeLabel = document.getElementById('botRuntimeLabel');
          const runtimeMeta = document.getElementById('botRuntimeMeta');
          const runtimeIcon = document.getElementById('botRuntimeIcon');
          const runtimePollingEnabled = {str(bool(runtime_polling_enabled)).lower()};

          function classifyRuntime(levelRaw) {{
            const level = String(levelRaw || '').trim().toLowerCase();
            if (level === 'stopped' || level === 'offline') {{
              return {{ variant: 'off', value: 'OFFLINE', icon: '⛔' }};
            }}
            if (['degraded', 'outage', 'auth_error', 'error', 'err'].includes(level)) {{
              return {{ variant: 'err', value: 'ERR', icon: '⚠️' }};
            }}
            if (['starting', 'restart', 'restarting', 'reload', 'reloading'].includes(level)) {{
              return {{ variant: 'loading', value: 'RELOADING', icon: '🔄' }};
            }}
            if (['ok', 'online', 'running'].includes(level)) {{
              return {{ variant: 'ok', value: 'ONLINE', icon: '🟢' }};
            }}
            return {{ variant: 'unknown', value: 'UNKNOWN', icon: 'ℹ️' }};
          }}

          function runtimeAgeText(updatedAtRaw) {{
            const updatedAt = Number(updatedAtRaw);
            if (!Number.isFinite(updatedAt) || updatedAt <= 0) {{
              return 'ยังไม่มีเวลาสถานะล่าสุด';
            }}
            let age = Math.max(0, Math.floor(Date.now() / 1000) - Math.floor(updatedAt));
            const days = Math.floor(age / (24 * 3600));
            age %= (24 * 3600);
            const hours = Math.floor(age / 3600);
            age %= 3600;
            const minutes = Math.floor(age / 60);
            const seconds = age % 60;
            return (
              'อัปเดตล่าสุด '
              + days + ' วัน '
              + hours + ' ชั่วโมง '
              + minutes + ' นาที '
              + seconds + ' วินาที ที่แล้ว'
            );
          }}

          function refreshRuntimeMeta() {{
            if (!runtimeCard || !runtimeMeta) return;
            runtimeMeta.textContent = runtimeAgeText(runtimeCard.getAttribute('data-runtime-updated-at'));
          }}

          function applyRuntimeState(payloadRaw) {{
            if (!runtimeCard) return;
            const payload = payloadRaw && typeof payloadRaw === 'object' ? payloadRaw : {{}};
            const state = classifyRuntime(payload.level || runtimeCard.getAttribute('data-runtime-level'));
            const message = String(payload.message || runtimeCard.getAttribute('data-runtime-message') || '').trim();
            runtimeCard.className = `stat-card bot-status-card bot-runtime-card bot-runtime-${'{'}state.variant{'}'}`;
            runtimeCard.setAttribute('data-runtime-level', String(payload.level || state.variant));
            runtimeCard.setAttribute('data-runtime-message', message);
            runtimeCard.setAttribute('data-runtime-updated-at', String(payload.updated_at || runtimeCard.getAttribute('data-runtime-updated-at') || ''));
            if (runtimeValue) runtimeValue.textContent = state.value;
            if (runtimeIcon) runtimeIcon.textContent = state.icon;
            if (runtimeLabel) runtimeLabel.textContent = message || 'สถานะ runtime อัปเดตแล้ว';
            refreshRuntimeMeta();
          }}

          const runtimePollVisibleMs = 60000;
          const runtimePollHiddenMs = 180000;
          let runtimePollTimer = 0;
          const runWhenIdle = (callback, timeoutMs = 2500) => {{
            if (typeof window.requestIdleCallback === 'function') {{
              window.requestIdleCallback(callback, {{ timeout: timeoutMs }});
            }} else {{
              window.setTimeout(callback, Math.min(timeoutMs, 1200));
            }}
          }};

          function scheduleRuntimePoll(delayMs) {{
            if (runtimePollTimer) {{
              clearTimeout(runtimePollTimer);
            }}
            runtimePollTimer = setTimeout(() => pollRuntime(), Math.max(1000, Number(delayMs) || runtimePollVisibleMs));
          }}

          async function pollRuntime(force = false) {{
            if (!runtimeCard) return;
            if (!force && document.visibilityState !== 'visible') {{
              scheduleRuntimePoll(runtimePollHiddenMs);
              return;
            }}
            try {{
              const response = await fetch('/dashboard/runtime/discord?compact=1', {{
                method: 'GET',
                credentials: 'same-origin',
                cache: 'no-cache',
                headers: {{ Accept: 'application/json' }},
              }});
              if (!response.ok) return;
              const payload = await response.json();
              applyRuntimeState(payload);
            }} catch (_error) {{
            }} finally {{
              scheduleRuntimePoll(document.visibilityState === 'visible' ? runtimePollVisibleMs : runtimePollHiddenMs);
            }}
          }}
          
          function updateUptime() {{
            const now = new Date().getTime();
            let diff = Math.floor((now - startTime) / 1000);
            if (diff < 0) diff = 0;
            
            const days = Math.floor(diff / (24 * 3600));
            diff %= (24 * 3600);
            const hours = Math.floor(diff / 3600);
            diff %= 3600;
            const minutes = Math.floor(diff / 60);
            const seconds = diff % 60;
            
            uptimeEl.textContent = `${{days}} วัน ${{hours}} ชั่วโมง ${{minutes}} นาที ${{seconds}} วินาที`;
          }}
          applyRuntimeState({{
            level: runtimeCard ? runtimeCard.getAttribute('data-runtime-level') : '',
            message: runtimeCard ? runtimeCard.getAttribute('data-runtime-message') : '',
            updated_at: runtimeCard ? runtimeCard.getAttribute('data-runtime-updated-at') : '',
          }});
          if (runtimePollingEnabled) {{
            runWhenIdle(() => pollRuntime(true), 2600);
            document.addEventListener('visibilitychange', () => {{
              if (document.visibilityState === 'visible') {{
                pollRuntime(true);
              }}
            }});
          }}
          setInterval(refreshRuntimeMeta, 5000);
          setInterval(updateUptime, 5000);
          refreshRuntimeMeta();
          updateUptime();
        }})();
      </script>
    </section>

    <section class="panel">
      <div class="developers-wrap">
        <div class="developers-head">
          <span class="developers-badge"><b>DEV</b> Developers</span>
          <h2 data-i18n="developers_title" data-icon-key="index_developers" style="margin:0;">ผู้พัฒนา</h2>
          <p class="muted" style="margin:0;">ผู้ที่มีส่วนร่วมในการพัฒนาบอท</p>
        </div>
        <div class="dev-grid">
          {dev_cards}
        </div>
      </div>
    </section>

    <section class="landing-showcase">
      <section class="trusted-banner">
        <div class="trusted-shell">
          <h2 data-icon-key="index_trusted">
            <span data-i18n="trusted_title_prefix">คอมมูนิตี้ผู้ใช้งานจริงที่เชื่อถือ:</span>
            {_escape(trusted_total_count)} <span data-i18n="trusted_title_servers">เซิร์ฟเวอร์</span>
            | <span data-i18n="trusted_title_premium">พรีเมียม</span> {_escape(trusted_premium_count)}
            | <span data-i18n="trusted_title_free">ฟรี</span> {_escape(trusted_free_count)}
          </h2>
          <div class="trusted-carousel" id="trustedCarousel">
            <div class="trusted-server-grid" id="trustedServerGrid">
              <div class="trusted-server-row" id="trustedServerRowPrimary">{trusted_cards_markup}</div>
              <div class="trusted-server-row" id="trustedServerRowSecondary" aria-hidden="true">{trusted_cards_markup}</div>
            </div>
          </div>
        </div>
      </section>

      <section class="panel" id="features">
        <div class="bestbot-grid">
          <article class="bestbot-lead">
            <h2 data-i18n="bestbot_title" data-icon-key="index_features">{bot_name}: ผู้ช่วย Discord สำหรับการจัดการเซิร์ฟเวอร์</h2>
            <div class="auth-actions" style="justify-content:flex-start; margin-top:8px;">{action}</div>
          </article>
          <article class="bestbot-feature">
            <span class="bestbot-icon"></span>
            <h3 data-i18n="bestbot_feature_1_title" data-icon-key="index_features_security">ปกป้องเซิร์ฟเวอร์ของคุณ</h3>
            <p data-i18n="bestbot_feature_1_desc">เสริมความปลอดภัยด้วย Anti-Nuke และ AutoMod เพื่อป้องกันสแปม ลิงก์อันตราย และการก่อกวน</p>
          </article>
          <article class="bestbot-feature">
            <span class="bestbot-icon"></span>
            <h3 data-i18n="bestbot_feature_2_title" data-icon-key="index_features_giveaway">จัดการ Giveaway ครบวงจร</h3>
            <p data-i18n="bestbot_feature_2_desc">สร้างกิจกรรมแจกของ สุ่มผู้ชนะ และประกาศผลได้อัตโนมัติจากระบบเดียว</p>
          </article>
          <article class="bestbot-feature">
            <span class="bestbot-icon"></span>
            <h3 data-i18n="bestbot_feature_3_title" data-icon-key="index_features_customize">ปรับแต่งบอทให้ตรงสไตล์เซิร์ฟเวอร์</h3>
            <p data-i18n="bestbot_feature_3_desc">ตั้งค่าข้อความ ระบบยศ ระบบเพลง และฟีเจอร์ต่างๆ ให้ตรงกับรูปแบบชุมชนของคุณ</p>
          </article>
        </div>
      </section>
    </section>

    <section class="panel index-link-hub" id="index-pages-hub">
      <div class="index-link-hub-head">
        <h2 data-icon-key="index_resources">ศูนย์รวมหน้าสำคัญ</h2>
        <p class="muted">รวมปุ่มทางลัดสำหรับหน้าใช้งานหลักของ SkylineBOT ให้เข้าถึงง่ายในคลิกเดียว</p>
        <div class="index-link-hub-meta">
          <span class="index-link-chip"><i class="fa-solid fa-compass" aria-hidden="true"></i> 15 หน้าสำคัญ</span>
          <span class="index-link-chip"><i class="fa-solid fa-bolt" aria-hidden="true"></i> เข้าถึงได้ในคลิกเดียว</span>
        </div>
      </div>
      <style>
        #index-pages-hub .index-link-hub-head h2 {{
          margin: 0;
          font-size: clamp(1.14rem, 2.1vw, 1.38rem);
          letter-spacing: -0.01em;
        }}
        #index-pages-hub .index-link-hub-head .muted {{
          margin: 6px 0 0;
          max-width: 72ch;
          line-height: 1.55;
        }}
        #index-pages-hub .index-link-hub-meta {{
          margin-top: 10px;
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
        }}
        #index-pages-hub .index-link-chip {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 10px;
          border-radius: 999px;
          border: 1px solid rgba(118, 159, 246, 0.34);
          background: rgba(83, 126, 220, 0.15);
          color: #c7dcff;
          font-size: 0.79rem;
          font-weight: 700;
          white-space: nowrap;
        }}
        #index-pages-hub .index-link-chip i {{
          color: #9ec7ff;
          font-size: 0.74rem;
        }}
        body.light-theme #index-pages-hub .index-link-chip {{
          background: rgba(83, 126, 220, 0.11);
          border-color: rgba(83, 126, 220, 0.3);
          color: #2f5da6;
        }}
        body.light-theme #index-pages-hub .index-link-chip i {{
          color: #3f6fbd;
        }}
        #index-pages-hub .index-link-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
          gap: 12px;
          margin-top: 14px;
        }}
        #index-pages-hub .index-link-card {{
          display: flex;
          flex-direction: column;
          gap: 9px;
          min-height: 154px;
          padding: 14px;
          border-radius: 14px;
          text-decoration: none;
          color: var(--text, #e6eeff);
          border: 1px solid rgba(97, 141, 235, 0.3);
          background:
            linear-gradient(165deg, rgba(96, 142, 240, 0.16), rgba(11, 28, 64, 0.52)),
            radial-gradient(90% 120% at 100% 0%, rgba(120, 164, 252, 0.12), transparent 58%);
          box-shadow: 0 8px 20px rgba(7, 18, 42, 0.28);
        }}
        #index-pages-hub .index-link-card:hover {{
          transform: translateY(-2px);
          border-color: rgba(124, 168, 255, 0.62);
          box-shadow: 0 12px 26px rgba(11, 28, 64, 0.32);
        }}
        #index-pages-hub .index-link-card:focus-visible {{
          outline: none;
          border-color: rgba(152, 189, 255, 0.82);
          box-shadow: 0 0 0 2px rgba(124, 168, 255, 0.24), 0 12px 26px rgba(11, 28, 64, 0.34);
        }}
        body.light-theme #index-pages-hub .index-link-card {{
          border-color: rgba(76, 117, 200, 0.32);
          background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 250, 255, 0.94)),
            radial-gradient(90% 120% at 100% 0%, rgba(124, 166, 255, 0.12), transparent 58%);
          box-shadow: 0 10px 22px rgba(44, 78, 141, 0.14);
        }}
        body.light-theme #index-pages-hub .index-link-card strong {{
          color: #16345f;
        }}
        body.light-theme #index-pages-hub .index-link-action {{
          color: #2f5da6;
        }}
        #index-pages-hub .index-link-icon {{
          width: 36px;
          height: 36px;
          border-radius: 11px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 1px solid rgba(124, 166, 255, 0.4);
          background: rgba(92, 136, 224, 0.2);
          color: #9bc8ff;
          font-size: 0.95rem;
        }}
        #index-pages-hub .index-link-card strong {{
          font-size: 1.04rem;
          line-height: 1.24;
          color: #ebf3ff;
        }}
        #index-pages-hub .index-link-card p {{
          margin: 0;
          color: var(--muted, #b7c9ee);
          line-height: 1.46;
          font-size: 0.9rem;
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }}
        #index-pages-hub .index-link-action {{
          margin-top: auto;
          color: #9bc7ff;
          font-weight: 800;
          font-size: 0.82rem;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          letter-spacing: 0.01em;
        }}
        #index-pages-hub .index-link-action::after {{
          content: "\\2192";
          font-weight: 700;
          transition: transform .18s ease;
        }}
        #index-pages-hub .index-link-card:hover .index-link-action::after {{
          transform: translateX(2px);
        }}
        @media (max-width: 760px) {{
          #index-pages-hub .index-link-hub-head .muted {{
            max-width: 100%;
          }}
          #index-pages-hub .index-link-grid {{
            grid-template-columns: repeat(auto-fit, minmax(152px, 1fr));
            gap: 9px;
          }}
          #index-pages-hub .index-link-card {{
            min-height: 132px;
            padding: 10px;
            gap: 7px;
          }}
          #index-pages-hub .index-link-card p {{
            font-size: 0.86rem;
            -webkit-line-clamp: 2;
          }}
          #index-pages-hub .index-link-icon {{
            width: 32px;
            height: 32px;
            font-size: 0.86rem;
          }}
        }}
      </style>
      <div class="index-link-grid">
        <a class="index-link-card" href="/commands" data-page-search="commands command คำสั่ง">
          <span class="index-link-icon"><i class="fa-solid fa-terminal" aria-hidden="true"></i></span>
          <strong data-i18n="hub_commands_title">Commands</strong>
          <p data-i18n="hub_commands_desc">ดูรายการคำสั่งทั้งหมดพร้อมวิธีใช้งาน</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/docs" data-page-search="docs documentation คู่มือ">
          <span class="index-link-icon"><i class="fa-solid fa-book-open" aria-hidden="true"></i></span>
          <strong data-i18n="hub_docs_title">Docs</strong>
          <p data-i18n="hub_docs_desc">เอกสารการตั้งค่าและคู่มือใช้งานครบถ้วน</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/invitebot" data-page-search="invitebot invite เชิญบอท">
          <span class="index-link-icon"><i class="fa-solid fa-user-plus" aria-hidden="true"></i></span>
          <strong data-i18n="hub_invite_title">Invite Bot</strong>
          <p data-i18n="hub_invite_desc">เชิญ SkylineBOT เข้าเซิร์ฟเวอร์ของคุณทันที</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/leaderboard" data-page-search="leader leaderboard leeder อันดับ">
          <span class="index-link-icon"><i class="fa-solid fa-ranking-star" aria-hidden="true"></i></span>
          <strong data-i18n="hub_leaderboard_title">Leaderboard</strong>
          <p data-i18n="hub_leaderboard_desc">ดูอันดับเซิร์ฟเวอร์และสถิติยอดนิยม</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/donate" data-page-search="donate donatebot donatebote โดเนทบอท">
          <span class="index-link-icon"><i class="fa-solid fa-hand-holding-heart" aria-hidden="true"></i></span>
          <strong data-i18n="hub_donate_title">Donate</strong>
          <p data-i18n="hub_donate_desc">จัดการระบบสนับสนุนและหน้ารับโดเนทของบอท</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/promoteserver" data-page-search="promoteserver promote server โปรโมตเซิร์ฟเวอร์">
          <span class="index-link-icon"><i class="fa-solid fa-bullhorn" aria-hidden="true"></i></span>
          <strong data-i18n="hub_promote_title">Promote Server</strong>
          <p data-i18n="hub_promote_desc">ดูโพสต์โปรโมตล่าสุดและติดตามการเติบโตชุมชน</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/terms" data-page-search="terms ข้อกำหนด">
          <span class="index-link-icon"><i class="fa-solid fa-file-contract" aria-hidden="true"></i></span>
          <strong data-i18n="hub_terms_title">Terms</strong>
          <p data-i18n="hub_terms_desc">ข้อกำหนดการใช้งานแพลตฟอร์ม SkylineBOT</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/privacy-policy" data-page-search="privacy policy privacy-policy ความเป็นส่วนตัว">
          <span class="index-link-icon"><i class="fa-solid fa-user-shield" aria-hidden="true"></i></span>
          <strong data-i18n="hub_privacy_title">Privacy Policy</strong>
          <p data-i18n="hub_privacy_desc">นโยบายความเป็นส่วนตัวและการคุ้มครองข้อมูล</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener" data-page-search="contact ติดต่อ">
          <span class="index-link-icon"><i class="fa-solid fa-headset" aria-hidden="true"></i></span>
          <strong data-i18n="hub_contact_title">Contact</strong>
          <p data-i18n="hub_contact_desc">ติดต่อทีมงานซัพพอร์ตผ่านเว็บได้โดยตรง</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/report" data-page-search="report bug bounty รายงานปัญหา">
          <span class="index-link-icon"><i class="fa-solid fa-bug" aria-hidden="true"></i></span>
          <strong data-i18n="hub_report_title">Report</strong>
          <p data-i18n="hub_report_desc">แจ้งบั๊กหรือปัญหาที่พบเพื่อให้ทีมตรวจสอบ</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/status?view=bot" data-page-search="status bot status สถานะบอท">
          <span class="index-link-icon"><i class="fa-solid fa-heart-pulse" aria-hidden="true"></i></span>
          <strong data-i18n="hub_bot_status_title">Bot Status</strong>
          <p data-i18n="hub_bot_status_desc">ตรวจสอบสถานะบอทและบริการหลักแบบเรียลไทม์</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card external" href="{uptime_public_url}" target="_blank" rel="noopener" data-page-search="uptime uptime-status service status status.skylinebot.xyz">
          <span class="index-link-icon"><i class="fa-solid fa-signal" aria-hidden="true"></i></span>
          <strong data-i18n="hub_uptime_title">Uptime Status</strong>
          <p data-i18n="hub_uptime_desc">หน้า Uptime ภายนอกสำหรับติดตาม SLA และเหตุขัดข้อง</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/redeem" data-page-search="redeem code โค้ด">
          <span class="index-link-icon"><i class="fa-solid fa-gift" aria-hidden="true"></i></span>
          <strong data-i18n="hub_redeem_title">Redeem</strong>
          <p data-i18n="hub_redeem_desc">แลกรับโค้ดสิทธิพิเศษและจัดการสิทธิ์การใช้งาน</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/premium" data-page-search="premium แพ็กเกจ พรีเมียม">
          <span class="index-link-icon"><i class="fa-solid fa-crown" aria-hidden="true"></i></span>
          <strong data-i18n="hub_premium_title">Premium</strong>
          <p data-i18n="hub_premium_desc">ดูแพ็กเกจ ราคา และความสามารถที่ปลดล็อกได้</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
        <a class="index-link-card" href="/personalizer" data-page-search="personalizer ปรับแต่ง">
          <span class="index-link-icon"><i class="fa-solid fa-sliders" aria-hidden="true"></i></span>
          <strong data-i18n="hub_personalizer_title">Personalizer</strong>
          <p data-i18n="hub_personalizer_desc">ปรับภาพลักษณ์และประสบการณ์ของบอทให้เข้าชุมชน</p>
          <span class="index-link-action" data-i18n="hub_open_page">เปิดหน้า</span>
        </a>
      </div>
    </section>



    <section class="panel" id="plugins-catalog">
      <div class="plugins-catalog-head">
        <h2 data-i18n="plugins_title" data-icon-key="index_plugins">Plugins</h2>
        <p class="muted" data-i18n="plugins_desc">Discover moderation, utility, social alerts, and engagement tools in one place.</p>
        <div class="plugins-catalog-pill-row">
          <span class="plugins-catalog-pill"><i class="fa-solid fa-bolt" aria-hidden="true"></i> Quick Setup</span>
          <span class="plugins-catalog-pill"><i class="fa-solid fa-layer-group" aria-hidden="true"></i> Modular Features</span>
          <span class="plugins-catalog-pill"><i class="fa-solid fa-rocket" aria-hidden="true"></i> Ready to Deploy</span>
        </div>
      </div>
      <div class="catalog-grid">
        <article class="catalog-item" id="plugin-moderation">
          <div class="catalog-head">
            <div class="catalog-head-main">
              <span class="catalog-icon"><i class="fa-solid fa-shield-halved" aria-hidden="true"></i></span>
              <a class="catalog-title-link" href="/plugins/moderation"><strong>Moderation & Safety</strong></a>
            </div>
            <span class="catalog-tag">Core</span>
          </div>
          <p>AutoMod, reaction roles, and staff command workflows for high-quality server safety.</p>
          <a class="catalog-media-link" href="/plugins/moderation"><img src="{_escape(style_urls.PLUGIN_CATALOG_MODERATION_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_SECURITY_IMAGE)}';" alt="SkylineBOT moderation"></a>
          <div class="catalog-foot">
            <span class="catalog-meta">Moderation</span>
            <a class="catalog-open" href="/plugins/moderation">Open <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
          </div>
        </article>
        <article class="catalog-item" id="plugin-utilities">
          <div class="catalog-head">
            <div class="catalog-head-main">
              <span class="catalog-icon"><i class="fa-solid fa-screwdriver-wrench" aria-hidden="true"></i></span>
              <a class="catalog-title-link" href="/plugins/utilities"><strong>Utilities Toolkit</strong></a>
            </div>
            <span class="catalog-tag">Toolkit</span>
          </div>
          <p>Embeds, ticket flow, reminders, OCR, and everyday operations tools for moderators.</p>
          <a class="catalog-media-link" href="/plugins/utilities"><img src="{_escape(style_urls.PLUGIN_CATALOG_UTILITIES_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_TICKET_IMAGE)}';" alt="SkylineBOT utilities"></a>
          <div class="catalog-foot">
            <span class="catalog-meta">Utilities</span>
            <a class="catalog-open" href="/plugins/utilities">Open <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
          </div>
        </article>
        <article class="catalog-item" id="plugin-social">
          <div class="catalog-head">
            <div class="catalog-head-main">
              <span class="catalog-icon"><i class="fa-solid fa-bullhorn" aria-hidden="true"></i></span>
              <a class="catalog-title-link" href="/plugins/social-alerts"><strong>Social Alerts</strong></a>
            </div>
            <span class="catalog-tag">Live Feed</span>
          </div>
          <p>Broadcast creator and platform updates from YouTube, Twitch, TikTok, GitHub, and Facebook.</p>
          <a class="catalog-media-link" href="/plugins/social-alerts"><img src="{_escape(style_urls.PLUGIN_CATALOG_SOCIAL_ALERTS_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_GIVEAWAY_IMAGE)}';" alt="SkylineBOT social alerts"></a>
          <div class="catalog-foot">
            <span class="catalog-meta">Social</span>
            <a class="catalog-open" href="/plugins/social-alerts">Open <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
          </div>
        </article>
        <article class="catalog-item" id="plugin-fun">
          <div class="catalog-head">
            <div class="catalog-head-main">
              <span class="catalog-icon"><i class="fa-solid fa-gamepad" aria-hidden="true"></i></span>
              <a class="catalog-title-link" href="/plugins/games-fun"><strong>Games & Fun</strong></a>
            </div>
            <span class="catalog-tag">Engagement</span>
          </div>
          <p>Mini-games, rewards, levels, and activity loops designed for community retention.</p>
          <a class="catalog-media-link" href="/plugins/games-fun"><img src="{_escape(style_urls.PLUGIN_CATALOG_FUN_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_HERO_IMAGE)}';" alt="SkylineBOT games and fun"></a>
          <div class="catalog-foot">
            <span class="catalog-meta">Fun</span>
            <a class="catalog-open" href="/plugins/games-fun">Open <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
          </div>
        </article>
        <article class="catalog-item" id="plugin-personalizer">
          <div class="catalog-head">
            <div class="catalog-head-main">
              <span class="catalog-icon"><i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i></span>
              <a class="catalog-title-link" href="/personalizer"><strong>Bot Personalizer</strong></a>
            </div>
            <span class="catalog-tag">Style</span>
          </div>
          <p>Customize appearance and personality so your bot matches each server identity.</p>
          <a class="catalog-media-link" href="/personalizer"><img src="{_escape(style_urls.PLUGIN_CATALOG_PERSONALIZE_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_HERO_IMAGE)}';" alt="SkylineBOT personalizer"></a>
          <div class="catalog-foot">
            <span class="catalog-meta">Personalize</span>
            <a class="catalog-open" href="/personalizer">Open <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
          </div>
        </article>
        <article class="catalog-item" id="plugin-premium">
          <div class="catalog-head">
            <div class="catalog-head-main">
              <span class="catalog-icon"><i class="fa-solid fa-crown" aria-hidden="true"></i></span>
              <a class="catalog-title-link" href="/premium"><strong>Premium Subscription</strong></a>
            </div>
            <span class="catalog-tag">Upgrade</span>
          </div>
          <p>Unlock premium capacity and advanced control layers across all SkylineBOT plugin modules.</p>
          <a class="catalog-media-link" href="/premium"><img src="{_escape(style_urls.PLUGIN_CATALOG_PREMIUM_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_HERO_IMAGE)}';" alt="SkylineBOT premium"></a>
          <div class="catalog-foot">
            <span class="catalog-meta">Premium</span>
            <a class="catalog-open" href="/premium">Open <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
          </div>
        </article>
      </div>
    </section>

    <section class="panel" id="resources-hub">
      <h2 data-i18n="resources_title" data-icon-key="index_resources">แหล่งข้อมูล</h2>
      <p class="muted" data-i18n="resources_desc">คู่มือและช่องทางช่วยเหลือสำหรับการใช้งาน SkylineBOT อย่างครบถ้วน</p>
      <div class="resources-panel">
        <div class="resources-col">
          <h3 data-i18n="tutorials_title_plain" data-icon-key="index_resources_tutorials">คู่มือ</h3>
          <a class="resources-link" href="/docs"><i></i><span data-i18n="tutorials_title_plain">คู่มือ</span></a>
          <p data-i18n="tutorials_desc">เรียนรู้การใช้งาน {bot_name} บน Discord อย่างเป็นขั้นตอน</p>
          <a class="resources-link" href="/docs"><i></i><span data-i18n="support_portal_title_plain">พอร์ทัลช่วยเหลือ</span></a>
          <p data-i18n="support_portal_desc">รวมคลังความรู้และเครื่องมือช่วยเหลือ</p>
          <a class="resources-link" href="{_escape(style_urls.SUPPORT_SERVER)}" target="_blank" rel="noopener"><i></i><span data-i18n="discord_server_title_plain">เซิร์ฟเวอร์ซัพพอร์ต</span></a>
          <p data-i18n="discord_server_desc">เข้าร่วมเซิร์ฟเวอร์ Discord เพื่อรับความช่วยเหลือ</p>
          <a class="resources-link" href="{_escape(_support_status_public_url())}" target="_blank" rel="noopener"><i></i><span>SkyLineBOT Service Status</span></a>
          <p>ตรวจสอบสถานะบริการหลักของ SkylineBOT แบบเรียลไทม์</p>
          <a class="resources-link" href="/status?view=bot"><i></i><span>SkyLineBOT Status</span></a>
          <p>ดูสถานะบอทและการเชื่อมต่อ Discord ล่าสุด</p>
        </div>
        <div class="resources-col">
          <h3 data-i18n="company_title_plain" data-icon-key="index_resources_company">เกี่ยวกับทีม</h3>
          <a class="resources-link" href="/careers"><i></i><span data-i18n="careers_title_plain">ร่วมงานกับเรา</span></a>
          <p data-i18n="careers_desc">ร่วมสร้าง {bot_name} สำหรับชุมชน Discord</p>
          <a class="resources-link" href="/terms"><i></i><span data-i18n="footer_terms">ข้อกำหนดการใช้งาน</span></a>
          <p>อ่านข้อกำหนดการใช้งานสำหรับ SkylineBOT และบริการที่เกี่ยวข้อง</p>
          <a class="resources-link" href="/privacy"><i></i><span data-i18n="footer_privacy">นโยบายความเป็นส่วนตัว</span></a>
          <p>ดูแนวทางการเก็บและใช้งานข้อมูลส่วนบุคคล</p>
          <a class="resources-link" href="/report"><i></i><span data-i18n="bug_bounty_title_plain">Bug Bounty</span></a>
          <p data-i18n="bug_bounty_desc">แจ้งช่องโหว่ด้านความปลอดภัยตามนโยบายที่กำหนด</p>
          <a class="resources-link" href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener"><i></i><span data-i18n="contact_us_title_plain">ติดต่อเรา</span></a>
          <p data-i18n="contact_us_desc">ส่งคำถามหรือข้อเสนอแนะถึงทีมงานได้ทุกเมื่อ</p>
          <a class="resources-link" href="/report"><i></i><span>รายงานปัญหา</span></a>
          <p>ส่งรายงานปัญหาผ่านฟอร์มเว็บไซต์พร้อมรหัสยืนยันกันบอท</p>
        </div>
        <div class="resources-col resources-spotlight">
          <h3 data-i18n="spotlight_title" data-icon-key="index_resources_spotlight">ไฮไลต์</h3>
          <a href="/docs" data-i18n="all_tutorials">ดูบทช่วยสอนทั้งหมด</a>
        </div>
      </div>
    </section>

    <section class="panel community-showcase" id="community-widget">
      <div class="community-showcase-copy">
        <h2 data-icon-key="index_resources_spotlight" data-i18n="community_title">Discord Community</h2>
        <p class="muted" data-i18n="community_desc">Join our support server directly from this page.</p>
        <p class="community-showcase-lead" data-i18n="community_lead">พูดคุยกับทีมงานและสมาชิกคอมมูนิตี้แบบเรียลไทม์ พร้อมรับข่าวอัปเดต ฟีเจอร์ใหม่ และคำแนะนำการใช้งาน</p>
        <div class="community-showcase-points">
          <span class="community-point"><i class="fa-solid fa-life-ring" aria-hidden="true"></i> <span data-i18n="community_point_1">ห้องช่วยเหลือสำหรับการตั้งค่าบอทและระบบต่าง ๆ</span></span>
          <span class="community-point"><i class="fa-solid fa-bullhorn" aria-hidden="true"></i> <span data-i18n="community_point_2">ข่าวประกาศและกิจกรรมจากทีม SkylineBOT</span></span>
          <span class="community-point"><i class="fa-solid fa-shield-heart" aria-hidden="true"></i> <span data-i18n="community_point_3">ช่องทางรายงานปัญหาและติดตามสถานะการแก้ไข</span></span>
        </div>
        <div class="auth-actions community-showcase-actions">
          <a class="primary-btn" href="{_escape(style_urls.SUPPORT_SERVER)}" target="_blank" rel="noopener" data-i18n="community_join_btn">Join Discord</a>
          <a class="ghost-btn" href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener" data-i18n="community_contact_btn">Contact Team</a>
          <a class="ghost-btn" href="/report" data-i18n="community_report_btn">Report Issue</a>
        </div>
      </div>
      <div class="community-showcase-grid">
        <div class="community-widget-shell">
          <iframe
            src="https://discord.com/widget?id=1414526528959811616&theme=dark"
            width="380"
            height="520"
            title="SkylineBOT Discord Server Widget"
            allowtransparency="true"
            frameborder="0"
            sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts"
            style="width:min(100%,380px);max-width:100%;border:0;border-radius:14px;overflow:hidden;">
          </iframe>
          <p class="muted community-widget-note" data-i18n="community_note">กด Join Discord เพื่อเข้าร่วมเซิร์ฟเวอร์ซัพพอร์ตอย่างเป็นทางการ</p>
        </div>
        <a class="community-media-shell" href="/docs">
          <img src="{_escape(style_urls.INDEX_NAV_RESOURCES_SPOTLIGHT_IMAGE)}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_GIVEAWAY_IMAGE)}';" alt="SkylineBOT Community Guide">
          <span class="community-media-overlay">
            <strong data-i18n="community_overlay_title">เริ่มใช้งานได้ไวขึ้น</strong>
            <span data-i18n="community_overlay_desc">รวมคู่มือ, แนวทางตั้งค่า และทริกสำหรับแอดมินเซิร์ฟเวอร์</span>
          </span>
        </a>
      </div>
    </section>

    <section class="panel">
      <h2 data-i18n="plans_pricing" data-icon-key="index_pricing_cards">ราคาแพ็กเกจ</h2>
      <p class="muted" data-i18n="plans_pricing_desc">เลือกแพ็กเกจที่เหมาะกับขนาดชุมชนและรูปแบบการใช้งานของคุณ</p>
      <div class="landing-grid price-grid" style="margin-top:12px;">
        {pricing_cards}
      </div>
    </section>

    <section class="cta-strip mee6-style">
      <h2 data-i18n="cta_title" data-icon-key="index_cta">พร้อมเริ่มจัดการ Discord ของคุณแล้วหรือยัง</h2>
      <div class="auth-actions" style="margin-top:0;">
        {action}
      </div>
    </section>

    <section class="site-footer mee6-style" data-icon-key="index_footer">
      <div class="footer-shell">
        <div class="footer-brand">
          <img class="footer-brand-badge" src="{bot_avatar_url}" onerror="this.onerror=null;this.src='{_escape(FALLBACK_HERO_IMAGE)}';" alt="{bot_name}">
          <strong>{bot_name}</strong>
          <p data-i18n="footer_brand_desc">บอท Discord สำหรับดูแลชุมชน จัดการระบบ และเพิ่มประสบการณ์การใช้งาน</p>
        </div>
        <div class="footer-col">
          <a class="footer-col-heading" href="#plugins-catalog" data-i18n="footer_plugins" data-icon-key="index_footer_plugins">ปลั๊กอิน</a>
          <a href="/plugins/moderation" data-i18n="footer_server_management">จัดการเซิร์ฟเวอร์</a>
          <a href="/plugins/utilities" data-i18n="footer_utilities">เครื่องมือเสริม</a>
          <a href="/plugins/social-alerts" data-i18n="footer_social_alerts">โซเชียลแจ้งเตือน</a>
          <a href="/plugins/games-fun" data-i18n="footer_engagement_fun">เกมและความสนุก</a>
        </div>
        <div class="footer-col">
          <a class="footer-col-heading" href="#resources-hub" data-i18n="footer_brand_title" data-icon-key="index_footer_brand">{bot_name}</a>
          <a href="/premium" data-i18n="premium_btn">Premium</a>
          <a href="/personalizer" data-i18n="footer_bot_personalizer">Bot Personalizer</a>
          <a href="{_escape(style_urls.SUPPORT_SERVER)}" target="_blank" rel="noopener" data-i18n="footer_support_server">เซิร์ฟเวอร์ซัพพอร์ต</a>
          <a href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener" data-i18n="footer_support_contact">ติดต่อซัพพอร์ต</a>
          <a href="{_escape(_support_status_public_url())}" target="_blank" rel="noopener">SkyLineBOT Service Status</a>
          <a href="/status?view=bot">SkyLineBOT Status</a>
          <a href="/report">รายงานปัญหา</a>
        </div>
        <div class="footer-col">
          <a class="footer-col-heading" href="#resources-hub" data-i18n="company_title_plain" data-icon-key="index_footer_company">เกี่ยวกับเรา</a>
          <a href="/careers" data-i18n="careers_title_plain">ร่วมงานกับเรา</a>
          <a href="/terms" data-i18n="footer_terms">ข้อกำหนดการใช้งาน</a>
          <a href="/privacy" data-i18n="footer_privacy">นโยบายความเป็นส่วนตัว</a>
          <a href="/report" data-i18n="bug_bounty_title_plain">Bug Bounty</a>
          <a href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener" data-i18n="contact_us_title_plain">ติดต่อเรา</a>
        </div>
      </div>
    </section>
    """
    resolved_seo_path = str(seo_path or "").strip() or "/dashboard"
    resolved_seo_image_path = str(seo_image_path or "").strip() or str(
        style_urls.INDEX_NAV_RESOURCES_SPOTLIGHT_IMAGE
        or style_urls.DEFAULT_MUSIC_BANNER
        or "/dashboard/static/image_web_bot/giveaways_dashboard.webp"
    ).strip()
    page_title = (
        "SkylineBOT | Discord Bot Dashboard"
        if resolved_seo_path == "/"
        else "เข้าสู่ระบบ SkylineBOT"
    )
    return _render_layout(
        title=page_title,
        body=body,
        session=session,
        notice=notice,
        seo_path=resolved_seo_path,
        seo_image_path=resolved_seo_image_path,
    )


def _render_public_doc_page(
    *,
    title: str,
    heading: str,
    description: str,
    bullets: list[str],
    session: dict[str, Any] | None = None,
) -> str:
    items_html = "".join(f"<li>{_escape(item)}</li>" for item in bullets)
    body = _render_dashboard_f_template("public_doc_page.html", locals())
    return _render_layout(title=title, body=body, session=session)


def _render_feature_landing_page(
    *,
    title: str,
    heading: str,
    description: str,
    highlights: list[str],
    cta_href: str = "/dashboard",
    cta_label: str = "Open Dashboard",
    theme_key: str = "",
    hero_image_url: str = "",
    hero_image_fallback_url: str = FALLBACK_HERO_IMAGE,
    hero_badges: list[str] | None = None,
    hero_metrics: list[tuple[str, str]] | None = None,
    overview_heading: str = "Overview",
    overview_description: str = "",
    extra_sections_html: str = "",
    session: dict[str, Any] | None = None,
) -> str:
    safe_highlights = [
        str(item or "").strip()
        for item in (highlights or [])
        if str(item or "").strip()
    ]
    cards_html = "".join(
        f'<article class="price-card"><p class="muted">{_escape(item)}</p></article>'
        for item in safe_highlights
    )

    hero_image_url = (
        str(hero_image_url or "").strip()
        or str(style_urls.DEFAULT_MUSIC_BANNER or "").strip()
        or FALLBACK_HERO_IMAGE
    )
    hero_image_fallback_url = str(hero_image_fallback_url or "").strip() or FALLBACK_HERO_IMAGE

    safe_badges = [
        str(item or "").strip()
        for item in (hero_badges or [])
        if str(item or "").strip()
    ]
    hero_badges_html = "".join(
        f'<span class="feature-landing-badge">{_escape(item)}</span>'
        for item in safe_badges
    )

    metric_cards: list[tuple[str, str]] = []
    for metric in (hero_metrics or []):
        value = ""
        label = ""
        if isinstance(metric, (list, tuple)) and len(metric) >= 2:
            value = str(metric[0] or "").strip()
            label = str(metric[1] or "").strip()
        if value and label:
            metric_cards.append((value, label))
    hero_metrics_html = "".join(
        f'<article class="feature-metric-card"><strong>{_escape(value)}</strong><span>{_escape(label)}</span></article>'
        for value, label in metric_cards
    )

    overview_heading = str(overview_heading or "Overview").strip() or "Overview"
    overview_description_text = str(overview_description or "").strip()
    overview_description_html = (
        f'<p class="muted feature-overview-description">{_escape(overview_description_text)}</p>'
        if overview_description_text
        else ""
    )
    extra_sections_html = str(extra_sections_html or "")
    safe_theme_key = "".join(
        ch for ch in str(theme_key or "").strip().lower()
        if ch.isalnum() or ch == "-"
    ).strip("-")
    feature_theme_class = f"feature-theme-{safe_theme_key}" if safe_theme_key else ""
    is_plugin_theme = safe_theme_key.startswith("plugins-")

    body = _render_dashboard_f_template("feature_landing_page.html", locals())
    return _render_layout(title=title, body=body, session=session)


def _render_commands_help_page(*, session: dict[str, Any] | None = None) -> str:
    def _normalize_command_name(raw: Any) -> str:
        name = str(raw or "").strip().lower()
        if name.startswith("/"):
            name = name[1:].strip()
        return " ".join(name.split())

    def _is_name_in_disabled_set(command_name: str, disabled_names: set[str]) -> bool:
        normalized = _normalize_command_name(command_name)
        if not normalized:
            return False
        if normalized in disabled_names:
            return True

        parts = normalized.split()
        chain = {" ".join(parts[:index]) for index in range(1, len(parts) + 1)}
        if chain.intersection(disabled_names):
            return True

        if len(parts) == 1:
            leaf = parts[0]
            suffix = f" {leaf}"
            if any(" " in item and item.endswith(suffix) for item in disabled_names):
                return True
        return False

    def _normalize_slash_state_name(raw: Any) -> str:
        normalized = _normalize_command_name(raw)
        if not normalized:
            return ""
        if ":" in normalized and not normalized.startswith("/"):
            return ""
        return normalized

    bot = get_bot()
    runtime_settings = _ownerbot_runtime_from_db()
    global_commands_enabled = bool(runtime_settings.get("global_command_response_enabled", True))
    disabled_names = {
        _normalize_command_name(name)
        for name in (runtime_settings.get("global_disabled_commands") or [])
        if _normalize_command_name(name)
    }

    slash_filtered_names: set[str] = set()
    slash_overflow_names: set[str] = set()
    slash_mode = "unknown"
    if bot is not None:
        slash_mode = str(getattr(bot, "_slash_command_mode", "unknown") or "unknown").strip().lower() or "unknown"
        for item in list(getattr(bot, "_slash_filtered_commands", []) or []):
            normalized = _normalize_slash_state_name(item)
            if normalized:
                slash_filtered_names.add(normalized)
                slash_filtered_names.add(normalized.split(" ", 1)[0])
        for item in list(getattr(bot, "_slash_overflow_commands", []) or []):
            normalized = _normalize_slash_state_name(item)
            if normalized:
                slash_overflow_names.add(normalized)
                slash_overflow_names.add(normalized.split(" ", 1)[0])

    session_data = _session_mapping(session)
    requested_language = str(session_data.get("language") or "th").strip().lower()
    catalog_language = requested_language if requested_language in {"th", "en"} else "th"
    is_en = catalog_language == "en"
    ui = {
        "no_description": "No description provided." if is_en else "ไม่มีคำอธิบาย",
        "general": "General" if is_en else "ทั่วไป",
        "mode_both": "Slash + Prefix" if is_en else "สแลช + พรีฟิกซ์",
        "mode_slash_only": "Slash only" if is_en else "เฉพาะสแลช",
        "mode_prefix_only": "Prefix only" if is_en else "เฉพาะพรีฟิกซ์",
        "mode_unavailable": "Unavailable" if is_en else "ไม่พร้อมใช้งาน",
        "status_open": "Open" if is_en else "เปิดใช้งาน",
        "status_closed": "Closed" if is_en else "ปิดใช้งาน",
        "status_closed_global": "Closed (global command response disabled)" if is_en else "ปิดใช้งาน (ปิดการตอบคำสั่งทั้งระบบ)",
        "status_closed_runtime": "Closed (disabled by runtime policy)" if is_en else "ปิดใช้งาน (นโยบายรันไทม์ปิดไว้)",
        "status_closed_quota": "Closed (slash quota overflow)" if is_en else "ปิดใช้งาน (เกินโควตาสแลช)",
        "status_closed_filtered": "Closed (slash filtered by current mode)" if is_en else "ปิดใช้งาน (ถูกกรองตามโหมดปัจจุบัน)",
        "plan_free": "Free" if is_en else "ฟรี",
        "plan_premium": "Premium" if is_en else "พรีเมียม",
        "state_on": "On" if is_en else "เปิด",
        "state_off": "Off" if is_en else "ปิด",
        "copy_command_title": "Copy command" if is_en else "คัดลอกคำสั่ง",
        "copy_command_aria": "Copy command" if is_en else "คัดลอกคำสั่ง",
        "toggle_favorite_title": "Toggle favorite" if is_en else "ปักหมุดคำสั่งโปรด",
        "toggle_favorite_aria": "Toggle favorite" if is_en else "ปักหมุดคำสั่งโปรด",
        "usage_title": "Usage" if is_en else "วิธีใช้",
        "examples_title": "Examples" if is_en else "ตัวอย่าง",
        "support_title": "Support" if is_en else "ข้อมูลเสริม",
        "category_label": "Category" if is_en else "หมวด",
        "slash_label": "Slash" if is_en else "สแลช",
        "prefix_label": "Prefix" if is_en else "พรีฟิกซ์",
        "all_button": "All" if is_en else "ทั้งหมด",
        "unknown": "Unknown" if is_en else "ไม่ทราบ",
        "connected": "Connected" if is_en else "เชื่อมต่อแล้ว",
        "offline": "Offline" if is_en else "ออฟไลน์",
        "no_commands": "No commands available." if is_en else "ยังไม่มีคำสั่งที่พร้อมใช้งาน",
    }
    catalog = sorted(
        _command_catalog(language=catalog_language),
        key=lambda item: str(item.get("name") or "").lower(),
    )

    command_cards: list[str] = []
    categories: set[str] = set()
    free_count = 0
    premium_count = 0
    open_count = 0
    closed_count = 0
    slash_count = 0
    prefix_count = 0
    both_count = 0

    for command in catalog:
        command_name = _normalize_command_name(command.get("name"))
        if not command_name:
            continue

        brief = str(command.get("brief") or ui["no_description"]).strip()
        category = str(command.get("category") or ui["general"]).strip() or ui["general"]
        categories.add(category)

        slash_available = bool(command.get("slash_available"))
        prefix_available = bool(command.get("prefix_available"))
        if slash_available:
            slash_count += 1
        if prefix_available:
            prefix_count += 1
        if slash_available and prefix_available:
            both_count += 1

        required_tier = _required_plan_for_command(command_name)
        is_premium = required_tier != "free"
        if is_premium:
            premium_count += 1
        else:
            free_count += 1

        disabled_by_runtime = _is_name_in_disabled_set(command_name, disabled_names)
        active_modes = int(slash_available) + int(prefix_available)
        is_open = global_commands_enabled and (not disabled_by_runtime) and active_modes > 0
        if is_open:
            open_count += 1
        else:
            closed_count += 1

        if slash_available and prefix_available:
            mode_code = "both"
            mode_text = ui["mode_both"]
        elif slash_available:
            mode_code = "slash"
            mode_text = ui["mode_slash_only"]
        elif prefix_available:
            mode_code = "prefix"
            mode_text = ui["mode_prefix_only"]
        else:
            mode_code = "none"
            mode_text = ui["mode_unavailable"]

        if is_open:
            status_code = "open"
            status_text = ui["status_open"]
        else:
            status_code = "closed"
            if not global_commands_enabled:
                status_text = ui["status_closed_global"]
            elif disabled_by_runtime:
                status_text = ui["status_closed_runtime"]
            elif slash_available is False and prefix_available is False:
                if command_name in slash_overflow_names or command_name.split(" ", 1)[0] in slash_overflow_names:
                    status_text = ui["status_closed_quota"]
                elif command_name in slash_filtered_names or command_name.split(" ", 1)[0] in slash_filtered_names:
                    status_text = ui["status_closed_filtered"]
                else:
                    status_text = ui["status_closed"]
            else:
                status_text = ui["status_closed"]

        usage_lines = [str(line).strip() for line in list(command.get("usage_lines") or []) if str(line).strip()]
        if not usage_lines:
            if slash_available:
                usage_lines.append(f"/{command_name}")
            if prefix_available:
                usage_lines.append(f"!{command_name}")
            if not usage_lines:
                usage_lines.append(command_name)

        example_lines = [str(line).strip() for line in list(command.get("example_lines") or []) if str(line).strip()]
        if not example_lines:
            example_lines = list(usage_lines)
        primary_copy_command = str(usage_lines[0] or f"/{command_name}").strip()

        usage_html = "".join(f"<li><code>{_escape(line)}</code></li>" for line in usage_lines[:6])
        example_html = "".join(f"<li><code>{_escape(line)}</code></li>" for line in example_lines[:6])

        required_plan_label = (
            ui["plan_free"]
            if required_tier == "free"
            else f"{ui['plan_premium']} ({required_tier.capitalize()}+)"
        )
        plan_code = "premium" if is_premium else "free"
        slash_state_label = ui["state_on"] if slash_available else ui["state_off"]
        prefix_state_label = ui["state_on"] if prefix_available else ui["state_off"]

        search_blob = " ".join(
            [
                command_name,
                brief,
                category,
                mode_text,
                status_text,
                required_plan_label,
                " ".join(usage_lines),
                " ".join(example_lines),
            ]
        ).lower()

        command_cards.append(
            f"""
            <details class="cmdhelp-card {status_code}" data-command-card data-category="{_escape(category)}" data-plan="{plan_code}" data-status="{status_code}" data-mode="{mode_code}" data-search="{_escape(search_blob)}" data-primary-usage="{_escape(primary_copy_command)}">
              <summary class="cmdhelp-card-head">
                <div class="cmdhelp-title-wrap">
                  <span class="cmdhelp-title">/{_escape(command_name)}</span>
                  <span class="cmdhelp-brief">{_escape(brief)}</span>
                </div>
                <div class="cmdhelp-badges">
                  <button type="button" class="cmdhelp-copy-btn" data-copy-command="{_escape(primary_copy_command)}" title="{_escape(ui['copy_command_title'])}" aria-label="{_escape(ui['copy_command_aria'])}">Copy</button>
                  <button type="button" class="cmdhelp-fav-btn" data-fav-toggle data-command-name="{_escape(command_name)}" title="{_escape(ui['toggle_favorite_title'])}" aria-label="{_escape(ui['toggle_favorite_aria'])}" aria-pressed="false">&#10084;</button>
                  <span class="cmdhelp-badge mode {mode_code}">{_escape(mode_text)}</span>
                  <span class="cmdhelp-badge plan {plan_code}">{_escape(required_plan_label)}</span>
                  <span class="cmdhelp-badge status {status_code}">{_escape(status_text)}</span>
                </div>
              </summary>
              <div class="cmdhelp-card-body">
                <div class="cmdhelp-meta-grid">
                  <article class="cmdhelp-meta-box">
                    <h4>{_escape(ui["usage_title"])}</h4>
                    <ul>{usage_html or "<li>-</li>"}</ul>
                  </article>
                  <article class="cmdhelp-meta-box">
                    <h4>{_escape(ui["examples_title"])}</h4>
                    <ul>{example_html or "<li>-</li>"}</ul>
                  </article>
                  <article class="cmdhelp-meta-box">
                    <h4>{_escape(ui["support_title"])}</h4>
                    <ul>
                      <li><strong>{_escape(ui["category_label"])}:</strong> {_escape(category)}</li>
                      <li><strong>{_escape(ui["slash_label"])}:</strong> {_escape(slash_state_label)}</li>
                      <li><strong>{_escape(ui["prefix_label"])}:</strong> {_escape(prefix_state_label)}</li>
                    </ul>
                  </article>
                </div>
              </div>
            </details>
            """
        )

    category_buttons = [
        f'<button type="button" class="cmdhelp-chip active" data-cat-chip="">{_escape(ui["all_button"])}</button>'
    ]
    for category in sorted(categories, key=lambda item: item.lower()):
        category_buttons.append(
            f'<button type="button" class="cmdhelp-chip" data-cat-chip="{_escape(category)}">{_escape(category)}</button>'
        )

    total_commands = len(command_cards)
    slash_mode_label = slash_mode.capitalize() if slash_mode != "unknown" else ui["unknown"]
    bot_status_label = ui["connected"] if bot is not None else ui["offline"]
    cmdhelp_no_commands_markup = (
        f'<div class="notice" data-i18n="cmdhelp_no_commands">{_escape(ui["no_commands"])}</div>'
    )
    public_base_url = str(getattr(BOT_CONFIG, "DASHBOARD_BASE_URL", "") or "").strip().rstrip("/")
    commands_source_url = "/dashboard"
    if public_base_url:
        commands_source_url = f"{public_base_url}/dashboard"

    body = _render_dashboard_f_template("commands_help_page.html", locals())
    return _render_layout(title="คู่มือคำสั่ง SkylineBOT", body=body, session=session)


def _render_report_page(
    *,
    notice: str | None = None,
    session: dict[str, Any] | None = None,
    form_prefill: dict[str, str] | None = None,
) -> str:
    session_data = _session_mapping(session)
    session_user = dict(session_data.get("user") or {})
    requested_language = str(session_data.get("language") or "th").strip().lower()
    report_lang = requested_language if requested_language in {"th", "en"} else "th"
    is_en = report_lang == "en"
    ui = {
        "guest_name": "Guest" if is_en else "ผู้เยี่ยมชม",
        "contact_placeholder_guest": "Discord tag / email / contact link" if is_en else "แท็ก Discord / อีเมล / ลิงก์ติดต่อ",
        "contact_placeholder_auth": "Contact (auto-filled from login, but you can edit)" if is_en else "ช่องทางติดต่อ (ระบบกรอกจากบัญชีให้แล้ว แต่แก้ไขได้)",
        "related_server_none": "Not related to a specific server" if is_en else "ไม่เกี่ยวข้องกับเซิร์ฟเวอร์เฉพาะ",
        "related_server_label": "Related server (optional)" if is_en else "เซิร์ฟเวอร์ที่เกี่ยวข้อง (ไม่บังคับ)",
        "related_server_help": "If this issue is tied to one server, choose it to help the team investigate faster." if is_en else "ถ้าปัญหานี้เกี่ยวข้องกับเซิร์ฟเวอร์ใดเซิร์ฟเวอร์หนึ่ง ให้เลือกเพื่อช่วยทีมตรวจสอบได้เร็วขึ้น",
        "image_help": "Optional: attach screenshot/image (PNG, JPG, WEBP, GIF; max 8MB)." if is_en else "แนบรูปภาพได้ (PNG, JPG, WEBP, GIF; สูงสุด 8MB)",
        "attached_prefix": "Attached image:" if is_en else "ไฟล์รูปที่แนบ:",
        "logged_user_label": "Logged in user" if is_en else "ผู้ใช้ที่เข้าสู่ระบบ",
        "logged_user_note": "You are logged in. Anti-bot confirm is disabled for this report." if is_en else "คุณเข้าสู่ระบบแล้ว ระบบยืนยันกันบอทถูกปิดสำหรับรายงานนี้",
        "guest_note": "Guest mode: please confirm anti-bot code before submitting." if is_en else "โหมดผู้เยี่ยมชม: โปรดยืนยันรหัสกันบอทก่อนส่งรายงาน",
        "challenge_label": "Confirm you are not a bot: type" if is_en else "ยืนยันว่าคุณไม่ใช่บอท: พิมพ์",
        "challenge_placeholder": "Type the challenge code exactly" if is_en else "พิมพ์รหัสยืนยันให้ตรงทั้งหมด",
        "issue_title_placeholder": "Example: /play command issue in some servers" if is_en else "ตัวอย่าง: คำสั่ง /play มีปัญหาในบางเซิร์ฟเวอร์",
        "detail_placeholder": "Describe the issue, reproduction steps, and expected result" if is_en else "อธิบายปัญหา ขั้นตอนการเกิดปัญหา และผลลัพธ์ที่คาดหวัง",
        "page_title": "Report Issue - SkylineBOT" if is_en else "รายงานปัญหา - SkylineBOT",
    }
    reporter_id = str(session_user.get("id") or "").strip()
    reporter_username = str(session_user.get("username") or "").strip()
    reporter_global_name = str(session_user.get("global_name") or "").strip()
    reporter_discriminator = str(session_user.get("discriminator") or "").strip()
    reporter_display_name = reporter_global_name or reporter_username or ui["guest_name"]

    reporter_tag = "-"
    if reporter_username:
        if reporter_discriminator and reporter_discriminator not in {"0", "0000"}:
            reporter_tag = f"{reporter_username}#{reporter_discriminator}"
        else:
            reporter_tag = f"@{reporter_username}"

    reporter_avatar_url = str(session_user.get("avatar_url") or "").strip()
    if not reporter_avatar_url:
        reporter_avatar_url = _discord_default_avatar_url(reporter_id or "0")

    reporter_is_authenticated = bool(reporter_id)
    if reporter_is_authenticated:
        challenge_id = ""
        challenge_text = ""
    else:
        challenge_id, challenge_text = _create_report_challenge()

    prefill = dict(form_prefill or {})
    title_value = _escape(str(prefill.get("title") or ""))
    contact_default = reporter_tag if reporter_is_authenticated and reporter_tag != "-" else ""
    contact_value = _escape(str(prefill.get("contact") or contact_default))
    detail_value = _escape(str(prefill.get("detail") or ""))
    related_guild_id_value = str(prefill.get("related_guild_id") or "").strip()
    image_name_value = _escape(str(prefill.get("image_name") or "").strip())
    challenge_answer_value = _escape(str(prefill.get("challenge_answer") or ""))
    challenge_code_markup = _escape(challenge_text)
    contact_placeholder = (
        ui["contact_placeholder_guest"]
        if not reporter_is_authenticated
        else ui["contact_placeholder_auth"]
    )
    contact_placeholder_key = (
        "report_contact_placeholder_guest"
        if not reporter_is_authenticated
        else "report_contact_placeholder_auth"
    )
    issue_title_placeholder = ui["issue_title_placeholder"]
    detail_placeholder = ui["detail_placeholder"]
    related_guild_field_markup = ""
    if reporter_is_authenticated:
        option_bits: list[str] = [
            f'<option value="" data-i18n="report_related_server_none">{_escape(ui["related_server_none"])}</option>'
        ]
        for row in _manageable_guilds(session or {}):
            guild_id = str(row.get("id") or "").strip()
            guild_name = str(row.get("name") or guild_id).strip() or guild_id
            if not guild_id:
                continue
            selected_attr = " selected" if guild_id == related_guild_id_value else ""
            option_bits.append(
                f'<option value="{_escape(guild_id)}"{selected_attr}>{_escape(guild_name)} ({_escape(guild_id)})</option>'
            )
        if len(option_bits) > 1:
            related_guild_field_markup = f"""
            <label class="switch-row report-field">
              <span data-i18n="report_related_server_label">{_escape(ui["related_server_label"])}</span>
              <select name="related_guild_id">
                {''.join(option_bits)}
              </select>
              <small class="report-field-help" data-i18n="report_related_server_help">{_escape(ui["related_server_help"])}</small>
            </label>
            """
    image_field_help_markup = (
        f'<small class="report-field-help">{_escape(ui["attached_prefix"])} {image_name_value}</small>'
        if image_name_value
        else f'<small class="report-field-help" data-i18n="report_image_help">{_escape(ui["image_help"])}</small>'
    )
    reporter_card_markup = (
        f"""
        <div class="report-login-card">
          <img src="{_escape(reporter_avatar_url)}" alt="{_escape(reporter_display_name)}" class="report-login-avatar">
          <div class="report-login-copy">
            <span class="report-login-label" data-i18n="report_logged_user_label">{_escape(ui["logged_user_label"])}</span>
            <strong class="report-login-name">{_escape(reporter_display_name)}</strong>
            <small class="report-login-meta">{_escape(reporter_tag)} | ID: {_escape(reporter_id)}</small>
          </div>
        </div>
        <div class="report-login-note" data-i18n="report_logged_user_note">{_escape(ui["logged_user_note"])}</div>
        """
        if reporter_is_authenticated
        else f'<div class="report-login-note" data-i18n="report_guest_note">{_escape(ui["guest_note"])}</div>'
    )
    challenge_block_markup = (
        ""
        if reporter_is_authenticated
        else f"""
        <input type="hidden" name="challenge_id" value="{_escape(challenge_id)}">
        <label class="switch-row report-field">
          <span><span data-i18n="report_challenge_label">{_escape(ui["challenge_label"])}</span> <span class="report-challenge-code">{challenge_code_markup}</span></span>
          <input
            type="text"
            name="challenge_answer"
            required
            maxlength="5"
            minlength="4"
            value="{challenge_answer_value}"
            placeholder="{_escape(ui['challenge_placeholder'])}"
            data-i18n-placeholder="report_challenge_placeholder"
            autocomplete="off"
            spellcheck="false"
            autocapitalize="characters"
          >
        </label>
        """
    )
    report_page_style_markup = """
    <style>
      .report-page-shell {
        max-width: 980px;
        margin: 0 auto;
        display: grid;
        gap: 16px;
        border: 1px solid rgba(112, 161, 255, 0.24);
        background:
          radial-gradient(1000px 280px at 100% -20%, rgba(91, 133, 255, 0.2), transparent 62%),
          radial-gradient(640px 260px at -10% 0%, rgba(74, 211, 255, 0.18), transparent 58%),
          linear-gradient(180deg, rgba(14, 26, 56, 0.98), rgba(10, 19, 44, 0.98));
      }
      .report-head {
        display: grid;
        gap: 6px;
        border-bottom: 1px solid rgba(126, 170, 255, 0.18);
        padding-bottom: 10px;
      }
      .report-head h1 {
        margin: 0;
        font-size: clamp(1.2rem, 1.3vw + 1rem, 1.85rem);
      }
      .report-head .muted {
        margin: 0;
      }
      .report-login-card {
        display: flex;
        align-items: center;
        gap: 12px;
        border-radius: 14px;
        padding: 12px 14px;
        border: 1px solid rgba(116, 186, 255, 0.35);
        background: linear-gradient(135deg, rgba(35, 58, 110, 0.45), rgba(16, 31, 70, 0.75));
      }
      .report-login-avatar {
        width: 46px;
        height: 46px;
        border-radius: 50%;
        object-fit: cover;
        border: 2px solid rgba(180, 219, 255, 0.8);
        box-shadow: 0 0 0 4px rgba(91, 133, 255, 0.18);
      }
      .report-login-copy {
        display: grid;
        gap: 2px;
      }
      .report-login-label {
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(199, 222, 255, 0.88);
      }
      .report-login-name {
        font-size: 1rem;
        line-height: 1.15;
      }
      .report-login-meta {
        color: rgba(198, 212, 238, 0.9);
      }
      .report-login-note {
        border-radius: 12px;
        padding: 9px 12px;
        border: 1px dashed rgba(125, 182, 255, 0.42);
        background: rgba(22, 42, 86, 0.55);
        color: rgba(212, 229, 255, 0.95);
        font-size: 0.92rem;
      }
      .report-field {
        display: grid;
        gap: 6px;
        align-items: stretch;
      }
      .report-field > span {
        font-weight: 600;
        color: rgba(226, 236, 255, 0.96);
      }
      .report-field-help {
        font-size: 0.82rem;
        color: rgba(186, 207, 244, 0.9);
      }
      .report-upload-input {
        padding: 8px 10px;
      }
      .report-challenge-code {
        display: inline-block;
        margin-left: 6px;
        padding: 5px 10px;
        border-radius: 10px;
        border: 1px solid rgba(255, 236, 143, 0.95);
        background: linear-gradient(180deg, rgba(255, 209, 73, 0.28), rgba(255, 166, 0, 0.18));
        color: #ffefb0;
        font-size: 1.05rem;
        font-weight: 900;
        letter-spacing: 0.18em;
        line-height: 1;
        text-transform: uppercase;
        text-shadow: 0 0 10px rgba(255, 192, 63, 0.75);
        box-shadow: 0 8px 16px rgba(28, 15, 0, 0.3);
      }
      .report-submit-row {
        justify-content: flex-start;
        margin-top: 4px;
        gap: 8px;
      }
    </style>
    """

    notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""
    body = _render_dashboard_f_template("report_page.html", locals())
    return _render_layout(title=ui["page_title"], body=body, session=session)


def _render_user_profile_settings_page(
    *,
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    profile: dict[str, Any],
    notice: str | None = None,
    wallet_balance: float = 0.0,
    topup_rows: list[dict[str, Any]] | None = None,
    premium_history_rows: list[dict[str, Any]] | None = None,
    plan_rows: list[dict[str, Any]] | None = None,
) -> str:
    def _as_utc_datetime(raw_value: Any) -> datetime.datetime | None:
        if not raw_value:
            return None
        if isinstance(raw_value, datetime.datetime):
            return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
        if isinstance(raw_value, (int, float)):
            try:
                ts = float(raw_value)
                if ts > 10_000_000_000:
                    ts /= 1000.0
                return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            except Exception:
                return None
        text = str(raw_value).strip()
        if not text:
            return None
        try:
            if text.isdigit():
                ts = float(text)
                if ts > 10_000_000_000:
                    ts /= 1000.0
                return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            return None

    def _fmt_datetime(raw_value: Any) -> str:
        parsed = _as_utc_datetime(raw_value)
        if not parsed:
            return "-"
        return parsed.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _fmt_money(raw_value: Any) -> str:
        try:
            return f"{float(raw_value or 0.0):,.2f}"
        except Exception:
            return "0.00"

    def _plan_label(raw_value: Any) -> str:
        normalized = _normalize_plan_tier(raw_value)
        return _plan_display_name(normalized)

    display_name = _escape(profile.get("display_name") or "Discord User")
    user_tag = _escape(profile.get("tag") or "-")
    user_id = _escape(profile.get("id") or "-")
    user_status = _escape(profile.get("status_label") or "Offline")
    status_key = _escape(profile.get("status_key") or "offline")
    avatar_url = _escape(profile.get("avatar_url") or _discord_default_avatar_url(profile.get("id") or "0"))
    avatar_fallback_url = _escape(_discord_default_avatar_url(profile.get("id") or "0"))
    banner_url = _escape(profile.get("banner_url") or "")
    accent_hex = _escape(profile.get("accent_hex") or "#4a78ff")
    account_created = _escape(profile.get("created_at_text") or "-")
    dashboard_login_at = _escape(profile.get("dashboard_login_at") or "-")
    banner_style = (
        f"background-image:url('{banner_url}'); background-size:cover; background-position:center;"
        if banner_url
        else f"background:linear-gradient(135deg, {accent_hex}, #22d3ee);"
    )
    wallet_balance_text = _fmt_money(wallet_balance)
    topup_rows_safe = list(topup_rows or [])
    premium_rows_safe = list(premium_history_rows or [])
    plan_rows_safe = list(plan_rows or [])
    paid_statuses = {"paid", "success", "succeeded", "approved", "completed", "captured"}
    paid_topups = [
        row
        for row in topup_rows_safe
        if str(row.get("status") or "").strip().lower() in paid_statuses
    ]
    pending_topup_count = sum(
        1 for row in topup_rows_safe if str(row.get("status") or "").strip().lower() == "pending"
    )
    def _amount_or_zero(row_value: dict[str, Any]) -> float:
        try:
            return float(row_value.get("amount") or 0.0)
        except Exception:
            return 0.0
    total_topup_amount = sum(
        _amount_or_zero(row) for row in paid_topups
    ) if paid_topups else 0.0
    last_topup_at_text = _fmt_datetime((paid_topups[0] if paid_topups else {}).get("paid_at"))
    topup_history_count = len(topup_rows_safe)

    topup_history_rows_markup: list[str] = []
    for row in topup_rows_safe[:80]:
        session_key = str(row.get("session_key") or "").strip()
        topup_history_rows_markup.append(
            f"""
            <tr>
              <td><code>{_escape(session_key[:16])}</code></td>
              <td>{_escape(_fmt_money(row.get("amount")))} THB</td>
              <td>{_escape(str(row.get("status") or "-"))}</td>
              <td>{_escape(str(row.get("verify_status") or "-"))}</td>
              <td>{_escape(_fmt_datetime(row.get("created_at")))}</td>
              <td>{_escape(_fmt_datetime(row.get("paid_at")))}</td>
            </tr>
            """
        )
    if not topup_history_rows_markup:
        topup_history_rows_markup.append(
            '<tr><td colspan="6" class="muted">ยังไม่มีประวัติการเติมเงิน</td></tr>'
        )
    profile_topup_rows_markup = "".join(topup_history_rows_markup)

    premium_history_rows_markup: list[str] = []
    for row in premium_rows_safe[:100]:
        premium_history_rows_markup.append(
            f"""
            <tr>
              <td>{_escape(str(row.get("event_type") or "-"))}</td>
              <td>{_escape(str(row.get("level") or "-"))}</td>
              <td>{_escape(str(row.get("message") or "-"))}</td>
              <td>{_escape(_fmt_datetime(row.get("created_at")))}</td>
            </tr>
            """
        )
    if not premium_history_rows_markup:
        premium_history_rows_markup.append(
            '<tr><td colspan="4" class="muted">ยังไม่มีประวัติพรีเมียม</td></tr>'
        )
    profile_premium_rows_markup = "".join(premium_history_rows_markup)

    profile_plan_cards_markup_parts: list[str] = []
    for row in plan_rows_safe:
        guild_id_value = int(row.get("guild_id") or 0)
        if guild_id_value <= 0:
            continue
        current_plan = _normalize_plan_tier(row.get("current_plan") or "free")
        pending_plan_raw = str(row.get("pending_plan") or "").strip()
        pending_plan = _normalize_plan_tier(pending_plan_raw) if pending_plan_raw else "free"
        if current_plan == "free" and pending_plan == "free":
            continue
        auto_renew = bool(row.get("auto_renew", True))
        pending_plan_label = _plan_label(pending_plan) if pending_plan_raw else "-"
        plan_end_text = "ถาวร" if current_plan == "permanent" else _fmt_datetime(row.get("current_period_end"))
        profile_plan_cards_markup_parts.append(
            f"""
            <article class="profile-plan-card">
              <h3 data-no-auto-i18n="1">{_escape(str(row.get("guild_name") or guild_id_value))}</h3>
              <div class="mini-stat">Guild ID: <code>{guild_id_value}</code></div>
              <div class="mini-stat">Current Plan: <strong>{_escape(_plan_label(current_plan))}</strong></div>
              <div class="mini-stat">Pending Plan: <strong>{_escape(pending_plan_label)}</strong></div>
              <div class="mini-stat">Status: <strong>{_escape(str(row.get("status") or "-"))}</strong></div>
              <div class="mini-stat">Plan End: {_escape(plan_end_text)}</div>
              <form method="post" action="/dashboard/wallet/plan/subscribe" class="settings-grid profile-plan-form">
                <input type="hidden" name="guild_id" value="{guild_id_value}">
                <input type="hidden" name="next" value="/dashboard/setting-profile-user">
                <label class="switch-row">
                  <span>เลือกแพ็กเกจ</span>
                  <select name="plan_tier">
                    <option value="silver"{' selected' if current_plan == 'silver' else ''}>Silver (40 THB / 30 วัน)</option>
                    <option value="golden"{' selected' if current_plan == 'golden' else ''}>Gole (120 THB / 30 วัน)</option>
                    <option value="diamond"{' selected' if current_plan == 'diamond' else ''}>Diamond (250 THB / 30 วัน)</option>
                    <option value="permanent"{' selected' if current_plan == 'permanent' else ''}>Permanent (500 THB / Lifetime)</option>
                  </select>
                </label>
                <label class="switch-row">
                  <span>ต่ออายุอัตโนมัติ</span>
                  <select name="auto_renew">
                    <option value="true"{' selected' if auto_renew else ''}>เปิด</option>
                    <option value="false"{'' if auto_renew else ' selected'}>ปิด</option>
                  </select>
                </label>
                <div class="auth-actions" style="justify-content:flex-start;">
                  <button class="primary-btn" type="submit">บันทึกแพ็กเกจ</button>
                </div>
              </form>
              <form method="post" action="/dashboard/wallet/plan/cancel" class="profile-plan-form profile-plan-cancel-form">
                <input type="hidden" name="guild_id" value="{guild_id_value}">
                <input type="hidden" name="next" value="/dashboard/setting-profile-user">
                <button class="ghost-btn" type="submit">ยกเลิกการต่ออายุ</button>
              </form>
            </article>
            """
        )
    if not profile_plan_cards_markup_parts:
        profile_plan_cards_markup_parts.append(
            '<div class="notice">ไม่พบเซิร์ฟเวอร์ที่คุณสามารถจัดการแผนได้</div>'
        )
    profile_plan_cards_markup = "".join(profile_plan_cards_markup_parts)
    premium_history_count = len(premium_rows_safe)
    profile_topup_history_url = "/dashboard/setting-profile-user/topup-history"
    profile_premium_history_url = "/dashboard/setting-profile-user/premium-history"
    topup_page_url = "/wallet"
    premium_page_url = "/premium"

    template_body = _render_dashboard_f_template("user_profile_settings_page.html", locals())

    body = (
        '<link rel="stylesheet" href="/dashboard/static/dashboard/pages/user-profile-settings.css">'
        + template_body
    )
    return _render_layout(
        title=f"SetingProfileUser - {display_name}",
        body=body,
        session=session,
        guilds=guilds,
        notice=notice,
    )


def _render_user_profile_topup_history_page(
    *,
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    profile: dict[str, Any],
    wallet_balance: float = 0.0,
    rows: list[dict[str, Any]] | None = None,
    page: int = 1,
    page_size: int = 30,
    total_count: int = 0,
    total_pages: int = 1,
    notice: str | None = None,
) -> str:
    def _as_utc_datetime(raw_value: Any) -> datetime.datetime | None:
        if not raw_value:
            return None
        if isinstance(raw_value, datetime.datetime):
            return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
        if isinstance(raw_value, (int, float)):
            try:
                ts = float(raw_value)
                if ts > 10_000_000_000:
                    ts /= 1000.0
                return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            except Exception:
                return None
        text = str(raw_value).strip()
        if not text:
            return None
        try:
            if text.isdigit():
                ts = float(text)
                if ts > 10_000_000_000:
                    ts /= 1000.0
                return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            return None

    def _fmt_datetime(raw_value: Any) -> str:
        parsed = _as_utc_datetime(raw_value)
        if not parsed:
            return "-"
        return parsed.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _fmt_money(raw_value: Any) -> str:
        try:
            return f"{float(raw_value or 0.0):,.2f}"
        except Exception:
            return "0.00"

    safe_rows = list(rows or [])
    safe_total = max(0, int(total_count or 0))
    safe_page_size = max(1, min(200, int(page_size or 30)))
    safe_total_pages = max(1, int(total_pages or 1))
    safe_page = max(1, min(int(page or 1), safe_total_pages))
    start_index = ((safe_page - 1) * safe_page_size) + 1 if safe_total else 0
    end_index = min(safe_total, safe_page * safe_page_size) if safe_total else 0

    page_base_url = "/dashboard/setting-profile-user/topup-history"
    profile_url = "/dashboard/setting-profile-user"
    premium_history_url = "/dashboard/setting-profile-user/premium-history"
    wallet_url = "/wallet"

    def _build_page_link(target_page: int) -> str:
        return f"{page_base_url}?{urlencode({'page': max(1, int(target_page))})}"

    prev_button_html = (
        f'<a class="ghost-btn profile-history-page-btn" href="{_escape(_build_page_link(safe_page - 1))}" aria-label="Previous page">&lt;</a>'
        if safe_page > 1
        else '<button class="ghost-btn profile-history-page-btn" type="button" disabled>&lt;</button>'
    )
    next_button_html = (
        f'<a class="ghost-btn profile-history-page-btn" href="{_escape(_build_page_link(safe_page + 1))}" aria-label="Next page">&gt;</a>'
        if safe_page < safe_total_pages
        else '<button class="ghost-btn profile-history-page-btn" type="button" disabled>&gt;</button>'
    )

    table_rows: list[str] = []
    for row in safe_rows:
        session_key = str(row.get("session_key") or "").strip()
        action_kind = str(row.get("action_kind") or "").strip().lower()
        action_label = str(row.get("action_label") or "").strip() or (
            "เติมเงิน" if str(row.get("entry_type") or "").strip().lower() == "payment" else "ปรับยอด"
        )
        actor_text = str(row.get("actor") or "").strip() or "-"
        note_text = str(row.get("note") or "").strip() or "-"
        row_class = "profile-topup-row"
        if action_kind == "admin_add":
            row_class += " is-admin-add"
        elif action_kind == "admin_delete":
            row_class += " is-admin-delete"
        elif action_kind == "admin_set":
            row_class += " is-admin-set"
        table_rows.append(
            f"""
            <tr class="{_escape(row_class)}">
              <td><code>{_escape(session_key[:16])}</code></td>
              <td>{_escape(action_label)}</td>
              <td>{_escape(_fmt_money(row.get("amount")))} THB</td>
              <td>{_escape(str(row.get("status") or "-"))}</td>
              <td>{_escape(str(row.get("verify_status") or "-"))}</td>
              <td>{_escape(actor_text)}</td>
              <td>{_escape(note_text)}</td>
              <td>{_escape(_fmt_datetime(row.get("created_at")))}</td>
              <td>{_escape(_fmt_datetime(row.get("paid_at")))}</td>
            </tr>
            """
        )
    if not table_rows:
        table_rows.append('<tr><td colspan="9" class="muted">ไม่พบประวัติการเติมเงิน</td></tr>')

    display_name = _escape(profile.get("display_name") or "Discord User")
    wallet_balance_text = _fmt_money(wallet_balance)
    body = f"""
    <link rel="stylesheet" href="/dashboard/static/dashboard/pages/user-profile-settings.css">
    <section class="panel profile-history-page-shell">
      <div class="profile-history-back">
        <a class="ghost-btn" href="{profile_url}"><i class="fa-solid fa-arrow-left"></i> บัญชีผู้ใช้</a>
        <a class="ghost-btn" href="{premium_history_url}"><i class="fa-solid fa-gem"></i> ประวัติฟรีเมียม</a>
        <a class="ghost-btn" href="{wallet_url}"><i class="fa-solid fa-wallet"></i> Wallet</a>
      </div>

      <div class="profile-section-head">
        <h2><i class="fa-solid fa-clock-rotate-left"></i> ประวัติการเติมเงิน</h2>
        <span class="mini-stat">บัญชี: {display_name}</span>
      </div>

      <div class="profile-history-summary">
        <span class="mini-stat">ยอดเงินคงเหลือ: <strong>{_escape(wallet_balance_text)} THB</strong></span>
        <span class="mini-stat">แสดง {start_index}-{end_index} จาก {safe_total} รายการ</span>
      </div>

      <div class="profile-table-wrap">
        <table class="audit-table">
          <thead>
            <tr>
              <th>Session</th>
              <th>Action</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Verify</th>
              <th>By</th>
              <th>Note</th>
              <th>Created</th>
              <th>Paid At</th>
            </tr>
          </thead>
          <tbody>{''.join(table_rows)}</tbody>
        </table>
      </div>

      <div class="profile-history-pagination">
        {prev_button_html}
        <span class="profile-history-page-number">{safe_page}/{safe_total_pages}</span>
        {next_button_html}
      </div>
    </section>
    """
    return _render_layout(
        title=f"ประวัติการเติมเงิน - {display_name}",
        body=body,
        session=session,
        guilds=guilds,
        notice=notice,
    )


def _render_user_profile_premium_history_page(
    *,
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    profile: dict[str, Any],
    wallet_balance: float = 0.0,
    rows: list[dict[str, Any]] | None = None,
    page: int = 1,
    page_size: int = 30,
    total_count: int = 0,
    total_pages: int = 1,
    notice: str | None = None,
) -> str:
    def _as_utc_datetime(raw_value: Any) -> datetime.datetime | None:
        if not raw_value:
            return None
        if isinstance(raw_value, datetime.datetime):
            return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
        if isinstance(raw_value, (int, float)):
            try:
                ts = float(raw_value)
                if ts > 10_000_000_000:
                    ts /= 1000.0
                return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            except Exception:
                return None
        text = str(raw_value).strip()
        if not text:
            return None
        try:
            if text.isdigit():
                ts = float(text)
                if ts > 10_000_000_000:
                    ts /= 1000.0
                return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            return None

    def _fmt_datetime(raw_value: Any) -> str:
        parsed = _as_utc_datetime(raw_value)
        if not parsed:
            return "-"
        return parsed.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _fmt_money(raw_value: Any) -> str:
        try:
            return f"{float(raw_value or 0.0):,.2f}"
        except Exception:
            return "0.00"

    def _safe_int(raw_value: Any, default: int = 0) -> int:
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return int(default)

    safe_rows = list(rows or [])
    safe_total = max(0, int(total_count or 0))
    safe_page_size = max(1, min(200, int(page_size or 30)))
    safe_total_pages = max(1, int(total_pages or 1))
    safe_page = max(1, min(int(page or 1), safe_total_pages))
    start_index = ((safe_page - 1) * safe_page_size) + 1 if safe_total else 0
    end_index = min(safe_total, safe_page * safe_page_size) if safe_total else 0

    page_base_url = "/dashboard/setting-profile-user/premium-history"
    profile_url = "/dashboard/setting-profile-user"
    topup_history_url = "/dashboard/setting-profile-user/topup-history"
    premium_page_url = "/premium"

    def _build_page_link(target_page: int) -> str:
        return f"{page_base_url}?{urlencode({'page': max(1, int(target_page))})}"

    prev_button_html = (
        f'<a class="ghost-btn profile-history-page-btn" href="{_escape(_build_page_link(safe_page - 1))}" aria-label="Previous page">&lt;</a>'
        if safe_page > 1
        else '<button class="ghost-btn profile-history-page-btn" type="button" disabled>&lt;</button>'
    )
    next_button_html = (
        f'<a class="ghost-btn profile-history-page-btn" href="{_escape(_build_page_link(safe_page + 1))}" aria-label="Next page">&gt;</a>'
        if safe_page < safe_total_pages
        else '<button class="ghost-btn profile-history-page-btn" type="button" disabled>&gt;</button>'
    )

    table_rows: list[str] = []
    for row in safe_rows:
        meta_payload = row.get("meta")
        meta = meta_payload if isinstance(meta_payload, dict) else {}
        claimed_by_user_id = _safe_int(meta.get("claimed_by_user_id"), 0) or _safe_int(row.get("user_id"), 0)
        claimed_by_text = str(meta.get("claimed_by_display") or "").strip()
        if not claimed_by_text:
            claimed_by_text = f"User {claimed_by_user_id}" if claimed_by_user_id > 0 else "-"
        guild_id_text = str(meta.get("redeemed_guild_id") or row.get("guild_id") or "").strip()
        guild_name_text = str(meta.get("redeemed_guild_name") or "").strip()
        if guild_name_text and guild_id_text:
            redeemed_server_text = f"{guild_name_text} ({guild_id_text})"
        elif guild_name_text:
            redeemed_server_text = guild_name_text
        elif guild_id_text:
            redeemed_server_text = f"ID {guild_id_text}"
        else:
            redeemed_server_text = "-"
        plan_text = str(meta.get("plan_label") or meta.get("plan_tier") or row.get("event_type") or "-").strip() or "-"
        support_role_text = str(meta.get("support_role_label") or "-").strip() or "-"
        code_created_text = _fmt_datetime(meta.get("code_created_at"))
        code_expires_text = _fmt_datetime(meta.get("code_expires_at"))
        redeemed_at_text = _fmt_datetime(meta.get("redeemed_at") or row.get("created_at"))
        table_rows.append(
            f"""
            <tr>
              <td>{_escape(str(meta.get("redeem_code") or "-"))}</td>
              <td>{_escape(claimed_by_text)}</td>
              <td>{_escape(redeemed_server_text)}</td>
              <td>{_escape(plan_text)}</td>
              <td>{_escape(support_role_text)}</td>
              <td>{_escape(code_created_text)}</td>
              <td>{_escape(code_expires_text)}</td>
              <td>{_escape(redeemed_at_text)}</td>
            </tr>
            """
        )
    if not table_rows:
        table_rows.append('<tr><td colspan="8" class="muted">ไม่พบประวัติฟรีเมียม</td></tr>')

    display_name = _escape(profile.get("display_name") or "Discord User")
    wallet_balance_text = _fmt_money(wallet_balance)
    body = f"""
    <link rel="stylesheet" href="/dashboard/static/dashboard/pages/user-profile-settings.css">
    <section class="panel profile-history-page-shell">
      <div class="profile-history-back">
        <a class="ghost-btn" href="{profile_url}"><i class="fa-solid fa-arrow-left"></i> บัญชีผู้ใช้</a>
        <a class="ghost-btn" href="{topup_history_url}"><i class="fa-solid fa-clock-rotate-left"></i> ประวัติการเติมเงิน</a>
        <a class="ghost-btn" href="{premium_page_url}"><i class="fa-solid fa-crown"></i> แพ็กเกจ</a>
      </div>

      <div class="profile-section-head">
        <h2><i class="fa-solid fa-gem"></i> ประวัติฟรีเมียม</h2>
        <span class="mini-stat">บัญชี: {display_name}</span>
      </div>

      <div class="profile-history-summary">
        <span class="mini-stat">ยอดเงินคงเหลือ: <strong>{_escape(wallet_balance_text)} THB</strong></span>
        <span class="mini-stat">แสดง {start_index}-{end_index} จาก {safe_total} รายการ</span>
      </div>

      <div class="profile-table-wrap">
        <table class="audit-table">
          <thead>
            <tr>
              <th>Redeem Code</th>
              <th>Claimed By</th>
              <th>Redeem Server</th>
              <th>Plan</th>
              <th>Support Role</th>
              <th>Code Created</th>
              <th>Code Expires</th>
              <th>Redeemed At</th>
            </tr>
          </thead>
          <tbody>{''.join(table_rows)}</tbody>
        </table>
      </div>

      <div class="profile-history-pagination">
        {prev_button_html}
        <span class="profile-history-page-number">{safe_page}/{safe_total_pages}</span>
        {next_button_html}
      </div>
    </section>
    """
    return _render_layout(
        title=f"ประวัติฟรีเมียม - {display_name}",
        body=body,
        session=session,
        guilds=guilds,
        notice=notice,
    )


def _render_trusted_servers_manager_page(
    *,
    session: dict[str, Any],
    order: list[str],
    available_names: list[str],
    notice: str | None = None,
) -> str:
    normalized_available = []
    seen = set()
    for name in available_names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized_available.append(name)

    ordered = []
    ordered_seen = set()
    for name in order:
        for candidate in normalized_available:
            if candidate.casefold() == name.casefold() and candidate.casefold() not in ordered_seen:
                ordered.append(candidate)
                ordered_seen.add(candidate.casefold())
                break
    for candidate in normalized_available:
        if candidate.casefold() not in ordered_seen:
            ordered.append(candidate)
            ordered_seen.add(candidate.casefold())

    list_items = "".join(
        f'<li class="trusted-manager-item" draggable="true" data-name="{_escape(name)}">'
        f'<span class="drag"></span><span>{_escape(name)}</span></li>'
        for name in ordered
    )
    notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""

    template_body = _render_dashboard_f_template("trusted_servers_manager_page.html", locals())

    body = (
        template_body
        + '<script src="/dashboard/static/dashboard/pages/trusted-servers-manager.js" defer></script>'
    )
    return _render_layout(title="จัดการเซิร์ฟเวอร์ที่เชื่อถือ", body=body, session=session)


def _render_ownerbot_console_page(
    *,
    session: dict[str, Any],
    guild_rows: list[dict[str, Any]],
    redeem_rows: list[dict[str, Any]],
    redeem_summary: dict[str, Any] | None = None,
    wallet_rows: list[dict[str, Any]],
    wallet_summary: dict[str, Any] | None = None,
    runtime_settings: dict[str, Any],
    payment_provider_settings: dict[str, Any],
    plan_pricing_settings: dict[str, Any],
    plan_pricing_snapshot: dict[str, Any],
    command_choices: list[str],
    upload_channel_settings: dict[str, Any],
    upload_guild_rows: list[dict[str, str]],
    upload_channel_rows: list[dict[str, str]],
    mongo_cluster_rows: list[dict[str, Any]] | None = None,
    mongo_uris_count: int = 0,
    mongo_healthy_count: int = 0,
    mongo_quota_warning_count: int = 0,
    mongo_collection_options: list[str] | None = None,
    mongo_primary_uri: str = "",
    mongo_backup_uri_text: str = "",
    mongo_database_name: str = "skylinebot",
    mongo_read_mode: str = "aggregate",
    mongo_write_mode: str = "hash",
    mongo_migration_history_retention_days: int = 90,
    mongo_health_totals: dict[str, Any] | None = None,
    mongo_migration_history_rows: list[dict[str, Any]] | None = None,
    promote_policy_settings: dict[str, Any] | None = None,
    promote_suspension_map: dict[str, Any] | None = None,
    discord_runtime: dict[str, Any] | None = None,
    notice: str | None = None,
    overview_only: bool = True,
    settings_active_section: str = "runtime",
    settings_active_runtime_page: str = "overview",
) -> str:
    return _dashboard_ownerbot_domain.render_ownerbot_console_page(
        session=session,
        guild_rows=guild_rows,
        redeem_rows=redeem_rows,
        redeem_summary=dict(redeem_summary or {}),
        wallet_rows=wallet_rows,
        wallet_summary=dict(wallet_summary or {}),
        runtime_settings=runtime_settings,
        payment_provider_settings=payment_provider_settings,
        plan_pricing_settings=plan_pricing_settings,
        plan_pricing_snapshot=plan_pricing_snapshot,
        command_choices=command_choices,
        upload_channel_settings=upload_channel_settings,
        upload_guild_rows=upload_guild_rows,
        upload_channel_rows=upload_channel_rows,
        mongo_cluster_rows=list(mongo_cluster_rows or []),
        mongo_uris_count=int(mongo_uris_count or 0),
        mongo_healthy_count=int(mongo_healthy_count or 0),
        mongo_quota_warning_count=int(mongo_quota_warning_count or 0),
        mongo_collection_options=list(mongo_collection_options or []),
        mongo_primary_uri=str(mongo_primary_uri or ""),
        mongo_backup_uri_text=str(mongo_backup_uri_text or ""),
        mongo_database_name=str(mongo_database_name or "skylinebot"),
        mongo_read_mode=str(mongo_read_mode or "aggregate"),
        mongo_write_mode=str(mongo_write_mode or "hash"),
        mongo_migration_history_retention_days=int(mongo_migration_history_retention_days or 0),
        mongo_health_totals=dict(mongo_health_totals or {}),
        mongo_migration_history_rows=list(mongo_migration_history_rows or []),
        promote_policy_settings=dict(promote_policy_settings or {}),
        promote_suspension_map=dict(promote_suspension_map or {}),
        discord_runtime=discord_runtime,
        notice=notice,
        escape_fn=_escape,
        render_layout_fn=_render_layout,
        render_dashboard_f_template_fn=_render_dashboard_f_template,
        normalize_runtime_settings_fn=_normalize_ownerbot_runtime_settings,
        ownerbot_hidden_dashboard_tabs_fn=_ownerbot_hidden_dashboard_tabs,
        developer_social_url_fn=_developer_social_url,
        developer_social_icon_fn=_developer_social_icon,
        format_datetime_local_fn=_format_datetime_local,
        format_datetime_th_fn=_format_datetime_th,
        redeem_code_types=REDEEM_CODE_TYPES,
        ownerbot_ai_model_ram_guide=OWNERBOT_AI_MODEL_RAM_GUIDE,
        social_platform_keys=SOCIAL_PLATFORM_KEYS,
        social_platform_labels=SOCIAL_PLATFORM_LABELS,
        social_platform_default_icons=SOCIAL_PLATFORM_DEFAULT_ICONS,
        ownerbot_upload_targets=OWNERBOT_UPLOAD_TARGETS,
        ownerbot_upload_target_labels=OWNERBOT_UPLOAD_TARGET_LABELS,
        ownerbot_upload_target_default_channels=OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS,
        ownerbot_hideable_tabs=OWNERBOT_HIDEABLE_TABS,
        ownerbot_hideable_tab_labels=OWNERBOT_HIDEABLE_TAB_LABELS,
        dashboard_tab_required_plan_defaults=DASHBOARD_TAB_REQUIRED_PLAN,
        dashboard_tab_plan_tiers=DASHBOARD_TAB_REQUIRED_PLAN_TIERS,
        dashboard_tab_new_badge_defaults=DASHBOARD_TAB_NEW_BADGES_DEFAULT,
        overview_only=bool(overview_only),
        settings_active_section=str(settings_active_section or "runtime"),
        settings_active_runtime_page=str(settings_active_runtime_page or "overview"),
    )


def _render_ownerbot_settings_page(
    *,
    session: dict[str, Any],
    guild_rows: list[dict[str, Any]],
    redeem_rows: list[dict[str, Any]],
    redeem_summary: dict[str, Any] | None = None,
    wallet_rows: list[dict[str, Any]],
    wallet_summary: dict[str, Any] | None = None,
    runtime_settings: dict[str, Any],
    payment_provider_settings: dict[str, Any],
    plan_pricing_settings: dict[str, Any],
    plan_pricing_snapshot: dict[str, Any],
    command_choices: list[str],
    upload_channel_settings: dict[str, Any],
    upload_guild_rows: list[dict[str, str]],
    upload_channel_rows: list[dict[str, str]],
    mongo_cluster_rows: list[dict[str, Any]] | None = None,
    mongo_uris_count: int = 0,
    mongo_healthy_count: int = 0,
    mongo_quota_warning_count: int = 0,
    mongo_collection_options: list[str] | None = None,
    mongo_primary_uri: str = "",
    mongo_backup_uri_text: str = "",
    mongo_database_name: str = "skylinebot",
    mongo_read_mode: str = "aggregate",
    mongo_write_mode: str = "hash",
    mongo_migration_history_retention_days: int = 90,
    mongo_health_totals: dict[str, Any] | None = None,
    mongo_migration_history_rows: list[dict[str, Any]] | None = None,
    promote_policy_settings: dict[str, Any] | None = None,
    promote_suspension_map: dict[str, Any] | None = None,
    discord_runtime: dict[str, Any] | None = None,
    notice: str | None = None,
    settings_active_section: str = "runtime",
    settings_active_runtime_page: str = "overview",
) -> str:
    return _render_ownerbot_console_page(
        session=session,
        guild_rows=guild_rows,
        redeem_rows=redeem_rows,
        redeem_summary=dict(redeem_summary or {}),
        wallet_rows=wallet_rows,
        wallet_summary=dict(wallet_summary or {}),
        runtime_settings=runtime_settings,
        payment_provider_settings=payment_provider_settings,
        plan_pricing_settings=plan_pricing_settings,
        plan_pricing_snapshot=plan_pricing_snapshot,
        command_choices=command_choices,
        upload_channel_settings=upload_channel_settings,
        upload_guild_rows=upload_guild_rows,
        upload_channel_rows=upload_channel_rows,
        mongo_cluster_rows=list(mongo_cluster_rows or []),
        mongo_uris_count=int(mongo_uris_count or 0),
        mongo_healthy_count=int(mongo_healthy_count or 0),
        mongo_quota_warning_count=int(mongo_quota_warning_count or 0),
        mongo_collection_options=list(mongo_collection_options or []),
        mongo_primary_uri=str(mongo_primary_uri or ""),
        mongo_backup_uri_text=str(mongo_backup_uri_text or ""),
        mongo_database_name=str(mongo_database_name or "skylinebot"),
        mongo_read_mode=str(mongo_read_mode or "aggregate"),
        mongo_write_mode=str(mongo_write_mode or "hash"),
        mongo_migration_history_retention_days=int(mongo_migration_history_retention_days or 0),
        mongo_health_totals=dict(mongo_health_totals or {}),
        mongo_migration_history_rows=list(mongo_migration_history_rows or []),
        promote_policy_settings=dict(promote_policy_settings or {}),
        promote_suspension_map=dict(promote_suspension_map or {}),
        discord_runtime=discord_runtime,
        notice=notice,
        overview_only=False,
        settings_active_section=str(settings_active_section or "runtime"),
        settings_active_runtime_page=str(settings_active_runtime_page or "overview"),
    )


def _render_redeem_web_page(
    *,
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    notice: str | None = None,
    form_values: dict[str, Any] | None = None,
    preview_payload: dict[str, Any] | None = None,
) -> str:
    safe_form_values = form_values if isinstance(form_values, dict) else {}
    redeem_code_value = str(safe_form_values.get("redeem_code") or "").strip()
    selected_target_guild_id = str(safe_form_values.get("target_guild_id") or "").strip()
    notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""
    option_rows: list[str] = []
    for guild in guilds:
        guild_id_text = str(guild.get("id"))
        selected_attr = " selected" if guild_id_text == selected_target_guild_id else ""
        option_rows.append(
            f'<option value="{_escape(guild_id_text)}"{selected_attr}>{_escape(str(guild.get("name") or guild.get("id")))}</option>'
        )
    guild_options = "".join(option_rows)
    preview_section_markup = ""
    preview = preview_payload if isinstance(preview_payload, dict) else {}
    if preview:
        preview_code = str(preview.get("redeem_code") or redeem_code_value).strip()
        preview_target_guild_id = str(preview.get("target_guild_id") or selected_target_guild_id).strip()
        preview_section_markup = f"""
        <section class="redeem-preview-card">
          <div class="redeem-card-head">
            <h2 data-icon-key="shield-check">Review Before Confirm</h2>
            <p class="muted">ตรวจสอบข้อมูลโค้ดและปลายทางก่อนกดยืนยัน</p>
          </div>
          <div class="panel-sub">
            <table class="audit-table redeem-preview-table">
              <tbody>
                <tr><th>Redeem Code</th><td><code>{_escape(preview_code or "-")}</code></td></tr>
                <tr><th>Guild Name</th><td>{_escape(str(preview.get("target_guild_name") or "-"))}</td></tr>
                <tr><th>Guild ID</th><td>{_escape(str(preview.get("target_guild_id_display") or "-"))}</td></tr>
                <tr><th>Code Created</th><td>{_escape(str(preview.get("code_created_at") or "-"))}</td></tr>
                <tr><th>Code Expires</th><td>{_escape(str(preview.get("code_expires_at") or "-"))}</td></tr>
                <tr><th>Plan</th><td>{_escape(str(preview.get("plan_label") or "-"))}</td></tr>
                <tr><th>Support Role</th><td>{_escape(str(preview.get("support_role_label") or "-"))}</td></tr>
              </tbody>
            </table>
          </div>
          <form method="post" action="/redeem" class="auth-actions redeem-actions" style="margin-top:10px;">
            <input type="hidden" name="redeem_action" value="confirm">
            <input type="hidden" name="redeem_code" value="{_escape(preview_code)}">
            <input type="hidden" name="target_guild_id" value="{_escape(preview_target_guild_id)}">
            <button class="primary-btn" type="submit"><i class="fa-solid fa-check-circle"></i> Confirm Redeem</button>
          </form>
        </section>
        """
    body = _render_dashboard_f_template("redeem_web_page.html", locals())
    return _render_layout(title="แลกรับโค้ด - SkylineBOT", body=body, session=session, guilds=guilds)


def _render_premium_doc_page(
    *,
    session: dict[str, Any] | None = None,
    subscribe_context: dict[str, Any] | None = None,
    interactive: bool = False,
    plan_pricing_snapshot: dict[str, Any] | None = None,
    notice: str | None = None,
) -> str:
    pricing_snapshot = (
        plan_pricing_snapshot
        if isinstance(plan_pricing_snapshot, dict)
        else _billing_workflow.build_plan_pricing_snapshot_from_settings({})
    )
    comparison_rows = _premium_table_rows(
        _premium_feature_rows_from_live_rules(),
        "premium_live",
        with_i18n=False,
    )
    command_rows = _premium_table_rows(
        _premium_command_rows_from_live_rules(),
        "command_plan_live",
        with_i18n=False,
    )
    donate_rows = _premium_table_rows(
        _donation_support_rows_from_live_rules(pricing_snapshot),
        "donation_plan_live",
        allow_html=True,
        with_i18n=False,
    )
    comparison_table_header_row = _premium_table_header_row("ฟีเจอร์")
    command_table_header_row = _premium_table_header_row("คำสั่ง / ฟีเจอร์")
    donate_table_header_row = _premium_table_header_row("รายละเอียดการสนับสนุน")
    pricing_cards = _premium_cards_markup(pricing_snapshot)
    subscribe_notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""

    subscribe_ctx = subscribe_context if isinstance(subscribe_context, dict) else {}
    guild_plan_rows_raw = list(subscribe_ctx.get("guild_plan_rows") or [])
    user_app_subscription_raw = subscribe_ctx.get("user_app_subscription")
    if not isinstance(user_app_subscription_raw, dict):
        user_app_subscription_raw = {}

    guild_plan_rows: list[dict[str, Any]] = []
    for item in guild_plan_rows_raw:
        if not isinstance(item, dict):
            continue
        try:
            guild_id_value = int(item.get("guild_id") or 0)
        except Exception:
            guild_id_value = 0
        if guild_id_value <= 0:
            continue
        current_plan_tier = _normalize_plan_tier(item.get("current_plan") or "free")
        pending_plan_raw = str(item.get("pending_plan") or "").strip()
        pending_plan_tier = _normalize_plan_tier(pending_plan_raw) if pending_plan_raw else "free"
        period_end_value = item.get("current_period_end")
        guild_plan_rows.append(
            {
                "guild_id": guild_id_value,
                "guild_name": str(item.get("guild_name") or guild_id_value),
                "current_plan_tier": current_plan_tier,
                "current_plan_label": _plan_display_name(current_plan_tier),
                "pending_plan_tier": pending_plan_tier,
                "pending_plan_label": _plan_display_name(pending_plan_tier) if pending_plan_raw else "-",
                "status": str(item.get("status") or "-").strip() or "-",
                "auto_renew": bool(item.get("auto_renew", True)),
                "period_end_text": _format_datetime_th(period_end_value),
            }
        )

    default_guild_id = str(guild_plan_rows[0]["guild_id"]) if guild_plan_rows else ""
    guild_select_options_markup = "".join(
        f'<option value="{_escape(str(row.get("guild_id") or ""))}">{_escape(str(row.get("guild_name") or row.get("guild_id") or ""))}</option>'
        for row in guild_plan_rows
    )

    plan_action_catalog = [
        {
            "tier": "silver",
            "title": "Silver",
            "price": "40.00 บาท / 30 วัน",
            "desc": "ปลดล็อกฟีเจอร์พรีเมียมหลักสำหรับเซิร์ฟเวอร์ที่เริ่มเติบโต",
            "button": "สมัครแพ็กเกจ Silver",
            "auto_renew": "true",
        },
        {
            "tier": "golden",
            "title": "Gole",
            "price": "120.00 บาท / 30 วัน",
            "desc": "เพิ่มขีดจำกัดการใช้งานสำหรับชุมชนที่ใช้งานหนาแน่น",
            "button": "สมัครแพ็กเกจ Gole",
            "auto_renew": "true",
        },
        {
            "tier": "diamond",
            "title": "Diamond",
            "price": "250.00 บาท / 30 วัน",
            "desc": "ปลดล็อกสิทธิ์และขีดจำกัดสูงสุดของระบบ",
            "button": "สมัครแพ็กเกจ Diamond",
            "auto_renew": "true",
        },
        {
            "tier": "permanent",
            "title": "Permanent",
            "price": "500.00 บาท / ตลอดชีพ",
            "desc": "ชำระครั้งเดียว ใช้งานสิทธิ์ถาวรสำหรับกิลด์ที่เลือก",
            "button": "สมัครแพ็กเกจ Permanent",
            "auto_renew": "false",
        },
    ]
    for card in plan_action_catalog:
        quote = _pricing_quote_from_snapshot(str(card.get("tier") or "free"), pricing_snapshot)
        card["price"] = _price_text_from_quote(quote, period_style="days")
        card["price_html"] = _price_html_from_quote(quote, period_style="days")
    subscribe_plan_style_markup = """
    <style>
      .premium-action-card {
        position: relative;
        display: grid;
        gap: 10px;
      }
      .premium-action-head-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .premium-action-head-row h3 {
        margin: 0;
      }
      .premium-current-badge {
        display: inline-flex;
        align-items: center;
        border: 1px solid rgba(125, 198, 151, 0.62);
        border-radius: 999px;
        background: rgba(51, 119, 86, 0.32);
        color: #a8ffd7;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        padding: 3px 10px;
        white-space: nowrap;
      }
      .premium-action-card.is-current-plan {
        border-color: rgba(111, 205, 157, 0.58);
        box-shadow: 0 0 0 1px rgba(111, 205, 157, 0.24), 0 14px 30px rgba(21, 42, 36, 0.38);
      }
      body.light-theme .premium-action-card.is-current-plan {
        border-color: rgba(35, 139, 82, 0.4);
        box-shadow: 0 0 0 1px rgba(35, 139, 82, 0.2);
      }
      body.light-theme .premium-current-badge {
        border-color: rgba(28, 127, 74, 0.4);
        background: rgba(28, 127, 74, 0.12);
        color: #166c43;
      }
    </style>
    """
    plan_action_cards_markup = "".join(
        f"""
        <article class="premium-action-card" data-plan-tier="{_escape(card['tier'])}">
          <div class="premium-action-head-row">
            <h3>{_escape(card['title'])}</h3>
            <span class="premium-current-badge" data-current-plan-badge hidden>แผนปัจจุบัน</span>
          </div>
          <p class="price">{card.get('price_html') or _escape(card['price'])}</p>
          <p class="muted">{_escape(card['desc'])}</p>
          <form method="post" action="/dashboard/wallet/plan/subscribe" class="premium-action-form">
            <input type="hidden" name="guild_id" value="{_escape(default_guild_id)}" data-subscribe-guild-id>
            <input type="hidden" name="plan_tier" value="{_escape(card['tier'])}">
            <input type="hidden" name="auto_renew" value="{_escape(card['auto_renew'])}">
            <input type="hidden" name="next" value="/dashboard/subscribe-plan">
            <button class="primary-btn" type="submit" data-plan-submit-button>{_escape(card['button'])}</button>
          </form>
        </article>
        """
        for card in plan_action_catalog
    )

    app_current_plan_raw = str(user_app_subscription_raw.get("current_plan") or "free").strip().lower()
    app_pending_plan_raw = str(user_app_subscription_raw.get("pending_plan") or "").strip().lower()
    app_current_label = "Discord App User Plan" if app_current_plan_raw == "user_app_plan" else "Free"
    app_pending_label = "Discord App User Plan" if app_pending_plan_raw == "user_app_plan" else "-"
    app_status_raw = str(user_app_subscription_raw.get("status") or "").strip().lower()
    app_expires_raw = user_app_subscription_raw.get("current_period_end")
    app_expires_text = _format_datetime_th(app_expires_raw)
    app_auto_renew = bool(user_app_subscription_raw.get("auto_renew", True))
    app_status_label = "ยังไม่เปิดใช้งาน"
    if app_current_plan_raw == "user_app_plan":
        app_status_label = "เปิดใช้งาน" if app_status_raw in {"active", "grace"} else "รอเปิดใช้งาน"
    app_user_quote = _pricing_quote_from_snapshot(_billing_workflow.USER_APP_PLAN_CODE, pricing_snapshot)
    app_user_price_text = _price_text_from_quote(app_user_quote, period_style="days")
    app_user_price_html = _price_html_from_quote(app_user_quote, period_style="days")

    subscribe_plan_shell_markup = ""
    if interactive:
        if not session:
            subscribe_plan_shell_markup = """
            <section class="panel" style="display:grid; gap:12px;">
              <h2 style="margin:0;">สมัครแพ็กเกจ</h2>
              <p class="muted" style="margin:0;">กรุณาเข้าสู่ระบบก่อนเพื่อสมัครแพ็กเกจเซิร์ฟเวอร์</p>
              <div class="auth-actions" style="justify-content:flex-start;">
                <a class="primary-btn" href="/dashboard/login?next=/dashboard/subscribe-plan">เข้าสู่ระบบ</a>
              </div>
            </section>
            """
        else:
            guild_selection_block = (
                f"""
                <section class="panel premium-subscribe-block" style="display:grid; gap:12px;">
                  <h2 style="margin:0;">สมัครแพ็กเกจรายกิลด์</h2>
                  <p class="muted" style="margin:0;">เลือกกิลด์เป้าหมายก่อน จากนั้นกดสมัครแพ็กเกจที่ต้องการได้ทันที</p>
                  <label class="switch-row">
                    <span>กิลด์เป้าหมาย</span>
                    <select id="subscribePlanGuildSelect" data-no-auto-i18n="1">{guild_select_options_markup}</select>
                  </label>
                  <div class="premium-subscribe-status-grid">
                    <article class="premium-subscribe-status-card">
                      <strong id="subscribePlanGuildName" data-no-auto-i18n="1">-</strong>
                      <div class="mini-stat">แพ็กเกจปัจจุบัน: <b id="subscribePlanCurrentPlan">-</b></div>
                      <div class="mini-stat">คิวแพ็กเกจถัดไป: <b id="subscribePlanPendingPlan">-</b></div>
                      <div class="mini-stat">สถานะ: <b id="subscribePlanStatus">-</b></div>
                      <div class="mini-stat">หมดอายุ: <b id="subscribePlanEndsAt">-</b></div>
                      <div class="mini-stat">ต่ออายุอัตโนมัติ: <b id="subscribePlanAutoRenew">-</b></div>
                    </article>
                  </div>
                  <div class="landing-grid price-grid">
                    {plan_action_cards_markup}
                  </div>
                  <form method="post" action="/dashboard/wallet/plan/cancel" class="premium-action-form" style="max-width:360px;">
                    <input type="hidden" name="guild_id" value="{_escape(default_guild_id)}" data-subscribe-guild-id>
                    <input type="hidden" name="next" value="/dashboard/subscribe-plan">
                    <button class="ghost-btn" type="submit">ยกเลิกการต่ออายุกิลด์ที่เลือก</button>
                  </form>
                </section>
                """
                if guild_plan_rows
                else """
                <section class="panel" style="display:grid; gap:8px;">
                  <h2 style="margin:0;">สมัครแพ็กเกจรายกิลด์</h2>
                  <p class="muted" style="margin:0;">ยังไม่พบกิลด์ที่คุณมีสิทธิ์จัดการ</p>
                </section>
                """
            )

            subscribe_plan_shell_markup = f"""
            {subscribe_plan_style_markup}
            {subscribe_notice_markup}
            {guild_selection_block}
            <section class="panel premium-user-plan-block" style="display:grid; gap:12px;">
              <h2 style="margin:0;">Discord App User Plan</h2>
              <p class="muted" style="margin:0;">แพ็กเกจแยกสำหรับผู้ใช้ (ไม่ใช่แพ็กเกจกิลด์) ราคา {app_user_price_html}</p>
              <div class="premium-subscribe-status-grid">
                <article class="premium-subscribe-status-card">
                  <strong>{_escape(app_current_label)}</strong>
                  <div class="mini-stat">สถานะ: <b>{_escape(app_status_label)}</b></div>
                  <div class="mini-stat">คิวแพ็กเกจถัดไป: <b>{_escape(app_pending_label)}</b></div>
                  <div class="mini-stat">หมดอายุ: <b>{_escape(app_expires_text)}</b></div>
                  <div class="mini-stat">ต่ออายุอัตโนมัติ: <b>{'เปิด' if app_auto_renew else 'ปิด'}</b></div>
                </article>
              </div>
              <form method="post" action="/dashboard/wallet/app-user/subscribe" class="settings-grid" style="max-width:560px;">
                <input type="hidden" name="next" value="/dashboard/subscribe-plan">
                <label class="switch-row">
                  <span>ต่ออายุอัตโนมัติ</span>
                    <select name="auto_renew">
                    <option value="true"{' selected' if app_auto_renew else ''}>เปิด</option>
                    <option value="false"{'' if app_auto_renew else ' selected'}>ปิด</option>
                  </select>
                </label>
                <div class="auth-actions" style="justify-content:flex-start;">
                  <button class="primary-btn" type="submit">สมัคร App User Plan ({_escape(app_user_price_text)})</button>
                </div>
              </form>
              <form method="post" action="/dashboard/wallet/app-user/cancel" class="premium-action-form" style="max-width:360px;">
                <input type="hidden" name="next" value="/dashboard/subscribe-plan">
                <button class="ghost-btn" type="submit">ยกเลิกการต่ออายุ App User Plan</button>
              </form>
            </section>
            """

    guild_plan_rows_json = json.dumps(guild_plan_rows, ensure_ascii=False)
    subscribe_plan_script_markup = ""
    if interactive and guild_plan_rows:
        subscribe_plan_script_markup = f"""
        <script id="subscribePlanGuildData" type="application/json">{_escape(guild_plan_rows_json)}</script>
        <script>
          (() => {{
            const selector = document.getElementById('subscribePlanGuildSelect');
            const rawData = document.getElementById('subscribePlanGuildData');
            if (!selector || !rawData) return;
            let rows = [];
            try {{
              rows = JSON.parse(rawData.textContent || '[]');
            }} catch (_err) {{
              rows = [];
            }}
            const hiddenInputs = Array.from(document.querySelectorAll('input[data-subscribe-guild-id]'));
            const planCards = Array.from(document.querySelectorAll('.premium-action-card[data-plan-tier]'));
            const nameEl = document.getElementById('subscribePlanGuildName');
            const currentEl = document.getElementById('subscribePlanCurrentPlan');
            const pendingEl = document.getElementById('subscribePlanPendingPlan');
            const statusEl = document.getElementById('subscribePlanStatus');
            const endsAtEl = document.getElementById('subscribePlanEndsAt');
            const renewEl = document.getElementById('subscribePlanAutoRenew');

            const applyGuild = () => {{
              const guildId = String(selector.value || '').trim();
              hiddenInputs.forEach((input) => {{
                input.value = guildId;
              }});
              const selected = rows.find((row) => String(row.guild_id || '') === guildId) || null;
              if (!selected) {{
                if (nameEl) nameEl.textContent = '-';
                if (currentEl) currentEl.textContent = '-';
                if (pendingEl) pendingEl.textContent = '-';
                if (statusEl) statusEl.textContent = '-';
                if (endsAtEl) endsAtEl.textContent = '-';
                if (renewEl) renewEl.textContent = '-';
                planCards.forEach((card) => {{
                  card.classList.remove('is-current-plan');
                  const badge = card.querySelector('[data-current-plan-badge]');
                  if (badge) badge.hidden = true;
                }});
                return;
              }}
              if (nameEl) nameEl.textContent = selected.guild_name || guildId;
              if (currentEl) currentEl.textContent = selected.current_plan_label || '-';
              if (pendingEl) pendingEl.textContent = selected.pending_plan_label || '-';
              if (statusEl) statusEl.textContent = selected.status || '-';
              if (endsAtEl) endsAtEl.textContent = selected.period_end_text || '-';
              if (renewEl) renewEl.textContent = selected.auto_renew ? 'เปิด' : 'ปิด';
              const currentTier = String(selected.current_plan_tier || '').trim().toLowerCase();
              planCards.forEach((card) => {{
                const tier = String(card.getAttribute('data-plan-tier') || '').trim().toLowerCase();
                const isCurrent = Boolean(currentTier) && tier === currentTier;
                card.classList.toggle('is-current-plan', isCurrent);
                const badge = card.querySelector('[data-current-plan-badge]');
                if (badge) badge.hidden = !isCurrent;
              }});
            }};

            selector.addEventListener('change', applyGuild);
            applyGuild();
          }})();
        </script>
        """

    body = _render_dashboard_f_template("premium_doc_page.html", locals())
    return _render_layout(title="สมัครแพ็กเกจ SkylineBOT", body=body, session=session)


def _render_guild_picker(session: dict[str, Any], guilds: list[dict[str, Any]], notice: str | None = None) -> str:
    max_members = max([int(item.get("members") or 0) for item in guilds], default=1)
    managed_count = len(guilds)
    managed_members_total = 0
    security_score_total = 0
    health_score_total = 0
    session_user_id = _session_user_id(session)
    ownerbot_mode = _dashboard_ownerbot_mode_enabled(session)
    joined_cards: list[str] = []
    for guild in guilds:
        guild_id = str(guild.get("id") or "").strip()
        guild_icon = str(guild.get("icon") or "").strip() or _discord_default_avatar_url(guild_id or "0")
        guild_icon_fallback = _discord_default_avatar_url(guild_id or "0")
        members = int(guild.get("members") or 0)
        channels = int(guild.get("channels") or 0)
        roles = int(guild.get("roles") or 0)
        health = _guild_health(guild)

        antinuke_row = cache.antinuke_settings.get(guild_id, {}) if hasattr(cache, "antinuke_settings") else {}
        automod_row = cache.automod.get(guild_id, {}) if hasattr(cache, "automod") else {}
        if not isinstance(antinuke_row, dict):
            antinuke_row = {}
        if not isinstance(automod_row, dict):
            automod_row = {}

        security_rules = (
            bool(antinuke_row.get("anti_bot_add")),
            bool(antinuke_row.get("anti_channel_delete")),
            bool(antinuke_row.get("anti_role_delete")),
            bool(antinuke_row.get("anti_webhook_create")),
            bool(antinuke_row.get("anti_everyone_mention")),
            bool(automod_row.get("antilink_enabled")),
            bool(automod_row.get("antispam_enabled")),
            bool(automod_row.get("antibadwords_enabled")),
        )
        security_enabled = sum(1 for flag in security_rules if flag)
        security_score = min(100, 20 + (security_enabled * 10))
        managed_members_total += members
        security_score_total += security_score
        health_score_total += int(health)
        access_level = str(guild.get("_dashboard_access_level") or "").strip().lower()
        access_bits = int(guild.get("_dashboard_permission_bits") or 0)
        if not access_level:
            guild_owner_id_raw = str(guild.get("owner_id") or "").strip()
            guild_owner_id = int(guild_owner_id_raw) if guild_owner_id_raw.isdigit() else 0
            if session_user_id is not None and guild_owner_id == int(session_user_id):
                access_level = "owner"
            elif ownerbot_mode:
                access_level = "ownerbot"
            elif access_bits & ADMINISTRATOR:
                access_level = "admin"
            elif access_bits & MANAGE_GUILD:
                access_level = "authorized"
        access_meta = _dashboard_access_visual_meta(access_level, access_bits)
        guild_access_scopes_html = "".join(
            f'<span class="guild-access-scope">{_escape(scope_label)}</span>'
            for scope_label in list(access_meta.get("scopes") or [])
        )
        guild_access_scopes_block = (
            f'<div class="guild-access-scopes">{guild_access_scopes_html}</div>'
            if guild_access_scopes_html
            else ""
        )
        guild_access_html = (
            f'<div class="guild-access-indicator guild-access-{_escape(access_meta["accent"])}">'
            f'<span class="guild-access-icon"><i class="{_escape(access_meta["icon"])}" aria-hidden="true"></i></span>'
            f'<span class="guild-access-copy"><strong>{_escape(access_meta["label"])}</strong>'
            f'<small>{_escape(access_meta["desc"])}</small></span>'
            f"{guild_access_scopes_block}"
            "</div>"
        )

        joined_cards.append(
            f"""
            <article class="guild-card managed-guild-card" data-managed-guild-card="1" data-guild-id="{_escape(guild_id)}">
              <div class="guild-card-topline">
                <span class="guild-card-tag"><i class="fa-solid fa-sparkles" aria-hidden="true"></i>Managed</span>
                <div class="guild-card-actions">
                  <span class="guild-card-score" aria-label="Security score {security_score}%"><i class="fa-solid fa-shield-halved" aria-hidden="true"></i>{security_score}%</span>
                  <button class="guild-pin-btn" type="button" data-guild-pin-toggle="1" data-guild-id="{_escape(guild_id)}" aria-pressed="false">
                    <i class="fa-regular fa-bookmark" aria-hidden="true"></i>
                    <span>Pin</span>
                  </button>
                </div>
              </div>
              <div class="guild-card-head">
                <img src="{_escape(guild_icon)}" alt="{_escape(guild['name'])}" loading="lazy" onerror="this.onerror=null;this.src='{_escape(guild_icon_fallback)}';">
                <div class="guild-card-copy">
                  <div class="guild-card-title-row">
                    <h3 data-no-auto-i18n="1">{_escape(guild['name'])}</h3>
                    <span class="guild-card-favorite-badge" data-guild-pin-badge hidden>
                      <i class="fa-solid fa-thumbtack" aria-hidden="true"></i>
                      Frequent
                    </span>
                  </div>
                  <p class="muted">Guild ID: {_escape(guild_id)}</p>
                </div>
              </div>
              {guild_access_html}
              <div class="guild-meta guild-meta-rich">
                <span class="mini-stat"><span data-i18n="guild_members_label">Members</span> {members}</span>
                <span class="mini-stat"><span data-i18n="guild_channels_label">Channels</span> {channels}</span>
                <span class="mini-stat"><span data-i18n="guild_roles_label">Roles</span> {roles}</span>
              </div>
              <div class="guild-meter-stack">
                {_render_meter("Member Count", members, max_members, "blue")}
                {_render_meter("Guild Health", health, 100, "green")}
                {_render_meter("Security Score", security_score, 100, "amber")}
              </div>
              <div class="auth-actions" style="justify-content:flex-start; margin-top:12px;">
                <a class="primary-btn" href="/dashboard/guild/{_escape(guild_id)}">Open Dashboard</a>
              </div>
            </article>
            """
        )

    invite_candidates = _invite_candidate_guilds(session)
    invite_count = len(invite_candidates)
    avg_security_score = int(round(security_score_total / managed_count)) if managed_count > 0 else 0
    avg_health_score = int(round(health_score_total / managed_count)) if managed_count > 0 else 0
    invite_cards: list[str] = []
    for guild in invite_candidates:
        guild_id = str(guild.get("id") or "").strip()
        guild_icon = str(guild.get("icon") or "").strip() or _discord_default_avatar_url(guild_id or "0")
        guild_icon_fallback = _discord_default_avatar_url(guild_id or "0")
        invite_cards.append(
            f"""
            <article class="guild-card invite-guild-card">
              <div class="guild-card-topline">
                <span class="guild-card-tag invite">Invite Needed</span>
              </div>
              <div class="guild-card-head">
                <img src="{_escape(guild_icon)}" alt="{_escape(guild['name'])}" loading="lazy" onerror="this.onerror=null;this.src='{_escape(guild_icon_fallback)}';">
                <div class="guild-card-copy">
                  <h3 data-no-auto-i18n="1">{_escape(guild['name'])}</h3>
                  <p class="muted">Guild ID: {_escape(guild_id)}</p>
                </div>
              </div>
              <div class="guild-meta">
                <span class="mini-stat" data-i18n="invite_missing_status">Bot is not in this guild yet</span>
              </div>
              <div class="auth-actions" style="justify-content:flex-start; margin-top:12px;">
                <a class="primary-btn" href="{_escape(guild['invite_url'])}" target="_blank" rel="noopener" data-i18n="invite_missing_action" data-invite-guild-id="{_escape(guild_id)}">Invite Bot</a>
              </div>
            </article>
            """
        )
    show_invite_section = invite_count > 0
    invite_panel_markup = ""
    if show_invite_section:
        invite_panel_markup = f"""
          <section class="panel-sub detail-page-section guild-section-invite">
            <div class="guild-section-head">
              <h2 style="margin-top:0;" data-icon-key="dashboard_invite">Invite SkylineBOT</h2>
              <span class="guild-section-chip invite">
                <i class="fa-solid fa-user-plus" aria-hidden="true"></i>
                {invite_count}
              </span>
            </div>
            <p class="muted" style="margin-top:4px;">Servers where you have admin access but SkylineBOT has not been invited yet.</p>
            <div class="guild-grid" style="margin-top:16px;">
              {''.join(invite_cards)}
            </div>
          </section>
        """
    body = _render_dashboard_f_template("guild_picker.html", locals())
    return _render_layout(title="เซิร์ฟเวอร์ SkylineBOT", body=body, session=session, guilds=guilds, notice=notice)


def _render_invite_hub(session: dict[str, Any], guilds: list[dict[str, Any]], notice: str | None = None) -> str:
    invite_candidates = _invite_candidate_guilds(session)
    invite_cards: list[str] = []
    for guild in invite_candidates:
        invite_cards.append(
            f"""
            <article class="guild-card">
              <div class="guild-card-head">
                <img src="{_escape(guild['icon'])}" alt="{_escape(guild['name'])}">
                <div class="guild-card-copy">
                  <h3 data-no-auto-i18n="1">{_escape(guild['name'])}</h3>
                  <p class="muted">Bot is not in this server yet.</p>
                </div>
              </div>
              <div class="auth-actions" style="justify-content:flex-start; margin-top:10px;">
                <a class="primary-btn" href="{_escape(guild['invite_url'])}" target="_blank" rel="noopener">Invite to Server</a>
              </div>
            </article>
            """
        )

    body = _render_dashboard_f_template("invite_hub.html", locals())
    return _render_layout(
        title="เชิญ SkylineBOT",
        body=body,
        session=session,
        guilds=guilds,
        notice=notice,
    )


def _render_donatebot_hub(
    session: dict[str, Any] | None,
    guilds: list[dict[str, Any]],
    notice: str | None = None,
    *,
    verify_status: str | None = None,
    show_guild_section: bool = True,
    top_donate_rows: list[dict[str, Any]] | None = None,
) -> str:
    cfg = _global_donatebot_settings()
    truemoney_phone = _escape(cfg.get("truemoney_phone") or "-")
    promptpay_number = _escape(cfg.get("promptpay_number") or "-")
    bank_name = _escape(cfg.get("bank_name") or "-")
    bank_account_number = _escape(cfg.get("bank_account_number") or "-")
    bank_account_name = _escape(cfg.get("bank_account_name") or "-")
    support_url = _escape(cfg.get("support_url") or "")
    session_user = dict((session or {}).get("user") or {})
    session_user_id_raw = str(session_user.get("id") or "").strip()
    session_user_name = _clean_text(
        session_user.get("global_name")
        or session_user.get("username")
        or session_user.get("name")
        or ""
    ).strip()[:80]
    session_user_avatar_raw = str(session_user.get("avatar_url") or "").strip()
    is_logged_in = bool(_session_user_id(session))
    session_user_display = _escape(session_user_name or ("Discord member" if is_logged_in else "Guest"))
    session_user_id_html = _escape(session_user_id_raw)
    session_user_avatar_url = _escape(
        _donatebot_safe_avatar_url(
            session_user_avatar_raw,
            seed_value=session_user_id_raw or session_user_name or "session",
        )
    )
    donor_profile_mode = "session" if is_logged_in else "manual"
    donor_profile_label_html = _escape(
        "Signed in: profile will be auto-filled for this verify request."
        if is_logged_in
        else "Guest mode: add Discord ID or name before verify."
    )
    donor_session_hidden_fields_html = ""
    donor_manual_fields_html = ""
    donor_avatar_upload_field_html = """
        <div class="field-item">
          <label>Donor Avatar (Optional)</label>
          <input type="file" name="donor_avatar" accept="image/png,image/jpeg,image/webp,image/gif">
        </div>
    """
    donor_avatar_upload_note_html = _escape(
        "Guest mode: provide Discord ID or donor name. Donor avatar is safety-checked before storing."
    )
    if donor_profile_mode == "session":
        donor_session_hidden_fields_html = (
            f'<input type="hidden" name="donor_name" value="{session_user_display}">'
            f'<input type="hidden" name="donor_discord_id" value="{session_user_id_html}">'
        )
        donor_avatar_upload_field_html = ""
        donor_avatar_upload_note_html = _escape(
            "Signed-in mode: your Discord avatar will be used automatically."
        )
    else:
        donor_manual_fields_html = """
      <div class="field-group donatebot-verify-grid">
        <div class="field-item">
          <label>Discord ID (Guest Mode)</label>
          <input type="text" name="donor_discord_id" maxlength="22" placeholder="e.g. 123456789012345678">
        </div>
        <div class="field-item">
          <label>Donor Name (Optional)</label>
          <input type="text" name="donor_name" maxlength="80" placeholder="e.g. SkylineUser">
        </div>
      </div>
        """

    verify_key = _normalize_donate_slip_status(verify_status) if verify_status else ""
    verify_block = ""
    if verify_key:
        verify_label = _donate_slip_status_label(verify_key)
        verify_hint_map = {
            "approved": "ผ่านการตรวจสอบแล้ว สามารถนำรายการนี้ไปยืนยันต่อได้ทันที",
            "pending": "ระบบกำลังรอผลหรือรอตรวจซ้ำ กรุณาตรวจสอบอีกครั้งภายหลัง",
            "rejected": "ลิงก์ไม่ผ่านการตรวจสอบ โปรดตรวจสอบความถูกต้องของข้อมูล",
        }
        verify_icon_map = {
            "approved": "fa-circle-check",
            "pending": "fa-clock",
            "rejected": "fa-triangle-exclamation",
        }
        verify_hint = _escape(verify_hint_map.get(verify_key, "สถานะไม่ถูกต้อง"))
        verify_icon = _escape(verify_icon_map.get(verify_key, "fa-circle-info"))
        verify_block = (
            f'<div class="panel-sub donatebot-verify-alert is-{verify_key}" role="status" aria-live="polite">'
            f'<span class="donatebot-verify-alert-icon" aria-hidden="true"><i class="fa-solid {verify_icon}"></i></span>'
            f'<div class="donatebot-verify-alert-copy">'
            f'<strong>Latest verify status: {_escape(verify_label)}</strong>'
            f'<span class="muted">{verify_hint}</span>'
            f"</div>"
            f'<span class="slip-status-badge slip-status-{verify_key}">{_escape(verify_label)}</span>'
            f"</div>"
        )

    def _render_top_podium_card(rank: int, row: dict[str, Any] | None) -> str:
        if not isinstance(row, dict):
            return (
                f'<article class="top-donate-podium-card is-rank{rank} is-empty">'
                f'<div class="top-donate-rank-badge">#{rank}</div>'
                f'<div class="top-donate-avatar-wrap"><img src="{_escape(_donatebot_default_avatar_url(rank))}" alt="Top donor slot {rank}"></div>'
                '<h3>Waiting...</h3><p class="top-donate-amount">-</p>'
                '</article>'
            )

        display_name = _escape(row.get("display_name") or "Unknown donor")
        amount_value = max(0, int(row.get("amount_total") or 0))
        donor_id_text = str(row.get("donor_discord_id") or "").strip()
        donor_id_html = _escape(donor_id_text)
        verify_count = max(1, int(row.get("verify_count") or 0))
        verify_count_text = _escape(f"{verify_count} verify")
        avatar_url = _escape(
            _donatebot_safe_avatar_url(
                row.get("avatar_url"),
                seed_value=donor_id_text or row.get("identity_key") or rank,
            )
        )
        return (
            f'<article class="top-donate-podium-card is-rank{rank}">'
            f'<div class="top-donate-rank-badge">#{rank}</div>'
            f'<div class="top-donate-avatar-wrap"><img src="{avatar_url}" alt="{display_name}"></div>'
            f"<h3>{display_name}</h3>"
            f'<p class="top-donate-amount">{_escape(f"{amount_value:,} THB")}</p>'
            f'<p class="top-donate-meta">ID: {donor_id_html or "-"} ยท {verify_count_text}</p>'
            '</article>'
        )

    def _render_top_list_card(row: dict[str, Any]) -> str:
        rank = max(4, int(row.get("rank") or 0))
        display_name = _escape(row.get("display_name") or "Unknown donor")
        amount_value = max(0, int(row.get("amount_total") or 0))
        donor_id_text = str(row.get("donor_discord_id") or "").strip()
        donor_id_html = _escape(donor_id_text)
        avatar_url = _escape(
            _donatebot_safe_avatar_url(
                row.get("avatar_url"),
                seed_value=donor_id_text or row.get("identity_key") or rank,
            )
        )
        return (
            f'<article class="top-donate-list-card" data-rank="{rank}">'
            f'<span class="top-donate-list-rank">#{rank}</span>'
            f'<span class="top-donate-list-avatar"><img src="{avatar_url}" alt="{display_name}"></span>'
            '<span class="top-donate-list-copy">'
            f"<strong>{display_name}</strong>"
            f"<small>ID: {donor_id_html or '-'} </small>"
            '</span>'
            f'<span class="top-donate-list-amount">{_escape(f"{amount_value:,} THB")}</span>'
            '</article>'
        )

    ranking_rows: list[dict[str, Any]] = []
    for raw in list(top_donate_rows or []):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        try:
            row["rank"] = max(1, int(row.get("rank") or (len(ranking_rows) + 1)))
        except Exception:
            row["rank"] = len(ranking_rows) + 1
        ranking_rows.append(row)
    ranking_rows.sort(key=lambda item: int(item.get("rank") or 0))
    rank_map = {
        int(row.get("rank") or 0): row
        for row in ranking_rows
        if int(row.get("rank") or 0) > 0
    }
    top_donate_podium_html = ''.join(
        [
            _render_top_podium_card(2, rank_map.get(2)),
            _render_top_podium_card(1, rank_map.get(1)),
            _render_top_podium_card(3, rank_map.get(3)),
        ]
    )
    top_donate_tail_rows = [row for row in ranking_rows if int(row.get("rank") or 0) >= 4]
    top_donate_list_html = ''.join([_render_top_list_card(row) for row in top_donate_tail_rows[:40]])
    if not top_donate_list_html:
        top_donate_list_html = '<div class="top-donate-empty muted">No ranks 4+ yet. Be the next supporter.</div>'
    top_donate_total_count = len(ranking_rows)

    guild_cards: list[str] = []
    for guild in guilds:
        guild_id = _escape(guild["id"])
        guild_cards.append(
            f"""
            <article class="guild-card">
              <div class="guild-card-head">
                <img src="{_escape(guild['icon'])}" alt="{_escape(guild['name'])}">
                <div class="guild-card-copy">
                  <h3 data-no-auto-i18n="1">{_escape(guild['name'])}</h3>
                  <p class="muted">จัดการ Donate ของกิลด์ และเปิดหน้ารับโดเนตสาธารณะได้ทันที</p>
                </div>
              </div>
              <div class="auth-actions" style="justify-content:flex-start; margin-top:10px; gap:8px; flex-wrap:wrap;">
                <a class="primary-btn" href="/dashboard/guild/{guild_id}/donate">จัดการ Donate กิลด์</a>
                <a class="ghost-btn" href="/dashboard/donate/{guild_id}" target="_blank" rel="noopener">เปิดหน้า Donate กิลด์</a>
              </div>
            </article>
            """
        )

    guild_section = ""
    if show_guild_section:
        if session:
            guild_section = f"""
            <section class="panel" id="donatebot-guilds">
              <h2>Donate กิลด์ (แยกจาก DonateBOT Center)</h2>
              <p class="muted">เลือกกิลด์ที่ต้องการเพื่อเปิดหน้า Donate ของกิลด์นั้น หรือเข้าไปตั้งค่าระบบรับเงิน/ตรวจสลิปได้ทันที</p>
              <p class="muted">จำนวนกิลด์ที่จัดการได้: {_escape(len(guilds))}</p>
              <div class="guild-grid" style="margin-top:14px;">
                {''.join(guild_cards) if guild_cards else '<div class="notice">ยังไม่พบกิลด์ที่คุณมีสิทธิ์จัดการ</div>'}
              </div>
            </section>
            """
        else:
            guild_section = """
            <section class="panel" id="donatebot-guilds">
              <h2>Donate กิลด์</h2>
              <p class="muted">ล็อกอินด้วย Discord เพื่อดูและจัดการหน้ารับโดเนตของแต่ละกิลด์</p>
              <div class="auth-actions" style="justify-content:flex-start; margin-top:10px;">
                <a class="primary-btn" href="/dashboard/login">เข้าสู่ระบบ Discord</a>
              </div>
            </section>
            """

    support_button = (
        f'<a class="ghost-btn" href="{support_url}" target="_blank" rel="noopener">ติดต่อซัพพอร์ต</a>'
        if support_url
        else '<a class="ghost-btn" href="{CONTACT_EXTERNAL_URL}" target="_blank" rel="noopener">ติดต่อทีมงาน</a>'
    )
    admin_logs_button = (
        '<a class="ghost-btn" href="/dashboard/admin/donatebot/verify-logs">ดู Verify Logs (Admin)</a>'
        if _is_dashboard_admin(session)
        else ""
    )

    body = _render_dashboard_f_template("donatebot_hub.html", locals())
    return _render_layout(
        title="โดเนทบอท - SkylineBOT",
        body=body,
        session=session,
        guilds=guilds,
        notice=notice,
    )

def _render_donatebot_verify_logs_admin_page(
    *,
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    total_count: int,
    page: int,
    page_size: int,
    status_filter: str,
    keyword: str,
    notice: str | None = None,
) -> str:
    safe_status = _normalize_donate_slip_status_filter(status_filter)
    safe_keyword = _clean_text(keyword).strip()[:120]
    safe_total = max(0, int(total_count or 0))
    safe_page_size = max(10, min(200, int(page_size or 60)))
    total_pages = max(1, (safe_total + safe_page_size - 1) // safe_page_size) if safe_total else 1
    safe_page = max(1, min(int(page or 1), total_pages))
    start_index = ((safe_page - 1) * safe_page_size) + 1 if safe_total else 0
    end_index = min(safe_total, safe_page * safe_page_size) if safe_total else 0

    status_options = [
        ("", "All statuses"),
        ("approved", "Approved"),
        ("pending", "Pending"),
        ("rejected", "Rejected"),
    ]
    status_select_html = "".join(
        f'<option value="{key}" {"selected" if key == safe_status else ""}>{label}</option>'
        for key, label in status_options
    )

    def _build_page_link(target_page: int) -> str:
        params: dict[str, str | int] = {"page": max(1, int(target_page))}
        if safe_status:
            params["status"] = safe_status
        if safe_keyword:
            params["q"] = safe_keyword
        return f"/dashboard/admin/donatebot/verify-logs?{urlencode(params)}"

    table_rows: list[str] = []
    for row in rows:
        status_key = _normalize_donate_slip_status(row.get("verify_status"))
        status_label = _donate_slip_status_label(status_key)
        status_class = f"slip-status-{status_key}"
        donor_name = _escape(row.get("donor_name") or "Unknown donor")
        amount_value = max(0, int(row.get("amount") or 0))
        amount_text = f"{amount_value:,} THB" if amount_value > 0 else "-"
        note_text = _escape(row.get("verify_note") or "-")
        checked_at = _escape(_format_datetime_th(row.get("checked_at")))
        requester_name = _escape(row.get("requester_global_name") or row.get("requester_username") or "-")
        requester_user_id = str(row.get("requester_user_id") or "").strip()
        requester_suffix = f" (ID: {_escape(requester_user_id)})" if requester_user_id else ""
        requester_admin = bool(row.get("requester_is_admin"))
        requester_badge = (
            '<span class="mini-stat" style="font-size:11px; margin-left:6px;">admin</span>'
            if requester_admin
            else ""
        )
        requester_ip = _escape(row.get("requester_ip") or "-")
        gift_link_raw = str(row.get("gift_link") or "").strip()
        gift_link_preview = _escape(gift_link_raw[:66] + ("..." if len(gift_link_raw) > 66 else ""))
        gift_link_html = (
            f'<a href="{_escape(gift_link_raw)}" target="_blank" rel="noopener">{gift_link_preview or "Open link"}</a>'
            if gift_link_raw.startswith("http://") or gift_link_raw.startswith("https://")
            else (_escape(gift_link_raw) if gift_link_raw else "-")
        )
        table_rows.append(
            f"""
            <tr>
              <td>{checked_at}</td>
              <td><span class="slip-status-badge {status_class}">{_escape(status_label)}</span></td>
              <td>{donor_name}</td>
              <td>{amount_text}</td>
              <td>{gift_link_html}</td>
              <td>{note_text}</td>
              <td>{requester_name}{requester_suffix}{requester_badge}</td>
              <td><code>{requester_ip}</code></td>
            </tr>
            """
        )
    if not table_rows:
        table_rows.append('<tr><td colspan="8" class="muted" style="text-align:center;">No verify logs found</td></tr>')

    prev_button_html = (
        f'<a class="ghost-btn" href="{_escape(_build_page_link(safe_page - 1))}">Previous</a>'
        if safe_page > 1
        else '<button class="ghost-btn" type="button" disabled>Previous</button>'
    )
    next_button_html = (
        f'<a class="ghost-btn" href="{_escape(_build_page_link(safe_page + 1))}">Next</a>'
        if safe_page < total_pages
        else '<button class="ghost-btn" type="button" disabled>Next</button>'
    )

    template_body = _render_dashboard_f_template("donatebot_verify_logs_admin_page.html", locals())

    body = (
        '<link rel="stylesheet" href="/dashboard/static/dashboard/pages/donatebot-verify-logs-admin.css">'
        + template_body
    )
    return _render_layout(
        title="แอดมิน Verify Logs DonateBOT",
        body=body,
        session=session,
        guilds=guilds,
        notice=notice,
    )


from .dashboard_tabs import (
    _overview_metrics,
    _render_overview,
    _render_security,
    _render_music,
    _render_control_panel,
    _render_moderation,
    _render_server_stats,
    _render_donate,
    _render_alerts,
    _render_commands,
    _render_promote,
    _render_temp_links,
    _render_probot_module_hub,
    _render_color_sets,
    _render_reaction_roles,
    _render_starboard,
    _render_customrole,
    _render_embed_messages,
    _render_temp_channels,
    _render_levels,
    _render_economy,
    _render_roleplay,
    _render_screening,
    _render_screening_categories,
    _render_logs,
    _render_giveaways,
    _render_tickets,
    _render_shop,
    _render_welcome,
    _render_leaver,
    _render_ocr,
    _render_verify,
    _render_aichat,
    _render_autoresponder,
    _render_media,
    _render_premium_receive,
    _render_voice_randomizer,
)



















async def _render_public_donate_page(
    guild_id: int,
    *,
    session: dict[str, Any] | None = None,
    notice: str | None = None,
) -> str:
    guild_id = int(guild_id)
    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    guild_name = _escape(getattr(bot_guild, "name", f"Guild {guild_id}"))
    guild_icon = _escape(_guild_icon(bot_guild)) if bot_guild else _escape(style_urls.DEFAULT_MUSIC_BANNER)
    bot_name, bot_avatar = _preview_bot_identity()

    donate_data = (
        cache.donate_settings_cache.get(str(guild_id))
        or await storage.donate_settings.get(guild_id=guild_id)
        or await _get_donate_fallback(guild_id)
        or {}
    )
    slip_logs = await _get_donate_slip_logs(guild_id, limit=80)
    methods_enabled_raw = donate_data.get("methods_enabled") or {}
    methods_enabled = {
        "truemoney": bool(methods_enabled_raw.get("truemoney")),
        "promptpay": bool(methods_enabled_raw.get("promptpay")),
        "bank": bool(methods_enabled_raw.get("bank")),
        "slipverify": bool(methods_enabled_raw.get("slipverify")),
        "goal": bool(methods_enabled_raw.get("goal", True)),
    }
    enabled = bool(donate_data.get("enabled"))

    donation_channel_id = str(donate_data.get("donation_channel_id") or "").strip()
    notification_channel_id = str(donate_data.get("notification_channel_id") or "").strip()
    guild_notification_channel_configured = notification_channel_id.isdigit()
    review_channel_id = str(donate_data.get("slipcheck_review_channel_id") or "").strip()
    guild_review_channel_configured = review_channel_id.isdigit()
    ownerbot_payment_settings = _ownerbot_payment_provider_settings_from_db()
    ownerbot_review_channel_id = str(ownerbot_payment_settings.get("slipcheck_review_channel_id") or "").strip()
    if not notification_channel_id.isdigit() and ownerbot_review_channel_id.isdigit():
        notification_channel_id = ownerbot_review_channel_id
    if not review_channel_id.isdigit() and ownerbot_review_channel_id.isdigit():
        review_channel_id = ownerbot_review_channel_id
    # Keep web slip upload available when admin enables SlipVerify but only sets
    # donation channel (legacy setup): fallback to donation_channel_id.
    slip_destination_channel_id = (
        notification_channel_id
        if notification_channel_id.isdigit()
        else (
            review_channel_id
            if review_channel_id.isdigit()
            else (donation_channel_id if donation_channel_id.isdigit() else "")
        )
    )
    used_ownerbot_channel_fallback = (
        not guild_notification_channel_configured
        and not guild_review_channel_configured
        and ownerbot_review_channel_id.isdigit()
    )
    donation_channel_url = (
        f"https://discord.com/channels/{guild_id}/{donation_channel_id}"
        if donation_channel_id.isdigit()
        else ""
    )
    notify_channel_url = ""
    if slip_destination_channel_id.isdigit():
        notify_channel_guild_id = 0
        if not used_ownerbot_channel_fallback:
            notify_channel_guild_id = int(guild_id)
        if bot:
            try:
                resolved_channel = bot.get_channel(int(slip_destination_channel_id))
            except Exception:
                resolved_channel = None
            resolved_guild_id = int(getattr(getattr(resolved_channel, "guild", None), "id", 0) or 0)
            if resolved_guild_id > 0:
                notify_channel_guild_id = resolved_guild_id
        if notify_channel_guild_id > 0:
            notify_channel_url = f"https://discord.com/channels/{notify_channel_guild_id}/{slip_destination_channel_id}"

    color = str(donate_data.get("color") or "#6b8cff").strip()
    if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
        color = "#6b8cff"

    truemoney_phone_raw = str(donate_data.get("truemoney_phone") or "").strip()
    promptpay_number_raw = str(donate_data.get("promptpay_number") or "").strip()
    truemoney_phone = _escape(truemoney_phone_raw)
    promptpay_number = _escape(promptpay_number_raw)
    promptpay_number_js = json.dumps(promptpay_number_raw, ensure_ascii=False)
    truemoney_phone_js = json.dumps(truemoney_phone_raw, ensure_ascii=False)
    bank_name_raw = str(donate_data.get("bank_name") or "").strip()
    bank_account_number_raw = str(donate_data.get("bank_account_number") or "").strip()
    bank_account_name_raw = str(donate_data.get("bank_account_name") or "").strip()
    bank_name = _escape(bank_name_raw)
    bank_account_number = _escape(bank_account_number_raw)
    bank_account_name = _escape(bank_account_name_raw)
    desc_web = _escape(
        donate_data.get("desc_web")
        or donate_data.get("desc_discord")
        or "Choose a donation method and support this server instantly."
    )
    image_url = _escape(donate_data.get("image_url") or "")

    goal_enabled = bool(methods_enabled.get("goal", True))
    goal_title = _escape((donate_data.get("goal_title") or "Donation Goal").strip() or "Donation Goal")
    goal_start = int(donate_data.get("goal_start_amount") or 0)
    goal_end = int(donate_data.get("goal_end_amount") or 0)
    goal_current = int(donate_data.get("goal_current_amount") or goal_start)
    goal_range = max(0, goal_end - goal_start)
    goal_progress_pct = 0
    if goal_range > 0:
        goal_progress_pct = int(max(0, min(100, round(((goal_current - goal_start) / goal_range) * 100))))

    donation_status = "Open for donations" if enabled else "Donations are closed"
    donation_status_color = "#4ade80" if enabled else "#f87171"
    guild_state = cache.guilds.get(str(guild_id), {}) or {}
    raw_plan_tier = _normalize_plan_tier(guild_state.get("subscription", "free"))
    premium_active = _looks_like_active_premium_from_state(guild_state)
    effective_plan_tier = raw_plan_tier if (raw_plan_tier == "free" or premium_active) else "free"
    plan_display_name = _escape(_plan_display_name(effective_plan_tier))
    is_free_plan = effective_plan_tier == "free"

    ads_enabled_for_free = bool(getattr(BOT_CONFIG, "DONATE_FREE_ADS_ENABLED", True))
    adsense_client_id_raw = str(getattr(BOT_CONFIG, "GOOGLE_ADSENSE_CLIENT_ID", "") or "").strip()
    adsense_slot_raw = str(getattr(BOT_CONFIG, "GOOGLE_ADSENSE_DONATE_SLOT", "") or "").strip()
    has_adsense_config = bool(adsense_client_id_raw and adsense_slot_raw)
    should_show_google_ads = bool(enabled and is_free_plan and ads_enabled_for_free and has_adsense_config)
    if not is_free_plan:
        ads_policy_badge_html = '<span class="mini-stat" style="border-color:rgba(74,222,128,.4);color:#86efac;">Premium: No Ads</span>'
    elif not ads_enabled_for_free:
        ads_policy_badge_html = '<span class="mini-stat">Free Plan: Ads disabled globally</span>'
    elif should_show_google_ads:
        ads_policy_badge_html = '<span class="mini-stat">Free Plan: Ads enabled</span>'
    else:
        ads_policy_badge_html = '<span class="mini-stat">Free Plan: Ads not configured</span>'
    ads_section_html = ""
    if should_show_google_ads:
        ads_client = _escape(adsense_client_id_raw)
        ads_slot = _escape(adsense_slot_raw)
        ads_section_html = _render_dashboard_f_template("donate_ads_google.html", locals())

    truemoney_ready = methods_enabled.get("truemoney", False) and bool(truemoney_phone_raw)
    promptpay_ready = methods_enabled.get("promptpay", False) and bool(promptpay_number_raw)
    bank_ready = methods_enabled.get("bank", False) and bool(
        bank_name_raw or bank_account_number_raw or bank_account_name_raw
    )
    slipverify_enabled = methods_enabled.get("slipverify", False)
    slipverify_ready = slipverify_enabled and bool(slip_destination_channel_id)
    slipverify_channel_label = (
        f"#{slip_destination_channel_id}"
        if slip_destination_channel_id.isdigit()
        else "Not configured"
    )

    method_theme_map = {
        "promptpay": {
            "label": "PromptPay",
            "icon": "fa-solid fa-qrcode",
            "tone_class": "tone-promptpay",
            "color": "#4f7dff",
            "color2": "#22d3ee",
        },
        "truemoney": {
            "label": "TrueMoney Wallet",
            "icon": "fa-solid fa-mobile-screen-button",
            "tone_class": "tone-truemoney",
            "color": "#f97316",
            "color2": "#fb7185",
        },
        "bank": {
            "label": "Bank Transfer",
            "icon": "fa-solid fa-building-columns",
            "tone_class": "tone-bank",
            "color": "#22c55e",
            "color2": "#84cc16",
        },
        "slipverify": {
            "label": "SlipVerify",
            "icon": "fa-solid fa-receipt",
            "tone_class": "tone-slipverify",
            "color": "#8b5cf6",
            "color2": "#a78bfa",
        },
    }
    method_theme_map_json = json.dumps(method_theme_map, ensure_ascii=False)

    method_cards: list[str] = []
    info_method_keys: list[str] = []

    if truemoney_ready:
        info_method_keys.append("truemoney")
        method_cards.append(
            f"""
            <article class="donate-method-card donate-method-item tone-truemoney is-ready" data-method="truemoney" data-ready="1">
              <div class="donate-method-head">
                <span class="donate-method-icon"><i class="fa-solid fa-mobile-screen-button" aria-hidden="true"></i></span>
                <div class="donate-method-copy">
                  <h3>TrueMoney Wallet</h3>
                  <p class="muted">Wallet number for transfer</p>
                </div>
                <span class="donate-method-state ok">พร้อมใช้งาน</span>
              </div>
              <div class="donate-method-value">{truemoney_phone}</div>
              <div class="auth-actions" style="justify-content:flex-start;gap:8px;">
                <button class="ghost-btn donate-copy-btn" type="button" data-copy="{truemoney_phone}">Copy Number</button>
                <button class="primary-btn donate-jump-method" type="button" data-method="truemoney">Generate QR</button>
              </div>
            </article>
            """
        )
    elif methods_enabled.get("truemoney"):
        info_method_keys.append("truemoney")
        method_cards.append(
            """
            <article class="donate-method-card donate-method-item tone-truemoney is-not-ready" data-method="truemoney" data-ready="0">
              <div class="donate-method-head">
                <span class="donate-method-icon"><i class="fa-solid fa-mobile-screen-button" aria-hidden="true"></i></span>
                <div class="donate-method-copy">
                  <h3>TrueMoney Wallet</h3>
                  <p class="muted">Not ready: wallet number has not been configured yet.</p>
                </div>
                <span class="donate-method-state warn">ยังไม่พร้อม</span>
              </div>
            </article>
            """
        )

    if promptpay_ready:
        info_method_keys.append("promptpay")
        method_cards.append(
            f"""
            <article class="donate-method-card donate-method-item tone-promptpay is-ready" data-method="promptpay" data-ready="1">
              <div class="donate-method-head">
                <span class="donate-method-icon"><i class="fa-solid fa-qrcode" aria-hidden="true"></i></span>
                <div class="donate-method-copy">
                  <h3>PromptPay</h3>
                  <p class="muted">PromptPay number</p>
                </div>
                <span class="donate-method-state ok">พร้อมใช้งาน</span>
              </div>
              <div class="donate-method-value">{promptpay_number}</div>
              <div class="auth-actions" style="justify-content:flex-start;gap:8px;">
                <button class="ghost-btn donate-copy-btn" type="button" data-copy="{promptpay_number}">Copy Number</button>
                <button class="primary-btn donate-jump-method" type="button" data-method="promptpay">Create QR</button>
              </div>
            </article>
            """
        )
    elif methods_enabled.get("promptpay"):
        info_method_keys.append("promptpay")
        method_cards.append(
            """
            <article class="donate-method-card donate-method-item tone-promptpay is-not-ready" data-method="promptpay" data-ready="0">
              <div class="donate-method-head">
                <span class="donate-method-icon"><i class="fa-solid fa-qrcode" aria-hidden="true"></i></span>
                <div class="donate-method-copy">
                  <h3>PromptPay</h3>
                  <p class="muted">Not ready: PromptPay number has not been configured yet.</p>
                </div>
                <span class="donate-method-state warn">ยังไม่พร้อม</span>
              </div>
            </article>
            """
        )

    if bank_ready:
        info_method_keys.append("bank")
        method_cards.append(
            f"""
            <article class="donate-method-card donate-method-item tone-bank is-ready" data-method="bank" data-ready="1">
              <div class="donate-method-head">
                <span class="donate-method-icon"><i class="fa-solid fa-building-columns" aria-hidden="true"></i></span>
                <div class="donate-method-copy">
                  <h3>Bank Transfer</h3>
                  <p class="muted">Manual transfer with account details</p>
                </div>
                <span class="donate-method-state ok">พร้อมใช้งาน</span>
              </div>
              <p class="muted">Bank Name</p>
              <div class="donate-method-value">{bank_name or '-'}</div>
              <p class="muted" style="margin-top:8px;">Account Number</p>
              <div class="donate-method-value">{bank_account_number or '-'}</div>
              <p class="muted" style="margin-top:8px;">Account Name</p>
              <div class="donate-method-value">{bank_account_name or '-'}</div>
            </article>
            """
        )
    elif methods_enabled.get("bank"):
        info_method_keys.append("bank")
        method_cards.append(
            """
            <article class="donate-method-card donate-method-item tone-bank is-not-ready" data-method="bank" data-ready="0">
              <div class="donate-method-head">
                <span class="donate-method-icon"><i class="fa-solid fa-building-columns" aria-hidden="true"></i></span>
                <div class="donate-method-copy">
                  <h3>Bank Transfer</h3>
                  <p class="muted">Not ready: bank account details have not been configured yet.</p>
                </div>
                <span class="donate-method-state warn">ยังไม่พร้อม</span>
              </div>
            </article>
            """
        )

    if slipverify_enabled:
        info_method_keys.append("slipverify")
        verify_link = (
            f'<a class="ghost-btn" href="{_escape(notify_channel_url)}" target="_blank" rel="noopener">Open Slip Review Channel</a>'
            if notify_channel_url
            else ""
        )
        method_cards.append(
            f"""
            <article class="donate-method-card donate-method-item tone-slipverify {'is-ready' if slipverify_ready else 'is-not-ready'}" data-method="slipverify" data-ready="{'1' if slipverify_ready else '0'}">
              <div class="donate-method-head">
                <span class="donate-method-icon"><i class="fa-solid fa-receipt" aria-hidden="true"></i></span>
                <div class="donate-method-copy">
                  <h3>SlipVerify</h3>
                  <p class="muted">Upload slip or payment evidence for admin review.</p>
                </div>
                <span class="donate-method-state {'ok' if slipverify_ready else 'warn'}">{'พร้อมใช้งาน' if slipverify_ready else 'ยังไม่พร้อม'}</span>
              </div>
              <p class="muted">Destination: {slipverify_channel_label}</p>
              {verify_link}
            </article>
            """
        )

    if not method_cards:
        method_cards.append(
            """
            <article class="donate-method-card donate-method-item" data-method="">
              <h3>No active donation methods</h3>
              <p class="muted">The server admin has not enabled donation methods yet.</p>
            </article>
            """
        )
    method_cards_html = "".join(method_cards)

    selector_labels = {
        "promptpay": "PromptPay",
        "truemoney": "TrueMoney",
        "bank": "Bank",
        "slipverify": "SlipVerify",
    }
    default_selected_method = (
        "promptpay"
        if "promptpay" in info_method_keys
        else (info_method_keys[0] if info_method_keys else "")
    )
    method_selector_buttons: list[str] = []
    for method_key in info_method_keys:
        label = _escape(selector_labels.get(method_key, method_key.title()))
        icon = _escape(str((method_theme_map.get(method_key) or {}).get("icon") or "fa-solid fa-circle"))
        tone_class = _escape(str((method_theme_map.get(method_key) or {}).get("tone_class") or ""))
        method_selector_buttons.append(
            f'<button type="button" class="ghost-btn donate-method-select-btn {tone_class}" data-method="{method_key}"><i class="{icon}" aria-hidden="true"></i><span>{label}</span></button>'
        )
    method_selector_html = ""
    if method_selector_buttons:
        method_selector_html = f"""
        <div class="donate-method-select-wrap">
          <div class="donate-method-select-bar">
            {"".join(method_selector_buttons)}
          </div>
          <p class="muted donate-method-select-note">Select a payment channel to show only that channel's details.</p>
        </div>
        """

    donate_channel_button = (
        f'<a class="primary-btn" href="{_escape(donation_channel_url)}" target="_blank" rel="noopener">Open Donation Channel in Discord</a>'
        if donation_channel_url
        else ""
    )

    goal_block = ""
    if goal_enabled:
        goal_block = f"""
        <section class="panel donate-goal-panel">
          <h2>{goal_title}</h2>
          <div class="donate-goal-progress"><span style="width:{goal_progress_pct}%; background:{_escape(color)};"></span></div>
          <div class="donate-goal-meta">
            <span>Start {goal_start:,}</span>
            <strong>{goal_current:,}</strong>
            <span>Goal {goal_end:,}</span>
          </div>
        </section>
        """

    payment_method_labels = {
        "promptpay": "PromptPay",
        "truemoney": "TrueMoney Wallet",
        "bank": "Bank",
        "slipverify": "SlipVerify",
        "other": "Other",
    }
    selectable_methods = {
        "promptpay": promptpay_ready,
        "truemoney": truemoney_ready,
        "bank": bank_ready,
        "slipverify": slipverify_enabled,
    }
    payment_method_options: list[str] = []
    for method_key in ("promptpay", "truemoney", "bank", "slipverify"):
        if selectable_methods.get(method_key):
            payment_method_options.append(
                f'<option value="{method_key}">{_escape(payment_method_labels.get(method_key, method_key))}</option>'
            )
    if not payment_method_options:
        payment_method_options.append('<option value="other">Other</option>')

    qr_method_options: list[str] = []
    if promptpay_ready:
        qr_method_options.append('<option value="promptpay">PromptPay</option>')
    if truemoney_ready:
        qr_method_options.append('<option value="truemoney">TrueMoney Wallet</option>')
    if not qr_method_options:
        if methods_enabled.get("promptpay"):
            qr_method_options.append('<option value="promptpay">PromptPay</option>')
        elif methods_enabled.get("truemoney"):
            qr_method_options.append('<option value="truemoney">TrueMoney Wallet</option>')
        else:
            qr_method_options.append('<option value="">No QR channels</option>')

    method_button_labels = {
        "promptpay": "PromptPay",
        "truemoney": "TrueMoney Wallet",
        "bank": "Bank",
        "slipverify": "SlipVerify",
    }
    method_flow_buttons: list[str] = []
    method_flow_keys: list[str] = []
    for method_key in ("promptpay", "truemoney", "bank", "slipverify"):
        if selectable_methods.get(method_key):
            method_flow_keys.append(method_key)
            flow_icon = _escape(str((method_theme_map.get(method_key) or {}).get("icon") or "fa-solid fa-circle"))
            flow_tone = _escape(str((method_theme_map.get(method_key) or {}).get("tone_class") or ""))
            method_flow_buttons.append(
                f'<button type="button" class="ghost-btn donate-flow-method {flow_tone}" data-method="{method_key}"><i class="{flow_icon}" aria-hidden="true"></i><span>{_escape(method_button_labels.get(method_key, method_key))}</span></button>'
            )

    show_method_flow = enabled and bool(method_flow_buttons)
    default_flow_method = (
        "promptpay"
        if "promptpay" in method_flow_keys
        else ("truemoney" if "truemoney" in method_flow_keys else (method_flow_keys[0] if method_flow_keys else ""))
    )
    allow_slip_upload = enabled and slipverify_enabled and bool(slip_destination_channel_id)

    slip_upload_block = ""
    if show_method_flow:
        slip_upload_block += f"""
        <section class="panel donate-slip-panel">
          <h2 style="margin-top:0;">Create Payment Step</h2>
          <p class="muted">Choose a channel, enter required info for that channel, then submit slip/evidence in the next section.</p>
          <div class="panel-sub" id="donateMethodFlowWrap" style="margin-bottom:12px;">
            <h3 style="margin:0 0 8px;">Choose Payment Channel</h3>
            <div class="auth-actions" style="justify-content:flex-start; gap:8px; margin-bottom:10px;">
              {"".join(method_flow_buttons)}
            </div>
            <input type="hidden" id="donateFlowSelectedMethod" value="{_escape(default_flow_method)}">
            <div id="donateFlowPromptPayPanel" style="display:none;">
              <div class="field-group" style="margin-bottom:8px;">
                <div class="field-item">
                  <label>Amount (THB)</label>
                  <input type="number" id="donateQrAmount" min="1" step="1" placeholder="Enter amount">
                </div>
                <div class="field-item">
                  <label>QR Channel</label>
                  <select id="donateQrMethod">
                    {"".join(qr_method_options)}
                  </select>
                </div>
              </div>
              <div class="auth-actions" style="justify-content:flex-start;gap:8px;">
                <button type="button" class="primary-btn" id="donateQrSaveBtn">Generate QR Code</button>
              </div>
              <div id="donateFlowActionHint" class="donate-action-hint muted" style="margin-top:8px;">Enter amount and generate QR.</div>
              <div id="donateQrWrap" style="display:none; margin-top:10px;">
                <img id="donateQrImage" alt="promptpay-qr" style="width:220px;height:220px;border-radius:12px;border:1px solid var(--line);object-fit:cover;">
              </div>
            </div>
            <div id="donateFlowTrueMoneyPanel" style="display:none;">
              <div class="field-item" style="margin-bottom:8px;">
                <label>TrueMoney Gift Link</label>
                <input type="url" id="donateGiftLinkInput" placeholder="https://gift.truemoney.com/campaign/?v=...">
                <span id="donateGiftValidationHint" class="muted" style="font-size:12px;">Paste gift link and validate before submit.</span>
              </div>
              <div class="auth-actions" style="justify-content:flex-start; gap:8px;">
                <button type="button" class="ghost-btn" id="donateGiftValidateBtn">Validate Link</button>
                <button type="button" class="primary-btn" id="donateGiftApplyBtn">Use Link in Slip Form</button>
              </div>
            </div>
            <div class="donate-flow-required-box">
              <strong>Required fields for selected channel</strong>
              <ul id="donateFlowRequiredList" class="donate-flow-required-list"></ul>
            </div>
          </div>
        </section>
        """

    if allow_slip_upload:
        slip_upload_block += f"""
        <section class="panel donate-slip-panel">
          <h2 style="margin-top:0;">Smart Donate Verification</h2>
          <p class="muted">Upload slip image or paste a TrueMoney gift link (at least one is required). The bot will post an embed to your configured review channel.</p>
          <form method="post" action="/dashboard/guild/{guild_id}/donate/slip" enctype="multipart/form-data" id="donateSlipForm">
            <div class="field-group">
              <div class="field-item">
                <label>Donor Name (optional)</label>
                <input type="text" name="donor_name" maxlength="80" placeholder="e.g. SkylineUser">
              </div>
              <div class="field-item">
                <label>Donor Avatar URL (optional)</label>
                <input type="url" name="donor_avatar_url" maxlength="1600" placeholder="https://example.com/avatar.png">
              </div>
              <div class="field-item">
                <label>Amount</label>
                <input type="number" name="amount" min="1" max="100000000" step="1" required placeholder="e.g. 50" id="donateSlipAmountInput">
              </div>
              <div class="field-item">
                <label>Payment Method</label>
                <select name="payment_method" id="donateSlipMethod">
                  {"".join(payment_method_options)}
                </select>
              </div>
            </div>
            <div class="field-item">
              <label>Evidence Type</label>
              <select name="evidence_type" id="donateEvidenceTypeSelect">
                <option value="auto">Auto (Gift Link or Slip)</option>
                <option value="gift">TrueMoney Gift Link</option>
                <option value="slip">Slip File</option>
              </select>
              <span class="muted" id="donateEvidenceTypeHint" style="font-size:12px;">Select preferred evidence type. Auto allows either one.</span>
            </div>
            <div class="field-item">
              <label>TrueMoney Gift Link (optional)</label>
              <input type="url" name="transfer_link" placeholder="https://gift.truemoney.com/campaign/?v=..." id="donateTransferLinkInput">
            </div>
            <div class="field-item">
              <label>Message to Owner (optional)</label>
              <textarea name="message" rows="3" maxlength="500" placeholder="e.g. Great system"></textarea>
            </div>
            <div class="field-item">
              <label>Slip File</label>
              <input type="file" name="slip_file" id="publicDonateSlipFile" accept=".png,.jpg,.jpeg,.webp">
              <span class="muted" id="publicDonateSlipFileLabel" style="font-size:12px;">Supports png/jpg/jpeg/webp</span>
            </div>
            <div class="auth-actions" style="justify-content:flex-start;">
              <button type="submit" class="primary-btn">Send Verification Embed</button>
              <a class="ghost-btn" href="{_escape(notify_channel_url)}" target="_blank" rel="noopener">Open Review Channel</a>
            </div>
          </form>
        </section>
        """
    elif slipverify_enabled:
        slip_upload_block += """
        <section class="panel donate-slip-panel">
          <h2 style="margin-top:0;">Slip Submit via Web</h2>
          <p class="muted">Admin has not configured a destination/review channel yet (Guild Donate page or OwnerBot Payment page), so web slip submission is unavailable.</p>
        </section>
        """

    public_slip_rows: list[str] = []
    for row in slip_logs[:60]:
        created_at = _format_datetime_display(_safe_parse_datetime(row.get("created_at")))
        status_key = _normalize_donate_slip_status(row.get("status"))
        status_label = _donate_slip_status_label(status_key)
        status_class = f"slip-status-{status_key}"
        donor_name = _escape(row.get("donor_name") or "Unknown")
        amount = int(row.get("amount") or 0)
        public_slip_rows.append(
            f"""
            <tr>
              <td>{created_at}</td>
              <td>{donor_name}</td>
              <td>{amount:,}</td>
              <td><span class="slip-status-badge {status_class}">{status_label}</span></td>
            </tr>
            """
        )
    public_slip_table_html = (
        "".join(public_slip_rows)
        if public_slip_rows
        else '<tr><td colspan="4" class="muted">No recent slip records.</td></tr>'
    )

    donate_css_url = _escape(
        _with_cache_bust("/dashboard/static/dashboard/pages/donate_2.css", bucket_seconds=300)
    )
    body = _render_dashboard_f_template("donate_public_page.html", locals())
    page_title = f"SkylineBOT Donate - {guild_name}"
    return _render_layout(title=page_title, body=body, session=session, notice=notice)

def _oauth_authorize_url(
    *,
    redirect_path: str | None = None,
    request: Request | None = None,
    callback_url_override: str | None = None,
) -> str:
    state_payload: dict[str, str] = {}
    safe_redirect = str(redirect_path or "").strip()
    if safe_redirect:
        state_payload["redirect_path"] = safe_redirect
    callback_url = _dashboard_callback_url(request=request, base_url_override=callback_url_override)
    state_payload["callback_url"] = callback_url
    query = urlencode(
        {
            "client_id": BOT_CONFIG.DISCORD_CLIENT_ID,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "identify guilds guilds.join",
            "prompt": "consent",
            "state": create_oauth_state(state_payload or None),
        }
    )
    return f"https://discord.com/oauth2/authorize?{query}"


async def _discord_api_request(url: str, token: str) -> dict[str, Any] | list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()


async def _exchange_code(code: str, callback_url: str | None = None) -> dict[str, Any]:
    resolved_callback_url = _dashboard_callback_url(base_url_override=callback_url)
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": BOT_CONFIG.DISCORD_CLIENT_ID,
                "client_secret": BOT_CONFIG.DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": resolved_callback_url,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
            except Exception:
                payload = None
            if isinstance(payload, dict):
                error_code = str(payload.get("error") or "").strip()
                error_description = str(payload.get("error_description") or "").strip()
                detail_parts = [part for part in (error_code, error_description) if part]
                detail = " | ".join(detail_parts)
            if not detail:
                detail = str(response.text or "").strip()[:300]
            raise RuntimeError(
                f"Discord OAuth token exchange failed ({response.status_code}): {detail or 'unknown error'}"
            )
        return response.json()


async def _load_oauth_profile(code: str, callback_url: str | None = None) -> dict[str, Any]:
    token_payload = await _exchange_code(code, callback_url=callback_url)
    access_token = token_payload["access_token"]
    user = await _discord_api_request(f"{DISCORD_API}/users/@me", access_token)
    guilds = await _discord_api_request(f"{DISCORD_API}/users/@me/guilds", access_token)
    avatar_hash = user.get("avatar")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{user['id']}/{avatar_hash}.png?size=128"
        if avatar_hash
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )
    return {
        "access_token": access_token,
        "created_at": int(time.time()),
        "user": {
            "id": user["id"],
            "username": user.get("username", "Discord User"),
            "global_name": user.get("global_name"),
            "avatar_url": avatar_url,
        },
        "guilds": guilds,
    }
def _pricing_table_html() -> str:
    return """
    <div class="pricing-grid" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 24px; margin: 40px 0;">
      <div class="pricing-card" style="background: var(--panel); padding: 30px; border-radius: 20px; border: 1px solid var(--brand); box-shadow: 0 0 20px var(--focus); position: relative;">
        <div style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: var(--brand); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold;">Current Plan</div>
        <h3 style="font-size: 1.5rem; margin-bottom: 10px;">Free</h3>
        <strong style="font-size: 1.5rem; color: var(--brand);">0 THB <small style="font-size: 0.9rem; color: var(--muted); font-weight: normal;">/ 30 วัน</small></strong>
        <p class="muted" style="font-size: 0.9rem; margin: 16px 0 20px;">เหมาะสำหรับเซิร์ฟเวอร์เริ่มต้นและใช้งานฟีเจอร์พื้นฐาน</p>
        <ul style="list-style: none; padding: 0; margin-bottom: 30px; line-height: 2;">
          <li> ใช้งานคำสั่งพื้นฐาน</li>
          <li> ระบบตั้งค่าเซิร์ฟเวอร์หลัก</li>
          <li> เหมาะสำหรับเริ่มต้นใช้งาน</li>
          <li> ใช้งานได้ทันทีโดยไม่ต้องสมัครแพ็กเกจ</li>
        </ul>
      </div>
      
      <div class="pricing-card" style="background: var(--panel); padding: 30px; border-radius: 20px; border: 1px solid rgba(240,191,71,.38);">
        <h3 style="font-size: 1.5rem; margin-bottom: 10px;">Silver</h3>
        <strong style="font-size: 1.5rem; color: #f6d47a;">40 THB <small style="font-size: 0.9rem; color: var(--muted); font-weight: normal;">/ 30 วัน</small></strong>
        <p class="muted" style="font-size: 0.9rem; margin: 16px 0 20px;">ปลดล็อกฟีเจอร์พรีเมียมหลัก เช่น ระบบเพลงและระบบขั้นสูง</p>
        <ul style="list-style: none; padding: 0; margin-bottom: 30px; line-height: 2;">
          <li> ปลดล็อกฟีเจอร์ระดับ Silver</li>
          <li> เพิ่มขีดจำกัดการตั้งค่าหลัก</li>
          <li> รองรับระบบเพลง/ลิงก์มากขึ้น</li>
        </ul>
        <span class="primary-btn" style="display:inline-flex; align-items:center; justify-content:center; padding: 10px 16px; font-size: 0.9rem;">เลือกแพ็กเกจนี้</span>
      </div>

      <div class="pricing-card" style="background: var(--panel); padding: 30px; border-radius: 20px; border: 1px solid #ff6b6b;">
        <h3 style="font-size: 1.5rem; margin-bottom: 10px;">Gole</h3>
        <strong style="font-size: 1.5rem; color: #ffb347;">120 THB <small style="font-size: 0.9rem; color: var(--muted); font-weight: normal;">/ 30 วัน</small></strong>
        <p class="muted" style="font-size: 0.9rem; margin: 16px 0 20px;">เพิ่มขีดจำกัดและสิทธิ์การใช้งานสำหรับชุมชนขนาดกลาง</p>
        <ul style="list-style: none; padding: 0; margin-bottom: 30px; line-height: 2;">
          <li> ปลดล็อกฟีเจอร์ระดับ Gole</li>
          <li> ขีดจำกัดสูงขึ้นจาก Silver</li>
          <li> เหมาะกับชุมชนที่เติบโตต่อเนื่อง</li>
        </ul>
        <span class="primary-btn" style="display:inline-flex; align-items:center; justify-content:center; padding: 10px 16px; font-size: 0.9rem;">เลือกแพ็กเกจนี้</span>
      </div>

      <div class="pricing-card" style="background: var(--panel); padding: 30px; border-radius: 20px; border: 1px solid #ffcc33; box-shadow: 0 0 30px rgba(255,204,51,0.15);">
        <h3 style="font-size: 1.5rem; margin-bottom: 10px;">Diamond</h3>
        <strong style="font-size: 1.5rem; color: #ffcc33;">250 THB <small style="font-size: 0.9rem; color: var(--muted); font-weight: normal;">/ 30 วัน</small></strong>
        <p class="muted" style="font-size: 0.9rem; margin: 16px 0 20px;">แพ็กเกจสูงสุดสำหรับชุมชนขนาดใหญ่และงานที่ต้องการสิทธิ์เต็ม</p>
        <ul style="list-style: none; padding: 0; margin-bottom: 30px; line-height: 2;">
          <li> ปลดล็อกฟีเจอร์ทั้งหมด</li>
          <li> ขีดจำกัดสูงสุดของระบบ</li>
          <li> เหมาะสำหรับงานโปรดักชันเต็มรูปแบบ</li>
        </ul>
        <span class="primary-btn" style="display:inline-flex; align-items:center; justify-content:center; padding: 10px 16px; font-size: 0.9rem;">เลือกแพ็กเกจนี้</span>
      </div>

      <div class="pricing-card" style="background: var(--panel); padding: 30px; border-radius: 20px; border: 1px solid #ff8ae2; box-shadow: 0 0 30px rgba(255,138,226,0.18);">
        <h3 style="font-size: 1.5rem; margin-bottom: 10px;">Permanent</h3>
        <strong style="font-size: 1.5rem; color: #ff8ae2;">500 THB <small style="font-size: 0.9rem; color: var(--muted); font-weight: normal;">/ Lifetime</small></strong>
        <p class="muted" style="font-size: 0.9rem; margin: 16px 0 20px;">จ่ายครั้งเดียว ใช้งานถาวร พร้อมสิทธิ์ฟีเจอร์พรีเมียมใหม่ในอนาคต</p>
        <ul style="list-style: none; padding: 0; margin-bottom: 30px; line-height: 2;">
          <li> สิทธิ์ครบทุกระบบ</li>
          <li> รวมสิทธิ์ฟีเจอร์ใหม่ที่เพิ่มในอนาคต</li>
          <li> ไม่มีรอบต่ออายุรายเดือน</li>
        </ul>
        <span class="primary-btn" style="display:inline-flex; align-items:center; justify-content:center; padding: 10px 16px; font-size: 0.9rem;">เลือกแพ็กเกจนี้</span>
      </div>
    </div>
    """

def _render_pricing_locked(session: dict[str, Any], guilds: list[dict[str, Any]], current_guild: dict[str, Any], tab_slug: str, state: dict[str, Any] = None) -> str:
    preview_html = ""

    body = _render_dashboard_f_template("pricing_locked.html", locals())
    return _render_layout(title="ต้องใช้พรีเมียม - SkylineBOT", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab=tab_slug)


def _render_ownerbot_runtime_blocked(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    guild_id: int,
    notice: str,
) -> str:
    invite_url = _bot_invite_url(guild_id)
    body = _render_dashboard_f_template("ownerbot_runtime_blocked.html", locals())
    return _render_layout(
        title="ล็อกโหมด OwnerBOT",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=None,
        notice=notice,
    )


def _dashboard_access_notice_from_state(state: dict[str, Any] | None) -> str:
    return _dashboard_security_domain.dashboard_access_notice_from_state(state)

def _dashboard_can_edit_settings_from_state(state: dict[str, Any] | None) -> bool:
    return _dashboard_security_domain.dashboard_can_edit_settings_from_state(state)

def _render_dashboard_access_blocked(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    guild_id: int,
    notice: str | None = None,
) -> str:
    invite_url = _bot_invite_url(guild_id)
    display_notice = str(notice or "").strip() or _dashboard_access_notice_from_state(None)
    body = _render_dashboard_f_template("dashboard_access_blocked.html", locals())
    return _render_layout(
        title="ไม่มีสิทธิ์การตั้งค่ากิลด์",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=None,
        notice=display_notice,
    )


def _blocked_context_redirect_or_dashboard(
    *,
    session: dict[str, Any] | None,
    current_guild: dict[str, Any] | None,
    state: dict[str, Any] | None,
    guild_id: int,
    request: Request | None = None,
    tab_slug: str | None = None,
) -> Any:
    return _dashboard_security_domain.blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug=tab_slug,
        dashboard_can_edit_settings_fn=_dashboard_can_edit_settings_from_state,
        dashboard_access_notice_fn=_dashboard_access_notice_from_state,
        ownerbot_tab_block_reason_fn=_ownerbot_dashboard_tab_block_reason,
        ownerbot_runtime_notice_fn=_ownerbot_runtime_notice_from_state,
        redirect_response_cls=RedirectResponse,
        urlencode_fn=urlencode,
    )

def _escape(value: Any) -> str:
    return _DASHBOARD_RENDER_HELPERS.escape(value)


def _load_dashboard_layout_template() -> str:
    return _DASHBOARD_RENDER_HELPERS.load_layout_template()


def _load_dashboard_page_template(template_name: str) -> str:
    return _DASHBOARD_RENDER_HELPERS.load_page_template(template_name)


def _render_dashboard_f_template(template_name: str, context: dict[str, Any]) -> str:
    return _DASHBOARD_RENDER_HELPERS.render_f_template(
        template_name,
        context,
        globals_scope=globals(),
    )


def _render_dashboard_layout_template(
    *,
    title_html: str,
    page_mode_html: str,
    topbar_html: str,
    content_markup: str,
    main_content_html: str,
    server_switcher_profile_html: str,
    server_switcher_items_html: str,
    sidebar_server_name_html: str,
    sidebar_server_icon_url: str,
    sidebar_server_access_html: str,
    topbar_center_html: str,
    topbar_actions_html: str,
    sidebar_menu_html: str,
    dashboard_bootstrap_json: str,
    global_copyright_html: str,
    seo_path: str = "/dashboard",
    seo_image_path: str = "/dashboard/static/image_web_bot/giveaways_dashboard.webp",
    language: str = "th",
) -> str:
    return _DASHBOARD_RENDER_HELPERS.render_layout_template(
        callback_url=_dashboard_callback_url(),
        title_html=title_html,
        page_mode_html=page_mode_html,
        topbar_html=topbar_html,
        content_markup=content_markup,
        main_content_html=main_content_html,
        server_switcher_profile_html=server_switcher_profile_html,
        server_switcher_items_html=server_switcher_items_html,
        sidebar_server_name_html=sidebar_server_name_html,
        sidebar_server_icon_url=sidebar_server_icon_url,
        sidebar_server_access_html=sidebar_server_access_html,
        topbar_center_html=topbar_center_html,
        topbar_actions_html=topbar_actions_html,
        sidebar_menu_html=sidebar_menu_html,
        dashboard_bootstrap_json=dashboard_bootstrap_json,
        global_copyright_html=global_copyright_html,
        seo_path=seo_path,
        seo_image_path=seo_image_path,
        language=language,
    )


def _is_premium_subscription(raw_value: Any) -> bool:
    return _dashboard_plan_utils.is_premium_subscription(raw_value)


def _normalize_plan_tier(raw_value: Any) -> str:
    return _dashboard_plan_utils.normalize_plan_tier(raw_value)


def _plan_display_name(raw_value: Any) -> str:
    return _dashboard_plan_utils.plan_display_name(raw_value)


def _plan_rank(raw_value: Any) -> int:
    return _dashboard_plan_utils.plan_rank(raw_value)


def _plan_limits_by_tier(plan_tier: str) -> dict[str, int]:
    return _dashboard_plan_utils.plan_limits_by_tier(plan_tier)


def _plan_limits_from_guild_state(guild_state: dict[str, Any]) -> dict[str, int]:
    return _dashboard_plan_utils.plan_limits_from_guild_state(guild_state)


def _is_plan_at_least(raw_plan: Any, target_tier: str) -> bool:
    return _dashboard_plan_utils.is_plan_at_least(raw_plan, target_tier)


def _required_plan_for_command(command_name: str) -> str:
    return _dashboard_plan_utils.required_plan_for_command(command_name)


def _dashboard_tab_required_plan_map(runtime_settings: dict[str, Any] | None = None) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for slug in OWNERBOT_HIDEABLE_TABS:
        tier = _normalize_plan_tier(DASHBOARD_TAB_REQUIRED_PLAN.get(slug, "free"))
        if tier not in DASHBOARD_TAB_REQUIRED_PLAN_TIERS:
            tier = "free"
        resolved[slug] = tier
    payload = runtime_settings if isinstance(runtime_settings, dict) else _ownerbot_runtime_from_db()
    overrides = payload.get("dashboard_tab_required_plan") if isinstance(payload, dict) else {}
    if isinstance(overrides, dict):
        for slug, tier in _parse_dashboard_tab_required_plan_map(overrides).items():
            resolved[slug] = tier
    # Guard against legacy runtime settings that may still lock Donate to paid tiers.
    resolved["donate"] = "free"
    return resolved


def _dashboard_tab_new_badges(runtime_settings: dict[str, Any] | None = None) -> set[str]:
    allowed_tabs = set(OWNERBOT_HIDEABLE_TABS)
    default_badges = set(slug for slug in DASHBOARD_TAB_NEW_BADGES_DEFAULT if slug in allowed_tabs)
    payload = runtime_settings if isinstance(runtime_settings, dict) else _ownerbot_runtime_from_db()
    if not isinstance(payload, dict):
        return default_badges
    raw_value = payload.get("dashboard_tab_new_badges")
    if raw_value is None:
        return default_badges
    if isinstance(raw_value, list):
        return set(
            slug
            for slug in (str(item or "").strip().lower() for item in raw_value)
            if slug and slug in allowed_tabs
        )
    if isinstance(raw_value, str):
        return set(_parse_tab_slug_list(raw_value, max_items=200))
    return default_badges


def _required_plan_for_dashboard_tab(tab_slug: str | None, runtime_settings: dict[str, Any] | None = None) -> str:
    slug = str(tab_slug or "").strip().lower()
    if not slug:
        return "free"
    return _dashboard_tab_required_plan_map(runtime_settings).get(slug, "free")


def _as_utc_datetime(raw_value: Any) -> datetime.datetime | None:
    """Coerce mixed datetime payloads (iso string / unix / datetime) to UTC-aware datetime."""
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


def _dashboard_ownerbot_mode_from_state(
    state: dict[str, Any] | None,
    *,
    session: dict[str, Any] | None = None,
) -> bool:
    payload = (state or {}).get("dashboard_access") if isinstance(state, dict) else {}
    if isinstance(payload, dict):
        if bool(payload.get("ownerbot_mode_enabled")):
            return True
    return _dashboard_ownerbot_mode_enabled(session)


def _dashboard_effective_plan_tier(
    state: dict[str, Any] | None,
    *,
    session: dict[str, Any] | None = None,
) -> str:
    def _coerce_plan_end_datetime(raw_value: Any) -> datetime.datetime | None:
        converter = globals().get("_as_utc_datetime")
        if callable(converter):
            try:
                return converter(raw_value)
            except Exception:
                pass
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

    payload = (state or {}).get("dashboard_access") if isinstance(state, dict) else {}
    if isinstance(payload, dict):
        forced = str(payload.get("forced_plan_tier") or "").strip().lower()
        if forced:
            return _normalize_plan_tier(forced)
    plan_subscription = (state or {}).get("plan_subscription") if isinstance(state, dict) else {}
    if isinstance(plan_subscription, dict):
        row_plan = _normalize_plan_tier(plan_subscription.get("current_plan"))
        row_status = str(plan_subscription.get("status") or "").strip().lower()
        row_end = _coerce_plan_end_datetime(plan_subscription.get("current_period_end"))
        if row_plan == "permanent":
            return "permanent"
        if row_plan != "free":
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            # Some legacy rows keep active paid plans without current_period_end.
            # Treat explicit active/grace states as paid even when end date is missing.
            if row_status in {"active", "grace", "awaiting_payment", "paused"}:
                if row_end is None or row_end > now_utc:
                    return row_plan
            elif row_end and row_end > now_utc:
                return row_plan
    guild_state = (state or {}).get("guild") if isinstance(state, dict) else {}
    raw_plan = (guild_state or {}).get("subscription", "free") if isinstance(guild_state, dict) else "free"
    plan_tier = _normalize_plan_tier(raw_plan)
    if _dashboard_ownerbot_mode_from_state(state, session=session):
        return "diamond"
    return plan_tier


def _looks_like_active_premium_from_state(guild_state: dict[str, Any]) -> bool:
    return _dashboard_plan_utils.looks_like_active_premium_from_state(guild_state)


def _verify_limits_by_tier(plan_tier: str) -> dict[str, int]:
    return _dashboard_limits_utils.verify_limits_by_tier(plan_tier)


def _verify_limits_from_guild_state(guild_state: dict[str, Any]) -> dict[str, int]:
    return _dashboard_limits_utils.verify_limits_from_guild_state(guild_state)


def _levels_plan_caps(plan_tier: str) -> dict[str, Any]:
    return _dashboard_limits_utils.levels_plan_caps(plan_tier)
