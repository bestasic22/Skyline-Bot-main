from __future__ import annotations

import datetime
import json
import re
import time
from typing import Any, Callable

from skylinebot.workflows import billing as billing_workflow
from skylinebot.workflows.redeem_control import lock_mode_from_flags, normalize_redeem_row

DEFAULT_DEVELOPER_SOCIAL_KEY = "__default__"
OWNERBOT_AI_PROVIDERS: tuple[str, ...] = (
    "opentyphoon",
    "openai",
    "google",
    "ollama",
    "chindax",
    "aiforthai",
    "cloudflare",
    "thaillm",
)
OWNERBOT_AI_PROVIDER_LABELS: dict[str, str] = {
    "ollama": "Ollama (Local/Cloud)",
    "openai": "OpenAI",
    "google": "Google Gemini",
    "opentyphoon": "OpenTyphoon",
    "chindax": "ChindaX",
    "aiforthai": "AI FOR THAI",
    "cloudflare": "Cloudflare Workers AI",
    "thaillm": "ThaiLLM",
}
_OWNERBOT_SETTINGS_SECTION_GROUP_RE = re.compile(
    r'(?P<block><div class="ownerbot-section-group[^>]*data-ownerbot-section="(?P<section>[^"]+)"[^>]*>\s*'
    r"<section\b[^>]*>.*?</section>\s*</div>)",
    flags=re.IGNORECASE | re.DOTALL,
)
_OWNERBOT_RUNTIME_SUBPAGE_DEFAULT = "overview"
_OWNERBOT_RUNTIME_SUBPAGES: tuple[str, ...] = (
    "overview",
    "ai",
    "vote",
    "dashboard",
    "commands",
    "social",
    "upload",
)
_OWNERBOT_RUNTIME_PANEL_RE = re.compile(
    r'(?P<block><div class="ownerbot-section-group[^>]*data-ownerbot-section="runtime"[^>]*>\s*'
    r'<section class="panel" id="ownerbotRuntimePanel">.*?</section>\s*</div>)',
    flags=re.IGNORECASE | re.DOTALL,
)
_OWNERBOT_UPLOAD_PANEL_RE = re.compile(
    r'(?P<block><div class="ownerbot-section-group[^>]*data-ownerbot-section="runtime"[^>]*>\s*'
    r'<section class="panel" id="ownerbotUploadPanel">.*?</section>\s*</div>)',
    flags=re.IGNORECASE | re.DOTALL,
)
_OWNERBOT_RUNTIME_SUBTAB_BLOCK_RE = re.compile(
    r'(?P<block><div class="ownerbot-subtab-panel[^>]*data-ownerbot-subtab-panel="(?P<subtab>runtime-[^"]+)"[^>]*>'
    r'.*?(?=(<div class="ownerbot-subtab-panel[^>]*data-ownerbot-subtab-panel="runtime-|<div class="auth-actions">)))',
    flags=re.IGNORECASE | re.DOTALL,
)


def _ownerbot_settings_keep_active_section(body_html: str, active_section: str) -> str:
    source = str(body_html or "")
    if not source:
        return ""
    target = str(active_section or "runtime").strip().lower() or "runtime"

    def _replace(match: re.Match[str]) -> str:
        section = str(match.group("section") or "").strip().lower()
        if section == target:
            return str(match.group("block") or "")
        return ""

    rendered = _OWNERBOT_SETTINGS_SECTION_GROUP_RE.sub(_replace, source)
    return re.sub(r"\n{3,}", "\n\n", rendered)


def _ownerbot_normalize_runtime_subpage(
    value: Any,
    fallback: str = _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT,
) -> str:
    page = str(value or "").strip().lower()
    if page in _OWNERBOT_RUNTIME_SUBPAGES:
        return page
    fallback_page = str(fallback or _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT).strip().lower()
    if fallback_page in _OWNERBOT_RUNTIME_SUBPAGES:
        return fallback_page
    return _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT


def _ownerbot_settings_keep_active_runtime_subpage(body_html: str, runtime_subpage: str) -> str:
    source = str(body_html or "")
    if not source:
        return ""
    target = _ownerbot_normalize_runtime_subpage(runtime_subpage, _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT)
    if target == "upload":
        source = _OWNERBOT_RUNTIME_PANEL_RE.sub("", source)
        return re.sub(r"\n{3,}", "\n\n", source)

    source = _OWNERBOT_UPLOAD_PANEL_RE.sub("", source)
    keep_subtab = f"runtime-{target}"

    def _replace_subtab(match: re.Match[str]) -> str:
        subtab = str(match.group("subtab") or "").strip().lower()
        if subtab == keep_subtab:
            return str(match.group("block") or "")
        return ""

    source = _OWNERBOT_RUNTIME_SUBTAB_BLOCK_RE.sub(_replace_subtab, source)
    return re.sub(r"\n{3,}", "\n\n", source)


def _normalize_ownerbot_ai_provider(value: Any, fallback: str = "opentyphoon") -> str:
    provider = str(value or "").strip().lower()
    if provider in OWNERBOT_AI_PROVIDERS:
        return provider
    fallback_provider = str(fallback or "opentyphoon").strip().lower()
    if fallback_provider in OWNERBOT_AI_PROVIDERS:
        return fallback_provider
    return "opentyphoon"


