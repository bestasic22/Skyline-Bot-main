from __future__ import annotations

import copy

from ..dashboard_core import (
    Any,
    ADMINISTRATOR,
    BOT_CONFIG,
    DEFAULT_DASHBOARD_ACCESS_MODE,
    DonateSlipReviewView,
    HTMLResponse,
    MANAGE_GUILD,
    JSONResponse,
    OWNERBOT_DASHBOARD_ACCESS_MODE,
    OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS,
    PROMOTE_COOLDOWN_SECONDS,
    PROMOTE_DEFAULT_BLOCKED_WORDS,
    Path,
    RedirectResponse,
    Request,
    Response,
    SCREENING_CATEGORY_DEFAULT_COLORS,
    SCREENING_CATEGORY_ITEMS,
    _allowed_antinuke_punishments,
    _allowed_automod_punishments,
    _append_dashboard_audit_event,
    _append_donate_slip_log,
    _apply_color_set_roles_to_guild,
    _auto_verify_donate_evidence,
    _blocked_context_redirect_or_dashboard,
    _bool_from_form,
    _can_manage_music_settings,
    _can_play_music_links,
    _can_use_antinuke_custom,
    _can_use_automod_custom,
    _can_use_automod_diamond,
    _clean_text,
    _dashboard_access_notice_from_state,
    _dashboard_access_mode_from_session,
    _dashboard_effective_plan_tier,
    _dashboard_emoji_picker_payload,
    _dashboard_editor_role_ids_from_db,
    _dashboard_editor_roles_config_key,
    _collect_color_roles_for_ui,
    _color_sets_config_key,
    _command_catalog,
    _default_verify_pages,
    _default_extra_protection_settings,
    _default_honeypot_settings,
    _default_roleplay_dashboard_settings,
    _discord_default_avatar_url,
    _donate_slip_status_label,
    _embed_messages_config_key,
    _ensure_dashboard_config_cache,
    _ensure_guild_records,
    _format_duration_th,
    _extra_protection_config_key,
    _honeypot_config_key,
    _get_alerts_fallback,
    _get_donate_fallback,
    _get_donate_slip_logs,
    _giveaway_dashboard_config_key,
    _giveaway_dashboard_settings_from_db,
    _handle_music_web_action,
    _int_from_form,
    _is_allowed_discord_invite_url,
    _is_allowed_promote_custom_url,
    _is_blocked_promote_custom_url,
    _is_atlas_collection_limit_error,
    _is_dashboard_admin,
    _is_plan_at_least,
    _levels_config_key,
    _levels_plan_caps,
    _live_options_payload,
    _live_payload,
    _manageable_guilds_live,
    _normalize_alert_entries,
    _normalize_alerts_settings,
    _normalize_color_hex,
    _normalize_color_sets_settings,
    _normalize_donate_slip_status,
    _normalize_economy_dashboard_settings,
    _normalize_roleplay_dashboard_settings,
    _normalize_embed_messages_settings,
    _normalize_extra_protection_settings,
    _normalize_honeypot_settings,
    _normalize_giveaway_dashboard_settings,
    _normalize_image_ocr_settings,
    _normalize_levels_settings,
    _normalize_plan_tier,
    _normalize_promote_attachment_url,
    _normalize_promote_allowed_domains,
    _normalize_promote_allowed_urls,
    _normalize_promote_blocked_words,
    _normalize_promote_candidate_url,
    _normalize_reaction_roles_settings,
    _normalize_dashboard_editor_role_ids,
    _normalize_starboard_settings,
    _normalize_temp_channels_settings,
    _normalize_temp_links_settings,
    _normalize_verify_pages,
    _normalize_verify_role_ids,
    _normalize_verify_settings,
    _normalize_voice_randomizer_settings,
    _dashboard_ownerbot_mode_from_state,
    _ownerbot_dashboard_tab_block_reason,
    _ownerbot_promote_policy_from_db,
    _ownerbot_payment_provider_settings_from_db,
    _ownerbot_upload_channel_settings_from_db,
    _ownerbot_runtime_block_reason,
    _ownerbot_runtime_notice_from_state,
    _ownerbot_runtime_from_db,
    _parse_duration_to_seconds_web,
    _parse_form,
    _plan_limits_from_guild_state,
    _promote_allowed_url_targets,
    _promote_blocked_url_targets,
    _promote_suspension_map_from_db,
    _promote_suspension_reason,
    _publish_verify_panel_from_dashboard,
    _publish_web_verify_panel_from_dashboard,
    _publish_voice_randomizer_panel_from_dashboard,
    _reaction_roles_config_key,
    _render_aichat,
    _render_alerts,
    _render_autoresponder,
    _render_color_sets,
    _render_commands,
    _render_control_panel,
    _render_customrole,
    _render_donate,
    _render_donate_slip_row_html,
    _render_economy,
    _render_roleplay,
    _render_embed_messages,
    _render_giveaways,
    _render_guild_picker,
    _render_leaver,
    _render_levels,
    _render_logs,
    _render_media,
    _render_moderation,
    _render_music,
    _render_ocr,
    _render_overview,
    _render_ownerbot_runtime_blocked,
    _render_dashboard_access_blocked,
    _render_pricing_locked,
    _render_probot_module_hub,
    _render_promote,
    _render_public_donate_page,
    _render_premium_receive,
    _render_reaction_roles,
    _render_screening,
    _render_screening_categories,
    _render_security,
    _render_server_stats,
    _render_starboard,
    _render_temp_channels,
    _render_temp_links,
    _render_tickets,
    _render_shop,
    _render_verify,
    _render_voice_randomizer,
    _render_welcome,
    _required_plan_for_command,
    _required_plan_for_dashboard_tab,
    _run_alerts_platform_test,
    _safe_upload_name,
    _safe_parse_datetime,
    _save_alerts_fallback,
    _save_donate_fallback,
    _save_image_ocr_fallback,
    _save_server_stats_fallback,
    _save_verify_fallback,
    _screening_categories_config_key,
    _screening_categories_plan_cap,
    _screening_categories_settings_from_db,
    _send_promote_feedback_to_discord,
    _session_from_request,
    _session_user_id,
    _dashboard_set_access_mode,
    _set_dashboard_config_value,
    _starboard_config_key,
    _temp_channels_config_key,
    _temp_links_config_key,
    _temp_links_settings_from_db,
    _update_donate_slip_log_status,
    _validate_promote_content,
    _verify_color_to_int,
    _verify_limits_from_guild_state,
    _voice_randomizer_config_key,
    asyncio,
    cache,
    dashboard_activity,
    datetime,
    discord,
    get_bot,
    guild_growth,
    hashlib,
    i18n,
    io,
    json,
    os,
    publish_donate_panel_message,
    re,
    storage,
    ticket_panel,
    time,
    style_urls,
    urlencode,
    uuid,
    wavelink,
)
from skylinebot.console.logging import logger
from skylinebot.utils import fancy_text
from skylinebot.workflows import shop as shop_flow
from skylinebot.utils.music_access import (
    evaluate_music_access,
    is_member_admin_like,
    parse_entity_id_list,
)
from skylinebot.utils import music_playlists as user_music_playlists
from PIL import Image, ImageOps
from skylinebot.surface.routes.dashboard_helpers.image_storage import (
    maybe_run_auto_orphan_cleanup,
    store_dashboard_image_asset,
)
from .guild_tabs import GuildTabRenderContext, render_dashboard_tab


_MANAGEABLE_GUILDS_CACHE_TTL_SECONDS = 20.0
_MANAGEABLE_GUILDS_CACHE: dict[str, dict[str, Any]] = {}
_DASHBOARD_STATE_CACHE_TTL_SECONDS = 30.0
_DASHBOARD_STATE_CACHE: dict[int, dict[str, Any]] = {}
_PLAN_SUBSCRIPTION_CACHE_TTL_SECONDS = 60.0
_PLAN_SUBSCRIPTION_CACHE: dict[int, dict[str, Any]] = {}
_POST_CONTEXT_CACHE_MAX_AGE_SECONDS = 4.0


def invalidate_dashboard_context_cache(
    *,
    guild_id: int | None = None,
    include_manageable_guilds: bool = False,
) -> None:
    if guild_id is not None:
        normalized_guild_id = int(guild_id)
        _DASHBOARD_STATE_CACHE.pop(normalized_guild_id, None)
        _PLAN_SUBSCRIPTION_CACHE.pop(normalized_guild_id, None)
    if include_manageable_guilds:
        _MANAGEABLE_GUILDS_CACHE.clear()


def _request_method(request: Request | None) -> str:
    return str(getattr(request, "method", "GET") or "GET").strip().upper()


def _request_is_cacheable_get(request: Request | None) -> bool:
    return _request_method(request) == "GET"


def _request_can_use_context_cache(request: Request | None) -> bool:
    return _request_method(request) in {"GET", "POST"}


def _request_can_write_context_cache(request: Request | None) -> bool:
    return _request_method(request) == "GET"


def _session_manageable_guilds_cache_key(session: dict[str, Any]) -> str:
    user_id = str(_session_user_id(session) or "0").strip()
    access_mode = str(_dashboard_access_mode_from_session(session) or "").strip().lower() or "guild"
    raw_guilds = list(session.get("guilds", []) or [])
    signature_parts: list[str] = []
    for row in raw_guilds[:240]:
        if not isinstance(row, dict):
            continue
        guild_id = str(row.get("id") or "").strip()
        if not guild_id:
            continue
        permissions = str(row.get("permissions") or "0").strip()
        owner_flag = "1" if bool(row.get("owner")) else "0"
        signature_parts.append(f"{guild_id}:{permissions}:{owner_flag}")
    signature_seed = "|".join(signature_parts)
    signature = hashlib.sha1(signature_seed.encode("utf-8", errors="ignore")).hexdigest()[:20]
    return f"{user_id}:{access_mode}:{len(raw_guilds)}:{signature}"


async def _manageable_guilds_live_cached(
    session: dict[str, Any],
    *,
    request: Request | None = None,
) -> list[dict[str, Any]]:
    if not _request_can_use_context_cache(request):
        return await _manageable_guilds_live(session)

    cache_key = _session_manageable_guilds_cache_key(session)
    now_ts = time.monotonic()
    cached_entry = _MANAGEABLE_GUILDS_CACHE.get(cache_key) or {}
    cached_expires_at = float(cached_entry.get("expires_at") or 0.0)
    cached_at = float(cached_entry.get("cached_at") or 0.0)
    cached_value = cached_entry.get("value")
    can_use_cached_for_post = (
        _request_method(request) == "POST"
        and (now_ts - cached_at) <= _POST_CONTEXT_CACHE_MAX_AGE_SECONDS
    )
    if (
        isinstance(cached_value, list)
        and (
            now_ts < cached_expires_at
            or can_use_cached_for_post
        )
    ):
        return copy.deepcopy(cached_value)

    resolved = await _manageable_guilds_live(session)
    if _request_can_write_context_cache(request):
        _MANAGEABLE_GUILDS_CACHE[cache_key] = {
            "cached_at": now_ts,
            "expires_at": now_ts + _MANAGEABLE_GUILDS_CACHE_TTL_SECONDS,
            "value": copy.deepcopy(resolved),
        }
    return resolved


def _bot_guild_signature(bot_guild: Any) -> str:
    if bot_guild is None:
        return "none"
    guild_id = int(getattr(bot_guild, "id", 0) or 0)
    try:
        channels_count = len(getattr(bot_guild, "channels", []) or [])
    except Exception:
        channels_count = 0
    try:
        roles_count = len(getattr(bot_guild, "roles", []) or [])
    except Exception:
        roles_count = 0
    try:
        members_count = int(getattr(bot_guild, "member_count", 0) or 0)
    except Exception:
        members_count = 0
    return f"{guild_id}:{channels_count}:{roles_count}:{members_count}"


async def _ensure_guild_records_cached(
    guild_id: int,
    bot_guild: Any,
    *,
    request: Request | None = None,
) -> dict[str, Any]:
    if not _request_can_use_context_cache(request):
        return await _ensure_guild_records(guild_id, bot_guild)

    normalized_guild_id = int(guild_id)
    now_ts = time.monotonic()
    signature = _bot_guild_signature(bot_guild)
    cached_entry = _DASHBOARD_STATE_CACHE.get(normalized_guild_id) or {}
    cached_expires_at = float(cached_entry.get("expires_at") or 0.0)
    cached_at = float(cached_entry.get("cached_at") or 0.0)
    cached_signature = str(cached_entry.get("signature") or "")
    cached_value = cached_entry.get("value")
    can_use_cached_for_post = (
        _request_method(request) == "POST"
        and (now_ts - cached_at) <= _POST_CONTEXT_CACHE_MAX_AGE_SECONDS
    )
    if (
        (now_ts < cached_expires_at or can_use_cached_for_post)
        and cached_signature == signature
        and isinstance(cached_value, dict)
    ):
        return copy.deepcopy(cached_value)

    resolved = await _ensure_guild_records(normalized_guild_id, bot_guild)
    if _request_can_write_context_cache(request):
        _DASHBOARD_STATE_CACHE[normalized_guild_id] = {
            "cached_at": now_ts,
            "expires_at": now_ts + _DASHBOARD_STATE_CACHE_TTL_SECONDS,
            "signature": signature,
            "value": copy.deepcopy(resolved),
        }
    return resolved


async def _guild_plan_subscription_cached(
    guild_id: int,
    *,
    request: Request | None = None,
) -> dict[str, Any]:
    normalized_guild_id = int(guild_id)
    if _request_can_use_context_cache(request):
        now_ts = time.monotonic()
        cached_entry = _PLAN_SUBSCRIPTION_CACHE.get(normalized_guild_id) or {}
        cached_expires_at = float(cached_entry.get("expires_at") or 0.0)
        cached_at = float(cached_entry.get("cached_at") or 0.0)
        cached_value = cached_entry.get("value")
        can_use_cached_for_post = (
            _request_method(request) == "POST"
            and (now_ts - cached_at) <= _POST_CONTEXT_CACHE_MAX_AGE_SECONDS
        )
        if (
            isinstance(cached_value, dict)
            and (
                now_ts < cached_expires_at
                or can_use_cached_for_post
            )
        ):
            return copy.deepcopy(cached_value)

    try:
        resolved = await storage.bot_plan_subscriptions.get(guild_id=normalized_guild_id) or {}
    except Exception:
        resolved = {}
    if not isinstance(resolved, dict):
        resolved = {}

    if _request_can_write_context_cache(request):
        _PLAN_SUBSCRIPTION_CACHE[normalized_guild_id] = {
            "cached_at": time.monotonic(),
            "expires_at": time.monotonic() + _PLAN_SUBSCRIPTION_CACHE_TTL_SECONDS,
            "value": copy.deepcopy(resolved),
        }
    return resolved


async def _require_dashboard_context(request: Request, guild_id: int):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return None, [], None, {}

    guilds = await _manageable_guilds_live_cached(session, request=request)
    wanted_guild_id = str(int(guild_id))
    current_guild = next(
        (row for row in guilds if str(row.get("id") or "").strip() == wanted_guild_id),
        None,
    )
    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not current_guild or not bot_guild:
        return session, guilds, None, {}

    state = await _ensure_guild_records_cached(guild_id, bot_guild, request=request)
    state = await _inject_dashboard_access_state(
        session=session,
        guild_id=guild_id,
        current_guild=current_guild,
        bot_guild=bot_guild,
        state=state,
    )
    plan_subscription = await _guild_plan_subscription_cached(guild_id, request=request)
    if isinstance(state, dict):
        enriched_state = dict(state)
        enriched_state["plan_subscription"] = plan_subscription
        state = enriched_state
    if isinstance(current_guild, dict):
        enriched_current_guild = dict(current_guild)
        enriched_current_guild["_plan_subscription"] = plan_subscription
        current_guild = enriched_current_guild
    runtime_settings = _ownerbot_runtime_from_db()
    block_reason = _ownerbot_runtime_block_reason(guild_id, runtime_settings)
    if block_reason:
        blocked_state = dict(state or {})
        blocked_state["ownerbot_block_reason"] = block_reason
        return session, guilds, None, blocked_state
    return session, guilds, current_guild, state


def _collect_channel_ids_for_upload(*values: Any) -> list[int]:
    collected: list[int] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            for nested in value:
                nested_text = str(nested or "").strip()
                if nested_text.isdigit():
                    nested_id = int(nested_text)
                    if nested_id not in collected:
                        collected.append(nested_id)
            continue
        text = str(value or "").strip()
        if text.isdigit():
            channel_id = int(text)
            if channel_id not in collected:
                collected.append(channel_id)
    return collected


def _normalize_discord_attachment_url(value: Any) -> str:
    raw_url = str(value or "").strip()
    if not raw_url:
        return ""
    return raw_url.split("?", 1)[0].split("#", 1)[0].strip()


_UPLOAD_TARGET_ALIASES: dict[str, str] = {
    "promote": "promote_attachment",
    "promote_attachment": "promote_attachment",
    "embed": "embed_messages_asset",
    "embed_messages": "embed_messages_asset",
    "embed_messages_asset": "embed_messages_asset",
    "starboard": "starboard_asset",
    "starboard_asset": "starboard_asset",
    "welcome": "welcome_asset",
    "leaver": "welcome_asset",
    "welcome_asset": "welcome_asset",
    "donate": "donate_asset",
    "donate_asset": "donate_asset",
    "verify": "verify_asset",
    "verify_asset": "verify_asset",
    "colors": "color_sets_asset",
    "color_sets": "color_sets_asset",
    "color_sets_asset": "color_sets_asset",
    "photo": "photo_asset",
    "photoroom": "photo_asset",
    "photo_asset": "photo_asset",
    "tickets": "embed_messages_asset",
    "ticket": "embed_messages_asset",
    "ticket_panel": "embed_messages_asset",
    "shop": "embed_messages_asset",
    "shop_product": "embed_messages_asset",
    "ocr": "embed_messages_asset",
    "image_ocr": "embed_messages_asset",
    "voice_randomizer": "embed_messages_asset",
    "temp_channels": "embed_messages_asset",
}

_IMAGE_OPTIMIZE_PROFILES: dict[str, dict[str, Any]] = {
    "icon": {
        "max_dimension": 384,
        "target_ratio": 0.32,
        "min_bytes": 28 * 1024,
        "max_bytes": 100 * 1024,
        "webp_qualities": (76, 70, 64, 58),
        "jpeg_qualities": (74, 68, 62, 56),
    },
    "thumbnail": {
        "max_dimension": 900,
        "target_ratio": 0.42,
        "min_bytes": 70 * 1024,
        "max_bytes": 240 * 1024,
        "webp_qualities": (80, 74, 68, 62),
        "jpeg_qualities": (78, 72, 66, 60),
    },
    "banner": {
        "max_dimension": 1600,
        "target_ratio": 0.52,
        "min_bytes": 160 * 1024,
        "max_bytes": 850 * 1024,
        "webp_qualities": (86, 82, 78, 74),
        "jpeg_qualities": (84, 80, 76, 72),
    },
    "image": {
        "max_dimension": 1280,
        "target_ratio": 0.5,
        "min_bytes": 140 * 1024,
        "max_bytes": 650 * 1024,
        "webp_qualities": (82, 78, 72, 66),
        "jpeg_qualities": (80, 76, 70, 64),
    },
}
_FAST_UPLOAD_SKIP_OPTIMIZE_MAX_BYTES = 1_600_000


def _normalize_image_asset_kind(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    if not key:
        return ""
    key = key.replace("-", "_").replace(" ", "_")
    if any(token in key for token in {"icon", "avatar", "author_icon", "footer_icon"}):
        return "icon"
    if "thumbnail" in key or "thumb" in key:
        return "thumbnail"
    if any(token in key for token in {"banner", "background", "cover", "header"}):
        return "banner"
    if "image" in key:
        return "image"
    if key in {"img", "pic", "photo"}:
        return "image"
    return ""


def _resolve_image_asset_kind(
    *,
    filename: str,
    upload_target: str | None = None,
    asset_kind: str | None = None,
) -> str:
    explicit = _normalize_image_asset_kind(asset_kind)
    if explicit:
        return explicit

    from_filename = _normalize_image_asset_kind(filename)
    if from_filename:
        return from_filename

    target_key = _UPLOAD_TARGET_ALIASES.get(str(upload_target or "").strip().lower(), "")
    if target_key in {"promote_attachment", "welcome_asset"}:
        return "banner"
    if target_key == "color_sets_asset":
        return "banner"
    return "image"


def _ownerbot_upload_channel_ids(upload_target: str | None) -> list[int]:
    target_key = _UPLOAD_TARGET_ALIASES.get(str(upload_target or "").strip().lower(), "")
    if not target_key:
        return []
    settings = _ownerbot_upload_channel_settings_from_db()
    channels = settings.get("channels") if isinstance(settings, dict) else {}
    if not isinstance(channels, dict):
        return []
    channel_id_text = str(channels.get(target_key) or "").strip()
    if not channel_id_text.isdigit():
        return []
    return [int(channel_id_text)]


async def _resolve_guild_upload_channel(
    guild_id: int,
    *,
    preferred_channel_ids: list[int] | None = None,
    allow_cross_guild_preferred: bool = False,
    upload_target: str | None = None,
    prefer_private_channel: bool = False,
):
    bot = get_bot()
    if not bot:
        return None
    bot_guild = bot.get_guild(int(guild_id))
    if not bot_guild:
        return None
    me = getattr(bot_guild, "me", None)

    def _has_upload_permission(channel: Any) -> bool:
        if not channel or not hasattr(channel, "send"):
            return False
        if not hasattr(channel, "permissions_for"):
            return True
        channel_guild = getattr(channel, "guild", None)
        target_member = me
        if channel_guild is not None:
            target_member = getattr(channel_guild, "me", None) or target_member
        if not target_member:
            return True
        try:
            perms = channel.permissions_for(target_member)
        except Exception:
            return True
        return bool(getattr(perms, "send_messages", False) and getattr(perms, "attach_files", False))

    def _is_public_channel(channel: Any) -> bool:
        if not channel or not hasattr(channel, "permissions_for"):
            return True
        channel_guild = getattr(channel, "guild", None)
        default_role = getattr(channel_guild, "default_role", None)
        if default_role is None:
            return True
        try:
            perms = channel.permissions_for(default_role)
        except Exception:
            return True
        return bool(getattr(perms, "view_channel", True))

    async def _resolve_channel_by_id(cid: int):
        channel = bot.get_channel(int(cid)) or bot_guild.get_channel(int(cid))
        if channel is None:
            try:
                fetched = await bot.fetch_channel(int(cid))
                fetched_guild_id = int(getattr(getattr(fetched, "guild", None), "id", 0) or 0)
                if allow_cross_guild_preferred or fetched_guild_id == int(guild_id):
                    channel = fetched
            except Exception:
                channel = None
        if channel is not None and not allow_cross_guild_preferred:
            channel_guild_id = int(getattr(getattr(channel, "guild", None), "id", 0) or 0)
            if channel_guild_id != int(guild_id):
                channel = None
        return channel

    checked_ids: set[int] = set()

    async def _pick_from_preferred(*, private_only: bool) -> Any:
        for cid in list(preferred_channel_ids or []):
            try:
                channel_id = int(cid)
            except Exception:
                continue
            if channel_id in checked_ids:
                continue
            channel = await _resolve_channel_by_id(channel_id)
            if not _has_upload_permission(channel):
                checked_ids.add(channel_id)
                continue
            if private_only and _is_public_channel(channel):
                continue
            checked_ids.add(channel_id)
            return channel
        return None

    def _pick_from_guild_channels(*, private_only: bool, name_filter: str | None = None) -> Any:
        wanted_name = str(name_filter or "").strip().lower()
        for channel in list(getattr(bot_guild, "text_channels", []) or []):
            channel_id = int(getattr(channel, "id", 0) or 0)
            if not channel_id or channel_id in checked_ids:
                continue
            if wanted_name and str(getattr(channel, "name", "") or "").strip().lower() != wanted_name:
                continue
            if not _has_upload_permission(channel):
                checked_ids.add(channel_id)
                continue
            if private_only and _is_public_channel(channel):
                continue
            checked_ids.add(channel_id)
            return channel
        return None

    target_key = _UPLOAD_TARGET_ALIASES.get(str(upload_target or "").strip().lower(), "")
    default_upload_channel_name = str(
        OWNERBOT_UPLOAD_TARGET_DEFAULT_CHANNELS.get(target_key) or ""
    ).strip().lower()
    candidate_upload_channel_names: list[str] = []
    if default_upload_channel_name:
        candidate_upload_channel_names.append(default_upload_channel_name[:96])
        if not default_upload_channel_name.endswith("-cache"):
            candidate_upload_channel_names.append(f"{default_upload_channel_name[:88]}-cache")

    def _guild_has_channel_named(name: str) -> bool:
        wanted_name = str(name or "").strip().lower()
        if not wanted_name:
            return False
        for channel in list(getattr(bot_guild, "text_channels", []) or []):
            if str(getattr(channel, "name", "") or "").strip().lower() == wanted_name:
                return True
        return False

    if allow_cross_guild_preferred:
        selected = await _pick_from_preferred(private_only=bool(prefer_private_channel))
        if selected is not None:
            return selected
        return None

    if prefer_private_channel:
        selected = await _pick_from_preferred(private_only=True)
        if selected is not None:
            return selected

        for candidate_name in candidate_upload_channel_names:
            selected = _pick_from_guild_channels(
                private_only=True,
                name_filter=candidate_name,
            )
            if selected is not None:
                return selected

        selected = _pick_from_guild_channels(private_only=True)
        if selected is not None:
            return selected

        for candidate_name in candidate_upload_channel_names:
            if _guild_has_channel_named(candidate_name):
                continue
            try:
                default_role = getattr(bot_guild, "default_role", None)
                overwrites: dict[Any, Any] = {}
                if default_role is not None:
                    overwrites[default_role] = discord.PermissionOverwrite(view_channel=False)
                if me is not None:
                    overwrites[me] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        attach_files=True,
                        read_message_history=True,
                    )
                create_kwargs: dict[str, Any] = {
                    "topic": f"SkylineBOT upload cache ({target_key or 'asset'})",
                }
                if overwrites:
                    create_kwargs["overwrites"] = overwrites
                created_channel = await bot_guild.create_text_channel(
                    candidate_name,
                    **create_kwargs,
                )
                if _has_upload_permission(created_channel):
                    return created_channel
            except Exception:
                continue
        return None

    if default_upload_channel_name:
        selected = _pick_from_guild_channels(
            private_only=False,
            name_filter=default_upload_channel_name,
        )
        if selected is not None:
            return selected

    selected = await _pick_from_preferred(private_only=False)
    if selected is not None:
        return selected

    selected = _pick_from_guild_channels(private_only=False)
    if selected is not None:
        return selected
    return None


async def _upload_image_to_discord_cdn(
    guild_id: int,
    *,
    raw_bytes: bytes,
    filename: str,
    preferred_channel_ids: list[int] | None = None,
    upload_target: str | None = None,
    asset_kind: str | None = None,
    request: Request | None = None,
    uploader_id: int | None = None,
    source_route: str | None = None,
    source_field: str | None = None,
) -> str:
    if not raw_bytes:
        return ""

    _ = preferred_channel_ids
    safe_name = _safe_upload_name(filename or "upload.png")
    original_name = safe_name
    upload_bytes = raw_bytes
    try:
        optimized_bytes, optimized_name = _optimize_image_bytes_for_upload(
            raw_bytes,
            safe_name,
            upload_target=upload_target,
            asset_kind=asset_kind,
        )
        if optimized_bytes:
            upload_bytes = optimized_bytes
        if optimized_name:
            safe_name = _safe_upload_name(optimized_name)
    except Exception:
        upload_bytes = raw_bytes
    resolved_target = str(upload_target or "").strip().lower() or "embed_messages"
    resolved_kind = _resolve_image_asset_kind(
        filename=safe_name,
        upload_target=resolved_target,
        asset_kind=asset_kind,
    )
    stored = await store_dashboard_image_asset(
        guild_id=int(guild_id),
        raw_bytes=raw_bytes,
        optimized_bytes=upload_bytes,
        original_filename=original_name,
        stored_filename=safe_name,
        upload_target=resolved_target,
        asset_kind=resolved_kind,
        uploader_id=int(uploader_id or 0),
        source_route=str(source_route or "").strip(),
        source_field=str(source_field or "").strip(),
        request=request,
    )
    if not stored:
        return ""
    try:
        asyncio.create_task(
            maybe_run_auto_orphan_cleanup(
                min_interval_seconds=60 * 20,
                limit=120,
                min_age_seconds=60 * 30,
            )
        )
    except Exception:
        pass
    return str(stored.get("url") or "").strip()


def _optimize_image_bytes_for_upload(
    raw_bytes: bytes,
    filename: str,
    *,
    upload_target: str | None = None,
    asset_kind: str | None = None,
) -> tuple[bytes, str]:
    if not raw_bytes:
        return raw_bytes, filename

    safe_name = _safe_upload_name(filename or "upload.png")
    lowered = safe_name.lower()
    if lowered.endswith(".gif"):
        return raw_bytes, safe_name
    # Speed-first path for common dashboard uploads:
    # skip expensive re-encode for small files and keep original quality.
    if len(raw_bytes) <= _FAST_UPLOAD_SKIP_OPTIMIZE_MAX_BYTES:
        return raw_bytes, safe_name

    try:
        resolved_kind = _resolve_image_asset_kind(
            filename=safe_name,
            upload_target=upload_target,
            asset_kind=asset_kind,
        )
        profile = dict(_IMAGE_OPTIMIZE_PROFILES.get(resolved_kind) or _IMAGE_OPTIMIZE_PROFILES["image"])
        max_dimension = int(profile.get("max_dimension") or 1400)
        target_ratio = float(profile.get("target_ratio") or 0.58)
        min_bytes = int(profile.get("min_bytes") or 180 * 1024)
        max_bytes = int(profile.get("max_bytes") or 900 * 1024)
        webp_qualities = tuple(int(item) for item in (profile.get("webp_qualities") or (86, 80, 74, 68)))
        jpeg_qualities = tuple(int(item) for item in (profile.get("jpeg_qualities") or (84, 78, 72, 66)))

        with Image.open(io.BytesIO(raw_bytes)) as image:
            if bool(getattr(image, "is_animated", False)):
                return raw_bytes, safe_name
            processed = ImageOps.exif_transpose(image)
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
            if max(processed.size or (0, 0)) > max_dimension:
                processed.thumbnail((max_dimension, max_dimension), resampling)

            base_name = Path(safe_name).stem or "upload"
            has_alpha = "A" in (processed.getbands() or ())
            target_bytes = max(min_bytes, min(max_bytes, int(len(raw_bytes) * target_ratio)))

            def _encode_webp(quality: int) -> bytes:
                out = io.BytesIO()
                processed.convert("RGBA" if has_alpha else "RGB").save(
                    out,
                    format="WEBP",
                    quality=max(55, min(quality, 95)),
                    method=6,
                )
                return out.getvalue()

            def _encode_jpeg(quality: int) -> bytes:
                out = io.BytesIO()
                processed.convert("RGB").save(
                    out,
                    format="JPEG",
                    quality=max(55, min(quality, 95)),
                    optimize=True,
                    progressive=True,
                )
                return out.getvalue()

            candidates: list[tuple[bytes, str]] = []
            for quality in webp_qualities:
                webp_blob = _encode_webp(quality)
                candidates.append((webp_blob, f"{base_name}.webp"))
                if len(webp_blob) <= target_bytes:
                    break

            if not has_alpha:
                for quality in jpeg_qualities:
                    jpeg_blob = _encode_jpeg(quality)
                    candidates.append((jpeg_blob, f"{base_name}.jpg"))
                    if len(jpeg_blob) <= target_bytes:
                        break

            if not candidates:
                return raw_bytes, safe_name
            best_blob, best_name = min(candidates, key=lambda item: len(item[0]))
            if len(best_blob) >= len(raw_bytes):
                return raw_bytes, safe_name
            return best_blob, best_name
    except Exception:
        return raw_bytes, safe_name


async def _ensure_verify_back_url_from_bot(
    guild_id: int,
    payload: dict[str, Any] | None,
    *,
    force_regenerate: bool = False,
) -> dict[str, Any]:
    normalized = _normalize_verify_settings(payload if isinstance(payload, dict) else {})
    current_url = str(normalized.get("back_to_server_url") or "").strip()
    current_lower = current_url.lower()
    expected_prefixes = (
        f"https://discord.com/channels/{int(guild_id)}".lower(),
        f"http://discord.com/channels/{int(guild_id)}".lower(),
    )
    if any(current_lower.startswith(prefix) for prefix in expected_prefixes) and not force_regenerate:
        return normalized

    bot = get_bot()
    verify_cog = bot.get_cog("Verify") if bot else None
    ensure_back_url_fn = getattr(verify_cog, "ensure_back_to_server_url", None) if verify_cog else None
    if callable(ensure_back_url_fn):
        try:
            _, updated = await ensure_back_url_fn(
                guild_id=int(guild_id),
                settings=normalized,
                force_regenerate=bool(force_regenerate),
            )
            resolved = _normalize_verify_settings(updated if isinstance(updated, dict) else normalized)
            resolved_url = str(resolved.get("back_to_server_url") or "").strip().lower()
            if any(resolved_url.startswith(prefix) for prefix in expected_prefixes):
                return resolved
        except Exception:
            pass

    normalized["back_to_server_url"] = f"https://discord.com/channels/{int(guild_id)}"
    return _normalize_verify_settings(normalized)


async def upload_dashboard_image_asset(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
    )
    if guard_response:
        return JSONResponse({"ok": False, "message": "forbidden"}, status_code=403)

    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"ok": False, "message": "invalid form payload"}, status_code=400)

    upload_obj = None
    for _, value in form.items():
        if value is None:
            continue
        if not hasattr(value, "filename"):
            continue
        if not getattr(value, "filename", None):
            continue
        upload_obj = value
        break

    if upload_obj is None:
        return JSONResponse({"ok": False, "message": "missing image file"}, status_code=400)

    try:
        raw_bytes = await upload_obj.read()
    except Exception:
        return JSONResponse({"ok": False, "message": "failed to read image file"}, status_code=400)

    if not raw_bytes:
        return JSONResponse({"ok": False, "message": "empty image file"}, status_code=400)

    upload_target = str(form.get("upload_target") or "").strip().lower() or "embed_messages"
    asset_kind = str(form.get("asset_kind") or "").strip().lower()
    hints_raw = str(form.get("channel_hints") or "").strip()
    hint_values = [token.strip() for token in re.split(r"[\s,;]+", hints_raw) if token.strip()]
    preferred_channels = _collect_channel_ids_for_upload(hint_values[:24])
    safe_name = _safe_upload_name(str(getattr(upload_obj, "filename", "upload.png")) or "upload.png")
    original_bytes = len(raw_bytes)
    uploader_id = int(_session_user_id(session) or 0)

    uploaded_url = await _upload_image_to_discord_cdn(
        guild_id,
        raw_bytes=raw_bytes,
        filename=safe_name,
        preferred_channel_ids=preferred_channels,
        upload_target=upload_target,
        asset_kind=asset_kind,
        request=request,
        uploader_id=uploader_id,
        source_route=str(getattr(request.url, "path", "") or ""),
        source_field="upload_dashboard_image_asset",
    )
    if not uploaded_url:
        return JSONResponse({"ok": False, "message": "upload failed"}, status_code=503)

    optimized_bytes, _ = _optimize_image_bytes_for_upload(
        raw_bytes,
        safe_name,
        upload_target=upload_target,
        asset_kind=asset_kind,
    )
    final_size = len(optimized_bytes or raw_bytes)
    resolved_kind = _resolve_image_asset_kind(
        filename=safe_name,
        upload_target=upload_target,
        asset_kind=asset_kind,
    )
    return JSONResponse(
        {
            "ok": True,
            "url": uploaded_url,
            "asset_kind": resolved_kind,
            "original_size": int(original_bytes),
            "optimized_size": int(final_size),
        }
    )


def _session_raw_guild(session: dict[str, Any] | None, guild_id: int) -> dict[str, Any] | None:
    if not session:
        return None
    wanted = str(int(guild_id))
    for raw_guild in list(session.get("guilds", []) or []):
        if str(raw_guild.get("id") or "").strip() == wanted:
            return raw_guild
    return None


def _dashboard_tab_requires_editor_access(tab_slug: str | None) -> bool:
    normalized = str(tab_slug or "").strip().lower()
    if normalized == "welcomer":
        normalized = "welcome"
    if not normalized:
        return False
    return normalized not in {"overview"}


def _permission_bits_from_raw_guild(raw_guild: dict[str, Any] | None) -> int:
    if not isinstance(raw_guild, dict):
        return 0
    raw_value = raw_guild.get("permissions", 0)
    try:
        return int(raw_value or 0)
    except Exception:
        return 0


ROLEPLAY_DASHBOARD_PRESETS: dict[str, dict[str, Any]] = {
    "modern_city": {
        "settings": {
            "currency_symbol": "credit",
            "start_coins": 350,
            "daily_reward_min": 100,
            "daily_reward_max": 240,
            "story_reward_min": 18,
            "story_reward_max": 50,
            "event_reward_xp": 140,
            "event_reward_coins": 260,
        },
        "scenarios": [
            {
                "scenario_key": "city_bank_heist",
                "name": "City Bank Heist",
                "description": "Plan a high-risk heist and escape before security closes all exits.",
                "difficulty": "hard",
                "reward_xp": 95,
                "reward_coins": 220,
            },
            {
                "scenario_key": "underground_race",
                "name": "Underground Race",
                "description": "Win an illegal night race through downtown checkpoints.",
                "difficulty": "normal",
                "reward_xp": 65,
                "reward_coins": 160,
            },
            {
                "scenario_key": "district_investigation",
                "name": "District Investigation",
                "description": "Track clues, question witnesses, and reveal the culprit.",
                "difficulty": "normal",
                "reward_xp": 75,
                "reward_coins": 180,
            },
        ],
    },
    "fantasy_kingdom": {
        "settings": {
            "currency_symbol": "gold",
            "start_coins": 300,
            "daily_reward_min": 90,
            "daily_reward_max": 220,
            "story_reward_min": 16,
            "story_reward_max": 48,
            "event_reward_xp": 170,
            "event_reward_coins": 300,
        },
        "scenarios": [
            {
                "scenario_key": "dragon_hunt",
                "name": "Dragon Hunt",
                "description": "Gather hunters and defeat a dragon threatening trade routes.",
                "difficulty": "hard",
                "reward_xp": 120,
                "reward_coins": 250,
            },
            {
                "scenario_key": "royal_court_trial",
                "name": "Royal Court Trial",
                "description": "Defend your faction in a tense political trial at the palace.",
                "difficulty": "normal",
                "reward_xp": 80,
                "reward_coins": 170,
            },
            {
                "scenario_key": "ancient_ruins",
                "name": "Ancient Ruins Expedition",
                "description": "Enter cursed ruins and recover a lost relic.",
                "difficulty": "hard",
                "reward_xp": 110,
                "reward_coins": 210,
            },
        ],
    },
    "school_life": {
        "settings": {
            "currency_symbol": "point",
            "start_coins": 200,
            "daily_reward_min": 70,
            "daily_reward_max": 180,
            "story_reward_min": 12,
            "story_reward_max": 38,
            "event_reward_xp": 120,
            "event_reward_coins": 190,
        },
        "scenarios": [
            {
                "scenario_key": "festival_preparation",
                "name": "Festival Preparation",
                "description": "Lead your class through deadlines before the school festival.",
                "difficulty": "normal",
                "reward_xp": 70,
                "reward_coins": 140,
            },
            {
                "scenario_key": "exam_mystery",
                "name": "Exam Mystery",
                "description": "Investigate suspicious leaks before the final exams begin.",
                "difficulty": "normal",
                "reward_xp": 75,
                "reward_coins": 135,
            },
            {
                "scenario_key": "sports_tournament",
                "name": "Sports Tournament",
                "description": "Win key matches and secure the championship trophy.",
                "difficulty": "easy",
                "reward_xp": 60,
                "reward_coins": 120,
            },
        ],
    },
    "custom_sandbox": {
        "settings": {
            "currency_symbol": "coin",
            "start_coins": 250,
            "daily_reward_min": 80,
            "daily_reward_max": 180,
            "story_reward_min": 12,
            "story_reward_max": 40,
            "event_reward_xp": 120,
            "event_reward_coins": 220,
        },
        "scenarios": [
            {
                "scenario_key": "starter_mission",
                "name": "Starter Mission",
                "description": "Complete your first mission and establish your character identity.",
                "difficulty": "easy",
                "reward_xp": 50,
                "reward_coins": 110,
            },
            {
                "scenario_key": "faction_negotiation",
                "name": "Faction Negotiation",
                "description": "Broker a deal between two factions with conflicting goals.",
                "difficulty": "normal",
                "reward_xp": 70,
                "reward_coins": 150,
            },
        ],
    },
}


def _roleplay_now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _roleplay_slugify(value: Any, *, fallback: str = "scenario") -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    return cleaned[:48] or fallback


def _roleplay_level_from_xp(xp: int, xp_per_level: int) -> int:
    threshold = max(1, int(xp_per_level or 1))
    return max(1, int(max(0, xp) // threshold) + 1)


ROLEPLAY_LEVEL_RANK: dict[str, int] = {"player": 1, "gm": 2, "admin": 3, "owner": 4}
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


def _roleplay_default_permissions() -> dict[str, Any]:
    return {
        "gm_role_ids": [],
        "player_role_ids": [],
        "action_levels": dict(ROLEPLAY_PERMISSION_DEFAULTS),
    }


def _roleplay_normalize_permissions(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _roleplay_default_permissions()
    gm_role_ids: list[str] = []
    for raw in list(src.get("gm_role_ids") or []):
        text = str(raw or "").strip()
        if text.isdigit() and text not in gm_role_ids:
            gm_role_ids.append(text)
    player_role_ids: list[str] = []
    for raw in list(src.get("player_role_ids") or []):
        text = str(raw or "").strip()
        if text.isdigit() and text not in player_role_ids:
            player_role_ids.append(text)
    out["gm_role_ids"] = gm_role_ids
    out["player_role_ids"] = player_role_ids
    src_actions = src.get("action_levels") if isinstance(src.get("action_levels"), dict) else {}
    out_actions = {}
    for action_key, default_level in ROLEPLAY_PERMISSION_DEFAULTS.items():
        level = str(src_actions.get(action_key) or default_level).strip().lower()
        if level not in ROLEPLAY_LEVEL_RANK:
            level = default_level
        out_actions[action_key] = level
    out["action_levels"] = out_actions
    return out


def _roleplay_default_economy_guard() -> dict[str, Any]:
    return {
        "enabled": False,
        "max_reward_xp": 250000,
        "max_reward_coins": 250000,
        "inflation_threshold_avg_coins": 25000,
        "base_reduce_percent": 20,
        "min_multiplier_percent": 55,
        "last_multiplier_percent": 100,
    }


def _roleplay_normalize_economy_guard(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _roleplay_default_economy_guard()

    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    out["enabled"] = bool(src.get("enabled"))
    out["max_reward_xp"] = _safe_int(src.get("max_reward_xp"), out["max_reward_xp"], 0, 2_500_000)
    out["max_reward_coins"] = _safe_int(src.get("max_reward_coins"), out["max_reward_coins"], 0, 2_500_000)
    out["inflation_threshold_avg_coins"] = _safe_int(
        src.get("inflation_threshold_avg_coins"),
        out["inflation_threshold_avg_coins"],
        1,
        10_000_000,
    )
    out["base_reduce_percent"] = _safe_int(src.get("base_reduce_percent"), out["base_reduce_percent"], 0, 95)
    out["min_multiplier_percent"] = _safe_int(src.get("min_multiplier_percent"), out["min_multiplier_percent"], 5, 100)
    out["last_multiplier_percent"] = _safe_int(src.get("last_multiplier_percent"), out["last_multiplier_percent"], 5, 100)
    if out["min_multiplier_percent"] > 100:
        out["min_multiplier_percent"] = 100
    return out


def _roleplay_schedule_next_run_utc(
    *,
    frequency: str,
    weekday: int,
    hour: int,
    minute: int,
    timezone_offset_minutes: int,
    from_utc: datetime.datetime | None = None,
) -> datetime.datetime:
    now_utc = from_utc if isinstance(from_utc, datetime.datetime) else _roleplay_now_utc()
    now_utc = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=datetime.timezone.utc)
    offset = datetime.timedelta(minutes=int(timezone_offset_minutes or 0))
    now_local = now_utc + offset
    local_base = now_local.replace(second=0, microsecond=0)
    candidate_local = local_base.replace(hour=int(hour), minute=int(minute))
    normalized_frequency = "weekly" if str(frequency or "").strip().lower() == "weekly" else "daily"
    if normalized_frequency == "weekly":
        target_weekday = max(0, min(6, int(weekday or 0)))
        delta_days = (target_weekday - candidate_local.weekday()) % 7
        candidate_local = candidate_local + datetime.timedelta(days=delta_days)
        if candidate_local <= now_local:
            candidate_local += datetime.timedelta(days=7)
    else:
        if candidate_local <= now_local:
            candidate_local += datetime.timedelta(days=1)
    return candidate_local - offset


def _roleplay_normalize_schedule(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    frequency = "weekly" if str(src.get("frequency") or "").strip().lower() == "weekly" else "daily"
    weekday = max(0, min(6, int(src.get("weekday") or 0)))
    hour = max(0, min(23, int(src.get("hour") or 20)))
    minute = max(0, min(59, int(src.get("minute") or 0)))
    timezone_offset_minutes = max(-720, min(840, int(src.get("timezone_offset_minutes") or 0)))
    duration_minutes = max(5, min(180, int(src.get("duration_minutes") or 30)))
    return {
        "schedule_name": str(src.get("schedule_name") or "Roleplay Schedule").strip()[:80] or "Roleplay Schedule",
        "enabled": bool(src.get("enabled")),
        "frequency": frequency,
        "weekday": weekday,
        "hour": hour,
        "minute": minute,
        "timezone_offset_minutes": timezone_offset_minutes,
        "duration_minutes": duration_minutes,
        "scenario_id": int(src.get("scenario_id")) if str(src.get("scenario_id") or "").isdigit() else None,
        "scenario_key": _roleplay_slugify(src.get("scenario_key"), fallback="") if str(src.get("scenario_key") or "").strip() else "",
        "reward_xp_override": int(src.get("reward_xp_override")) if str(src.get("reward_xp_override") or "").strip().isdigit() else None,
        "reward_coins_override": int(src.get("reward_coins_override")) if str(src.get("reward_coins_override") or "").strip().isdigit() else None,
    }


async def _roleplay_ensure_permissions_row(guild_id: int) -> dict[str, Any]:
    row = await storage.rp_permissions.get(guild_id=guild_id) or {}
    if not row:
        await storage.rp_permissions.insert(guild_id=guild_id, **_roleplay_default_permissions())
        row = await storage.rp_permissions.get(guild_id=guild_id) or {}
    return row


async def _roleplay_ensure_economy_guard_row(guild_id: int) -> dict[str, Any]:
    row = await storage.rp_economy_guard.get(guild_id=guild_id) or {}
    if not row:
        await storage.rp_economy_guard.insert(guild_id=guild_id, **_roleplay_default_economy_guard())
        row = await storage.rp_economy_guard.get(guild_id=guild_id) or {}
    return row


def _roleplay_actor_level(
    *,
    session: dict[str, Any] | None,
    current_guild: dict[str, Any] | None,
    bot_guild: Any,
    state: dict[str, Any],
    permissions_row: dict[str, Any],
) -> str:
    normalized = _roleplay_normalize_permissions(permissions_row)
    dashboard_access = state.get("dashboard_access") if isinstance(state, dict) else {}
    dashboard_access = dashboard_access if isinstance(dashboard_access, dict) else {}
    user_id_raw = str(((session or {}).get("user") or {}).get("id") or "").strip()
    user_id = int(user_id_raw) if user_id_raw.isdigit() else 0
    owner_id_raw = str((current_guild or {}).get("owner_id") or getattr(bot_guild, "owner_id", 0) or "").strip()
    owner_id = int(owner_id_raw) if owner_id_raw.isdigit() else 0
    is_owner = bool(
        dashboard_access.get("effective_is_owner")
        or (user_id and owner_id and int(user_id) == int(owner_id))
    )
    if is_owner:
        return "owner"
    if bool(dashboard_access.get("has_admin_like_permission") or dashboard_access.get("is_dashboard_admin")):
        return "admin"
    member = bot_guild.get_member(user_id) if bot_guild and user_id else None
    role_ids = {
        str(int(getattr(role, "id", 0) or 0))
        for role in list(getattr(member, "roles", []) or [])
        if str(getattr(role, "id", "") or "").strip().isdigit()
    }
    if any(role_id in role_ids for role_id in normalized["gm_role_ids"]):
        return "gm"
    return "player"


def _roleplay_can_action(*, actor_level: str, permissions_row: dict[str, Any], action_key: str) -> bool:
    normalized = _roleplay_normalize_permissions(permissions_row)
    required_level = normalized["action_levels"].get(action_key, "owner")
    return ROLEPLAY_LEVEL_RANK.get(actor_level, 0) >= ROLEPLAY_LEVEL_RANK.get(required_level, 99)


async def _roleplay_export_snapshot(guild_id: int, *, include_runtime_event: bool = True) -> dict[str, Any]:
    settings_row = _normalize_roleplay_dashboard_settings(await storage.rp_settings.get(guild_id=guild_id) or {})
    scenarios_raw = await storage.rp_scenarios.gets(guild_id=guild_id) or []
    scenarios: list[dict[str, Any]] = []
    for row in scenarios_raw:
        if not isinstance(row, dict):
            continue
        scenarios.append(
            {
                "scenario_key": str(row.get("scenario_key") or ""),
                "name": str(row.get("name") or "Scenario"),
                "description": str(row.get("description") or ""),
                "template_key": str(row.get("template_key") or "custom"),
                "difficulty": str(row.get("difficulty") or "normal"),
                "reward_xp": int(row.get("reward_xp") or 0),
                "reward_coins": int(row.get("reward_coins") or 0),
                "is_enabled": bool(row.get("is_enabled", True)),
                "is_preset": bool(row.get("is_preset")),
            }
        )
    permissions_row = _roleplay_normalize_permissions(await _roleplay_ensure_permissions_row(guild_id))
    economy_guard = _roleplay_normalize_economy_guard(await _roleplay_ensure_economy_guard_row(guild_id))
    schedules_raw = await storage.rp_schedules.gets(guild_id=guild_id) or []
    schedules: list[dict[str, Any]] = []
    for row in schedules_raw:
        if not isinstance(row, dict):
            continue
        normalized = _roleplay_normalize_schedule(row)
        normalized["enabled"] = bool(row.get("enabled"))
        schedules.append(normalized)
    payload: dict[str, Any] = {
        "version": 1,
        "guild_id": int(guild_id),
        "exported_at": _roleplay_now_utc().isoformat(),
        "settings": settings_row,
        "scenarios": scenarios,
        "permissions": permissions_row,
        "economy_guard": economy_guard,
        "schedules": schedules,
    }
    if include_runtime_event:
        payload["event"] = await storage.rp_events.get(guild_id=guild_id) or {}
    return payload


async def _roleplay_apply_snapshot(guild_id: int, snapshot: dict[str, Any]) -> dict[str, Any]:
    settings_payload = _normalize_roleplay_dashboard_settings(snapshot.get("settings") if isinstance(snapshot, dict) else {})
    settings_row = await storage.rp_settings.get(guild_id=guild_id) or {}
    if settings_row.get("id"):
        await storage.rp_settings.update(id=settings_row["id"], **settings_payload, updated_at=_roleplay_now_utc())
    else:
        await storage.rp_settings.insert(guild_id=guild_id, **settings_payload, updated_at=_roleplay_now_utc())

    await storage.rp_scenarios.delete(guild_id=guild_id)
    for row in list(snapshot.get("scenarios") or [])[:300]:
        if not isinstance(row, dict):
            continue
        await _roleplay_upsert_scenario(
            guild_id,
            scenario_key=str(row.get("scenario_key") or row.get("name") or ""),
            name=str(row.get("name") or "Scenario"),
            description=str(row.get("description") or ""),
            template_key=str(row.get("template_key") or "custom"),
            difficulty=str(row.get("difficulty") or "normal"),
            reward_xp=int(row.get("reward_xp") or 0),
            reward_coins=int(row.get("reward_coins") or 0),
            is_preset=bool(row.get("is_preset")),
        )

    permissions_payload = _roleplay_normalize_permissions(snapshot.get("permissions") if isinstance(snapshot, dict) else {})
    permission_row = await _roleplay_ensure_permissions_row(guild_id)
    if permission_row.get("id"):
        await storage.rp_permissions.update(
            id=permission_row["id"],
            gm_role_ids=permissions_payload["gm_role_ids"],
            player_role_ids=permissions_payload["player_role_ids"],
            action_levels=permissions_payload["action_levels"],
            updated_at=_roleplay_now_utc(),
        )

    guard_payload = _roleplay_normalize_economy_guard(snapshot.get("economy_guard") if isinstance(snapshot, dict) else {})
    guard_row = await _roleplay_ensure_economy_guard_row(guild_id)
    if guard_row.get("id"):
        await storage.rp_economy_guard.update(
            id=guard_row["id"],
            enabled=guard_payload["enabled"],
            max_reward_xp=guard_payload["max_reward_xp"],
            max_reward_coins=guard_payload["max_reward_coins"],
            inflation_threshold_avg_coins=guard_payload["inflation_threshold_avg_coins"],
            base_reduce_percent=guard_payload["base_reduce_percent"],
            min_multiplier_percent=guard_payload["min_multiplier_percent"],
            last_multiplier_percent=guard_payload["last_multiplier_percent"],
            updated_at=_roleplay_now_utc(),
        )

    await storage.rp_schedules.delete(guild_id=guild_id)
    for row in list(snapshot.get("schedules") or [])[:120]:
        if not isinstance(row, dict):
            continue
        normalized = _roleplay_normalize_schedule(row)
        next_run = _roleplay_schedule_next_run_utc(
            frequency=normalized["frequency"],
            weekday=normalized["weekday"],
            hour=normalized["hour"],
            minute=normalized["minute"],
            timezone_offset_minutes=normalized["timezone_offset_minutes"],
            from_utc=_roleplay_now_utc(),
        )
        await storage.rp_schedules.insert(
            guild_id=guild_id,
            schedule_name=normalized["schedule_name"],
            enabled=bool(normalized["enabled"]),
            frequency=normalized["frequency"],
            weekday=normalized["weekday"],
            hour=normalized["hour"],
            minute=normalized["minute"],
            timezone_offset_minutes=normalized["timezone_offset_minutes"],
            duration_minutes=normalized["duration_minutes"],
            scenario_id=normalized["scenario_id"],
            scenario_key=normalized["scenario_key"],
            reward_xp_override=normalized["reward_xp_override"],
            reward_coins_override=normalized["reward_coins_override"],
            next_run_at=next_run,
            updated_at=_roleplay_now_utc(),
        )

    event_payload = snapshot.get("event") if isinstance(snapshot.get("event"), dict) else {}
    event_row = await storage.rp_events.get(guild_id=guild_id) or {}
    if event_payload and event_row.get("id"):
        await storage.rp_events.update(
            id=event_row["id"],
            status=str(event_payload.get("status") or "idle"),
            event_title=str(event_payload.get("event_title") or ""),
            template_key=str(event_payload.get("template_key") or ""),
            description=str(event_payload.get("description") or ""),
            reward_xp=max(0, int(event_payload.get("reward_xp") or 0)),
            reward_coins=max(0, int(event_payload.get("reward_coins") or 0)),
            participants=list(event_payload.get("participants") or []),
            started_by=int(event_payload.get("started_by") or 0),
            trigger_type=str(event_payload.get("trigger_type") or "manual")[:60],
            schedule_name=str(event_payload.get("schedule_name") or "")[:80],
            started_at=event_payload.get("started_at"),
            ends_at=event_payload.get("ends_at"),
            updated_at=_roleplay_now_utc(),
        )
    elif event_payload and not event_row:
        await storage.rp_events.insert(
            guild_id=guild_id,
            status=str(event_payload.get("status") or "idle"),
            event_title=str(event_payload.get("event_title") or ""),
            template_key=str(event_payload.get("template_key") or ""),
            description=str(event_payload.get("description") or ""),
            reward_xp=max(0, int(event_payload.get("reward_xp") or 0)),
            reward_coins=max(0, int(event_payload.get("reward_coins") or 0)),
            participants=list(event_payload.get("participants") or []),
            started_by=int(event_payload.get("started_by") or 0),
            trigger_type=str(event_payload.get("trigger_type") or "manual")[:60],
            schedule_name=str(event_payload.get("schedule_name") or "")[:80],
            started_at=event_payload.get("started_at"),
            ends_at=event_payload.get("ends_at"),
            updated_at=_roleplay_now_utc(),
        )
    return await _roleplay_export_snapshot(guild_id, include_runtime_event=True)


async def _roleplay_append_audit(
    guild_id: int,
    session: dict[str, Any] | None,
    *,
    action: str,
    scope: str,
    note: str,
    snapshot_before: dict[str, Any] | None,
    snapshot_after: dict[str, Any] | None,
) -> None:
    user = (session or {}).get("user") if isinstance(session, dict) else {}
    user = user if isinstance(user, dict) else {}
    actor_user_raw = str(user.get("id") or "").strip()
    actor_user_id = int(actor_user_raw) if actor_user_raw.isdigit() else 0
    actor_name = str(user.get("global_name") or user.get("username") or f"User {actor_user_id or 0}")
    await storage.rp_audit_logs.insert(
        guild_id=guild_id,
        actor_user_id=actor_user_id,
        actor_name=actor_name[:120],
        action=str(action or "action")[:100],
        scope=str(scope or "config")[:80],
        note=str(note or "")[:400],
        snapshot_before=snapshot_before if isinstance(snapshot_before, dict) else {},
        snapshot_after=snapshot_after if isinstance(snapshot_after, dict) else {},
        created_at=_roleplay_now_utc(),
    )
    await storage.rp_audit_logs.delete_limited(
        300,
        {"guild_id": guild_id},
    )


async def _roleplay_average_coins(guild_id: int) -> int:
    rows = await storage.rp_characters.gets(guild_id=guild_id) or []
    if not rows:
        return 0
    total = 0
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += max(0, int(row.get("coins") or 0))
        count += 1
    if count <= 0:
        return 0
    return int(total / count)


async def _roleplay_guard_reward(
    guild_id: int,
    *,
    reward_xp: int,
    reward_coins: int,
) -> tuple[int, int, dict[str, Any]]:
    guard_row = await _roleplay_ensure_economy_guard_row(guild_id)
    guard = _roleplay_normalize_economy_guard(guard_row)
    base_xp = max(0, int(reward_xp or 0))
    base_coins = max(0, int(reward_coins or 0))
    if not guard["enabled"]:
        return base_xp, base_coins, {"multiplier_percent": 100, "avg_coins": await _roleplay_average_coins(guild_id)}

    avg_coins = await _roleplay_average_coins(guild_id)
    threshold = max(1, int(guard["inflation_threshold_avg_coins"] or 1))
    overflow_ratio = max(0.0, (avg_coins - threshold) / threshold) if avg_coins > threshold else 0.0
    dynamic_reduce = int(guard["base_reduce_percent"] + min(70.0, overflow_ratio * 40.0))
    multiplier_percent = max(int(guard["min_multiplier_percent"]), min(100, 100 - dynamic_reduce))
    clamped_xp = min(base_xp, int(guard["max_reward_xp"]))
    clamped_coins = min(base_coins, int(guard["max_reward_coins"]))
    final_xp = max(0, int(clamped_xp * multiplier_percent / 100))
    final_coins = max(0, int(clamped_coins * multiplier_percent / 100))
    if guard_row.get("id"):
        await storage.rp_economy_guard.update(
            id=guard_row["id"],
            last_multiplier_percent=multiplier_percent,
            updated_at=_roleplay_now_utc(),
        )
    return final_xp, final_coins, {"multiplier_percent": multiplier_percent, "avg_coins": avg_coins}


async def _roleplay_track_scenario_stats(
    guild_id: int,
    *,
    scenario_key: str,
    scenario_name: str,
    play_count_delta: int = 0,
    event_start_delta: int = 0,
    reward_xp_delta: int = 0,
    reward_coins_delta: int = 0,
) -> None:
    key = _roleplay_slugify(scenario_key, fallback="scenario")
    row = await storage.rp_scenario_stats.get(guild_id=guild_id, scenario_key=key) or {}
    now = _roleplay_now_utc()
    if row.get("id"):
        await storage.rp_scenario_stats.update(
            id=row["id"],
            scenario_name=str(scenario_name or row.get("scenario_name") or key)[:160],
            play_count=max(0, int(row.get("play_count") or 0) + int(play_count_delta)),
            event_start_count=max(0, int(row.get("event_start_count") or 0) + int(event_start_delta)),
            total_reward_xp=max(0, int(row.get("total_reward_xp") or 0) + int(reward_xp_delta)),
            total_reward_coins=max(0, int(row.get("total_reward_coins") or 0) + int(reward_coins_delta)),
            last_played_at=now,
            updated_at=now,
        )
        return
    await storage.rp_scenario_stats.insert(
        guild_id=guild_id,
        scenario_key=key,
        scenario_name=str(scenario_name or key)[:160],
        play_count=max(0, int(play_count_delta)),
        event_start_count=max(0, int(event_start_delta)),
        total_reward_xp=max(0, int(reward_xp_delta)),
        total_reward_coins=max(0, int(reward_coins_delta)),
        last_played_at=now,
        updated_at=now,
    )


async def _roleplay_upsert_scenario(
    guild_id: int,
    *,
    scenario_key: str,
    name: str,
    description: str,
    template_key: str,
    difficulty: str,
    reward_xp: int,
    reward_coins: int,
    is_preset: bool,
) -> dict[str, Any] | None:
    normalized_key = _roleplay_slugify(scenario_key, fallback="scenario")
    existing = await storage.rp_scenarios.get(guild_id=guild_id, scenario_key=normalized_key)
    payload = {
        "guild_id": int(guild_id),
        "scenario_key": normalized_key,
        "name": str(name or "Scenario").strip()[:120] or "Scenario",
        "description": str(description or "").strip()[:800],
        "template_key": _roleplay_slugify(template_key, fallback="custom"),
        "difficulty": _roleplay_slugify(difficulty, fallback="normal"),
        "reward_xp": max(0, min(500_000, int(reward_xp or 0))),
        "reward_coins": max(0, min(500_000, int(reward_coins or 0))),
        "is_enabled": True,
        "is_preset": bool(is_preset),
        "updated_at": _roleplay_now_utc(),
    }
    if existing and existing.get("id"):
        return await storage.rp_scenarios.update(id=existing["id"], **payload)
    return await storage.rp_scenarios.insert(**payload)


async def _roleplay_apply_preset(guild_id: int, preset_key: str) -> tuple[dict[str, Any], int]:
    _ = _roleplay_slugify(preset_key, fallback="modern_city")
    normalized_key = "modern_city"
    preset_payload = ROLEPLAY_DASHBOARD_PRESETS["modern_city"]
    settings = await storage.rp_settings.get(guild_id=guild_id) or {}
    if not settings:
        await storage.rp_settings.insert(guild_id=guild_id)
        settings = await storage.rp_settings.get(guild_id=guild_id) or {}
    merged_settings = _default_roleplay_dashboard_settings()
    merged_settings.update(dict(preset_payload.get("settings") or {}))
    merged_settings["enabled"] = True
    merged_settings["allow_custom_config"] = True
    merged_settings["allow_custom_scenarios"] = True
    merged_settings["preset_key"] = normalized_key
    normalized_settings = _normalize_roleplay_dashboard_settings(merged_settings)
    normalized_settings["enabled"] = True
    normalized_settings["allow_custom_config"] = True
    normalized_settings["allow_custom_scenarios"] = True
    normalized_settings["updated_at"] = _roleplay_now_utc()
    updated_settings = (
        await storage.rp_settings.update(id=settings["id"], **normalized_settings)
        if settings.get("id")
        else await storage.rp_settings.insert(guild_id=guild_id, **normalized_settings)
    ) or settings
    created_count = 0
    for row in list(preset_payload.get("scenarios") or []):
        upserted = await _roleplay_upsert_scenario(
            guild_id,
            scenario_key=str(row.get("scenario_key") or row.get("name") or ""),
            name=str(row.get("name") or "Scenario"),
            description=str(row.get("description") or ""),
            template_key=normalized_key,
            difficulty=str(row.get("difficulty") or "normal"),
            reward_xp=int(row.get("reward_xp") or 0),
            reward_coins=int(row.get("reward_coins") or 0),
            is_preset=True,
        )
        if upserted:
            created_count += 1
    return updated_settings, created_count


async def _roleplay_apply_city_starter_pack(guild_id: int) -> tuple[dict[str, Any], int, dict[str, Any]]:
    settings, scenario_count = await _roleplay_apply_preset(guild_id, "modern_city")
    guard_row = await _roleplay_ensure_economy_guard_row(guild_id)
    starter_guard = _roleplay_default_economy_guard()
    starter_guard["enabled"] = True
    normalized_guard = _roleplay_normalize_economy_guard(starter_guard)
    if guard_row.get("id"):
        await storage.rp_economy_guard.update(
            id=guard_row["id"],
            enabled=normalized_guard["enabled"],
            max_reward_xp=normalized_guard["max_reward_xp"],
            max_reward_coins=normalized_guard["max_reward_coins"],
            inflation_threshold_avg_coins=normalized_guard["inflation_threshold_avg_coins"],
            base_reduce_percent=normalized_guard["base_reduce_percent"],
            min_multiplier_percent=normalized_guard["min_multiplier_percent"],
            last_multiplier_percent=normalized_guard["last_multiplier_percent"],
            updated_at=_roleplay_now_utc(),
        )
    else:
        await storage.rp_economy_guard.insert(
            guild_id=guild_id,
            enabled=normalized_guard["enabled"],
            max_reward_xp=normalized_guard["max_reward_xp"],
            max_reward_coins=normalized_guard["max_reward_coins"],
            inflation_threshold_avg_coins=normalized_guard["inflation_threshold_avg_coins"],
            base_reduce_percent=normalized_guard["base_reduce_percent"],
            min_multiplier_percent=normalized_guard["min_multiplier_percent"],
            last_multiplier_percent=normalized_guard["last_multiplier_percent"],
            updated_at=_roleplay_now_utc(),
        )
    await _roleplay_ensure_permissions_row(guild_id)
    return settings, scenario_count, normalized_guard


async def _roleplay_ensure_character(
    guild_id: int,
    user_id: int,
    settings: dict[str, Any],
) -> dict[str, Any] | None:
    row = await storage.rp_characters.get(guild_id=guild_id, user_id=user_id)
    if row:
        return row
    start_xp = max(0, int(settings.get("start_xp") or 0))
    xp_per_level = max(1, int(settings.get("xp_per_level") or 120))
    await storage.rp_characters.insert(
        guild_id=guild_id,
        user_id=user_id,
        xp=start_xp,
        coins=max(0, int(settings.get("start_coins") or 0)),
        level=_roleplay_level_from_xp(start_xp, xp_per_level),
    )
    return await storage.rp_characters.get(guild_id=guild_id, user_id=user_id)


def _roleplay_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _roleplay_coins_text(settings: dict[str, Any], amount: int) -> str:
    symbol = str(settings.get("currency_symbol") or "coin").strip()[:12] or "coin"
    return f"{int(max(0, amount)):,} {symbol}"


async def _roleplay_resolve_event_announce_channel(
    guild_id: int,
    settings: dict[str, Any],
) -> Any | None:
    channel_id_raw = str(settings.get("event_announce_channel_id") or "").strip()
    if not channel_id_raw.isdigit():
        return None
    bot = get_bot()
    if not bot:
        return None
    channel_id = int(channel_id_raw)
    guild = bot.get_guild(int(guild_id))
    channel = bot.get_channel(channel_id) or (guild.get_channel(channel_id) if guild else None)
    if channel is None:
        try:
            fetched = await bot.fetch_channel(channel_id)
            fetched_guild_id = int(getattr(getattr(fetched, "guild", None), "id", 0) or 0)
            if fetched_guild_id == int(guild_id):
                channel = fetched
        except Exception:
            channel = None
    if channel is None or not hasattr(channel, "send"):
        return None
    try:
        if hasattr(channel, "permissions_for"):
            target_member = getattr(getattr(channel, "guild", None), "me", None) or (guild.me if guild else None)
            if target_member is not None:
                perms = channel.permissions_for(target_member)
                if not bool(getattr(perms, "send_messages", False)):
                    return None
    except Exception:
        return None
    return channel


async def _roleplay_send_schedule_end_notice(
    guild_id: int,
    settings: dict[str, Any],
    event_row: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    if not _roleplay_bool(settings.get("schedule_notify_on_end"), True):
        return
    channel = await _roleplay_resolve_event_announce_channel(guild_id, settings)
    if channel is None:
        return
    title = str(summary.get("title") or event_row.get("event_title") or "Roleplay Event")
    schedule_name = str(event_row.get("schedule_name") or "schedule")
    participants = max(0, int(summary.get("participants") or 0))
    total_xp = max(0, int(summary.get("total_xp") or 0))
    total_coins = max(0, int(summary.get("total_coins") or 0))
    message = (
        "[RP Scheduler] Event ended\n"
        f"Event: **{title}**\n"
        f"Schedule: `{schedule_name}`\n"
        f"Rewarded players: {participants}\n"
        f"Total rewards: +{total_xp} XP and +{_roleplay_coins_text(settings, total_coins)}"
    )
    try:
        await channel.send(message)
    except Exception:
        return


async def _roleplay_finish_event_and_reward(
    guild_id: int,
    event_row: dict[str, Any],
    settings: dict[str, Any],
    *,
    trigger_type: str = "manual",
) -> dict[str, Any]:
    participants_raw = event_row.get("participants") if isinstance(event_row.get("participants"), list) else []
    participant_ids: list[int] = []
    for raw in participants_raw:
        text = str(raw or "").strip()
        if text.isdigit():
            user_id = int(text)
            if user_id not in participant_ids:
                participant_ids.append(user_id)

    base_xp = max(0, int(event_row.get("reward_xp") or 0))
    base_coins = max(0, int(event_row.get("reward_coins") or 0))
    payout_xp, payout_coins, guard_meta = await _roleplay_guard_reward(
        guild_id,
        reward_xp=base_xp,
        reward_coins=base_coins,
    )
    xp_per_level = max(1, int(settings.get("xp_per_level") or 120))
    rewarded = 0
    total_xp = 0
    total_coins = 0
    for user_id in participant_ids:
        character = await _roleplay_ensure_character(guild_id, user_id, settings)
        if not character or not character.get("id"):
            continue
        next_xp = max(0, int(character.get("xp") or 0) + payout_xp)
        next_coins = max(0, int(character.get("coins") or 0) + payout_coins)
        await storage.rp_characters.update(
            id=character["id"],
            xp=next_xp,
            coins=next_coins,
            level=_roleplay_level_from_xp(next_xp, xp_per_level),
            completed_events=max(0, int(character.get("completed_events") or 0) + 1),
            updated_at=_roleplay_now_utc(),
        )
        rewarded += 1
        total_xp += payout_xp
        total_coins += payout_coins

    if event_row.get("id"):
        await storage.rp_events.update(
            id=event_row["id"],
            status="idle",
            participants=[],
            ends_at=None,
            updated_at=_roleplay_now_utc(),
        )
    scenario_key = str(event_row.get("template_key") or "")
    scenario_name = str(event_row.get("event_title") or scenario_key or "Roleplay Event")
    if scenario_key:
        await _roleplay_track_scenario_stats(
            guild_id,
            scenario_key=scenario_key,
            scenario_name=scenario_name,
            reward_xp_delta=total_xp,
            reward_coins_delta=total_coins,
        )
    participants_count = max(0, rewarded)
    if participants_count > 0:
        await storage.rp_event_history.insert(
            guild_id=guild_id,
            event_title=scenario_name,
            scenario_key=scenario_key,
            trigger_type=str(trigger_type or "manual")[:60],
            participants_count=participants_count,
            total_reward_xp=total_xp,
            total_reward_coins=total_coins,
            reward_xp_per_player=int(total_xp / participants_count),
            reward_coins_per_player=int(total_coins / participants_count),
            started_at=event_row.get("started_at"),
            ended_at=_roleplay_now_utc(),
            created_at=_roleplay_now_utc(),
        )
        await storage.rp_event_history.delete_limited(500, {"guild_id": guild_id})
    summary = {
        "rewarded": rewarded,
        "reward_xp": payout_xp,
        "reward_coins": payout_coins,
        "total_reward_xp": total_xp,
        "total_reward_coins": total_coins,
        "guard_multiplier_percent": int(guard_meta.get("multiplier_percent") or 100),
        "title": scenario_name,
        "participants": rewarded,
        "total_xp": total_xp,
        "total_coins": total_coins,
        "coins_text": _roleplay_coins_text(settings, total_coins),
    }
    trigger_source = str(event_row.get("trigger_type") or "").strip().lower()
    if trigger_source.startswith("scheduled"):
        await _roleplay_send_schedule_end_notice(guild_id, settings, event_row, summary)
    return summary


async def _resolve_guild_member(bot_guild: Any, user_id: int | None) -> Any | None:
    if not bot_guild or not user_id:
        return None
    try:
        cached = bot_guild.get_member(int(user_id))
    except Exception:
        cached = None
    if cached is not None:
        return cached
    try:
        return await bot_guild.fetch_member(int(user_id))
    except Exception:
        return None


def _safe_audit_datetime_utc(raw_value: Any) -> datetime.datetime | None:
    if not isinstance(raw_value, datetime.datetime):
        return None
    if raw_value.tzinfo is None:
        return raw_value.replace(tzinfo=datetime.timezone.utc)
    return raw_value.astimezone(datetime.timezone.utc)


_LIVE_MOD_AUDIT_CACHE_TTL_SECONDS = 8.0
_LIVE_MOD_AUDIT_CACHE: dict[tuple[int, int], dict[str, Any]] = {}


def _get_live_mod_audit_cache(cache_key: tuple[int, int]) -> list[dict[str, Any]] | None:
    cached = _LIVE_MOD_AUDIT_CACHE.get(cache_key)
    if not isinstance(cached, dict):
        return None
    expires_at = float(cached.get("expires_at") or 0.0)
    if expires_at <= time.time():
        _LIVE_MOD_AUDIT_CACHE.pop(cache_key, None)
        return None
    rows = cached.get("rows")
    if isinstance(rows, list):
        return rows
    return []


def _posted_form_value(data: dict[str, Any], key: str, fallback: Any = "") -> Any:
    # If key is posted (even empty), keep the posted value.
    if isinstance(data, dict) and key in data:
        return data.get(key)
    return fallback


def _set_live_mod_audit_cache(cache_key: tuple[int, int], rows: list[dict[str, Any]]) -> None:
    _LIVE_MOD_AUDIT_CACHE[cache_key] = {
        "expires_at": time.time() + _LIVE_MOD_AUDIT_CACHE_TTL_SECONDS,
        "rows": list(rows or []),
    }


def _profile_from_user_obj(
    user_obj: Any | None,
    *,
    fallback_id: str = "",
    fallback_name: str = "unknown",
) -> tuple[str, str, bool]:
    display_name = str(fallback_name or "unknown").strip() or "unknown"
    avatar_url = ""
    is_bot_user = False
    if user_obj is not None:
        try:
            display_name = str(
                getattr(user_obj, "display_name", "")
                or getattr(user_obj, "global_name", "")
                or getattr(user_obj, "name", "")
                or display_name
            ).strip() or display_name
        except Exception:
            pass
        try:
            avatar_url = str(getattr(getattr(user_obj, "display_avatar", None), "url", "") or "").strip()
        except Exception:
            avatar_url = ""
        try:
            is_bot_user = bool(getattr(user_obj, "bot", False))
        except Exception:
            is_bot_user = False
    if not avatar_url:
        avatar_url = _discord_default_avatar_url(fallback_id or display_name or "0")
    return display_name, avatar_url, is_bot_user


async def _fetch_live_moderation_audit_rows(
    bot_guild: Any | None,
    *,
    limit: int = 180,
) -> list[dict[str, Any]]:
    if bot_guild is None:
        return []

    audit_reader = getattr(bot_guild, "audit_logs", None)
    if not callable(audit_reader):
        return []

    ban_action = getattr(discord.AuditLogAction, "ban", None)
    unban_action = getattr(discord.AuditLogAction, "unban", None)
    kick_action = getattr(discord.AuditLogAction, "kick", None)
    member_update_action = getattr(discord.AuditLogAction, "member_update", None)
    tracked_actions = {action for action in (ban_action, unban_action, kick_action, member_update_action) if action is not None}
    if not tracked_actions:
        return []

    bot_instance = get_bot()
    user_cache: dict[int, Any | None] = {}
    rows: list[dict[str, Any]] = []
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    bkk_tz = datetime.timezone(datetime.timedelta(hours=7))
    read_limit = max(40, min(int(limit), 400))
    guild_id_int = int(getattr(bot_guild, "id", 0) or 0)
    cache_key = (guild_id_int, read_limit)
    cached_rows = _get_live_mod_audit_cache(cache_key)
    if cached_rows is not None:
        return list(cached_rows)

    def _resolve_user_obj(user_id_int: int) -> Any | None:
        if user_id_int <= 0:
            return None
        if user_id_int in user_cache:
            return user_cache.get(user_id_int)
        resolved_obj = None
        try:
            resolved_obj = bot_guild.get_member(user_id_int)
        except Exception:
            resolved_obj = None
        if resolved_obj is None and bot_instance is not None:
            try:
                resolved_obj = bot_instance.get_user(user_id_int)
            except Exception:
                resolved_obj = None
        user_cache[user_id_int] = resolved_obj
        return resolved_obj

    try:
        async for entry in bot_guild.audit_logs(limit=read_limit):
            action = getattr(entry, "action", None)
            if action not in tracked_actions:
                continue

            action_key = "all"
            action_label = "-"
            punish_time = "-"
            remaining = "-"

            if action == ban_action:
                action_key = "ban"
                action_label = "แบน"
            elif action == unban_action:
                action_key = "ban"
                action_label = "ปลดแบน"
            elif action == kick_action:
                action_key = "warn"
                action_label = "เตะ"
            elif action == member_update_action:
                before_timeout = _safe_audit_datetime_utc(getattr(getattr(entry, "before", None), "timed_out_until", None))
                after_timeout = _safe_audit_datetime_utc(getattr(getattr(entry, "after", None), "timed_out_until", None))
                if before_timeout == after_timeout:
                    continue
                action_key = "mute"
                if after_timeout is not None and after_timeout > now_utc:
                    action_label = "ปิดเสียง"
                    created_utc_for_duration = _safe_audit_datetime_utc(getattr(entry, "created_at", None)) or now_utc
                    duration_seconds = 0
                    if before_timeout is not None and after_timeout > before_timeout:
                        duration_seconds = max(0, int((after_timeout - before_timeout).total_seconds()))
                    else:
                        duration_seconds = max(0, int((after_timeout - created_utc_for_duration).total_seconds()))
                    if duration_seconds > 0:
                        punish_time = _format_duration_th(duration_seconds)
                    remaining_seconds = max(0, int((after_timeout - now_utc).total_seconds()))
                    remaining = _format_duration_th(remaining_seconds) if remaining_seconds > 0 else "หมดเวลาแล้ว"
                else:
                    action_label = "ยกเลิกปิดเสียง"
                    remaining = "-"

            created_at_utc = _safe_audit_datetime_utc(getattr(entry, "created_at", None)) or now_utc
            created_ts = int(created_at_utc.timestamp())
            punished_at = created_at_utc.astimezone(bkk_tz).strftime("%d/%m/%Y %H:%M")

            target_obj = getattr(entry, "target", None)
            target_id_int = int(getattr(target_obj, "id", 0) or 0)
            target_id = str(target_id_int) if target_id_int > 0 else ""
            resolved_target_obj = _resolve_user_obj(target_id_int) if target_id_int > 0 else None
            target_name, target_avatar_url, _ = _profile_from_user_obj(
                resolved_target_obj or target_obj,
                fallback_id=target_id or "0",
                fallback_name=target_id or "unknown",
            )

            actor_obj = getattr(entry, "user", None)
            actor_id_int = int(getattr(actor_obj, "id", 0) or 0)
            actor_id = str(actor_id_int) if actor_id_int > 0 else ""
            resolved_actor_obj = _resolve_user_obj(actor_id_int) if actor_id_int > 0 else None
            actor_name, actor_avatar_url, actor_is_bot = _profile_from_user_obj(
                resolved_actor_obj or actor_obj,
                fallback_id=actor_id or "0",
                fallback_name=actor_id or "unknown",
            )
            if actor_obj is None and not actor_id:
                actor_label_prefix = "System"
            else:
                actor_label_prefix = "Bot" if actor_is_bot else "Admin"
            responsible = f"{actor_label_prefix}: {actor_name}"
            if actor_id:
                responsible = f"{responsible} ({actor_id})"

            rows.append(
                {
                    "ts": created_ts,
                    "member": target_id or "-",
                    "member_name": target_name,
                    "member_avatar_url": target_avatar_url,
                    "action": action_label,
                    "action_key": action_key,
                    "responsible": responsible,
                    "responsible_name": actor_name,
                    "responsible_id": actor_id,
                    "responsible_is_bot": actor_is_bot,
                    "responsible_avatar_url": actor_avatar_url,
                    "punish_time": punish_time,
                    "remaining": remaining,
                    "punished_at": punished_at,
                    "source": "discord_audit",
                }
            )
    except Exception as error:
        logger.debug(f"Live moderation audit fetch failed in guild {getattr(bot_guild, 'id', 0)}: {error}")
        _set_live_mod_audit_cache(cache_key, [])
        return []

    rows.sort(key=lambda row: int(row.get("ts") or 0), reverse=True)
    resolved_rows = rows[:300]
    _set_live_mod_audit_cache(cache_key, resolved_rows)
    return resolved_rows


def _dashboard_access_payload_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    payload = (state or {}).get("dashboard_access") if isinstance(state, dict) else {}
    return payload if isinstance(payload, dict) else {}


def _safe_dashboard_next_path(guild_id: int, raw_next: Any) -> str:
    fallback = f"/dashboard/guild/{int(guild_id)}"
    candidate = str(raw_next or "").strip()
    if not candidate:
        return fallback
    if "://" in candidate or candidate.startswith("//"):
        return fallback
    if not candidate.startswith("/dashboard/"):
        return fallback
    return candidate


async def dashboard_set_access_mode(request: Request, guild_id: int, mode: str, next: str | None = None):
    session = _session_from_request(request)
    safe_next = _safe_dashboard_next_path(guild_id, next)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        encoded_notice = urlencode({"notice": "เฉพาะ Owner BOT เท่านั้นที่เปลี่ยนโหมดสิทธิ์ได้"}).split("=", 1)[1]
        sep = "&" if "?" in safe_next else "?"
        return RedirectResponse(f"{safe_next}{sep}notice={encoded_notice}", status_code=303)

    applied_mode = _dashboard_set_access_mode(session, mode)
    mode_notice = (
        "สลับเป็นโหมด Owner BOT แล้ว (ปลดล็อกแก้ไขทุกระบบ)"
        if applied_mode == OWNERBOT_DASHBOARD_ACCESS_MODE
        else "สลับเป็นโหมด Owner Guild แล้ว (ใช้ข้อจำกัดตามแพลนกิลด์)"
    )
    encoded_notice = urlencode({"notice": mode_notice}).split("=", 1)[1]
    sep = "&" if "?" in safe_next else "?"
    return RedirectResponse(f"{safe_next}{sep}notice={encoded_notice}", status_code=303)


async def _inject_dashboard_access_state(
    *,
    session: dict[str, Any],
    guild_id: int,
    current_guild: dict[str, Any] | None,
    bot_guild: Any,
    state: dict[str, Any],
) -> dict[str, Any]:
    safe_state = dict(state or {})
    user_id_raw = _session_user_id(session)
    is_dashboard_admin_user = _is_dashboard_admin(session)
    access_mode = _dashboard_access_mode_from_session(session)
    ownerbot_mode_enabled = bool(
        is_dashboard_admin_user and access_mode == OWNERBOT_DASHBOARD_ACCESS_MODE
    )
    try:
        user_id = int(user_id_raw) if user_id_raw is not None else None
    except Exception:
        user_id = None

    owner_id_raw = (current_guild or {}).get("owner_id") if isinstance(current_guild, dict) else None
    if not owner_id_raw:
        owner_id_raw = getattr(bot_guild, "owner_id", 0)
    try:
        owner_id = int(owner_id_raw or 0)
    except Exception:
        owner_id = 0

    raw_guild = _session_raw_guild(session, guild_id)
    raw_permissions = _permission_bits_from_raw_guild(raw_guild)
    member = await _resolve_guild_member(bot_guild, user_id)
    guild_permission_bits = int(getattr(getattr(member, "guild_permissions", None), "value", 0) or 0)
    effective_permissions = int(raw_permissions | guild_permission_bits)

    has_admin_permission = bool(effective_permissions & ADMINISTRATOR)
    has_manage_guild_permission = bool(effective_permissions & MANAGE_GUILD)
    has_admin_like_permission = has_admin_permission or has_manage_guild_permission
    is_owner = bool(user_id and owner_id and int(user_id) == int(owner_id))
    effective_is_owner = bool(is_owner or is_dashboard_admin_user)

    allowed_role_ids = _dashboard_editor_role_ids_from_db(guild_id)
    member_role_ids: list[str] = []
    if member is not None:
        try:
            for role in list(getattr(member, "roles", []) or []):
                role_id = str(getattr(role, "id", "") or "").strip()
                if role_id.isdigit():
                    member_role_ids.append(role_id)
        except Exception:
            member_role_ids = []
    allowed_role_set = set(allowed_role_ids)
    has_allowed_role = any(role_id in allowed_role_set for role_id in member_role_ids)

    can_edit_settings = bool(effective_is_owner or (has_admin_like_permission and has_allowed_role))
    if can_edit_settings:
        deny_notice = ""
    elif is_dashboard_admin_user:
        deny_notice = ""
    elif not has_admin_like_permission:
        deny_notice = "ไม่มีสิทธิ์ผู้ดูแลกิลด์ และไม่มีสิทธิ์การตั้งค่ากิลด์"
    else:
        deny_notice = "ไม่มีสิทธิ์การตั้งค่ากิลด์"

    safe_state["dashboard_access"] = {
        "user_id": str(user_id or ""),
        "owner_id": str(owner_id or ""),
        "is_owner": is_owner,
        "effective_is_owner": effective_is_owner,
        "is_dashboard_admin": is_dashboard_admin_user,
        "access_mode": access_mode,
        "ownerbot_mode_enabled": ownerbot_mode_enabled,
        "forced_plan_tier": ("diamond" if ownerbot_mode_enabled else ""),
        "has_admin_permission": has_admin_permission,
        "has_manage_guild_permission": has_manage_guild_permission,
        "has_admin_like_permission": has_admin_like_permission,
        "allowed_role_ids": allowed_role_ids,
        "member_role_ids": member_role_ids,
        "has_allowed_role": has_allowed_role,
        "can_edit_settings": can_edit_settings,
        "deny_notice": deny_notice,
    }
    return safe_state


def _user_music_guild_payload(bot_guild: Any, raw_guild: dict[str, Any] | None = None) -> dict[str, Any]:
    guild_id = str(getattr(bot_guild, "id", "0") or "0")
    icon_hash = str((raw_guild or {}).get("icon") or "").strip()
    icon_url = (
        f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png?size=128"
        if icon_hash
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )
    return {
        "id": guild_id,
        "name": str(getattr(bot_guild, "name", f"Guild {guild_id}") or f"Guild {guild_id}"),
        "icon": icon_url,
        "members": int(getattr(bot_guild, "member_count", 0) or 0),
        "channels": len(getattr(bot_guild, "channels", []) or []),
        "roles": len(getattr(bot_guild, "roles", []) or []),
        "owner_id": int(getattr(bot_guild, "owner_id", 0) or 0),
    }


async def _require_music_member_context(request: Request, guild_id: int):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return None, None, None, {}

    raw_guild = _session_raw_guild(session, guild_id)
    if not raw_guild:
        return session, None, None, {}

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return session, None, None, {}

    state = await _ensure_guild_records(guild_id, bot_guild)
    runtime_settings = _ownerbot_runtime_from_db()
    block_reason = _ownerbot_runtime_block_reason(guild_id, runtime_settings)
    if block_reason:
        blocked_state = dict(state or {})
        blocked_state["ownerbot_block_reason"] = block_reason
        return session, None, None, blocked_state

    current_guild = _user_music_guild_payload(bot_guild, raw_guild)
    return session, current_guild, bot_guild, state


_WEB_MUSIC_PLAYLISTS: dict[str, dict[str, Any]] = {
    "thai_pop": {
        "label": "Thai Pop",
        "queries": [
            "Tilly Birds เพื่อนเล่น ไม่เล่นเพื่อน",
            "MILLI สุดปัง",
            "Three Man Down ฝนตกไหม",
            "Billkin กีดกัน",
            "BOWKYLION ลงใจ",
        ],
    },
    "chill": {
        "label": "Chill Mix",
        "queries": [
            "chill hits playlist",
            "LANY Malibu Nights",
            "RINI My Favourite Clothes",
            "HONNE Day 1",
            "Daniel Caesar Best Part",
        ],
    },
    "lofi": {
        "label": "Lo-Fi Study",
        "queries": [
            "lofi hip hop beats to relax/study to",
            "j'san alone by your side",
            "idealism both of us",
            "Aso Seasons",
            "Nymano Solitude",
        ],
    },
    "edm": {
        "label": "EDM Party",
        "queries": [
            "Martin Garrix Animals",
            "Alan Walker Faded",
            "The Chainsmokers Closer",
            "Avicii Wake Me Up",
            "David Guetta Titanium",
        ],
    },
}


def _music_setup_channel_ids_from_state(state: dict[str, Any] | None) -> tuple[int | None, int | None]:
    music_state = (state or {}).get("music") or {}
    setup_text_raw = (
        music_state.get("music_setup_channel_id")
        or music_state.get("music_command_channel_id")
    )
    setup_voice_raw = (
        music_state.get("music_setup_voice_channel_id")
        or music_state.get("music_voice_channel_id")
    )
    setup_text_id = int(setup_text_raw) if str(setup_text_raw or "").strip().isdigit() else None
    setup_voice_id = int(setup_voice_raw) if str(setup_voice_raw or "").strip().isdigit() else None
    return setup_text_id, setup_voice_id


def _voice_human_members(voice_channel: Any) -> list[Any]:
    return [member for member in list(getattr(voice_channel, "members", []) or []) if not bool(getattr(member, "bot", False))]


def _music_queue_limit_from_guild_state(guild_state: dict[str, Any] | None) -> int:
    tier = _normalize_plan_tier((guild_state or {}).get("subscription", "free"))
    if tier in {"diamond", "permanent"}:
        return 99
    if tier == "golden":
        return 60
    if tier == "silver":
        return 30
    return 15


async def _ensure_web_music_voice_client(
    *,
    bot_guild: Any,
    state: dict[str, Any] | None,
    actor_member: Any | None,
    action: str,
) -> tuple[Any | None, str | None]:
    voice_client = getattr(bot_guild, "voice_client", None)
    if voice_client and getattr(voice_client, "connected", True):
        return voice_client, None

    if action not in {"add_track", "add_track_at", "add_playlist", "playlist_play"}:
        return None, "บอทยังไม่ได้เชื่อมห้องเสียงในกิลด์นี้"

    _, setup_voice_id = _music_setup_channel_ids_from_state(state)
    setup_voice_channel = bot_guild.get_channel(int(setup_voice_id)) if setup_voice_id else None
    actor_voice_channel = (
        getattr(getattr(actor_member, "voice", None), "channel", None)
        if actor_member
        else None
    )
    target_channel = setup_voice_channel or actor_voice_channel
    if not target_channel:
        return None, "บอทไม่ได้อยู่ในห้องเสียง หรือคุณไม่ได้อยู่ในห้องเสียง"

    try:
        connected = await target_channel.connect(
            cls=wavelink.Player,
            timeout=25,
            self_deaf=True,
        )
    except discord.ClientException:
        connected = getattr(bot_guild, "voice_client", None)
    except Exception as exc:
        return None, f"เชื่อมห้องเสียงไม่สำเร็จ: {type(exc).__name__}"

    if connected and hasattr(connected, "inactive_timeout"):
        try:
            connected.inactive_timeout = 10
        except Exception:
            pass
    return connected, None


async def _move_music_queue(
    *,
    voice_client: Any,
    queue_index: int,
    direction: str,
) -> tuple[bool, str]:
    queue_obj = getattr(voice_client, "queue", None)
    if queue_obj is None:
        return False, "ไม่พบคิวเพลง"
    queue_items = list(queue_obj or [])
    if not queue_items:
        return False, "คิวเพลงว่างอยู่ตอนนี้"
    source_idx = max(1, int(queue_index)) - 1
    if source_idx < 0 or source_idx >= len(queue_items):
        return False, "ลำดับคิวไม่ถูกต้อง"
    target_idx = source_idx - 1 if direction == "up" else source_idx + 1
    if target_idx < 0 or target_idx >= len(queue_items):
        return False, "ไม่สามารถย้ายคิวไปตำแหน่งนั้นได้"

    picked_track = queue_items.pop(source_idx)
    queue_items.insert(target_idx, picked_track)
    try:
        queue_obj.clear()
        for item in queue_items:
            await queue_obj.put_wait(item)
    except Exception:
        return False, "ย้ายลำดับคิวไม่สำเร็จ"
    return True, f"ย้ายคิวเพลง: {getattr(picked_track, 'title', 'Unknown')}"


async def _delete_music_queue_item(queue_obj: Any, index: int) -> None:
    delete_result = queue_obj.delete(index)
    if asyncio.iscoroutine(delete_result):
        await delete_result


async def _play_music_queue_now(
    *,
    voice_client: Any,
    queue_index: int,
    default_volume: int,
) -> tuple[bool, str]:
    queue_obj = getattr(voice_client, "queue", None)
    if queue_obj is None:
        return False, "ไม่พบคิวเพลง"

    queue_items = list(queue_obj or [])
    if not queue_items:
        return False, "คิวเพลงว่างอยู่ตอนนี้"

    source_idx = max(1, int(queue_index)) - 1
    if source_idx < 0 or source_idx >= len(queue_items):
        return False, "ลำดับคิวไม่ถูกต้อง"

    selected_track = queue_items.pop(source_idx)

    try:
        queue_obj.clear()
        for item in queue_items:
            await queue_obj.put_wait(item)
    except Exception:
        return False, "ไม่สามารถจัดการคิวเพลงได้"

    safe_volume = max(
        0,
        min(
            100,
            int(getattr(voice_client, "volume", 0) or 0) or int(default_volume or 80),
        ),
    )
    try:
        await voice_client.play(selected_track, volume=safe_volume)
    except Exception:
        try:
            if hasattr(queue_obj, "put_at"):
                queue_obj.put_at(0, selected_track)
            else:
                rebuilt_queue = [selected_track, *list(queue_obj or [])]
                queue_obj.clear()
                for item in rebuilt_queue:
                    await queue_obj.put_wait(item)
        except Exception:
            pass
        return False, "สั่งเล่นเพลงจากคิวไม่สำเร็จ"

    selected_title = _clean_text(getattr(selected_track, "title", "Unknown"))
    return True, f"กำลังเล่นเพลงจากคิว: {selected_title}"


async def _add_music_playlist(
    *,
    voice_client: Any,
    playlist_key: str,
    default_volume: int,
    queue_limit: int,
) -> tuple[bool, str]:
    playlist = _WEB_MUSIC_PLAYLISTS.get(str(playlist_key or "").strip())
    if not playlist:
        return False, "ไม่พบเพลย์ลิสต์ที่เลือก"

    tracks: list[Any] = []
    for raw_query in list(playlist.get("queries") or [])[:12]:
        query = str(raw_query or "").strip()
        if not query:
            continue
        try:
            result = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
        except Exception:
            result = []
        if result:
            tracks.append(result[0])
    if not tracks:
        return False, "ไม่พบเพลงจากเพลย์ลิสต์ที่เลือก"

    safe_queue_limit = max(1, min(99, int(queue_limit or 15)))
    added_count = 0
    skipped_count = 0
    for index, track in enumerate(tracks):
        if not getattr(voice_client, "current", None) and index == 0:
            await voice_client.play(track, volume=max(0, min(100, int(default_volume or 80))))
            added_count += 1
            continue
        try:
            current_queue_size = len(getattr(voice_client, "queue", []) or [])
        except Exception:
            current_queue_size = 0
        if current_queue_size >= safe_queue_limit:
            skipped_count += 1
            continue
        await voice_client.queue.put_wait(track)
        added_count += 1

    if added_count <= 0:
        return False, f"คิวเต็มแล้ว (เพิ่มได้สูงสุด {safe_queue_limit} เพลง)"

    try:
        queue_obj = getattr(voice_client, "queue", None)
        if queue_obj is not None and hasattr(queue_obj, "mode"):
            if hasattr(wavelink.QueueMode, "loop_all"):
                queue_obj.mode = wavelink.QueueMode.loop_all
            else:
                queue_obj.mode = wavelink.QueueMode.loop
    except Exception:
        pass

    try:
        if getattr(voice_client, "autoplay", None) == wavelink.AutoPlayMode.disabled:
            voice_client.autoplay = wavelink.AutoPlayMode.enabled
    except Exception:
        pass

    playlist_name = str(playlist.get("label") or playlist_key)
    message = f"เพิ่มเพลย์ลิสต์ {playlist_name} แล้ว ({added_count} เพลง)"
    if skipped_count > 0:
        message += f" | ข้าม {skipped_count} เพลงเพราะคิวเต็ม"
    return True, message


def _web_playlist_entry_payload(entry: dict[str, Any], index: int) -> dict[str, Any]:
    kind = str(entry.get("kind") or "query").strip().lower()
    if kind not in {"url", "query"}:
        kind = "query"
    value = _clean_text(str(entry.get("value") or "").strip())[:220]
    return {
        "index": index,
        "kind": kind,
        "value": value,
    }


def _web_user_playlist_payload(
    rows: list[dict[str, Any]],
    *,
    selected_key: str = "",
    max_playlists: int = user_music_playlists.MAX_USER_PLAYLISTS,
    max_items_per_playlist: int = user_music_playlists.MAX_ITEMS_PER_PLAYLIST,
) -> dict[str, Any]:
    selected_lookup = str(selected_key or "").strip().casefold()
    payload_rows: list[dict[str, Any]] = []
    selected_row: dict[str, Any] | None = None
    for row in list(rows or []):
        row_slug = str(row.get("slug") or "").strip()
        row_name = str(row.get("name") or "").strip()
        items = list(row.get("items") or [])
        row_payload = {
            "id": int(row.get("id", 0) or 0),
            "slug": row_slug,
            "name": row_name or row_slug,
            "item_count": len(items),
            "items": [
                _web_playlist_entry_payload(item, index)
                for index, item in enumerate(items, start=1)
            ],
        }
        payload_rows.append(row_payload)
        if (
            selected_lookup
            and (
                row_slug.casefold() == selected_lookup
                or row_name.casefold() == selected_lookup
                or str(row_payload["id"]) == selected_lookup
            )
            and selected_row is None
        ):
            selected_row = row_payload
    if selected_row is None and payload_rows:
        selected_row = payload_rows[0]
    return {
        "playlists": payload_rows,
        "selected_playlist": selected_row,
        "max_playlists": max(1, int(max_playlists or user_music_playlists.MAX_USER_PLAYLISTS)),
        "max_items_per_playlist": max(1, int(max_items_per_playlist or user_music_playlists.MAX_ITEMS_PER_PLAYLIST)),
    }


def _parse_web_pick_indexes(raw_value: Any, *, max_index: int) -> tuple[list[int], str | None]:
    text = str(raw_value or "").strip().lower()
    if not text:
        return [], "empty"
    if not re.fullmatch(r"[0-9,\s\-]+", text):
        return [], "format"
    picks: list[int] = []
    seen: set[int] = set()
    for token in [part for part in re.split(r"[\s,]+", text) if part]:
        if "-" in token:
            left, right = token.split("-", 1)
            if not left.isdigit() or not right.isdigit():
                return [], "format"
            start, end = int(left), int(right)
            if start < 1 or end < 1:
                return [], "range"
            step = 1 if end >= start else -1
            for value in range(start, end + step, step):
                if value > max_index:
                    return [], "out_of_range"
                if value not in seen:
                    seen.add(value)
                    picks.append(value)
        else:
            if not token.isdigit():
                return [], "format"
            value = int(token)
            if value < 1 or value > max_index:
                return [], "out_of_range"
            if value not in seen:
                seen.add(value)
                picks.append(value)
    if not picks:
        return [], "empty"
    return picks, None


async def _web_search_tracks(query: str) -> list[Any]:
    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        return []

    attempts: list[tuple[str, dict[str, Any]]] = []
    if cleaned_query.startswith("http://") or cleaned_query.startswith("https://"):
        attempts.append(("direct", {}))
        attempts.append(("youtube", {"source": wavelink.TrackSource.YouTube}))
    else:
        attempts.append(("youtube", {"source": wavelink.TrackSource.YouTube}))
        attempts.append(("direct", {}))

    for _mode, kwargs in attempts:
        try:
            result = await wavelink.Playable.search(cleaned_query, **kwargs)
        except Exception:
            continue
        if result:
            return list(result)
    return []


async def _resolve_web_playlist_entries_to_tracks(
    entries: list[dict[str, Any]],
    *,
    max_tracks: int = 120,
) -> tuple[list[Any], list[str]]:
    tracks: list[Any] = []
    unresolved: list[str] = []
    for entry in list(entries or []):
        value = str(entry.get("value") or "").strip()
        if not value:
            continue
        kind = str(entry.get("kind") or "query").strip().lower()
        result = await _web_search_tracks(value)
        if not result:
            unresolved.append(value)
            continue
        selected_tracks = (
            list(result[:25])
            if kind == "url" and "list=" in value.lower()
            else [result[0]]
        )
        for track in selected_tracks:
            tracks.append(track)
            if len(tracks) >= max_tracks:
                return tracks, unresolved
    return tracks, unresolved


async def _enqueue_web_tracks(
    *,
    voice_client: Any,
    tracks: list[Any],
    default_volume: int,
    queue_limit: int,
    requester: Any = None,
) -> tuple[int, int]:
    safe_queue_limit = max(1, min(99, int(queue_limit or 15)))
    added_count = 0
    skipped_count = 0
    for track in list(tracks or []):
        try:
            if requester is not None:
                track.requester = requester
        except Exception:
            pass
        if not getattr(voice_client, "current", None) and added_count <= 0:
            await voice_client.play(
                track, volume=max(0, min(100, int(default_volume or 80)))
            )
            added_count += 1
            continue
        try:
            current_queue_size = len(getattr(voice_client, "queue", []) or [])
        except Exception:
            current_queue_size = 0
        if current_queue_size >= safe_queue_limit:
            skipped_count += 1
            continue
        await voice_client.queue.put_wait(track)
        added_count += 1
    return added_count, skipped_count


async def dashboard_music_user(request: Request, guild_id: int, notice: str | None = None):
    session, current_guild, bot_guild, state = await _require_music_member_context(request, guild_id)
    if not session:
        next_path = f"/dashboard/music/{guild_id}"
        return RedirectResponse(
            f"/dashboard/login?{urlencode({'next': next_path})}",
            status_code=303,
        )
    if not current_guild or not bot_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return HTMLResponse(
                _render_ownerbot_runtime_blocked(session, [], guild_id, blocked_notice),
                status_code=403,
            )
        return HTMLResponse(
            _render_guild_picker(session, await _manageable_guilds_live(session), "คุณไม่มีสิทธิ์ใช้งานหน้าเพลงของเซิร์ฟเวอร์นี้"),
            status_code=403,
        )
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="music")
    if tab_block_reason:
        return HTMLResponse(
            _render_ownerbot_runtime_blocked(session, [current_guild], guild_id, tab_block_reason),
            status_code=403,
        )

    return HTMLResponse(
        _render_music(
            session,
            [current_guild],
            current_guild,
            bot_guild,
            state,
            notice=notice,
            active_tab_slug="music",
            title_override="เพลงสำหรับสมาชิก",
            description_override="ควบคุมเพลงร่วมกันได้ทันทีจากหน้าเว็บนี้",
            show_settings_panel=False,
            control_action_path=f"/dashboard/music/{guild_id}/control",
            compact_user_layout=True,
        )
    )


async def dashboard_music_user_live(request: Request, guild_id: int):
    session, current_guild, bot_guild, state = await _require_music_member_context(request, guild_id)
    if not session:
        return JSONResponse({"error": "ยังไม่ได้เข้าสู่ระบบ"}, status_code=403)
    if not current_guild or not bot_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"error": blocked_notice}, status_code=403)
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="music")
    if tab_block_reason:
        return JSONResponse({"error": tab_block_reason}, status_code=403)
    return JSONResponse(
        _live_payload(current_guild, bot_guild, state, tab="music"),
        headers={"Cache-Control": "private, no-cache, must-revalidate", "Vary": "Cookie"},
    )


async def dashboard_music_user_live_options(request: Request, guild_id: int):
    session, current_guild, bot_guild, state = await _require_music_member_context(request, guild_id)
    if not session:
        return JSONResponse({"error": "ยังไม่ได้เข้าสู่ระบบ"}, status_code=403)
    if not current_guild or not bot_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"error": blocked_notice}, status_code=403)
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="music")
    if tab_block_reason:
        return JSONResponse({"error": tab_block_reason}, status_code=403)
    return _live_options_json_response(request, bot_guild)


async def dashboard_overview(request: Request, guild_id: int, notice: str | None = None):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return HTMLResponse(
                _render_ownerbot_runtime_blocked(session, guilds, guild_id, blocked_notice),
                status_code=403,
            )
        return HTMLResponse(_render_guild_picker(session, guilds, "คุณไม่มีสิทธิ์เข้าถึงเซิร์ฟเวอร์นี้"), status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="overview")
    if tab_block_reason:
        return HTMLResponse(
            _render_ownerbot_runtime_blocked(session, guilds, guild_id, tab_block_reason),
            status_code=403,
        )
    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    try:
        await dashboard_activity.ensure_loaded(guild_id)
        if bot_guild:
            await dashboard_activity.record_member_snapshot(
                guild_id,
                int(getattr(bot_guild, "member_count", 0) or 0),
            )
    except Exception:
        pass
    return HTMLResponse(_render_overview(session, guilds, current_guild, bot_guild, state, notice=notice))


def _resolve_live_tab_slug(tab: str | None, fallback: str = "overview") -> str:
    normalized = str(tab or "").strip().lower()
    if not normalized:
        normalized = fallback
    if normalized == "welcomer":
        return "welcome"
    return normalized


def _if_none_match_contains(request: Request, etag: str) -> bool:
    candidate = str(etag or "").strip()
    if not candidate:
        return False
    raw = str(request.headers.get("if-none-match") or "").strip()
    if not raw:
        return False
    for part in raw.split(","):
        token = str(part or "").strip()
        if not token:
            continue
        if token == "*" or token == candidate:
            return True
    return False


def _live_options_json_response(request: Request, bot_guild) -> Response:
    payload = _live_options_payload(bot_guild)
    signature = str(payload.get("signature") or "").strip()
    etag = f'W/"live-options-{signature}"' if signature else ""
    headers = {
        "Cache-Control": "private, no-cache, must-revalidate",
        "Vary": "Cookie",
    }
    if etag:
        headers["ETag"] = etag
        if _if_none_match_contains(request, etag):
            return Response(status_code=304, headers=headers)
    return JSONResponse(payload, headers=headers)


async def dashboard_live(request: Request, guild_id: int, tab: str | None = None):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"error": blocked_notice}, status_code=403)
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    requested_tab = _resolve_live_tab_slug(tab, fallback="overview")
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug=requested_tab)
    if tab_block_reason:
        return JSONResponse({"error": tab_block_reason}, status_code=403)
    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    return JSONResponse(
        _live_payload(current_guild, bot_guild, state, tab=requested_tab),
        headers={"Cache-Control": "private, no-cache, must-revalidate", "Vary": "Cookie"},
    )

async def dashboard_live_options(request: Request, guild_id: int, tab: str | None = None):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"error": blocked_notice}, status_code=403)
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    requested_tab = _resolve_live_tab_slug(tab, fallback="overview")
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug=requested_tab)
    if tab_block_reason:
        return JSONResponse({"error": tab_block_reason}, status_code=403)
    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    return _live_options_json_response(request, bot_guild)

async def dashboard_emoji_picker_payload(request: Request, guild_id: int):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"error": blocked_notice}, status_code=403)
        return JSONResponse({"error": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    return JSONResponse(_dashboard_emoji_picker_payload(session, guilds))

async def dashboard_public_donate(request: Request, guild_id: int, notice: str | None = None):
    session = _session_from_request(request)
    return HTMLResponse(await _render_public_donate_page(guild_id, session=session, notice=notice))

async def dashboard_promote_history_redirect(request: Request, guild_id: int):
    query_params: dict[str, str] = {"guild_id": str(int(guild_id))}
    query_text = str(request.query_params.get("q") or "").strip()
    if query_text:
        query_params["q"] = query_text[:140]
    source_filter = str(request.query_params.get("source") or "").strip().lower()
    if source_filter in {"web", "discord"}:
        query_params["source"] = source_filter
    limit_filter = str(request.query_params.get("limit") or "").strip()
    if limit_filter in {"50", "100", "200"}:
        query_params["limit"] = limit_filter
    return RedirectResponse(f"/promotehistory?{urlencode(query_params)}", status_code=303)

async def dashboard_tab(request: Request, guild_id: int, tab: str, notice: str | None = None):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    bot = get_bot()
    if bot:
        try:
            await guild_growth.record_snapshot(
                len(getattr(bot, "guilds", []) or []),
                source=f"dashboard_tab:{tab}",
            )
        except Exception:
            pass
    if tab == "welcomer":
        return RedirectResponse(f"/dashboard/guild/{guild_id}/welcome", status_code=303)
    if tab == "tools":
        return RedirectResponse(f"/dashboard/guild/{guild_id}", status_code=303)
    if tab == "donate" and not session:
        target = f"/dashboard/donate/{guild_id}"
        if notice:
            encoded_notice = urlencode({"notice": notice}).split("=", 1)[1]
            target = f"{target}?notice={encoded_notice}"
        return RedirectResponse(target, status_code=303)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return HTMLResponse(
                _render_ownerbot_runtime_blocked(session, guilds, guild_id, blocked_notice),
                status_code=403,
            )
        return HTMLResponse(_render_guild_picker(session, guilds, "คุณไม่มีสิทธิ์เข้าถึงเซิร์ฟเวอร์นี้"), status_code=403)

    if tab == "tickets_plus":
        query_suffix = f"?{request.url.query}" if str(request.url.query or "").strip() else ""
        return RedirectResponse(f"/dashboard/guild/{guild_id}/tickets{query_suffix}", status_code=303)

    resolved_tab_for_access = "welcome" if tab == "welcomer" else tab
    if _dashboard_tab_requires_editor_access(resolved_tab_for_access):
        dashboard_access = _dashboard_access_payload_from_state(state)
        if not bool(dashboard_access.get("can_edit_settings")):
            deny_notice = _dashboard_access_notice_from_state(state)
            return HTMLResponse(
                _render_dashboard_access_blocked(session, guilds, guild_id, deny_notice),
                status_code=403,
            )

    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug=tab)
    if tab_block_reason:
        return HTMLResponse(
            _render_ownerbot_runtime_blocked(session, guilds, guild_id, tab_block_reason),
            status_code=403,
        )
    bot_guild = bot.get_guild(guild_id) if bot else None
    if tab in {"audit_logs", "logs"} and bot_guild is not None:
        live_moderation_rows = await _fetch_live_moderation_audit_rows(bot_guild, limit=220)
        if live_moderation_rows:
            hydrated_state = dict(state or {})
            hydrated_state["live_moderation_audit_rows"] = live_moderation_rows
            state = hydrated_state
    if tab == "overview":
        try:
            await dashboard_activity.ensure_loaded(guild_id)
            if bot_guild:
                await dashboard_activity.record_member_snapshot(
                    guild_id,
                    int(getattr(bot_guild, "member_count", 0) or 0),
                )
        except Exception:
            pass
    if tab == "verify":
        state = dict(state or {})
        requested_view = str(request.query_params.get("view") or "").strip().lower()
        state["verify_view_mode"] = "web_verify" if requested_view in {"web", "web_verify"} else "verify"
        verify_before = _normalize_verify_settings(state.get("verify") or {})
        verify_after = await _ensure_verify_back_url_from_bot(guild_id, verify_before)
        if verify_after != verify_before:
            await _save_verify_fallback(guild_id, verify_after)
        state["verify"] = verify_after
    tab_context = GuildTabRenderContext(
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        bot_guild=bot_guild,
        state=state,
        notice=notice,
    )

    # Plan check for tab access
    effective_plan_tier = _dashboard_effective_plan_tier(state, session=session)

    def _is_subscription_expired(raw_value: Any) -> bool:
        if not raw_value:
            return False
        end_dt = None
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

    if (
        not _dashboard_ownerbot_mode_from_state(state, session=session)
        and effective_plan_tier != "free"
        and _is_subscription_expired(state["guild"].get("subscription_end"))
    ):
        effective_plan_tier = "free"

    required_plan_tier = _required_plan_for_dashboard_tab(tab)
    if required_plan_tier != "free" and not _is_plan_at_least(effective_plan_tier, required_plan_tier):
        return HTMLResponse(_render_pricing_locked(session, guilds, current_guild, tab, state=state))

    rendered_html = render_dashboard_tab(tab, tab_context)
    if rendered_html is None:
        return RedirectResponse(f"/dashboard/guild/{guild_id}", status_code=303)
    return HTMLResponse(rendered_html)

async def update_general_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)
    prefix = (data.get("prefix") or BOT_CONFIG.PREFIX).strip()[:5] or BOT_CONFIG.PREFIX
    requested_language = str(data.get("language") or state["guild"].get("language") or "th").strip().lower()
    language = requested_language if requested_language in {"th", "en"} else "th"
    await storage.guilds.update(
        id=state["guild"]["id"],
        prefix=prefix,
        language=language,
        owner_id=current_guild["owner_id"],
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าทั่วไปแล้ว", target="general")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'บันทึกการตั้งค่าแล้ว'}).split('=',1)[1]}", status_code=303)

async def update_bot_profile_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
    )
    if guard_response:
        return guard_response

    effective_plan_tier = _dashboard_effective_plan_tier(state, session=session)
    if not _is_plan_at_least(effective_plan_tier, "silver"):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'ชื่อและรูปโปรไฟล์บอทใช้ได้เฉพาะพรีเมียม (Silver/Gole/Diamond/Permanent)'}).split('=',1)[1]}",
            status_code=303,
        )

    content_type = str(request.headers.get("content-type") or "").lower()
    parsed_form = None
    data: dict[str, str]
    if "multipart/form-data" in content_type:
        try:
            parsed_form = await request.form()
        except AssertionError:
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'เซิร์ฟเวอร์ยังไม่รองรับการอ่านฟอร์มแบบไฟล์ กรุณาติดตั้งแพ็กเกจ python-multipart แล้วรีสตาร์ตบอท'}).split('=',1)[1]}",
                status_code=303,
            )
        data = {k: str(v) for k, v in parsed_form.items() if k != "bot_avatar_file"}
    else:
        data = await _parse_form(request)

    profile_action = str(data.get("bot_profile_action") or "save").strip().lower()
    if profile_action not in {"save", "reset_nickname", "reset_avatar"}:
        profile_action = "save"

    requested_nickname = str(data.get("bot_nickname") or "").strip()
    uploaded_avatar = parsed_form.get("bot_avatar_file") if parsed_form is not None else None

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    bot_member = getattr(bot_guild, "me", None) if bot_guild else None
    if not bot or not bot_member:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'ไม่พบบอทในเซิร์ฟเวอร์นี้ หรือบอทออฟไลน์'}).split('=',1)[1]}",
            status_code=303,
        )

    edit_kwargs: dict[str, Any] = {}

    if profile_action == "reset_nickname":
        edit_kwargs["nick"] = None
    elif profile_action == "reset_avatar":
        edit_kwargs["avatar"] = None
    else:
        if requested_nickname:
            edit_kwargs["nick"] = requested_nickname[:32]

        if uploaded_avatar and getattr(uploaded_avatar, "filename", None):
            filename = str(getattr(uploaded_avatar, "filename", "") or "").strip()
            ext = Path(filename).suffix.lower()
            upload_content_type = str(getattr(uploaded_avatar, "content_type", "") or "").strip().lower()
            allowed_ext = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
            if ext not in allowed_ext and not upload_content_type.startswith("image/"):
                return RedirectResponse(
                    f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'ชนิดไฟล์รูปไม่รองรับ (รองรับเฉพาะ PNG/JPG/WEBP/GIF)'}).split('=',1)[1]}",
                    status_code=303,
                )
            raw_bytes = await uploaded_avatar.read()
            if not raw_bytes:
                return RedirectResponse(
                    f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'ไม่พบข้อมูลรูปภาพที่อัปโหลด'}).split('=',1)[1]}",
                    status_code=303,
                )
            if len(raw_bytes) > 8 * 1024 * 1024:
                return RedirectResponse(
                    f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'ไฟล์รูปมีขนาดใหญ่เกินไป (สูงสุด 8MB)'}).split('=',1)[1]}",
                    status_code=303,
                )
            edit_kwargs["avatar"] = raw_bytes

    if not edit_kwargs:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'ไม่มีข้อมูลที่ต้องบันทึก'}).split('=',1)[1]}",
            status_code=303,
        )

    try:
        await bot_member.edit(
            reason=f"Dashboard bot profile update by {session.get('user', {}).get('username', 'dashboard-user')}",
            **edit_kwargs,
        )
    except discord.Forbidden:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': 'บอทไม่มีสิทธิ์เพียงพอในการแก้ไขโปรไฟล์'}).split('=',1)[1]}",
            status_code=303,
        )
    except discord.HTTPException as error:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': f'บันทึกไม่สำเร็จ: {str(error)[:140]}'}).split('=',1)[1]}",
            status_code=303,
        )
    except Exception as error:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': f'เกิดข้อผิดพลาด: {str(error)[:140]}'}).split('=',1)[1]}",
            status_code=303,
        )

    if profile_action == "reset_nickname":
        success_notice = "รีเซ็ตชื่อเล่นบอทกลับค่าเดิมแล้ว"
        audit_text = "รีเซ็ตชื่อเล่นบอทกลับค่าเดิมแล้ว"
    elif profile_action == "reset_avatar":
        success_notice = "รีเซ็ตรูปโปรไฟล์บอทเฉพาะกิลด์แล้ว"
        audit_text = "รีเซ็ตรูปโปรไฟล์บอทเฉพาะกิลด์แล้ว"
    else:
        success_notice = "อัปเดตโปรไฟล์บอทสำหรับเซิร์ฟเวอร์นี้แล้ว"
        audit_text = "อัปเดตการตั้งค่าโปรไฟล์บอทแล้ว"

    await _append_dashboard_audit_event(guild_id, session, audit_text, target="server_settings")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/server_settings?notice={urlencode({'notice': success_notice}).split('=',1)[1]}",
        status_code=303,
    )

async def update_security_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)
    dashboard_access = _dashboard_access_payload_from_state(state)
    redirect_tab = (data.get("redirect_tab") or "security").strip().lower()
    if redirect_tab not in {"security", "server_settings", "automation", "anti_raid", "extra_protection"}:
        redirect_tab = "security"
    redirect_path = f"/dashboard/guild/{guild_id}/{redirect_tab}"
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(state.get("guild") or {})
    guild_state_for_plan["subscription"] = plan_tier
    security_action = str(data.get("security_action") or "").strip().lower()
    if security_action == "dashboard_editor_roles":
        if not bool(dashboard_access.get("effective_is_owner")):
            return RedirectResponse(
                f"{redirect_path}?notice={urlencode({'notice': 'เฉพาะเจ้าของกิลด์เท่านั้นที่ตั้งค่ายศผู้ดูแลแดชบอร์ดได้'}).split('=',1)[1]}",
                status_code=303,
            )
        editor_role_ids = _normalize_dashboard_editor_role_ids(data.get("dashboard_editor_role_ids"))
        await _set_dashboard_config_value(
            _dashboard_editor_roles_config_key(guild_id),
            json.dumps(editor_role_ids, ensure_ascii=False, separators=(",", ":")),
        )
        await _append_dashboard_audit_event(
            guild_id,
            session,
            "อัปเดตยศผู้ดูแลแดชบอร์ดแล้ว",
            target="server_settings",
        )
        return RedirectResponse(
            f"{redirect_path}?notice={urlencode({'notice': 'บันทึกยศผู้ดูแลแดชบอร์ดแล้ว'}).split('=',1)[1]}",
            status_code=303,
        )
    if security_action == "delast_access_users":
        if not bool(dashboard_access.get("effective_is_owner")):
            return RedirectResponse(
                f"{redirect_path}?notice={urlencode({'notice': 'เฉพาะเจ้าของกิลด์เท่านั้นที่ตั้งค่าผู้ใช้คำสั่งลบข้อความได้'}).split('=',1)[1]}",
                status_code=303,
            )
        raw_allowed_value = data.get("delast_access_user_ids") or ""
        if isinstance(raw_allowed_value, (list, tuple, set)):
            candidates = [str(item or "").strip() for item in raw_allowed_value]
        else:
            candidates = (
                str(raw_allowed_value or "")
                .replace("\r", "\n")
                .replace(",", "\n")
                .split("\n")
            )
        allowed_user_ids: list[str] = []
        for item in candidates:
            user_id = str(item or "").strip()
            if not user_id.isdigit():
                continue
            if user_id in allowed_user_ids:
                continue
            allowed_user_ids.append(user_id)

        command_access_state = state.get("command_access") or {}
        command_access_id = command_access_state.get("id")
        if not command_access_id:
            existing = await storage.command_access.get(guild_id=guild_id)
            if not existing:
                existing = await storage.command_access.insert(
                    guild_id=guild_id,
                    disabled_commands=[],
                    delast_access_user_ids=allowed_user_ids,
                )
            command_access_id = existing.get("id")
        if not command_access_id:
            return RedirectResponse(
                f"{redirect_path}?notice={urlencode({'notice': 'ไม่สามารถบันทึกสิทธิ์คำสั่งลบข้อความได้ในขณะนี้'}).split('=',1)[1]}",
                status_code=303,
            )
        await storage.command_access.update(
            id=command_access_id,
            delast_access_user_ids=allowed_user_ids,
        )
        await _append_dashboard_audit_event(
            guild_id,
            session,
            "อัปเดตรายชื่อผู้ใช้คำสั่งลบข้อความแล้ว",
            target="server_settings",
        )
        return RedirectResponse(
            f"{redirect_path}?notice={urlencode({'notice': 'บันทึกรายชื่อผู้ใช้คำสั่งลบข้อความแล้ว'}).split('=',1)[1]}",
            status_code=303,
        )
    if security_action == "extra_protection_save":
        required_tier = _required_plan_for_dashboard_tab("extra_protection")
        if required_tier and not _is_plan_at_least(plan_tier, required_tier):
            return RedirectResponse(
                f"{redirect_path}?notice={urlencode({'notice': f'แท็บ Extra Protection ต้องใช้แพ็กเกจ {required_tier.title()} ขึ้นไป'}).split('=',1)[1]}",
                status_code=303,
            )

        current_extra = state.get("extra_protection") or _default_extra_protection_settings()

        def _parse_id_values(raw_value: Any) -> list[str]:
            if isinstance(raw_value, (list, tuple, set)):
                candidates = [str(item or "").strip() for item in raw_value]
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
                        candidates = [str(item or "").strip() for item in decoded]
                    else:
                        candidates = [
                            str(item or "").strip()
                            for item in re.split(r"[\s,\n\r]+", text_value)
                        ]
            values: list[str] = []
            for item in candidates:
                if item.isdigit() and item not in values:
                    values.append(item)
            return values

        def _merge_id_sets(
            *,
            baseline: Any,
            replacement: Any,
            add_values: Any,
            remove_values: Any,
        ) -> list[str]:
            base_items = _parse_id_values(replacement)
            if not base_items:
                base_items = _parse_id_values(baseline)
            for value in _parse_id_values(add_values):
                if value not in base_items:
                    base_items.append(value)
            remove_items = set(_parse_id_values(remove_values))
            return [value for value in base_items if value not in remove_items]

        whitelist_user_ids = _merge_id_sets(
            baseline=current_extra.get("bot_add_whitelist_user_ids", []),
            replacement=data.get("xp_whitelist_user_ids_text"),
            add_values=data.get("xp_whitelist_user_add"),
            remove_values=data.get("xp_whitelist_user_remove"),
        )
        whitelist_bot_ids = _merge_id_sets(
            baseline=current_extra.get("bot_add_whitelist_bot_ids", []),
            replacement=data.get("xp_whitelist_bot_ids_text"),
            add_values=data.get("xp_whitelist_bot_add"),
            remove_values=data.get("xp_whitelist_bot_remove"),
        )

        delete_action = str(
            _posted_form_value(data, "xp_delete_action", current_extra.get("delete_action") or "warn")
            or ""
        ).strip().lower()
        if delete_action not in {"none", "warn", "mute", "kick", "ban"}:
            delete_action = "warn"

        detect_nsfw_image_enabled = bool(current_extra.get("detect_nsfw_image_enabled"))
        if "xp_detect_nsfw_image_enabled" in data:
            detect_nsfw_image_enabled = _bool_from_form(data, "xp_detect_nsfw_image_enabled")
        detect_nsfw_image_mode = str(
            _posted_form_value(
                data,
                "xp_detect_nsfw_image_mode",
                current_extra.get("detect_nsfw_image_mode") or "allowlist_only",
            )
            or ""
        ).strip().lower()
        if detect_nsfw_image_mode not in {"allowlist_only", "all_except_allowlist"}:
            detect_nsfw_image_mode = "allowlist_only"
        try:
            detect_nsfw_image_threshold = float(
                str(
                    data.get("xp_detect_nsfw_image_threshold")
                    if "xp_detect_nsfw_image_threshold" in data
                    else current_extra.get("detect_nsfw_image_threshold", 0.72)
                ).strip()
            )
        except Exception:
            detect_nsfw_image_threshold = 0.72
        detect_nsfw_image_threshold = max(0.05, min(0.995, detect_nsfw_image_threshold))

        candidate_payload = {
            "enabled": _bool_from_form(data, "xp_enabled"),
            "block_bot_add_enabled": _bool_from_form(data, "xp_block_bot_add_enabled"),
            "bot_add_whitelist_user_ids": whitelist_user_ids,
            "bot_add_whitelist_bot_ids": whitelist_bot_ids,
            "anti_spam_enabled": _bool_from_form(data, "xp_anti_spam_enabled"),
            "spam_message_limit": _int_from_form(data, "xp_spam_message_limit", 7, 3, 30),
            "spam_window_seconds": _int_from_form(data, "xp_spam_window_seconds", 12, 3, 180),
            "anti_mass_mention_enabled": _bool_from_form(data, "xp_anti_mass_mention_enabled"),
            "mass_mention_limit": _int_from_form(data, "xp_mass_mention_limit", 5, 2, 30),
            "delete_discord_invite_enabled": _bool_from_form(data, "xp_delete_discord_invite_enabled"),
            "delete_scam_links_enabled": _bool_from_form(data, "xp_delete_scam_links_enabled"),
            "anti_virus_keywords_enabled": _bool_from_form(data, "xp_anti_virus_keywords_enabled"),
            "custom_virus_keywords": str(data.get("xp_custom_virus_keywords") or ""),
            "detect_nsfw_image_enabled": detect_nsfw_image_enabled,
            "detect_nsfw_image_mode": detect_nsfw_image_mode,
            "detect_nsfw_image_threshold": detect_nsfw_image_threshold,
            "delete_action": delete_action,
            "timeout_seconds": _int_from_form(data, "xp_timeout_seconds", 300, 30, 86400),
        }
        normalized = _normalize_extra_protection_settings(candidate_payload)
        previous_block_enabled = bool(current_extra.get("enabled")) and bool(current_extra.get("block_bot_add_enabled"))
        next_block_enabled = bool(normalized.get("enabled")) and bool(normalized.get("block_bot_add_enabled"))
        try:
            previous_armed_at_ts = max(
                0,
                int(float(str(current_extra.get("block_bot_add_armed_at_ts", 0)).strip() or "0")),
            )
        except Exception:
            previous_armed_at_ts = 0
        if next_block_enabled:
            if not previous_block_enabled:
                normalized["block_bot_add_armed_at_ts"] = int(time.time())
            elif previous_armed_at_ts > 0:
                normalized["block_bot_add_armed_at_ts"] = previous_armed_at_ts
            elif int(normalized.get("block_bot_add_armed_at_ts", 0) or 0) <= 0:
                normalized["block_bot_add_armed_at_ts"] = int(time.time())
        else:
            normalized["block_bot_add_armed_at_ts"] = 0
        await _set_dashboard_config_value(
            _extra_protection_config_key(guild_id),
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
        )
        await _append_dashboard_audit_event(
            guild_id,
            session,
            "อัปเดตการตั้งค่า Extra Protection แล้ว",
            target="extra_protection",
        )
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/extra_protection?notice={urlencode({'notice': 'บันทึกการตั้งค่า Extra Protection แล้ว'}).split('=',1)[1]}",
            status_code=303,
        )
    requested_type = (data.get("type") or "normal").lower()
    if requested_type == "extream":
        requested_type = "extreme"
    if requested_type not in {"normal", "extreme", "custom"}:
        requested_type = "normal"
    if requested_type == "custom" and not _can_use_antinuke_custom(guild_state_for_plan):
        message = "แพ็กเกจฟรียังไม่สามารถตั้งค่า Anti-Nuke แบบกำหนดเองได้"
        return RedirectResponse(
            f"{redirect_path}?notice={urlencode({'notice': message}).split('=',1)[1]}",
            status_code=303,
        )
    antinuke = state.get("antinuke")
    if not antinuke:
        antinuke = await storage.antinuke_settings.get(guild_id=guild_id)
        if not antinuke:
            await storage.antinuke_settings.insert(guild_id=guild_id)
            antinuke = await storage.antinuke_settings.get(guild_id=guild_id)

    allowed_antinuke_punishments = _allowed_antinuke_punishments(guild_state_for_plan)
    def _safe_antinuke_punishment(key: str, default: str = "kick") -> str:
        value = (data.get(key) or default).lower()
        if value not in allowed_antinuke_punishments:
            return "mute" if "mute" in allowed_antinuke_punishments else sorted(allowed_antinuke_punishments)[0]
        return value

    raw_bypass_roles = (data.get("bypass_role_ids") or data.get("bypass_role_id") or "").strip()
    bypass_role_ids = []
    for role_id in raw_bypass_roles.split(","):
        role_id = role_id.strip()
        if role_id.isdigit() and role_id not in bypass_role_ids:
            bypass_role_ids.append(role_id)
    bypass_role_value = ",".join(bypass_role_ids) if bypass_role_ids else None

    if requested_type in ("normal", "extreme"):
        await storage.antinuke_settings.change_antinuke_settings_type(antinuke, requested_type)

    await storage.antinuke_settings.update(
        id=antinuke["id"],
        enabled=_bool_from_form(data, "enabled"),
        type=requested_type,
        bypass_role_id=bypass_role_value,
        anti_bot_add=_bool_from_form(data, "anti_bot_add"),
        anti_bot_add_limit=_int_from_form(data, "anti_bot_add_limit", 1, 1, 20),
        anti_bot_add_punishment=_safe_antinuke_punishment("anti_bot_add_punishment", "kick"),
        anti_channel_delete=_bool_from_form(data, "anti_channel_delete"),
        anti_channel_delete_limit=_int_from_form(data, "anti_channel_delete_limit", 1, 1, 20),
        anti_channel_delete_punishment=_safe_antinuke_punishment("anti_channel_delete_punishment", "kick"),
        anti_role_delete=_bool_from_form(data, "anti_role_delete"),
        anti_role_delete_limit=_int_from_form(data, "anti_role_delete_limit", 1, 1, 20),
        anti_role_delete_punishment=_safe_antinuke_punishment("anti_role_delete_punishment", "kick"),
        anti_webhook_create=_bool_from_form(data, "anti_webhook_create"),
        anti_webhook_create_limit=_int_from_form(data, "anti_webhook_create_limit", 1, 1, 20),
        anti_webhook_create_punishment=_safe_antinuke_punishment("anti_webhook_create_punishment", "kick"),
        anti_everyone_mention=_bool_from_form(data, "anti_everyone_mention"),
        anti_everyone_mention_limit=_int_from_form(data, "anti_everyone_mention_limit", 1, 1, 20),
        anti_everyone_mention_punishment=_safe_antinuke_punishment("anti_everyone_mention_punishment", "kick"),
    )

    current_honeypot = _normalize_honeypot_settings(
        state.get("honeypot") or _default_honeypot_settings()
    )
    next_honeypot = dict(current_honeypot)
    can_use_honeypot = _is_plan_at_least(plan_tier, "golden")
    if can_use_honeypot:
        raw_channel_id = str(data.get("honeypot_channel_id") or "").strip()
        if raw_channel_id.startswith("<#") and raw_channel_id.endswith(">"):
            raw_channel_id = raw_channel_id[2:-1].strip()
        if not raw_channel_id.isdigit():
            raw_channel_id = ""
        timeout_days = _int_from_form(data, "honeypot_timeout_days", 7, 1, 28)
        cooldown_minutes = _int_from_form(data, "honeypot_edit_cooldown_minutes", 2, 2, 5)
        next_honeypot.update(
            {
                "enabled": _bool_from_form(data, "honeypot_enabled") and bool(raw_channel_id),
                "channel_id": raw_channel_id,
                "timeout_seconds": int(timeout_days) * 86400,
                "delete_message": _bool_from_form(data, "honeypot_delete_message"),
                "status_edit_cooldown_seconds": int(cooldown_minutes) * 60,
            }
        )
    else:
        next_honeypot["enabled"] = False

    normalized_honeypot = _normalize_honeypot_settings(next_honeypot)
    await _set_dashboard_config_value(
        _honeypot_config_key(guild_id),
        json.dumps(normalized_honeypot, ensure_ascii=False, separators=(",", ":")),
    )

    cache.antinuke_settings[str(guild_id)] = await storage.antinuke_settings.get(guild_id=guild_id)
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าความปลอดภัยแล้ว", target=redirect_tab)
    return RedirectResponse(f"{redirect_path}?notice={urlencode({'notice': 'บันทึกการตั้งค่าความปลอดภัยแล้ว'}).split('=',1)[1]}", status_code=303)

async def update_moderation_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)
    redirect_tab = (data.get("redirect_tab") or "moderation").strip().lower()
    if redirect_tab not in {"moderation", "screening", "automation"}:
        redirect_tab = "moderation"
    redirect_path = f"/dashboard/guild/{guild_id}/{redirect_tab}"
    requested_mode = (data.get("mode") or "normal").lower()
    if requested_mode not in {"normal", "extreme", "custom", "diamond"}:
        requested_mode = "normal"

    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state = state.get("guild") or {}
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    can_use_custom = _can_use_automod_custom(guild_state_for_plan)
    can_use_diamond = _can_use_automod_diamond(guild_state_for_plan)

    if requested_mode == "custom" and not can_use_custom:
        message = "แพ็กเกจฟรียังไม่สามารถใช้โหมด AutoMod แบบกำหนดเองได้"
        return RedirectResponse(
            f"{redirect_path}?notice={urlencode({'notice': message}).split('=',1)[1]}",
            status_code=303,
        )
    if requested_mode == "diamond" and not can_use_diamond:
        message = "โหมด AutoMod Diamond ใช้ได้เฉพาะแพ็กเกจ Diamond"
        return RedirectResponse(
            f"{redirect_path}?notice={urlencode({'notice': message}).split('=',1)[1]}",
            status_code=303,
        )

    automod = state.get("automod")
    if not automod:
        automod = await storage.automod.get(guild_id=guild_id)
        if not automod:
            await storage.automod.insert(guild_id=guild_id)
            automod = await storage.automod.get(guild_id=guild_id)

    if requested_mode in ("normal", "extreme", "diamond"):
        await storage.automod.change_automod_settings_type(automod, requested_mode)
        await storage.automod.update(
            id=automod["id"],
            mode=requested_mode,
        )
    else:
        badwords = [word.strip() for word in (data.get("antibadwords_words") or "").split(",") if word.strip()]
        allowed_punishments = _allowed_automod_punishments(guild_state_for_plan)
        punishment = (data.get("antispam_punishment") or "mute").lower()
        if punishment not in allowed_punishments:
            punishment = "mute"
        antispam_interval = _int_from_form(
            data,
            "antispam_timeframe",
            _int_from_form(data, "antispam_max_interval", 30, 1, 120),
            1,
            300,
        )
        await storage.automod.update(
            id=automod["id"],
            mode=requested_mode,
            antilink_enabled=_bool_from_form(data, "antilink_enabled"),
            antispam_enabled=_bool_from_form(data, "antispam_enabled"),
            antibadwords_enabled=_bool_from_form(data, "antibadwords_enabled"),
            antispam_max_messages=_int_from_form(data, "antispam_max_messages", 10, 1, 50),
            antispam_max_interval=antispam_interval,
            antispam_max_mentions=_int_from_form(data, "antispam_max_mentions", 5, 1, 30),
            antispam_max_emojis=_int_from_form(data, "antispam_max_emojis", 10, 1, 50),
            antispam_max_caps=_int_from_form(data, "antispam_max_caps", 50, 1, 100),
            antispam_punishment=punishment,
            antispam_punishment_duration=_int_from_form(data, "antispam_punishment_duration", 10, 1, 1440),
            antibadwords_words=badwords,
        )

    cache.automod[str(guild_id)] = await storage.automod.get(guild_id=guild_id)
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าการดูแลแชตแล้ว", target=redirect_tab)
    return RedirectResponse(f"{redirect_path}?notice={urlencode({'notice': 'บันทึกการตั้งค่าการดูแลแชตแล้ว'}).split('=',1)[1]}", status_code=303)

async def update_screening_categories_settings(request: Request, guild_id: int):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="screening_categories",
    )
    if blocked_response:
        return blocked_response

    await _ensure_dashboard_config_cache()
    data = await _parse_form(request)
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    plan_cap = max(0, int(_screening_categories_plan_cap(plan_tier)))
    existing = _screening_categories_settings_from_db(guild_id)

    payload: dict[str, dict[str, Any]] = {}
    ordered_keys: list[str] = []

    for item in SCREENING_CATEGORY_ITEMS:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        ordered_keys.append(key)

        log_type = str(item.get("log_type") or "").strip().lower()
        required_tier = str(item.get("premium_tier") or "").strip().lower()
        locked = bool(required_tier) and not _is_plan_at_least(plan_tier, required_tier)
        previous = existing.get(key) or {}

        enabled = bool(data.get(f"sc_{key}_enabled")) and not locked
        channel_id = str(data.get(f"sc_{key}_channel_id") or "").strip()
        if not channel_id.isdigit():
            channel_id = str(previous.get("channel_id") or "").strip()
            if not channel_id.isdigit():
                channel_id = ""

        color_value = str(
            _posted_form_value(data, f"sc_{key}_color", previous.get("color") or "")
            or ""
        ).strip()
        fallback_color = SCREENING_CATEGORY_DEFAULT_COLORS.get(log_type, "#6b8cff")
        if not re.match(r"^#[0-9A-Fa-f]{6}$", color_value):
            color_value = fallback_color

        payload[key] = {
            "enabled": enabled,
            "channel_id": channel_id,
            "color": color_value,
            "log_type": log_type,
        }

    enabled_keys = [key for key in ordered_keys if bool((payload.get(key) or {}).get("enabled"))]
    trimmed_count = 0
    if len(enabled_keys) > plan_cap:
        trimmed_count = len(enabled_keys) - plan_cap
        for key in enabled_keys[plan_cap:]:
            row = payload.get(key)
            if isinstance(row, dict):
                row["enabled"] = False

    await _set_dashboard_config_value(
        _screening_categories_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )

    await _append_dashboard_audit_event(
        guild_id,
        session,
        "Updated screening categories settings.",
        target="screening_categories",
    )

    notice_message = "Saved screening categories settings."
    if trimmed_count > 0:
        notice_message = (
            f"Saved with plan limit: max {plan_cap} enabled categories. "
            f"Disabled {trimmed_count} extra categories."
        )

    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/screening_categories?notice={urlencode({'notice': notice_message}).split('=',1)[1]}",
        status_code=303,
    )

async def update_color_sets_settings(request: Request, guild_id: int):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="colors",
    )
    if blocked_response:
        return blocked_response

    await _ensure_dashboard_config_cache()
    form = await request.form()
    data = {
        key: str(value)
        for key, value in form.items()
        if key
        not in {
            "embed_author_icon_file",
            "embed_thumbnail_file",
            "embed_image_file",
            "embed_footer_icon_file",
            "background_image_file",
        }
    }
    upload_map = {
        "embed_author_icon_file": "embed_author_icon_url",
        "embed_thumbnail_file": "embed_thumbnail_url",
        "embed_image_file": "embed_image_url",
        "embed_footer_icon_file": "embed_footer_icon_url",
        "background_image_file": "background_image_url",
    }
    upload_kind_map = {
        "embed_author_icon_file": "icon",
        "embed_thumbnail_file": "thumbnail",
        "embed_image_file": "image",
        "embed_footer_icon_file": "icon",
        "background_image_file": "banner",
    }
    for upload_key, data_key in upload_map.items():
        uploaded = form.get(upload_key)
        if not uploaded or not getattr(uploaded, "filename", None):
            continue
        try:
            raw_bytes = await uploaded.read()
            if not raw_bytes:
                continue
            uploaded_url = await _upload_image_to_discord_cdn(
                guild_id,
                raw_bytes=raw_bytes,
                filename=str(getattr(uploaded, "filename", "tempvoice.png")),
                upload_target="colors",
                asset_kind=upload_kind_map.get(upload_key),
                request=request,
                uploader_id=int(_session_user_id(session) or 0),
                source_route=str(getattr(request.url, "path", "") or ""),
                source_field=upload_key,
            )
            if uploaded_url:
                data[data_key] = uploaded_url
        except Exception:
            continue
    sets_payload: list[dict[str, Any]] = []
    try:
        decoded_sets = json.loads(data.get("sets_json", "[]"))
        if isinstance(decoded_sets, list):
            sets_payload = decoded_sets
    except Exception:
        sets_payload = []

    payload = _normalize_color_sets_settings(
        {
            "enabled": _bool_from_form(data, "enabled"),
            "command_color_enabled": _bool_from_form(data, "command_color_enabled"),
            "command_colors_enabled": _bool_from_form(data, "command_colors_enabled"),
            "applied_set_id": data.get("applied_set_id", ""),
            "list_name": data.get("list_name", ""),
            "shape_name": data.get("shape_name", ""),
            "background_style": data.get("background_style", ""),
            "background_image_url": data.get("background_image_url", ""),
            "sets": sets_payload,
        }
    )
    await _set_dashboard_config_value(
        _color_sets_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    color_action = str(data.get("color_action") or "save").strip().lower()
    notice_text = "บันทึกชุดสีแล้ว"
    audit_action = "อัปเดตชุดสีแล้ว"

    if color_action == "apply_set":
        selected_set_id = str(payload.get("applied_set_id") or "").strip()
        selected_set = None
        for row in payload.get("sets", []):
            if str((row or {}).get("id") or "").strip() == selected_set_id:
                selected_set = row
                break
        if not selected_set and payload.get("sets"):
            selected_set = payload["sets"][0]

        if not isinstance(selected_set, dict):
            notice_text = "ไม่พบชุดสีที่เลือก"
            audit_action = "ปรับใช้ชุดสีไม่สำเร็จ"
        else:
            bot = get_bot()
            bot_guild = bot.get_guild(guild_id) if bot else None
            ok, role_notice, _ = await _apply_color_set_roles_to_guild(bot_guild, selected_set)
            set_name = str(selected_set.get("name") or "ชุดสี").strip()
            notice_text = f"{role_notice} | ชุดสี: {set_name}"
            audit_action = f"ปรับใช้ชุดสีแล้ว: {set_name}" if ok else f"ปรับใช้ชุดสีไม่สำเร็จ: {set_name}"

    await _append_dashboard_audit_event(guild_id, session, audit_action, target="colors")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/colors?notice={urlencode({'notice': notice_text}).split('=',1)[1]}",
        status_code=303,
    )

async def apply_color_set_now(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"ok": False, "message": blocked_notice}, status_code=403)
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="colors")
    if tab_block_reason:
        return JSONResponse({"ok": False, "message": tab_block_reason}, status_code=403)

    await _ensure_dashboard_config_cache()
    form = await request.form()
    data = {
        key: str(value)
        for key, value in form.items()
        if key
        not in {
            "embed_author_icon_file",
            "embed_thumbnail_file",
            "embed_image_file",
            "embed_footer_icon_file",
            "background_image_file",
        }
    }
    upload_map = {
        "background_image_file": "background_image_url",
    }
    upload_kind_map = {
        "background_image_file": "banner",
    }
    for upload_key, data_key in upload_map.items():
        uploaded = form.get(upload_key)
        if not uploaded or not getattr(uploaded, "filename", None):
            continue
        try:
            raw_bytes = await uploaded.read()
            if not raw_bytes:
                continue
            uploaded_url = await _upload_image_to_discord_cdn(
                guild_id,
                raw_bytes=raw_bytes,
                filename=str(getattr(uploaded, "filename", "tempvoice.png")),
                upload_target="colors",
                asset_kind=upload_kind_map.get(upload_key),
                request=request,
                uploader_id=int(_session_user_id(session) or 0),
                source_route=str(getattr(request.url, "path", "") or ""),
                source_field=upload_key,
            )
            if uploaded_url:
                data[data_key] = uploaded_url
        except Exception:
            continue
    sets_payload: list[dict[str, Any]] = []
    try:
        decoded_sets = json.loads(data.get("sets_json", "[]"))
        if isinstance(decoded_sets, list):
            sets_payload = decoded_sets
    except Exception:
        sets_payload = []

    payload = _normalize_color_sets_settings(
        {
            "enabled": _bool_from_form(data, "enabled"),
            "command_color_enabled": _bool_from_form(data, "command_color_enabled"),
            "command_colors_enabled": _bool_from_form(data, "command_colors_enabled"),
            "applied_set_id": data.get("applied_set_id", ""),
            "list_name": data.get("list_name", ""),
            "shape_name": data.get("shape_name", ""),
            "background_style": data.get("background_style", ""),
            "background_image_url": data.get("background_image_url", ""),
            "sets": sets_payload,
        }
    )
    await _set_dashboard_config_value(
        _color_sets_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    color_action = str(data.get("color_action") or "apply_set").strip().lower()
    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None

    if color_action in {"delete_role", "delete_all_roles"}:
        if bot_guild is None:
            return JSONResponse({"ok": False, "message": "บอทยังไม่อยู่ในเซิร์ฟเวอร์", "roles": []}, status_code=400)
        me = bot_guild.me
        if me is None:
            return JSONResponse({"ok": False, "message": "ไม่พบบัญชีบอทในเซิร์ฟเวอร์", "roles": _collect_color_roles_for_ui(bot_guild)}, status_code=400)
        if not me.guild_permissions.manage_roles:
            return JSONResponse({"ok": False, "message": "บอทยังไม่มีสิทธิ์ Manage Roles", "roles": _collect_color_roles_for_ui(bot_guild)}, status_code=400)

        if color_action == "delete_role":
            target_role_id_raw = str(data.get("target_role_id") or "").strip()
            if not target_role_id_raw.isdigit():
                return JSONResponse(
                    {"ok": False, "message": "ไม่พบบทบาทสีที่ต้องการลบ", "roles": _collect_color_roles_for_ui(bot_guild)},
                    status_code=400,
                )
            target_role = bot_guild.get_role(int(target_role_id_raw))
            target_role_name = str(getattr(target_role, "name", "") or "").strip() if target_role else ""
            if target_role is None or target_role.is_default() or not target_role_name.isdigit():
                return JSONResponse(
                    {"ok": False, "message": "ไม่พบบทบาทสีที่ต้องการลบ", "roles": _collect_color_roles_for_ui(bot_guild)},
                    status_code=400,
                )
            if target_role.managed or me.top_role <= target_role:
                return JSONResponse(
                    {
                        "ok": False,
                        "message": "บอทไม่สามารถลบบทบาทนี้ได้ (ลำดับบทบาทไม่พอหรือเป็นบทบาทระบบ)",
                        "roles": _collect_color_roles_for_ui(bot_guild),
                    },
                    status_code=400,
                )
            try:
                await target_role.delete(reason="Dashboard Colors: delete one color role")
            except Exception:
                return JSONResponse(
                    {"ok": False, "message": "ลบบทบาทสีไม่สำเร็จ", "roles": _collect_color_roles_for_ui(bot_guild)},
                    status_code=500,
                )

            await _append_dashboard_audit_event(
                guild_id,
                session,
                f"ลบบทบาทสีแล้ว: {target_role_name}",
                target="colors",
            )
            return JSONResponse(
                {
                    "ok": True,
                    "message": f"ลบบทบาทสีแล้ว: {target_role_name}",
                    "roles": _collect_color_roles_for_ui(bot_guild),
                    "deleted_role_ids": [target_role_id_raw],
                }
            )

        color_roles_rows = _collect_color_roles_for_ui(bot_guild)
        removed = 0
        skipped = 0
        failed = 0
        deleted_role_ids: list[str] = []
        for role_row in color_roles_rows:
            role_id_raw = str((role_row or {}).get("id") or "").strip()
            if not role_id_raw.isdigit():
                continue
            target_role = bot_guild.get_role(int(role_id_raw))
            if target_role is None:
                skipped += 1
                continue
            if target_role.managed or me.top_role <= target_role:
                skipped += 1
                continue
            try:
                await target_role.delete(reason="Dashboard Colors: delete all color roles")
                removed += 1
                deleted_role_ids.append(role_id_raw)
            except Exception:
                failed += 1

        ok = failed == 0
        summary = f"ลบ {removed} | ข้าม {skipped} | ล้มเหลว {failed}"
        message = (
            f"ลบบทบาทสีสำเร็จ ({summary})"
            if ok
            else f"ลบบทบาทสีบางส่วนไม่สำเร็จ ({summary})"
        )
        audit_action = (
            f"ลบบทบาทสีทั้งหมดแล้ว ({summary})"
            if ok
            else f"ลบบทบาทสีทั้งหมดบางส่วนไม่สำเร็จ ({summary})"
        )
        await _append_dashboard_audit_event(guild_id, session, audit_action, target="colors")
        return JSONResponse(
            {
                "ok": ok,
                "message": message,
                "roles": _collect_color_roles_for_ui(bot_guild),
                "deleted_role_ids": deleted_role_ids,
            }
        )

    selected_set_id = str(payload.get("applied_set_id") or "").strip()
    selected_set = None
    for row in payload.get("sets", []):
        if str((row or {}).get("id") or "").strip() == selected_set_id:
            selected_set = row
            break
    if not selected_set and payload.get("sets"):
        selected_set = payload["sets"][0]
        selected_set_id = str((selected_set or {}).get("id") or "").strip()

    if not isinstance(selected_set, dict):
        await _append_dashboard_audit_event(guild_id, session, "ปรับใช้ชุดสีไม่สำเร็จ", target="colors")
        return JSONResponse({"ok": False, "message": "ไม่พบชุดสีที่เลือก", "roles": []}, status_code=400)

    ok, role_notice, created_role_ids = await _apply_color_set_roles_to_guild(bot_guild, selected_set)
    set_name = str(selected_set.get("name") or "ชุดสี").strip()
    message = f"{role_notice} | ชุดสี: {set_name}"
    audit_action = f"ปรับใช้ชุดสีแล้ว: {set_name}" if ok else f"ปรับใช้ชุดสีไม่สำเร็จ: {set_name}"
    await _append_dashboard_audit_event(guild_id, session, audit_action, target="colors")

    roles_payload = _collect_color_roles_for_ui(bot_guild)
    return JSONResponse(
        {
            "ok": ok,
            "message": message,
            "roles": roles_payload,
            "highlight_role_ids": created_role_ids,
            "applied_set_id": selected_set_id,
            "applied_set_name": set_name,
            "background_image_url": str(payload.get("background_image_url") or "").strip(),
        }
    )

async def update_levels_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="levels",
    )
    if blocked_response:
        return blocked_response

    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    caps = _levels_plan_caps(plan_tier)
    if not bool(caps.get("can_use")):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/levels?notice={urlencode({'notice': 'แพ็กเกจ Free ยังไม่สามารถใช้ระบบเลเวลได้'}).split('=',1)[1]}",
            status_code=303,
        )

    await _ensure_dashboard_config_cache()
    data = await _parse_form(request)
    action = str(data.get("action") or "save").strip().lower()

    def _levels_redirect(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/levels?notice={urlencode({'notice': message}).split('=',1)[1]}",
            status_code=303,
        )

    if action == "reset_user":
        target_user_id_raw = str(data.get("reset_target_user_id") or "").strip()
        if not target_user_id_raw.isdigit():
            return _levels_redirect("กรุณาเลือกสมาชิกที่ต้องการรีเซ็ตเลเวล")
        target_user_id = int(target_user_id_raw)
        deleted_rows = await storage.levels_users.delete(guild_id=guild_id, user_id=target_user_id)
        target_label = target_user_id_raw
        try:
            bot = get_bot()
            bot_guild = bot.get_guild(guild_id) if bot else None
            member = bot_guild.get_member(target_user_id) if bot_guild else None
            if member:
                target_label = member.display_name
        except Exception:
            pass
        if deleted_rows:
            await _append_dashboard_audit_event(
                guild_id,
                session,
                f"รีเซ็ตเลเวลสมาชิกแล้ว: {target_label}",
                target="levels",
            )
            return _levels_redirect(f"รีเซ็ตเลเวลของ {target_label} แล้ว")
        return _levels_redirect(f"ไม่พบข้อมูลเลเวลของ {target_label}")

    if action == "reset_all":
        deleted_rows = await storage.levels_users.delete(guild_id=guild_id)
        deleted_count = len(deleted_rows or [])
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"รีเซ็ตเลเวลสมาชิกทั้งหมดแล้ว ({deleted_count} คน)",
            target="levels",
        )
        return _levels_redirect(f"รีเซ็ตเลเวลสมาชิกทั้งหมดแล้ว ({deleted_count} คน)")

    reward_roles: list[dict[str, Any]] = []
    max_rewards = int(caps.get("max_rewards") or 0)
    for index in range(max_rewards):
        role_id = str(data.get(f"reward_role_id_{index}") or "").strip()
        level_raw = data.get(f"reward_level_{index}")
        if not role_id.isdigit():
            continue
        level_value = _int_from_form(data, f"reward_level_{index}", (index + 1) * 10, 1, 1000)
        reward_roles.append(
            {
                "id": f"reward_{index+1}_{uuid.uuid4().hex[:8]}",
                "level": level_value,
                "role_id": role_id,
            }
        )

    # Prevent duplicate role entries while preserving sort by level.
    seen_role_ids: set[str] = set()
    normalized_rewards: list[dict[str, Any]] = []
    for row in sorted(reward_roles, key=lambda item: int(item.get("level") or 0)):
        rid = str(row.get("role_id") or "")
        if rid in seen_role_ids:
            continue
        seen_role_ids.add(rid)
        normalized_rewards.append(row)

    source_payload = {
        "text": bool(caps.get("text_xp")) and _bool_from_form(data, "source_text"),
        "voice": bool(caps.get("voice_xp")) and _bool_from_form(data, "source_voice"),
        "command": bool(caps.get("command_xp")) and _bool_from_form(data, "source_command"),
        "reaction": bool(caps.get("reaction_xp")) and _bool_from_form(data, "source_reaction"),
    }
    notify_send_text = _bool_from_form(data, "notify_send_text")
    notify_send_embed = _bool_from_form(data, "notify_send_embed")
    notify_send_image = _bool_from_form(data, "notify_send_image")
    if not (notify_send_text or notify_send_embed or notify_send_image):
        notify_send_text = True
    payload = _normalize_levels_settings(
        {
            "enabled": _bool_from_form(data, "enabled"),
            "notify_channel_id": data.get("notify_channel_id", ""),
            "notify_message": data.get("notify_message", ""),
            "notify_send_text": notify_send_text,
            "notify_send_embed": notify_send_embed,
            "notify_send_image": notify_send_image,
            "notify_embed_title": (data.get("notify_embed_title") or "").strip(),
            "notify_embed_description": (data.get("notify_embed_description") or "").strip(),
            "notify_image_theme": (data.get("notify_image_theme") or "").strip(),
            "notify_image_theme_url": (data.get("notify_image_theme_url") or "").strip(),
            "notify_image_layout_mode": (data.get("notify_image_layout_mode") or "").strip(),
            "notify_image_avatar_position": (data.get("notify_image_avatar_position") or "").strip(),
            "notify_image_text_align": (data.get("notify_image_text_align") or "").strip(),
            "notify_image_font_style": (data.get("notify_image_font_style") or "").strip(),
            "notify_image_top_text": (data.get("notify_image_top_text") or "").strip(),
            "notify_image_bottom_text": (data.get("notify_image_bottom_text") or "").strip(),
            "max_level": _int_from_form(data, "max_level", 120, 5, int(caps.get("max_level") or 120)),
            "sources": source_payload,
            "text_xp_min": _int_from_form(data, "text_xp_min", 8, 0, 300),
            "text_xp_max": _int_from_form(data, "text_xp_max", 14, 0, 600),
            "text_cooldown": _int_from_form(data, "text_cooldown", 45, 0, 3600),
            "voice_xp_gain": _int_from_form(data, "voice_xp_gain", 6, 0, 200),
            "voice_cooldown": _int_from_form(data, "voice_cooldown", 300, 10, 3600),
            "command_xp_gain": _int_from_form(data, "command_xp_gain", 5, 0, 300),
            "command_cooldown": _int_from_form(data, "command_cooldown", 120, 10, 3600),
            "reaction_xp_gain": _int_from_form(data, "reaction_xp_gain", 2, 0, 100),
            "reaction_cooldown": _int_from_form(data, "reaction_cooldown", 90, 5, 3600),
            "reward_roles": normalized_rewards,
            "stack_reward_roles": _bool_from_form(data, "stack_reward_roles"),
        }
    )
    payload["enabled"] = bool(payload.get("enabled")) and any(bool(payload.get("sources", {}).get(k)) for k in ("text", "voice", "command", "reaction"))

    await _set_dashboard_config_value(
        _levels_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าระบบเลเวลแล้ว", target="levels")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/levels?notice={urlencode({'notice': 'บันทึกการตั้งค่าระบบเลเวลแล้ว'}).split('=',1)[1]}",
        status_code=303,
    )

async def update_economy_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="economy",
    )
    if blocked_response:
        return blocked_response

    data = await _parse_form(request)
    role_income_rows: list[dict[str, Any]] = []
    for index in range(12):
        role_id = str(data.get(f"role_income_role_{index}") or "").strip()
        if not role_id.isdigit():
            continue
        role_channel_id = str(data.get(f"role_income_channel_{index}") or "").strip()
        role_income_rows.append(
            {
                "role_id": role_id,
                "amount": _int_from_form(data, f"role_income_amount_{index}", 0, 0, 10_000_000),
                "cooldown": _int_from_form(data, f"role_income_cooldown_{index}", 3600, 10, 86400),
                "channel_id": role_channel_id if role_channel_id.isdigit() else "",
            }
        )

    chat_channel_values: list[str] = []
    chat_csv = str(data.get("chat_money_channels_csv") or "")
    for part in chat_csv.split(","):
        item = part.strip()
        if item.isdigit() and item not in chat_channel_values:
            chat_channel_values.append(item)
    cmd_channel_values: list[str] = []
    cmd_csv = str(data.get("economy_command_channels_csv") or "")
    for part in cmd_csv.split(","):
        item = part.strip()
        if item.isdigit() and item not in cmd_channel_values:
            cmd_channel_values.append(item)
    settings_payload = _normalize_economy_dashboard_settings(
        {
            "currency_symbol": data.get("currency_symbol", "coin"),
            "start_cash": _int_from_form(data, "start_cash", 0, 0, 1_000_000_000_000),
            "start_bank": _int_from_form(data, "start_bank", 0, 0, 1_000_000_000_000),
            "max_cash": _int_from_form(data, "max_cash", 1_000_000_000, 0, 1_000_000_000_000),
            "max_bank": _int_from_form(data, "max_bank", 1_000_000_000, 0, 1_000_000_000_000),
            "audit_channel_id": data.get("audit_channel_id", ""),
            "command_work_enabled": _bool_from_form(data, "command_work_enabled"),
            "command_slut_enabled": _bool_from_form(data, "command_slut_enabled"),
            "command_crime_enabled": _bool_from_form(data, "command_crime_enabled"),
            "command_rob_enabled": _bool_from_form(data, "command_rob_enabled"),
            "economy_channels_enabled": _bool_from_form(data, "economy_channels_enabled"),
            "economy_allow_all_channels": _bool_from_form(data, "economy_allow_all_channels"),
            "economy_command_channels": cmd_channel_values,
            "work_cooldown": _int_from_form(data, "work_cooldown", 3600, 10, 86400),
            "work_payout_min": _int_from_form(data, "work_payout_min", 100, 1, 10_000_000),
            "work_payout_max": _int_from_form(data, "work_payout_max", 300, 1, 10_000_000),
            "work_fail_rate": _int_from_form(data, "work_fail_rate", 0, 0, 100),
            "work_fine_type": data.get("work_fine_type", "fixed"),
            "work_fine_min": _int_from_form(data, "work_fine_min", 0, 0, 20_000_000),
            "work_fine_max": _int_from_form(data, "work_fine_max", 0, 0, 20_000_000),
            "slut_cooldown": _int_from_form(data, "slut_cooldown", 7200, 10, 86400),
            "slut_payout_min": _int_from_form(data, "slut_payout_min", 120, 1, 20_000_000),
            "slut_payout_max": _int_from_form(data, "slut_payout_max", 450, 1, 20_000_000),
            "crime_cooldown": _int_from_form(data, "crime_cooldown", 10800, 10, 86400),
            "crime_payout_min": _int_from_form(data, "crime_payout_min", 180, 1, 20_000_000),
            "crime_payout_max": _int_from_form(data, "crime_payout_max", 750, 1, 20_000_000),
            "rob_cooldown": _int_from_form(data, "rob_cooldown", 14400, 10, 86400),
            "rob_payout_min": _int_from_form(data, "rob_payout_min", 300, 1, 20_000_000),
            "rob_payout_max": _int_from_form(data, "rob_payout_max", 1200, 1, 20_000_000),
            "slut_fail_rate": _int_from_form(data, "slut_fail_rate", 35, 0, 100),
            "slut_fine_type": data.get("slut_fine_type", "fixed"),
            "slut_fine_min": _int_from_form(data, "slut_fine_min", 20, 0, 20_000_000),
            "slut_fine_max": _int_from_form(data, "slut_fine_max", 150, 0, 20_000_000),
            "crime_fail_rate": _int_from_form(data, "crime_fail_rate", 45, 0, 100),
            "crime_fine_type": data.get("crime_fine_type", "fixed"),
            "crime_fine_min": _int_from_form(data, "crime_fine_min", 35, 0, 20_000_000),
            "crime_fine_max": _int_from_form(data, "crime_fine_max", 260, 0, 20_000_000),
            "rob_fail_rate": _int_from_form(data, "rob_fail_rate", 60, 0, 100),
            "rob_fine_type": data.get("rob_fine_type", "percent"),
            "rob_fine_min": _int_from_form(data, "rob_fine_min", 5, 0, 100),
            "rob_fine_max": _int_from_form(data, "rob_fine_max", 25, 0, 100),
            "role_income_enabled": _bool_from_form(data, "role_income_enabled"),
            "role_income_entries": role_income_rows,
            "chat_money_enabled": _bool_from_form(data, "chat_money_enabled"),
            "chat_money_min": _int_from_form(data, "chat_money_min", 5, 0, 5000),
            "chat_money_max": _int_from_form(data, "chat_money_max", 15, 0, 5000),
            "chat_money_cooldown": _int_from_form(data, "chat_money_cooldown", 60, 5, 3600),
            "chat_money_channels": chat_channel_values,
            "items_enabled": _bool_from_form(data, "items_enabled"),
            "custom_replies_enabled": _bool_from_form(data, "custom_replies_enabled"),
            "store_sell_rate": _int_from_form(data, "store_sell_rate", 50, 0, 100),
            "inventory_max_items": _int_from_form(data, "inventory_max_items", 250, 1, 5000),
            "work_replies": [line.strip() for line in str(data.get("work_replies") or "").splitlines() if line.strip()],
            "slut_replies": [line.strip() for line in str(data.get("slut_replies") or "").splitlines() if line.strip()],
            "crime_replies": [line.strip() for line in str(data.get("crime_replies") or "").splitlines() if line.strip()],
            "rob_replies": [line.strip() for line in str(data.get("rob_replies") or "").splitlines() if line.strip()],
            "bet_min": _int_from_form(data, "bet_min", 10, 1, 100_000_000),
            "bet_max": _int_from_form(data, "bet_max", 100000, 1, 100_000_000),
        }
    )

    existing = state.get("economy_settings") if isinstance(state.get("economy_settings"), dict) else {}
    if not existing:
        existing = await storage.economy_settings.get(guild_id=guild_id) or {}
    if existing.get("id"):
        await storage.economy_settings.update(
            id=existing["id"],
            currency_symbol=settings_payload["currency_symbol"],
            start_cash=settings_payload["start_cash"],
            start_bank=settings_payload["start_bank"],
            max_cash=settings_payload["max_cash"],
            max_bank=settings_payload["max_bank"],
            audit_channel_id=int(settings_payload["audit_channel_id"]) if str(settings_payload["audit_channel_id"]).isdigit() else None,
            command_work_enabled=settings_payload["command_work_enabled"],
            command_slut_enabled=settings_payload["command_slut_enabled"],
            command_crime_enabled=settings_payload["command_crime_enabled"],
            command_rob_enabled=settings_payload["command_rob_enabled"],
            economy_channels_enabled=settings_payload["economy_channels_enabled"],
            economy_allow_all_channels=settings_payload["economy_allow_all_channels"],
            economy_command_channels=settings_payload["economy_command_channels"],
            work_cooldown=settings_payload["work_cooldown"],
            work_payout_min=settings_payload["work_payout_min"],
            work_payout_max=settings_payload["work_payout_max"],
            work_fail_rate=settings_payload["work_fail_rate"],
            work_fine_type=settings_payload["work_fine_type"],
            work_fine_min=settings_payload["work_fine_min"],
            work_fine_max=settings_payload["work_fine_max"],
            slut_cooldown=settings_payload["slut_cooldown"],
            slut_payout_min=settings_payload["slut_payout_min"],
            slut_payout_max=settings_payload["slut_payout_max"],
            crime_cooldown=settings_payload["crime_cooldown"],
            crime_payout_min=settings_payload["crime_payout_min"],
            crime_payout_max=settings_payload["crime_payout_max"],
            rob_cooldown=settings_payload["rob_cooldown"],
            rob_payout_min=settings_payload["rob_payout_min"],
            rob_payout_max=settings_payload["rob_payout_max"],
            slut_fail_rate=settings_payload["slut_fail_rate"],
            slut_fine_type=settings_payload["slut_fine_type"],
            slut_fine_min=settings_payload["slut_fine_min"],
            slut_fine_max=settings_payload["slut_fine_max"],
            crime_fail_rate=settings_payload["crime_fail_rate"],
            crime_fine_type=settings_payload["crime_fine_type"],
            crime_fine_min=settings_payload["crime_fine_min"],
            crime_fine_max=settings_payload["crime_fine_max"],
            rob_fail_rate=settings_payload["rob_fail_rate"],
            rob_fine_type=settings_payload["rob_fine_type"],
            rob_fine_min=settings_payload["rob_fine_min"],
            rob_fine_max=settings_payload["rob_fine_max"],
            role_income_enabled=settings_payload["role_income_enabled"],
            role_income_entries=settings_payload["role_income_entries"],
            chat_money_enabled=settings_payload["chat_money_enabled"],
            chat_money_min=settings_payload["chat_money_min"],
            chat_money_max=settings_payload["chat_money_max"],
            chat_money_cooldown=settings_payload["chat_money_cooldown"],
            chat_money_channels=settings_payload["chat_money_channels"],
            items_enabled=settings_payload["items_enabled"],
            custom_replies_enabled=settings_payload["custom_replies_enabled"],
            store_sell_rate=settings_payload["store_sell_rate"],
            inventory_max_items=settings_payload["inventory_max_items"],
            work_replies=settings_payload["work_replies"],
            slut_replies=settings_payload["slut_replies"],
            crime_replies=settings_payload["crime_replies"],
            rob_replies=settings_payload["rob_replies"],
            bet_min=settings_payload["bet_min"],
            bet_max=settings_payload["bet_max"],
            updated_at=datetime.datetime.now(tz=datetime.timezone.utc),
        )
    else:
        await storage.economy_settings.insert(
            guild_id=guild_id,
            currency_symbol=settings_payload["currency_symbol"],
            start_cash=settings_payload["start_cash"],
            start_bank=settings_payload["start_bank"],
            max_cash=settings_payload["max_cash"],
            max_bank=settings_payload["max_bank"],
            audit_channel_id=int(settings_payload["audit_channel_id"]) if str(settings_payload["audit_channel_id"]).isdigit() else None,
            command_work_enabled=settings_payload["command_work_enabled"],
            command_slut_enabled=settings_payload["command_slut_enabled"],
            command_crime_enabled=settings_payload["command_crime_enabled"],
            command_rob_enabled=settings_payload["command_rob_enabled"],
            economy_channels_enabled=settings_payload["economy_channels_enabled"],
            economy_allow_all_channels=settings_payload["economy_allow_all_channels"],
            economy_command_channels=settings_payload["economy_command_channels"],
            work_cooldown=settings_payload["work_cooldown"],
            work_payout_min=settings_payload["work_payout_min"],
            work_payout_max=settings_payload["work_payout_max"],
            work_fail_rate=settings_payload["work_fail_rate"],
            work_fine_type=settings_payload["work_fine_type"],
            work_fine_min=settings_payload["work_fine_min"],
            work_fine_max=settings_payload["work_fine_max"],
            slut_cooldown=settings_payload["slut_cooldown"],
            slut_payout_min=settings_payload["slut_payout_min"],
            slut_payout_max=settings_payload["slut_payout_max"],
            crime_cooldown=settings_payload["crime_cooldown"],
            crime_payout_min=settings_payload["crime_payout_min"],
            crime_payout_max=settings_payload["crime_payout_max"],
            rob_cooldown=settings_payload["rob_cooldown"],
            rob_payout_min=settings_payload["rob_payout_min"],
            rob_payout_max=settings_payload["rob_payout_max"],
            slut_fail_rate=settings_payload["slut_fail_rate"],
            slut_fine_type=settings_payload["slut_fine_type"],
            slut_fine_min=settings_payload["slut_fine_min"],
            slut_fine_max=settings_payload["slut_fine_max"],
            crime_fail_rate=settings_payload["crime_fail_rate"],
            crime_fine_type=settings_payload["crime_fine_type"],
            crime_fine_min=settings_payload["crime_fine_min"],
            crime_fine_max=settings_payload["crime_fine_max"],
            rob_fail_rate=settings_payload["rob_fail_rate"],
            rob_fine_type=settings_payload["rob_fine_type"],
            rob_fine_min=settings_payload["rob_fine_min"],
            rob_fine_max=settings_payload["rob_fine_max"],
            role_income_enabled=settings_payload["role_income_enabled"],
            role_income_entries=settings_payload["role_income_entries"],
            chat_money_enabled=settings_payload["chat_money_enabled"],
            chat_money_min=settings_payload["chat_money_min"],
            chat_money_max=settings_payload["chat_money_max"],
            chat_money_cooldown=settings_payload["chat_money_cooldown"],
            chat_money_channels=settings_payload["chat_money_channels"],
            items_enabled=settings_payload["items_enabled"],
            custom_replies_enabled=settings_payload["custom_replies_enabled"],
            store_sell_rate=settings_payload["store_sell_rate"],
            inventory_max_items=settings_payload["inventory_max_items"],
            work_replies=settings_payload["work_replies"],
            slut_replies=settings_payload["slut_replies"],
            crime_replies=settings_payload["crime_replies"],
            rob_replies=settings_payload["rob_replies"],
            bet_min=settings_payload["bet_min"],
            bet_max=settings_payload["bet_max"],
            updated_at=datetime.datetime.now(tz=datetime.timezone.utc),
        )

    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่า Economy แล้ว", target="economy")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/economy?notice={urlencode({'notice': 'บันทึกการตั้งค่า Economy แล้ว'}).split('=',1)[1]}",
        status_code=303,
    )

async def _handle_roleplay_guildstyle_studio_actions(
    *,
    guild_id: int,
    action: str,
    data: dict[str, str],
    form_data: Any | None,
    session: dict[str, Any] | None,
    permissions_row: dict[str, Any],
    normalized_permissions: dict[str, Any],
    actor_level: str,
    redirect_tab: str,
) -> RedirectResponse | None:
    normalized_action = str(action or "").strip().lower()
    if normalized_action not in {
        "apply_guildstyle_roleplay",
        "guildstyle_create_layout",
        "guildstyle_set_role_color",
        "guildstyle_rename_role",
        "guildstyle_create_role",
        "guildstyle_set_channel_acl",
        "guildstyle_create_category",
        "guildstyle_edit_category",
        "guildstyle_delete_category",
        "guildstyle_create_channel",
        "guildstyle_edit_channel",
        "guildstyle_delete_channel",
        "guildstyle_set_category_theme",
        "guildstyle_set_rename_excludes",
        "guildstyle_reorder_category",
        "guildstyle_reorder_channel",
        "guildstyle_reorder_role",
        "guildstyle_apply_theme_engine",
        "guildstyle_visibility_category_simple",
        "guildstyle_visibility_channel_simple",
    }:
        return None

    safe_tab = "guildstyle_studio" if str(redirect_tab or "").strip().lower() == "guildstyle_studio" else "roleplay"
    redirect_base_url = f"/dashboard/guild/{guild_id}/{safe_tab}"
    audit_target = "guildstyle_studio" if safe_tab == "guildstyle_studio" else "roleplay"
    if safe_tab == "guildstyle_studio":
        forced_permissions = dict(normalized_permissions if isinstance(normalized_permissions, dict) else {})
        forced_action_levels = dict(forced_permissions.get("action_levels") or {})
        forced_action_levels["apply_preset"] = "admin"
        forced_action_levels["manage_permissions"] = "admin"
        forced_permissions["action_levels"] = forced_action_levels
        normalized_permissions = forced_permissions

    def _redirect(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"{redirect_base_url}?notice={urlencode({'notice': message}).split('=', 1)[1]}",
            status_code=303,
        )

    def _permission_denied(action_key: str) -> RedirectResponse:
        required = normalized_permissions["action_levels"].get(action_key, "owner")
        return _redirect(f"Permission denied: {action_key} requires {required.upper()} level.")

    def _normalize_theme_key(raw_value: Any) -> str:
        theme_key = str(raw_value or "roleplay").strip().lower()
        if theme_key not in {"community", "shop", "gaming", "roleplay", "custom"}:
            theme_key = "roleplay"
        return theme_key

    def _normalize_font_style(raw_value: Any) -> str:
        raw_style = str(raw_value or "").strip()
        if raw_style and fancy_text.is_known_style(raw_style):
            return fancy_text.normalize_style_key(raw_style)
        return "bold"

    def _normalize_name_mode(raw_value: Any) -> str:
        mode_key = str(raw_value or "fancy").strip().lower()
        if mode_key not in {
            "fancy",
            "plain",
            "styled",
            "emoji_bracket",
            "emoji_dash",
            "emoji_dot",
            "capsule",
            "template",
        }:
            mode_key = "fancy"
        return mode_key

    def _normalize_id_list(raw_values: Any) -> list[str]:
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        out: list[str] = []
        for raw in values:
            for token in re.split(r"[\s,]+", str(raw or "").strip()):
                text = str(token or "").strip()
                if text.isdigit() and text not in out:
                    out.append(text)
        return out[:500]

    def _sanitize_name_template(raw_value: Any) -> str:
        template = str(raw_value or "").strip()
        if not template:
            template = "₊˚꒰{emoji}꒱ ₊{name}✧꒷₊˚"
        template = template.replace("{{emoji}}", "{emoji}").replace("{{name}}", "{name}")
        if "{emoji}" not in template and "{name}" not in template:
            template = "₊˚꒰{emoji}꒱ ₊{name}✧꒷₊˚"
        return template[:180]

    def _extract_base_slug(raw_name: Any, *, fallback: str) -> str:
        text = str(raw_name or "").strip()
        if not text:
            return fallback
        text = text.replace("_", " ").replace("-", " ")
        text = re.sub(r"[^\w\u0E00-\u0E7F ]+", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip().lower()
        if not text:
            return fallback
        slug = text.replace(" ", "-")
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug or fallback

    async def _load_guildstyle_layout_record() -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            record = await storage.ops_hub_records.get(
                guild_id=guild_id,
                kind="config",
                key="guildstyle_layout",
            ) or {}
        except Exception:
            record = {}
        payload = (
            dict(record.get("data"))
            if isinstance(record, dict) and isinstance(record.get("data"), dict)
            else {}
        )
        return record if isinstance(record, dict) else {}, payload

    async def _save_guildstyle_layout_record(record: dict[str, Any], payload: dict[str, Any]) -> None:
        now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
        safe_payload = dict(payload if isinstance(payload, dict) else {})
        safe_payload["updated_at"] = now_utc.isoformat()
        if record.get("id"):
            await storage.ops_hub_records.update(
                id=int(record.get("id") or 0),
                data=safe_payload,
                updated_at=now_utc,
            )
            return
        await storage.ops_hub_records.insert(
            guild_id=guild_id,
            kind="config",
            key="guildstyle_layout",
            status="active",
            data=safe_payload,
            updated_at=now_utc,
        )

    def _visibility_state(raw_value: Any) -> bool | None:
        state_key = str(raw_value or "inherit").strip().lower()
        if state_key == "allow":
            return True
        if state_key == "deny":
            return False
        return None

    if normalized_action == "apply_guildstyle_roleplay":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="apply_preset"):
            return _permission_denied("apply_preset")
        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        guildstyle_cog = bot.get_cog("GuildStyler")
        if guildstyle_cog is None or not hasattr(guildstyle_cog, "apply_roleplay_theme_from_dashboard"):
            return _redirect("GuildStyle module is not available.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        user_payload = (session.get("user") or {}) if isinstance(session, dict) else {}
        actor_name = str(user_payload.get("username") or user_payload.get("name") or "dashboard-user")
        actor_id = str(user_payload.get("id") or "0")
        apply_result = await guildstyle_cog.apply_roleplay_theme_from_dashboard(
            bot_guild,
            actor_label=f"{actor_name} ({actor_id})",
            font_style="bold",
            setup_autorole=True,
            setup_permissions=True,
        )
        if not bool(apply_result.get("ok")):
            if bool(apply_result.get("limit_reached")):
                used = int(apply_result.get("create_runs") or 0)
                max_runs = int(apply_result.get("max_runs") or 0)
                return _redirect(f"GuildStyle free plan limit reached ({used}/{max_runs}).")
            error_payload = apply_result.get("error")
            if isinstance(error_payload, dict):
                over_channels = int(error_payload.get("channel_over_limit_by") or 0)
                over_roles = int(error_payload.get("role_over_limit_by") or 0)
                return _redirect(
                    "GuildStyle preflight blocked: "
                    f"channels over limit by {over_channels}, roles over limit by {over_roles}."
                )
            return _redirect("Failed to apply GuildStyle roleplay theme.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            "Applied GuildStyle roleplay theme from dashboard",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        result_payload = apply_result.get("result") if isinstance(apply_result.get("result"), dict) else {}
        await _roleplay_append_audit(
            guild_id,
            session,
            action="apply_guildstyle_roleplay",
            scope="settings",
            note=(
                "One-click roleplay theme applied "
                f"(categories {int(result_payload.get('created_categories') or 0)}, "
                f"text {int(result_payload.get('created_text') or 0)}, "
                f"voice {int(result_payload.get('created_voice') or 0)}, "
                f"roles {int(result_payload.get('created_roles') or 0)})"
            ),
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay theme applied via one-click setup.")

    if normalized_action == "guildstyle_create_layout":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="apply_preset"):
            return _permission_denied("apply_preset")
        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        guildstyle_cog = bot.get_cog("GuildStyler")
        if guildstyle_cog is None:
            return _redirect("GuildStyle module is not available.")

        requested_theme = str(data.get("guildstyle_create_theme") or "roleplay").strip().lower()
        if requested_theme not in {"community", "shop", "gaming", "roleplay"}:
            requested_theme = "roleplay"
        font_style = _normalize_font_style(data.get("guildstyle_create_font_style"))
        setup_autorole = str(data.get("guildstyle_setup_autorole") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }
        setup_permissions = str(data.get("guildstyle_setup_permissions") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        user_payload = (session.get("user") or {}) if isinstance(session, dict) else {}
        actor_name = str(user_payload.get("username") or user_payload.get("name") or "dashboard-user")
        actor_id = str(user_payload.get("id") or "0")

        apply_result: dict[str, Any]
        apply_theme_fn = getattr(guildstyle_cog, "apply_theme_from_dashboard", None)
        if callable(apply_theme_fn):
            apply_result = await apply_theme_fn(
                bot_guild,
                actor_label=f"{actor_name} ({actor_id})",
                theme=requested_theme,
                font_style=font_style,
                setup_autorole=setup_autorole,
                setup_permissions=setup_permissions,
            )
        elif requested_theme == "roleplay" and hasattr(guildstyle_cog, "apply_roleplay_theme_from_dashboard"):
            apply_result = await guildstyle_cog.apply_roleplay_theme_from_dashboard(
                bot_guild,
                actor_label=f"{actor_name} ({actor_id})",
                font_style=font_style,
                setup_autorole=setup_autorole,
                setup_permissions=setup_permissions,
            )
        else:
            return _redirect("GuildStyle module version does not support web create for this theme.")

        if not bool(apply_result.get("ok")):
            if bool(apply_result.get("limit_reached")):
                used = int(apply_result.get("create_runs") or 0)
                max_runs = int(apply_result.get("max_runs") or 0)
                return _redirect(f"GuildStyle free plan limit reached ({used}/{max_runs}).")
            error_payload = apply_result.get("error")
            if isinstance(error_payload, dict):
                over_channels = int(error_payload.get("channel_over_limit_by") or 0)
                over_roles = int(error_payload.get("role_over_limit_by") or 0)
                return _redirect(
                    "GuildStyle preflight blocked: "
                    f"channels over limit by {over_channels}, roles over limit by {over_roles}."
                )
            return _redirect("Failed to create GuildStyle layout.")

        result_payload = apply_result.get("result") if isinstance(apply_result.get("result"), dict) else {}
        resolved_theme = str(apply_result.get("theme") or requested_theme).strip().lower() or "roleplay"
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Created GuildStyle layout from dashboard ({resolved_theme})",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_create_layout",
            scope="settings",
            note=(
                f"GuildStyle create theme={resolved_theme}, font={font_style} "
                f"(categories {int(result_payload.get('created_categories') or 0)}, "
                f"text {int(result_payload.get('created_text') or 0)}, "
                f"voice {int(result_payload.get('created_voice') or 0)}, "
                f"roles {int(result_payload.get('created_roles') or 0)})"
            ),
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"GuildStyle create completed for theme '{resolved_theme}'.")

    if normalized_action == "guildstyle_set_role_color":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        role_id_raw = str(data.get("guildstyle_role_id") or "").strip()
        color_raw = str(data.get("guildstyle_role_color") or "").strip()
        if not role_id_raw.isdigit():
            return _redirect("Please select a role first.")
        if not re.match(r"^#?[0-9A-Fa-f]{6}$", color_raw):
            return _redirect("Invalid color format. Use #RRGGBB.")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_roles", False):
            return _redirect("Bot requires Manage Roles permission.")
        role_obj = bot_guild.get_role(int(role_id_raw))
        if role_obj is None:
            return _redirect("Role not found.")
        if bool(getattr(role_obj, "is_default", lambda: False)()):
            return _redirect("Default @everyone role is not editable from this panel.")
        if bool(getattr(role_obj, "managed", False)):
            return _redirect("This role is managed by an integration and cannot be edited.")
        if int(bot_member.top_role.position) <= int(role_obj.position):
            return _redirect("Bot role must be higher than target role.")

        color_hex = color_raw if color_raw.startswith("#") else f"#{color_raw}"
        color_value = int(color_hex.lstrip("#"), 16)
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            await role_obj.edit(
                color=discord.Colour(color_value),
                reason=f"Dashboard GuildStyle role color by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to update role color. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Updated role color: {role_obj.name} -> {color_hex.upper()}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_set_role_color",
            scope="permissions",
            note=f"Role {role_obj.name} color set to {color_hex.upper()}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Role color updated.")

    if normalized_action == "guildstyle_rename_role":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        role_id_raw = str(data.get("guildstyle_role_id") or "").strip()
        role_name_raw = _clean_text(str(data.get("guildstyle_role_name") or "")).strip()
        if not role_id_raw.isdigit():
            return _redirect("Please select a role first.")
        if not role_name_raw:
            return _redirect("Please enter a new role name.")
        if len(role_name_raw) > 100:
            return _redirect("Role name is too long (max 100 characters).")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_roles", False):
            return _redirect("Bot requires Manage Roles permission.")
        role_obj = bot_guild.get_role(int(role_id_raw))
        if role_obj is None:
            return _redirect("Role not found.")
        if bool(getattr(role_obj, "is_default", lambda: False)()):
            return _redirect("Default @everyone role is not editable from this panel.")
        if bool(getattr(role_obj, "managed", False)):
            return _redirect("This role is managed by an integration and cannot be edited.")
        if int(bot_member.top_role.position) <= int(role_obj.position):
            return _redirect("Bot role must be higher than target role.")

        previous_name = str(getattr(role_obj, "name", "") or "").strip()
        if previous_name == role_name_raw:
            return _redirect("Role name is already the same.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            await role_obj.edit(
                name=role_name_raw,
                reason=f"Dashboard GuildStyle role rename by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to rename role. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Renamed role: {previous_name} -> {role_name_raw}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_rename_role",
            scope="permissions",
            note=f"Role renamed from {previous_name} to {role_name_raw}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Role renamed.")

    if normalized_action == "guildstyle_create_role":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        role_name_raw = _clean_text(str(data.get("guildstyle_new_role_name") or "")).strip()
        color_raw = str(data.get("guildstyle_new_role_color") or "").strip()
        if not role_name_raw:
            return _redirect("Please enter a role name.")
        if len(role_name_raw) > 100:
            return _redirect("Role name is too long (max 100 characters).")
        if color_raw and not re.match(r"^#?[0-9A-Fa-f]{6}$", color_raw):
            return _redirect("Invalid color format. Use #RRGGBB.")

        color_hex = (color_raw if color_raw else "#5865F2").strip()
        if not color_hex.startswith("#"):
            color_hex = f"#{color_hex}"
        color_value = int(color_hex.lstrip("#"), 16)

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_roles", False):
            return _redirect("Bot requires Manage Roles permission.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            created_role = await bot_guild.create_role(
                name=role_name_raw,
                color=discord.Colour(color_value),
                mentionable=False,
                hoist=False,
                reason=f"Dashboard GuildStyle role create by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to create role. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Created role: {created_role.name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_create_role",
            scope="permissions",
            note=f"Role created: {created_role.name} ({color_hex.upper()})",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Role created: {created_role.name}.")

    if normalized_action == "guildstyle_reorder_role":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        ordered_role_ids = _normalize_id_list(data.get("guildstyle_role_order_ids") or "")
        if len(ordered_role_ids) < 2:
            return _redirect("Drag at least 2 roles before applying reorder.")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_roles", False):
            return _redirect("Bot requires Manage Roles permission.")

        bot_top_position = int(getattr(getattr(bot_member, "top_role", None), "position", 0) or 0)
        manageable_roles = sorted(
            [
                role
                for role in list(getattr(bot_guild, "roles", []) or [])
                if (
                    not bool(getattr(role, "is_default", lambda: False)())
                    and not bool(getattr(role, "managed", False))
                    and int(getattr(role, "position", 0) or 0) < bot_top_position
                )
            ],
            key=lambda item: int(getattr(item, "position", 0) or 0),
            reverse=True,
        )
        if len(manageable_roles) < 2:
            return _redirect("No manageable roles available for reorder.")

        role_by_id = {
            str(int(getattr(role, "id", 0) or 0)): role
            for role in manageable_roles
        }
        current_order_ids = [
            str(int(getattr(role, "id", 0) or 0))
            for role in manageable_roles
        ]
        requested_ids = [role_id for role_id in ordered_role_ids if role_id in role_by_id]
        if len(requested_ids) < 2:
            return _redirect("Selected roles are not reorderable by this bot.")
        final_ids = requested_ids + [role_id for role_id in current_order_ids if role_id not in requested_ids]
        if final_ids == current_order_ids:
            return _redirect("Role order is already up to date.")

        slot_positions = [
            int(getattr(role, "position", index) or index)
            for index, role in enumerate(manageable_roles)
        ]
        role_position_map: dict[Any, int] = {}
        for target_index, role_id in enumerate(final_ids):
            role_obj = role_by_id.get(role_id)
            if role_obj is None:
                continue
            if target_index >= len(slot_positions):
                break
            role_position_map[role_obj] = slot_positions[target_index]
        if len(role_position_map) < 2:
            return _redirect("Not enough roles to apply reorder.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        moved_count = 0
        failed_count = 0
        reason_label = f"Dashboard GuildStyle role reorder (drag) by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}"
        try:
            await bot_guild.edit_role_positions(
                positions=role_position_map,
                reason=reason_label,
            )
            moved_count = len(role_position_map)
        except Exception:
            for target_index, role_id in enumerate(final_ids):
                role_obj = role_by_id.get(role_id)
                if role_obj is None or target_index >= len(slot_positions):
                    continue
                try:
                    await role_obj.edit(
                        position=slot_positions[target_index],
                        reason=reason_label,
                    )
                    moved_count += 1
                except Exception:
                    failed_count += 1

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Reordered roles via drag-and-drop (moved {moved_count}, failed {failed_count})",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_reorder_role",
            scope="permissions",
            note=f"Role drag reorder applied (moved={moved_count}, failed={failed_count})",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Role order updated. Moved: {moved_count}, Failed: {failed_count}.")

    if normalized_action == "guildstyle_set_category_theme":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        category_id_raw = str(data.get("guildstyle_category_id") or "").strip()
        if not category_id_raw.isdigit():
            return _redirect("Please select a category first.")
        selected_theme = str(data.get("guildstyle_category_theme") or "inherit").strip().lower()
        if selected_theme not in {"inherit", "community", "shop", "gaming", "roleplay", "custom"}:
            selected_theme = "inherit"

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        category_obj = bot_guild.get_channel(int(category_id_raw))
        if not isinstance(category_obj, discord.CategoryChannel):
            return _redirect("Category not found.")

        layout_record, layout_payload = await _load_guildstyle_layout_record()
        category_theme_map = (
            dict(layout_payload.get("category_theme_map"))
            if isinstance(layout_payload.get("category_theme_map"), dict)
            else {}
        )
        if selected_theme == "inherit":
            category_theme_map.pop(category_id_raw, None)
        else:
            category_theme_map[category_id_raw] = selected_theme
        layout_payload["category_theme_map"] = category_theme_map
        await _save_guildstyle_layout_record(layout_record, layout_payload)
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Set category theme: {category_obj.name} -> {selected_theme}",
            target=audit_target,
        )
        return _redirect("Category theme mapping updated.")

    if normalized_action == "guildstyle_set_rename_excludes":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")

        role_raw_values: list[Any] = []
        channel_raw_values: list[Any] = []
        if form_data is not None and hasattr(form_data, "getlist"):
            try:
                role_raw_values = list(form_data.getlist("guildstyle_exclude_role_ids") or [])
            except Exception:
                role_raw_values = []
            try:
                channel_raw_values = list(form_data.getlist("guildstyle_exclude_channel_ids") or [])
            except Exception:
                channel_raw_values = []
        if not role_raw_values:
            role_raw_values = [
                data.get("guildstyle_exclude_role_ids_csv")
                or data.get("guildstyle_exclude_role_ids")
                or ""
            ]
        if not channel_raw_values:
            channel_raw_values = [
                data.get("guildstyle_exclude_channel_ids_csv")
                or data.get("guildstyle_exclude_channel_ids")
                or ""
            ]

        selected_role_ids = _normalize_id_list(role_raw_values)
        selected_channel_ids = _normalize_id_list(channel_raw_values)

        bot = get_bot()
        bot_guild = bot.get_guild(guild_id) if bot else None
        if bot_guild:
            valid_role_ids = {
                str(int(getattr(role_obj, "id", 0) or 0))
                for role_obj in list(getattr(bot_guild, "roles", []) or [])
                if not bool(getattr(role_obj, "is_default", lambda: False)())
            }
            valid_channel_ids = {
                str(int(getattr(channel_obj, "id", 0) or 0))
                for channel_obj in list(getattr(bot_guild, "channels", []) or [])
                if isinstance(channel_obj, (discord.CategoryChannel, discord.TextChannel, discord.VoiceChannel))
            }
            selected_role_ids = [role_id for role_id in selected_role_ids if role_id in valid_role_ids]
            selected_channel_ids = [channel_id for channel_id in selected_channel_ids if channel_id in valid_channel_ids]

        layout_record, layout_payload = await _load_guildstyle_layout_record()
        layout_payload["rename_exclude_role_ids"] = selected_role_ids
        layout_payload["rename_exclude_channel_ids"] = selected_channel_ids
        await _save_guildstyle_layout_record(layout_record, layout_payload)
        await _append_dashboard_audit_event(
            guild_id,
            session,
            (
                "Updated GuildStyle rename exclusion list "
                f"(roles {len(selected_role_ids)}, channels {len(selected_channel_ids)})"
            ),
            target=audit_target,
        )
        return _redirect("Rename exclusion list updated.")

    if normalized_action == "guildstyle_reorder_category":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        category_id_raw = str(data.get("guildstyle_category_id") or "").strip()
        position_raw = str(data.get("guildstyle_category_position") or "").strip()
        ordered_category_ids = _normalize_id_list(data.get("guildstyle_category_order_ids") or "")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")

        categories = sorted(
            list(getattr(bot_guild, "categories", []) or []),
            key=lambda item: int(getattr(item, "position", 0) or 0),
        )
        if not categories:
            return _redirect("No categories found.")
        category_by_id = {
            str(int(getattr(cat, "id", 0) or 0)): cat
            for cat in categories
        }
        current_order_ids = [
            str(int(getattr(cat, "id", 0) or 0))
            for cat in categories
        ]

        if ordered_category_ids:
            requested_ids = [
                cat_id
                for cat_id in ordered_category_ids
                if cat_id in category_by_id
            ]
            if len(requested_ids) < 2:
                return _redirect("Drag at least 2 categories before applying reorder.")
            final_ids = requested_ids + [cat_id for cat_id in current_order_ids if cat_id not in requested_ids]
            if final_ids == current_order_ids:
                return _redirect("Category order is already up to date.")

            snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
            moved_count = 0
            failed_count = 0
            for target_position, category_id in enumerate(final_ids):
                category_obj = category_by_id.get(category_id)
                if category_obj is None:
                    continue
                try:
                    await category_obj.edit(
                        position=target_position,
                        reason=f"Dashboard GuildStyle category reorder (drag) by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                    )
                    moved_count += 1
                except Exception:
                    failed_count += 1

            await _append_dashboard_audit_event(
                guild_id,
                session,
                f"Reordered categories via drag-and-drop (moved {moved_count}, failed {failed_count})",
                target=audit_target,
            )
            snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
            await _roleplay_append_audit(
                guild_id,
                session,
                action="guildstyle_reorder_category",
                scope="permissions",
                note=f"Category drag reorder applied (moved={moved_count}, failed={failed_count})",
                snapshot_before=snapshot_before,
                snapshot_after=snapshot_after,
            )
            return _redirect(f"Category order updated. Moved: {moved_count}, Failed: {failed_count}.")

        if not category_id_raw.isdigit():
            return _redirect("Please select a category first.")
        if not position_raw.isdigit():
            return _redirect("Please enter category position as number.")

        category_obj = bot_guild.get_channel(int(category_id_raw))
        if not isinstance(category_obj, discord.CategoryChannel):
            return _redirect("Category not found.")
        current_index = next(
            (idx for idx, cat in enumerate(categories) if int(getattr(cat, "id", 0) or 0) == int(category_id_raw)),
            None,
        )
        if current_index is None:
            return _redirect("Category not found in current layout.")
        target_one_based = max(1, min(len(categories), int(position_raw)))
        target_zero = target_one_based - 1
        if current_index == target_zero:
            return _redirect("Category is already in that position.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        previous_position = current_index + 1
        try:
            await category_obj.edit(
                position=target_zero,
                reason=f"Dashboard GuildStyle category reorder by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to reorder category. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Reordered category: {category_obj.name} ({previous_position} -> {target_one_based})",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_reorder_category",
            scope="permissions",
            note=f"Category reordered: {category_obj.name} ({previous_position} -> {target_one_based})",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(
            f"Category reordered: {category_obj.name} ({previous_position} -> {target_one_based})."
        )

    if normalized_action == "guildstyle_reorder_channel":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        channel_id_raw = str(data.get("guildstyle_channel_id") or "").strip()
        position_raw = str(data.get("guildstyle_channel_position") or "").strip()
        channel_group_raw = str(data.get("guildstyle_channel_group") or "").strip().lower()
        ordered_channel_ids = _normalize_id_list(data.get("guildstyle_channel_order_ids") or "")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")

        def _siblings_from_group(group_key: str) -> tuple[list[Any], str, str]:
            normalized_group = str(group_key or "").strip().lower()
            if normalized_group.startswith("cat:"):
                group_parts = normalized_group.split(":")
                if len(group_parts) < 2 or not group_parts[1].isdigit():
                    return [], "", ""
                category_obj = bot_guild.get_channel(int(group_parts[1]))
                if not isinstance(category_obj, discord.CategoryChannel):
                    return [], "", ""
                if len(group_parts) >= 3 and group_parts[2] in {"text", "voice"}:
                    channel_type = group_parts[2]
                    channels = list(
                        getattr(category_obj, "text_channels" if channel_type == "text" else "voice_channels", []) or []
                    )
                    channels = sorted(channels, key=lambda item: int(getattr(item, "position", 0) or 0))
                    return channels, f"{category_obj.name}/{channel_type}", channel_type
                text_channels = sorted(
                    list(getattr(category_obj, "text_channels", []) or []),
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
                voice_channels = sorted(
                    list(getattr(category_obj, "voice_channels", []) or []),
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
                return text_channels + voice_channels, category_obj.name, "mixed"
            if normalized_group == "uncat":
                text_channels = sorted(
                    [
                        ch
                        for ch in list(getattr(bot_guild, "text_channels", []) or [])
                        if not getattr(ch, "category_id", None)
                    ],
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
                voice_channels = sorted(
                    [
                        ch
                        for ch in list(getattr(bot_guild, "voice_channels", []) or [])
                        if not getattr(ch, "category_id", None)
                    ],
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
                return text_channels + voice_channels, "uncategorized", "mixed"
            if normalized_group == "uncat:text":
                channels = sorted(
                    [
                        ch
                        for ch in list(getattr(bot_guild, "text_channels", []) or [])
                        if not getattr(ch, "category_id", None)
                    ],
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
                return channels, "uncategorized/text", "text"
            if normalized_group == "uncat:voice":
                channels = sorted(
                    [
                        ch
                        for ch in list(getattr(bot_guild, "voice_channels", []) or [])
                        if not getattr(ch, "category_id", None)
                    ],
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
                return channels, "uncategorized/voice", "voice"
            return [], "", ""

        if ordered_channel_ids:
            siblings, group_label, group_mode = _siblings_from_group(channel_group_raw)
            if not siblings:
                return _redirect("Please select a valid channel group first.")
            if len(siblings) < 2:
                return _redirect("Selected group has less than 2 channels to reorder.")

            channel_by_id = {
                str(int(getattr(ch, "id", 0) or 0)): ch
                for ch in siblings
            }
            current_order_ids = [
                str(int(getattr(ch, "id", 0) or 0))
                for ch in siblings
            ]
            requested_ids = [
                ch_id
                for ch_id in ordered_channel_ids
                if ch_id in channel_by_id
            ]
            if len(requested_ids) < 2:
                return _redirect("Drag at least 2 channels before applying reorder.")
            final_ids = requested_ids + [ch_id for ch_id in current_order_ids if ch_id not in requested_ids]
            snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
            moved_count = 0
            failed_count = 0
            reason_text = f"Dashboard GuildStyle channel reorder (drag) by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}"

            if group_mode == "mixed":
                current_text_ids = [
                    ch_id
                    for ch_id in current_order_ids
                    if isinstance(channel_by_id.get(ch_id), discord.TextChannel)
                ]
                current_voice_ids = [
                    ch_id
                    for ch_id in current_order_ids
                    if isinstance(channel_by_id.get(ch_id), discord.VoiceChannel)
                ]
                final_text_ids = [
                    ch_id
                    for ch_id in final_ids
                    if ch_id in current_text_ids
                ]
                final_voice_ids = [
                    ch_id
                    for ch_id in final_ids
                    if ch_id in current_voice_ids
                ]
                if final_text_ids == current_text_ids and final_voice_ids == current_voice_ids:
                    return _redirect("Channel order is already up to date.")

                async def _apply_lane(
                    *,
                    lane_ids: list[str],
                    current_ids: list[str],
                ) -> tuple[int, int]:
                    lane_moved = 0
                    lane_failed = 0
                    lane_channels = [channel_by_id[ch_id] for ch_id in current_ids if ch_id in channel_by_id]
                    lane_positions = [
                        int(getattr(ch, "position", idx) or idx)
                        for idx, ch in enumerate(lane_channels)
                    ]
                    for target_index, channel_id in enumerate(lane_ids):
                        if target_index >= len(lane_positions):
                            break
                        channel_obj = channel_by_id.get(channel_id)
                        if channel_obj is None:
                            continue
                        target_position = lane_positions[target_index]
                        try:
                            await channel_obj.edit(
                                position=target_position,
                                reason=reason_text,
                            )
                            lane_moved += 1
                        except Exception:
                            lane_failed += 1
                    return lane_moved, lane_failed

                text_moved, text_failed = await _apply_lane(lane_ids=final_text_ids, current_ids=current_text_ids)
                voice_moved, voice_failed = await _apply_lane(lane_ids=final_voice_ids, current_ids=current_voice_ids)
                moved_count = text_moved + voice_moved
                failed_count = text_failed + voice_failed
            else:
                if final_ids == current_order_ids:
                    return _redirect("Channel order is already up to date.")
                slot_positions = [
                    int(getattr(ch, "position", index) or index)
                    for index, ch in enumerate(siblings)
                ]
                for target_index, channel_id in enumerate(final_ids):
                    channel_obj = channel_by_id.get(channel_id)
                    if channel_obj is None:
                        continue
                    target_position = slot_positions[target_index] if target_index < len(slot_positions) else target_index
                    try:
                        await channel_obj.edit(
                            position=target_position,
                            reason=reason_text,
                        )
                        moved_count += 1
                    except Exception:
                        failed_count += 1

            await _append_dashboard_audit_event(
                guild_id,
                session,
                f"Reordered channels via drag-and-drop ({group_label}) moved {moved_count}, failed {failed_count}",
                target=audit_target,
            )
            snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
            await _roleplay_append_audit(
                guild_id,
                session,
                action="guildstyle_reorder_channel",
                scope="permissions",
                note=f"Channel drag reorder ({group_label}) moved={moved_count}, failed={failed_count}",
                snapshot_before=snapshot_before,
                snapshot_after=snapshot_after,
            )
            return _redirect(f"Channel order updated for {group_label}. Moved: {moved_count}, Failed: {failed_count}.")

        if not channel_id_raw.isdigit():
            return _redirect("Please select a channel first.")
        if not position_raw.isdigit():
            return _redirect("Please enter channel position as number.")

        channel_obj = bot_guild.get_channel(int(channel_id_raw))
        if not isinstance(channel_obj, (discord.TextChannel, discord.VoiceChannel)):
            return _redirect("Only text/voice channels are reorderable from this form.")

        is_text = isinstance(channel_obj, discord.TextChannel)
        category_obj = getattr(channel_obj, "category", None)
        if category_obj and isinstance(category_obj, discord.CategoryChannel):
            siblings = sorted(
                list(getattr(category_obj, "text_channels" if is_text else "voice_channels", []) or []),
                key=lambda item: int(getattr(item, "position", 0) or 0),
            )
        else:
            if is_text:
                siblings = sorted(
                    [
                        ch
                        for ch in list(getattr(bot_guild, "text_channels", []) or [])
                        if not getattr(ch, "category_id", None)
                    ],
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
            else:
                siblings = sorted(
                    [
                        ch
                        for ch in list(getattr(bot_guild, "voice_channels", []) or [])
                        if not getattr(ch, "category_id", None)
                    ],
                    key=lambda item: int(getattr(item, "position", 0) or 0),
                )
        if not siblings:
            return _redirect("No channels found for reordering.")
        current_index = next(
            (idx for idx, ch in enumerate(siblings) if int(getattr(ch, "id", 0) or 0) == int(channel_id_raw)),
            None,
        )
        if current_index is None:
            return _redirect("Channel not found in current group.")
        target_one_based = max(1, min(len(siblings), int(position_raw)))
        target_zero = target_one_based - 1
        if current_index == target_zero:
            return _redirect("Channel is already in that position.")

        target_anchor = siblings[target_zero]
        target_position = int(getattr(target_anchor, "position", target_zero) or target_zero)
        previous_position = current_index + 1
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            await channel_obj.edit(
                position=target_position,
                reason=f"Dashboard GuildStyle channel reorder by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to reorder channel. Check bot permissions.")

        channel_name = str(getattr(channel_obj, "name", "") or channel_id_raw)
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Reordered channel: {channel_name} ({previous_position} -> {target_one_based})",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_reorder_channel",
            scope="permissions",
            note=f"Channel reordered: {channel_name} ({previous_position} -> {target_one_based})",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(
            f"Channel reordered: {channel_name} ({previous_position} -> {target_one_based})."
        )

    if normalized_action == "guildstyle_create_category":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        category_name = _clean_text(str(data.get("guildstyle_category_name") or "")).strip()
        if not category_name:
            return _redirect("Please enter category name.")
        if len(category_name) > 100:
            return _redirect("Category name is too long (max 100 characters).")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            created_category = await bot_guild.create_category(
                name=category_name,
                reason=f"Dashboard GuildStyle category create by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to create category. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Created category: {created_category.name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_create_category",
            scope="permissions",
            note=f"Category created: {created_category.name}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Category created: {created_category.name}.")

    if normalized_action == "guildstyle_edit_category":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        category_id_raw = str(data.get("guildstyle_category_id") or "").strip()
        if not category_id_raw.isdigit():
            return _redirect("Please select a category first.")
        new_name = _clean_text(str(data.get("guildstyle_new_category_name") or "")).strip()
        if new_name and len(new_name) > 100:
            return _redirect("Category name is too long (max 100 characters).")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        category_obj = bot_guild.get_channel(int(category_id_raw))
        if not isinstance(category_obj, discord.CategoryChannel):
            return _redirect("Category not found.")

        previous_name = str(getattr(category_obj, "name", "") or "")
        if not new_name:
            return _redirect("No change to apply. Please enter new category name.")
        if new_name == previous_name:
            return _redirect("Category name is already the same.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            await category_obj.edit(
                name=new_name,
                reason=f"Dashboard GuildStyle category edit by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to rename category. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Renamed category: {previous_name} -> {new_name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_edit_category",
            scope="permissions",
            note=f"Category renamed to {new_name}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Category updated.")

    if normalized_action == "guildstyle_delete_category":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        category_id_raw = str(data.get("guildstyle_category_id") or "").strip()
        if not category_id_raw.isdigit():
            return _redirect("Please select a category first.")
        delete_children = str(data.get("guildstyle_delete_children") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        category_obj = bot_guild.get_channel(int(category_id_raw))
        if not isinstance(category_obj, discord.CategoryChannel):
            return _redirect("Category not found.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        deleted_children = 0
        if delete_children:
            for child in list(getattr(category_obj, "channels", []) or []):
                try:
                    await child.delete(
                        reason=f"Dashboard GuildStyle category cleanup by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                    )
                    deleted_children += 1
                except Exception:
                    continue
        try:
            category_name = str(getattr(category_obj, "name", "") or category_id_raw)
            await category_obj.delete(
                reason=f"Dashboard GuildStyle category delete by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to delete category. Delete child channels first or enable child deletion.")

        layout_record, layout_payload = await _load_guildstyle_layout_record()
        category_theme_map = (
            dict(layout_payload.get("category_theme_map"))
            if isinstance(layout_payload.get("category_theme_map"), dict)
            else {}
        )
        category_theme_map.pop(category_id_raw, None)
        layout_payload["category_theme_map"] = category_theme_map
        await _save_guildstyle_layout_record(layout_record, layout_payload)

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Deleted category: {category_name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_delete_category",
            scope="permissions",
            note=f"Category deleted: {category_name} (children removed: {deleted_children})",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Category deleted: {category_name}.")

    if normalized_action == "guildstyle_create_channel":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        channel_type = str(data.get("guildstyle_channel_type") or "text").strip().lower()
        if channel_type not in {"text", "voice"}:
            channel_type = "text"
        channel_name = _clean_text(str(data.get("guildstyle_channel_name") or "")).strip()
        if not channel_name:
            return _redirect("Please enter channel name.")
        if len(channel_name) > 100:
            return _redirect("Channel name is too long (max 100 characters).")
        category_id_raw = str(data.get("guildstyle_category_id") or "").strip()

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        parent_category = None
        if category_id_raw.isdigit():
            parent_obj = bot_guild.get_channel(int(category_id_raw))
            if isinstance(parent_obj, discord.CategoryChannel):
                parent_category = parent_obj

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            if channel_type == "voice":
                created_channel = await bot_guild.create_voice_channel(
                    name=channel_name,
                    category=parent_category,
                    reason=f"Dashboard GuildStyle channel create by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                )
            else:
                created_channel = await bot_guild.create_text_channel(
                    name=channel_name,
                    category=parent_category,
                    reason=f"Dashboard GuildStyle channel create by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                )
        except Exception:
            return _redirect("Failed to create channel. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Created {channel_type} channel: {created_channel.name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_create_channel",
            scope="permissions",
            note=f"Created {channel_type} channel: {created_channel.name}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Channel created: {created_channel.name}.")

    if normalized_action == "guildstyle_edit_channel":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        channel_id_raw = str(data.get("guildstyle_channel_id") or "").strip()
        if not channel_id_raw.isdigit():
            return _redirect("Please select a channel first.")
        new_name = _clean_text(str(data.get("guildstyle_new_channel_name") or "")).strip()
        if new_name and len(new_name) > 100:
            return _redirect("Channel name is too long (max 100 characters).")
        new_category_id_raw = str(data.get("guildstyle_new_category_id") or "").strip()

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        channel_obj = bot_guild.get_channel(int(channel_id_raw))
        if not isinstance(channel_obj, (discord.TextChannel, discord.VoiceChannel)):
            return _redirect("Only text/voice channels are editable from this form.")

        patch: dict[str, Any] = {}
        if new_name and new_name != str(getattr(channel_obj, "name", "") or ""):
            patch["name"] = new_name
        if new_category_id_raw == "__keep__":
            pass
        elif new_category_id_raw == "__none__":
            if getattr(channel_obj, "category_id", None):
                patch["category"] = None
        elif new_category_id_raw:
            if new_category_id_raw.isdigit():
                parent_obj = bot_guild.get_channel(int(new_category_id_raw))
                if isinstance(parent_obj, discord.CategoryChannel):
                    if getattr(channel_obj, "category_id", None) != int(new_category_id_raw):
                        patch["category"] = parent_obj
        if not patch:
            return _redirect("No change to apply.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            await channel_obj.edit(
                reason=f"Dashboard GuildStyle channel edit by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                **patch,
            )
        except Exception:
            return _redirect("Failed to update channel. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Updated channel: {channel_obj.name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_edit_channel",
            scope="permissions",
            note=f"Updated channel: {channel_obj.name}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Channel updated.")

    if normalized_action == "guildstyle_delete_channel":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        channel_id_raw = str(data.get("guildstyle_channel_id") or "").strip()
        if not channel_id_raw.isdigit():
            return _redirect("Please select a channel first.")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        channel_obj = bot_guild.get_channel(int(channel_id_raw))
        if not isinstance(channel_obj, (discord.TextChannel, discord.VoiceChannel)):
            return _redirect("Only text/voice channels are deletable from this form.")

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        channel_name = str(getattr(channel_obj, "name", "") or channel_id_raw)
        try:
            await channel_obj.delete(
                reason=f"Dashboard GuildStyle channel delete by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to delete channel. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Deleted channel: {channel_name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_delete_channel",
            scope="permissions",
            note=f"Deleted channel: {channel_name}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Channel deleted: {channel_name}.")

    if normalized_action == "guildstyle_visibility_category_simple":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        role_id_raw = str(data.get("guildstyle_role_id") or "").strip()
        category_id_raw = str(data.get("guildstyle_category_id") or "").strip()
        if not role_id_raw.isdigit() or not category_id_raw.isdigit():
            return _redirect("Please select both role and category.")
        visibility_state = _visibility_state(data.get("guildstyle_visibility_state"))
        apply_children = str(data.get("guildstyle_apply_children") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        role_obj = bot_guild.get_role(int(role_id_raw))
        if role_obj is None:
            return _redirect("Role not found.")
        if int(bot_member.top_role.position) <= int(role_obj.position):
            return _redirect("Bot role must be higher than target role.")
        category_obj = bot_guild.get_channel(int(category_id_raw))
        if not isinstance(category_obj, discord.CategoryChannel):
            return _redirect("Category not found.")

        targets: list[discord.abc.GuildChannel] = [category_obj]
        if apply_children:
            for child in list(getattr(category_obj, "channels", []) or []):
                if isinstance(child, (discord.TextChannel, discord.VoiceChannel)):
                    targets.append(child)

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        changed_count = 0
        failed_count = 0
        for target in targets:
            overwrite = target.overwrites_for(role_obj)
            current_state = getattr(overwrite, "view_channel", None)
            if current_state == visibility_state:
                continue
            setattr(overwrite, "view_channel", visibility_state)
            try:
                await target.set_permissions(
                    role_obj,
                    overwrite=overwrite,
                    reason=f"Dashboard GuildStyle visibility by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                )
                changed_count += 1
            except Exception:
                failed_count += 1

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Visibility update for {role_obj.name} on category {category_obj.name} (changed {changed_count}, failed {failed_count})",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_visibility_category_simple",
            scope="permissions",
            note=(
                f"Category visibility set for role {role_obj.name} on {category_obj.name} "
                f"(apply_children={apply_children}, changed={changed_count}, failed={failed_count})"
            ),
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Category visibility applied. Changed: {changed_count}, Failed: {failed_count}.")

    if normalized_action == "guildstyle_visibility_channel_simple":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        role_id_raw = str(data.get("guildstyle_role_id") or "").strip()
        channel_id_raw = str(data.get("guildstyle_channel_id") or "").strip()
        if not role_id_raw.isdigit() or not channel_id_raw.isdigit():
            return _redirect("Please select both role and channel.")
        visibility_state = _visibility_state(data.get("guildstyle_visibility_state"))

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        role_obj = bot_guild.get_role(int(role_id_raw))
        if role_obj is None:
            return _redirect("Role not found.")
        if int(bot_member.top_role.position) <= int(role_obj.position):
            return _redirect("Bot role must be higher than target role.")
        channel_obj = bot_guild.get_channel(int(channel_id_raw))
        if not isinstance(channel_obj, (discord.TextChannel, discord.VoiceChannel)):
            return _redirect("Channel not found.")

        overwrite = channel_obj.overwrites_for(role_obj)
        current_state = getattr(overwrite, "view_channel", None)
        if current_state == visibility_state:
            return _redirect("No change required. Visibility is already set.")

        setattr(overwrite, "view_channel", visibility_state)
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            await channel_obj.set_permissions(
                role_obj,
                overwrite=overwrite,
                reason=f"Dashboard GuildStyle visibility by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to update channel visibility. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Visibility update for {role_obj.name} on channel {channel_obj.name}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_visibility_channel_simple",
            scope="permissions",
            note=f"Channel visibility set for role {role_obj.name} on {channel_obj.name}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Channel visibility applied.")

    if normalized_action == "guildstyle_apply_theme_engine":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        raw_selected_theme = str(data.get("guildstyle_theme") or "").strip().lower()
        selected_theme = _normalize_theme_key(raw_selected_theme) if raw_selected_theme else ""
        selected_font_style = _normalize_font_style(data.get("guildstyle_font_style"))
        selected_name_mode = _normalize_name_mode(data.get("guildstyle_name_mode"))
        selected_name_template = _sanitize_name_template(data.get("guildstyle_name_template"))
        apply_categories = str(data.get("guildstyle_apply_categories") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }
        apply_channels = str(data.get("guildstyle_apply_channels") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }
        apply_roles = str(data.get("guildstyle_apply_roles") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }
        force_all_rename = str(data.get("guildstyle_force_all_rename") or "").strip().lower() in {
            "1", "true", "yes", "on", "enable", "enabled",
        }
        if not any([apply_categories, apply_channels, apply_roles]):
            return _redirect("Please enable at least one apply target.")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        bot_member = getattr(bot_guild, "me", None)
        if bot_member is None:
            return _redirect("Bot member is not available in this guild.")
        if (apply_categories or apply_channels) and not getattr(getattr(bot_member, "guild_permissions", None), "manage_channels", False):
            return _redirect("Bot requires Manage Channels permission.")
        if apply_roles and not getattr(getattr(bot_member, "guild_permissions", None), "manage_roles", False):
            return _redirect("Bot requires Manage Roles permission.")

        try:
            from skylinebot.src.commands.guildstyle import (
                GuildStyler,
                _fancy_wrap,
                _keyword_emoji,
                _keyword_emoji_ai,
                _title_case_from_slug,
                _trim_name,
            )
        except Exception:
            return _redirect("GuildStyle formatter is not available right now.")

        layout_record, layout_payload = await _load_guildstyle_layout_record()
        category_theme_map_src = (
            dict(layout_payload.get("category_theme_map"))
            if isinstance(layout_payload.get("category_theme_map"), dict)
            else {}
        )
        category_theme_map: dict[str, str] = {}
        for raw_cat_id, raw_theme in category_theme_map_src.items():
            cat_id_text = str(raw_cat_id or "").strip()
            if not cat_id_text.isdigit():
                continue
            theme_key = _normalize_theme_key(raw_theme)
            category_theme_map[cat_id_text] = theme_key
        rename_exclude_role_ids = set(
            _normalize_id_list(layout_payload.get("rename_exclude_role_ids"))
        )
        rename_exclude_channel_ids = set(
            _normalize_id_list(layout_payload.get("rename_exclude_channel_ids"))
        )
        if force_all_rename:
            rename_exclude_role_ids = set()
            rename_exclude_channel_ids = set()

        theme_cache: dict[str, dict[str, Any]] = {}

        def _theme_blueprint_for(theme_key: str) -> dict[str, Any]:
            normalized = theme_key if theme_key in {"community", "shop", "gaming", "roleplay"} else ""
            if not normalized:
                return {"categories": []}
            cached = theme_cache.get(normalized)
            if isinstance(cached, dict):
                return cached
            blueprint = GuildStyler._theme_blueprint(normalized)
            if not isinstance(blueprint, dict):
                blueprint = {"categories": []}
            theme_cache[normalized] = blueprint
            return blueprint

        emoji_ai_cache: dict[str, str] = {}
        thaimoji_api_key = str(
            os.getenv(
                "THAIMOJI_API_KEY",
                os.getenv("AIFORTHAI_EMOJI_API_KEY", os.getenv("AIFORTHAI_API_KEY", "")),
            )
        ).strip()

        def _is_direct_emoji_token(raw_value: str) -> bool:
            candidate = str(raw_value or "").strip()
            if not candidate:
                return False
            if re.fullmatch(r"<a?:[A-Za-z0-9_]{2,32}:\d{16,22}>", candidate):
                return True
            return bool(re.search(r"[\U0001F1E6-\U0001FAFF\u2600-\u27BF]", candidate))

        async def _resolve_emoji_token(base_slug: str, emoji_value: str = "") -> str:
            safe_slug = _extract_base_slug(base_slug, fallback="item")
            preset_token = str(emoji_value or "").strip()[:64]
            if _is_direct_emoji_token(preset_token):
                return preset_token

            detected = await _keyword_emoji_ai(
                safe_slug,
                api_key=thaimoji_api_key,
                cache=emoji_ai_cache,
            )
            if detected:
                return str(detected).strip()[:64]

            if preset_token:
                return preset_token
            return str(_keyword_emoji(safe_slug)).strip()[:64]

        async def _format_name(base_slug: str, emoji_value: str) -> str:
            safe_slug = _extract_base_slug(base_slug, fallback="item")
            emoji_token = await _resolve_emoji_token(safe_slug, emoji_value)
            if not emoji_token:
                emoji_token = _keyword_emoji(safe_slug)
            pretty = _title_case_from_slug(safe_slug)
            pretty_styled = fancy_text.transform_text(pretty, selected_font_style)
            if selected_name_mode == "fancy":
                return _trim_name(_fancy_wrap(safe_slug, emoji_token, selected_font_style))
            if selected_name_mode == "plain":
                return _trim_name(f"{emoji_token} {pretty_styled}".strip())
            if selected_name_mode == "styled":
                return _trim_name(pretty_styled or pretty)
            if selected_name_mode == "emoji_bracket":
                return _trim_name(f"[{emoji_token}] {pretty_styled or pretty}".strip())
            if selected_name_mode == "emoji_dash":
                return _trim_name(f"{emoji_token} - {pretty_styled or pretty}".strip())
            if selected_name_mode == "emoji_dot":
                return _trim_name(f"{emoji_token} . {pretty_styled or pretty}".strip())
            if selected_name_mode == "capsule":
                return _trim_name(f"[{pretty_styled or pretty}]".strip())
            rendered = selected_name_template.replace("{emoji}", emoji_token).replace("{name}", pretty_styled)
            rendered = re.sub(r"\s+", " ", rendered).strip()
            if not rendered:
                rendered = f"{emoji_token} {pretty_styled}".strip()
            return _trim_name(rendered)

        summary = {
            "category_renamed": 0,
            "channel_renamed": 0,
            "role_renamed": 0,
            "role_recolored": 0,
            "rename_excluded": 0,
            "skipped": 0,
            "failed": 0,
        }
        failed_samples: list[str] = []

        def _mark_failed(sample: str) -> None:
            summary["failed"] += 1
            sample_text = str(sample or "").strip()
            if not sample_text:
                return
            if len(failed_samples) >= 5:
                return
            if sample_text in failed_samples:
                return
            failed_samples.append(sample_text[:72])

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        categories = sorted(
            list(getattr(bot_guild, "categories", []) or []),
            key=lambda item: int(getattr(item, "position", 0) or 0),
        )
        for cat_index, category in enumerate(categories):
            cat_id_text = str(int(getattr(category, "id", 0) or 0))
            cat_theme = category_theme_map.get(cat_id_text, selected_theme) if selected_theme else ""
            blueprint = _theme_blueprint_for(cat_theme)
            category_specs = list(blueprint.get("categories") or [])
            category_spec = category_specs[cat_index % len(category_specs)] if category_specs else {}

            if apply_categories:
                target_cat_slug = str(category_spec.get("name") or _extract_base_slug(category.name, fallback="category"))
                target_cat_emoji = str(category_spec.get("emoji") or "").strip()
                target_cat_name = await _format_name(target_cat_slug, target_cat_emoji)
                if target_cat_name != str(getattr(category, "name", "") or ""):
                    if cat_id_text in rename_exclude_channel_ids:
                        summary["rename_excluded"] += 1
                        continue
                    try:
                        await category.edit(
                            name=target_cat_name,
                            reason=f"Dashboard GuildStyle theme apply by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                        )
                        summary["category_renamed"] += 1
                    except Exception:
                        _mark_failed(f"Category: {getattr(category, 'name', cat_id_text)}")

            if not apply_channels:
                continue
            text_specs = list(category_spec.get("text") or [])
            voice_specs = list(category_spec.get("voice") or [])
            for text_index, text_channel in enumerate(
                sorted(list(getattr(category, "text_channels", []) or []), key=lambda item: int(getattr(item, "position", 0) or 0))
            ):
                text_slug = (
                    str(text_specs[text_index % len(text_specs)]).strip()
                    if text_specs
                    else _extract_base_slug(text_channel.name, fallback="text-channel")
                )
                target_text_name = await _format_name(text_slug, "")
                if target_text_name == str(getattr(text_channel, "name", "") or ""):
                    continue
                text_id = str(int(getattr(text_channel, "id", 0) or 0))
                if text_id in rename_exclude_channel_ids:
                    summary["rename_excluded"] += 1
                    continue
                try:
                    await text_channel.edit(
                        name=target_text_name,
                        reason=f"Dashboard GuildStyle theme apply by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                    )
                    summary["channel_renamed"] += 1
                except Exception:
                    _mark_failed(f"Text: {getattr(text_channel, 'name', text_id)}")
            for voice_index, voice_channel in enumerate(
                sorted(list(getattr(category, "voice_channels", []) or []), key=lambda item: int(getattr(item, "position", 0) or 0))
            ):
                voice_slug = (
                    str(voice_specs[voice_index % len(voice_specs)]).strip()
                    if voice_specs
                    else _extract_base_slug(voice_channel.name, fallback="voice-room")
                )
                target_voice_name = await _format_name(voice_slug, "")
                if target_voice_name == str(getattr(voice_channel, "name", "") or ""):
                    continue
                voice_id = str(int(getattr(voice_channel, "id", 0) or 0))
                if voice_id in rename_exclude_channel_ids:
                    summary["rename_excluded"] += 1
                    continue
                try:
                    await voice_channel.edit(
                        name=target_voice_name,
                        reason=f"Dashboard GuildStyle theme apply by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                    )
                    summary["channel_renamed"] += 1
                except Exception:
                    _mark_failed(f"Voice: {getattr(voice_channel, 'name', voice_id)}")

        if apply_channels:
            uncategorized_text = sorted(
                [
                    ch
                    for ch in list(getattr(bot_guild, "text_channels", []) or [])
                    if not getattr(ch, "category_id", None)
                ],
                key=lambda item: int(getattr(item, "position", 0) or 0),
            )
            uncategorized_voice = sorted(
                [
                    ch
                    for ch in list(getattr(bot_guild, "voice_channels", []) or [])
                    if not getattr(ch, "category_id", None)
                ],
                key=lambda item: int(getattr(item, "position", 0) or 0),
            )
            for index, text_channel in enumerate(uncategorized_text):
                slug = _extract_base_slug(text_channel.name, fallback=f"text-{index+1}")
                target_name = await _format_name(slug, "")
                if target_name == str(getattr(text_channel, "name", "") or ""):
                    continue
                text_id = str(int(getattr(text_channel, "id", 0) or 0))
                if text_id in rename_exclude_channel_ids:
                    summary["rename_excluded"] += 1
                    continue
                try:
                    await text_channel.edit(
                        name=target_name,
                        reason=f"Dashboard GuildStyle theme apply by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                    )
                    summary["channel_renamed"] += 1
                except Exception:
                    _mark_failed(f"Text: {getattr(text_channel, 'name', text_id)}")
            for index, voice_channel in enumerate(uncategorized_voice):
                slug = _extract_base_slug(voice_channel.name, fallback=f"voice-{index+1}")
                target_name = await _format_name(slug, "")
                if target_name == str(getattr(voice_channel, "name", "") or ""):
                    continue
                voice_id = str(int(getattr(voice_channel, "id", 0) or 0))
                if voice_id in rename_exclude_channel_ids:
                    summary["rename_excluded"] += 1
                    continue
                try:
                    await voice_channel.edit(
                        name=target_name,
                        reason=f"Dashboard GuildStyle theme apply by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                    )
                    summary["channel_renamed"] += 1
                except Exception:
                    _mark_failed(f"Voice: {getattr(voice_channel, 'name', voice_id)}")

        if apply_roles:
            editable_roles = sorted(
                [role for role in list(getattr(bot_guild, "roles", []) or []) if not role.is_default()],
                key=lambda item: int(getattr(item, "position", 0) or 0),
                reverse=True,
            )
            role_theme_enabled = selected_theme in {"community", "shop", "gaming", "roleplay"}
            role_specs = GuildStyler._role_specs_for_theme(selected_theme) if role_theme_enabled else []
            for role_index, role_obj in enumerate(editable_roles):
                if bool(getattr(role_obj, "managed", False)):
                    summary["skipped"] += 1
                    continue
                if int(bot_member.top_role.position) <= int(role_obj.position):
                    summary["skipped"] += 1
                    continue
                if role_specs:
                    role_slug, role_emoji, role_color = role_specs[role_index % len(role_specs)]
                else:
                    role_slug = _extract_base_slug(getattr(role_obj, "name", ""), fallback=f"role-{role_index+1}")
                    role_emoji = ""
                    role_color = getattr(role_obj, "color", discord.Colour.default())
                target_role_name = await _format_name(role_slug, role_emoji)
                role_id_text = str(int(getattr(role_obj, "id", 0) or 0))
                need_name = target_role_name != str(getattr(role_obj, "name", "") or "")
                if need_name and role_id_text in rename_exclude_role_ids:
                    need_name = False
                    summary["rename_excluded"] += 1
                need_color = bool(role_specs) and (
                    int(getattr(getattr(role_obj, "color", None), "value", 0) or 0)
                    != int(getattr(role_color, "value", 0) or 0)
                )
                if not need_name and not need_color:
                    continue
                try:
                    await role_obj.edit(
                        name=target_role_name if need_name else str(getattr(role_obj, "name", "") or ""),
                        color=role_color if need_color else getattr(role_obj, "color", discord.Colour.default()),
                        reason=f"Dashboard GuildStyle role theme by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
                    )
                    if need_name:
                        summary["role_renamed"] += 1
                    if need_color:
                        summary["role_recolored"] += 1
                except Exception:
                    _mark_failed(f"Role: {getattr(role_obj, 'name', role_id_text)}")

        layout_payload["theme"] = selected_theme if selected_theme else "custom"
        layout_payload["font_style"] = selected_font_style
        layout_payload["name_mode"] = selected_name_mode
        layout_payload["name_template"] = selected_name_template
        layout_payload["category_theme_map"] = category_theme_map
        if selected_theme in {"community", "shop", "gaming", "roleplay"}:
            layout_payload["blueprint"] = GuildStyler._theme_blueprint(selected_theme)
        else:
            layout_payload.pop("blueprint", None)
        await _save_guildstyle_layout_record(layout_record, layout_payload)

        await _append_dashboard_audit_event(
            guild_id,
            session,
            (
                "Applied GuildStyle Theme Engine "
                f"(cat {summary['category_renamed']}, ch {summary['channel_renamed']}, "
                f"role name {summary['role_renamed']}, role color {summary['role_recolored']}, "
                f"rename-excluded {summary['rename_excluded']}, "
                f"skipped {summary['skipped']}, failed {summary['failed']})"
            ),
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_apply_theme_engine",
            scope="permissions",
            note=(
                f"Theme={selected_theme or 'none(custom-guild)'}, mode={selected_name_mode}, font={selected_font_style}, "
                f"renamed(cat={summary['category_renamed']}, ch={summary['channel_renamed']}, role={summary['role_renamed']}), "
                f"recolored(role={summary['role_recolored']}), rename_excluded={summary['rename_excluded']}, "
                f"skipped={summary['skipped']}, failed={summary['failed']}, force_all_rename={force_all_rename}"
            ),
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(
            "Theme applied. "
            f"Categories renamed: {summary['category_renamed']}, "
            f"Channels renamed: {summary['channel_renamed']}, "
            f"Roles renamed: {summary['role_renamed']}, "
            f"Role colors updated: {summary['role_recolored']}, "
            f"Rename excluded: {summary['rename_excluded']}, "
            f"Failed: {summary['failed']}, "
            f"Ignore exclude list: {'on' if force_all_rename else 'off'}"
            f"{'. Failed samples: ' + ', '.join(failed_samples) if failed_samples else '.'}"
        )

    if normalized_action == "guildstyle_set_channel_acl":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        channel_id_raw = str(data.get("guildstyle_channel_id") or "").strip()
        role_id_raw = str(data.get("guildstyle_role_id") or "").strip()
        if not channel_id_raw.isdigit() or not role_id_raw.isdigit():
            return _redirect("Please select both room and role.")

        bot = get_bot()
        if not bot:
            return _redirect("Bot runtime is not available right now.")
        bot_guild = bot.get_guild(guild_id)
        if not bot_guild:
            return _redirect("Guild is not available on bot runtime.")
        channel_obj = bot_guild.get_channel(int(channel_id_raw))
        role_obj = bot_guild.get_role(int(role_id_raw))
        if channel_obj is None or role_obj is None:
            return _redirect("Room or role not found.")
        if not isinstance(channel_obj, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
            return _redirect("Selected room type is not supported.")
        if getattr(bot_guild, "me", None) and int(bot_guild.me.top_role.position) <= int(role_obj.position):
            return _redirect("Bot role must be higher than target role.")

        state_map: dict[str, bool | None] = {"allow": True, "deny": False, "inherit": None}
        perm_fields = {
            "view_channel": "perm_view_channel",
            "send_messages": "perm_send_messages",
            "read_message_history": "perm_read_message_history",
            "connect": "perm_connect",
            "speak": "perm_speak",
            "manage_messages": "perm_manage_messages",
        }
        patch: dict[str, bool | None] = {}
        for perm_attr, field_name in perm_fields.items():
            raw_state = str(data.get(field_name) or "inherit").strip().lower()
            patch[perm_attr] = state_map.get(raw_state, None)

        overwrite = channel_obj.overwrites_for(role_obj)
        for perm_attr, perm_value in patch.items():
            setattr(overwrite, perm_attr, perm_value)

        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        try:
            await channel_obj.set_permissions(
                role_obj,
                overwrite=overwrite,
                reason=f"Dashboard GuildStyle ACL by {((session.get('user') or {}).get('id') if isinstance(session, dict) else 0)}",
            )
        except Exception:
            return _redirect("Failed to update room permissions. Check bot permissions.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Updated room ACL for {role_obj.name} on {getattr(channel_obj, 'name', channel_id_raw)}",
            target=audit_target,
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="guildstyle_set_channel_acl",
            scope="permissions",
            note=(
                f"ACL updated for role {role_obj.name} on channel {getattr(channel_obj, 'name', channel_id_raw)}"
            ),
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Room permission updated.")

    return None

async def update_roleplay_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="roleplay",
    )
    if blocked_response:
        return blocked_response

    form = await request.form()
    data: dict[str, str] = {}
    for key, value in form.items():
        if hasattr(value, "filename"):
            continue
        data[str(key)] = str(value)
    action = str(data.get("action") or "save").strip().lower()
    origin_tab_raw = str(data.get("origin_tab") or "").strip().lower()
    origin_tab = "guildstyle_studio" if origin_tab_raw == "guildstyle_studio" else "roleplay"
    origin_tab_url = f"/dashboard/guild/{guild_id}/{origin_tab}"

    def _redirect(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"{origin_tab_url}?notice={urlencode({'notice': message}).split('=', 1)[1]}",
            status_code=303,
        )

    raw_settings = state.get("rp_settings") if isinstance(state.get("rp_settings"), dict) else {}
    settings_row = raw_settings if raw_settings else await storage.rp_settings.get(guild_id=guild_id) or {}
    if not settings_row:
        await storage.rp_settings.insert(guild_id=guild_id)
        settings_row = await storage.rp_settings.get(guild_id=guild_id) or {}
    settings = _normalize_roleplay_dashboard_settings(settings_row)
    permissions_row = await _roleplay_ensure_permissions_row(guild_id)
    normalized_permissions = _roleplay_normalize_permissions(permissions_row)
    actor_level = _roleplay_actor_level(
        session=session,
        current_guild=current_guild,
        bot_guild=get_bot().get_guild(guild_id) if get_bot() else None,
        state=state,
        permissions_row=permissions_row,
    )

    def _permission_denied(action_key: str) -> RedirectResponse:
        required = normalized_permissions["action_levels"].get(action_key, "owner")
        return _redirect(f"Permission denied: {action_key} requires {required.upper()} level.")

    theme_only_actions = {
        "apply_guildstyle_roleplay",
        "guildstyle_create_layout",
        "guildstyle_set_role_color",
        "guildstyle_rename_role",
        "guildstyle_create_role",
        "guildstyle_set_channel_acl",
        "guildstyle_create_category",
        "guildstyle_edit_category",
        "guildstyle_delete_category",
        "guildstyle_create_channel",
        "guildstyle_edit_channel",
        "guildstyle_delete_channel",
        "guildstyle_set_category_theme",
        "guildstyle_set_rename_excludes",
        "guildstyle_reorder_category",
        "guildstyle_reorder_channel",
        "guildstyle_reorder_role",
        "guildstyle_apply_theme_engine",
        "guildstyle_visibility_category_simple",
        "guildstyle_visibility_channel_simple",
    }
    if action in theme_only_actions:
        return _redirect("This action belongs to Theme guildstyle tab only.")

    if action in {"save", "apply_preset", "apply_city_starter"}:
        permission_key = "apply_preset" if action in {"apply_preset", "apply_city_starter"} else "save_settings"
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key=permission_key):
            return _permission_denied(permission_key)
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        candidate = dict(settings)
        candidate.update(
            {
                "enabled": _bool_from_form(data, "enabled"),
                "preset_key": "modern_city",
                "allow_custom_config": _bool_from_form(data, "allow_custom_config"),
                "allow_custom_scenarios": _bool_from_form(data, "allow_custom_scenarios"),
                "currency_symbol": data.get("currency_symbol", settings.get("currency_symbol", "coin")),
                "start_coins": _int_from_form(data, "start_coins", int(settings.get("start_coins") or 250), 0, 2_000_000),
                "start_xp": int(settings.get("start_xp") or 0),
                "xp_per_level": _int_from_form(data, "xp_per_level", int(settings.get("xp_per_level") or 120), 20, 10_000),
                "daily_reward_min": _int_from_form(data, "daily_reward_min", int(settings.get("daily_reward_min") or 80), 0, 200_000),
                "daily_reward_max": _int_from_form(data, "daily_reward_max", int(settings.get("daily_reward_max") or 180), 0, 300_000),
                "story_min_length": _int_from_form(data, "story_min_length", int(settings.get("story_min_length") or 20), 5, 2_000),
                "story_cooldown_seconds": _int_from_form(data, "story_cooldown_seconds", int(settings.get("story_cooldown_seconds") or 300), 0, 86_400),
                "story_reward_min": _int_from_form(data, "story_reward_min", int(settings.get("story_reward_min") or 12), 0, 100_000),
                "story_reward_max": _int_from_form(data, "story_reward_max", int(settings.get("story_reward_max") or 40), 0, 150_000),
                "scenario_cooldown_seconds": _int_from_form(data, "scenario_cooldown_seconds", int(settings.get("scenario_cooldown_seconds") or 900), 0, 86_400),
                "event_reward_xp": _int_from_form(data, "event_reward_xp", int(settings.get("event_reward_xp") or 120), 0, 250_000),
                "event_reward_coins": _int_from_form(data, "event_reward_coins", int(settings.get("event_reward_coins") or 220), 0, 250_000),
                "event_announce_channel_id": (
                    str(data.get("event_announce_channel_id") or "").strip()
                    if str(data.get("event_announce_channel_id") or "").strip().isdigit()
                    else None
                ),
                "schedule_notify_on_start": _bool_from_form(data, "schedule_notify_on_start"),
                "schedule_notify_on_end": _bool_from_form(data, "schedule_notify_on_end"),
                "max_custom_scenarios": _int_from_form(data, "max_custom_scenarios", int(settings.get("max_custom_scenarios") or 30), 1, 200),
            }
        )
        normalized = _normalize_roleplay_dashboard_settings(candidate)
        if settings_row.get("id"):
            await storage.rp_settings.update(id=settings_row["id"], **normalized, updated_at=_roleplay_now_utc())
        else:
            await storage.rp_settings.insert(guild_id=guild_id, **normalized, updated_at=_roleplay_now_utc())

        if action == "apply_city_starter":
            applied_settings, scenario_count, guard_payload = await _roleplay_apply_city_starter_pack(guild_id)
            await _append_dashboard_audit_event(
                guild_id,
                session,
                "Applied city roleplay starter pack from dashboard",
                target="roleplay",
            )
            snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
            await _roleplay_append_audit(
                guild_id,
                session,
                action="apply_city_starter",
                scope="settings",
                note=(
                    "Applied city roleplay starter pack "
                    f"(preset {applied_settings.get('preset_key', 'modern_city')}, "
                    f"scenarios {scenario_count}, guard {'on' if guard_payload.get('enabled') else 'off'})"
                ),
                snapshot_before=snapshot_before,
                snapshot_after=snapshot_after,
            )
            return _redirect(
                f"City Roleplay starter pack applied. Ready with {scenario_count} scenarios and economy guard."
            )

        if action == "apply_preset":
            applied_settings, scenario_count = await _roleplay_apply_preset(
                guild_id,
                "modern_city",
            )
            await _append_dashboard_audit_event(
                guild_id,
                session,
                f"Applied roleplay preset: {applied_settings.get('preset_key', 'modern_city')}",
                target="roleplay",
            )
            snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
            await _roleplay_append_audit(
                guild_id,
                session,
                action="apply_preset",
                scope="settings",
                note=f"Applied preset {applied_settings.get('preset_key', 'modern_city')} with {scenario_count} scenarios",
                snapshot_before=snapshot_before,
                snapshot_after=snapshot_after,
            )
            return _redirect(f"City roleplay preset applied and {scenario_count} scenarios installed.")

        await _append_dashboard_audit_event(
            guild_id,
            session,
            "Updated roleplay dashboard settings",
            target="roleplay",
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="save_settings",
            scope="settings",
            note="Updated roleplay settings",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay settings saved.")

    if action == "save_permissions":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_permissions"):
            return _permission_denied("manage_permissions")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        gm_role_ids: list[str] = []
        for raw in list(form.getlist("gm_role_ids") or []):
            text = str(raw or "").strip()
            if text.isdigit() and text not in gm_role_ids:
                gm_role_ids.append(text)
        player_role_ids: list[str] = []
        for raw in list(form.getlist("player_role_ids") or []):
            text = str(raw or "").strip()
            if text.isdigit() and text not in player_role_ids:
                player_role_ids.append(text)
        action_levels: dict[str, str] = {}
        for action_key, default_level in ROLEPLAY_PERMISSION_DEFAULTS.items():
            raw_level = str(data.get(f"perm_{action_key}") or default_level).strip().lower()
            action_levels[action_key] = raw_level if raw_level in ROLEPLAY_LEVEL_RANK else default_level
        normalized = _roleplay_normalize_permissions(
            {
                "gm_role_ids": gm_role_ids,
                "player_role_ids": player_role_ids,
                "action_levels": action_levels,
            }
        )
        if permissions_row.get("id"):
            await storage.rp_permissions.update(
                id=permissions_row["id"],
                gm_role_ids=normalized["gm_role_ids"],
                player_role_ids=normalized["player_role_ids"],
                action_levels=normalized["action_levels"],
                updated_at=_roleplay_now_utc(),
            )
        else:
            await storage.rp_permissions.insert(
                guild_id=guild_id,
                gm_role_ids=normalized["gm_role_ids"],
                player_role_ids=normalized["player_role_ids"],
                action_levels=normalized["action_levels"],
                updated_at=_roleplay_now_utc(),
            )
        await _append_dashboard_audit_event(guild_id, session, "Updated roleplay permission matrix", target="roleplay")
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="save_permissions",
            scope="permissions",
            note="Updated RP role permission matrix",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay permission matrix saved.")

    if action == "save_economy_guard":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_economy_guard"):
            return _permission_denied("manage_economy_guard")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        guard_row = await _roleplay_ensure_economy_guard_row(guild_id)
        normalized_guard = _roleplay_normalize_economy_guard(
            {
                "enabled": _bool_from_form(data, "guard_enabled"),
                "max_reward_xp": _int_from_form(data, "guard_max_reward_xp", 250000, 0, 2_500_000),
                "max_reward_coins": _int_from_form(data, "guard_max_reward_coins", 250000, 0, 2_500_000),
                "inflation_threshold_avg_coins": _int_from_form(
                    data,
                    "guard_inflation_threshold_avg_coins",
                    25000,
                    1,
                    10_000_000,
                ),
                "base_reduce_percent": _int_from_form(data, "guard_base_reduce_percent", 20, 0, 95),
                "min_multiplier_percent": _int_from_form(data, "guard_min_multiplier_percent", 55, 5, 100),
                "last_multiplier_percent": int(guard_row.get("last_multiplier_percent") or 100),
            }
        )
        if guard_row.get("id"):
            await storage.rp_economy_guard.update(
                id=guard_row["id"],
                enabled=normalized_guard["enabled"],
                max_reward_xp=normalized_guard["max_reward_xp"],
                max_reward_coins=normalized_guard["max_reward_coins"],
                inflation_threshold_avg_coins=normalized_guard["inflation_threshold_avg_coins"],
                base_reduce_percent=normalized_guard["base_reduce_percent"],
                min_multiplier_percent=normalized_guard["min_multiplier_percent"],
                last_multiplier_percent=normalized_guard["last_multiplier_percent"],
                updated_at=_roleplay_now_utc(),
            )
        else:
            await storage.rp_economy_guard.insert(guild_id=guild_id, **normalized_guard, updated_at=_roleplay_now_utc())
        await _append_dashboard_audit_event(guild_id, session, "Updated roleplay economy guard", target="roleplay")
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="save_economy_guard",
            scope="economy_guard",
            note="Updated RP economy balance guard",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay economy guard saved.")

    if action == "add_scenario":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="add_scenario"):
            return _permission_denied("add_scenario")
        if not bool(settings.get("allow_custom_scenarios")):
            return _redirect("Custom scenarios are disabled for this server.")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        scenario_name = str(data.get("scenario_name") or "").strip()[:120]
        scenario_description = str(data.get("scenario_description") or "").strip()[:800]
        if not scenario_name:
            return _redirect("Scenario name is required.")
        all_rows = await storage.rp_scenarios.gets(guild_id=guild_id) or []
        custom_rows = [row for row in all_rows if isinstance(row, dict) and not bool(row.get("is_preset"))]
        max_custom = int(settings.get("max_custom_scenarios") or 30)
        if len(custom_rows) >= max_custom:
            return _redirect(f"Custom scenario limit reached ({max_custom}).")
        base_key = _roleplay_slugify(scenario_name, fallback="scenario")
        scenario_key = f"custom_{base_key[:28]}"
        suffix = 2
        while await storage.rp_scenarios.get(guild_id=guild_id, scenario_key=scenario_key):
            scenario_key = f"custom_{base_key[:24]}_{suffix}"
            suffix += 1

        difficulty = str(data.get("scenario_difficulty") or "normal").strip().lower()
        if difficulty not in {"easy", "normal", "hard"}:
            difficulty = "normal"
        reward_xp = _int_from_form(data, "scenario_reward_xp", 70, 0, 500_000)
        reward_coins = _int_from_form(data, "scenario_reward_coins", 150, 0, 500_000)
        await _roleplay_upsert_scenario(
            guild_id,
            scenario_key=scenario_key,
            name=scenario_name,
            description=scenario_description,
            template_key="custom",
            difficulty=difficulty,
            reward_xp=reward_xp,
            reward_coins=reward_coins,
            is_preset=False,
        )
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Created roleplay scenario: {scenario_name}",
            target="roleplay",
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="add_scenario",
            scope="scenario",
            note=f"Created scenario {scenario_name}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Custom scenario created.")

    if action == "delete_scenario":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="delete_scenario"):
            return _permission_denied("delete_scenario")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        scenario_id_raw = str(data.get("delete_scenario_id") or "").strip()
        if not scenario_id_raw.isdigit():
            return _redirect("Please select a custom scenario to delete.")
        target = await storage.rp_scenarios.get(id=int(scenario_id_raw), guild_id=guild_id)
        if not target:
            return _redirect("Scenario not found.")
        if bool(target.get("is_preset")):
            return _redirect("Preset scenarios cannot be deleted.")
        await storage.rp_scenarios.delete(id=int(scenario_id_raw))
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Deleted roleplay scenario: {target.get('name', 'scenario')}",
            target="roleplay",
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="delete_scenario",
            scope="scenario",
            note=f"Deleted scenario {target.get('name', 'scenario')}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Scenario deleted.")

    if action == "start_event":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="start_event"):
            return _permission_denied("start_event")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        scenario_id_raw = str(data.get("event_scenario_id") or "").strip()
        event_row = await storage.rp_events.get(guild_id=guild_id) or {}
        if str(event_row.get("status") or "").strip().lower() == "active":
            return _redirect("There is already an active roleplay event.")

        scenario_row = None
        if scenario_id_raw.isdigit():
            scenario_row = await storage.rp_scenarios.get(id=int(scenario_id_raw), guild_id=guild_id)
        if not scenario_row:
            scenario_rows = await storage.rp_scenarios.gets(guild_id=guild_id) or []
            scenario_row = next(
                (
                    row
                    for row in scenario_rows
                    if isinstance(row, dict) and bool(row.get("is_enabled", True))
                ),
                None,
            )
        if not scenario_row:
            return _redirect("No scenario available for event start.")

        minutes = _int_from_form(data, "event_minutes", 30, 5, 180)
        now = _roleplay_now_utc()
        reward_xp = _int_from_form(
            data,
            "event_reward_xp",
            max(int(settings.get("event_reward_xp") or 120), int(scenario_row.get("reward_xp") or 0)),
            0,
            500_000,
        )
        reward_coins = _int_from_form(
            data,
            "event_reward_coins",
            max(int(settings.get("event_reward_coins") or 220), int(scenario_row.get("reward_coins") or 0)),
            0,
            500_000,
        )
        session_user_id_raw = str((session.get("user") or {}).get("id") or "").strip() if isinstance(session, dict) else ""
        started_by = int(session_user_id_raw) if session_user_id_raw.isdigit() else 0
        payload = {
            "guild_id": guild_id,
            "status": "active",
            "event_title": str(scenario_row.get("name") or "Roleplay Event"),
            "template_key": str(scenario_row.get("scenario_key") or ""),
            "description": str(scenario_row.get("description") or ""),
            "reward_xp": reward_xp,
            "reward_coins": reward_coins,
            "participants": [],
            "started_by": started_by,
            "trigger_type": "manual_dashboard_start",
            "schedule_name": "",
            "started_at": now,
            "ends_at": now + datetime.timedelta(minutes=minutes),
            "updated_at": now,
        }
        if event_row.get("id"):
            await storage.rp_events.update(id=event_row["id"], **payload)
        else:
            await storage.rp_events.insert(**payload)
        await _roleplay_track_scenario_stats(
            guild_id,
            scenario_key=str(scenario_row.get("scenario_key") or ""),
            scenario_name=str(scenario_row.get("name") or "Scenario"),
            event_start_delta=1,
        )
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Started roleplay event: {payload['event_title']}",
            target="roleplay",
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="start_event",
            scope="event",
            note=f"Started event {payload['event_title']}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay event started.")

    if action == "end_event":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="end_event"):
            return _permission_denied("end_event")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        event_row = await storage.rp_events.get(guild_id=guild_id) or {}
        if str(event_row.get("status") or "").strip().lower() != "active":
            return _redirect("No active roleplay event found.")
        result = await _roleplay_finish_event_and_reward(
            guild_id,
            event_row,
            settings,
            trigger_type="manual_dashboard",
        )
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Ended roleplay event and rewarded {int(result.get('rewarded') or 0)} participants",
            target="roleplay",
        )
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="end_event",
            scope="event",
            note=(
                f"Ended event with {int(result.get('rewarded') or 0)} rewards, "
                f"multiplier {int(result.get('guard_multiplier_percent') or 100)}%"
            ),
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(
            f"Event ended. Rewarded {int(result.get('rewarded') or 0)} participants "
            f"({int(result.get('reward_xp') or 0)} XP / {int(result.get('reward_coins') or 0)} coins)."
        )

    if action == "add_schedule":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_scheduler"):
            return _permission_denied("manage_scheduler")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        normalized_schedule = _roleplay_normalize_schedule(
            {
                "schedule_name": data.get("schedule_name"),
                "enabled": True,
                "frequency": data.get("schedule_frequency"),
                "weekday": _int_from_form(data, "schedule_weekday", 0, 0, 6),
                "hour": _int_from_form(data, "schedule_hour", 20, 0, 23),
                "minute": _int_from_form(data, "schedule_minute", 0, 0, 59),
                "timezone_offset_minutes": _int_from_form(data, "schedule_timezone_offset_minutes", 420, -720, 840),
                "duration_minutes": _int_from_form(data, "schedule_duration_minutes", 30, 5, 180),
                "scenario_key": data.get("schedule_scenario_key"),
            }
        )
        existing = await storage.rp_schedules.get(guild_id=guild_id, schedule_name=normalized_schedule["schedule_name"])
        if existing:
            suffix = 2
            base_name = normalized_schedule["schedule_name"][:66]
            while await storage.rp_schedules.get(guild_id=guild_id, schedule_name=f"{base_name}_{suffix}"):
                suffix += 1
            normalized_schedule["schedule_name"] = f"{base_name}_{suffix}"
        next_run = _roleplay_schedule_next_run_utc(
            frequency=normalized_schedule["frequency"],
            weekday=normalized_schedule["weekday"],
            hour=normalized_schedule["hour"],
            minute=normalized_schedule["minute"],
            timezone_offset_minutes=normalized_schedule["timezone_offset_minutes"],
            from_utc=_roleplay_now_utc(),
        )
        await storage.rp_schedules.insert(
            guild_id=guild_id,
            schedule_name=normalized_schedule["schedule_name"],
            enabled=True,
            frequency=normalized_schedule["frequency"],
            weekday=normalized_schedule["weekday"],
            hour=normalized_schedule["hour"],
            minute=normalized_schedule["minute"],
            timezone_offset_minutes=normalized_schedule["timezone_offset_minutes"],
            duration_minutes=normalized_schedule["duration_minutes"],
            scenario_id=normalized_schedule["scenario_id"],
            scenario_key=normalized_schedule["scenario_key"],
            reward_xp_override=normalized_schedule["reward_xp_override"],
            reward_coins_override=normalized_schedule["reward_coins_override"],
            next_run_at=next_run,
            updated_at=_roleplay_now_utc(),
        )
        await _append_dashboard_audit_event(guild_id, session, "Created roleplay auto event schedule", target="roleplay")
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="add_schedule",
            scope="scheduler",
            note=f"Created schedule {normalized_schedule['schedule_name']}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay schedule created.")

    if action == "toggle_schedule":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_scheduler"):
            return _permission_denied("manage_scheduler")
        schedule_id_raw = str(data.get("schedule_id") or "").strip()
        if not schedule_id_raw.isdigit():
            return _redirect("Schedule not found.")
        row = await storage.rp_schedules.get(id=int(schedule_id_raw), guild_id=guild_id)
        if not row:
            return _redirect("Schedule not found.")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        enabled_next = not bool(row.get("enabled"))
        next_run = row.get("next_run_at")
        if enabled_next:
            normalized_row = _roleplay_normalize_schedule(row)
            next_run = _roleplay_schedule_next_run_utc(
                frequency=normalized_row["frequency"],
                weekday=normalized_row["weekday"],
                hour=normalized_row["hour"],
                minute=normalized_row["minute"],
                timezone_offset_minutes=normalized_row["timezone_offset_minutes"],
                from_utc=_roleplay_now_utc(),
            )
        await storage.rp_schedules.update(
            id=row["id"],
            enabled=enabled_next,
            next_run_at=next_run,
            updated_at=_roleplay_now_utc(),
        )
        await _append_dashboard_audit_event(guild_id, session, "Updated roleplay schedule state", target="roleplay")
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="toggle_schedule",
            scope="scheduler",
            note=f"{'Enabled' if enabled_next else 'Disabled'} schedule {row.get('schedule_name', row['id'])}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay schedule updated.")

    if action == "delete_schedule":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="manage_scheduler"):
            return _permission_denied("manage_scheduler")
        schedule_id_raw = str(data.get("schedule_id") or "").strip()
        if not schedule_id_raw.isdigit():
            return _redirect("Schedule not found.")
        row = await storage.rp_schedules.get(id=int(schedule_id_raw), guild_id=guild_id)
        if not row:
            return _redirect("Schedule not found.")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await storage.rp_schedules.delete(id=int(schedule_id_raw))
        await _append_dashboard_audit_event(guild_id, session, "Deleted roleplay schedule", target="roleplay")
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="delete_schedule",
            scope="scheduler",
            note=f"Deleted schedule {row.get('schedule_name', row['id'])}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay schedule deleted.")

    if action == "import_config":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="import_config"):
            return _permission_denied("import_config")
        json_payload = str(data.get("import_json_payload") or "").strip()
        import_file = form.get("import_json_file")
        if not json_payload and import_file and hasattr(import_file, "read"):
            try:
                file_bytes = await import_file.read()
                json_payload = file_bytes.decode("utf-8", errors="ignore").strip()
            except Exception:
                json_payload = ""
        if not json_payload:
            return _redirect("Please provide JSON payload or upload JSON file.")
        try:
            parsed = json.loads(json_payload)
        except Exception:
            return _redirect("Invalid JSON payload.")
        if not isinstance(parsed, dict):
            return _redirect("Invalid RP config format.")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_apply_snapshot(guild_id, parsed)
        await _append_dashboard_audit_event(guild_id, session, "Imported roleplay config", target="roleplay")
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_append_audit(
            guild_id,
            session,
            action="import_config",
            scope="import",
            note="Imported RP configuration snapshot",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect("Roleplay config imported.")

    if action == "rollback":
        if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="rollback"):
            return _permission_denied("rollback")
        audit_id_raw = str(data.get("audit_id") or "").strip()
        if not audit_id_raw.isdigit():
            return _redirect("Invalid audit log selected.")
        target_log = await storage.rp_audit_logs.get(id=int(audit_id_raw), guild_id=guild_id)
        if not target_log:
            return _redirect("Audit log not found.")
        snapshot_target = target_log.get("snapshot_before") if isinstance(target_log.get("snapshot_before"), dict) else {}
        if not snapshot_target:
            snapshot_target = target_log.get("snapshot_after") if isinstance(target_log.get("snapshot_after"), dict) else {}
        if not snapshot_target:
            return _redirect("Selected audit log has no rollback snapshot.")
        snapshot_before = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _roleplay_apply_snapshot(guild_id, snapshot_target)
        snapshot_after = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
        await _append_dashboard_audit_event(
            guild_id,
            session,
            f"Rolled back roleplay using audit #{audit_id_raw}",
            target="roleplay",
        )
        await _roleplay_append_audit(
            guild_id,
            session,
            action="rollback",
            scope="rollback",
            note=f"Rollback executed from audit #{audit_id_raw}",
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
        )
        return _redirect(f"Rollback completed from audit #{audit_id_raw}.")

    return _redirect("Unknown action.")


async def update_guildstyle_studio_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="guildstyle_studio",
    )
    if blocked_response:
        return blocked_response

    form = await request.form()
    data: dict[str, str] = {}
    for key, value in form.items():
        if hasattr(value, "filename"):
            continue
        data[str(key)] = str(value)

    action = str(data.get("action") or "").strip().lower()

    def _redirect(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/guildstyle_studio?notice={urlencode({'notice': message}).split('=', 1)[1]}",
            status_code=303,
        )

    permissions_row = await _roleplay_ensure_permissions_row(guild_id)
    normalized_permissions = _roleplay_normalize_permissions(permissions_row)
    actor_level = _roleplay_actor_level(
        session=session,
        current_guild=current_guild,
        bot_guild=get_bot().get_guild(guild_id) if get_bot() else None,
        state=state,
        permissions_row=permissions_row,
    )
    guildstyle_action_response = await _handle_roleplay_guildstyle_studio_actions(
        guild_id=guild_id,
        action=action,
        data=data,
        form_data=form,
        session=session,
        permissions_row=permissions_row,
        normalized_permissions=normalized_permissions,
        actor_level=actor_level,
        redirect_tab="guildstyle_studio",
    )
    if guildstyle_action_response:
        return guildstyle_action_response
    return _redirect("Unknown action.")


async def export_roleplay_config(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="roleplay",
    )
    if blocked_response:
        return blocked_response

    permissions_row = await _roleplay_ensure_permissions_row(guild_id)
    actor_level = _roleplay_actor_level(
        session=session,
        current_guild=current_guild,
        bot_guild=get_bot().get_guild(guild_id) if get_bot() else None,
        state=state,
        permissions_row=permissions_row,
    )
    if not _roleplay_can_action(actor_level=actor_level, permissions_row=permissions_row, action_key="export_config"):
        required = _roleplay_normalize_permissions(permissions_row)["action_levels"].get("export_config", "owner")
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/roleplay?notice={urlencode({'notice': f'Permission denied: export requires {required.upper()} level.'}).split('=',1)[1]}",
            status_code=303,
        )

    snapshot = await _roleplay_export_snapshot(guild_id, include_runtime_event=True)
    filename = f"roleplay_config_guild_{int(guild_id)}.json"
    return Response(
        content=json.dumps(
            snapshot,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.isoformat() if isinstance(value, datetime.datetime) else str(value),
        ),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


async def update_reaction_roles_settings(request: Request, guild_id: int):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="reaction_roles",
    )
    if blocked_response:
        return blocked_response

    await _ensure_dashboard_config_cache()
    data = await _parse_form(request)
    items_payload: list[dict[str, Any]] = []
    try:
        decoded_items = json.loads(data.get("items_json", "[]"))
        if isinstance(decoded_items, list):
            items_payload = decoded_items
    except Exception:
        items_payload = []

    payload = _normalize_reaction_roles_settings(
        {
            "enabled": _bool_from_form(data, "enabled"),
            "selection_mode": str(data.get("selection_mode", "single") or "single").strip().lower(),
            "items": items_payload,
        }
    )

    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict((state or {}).get("guild") or {})
    guild_state_for_plan["subscription"] = plan_tier
    plan_limits = _plan_limits_from_guild_state(guild_state_for_plan)
    max_reaction_role_bindings = max(1, min(100, int(plan_limits.get("reaction_roles", 10) or 10)))

    trimmed_count = 0
    kept_total = 0
    trimmed_items: list[dict[str, Any]] = []
    for item in list(payload.get("items") or []):
        row = dict(item or {})
        options = row.get("options") if isinstance(row.get("options"), list) else []
        kept_options: list[dict[str, Any]] = []
        for option in options:
            if kept_total >= max_reaction_role_bindings:
                trimmed_count += 1
                continue
            kept_options.append(option if isinstance(option, dict) else {})
            kept_total += 1
        if not kept_options:
            continue
        row["options"] = kept_options
        mode = str(row.get("selection_mode") or "single").strip().lower()
        if mode != "multiple":
            row["selection_mode"] = "single"
            row["max_select"] = 1
        else:
            try:
                max_select_value = int(row.get("max_select") or 1)
            except Exception:
                max_select_value = 1
            row["max_select"] = max(1, min(25, len(kept_options), max_select_value))
        trimmed_items.append(row)
    payload["items"] = trimmed_items

    await _set_dashboard_config_value(
        _reaction_roles_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตบทบาทรีแอ็กชันแล้ว", target="reaction_roles")
    if trimmed_count > 0:
        notice_text = f"บันทึก Reaction Roles แล้ว (ปรับตามแพลน: เหลือ {max_reaction_role_bindings} บทบาท)"
    else:
        notice_text = "บันทึก Reaction Roles แล้ว"
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/reaction_roles?notice={urlencode({'notice': notice_text}).split('=',1)[1]}",
        status_code=303,
    )

async def update_starboard_settings(request: Request, guild_id: int):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="starboard",
    )
    if blocked_response:
        return blocked_response

    await _ensure_dashboard_config_cache()
    form = await request.form()
    data = {
        key: str(value)
        for key, value in form.items()
        if key not in {"embed_author_icon_file", "embed_thumbnail_file", "embed_image_file", "embed_footer_icon_file"}
    }
    uploaded_field_map = {
        "embed_author_icon_file": "embed_author_icon_url",
        "embed_thumbnail_file": "embed_thumbnail_url",
        "embed_image_file": "embed_image_url",
        "embed_footer_icon_file": "embed_footer_icon_url",
    }
    uploaded_kind_map = {
        "embed_author_icon_file": "icon",
        "embed_thumbnail_file": "thumbnail",
        "embed_image_file": "image",
        "embed_footer_icon_file": "icon",
    }
    starboard_upload_channels = _collect_channel_ids_for_upload(
        data.get("channel_id"),
        data.get("enabled_channel_id"),
    )
    for upload_key, target_key in uploaded_field_map.items():
        uploaded = form.get(upload_key)
        if not uploaded or not getattr(uploaded, "filename", None):
            continue
        try:
            raw_bytes = await uploaded.read()
            if not raw_bytes:
                continue
            uploaded_url = await _upload_image_to_discord_cdn(
                guild_id,
                raw_bytes=raw_bytes,
                filename=str(getattr(uploaded, "filename", "starboard.png")),
                preferred_channel_ids=starboard_upload_channels,
                upload_target="starboard",
                asset_kind=uploaded_kind_map.get(upload_key),
                request=request,
                uploader_id=int(_session_user_id(session) or 0),
                source_route=str(getattr(request.url, "path", "") or ""),
                source_field=upload_key,
            )
            if uploaded_url:
                data[target_key] = uploaded_url
        except Exception:
            continue
    fields_payload: list[dict[str, Any]] = []
    try:
        decoded_fields = json.loads(data.get("fields_json", "[]"))
        if isinstance(decoded_fields, list):
            fields_payload = decoded_fields
    except Exception:
        fields_payload = []
    payload = _normalize_starboard_settings(
        {
            "enabled": _bool_from_form(data, "enabled"),
            "active": _bool_from_form(data, "active"),
            "name": data.get("name", ""),
            "enabled_channel_id": data.get("enabled_channel_id", ""),
            "channel_id": data.get("channel_id", ""),
            "required_role_id": data.get("required_role_id", ""),
            "stars_limit": data.get("stars_limit", "3"),
            "custom_emoji": data.get("custom_emoji", ""),
            "message_mode": data.get("message_mode", ""),
            "message_template": data.get("message_template", ""),
            "embed_author_name": data.get("embed_author_name", ""),
            "embed_author_url": data.get("embed_author_url", ""),
            "embed_author_icon_url": data.get("embed_author_icon_url", ""),
            "embed_title": data.get("embed_title", ""),
            "embed_description": data.get("embed_description", ""),
            "embed_thumbnail_url": data.get("embed_thumbnail_url", ""),
            "embed_image_url": data.get("embed_image_url", ""),
            "embed_footer_text": data.get("embed_footer_text", ""),
            "embed_footer_icon_url": data.get("embed_footer_icon_url", ""),
            "fields": fields_payload,
            "color": data.get("color", ""),
            "ignore_self_stars": _bool_from_form(data, "ignore_self_stars"),
            "react_to_starboard_post": _bool_from_form(data, "react_to_starboard_post"),
        }
    )
    await _set_dashboard_config_value(
        _starboard_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดต Starboard แล้ว", target="starboard")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/starboard?notice={urlencode({'notice': 'บันทึกการตั้งค่า Starboard แล้ว'}).split('=',1)[1]}",
        status_code=303,
    )

async def update_embed_messages_settings(request: Request, guild_id: int):
    session, guilds, current_guild, state = await _require_dashboard_context(request, guild_id)
    blocked_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="embed_messages",
    )
    if blocked_response:
        return blocked_response

    await _ensure_dashboard_config_cache()
    form = await request.form()
    data = {
        key: str(value)
        for key, value in form.items()
        if key not in {"embed_author_icon_file", "embed_thumbnail_file", "embed_image_file", "embed_footer_icon_file"}
    }
    items_payload: list[dict[str, Any]] = []
    try:
        decoded_items = json.loads(data.get("items_json", "[]"))
        if isinstance(decoded_items, list):
            items_payload = decoded_items
    except Exception:
        items_payload = []
    selected_id = str(data.get("selected_id") or "").strip()
    if items_payload and selected_id:
        selected_item = None
        for row in items_payload:
            if isinstance(row, dict) and str(row.get("id") or "") == selected_id:
                selected_item = row
                break
        if isinstance(selected_item, dict):
            upload_map = {
                "embed_author_icon_file": "author_icon_url",
                "embed_thumbnail_file": "thumbnail_url",
                "embed_image_file": "image_url",
                "embed_footer_icon_file": "footer_icon_url",
            }
            upload_kind_map = {
                "embed_author_icon_file": "icon",
                "embed_thumbnail_file": "thumbnail",
                "embed_image_file": "image",
                "embed_footer_icon_file": "icon",
            }
            for upload_key, item_key in upload_map.items():
                uploaded = form.get(upload_key)
                if not uploaded or not getattr(uploaded, "filename", None):
                    continue
                try:
                    raw_bytes = await uploaded.read()
                    if not raw_bytes:
                        continue
                    embed_upload_channels = _collect_channel_ids_for_upload(
                        selected_item.get("channel_id"),
                        data.get("channel_id"),
                    )
                    uploaded_url = await _upload_image_to_discord_cdn(
                        guild_id,
                        raw_bytes=raw_bytes,
                        filename=str(getattr(uploaded, "filename", "embed.png")),
                        preferred_channel_ids=embed_upload_channels,
                        upload_target="embed_messages",
                        asset_kind=upload_kind_map.get(upload_key),
                        request=request,
                        uploader_id=int(_session_user_id(session) or 0),
                        source_route=str(getattr(request.url, "path", "") or ""),
                        source_field=upload_key,
                    )
                    if uploaded_url:
                        selected_item[item_key] = uploaded_url
                except Exception:
                    continue

    payload = _normalize_embed_messages_settings(
        {
            "enabled": True,
            "selected_id": selected_id,
            "items": items_payload,
        }
    )
    await _set_dashboard_config_value(
        _embed_messages_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดต Embed Messages แล้ว", target="embed_messages")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/embed_messages?notice={urlencode({'notice': 'บันทึก Embed Messages แล้ว'}).split('=',1)[1]}",
        status_code=303,
    )

async def send_embed_message_from_dashboard(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"ok": False, "message": blocked_notice}, status_code=403)
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="embed_messages")
    if tab_block_reason:
        return JSONResponse({"ok": False, "message": tab_block_reason}, status_code=403)

    data = await _parse_form(request)
    selected_id = str(data.get("selected_id") or "").strip()
    items_payload: list[dict[str, Any]] = []
    try:
        decoded_items = json.loads(data.get("items_json", "[]"))
        if isinstance(decoded_items, list):
            items_payload = decoded_items
    except Exception:
        items_payload = []
    settings_payload = _normalize_embed_messages_settings(
        {
            "enabled": True,
            "selected_id": selected_id,
            "items": items_payload,
        }
    )
    items = settings_payload.get("items") if isinstance(settings_payload.get("items"), list) else []
    selected_item = None
    for item in items:
        if str(item.get("id") or "") == selected_id:
            selected_item = item
            break
    if not selected_item:
        return JSONResponse({"ok": False, "message": "ไม่พบ Embed ที่เลือก"}, status_code=400)

    override_channel_id = str(data.get("send_channel_id") or "").strip()
    if override_channel_id and not override_channel_id.isdigit():
        return JSONResponse({"ok": False, "message": "รหัสห้องไม่ถูกต้อง"}, status_code=400)

    channel_id = override_channel_id if override_channel_id else str(selected_item.get("channel_id") or "").strip()
    if not channel_id.isdigit():
        return JSONResponse({"ok": False, "message": "กรุณาเลือกห้องข้อความ"}, status_code=400)

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return JSONResponse({"ok": False, "message": "ไม่พบกิลด์นี้ในระบบบอท"}, status_code=404)
    channel = bot_guild.get_channel(int(channel_id))
    if not channel or not hasattr(channel, "send"):
        return JSONResponse({"ok": False, "message": "บอทไม่สามารถเข้าถึงห้องที่เลือกได้"}, status_code=400)

    content = str(selected_item.get("content") or "")[:4000]
    color_value = _normalize_color_hex(selected_item.get("color"), "#5865F2")
    embed = discord.Embed(
        title=str(selected_item.get("title") or "").strip() or None,
        description=str(selected_item.get("description") or "")[:4000] or None,
        color=int(color_value[1:], 16),
    )
    author_name = str(selected_item.get("author_name") or "").strip()
    if author_name:
        embed.set_author(
            name=author_name,
            url=str(selected_item.get("author_url") or "").strip() or None,
            icon_url=str(selected_item.get("author_icon_url") or "").strip() or None,
        )
    thumbnail_url = str(selected_item.get("thumbnail_url") or "").strip()
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    image_url = str(selected_item.get("image_url") or "").strip()
    if image_url:
        embed.set_image(url=image_url)
    footer_text = str(selected_item.get("footer_text") or "")[:2048]
    if footer_text:
        embed.set_footer(
            text=footer_text,
            icon_url=str(selected_item.get("footer_icon_url") or "").strip() or None,
        )
    fields = selected_item.get("fields")
    if isinstance(fields, list):
        for field in fields[:25]:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()[:256]
            value = str(field.get("value") or "").strip()[:1024]
            if not name and not value:
                continue
            embed.add_field(name=name or "หัวข้อ", value=value or "-", inline=bool(field.get("inline", False)))

    embed_is_empty = not bool(embed.title or embed.description or embed.fields or embed.author or embed.footer or embed.thumbnail or embed.image)
    if not content.strip() and embed_is_empty:
        return JSONResponse({"ok": False, "message": "ไม่มีเนื้อหา กรุณากรอกข้อความหรือ Embed"}, status_code=400)
    try:
        await channel.send(content=content if content.strip() else None, embed=None if embed_is_empty else embed)
    except Exception as error:
        return JSONResponse({"ok": False, "message": f"ส่งข้อความไม่สำเร็จ: {error}"}, status_code=500)

    return JSONResponse({"ok": True, "message": "ส่ง Embed สำเร็จแล้ว"})

async def add_autoresponder(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(state.get("guild") or {})
    guild_state_for_plan["subscription"] = plan_tier
    limits = _plan_limits_from_guild_state(guild_state_for_plan)
    responders = state.get("auto_responder") or []
    if len(responders) >= int(limits["auto_responders"]):
        message = f"แพ็กเกจนี้เพิ่มระบบตอบกลับอัตโนมัติได้สูงสุด {limits['auto_responders']} รายการ"
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/autoresponder?notice={urlencode({'notice': message}).split('=',1)[1]}",
            status_code=303,
        )
    data = await _parse_form(request)
    keyword = data.get("keyword", "").strip()
    response = data.get("response", "").strip()
    if keyword and response:
        await storage.auto_responder.insert(guild_id=guild_id, keyword=keyword, response=response)
        await _append_dashboard_audit_event(guild_id, session, f"เพิ่มระบบตอบกลับอัตโนมัติ ({keyword[:32]})", target="autoresponder")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/autoresponder?notice={urlencode({'notice': 'เพิ่มคีย์เวิร์ดตอบกลับแล้ว'}).split('=',1)[1]}", status_code=303)

async def delete_autoresponder(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    data = await _parse_form(request)
    res_id = data.get("id")
    if res_id:
        await storage.auto_responder.delete(id=int(res_id))
        await _append_dashboard_audit_event(guild_id, session, f"ลบระบบตอบกลับอัตโนมัติ #{res_id}", target="autoresponder")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/autoresponder?notice={urlencode({'notice': 'ลบคีย์เวิร์ดตอบกลับแล้ว'}).split('=',1)[1]}", status_code=303)

async def add_customrole(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(state.get("guild") or {})
    guild_state_for_plan["subscription"] = plan_tier
    limits = _plan_limits_from_guild_state(guild_state_for_plan)
    roles_data = state.get("custom_roles") or []
    if len(roles_data) >= int(limits["custom_roles"]):
        message = f"แพ็กเกจนี้เพิ่มบทบาทพิเศษได้สูงสุด {limits['custom_roles']} รายการ"
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': message}).split('=',1)[1]}",
            status_code=303,
        )
    data = await _parse_form(request)
    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบกิลด์ในบอทที่กำลังรันอยู่'}).split('=',1)[1]}",
            status_code=303,
        )

    raw_name = str(data.get("name", "") or "").strip().lower()
    role_id = str(data.get("role_id", "") or "").strip()
    if not raw_name or not role_id.isdigit():
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'กรอกคีย์คำสั่งและเลือกยศก่อนบันทึก'}).split('=',1)[1]}",
            status_code=303,
        )
    if not re.fullmatch(r"[a-z0-9_-]{2,32}", raw_name):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'คีย์คำสั่งต้องเป็น a-z, 0-9, _ หรือ - ความยาว 2-32 ตัว'}).split('=',1)[1]}",
            status_code=303,
        )
    if bot.get_command(raw_name):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': f'คีย์ `{raw_name}` ซ้ำกับคำสั่งหลักของบอท'}).split('=',1)[1]}",
            status_code=303,
        )

    duplicate = next((row for row in roles_data if str(row.get("name") or "").strip().lower() == raw_name), None)
    if duplicate:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': f'มีคีย์คำสั่ง `{raw_name}` อยู่แล้ว'}).split('=',1)[1]}",
            status_code=303,
        )

    role_obj = bot_guild.get_role(int(role_id))
    if not role_obj:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบบทบาทที่เลือก'}).split('=',1)[1]}",
            status_code=303,
        )
    if role_obj.permissions.administrator:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'บทบาทที่มีสิทธิ์ Administrator ใช้เป็น Custom Role ไม่ได้'}).split('=',1)[1]}",
            status_code=303,
        )

    await storage.custom_roles.insert(guild_id=guild_id, name=raw_name, role_id=int(role_id))
    await _append_dashboard_audit_event(guild_id, session, f"เพิ่มบทบาทพิเศษ ({raw_name[:32]})", target="customrole")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'เพิ่มรายการบทบาทพิเศษแล้ว'}).split('=',1)[1]}", status_code=303)

async def update_customrole(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    data = await _parse_form(request)
    row_id = str(data.get("id", "") or "").strip()
    raw_name = str(data.get("name", "") or "").strip().lower()
    role_id = str(data.get("role_id", "") or "").strip()
    if not row_id.isdigit():
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบรายการที่ต้องการแก้ไข'}).split('=',1)[1]}",
            status_code=303,
        )
    if not raw_name or not role_id.isdigit():
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'กรอกคีย์คำสั่งและเลือกยศก่อนบันทึก'}).split('=',1)[1]}",
            status_code=303,
        )
    if not re.fullmatch(r"[a-z0-9_-]{2,32}", raw_name):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'คีย์คำสั่งต้องเป็น a-z, 0-9, _ หรือ - ความยาว 2-32 ตัว'}).split('=',1)[1]}",
            status_code=303,
        )

    roles_data = state.get("custom_roles") or []
    target = next((row for row in roles_data if int(row.get("id") or 0) == int(row_id)), None)
    if not target:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบรายการที่ต้องการแก้ไข'}).split('=',1)[1]}",
            status_code=303,
        )

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบกิลด์ในบอทที่กำลังรันอยู่'}).split('=',1)[1]}",
            status_code=303,
        )

    if bot.get_command(raw_name):
        current_name = str(target.get("name") or "").strip().lower()
        if raw_name != current_name:
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': f'คีย์ `{raw_name}` ซ้ำกับคำสั่งหลักของบอท'}).split('=',1)[1]}",
                status_code=303,
            )

    duplicate = next(
        (
            row for row in roles_data
            if int(row.get("id") or 0) != int(row_id)
            and str(row.get("name") or "").strip().lower() == raw_name
        ),
        None,
    )
    if duplicate:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': f'มีคีย์คำสั่ง `{raw_name}` อยู่แล้ว'}).split('=',1)[1]}",
            status_code=303,
        )

    role_obj = bot_guild.get_role(int(role_id))
    if not role_obj:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบบทบาทที่เลือก'}).split('=',1)[1]}",
            status_code=303,
        )
    if role_obj.permissions.administrator:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'บทบาทที่มีสิทธิ์ Administrator ใช้เป็น Custom Role ไม่ได้'}).split('=',1)[1]}",
            status_code=303,
        )

    await storage.custom_roles.update(
        id=int(row_id),
        guild_id=guild_id,
        name=raw_name,
        role_id=int(role_id),
    )
    await _append_dashboard_audit_event(guild_id, session, f"แก้ไขบทบาทพิเศษ ({raw_name[:32]})", target="customrole")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'บันทึกรายการบทบาทพิเศษแล้ว'}).split('=',1)[1]}", status_code=303)

async def set_customrole_required_role(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    data = await _parse_form(request)
    required_role_id = str(data.get("required_role_id", "") or "").strip()
    if not required_role_id.isdigit():
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'กรุณาเลือกยศก่อนบันทึก Required Role'}).split('=',1)[1]}",
            status_code=303,
        )

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบกิลด์ในบอทที่กำลังรันอยู่'}).split('=',1)[1]}",
            status_code=303,
        )
    role_obj = bot_guild.get_role(int(required_role_id))
    if not role_obj:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่พบบทบาทที่เลือก'}).split('=',1)[1]}",
            status_code=303,
        )
    if role_obj.is_default():
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ไม่สามารถใช้ @everyone เป็น Required Role ได้'}).split('=',1)[1]}",
            status_code=303,
        )

    current = state.get("custom_roles_permission") or await storage.custom_roles_permissions.get(guild_id=guild_id) or {}
    if current.get("id"):
        await storage.custom_roles_permissions.update(id=int(current.get("id")), guild_id=guild_id, required_role_id=int(required_role_id))
    else:
        await storage.custom_roles_permissions.insert(guild_id=guild_id, required_role_id=int(required_role_id))
    await _append_dashboard_audit_event(guild_id, session, f"ตั้ง Required Role ของ Custom Role เป็น {role_obj.name}", target="customrole")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'บันทึก Required Role แล้ว'}).split('=',1)[1]}", status_code=303)

async def clear_customrole_required_role(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    await storage.custom_roles_permissions.delete(guild_id=guild_id)
    await _append_dashboard_audit_event(guild_id, session, "ล้าง Required Role ของ Custom Role", target="customrole")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ล้าง Required Role แล้ว'}).split('=',1)[1]}", status_code=303)

async def delete_customrole(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    data = await _parse_form(request)
    res_id = str(data.get("id", "") or "").strip()
    if res_id.isdigit():
        await storage.custom_roles.delete(id=int(res_id))
        await _append_dashboard_audit_event(guild_id, session, f"ลบบทบาทพิเศษ #{res_id}", target="customrole")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/customrole?notice={urlencode({'notice': 'ลบรายการบทบาทพิเศษแล้ว'}).split('=',1)[1]}", status_code=303)

async def update_music_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(state.get("guild") or {})
    guild_state_for_plan["subscription"] = plan_tier
    if not _can_manage_music_settings(guild_state_for_plan):
        message = "แพ็กเกจฟรียังไม่สามารถจัดการการตั้งค่าเพลงได้"
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/music?notice={urlencode({'notice': message}).split('=',1)[1]}",
            status_code=303,
        )
    data = await _parse_form(request)
    volume = max(0, min(100, int(data.get("default_volume", 80) or 80)))
    setup_mode_enabled = _bool_from_form(data, "setup_music_mode")
    setup_channel_id = data.get("music_command_channel_id") if setup_mode_enabled else None
    setup_voice_id = data.get("music_voice_channel_id") if setup_mode_enabled else None
    music_usage_role_ids = parse_entity_id_list(data.get("music_usage_role_ids"))
    music_usage_user_ids = parse_entity_id_list(data.get("music_usage_user_ids"))
    music_usage_channel_ids = parse_entity_id_list(data.get("music_usage_channel_ids"))
    music_usage_enabled = _bool_from_form(data, "music_usage_enabled")
    music_usage_admin_only = _bool_from_form(data, "music_usage_admin_only")
    music_usage_restrict_enabled = _bool_from_form(
        data, "music_usage_restrict_enabled"
    )
    music_usage_allow_admin_bypass = _bool_from_form(
        data, "music_usage_allow_admin_bypass"
    )
    await storage.music.update(
        id=state["music"]["id"],
        default_volume=volume,
        default_repeat=_bool_from_form(data, "default_repeat"),
        default_autoplay=_bool_from_form(data, "default_autoplay"),
        setup_music_mode=setup_mode_enabled,
        music_setup_channel_id=(int(setup_channel_id) if str(setup_channel_id or "").strip().isdigit() else None),
        music_setup_voice_channel_id=(int(setup_voice_id) if str(setup_voice_id or "").strip().isdigit() else None),
        music_usage_enabled=music_usage_enabled,
        music_usage_admin_only=music_usage_admin_only,
        music_usage_restrict_enabled=music_usage_restrict_enabled,
        music_usage_allow_admin_bypass=music_usage_allow_admin_bypass,
        music_usage_role_ids=music_usage_role_ids,
        music_usage_user_ids=music_usage_user_ids,
        music_usage_channel_ids=music_usage_channel_ids,
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าเพลงแล้ว", target="music")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/music?notice={urlencode({'notice': 'บันทึกการตั้งค่าเพลงแล้ว'}).split('=',1)[1]}", status_code=303)

async def update_temp_channels_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    await _ensure_dashboard_config_cache()
    data = await _parse_form(request)
    redirect_tab = str(data.get("redirect_tab") or "join_to_create").strip().lower()
    if redirect_tab not in {"temp_channels", "join_to_create"}:
        redirect_tab = "join_to_create"
    fields_payload: list[dict[str, Any]] = []
    try:
        decoded_fields = json.loads(data.get("fields_json", "[]"))
        if isinstance(decoded_fields, list):
            fields_payload = decoded_fields
    except Exception:
        fields_payload = []
    payload = _normalize_temp_channels_settings({**data, "fields": fields_payload})

    j2c_row = state.get("j2c_settings") if isinstance(state, dict) else None
    if not isinstance(j2c_row, dict) or not j2c_row.get("id"):
        j2c_row = cache.j2c_settings.get(str(guild_id), {}) or await storage.j2c_settings.get(guild_id=guild_id) or {}
    if not j2c_row:
        try:
            await storage.j2c_settings.insert(guild_id=guild_id)
        except Exception:
            pass
        j2c_row = cache.j2c_settings.get(str(guild_id), {}) or await storage.j2c_settings.get(guild_id=guild_id) or {}

    j2c_id = j2c_row.get("id")
    if j2c_id:
        await storage.j2c_settings.update(
            id=j2c_id,
            enabled=bool(payload.get("enabled")),
            create_vc_channel_id=(int(payload.get("create_vc_channel_id")) if str(payload.get("create_vc_channel_id") or "").isdigit() else None),
            create_vc_category_id=(int(payload.get("create_vc_category_id")) if str(payload.get("create_vc_category_id") or "").isdigit() else None),
        )

    await _set_dashboard_config_value(
        _temp_channels_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าห้องชั่วคราวแล้ว", target="temp_channels")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/{redirect_tab}?notice={urlencode({'notice': 'Join To Create VC settings saved'}).split('=',1)[1]}",
        status_code=303,
    )

async def send_temp_channels_interface(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"ok": False, "message": blocked_notice}, status_code=403)
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="temp_channels")
    if tab_block_reason:
        return JSONResponse({"ok": False, "message": tab_block_reason}, status_code=403)

    data = await _parse_form(request)
    fields_payload: list[dict[str, Any]] = []
    try:
        decoded_fields = json.loads(data.get("fields_json", "[]"))
        if isinstance(decoded_fields, list):
            fields_payload = decoded_fields
    except Exception:
        fields_payload = []
    payload = _normalize_temp_channels_settings({**data, "fields": fields_payload})
    send_channel_id = str(payload.get("send_channel_id") or "").strip()
    if not send_channel_id.isdigit():
        return JSONResponse({"ok": False, "message": "กรุณาเลือกห้องข้อความสำหรับส่งแผงควบคุม"}, status_code=400)

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return JSONResponse({"ok": False, "message": "ไม่พบกิลด์นี้ในระบบบอท"}, status_code=404)
    channel = bot_guild.get_channel(int(send_channel_id))
    if not channel or not hasattr(channel, "send"):
        return JSONResponse({"ok": False, "message": "บอทไม่สามารถเข้าถึงห้องที่เลือกได้"}, status_code=400)

    embed = discord.Embed(
        title=str(payload.get("embed_title") or "แผงควบคุม TempVoice")[:256],
        description=str(payload.get("embed_description") or "").strip()[:4000],
        color=_verify_color_to_int(payload.get("embed_color")),
    )
    author_name = str(payload.get("embed_author_name") or "").strip()
    if author_name:
        embed.set_author(
            name=author_name[:256],
            url=str(payload.get("embed_author_url") or "").strip() or None,
            icon_url=str(payload.get("embed_author_icon_url") or "").strip() or None,
        )
    thumbnail_url = str(payload.get("embed_thumbnail_url") or "").strip()
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    image_url = str(payload.get("embed_image_url") or "").strip()
    if image_url:
        embed.set_image(url=image_url)
    footer_text = str(payload.get("embed_footer_text") or "").strip()
    if footer_text:
        embed.set_footer(
            text=footer_text[:2048],
            icon_url=str(payload.get("embed_footer_icon_url") or "").strip() or None,
        )
    fields = payload.get("fields")
    if isinstance(fields, list):
        for field in fields[:25]:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()[:256]
            value = str(field.get("value") or "").strip()[:1024]
            if not name and not value:
                continue
            embed.add_field(name=name or "หัวข้อ", value=value or "-", inline=bool(field.get("inline", False)))

    button_defs: list[tuple[str, str]] = [
        ("name", "เปลี่ยนชื่อ"),
        ("limit", "จำนวนคน"),
        ("privacy", "ล็อก/ปลดล็อก"),
        ("chat", "เปิด/ปิดแชต"),
        ("trust", "อนุญาตสมาชิก"),
        ("untrust", "ยกเลิกอนุญาต"),
        ("kick", "เตะออกจากห้อง"),
        ("region", "ภูมิภาค"),
        ("block", "บล็อกสมาชิก"),
        ("unblock", "ยกเลิกบล็อก"),
        ("claim", "รับสิทธิ์เจ้าของ"),
        ("transfer", "โอนสิทธิ์เจ้าของ"),
        ("delete", "ลบห้อง"),
    ]
    buttons_state = payload.get("buttons") if isinstance(payload.get("buttons"), dict) else {}
    selected_buttons = [(key, label) for key, label in button_defs if bool(buttons_state.get(key, True))]
    view = discord.ui.View(timeout=None)
    danger_actions = {"delete", "block", "kick", "untrust"}
    for index, (action_key, label) in enumerate(selected_buttons[:25]):
        style = discord.ButtonStyle.danger if action_key in danger_actions else discord.ButtonStyle.secondary
        view.add_item(
            discord.ui.Button(
                label=label[:80],
                style=style,
                custom_id=f"tempiface:{action_key}",
                row=index // 5,
            )
        )
    content = str(payload.get("interface_content") or "").strip()
    mode = str(payload.get("interface_mode") or "embed").strip().lower()
    try:
        if mode == "text":
            await channel.send(content=content or "แผงควบคุม Join To Create VC", view=view if selected_buttons else None)
        else:
            await channel.send(content=content or None, embed=embed, view=view if selected_buttons else None)
    except Exception as error:
        return JSONResponse({"ok": False, "message": f"ส่งแผงควบคุมไม่สำเร็จ: {error}"}, status_code=500)

    await _append_dashboard_audit_event(guild_id, session, "ส่งแผงควบคุมห้องชั่วคราวแล้ว", target="temp_channels")
    return JSONResponse({"ok": True, "message": "ส่งแผงควบคุมไปยังห้องที่เลือกแล้ว"})

async def _music_web_control_core(
    *,
    request: Request,
    guild_id: int,
    session: dict[str, Any],
    current_guild: dict[str, Any],
    state: dict[str, Any],
    bot_guild: Any,
):
    data = await _parse_form(request)
    action = (data.get("action") or "").strip().lower()
    query = (data.get("query") or "").strip()
    volume_raw = (data.get("volume") or "").strip()
    queue_index_raw = (data.get("queue_index") or "").strip()
    select_index_raw = (data.get("select_index") or "").strip()
    seek_ms_raw = (data.get("seek_ms") or "").strip()
    playlist_key = (
        data.get("playlist")
        or data.get("playlist_key")
        or ""
    ).strip()
    playlist_item_value = (
        data.get("item")
        or data.get("item_value")
        or ""
    ).strip()
    playlist_mode = (data.get("mode") or "all").strip().lower()
    playlist_picks_raw = (
        data.get("picks")
        or data.get("indexes")
        or ""
    ).strip()
    volume = int(volume_raw) if volume_raw.isdigit() else None
    queue_index = int(queue_index_raw) if queue_index_raw.isdigit() else None
    select_index = int(select_index_raw) if select_index_raw.isdigit() else None
    seek_ms = int(seek_ms_raw) if seek_ms_raw.isdigit() else None
    default_volume = int(state.get("music", {}).get("default_volume", 80) or 80)
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict((state or {}).get("guild") or {})
    guild_state_for_plan["subscription"] = plan_tier
    allow_link_playback = _can_play_music_links(guild_state_for_plan)
    queue_limit = _music_queue_limit_from_guild_state(guild_state_for_plan)
    plan_limits = _plan_limits_from_guild_state(guild_state_for_plan)
    playlist_quota_max = max(
        1,
        min(
            user_music_playlists.MAX_USER_PLAYLISTS,
            int(plan_limits.get("music_user_playlists", user_music_playlists.MAX_USER_PLAYLISTS) or user_music_playlists.MAX_USER_PLAYLISTS),
        ),
    )
    playlist_item_limit = max(
        1,
        min(
            user_music_playlists.MAX_ITEMS_PER_PLAYLIST,
            int(plan_limits.get("music_playlist_items", user_music_playlists.MAX_ITEMS_PER_PLAYLIST) or user_music_playlists.MAX_ITEMS_PER_PLAYLIST),
        ),
    )

    actor_user_id = _session_user_id(session)
    actor_member = bot_guild.get_member(actor_user_id) if actor_user_id else None
    owner_id_raw = (current_guild or {}).get("owner_id") or getattr(bot_guild, "owner_id", 0)
    try:
        owner_id = int(owner_id_raw or 0)
    except Exception:
        owner_id = 0
    actor_role_ids = [
        int(getattr(role, "id", 0) or 0)
        for role in list(getattr(actor_member, "roles", []) or [])
        if str(getattr(role, "id", "") or "").strip().isdigit()
    ]
    is_owner = bool(actor_user_id and owner_id and int(actor_user_id) == int(owner_id))
    dashboard_access = (state or {}).get("dashboard_access") if isinstance(state, dict) else {}
    is_dashboard_admin_like = bool(
        isinstance(dashboard_access, dict)
        and (
            dashboard_access.get("has_admin_like_permission")
            or dashboard_access.get("effective_is_owner")
            or dashboard_access.get("is_dashboard_admin")
        )
    )
    is_admin_like = bool(is_member_admin_like(actor_member) or is_dashboard_admin_like)
    allowed_music_usage, music_usage_message = evaluate_music_access(
        (state or {}).get("music") if isinstance(state, dict) else {},
        actor_user_id=actor_user_id,
        actor_role_ids=actor_role_ids,
        actor_channel_id=None,
        is_owner=is_owner,
        is_admin=is_admin_like,
    )
    if not allowed_music_usage:
        return JSONResponse({"ok": False, "message": music_usage_message}, status_code=403)

    if not actor_user_id:
        return JSONResponse({"ok": False, "message": "Session expired."}, status_code=403)

    async def _playlist_extra(selected: str = "") -> dict[str, Any]:
        rows = await user_music_playlists.list_user_playlists(int(actor_user_id))
        payload = _web_user_playlist_payload(
            rows,
            selected_key=selected,
            max_playlists=playlist_quota_max,
            max_items_per_playlist=playlist_item_limit,
        )
        payload["playlist_quota_used"] = len(rows)
        payload["playlist_quota_max"] = playlist_quota_max
        payload["playlist_quota_remaining"] = max(
            0,
            playlist_quota_max - len(rows),
        )
        return payload

    if action == "playlist_sync":
        selected = playlist_key or query
        return JSONResponse(
            {
                "ok": True,
                "message": "Playlist synced.",
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": await _playlist_extra(selected=selected),
            }
        )

    if action == "playlist_create":
        requested_name = query or str(data.get("name") or "").strip()
        ok, message, row = await user_music_playlists.create_user_playlist(
            int(actor_user_id),
            requested_name,
            max_playlists=playlist_quota_max,
        )
        selected = str((row or {}).get("slug") or "")
        return JSONResponse(
            {
                "ok": ok,
                "message": _clean_text(message),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": await _playlist_extra(selected=selected),
            }
        )

    if action == "playlist_delete":
        target_playlist = playlist_key or query
        if not target_playlist:
            return JSONResponse(
                {"ok": False, "message": "Please choose a playlist to delete."},
                status_code=400,
            )
        ok, message = await user_music_playlists.delete_user_playlist(
            int(actor_user_id),
            target_playlist,
        )
        return JSONResponse(
            {
                "ok": ok,
                "message": _clean_text(message),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": await _playlist_extra(),
            }
        )

    if action == "playlist_add_item":
        target_playlist = playlist_key or str(data.get("name") or "").strip()
        item_value = playlist_item_value or query
        if not target_playlist:
            return JSONResponse(
                {"ok": False, "message": "Please choose a playlist."},
                status_code=400,
            )
        if not item_value:
            return JSONResponse(
                {"ok": False, "message": "Please provide a song name or URL."},
                status_code=400,
            )
        ok, message, updated = await user_music_playlists.add_item_to_playlist(
            int(actor_user_id),
            target_playlist,
            item_value,
            max_items_per_playlist=playlist_item_limit,
        )
        selected = str((updated or {}).get("slug") or target_playlist)
        return JSONResponse(
            {
                "ok": ok,
                "message": _clean_text(message),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": await _playlist_extra(selected=selected),
            }
        )

    if action == "playlist_remove_items":
        target_playlist = playlist_key or str(data.get("name") or "").strip()
        picks_source = playlist_picks_raw or query
        if not target_playlist:
            return JSONResponse(
                {"ok": False, "message": "Please choose a playlist."},
                status_code=400,
            )
        playlist_row = await user_music_playlists.get_user_playlist(
            int(actor_user_id),
            target_playlist,
        )
        if not playlist_row:
            return JSONResponse(
                {"ok": False, "message": "Playlist not found."},
                status_code=404,
            )
        current_items = list(playlist_row.get("items") or [])
        if not current_items:
            return JSONResponse(
                {"ok": False, "message": "Playlist is empty."},
                status_code=400,
            )
        picks, picks_error = _parse_web_pick_indexes(
            picks_source,
            max_index=len(current_items),
        )
        if picks_error:
            if picks_error == "out_of_range":
                message = "Item index out of range."
            else:
                message = "Invalid indexes format. Use: 1, 1 3 5, 1-4"
            return JSONResponse(
                {"ok": False, "message": message},
                status_code=400,
            )
        ok, message, updated, _removed = await user_music_playlists.remove_items_from_playlist(
            int(actor_user_id),
            target_playlist,
            picks,
        )
        selected = str((updated or {}).get("slug") or target_playlist)
        return JSONResponse(
            {
                "ok": ok,
                "message": _clean_text(message),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": await _playlist_extra(selected=selected),
            }
        )

    guarded_actions = {
        "pause_toggle",
        "skip",
        "previous",
        "seek_backward",
        "seek_forward",
        "seek_to",
        "loop_toggle",
        "autoplay_toggle",
        "shuffle_queue",
        "stop",
        "volume_up",
        "volume_down",
        "set_volume",
        "delete_queue",
        "move_queue_up",
        "move_queue_down",
        "play_queue_now",
        "add_track",
        "add_track_at",
        "add_playlist",
        "playlist_play",
    }
    add_actions = {"add_track", "add_track_at", "add_playlist", "playlist_play"}
    voice_client = getattr(bot_guild, "voice_client", None)
    if action in guarded_actions:
        resolved_voice_client, connect_error = await _ensure_web_music_voice_client(
            bot_guild=bot_guild,
            state=state,
            actor_member=actor_member,
            action=action,
        )
        if connect_error:
            return JSONResponse({"ok": False, "message": connect_error}, status_code=400)
        voice_client = resolved_voice_client
        active_channel = getattr(voice_client, "channel", None) if voice_client else None
        actor_channel = getattr(getattr(actor_member, "voice", None), "channel", None)
        if action not in add_actions:
            if not actor_member or not getattr(actor_member, "voice", None):
                return JSONResponse({"ok": False, "message": "คุณต้องอยู่ในห้องเสียงก่อน"}, status_code=403)
            if active_channel and (not actor_channel or int(actor_channel.id) != int(active_channel.id)):
                return JSONResponse({"ok": False, "message": "คุณต้องอยู่ในห้องเสียงเดียวกับบอทก่อนจึงจะควบคุมเพลงได้"}, status_code=403)
            if active_channel and not _voice_human_members(active_channel):
                return JSONResponse({"ok": False, "message": "ยังไม่มีผู้ใช้อยู่ในห้องเสียง"}, status_code=400)

        actor_name = _clean_text(
            str(getattr(actor_member, "display_name", None) or getattr(actor_member, "name", None) or "unknown")
        )
        actor_id = int(actor_user_id) if actor_user_id else 0
        actor_channel_id = str(getattr(actor_channel, "id", "") or "")
        actor_channel_name = _clean_text(str(getattr(actor_channel, "name", "") or ""))
        guild_name = _clean_text(str(getattr(bot_guild, "name", "") or ""))
        logger.info(
            f"[music_action] guild={guild_id}({guild_name}) actor={actor_id}({actor_name}) "
            f"channel={actor_channel_id}({actor_channel_name}) action={action}"
        )

    if action in {"move_queue_up", "move_queue_down"}:
        if queue_index is None:
            return JSONResponse({"ok": False, "message": "ไม่พบลำดับคิวที่ต้องการย้าย"}, status_code=400)
        ok, message = await _move_music_queue(
            voice_client=voice_client,
            queue_index=queue_index,
            direction="up" if action == "move_queue_up" else "down",
        )
        return JSONResponse(
            {
                "ok": ok,
                "message": _clean_text(message),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": {},
            }
        )

    if action == "play_queue_now":
        if queue_index is None:
            return JSONResponse({"ok": False, "message": "ไม่พบลำดับคิวที่ต้องการเล่น"}, status_code=400)
        ok, message = await _play_music_queue_now(
            voice_client=voice_client,
            queue_index=queue_index,
            default_volume=default_volume,
        )
        return JSONResponse(
            {
                "ok": ok,
                "message": _clean_text(message),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": {},
            }
        )

    if action == "add_playlist":
        ok, message = await _add_music_playlist(
            voice_client=voice_client,
            playlist_key=query,
            default_volume=default_volume,
            queue_limit=queue_limit,
        )
        return JSONResponse(
            {
                "ok": ok,
                "message": _clean_text(message),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": {},
            }
        )

    if action == "playlist_play":
        target_playlist = playlist_key or query
        if not target_playlist:
            return JSONResponse(
                {"ok": False, "message": "Please choose a playlist."},
                status_code=400,
            )
        playlist_row = await user_music_playlists.get_user_playlist(
            int(actor_user_id),
            target_playlist,
        )
        if not playlist_row:
            return JSONResponse(
                {"ok": False, "message": "Playlist not found."},
                status_code=404,
            )
        entries = list(playlist_row.get("items") or [])
        if not entries:
            return JSONResponse(
                {"ok": False, "message": "Playlist is empty."},
                status_code=400,
            )

        selected_entries = entries
        if playlist_mode in {"selected", "select", "pick", "choice"}:
            picks, picks_error = _parse_web_pick_indexes(
                playlist_picks_raw,
                max_index=len(entries),
            )
            if picks_error:
                if picks_error == "out_of_range":
                    message = "Item index out of range."
                elif picks_error == "empty":
                    message = "Please provide playlist item indexes."
                else:
                    message = "Invalid indexes format. Use: 1, 1 3 5, 1-4"
                return JSONResponse({"ok": False, "message": message}, status_code=400)
            selected_entries = [entries[index - 1] for index in picks]

        if not allow_link_playback and any(
            str(item.get("kind") or "").strip().lower() == "url"
            for item in selected_entries
        ):
            return JSONResponse(
                {
                    "ok": False,
                    "message": "Free plan cannot play URL items from playlist.",
                },
                status_code=403,
            )

        tracks, unresolved = await _resolve_web_playlist_entries_to_tracks(
            selected_entries
        )
        if not tracks:
            return JSONResponse(
                {
                    "ok": False,
                    "message": "No playable track resolved from selected playlist items.",
                    "payload": _live_payload(current_guild, bot_guild, state),
                    "extra": await _playlist_extra(selected=target_playlist),
                },
                status_code=400,
            )

        added_count, skipped_count = await _enqueue_web_tracks(
            voice_client=voice_client,
            tracks=tracks,
            default_volume=default_volume,
            queue_limit=queue_limit,
            requester=actor_member,
        )
        if added_count <= 0:
            return JSONResponse(
                {
                    "ok": False,
                    "message": f"Queue is full (limit {queue_limit}).",
                    "payload": _live_payload(current_guild, bot_guild, state),
                    "extra": await _playlist_extra(selected=target_playlist),
                },
                status_code=400,
            )
        await user_music_playlists.mark_playlist_used(int(actor_user_id), target_playlist)

        summary = (
            f"Added {added_count} track(s) from playlist {playlist_row.get('name')}."
        )
        if unresolved:
            summary += f" Unresolved {len(unresolved)} item(s)."
        if skipped_count:
            summary += f" Queue skipped {skipped_count} track(s)."
        return JSONResponse(
            {
                "ok": True,
                "message": _clean_text(summary),
                "payload": _live_payload(current_guild, bot_guild, state),
                "extra": await _playlist_extra(selected=target_playlist),
            }
        )

    ok, message, extra = await _handle_music_web_action(
        bot_guild,
        action,
        query=query,
        volume=volume,
        queue_index=queue_index,
        select_index=select_index,
        seek_ms=seek_ms,
        default_volume=default_volume,
        allow_link_playback=allow_link_playback,
        queue_limit=queue_limit,
    )
    return JSONResponse(
        {
            "ok": ok,
            "message": _clean_text(message),
            "payload": _live_payload(current_guild, bot_guild, state),
            "extra": extra or {},
        }
    )

async def music_web_control(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"ok": False, "message": blocked_notice}, status_code=403)
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="music")
    if tab_block_reason:
        return JSONResponse({"ok": False, "message": tab_block_reason}, status_code=403)

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return JSONResponse({"ok": False, "message": "ไม่พบกิลด์นี้ในระบบบอท"}, status_code=404)

    return await _music_web_control_core(
        request=request,
        guild_id=guild_id,
        session=session,
        current_guild=current_guild,
        state=state,
        bot_guild=bot_guild,
    )


async def music_web_control_user(request: Request, guild_id: int):
    session, current_guild, bot_guild, state = await _require_music_member_context(request, guild_id)
    if not session:
        return JSONResponse({"ok": False, "message": "ยังไม่ได้เข้าสู่ระบบ"}, status_code=403)
    if not current_guild or not bot_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"ok": False, "message": blocked_notice}, status_code=403)
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    tab_block_reason = _ownerbot_dashboard_tab_block_reason(session=session, tab_slug="music")
    if tab_block_reason:
        return JSONResponse({"ok": False, "message": tab_block_reason}, status_code=403)

    return await _music_web_control_core(
        request=request,
        guild_id=guild_id,
        session=session,
        current_guild=current_guild,
        state=state,
        bot_guild=bot_guild,
    )

_PROMOTE_SAVED_LIMITS_BY_PLAN = {
    "free": 0,
    "silver": 1,
    "golden": 2,
    "diamond": 5,
    "permanent": 8,
}

_PROMOTE_URL_RE = re.compile(r"((?:https?://|discord\.gg/|discord\.com/invite/)[^\s<>()]+)", re.I)


def _promote_saved_messages_list(promote_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = promote_data.get("saved_messages") if isinstance(promote_data, dict) else []
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        try:
            row_id = int(row.get("id"))
        except Exception:
            continue
        attachments = row.get("attachments")
        if not isinstance(attachments, list):
            attachments = []
        items.append(
            {
                "id": row_id,
                "name": _clean_text(row.get("name") or f"บันทึก #{row_id}")[:80].strip() or f"บันทึก #{row_id}",
                "content": _clean_text(row.get("content") or "")[:1800],
                "attachments": [str(item).strip() for item in attachments if str(item).strip()][:5],
                "invite_url": _clean_text(row.get("invite_url") or "").strip() or None,
                "created_by": str(row.get("created_by") or "").strip(),
                "created_at": int(row.get("created_at") or int(time.time())),
            }
        )
    items.sort(key=lambda item: int(item.get("id") or 0))
    return items


def _promote_saved_limit_for_plan(plan_tier: str) -> int:
    return int(_PROMOTE_SAVED_LIMITS_BY_PLAN.get(str(plan_tier or "free").strip().lower(), 0))


def _promote_effective_plan_tier(state: dict[str, Any] | None) -> str:
    if not isinstance(state, dict):
        return "free"
    # Promote permission checks should reflect the guild's real plan tier.
    # Do not elevate via ownerbot forced-plan mode; that causes confusing UI/behavior mismatches.
    tier_state = dict(state)
    dashboard_access = dict(tier_state.get("dashboard_access") or {})
    dashboard_access["forced_plan_tier"] = ""
    dashboard_access["ownerbot_mode_enabled"] = False
    tier_state["dashboard_access"] = dashboard_access
    return _dashboard_effective_plan_tier(tier_state, session=None)


def _promote_next_saved_id(saved_messages: list[dict[str, Any]]) -> int:
    if not saved_messages:
        return 1
    return max(int(item.get("id") or 0) for item in saved_messages) + 1


def _promote_extract_urls(text: str) -> list[str]:
    content = str(text or "")
    urls: list[str] = []
    for match in _PROMOTE_URL_RE.finditer(content):
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


def _promote_allowed_url_hint(allowed_domains: list[str], allowed_urls: list[str]) -> str:
    domain_targets, url_targets = _promote_allowed_url_targets(allowed_domains, allowed_urls)
    domains_text = ", ".join(domain_targets[:10]) if domain_targets else "-"
    if url_targets:
        urls_text = ", ".join(url_targets[:6])
        return f"Allowed domains: {domains_text} | Allowed URL prefixes: {urls_text}"
    return f"Allowed domains: {domains_text}"


def _promote_blocked_url_hint(blocked_domains: list[str], blocked_urls: list[str]) -> str:
    domain_targets, url_targets = _promote_blocked_url_targets(blocked_domains, blocked_urls)
    domains_text = ", ".join(domain_targets[:10]) if domain_targets else "-"
    if url_targets:
        urls_text = ", ".join(url_targets[:6])
        return f"Blocked domains: {domains_text} | Blocked URL prefixes: {urls_text}"
    return f"Blocked domains: {domains_text}"


def _promote_merge_blocked_words(*sources: Any) -> list[str]:
    merged: list[str] = []
    for source in sources:
        normalized = _normalize_promote_blocked_words(source)
        for token in normalized:
            if token and token not in merged:
                merged.append(token)
    return merged[:260]


def _promote_find_blocked_urls(
    urls: list[str],
    *,
    blocked_domains: list[str],
    blocked_urls: list[str],
) -> list[str]:
    blocked_hits: list[str] = []
    for raw_url in urls:
        candidate = str(raw_url or "").strip()
        if not candidate:
            continue
        if _is_blocked_promote_custom_url(candidate, blocked_domains, blocked_urls):
            blocked_hits.append(candidate)
    deduped: list[str] = []
    for item in blocked_hits:
        if item in deduped:
            continue
        deduped.append(item)
    return deduped[:8]


def _promote_collect_image_urls(
    *,
    attachments: list[str],
    content_links: list[str],
) -> list[str]:
    image_exts = (
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
    urls: list[str] = []
    for raw in [*(attachments or []), *(content_links or [])]:
        link = str(raw or "").strip()
        if not link:
            continue
        base = link.lower().split("?", 1)[0].split("#", 1)[0]
        if not (base.endswith(image_exts) or "/dashboard/assets/db/" in base):
            continue
        if link in urls:
            continue
        urls.append(link)
        if len(urls) >= 4:
            break
    return urls


async def _promote_scan_image_urls(
    *,
    bot: Any,
    guild_id: int,
    image_urls: list[str],
) -> tuple[bool, str]:
    if not image_urls:
        return True, ""
    promote_cog = bot.get_cog("message") if bot else None
    if not promote_cog or not hasattr(promote_cog, "scan_promote_image_urls"):
        return False, "ระบบตรวจรูปภาพยังไม่พร้อมใช้งาน"
    try:
        allowed, reason = await promote_cog.scan_promote_image_urls(
            int(guild_id),
            image_urls,
            source="web",
        )
        reason_text = str(reason or "").strip()
        if bool(allowed) and reason_text.lower().startswith("warn:"):
            return True, reason_text.split(":", 1)[1].strip()
        return bool(allowed), reason_text
    except Exception:
        return False, "ระบบตรวจรูปภาพล้มเหลวชั่วคราว"


def _promote_validate_content_links(
    content: str,
    *,
    allowed_domains: list[str],
    allowed_urls: list[str],
    allow_unrestricted: bool = False,
) -> tuple[list[str], list[str]]:
    valid_urls: list[str] = []
    invalid_urls: list[str] = []
    for raw_url in _promote_extract_urls(content):
        candidate = raw_url if "://" in raw_url else f"https://{raw_url}"
        if _is_allowed_discord_invite_url(raw_url) or _is_allowed_discord_invite_url(candidate):
            valid_urls.append(candidate)
            continue
        normalized = _normalize_promote_attachment_url(raw_url)
        if normalized:
            valid_urls.append(normalized)
            continue
        if allow_unrestricted:
            normalized_custom = _normalize_promote_candidate_url(candidate) or ""
            if normalized_custom:
                valid_urls.append(normalized_custom)
                continue
            invalid_urls.append(raw_url)
            continue
        if _is_allowed_promote_custom_url(candidate, allowed_domains, allowed_urls):
            normalized_custom = _normalize_promote_candidate_url(candidate) or candidate
            valid_urls.append(normalized_custom)
            continue
        invalid_urls.append(raw_url)
    return valid_urls, invalid_urls


async def promote_web_send(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
    )
    if guard_response:
        return guard_response

    request_headers = getattr(request, "headers", {}) or {}
    content_type = str(getattr(request_headers, "get", lambda *_: "")("content-type") or "").lower()
    parsed_form = None
    if not hasattr(request, "headers") and hasattr(request, "form"):
        parsed_form = await request.form()
        data = {k: str(v) for k, v in parsed_form.items() if k != "image_file"}
    elif "multipart/form-data" in content_type:
        try:
            parsed_form = await request.form()
        except AssertionError:
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/promote?{urlencode({'notice': 'เซิร์ฟเวอร์ยังไม่รองรับการอ่านฟอร์มแบบไฟล์ กรุณาติดตั้งแพ็กเกจ python-multipart แล้วรีสตาร์ตบอท'})}",
                status_code=303,
            )
        data = {k: str(v) for k, v in parsed_form.items() if k != "image_file"}
    else:
        data = await _parse_form(request)
    redirect_tab = (data.get("redirect_tab") or "promote").strip().lower()
    if redirect_tab not in {"overview", "promote"}:
        redirect_tab = "promote"
    redirect_path = f"/dashboard/guild/{guild_id}" if redirect_tab == "overview" else f"/dashboard/guild/{guild_id}/{redirect_tab}"

    try:
        promote_data = await storage.promote_channels.get(guild_id=guild_id) or {}
    except Exception as error:
        logger.warning(
            "promote_web_send config load failed | guild=%s error=%s",
            guild_id,
            error,
        )
        promote_data = {}
    if not promote_data:
        promote_data = state.get("promote") or cache.promote_channels.get(str(guild_id), {}) or {}
    owner_policy = _ownerbot_promote_policy_from_db()
    allowed_domains_cfg = _normalize_promote_allowed_domains(owner_policy.get("allowed_domains"))
    allowed_urls_cfg = _normalize_promote_allowed_urls(owner_policy.get("allowed_urls"))
    allowed_url_hint = _promote_allowed_url_hint(allowed_domains_cfg, allowed_urls_cfg)
    blocked_domains_cfg = _normalize_promote_allowed_domains(owner_policy.get("blocked_domains"))
    blocked_urls_cfg = _normalize_promote_allowed_urls(owner_policy.get("blocked_urls"))
    blocked_words_cfg = _normalize_promote_blocked_words(owner_policy.get("blocked_words"))
    blocked_url_hint = _promote_blocked_url_hint(blocked_domains_cfg, blocked_urls_cfg)
    submit_channel_id = promote_data.get("submit_channel_id")
    public_channel_id = promote_data.get("public_channel_id")
    if not submit_channel_id or not public_channel_id:
        return RedirectResponse(
            f"{redirect_path}?{urlencode({'notice': 'ยังไม่ได้เปิดใช้งานระบบโปรโมตสำหรับกิลด์นี้'})}",
            status_code=303,
        )

    action = (data.get("action") or "").strip().lower()
    valid_actions = {"send", "save", "send_saved", "delete_saved", "update_saved"}
    if action not in valid_actions:
        template_raw = str(data.get("template_id") or "").strip()
        action = "update_saved" if template_raw.isdigit() else "save"
    plan_tier = _promote_effective_plan_tier(state)
    ownerbot_unrestricted = bool(_dashboard_ownerbot_mode_from_state(state, session=session))
    can_use_rich_media = ownerbot_unrestricted or _is_plan_at_least(plan_tier, "silver")
    max_saved_messages = _promote_saved_limit_for_plan(plan_tier)

    saved_messages = _promote_saved_messages_list(promote_data)

    user_id = str(((session.get("user") or {}).get("id") or "")).strip()
    if not user_id:
        return RedirectResponse(
            f"{redirect_path}?{urlencode({'notice': 'เซสชันผู้ใช้ไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่'})}",
            status_code=303,
        )

    automod_data = state.get("automod") or {}
    automod_words = automod_data.get("antibadwords_words", [])
    if isinstance(automod_words, str):
        try:
            automod_words = json.loads(automod_words)
        except Exception:
            automod_words = []
    blocked_word_pool = _promote_merge_blocked_words(
        PROMOTE_DEFAULT_BLOCKED_WORDS,
        automod_words,
        blocked_words_cfg,
    )

    def _redirect_notice(message: str) -> RedirectResponse:
        return RedirectResponse(f"{redirect_path}?{urlencode({'notice': message})}", status_code=303)

    promote_enabled = bool(promote_data.get("enabled", True))
    if (action in {"send", "send_saved"}) and (not promote_enabled):
        return _redirect_notice("ระบบโปรโมตถูกปิดใช้งานอยู่ กรุณาเปิดใช้งานก่อนส่ง")

    suspension_map = _promote_suspension_map_from_db()
    suspension_reason = _promote_suspension_reason(guild_id, suspension_map)
    if suspension_reason:
        return _redirect_notice(suspension_reason)

    async def _persist_saved() -> bool:
        try:
            promote_row_id = int(promote_data.get("id") or 0) if str(promote_data.get("id") or "").isdigit() else 0
            if promote_row_id <= 0:
                latest_row = await storage.promote_channels.get(guild_id=guild_id) or {}
                if isinstance(latest_row, dict) and str(latest_row.get("id") or "").isdigit():
                    promote_row_id = int(latest_row.get("id") or 0)
                    promote_data.update(latest_row)
            if promote_row_id <= 0:
                created_row = await storage.promote_channels.insert(
                    guild_id=guild_id,
                    submit_channel_id=int(submit_channel_id) if str(submit_channel_id).isdigit() else 0,
                    public_channel_id=int(public_channel_id) if str(public_channel_id).isdigit() else 0,
                    cooldown_seconds=int(promote_data.get("cooldown_seconds") or PROMOTE_COOLDOWN_SECONDS or 43200),
                    cooldowns=dict(promote_data.get("cooldowns") or {}),
                    enabled=bool(promote_data.get("enabled", True)),
                    saved_messages=[],
                )
                if isinstance(created_row, dict):
                    promote_data.update(created_row)
                    promote_row_id = int(created_row.get("id") or 0)
            if promote_row_id <= 0:
                raise ValueError("promote row id missing while saving templates")
            updated_row = await storage.promote_channels.update(id=promote_row_id, saved_messages=saved_messages)
            if isinstance(updated_row, dict):
                promote_data.update(updated_row)
            return True
        except Exception as error:
            logger.warning(
                "promote_web_send persist_saved failed | guild=%s error=%s",
                guild_id,
                error,
            )
            return False
        finally:
            cache_snapshot = dict(promote_data or {})
            cache_snapshot["saved_messages"] = list(saved_messages or [])
            cache.promote_channels[str(guild_id)] = cache_snapshot

    def _find_saved_item() -> tuple[dict[str, Any] | None, int | None]:
        template_raw = (data.get("template_id") or "").strip()
        if not template_raw.isdigit():
            return None, None
        template_id = int(template_raw)
        for row in saved_messages:
            if int(row.get("id") or 0) == template_id:
                return row, template_id
        return None, template_id

    item, template_id = _find_saved_item()
    if action == "delete_saved":
        if not item:
            return _redirect_notice("ไม่พบรายการบันทึกที่ต้องการลบ")
        saved_messages[:] = [row for row in saved_messages if int(row.get("id") or 0) != int(template_id or 0)]
        if not await _persist_saved():
            return _redirect_notice("บันทึกรายการไม่สำเร็จชั่วคราว กรุณาลองใหม่อีกครั้ง")
        await _append_dashboard_audit_event(guild_id, session, f"ลบรายการโปรโมตบันทึก #{template_id}", target="promote")
        return _redirect_notice("ลบรายการบันทึกแล้ว")

    if action == "update_saved":
        if not item:
            return _redirect_notice("ไม่พบรายการบันทึกที่ต้องการแก้ไข")
        template_name = _clean_text(data.get("template_name") or "").strip()[:80] or item.get("name") or f"บันทึก #{template_id}"
        content_value = _clean_text(data.get("content") or "").strip()
        attachments_raw = _clean_text(data.get("attachments") or "")
        raw_attachments = [part.strip() for part in attachments_raw.split(",") if part.strip()][:5]
        attachments: list[str] = []
        invalid_attachments: list[str] = []
        for part in raw_attachments:
            normalized = _normalize_promote_attachment_url(part)
            if normalized:
                attachments.append(normalized)
            else:
                invalid_attachments.append(part)
        custom_invite_url = _clean_text(data.get("custom_invite_url") or "").strip()
        if custom_invite_url and "://" not in custom_invite_url:
            custom_invite_url = f"https://{custom_invite_url}"
        if (
            (not ownerbot_unrestricted)
            and custom_invite_url
            and not (
                _is_allowed_discord_invite_url(custom_invite_url)
                or _is_allowed_promote_custom_url(custom_invite_url, allowed_domains_cfg, allowed_urls_cfg)
            )
        ):
            return _redirect_notice(f"URL นี้ไม่อยู่ใน allowlist | {allowed_url_hint}")
        if custom_invite_url and not _is_allowed_discord_invite_url(custom_invite_url):
            custom_invite_url = _normalize_promote_candidate_url(custom_invite_url) or custom_invite_url
        content_links, invalid_content_links = _promote_validate_content_links(
            content_value,
            allowed_domains=allowed_domains_cfg,
            allowed_urls=allowed_urls_cfg,
            allow_unrestricted=ownerbot_unrestricted,
        )
        if invalid_content_links or invalid_attachments:
            return _redirect_notice(f"พบลิงก์ที่ไม่ถูกต้องในเนื้อหา/ไฟล์แนบ | {allowed_url_hint}")
        if not ownerbot_unrestricted:
            blocked_links = _promote_find_blocked_urls(
                [
                    *attachments,
                    *content_links,
                    *([custom_invite_url] if custom_invite_url else []),
                ],
                blocked_domains=blocked_domains_cfg,
                blocked_urls=blocked_urls_cfg,
            )
            if blocked_links:
                return _redirect_notice(f"Blocked URL matched blocklist: {blocked_links[0]} | {blocked_url_hint}")
        content_ok, content_reason = _validate_promote_content(content_value, blocked_word_pool)
        if not content_ok:
            return _redirect_notice(f"{i18n.tr('promote_badword_blocked', guild_id)} ({content_reason})")
        if not can_use_rich_media and (attachments or custom_invite_url or content_links):
            return _redirect_notice("แพ็กเกจ Free ไม่รองรับลิงก์และรูปภาพในโปรโมต (ต้องใช้ Silver ขึ้นไป)")
        if not content_value and not attachments:
            return _redirect_notice("กรุณากรอกเนื้อหาหรือแนบไฟล์อย่างน้อย 1 รายการ")
        item["name"] = template_name
        item["content"] = content_value
        item["attachments"] = attachments
        item["invite_url"] = custom_invite_url or None
        if not await _persist_saved():
            return _redirect_notice("บันทึกรายการไม่สำเร็จชั่วคราว กรุณาลองใหม่อีกครั้ง")
        await _append_dashboard_audit_event(guild_id, session, f"แก้ไขรายการโปรโมตบันทึก #{template_id}", target="promote")
        return _redirect_notice("บันทึกรายการโปรโมตที่แก้ไขแล้ว")

    content = ""
    attachments: list[str] = []
    custom_invite_url = ""
    template_name = _clean_text(data.get("template_name") or "").strip()[:80]
    if action == "send_saved":
        if not item:
            return _redirect_notice("ไม่พบรายการบันทึกที่ต้องการส่ง")
        content = _clean_text(item.get("content") or "").strip()
        raw_saved_attachments = [str(a).strip() for a in (item.get("attachments") or []) if str(a).strip()][:5]
        attachments = []
        for raw_link in raw_saved_attachments:
            normalized_saved = _normalize_promote_attachment_url(raw_link)
            if normalized_saved:
                attachments.append(normalized_saved)
        custom_invite_url = _clean_text(item.get("invite_url") or "").strip()
    else:
        content = _clean_text(data.get("content") or "").strip()
        attachments_raw = _clean_text(data.get("attachments") or "")
        raw_attachments = [part.strip() for part in attachments_raw.split(",") if part.strip()][:5]
        invalid_attachments: list[str] = []
        for part in raw_attachments:
            normalized = _normalize_promote_attachment_url(part)
            if normalized:
                attachments.append(normalized)
            else:
                invalid_attachments.append(part)
        if invalid_attachments:
            return _redirect_notice("ลิงก์ไฟล์แนบบางรายการไม่ผ่านการตรวจสอบ")
        custom_invite_url = _clean_text(data.get("custom_invite_url") or "").strip()
        if custom_invite_url and "://" not in custom_invite_url:
            custom_invite_url = f"https://{custom_invite_url}"

        uploaded_image = parsed_form.get("image_file") if parsed_form is not None else None
        if uploaded_image and getattr(uploaded_image, "filename", None):
            if not can_use_rich_media:
                return _redirect_notice("แพ็กเกจ Free ยังอัปโหลดรูปโปรโมตไม่ได้ (ต้องใช้ Silver ขึ้นไป)")
            try:
                raw_bytes = await uploaded_image.read()
                if not raw_bytes:
                    return _redirect_notice("อัปโหลดรูปไม่สำเร็จ (ไฟล์ว่าง)")
                if len(raw_bytes) > (8 * 1024 * 1024):
                    return _redirect_notice("ไฟล์รูปใหญ่เกินไป (สูงสุด 8MB)")
                promote_upload_channels = _collect_channel_ids_for_upload(
                    submit_channel_id,
                    public_channel_id,
                    state.get("promote", {}).get("submit_channel_id"),
                    state.get("promote", {}).get("public_channel_id"),
                )
                uploaded_url = await _upload_image_to_discord_cdn(
                    guild_id,
                    raw_bytes=raw_bytes,
                    filename=str(getattr(uploaded_image, "filename", "promote.png")),
                    preferred_channel_ids=promote_upload_channels,
                    upload_target="promote",
                    asset_kind="banner",
                    request=request,
                    uploader_id=int(_session_user_id(session) or 0),
                    source_route=str(getattr(request.url, "path", "") or ""),
                    source_field="image_file",
                )
                normalized_uploaded = _normalize_promote_attachment_url(uploaded_url)
                if (
                    not normalized_uploaded
                    and str(uploaded_url or "").strip().startswith(("http://", "https://"))
                    and "/dashboard/assets/db/" in str(uploaded_url or "")
                ):
                    normalized_uploaded = str(uploaded_url or "").strip()
                if not normalized_uploaded:
                    return _redirect_notice("อัปโหลดรูปแล้ว แต่ลิงก์รูปไม่ผ่านการตรวจสอบ")
                attachments.append(normalized_uploaded)
            except Exception:
                return _redirect_notice("อัปโหลดรูปโปรโมตไม่สำเร็จ (ตรวจสอบสิทธิ์ส่งไฟล์ของบอท)")

    if (
        (not ownerbot_unrestricted)
        and custom_invite_url
        and not (
            _is_allowed_discord_invite_url(custom_invite_url)
            or _is_allowed_promote_custom_url(custom_invite_url, allowed_domains_cfg, allowed_urls_cfg)
        )
    ):
        return _redirect_notice(f"{i18n.tr('promote_invite_invalid_domain', guild_id)} | {allowed_url_hint}")
    if custom_invite_url and not _is_allowed_discord_invite_url(custom_invite_url):
        custom_invite_url = _normalize_promote_candidate_url(custom_invite_url) or custom_invite_url

    if not content and not attachments:
        return _redirect_notice("กรุณากรอกเนื้อหาหรือแนบไฟล์อย่างน้อย 1 รายการ")

    content_links, invalid_content_links = _promote_validate_content_links(
        content,
        allowed_domains=allowed_domains_cfg,
        allowed_urls=allowed_urls_cfg,
        allow_unrestricted=ownerbot_unrestricted,
    )
    if invalid_content_links:
        return _redirect_notice(f"ลิงก์ในเนื้อหาไม่อยู่ใน allowlist หรือไม่ปลอดภัย | {allowed_url_hint}")

    if not ownerbot_unrestricted:
        blocked_links = _promote_find_blocked_urls(
            [
                *attachments,
                *content_links,
                *([custom_invite_url] if custom_invite_url else []),
            ],
            blocked_domains=blocked_domains_cfg,
            blocked_urls=blocked_urls_cfg,
        )
        if blocked_links:
            return _redirect_notice(f"Blocked URL matched blocklist: {blocked_links[0]} | {blocked_url_hint}")

    if not can_use_rich_media and (attachments or custom_invite_url or content_links):
        return _redirect_notice("แพ็กเกจ Free ไม่รองรับลิงก์และรูปภาพในโปรโมต (ต้องใช้ Silver ขึ้นไป)")

    content_ok, content_reason = _validate_promote_content(content, blocked_word_pool)
    if not content_ok:
        return _redirect_notice(f"{i18n.tr('promote_badword_blocked', guild_id)} ({content_reason})")

    image_scan_warning = ""
    if action != "save":
        image_urls = _promote_collect_image_urls(attachments=attachments, content_links=content_links)
        bot_for_scan = get_bot()
        promote_cog_for_scan = bot_for_scan.get_cog("message") if bot_for_scan and hasattr(bot_for_scan, "get_cog") else None
        if image_urls and promote_cog_for_scan and hasattr(promote_cog_for_scan, "scan_promote_image_urls"):
            image_ok, image_reason = await _promote_scan_image_urls(
                bot=bot_for_scan,
                guild_id=guild_id,
                image_urls=image_urls,
            )
            if not image_ok:
                return _redirect_notice(image_reason or "Image failed safety scan")
            if image_reason:
                image_scan_warning = str(image_reason).strip()
        elif image_urls:
            image_scan_warning = "รอตรวจรูปในโปรเซสบอทตอนเข้าคิว"

    if action == "save":
        if max_saved_messages <= 0:
            return _redirect_notice("แพ็กเกจนี้ยังไม่รองรับบันทึกข้อความโปรโมต (Free = 0)")
        if len(saved_messages) >= max_saved_messages:
            return _redirect_notice(f"เกินลิมิตรายการบันทึกแล้ว ({len(saved_messages)}/{max_saved_messages})")
        new_template_id = _promote_next_saved_id(saved_messages)
        saved_messages.append(
            {
                "id": new_template_id,
                "name": template_name or f"บันทึก #{new_template_id}",
                "content": content,
                "attachments": attachments[:5],
                "invite_url": custom_invite_url or None,
                "created_by": user_id,
                "created_at": int(time.time()),
            }
        )
        if not await _persist_saved():
            return _redirect_notice("บันทึกรายการไม่สำเร็จชั่วคราว กรุณาลองใหม่อีกครั้ง")
        await _append_dashboard_audit_event(guild_id, session, f"บันทึกข้อความโปรโมต #{new_template_id}", target="promote")
        return _redirect_notice("บันทึกข้อความโปรโมตแล้ว")

    cooldown_seconds = int(promote_data.get("cooldown_seconds") or PROMOTE_COOLDOWN_SECONDS or 43200)
    cooldowns = dict(promote_data.get("cooldowns") or {})
    now_ts = int(time.time())
    last_post = int(cooldowns.get(user_id, 0) or 0)
    if (not ownerbot_unrestricted) and (now_ts - last_post < cooldown_seconds):
        remaining = cooldown_seconds - (now_ts - last_post)
        return _redirect_notice(f"ติดคูลดาวน์อยู่ กรุณารอ {_format_duration_th(remaining)}")

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return _redirect_notice("ไม่พบกิลด์นี้ในระบบบอทที่กำลังทำงาน")

    invite_url = custom_invite_url or None
    if not invite_url:
        try:
            submit_channel = bot_guild.get_channel(int(submit_channel_id))
            me = getattr(bot_guild, "me", None)
            if submit_channel and me and submit_channel.permissions_for(me).create_instant_invite:
                invite = await submit_channel.create_invite(
                    max_age=86400,
                    max_uses=0,
                    unique=False,
                    reason=f"Promote web invite requested by dashboard user {user_id}",
                )
                invite_url = invite.url
        except Exception:
            invite_url = None

    if not ownerbot_unrestricted:
        cooldowns[user_id] = now_ts
        promote_data["cooldowns"] = cooldowns
        cache.promote_channels[str(guild_id)] = dict(promote_data or {})
        promote_row_id = int(promote_data.get("id") or 0) if str(promote_data.get("id") or "").isdigit() else 0
        if promote_row_id <= 0:
            try:
                latest_row = await storage.promote_channels.get(guild_id=guild_id) or {}
            except Exception:
                latest_row = {}
            if isinstance(latest_row, dict) and str(latest_row.get("id") or "").isdigit():
                promote_row_id = int(latest_row.get("id") or 0)
                promote_data.update(latest_row)
        if promote_row_id > 0:
            try:
                await storage.promote_channels.update(id=promote_row_id, cooldowns=cooldowns)
            except Exception as error:
                logger.warning(
                    "promote_web_send cooldown update failed | guild=%s error=%s",
                    guild_id,
                    error,
                )

    user_data = session.get("user") or {}
    author_name = _clean_text(user_data.get("username") or f"ผู้ใช้ {user_id}")
    queue_payload = {
        "guild_id": guild_id,
        "author_id": int(user_id) if user_id.isdigit() else user_id,
        "author_name": author_name,
        "author_mention": f"{author_name} (`{user_id}`)",
        "content": content,
        "attachments": attachments[:5],
        "invite_url": invite_url,
        "source_origin": "web",
        "source_channel_id": int(submit_channel_id) if str(submit_channel_id).isdigit() else 0,
        "source_channel_name": str(getattr(bot_guild.get_channel(int(submit_channel_id)), "name", "") or "") if bot_guild and str(submit_channel_id).isdigit() else "",
        "guild_name": str(current_guild.get("name") or f"Guild {guild_id}"),
        "allowed_domains": allowed_domains_cfg,
        "allowed_urls": allowed_urls_cfg,
        "blocked_words": blocked_words_cfg,
        "blocked_domains": blocked_domains_cfg,
        "blocked_urls": blocked_urls_cfg,
        "ownerbot_unrestricted": bool(ownerbot_unrestricted),
    }

    promote_cog = bot.get_cog("message") if bot else None
    if not promote_cog or not hasattr(promote_cog, "promote_queue"):
        try:
            await storage.promote_web_queue.insert(
                guild_id=guild_id,
                user_id=(int(user_id) if user_id.isdigit() else 0),
                payload=queue_payload,
                status="pending",
                attempts=0,
                error="",
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception as error:
            logger.warning(
                "promote_web_send queue fallback insert failed | guild=%s error=%s",
                guild_id,
                error,
            )
            return _redirect_notice("บริการคิวโปรโมทยังไม่พร้อมใช้งาน")
        await _append_dashboard_audit_event(guild_id, session, "ส่งคำขอโปรโมตจากเว็บ (รอ dispatch)", target="promote")
        fallback_notice = "รับคำขอโปรโมตแล้ว ระบบกำลังส่งเข้าคิวจากบอทภายในไม่กี่วินาที"
        if image_scan_warning:
            fallback_notice = f"{fallback_notice} | หมายเหตุ: {image_scan_warning}"
        return _redirect_notice(fallback_notice)

    queued, queue_position, queue_status = await promote_cog.enqueue_promote_job(queue_payload)
    if not queued and queue_status == "duplicate":
        await _send_promote_feedback_to_discord(
            bot_guild=bot_guild,
            submit_channel_id=submit_channel_id,
            user_id=user_id,
            ok=True,
            message="มีโปรโมตลิงก์เดียวกันอยู่ในคิวแล้ว ระบบจะส่งเพียงครั้งเดียว",
        )
        return _redirect_notice("มีโปรโมตลิงก์เดียวกันอยู่ในคิวแล้ว ระบบจะส่งครั้งเดียว")
    if not queued and str(queue_status or "").startswith("policy_blocked:"):
        reason = str(queue_status).split(":", 1)[1].strip() or "Promote was blocked by safety policy"
        await _send_promote_feedback_to_discord(
            bot_guild=bot_guild,
            submit_channel_id=submit_channel_id,
            user_id=user_id,
            ok=False,
            message=reason,
        )
        return _redirect_notice(reason)
    if not queued:
        return _redirect_notice("Promote enqueue failed temporarily, please try again")
    queue_warning = ""
    if str(queue_status or "").startswith("queued_warn:"):
        queue_warning = str(queue_status).split(":", 1)[1].strip()
    warning_note = queue_warning or image_scan_warning
    success_message = f"ส่งข้อความโปรโมตเข้าคิวสำเร็จ ลำดับที่ {queue_position}"
    if warning_note:
        success_message = f"{success_message} | หมายเหตุระบบตรวจรูป: {warning_note}"
    await _send_promote_feedback_to_discord(
        bot_guild=bot_guild,
        submit_channel_id=submit_channel_id,
        user_id=user_id,
        ok=True,
        message=success_message,
    )
    await _append_dashboard_audit_event(guild_id, session, "ส่งข้อความโปรโมตจากเว็บ", target="promote")
    if warning_note:
        return _redirect_notice(f"ส่งข้อความโปรโมตเข้าคิวแล้ว (ลำดับ {queue_position}) | หมายเหตุระบบตรวจรูป: {warning_note}")
    return _redirect_notice(f"ส่งข้อความโปรโมตเข้าคิวแล้ว (ลำดับ {queue_position})")

async def promote_web_update_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response

    redirect_path = f"/dashboard/guild/{guild_id}/promote"
    def _redirect_notice(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"{redirect_path}?{urlencode({'notice': str(message or '').strip()})}",
            status_code=303,
        )

    data = await _parse_form(request)
    action = str(data.get("action") or "save_channels").strip().lower()

    promote_data: dict[str, Any] = {}
    try:
        promote_data = await storage.promote_channels.get(guild_id=guild_id) or {}
    except Exception as error:
        logger.warning(
            "promote_web_update_settings load failed | guild=%s error=%s",
            guild_id,
            error,
        )
        promote_data = {}
    if not promote_data:
        promote_data = dict(state.get("promote") or cache.promote_channels.get(str(guild_id), {}) or {})

    if action in {"reset", "delete"}:
        storage_failed = False
        deleted_any = False
        try:
            deleted_rows = await storage.promote_channels.delete(guild_id=guild_id)
            deleted_any = bool(deleted_rows)
        except Exception as error:
            storage_failed = True
            logger.warning(
                "promote_web_update_settings reset failed | guild=%s error=%s",
                guild_id,
                error,
            )
        cache.promote_channels.pop(str(guild_id), None)
        await _append_dashboard_audit_event(guild_id, session, "ลบ/รีเซ็ตค่าระบบโปรโมตแล้ว", target="promote")
        if storage_failed:
            return _redirect_notice("รีเซ็ตค่าแล้วในหน่วยความจำ แต่ฐานข้อมูลยังไม่พร้อม")
        if not deleted_any:
            return _redirect_notice("ยังไม่ได้ตั้งค่าระบบโปรโมต")
        return _redirect_notice("ลบและรีเซ็ตค่าระบบโปรโมตแล้ว")

    if action == "toggle_enabled":
        if not promote_data:
            return _redirect_notice("ยังไม่ได้ตั้งค่าห้องโปรโมต กรุณาบันทึกห้องก่อน")
        submit_id = int(promote_data.get("submit_channel_id") or 0)
        public_id = int(promote_data.get("public_channel_id") or 0)
        if submit_id <= 0 or public_id <= 0:
            return _redirect_notice("ยังไม่ได้ตั้งค่าห้องโปรโมต กรุณาบันทึกห้องก่อน")
        next_enabled = not bool(promote_data.get("enabled", True))
        storage_failed = False
        try:
            promote_row_id = int(promote_data.get("id") or 0) if str(promote_data.get("id") or "").isdigit() else 0
            if promote_row_id <= 0:
                latest_promote_data = await storage.promote_channels.get(guild_id=guild_id) or {}
                if isinstance(latest_promote_data, dict) and str(latest_promote_data.get("id") or "").isdigit():
                    promote_data.update(latest_promote_data)
                    promote_row_id = int(promote_data.get("id") or 0)
            if promote_row_id > 0:
                updated_row = await storage.promote_channels.update(
                    id=promote_row_id,
                    enabled=next_enabled,
                )
                if isinstance(updated_row, dict):
                    promote_data.update(updated_row)
            else:
                inserted_row = await storage.promote_channels.insert(
                    guild_id=guild_id,
                    submit_channel_id=submit_id,
                    public_channel_id=public_id,
                    cooldown_seconds=int(promote_data.get("cooldown_seconds") or PROMOTE_COOLDOWN_SECONDS),
                    cooldowns=dict(promote_data.get("cooldowns") or {}),
                    enabled=next_enabled,
                )
                if isinstance(inserted_row, dict):
                    promote_data.update(inserted_row)
        except Exception as error:
            storage_failed = True
            logger.warning(
                "promote_web_update_settings toggle failed | guild=%s error=%s",
                guild_id,
                error,
            )

        cache_snapshot = dict(promote_data or {})
        cache_snapshot["guild_id"] = int(guild_id)
        cache_snapshot["submit_channel_id"] = int(submit_id)
        cache_snapshot["public_channel_id"] = int(public_id)
        cache_snapshot["enabled"] = bool(next_enabled)
        if not str(cache_snapshot.get("cooldown_seconds") or "").strip().isdigit():
            cache_snapshot["cooldown_seconds"] = int(PROMOTE_COOLDOWN_SECONDS)
        if not isinstance(cache_snapshot.get("cooldowns"), dict):
            cache_snapshot["cooldowns"] = {}
        cache.promote_channels[str(guild_id)] = cache_snapshot

        if next_enabled:
            await _append_dashboard_audit_event(guild_id, session, "เปิดใช้งานระบบโปรโมตแล้ว", target="promote")
            return _redirect_notice(
                "เปิดใช้งานระบบโปรโมตแล้ว"
                + (" (โหมดชั่วคราว: ใช้ค่าในหน่วยความจำ เนื่องจากฐานข้อมูลไม่พร้อม)" if storage_failed else "")
            )
        await _append_dashboard_audit_event(guild_id, session, "ปิดใช้งานระบบโปรโมตแล้ว", target="promote")
        return _redirect_notice(
            "ปิดใช้งานระบบโปรโมตแล้ว"
            + (" (โหมดชั่วคราว: ใช้ค่าในหน่วยความจำ เนื่องจากฐานข้อมูลไม่พร้อม)" if storage_failed else "")
        )

    submit_raw = (data.get("submit_channel_id") or "").strip()
    public_raw = (data.get("public_channel_id") or "").strip()

    if not submit_raw.isdigit() or not public_raw.isdigit():
        return _redirect_notice("กรุณาเลือกห้องส่งคำขอและห้องสาธารณะ")
    if submit_raw == public_raw:
        return _redirect_notice("ห้องส่งคำขอและห้องสาธารณะต้องไม่ซ้ำกัน")

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return _redirect_notice("ไม่พบกิลด์นี้ในระบบบอทที่กำลังทำงาน")

    submit_channel = bot_guild.get_channel(int(submit_raw))
    public_channel = bot_guild.get_channel(int(public_raw))
    allowed_types = {"text", "news"}
    if not submit_channel or str(getattr(submit_channel, "type", "")) not in allowed_types:
        return _redirect_notice("ห้องส่งคำขอต้องเป็นประเภท text/news")
    if not public_channel or str(getattr(public_channel, "type", "")) not in allowed_types:
        return _redirect_notice("ห้องสาธารณะต้องเป็นประเภท text/news")

    bot_member = bot_guild.me or bot_guild.get_member(getattr(getattr(bot, "user", None), "id", 0))
    if not bot_member:
        return _redirect_notice("ไม่พบบัญชีบอทในกิลด์นี้ กรุณาลองใหม่อีกครั้ง")

    def _missing_perms(channel: Any) -> list[str]:
        try:
            perms = channel.permissions_for(bot_member)
        except Exception:
            return ["View Channel", "Send Messages", "Embed Links"]
        missing: list[str] = []
        if not bool(getattr(perms, "view_channel", False)):
            missing.append("View Channel")
        if not bool(getattr(perms, "send_messages", False)):
            missing.append("Send Messages")
        if not bool(getattr(perms, "embed_links", False)):
            missing.append("Embed Links")
        return missing

    submit_missing = _missing_perms(submit_channel)
    public_missing = _missing_perms(public_channel)
    if submit_missing or public_missing:
        lines: list[str] = []
        if submit_missing:
            lines.append(f"ห้องส่ง {getattr(submit_channel, 'mention', '#unknown')}: {', '.join(submit_missing)}")
        if public_missing:
            lines.append(f"ห้องสาธารณะ {getattr(public_channel, 'mention', '#unknown')}: {', '.join(public_missing)}")
        return _redirect_notice(
            "บอทยังไม่มีสิทธิ์ที่จำเป็นในห้องที่เลือก: " + " | ".join(lines)
        )

    is_first_setup = not bool(promote_data)
    enabled_value = bool(promote_data.get("enabled", True)) if promote_data else True
    storage_failed = False
    try:
        if not promote_data:
            promote_data = await storage.promote_channels.insert(
                guild_id=guild_id,
                submit_channel_id=int(submit_raw),
                public_channel_id=int(public_raw),
                cooldown_seconds=PROMOTE_COOLDOWN_SECONDS,
                cooldowns={},
                enabled=enabled_value,
            )
        else:
            promote_row_id = int(promote_data.get("id") or 0) if str(promote_data.get("id") or "").isdigit() else 0
            if promote_row_id <= 0:
                latest_promote_data = await storage.promote_channels.get(guild_id=guild_id)
                if latest_promote_data:
                    promote_data = latest_promote_data
                    promote_row_id = int(promote_data.get("id") or 0) if str(promote_data.get("id") or "").isdigit() else 0
            if promote_row_id <= 0:
                promote_data = await storage.promote_channels.insert(
                    guild_id=guild_id,
                    submit_channel_id=int(submit_raw),
                    public_channel_id=int(public_raw),
                    cooldown_seconds=PROMOTE_COOLDOWN_SECONDS,
                    cooldowns={},
                    enabled=enabled_value,
                )
                promote_row_id = int(promote_data.get("id") or 0) if str(promote_data.get("id") or "").isdigit() else 0
            if promote_row_id > 0:
                updated_row = await storage.promote_channels.update(
                    id=promote_row_id,
                    submit_channel_id=int(submit_raw),
                    public_channel_id=int(public_raw),
                    enabled=enabled_value,
                )
                if isinstance(updated_row, dict):
                    promote_data.update(updated_row)
    except Exception as error:
        storage_failed = True
        logger.warning(
            "promote_web_update_settings save failed | guild=%s error=%s",
            guild_id,
            error,
        )

    cache_snapshot = dict(promote_data or {})
    cache_snapshot["guild_id"] = int(guild_id)
    cache_snapshot["submit_channel_id"] = int(submit_raw)
    cache_snapshot["public_channel_id"] = int(public_raw)
    cache_snapshot["enabled"] = bool(enabled_value)
    if not str(cache_snapshot.get("cooldown_seconds") or "").strip().isdigit():
        cache_snapshot["cooldown_seconds"] = int(PROMOTE_COOLDOWN_SECONDS)
    if not isinstance(cache_snapshot.get("cooldowns"), dict):
        cache_snapshot["cooldowns"] = {}
    cache.promote_channels[str(guild_id)] = cache_snapshot

    if is_first_setup and str(getattr(public_channel, "type", "")) in {"text", "news"}:
        try:
            welcome_embed = discord.Embed(
                title="เปิดใช้งานห้องโปรโมตสาธารณะแล้ว",
                description=(
                    "ห้องนี้ถูกตั้งเป็นห้องโปรโมตสาธารณะของเซิร์ฟเวอร์นี้\n"
                    "โพสต์โปรโมตใหม่ที่อนุมัติแล้วจะถูกส่งมายังห้องนี้อัตโนมัติ"
                ),
                color=discord.Color.blurple(),
            )
            welcome_embed.set_image(url=style_urls.PROMOTE_FIRST_SETUP_IMAGE)
            welcome_embed.set_footer(text="SkylineBOT Promote")
            await public_channel.send(embed=welcome_embed)
        except Exception as exc:
            logger.warning(
                "ไม่สามารถส่งรูปแนะนำโปรโมตครั้งแรกได้ | guild=%s channel=%s err=%s",
                guild_id,
                int(public_raw),
                exc,
            )

    await _append_dashboard_audit_event(guild_id, session, "อัปเดตห้องโปรโมตแล้ว", target="promote")
    suspension_reason = _promote_suspension_reason(guild_id, _promote_suspension_map_from_db())
    notice_text = "บันทึกห้องโปรโมตแล้ว"
    if storage_failed:
        notice_text = f"{notice_text} (โหมดชั่วคราว: ใช้ค่าในหน่วยความจำ เนื่องจากฐานข้อมูลไม่พร้อม)"
    if suspension_reason:
        notice_text = f"{notice_text} | {suspension_reason}"
    return _redirect_notice(notice_text)

async def update_temp_links_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="temp_links",
    )
    if guard_response:
        return guard_response
    await _ensure_dashboard_config_cache()
    data = await _parse_form(request)
    current = _temp_links_settings_from_db(guild_id)
    max_age_minutes = _int_from_form(
        data,
        "max_age_minutes",
        max(1, round(int(current.get("max_age_seconds") or 3600) / 60)),
        1,
        10080,
    )
    merged = {
        **current,
        "enabled": _bool_from_form(data, "enabled"),
        "channel_id": (data.get("channel_id") or "").strip(),
        "max_uses": _int_from_form(data, "max_uses", int(current.get("max_uses") or 1), 1, 100),
        "max_age_seconds": int(max_age_minutes) * 60,
        "temporary_membership": _bool_from_form(data, "temporary_membership"),
        "unique_per_member": _bool_from_form(data, "unique_per_member"),
        "history": current.get("history") or [],
    }
    payload = _normalize_temp_links_settings(merged)
    await _set_dashboard_config_value(
        _temp_links_config_key(guild_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าลิงก์ชั่วคราวแล้ว", target="temp_links")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': 'บันทึกการตั้งค่าลิงก์ชั่วคราวแล้ว'}).split('=',1)[1]}",
        status_code=303,
    )

async def create_temp_link(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
        tab_slug="temp_links",
    )
    if guard_response:
        return guard_response
    await _ensure_dashboard_config_cache()
    data = await _parse_form(request)
    settings = _temp_links_settings_from_db(guild_id)
    if not bool(settings.get("enabled")):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': 'ระบบลิงก์ชั่วคราวยังปิดใช้งานอยู่'}).split('=',1)[1]}",
            status_code=303,
        )

    default_channel_id = str(settings.get("channel_id") or "").strip()
    channel_id = (data.get("channel_id") or "").strip() or default_channel_id
    if not channel_id.isdigit():
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': 'กรุณาเลือกห้องสำหรับลิงก์ชั่วคราว'}).split('=',1)[1]}",
            status_code=303,
        )

    max_uses = _int_from_form(data, "max_uses", int(settings.get("max_uses") or 1), 1, 100)
    max_age_minutes = _int_from_form(
        data,
        "max_age_minutes",
        max(1, round(int(settings.get("max_age_seconds") or 3600) / 60)),
        1,
        10080,
    )
    max_age_seconds = int(max_age_minutes) * 60
    temporary_membership = _bool_from_form(data, "temporary_membership")

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': 'ไม่พบกิลด์นี้ในระบบบอท'}).split('=',1)[1]}",
            status_code=303,
        )
    channel = bot_guild.get_channel(int(channel_id))
    if not channel or not hasattr(channel, "create_invite"):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': 'บอทไม่สามารถสร้างลิงก์เชิญในห้องที่เลือกได้'}).split('=',1)[1]}",
            status_code=303,
        )

    me = getattr(bot_guild, "me", None)
    try:
        if me and hasattr(channel, "permissions_for"):
            perms = channel.permissions_for(me)
            if not getattr(perms, "create_instant_invite", False):
                return RedirectResponse(
                    f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': 'บอทไม่มีสิทธิ์สร้างลิงก์เชิญในห้องนี้'}).split('=',1)[1]}",
                    status_code=303,
                )
    except Exception:
        pass

    user = (session or {}).get("user") or {}
    creator_id = str(_session_user_id(session) or "").strip()
    creator_name = str(user.get("username") or user.get("global_name") or "unknown").strip()[:120] or "unknown"
    unique_per_member = bool(settings.get("unique_per_member", True))
    now_dt = datetime.datetime.now(tz=datetime.timezone.utc)
    now_ts = int(now_dt.timestamp())
    if unique_per_member and creator_id:
        for row in (settings.get("history") or []):
            if str(row.get("creator_id") or "").strip() != creator_id:
                continue
            created_raw = str(row.get("created_at") or "").strip()
            try:
                created_dt = datetime.datetime.fromisoformat(created_raw)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=datetime.timezone.utc)
                if now_ts - int(created_dt.timestamp()) <= 300:
                    old_url = str(row.get("url") or "").strip()
                    if old_url:
                        return RedirectResponse(
                            f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': f'ลิงก์ล่าสุดของคุณ: {old_url}'}).split('=',1)[1]}",
                            status_code=303,
                        )
            except Exception:
                continue

    try:
        invite = await channel.create_invite(
            max_age=max_age_seconds,
            max_uses=max_uses,
            temporary=temporary_membership,
            unique=True,
            reason=f"ลิงก์ชั่วคราวจากแดชบอร์ดโดย {creator_name} ({creator_id or 'ไม่ทราบ'})",
        )
    except Exception as error:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/temp_links?notice={urlencode({'notice': f'สร้างลิงก์เชิญไม่สำเร็จ: {error}'}).split('=',1)[1]}",
            status_code=303,
        )

    new_entry = {
        "url": str(getattr(invite, "url", "") or "").strip(),
        "code": str(getattr(invite, "code", "") or "").strip(),
        "created_at": now_dt.isoformat(),
        "creator_id": creator_id,
        "creator_name": creator_name,
        "channel_id": channel_id,
        "max_uses": max_uses,
        "max_age_seconds": max_age_seconds,
        "temporary_membership": temporary_membership,
    }
    updated_payload = {
        **settings,
        "history": [new_entry, *(settings.get("history") or [])],
    }
    normalized = _normalize_temp_links_settings(updated_payload)
    await _set_dashboard_config_value(
        _temp_links_config_key(guild_id),
        json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
    )
    await _append_dashboard_audit_event(guild_id, session, "สร้างลิงก์เชิญชั่วคราวแล้ว", target="temp_links")
    notice_text = f"สร้างลิงก์ชั่วคราวแล้ว: {new_entry['url']}"
    notice_query = urlencode({"notice": notice_text}).split("=", 1)[1]
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/temp_links?notice={notice_query}",
        status_code=303,
    )

async def toggle_command(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)
    command_name = (data.get("command_name") or "").strip().lower()
    action = (data.get("action") or "disable").strip().lower()
    known_commands = {item["name"] for item in _command_catalog(language="en")}
    command_access_state = state.get("command_access") or {}
    disabled = set(command_access_state.get("disabled_commands", []) or [])
    command_access_id = command_access_state.get("id")
    if not command_access_id:
        existing = await storage.command_access.get(guild_id=guild_id)
        if not existing:
            existing = await storage.command_access.insert(guild_id=guild_id, disabled_commands=[])
        command_access_id = existing.get("id")
        if not command_access_id:
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/commands?notice={urlencode({'notice': 'ไม่สามารถอัปเดตคำสั่งได้ในขณะนี้'}).split('=',1)[1]}",
                status_code=303,
            )

    audit_message = "อัปเดตการเข้าถึงคำสั่งแล้ว"
    if action == "enable_all":
        disabled.clear()
        audit_message = "เปิดใช้งานคำสั่งทั้งหมดในกิลด์แล้ว"
    elif action == "disable_all":
        disabled = set(known_commands)
        audit_message = "ปิดใช้งานคำสั่งทั้งหมดในกิลด์แล้ว"
    else:
        if command_name not in known_commands:
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/commands?notice={urlencode({'notice': 'ไม่พบคำสั่งที่ระบุ'}).split('=',1)[1]}",
                status_code=303,
            )
        required_tier = _required_plan_for_command(command_name)
        current_plan = _dashboard_effective_plan_tier(state, session=session)
        if not _is_plan_at_least(current_plan, required_tier):
            message = f" /{command_name} ต้องใช้แพ็กเกจ {required_tier.capitalize()} "
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/commands?notice={urlencode({'notice': message}).split('=',1)[1]}",
                status_code=303,
            )
        if action == "enable":
            disabled.discard(command_name)
            audit_message = f"เปิดใช้งานคำสั่ง /{command_name}"
        else:
            disabled.add(command_name)
            audit_message = f"ปิดใช้งานคำสั่ง /{command_name}"

    await storage.command_access.update(id=command_access_id, disabled_commands=sorted(disabled))
    await _append_dashboard_audit_event(
        guild_id,
        session,
        audit_message,
        target="commands",
    )
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/commands?notice={urlencode({'notice': 'อัปเดตการเข้าถึงคำสั่งแล้ว'}).split('=',1)[1]}",
        status_code=303,
    )

async def update_giveaway_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)
    required_role_id = int(data["required_role_id"]) if data.get("required_role_id", "").isdigit() else None
    await storage.giveaways_permissions.update(id=state["giveaway_permissions"]["id"], required_role_id=required_role_id)
    giveaway_payload = _normalize_giveaway_dashboard_settings(
        {
            "default_channel_id": (data.get("default_channel_id") or "").strip() or None,
            "default_duration": (data.get("default_duration") or "").strip(),
            "default_winners": _int_from_form(data, "default_winners", 1, 1, 50),
            "default_prize": (data.get("default_prize") or "").strip(),
            "embed_title": (data.get("embed_title") or "").strip(),
            "embed_description": (data.get("embed_description") or "").strip(),
            "embed_color": (data.get("embed_color") or "").strip(),
        }
    )
    await _set_dashboard_config_value(
        _giveaway_dashboard_config_key(guild_id),
        json.dumps(giveaway_payload, ensure_ascii=False),
    )
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่ากิฟอะเวย์แล้ว", target="giveaways")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': 'บันทึกการตั้งค่ากิฟอะเวย์แล้ว'}).split('=',1)[1]}", status_code=303)

async def create_giveaway_from_web(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)

    channel_id = int(data["channel_id"]) if data.get("channel_id", "").isdigit() else None
    duration_text = (data.get("duration") or "").strip()
    winner_limit = _int_from_form(data, "winner_limit", 1, 1, 50)
    prize = (data.get("prize") or "").strip()[:180]

    if not channel_id:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': 'กรุณาเลือกห้องสำหรับกิฟอะเวย์'}).split('=',1)[1]}",
            status_code=303,
        )
    duration_seconds = _parse_duration_to_seconds_web(duration_text)
    if not duration_seconds:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': 'รูปแบบระยะเวลาไม่ถูกต้อง เช่น 30m, 1h, 1d2h'}).split('=',1)[1]}",
            status_code=303,
        )
    if not prize:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': 'กรุณาระบุของรางวัล'}).split('=',1)[1]}",
            status_code=303,
        )

    bot = get_bot()
    bot_guild = bot.get_guild(guild_id) if bot else None
    if not bot_guild:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': 'ไม่พบกิลด์นี้ในระบบบอทที่กำลังทำงาน'}).split('=',1)[1]}",
            status_code=303,
        )
    channel = bot_guild.get_channel(channel_id) if bot_guild else None
    if not channel:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': 'ไม่พบห้องที่เลือกหรือบอทเข้าถึงไม่ได้'}).split('=',1)[1]}",
            status_code=303,
        )

    guild_subscription = str((cache.guilds.get(str(guild_id), {}) or {}).get("subscription") or "free")
    if guild_subscription in {"diamond_guild_premium", "permanent_guild_premium", "lifetime_guild_premium"}:
        giveaway_limit = 10
    elif guild_subscription == "golden_guild_premium":
        giveaway_limit = 5
    elif guild_subscription == "silver_guild_preminum":
        giveaway_limit = 3
    else:
        giveaway_limit = 1
    guild_giveaways = cache.giveaways.get(str(guild_id), {}) or {}
    running_count = sum(1 for g in guild_giveaways.values() if not g.get("ended"))
    if running_count >= giveaway_limit:
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': f'เซิร์ฟเวอร์นี้อนุญาตกิฟอะเวย์ที่กำลังทำงานได้สูงสุด {giveaway_limit} รายการ'}).split('=',1)[1]}",
            status_code=303,
        )

    settings = _giveaway_dashboard_settings_from_db(guild_id)
    user_id = _session_user_id(session) or int(bot_guild.owner_id or 0) or 0
    ends_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration_seconds)
    giveaway_row = await storage.giveaways.insert(
        guild_id=guild_id,
        channel_id=channel_id,
        host_id=user_id,
        winner_limit=winner_limit,
        prize=prize,
        ends_at=ends_at.isoformat(),
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

    giveaway_cog = bot.get_cog("Giveaway") if bot else None
    if giveaway_cog and giveaway_row:
        try:
            web_data = dict(giveaway_row)
            web_data["embed_title"] = settings.get("embed_title")
            web_data["embed_description"] = settings.get("embed_description")
            web_data["embed_color"] = settings.get("embed_color")
            asyncio.create_task(giveaway_cog.create_giveaway_message(data=web_data, channel=channel, waiting_message=None))
        except Exception:
            pass

    await _append_dashboard_audit_event(guild_id, session, f"สร้างกิฟอะเวย์แล้ว ({prize})", target="giveaways")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/giveaways?notice={urlencode({'notice': 'สร้างกิฟอะเวย์จากเว็บแดชบอร์ดแล้ว'}).split('=',1)[1]}",
        status_code=303,
    )

async def update_ticket_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)
    module = sorted(state["ticket_modules"], key=lambda item: item.get("ticket_module_id", 0))[0]
    support_roles = [int(item.strip()) for item in (data.get("support_roles") or "").split(",") if item.strip().isdigit()]
    panel_message_content = (data.get("ticket_panel_message_content") or "").strip()
    panel_embed_title = str(data.get("ticket_panel_embed_title") or "").strip()[:120]
    panel_embed_image_url = str(data.get("ticket_panel_embed_image_url") or "").strip()[:1000]
    panel_button_label = str(data.get("ticket_panel_button_label") or "").strip()[:45]
    panel_button_color = str(data.get("ticket_panel_button_color") or "blurple").strip().lower()
    if panel_button_color not in {"green", "blurple", "red", "gray"}:
        panel_button_color = "blurple"
    panel_button_emoji = str(data.get("ticket_panel_button_emoji") or "").strip()[:64]
    panel_embed_data = module.get("ticket_panel_message_embed") or {}
    if isinstance(panel_embed_data, str):
        try:
            panel_embed_data = json.loads(panel_embed_data)
        except Exception:
            panel_embed_data = {}
    if not isinstance(panel_embed_data, dict):
        panel_embed_data = {}
    panel_embed_payload = dict(panel_embed_data)
    if panel_embed_title:
        panel_embed_payload["title"] = panel_embed_title
    else:
        panel_embed_payload.pop("title", None)
    if panel_message_content:
        panel_embed_payload["description"] = panel_message_content[:4000]
    else:
        panel_embed_payload.pop("description", None)
    if panel_button_label:
        panel_embed_payload["button_label"] = panel_button_label
        panel_embed_payload["button_text"] = panel_button_label
    else:
        panel_embed_payload.pop("button_label", None)
        panel_embed_payload.pop("button_text", None)
    panel_embed_payload["button_color"] = panel_button_color
    if panel_button_emoji:
        panel_embed_payload["button_emoji"] = panel_button_emoji
        panel_embed_payload["emoji"] = panel_button_emoji
    else:
        panel_embed_payload.pop("button_emoji", None)
        panel_embed_payload.pop("emoji", None)
    if panel_embed_image_url:
        panel_embed_payload["image_url"] = panel_embed_image_url
    else:
        panel_embed_payload.pop("image_url", None)
        panel_embed_payload.pop("image", None)
        panel_embed_payload.pop("thumbnail", None)

    updated_module = await storage.ticket_settings.update(
        id=module["id"],
        enabled=_bool_from_form(data, "enabled"),
        support_roles=support_roles,
        ticket_limit=int(data.get("ticket_limit", 1) or 1),
        open_ticket_category_id=int(data["open_ticket_category_id"]) if data.get("open_ticket_category_id", "").isdigit() else None,
        closed_ticket_category_id=int(data["closed_ticket_category_id"]) if data.get("closed_ticket_category_id", "").isdigit() else None,
        ticket_panel_channel_id=int(data["ticket_panel_channel_id"]) if data.get("ticket_panel_channel_id", "").isdigit() else None,
        ticket_panel_message_content=panel_message_content or None,
        ticket_panel_message_embed=panel_embed_payload,
        close_ticket_message_content=(data.get("close_ticket_message_content") or "").strip() or None,
    )
    bot = get_bot()
    if bot and updated_module:
        try:
            await ticket_panel.send_ticket_panel_message(updated_module, bot)
            open_tickets = await storage.tickets.gets(
                guild_id=guild_id,
                ticket_module_id=updated_module.get("ticket_module_id"),
                closed=False,
                deleted=False,
            )
            for ticket in open_tickets:
                await ticket_panel.send_close_ticket_module(ticket, bot)
        except Exception:
            pass
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าโมดูลทิกเก็ตแล้ว", target="tickets")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/tickets?notice={urlencode({'notice': 'บันทึกการตั้งค่าโมดูลทิกเก็ตแล้ว'}).split('=',1)[1]}", status_code=303)

async def update_shop_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(
        session=session,
        current_guild=current_guild,
        state=state,
        guild_id=guild_id,
        request=request,
    )
    if guard_response:
        return guard_response

    def _shop_redirect(notice_text: str):
        encoded = urlencode({"notice": notice_text}).split("=", 1)[1]
        return RedirectResponse(f"/dashboard/guild/{guild_id}/shop?notice={encoded}", status_code=303)

    data = await _parse_form(request)
    action = str(data.get("shop_action") or "save_settings").strip().lower()
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    product_limit = shop_flow.product_limit_for_plan(plan_tier)
    can_truemoney = shop_flow.is_shop_feature_allowed(plan_tier, "payment_truemoney_gift")
    can_shipok = shop_flow.is_shop_feature_allowed(plan_tier, "payment_shipok")
    can_auto_verify = shop_flow.is_shop_feature_allowed(plan_tier, "auto_verify")
    can_auto_delivery = shop_flow.is_shop_feature_allowed(plan_tier, "auto_delivery")
    can_delivery_dm_text = shop_flow.is_shop_feature_allowed(plan_tier, "delivery_dm_text")
    can_delivery_role = shop_flow.is_shop_feature_allowed(plan_tier, "delivery_role")
    can_auto_open_failed_ticket = shop_flow.is_shop_feature_allowed(plan_tier, "auto_open_failed_delivery_ticket")

    settings_row = await storage.shop_settings.get(guild_id=guild_id)
    if not settings_row:
        await storage.shop_settings.insert(guild_id=guild_id)
        settings_row = await storage.shop_settings.get(guild_id=guild_id) or {}
    settings_id = int(settings_row.get("id") or 0)
    if settings_id <= 0:
        return _shop_redirect("Shop settings unavailable. Please try again.")

    if action == "save_settings":
        payment_mode = shop_flow.normalize_payment_mode(data.get("payment_mode"))
        warnings: list[str] = []
        if payment_mode == "truemoney_gift" and not can_truemoney:
            payment_mode = "manual"
            warnings.append("TrueMoney gift payment requires Silver+ plan.")
        if payment_mode == "shipok" and not can_shipok:
            payment_mode = "manual"
            warnings.append("SHIPOK/SlipOK payment requires Gole+ plan.")
        promptpay_number = "".join(ch for ch in str(data.get("promptpay_number") or "") if ch.isdigit())[:20]
        truemoney_phone = "".join(ch for ch in str(data.get("truemoney_phone") or "") if ch.isdigit())[:20]
        support_role_ids = shop_flow.parse_role_ids(data.get("support_role_ids"))
        shop_channel_id = int(data.get("shop_channel_id")) if str(data.get("shop_channel_id") or "").isdigit() else None
        order_log_channel_id = int(data.get("order_log_channel_id")) if str(data.get("order_log_channel_id") or "").isdigit() else None
        admin_contact_channel_id = int(data.get("admin_contact_channel_id")) if str(data.get("admin_contact_channel_id") or "").isdigit() else None
        auto_verify_enabled = _bool_from_form(data, "auto_verify") and can_auto_verify
        auto_delivery_enabled = _bool_from_form(data, "auto_delivery") and can_auto_delivery
        truemoney_gift_enabled = _bool_from_form(data, "truemoney_gift_enabled") and can_truemoney
        shipok_enabled = _bool_from_form(data, "shipok_enabled") and can_shipok
        auto_open_failed_ticket = _bool_from_form(data, "auto_open_ticket_on_failed_delivery") and can_auto_open_failed_ticket
        slipcheck_verify_engine_raw = str(data.get("slipcheck_verify_engine") or "slipok").strip().lower()
        if slipcheck_verify_engine_raw in {"skylinebot", "skyline", "skylinebot_slip", "skyline_slip", "internal", "ocr"}:
            slipcheck_verify_engine = "skylinebotslip"
        else:
            slipcheck_verify_engine = "slipok"
        slipcheck_receiver_name = str(data.get("slipcheck_expected_receiver_name") or "").strip()[:220]
        slipcheck_receiver_first_name_th = str(data.get("slipcheck_expected_receiver_first_name_th") or "").strip()[:120]
        slipcheck_receiver_last_name_th = str(data.get("slipcheck_expected_receiver_last_name_th") or "").strip()[:120]
        slipcheck_receiver_first_name_en = str(data.get("slipcheck_expected_receiver_first_name_en") or "").strip()[:120]
        slipcheck_receiver_last_name_en = str(data.get("slipcheck_expected_receiver_last_name_en") or "").strip()[:120]
        slipcheck_receiver_bank = str(data.get("slipcheck_expected_receiver_bank") or "").strip()[:220]
        slipcheck_receiver_account = "".join(ch for ch in str(data.get("slipcheck_expected_receiver_account") or "") if ch.isdigit())[:30]
        slipcheck_sender_name = str(data.get("slipcheck_expected_sender_name") or "").strip()[:220]
        slipcheck_sender_first_name_th = str(data.get("slipcheck_expected_sender_first_name_th") or "").strip()[:120]
        slipcheck_sender_last_name_th = str(data.get("slipcheck_expected_sender_last_name_th") or "").strip()[:120]
        slipcheck_sender_first_name_en = str(data.get("slipcheck_expected_sender_first_name_en") or "").strip()[:120]
        slipcheck_sender_last_name_en = str(data.get("slipcheck_expected_sender_last_name_en") or "").strip()[:120]
        slipcheck_sender_bank = str(data.get("slipcheck_expected_sender_bank") or "").strip()[:220]
        slipcheck_sender_account = "".join(ch for ch in str(data.get("slipcheck_expected_sender_account") or "") if ch.isdigit())[:30]
        slipcheck_expected_reference = str(data.get("slipcheck_expected_reference") or "").strip()[:120]
        slipcheck_expected_qr_reference = str(data.get("slipcheck_expected_qr_reference") or "").strip()[:300]
        slipcheck_max_age_minutes = _int_from_form(data, "slipcheck_max_age_minutes", 1440, 0, 60 * 24 * 30)
        slipcheck_duplicate_window_hours = _int_from_form(data, "slipcheck_duplicate_window_hours", 72, 1, 24 * 90)
        try:
            slipcheck_auto_approve_confidence = round(
                max(0.0, min(100.0, float(str(data.get("slipcheck_auto_approve_confidence") or "85").strip()))),
                2,
            )
        except Exception:
            slipcheck_auto_approve_confidence = 85.0
        try:
            slipcheck_manual_review_confidence = round(
                max(0.0, min(100.0, float(str(data.get("slipcheck_manual_review_confidence") or "55").strip()))),
                2,
            )
        except Exception:
            slipcheck_manual_review_confidence = 55.0
        slipcheck_review_channel_id = (
            int(str(data.get("slipcheck_review_channel_id") or "").strip())
            if str(data.get("slipcheck_review_channel_id") or "").strip().isdigit()
            else None
        )
        slipcheck_dm_ids_raw = str(data.get("slipcheck_review_dm_user_ids") or "").strip()
        slipcheck_dm_ids: list[str] = []
        for token in slipcheck_dm_ids_raw.replace(";", ",").replace("\n", ",").replace("\t", ",").replace(" ", ",").split(","):
            token = str(token or "").strip()
            if not token.isdigit() or token in slipcheck_dm_ids:
                continue
            slipcheck_dm_ids.append(token)
            if len(slipcheck_dm_ids) >= 20:
                break
        slipcheck_review_dm_user_ids = ",".join(slipcheck_dm_ids)
        if _bool_from_form(data, "auto_verify") and not can_auto_verify:
            warnings.append("Auto verify requires Silver+ plan.")
        if _bool_from_form(data, "auto_delivery") and not can_auto_delivery:
            warnings.append("Auto delivery requires Gole+ plan.")
        if _bool_from_form(data, "auto_open_ticket_on_failed_delivery") and not can_auto_open_failed_ticket:
            warnings.append("Auto open support ticket on failed delivery requires Diamond plan.")

        await storage.shop_settings.update(
            id=settings_id,
            enabled=_bool_from_form(data, "enabled"),
            currency_symbol=(str(data.get("currency_symbol") or "THB").strip()[:12] or "THB"),
            payment_mode=payment_mode,
            allow_wallet_payment=_bool_from_form(data, "allow_wallet_payment"),
            auto_verify=auto_verify_enabled,
            auto_delivery=auto_delivery_enabled,
            auto_open_ticket_on_failed_delivery=auto_open_failed_ticket,
            promptpay_number=promptpay_number,
            truemoney_phone=truemoney_phone,
            truemoney_gift_enabled=truemoney_gift_enabled,
            shipok_enabled=shipok_enabled,
            slipcheck_verify_engine=slipcheck_verify_engine,
            slipok_api_url=(str(data.get("slipok_api_url") or "").strip()[:280]),
            slipok_key=(str(data.get("slipok_key") or "").strip()[:240]),
            slipcheck_expected_receiver_name=slipcheck_receiver_name,
            slipcheck_expected_receiver_first_name_th=slipcheck_receiver_first_name_th,
            slipcheck_expected_receiver_last_name_th=slipcheck_receiver_last_name_th,
            slipcheck_expected_receiver_first_name_en=slipcheck_receiver_first_name_en,
            slipcheck_expected_receiver_last_name_en=slipcheck_receiver_last_name_en,
            slipcheck_expected_receiver_bank=slipcheck_receiver_bank,
            slipcheck_expected_receiver_account=slipcheck_receiver_account,
            slipcheck_expected_sender_name=slipcheck_sender_name,
            slipcheck_expected_sender_first_name_th=slipcheck_sender_first_name_th,
            slipcheck_expected_sender_last_name_th=slipcheck_sender_last_name_th,
            slipcheck_expected_sender_first_name_en=slipcheck_sender_first_name_en,
            slipcheck_expected_sender_last_name_en=slipcheck_sender_last_name_en,
            slipcheck_expected_sender_bank=slipcheck_sender_bank,
            slipcheck_expected_sender_account=slipcheck_sender_account,
            slipcheck_expected_reference=slipcheck_expected_reference,
            slipcheck_expected_qr_reference=slipcheck_expected_qr_reference,
            slipcheck_max_age_minutes=slipcheck_max_age_minutes,
            slipcheck_auto_approve_confidence=slipcheck_auto_approve_confidence,
            slipcheck_manual_review_confidence=slipcheck_manual_review_confidence,
            slipcheck_duplicate_window_hours=slipcheck_duplicate_window_hours,
            slipcheck_review_channel_id=slipcheck_review_channel_id,
            slipcheck_review_dm_user_ids=slipcheck_review_dm_user_ids,
            support_role_ids=support_role_ids,
            buyer_view_only_roles=_bool_from_form(data, "buyer_view_only_roles"),
            shop_channel_id=shop_channel_id,
            order_log_channel_id=order_log_channel_id,
            admin_contact_channel_id=admin_contact_channel_id,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        await _append_dashboard_audit_event(guild_id, session, "Updated guild shop settings", target="shop")
        notice_text = "Saved shop settings."
        if warnings:
            notice_text += " " + " ".join(warnings[:3])
        return _shop_redirect(notice_text)

    if action == "add_product":
        current_products_count = await storage.shop_products.count(guild_id=guild_id)
        if int(current_products_count or 0) >= int(product_limit):
            return _shop_redirect(
                f"Your current plan ({plan_tier}) allows up to {product_limit} products."
            )
        name = str(data.get("name") or "").strip()[:120]
        if not name:
            return _shop_redirect("Product name is required.")

        sku_text = str(data.get("sku") or "").strip().upper()
        if not sku_text:
            sku_text = f"P{int(time.time())}"
        try:
            price_value = float(str(data.get("price") or "0").strip() or 0.0)
        except Exception:
            price_value = 0.0
        stock_value = _int_from_form(data, "stock", 0, -1, 999999999)
        normalized_delivery_type = shop_flow.normalize_delivery_type(data.get("delivery_type"))
        delivery_warnings: list[str] = []
        if normalized_delivery_type == "role" and not can_delivery_role:
            normalized_delivery_type = "none"
            delivery_warnings.append("Role auto-delivery requires Diamond plan.")
        elif normalized_delivery_type in {"dm", "text"} and not can_delivery_dm_text:
            normalized_delivery_type = "none"
            delivery_warnings.append("DM auto-delivery requires Silver+ plan.")
        delivery_role_id = int(data.get("delivery_role_id")) if str(data.get("delivery_role_id") or "").isdigit() else None
        normalized = shop_flow.normalize_shop_product(
            {
                "guild_id": guild_id,
                "sku": sku_text,
                "name": name,
                "description": str(data.get("description") or "").strip()[:2000],
                "price": max(0.0, float(price_value)),
                "stock": stock_value,
                "image_url": str(data.get("image_url") or "").strip()[:500],
                "enabled": _bool_from_form(data, "enabled"),
                "visible_role_ids": shop_flow.parse_role_ids(data.get("visible_role_ids")),
                "buy_role_ids": shop_flow.parse_role_ids(data.get("buy_role_ids")),
                "delivery_type": normalized_delivery_type,
                "delivery_role_id": delivery_role_id,
                "delivery_payload": str(data.get("delivery_payload") or ""),
                "delivery_note": str(data.get("delivery_note") or "").strip()[:1200],
                "sort_order": _int_from_form(data, "sort_order", 0, -99999, 99999),
            }
        )
        try:
            await storage.shop_products.insert(
                guild_id=guild_id,
                sku=normalized.get("sku"),
                name=normalized.get("name"),
                description=normalized.get("description"),
                price=normalized.get("price"),
                stock=normalized.get("stock"),
                image_url=normalized.get("image_url"),
                enabled=bool(normalized.get("enabled")),
                visible_role_ids=normalized.get("visible_role_ids") or [],
                buy_role_ids=normalized.get("buy_role_ids") or [],
                delivery_type=normalized.get("delivery_type"),
                delivery_role_id=normalized.get("delivery_role_id"),
                delivery_payload=normalized.get("delivery_payload") or "",
                delivery_note=normalized.get("delivery_note") or "",
                sort_order=int(normalized.get("sort_order") or 0),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception as error:
            return _shop_redirect(f"Unable to add product: {type(error).__name__}")
        await _append_dashboard_audit_event(guild_id, session, f"Added shop product: {name}", target="shop")
        notice_text = "Added product."
        if delivery_warnings:
            notice_text += " " + " ".join(delivery_warnings[:2])
        return _shop_redirect(notice_text)

    if action == "update_product":
        product_id = int(data.get("product_id")) if str(data.get("product_id") or "").isdigit() else 0
        if product_id <= 0:
            return _shop_redirect("Invalid product id.")
        existing = await storage.shop_products.get(id=product_id)
        if not existing or int(existing.get("guild_id") or 0) != int(guild_id):
            return _shop_redirect("Product not found.")

        sku_text = str(data.get("sku") or "").strip().upper() or str(existing.get("sku") or "").strip().upper()
        name = str(_posted_form_value(data, "name", existing.get("name") or "") or "").strip()[:120]
        if not name:
            return _shop_redirect("Product name is required.")
        try:
            price_value = float(
                str(_posted_form_value(data, "price", existing.get("price") or 0) or "").strip() or 0.0
            )
        except Exception:
            price_value = 0.0
        stock_value = _int_from_form(
            data,
            "stock",
            int(existing.get("stock") or 0),
            -1,
            999999999,
        )
        normalized_delivery_type = shop_flow.normalize_delivery_type(data.get("delivery_type"))
        delivery_warnings: list[str] = []
        if normalized_delivery_type == "role" and not can_delivery_role:
            normalized_delivery_type = "none"
            delivery_warnings.append("Role auto-delivery requires Diamond plan.")
        elif normalized_delivery_type in {"dm", "text"} and not can_delivery_dm_text:
            normalized_delivery_type = "none"
            delivery_warnings.append("DM auto-delivery requires Silver+ plan.")
        delivery_role_id = int(data.get("delivery_role_id")) if str(data.get("delivery_role_id") or "").isdigit() else None
        merged = dict(existing)
        merged.update(
            {
                "sku": sku_text,
                "name": name,
                "description": str(data.get("description") or "").strip()[:2000],
                "price": max(0.0, float(price_value)),
                "stock": stock_value,
                "image_url": str(data.get("image_url") or "").strip()[:500],
                "enabled": _bool_from_form(data, "enabled"),
                "visible_role_ids": shop_flow.parse_role_ids(data.get("visible_role_ids")),
                "buy_role_ids": shop_flow.parse_role_ids(data.get("buy_role_ids")),
                "delivery_type": normalized_delivery_type,
                "delivery_role_id": delivery_role_id,
                "delivery_payload": str(data.get("delivery_payload") or ""),
                "delivery_note": str(data.get("delivery_note") or "").strip()[:1200],
                "sort_order": _int_from_form(
                    data,
                    "sort_order",
                    int(existing.get("sort_order") or 0),
                    -99999,
                    99999,
                ),
            }
        )
        normalized = shop_flow.normalize_shop_product(merged)
        try:
            await storage.shop_products.update(
                id=product_id,
                sku=normalized.get("sku"),
                name=normalized.get("name"),
                description=normalized.get("description"),
                price=normalized.get("price"),
                stock=normalized.get("stock"),
                image_url=normalized.get("image_url"),
                enabled=bool(normalized.get("enabled")),
                visible_role_ids=normalized.get("visible_role_ids") or [],
                buy_role_ids=normalized.get("buy_role_ids") or [],
                delivery_type=normalized.get("delivery_type"),
                delivery_role_id=normalized.get("delivery_role_id"),
                delivery_payload=normalized.get("delivery_payload") or "",
                delivery_note=normalized.get("delivery_note") or "",
                sort_order=int(normalized.get("sort_order") or 0),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception as error:
            return _shop_redirect(f"Unable to update product: {type(error).__name__}")
        await _append_dashboard_audit_event(guild_id, session, f"Updated shop product #{product_id}", target="shop")
        notice_text = "Updated product."
        if delivery_warnings:
            notice_text += " " + " ".join(delivery_warnings[:2])
        return _shop_redirect(notice_text)

    if action == "delete_product":
        product_id = int(data.get("product_id")) if str(data.get("product_id") or "").isdigit() else 0
        if product_id <= 0:
            return _shop_redirect("Invalid product id.")
        await storage.shop_products.delete(id=product_id, guild_id=guild_id)
        await _append_dashboard_audit_event(guild_id, session, f"Deleted shop product #{product_id}", target="shop")
        return _shop_redirect("Deleted product.")

    return _shop_redirect("Unsupported shop action.")

async def update_welcomer_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    form = await request.form()
    data = {k: str(v) for k, v in form.items() if k != "welcome_embed_image_file"}
    existing = state.get("welcomer") or {}
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    can_use_image_cards = _is_plan_at_least(plan_tier, "silver")

    # Keep backward compatibility for older forms and route aliases.
    form_section = (data.get("form_section") or "").strip().lower()
    requested_redirect_tab = (data.get("redirect_tab") or "").strip().lower()
    path_section = "leaver" if request.url.path.rstrip("/").endswith("/leaver") else "welcome"
    target_section = form_section if form_section in {"welcome", "leaver"} else path_section
    allowed_image_theme_keys = {"music", "security", "giveaway", "custom", "user", "guild"}

    def _normalize_image_theme(raw_value: Any, fallback: str, default_value: str = "music") -> str:
        key = str(raw_value or "").strip().lower()
        if key in allowed_image_theme_keys:
            return key
        fallback_key = str(fallback or "").strip().lower()
        if fallback_key in allowed_image_theme_keys:
            return fallback_key
        default_key = str(default_value or "music").strip().lower()
        if default_key in allowed_image_theme_keys:
            return default_key
        return "music"

    if target_section == "leaver":
        leave_channel_value = (data.get("leave_channel") or "").strip()
        leave_channels = [int(leave_channel_value)] if leave_channel_value.isdigit() else []
        requested_leave_image = _bool_from_form(data, "leave_image")
        leave_message_enabled = _bool_from_form(data, "leave_message_enabled")
        leave_embed_enabled = _bool_from_form(data, "leave_embed")
        leave_image_enabled = requested_leave_image and can_use_image_cards
        if not (leave_message_enabled or leave_embed_enabled or leave_image_enabled):
            leave_message_enabled = True
        await storage.welcomer_settings.update(
            id=state["welcomer"]["id"],
            leave=_bool_from_form(data, "leave"),
            leave_message_enabled=leave_message_enabled,
            leave_embed=leave_embed_enabled,
            leave_image=leave_image_enabled,
            leave_channels=leave_channels,
            leave_message=(data.get("leave_message") or "").strip() or None,
            leave_embed_title=(data.get("leave_embed_title") or "").strip() or None,
            leave_embed_description=(data.get("leave_embed_description") or "").strip() or None,
            leave_image_theme=_normalize_image_theme(
                data.get("leave_image_theme"),
                str(existing.get("leave_image_theme") or "security"),
                default_value="security",
            ),
            leave_image_theme_url=(data.get("leave_image_theme_url") or "").strip() or None,
            leave_image_layout_mode=(data.get("leave_image_layout_mode") or "").strip().lower() or None,
            leave_image_avatar_position=(data.get("leave_image_avatar_position") or "").strip().lower() or None,
            leave_image_text_align=(data.get("leave_image_text_align") or "").strip().lower() or None,
            leave_image_font_style=(data.get("leave_image_font_style") or "").strip().lower() or None,
            leave_image_top_text=(data.get("leave_image_top_text") or "").strip() or None,
            leave_image_bottom_text=(data.get("leave_image_bottom_text") or "").strip() or None,
            leave_delete_after=_int_from_form(
                data,
                "leave_delete_after",
                int(existing.get("leave_delete_after", 0) or 0),
                0,
                600,
            ),
        )
        notice_message = "บันทึกการตั้งค่าข้อความลาออกแล้ว"
        if requested_leave_image and not can_use_image_cards:
            notice_message += " (ส่งรูปต้องใช้แพ็กเกจ Silver ขึ้นไป)"
        redirect_tab = "leaver"
    else:
        welcome_embed_image = (data.get("welcome_embed_image") or "").strip()
        uploaded_welcome = form.get("welcome_embed_image_file")
        if uploaded_welcome and getattr(uploaded_welcome, "filename", None):
            try:
                raw_bytes = await uploaded_welcome.read()
                if raw_bytes:
                    welcome_upload_channels = _collect_channel_ids_for_upload(
                        data.get("welcome_channel"),
                        existing.get("welcome_channel"),
                        existing.get("greet_channels"),
                    )
                    uploaded_url = await _upload_image_to_discord_cdn(
                        guild_id,
                        raw_bytes=raw_bytes,
                        filename=str(getattr(uploaded_welcome, "filename", "welcome.png")),
                        preferred_channel_ids=welcome_upload_channels,
                        upload_target="welcome",
                        asset_kind="banner",
                        request=request,
                        uploader_id=int(_session_user_id(session) or 0),
                        source_route=str(getattr(request.url, "path", "") or ""),
                        source_field="welcome_embed_image_file",
                    )
                    if uploaded_url:
                        welcome_embed_image = uploaded_url
            except Exception:
                pass

        autoroles = [int(item.strip()) for item in (data.get("autoroles") or "").split(",") if item.strip().isdigit()]
        guild_state_for_plan = dict(state.get("guild") or {})
        guild_state_for_plan["subscription"] = plan_tier
        limits = _plan_limits_from_guild_state(guild_state_for_plan)
        max_autoroles = int(limits["autoroles"])
        raw_autorole_count = len(autoroles)
        if raw_autorole_count > max_autoroles:
            autoroles = autoroles[:max_autoroles]

        greet_enabled = _bool_from_form(data, "greet") if "greet" in data else bool(existing.get("greet"))
        greet_channels = existing.get("greet_channels")
        greet_message = existing.get("greet_message")
        requested_welcome_image = _bool_from_form(data, "welcome_image")
        welcome_image_enabled = requested_welcome_image and can_use_image_cards
        welcome_message_enabled = _bool_from_form(data, "welcome_message")
        welcome_embed_enabled = _bool_from_form(data, "welcome_embed")
        invite_tracking_enabled = _bool_from_form(data, "invite_tracking_enabled")
        invite_welcome_enabled = _bool_from_form(data, "invite_welcome_enabled")
        invite_welcome_template = (data.get("invite_welcome_template") or "").strip()
        invite_welcome_unknown_template = (data.get("invite_welcome_unknown_template") or "").strip()
        if not (welcome_message_enabled or welcome_embed_enabled or welcome_image_enabled):
            welcome_message_enabled = True
        await storage.welcomer_settings.update(
            id=state["welcomer"]["id"],
            welcome=_bool_from_form(data, "welcome"),
            welcome_message=welcome_message_enabled,
            welcome_embed=welcome_embed_enabled,
            welcome_image=welcome_image_enabled,
            autorole=_bool_from_form(data, "autorole"),
            autonick=_bool_from_form(data, "autonick"),
            greet=greet_enabled,
            welcome_channel=int(data["welcome_channel"]) if data.get("welcome_channel", "").isdigit() else None,
            autoroles=autoroles,
            autonick_format=(data.get("autonick_format") or "").strip() or None,
            greet_channels=greet_channels,
            welcome_message_content=(data.get("welcome_message_content") or "").strip() or None,
            welcome_embed_image=welcome_embed_image or None,
            welcome_image_theme=_normalize_image_theme(
                data.get("welcome_image_theme"),
                str(existing.get("welcome_image_theme") or "music"),
                default_value="music",
            ),
            welcome_image_theme_url=(data.get("welcome_image_theme_url") or "").strip() or None,
            welcome_image_layout_mode=(data.get("welcome_image_layout_mode") or "").strip().lower() or None,
            welcome_image_avatar_position=(data.get("welcome_image_avatar_position") or "").strip().lower() or None,
            welcome_image_text_align=(data.get("welcome_image_text_align") or "").strip().lower() or None,
            welcome_image_font_style=(data.get("welcome_image_font_style") or "").strip().lower() or None,
            welcome_image_top_text=(data.get("welcome_image_top_text") or "").strip() or None,
            welcome_image_bottom_text=(data.get("welcome_image_bottom_text") or "").strip() or None,
            invite_tracking_enabled=invite_tracking_enabled,
            invite_welcome_enabled=invite_welcome_enabled,
            invite_welcome_template=invite_welcome_template[:500] or None,
            invite_welcome_unknown_template=invite_welcome_unknown_template[:500] or None,
            greet_message=greet_message,
        )
        notice_message = "บันทึกการตั้งค่าต้อนรับแล้ว"
        if raw_autorole_count > max_autoroles:
            notice_message = f"บันทึกแล้ว และจำกัดบทบาทอัตโนมัติสูงสุด {max_autoroles} ตามแพ็กเกจ"
        if requested_welcome_image and not can_use_image_cards:
            notice_message += " (ส่งรูปต้องใช้แพ็กเกจ Silver ขึ้นไป)"
        if requested_redirect_tab in {"welcome", "welcome_center", "autoroles"}:
            redirect_tab = requested_redirect_tab
        else:
            redirect_tab = "welcome"

    await _append_dashboard_audit_event(
        guild_id,
        session,
        "อัปเดตการตั้งค่าต้อนรับแล้ว",
        target=redirect_tab,
    )
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/{redirect_tab}?notice={urlencode({'notice': notice_message}).split('=',1)[1]}",
        status_code=303,
    )

async def update_ocr_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    data = await _parse_form(request)
    
    keywords = [k.strip() for k in (data.get("keywords") or "").split(",") if k.strip()]

    payload = _normalize_image_ocr_settings(
        {
            "guild_id": guild_id,
            "enabled": _bool_from_form(data, "enabled"),
            "image_count": _int_from_form(data, "image_count", 1, 1, 10),
            "webhook_url": (data.get("webhook_url") or "").strip() or None,
            "target_channel_id": (data.get("target_channel_id") or "").strip() or None,
            "notification_channel_id": (data.get("notification_channel_id") or "").strip() or None,
            "admin_channel_id": (data.get("admin_channel_id") or "").strip() or None,
            "reward_role_id": (data.get("reward_role_id") or "").strip() or None,
            "keywords": keywords,
            "notify_embed_title": (data.get("notify_embed_title") or "").strip() or None,
            "notify_embed_description": (data.get("notify_embed_description") or "").strip() or None,
            "notify_embed_image_url": (data.get("notify_embed_image_url") or "").strip() or None,
        }
    )

    persisted_settings: dict[str, Any] = {}
    save_mode = "db"
    try:
        ocr_settings = state.get("image_ocr") if isinstance(state.get("image_ocr"), dict) else {}
        db_row = ocr_settings if ocr_settings.get("id") else {}
        if not db_row:
            try:
                db_row = await storage.image_ocr_settings.get(guild_id=guild_id) or {}
            except Exception as get_error:
                if not _is_atlas_collection_limit_error(get_error):
                    raise
                db_row = {}

        if db_row.get("id"):
            await storage.image_ocr_settings.update(
                id=db_row["id"],
                enabled=payload.get("enabled"),
                image_count=payload.get("image_count"),
                webhook_url=payload.get("webhook_url"),
                target_channel_id=payload.get("target_channel_id"),
                notification_channel_id=payload.get("notification_channel_id"),
                admin_channel_id=payload.get("admin_channel_id"),
                reward_role_id=payload.get("reward_role_id"),
                keywords=payload.get("keywords"),
                notify_embed_title=payload.get("notify_embed_title"),
                notify_embed_description=payload.get("notify_embed_description"),
                notify_embed_image_url=payload.get("notify_embed_image_url"),
            )
            try:
                persisted_settings = await storage.image_ocr_settings.get(guild_id=guild_id) or {}
            except Exception as get_error:
                if not _is_atlas_collection_limit_error(get_error):
                    raise
                persisted_settings = {}
        else:
            try:
                inserted = await storage.image_ocr_settings.insert(guild_id=guild_id)
                inserted_id = (inserted or {}).get("id")
                if inserted_id:
                    await storage.image_ocr_settings.update(
                        id=inserted_id,
                        enabled=payload.get("enabled"),
                        image_count=payload.get("image_count"),
                        webhook_url=payload.get("webhook_url"),
                        target_channel_id=payload.get("target_channel_id"),
                        notification_channel_id=payload.get("notification_channel_id"),
                        admin_channel_id=payload.get("admin_channel_id"),
                        reward_role_id=payload.get("reward_role_id"),
                        keywords=payload.get("keywords"),
                        notify_embed_title=payload.get("notify_embed_title"),
                        notify_embed_description=payload.get("notify_embed_description"),
                        notify_embed_image_url=payload.get("notify_embed_image_url"),
                    )
                    persisted_settings = await storage.image_ocr_settings.get(guild_id=guild_id) or {}
            except Exception as insert_error:
                if not _is_atlas_collection_limit_error(insert_error):
                    raise
                persisted_settings = {}
    except Exception as error:
        if not _is_atlas_collection_limit_error(error):
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/ocr?notice={urlencode({'notice': f'ข้อผิดพลาด: {error}'}).split('=',1)[1]}",
                status_code=303,
            )
        persisted_settings = {}

    if not persisted_settings:
        save_mode = "fallback"
        persisted_settings = await _save_image_ocr_fallback(guild_id, payload)
    else:
        persisted_settings = _normalize_image_ocr_settings({**persisted_settings, **payload})

    from skylinebot.memory.cache import cache
    cache.image_ocr_cache[str(guild_id)] = persisted_settings

    done_notice = "บันทึกการตั้งค่า OCR แล้ว"
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่า OCR แล้ว", target="ocr")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/ocr?notice={urlencode({'notice': done_notice}).split('=',1)[1]}",
        status_code=303,
    )

async def update_server_stats(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    effective_plan_tier = _dashboard_effective_plan_tier(state, session=session)
    if not _is_plan_at_least(effective_plan_tier, "silver"):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}?notice={urlencode({'notice': 'Statistics is premium only (Silver/Gole/Diamond/Permanent)'}).split('=',1)[1]}",
            status_code=303,
        )
    data = await _parse_form(request)

    stats_settings = state.get("server_stats") or {}
    try:
        stat_types = [
            'total_members', 'members', 'bots', 'voice', 'boosts',
            'online', 'idle', 'dnd', 'offline'
        ]
        guild_state_for_plan = dict(state.get("guild") or {})
        guild_state_for_plan["subscription"] = effective_plan_tier
        guild_limits = _plan_limits_from_guild_state(guild_state_for_plan)
        max_stats_channels = int(guild_limits.get("server_stats_channels", 4) or 4)
        selected_types = [t for t in stat_types if _bool_from_form(data, f"stat_{t}_enabled")]
        if len(selected_types) > max_stats_channels:
            notice = f"แพ็กเกจของคุณรองรับห้องสถิติได้สูงสุด {max_stats_channels} ห้อง (เลือกไว้ {len(selected_types)} ห้อง)"
            return RedirectResponse(
                f"/dashboard/guild/{guild_id}/server_stats?notice={urlencode({'notice': notice}).split('=',1)[1]}",
                status_code=303,
            )
        default_formats = {
            'total_members': 'สมาชิกทั้งหมด: {Count}',
            'members': 'สมาชิก: {Count}',
            'bots': 'บอท: {Count}',
            'voice': 'อยู่ในห้องเสียง: {Count}',
            'boosts': 'บูสต์: {Count}',
            'online': 'ออนไลน์: {Count}',
            'idle': 'ไม่พร้อมใช้งาน: {Count}',
            'dnd': 'ห้ามรบกวน: {Count}',
            'offline': 'ออฟไลน์: {Count}',
        }
        configs = []
        enabled = _bool_from_form(data, "enabled")
        auto_create = (data.get("auto_create") or "0") == "1"
        category_name = (data.get("category_name") or "สถิติเซิร์ฟเวอร์").strip()

        bot = get_bot()
        guild = bot.get_guild(guild_id) if bot else None
        category = None

        for t in stat_types:
            is_stat_enabled = _bool_from_form(data, f"stat_{t}_enabled")
            if not is_stat_enabled:
                continue

            # FIX: correct field name
            channel_id = (data.get(f"stat_{t}_channel") or "").strip()
            if channel_id in ("None", "none", "0"):
                channel_id = ""
            format_str = str(_posted_form_value(data, f"stat_{t}_format", "") or "").strip()
            if not format_str:
                format_str = default_formats.get(t, "{Count}")

            # Compute real initial display value
            def _display_val(t):
                if not guild:
                    return "0"
                if t == 'total_members': return str(guild.member_count or 0)
                if t == 'members': return str(sum(1 for m in guild.members if not m.bot))
                if t == 'bots': return str(sum(1 for m in guild.members if m.bot))
                if t == 'voice': return str(sum(len(vc.members) for vc in guild.voice_channels))
                if t == 'boosts': return str(guild.premium_subscription_count or 0)
                if t == 'online': return str(sum(1 for m in guild.members if str(m.status) == 'online'))
                if t == 'idle': return str(sum(1 for m in guild.members if str(m.status) == 'idle'))
                if t == 'dnd': return str(sum(1 for m in guild.members if str(m.status) == 'dnd'))
                if t == 'offline': return str(sum(1 for m in guild.members if str(m.status) == 'offline'))
                return "0"

            # Auto-create when no channel or auto_create button pressed
            if enabled and guild and (not channel_id or auto_create):
                try:
                    if not category:
                        category = discord.utils.get(guild.categories, name=category_name)
                        if not category:
                            overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}
                            category = await guild.create_category(category_name, overwrites=overwrites)
                    dv = _display_val(t)
                    new_channel = await guild.create_voice_channel(
                        name=format_str.replace("{Count}", dv),
                        category=category,
                        overwrites={guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True)}
                    )
                    channel_id = str(new_channel.id)
                except Exception:
                    pass
            elif channel_id and guild:
                # Rename existing channel to reflect new format
                try:
                    ch = guild.get_channel(int(channel_id))
                    if ch:
                        dv = _display_val(t)
                        await ch.edit(name=format_str.replace("{Count}", dv))
                except Exception:
                    pass

            if channel_id and channel_id not in ("None", ""):
                configs.append({'type': t, 'channel_id': channel_id, 'format': format_str})

        payload = {
            "enabled": enabled,
            "stats_configs": configs,
            "category_name": category_name,
        }
        persisted_settings: dict[str, Any] = {}
        save_mode = "db"

        db_row = stats_settings if isinstance(stats_settings, dict) else {}
        if not db_row.get("id"):
            try:
                db_row = await storage.server_stats.get(guild_id=guild_id) or {}
            except Exception as get_error:
                if not _is_atlas_collection_limit_error(get_error):
                    raise
                db_row = {}

        if db_row.get("id"):
            try:
                await storage.server_stats.update(
                    id=db_row["id"],
                    enabled=enabled,
                    stats_configs=configs,
                    category_name=category_name,
                )
            except TypeError:
                await storage.server_stats.update(
                    id=db_row["id"],
                    enabled=enabled,
                    stats_configs=configs,
                )
            try:
                persisted_settings = await storage.server_stats.get(guild_id=guild_id) or {}
            except Exception as get_error:
                if not _is_atlas_collection_limit_error(get_error):
                    raise
                persisted_settings = {}
        else:
            try:
                inserted = await storage.server_stats.insert(guild_id=guild_id)
                inserted_id = (inserted or {}).get("id")
                if inserted_id:
                    try:
                        await storage.server_stats.update(
                            id=inserted_id,
                            enabled=enabled,
                            stats_configs=configs,
                            category_name=category_name,
                        )
                    except TypeError:
                        await storage.server_stats.update(
                            id=inserted_id,
                            enabled=enabled,
                            stats_configs=configs,
                        )
                    try:
                        persisted_settings = await storage.server_stats.get(guild_id=guild_id) or {}
                    except Exception as get_error:
                        if not _is_atlas_collection_limit_error(get_error):
                            raise
                        persisted_settings = {}
            except Exception as insert_error:
                if not _is_atlas_collection_limit_error(insert_error):
                    raise
                persisted_settings = {}

        if not persisted_settings:
            save_mode = "fallback"
            persisted_settings = await _save_server_stats_fallback(guild_id, payload)
        else:
            persisted_settings = {**payload, **persisted_settings}
            persisted_settings["category_name"] = category_name

        from skylinebot.memory.cache import cache
        cache.server_stats_cache[str(guild_id)] = persisted_settings

        # Refresh stat channels after save without creating extra task
        if bot and guild:
            try:
                stats_cog = bot.get_cog("ServerStats")
                if stats_cog and hasattr(stats_cog, "update_guild_stats"):
                    await stats_cog.update_guild_stats(guild, force=True)
            except Exception:
                pass

    except Exception as e:
        return RedirectResponse(f"/dashboard/guild/{guild_id}/server_stats?notice={urlencode({'notice': f'ข้อผิดพลาด: {e}'}).split('=',1)[1]}", status_code=303)

    done_notice = "บันทึกการตั้งค่าสถิติเซิร์ฟเวอร์แล้ว"
    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าสถิติเซิร์ฟเวอร์แล้ว", target="server_stats")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/server_stats?notice={urlencode({'notice': done_notice}).split('=',1)[1]}", status_code=303)

async def update_donate_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    form = await request.form()
    data = {k: str(v) for k, v in form.items() if k != "image_file"}

    donate_settings = state.get("donate")
    save_notice = "บันทึกการตั้งค่าระบบโดเนตแล้ว"
    try:
        if not donate_settings or not donate_settings.get("id"):
            donate_settings = await storage.donate_settings.get(guild_id=guild_id)
            if not donate_settings:
                try:
                    await storage.donate_settings.insert(guild_id=guild_id)
                    donate_settings = await storage.donate_settings.get(guild_id=guild_id)
                except Exception as insert_error:
                    if not _is_atlas_collection_limit_error(insert_error):
                        raise
                    donate_settings = None

        methods_enabled = {
            "truemoney": _bool_from_form(data, "method_truemoney"),
            "promptpay": _bool_from_form(data, "method_promptpay"),
            "bank": _bool_from_form(data, "method_bank"),
            "slipverify": _bool_from_form(data, "method_slipverify"),
            "goal": _bool_from_form(data, "method_goal"),
        }

        image_url = (data.get("image_url") or "").strip()
        uploaded = form.get("image_file")
        if uploaded and getattr(uploaded, "filename", None):
            try:
                raw_bytes = await uploaded.read()
                if raw_bytes:
                    donate_upload_channels = _collect_channel_ids_for_upload(
                        data.get("donation_channel_id"),
                        data.get("notification_channel_id"),
                    )
                    uploaded_url = await _upload_image_to_discord_cdn(
                        guild_id,
                        raw_bytes=raw_bytes,
                        filename=str(getattr(uploaded, "filename", "upload.png")),
                        preferred_channel_ids=donate_upload_channels,
                        upload_target="donate",
                        asset_kind="banner",
                        request=request,
                        uploader_id=int(_session_user_id(session) or 0),
                        source_route=str(getattr(request.url, "path", "") or ""),
                        source_field="image_file",
                    )
                    if uploaded_url:
                        image_url = uploaded_url
            except Exception:
                pass

        payload = {
            "enabled": _bool_from_form(data, "enabled"),
            "donation_channel_id": (data.get("donation_channel_id") or "").strip() or None,
            "notification_channel_id": (data.get("notification_channel_id") or "").strip() or None,
            "reward_role_id": (data.get("reward_role_id") or "").strip() or None,
            "color": (data.get("color") or "#6b8cff").strip(),
            "desc_discord": (data.get("desc_discord") or "").strip(),
            "desc_web": (data.get("desc_web") or "").strip(),
            "truemoney_phone": (data.get("truemoney_phone") or "").strip(),
            "promptpay_number": (data.get("promptpay_number") or "").strip(),
            "bank_name": (data.get("bank_name") or "").strip(),
            "bank_account_number": (data.get("bank_account_number") or "").strip(),
            "bank_account_name": (data.get("bank_account_name") or "").strip(),
            "slipcheck_verify_engine": (
                "skylinebotslip"
                if str(data.get("slipcheck_verify_engine") or "").strip().lower() in {"skylinebot", "skyline", "skylinebotslip", "skyline_slip", "internal", "ocr"}
                else "slipok"
            ),
            "slipok_api_url": (data.get("slipok_api_url") or "https://api.slipok.com/api/line/apikey/1150").strip(),
            "slipok_key": (data.get("slipok_key") or "").strip(),
            "slipcheck_expected_receiver_name": (data.get("slipcheck_expected_receiver_name") or "").strip()[:220],
            "slipcheck_expected_receiver_first_name_th": (data.get("slipcheck_expected_receiver_first_name_th") or "").strip()[:120],
            "slipcheck_expected_receiver_last_name_th": (data.get("slipcheck_expected_receiver_last_name_th") or "").strip()[:120],
            "slipcheck_expected_receiver_first_name_en": (data.get("slipcheck_expected_receiver_first_name_en") or "").strip()[:120],
            "slipcheck_expected_receiver_last_name_en": (data.get("slipcheck_expected_receiver_last_name_en") or "").strip()[:120],
            "slipcheck_expected_receiver_bank": (data.get("slipcheck_expected_receiver_bank") or "").strip()[:220],
            "slipcheck_expected_receiver_account": "".join(
                ch for ch in str(data.get("slipcheck_expected_receiver_account") or "") if ch.isdigit()
            )[:30],
            "slipcheck_expected_sender_name": (data.get("slipcheck_expected_sender_name") or "").strip()[:220],
            "slipcheck_expected_sender_first_name_th": (data.get("slipcheck_expected_sender_first_name_th") or "").strip()[:120],
            "slipcheck_expected_sender_last_name_th": (data.get("slipcheck_expected_sender_last_name_th") or "").strip()[:120],
            "slipcheck_expected_sender_first_name_en": (data.get("slipcheck_expected_sender_first_name_en") or "").strip()[:120],
            "slipcheck_expected_sender_last_name_en": (data.get("slipcheck_expected_sender_last_name_en") or "").strip()[:120],
            "slipcheck_expected_sender_bank": (data.get("slipcheck_expected_sender_bank") or "").strip()[:220],
            "slipcheck_expected_sender_account": "".join(
                ch for ch in str(data.get("slipcheck_expected_sender_account") or "") if ch.isdigit()
            )[:30],
            "slipcheck_expected_reference": (data.get("slipcheck_expected_reference") or "").strip()[:120],
            "slipcheck_expected_qr_reference": (data.get("slipcheck_expected_qr_reference") or "").strip()[:300],
            "slipcheck_max_age_minutes": _int_from_form(data, "slipcheck_max_age_minutes", 1440, 0, 60 * 24 * 30),
            "slipcheck_duplicate_window_hours": _int_from_form(data, "slipcheck_duplicate_window_hours", 72, 1, 24 * 90),
            "slipcheck_review_channel_id": (
                (data.get("slipcheck_review_channel_id") or "").strip()
                if str(data.get("slipcheck_review_channel_id") or "").strip().isdigit()
                else ""
            ),
            "slipcheck_review_dm_user_ids": ",".join(
                [
                    str(token or "").strip()
                    for token in (
                        str(data.get("slipcheck_review_dm_user_ids") or "")
                        .replace(";", ",")
                        .replace("\n", ",")
                        .replace("\t", ",")
                        .replace(" ", ",")
                        .split(",")
                    )
                    if str(token or "").strip().isdigit()
                ][:20]
            ),
            "goal_title": (data.get("goal_title") or "").strip(),
            "goal_start_amount": _int_from_form(data, "goal_start_amount", 0, 0, 1_000_000_000),
            "goal_end_amount": _int_from_form(data, "goal_end_amount", 500, 0, 1_000_000_000),
            "goal_start_date": (data.get("goal_start_date") or "").strip(),
            "image_url": image_url,
            "methods_enabled": methods_enabled,
        }
        try:
            payload["slipcheck_auto_approve_confidence"] = round(
                max(50.0, min(100.0, float(str(data.get("slipcheck_auto_approve_confidence") or "85").strip()))),
                2,
            )
        except Exception:
            payload["slipcheck_auto_approve_confidence"] = 85.0
        payload["slipcheck_manual_review_confidence"] = 0.0

        if methods_enabled.get("slipverify"):
            slip_engine_value = str(payload.get("slipcheck_verify_engine") or "slipok").strip().lower()
            if slip_engine_value == "slipok":
                if not str(payload.get("slipok_api_url") or "").strip() or not str(payload.get("slipok_key") or "").strip():
                    notice = "กรุณากรอก SlipOK API URL และ SlipOK API Key ให้ครบถ้วน"
                    return RedirectResponse(
                        f"/dashboard/guild/{guild_id}/donate?notice={urlencode({'notice': notice}).split('=',1)[1]}",
                        status_code=303,
                    )
            else:
                receiver_account_digits = "".join(ch for ch in str(payload.get("slipcheck_expected_receiver_account") or "") if ch.isdigit())
                has_receiver_name = bool(
                    str(payload.get("slipcheck_expected_receiver_name") or "").strip()
                    or (
                        str(payload.get("slipcheck_expected_receiver_first_name_th") or "").strip()
                        and str(payload.get("slipcheck_expected_receiver_last_name_th") or "").strip()
                    )
                    or (
                        str(payload.get("slipcheck_expected_receiver_first_name_en") or "").strip()
                        and str(payload.get("slipcheck_expected_receiver_last_name_en") or "").strip()
                    )
                )
                if len(receiver_account_digits) < 6 or len(receiver_account_digits) > 30 or not has_receiver_name:
                    notice = "SkylineBotSlip ต้องมีชื่อผู้รับและเลขบัญชีผู้รับให้ครบถ้วน"
                    return RedirectResponse(
                        f"/dashboard/guild/{guild_id}/donate?notice={urlencode({'notice': notice}).split('=',1)[1]}",
                        status_code=303,
                    )

        saved_payload: dict[str, Any] | None = None
        if donate_settings and donate_settings.get("id"):
            try:
                await storage.donate_settings.update(
                    id=donate_settings["id"],
                    **payload,
                )
                saved_payload = await storage.donate_settings.get(guild_id=guild_id)
            except Exception as update_error:
                if not _is_atlas_collection_limit_error(update_error):
                    raise

        if not saved_payload:
            saved_payload = await _save_donate_fallback(guild_id, payload)
            if not saved_payload:
                raise RuntimeError("บันทึกการตั้งค่าระบบโดเนตไม่สำเร็จทั้ง DB และ fallback")

        cache.donate_settings_cache[str(guild_id)] = saved_payload

        if saved_payload.get("enabled"):
            bot = get_bot()
            ok, panel_message = await publish_donate_panel_message(bot, guild_id, saved_payload)
            if ok:
                save_notice = "บันทึกการตั้งค่าระบบโดเนตแล้ว และส่งแผงข้อความไปยังห้องที่ตั้งค่าไว้แล้ว"
            else:
                save_notice = f"บันทึกการตั้งค่าระบบโดเนตแล้ว แต่ส่งแผงข้อความอัตโนมัติไม่สำเร็จ ({panel_message})"
    except Exception as error:
        if _is_atlas_collection_limit_error(error):
            notice = "บันทึกไม่สำเร็จ (เกินขีดจำกัดฐานข้อมูล)"
        else:
            notice = "บันทึกการตั้งค่าระบบโดเนตไม่สำเร็จ"
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/donate?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    await _append_dashboard_audit_event(guild_id, session, "อัปเดตการตั้งค่าระบบโดเนตแล้ว", target="donate")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/donate?notice={urlencode({'notice': save_notice}).split('=',1)[1]}",
        status_code=303,
    )

async def upload_donate_slip(request: Request, guild_id: int):
    form = await request.form()
    donor_name = (str(form.get("donor_name") or "").strip() or "ไม่ระบุชื่อ")[:80]
    donor_avatar_url = str(form.get("donor_avatar_url") or "").strip()[:1600]
    payment_method = (str(form.get("payment_method") or "").strip() or "other")[:30]
    evidence_type = str(form.get("evidence_type") or "auto").strip().lower()
    message = (str(form.get("message") or "").strip())[:500]
    transfer_link = (str(form.get("transfer_link") or "").strip())[:500]
    amount_raw = str(form.get("amount") or "").strip()
    uploaded = form.get("slip_file")

    redirect_base = f"/dashboard/donate/{guild_id}"

    try:
        amount = int(float(amount_raw))
    except Exception:
        amount = 0
    if amount <= 0:
        notice = "จำนวนเงินไม่ถูกต้อง"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    has_uploaded_file = bool(uploaded and getattr(uploaded, "filename", None))
    if donor_avatar_url and not re.match(r"^https?://\S+$", donor_avatar_url, re.I):
        notice = "Donor Avatar URL must start with http:// or https://"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    if evidence_type in {"gift", "truemoney"}:
        if not transfer_link:
            notice = "Please provide a TrueMoney Gift Link"
            return RedirectResponse(
                f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
                status_code=303,
            )
        if not re.match(r"^https?://gift\.truemoney\.com/campaign/\?v=[A-Za-z0-9_-]{8,}$", transfer_link, re.I):
            notice = "TrueMoney Gift Link format is invalid"
            return RedirectResponse(
                f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
                status_code=303,
            )
        payment_method = "truemoney"
    elif evidence_type in {"slip", "file"} and not has_uploaded_file:
        notice = "Please upload a slip file"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )
    if not has_uploaded_file and not transfer_link:
        notice = "กรุณาแนบไฟล์สลิปหรือใส่ลิงก์อ้างอิง"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    settings = (
        cache.donate_settings_cache.get(str(guild_id))
        or await storage.donate_settings.get(guild_id=guild_id)
        or await _get_donate_fallback(guild_id)
        or {}
    )
    methods_enabled = settings.get("methods_enabled") or {}
    if not settings.get("enabled"):
        notice = "ยังไม่ได้เปิดใช้งานระบบโดเนตสำหรับเซิร์ฟเวอร์นี้"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )
    if not methods_enabled.get("slipverify"):
        notice = "ยังไม่ได้เปิดใช้งานการตรวจสลิปสำหรับเซิร์ฟเวอร์นี้"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    ownerbot_payment_settings = _ownerbot_payment_provider_settings_from_db()
    ownerbot_review_channel_id = str(ownerbot_payment_settings.get("slipcheck_review_channel_id") or "").strip()
    ownerbot_review_dm_ids_raw = str(ownerbot_payment_settings.get("slipcheck_review_dm_user_ids") or "").strip()
    ownerbot_low_conf_route_raw = str(ownerbot_payment_settings.get("slipcheck_low_confidence_route") or "").strip().lower()
    effective_auto_verify_settings = dict(settings)
    for key, value in (ownerbot_payment_settings or {}).items():
        key_text = str(key or "")
        if not (key_text.startswith("slipcheck_") or key_text.startswith("slipok_")):
            continue
        current_value = effective_auto_verify_settings.get(key_text)
        if current_value in (None, "", [], {}):
            effective_auto_verify_settings[key_text] = value

    notification_channel_id = str(settings.get("notification_channel_id") or "").strip()
    review_channel_id = str(settings.get("slipcheck_review_channel_id") or "").strip()
    donation_channel_id = str(settings.get("donation_channel_id") or "").strip()
    if not notification_channel_id.isdigit() and ownerbot_review_channel_id.isdigit():
        notification_channel_id = ownerbot_review_channel_id
    if not review_channel_id.isdigit() and ownerbot_review_channel_id.isdigit():
        review_channel_id = ownerbot_review_channel_id
    slip_destination_channel_id = (
        notification_channel_id
        if notification_channel_id.isdigit()
        else (
            review_channel_id
            if review_channel_id.isdigit()
            else (donation_channel_id if donation_channel_id.isdigit() else "")
        )
    )
    review_dm_ids_raw = str(settings.get("slipcheck_review_dm_user_ids") or "").strip() or ownerbot_review_dm_ids_raw
    review_dm_user_ids: list[str] = []
    if review_dm_ids_raw:
        for token in review_dm_ids_raw.replace(";", ",").replace("\n", ",").replace("\t", ",").replace(" ", ",").split(","):
            token = token.strip()
            if not token.isdigit() or token in review_dm_user_ids:
                continue
            review_dm_user_ids.append(token)
            if len(review_dm_user_ids) >= 20:
                break
    low_conf_route_raw = str(settings.get("slipcheck_low_confidence_route") or "").strip().lower()
    if not low_conf_route_raw:
        low_conf_route_raw = ownerbot_low_conf_route_raw or "both"
    if low_conf_route_raw in {"embed", "embed_channel", "channel", "room", "guild", "discord"}:
        low_confidence_route = "channel"
    elif low_conf_route_raw in {"dm", "direct", "direct_message", "directmessage", "user_dm"}:
        low_confidence_route = "dm"
    else:
        low_confidence_route = "both"
    should_route_pending_channel = low_confidence_route in {"channel", "both"}
    should_route_pending_dm = low_confidence_route in {"dm", "both"}
    if not slip_destination_channel_id.isdigit():
        notice = "ผู้ดูแลยังไม่ได้ตั้งค่าห้องแจ้งเตือนหรือห้องรีวิวสลิป"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    raw_bytes = b""
    safe_name = _safe_upload_name(getattr(uploaded, "filename", "slip.png"))
    slip_asset_url = ""
    if has_uploaded_file:
        raw_bytes = await uploaded.read()
        if not raw_bytes:
            notice = "ไฟล์สลิปว่างหรืออ่านข้อมูลไม่ได้"
            return RedirectResponse(
                f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
                status_code=303,
            )
        if len(raw_bytes) > 12 * 1024 * 1024:
            notice = "ไฟล์สลิปมีขนาดใหญ่เกินไป (สูงสุด 12MB)"
            return RedirectResponse(
                f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
                status_code=303,
            )

    bot = get_bot()
    guild = bot.get_guild(guild_id) if bot else None
    if guild is None:
        notice = "ไม่พบบอทในกิลด์นี้"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    channel = guild.get_channel(int(slip_destination_channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(slip_destination_channel_id))
        except Exception:
            channel = None
    if channel is None or not hasattr(channel, "send"):
        notice = "ไม่พบห้องแจ้งเตือนหรือบอทไม่สามารถส่งข้อความได้"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    payment_method_labels = {
        "truemoney": "ทรูมันนี่ วอลเล็ท",
        "promptpay": "PromptPay",
        "bank": "ธนาคาร",
        "slipverify": "SlipVerify",
        "other": "อื่นๆ",
    }
    method_label = payment_method_labels.get(payment_method, payment_method)
    if payment_method not in payment_method_labels:
        method_label = "อื่นๆ"

    guild_name = str(getattr(guild, "name", f"เซิร์ฟเวอร์ {guild_id}"))
    color_value = str(settings.get("color") or "#6b8cff").strip().lstrip("#")
    try:
        embed_color = int(color_value[:6], 16)
    except Exception:
        embed_color = 0x6B8CFF
    embed = discord.Embed(
        title="แจ้งเตือนสลิปจากเว็บแดชบอร์ด",
        color=embed_color,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    embed.add_field(name="เซิร์ฟเวอร์", value=guild_name, inline=True)
    embed.add_field(name="จำนวนเงิน", value=f"{amount:,} บาท", inline=True)
    embed.add_field(name="ช่องทางชำระเงิน", value=method_label, inline=True)
    embed.add_field(name="ผู้โอน", value=donor_name, inline=True)
    if donor_avatar_url:
        try:
            embed.set_thumbnail(url=donor_avatar_url)
        except Exception:
            donor_avatar_url = ""
    if transfer_link:
        embed.add_field(name="ลิงก์อ้างอิง / หลักฐาน", value=transfer_link[:1024], inline=False)
    if message:
        embed.add_field(name="ข้อความถึงเรา", value=message[:1024], inline=False)
    auto_status, auto_note = await _auto_verify_donate_evidence(
        settings=effective_auto_verify_settings,
        payment_method=payment_method,
        amount=amount,
        image_url=(slip_asset_url if slip_asset_url else ""),
        raw_bytes=(raw_bytes if raw_bytes else None),
        filename=safe_name,
        transfer_link=transfer_link,
    )
    embed.add_field(name="Auto Verify", value=_donate_slip_status_label(auto_status), inline=True)
    if auto_note:
        embed.add_field(name="Verification Detail", value=auto_note[:1024], inline=False)
    embed.set_footer(text=f"Uploaded via SkylineBOT | Guild ID: {guild_id}")

    send_channel = channel
    send_channel_id = slip_destination_channel_id
    if auto_status == "pending" and should_route_pending_channel and review_channel_id.isdigit():
        review_channel_obj = guild.get_channel(int(review_channel_id))
        if review_channel_obj is None:
            try:
                review_channel_obj = await bot.fetch_channel(int(review_channel_id))
            except Exception:
                review_channel_obj = None
        if review_channel_obj is not None and hasattr(review_channel_obj, "send"):
            send_channel = review_channel_obj
            send_channel_id = review_channel_id

    discord_file = None
    if raw_bytes:
        attachment_name = f"donate_slip_{safe_name}"
        discord_file = discord.File(io.BytesIO(raw_bytes), filename=attachment_name)
        embed.set_image(url=f"attachment://{attachment_name}")

    slip_id = uuid.uuid4().hex
    review_view = DonateSlipReviewView(
        guild_id=guild_id,
        slip_id=slip_id,
        transfer_link=transfer_link,
    )
    sent_message_id = ""
    try:
        if discord_file:
            sent_message = await send_channel.send(embed=embed, file=discord_file, view=review_view)
        else:
            sent_message = await send_channel.send(embed=embed, view=review_view)
        sent_message_id = str(getattr(sent_message, "id", "") or "")
        if discord_file:
            sent_attachments = list(getattr(sent_message, "attachments", []) or [])
            if sent_attachments:
                slip_asset_url = str(getattr(sent_attachments[0], "url", "") or "").strip()
        if transfer_link or slip_asset_url:
            try:
                enriched_view = DonateSlipReviewView(
                    guild_id=guild_id,
                    slip_id=slip_id,
                    transfer_link=transfer_link,
                    proof_url=slip_asset_url,
                )
                await sent_message.edit(view=enriched_view)
            except Exception:
                pass
    except Exception:
        notice = "ส่งสลิปไปยัง Discord ไม่สำเร็จ กรุณาตรวจสอบสิทธิ์บอทในห้องแจ้งเตือน"
        return RedirectResponse(
            f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
            status_code=303,
        )

    dm_notice_sent = 0
    if auto_status == "pending" and should_route_pending_dm and review_dm_user_ids:
        jump_url = str(getattr(sent_message, "jump_url", "") or "").strip()
        dm_embed = discord.Embed(
            title="ต้องตรวจสอบสลิปโดเนต",
            description="ระบบตรวจสลิปยังไม่มั่นใจ และต้องการการยืนยันจากผู้ดูแล",
            color=embed_color,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        dm_embed.add_field(name="เซิร์ฟเวอร์", value=guild_name, inline=True)
        dm_embed.add_field(name="ยอดเงิน", value=f"{amount:,} บาท", inline=True)
        dm_embed.add_field(name="ผู้โอน", value=donor_name, inline=True)
        dm_embed.add_field(name="สถานะ", value=_donate_slip_status_label(auto_status), inline=True)
        if auto_note:
            dm_embed.add_field(name="ผลตรวจ", value=auto_note[:1024], inline=False)
        if jump_url:
            dm_embed.add_field(name="ลิงก์ไปข้อความตรวจสอบ", value=jump_url, inline=False)
        if slip_asset_url:
            dm_embed.set_image(url=slip_asset_url)
        dm_embed.set_footer(text=f"Guild ID: {guild_id}")
        for user_id_text in review_dm_user_ids:
            user_id = int(user_id_text)
            target_user = bot.get_user(user_id)
            if target_user is None:
                try:
                    target_user = await bot.fetch_user(user_id)
                except Exception:
                    target_user = None
            if target_user is None:
                continue
            try:
                await target_user.send(embed=dm_embed)
                dm_notice_sent += 1
            except Exception:
                continue

    await _append_donate_slip_log(
        guild_id,
        {
            "slip_id": slip_id,
            "created_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "status": auto_status,
            "donor_name": donor_name,
            "amount": amount,
            "payment_method": payment_method,
            "message": f"{message}\n{('ลิงก์: ' + transfer_link) if transfer_link else ''}".strip(),
            "image_url": slip_asset_url,
            "discord_channel_id": str(send_channel_id),
            "discord_message_id": sent_message_id,
            "reviewed_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat() if auto_status != "pending" else "",
            "reviewed_by_id": "system" if auto_status != "pending" else "",
            "reviewed_by_name": "ตรวจสอบอัตโนมัติ" if auto_status != "pending" else "",
        },
    )

    notice = "ส่งหลักฐานเรียบร้อยแล้ว และส่งต่อไปยัง Discord เพื่อให้แอดมินตรวจสอบ"
    if auto_status == "pending" and should_route_pending_channel and review_channel_id.isdigit():
        notice = "ส่งหลักฐานเรียบร้อยแล้ว อยู่ระหว่างรอทีมงานตรวจสอบในห้องรีวิว"
    if dm_notice_sent > 0:
        notice = f"{notice} (แจ้งเตือน DM แล้ว {dm_notice_sent} คน)"
    return RedirectResponse(
        f"{redirect_base}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
        status_code=303,
    )

async def update_donate_slip_status(request: Request, guild_id: int, slip_id: str):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response

    data = await _parse_form(request)
    status = _normalize_donate_slip_status(data.get("status") or "pending")
    user = (session or {}).get("user") or {}
    reviewer_id = str(user.get("id") or "")
    reviewer_name = str(
        user.get("global_name")
        or user.get("username")
        or user.get("name")
        or "ผู้ดูแล"
    ).strip() or "ผู้ดูแล"

    ok = await _update_donate_slip_log_status(
        guild_id,
        slip_id,
        status,
        reviewer_id=reviewer_id,
        reviewer_name=reviewer_name,
    )
    if ok:
        notice = f"อัปเดตสถานะสลิปเป็น {_donate_slip_status_label(status)} แล้ว"
    else:
        notice = "ไม่พบรายการสลิป"
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/donate?notice={urlencode({'notice': notice}).split('=',1)[1]}",
        status_code=303,
    )

async def donate_slips_live_data(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    if not session:
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)
    if not current_guild:
        blocked_notice = _ownerbot_runtime_notice_from_state(state)
        if blocked_notice:
            return JSONResponse({"ok": False, "message": blocked_notice}, status_code=403)
        return JSONResponse({"ok": False, "message": "ไม่มีสิทธิ์เข้าถึง"}, status_code=403)

    slip_logs = await _get_donate_slip_logs(guild_id, limit=120)
    etag_payload = [
        {
            "id": str(row.get("slip_id") or row.get("id") or ""),
            "status": _normalize_donate_slip_status(row.get("status")),
            "amount": int(row.get("amount") or 0),
            "donor_name": str(row.get("donor_name") or ""),
            "created_at": _safe_parse_datetime(row.get("created_at")).isoformat() if _safe_parse_datetime(row.get("created_at")) else "",
            "reviewed_at": _safe_parse_datetime(row.get("reviewed_at")).isoformat() if _safe_parse_datetime(row.get("reviewed_at")) else "",
            "reviewer_id": str(row.get("reviewer_id") or ""),
        }
        for row in slip_logs
    ]
    etag_source = json.dumps(
        {"guild_id": int(guild_id), "rows": etag_payload},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    etag = '"' + hashlib.sha1(etag_source.encode("utf-8")).hexdigest() + '"'
    if_none_match = (request.headers.get("if-none-match") or "").strip()
    if if_none_match:
        tokens = [token.strip() for token in if_none_match.split(",") if token.strip()]
        normalized_tokens = {token[2:] if token.startswith("W/") else token for token in tokens}
        if etag in normalized_tokens:
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": "private, no-cache",
                    "Vary": "Cookie",
                },
            )

    rows_html = "".join(
        _render_donate_slip_row_html(int(guild_id), row, with_actions=True)
        for row in slip_logs
    )
    if not rows_html:
        rows_html = '<tr><td colspan="11" class="muted">ยังไม่มีประวัติ</td></tr>'
    return JSONResponse(
        {
            "ok": True,
            "count": len(slip_logs),
            "rows_html": rows_html,
            "updated_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        },
        headers={
            "ETag": etag,
            "Cache-Control": "private, no-cache",
            "Vary": "Cookie",
        },
    )

async def update_alerts_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response

    data = await _parse_form(request)
    raw_role_ids = (data.get("mention_role_ids") or "").strip()
    mention_role_ids: list[str] = []
    for role_id in raw_role_ids.split(","):
        role_id = role_id.strip()
        if role_id.isdigit() and role_id not in mention_role_ids:
            mention_role_ids.append(role_id)

    notify_channel_id = (data.get("notify_channel_id") or "").strip() or None

    def _read_entries_json(key: str) -> list[dict[str, str]]:
        raw = (data.get(key) or "").strip()
        if not raw:
            return []
        try:
            decoded = json.loads(raw)
        except Exception:
            return []
        return _normalize_alert_entries(decoded, default_channel=notify_channel_id, max_items=60)

    active_tab_slug = str(data.get("active_tab_slug") or "alerts").strip().lower()
    tab_to_platform = {
        "alerts_twitch": "twitch",
        "alerts_youtube": "youtube",
        "alerts_tiktok": "tiktok",
        "alerts_github": "github",
        "alerts_facebook": "facebook",
    }
    target_platform = tab_to_platform.get(active_tab_slug)
    existing_settings = _normalize_alerts_settings(await _get_alerts_fallback(guild_id))

    payload = {
        "enabled": _bool_from_form(data, "enabled"),
        "notify_channel_id": notify_channel_id,
        "mention_role_ids": mention_role_ids,
        "cooldown_seconds": _int_from_form(data, "cooldown_seconds", 60, 10, 3600),
        "platforms": dict(existing_settings.get("platforms") or {}),
    }

    if target_platform:
        current_platform = dict((payload.get("platforms") or {}).get(target_platform) or {})
        payload["platforms"][target_platform] = {
            "enabled": _bool_from_form(data, f"{target_platform}_enabled"),
            "entries": _read_entries_json(f"{target_platform}_entries_json"),
            "message_template": (
                str(
                    _posted_form_value(
                        data,
                        f"{target_platform}_template",
                        current_platform.get("message_template") or "{platform}: {title} {url}",
                    )
                    or ""
                ).strip()[:300]
            ),
        }
    else:
        payload["platforms"] = {
            "twitch": {
                "enabled": _bool_from_form(data, "twitch_enabled"),
                "entries": _read_entries_json("twitch_entries_json"),
                "message_template": (data.get("twitch_template") or "{platform}: {title} {url}").strip()[:300],
            },
            "tiktok": {
                "enabled": _bool_from_form(data, "tiktok_enabled"),
                "entries": _read_entries_json("tiktok_entries_json"),
                "message_template": (data.get("tiktok_template") or "{platform}: {title} {url}").strip()[:300],
            },
            "github": {
                "enabled": _bool_from_form(data, "github_enabled"),
                "entries": _read_entries_json("github_entries_json"),
                "message_template": (data.get("github_template") or "{platform}: {title} {url}").strip()[:300],
            },
            "youtube": {
                "enabled": _bool_from_form(data, "youtube_enabled"),
                "entries": _read_entries_json("youtube_entries_json"),
                "message_template": (data.get("youtube_template") or "{platform}: {title} {url}").strip()[:300],
            },
            "facebook": {
                "enabled": _bool_from_form(data, "facebook_enabled"),
                "entries": _read_entries_json("facebook_entries_json"),
                "message_template": (data.get("facebook_template") or "{platform}: {title} {url}").strip()[:300],
            },
        }

    has_active_platform = any(
        bool(platform_payload.get("enabled")) and bool(platform_payload.get("entries"))
        for platform_payload in payload.get("platforms", {}).values()
        if isinstance(platform_payload, dict)
    )
    if not payload["enabled"] and has_active_platform and notify_channel_id:
        payload["enabled"] = True

    await _save_alerts_fallback(guild_id, payload)
    redirect_tab = active_tab_slug if active_tab_slug in {"alerts", *tab_to_platform.keys()} else "alerts"
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/{redirect_tab}?notice={urlencode({'notice': 'Alerts settings saved'}).split('=',1)[1]}",
        status_code=303,
    )

async def test_alerts_settings_now(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response

    data = await _parse_form(request)
    active_tab_slug = str(data.get("active_tab_slug") or "alerts").strip().lower()
    tab_to_platform = {
        "alerts_twitch": "twitch",
        "alerts_youtube": "youtube",
        "alerts_tiktok": "tiktok",
        "alerts_github": "github",
        "alerts_facebook": "facebook",
    }
    platform = str(data.get("platform") or "").strip().lower() or tab_to_platform.get(active_tab_slug, "")
    settings = await _get_alerts_fallback(guild_id)
    ok, message = await _run_alerts_platform_test(guild_id, platform, settings)
    notice = message if ok else f"ทดสอบไม่สำเร็จ: {message}"
    redirect_tab = active_tab_slug if active_tab_slug in {"alerts", *tab_to_platform.keys()} else "alerts"
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/{redirect_tab}?notice={urlencode({'notice': notice}).split('=',1)[1]}",
        status_code=303,
    )


async def update_voice_randomizer_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response

    form = await request.form()
    data = {
        k: str(v)
        for k, v in form.items()
        if k not in {"embed_thumbnail_file", "embed_image_file"}
    }

    embed_thumbnail_url = (data.get("embed_thumbnail_url") or "").strip()
    embed_image_url = (data.get("embed_image_url") or "").strip()
    upload_preferred_channels = _collect_channel_ids_for_upload((data.get("panel_channel_id") or "").strip())

    uploaded_thumbnail = form.get("embed_thumbnail_file")
    if uploaded_thumbnail and getattr(uploaded_thumbnail, "filename", None):
        try:
            thumbnail_bytes = await uploaded_thumbnail.read()
            if thumbnail_bytes:
                uploaded_thumbnail_url = await _upload_image_to_discord_cdn(
                    guild_id,
                    raw_bytes=thumbnail_bytes,
                    filename=str(getattr(uploaded_thumbnail, "filename", "voice_randomizer_thumb.png")),
                    preferred_channel_ids=upload_preferred_channels,
                    upload_target="embed_messages",
                    asset_kind="thumbnail",
                    request=request,
                    uploader_id=int(_session_user_id(session) or 0),
                    source_route=str(getattr(request.url, "path", "") or ""),
                    source_field="embed_thumbnail_file",
                )
                if uploaded_thumbnail_url:
                    embed_thumbnail_url = uploaded_thumbnail_url
        except Exception:
            pass

    uploaded_image = form.get("embed_image_file")
    if uploaded_image and getattr(uploaded_image, "filename", None):
        try:
            image_bytes = await uploaded_image.read()
            if image_bytes:
                uploaded_image_url = await _upload_image_to_discord_cdn(
                    guild_id,
                    raw_bytes=image_bytes,
                    filename=str(getattr(uploaded_image, "filename", "voice_randomizer_image.png")),
                    preferred_channel_ids=upload_preferred_channels,
                    upload_target="embed_messages",
                    asset_kind="image",
                    request=request,
                    uploader_id=int(_session_user_id(session) or 0),
                    source_route=str(getattr(request.url, "path", "") or ""),
                    source_field="embed_image_file",
                )
                if uploaded_image_url:
                    embed_image_url = uploaded_image_url
        except Exception:
            pass

    payload = _normalize_voice_randomizer_settings(
        {
            "enabled": _bool_from_form(data, "enabled"),
            "panel_channel_id": (data.get("panel_channel_id") or "").strip(),
            "allowed_category_ids": (data.get("allowed_category_ids") or "").strip(),
            "default_category_id": (data.get("default_category_id") or "").strip(),
            "room_mode": (data.get("room_mode") or "normal").strip().lower(),
            "embed_title": (data.get("embed_title") or "").strip(),
            "embed_description": (data.get("embed_description") or "").strip(),
            "embed_color": (data.get("embed_color") or "#5865F2").strip(),
            "embed_footer": (data.get("embed_footer") or "").strip(),
            "embed_thumbnail_url": embed_thumbnail_url,
            "embed_image_url": embed_image_url,
            "category_placeholder": (data.get("category_placeholder") or "").strip(),
            "mode_placeholder": (data.get("mode_placeholder") or "").strip(),
            "button_label": (data.get("button_label") or "").strip(),
            "button_color": (data.get("button_color") or "green").strip().lower(),
            "button_emoji": (data.get("button_emoji") or "").strip(),
            "panel_message_id": str((state.get("voice_randomizer") or {}).get("panel_message_id") or "").strip(),
            "panel_message_channel_id": str((state.get("voice_randomizer") or {}).get("panel_message_channel_id") or "").strip(),
        }
    )

    config_key = _voice_randomizer_config_key(guild_id)
    await _set_dashboard_config_value(config_key, json.dumps(payload, ensure_ascii=False))

    publish_notice = ""
    if payload.get("enabled") and payload.get("panel_channel_id"):
        try:
            published, message, updated_payload = await _publish_voice_randomizer_panel_from_dashboard(guild_id, payload)
            payload = _normalize_voice_randomizer_settings(updated_payload)
            await _set_dashboard_config_value(config_key, json.dumps(payload, ensure_ascii=False))
            if published:
                publish_notice = f" and {message}"
            elif message:
                publish_notice = f" (panel not published: {message})"
        except Exception as error:
            publish_notice = f" (panel not published: {str(error)[:120]})"

    await _append_dashboard_audit_event(guild_id, session, "Updated Voice Randomizer settings", target="voice_randomizer")
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/voice_randomizer?notice={urlencode({'notice': f'Voice Randomizer settings saved{publish_notice}'}).split('=',1)[1]}",
        status_code=303,
    )


async def update_verify_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response

    form = await request.form()
    data = {
        k: str(v)
        for k, v in form.items()
        if k not in {"slip_image_file", "web_verify_embed_image_file"}
    }
    requested_view = str(data.get("verify_view_mode") or "").strip().lower()
    response_view = "web_verify" if requested_view in {"web", "web_verify"} else "verify"
    current_settings = _normalize_verify_settings(state.get("verify") or {})

    pages_raw = (data.get("verify_pages_json") or "").strip()
    try:
        decoded_pages = json.loads(pages_raw) if pages_raw else _default_verify_pages()
    except Exception:
        decoded_pages = _default_verify_pages()
    effective_plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(state.get("guild") or {})
    guild_state_for_plan["subscription"] = effective_plan_tier
    verify_limits = _verify_limits_from_guild_state(guild_state_for_plan)
    verify_limits["max_pages"] = 1
    normalized_pages = _normalize_verify_pages(
        decoded_pages,
        max_pages=int(verify_limits.get("max_pages", 5)),
        max_items_per_page=int(verify_limits.get("max_items_per_page", 12)),
        title_max_length=int(verify_limits.get("title_max_length", 45)),
    )

    payload: dict[str, Any] = dict(current_settings)

    if response_view == "verify":
        payload.update(
            {
                "enabled": _bool_from_form(data, "enabled"),
                "reward_role_ids": _normalize_verify_role_ids((data.get("reward_role_ids") or "").strip()),
                "remove_role_ids": _normalize_verify_role_ids((data.get("remove_role_ids") or "").strip()),
                "color": (data.get("color") or "#39ff14").strip(),
                "description": (data.get("description") or "").strip(),
                "embed_title": (data.get("embed_title") or "Verify").strip(),
                "embed_footer": (data.get("embed_footer") or "").strip(),
                "embed_thumbnail_url": (data.get("embed_thumbnail_url") or "").strip(),
                "embed_image_url": (data.get("embed_image_url") or "").strip(),
                "pages": normalized_pages,
                "verify_channel_id": (data.get("verify_channel_id") or "").strip() or None,
                "notify_channel_id": (data.get("notify_channel_id") or "").strip() or None,
                "auto_role_enabled": (data.get("auto_role_enabled") or "off").strip().lower() == "on",
                "nickname_from_first_input": (data.get("nickname_from_first_input") or "off").strip().lower() == "on",
                "button_color": (data.get("button_color") or "green").strip().lower(),
                "button_label": (data.get("button_label") or "Verify").strip(),
                "button_emoji": (data.get("button_emoji") or "").strip(),
            }
        )
    else:
        web_verify_embed_image_url = (
            (data.get("web_verify_embed_image_url") or data.get("slip_image_url") or "").strip()
            or str(payload.get("web_verify_embed_image_url") or "")
        )
        uploaded = form.get("web_verify_embed_image_file") or form.get("slip_image_file")
        if uploaded and getattr(uploaded, "filename", None):
            try:
                raw_bytes = await uploaded.read()
                if raw_bytes:
                    verify_upload_channels = _collect_channel_ids_for_upload(
                        data.get("web_verify_channel_id"),
                        data.get("web_verify_notify_channel_id"),
                        data.get("verify_channel_id"),
                        data.get("notify_channel_id"),
                        payload.get("web_verify_channel_id"),
                        payload.get("web_verify_notify_channel_id"),
                        payload.get("verify_channel_id"),
                        payload.get("notify_channel_id"),
                    )
                    uploaded_url = await _upload_image_to_discord_cdn(
                        guild_id,
                        raw_bytes=raw_bytes,
                        filename=str(getattr(uploaded, "filename", "web_verify.png")),
                        preferred_channel_ids=verify_upload_channels,
                        upload_target="verify",
                        asset_kind="banner",
                        request=request,
                        uploader_id=int(_session_user_id(session) or 0),
                        source_route=str(getattr(request.url, "path", "") or ""),
                        source_field="web_verify_embed_image_file",
                    )
                    if uploaded_url:
                        web_verify_embed_image_url = uploaded_url
            except Exception:
                pass

        payload.update(
            {
                "web_verify_enabled": _bool_from_form(data, "web_verify_enabled"),
                "web_verify_channel_id": (data.get("web_verify_channel_id") or "").strip() or None,
                "web_verify_notify_channel_id": (data.get("web_verify_notify_channel_id") or "").strip() or None,
                "web_verify_reward_role_ids": _normalize_verify_role_ids((data.get("web_verify_reward_role_ids") or "").strip()),
                "web_verify_remove_role_ids": _normalize_verify_role_ids((data.get("web_verify_remove_role_ids") or "").strip()),
                "web_verify_auto_role_enabled": (data.get("web_verify_auto_role_enabled") or "off").strip().lower() == "on",
                "web_verify_color": (data.get("web_verify_color") or "#5865f2").strip(),
                "web_verify_embed_title": (data.get("web_verify_embed_title") or "Web Verify").strip(),
                "web_verify_embed_description": (data.get("web_verify_embed_description") or "").strip(),
                "web_verify_embed_footer": (data.get("web_verify_embed_footer") or "").strip(),
                "web_verify_embed_thumbnail_url": (data.get("web_verify_embed_thumbnail_url") or "").strip(),
                "web_verify_embed_image_url": web_verify_embed_image_url,
                "slip_image_url": web_verify_embed_image_url,
                "web_verify_intro": (data.get("web_verify_intro") or "").strip(),
                "web_verify_success": (data.get("web_verify_success") or "").strip(),
                "web_verify_error": (data.get("web_verify_error") or "").strip(),
                "web_verify_button_label": (data.get("web_verify_button_label") or "Verify Now").strip(),
                "web_verify_button_color": (data.get("web_verify_button_color") or "green").strip().lower(),
                "web_verify_button_emoji": (data.get("web_verify_button_emoji") or "").strip(),
                "web_back_button_label": (data.get("web_back_button_label") or "Back to Server").strip(),
            }
        )

    payload["reward_role_id"] = payload["reward_role_ids"][0] if payload.get("reward_role_ids") else None
    payload["back_to_server_url"] = str(
        payload.get("back_to_server_url") or str(current_settings.get("back_to_server_url") or "")
    ).strip()
    payload = await _ensure_verify_back_url_from_bot(guild_id, payload)

    await _save_verify_fallback(guild_id, payload)
    publish_notice = ""
    should_publish_verify_panel = (
        response_view == "verify" and bool(payload.get("enabled")) and bool(payload.get("verify_channel_id"))
    )
    should_publish_web_panel = (
        response_view == "web_verify"
        and bool(payload.get("web_verify_channel_id"))
    )

    if should_publish_verify_panel:
        try:
            published, message, updated_payload = await _publish_verify_panel_from_dashboard(guild_id, payload)
            payload = _normalize_verify_settings(updated_payload)
            await _save_verify_fallback(guild_id, payload)
            if published:
                publish_notice = f" ({message})"
            elif message:
                publish_notice = f" (Verify panel was not sent: {message})"
        except Exception as error:
            publish_notice = f" (Verify panel was not sent: {str(error)[:120]})"
    elif should_publish_web_panel:
        try:
            published, message, updated_payload = await _publish_web_verify_panel_from_dashboard(guild_id, payload)
            payload = _normalize_verify_settings(updated_payload)
            await _save_verify_fallback(guild_id, payload)
            if published:
                publish_notice = f" ({message})"
            elif message:
                publish_notice = f" (Web Verify panel was not sent: {message})"
        except Exception as error:
            publish_notice = f" (Web Verify panel was not sent: {str(error)[:120]})"

    query_params = {
        "notice": f"Verification settings saved{publish_notice}",
        "view": response_view,
    }
    return RedirectResponse(
        f"/dashboard/guild/{guild_id}/verify?{urlencode(query_params)}",
        status_code=303,
    )

async def update_aichat_settings(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response:
        return guard_response
    
    data = await _parse_form(request)
    channel_id = (data.get("channel_id") or "").strip()
    memory = (data.get("memory") or "").strip()
    reply_chance_raw = str(data.get("reply_chance", 100) or 100).strip()
    try:
        reply_chance = int(reply_chance_raw)
    except Exception:
        reply_chance = 100
    reply_chance = max(1, min(100, reply_chance))

    if channel_id and channel_id != "None" and not channel_id.isdigit():
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}/aichat?notice=รหัสห้องแชต AI ไม่ถูกต้อง",
            status_code=303,
        )
    
    # Update AI Channel
    existing = await storage.ai_chat_channels.get(guild_id=guild_id)
    if channel_id and channel_id != "None":
        if existing:
            await storage.ai_chat_channels.update(id=existing["id"], channel_id=int(channel_id), reply_chance=reply_chance)
        else:
            await storage.ai_chat_channels.insert(guild_id=guild_id, channel_id=int(channel_id), reply_chance=reply_chance)
    elif existing:
        await storage.ai_chat_channels.update(id=existing["id"], channel_id=None, reply_chance=reply_chance)
        
    # Update AI Memory
    existing_mem = await storage.ai_memories.get(target_id=guild_id, type="guild")
    now_iso = datetime.datetime.now().isoformat()
    if existing_mem:
        await storage.ai_memories.update(id=existing_mem["id"], memory=memory, updated_at=now_iso)
    else:
        await storage.ai_memories.insert(target_id=guild_id, type="guild", memory=memory, created_at=now_iso, updated_at=now_iso)
        
    return RedirectResponse(f"/dashboard/guild/{guild_id}/aichat?notice=บันทึกการตั้งค่า AI สำเร็จแล้ว", status_code=303)

async def clear_aichat_memories(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    await storage.ai_memories.delete(target_id=guild_id, type="guild")
    return RedirectResponse(f"/dashboard/guild/{guild_id}/aichat?notice=ล้างความจำ AI ของเซิร์ฟเวอร์แล้ว", status_code=303)

async def delete_all_server_stats(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    effective_plan_tier = _dashboard_effective_plan_tier(state, session=session)
    if not _is_plan_at_least(effective_plan_tier, "silver"):
        return RedirectResponse(
            f"/dashboard/guild/{guild_id}?notice={urlencode({'notice': 'Statistics is premium only (Silver/Gole/Diamond/Permanent)'}).split('=',1)[1]}",
            status_code=303,
        )
    
    bot = get_bot()
    guild = bot.get_guild(guild_id)
    if not guild: return RedirectResponse(f"/dashboard/guild/{guild_id}/server_stats?notice=Guild data not found", status_code=303)
    
    stats_settings = state.get("server_stats") or {}
    configs = stats_settings.get("stats_configs", [])
    for config in configs:
        channel_id = config.get("channel_id")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                try:
                    await channel.delete()
                except Exception:
                    pass

    updated_settings: dict[str, Any] = {}
    used_fallback = False
    db_row = stats_settings if isinstance(stats_settings, dict) else {}
    if not db_row.get("id"):
        try:
            db_row = await storage.server_stats.get(guild_id=guild_id) or {}
        except Exception as get_error:
            if not _is_atlas_collection_limit_error(get_error):
                raise
            db_row = {}

    if db_row.get("id"):
        try:
            updated_settings = await storage.server_stats.update(
                id=db_row["id"],
                stats_configs=[],
                enabled=False,
            ) or {}
        except Exception as update_error:
            if not _is_atlas_collection_limit_error(update_error):
                raise
            updated_settings = {}

    if not updated_settings:
        used_fallback = True
        updated_settings = await _save_server_stats_fallback(
            guild_id,
            {
                "enabled": False,
                "stats_configs": [],
                "category_name": (stats_settings.get("category_name") or "สถิติเซิร์ฟเวอร์"),
            },
        )

    from skylinebot.memory.cache import cache
    cache.server_stats_cache[str(guild_id)] = updated_settings

    notice = "ลบห้องสถิติทั้งหมดแล้ว"
    return RedirectResponse(f"/dashboard/guild/{guild_id}/server_stats?notice={urlencode({'notice': notice}).split('=',1)[1]}", status_code=303)

async def add_media_channel(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    data = await _parse_form(request)
    channel_id = data.get("channel_id")
    if channel_id and channel_id != "None":
        await storage.media_channels.insert(guild_id=guild_id, channel_id=int(channel_id))
    return RedirectResponse(f"/dashboard/guild/{guild_id}/media?notice=ตั้งค่าช่องส่งสื่อแล้ว", status_code=303)

async def delete_media_channel(request: Request, guild_id: int):
    session, _, current_guild, state = await _require_dashboard_context(request, guild_id)
    guard_response = _blocked_context_redirect_or_dashboard(session=session, current_guild=current_guild, state=state, guild_id=guild_id, request=request)
    if guard_response: return guard_response
    data = await _parse_form(request)
    res_id = data.get("id")
    if res_id:
        await storage.media_channels.delete(id=int(res_id))
    return RedirectResponse(f"/dashboard/guild/{guild_id}/media?notice=ยกเลิกช่องส่งสื่อแล้ว", status_code=303)
