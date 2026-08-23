import os
from urllib.parse import quote, urlsplit, urlunsplit
from skylinebot.config.config import BotConfigClass


BOT_CONFIG = BotConfigClass()


SUPPORT_SERVER = "https://discord.gg/6g294K6KMp"
CONTACT = str(
    os.getenv("SKYLINE_CONTACT_URL")
    or "https://niceshopallforme.web.app/contact"
    or ""
).strip()

_raw_dashboard_base = str(
    os.getenv("DASHBOARD_BASE_URL")
    or getattr(BOT_CONFIG, "DASHBOARD_BASE_URL", "")
    or ""
).strip()
if _raw_dashboard_base and "://" not in _raw_dashboard_base:
    _raw_dashboard_base = f"https://{_raw_dashboard_base}"
WEBSITE = _raw_dashboard_base.rstrip("/") if _raw_dashboard_base else "https://skylinebot"
PRIVACY_POLICY = f"{WEBSITE}/privacy"
TERMS_OF_SERVICE = f"{WEBSITE}/terms"
VOTE = "https://top.gg/bot/1484505852449787944"


def _strip_discord_cdn_query(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    if "cdn.discordapp.com" not in raw:
        return raw
    try:
        parsed = urlsplit(raw)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except Exception:
        return raw.split("?", 1)[0]


def _prefer_optimized_webp(url: str) -> str:
    raw = str(url or "").strip()
    if not raw or ".png" not in raw.lower():
        return raw
    try:
        parsed = urlsplit(raw)
        path = str(parsed.path or "")
        normalized_path = path.lower()
        if "/dashboard/static/image_web_bot/" not in normalized_path:
            return raw
        if not normalized_path.endswith(".png"):
            return raw
        webp_path = f"{path[:-4]}.webp"
        return urlunsplit((parsed.scheme, parsed.netloc, webp_path, parsed.query, parsed.fragment))
    except Exception:
        lowered = raw.lower()
        if "/dashboard/static/image_web_bot/" not in lowered or not lowered.endswith(".png"):
            return raw
        return f"{raw[:-4]}.webp"


def _visual_url(env_key: str, default_url: str = "") -> str:
    override = str(os.getenv(env_key) or "").strip()
    if override:
        return _prefer_optimized_webp(_strip_discord_cdn_query(override))
    return _prefer_optimized_webp(_strip_discord_cdn_query(default_url))


ANTINUKE = _visual_url(
    "SKYLINE_ANTINUKE_IMAGE_URL",
    "",
)
INVITE = (
    f"https://discord.com/oauth2/authorize?client_id={BOT_CONFIG.DISCORD_CLIENT_ID}"
    "&permissions=8&integration_type=0&scope=bot+applications.commands"
)
GIVEAWAY = _visual_url(
    "SKYLINE_GIVEAWAY_IMAGE_URL",
    "",
)
TICKET = _visual_url(
    "SKYLINE_TICKET_IMAGE_URL",
    "",
)

SERVER_STATS = _visual_url(
    "SKYLINE_SERVER_STATS_IMAGE_URL",
    "",
)
DEFAULT_MUSIC_BANNER = _visual_url(
    "SKYLINE_DEFAULT_MUSIC_BANNER_URL",
    "",
)
SECURITY = _visual_url(
    "SKYLINE_SECURITY_IMAGE_URL",
    "",
)
MODERATION = _visual_url(
    "SKYLINE_MODERATION_IMAGE_URL",
    "",
)
PROMOTE_FIRST_SETUP_IMAGE = _visual_url("SKYLINE_PROMOTE_FIRST_SETUP_IMAGE_URL", "")

# Landing/Index plugin catalog image keys.
# Each section can be overridden independently to avoid duplicated visuals.
PLUGIN_CATALOG_MODERATION_IMAGE = _visual_url(
    "SKYLINE_PLUGIN_CATALOG_MODERATION_IMAGE_URL",
    str(MODERATION or "/dashboard/static/image_web_bot/moderation_bot_safe_community.webp").strip(),
)
PLUGIN_CATALOG_UTILITIES_IMAGE = _visual_url(
    "SKYLINE_PLUGIN_CATALOG_UTILITIES_IMAGE_URL",
    str(TICKET or "/dashboard/static/image_web_bot/ticket_bot_support_system.webp").strip(),
)
PLUGIN_CATALOG_SOCIAL_ALERTS_IMAGE = _visual_url(
    "SKYLINE_PLUGIN_CATALOG_SOCIAL_ALERTS_IMAGE_URL",
    "/dashboard/static/image_web_bot/alerts_hub_multi_platform.webp",
)
PLUGIN_CATALOG_FUN_IMAGE = _visual_url(
    "SKYLINE_PLUGIN_CATALOG_FUN_IMAGE_URL",
    str(DEFAULT_MUSIC_BANNER or "/dashboard/static/image_web_bot/music_banner_discord_bot.webp").strip(),
)
PLUGIN_CATALOG_PERSONALIZE_IMAGE = _visual_url(
    "SKYLINE_PLUGIN_CATALOG_PERSONALIZE_IMAGE_URL",
    "/dashboard/static/image_web_bot/server_settings_dashboard.webp",
)
PLUGIN_CATALOG_PREMIUM_IMAGE = _visual_url(
    "SKYLINE_PLUGIN_CATALOG_PREMIUM_IMAGE_URL",
    "/dashboard/static/image_web_bot/premium_status_unlocked.webp",
)
PLUGIN_CATALOG_AI_IMAGE = _visual_url(
    "SKYLINE_PLUGIN_CATALOG_AI_IMAGE_URL",
    "/dashboard/static/image_web_bot/ai_chatbot_system_stats.webp",
)

PLUGIN_CATALOG_IMAGES: dict[str, str] = {
    "moderation": PLUGIN_CATALOG_MODERATION_IMAGE,
    "utilities": PLUGIN_CATALOG_UTILITIES_IMAGE,
    "social_alerts": PLUGIN_CATALOG_SOCIAL_ALERTS_IMAGE,
    "fun": PLUGIN_CATALOG_FUN_IMAGE,
    "personalize": PLUGIN_CATALOG_PERSONALIZE_IMAGE,
    "premium": PLUGIN_CATALOG_PREMIUM_IMAGE,
    "ai": PLUGIN_CATALOG_AI_IMAGE,
}

# Landing/Index image keys for features/resources/tutorial showcase.
# Keep these in one place so replacing assets does not require touching page templates/routes.
INDEX_FEATURE_CARD_1_IMAGE = _visual_url(
    "SKYLINE_INDEX_FEATURE_CARD_1_IMAGE_URL",
    str(SECURITY or "/dashboard/static/image_web_bot/security_bot_protection.webp").strip(),
)
INDEX_FEATURE_CARD_2_IMAGE = _visual_url(
    "SKYLINE_INDEX_FEATURE_CARD_2_IMAGE_URL",
    str(GIVEAWAY or "/dashboard/static/image_web_bot/giveaways_dashboard.webp").strip(),
)
INDEX_FEATURE_CARD_3_IMAGE = _visual_url(
    "SKYLINE_INDEX_FEATURE_CARD_3_IMAGE_URL",
    str(DEFAULT_MUSIC_BANNER or "/dashboard/static/image_web_bot/music_banner_discord_bot.webp").strip(),
)
INDEX_NAV_PLUGINS_SPOTLIGHT_IMAGE = _visual_url(
    "SKYLINE_INDEX_NAV_PLUGINS_SPOTLIGHT_IMAGE_URL",
    str(DEFAULT_MUSIC_BANNER or "/dashboard/static/image_web_bot/music_banner_discord_bot.webp").strip(),
)
INDEX_NAV_RESOURCES_SPOTLIGHT_IMAGE = _visual_url(
    "SKYLINE_INDEX_NAV_RESOURCES_SPOTLIGHT_IMAGE_URL",
    str(GIVEAWAY or "/dashboard/static/image_web_bot/giveaways_dashboard.webp").strip(),
)
INDEX_TUTORIAL_CARD_1_IMAGE = _visual_url(
    "SKYLINE_INDEX_TUTORIAL_CARD_1_IMAGE_URL",
    str(ANTINUKE or "/dashboard/static/image_web_bot/security_bot_protection.webp").strip(),
)
INDEX_TUTORIAL_CARD_2_IMAGE = _visual_url(
    "SKYLINE_INDEX_TUTORIAL_CARD_2_IMAGE_URL",
    "/dashboard/static/image_web_bot/server_promote_growth.webp",
)
INDEX_TUTORIAL_CARD_3_IMAGE = _visual_url(
    "SKYLINE_INDEX_TUTORIAL_CARD_3_IMAGE_URL",
    "/dashboard/static/image_web_bot/customrole_bot_system.webp",
)

INDEX_LANDING_IMAGES: dict[str, str] = {
    "feature_card_1": INDEX_FEATURE_CARD_1_IMAGE,
    "feature_card_2": INDEX_FEATURE_CARD_2_IMAGE,
    "feature_card_3": INDEX_FEATURE_CARD_3_IMAGE,
    "nav_plugins_spotlight": INDEX_NAV_PLUGINS_SPOTLIGHT_IMAGE,
    "nav_resources_spotlight": INDEX_NAV_RESOURCES_SPOTLIGHT_IMAGE,
    "tutorial_card_1": INDEX_TUTORIAL_CARD_1_IMAGE,
    "tutorial_card_2": INDEX_TUTORIAL_CARD_2_IMAGE,
    "tutorial_card_3": INDEX_TUTORIAL_CARD_3_IMAGE,
}


def get_theme_presets(
    *,
    user_url: str = "",
    guild_url: str = "",
    include_extended: bool = True,
) -> dict[str, str]:
    presets: dict[str, str] = {
        "music": str(DEFAULT_MUSIC_BANNER or "").strip(),
        "security": str(SECURITY or "").strip(),
        "giveaway": str(GIVEAWAY or "").strip(),
    }
    if include_extended:
        presets.update(
            {
                "ticket": str(TICKET or "").strip(),
                "stats": str(SERVER_STATS or "").strip(),
                "antinuke": str(ANTINUKE or "").strip(),
            }
        )
    user = str(user_url or "").strip()
    guild = str(guild_url or "").strip()
    if user:
        presets["user"] = user
    if guild:
        presets["guild"] = guild
    return presets


def resolve_theme_image(
    theme_key: str,
    custom_url: str = "",
    *,
    user_url: str = "",
    guild_url: str = "",
    fallback: str = DEFAULT_MUSIC_BANNER,
    include_extended: bool = True,
) -> str:
    key = str(theme_key or "").strip().lower()
    custom = str(custom_url or "").strip()
    user = str(user_url or "").strip()
    guild = str(guild_url or "").strip()
    fallback_url = str(fallback or "").strip()

    if key == "custom":
        return custom or fallback_url
    if key in {"user", "avatar", "member"} and user:
        return user
    if key in {"guild", "server"} and guild:
        return guild
    presets = get_theme_presets(
        user_url=user,
        guild_url=guild,
        include_extended=include_extended,
    )
    if key in presets:
        return str(presets.get(key) or "").strip()
    if not key and custom:
        return custom
    return fallback_url


def _hero_seed(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "default"
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in raw)
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-") or "default"


# Centralized hero image seeds per dashboard tab/page.
# Keep this list in urls.py so visual updates can be managed from one place.
DASHBOARD_TAB_HERO_SEEDS: dict[str, str] = {
    "overview": "overview-system",
    "security": "security-shield",
    "moderation": "moderation-control",
    "music": "music-live",
    "commands": "commands-terminal",
    "logs": "logs-history",
    "giveaways": "giveaways-event",
    "tickets": "tickets-support",
    "welcomer": "welcomer-community",
    "welcome": "welcome-message",
    "leaver": "leaver-goodbye",
    "promote": "promote-server",
    "ocr": "ocr-vision",
    "verify": "verify-check",
    "autoresponder": "autoresponder-chat",
    "customrole": "customrole-member",
    "media": "media-gallery",
    "server_stats": "server-stats",
    "donate": "donate-support",
    "alerts": "alerts-social",
    "aichat": "aichat-assistant",
    "server_settings": "settings-server",
    "embed_messages": "embed-message",
    "premium_receive": "premium-subscription",
    "tools": "tools-admin",
    "welcome_center": "welcome-center",
    "auto_reply_center": "auto-reply-center",
    "economy": "economy-finance",
    "levels": "levels-xp",
    "autoroles": "autoroles-permission",
    "colors": "colors-theme",
    "reaction_roles": "reaction-roles",
    "starboard": "starboard-highlight",
    "temp_channels": "temp-channels",
    "join_to_create": "join-to-create",
    "temp_links": "temp-links",
    "statistics_plus": "statistics-plus",
    "tickets_plus": "tickets-plus",
    "screening": "screening-safety",
    "screening_categories": "screening-categories",
    "automation": "automation-workflow",
    "anti_raid": "anti-raid",
    "extra_protection": "extra-protection",
    "alerts_twitch": "alerts-twitch",
    "alerts_youtube": "alerts-youtube",
    "alerts_tiktok": "alerts-tiktok",
    "alerts_github": "alerts-github",
    "alerts_facebook": "alerts-facebook",
    "control_panel": "control-panel",
    "audit_logs": "audit-logs",
}

DASHBOARD_TAB_HERO_IMAGES: dict[str, str] = {
    key: _visual_url(f"SKYLINE_DASHBOARD_HERO_{key.upper()}_URL", "")
    for key in DASHBOARD_TAB_HERO_SEEDS
}

# Welcome/Welcomer share the same visual by default.
# If only one env key is set, mirror it to the other key automatically.
if not str(DASHBOARD_TAB_HERO_IMAGES.get("welcomer") or "").strip():
    DASHBOARD_TAB_HERO_IMAGES["welcomer"] = str(DASHBOARD_TAB_HERO_IMAGES.get("welcome") or "").strip()
if not str(DASHBOARD_TAB_HERO_IMAGES.get("welcome") or "").strip():
    DASHBOARD_TAB_HERO_IMAGES["welcome"] = str(DASHBOARD_TAB_HERO_IMAGES.get("welcomer") or "").strip()


def get_dashboard_tab_hero_image(tab_slug: str, fallback: str = DEFAULT_MUSIC_BANNER) -> str:
    key = _hero_seed(tab_slug)
    direct = str(DASHBOARD_TAB_HERO_IMAGES.get(key) or "").strip()
    if direct:
        return direct
    return str(fallback or "").strip()


def _parse_env_int_set(*env_names: str) -> set[int]:
    values: set[int] = set()
    for env_name in env_names:
        raw_value = str(os.getenv(env_name, "") or "").strip()
        if not raw_value:
            continue
        for piece in raw_value.replace(";", ",").split(","):
            candidate = str(piece or "").strip()
            if candidate.isdigit():
                values.add(int(candidate))
    return values


def photo_root_scope_guild_ids() -> set[int]:
    ids = _parse_env_int_set(
        "PHOTO_ROOT_GUILD_IDS",
        "SUPPORT_GUILD_ID",
        "SUPPORT_HOME_GUILD_ID",
        "OWNERBOT_GUILD_ID",
        "OWNER_GUILD_ID",
    )
    return ids


def photo_scope_guild_id(guild_id: int | str | None) -> int:
    try:
        resolved = int(str(guild_id or "").strip())
    except Exception:
        return 0
    if resolved <= 0:
        return 0
    if resolved in photo_root_scope_guild_ids():
        return 0
    return resolved


def photo_path(guild_id: int | str | None, slug: str) -> str:
    scope_guild_id = photo_scope_guild_id(guild_id)
    safe_slug = quote(str(slug or "").strip().strip("/"), safe="-_.~")
    if scope_guild_id <= 0:
        return f"/photo/{safe_slug}"
    return f"/{scope_guild_id}/photo/{safe_slug}"


def photo_url(guild_id: int | str | None, slug: str, *, base_url: str = "") -> str:
    origin = str(base_url or "").strip() or str(WEBSITE or "").strip()
    if not origin:
        origin = "https://skylinebot.xyz"
    if "://" not in origin:
        origin = f"https://{origin}"
    return f"{origin.rstrip('/')}{photo_path(guild_id, slug)}"