def _default_ownerbot_model_for_provider(
    provider: str,
    *,
    openai_model: str | None = None,
    google_model: str | None = None,
    ollama_model: str | None = None,
    opentyphoon_model: str | None = None,
    chindax_model: str | None = None,
    aiforthai_model: str | None = None,
    cloudflare_model: str | None = None,
    thaillm_model: str | None = None,
) -> str:
    normalized = _normalize_ownerbot_ai_provider(provider, fallback="opentyphoon")
    if normalized == "openai":
        return str(openai_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
    if normalized == "google":
        return str(google_model or "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    if normalized == "opentyphoon":
        return (
            str(opentyphoon_model or "typhoon-v2.5-30b-a3b-instruct").strip()
            or "typhoon-v2.5-30b-a3b-instruct"
        )
    if normalized == "chindax":
        return (
            str(chindax_model or "accounts/fireworks/models/gpt-oss-20b").strip()
            or "accounts/fireworks/models/gpt-oss-20b"
        )
    if normalized == "aiforthai":
        return str(aiforthai_model or "aiforthai-chat").strip() or "aiforthai-chat"
    if normalized == "cloudflare":
        return str(cloudflare_model or "@cf/meta/llama-3.1-8b-instruct").strip() or "@cf/meta/llama-3.1-8b-instruct"
    if normalized == "thaillm":
        return (
            str(thaillm_model or "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2").strip()
            or "OpenThaiGPT-ThaiLLM-8B-Instruct-v7.2"
        )
    return str(ollama_model or "qwen2.5:0.5b-instruct").strip() or "qwen2.5:0.5b-instruct"


def default_ownerbot_runtime_settings(
    *,
    ai_provider: str | None,
    openai_model: str | None,
    google_model: str | None,
    ollama_model: str | None,
    opentyphoon_model: str | None = None,
    chindax_model: str | None = None,
    aiforthai_model: str | None = None,
    cloudflare_model: str | None = None,
    thaillm_model: str | None = None,
    default_dashboard_tab_new_badges: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    provider = _normalize_ownerbot_ai_provider(ai_provider, fallback="opentyphoon")
    default_ai_model = _default_ownerbot_model_for_provider(
        provider,
        openai_model=openai_model,
        google_model=google_model,
        ollama_model=ollama_model,
        opentyphoon_model=opentyphoon_model,
        chindax_model=chindax_model,
        aiforthai_model=aiforthai_model,
        cloudflare_model=cloudflare_model,
        thaillm_model=thaillm_model,
    )
    default_new_badges: list[str] = []
    for item in list(default_dashboard_tab_new_badges or []):
        slug = str(item or "").strip().lower()
        if not slug or slug in default_new_badges:
            continue
        default_new_badges.append(slug)
    return {
        "global_command_response_enabled": True,
        "global_bot_response_enabled": True,
        "global_ai_provider": provider,
        "global_ai_model": default_ai_model,
        "guild_mode": "all",
        "whitelist_guild_ids": [],
        "blacklist_guild_ids": [],
        "tester_enabled": False,
        "tester_guild_ids": [],
        "global_disabled_commands": [],
        "developer_social_links": {},
        "hidden_dashboard_tabs": [],
        "dashboard_tab_required_plan": {},
        "dashboard_tab_new_badges": default_new_badges,
        "discordbotlist_vote_result_channel_id": "",
        "discordbotlist_vote_embed_channel_id": "",
        "discordbotlist_vote_button_url": "",
        "discordbotlist_vote_webhook_secret": "",
        "dashboard_status_override_level": "auto",
        "dashboard_status_override_activity": "auto",
        "dashboard_status_override_display": "auto",
        "dashboard_status_override_message": "",
        "dashboard_status_override_messages": [],
        "rich_presence_mode": "off",
    }


def _parse_override_messages(raw_value: Any, *, limit: int = 12) -> list[str]:
    items = raw_value if isinstance(raw_value, list) else str(raw_value or "").splitlines()
    out: list[str] = []
    for item in items:
        text = " ".join(str(item or "").strip().split())
        if not text:
            continue
        out.append(text[:120])
        if len(out) >= int(limit):
            break
    return out


def normalize_ownerbot_runtime_settings(
    payload: dict[str, Any] | None,
    *,
    default_factory: Callable[[], dict[str, Any]],
    parse_guild_id_list: Callable[[str | None], list[str]],
    parse_command_name_list: Callable[[str | None], list[str]],
    parse_tab_slug_list: Callable[[str | None], list[str]],
    parse_dashboard_tab_required_plan_map: Callable[[Any], dict[str, str]],
    parse_developer_social_links: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = default_factory()
    guild_mode = str(src.get("guild_mode") or "all").strip().lower()
    if guild_mode not in {"all", "whitelist", "blacklist", "tester"}:
        guild_mode = "all"

    out["global_command_response_enabled"] = bool(src.get("global_command_response_enabled", True))
    out["global_bot_response_enabled"] = bool(src.get("global_bot_response_enabled", True))
    out["global_ai_provider"] = _normalize_ownerbot_ai_provider(
        src.get("global_ai_provider"),
        fallback=str(out.get("global_ai_provider") or "opentyphoon"),
    )
    provider_default_model = _default_ownerbot_model_for_provider(
        str(out.get("global_ai_provider") or "opentyphoon")
    )
    out["global_ai_model"] = provider_default_model
    runtime_ai_model = str(src.get("global_ai_model") or "").strip()
    allowed_chars = re.compile(r"^[A-Za-z0-9._:/-]+$")
    if runtime_ai_model and len(runtime_ai_model) <= 120 and allowed_chars.match(runtime_ai_model):
        out["global_ai_model"] = runtime_ai_model
    out["guild_mode"] = guild_mode
    out["whitelist_guild_ids"] = parse_guild_id_list(
        ",".join(src.get("whitelist_guild_ids", []))
        if isinstance(src.get("whitelist_guild_ids"), list)
        else str(src.get("whitelist_guild_ids") or "")
    )
    out["blacklist_guild_ids"] = parse_guild_id_list(
        ",".join(src.get("blacklist_guild_ids", []))
        if isinstance(src.get("blacklist_guild_ids"), list)
        else str(src.get("blacklist_guild_ids") or "")
    )
    out["tester_enabled"] = bool(src.get("tester_enabled", False))
    out["tester_guild_ids"] = parse_guild_id_list(
        ",".join(src.get("tester_guild_ids", []))
        if isinstance(src.get("tester_guild_ids"), list)
        else str(src.get("tester_guild_ids") or "")
    )
    out["global_disabled_commands"] = parse_command_name_list(
        ",".join(src.get("global_disabled_commands", []))
        if isinstance(src.get("global_disabled_commands"), list)
        else str(src.get("global_disabled_commands") or "")
    )
    out["developer_social_links"] = parse_developer_social_links(src.get("developer_social_links"))
    out["hidden_dashboard_tabs"] = parse_tab_slug_list(
        ",".join(src.get("hidden_dashboard_tabs", []))
        if isinstance(src.get("hidden_dashboard_tabs"), list)
        else str(src.get("hidden_dashboard_tabs") or "")
    )
    if "dashboard_tab_required_plan" in src:
        out["dashboard_tab_required_plan"] = parse_dashboard_tab_required_plan_map(src.get("dashboard_tab_required_plan"))
    if "dashboard_tab_new_badges" in src:
        out["dashboard_tab_new_badges"] = parse_tab_slug_list(
            ",".join(src.get("dashboard_tab_new_badges", []))
            if isinstance(src.get("dashboard_tab_new_badges"), list)
            else str(src.get("dashboard_tab_new_badges") or "")
        )
    for key in (
        "discordbotlist_vote_result_channel_id",
        "discordbotlist_vote_embed_channel_id",
    ):
        value = str(src.get(key) or "").strip()
        out[key] = value if value.isdigit() else ""
    vote_button_url = str(src.get("discordbotlist_vote_button_url") or "").strip()
    if vote_button_url and not re.match(r"^https?://", vote_button_url, flags=re.IGNORECASE):
        vote_button_url = ""
    out["discordbotlist_vote_button_url"] = vote_button_url[:300]
    out["discordbotlist_vote_webhook_secret"] = str(src.get("discordbotlist_vote_webhook_secret") or "").strip()[:240]
    allowed_levels = {"auto", "online", "idle", "dnd", "offline"}
    allowed_activities = {"auto", "playing", "streaming", "listening", "watching", "competing"}
    non_auto_activities = allowed_activities - {"auto"}
    allowed_display_values = {"auto", "online", "idle", "dnd", "offline", "playing", "streaming", "listening", "watching", "competing"}
    legacy_level_map = {"live": "online", "stream": "idle", "ded": "dnd"}
    legacy_activity_map = {"custom": "watching"}

    override_level = str(
        src.get("dashboard_status_override_level")
        or out.get("dashboard_status_override_level")
        or "auto"
    ).strip().lower()
    override_level = legacy_level_map.get(override_level, override_level)
    if override_level not in allowed_levels:
        override_level = "auto"
    override_activity = str(
        src.get("dashboard_status_override_activity")
        or out.get("dashboard_status_override_activity")
        or "auto"
    ).strip().lower()
    override_activity = legacy_activity_map.get(override_activity, override_activity)
    if override_activity not in allowed_activities:
        override_activity = "auto"
    if override_level == "auto" and override_activity in non_auto_activities:
        override_level = "online"
    override_display = str(
        src.get("dashboard_status_override_display")
        or out.get("dashboard_status_override_display")
        or ""
    ).strip().lower()
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
    override_message_text = str(
        src.get("dashboard_status_override_message")
        or out.get("dashboard_status_override_message")
        or ""
    ).strip()[:2000]
    override_messages = _parse_override_messages(src.get("dashboard_status_override_messages"))
    if not override_messages and override_message_text:
        override_messages = _parse_override_messages(override_message_text)
    out["dashboard_status_override_level"] = override_level
    out["dashboard_status_override_activity"] = override_activity
    out["dashboard_status_override_display"] = override_display
    out["dashboard_status_override_messages"] = override_messages
    out["dashboard_status_override_message"] = (
        override_message_text or "\n".join(override_messages)
    )[:2000]
    rich_presence_mode = str(src.get("rich_presence_mode") or out.get("rich_presence_mode") or "off").strip().lower()
    if rich_presence_mode not in {"off", "voice", "always"}:
        rich_presence_mode = "off"
    out["rich_presence_mode"] = rich_presence_mode
    return out


def ownerbot_runtime_from_cache(
    raw_value: str,
    *,
    default_factory: Callable[[], dict[str, Any]],
    normalize_settings: Callable[[dict[str, Any] | None], dict[str, Any]],
) -> dict[str, Any]:
    raw = str(raw_value or "").strip()
    if not raw:
        return default_factory()
    try:
        decoded = json.loads(raw)
    except Exception:
        return default_factory()
    return normalize_settings(decoded if isinstance(decoded, dict) else {})


def ownerbot_runtime_block_reason(guild_id: int, runtime_settings: dict[str, Any]) -> str | None:
    gid = str(guild_id)
    mode = str(runtime_settings.get("guild_mode") or "all").strip().lower()
    whitelist = set(runtime_settings.get("whitelist_guild_ids") or [])
    blacklist = set(runtime_settings.get("blacklist_guild_ids") or [])
    tester_enabled = bool(runtime_settings.get("tester_enabled", False))
    tester_ids = set(runtime_settings.get("tester_guild_ids") or [])
    if tester_enabled or mode == "tester":
        return None if gid in tester_ids else "tester_only"
    if mode == "whitelist":
        return None if gid in whitelist else "whitelist_only"
    if mode == "blacklist":
        return "blacklist_blocked" if gid in blacklist else None
    return None


def ownerbot_runtime_block_message(reason_code: str | None) -> str:
    mapping = {
        "whitelist_only": "รองรับเฉพาะ Whitelist Guild",
        "tester_only": "รองรับเฉพาะ Server Tester Mode",
        "blacklist_blocked": "Server นี้ติด Blacklist Guild",
    }
    return mapping.get(str(reason_code or ""), "เซิร์ฟเวอร์นี้ไม่อยู่ในโหมดที่อนุญาต")


def ownerbot_runtime_notice_from_state(
    state: dict[str, Any] | None,
    *,
    block_message_fn: Callable[[str | None], str],
) -> str | None:
    if not isinstance(state, dict):
        return None
    reason = str(state.get("ownerbot_block_reason") or "").strip()
    if not reason:
        return None
    return block_message_fn(reason)


def ownerbot_hidden_dashboard_tabs(
    runtime_settings: dict[str, Any] | None,
    *,
    parse_tab_slug_list: Callable[[str | None], list[str]],
) -> set[str]:
    if not isinstance(runtime_settings, dict):
        return set()
    hidden = runtime_settings.get("hidden_dashboard_tabs")
    if isinstance(hidden, list):
        hidden_tabs = set(parse_tab_slug_list(",".join(str(x or "") for x in hidden)))
    else:
        hidden_tabs = set(parse_tab_slug_list(str(hidden or "")))
    if "temp_channels" in hidden_tabs:
        hidden_tabs.add("join_to_create")
    if "join_to_create" in hidden_tabs:
        hidden_tabs.add("temp_channels")
    return hidden_tabs


def ownerbot_dashboard_tab_block_reason(
    *,
    session: dict[str, Any] | None,
    tab_slug: str,
    runtime_settings: dict[str, Any] | None = None,
    is_dashboard_admin_fn: Callable[[dict[str, Any] | None], bool],
    ownerbot_runtime_from_db_fn: Callable[[], dict[str, Any]],
    ownerbot_hidden_tabs_fn: Callable[[dict[str, Any] | None], set[str]],
) -> str | None:
    if is_dashboard_admin_fn(session):
        return None
    runtime_payload = runtime_settings if isinstance(runtime_settings, dict) else ownerbot_runtime_from_db_fn()
    hidden_tabs = ownerbot_hidden_tabs_fn(runtime_payload)
    if str(tab_slug or "").strip().lower() in hidden_tabs:
        return "แท็บนี้ถูกปิดการใช้งาน"
    return None


def render_ownerbot_console_page(
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
    escape_fn: Callable[[Any], str],
    render_layout_fn: Callable[..., str],
    render_dashboard_f_template_fn: Callable[[str, dict[str, Any]], str],
    normalize_runtime_settings_fn: Callable[[dict[str, Any] | None], dict[str, Any]],
    ownerbot_hidden_dashboard_tabs_fn: Callable[[dict[str, Any] | None], set[str]],
    developer_social_url_fn: Callable[[dict[str, Any], str, str], str],
    developer_social_icon_fn: Callable[[dict[str, Any], str], str],
    format_datetime_local_fn: Callable[[Any], str],
    format_datetime_th_fn: Callable[[Any], str],
    redeem_code_types: dict[str, str],
    ownerbot_ai_model_ram_guide: list[dict[str, Any]],
    social_platform_keys: tuple[str, ...],
    social_platform_labels: dict[str, str],
    social_platform_default_icons: dict[str, str],
    ownerbot_upload_targets: tuple[str, ...],
    ownerbot_upload_target_labels: dict[str, str],
    ownerbot_upload_target_default_channels: dict[str, str],
    ownerbot_hideable_tabs: tuple[str, ...],
    ownerbot_hideable_tab_labels: dict[str, str],
    dashboard_tab_required_plan_defaults: dict[str, str],
    dashboard_tab_plan_tiers: tuple[str, ...],
    dashboard_tab_new_badge_defaults: tuple[str, ...],
    overview_only: bool = True,
    settings_active_section: str = "runtime",
    settings_active_runtime_page: str = _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT,
) -> str:
    _escape = escape_fn
    _render_layout = render_layout_fn
    _render_dashboard_f_template = render_dashboard_f_template_fn
    _normalize_ownerbot_runtime_settings = normalize_runtime_settings_fn
    _ownerbot_hidden_dashboard_tabs = ownerbot_hidden_dashboard_tabs_fn
    _developer_social_url = developer_social_url_fn
    _developer_social_icon = developer_social_icon_fn
    _format_datetime_local = format_datetime_local_fn
    _format_datetime_th = format_datetime_th_fn
    REDEEM_CODE_TYPES = redeem_code_types
    OWNERBOT_AI_MODEL_RAM_GUIDE = ownerbot_ai_model_ram_guide
    SOCIAL_PLATFORM_KEYS = social_platform_keys
    SOCIAL_PLATFORM_LABELS = social_platform_labels
    SOCIAL_PLATFORM_DEFAULT_ICONS = social_platform_default_icons
    OWNERBOT_UPLOAD_TARGETS = ownerbot_upload_targets
    OWNERBOT_UPLOAD_TARGET_LABELS = ownerbot_upload_target_labels
    OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS = ownerbot_upload_target_default_channels
    OWNERBOT_HIDEABLE_TABS = ownerbot_hideable_tabs
    OWNERBOT_HIDEABLE_TAB_LABELS = ownerbot_hideable_tab_labels
    DASHBOARD_TAB_REQUIRED_PLAN_DEFAULTS = dashboard_tab_required_plan_defaults
    DASHBOARD_TAB_PLAN_TIERS = tuple(str(item or "").strip().lower() for item in dashboard_tab_plan_tiers if str(item or "").strip())
    DASHBOARD_TAB_NEW_BADGE_DEFAULTS = tuple(
        str(item or "").strip().lower()
        for item in dashboard_tab_new_badge_defaults
        if str(item or "").strip()
    )

    # Lightweight overview mode to keep OwnerBOT page fast and stable.
    runtime_settings = _normalize_ownerbot_runtime_settings(runtime_settings)
    notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""
    guild_mode_value = str(runtime_settings.get("guild_mode") or "all").strip().lower()
    tester_enabled_value = bool(runtime_settings.get("tester_enabled", False))
    status_override_level = str(runtime_settings.get("dashboard_status_override_level") or "auto").strip().lower()
    if status_override_level not in {"auto", "online", "idle", "dnd", "offline"}:
        status_override_level = "auto"
    status_override_activity = str(runtime_settings.get("dashboard_status_override_activity") or "auto").strip().lower()
    if status_override_activity not in {"auto", "playing", "streaming", "listening", "watching", "competing"}:
        status_override_activity = "auto"
    status_override_display = str(runtime_settings.get("dashboard_status_override_display") or "").strip().lower()
    if status_override_display not in {"auto", "online", "idle", "dnd", "offline", "playing", "streaming", "listening", "watching", "competing"}:
        if status_override_level == "auto" and status_override_activity == "auto":
            status_override_display = "auto"
        elif status_override_level in {"online", "idle", "dnd", "offline"}:
            if status_override_level == "online" and status_override_activity in {"playing", "streaming", "listening", "watching", "competing"}:
                status_override_display = status_override_activity
            else:
                status_override_display = status_override_level
        elif status_override_activity in {"playing", "streaming", "listening", "watching", "competing"}:
            status_override_display = status_override_activity
        else:
            status_override_display = "auto"
    status_override_message = str(runtime_settings.get("dashboard_status_override_message") or "").strip()
    status_override_messages = _parse_override_messages(runtime_settings.get("dashboard_status_override_messages"))
    if not status_override_messages and status_override_message:
        status_override_messages = _parse_override_messages(status_override_message)
    status_override_primary_message = status_override_messages[0] if status_override_messages else ""

    discord_runtime_payload = discord_runtime if isinstance(discord_runtime, dict) else {}
    runtime_level = str(discord_runtime_payload.get("level") or "unknown").strip().lower()
    runtime_message = str(discord_runtime_payload.get("message") or "").strip()
    runtime_updated_at = float(discord_runtime_payload.get("updated_at") or 0.0)

    runtime_tone = "unknown"
    runtime_label = "UNKNOWN"
    runtime_error_levels = {"ded", "degraded", "outage", "auth_error", "error", "err", "stopped"}
    runtime_starting_levels = {"stream", "starting", "restart", "restarting", "reload", "reloading", "unknown"}

    if runtime_level in runtime_error_levels:
        runtime_tone = "err"
        runtime_label = "DED"
        runtime_level = "ded"
        runtime_message = "บอทไม่พร้อมทำงาน กำลังเร่งแก้ไขระบบ"
    elif runtime_level in runtime_starting_levels:
        runtime_tone = "loading"
        runtime_label = "สตรีม"
        runtime_level = "stream"
        runtime_message = "บอทกำลังเริ่มระบบ"
    elif tester_enabled_value or guild_mode_value == "tester":
        runtime_tone = "err"
        runtime_label = "DED"
        runtime_level = "ded"
        runtime_message = "กำลังปิดปรับปรุง"
    elif guild_mode_value == "whitelist":
        runtime_tone = "ok"
        runtime_label = "LIVE"
        runtime_level = "live"
        runtime_message = "บอทยังไม่พร้อมทำงานทุกกิลด์"
    elif runtime_level in {"ok", "online", "running"}:
        runtime_tone = "ok"
        runtime_label = "ONLINE"
        runtime_level = "online"
        runtime_message = runtime_message or "Bot is running normally."
    else:
        runtime_tone = "unknown"
        runtime_label = "UNKNOWN"
        runtime_level = "unknown"
        runtime_message = runtime_message or "Runtime state is not available yet."

    if status_override_level in {"online", "idle", "dnd", "offline"}:
        if status_override_level == "idle":
            runtime_tone = "loading"
            runtime_label = "IDLE"
            runtime_level = "idle"
            runtime_message = status_override_primary_message or "Bot is idle."
        elif status_override_level == "dnd":
            runtime_tone = "err"
            runtime_label = "DND"
            runtime_level = "dnd"
            runtime_message = status_override_primary_message or "Do not disturb."
        elif status_override_level == "offline":
            runtime_tone = "err"
            runtime_label = "OFFLINE"
            runtime_level = "offline"
            runtime_message = status_override_primary_message or "บอทถูกปิดอยู่"
        else:
            runtime_tone = "ok"
            runtime_label = "ONLINE"
            runtime_level = "online"
            if status_override_primary_message:
                runtime_message = status_override_primary_message
            elif status_override_activity in {"playing", "streaming", "listening", "watching", "competing"}:
                runtime_message = "SkylineBot"
            else:
                runtime_message = "Bot is running normally."

    runtime_age_seconds = int(time.time() - runtime_updated_at) if runtime_updated_at > 0 else None
    runtime_meta = (
        f"Last update {runtime_age_seconds}s ago"
        if isinstance(runtime_age_seconds, int) and runtime_age_seconds >= 0
        else "No runtime timestamp yet"
    )
    runtime_status_payload = dict(discord_runtime_payload)
    runtime_status_payload["level"] = runtime_level
    runtime_status_payload["message"] = runtime_message
    runtime_status_json = json.dumps(runtime_status_payload, ensure_ascii=False)

    redeem_summary_map = dict(redeem_summary or {}) if isinstance(redeem_summary, dict) else {}
    wallet_summary_map = dict(wallet_summary or {}) if isinstance(wallet_summary, dict) else {}

    total_codes = int(redeem_summary_map.get("total_codes") or len(redeem_rows))
    total_claimed = int(
        redeem_summary_map.get("claimed_codes")
        if redeem_summary_map.get("claimed_codes") is not None
        else len([row for row in redeem_rows if isinstance(row, dict) and bool(row.get("claimed"))])
    )
    total_unclaimed = int(
        redeem_summary_map.get("unclaimed_codes")
        if redeem_summary_map.get("unclaimed_codes") is not None
        else max(0, total_codes - total_claimed)
    )
    total_wallet_users = int(
        wallet_summary_map.get("total_wallet_users")
        if wallet_summary_map.get("total_wallet_users") is not None
        else len(wallet_rows)
    )
    wallet_positive_users = int(
        wallet_summary_map.get("wallet_positive_users")
        if wallet_summary_map.get("wallet_positive_users") is not None
        else len([row for row in wallet_rows if float((row or {}).get("balance") or 0) > 0])
    )
    wallet_balance_total_text = str(
        wallet_summary_map.get("wallet_balance_total_text")
        or f"{float(wallet_summary_map.get('wallet_balance_total') or 0.0):,.2f}"
    )

    def _plan_bucket(raw_value: Any) -> str:
        text = str(raw_value or "").strip().lower()
        if text in {"", "free", "none"}:
            return "free"
        if "silver" in text:
            return "silver"
        if "gold" in text or "golden" in text:
            return "golden"
        if "diamond" in text:
            return "diamond"
        if "permanent" in text or "lifetime" in text:
            return "permanent"
        return "other"

    plan_counts = {"free": 0, "silver": 0, "golden": 0, "diamond": 0, "permanent": 0, "other": 0}
    for row in guild_rows:
        if isinstance(row, dict):
            plan_counts[_plan_bucket(row.get("subscription"))] += 1

    total_guilds = len(guild_rows)
    whitelist_count = len(runtime_settings.get("whitelist_guild_ids", []) or [])
    blacklist_count = len(runtime_settings.get("blacklist_guild_ids", []) or [])
    tester_guild_count = len(runtime_settings.get("tester_guild_ids", []) or [])
    disabled_commands_count = len(runtime_settings.get("global_disabled_commands", []) or [])
    hidden_tabs_count = len(_ownerbot_hidden_dashboard_tabs(runtime_settings))

    runtime_control_chips_markup = "".join(
        [
            '<span class="ownerbot-runtime-control-chip ' + ("on" if bool(runtime_settings.get("global_command_response_enabled", True)) else "off") + '">Command Response: ' + ("ON" if bool(runtime_settings.get("global_command_response_enabled", True)) else "OFF") + "</span>",
            '<span class="ownerbot-runtime-control-chip ' + ("on" if bool(runtime_settings.get("global_bot_response_enabled", True)) else "off") + '">Bot Response: ' + ("ON" if bool(runtime_settings.get("global_bot_response_enabled", True)) else "OFF") + "</span>",
            '<span class="ownerbot-runtime-control-chip ' + ("on" if tester_enabled_value else "off") + '">Tester Mode: ' + ("ON" if tester_enabled_value else "OFF") + "</span>",
        ]
    )

    guild_mode_labels = {
        "all": "All Guilds",
        "whitelist": "Whitelist Only",
        "blacklist": "Blacklist Mode",
        "tester": "Tester Only",
    }
    guild_mode_label = guild_mode_labels.get(guild_mode_value, "All Guilds")

    plan_chart_payload = {
        "labels": ["Free", "Silver", "Gole", "Diamond", "Permanent"],
        "values": [
            int(plan_counts.get("free") or 0),
            int(plan_counts.get("silver") or 0),
            int(plan_counts.get("golden") or 0),
            int(plan_counts.get("diamond") or 0),
            int(plan_counts.get("permanent") or 0),
        ],
    }
    plan_chart_json = json.dumps(plan_chart_payload, ensure_ascii=False)

    mongo_rows = list(mongo_cluster_rows or [])
    mongo_total_clusters = max(int(mongo_uris_count or 0), len(mongo_rows))
    mongo_online_clusters = max(0, min(int(mongo_healthy_count or 0), mongo_total_clusters if mongo_total_clusters > 0 else 0))
    mongo_quota_hits = max(0, int(mongo_quota_warning_count or 0))
    mongo_cluster_rows_markup = ""
    mongo_size_chart_payload = {"labels": [], "storage_mb": [], "data_mb": []}
    mongo_health_chart_payload = {"labels": [], "read_rate": [], "write_rate": []}
    for row in mongo_rows:
        if not isinstance(row, dict):
            continue
        row_index = int(row.get("index") or 0)
        row_host = str(row.get("host") or f"cluster-{row_index}" if row_index > 0 else "-")
        row_ok = bool(row.get("ok"))
        row_status = "ONLINE" if row_ok else "ERROR"
        row_detail = str(row.get("detail") or "").strip()
        status_attr = f' title="{_escape(row_detail)}"' if row_detail else ""
        row_latency = int(row.get("latency_ms") or 0)
        row_collections = int(row.get("collections_total") or 0)
        storage_mb = round(float(row.get("storage_size_bytes") or 0) / (1024 * 1024), 2)
        data_mb = round(float(row.get("data_size_bytes") or 0) / (1024 * 1024), 2)
        read_rate = float(row.get("read_success_rate") or 0.0)
        write_rate = float(row.get("write_success_rate") or 0.0)
        label = f"#{row_index} {row_host}" if row_index > 0 else row_host
        mongo_size_chart_payload["labels"].append(label)
        mongo_size_chart_payload["storage_mb"].append(storage_mb)
        mongo_size_chart_payload["data_mb"].append(data_mb)
        mongo_health_chart_payload["labels"].append(label)
        mongo_health_chart_payload["read_rate"].append(round(read_rate * 100, 2))
        mongo_health_chart_payload["write_rate"].append(round(write_rate * 100, 2))
        mongo_cluster_rows_markup += (
            "<tr>"
            f"<td>{_escape(label)}</td>"
            f"<td{status_attr}>{_escape(row_status)}</td>"
            f"<td>{_escape(str(row_latency))}</td>"
            f"<td>{_escape(str(row_collections))}</td>"
            f"<td>{_escape(f'{storage_mb:,.2f}')}</td>"
            f"<td>{_escape(f'{data_mb:,.2f}')}</td>"
            "</tr>"
        )
    if not mongo_cluster_rows_markup:
        mongo_cluster_rows_markup = '<tr><td colspan="6" class="muted">No Mongo cluster data.</td></tr>'
    mongo_size_chart_json = json.dumps(mongo_size_chart_payload, ensure_ascii=False)
    mongo_health_chart_json = json.dumps(mongo_health_chart_payload, ensure_ascii=False)

    recent_redeem_rows_markup = ""
    for row in list(redeem_rows or [])[:8]:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "-")
        code_type = str(REDEEM_CODE_TYPES.get(str(row.get("code_value") or ""), str(row.get("code_value") or "-")))
        status = "used" if bool(row.get("claimed")) else "unused"
        created_at_text = _format_datetime_th(row.get("created_at"))
        claimed_by = str(row.get("claimed_by") or "-")
        recent_redeem_rows_markup += (
            "<tr>"
            f"<td><code>{_escape(code)}</code></td>"
            f"<td>{_escape(code_type)}</td>"
            f"<td>{_escape(status)}</td>"
            f"<td>{_escape(created_at_text)}</td>"
            f"<td>{_escape(claimed_by)}</td>"
            "</tr>"
        )
    if not recent_redeem_rows_markup:
        recent_redeem_rows_markup = '<tr><td colspan="5" class="muted">No redeem data.</td></tr>'

    overview_live_seed_json = json.dumps(
        {
            "runtime": runtime_status_payload,
            "kpi": {
                "total_codes": total_codes,
                "total_unclaimed": total_unclaimed,
                "total_claimed": total_claimed,
                "total_guilds": total_guilds,
                "disabled_commands_count": disabled_commands_count,
                "hidden_tabs_count": hidden_tabs_count,
                "total_wallet_users": total_wallet_users,
                "wallet_balance_total_text": wallet_balance_total_text,
                "wallet_positive_users": wallet_positive_users,
                "whitelist_count": whitelist_count,
                "blacklist_count": blacklist_count,
                "tester_guild_count": tester_guild_count,
            },
            "plan_counts": plan_counts,
            "mongo": {
                "uris_count": mongo_total_clusters,
                "healthy_count": mongo_online_clusters,
                "quota_warning_count": mongo_quota_hits,
                "rows": mongo_rows,
            },
            "charts": {
                "plan": plan_chart_payload,
                "mongo_size": mongo_size_chart_payload,
                "mongo_health": mongo_health_chart_payload,
            },
            "recent_redeem_rows": [
                {
                    "code": str(row.get("code") or "-"),
                    "type": str(REDEEM_CODE_TYPES.get(str(row.get("code_value") or ""), str(row.get("code_value") or "-"))),
                    "status": "used" if bool(row.get("claimed")) else "unused",
                    "created_at": _format_datetime_th(row.get("created_at")),
                    "claimed_by": str(row.get("claimed_by") or "-"),
                }
                for row in list(redeem_rows or [])[:8]
                if isinstance(row, dict)
            ],
        },
        ensure_ascii=False,
    )
    overview_seed_json = overview_live_seed_json

    body = _render_dashboard_f_template("ownerbot_console_page.html", locals())
    if overview_only:
        return _render_layout(title="ภาพรวม OwnerBOT", body=body, session=session)

    notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""
    allowed_settings_sections = ("runtime", "payment", "mongo", "redeem", "wallet", "guild", "promote")
    settings_active_section = str(settings_active_section or "runtime").strip().lower()
    if settings_active_section not in allowed_settings_sections:
        settings_active_section = "runtime"
    settings_active_runtime_page = _ownerbot_normalize_runtime_subpage(
        settings_active_runtime_page,
        _OWNERBOT_RUNTIME_SUBPAGE_DEFAULT,
    )
    settings_section_base_path = "/dashboard/admin/ownerbot/settings"
    settings_runtime_subpage_base_path = f"{settings_section_base_path}/runtime"
    settings_section_runtime_url = f"{settings_runtime_subpage_base_path}/{_OWNERBOT_RUNTIME_SUBPAGE_DEFAULT}"
    settings_section_payment_url = f"{settings_section_base_path}/payment"
    settings_section_mongo_url = f"{settings_section_base_path}/mongo"
    settings_section_redeem_url = f"{settings_section_base_path}/redeem"
    settings_section_wallet_url = f"{settings_section_base_path}/wallet"
    settings_section_guild_url = f"{settings_section_base_path}/guild"
    settings_section_promote_url = f"{settings_section_base_path}/promote"
    settings_runtime_overview_url = f"{settings_runtime_subpage_base_path}/overview"
    settings_runtime_ai_url = f"{settings_runtime_subpage_base_path}/ai"
    settings_runtime_vote_url = f"{settings_runtime_subpage_base_path}/vote"
    settings_runtime_dashboard_url = f"{settings_runtime_subpage_base_path}/dashboard"
    settings_runtime_commands_url = f"{settings_runtime_subpage_base_path}/commands"
    settings_runtime_social_url = f"{settings_runtime_subpage_base_path}/social"
    settings_runtime_upload_url = f"{settings_runtime_subpage_base_path}/upload"
    runtime_subpage_nav_rows = (
        ("overview", "Runtime Overview", settings_runtime_overview_url),
        ("ai", "AI Model", settings_runtime_ai_url),
        ("vote", "Vote/Webhook", settings_runtime_vote_url),
        ("dashboard", "Dashboard Tabs", settings_runtime_dashboard_url),
        ("commands", "Global Commands", settings_runtime_commands_url),
        ("social", "Developer Social", settings_runtime_social_url),
        ("upload", "Upload Storage", settings_runtime_upload_url),
    )
    runtime_subpage_nav_markup = "".join(
        (
            f'<a class="ghost-btn ownerbot-section-tab {"is-active" if settings_active_runtime_page == slug else ""}" '
            f'href="{_escape(url)}">{_escape(label)}</a>'
        )
        for slug, label, url in runtime_subpage_nav_rows
    )
    settings_render_runtime = settings_active_section == "runtime"
    settings_render_payment = settings_active_section == "payment"
    settings_render_mongo = settings_active_section == "mongo"
    settings_render_redeem = settings_active_section == "redeem"
    settings_render_wallet = settings_active_section == "wallet"
    settings_render_guild = settings_active_section == "guild"
    settings_render_promote = settings_active_section == "promote"
    code_options = "".join(
        f'<option value="{_escape(code_value)}">{_escape(code_label)}</option>'
        for code_value, code_label in REDEEM_CODE_TYPES.items()
    )
    runtime_settings = _normalize_ownerbot_runtime_settings(runtime_settings)
    discordbotlist_vote_result_channel_id = str(runtime_settings.get("discordbotlist_vote_result_channel_id") or "").strip()
    discordbotlist_vote_embed_channel_id = str(runtime_settings.get("discordbotlist_vote_embed_channel_id") or "").strip()
    discordbotlist_vote_button_url = str(runtime_settings.get("discordbotlist_vote_button_url") or "").strip()
    discordbotlist_vote_webhook_secret = str(runtime_settings.get("discordbotlist_vote_webhook_secret") or "").strip()
    whitelist_text = ", ".join(runtime_settings.get("whitelist_guild_ids", []))
    blacklist_text = ", ".join(runtime_settings.get("blacklist_guild_ids", []))
    tester_text = ", ".join(runtime_settings.get("tester_guild_ids", []))
    hidden_tabs_set = _ownerbot_hidden_dashboard_tabs(runtime_settings)
    disabled_commands_text = "\n".join(runtime_settings.get("global_disabled_commands", []))
    selected_global_ai_provider = _normalize_ownerbot_ai_provider(
        runtime_settings.get("global_ai_provider"),
        fallback="opentyphoon",
    )
    selected_global_ai_model = str(runtime_settings.get("global_ai_model") or "").strip()
    ai_provider_options = "".join(
        (
            f'<option value="{_escape(provider)}" '
            f'{"selected" if provider == selected_global_ai_provider else ""}>'
            f'{_escape(OWNERBOT_AI_PROVIDER_LABELS.get(provider, provider.title()))}'
            "</option>"
        )
        for provider in OWNERBOT_AI_PROVIDERS
    )
    ai_model_options = "".join(
        f'<option value="{_escape(row.get("value") or "")}" '
        f'data-provider="{_escape(_normalize_ownerbot_ai_provider(row.get("provider"), fallback="opentyphoon"))}" '
        f'{"selected" if str(row.get("value") or "") == selected_global_ai_model else ""}>'
        f'{_escape(row.get("label") or row.get("value") or "")}'
        "</option>"
        for row in OWNERBOT_AI_MODEL_RAM_GUIDE
    )
    ai_model_ram_rows = "".join(
        (
            f'<tr data-provider="{_escape(_normalize_ownerbot_ai_provider(row.get("provider"), fallback="opentyphoon"))}">'
            f'<td>{_escape(OWNERBOT_AI_PROVIDER_LABELS.get(_normalize_ownerbot_ai_provider(row.get("provider"), fallback="opentyphoon"), "OpenTyphoon"))}</td>'
            f'<td><code>{_escape(row.get("value") or "")}</code></td>'
            f'<td>{_escape(row.get("model_size") or "-")}</td>'
            f'<td>{_escape(row.get("min_ram") or "-")}</td>'
            "</tr>"
        )
        for row in OWNERBOT_AI_MODEL_RAM_GUIDE
    )
    ai_model_guide_json = json.dumps(list(OWNERBOT_AI_MODEL_RAM_GUIDE), ensure_ascii=False)
    ai_provider_labels_json = json.dumps(OWNERBOT_AI_PROVIDER_LABELS, ensure_ascii=False)
    developer_social_rows: list[dict[str, str]] = []
    developer_social_payload = runtime_settings.get("developer_social_links") or {}
    if isinstance(developer_social_payload, dict):
        for dev_id, dev_links in developer_social_payload.items():
            dev_id_text = str(dev_id or "").strip()
            if not dev_id_text:
                continue
            row_dev_id = "" if dev_id_text == DEFAULT_DEVELOPER_SOCIAL_KEY else dev_id_text
            for platform in SOCIAL_PLATFORM_KEYS:
                platform_url = _developer_social_url(dev_links, platform, "")
                if not platform_url:
                    continue
                developer_social_rows.append(
                    {
                        "dev_id": row_dev_id,
                        "platform": platform,
                        "url": platform_url,
                        "icon": _developer_social_icon(dev_links, platform),
                    }
                )
    selected_disabled_commands_json = json.dumps(runtime_settings.get("global_disabled_commands", []), ensure_ascii=False)
    social_rows_json = json.dumps(developer_social_rows, ensure_ascii=False)
    social_platform_keys_json = json.dumps(list(SOCIAL_PLATFORM_KEYS), ensure_ascii=False)
    social_platform_labels_json = json.dumps(SOCIAL_PLATFORM_LABELS, ensure_ascii=False)
    social_platform_icons_json = json.dumps(SOCIAL_PLATFORM_DEFAULT_ICONS, ensure_ascii=False)
    payment_provider_raw = payment_provider_settings if isinstance(payment_provider_settings, dict) else {}
    payment_provider_choices = ("promptpay", "bank", "gateway", "truemoney", "stripe")
    topup_provider = str(payment_provider_raw.get("topup_provider") or "promptpay").strip().lower()
    donate_provider = str(payment_provider_raw.get("donate_provider") or "promptpay").strip().lower()
    payment_enable_bank_provider = bool(payment_provider_raw.get("enable_bank_provider", True))
    payment_enable_gateway_provider = bool(payment_provider_raw.get("enable_gateway_provider", True))
    payment_enable_stripe_provider = bool(payment_provider_raw.get("enable_stripe_provider", True))
    payment_enable_truemoney_qr_provider = bool(payment_provider_raw.get("enable_truemoney_qr_provider", True))
    if topup_provider not in payment_provider_choices:
        topup_provider = "promptpay"
    if donate_provider not in payment_provider_choices:
        donate_provider = "promptpay"
    payment_provider_guide_text = {
        "promptpay": "Use PromptPay/TrueMoney as the primary payment channel.",
        "bank": "Receive bank transfer payments and verify by manual slip or webhook auto mode.",
        "gateway": "Receive payment confirmations from external gateway via webhook.",
        "stripe": "Stripe Checkout + webhook + inquiry auto verification",
        "truemoney": "TrueMoney QR + callback + inquiry auto verify",
    }
    payment_promptpay_account_name = str(payment_provider_raw.get("promptpay_account_name") or "").strip()
    payment_promptpay_number = str(payment_provider_raw.get("promptpay_number") or "").strip()
    payment_truemoney_phone = str(payment_provider_raw.get("truemoney_phone") or "").strip()
    payment_truemoney_gift_phone = str(payment_provider_raw.get("truemoney_gift_phone") or "").strip()
    payment_truemoney_gift_url = str(payment_provider_raw.get("truemoney_gift_url") or "").strip()
    payment_bank_topup_verification_mode = str(payment_provider_raw.get("bank_topup_verification_mode") or "manual_slip").strip().lower()
    if payment_bank_topup_verification_mode not in {"manual_slip", "webhook_auto"}:
        payment_bank_topup_verification_mode = "manual_slip"
    payment_bank_donate_verification_mode = str(
        payment_provider_raw.get("bank_donate_verification_mode") or payment_bank_topup_verification_mode
    ).strip().lower()
    if payment_bank_donate_verification_mode not in {"manual_slip", "webhook_auto"}:
        payment_bank_donate_verification_mode = payment_bank_topup_verification_mode
    payment_bank_name = str(payment_provider_raw.get("bank_name") or "").strip()
    payment_bank_account_name = str(payment_provider_raw.get("bank_account_name") or "").strip()
    payment_bank_account_number = str(payment_provider_raw.get("bank_account_number") or "").strip()
    payment_gateway_name = str(payment_provider_raw.get("gateway_name") or "").strip()
    payment_webhook_secret = str(payment_provider_raw.get("webhook_secret") or "").strip()
    payment_gateway_webhook_secret = str(payment_provider_raw.get("gateway_webhook_secret") or "").strip()
    payment_gateway_signature_header = str(payment_provider_raw.get("gateway_signature_header") or "x-gateway-signature").strip()
    payment_gateway_signature_prefix = str(payment_provider_raw.get("gateway_signature_prefix") or "").strip()
    payment_gateway_signature_algorithm = str(payment_provider_raw.get("gateway_signature_algorithm") or "sha256").strip().lower()
    payment_gateway_session_field = str(payment_provider_raw.get("gateway_metadata_session_key_field") or "metadata.session_key").strip()
    payment_stripe_secret_key = str(payment_provider_raw.get("stripe_secret_key") or "").strip()
    payment_stripe_publishable_key = str(payment_provider_raw.get("stripe_publishable_key") or "").strip()
    payment_stripe_webhook_secret = str(
        payment_provider_raw.get("stripe_webhook_secret")
        or payment_provider_raw.get("webhook_secret")
        or ""
    ).strip()
    payment_stripe_signature_header = str(payment_provider_raw.get("stripe_signature_header") or "stripe-signature").strip().lower()
    payment_stripe_signature_tolerance_seconds = str(payment_provider_raw.get("stripe_signature_tolerance_seconds") or "300").strip()
    payment_stripe_api_base_url = str(payment_provider_raw.get("stripe_api_base_url") or "https://api.stripe.com").strip()
    payment_stripe_checkout_session_url = str(
        payment_provider_raw.get("stripe_checkout_session_url") or "https://api.stripe.com/v1/checkout/sessions"
    ).strip()
    payment_stripe_inquiry_url = str(
        payment_provider_raw.get("stripe_inquiry_url") or "https://api.stripe.com/v1/checkout/sessions"
    ).strip()
    payment_stripe_success_url = str(payment_provider_raw.get("stripe_success_url") or "").strip()
    payment_stripe_cancel_url = str(payment_provider_raw.get("stripe_cancel_url") or "").strip()
    payment_stripe_auto_verify = bool(payment_provider_raw.get("stripe_auto_verify", True))
    payment_truemoney_create_payment_url = str(payment_provider_raw.get("truemoney_create_payment_url") or "").strip()
    payment_truemoney_inquiry_url = str(payment_provider_raw.get("truemoney_inquiry_url") or "").strip()
    payment_truemoney_api_key = str(payment_provider_raw.get("truemoney_api_key") or "").strip()
    payment_truemoney_api_secret = str(payment_provider_raw.get("truemoney_api_secret") or "").strip()
    payment_truemoney_bearer_token = str(payment_provider_raw.get("truemoney_bearer_token") or "").strip()
    payment_truemoney_callback_url = str(payment_provider_raw.get("truemoney_callback_url") or "").strip()
    payment_truemoney_webhook_secret = str(
        payment_provider_raw.get("truemoney_webhook_secret")
        or payment_provider_raw.get("webhook_secret")
        or ""
    ).strip()
    payment_truemoney_signature_header = str(payment_provider_raw.get("truemoney_signature_header") or "x-truemoney-signature").strip()
    payment_truemoney_signature_prefix = str(payment_provider_raw.get("truemoney_signature_prefix") or "").strip()
    payment_truemoney_signature_algorithm = str(payment_provider_raw.get("truemoney_signature_algorithm") or "sha256").strip().lower()
    payment_truemoney_amount_field = str(payment_provider_raw.get("truemoney_amount_field") or "amount").strip()
    payment_truemoney_currency_field = str(payment_provider_raw.get("truemoney_currency_field") or "currency").strip()
    payment_truemoney_reference_field = str(payment_provider_raw.get("truemoney_reference_field") or "reference").strip()
    payment_truemoney_callback_field = str(payment_provider_raw.get("truemoney_callback_field") or "callbackUrl").strip()
    payment_truemoney_qr_image_field = str(payment_provider_raw.get("truemoney_qr_image_field") or "data.qrImageUrl").strip()
    payment_truemoney_qr_code_field = str(payment_provider_raw.get("truemoney_qr_code_field") or "data.qrRawData").strip()
    payment_truemoney_payment_url_field = str(payment_provider_raw.get("truemoney_payment_url_field") or "data.paymentUrl").strip()
    payment_truemoney_reference_resp_field = str(payment_provider_raw.get("truemoney_reference_resp_field") or "data.orderId").strip()
    payment_truemoney_transaction_id_field = str(payment_provider_raw.get("truemoney_transaction_id_field") or "data.transactionId").strip()
    payment_truemoney_inquiry_status_field = str(payment_provider_raw.get("truemoney_inquiry_status_field") or "data.status").strip()
    payment_truemoney_paid_status_values = str(
        payment_provider_raw.get("truemoney_paid_status_values") or "paid,success,completed,settled"
    ).strip()
    payment_truemoney_auto_verify = bool(payment_provider_raw.get("truemoney_auto_verify", True))
    payment_slipok_api_url = str(
        payment_provider_raw.get("slipok_api_url")
        or "https://api.slipok.com/api/line/apikey/1150"
    ).strip() or "https://api.slipok.com/api/line/apikey/1150"
    payment_slipok_key = str(payment_provider_raw.get("slipok_key") or "").strip()
    payment_slipcheck_verify_engine = str(payment_provider_raw.get("slipcheck_verify_engine") or "slipok").strip().lower()
    if payment_slipcheck_verify_engine not in {"slipok", "skylinebotslip"}:
        payment_slipcheck_verify_engine = "slipok"
    payment_slipcheck_expected_receiver_name = str(payment_provider_raw.get("slipcheck_expected_receiver_name") or "").strip()
    payment_slipcheck_expected_receiver_first_name_th = str(payment_provider_raw.get("slipcheck_expected_receiver_first_name_th") or "").strip()
    payment_slipcheck_expected_receiver_last_name_th = str(payment_provider_raw.get("slipcheck_expected_receiver_last_name_th") or "").strip()
    payment_slipcheck_expected_receiver_first_name_en = str(payment_provider_raw.get("slipcheck_expected_receiver_first_name_en") or "").strip()
    payment_slipcheck_expected_receiver_last_name_en = str(payment_provider_raw.get("slipcheck_expected_receiver_last_name_en") or "").strip()
    payment_slipcheck_expected_receiver_bank = str(payment_provider_raw.get("slipcheck_expected_receiver_bank") or "").strip()
    payment_slipcheck_expected_receiver_account = str(payment_provider_raw.get("slipcheck_expected_receiver_account") or "").strip()
    payment_slipcheck_expected_sender_name = str(payment_provider_raw.get("slipcheck_expected_sender_name") or "").strip()
    payment_slipcheck_expected_sender_first_name_th = str(payment_provider_raw.get("slipcheck_expected_sender_first_name_th") or "").strip()
    payment_slipcheck_expected_sender_last_name_th = str(payment_provider_raw.get("slipcheck_expected_sender_last_name_th") or "").strip()
    payment_slipcheck_expected_sender_first_name_en = str(payment_provider_raw.get("slipcheck_expected_sender_first_name_en") or "").strip()
    payment_slipcheck_expected_sender_last_name_en = str(payment_provider_raw.get("slipcheck_expected_sender_last_name_en") or "").strip()
    payment_slipcheck_expected_sender_bank = str(payment_provider_raw.get("slipcheck_expected_sender_bank") or "").strip()
    payment_slipcheck_expected_sender_account = str(payment_provider_raw.get("slipcheck_expected_sender_account") or "").strip()
    payment_slipcheck_expected_reference = str(payment_provider_raw.get("slipcheck_expected_reference") or "").strip()
    payment_slipcheck_expected_qr_reference = str(payment_provider_raw.get("slipcheck_expected_qr_reference") or "").strip()
    payment_slipcheck_max_age_minutes = str(payment_provider_raw.get("slipcheck_max_age_minutes") or "1440").strip()
    payment_slipcheck_auto_approve_confidence = str(payment_provider_raw.get("slipcheck_auto_approve_confidence") or "85").strip()
    payment_slipcheck_manual_review_confidence = str(payment_provider_raw.get("slipcheck_manual_review_confidence") or "55").strip()
    payment_slipcheck_duplicate_window_hours = str(payment_provider_raw.get("slipcheck_duplicate_window_hours") or "72").strip()
    payment_slipcheck_review_channel_id = str(payment_provider_raw.get("slipcheck_review_channel_id") or "").strip()
    payment_slipcheck_review_dm_user_ids = str(payment_provider_raw.get("slipcheck_review_dm_user_ids") or "").strip()
    payment_slipcheck_low_confidence_route = str(
        payment_provider_raw.get("slipcheck_low_confidence_route") or "both"
    ).strip().lower()
    if payment_slipcheck_low_confidence_route not in {"channel", "dm", "both"}:
        payment_slipcheck_low_confidence_route = "both"

    pricing_settings_raw = plan_pricing_settings if isinstance(plan_pricing_settings, dict) else {}
    pricing_snapshot_raw = plan_pricing_snapshot if isinstance(plan_pricing_snapshot, dict) else {}
    pricing_quotes_raw = pricing_snapshot_raw.get("quotes") if isinstance(pricing_snapshot_raw.get("quotes"), dict) else {}
    pricing_guild_prices = pricing_settings_raw.get("guild_prices") if isinstance(pricing_settings_raw.get("guild_prices"), dict) else {}
    pricing_promotions = pricing_settings_raw.get("promotions") if isinstance(pricing_settings_raw.get("promotions"), dict) else {}

    def _promo_datetime_text(raw_value: Any) -> str:
        if isinstance(raw_value, datetime.datetime):
            return _format_datetime_th(raw_value)
        text = str(raw_value or "").strip()
        if not text:
            return "-"
        parsed: datetime.datetime | None = None
        try:
            if text.isdigit():
                epoch = float(text)
                if epoch > 10_000_000_000:
                    epoch /= 1000.0
                parsed = datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc)
            else:
                parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            parsed = None
        return _format_datetime_th(parsed)

    def _pricing_status_text(quote_payload: dict[str, Any]) -> str:
        status = str(quote_payload.get("promo_status") or "inactive").strip().lower()
        if status == "active":
            end_text = _promo_datetime_text(quote_payload.get("promo_end_at"))
            percent = float(quote_payload.get("discount_percent") or 0.0)
            return f"กำลังลด {percent:.2f}% ถึง {end_text}"
        if status == "scheduled":
            start_text = _promo_datetime_text(quote_payload.get("promo_start_at"))
            return f"ตั้งเวลาโปรไว้ เริ่ม {start_text}"
        if status == "expired":
            end_text = _promo_datetime_text(quote_payload.get("promo_end_at"))
            return f"โปรหมดแล้ว ({end_text})"
        return "ไม่มีโปร"

    def _promo_value_for_key(key: str, field: str, default_value: Any) -> Any:
        raw_entry = pricing_promotions.get(key) if isinstance(pricing_promotions.get(key), dict) else {}
        value = raw_entry.get(field)
        if value is None:
            return default_value
        return value

    pricing_rows_catalog = [
        ("silver", "Silver", float(pricing_guild_prices.get("silver") or 40.0)),
        ("golden", "Gole", float(pricing_guild_prices.get("golden") or 120.0)),
        ("diamond", "Diamond", float(pricing_guild_prices.get("diamond") or 250.0)),
        ("permanent", "Permanent", float(pricing_guild_prices.get("permanent") or 500.0)),
        ("app_user", "Discord App User Plan", float(pricing_settings_raw.get("user_app_price") or 69.0)),
    ]
    plan_pricing_rows_markup_parts: list[str] = []
    for key, label, default_price in pricing_rows_catalog:
        # Recompute quote from current settings to avoid stale snapshot status after save/reset.
        if key == billing_workflow.USER_APP_PLAN_CODE:
            quote_payload = billing_workflow.build_user_app_price_quote(settings=pricing_settings_raw)
        else:
            quote_payload = billing_workflow.build_plan_price_quote(key, settings=pricing_settings_raw)
        if not isinstance(quote_payload, dict):
            quote_payload = pricing_quotes_raw.get(key) if isinstance(pricing_quotes_raw.get(key), dict) else {}
        base_price_value = float(quote_payload.get("base_price") or default_price or 0.0)
        final_price_value = float(quote_payload.get("final_price") or base_price_value)
        price_field_key = "user_app" if key == "app_user" else key
        discount_percent_value = float(_promo_value_for_key(key, "discount_percent", quote_payload.get("discount_percent") or 0.0) or 0.0)
        duration_value = int(_promo_value_for_key(key, "duration_value", quote_payload.get("promo_duration_value") or 0) or 0)
        duration_unit = str(_promo_value_for_key(key, "duration_unit", quote_payload.get("promo_duration_unit") or "day") or "day").strip().lower()
        if duration_unit not in {"day", "month"}:
            duration_unit = "day"
        status_text = _pricing_status_text(quote_payload)
        plan_pricing_rows_markup_parts.append(
            f"""
            <article class="ownerbot-pricing-row">
              <h4>{_escape(label)}</h4>
              <div class="field-grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin-top:8px;">
                <label>ราคาปกติ (THB)
                  <input type="number" name="price_{_escape(price_field_key)}" min="0" max="1000000" step="0.01" value="{base_price_value:.2f}">
                </label>
                <label>ส่วนลด (%)
                  <input type="number" name="promo_{_escape(key)}_discount_percent" min="0" max="100" step="0.01" value="{discount_percent_value:.2f}">
                </label>
                <label>ระยะเวลาโปร
                  <input type="number" name="promo_{_escape(key)}_duration_value" min="0" max="1200" step="1" value="{duration_value}">
                </label>
                <label>หน่วยระยะเวลา
                  <select name="promo_{_escape(key)}_duration_unit">
                    <option value="day" {"selected" if duration_unit == "day" else ""}>วัน</option>
                    <option value="month" {"selected" if duration_unit == "month" else ""}>เดือน</option>
                  </select>
                </label>
              </div>
              <small class="muted">ราคาที่ใช้งานตอนนี้: <strong>{base_price_value:,.2f} THB</strong> -> <strong>{final_price_value:,.2f} THB</strong> | {status_text}</small>
            </article>
            """
        )
    plan_pricing_rows_markup = "".join(plan_pricing_rows_markup_parts)

    upload_settings = upload_channel_settings if isinstance(upload_channel_settings, dict) else {}
    upload_channels_payload = upload_settings.get("channels")
    upload_channels_map = upload_channels_payload if isinstance(upload_channels_payload, dict) else {}
    storage_guild_id = str(upload_settings.get("storage_guild_id") or "").strip()
    if not storage_guild_id:
        first_guild = next((row for row in upload_guild_rows if str(row.get("id") or "").strip().isdigit()), None)
        storage_guild_id = str((first_guild or {}).get("id") or "").strip()

    upload_channels_by_guild: dict[str, list[dict[str, str]]] = {}
    for channel_row in upload_channel_rows:
        row = channel_row if isinstance(channel_row, dict) else {}
        gid = str(row.get("guild_id") or "").strip()
        cid = str(row.get("id") or "").strip()
        cname = str(row.get("name") or "").strip()
        if not gid or not cid:
            continue
        upload_channels_by_guild.setdefault(gid, []).append(
            {
                "id": cid,
                "name": cname,
                "label": str(row.get("label") or f"#{cname}" if cname else cid),
            }
        )
    for gid, rows in upload_channels_by_guild.items():
        rows.sort(key=lambda item: str(item.get("name") or "").lower())

    upload_guild_options_markup = "".join(
        f'<option value="{_escape(str(row.get("id") or ""))}" {"selected" if str(row.get("id") or "") == storage_guild_id else ""}>'
        f'{_escape(str(row.get("name") or row.get("id") or ""))} ({_escape(str(row.get("id") or ""))})'
        "</option>"
        for row in upload_guild_rows
        if str(row.get("id") or "").strip()
    )
    available_storage_channels = upload_channels_by_guild.get(storage_guild_id, [])
    upload_target_rows_markup = ""
    configured_upload_targets = 0
    for target in OWNERBOT_UPLOAD_TARGETS:
        saved_channel_id = str(upload_channels_map.get(target) or "").strip()
        if saved_channel_id:
            configured_upload_targets += 1
        select_options = ['<option value="">-- ไม่กำหนด (ใช้ fallback อัตโนมัติ) --</option>']
        for channel_row in available_storage_channels:
            cid = str(channel_row.get("id") or "").strip()
            select_options.append(
                f'<option value="{_escape(cid)}" {"selected" if cid == saved_channel_id else ""}>'
                f'{_escape(str(channel_row.get("label") or cid))}'
                "</option>"
            )
        default_channel_name = str(OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS.get(target) or "").strip()
        upload_target_rows_markup += (
            '<article class="ownerbot-upload-row">'
            f'<div><strong>{_escape(OWNERBOT_UPLOAD_TARGET_LABELS.get(target, target))}</strong>'
            f'<small class="muted">ชื่อห้องแนะนำ: <code>{_escape(default_channel_name or "upload-files")}</code></small></div>'
            f'<select name="channel_{_escape(target)}">{"".join(select_options)}</select>'
            "</article>"
        )
    selected_storage_guild_name = next(
        (str(row.get("name") or "") for row in upload_guild_rows if str(row.get("id") or "") == storage_guild_id),
        "",
    )

    mongo_rows = list(mongo_cluster_rows or [])
    mongo_total_clusters = max(int(mongo_uris_count or 0), len(mongo_rows))
    mongo_online_clusters = int(mongo_healthy_count or 0)
    if mongo_online_clusters < 0:
        mongo_online_clusters = 0
    if mongo_total_clusters > 0:
        mongo_online_clusters = min(mongo_online_clusters, mongo_total_clusters)
    mongo_quota_hits = max(0, int(mongo_quota_warning_count or 0))
    mongo_primary_uri = str(mongo_primary_uri or "").strip()
    mongo_database_name = str(mongo_database_name or "skylinebot").strip() or "skylinebot"
    mongo_read_mode = str(mongo_read_mode or "aggregate").strip().lower()
    if mongo_read_mode not in {"primary", "aggregate"}:
        mongo_read_mode = "aggregate"
    mongo_write_mode = str(mongo_write_mode or "hash").strip().lower()
    if mongo_write_mode not in {"primary", "hash", "broadcast"}:
        mongo_write_mode = "hash"
    mongo_migration_history_retention_days = max(0, min(3650, int(mongo_migration_history_retention_days or 0)))
    mongo_migration_history_retention_label = (
        f"{mongo_migration_history_retention_days} day(s)"
        if mongo_migration_history_retention_days > 0
        else "OFF"
    )
    mongo_health_totals = dict(mongo_health_totals or {})

    backup_uri_items: list[str] = []
    for part in str(mongo_backup_uri_text or "").replace("\r", "\n").replace(";", "\n").replace(",", "\n").split("\n"):
        value = str(part or "").strip()
        if not value or value in backup_uri_items:
            continue
        backup_uri_items.append(value)
    mongo_backup_uri_textarea = "\n".join(backup_uri_items)

    def _mongo_bytes_to_text(value: Any) -> str:
        try:
            size = float(value or 0)
        except Exception:
            size = 0.0
        if size <= 0:
            return "0 MB"
        return f"{size / (1024.0 * 1024.0):,.2f} MB"

    def _mongo_rate_text(rate_value: Any, total_ops: Any) -> str:
        try:
            total = int(total_ops or 0)
        except Exception:
            total = 0
        if total <= 0:
            return "N/A"
        try:
            rate_float = float(rate_value)
        except Exception:
            return "N/A"
        return f"{max(0.0, min(100.0, rate_float)):.2f}%"

    mongo_health_read_ok = int(mongo_health_totals.get("read_ok") or 0)
    mongo_health_read_fail = int(mongo_health_totals.get("read_fail") or 0)
    mongo_health_write_ok = int(mongo_health_totals.get("write_ok") or 0)
    mongo_health_write_fail = int(mongo_health_totals.get("write_fail") or 0)
    mongo_health_read_total = int(mongo_health_totals.get("read_total") or 0)
    mongo_health_write_total = int(mongo_health_totals.get("write_total") or 0)
    mongo_health_read_rate_text = _mongo_rate_text(mongo_health_totals.get("read_success_rate"), mongo_health_read_total)
    mongo_health_write_rate_text = _mongo_rate_text(mongo_health_totals.get("write_success_rate"), mongo_health_write_total)
    mongo_migration_history_rows = list(mongo_migration_history_rows or [])

    def _mongo_history_int(row: dict[str, Any], key: str) -> int:
        try:
            return int((row.get("totals") if isinstance(row.get("totals"), dict) else {}).get(key) or row.get(key) or 0)
        except Exception:
            return 0

    def _mongo_history_sort_epoch(row: dict[str, Any]) -> float:
        try:
            epoch_value = float(row.get("created_at_epoch") or 0.0)
        except Exception:
            epoch_value = 0.0
        if epoch_value > 0:
            return epoch_value
        created_at = row.get("created_at")
        if hasattr(created_at, "timestamp"):
            try:
                return float(created_at.timestamp())
            except Exception:
                return 0.0
        return 0.0

    mongo_migration_history_rows = sorted(
        [row for row in mongo_migration_history_rows if isinstance(row, dict)],
        key=_mongo_history_sort_epoch,
        reverse=True,
    )[:80]
    mongo_migration_history_total = len(mongo_migration_history_rows)

    mongo_history_rows_markup_parts: list[str] = []
    for row in mongo_migration_history_rows[:30]:
        created_at_text = _format_datetime_th(row.get("created_at"))
        if not str(created_at_text or "").strip() or str(created_at_text).strip() == "-":
            try:
                created_epoch = float(row.get("created_at_epoch") or 0.0)
            except Exception:
                created_epoch = 0.0
            if created_epoch > 0:
                created_at_text = str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_epoch)))
            else:
                created_at_text = "-"
        run_id_text = str(row.get("run_id") or row.get("_id") or "-")
        mode_text = str(row.get("mode") or ("execute" if bool(row.get("execute")) else "dry_run")).strip().lower()
        mode_badge = "EXECUTE" if mode_text == "execute" else "DRY-RUN"
        source_index = int(row.get("source_index") or 0)
        target_indexes = list(row.get("target_indexes") or [])
        target_text = ", ".join(f"#{int(item)}" for item in target_indexes if str(item).strip().isdigit()) or "-"
        collections_total_row = int(row.get("collections_total") or 0)
        scanned_row = _mongo_history_int(row, "scanned")
        upserted_row = _mongo_history_int(row, "upserted")
        errors_row = _mongo_history_int(row, "errors")
        ok_state = bool(row.get("ok"))
        status_label = "OK" if ok_state else "FAILED"
        status_class = "ownerbot-mongo-status-ok" if ok_state else "ownerbot-mongo-status-error"
        status_key = "ok" if ok_state else "failed"
        actor_text = str(row.get("created_by_label") or row.get("created_by_user_id") or "-")
        search_blob = " ".join(
            [
                created_at_text,
                run_id_text,
                mode_badge,
                str(source_index),
                target_text,
                str(collections_total_row),
                str(scanned_row),
                str(upserted_row),
                str(errors_row),
                status_label,
                actor_text,
            ]
        ).strip().lower()
        mongo_history_rows_markup_parts.append(
            (
                f"<tr data-mongo-history-row data-mode=\"{_escape(mode_text)}\" "
                f"data-status=\"{_escape(status_key)}\" data-search=\"{_escape(search_blob)}\" "
                f"data-run-id=\"{_escape(run_id_text)}\">"
                f"<td><input type=\"checkbox\" data-mongo-history-select value=\"{_escape(run_id_text)}\"></td>"
                f"<td>{_escape(created_at_text)}</td>"
                f"<td><code>{_escape(run_id_text[-10:])}</code></td>"
                f"<td>{_escape(mode_badge)}</td>"
                f"<td>#{source_index} -> {_escape(target_text)}</td>"
                f"<td>{collections_total_row}</td>"
                f"<td>{scanned_row}</td>"
                f"<td>{upserted_row}</td>"
                f"<td>{errors_row}</td>"
                f"<td><span class=\"ownerbot-mongo-chip {status_class}\">{_escape(status_label)}</span></td>"
                f"<td>{_escape(actor_text)}</td>"
                "</tr>"
            )
        )
    mongo_migration_history_rows_markup = "".join(mongo_history_rows_markup_parts)
    if not mongo_migration_history_rows_markup:
        mongo_migration_history_rows_markup = '<tr><td colspan="11" class="muted">No migration history log yet</td></tr>'

    mongo_cluster_chart_payload = {
        "labels": [],
        "storage_mb": [],
        "data_mb": [],
    }
    mongo_io_chart_payload = {
        "labels": [],
        "read_rate": [],
        "write_rate": [],
    }
    for row in mongo_rows:
        row_index = int((row or {}).get("index") or 0)
        row_host = str((row or {}).get("host") or f"cluster-{row_index}").strip()
        label = f"#{row_index} {row_host}" if row_index > 0 else row_host
        try:
            storage_mb = round(float((row or {}).get("storage_size_bytes") or 0.0) / (1024.0 * 1024.0), 2)
        except Exception:
            storage_mb = 0.0
        try:
            data_mb = round(float((row or {}).get("data_size_bytes") or 0.0) / (1024.0 * 1024.0), 2)
        except Exception:
            data_mb = 0.0
        read_total = int((row or {}).get("read_total") or 0)
        write_total = int((row or {}).get("write_total") or 0)
        read_rate = (row or {}).get("read_success_rate")
        write_rate = (row or {}).get("write_success_rate")
        try:
            read_rate_float = round(max(0.0, min(100.0, float(read_rate))), 2) if read_total > 0 else None
        except Exception:
            read_rate_float = None
        try:
            write_rate_float = round(max(0.0, min(100.0, float(write_rate))), 2) if write_total > 0 else None
        except Exception:
            write_rate_float = None
        mongo_cluster_chart_payload["labels"].append(label)
        mongo_cluster_chart_payload["storage_mb"].append(storage_mb)
        mongo_cluster_chart_payload["data_mb"].append(data_mb)
        mongo_io_chart_payload["labels"].append(label)
        mongo_io_chart_payload["read_rate"].append(read_rate_float)
        mongo_io_chart_payload["write_rate"].append(write_rate_float)

    mongo_history_chart_payload = {
        "labels": [],
        "scanned": [],
        "upserted": [],
        "errors": [],
    }
    chart_rows = list(reversed(mongo_migration_history_rows[:12]))
    for row in chart_rows:
        created_at = row.get("created_at")
        label_text = ""
        if hasattr(created_at, "strftime"):
            try:
                label_text = str(created_at.strftime("%m-%d %H:%M"))
            except Exception:
                label_text = ""
        if not label_text:
            label_text = str(row.get("run_id") or row.get("_id") or "-")[-6:]
        mongo_history_chart_payload["labels"].append(label_text)
        mongo_history_chart_payload["scanned"].append(_mongo_history_int(row, "scanned"))
        mongo_history_chart_payload["upserted"].append(_mongo_history_int(row, "upserted"))
        mongo_history_chart_payload["errors"].append(_mongo_history_int(row, "errors"))

    mongo_cluster_chart_json = json.dumps(mongo_cluster_chart_payload, ensure_ascii=False)
    mongo_io_chart_json = json.dumps(mongo_io_chart_payload, ensure_ascii=False)
    mongo_history_chart_json = json.dumps(mongo_history_chart_payload, ensure_ascii=False)

    mongo_read_mode_options_markup = "".join(
        [
            f'<option value="aggregate" {"selected" if mongo_read_mode == "aggregate" else ""}>Aggregate (read all clusters)</option>',
            f'<option value="primary" {"selected" if mongo_read_mode == "primary" else ""}>Primary only</option>',
        ]
    )
    mongo_write_mode_options_markup = "".join(
        [
            f'<option value="hash" {"selected" if mongo_write_mode == "hash" else ""}>Hash + failover</option>',
            f'<option value="primary" {"selected" if mongo_write_mode == "primary" else ""}>Primary only</option>',
            f'<option value="broadcast" {"selected" if mongo_write_mode == "broadcast" else ""}>Broadcast (write all clusters)</option>',
        ]
    )

    mongo_collection_option_set: set[str] = set()
    for row in mongo_rows:
        for c_row in list((row or {}).get("collection_rows") or []):
            name = str((c_row or {}).get("name") or "").strip()
            if name:
                mongo_collection_option_set.add(name)
    for item in list(mongo_collection_options or []):
        name = str(item or "").strip()
        if name:
            mongo_collection_option_set.add(name)
    mongo_collection_names_sorted = sorted(mongo_collection_option_set)
    mongo_collection_options_markup = "".join(
        f'<option value="{_escape(name)}">{_escape(name)}</option>'
        for name in mongo_collection_names_sorted
    )

    mongo_target_options_markup = ['<option value="all">All MongoDB Clusters</option>']
    mongo_single_target_options_markup: list[str] = []
    for row in mongo_rows:
        row_index = int((row or {}).get("index") or 0)
        row_host = str((row or {}).get("host") or f"cluster-{row_index}").strip()
        row_status = "ok" if bool((row or {}).get("ok")) else "error"
        mongo_target_options_markup.append(
            f'<option value="{row_index}">Mongo #{row_index} - {_escape(row_host)} ({row_status})</option>'
        )
        mongo_single_target_options_markup.append(
            f'<option value="{row_index}" {"selected" if row_index == 1 else ""}>Mongo #{row_index} - {_escape(row_host)} ({row_status})</option>'
        )
    mongo_target_options_markup = "".join(mongo_target_options_markup)
    mongo_single_target_options_markup = "".join(mongo_single_target_options_markup)
    if not mongo_single_target_options_markup:
        mongo_single_target_options_markup = '<option value="1" selected>Mongo #1</option>'

    mongo_cluster_cards_markup_parts: list[str] = []
    for row in mongo_rows:
        row_index = int((row or {}).get("index") or 0)
        row_host = str((row or {}).get("host") or f"cluster-{row_index}").strip()
        row_database = str((row or {}).get("database") or mongo_database_name).strip() or mongo_database_name
        row_ok = bool((row or {}).get("ok"))
        row_detail = str((row or {}).get("detail") or "").strip()
        row_latency_ms = int((row or {}).get("latency_ms") or 0)
        row_storage_text = _mongo_bytes_to_text((row or {}).get("storage_size_bytes"))
        row_data_text = _mongo_bytes_to_text((row or {}).get("data_size_bytes"))
        row_collections_total = int((row or {}).get("collections_total") or 0)
        row_docs_total = int((row or {}).get("estimated_documents_total") or 0)
        row_quota_warning = bool((row or {}).get("quota_warning"))
        row_read_ok = int((row or {}).get("read_ok") or 0)
        row_read_fail = int((row or {}).get("read_fail") or 0)
        row_write_ok = int((row or {}).get("write_ok") or 0)
        row_write_fail = int((row or {}).get("write_fail") or 0)
        row_read_total = int((row or {}).get("read_total") or (row_read_ok + row_read_fail))
        row_write_total = int((row or {}).get("write_total") or (row_write_ok + row_write_fail))
        row_read_rate_text = _mongo_rate_text((row or {}).get("read_success_rate"), row_read_total)
        row_write_rate_text = _mongo_rate_text((row or {}).get("write_success_rate"), row_write_total)
        row_health_error = str((row or {}).get("last_error") or "").strip()
        status_class = "ownerbot-mongo-status-ok" if row_ok else "ownerbot-mongo-status-error"
        status_label = "Connected" if row_ok else "Error"
        if row_quota_warning:
            status_label = "Quota Warning"
            status_class = "ownerbot-mongo-status-warn"

        collection_rows_markup = "".join(
            (
                "<tr>"
                f"<td><code>{_escape(str((c_row or {}).get('name') or '-'))}</code></td>"
                f"<td>{_escape(str((c_row or {}).get('estimated_count') if (c_row or {}).get('estimated_count') is not None else '-'))}</td>"
                "</tr>"
            )
            for c_row in list((row or {}).get("collection_rows") or [])
        )
        if not collection_rows_markup:
            collection_rows_markup = '<tr><td colspan="2" class="muted">No collection detail</td></tr>'
        row_health_error_markup = (
            f'<p class="muted">Last IO Error: {_escape(row_health_error)}</p>'
            if row_health_error
            else ""
        )

        mongo_cluster_cards_markup_parts.append(
            f"""
            <details class="command-category ownerbot-mongo-cluster" {"open" if row_index == 1 else ""}>
              <summary>
                <span>Mongo #{row_index} - {_escape(row_host)}</span>
                <span class="public-command-meta">{_escape(status_label)} | DB: {_escape(row_database)} | {row_latency_ms} ms</span>
              </summary>
              <div class="command-category-body">
                <div class="ownerbot-mongo-cluster-kpis">
                  <span class="ownerbot-mongo-chip {status_class}">{_escape(status_label)}</span>
                  <span class="ownerbot-mongo-chip">Collections: {_escape(row_collections_total)}</span>
                  <span class="ownerbot-mongo-chip">Estimated Docs: {_escape(row_docs_total)}</span>
                  <span class="ownerbot-mongo-chip">Storage: {_escape(row_storage_text)}</span>
                  <span class="ownerbot-mongo-chip">Data: {_escape(row_data_text)}</span>
                  <span class="ownerbot-mongo-chip">Read: {_escape(row_read_ok)}/{_escape(row_read_total)} ({_escape(row_read_rate_text)})</span>
                  <span class="ownerbot-mongo-chip">Write: {_escape(row_write_ok)}/{_escape(row_write_total)} ({_escape(row_write_rate_text)})</span>
                </div>
                <p class="muted">Detail: {_escape(row_detail or ('Connected normally' if row_ok else 'Unable to connect'))}</p>
                {row_health_error_markup}
                <div class="ownerbot-table-wrap">
                  <table>
                    <thead>
                      <tr><th>Collection</th><th>Estimated Documents</th></tr>
                    </thead>
                    <tbody>
                      {collection_rows_markup}
                    </tbody>
                  </table>
                </div>
              </div>
            </details>
            """
        )
    mongo_cluster_cards_markup = "".join(mongo_cluster_cards_markup_parts)

    discord_runtime_payload = discord_runtime if isinstance(discord_runtime, dict) else {}
    runtime_level = str(discord_runtime_payload.get("level") or "unknown").strip().lower()
    runtime_message = str(discord_runtime_payload.get("message") or "").strip()
    runtime_updated_at = float(discord_runtime_payload.get("updated_at") or 0.0)
    guild_mode_value = str(runtime_settings.get("guild_mode") or "all").strip().lower()
    tester_enabled_value = bool(runtime_settings.get("tester_enabled", False))

    runtime_tone_map = {
        "ok": "ok",
        "starting": "loading",
        "stream": "loading",
        "reloading": "loading",
        "degraded": "err",
        "outage": "err",
        "auth_error": "err",
        "error": "err",
        "err": "err",
        "ded": "err",
        "stopped": "off",
    }
    runtime_tone = runtime_tone_map.get(runtime_level, "unknown")
    runtime_label_map = {
        "ok": "ONLINE",
        "starting": "สตรีม",
        "stream": "สตรีม",
        "reloading": "สตรีม",
        "degraded": "DED",
        "outage": "DED",
        "auth_error": "DED",
        "error": "DED",
        "err": "DED",
        "ded": "DED",
        "stopped": "OFFLINE",
        "unknown": "UNKNOWN",
    }
    runtime_label = runtime_label_map.get(runtime_level, "UNKNOWN")
    runtime_default_message_map = {
        "ok": "Bot is running normally.",
        "starting": "บอทกำลังเริ่มระบบ",
        "stream": "บอทกำลังเริ่มระบบ",
        "reloading": "บอทกำลังเริ่มระบบ",
        "degraded": "Bot has warning or degraded state.",
        "outage": "Bot cannot connect to Discord.",
        "auth_error": "Discord authentication failed.",
        "error": "Bot has warning or degraded state.",
        "err": "Bot has warning or degraded state.",
        "stopped": "Bot has been stopped.",
        "unknown": "Runtime state is not available yet.",
    }
    runtime_message = runtime_message or runtime_default_message_map.get(runtime_level, runtime_default_message_map["unknown"])
    runtime_error_levels = {"ded", "degraded", "outage", "auth_error", "error", "err", "stopped"}
    runtime_starting_levels = {"stream", "starting", "restart", "restarting", "reload", "reloading", "unknown"}
    if runtime_level in runtime_error_levels:
        runtime_tone = "err"
        runtime_label = "DED"
        runtime_level = "ded"
        runtime_message = "บอทไม่พร้อมทำงาน กำลังเร่งแก้ไขระบบ"
    elif runtime_level in runtime_starting_levels:
        runtime_tone = "loading"
        runtime_label = "สตรีม"
        runtime_level = "stream"
        runtime_message = "บอทกำลังเริ่มระบบ"
    elif tester_enabled_value or guild_mode_value == "tester":
        runtime_tone = "err"
        runtime_label = "DED"
        runtime_level = "ded"
        runtime_message = "กำลังปิดปรับปรุง"
    elif guild_mode_value == "whitelist":
        runtime_tone = "ok"
        runtime_label = "LIVE"
        runtime_level = "live"
        runtime_message = "บอทยังไม่พร้อมทำงานทุกกิลด์"
    runtime_age_seconds = int(time.time() - runtime_updated_at) if runtime_updated_at > 0 else None
    runtime_meta = (
        f"Last update {runtime_age_seconds}s ago"
        if isinstance(runtime_age_seconds, int) and runtime_age_seconds >= 0
        else "No runtime timestamp yet"
    )
    runtime_status_payload = dict(discord_runtime_payload)
    runtime_status_payload["level"] = runtime_level
    runtime_status_payload["message"] = runtime_message
    runtime_status_json = json.dumps(runtime_status_payload, ensure_ascii=False)
    runtime_controls = [
        {
            "label": "Command Response",
            "enabled": bool(runtime_settings.get("global_command_response_enabled", True)),
        },
        {
            "label": "Bot Response",
            "enabled": bool(runtime_settings.get("global_bot_response_enabled", True)),
        },
        {
            "label": "Tester Mode",
            "enabled": tester_enabled_value,
        },
    ]
    disabled_commands_count = len(runtime_settings.get("global_disabled_commands", []) or [])
    hidden_tabs_count = len(hidden_tabs_set)
    whitelist_count = len(runtime_settings.get("whitelist_guild_ids", []) or [])
    blacklist_count = len(runtime_settings.get("blacklist_guild_ids", []) or [])
    tester_guild_count = len(runtime_settings.get("tester_guild_ids", []) or [])
    social_link_count = len(developer_social_rows)
    social_developer_count = len(
        {
            str(row.get("dev_id") or "").strip()
            for row in developer_social_rows
            if str(row.get("dev_id") or "").strip()
        }
    )
    guild_mode_labels = {
        "all": "All Guilds",
        "whitelist": "Whitelist Only",
        "blacklist": "Blacklist Mode",
        "tester": "Tester Only",
    }
    guild_mode_label = guild_mode_labels.get(guild_mode_value, "All Guilds")
    tab_visibility_toggles = "".join(
        (
            '<label class="ux-toggle">'
            f'<span class="ux-toggle-label">แสดงหน้า { _escape(OWNERBOT_HIDEABLE_TAB_LABELS.get(slug, slug)) }</span>'
            f'<input type="checkbox" name="show_tab_{_escape(slug)}" {"checked" if slug not in hidden_tabs_set else ""}>'
            '<span class="ux-switch"></span>'
            "</label>"
        )
        for slug in OWNERBOT_HIDEABLE_TABS
    )

    allowed_tab_slugs = set(OWNERBOT_HIDEABLE_TABS)
    allowed_plan_tiers = set(DASHBOARD_TAB_PLAN_TIERS or ("free", "silver", "golden", "diamond", "permanent"))
    if not allowed_plan_tiers:
        allowed_plan_tiers = {"free", "silver", "golden", "diamond", "permanent"}
    if "free" not in allowed_plan_tiers:
        allowed_plan_tiers.add("free")
    plan_label_map = {
        "free": "Free",
        "silver": "Silver",
        "golden": "Gole",
        "diamond": "Diamond",
        "permanent": "Permanent",
    }
    runtime_required_plan_payload = runtime_settings.get("dashboard_tab_required_plan")
    runtime_required_plan_map: dict[str, str] = {}
    if isinstance(runtime_required_plan_payload, dict):
        for raw_slug, raw_tier in runtime_required_plan_payload.items():
            slug = str(raw_slug or "").strip().lower()
            if not slug or slug not in allowed_tab_slugs:
                continue
            tier = str(raw_tier or "").strip().lower() or "free"
            if tier not in allowed_plan_tiers:
                tier = "free"
            runtime_required_plan_map[slug] = tier
    runtime_new_badges_payload = runtime_settings.get("dashboard_tab_new_badges")
    if runtime_new_badges_payload is None:
        runtime_new_badges_set = set(
            slug
            for slug in DASHBOARD_TAB_NEW_BADGE_DEFAULTS
            if slug in allowed_tab_slugs
        )
    elif isinstance(runtime_new_badges_payload, list):
        runtime_new_badges_set = set(
            slug
            for slug in (str(item or "").strip().lower() for item in runtime_new_badges_payload)
            if slug and slug in allowed_tab_slugs
        )
    elif isinstance(runtime_new_badges_payload, str):
        runtime_new_badges_set = set(
            slug
            for slug in (str(item or "").strip().lower() for item in re.split(r"[\n,]+", runtime_new_badges_payload))
            if slug and slug in allowed_tab_slugs
        )
    else:
        runtime_new_badges_set = set()
    tab_plan_badge_toggles = ""
    sorted_plan_tiers = tuple(
        tier
        for tier in ("free", "silver", "golden", "diamond", "permanent")
        if tier in allowed_plan_tiers
    ) or ("free", "silver", "golden", "diamond", "permanent")
    for slug in OWNERBOT_HIDEABLE_TABS:
        default_tier = str(DASHBOARD_TAB_REQUIRED_PLAN_DEFAULTS.get(slug) or "free").strip().lower() or "free"
        if default_tier not in allowed_plan_tiers:
            default_tier = "free"
        selected_tier = str(runtime_required_plan_map.get(slug) or default_tier).strip().lower() or default_tier
        if selected_tier not in allowed_plan_tiers:
            selected_tier = default_tier
        plan_options_markup = "".join(
            f'<option value="{_escape(tier)}" {"selected" if tier == selected_tier else ""}>{_escape(plan_label_map.get(tier, tier.title()))}</option>'
            for tier in sorted_plan_tiers
        )
        tab_plan_badge_toggles += (
            '<article class="ownerbot-tab-policy-row">'
            '<div class="ownerbot-tab-policy-meta">'
            f'<strong>{_escape(OWNERBOT_HIDEABLE_TAB_LABELS.get(slug, slug))}</strong>'
            f'<small>/{_escape(slug)}</small>'
            "</div>"
            '<div class="ownerbot-tab-policy-controls">'
            '<label>Required plan'
            f'<select name="required_plan_{_escape(slug)}">{plan_options_markup}</select>'
            "</label>"
            '<label class="ux-toggle">'
            '<span class="ux-toggle-label">New badge</span>'
            f'<input type="checkbox" name="new_badge_{_escape(slug)}" {"checked" if slug in runtime_new_badges_set else ""}>'
            '<span class="ux-switch"></span>'
            "</label>"
            "</div>"
            "</article>"
        )
    tab_visibility_toggles = (
        tab_visibility_toggles
        + '<div class="ownerbot-tab-policy-block">'
        + '<strong class="ownerbot-tab-policy-headline">Tab Plan + NEW Badge</strong>'
        + '<small class="muted">ตั้งค่า required plan และเปิด/ปิด NEW ต่อแท็บ</small>'
        + '<input type="hidden" name="dashboard_tab_policy_enabled" value="1">'
        + f'<div class="ownerbot-tab-policy-grid">{tab_plan_badge_toggles}</div>'
        + "</div>"
    )

    plan_counts = {
        "free": 0,
        "silver": 0,
        "golden": 0,
        "diamond": 0,
        "permanent": 0,
        "other": 0,
    }

    def _plan_bucket(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if raw in {"free", "none", ""}:
            return "free"
        if "permanent" in raw or "lifetime" in raw or "forever" in raw:
            return "permanent"
        if "diamond" in raw:
            return "diamond"
        if "golden" in raw or "gold" in raw:
            return "golden"
        if "silver" in raw:
            return "silver"
        return "other"

    def _plan_display_from_subscription(value: Any) -> str:
        raw = str(value or "").strip().lower()
        mapping = {
            "free": "Free",
            "silver_guild_preminum": "Silver",
            "silver_guild_premium": "Silver",
            "golden_guild_premium": "Gole",
            "gole_guild_premium": "Gole",
            "diamond_guild_premium": "Diamond",
            "permanent_guild_premium": "Permanent (Lifetime)",
            "lifetime_guild_premium": "Permanent (Lifetime)",
        }
        return mapping.get(raw, str(value or "free"))

    promote_policy = promote_policy_settings if isinstance(promote_policy_settings, dict) else {}
    promote_policy_allowed_domains = [str(item).strip() for item in list(promote_policy.get("allowed_domains") or []) if str(item).strip()]
    promote_policy_allowed_urls = [str(item).strip() for item in list(promote_policy.get("allowed_urls") or []) if str(item).strip()]
    promote_policy_blocked_words = [str(item).strip() for item in list(promote_policy.get("blocked_words") or []) if str(item).strip()]
    promote_policy_blocked_domains = [str(item).strip() for item in list(promote_policy.get("blocked_domains") or []) if str(item).strip()]
    promote_policy_blocked_urls = [str(item).strip() for item in list(promote_policy.get("blocked_urls") or []) if str(item).strip()]
    promote_policy_allowed_domains_text = ", ".join(promote_policy_allowed_domains)
    promote_policy_allowed_urls_text = ", ".join(promote_policy_allowed_urls)
    promote_policy_blocked_words_text = ", ".join(promote_policy_blocked_words)
    promote_policy_blocked_domains_text = ", ".join(promote_policy_blocked_domains)
    promote_policy_blocked_urls_text = ", ".join(promote_policy_blocked_urls)
    promote_policy_allowed_domains_display = ", ".join(promote_policy_allowed_domains[:20]) if promote_policy_allowed_domains else "-"
    promote_policy_allowed_urls_display = ", ".join(promote_policy_allowed_urls[:20]) if promote_policy_allowed_urls else "-"
    promote_policy_blocked_words_display = ", ".join(promote_policy_blocked_words[:30]) if promote_policy_blocked_words else "-"
    promote_policy_blocked_domains_display = ", ".join(promote_policy_blocked_domains[:20]) if promote_policy_blocked_domains else "-"
    promote_policy_blocked_urls_display = ", ".join(promote_policy_blocked_urls[:20]) if promote_policy_blocked_urls else "-"

    promote_suspension_rows = promote_suspension_map if isinstance(promote_suspension_map, dict) else {}
    guild_name_map: dict[str, str] = {}
    for _guild_row in guild_rows:
        guild_id_text = str(_guild_row.get("guild_id") or "").strip()
        if guild_id_text and guild_id_text not in guild_name_map:
            guild_name_map[guild_id_text] = str(_guild_row.get("name") or f"Guild {guild_id_text}").strip() or f"Guild {guild_id_text}"
    promote_suspension_cards: list[str] = []
    promote_suspension_total = 0
    promote_suspension_sorted: list[tuple[str, dict[str, str], str]] = []
    for guild_id_text, raw_row in promote_suspension_rows.items():
        gid = str(guild_id_text or "").strip()
        if not gid.isdigit():
            continue
        row = raw_row if isinstance(raw_row, dict) else {}
        guild_name = guild_name_map.get(gid) or f"Guild {gid}"
        promote_suspension_sorted.append((gid, row, guild_name))
    promote_suspension_sorted.sort(key=lambda item: (str(item[2]).lower(), int(item[0])))
    promote_suspension_detail_map = {gid: row for gid, row, _ in promote_suspension_sorted}
    promote_suspension_total = len(promote_suspension_sorted)
    if settings_render_promote:
        for gid, row, guild_name in promote_suspension_sorted:
            note_text = str(row.get("note") or "").strip()
            by_name_text = str(row.get("by_name") or "").strip() or "-"
            updated_at_text = str(row.get("updated_at") or "").strip() or "-"
            promote_suspension_cards.append(
                f"""
                <details class="command-category ownerbot-promote-suspension-card" data-ownerbot-promote-suspension-card data-guild-id="{_escape(gid)}" data-guild-name="{_escape(guild_name.lower())}" style="margin-bottom:10px;">
                  <summary>
                    <span>{_escape(guild_name)}</span>
                    <span class="public-command-meta">Guild ID: {_escape(gid)} | By: {_escape(by_name_text)}</span>
                  </summary>
                  <div class="command-category-body">
                    <div style="display:grid;gap:4px;">
                      <strong>ID: {_escape(gid)}</strong>
                      <span class="muted">Updated: {_escape(updated_at_text)}</span>
                      <span class="muted">Note: {_escape(note_text or "-")}</span>
                    </div>
                    <form method="post" action="/dashboard/admin/ownerbot/promote/suspension" style="display:grid;gap:10px;margin-top:10px;">
                      <input type="hidden" name="action" value="unsuspend">
                      <input type="hidden" name="guild_id" value="{_escape(gid)}">
                      <label>Note (optional)
                        <input type="text" name="note" maxlength="600" placeholder="เหตุผลการปลดระงับ">
                      </label>
                      <div class="auth-actions" style="justify-content:flex-start;">
                        <button class="danger-btn" type="submit">Unsuspend Guild</button>
                      </div>
                    </form>
                  </div>
                </details>
                """
            )

    promote_suspension_cards_markup = (
        "".join(promote_suspension_cards)
        if promote_suspension_cards
        else '<div class="notice">ยังไม่มีกิลด์ที่ถูกระงับ Promote</div>'
    )
    promote_all_guild_cards: list[str] = []
    promote_all_guild_rows: list[tuple[str, int, str, str, bool, str, str, str]] = []
    for _guild_row in guild_rows:
        gid = str(_guild_row.get("guild_id") or "").strip()
        if not gid.isdigit():
            continue
        guild_name = (
            str(_guild_row.get("name") or guild_name_map.get(gid) or f"Guild {gid}").strip()
            or f"Guild {gid}"
        )
        suspend_row = promote_suspension_detail_map.get(gid) or {}
        is_suspended = gid in promote_suspension_detail_map
        note_text = str(suspend_row.get("note") or "").strip()
        by_name_text = str(suspend_row.get("by_name") or "").strip() or "-"
        updated_at_text = str(suspend_row.get("updated_at") or "").strip() or "-"
        promote_all_guild_rows.append(
            (
                guild_name.lower(),
                int(gid),
                gid,
                guild_name,
                bool(is_suspended),
                note_text,
                by_name_text,
                updated_at_text,
            )
        )
    promote_all_guild_rows.sort(key=lambda item: (item[0], item[1]))
    promote_all_guild_total = len(promote_all_guild_rows)
    promote_default_visible_guild_count = min(12, promote_all_guild_total)
    if settings_render_promote:
        for _, __, gid, guild_name, is_suspended, note_text, by_name_text, updated_at_text in promote_all_guild_rows:
            status_label = "Suspended" if is_suspended else "Active"
            action_value = "unsuspend" if is_suspended else "suspend"
            action_label = "Unsuspend Guild" if is_suspended else "Suspend Guild"
            action_btn_class = "primary-btn" if is_suspended else "danger-btn"
            note_placeholder = (
                "เหตุผลการปลดระงับ"
                if is_suspended
                else "เหตุผลที่ระงับ (แสดงให้ทีมเห็นใน OwnerBot)"
            )
            promote_all_guild_cards.append(
                f"""
                <details class="command-category ownerbot-promote-guild-card" data-ownerbot-promote-guild-card data-guild-id="{_escape(gid)}" data-guild-name="{_escape(guild_name.lower())}" data-guild-status="{_escape(status_label.lower())}" style="margin-bottom:10px;">
                  <summary>
                    <span>{_escape(guild_name)}</span>
                    <span class="public-command-meta">Guild ID: {_escape(gid)} | Status: {_escape(status_label)}</span>
                  </summary>
                  <div class="command-category-body">
                    <div style="display:grid;gap:4px;">
                      <strong>ID: {_escape(gid)}</strong>
                      <span class="muted">Status: {_escape(status_label)}</span>
                      <span class="muted">Updated: {_escape(updated_at_text)} | By: {_escape(by_name_text)}</span>
                      <span class="muted">Note: {_escape(note_text or "-")}</span>
                    </div>
                    <form method="post" action="/dashboard/admin/ownerbot/promote/suspension" style="display:grid;gap:10px;margin-top:10px;">
                      <input type="hidden" name="action" value="{_escape(action_value)}">
                      <input type="hidden" name="guild_id" value="{_escape(gid)}">
                      <label>Note (optional)
                        <input type="text" name="note" maxlength="600" placeholder="{_escape(note_placeholder)}">
                      </label>
                      <div class="auth-actions" style="justify-content:flex-start;">
                        <button class="{_escape(action_btn_class)}" type="submit">{_escape(action_label)}</button>
                      </div>
                    </form>
                  </div>
                </details>
                """
            )
    promote_all_guild_cards_markup = (
        "".join(promote_all_guild_cards)
        if promote_all_guild_cards
        else '<div class="notice">ยังไม่พบกิลด์ในระบบ</div>'
    )

    guild_cards = []
    guild_select_options = []
    guild_name_lookup: dict[str, str] = {}
    plan_options = [
        ("free", "Free"),
        ("silver_guild_preminum", "Silver"),
        ("golden_guild_premium", "Gole"),
        ("diamond_guild_premium", "Diamond"),
        ("permanent_guild_premium", "Permanent (Lifetime)"),
    ]
    for row in guild_rows:
        guild_id = str(row.get("guild_id") or "").strip()
        if not guild_id.isdigit():
            continue
        guild_name = str(row.get("name") or f"Guild {guild_id}")
        guild_name_lookup[guild_id] = guild_name
        plan_counts[_plan_bucket(row.get("subscription"))] += 1
        if not settings_render_guild:
            continue
        guild_select_options.append(
            f'<option value="{_escape(guild_id)}">{_escape(guild_name)} (ID: {_escape(guild_id)})</option>'
        )
        current_sub_value = str(row.get("subscription") or "free")
        current_end_value = row.get("subscription_end")
        current_plan_bucket = _plan_bucket(current_sub_value)
        current_sub = _plan_display_from_subscription(current_sub_value)
        current_end = None if current_plan_bucket in {"free", "permanent"} else current_end_value
        plan_select = "".join(
            f'<option value="{_escape(value)}" {"selected" if current_sub_value == value else ""}>{_escape(label)}</option>'
            for value, label in plan_options
        )
        guild_cards.append(
            f"""
            <details class="command-category ownerbot-guild-card" data-ownerbot-guild-card data-guild-id="{_escape(guild_id)}" data-guild-name="{_escape(guild_name.lower())}" style="margin-bottom:10px;">
              <summary>
                <span>{_escape(guild_name)}</span>
                <span class="public-command-meta">Plan: {_escape(current_sub)} | หมดอายุ: {_escape(_format_datetime_th(current_end))}</span>
              </summary>
              <div class="command-category-body">
                <form method="post" action="/dashboard/admin/ownerbot/guild" style="display:grid; gap:10px;">
                  <input type="hidden" name="guild_id" value="{_escape(guild_id)}">
                  <div style="display:grid; gap:2px;">
                    <strong>ID: {_escape(guild_id)}</strong>
                    <span class="muted">อัปเดตแพ็กเกจและวันหมดอายุของเซิร์ฟ</span>
                  </div>
                  <div class="field-grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px;">
                    <label style="display:grid; gap:6px;">แพ็กเกจ
                      <select name="subscription">{plan_select}</select>
                    </label>
                    <label style="display:grid; gap:6px;">เพิ่มวัน (0 = ไม่เพิ่ม)
                      <input type="number" name="add_days" value="0" min="0" max="3650">
                    </label>
                    <label style="display:grid; gap:6px;">กำหนดวันหมดอายุ (ถ้ามี)
                      <input type="datetime-local" name="subscription_end" value="{_escape(_format_datetime_local(current_end))}">
                    </label>
                  </div>
                  <div class="auth-actions" style="justify-content:flex-start;">
                    <button class="primary-btn" type="submit">บันทึกแพ็กเกจ</button>
                  </div>
                </form>
              </div>
            </details>
            """
        )

    redeem_cards_claimed = []
    redeem_cards_unclaimed = []
    for row in redeem_rows:
        if not settings_render_redeem:
            continue
        redeem_data = normalize_redeem_row(row if isinstance(row, dict) else {})
        redeem_id = redeem_data.get("id")
        code = str(redeem_data.get("code") or "")
        code_value = str(redeem_data.get("code_value") or "")
        valid_for_days = int(redeem_data.get("valid_for_days") or 0)
        expires_at = redeem_data.get("expires_at")
        claimed = bool(redeem_data.get("claimed"))
        claimed_by = str(redeem_data.get("claimed_by") or "")
        claimed_at = redeem_data.get("claimed_at")
        claim_history_raw = list(redeem_data.get("claim_history") or [])
        claim_history_full = [dict(entry) for entry in claim_history_raw if isinstance(entry, dict)]
        claim_history_preview_entries = list(reversed(claim_history_full[-12:]))
        claim_history_rows_markup_parts: list[str] = []
        for history_entry in claim_history_preview_entries:
            history_time = _format_datetime_th(history_entry.get("claimed_at"))
            history_source = str(history_entry.get("source") or "").strip().lower() or "-"
            history_user_id = str(history_entry.get("user_id") or "").strip()
            history_guild_id = str(history_entry.get("guild_id") or "").strip()
            if history_user_id.isdigit():
                history_user_markup = (
                    f'<a href="https://discord.com/users/{_escape(history_user_id)}" '
                    f'target="_blank" rel="noopener noreferrer"><code>{_escape(history_user_id)}</code></a>'
                )
            else:
                history_user_markup = "<span class=\"muted\">-</span>"
            if history_guild_id.isdigit():
                history_guild_name = str(guild_name_lookup.get(history_guild_id) or f"Guild {history_guild_id}")
                history_guild_markup = (
                    f"{_escape(history_guild_name)} "
                    f"<code>{_escape(history_guild_id)}</code>"
                )
            else:
                history_guild_markup = "<span class=\"muted\">User plan (no guild)</span>"
            claim_history_rows_markup_parts.append(
                "<div style=\"display:grid;gap:3px;padding:8px 10px;border:1px solid var(--line);border-radius:10px;\">"
                f"<div style=\"display:flex;gap:8px;flex-wrap:wrap;align-items:center;\">"
                f"<span>{_escape(history_time)}</span>"
                f"<code>{_escape(history_source)}</code>"
                "</div>"
                f"<div class=\"muted\" style=\"display:flex;gap:10px;flex-wrap:wrap;\">"
                f"<span>user: {history_user_markup}</span>"
                f"<span>server: {history_guild_markup}</span>"
                "</div>"
                "</div>"
            )
        claim_history_markup = (
            "<div style=\"display:grid;gap:8px;margin-top:10px;\">"
            f"<strong>Claim History ({len(claim_history_full)} total, latest {len(claim_history_preview_entries)})</strong>"
            + "".join(claim_history_rows_markup_parts)
            + "</div>"
            if claim_history_rows_markup_parts
            else '<p class="muted" style="margin:10px 0 0;">No claim history yet.</p>'
        )
        claim_count = int(redeem_data.get("claim_count") or 0)
        max_claims = int(redeem_data.get("max_claims") or 1)
        lock_mode_value = lock_mode_from_flags(
            lock_unique_user=bool(redeem_data.get("lock_unique_user")),
            lock_unique_guild=bool(redeem_data.get("lock_unique_guild")),
        )
        lock_mode_options = "".join(
            f'<option value="{_escape(value)}" {"selected" if lock_mode_value == value else ""}>{_escape(label)}</option>'
            for value, label in (
                ("none", "No user/server lock"),
                ("user", "Lock 1 user per code"),
                ("server", "Lock 1 server per code"),
                ("user_server", "Lock 1 user + 1 server"),
            )
        )
        usage_text = "unlimited" if max_claims == 0 else f"{claim_count}/{max_claims}"
        code_value_options = "".join(
            f'<option value="{_escape(value)}" {"selected" if code_value == value else ""}>{_escape(label)}</option>'
            for value, label in REDEEM_CODE_TYPES.items()
        )
        card_markup = (
            f"""
            <details class="command-category ownerbot-redeem-item" data-ownerbot-redeem data-code="{_escape(code.lower())}" data-value="{_escape(code_value.lower())}" data-claimed="{"1" if claimed else "0"}" style="margin-bottom:10px;">
              <summary>
                <span>{_escape(code)}</span>
                <span class="public-command-meta">{"ใช้แล้ว" if claimed else "ยังไม่ใช้"} | {_escape(REDEEM_CODE_TYPES.get(code_value, code_value))} | used {usage_text}</span>
              </summary>
              <div class="command-category-body">
                <form method="post" action="/dashboard/admin/ownerbot/redeem/update" style="display:grid; gap:10px;">
                  <input type="hidden" name="redeem_id" value="{_escape(redeem_id)}">
                  <input type="hidden" name="redeem_code_lookup" value="{_escape(code)}">
                  <div style="display:grid; gap:2px;">
                    <strong>{_escape(code)}</strong>
                    <span class="muted">สร้าง: {_escape(_format_datetime_th(row.get("created_at")))} | ผู้ใช้ที่ใช้: {_escape(claimed_by or "-")} | เวลาใช้: {_escape(_format_datetime_th(claimed_at))}</span>
                  </div>
                  <div class="field-grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px;">
                    <label style="display:grid; gap:6px;">ประเภทสิทธิ์
                      <select name="code_value">{code_value_options}</select>
                    </label>
                    <label style="display:grid; gap:6px;">Redeem Code
                      <input type="text" name="code" maxlength="64" value="{_escape(code)}">
                    </label>
                    <label style="display:grid; gap:6px;">จำนวนวันสิทธิ์ (0 = ตลอด)
                      <input type="number" name="valid_for_days" min="0" max="3650" value="{valid_for_days}">
                    </label>
                    <label style="display:grid; gap:6px;">Max Claims (0 = unlimited)
                      <input type="number" name="max_claims" min="0" max="100000" value="{max_claims}">
                    </label>
                    <label style="display:grid; gap:6px;">Claim Count
                      <input type="number" name="claim_count" min="0" max="100000" value="{claim_count}">
                    </label>
                    <label style="display:grid; gap:6px;">Lock Mode
                      <select name="lock_mode">{lock_mode_options}</select>
                    </label>
                    <label style="display:grid; gap:6px;">หมดอายุโค้ด (ถ้ามี = ไม่หมดอายุ)
                      <input type="datetime-local" name="expires_at" value="{_escape(_format_datetime_local(expires_at))}">
                    </label>
                    <label style="display:grid; gap:6px;">สถานะการใช้
                      <select name="claimed">
                        <option value="false" {"selected" if not claimed else ""}>ยังไม่ใช้</option>
                        <option value="true" {"selected" if claimed else ""}>ใช้แล้ว</option>
                      </select>
                    </label>
                  </div>
                  <div class="auth-actions" style="justify-content:flex-start;">
                    <button class="primary-btn" type="submit" name="action" value="save">บันทึกโค้ด</button>
                    <button class="ghost-btn" type="submit" name="action" value="unclaim">รีเซ็ตสถานะใช้</button>
                    <button class="ghost-btn" type="submit" name="action" value="delete" onclick="return confirm('ลบโค้ดนี้?');">ลบโค้ด</button>
                  </div>
                </form>
                {claim_history_markup}
              </div>
            </details>
            """
        )
        if claimed:
            redeem_cards_claimed.append(card_markup)
        else:
            redeem_cards_unclaimed.append(card_markup)

    def _wallet_ledger_action_label(kind_value: Any, source_mode_value: Any, amount_value: float) -> str:
        kind_text = str(kind_value or "").strip().lower()
        source_mode_text = str(source_mode_value or "").strip().lower()
        mapping = {
            "topup_credit": "Top-up",
            "plan_debit": "Plan charge",
            "ownerbot_admin_credit": "Admin add",
            "ownerbot_admin_set": "Admin set",
            "ownerbot_admin_clear": "Admin clear",
        }
        if kind_text in mapping:
            return mapping[kind_text]
        if source_mode_text == "ownerbot_admin":
            return "Admin adjust"
        if amount_value >= 0:
            return "Credit"
        return "Debit"

    def _wallet_ledger_reference_text(meta_value: Any) -> str:
        meta_payload = meta_value if isinstance(meta_value, dict) else {}
        candidates = [
            meta_payload.get("transaction_id"),
            meta_payload.get("truemoney_transaction_id"),
            meta_payload.get("transaction_ref"),
            meta_payload.get("reference"),
            meta_payload.get("txid"),
            meta_payload.get("txn_id"),
        ]
        for candidate in candidates:
            text = str(candidate or "").strip()
            if text:
                return text[:120]
        return ""

    wallet_cards = []
    wallet_total_balance = 0.0
    wallet_positive_users = 0
    wallet_history_page_size = 8
    for row in wallet_rows:
        if not settings_render_wallet:
            continue
        wallet_user_id = str(row.get("user_id") or "").strip()
        if not wallet_user_id.isdigit():
            continue
        wallet_display_name = str(row.get("display_name") or f"User {wallet_user_id}").strip() or f"User {wallet_user_id}"
        try:
            wallet_balance_value = round(float(row.get("balance") or 0.0), 2)
        except Exception:
            wallet_balance_value = 0.0
        wallet_total_balance += wallet_balance_value
        if wallet_balance_value > 0:
            wallet_positive_users += 1
        wallet_balance_text = f"{wallet_balance_value:,.2f}"
        wallet_ledger_rows_raw = list((row or {}).get("recent_ledger") or [])
        wallet_ledger_rows = [dict(entry) for entry in wallet_ledger_rows_raw if isinstance(entry, dict)]
        wallet_history_rows_markup_parts: list[str] = []
        wallet_history_search_tokens: list[str] = []
        for entry_index, ledger_entry in enumerate(wallet_ledger_rows):
            page_number = (entry_index // wallet_history_page_size) + 1
            transaction_id_text = str(ledger_entry.get("id") or "").strip()
            amount_text = "0.00"
            amount_value = 0.0
            try:
                amount_value = round(float(ledger_entry.get("amount") or 0.0), 2)
            except Exception:
                amount_value = 0.0
            amount_abs = abs(amount_value)
            amount_text = f"{amount_abs:,.2f}"
            amount_signed_text = f"+{amount_text}" if amount_value >= 0 else f"-{amount_text}"
            amount_color = "#9af5bb" if amount_value >= 0 else "#ffb4c2"
            action_text = _wallet_ledger_action_label(
                ledger_entry.get("kind"),
                ledger_entry.get("source_mode"),
                amount_value,
            )
            created_text = _format_datetime_th(ledger_entry.get("created_at"))
            source_text = str(ledger_entry.get("source_mode") or "").strip().lower() or "-"
            session_key_text = str(ledger_entry.get("session_key") or "").strip()
            note_text = str(ledger_entry.get("note") or "").strip()
            ref_text = _wallet_ledger_reference_text(ledger_entry.get("meta"))
            entry_search_tokens: list[str] = []
            if transaction_id_text:
                entry_search_tokens.append(transaction_id_text.lower())
            if session_key_text:
                entry_search_tokens.append(session_key_text.lower())
            if ref_text:
                entry_search_tokens.append(ref_text.lower())
            if note_text:
                entry_search_tokens.append(note_text.lower())
            entry_search_text = " ".join(entry_search_tokens).strip()
            if entry_search_text:
                wallet_history_search_tokens.append(entry_search_text)
            row_display_style = "" if page_number == 1 else "display:none;"
            ref_markup = f"<span>ref: {_escape(ref_text)}</span>" if ref_text else ""
            note_markup = f'<div class="muted">note: {_escape(note_text)}</div>' if note_text else ""
            wallet_history_rows_markup_parts.append(
                f"<div data-wallet-history-entry data-wallet-history-page=\"{page_number}\" data-wallet-history-search=\"{_escape(entry_search_text)}\" style=\"display:grid;gap:4px;padding:8px 10px;border:1px solid var(--line);border-radius:10px;{row_display_style}\">"
                f"<div style=\"display:flex;gap:8px;flex-wrap:wrap;align-items:center;\">"
                f"<code>TX#{_escape(transaction_id_text or '-')}</code>"
                f"<span>{_escape(action_text)}</span>"
                f"<span style=\"font-weight:700;color:{amount_color};\">{_escape(amount_signed_text)} THB</span>"
                f"<span class=\"muted\">{_escape(created_text)}</span>"
                "</div>"
                f"<div class=\"muted\" style=\"display:flex;gap:10px;flex-wrap:wrap;\">"
                f"<span>source: {_escape(source_text)}</span>"
                f"<span>session: {_escape(session_key_text or '-')}</span>"
                f"{ref_markup}"
                "</div>"
                f"{note_markup}"
                "</div>"
            )
        wallet_history_query_text = " ".join(wallet_history_search_tokens).strip()[:2400]
        wallet_history_total_entries = len(wallet_ledger_rows)
        wallet_history_total_pages = (
            max(1, (wallet_history_total_entries + wallet_history_page_size - 1) // wallet_history_page_size)
            if wallet_history_total_entries > 0
            else 1
        )
        wallet_history_pager_markup = ""
        if wallet_history_total_entries > wallet_history_page_size:
            wallet_history_page_button_markup = "".join(
                f"<button class=\"ghost-btn\" type=\"button\" data-wallet-history-page-jump=\"{page_index}\">{page_index}</button>"
                for page_index in range(1, wallet_history_total_pages + 1)
            )
            wallet_history_pager_markup = (
                f"<div class=\"auth-actions\" data-wallet-history-pager data-wallet-history-total-pages=\"{wallet_history_total_pages}\" style=\"justify-content:flex-start;gap:8px;flex-wrap:wrap;\">"
                "<button class=\"ghost-btn\" type=\"button\" data-wallet-history-prev>Prev</button>"
                f"<div data-wallet-history-page-jumps style=\"display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;\">{wallet_history_page_button_markup}</div>"
                f"<small class=\"muted\" data-wallet-history-page-label>Page 1 / {wallet_history_total_pages}</small>"
                "<button class=\"ghost-btn\" type=\"button\" data-wallet-history-next>Next</button>"
                "</div>"
            )
        wallet_history_markup = (
            "<div style=\"display:grid;gap:8px;margin-top:10px;\">"
            "<strong>Recent Wallet Transactions</strong>"
            + "".join(wallet_history_rows_markup_parts)
            + wallet_history_pager_markup
            + "</div>"
            if wallet_history_rows_markup_parts
            else '<p class="muted" style="margin:10px 0 0;">No wallet transactions yet.</p>'
        )
        wallet_cards.append(
            f"""
            <details class="command-category ownerbot-wallet-card" data-ownerbot-wallet-card data-wallet-user-id="{_escape(wallet_user_id)}" data-wallet-display="{_escape(wallet_display_name.lower())}" data-wallet-history-query="{_escape(wallet_history_query_text)}" data-wallet-history-total-pages="{wallet_history_total_pages}" data-wallet-history-current-page="1" style="margin-bottom:10px;">
              <summary>
                <span>{_escape(wallet_display_name)}</span>
                <span class="public-command-meta">User ID: {_escape(wallet_user_id)} | Balance: {_escape(wallet_balance_text)} THB</span>
              </summary>
              <div class="command-category-body">
                <form method="post" action="/dashboard/admin/ownerbot/user-wallet" class="ownerbot-wallet-form">
                  <input type="hidden" name="user_id" value="{_escape(wallet_user_id)}">
                  <div style="display:grid; gap:2px;">
                    <strong>{_escape(wallet_display_name)}</strong>
                    <span class="muted">Current balance: <strong>{_escape(wallet_balance_text)} THB</strong> | Updated: {_escape(_format_datetime_th(row.get("updated_at")))} | Created: {_escape(_format_datetime_th(row.get("created_at")))}</span>
                  </div>
                  {wallet_history_markup}
                  <div class="ownerbot-wallet-form-grid">
                    <label style="display:grid; gap:6px;">Action
                      <select name="action">
                        <option value="add">Add (+)</option>
                        <option value="set">Set exact amount</option>
                        <option value="clear">Clear to 0.00</option>
                      </select>
                    </label>
                    <label style="display:grid; gap:6px;">Amount (THB)
                      <input type="number" name="amount" min="0" step="0.01" value="{wallet_balance_value:.2f}">
                    </label>
                    <label style="display:grid; gap:6px;" class="span-all">Note
                      <input type="text" name="note" maxlength="220" placeholder="Optional note for audit log">
                    </label>
                  </div>
                  <div class="auth-actions" style="justify-content:flex-start;">
                    <button class="primary-btn" type="submit">Apply wallet update</button>
                  </div>
                </form>
              </div>
            </details>
            """
        )

    total_codes = int(
        redeem_summary_map.get("total_codes")
        if redeem_summary_map.get("total_codes") is not None
        else len(redeem_rows)
    )
    total_unclaimed = int(
        redeem_summary_map.get("unclaimed_codes")
        if redeem_summary_map.get("unclaimed_codes") is not None
        else len(redeem_cards_unclaimed)
    )
    total_claimed = int(
        redeem_summary_map.get("claimed_codes")
        if redeem_summary_map.get("claimed_codes") is not None
        else len(redeem_cards_claimed)
    )
    total_guilds = len(guild_cards)
    total_wallet_users = int(
        wallet_summary_map.get("total_wallet_users")
        if wallet_summary_map.get("total_wallet_users") is not None
        else len(wallet_cards)
    )
    wallet_positive_users = int(
        wallet_summary_map.get("wallet_positive_users")
        if wallet_summary_map.get("wallet_positive_users") is not None
        else wallet_positive_users
    )
    wallet_balance_total_text = str(
        wallet_summary_map.get("wallet_balance_total_text")
        if wallet_summary_map.get("wallet_balance_total_text") is not None
        else f"{wallet_total_balance:,.2f}"
    )
    default_visible_wallet_count = min(12, total_wallet_users)
    default_visible_guild_count = min(8, total_guilds)
    recent_redeem_rows = list(redeem_rows[:8])
    recent_redeem_rows_markup = "".join(
        [
            (
                "<tr>"
                f"<td><code>{_escape(str(row.get('code') or '-'))}</code></td>"
                f"<td>{_escape(REDEEM_CODE_TYPES.get(str(row.get('code_value') or ''), str(row.get('code_value') or '-')))}</td>"
                f"<td>{'used' if bool(row.get('claimed')) else 'unused'}</td>"
                f"<td>{_escape(_format_datetime_th(row.get('created_at')))}</td>"
                f"<td>{_escape(_format_datetime_th(row.get('expires_at')))}</td>"
                f"<td>{_escape(str(row.get('claimed_by') or '-'))}</td>"
                "</tr>"
            )
            for row in recent_redeem_rows
        ]
    )
    runtime_control_chips_markup = "".join(
        (
            '<span class="ownerbot-runtime-control-chip '
            + ("on" if bool(item.get("enabled")) else "off")
            + '">'
            + _escape(item.get("label") or "-")
            + ": "
            + ("ON" if bool(item.get("enabled")) else "OFF")
            + "</span>"
        )
        for item in runtime_controls
    )
    plan_distribution_chips_markup = "".join(
        [
            f'<span class="ownerbot-plan-chip free">Free {int(plan_counts.get("free") or 0)}</span>',
            f'<span class="ownerbot-plan-chip silver">Silver {int(plan_counts.get("silver") or 0)}</span>',
            f'<span class="ownerbot-plan-chip golden">Gole {int(plan_counts.get("golden") or 0)}</span>',
            f'<span class="ownerbot-plan-chip diamond">Diamond {int(plan_counts.get("diamond") or 0)}</span>',
            f'<span class="ownerbot-plan-chip permanent">Permanent {int(plan_counts.get("permanent") or 0)}</span>',
        ]
    )
    if settings_render_runtime:
        runtime_script_paths = {
            "overview": "/dashboard/static/dashboard/pages/ownerbot_settings_runtime_overview.js",
            "ai": "/dashboard/static/dashboard/pages/ownerbot_settings_runtime_ai.js",
            "vote": "/dashboard/static/dashboard/pages/ownerbot_settings_runtime_vote.js",
            "dashboard": "/dashboard/static/dashboard/pages/ownerbot_settings_runtime_dashboard.js",
            "commands": "/dashboard/static/dashboard/pages/ownerbot_settings_runtime_commands.js",
            "social": "/dashboard/static/dashboard/pages/ownerbot_settings_runtime_social.js",
            "upload": "/dashboard/static/dashboard/pages/ownerbot_settings_runtime_upload.js",
        }
        runtime_script_path = runtime_script_paths.get(
            settings_active_runtime_page,
            runtime_script_paths["overview"],
        )
        ownerbot_settings_script_markup = f'<script src="{_escape(runtime_script_path)}"></script>'
    else:
        ownerbot_settings_script_markup = (
            '<script src="/dashboard/static/dashboard/pages/ownerbot_settings_section_page.js"></script>'
        )
    body = _render_dashboard_f_template("ownerbot_settings_page.html", locals())
    body = _ownerbot_settings_keep_active_section(body, settings_active_section)
    if settings_render_runtime:
        body = _ownerbot_settings_keep_active_runtime_subpage(body, settings_active_runtime_page)
    return _render_layout(title="ตั้งค่า OwnerBOT", body=body, session=session)
