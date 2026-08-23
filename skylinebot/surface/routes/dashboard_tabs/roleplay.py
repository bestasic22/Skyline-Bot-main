from __future__ import annotations

import datetime
import json
import re
from typing import Any

from .. import dashboard_core as core
from skylinebot.utils import fancy_text


ROLEPLAY_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("modern_city", "City Roleplay Pack"),
)

ROLEPLAY_ACTION_LABELS: dict[str, str] = {
    "save_settings": "Save Settings",
    "apply_preset": "Apply Preset",
    "manage_permissions": "Manage Permission Matrix",
    "add_scenario": "Create Scenario",
    "delete_scenario": "Delete Scenario",
    "start_event": "Start Event",
    "end_event": "End Event",
    "manage_scheduler": "Manage Scheduler",
    "manage_economy_guard": "Manage Economy Guard",
    "import_config": "Import RP Config",
    "export_config": "Export RP Config",
    "view_audit": "View Audit Log",
    "rollback": "Rollback",
}

ROLEPLAY_ACTION_DEFAULT_LEVELS: dict[str, str] = {
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

ROLEPLAY_LEVEL_OPTIONS: tuple[str, ...] = ("owner", "admin", "gm", "player")
ROLEPLAY_LEVEL_RANK: dict[str, int] = {"player": 1, "gm": 2, "admin": 3, "owner": 4}


def _normalize_hex_color(value: Any, default: str = "#99AAB5") -> str:
    raw = str(value or "").strip()
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if re.match(r"^#[0-9A-Fa-f]{6}$", raw):
        return raw.upper()
    return default


def _normalize_id_list(raw_values: Any) -> list[str]:
    values = raw_values if isinstance(raw_values, list) else [raw_values]
    out: list[str] = []
    for raw in values:
        for token in re.split(r"[\s,]+", str(raw or "").strip()):
            text = str(token or "").strip()
            if text.isdigit() and text not in out:
                out.append(text)
    return out[:500]


def _as_utc(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)


def _normalize_permission_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    gm_role_ids: list[str] = []
    player_role_ids: list[str] = []
    for raw in list(src.get("gm_role_ids") or []):
        text = str(raw or "").strip()
        if text.isdigit() and text not in gm_role_ids:
            gm_role_ids.append(text)
    for raw in list(src.get("player_role_ids") or []):
        text = str(raw or "").strip()
        if text.isdigit() and text not in player_role_ids:
            player_role_ids.append(text)
    action_levels: dict[str, str] = {}
    raw_action_levels = src.get("action_levels") if isinstance(src.get("action_levels"), dict) else {}
    for action_key, fallback_level in ROLEPLAY_ACTION_DEFAULT_LEVELS.items():
        normalized_level = str(raw_action_levels.get(action_key) or fallback_level).strip().lower()
        if normalized_level not in ROLEPLAY_LEVEL_RANK:
            normalized_level = fallback_level
        action_levels[action_key] = normalized_level
    return {
        "gm_role_ids": gm_role_ids,
        "player_role_ids": player_role_ids,
        "action_levels": action_levels,
    }


def _normalize_economy_guard(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}

    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    return {
        "enabled": bool(src.get("enabled")),
        "max_reward_xp": _safe_int(src.get("max_reward_xp"), 250000, 0, 2500000),
        "max_reward_coins": _safe_int(src.get("max_reward_coins"), 250000, 0, 2500000),
        "inflation_threshold_avg_coins": _safe_int(src.get("inflation_threshold_avg_coins"), 25000, 1, 10000000),
        "base_reduce_percent": _safe_int(src.get("base_reduce_percent"), 20, 0, 95),
        "min_multiplier_percent": _safe_int(src.get("min_multiplier_percent"), 55, 5, 100),
        "last_multiplier_percent": _safe_int(src.get("last_multiplier_percent"), 100, 5, 100),
    }


def _render_roleplay(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "roleplay",
) -> str:
    _core = core
    _escape = _core._escape
    _normalize_roleplay_dashboard_settings = _core._normalize_roleplay_dashboard_settings
    _normalize_economy_dashboard_settings = _core._normalize_economy_dashboard_settings
    _format_datetime_th = _core._format_datetime_th
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    is_guildstyle_studio = str(active_tab_slug or "").strip().lower() == "guildstyle_studio"

    settings_raw = state.get("rp_settings") if isinstance(state.get("rp_settings"), dict) else {}
    settings = _normalize_roleplay_dashboard_settings(settings_raw)
    scenarios = state.get("rp_scenarios") if isinstance(state.get("rp_scenarios"), list) else []
    active_event = state.get("rp_event") if isinstance(state.get("rp_event"), dict) else {}
    leaderboard = state.get("rp_characters_top") if isinstance(state.get("rp_characters_top"), list) else []
    permission_payload = _normalize_permission_settings(
        state.get("rp_permissions") if isinstance(state.get("rp_permissions"), dict) else {}
    )
    economy_guard = _normalize_economy_guard(
        state.get("rp_economy_guard") if isinstance(state.get("rp_economy_guard"), dict) else {}
    )
    schedules = state.get("rp_schedules") if isinstance(state.get("rp_schedules"), list) else []
    audit_rows = state.get("rp_audit_logs") if isinstance(state.get("rp_audit_logs"), list) else []
    event_history = state.get("rp_event_history") if isinstance(state.get("rp_event_history"), list) else []
    scenario_stats = state.get("rp_scenario_stats") if isinstance(state.get("rp_scenario_stats"), list) else []
    economy_settings = _normalize_economy_dashboard_settings(
        state.get("economy_settings") if isinstance(state.get("economy_settings"), dict) else {}
    )
    economy_currency_symbol = str(economy_settings.get("currency_symbol") or "coin").strip() or "coin"
    economy_work_enabled = bool(economy_settings.get("command_work_enabled"))
    economy_crime_enabled = bool(economy_settings.get("command_crime_enabled"))
    economy_role_income_enabled = bool(economy_settings.get("role_income_enabled"))
    economy_chat_money_enabled = bool(economy_settings.get("chat_money_enabled"))
    economy_channels_enabled = bool(economy_settings.get("economy_channels_enabled"))
    economy_allow_all_channels = bool(economy_settings.get("economy_allow_all_channels"))
    economy_command_channels = list(economy_settings.get("economy_command_channels") or [])
    economy_command_mode_text = (
        "all channels"
        if not economy_channels_enabled or economy_allow_all_channels
        else f"{len(economy_command_channels)} channels"
    )
    dashboard_access = state.get("dashboard_access") if isinstance(state.get("dashboard_access"), dict) else {}
    guildstyle_layout_state = (
        state.get("guildstyle_layout")
        if isinstance(state.get("guildstyle_layout"), dict)
        else {}
    )
    guildstyle_selected_theme = str(guildstyle_layout_state.get("theme") or "roleplay").strip().lower()
    if guildstyle_selected_theme not in {"community", "shop", "gaming", "roleplay", "custom"}:
        guildstyle_selected_theme = "roleplay"
    if is_guildstyle_studio and guildstyle_selected_theme not in {"community", "shop", "gaming", "roleplay"}:
        guildstyle_selected_theme = "roleplay"
    guildstyle_font_style_rows: list[dict[str, str]] = []
    guildstyle_font_style_labels: dict[str, str] = {}
    guildstyle_font_style_keys: list[str] = []
    for row in fancy_text.list_styles(sample_text="GuildStyle"):
        style_key = str(row.get("id") or "").strip().lower()
        if not style_key or style_key in guildstyle_font_style_labels:
            continue
        guildstyle_font_style_labels[style_key] = str(row.get("name") or style_key).strip() or style_key
        guildstyle_font_style_keys.append(style_key)
        guildstyle_font_style_rows.append(
            {
                "id": style_key,
                "name": guildstyle_font_style_labels[style_key],
            }
        )
    if not guildstyle_font_style_keys:
        guildstyle_font_style_keys = ["bold"]
        guildstyle_font_style_labels = {"bold": "Bold"}
        guildstyle_font_style_rows = [{"id": "bold", "name": "Bold"}]

    raw_saved_font_style = str(guildstyle_layout_state.get("font_style") or "").strip()
    if raw_saved_font_style and fancy_text.is_known_style(raw_saved_font_style):
        guildstyle_selected_font_style = fancy_text.normalize_style_key(raw_saved_font_style)
    else:
        guildstyle_selected_font_style = "bold" if "bold" in guildstyle_font_style_keys else guildstyle_font_style_keys[0]
    if guildstyle_selected_font_style not in guildstyle_font_style_keys:
        guildstyle_selected_font_style = "bold" if "bold" in guildstyle_font_style_keys else guildstyle_font_style_keys[0]
    guildstyle_selected_name_mode = str(guildstyle_layout_state.get("name_mode") or "fancy").strip().lower()
    if guildstyle_selected_name_mode not in {
        "fancy",
        "plain",
        "styled",
        "emoji_bracket",
        "emoji_dash",
        "emoji_dot",
        "capsule",
        "template",
    }:
        guildstyle_selected_name_mode = "fancy"
    guildstyle_selected_name_template = str(
        guildstyle_layout_state.get("name_template") or "₊˚꒰{emoji}꒱ ₊{name}✧꒷₊˚"
    ).strip()[:180]
    if not guildstyle_selected_name_template:
        guildstyle_selected_name_template = "₊˚꒰{emoji}꒱ ₊{name}✧꒷₊˚"
    guildstyle_name_mode_rows = [
        {"id": "fancy", "name": "Fancy Wrapper"},
        {"id": "plain", "name": "Emoji + Styled Name"},
        {"id": "styled", "name": "Styled Name Only"},
        {"id": "emoji_bracket", "name": "Bracket [emoji] Name"},
        {"id": "emoji_dash", "name": "Emoji - Name"},
        {"id": "emoji_dot", "name": "Emoji . Name"},
        {"id": "capsule", "name": "Bracket [Name]"},
        {"id": "template", "name": "Custom Template"},
    ]
    guildstyle_name_mode_keys = [
        str(row.get("id") or "").strip().lower()
        for row in guildstyle_name_mode_rows
        if str(row.get("id") or "").strip()
    ]
    if guildstyle_selected_name_mode not in guildstyle_name_mode_keys:
        guildstyle_selected_name_mode = "fancy"
    guildstyle_selected_name_template = (
        str(guildstyle_selected_name_template or "").strip()[:180] or "₊˚꒰{emoji}꒱ ₊{name}✧꒷₊˚"
    )

    guildstyle_category_theme_map = (
        guildstyle_layout_state.get("category_theme_map")
        if isinstance(guildstyle_layout_state.get("category_theme_map"), dict)
        else {}
    )
    guildstyle_rename_exclude_role_ids = set(
        _normalize_id_list(guildstyle_layout_state.get("rename_exclude_role_ids"))
    )
    guildstyle_rename_exclude_channel_ids = set(
        _normalize_id_list(guildstyle_layout_state.get("rename_exclude_channel_ids"))
    )
    guildstyle_font_style_option_html = "".join(
        (
            f"<option value='{_escape(style_key)}' {'selected' if guildstyle_selected_font_style == style_key else ''}>"
            f"{_escape(style_key)} ({_escape(guildstyle_font_style_labels.get(style_key, style_key))})"
            "</option>"
        )
        for style_key in guildstyle_font_style_keys
    )
    guildstyle_name_mode_option_html = "".join(
        (
            f"<option value='{_escape(mode_key)}' "
            f"data-base-label='{_escape(str(row.get('name') or mode_key))}' "
            f"{'selected' if guildstyle_selected_name_mode == mode_key else ''}>"
            f"{_escape(str(row.get('name') or mode_key))}"
            "</option>"
        )
        for row in guildstyle_name_mode_rows
        for mode_key in [str(row.get("id") or "").strip().lower()]
        if mode_key
    )
    guildstyle_preview_font_pills_html = "".join(
        (
            f"<button type='button' class='pill gsPreviewFontPill' data-gs-font-style='{_escape(style_key)}' "
            f"title='{_escape(guildstyle_font_style_labels.get(style_key, style_key))}'>"
            f"{_escape(style_key)}"
            "</button>"
        )
        for style_key in guildstyle_font_style_keys
    )
    guildstyle_font_style_allowed_csv = ",".join(guildstyle_font_style_keys)

    session_user_raw = str(((session or {}).get("user") or {}).get("id") or "").strip()
    session_user_id = int(session_user_raw) if session_user_raw.isdigit() else 0
    actor_member = bot_guild.get_member(session_user_id) if bot_guild and session_user_id else None
    actor_role_ids = {
        str(int(getattr(role, "id", 0) or 0))
        for role in list(getattr(actor_member, "roles", []) or [])
        if str(getattr(role, "id", "") or "").strip().isdigit()
    }
    owner_id_raw = str((current_guild or {}).get("owner_id") or getattr(bot_guild, "owner_id", 0) or "").strip()
    owner_id = int(owner_id_raw) if owner_id_raw.isdigit() else 0
    is_owner = bool(session_user_id and owner_id and int(session_user_id) == int(owner_id))
    is_owner = bool(is_owner or dashboard_access.get("effective_is_owner"))
    is_admin = bool(
        dashboard_access.get("has_admin_like_permission")
        or dashboard_access.get("is_dashboard_admin")
    )
    actor_level = "player"
    if is_owner:
        actor_level = "owner"
    elif is_admin:
        actor_level = "admin"
    elif any(role_id in actor_role_ids for role_id in permission_payload["gm_role_ids"]):
        actor_level = "gm"

    def _can(action_key: str) -> bool:
        required_level = permission_payload["action_levels"].get(action_key, "owner")
        return ROLEPLAY_LEVEL_RANK.get(actor_level, 0) >= ROLEPLAY_LEVEL_RANK.get(required_level, 99)

    can_save_settings = _can("save_settings")
    can_apply_preset = _can("apply_preset")
    can_manage_permissions = _can("manage_permissions")
    can_manage_channels = bool(can_manage_permissions)
    can_add_scenario = _can("add_scenario")
    can_delete_scenario = _can("delete_scenario")
    can_start_event = _can("start_event")
    can_end_event = _can("end_event")
    can_manage_scheduler = _can("manage_scheduler")
    can_manage_guard = _can("manage_economy_guard")
    can_import_config = _can("import_config")
    can_export_config = _can("export_config")
    can_view_audit = _can("view_audit")
    can_rollback = _can("rollback")
    if is_guildstyle_studio:
        # Keep Theme Studio permissions independent from RP action matrix.
        theme_admin_access = bool(is_owner or is_admin)
        can_apply_preset = theme_admin_access
        can_manage_permissions = theme_admin_access
        can_manage_channels = theme_admin_access
    export_config_url = (
        f"/dashboard/guild/{current_guild['id']}/roleplay/export"
        if can_export_config
        else f"/dashboard/guild/{current_guild['id']}/roleplay"
    )

    permission_badges: list[str] = []
    for key, label in ROLEPLAY_ACTION_LABELS.items():
        level = permission_payload["action_levels"].get(key, ROLEPLAY_ACTION_DEFAULT_LEVELS.get(key, "owner"))
        permission_badges.append(
            "<tr>"
            f"<td>{_escape(label)}</td>"
            "<td>"
            f"<select name=\"perm_{_escape(key)}\" {'disabled' if not can_manage_permissions else ''}>"
            + "".join(
                f"<option value=\"{lvl}\" {'selected' if level == lvl else ''}>{lvl.upper()}</option>"
                for lvl in ROLEPLAY_LEVEL_OPTIONS
            )
            + "</select>"
            "</td>"
            "</tr>"
        )
    permission_matrix_rows_html = "".join(permission_badges)

    preset_rows = []
    current_preset = str(settings.get("preset_key") or "modern_city").strip()
    for key, label in ROLEPLAY_PRESET_OPTIONS:
        selected = "selected" if current_preset == key else ""
        preset_rows.append(f'<option value="{_escape(key)}" {selected}>{_escape(label)}</option>')
    preset_select_html = "".join(preset_rows)

    announce_channel_id = str(settings.get("event_announce_channel_id") or "").strip()
    announce_channel_options: list[str] = ["<option value=''>No notification channel</option>"]
    if bot_guild:
        for channel in sorted(
            list(getattr(bot_guild, "text_channels", []) or []),
            key=lambda row: int(getattr(row, "position", 0) or 0),
        )[:250]:
            channel_id = str(int(getattr(channel, "id", 0) or 0))
            channel_name = str(getattr(channel, "name", "") or channel_id)
            selected = "selected" if channel_id == announce_channel_id else ""
            announce_channel_options.append(
                f"<option value='{_escape(channel_id)}' {selected}>#{_escape(channel_name)}</option>"
            )
    event_announce_channel_select_html = "".join(announce_channel_options)

    role_options: list[str] = []
    if bot_guild:
        for role in sorted(
            [role for role in list(getattr(bot_guild, "roles", []) or []) if not role.is_default()],
            key=lambda row: int(getattr(row, "position", 0) or 0),
            reverse=True,
        )[:250]:
            role_id = str(int(getattr(role, "id", 0) or 0))
            role_name = str(getattr(role, "name", "") or role_id)
            gm_selected = "checked" if role_id in permission_payload["gm_role_ids"] else ""
            player_selected = "checked" if role_id in permission_payload["player_role_ids"] else ""
            role_options.append(
                "<tr>"
                f"<td>{_escape(role_name)}</td>"
                f"<td><input type='checkbox' name='gm_role_ids' value='{_escape(role_id)}' {gm_selected} {'disabled' if not can_manage_permissions else ''}></td>"
                f"<td><input type='checkbox' name='player_role_ids' value='{_escape(role_id)}' {player_selected} {'disabled' if not can_manage_permissions else ''}></td>"
                "</tr>"
            )
    role_matrix_rows_html = (
        "".join(role_options)
        if role_options
        else "<tr><td colspan='3' class='muted'>No roles found in this server.</td></tr>"
    )

    # GuildStyle Studio data (live + preview)
    guildstyle_theme_preview_cards_html = ""
    guildstyle_live_acl_rows_html = ""
    guildstyle_role_inspector_rows_html = ""
    guildstyle_role_palette_rows_html = ""
    guildstyle_role_option_html = "<option value=''>Select role</option>"
    guildstyle_channel_option_html = "<option value=''>Select room</option>"
    guildstyle_category_option_html = "<option value=''>Select category</option>"
    guildstyle_channel_parent_option_html = "<option value=''>No category (uncategorized)</option>"
    guildstyle_channel_manage_option_html = "<option value=''>Select channel</option>"
    guildstyle_role_exclude_option_html = ""
    guildstyle_channel_exclude_option_html = ""
    guildstyle_category_reorder_option_html = "<option value=''>Select category</option>"
    guildstyle_channel_reorder_option_html = "<option value=''>Select channel</option>"
    guildstyle_category_drag_items_html = "<li class='gs-dnd-empty muted'>No categories found.</li>"
    guildstyle_channel_drag_items_html = "<li class='gs-dnd-empty muted'>No channels found.</li>"
    guildstyle_role_drag_items_html = "<li class='gs-dnd-empty muted'>No roles found.</li>"
    guildstyle_channel_reorder_group_option_html = "<option value=''>No channel groups</option>"
    guildstyle_category_theme_rows_html = "<tr><td colspan='3' class='muted'>No categories found.</td></tr>"
    guildstyle_engine_compare_rows_html = "<tr><td colspan='3' class='muted'>No preview sample available.</td></tr>"
    guildstyle_role_filter_options_html = ""
    guildstyle_room_count = 0
    guildstyle_role_count = 0
    guildstyle_preview_notice = ""

    if bot_guild and is_guildstyle_studio:
        bot_self_member = getattr(bot_guild, "me", None)
        bot_top_role_position = int(getattr(getattr(bot_self_member, "top_role", None), "position", 0) or 0)
        roles_for_ui = sorted(
            [role for role in list(getattr(bot_guild, "roles", []) or []) if not role.is_default()],
            key=lambda item: int(getattr(item, "position", 0) or 0),
            reverse=True,
        )[:80]
        guildstyle_role_count = len(roles_for_ui)
        role_id_map = {str(int(getattr(role, "id", 0) or 0)): role for role in roles_for_ui}
        role_options_markup: list[str] = ["<option value=''>Select role</option>"]
        role_exclude_options_markup: list[str] = []
        for role in roles_for_ui:
            role_id = str(int(getattr(role, "id", 0) or 0))
            role_name = str(getattr(role, "name", "") or "Role")
            role_color_hex = _normalize_hex_color(
                f"#{int(getattr(getattr(role, 'color', None), 'value', 0) or 0):06X}"
            )
            role_options_markup.append(
                f"<option value='{_escape(role_id)}' data-role-color='{_escape(role_color_hex)}' data-role-name='{_escape(role_name)}'>{_escape(role_name)}</option>"
            )
            role_exclude_options_markup.append(
                f"<option value='{_escape(role_id)}' {'selected' if role_id in guildstyle_rename_exclude_role_ids else ''}>"
                f"{_escape(role_name)}"
                "</option>"
            )
        guildstyle_role_option_html = "".join(role_options_markup)
        guildstyle_role_exclude_option_html = "".join(role_exclude_options_markup)
        guildstyle_role_filter_options_html = "".join(
            f"<label class='pill gs-role-filter-pill'><input type='checkbox' class='gsRoleFilterCheckbox' value='{_escape(str(int(getattr(role, 'id', 0) or 0)))}'>"
            f"<span>{_escape(str(getattr(role, 'name', '') or 'Role'))}</span></label>"
            for role in roles_for_ui[:40]
        )

        selected_theme_by_category: dict[str, str] = {}
        for raw_cat_id, raw_theme in guildstyle_category_theme_map.items():
            cat_id_text = str(raw_cat_id or "").strip()
            theme_key = str(raw_theme or "").strip().lower()
            if not cat_id_text.isdigit():
                continue
            if theme_key not in {"community", "shop", "gaming", "roleplay", "custom"}:
                continue
            selected_theme_by_category[cat_id_text] = theme_key
        theme_display_name = {
            "community": "Community",
            "shop": "Shop",
            "gaming": "Gaming",
            "roleplay": "Roleplay",
            "custom": "custom",
        }

        everyone_role = getattr(bot_guild, "default_role", None)
        live_channels: list[Any] = []
        categories = sorted(
            list(getattr(bot_guild, "categories", []) or []),
            key=lambda item: int(getattr(item, "position", 0) or 0),
        )
        category_options_markup: list[str] = ["<option value=''>Select category</option>"]
        category_reorder_options_markup: list[str] = ["<option value=''>Select category</option>"]
        category_drag_items_markup: list[str] = []
        channel_parent_options_markup: list[str] = ["<option value=''>No category (uncategorized)</option>"]
        category_theme_rows: list[str] = []
        for cat_order_index, category in enumerate(categories, start=1):
            category_id = str(int(getattr(category, "id", 0) or 0))
            category_name = str(getattr(category, "name", "") or category_id)
            mapped_theme = selected_theme_by_category.get(category_id, "")
            effective_theme = mapped_theme or guildstyle_selected_theme
            mapped_badge = theme_display_name.get(mapped_theme, mapped_theme) if mapped_theme else "inherit"
            effective_badge = theme_display_name.get(effective_theme, effective_theme)
            category_options_markup.append(
                f"<option value='{_escape(category_id)}'>{_escape(category_name)}</option>"
            )
            category_reorder_options_markup.append(
                f"<option value='{_escape(category_id)}'>{_escape(f'[{cat_order_index}] {category_name}')}</option>"
            )
            category_drag_items_markup.append(
                "<li class='gs-dnd-item' draggable='true' "
                f"data-dnd-id='{_escape(category_id)}' "
                f"data-category-id='{_escape(category_id)}'>"
                "<span class='gs-dnd-handle' aria-hidden='true'>::</span>"
                f"<span class='gs-dnd-title'>{_escape(category_name)}</span>"
                f"<small class='muted'>#{cat_order_index}</small>"
                "</li>"
            )
            channel_parent_options_markup.append(
                f"<option value='{_escape(category_id)}'>{_escape(category_name)}</option>"
            )
            category_theme_rows.append(
                "<tr class='gs-category-map-row' "
                f"data-category-id='{_escape(category_id)}' "
                f"data-mapped-theme='{_escape(mapped_theme if mapped_theme else 'inherit')}'>"
                f"<td>{_escape(category_name)}</td>"
                f"<td><code>{_escape(mapped_badge)}</code></td>"
                f"<td><code>{_escape(effective_badge)}</code></td>"
                "</tr>"
            )
            live_channels.append(category)
            for text_ch in sorted(list(getattr(category, "text_channels", []) or []), key=lambda item: int(getattr(item, "position", 0) or 0)):
                live_channels.append(text_ch)
            for voice_ch in sorted(list(getattr(category, "voice_channels", []) or []), key=lambda item: int(getattr(item, "position", 0) or 0)):
                live_channels.append(voice_ch)
        guildstyle_category_option_html = "".join(category_options_markup)
        guildstyle_category_reorder_option_html = "".join(category_reorder_options_markup)
        guildstyle_category_drag_items_html = (
            "".join(category_drag_items_markup)
            if category_drag_items_markup
            else "<li class='gs-dnd-empty muted'>No categories found.</li>"
        )
        guildstyle_channel_parent_option_html = "".join(channel_parent_options_markup)
        guildstyle_category_theme_rows_html = (
            "".join(category_theme_rows)
            if category_theme_rows
            else "<tr><td colspan='3' class='muted'>No categories found.</td></tr>"
        )
        uncategorized_text = [
            ch
            for ch in list(getattr(bot_guild, "text_channels", []) or [])
            if not getattr(ch, "category_id", None)
        ]
        uncategorized_voice = [
            ch
            for ch in list(getattr(bot_guild, "voice_channels", []) or [])
            if not getattr(ch, "category_id", None)
        ]
        for text_ch in sorted(uncategorized_text, key=lambda item: int(getattr(item, "position", 0) or 0)):
            live_channels.append(text_ch)
        for voice_ch in sorted(uncategorized_voice, key=lambda item: int(getattr(item, "position", 0) or 0)):
            live_channels.append(voice_ch)
        live_channels = live_channels[:180]
        guildstyle_room_count = len(live_channels)
        channel_options_markup: list[str] = ["<option value=''>Select room</option>"]
        channel_exclude_options_markup: list[str] = []
        channel_manage_options_markup: list[str] = ["<option value=''>Select channel</option>"]
        channel_reorder_options_markup: list[str] = ["<option value=''>Select channel</option>"]
        channel_reorder_group_labels: dict[str, str] = {}
        channel_drag_items_markup: list[str] = []
        for ch in live_channels:
            channel_id = str(int(getattr(ch, "id", 0) or 0))
            channel_name = str(getattr(ch, "name", "") or channel_id)
            is_category = hasattr(ch, "text_channels") and hasattr(ch, "voice_channels")
            if is_category:
                channel_label = f"[CAT] {channel_name}"
            else:
                channel_label = ("#" if hasattr(ch, "topic") else "[VC] ") + channel_name
            channel_options_markup.append(
                f"<option value='{_escape(channel_id)}'>{_escape(channel_label)}</option>"
            )
            channel_exclude_options_markup.append(
                f"<option value='{_escape(channel_id)}' {'selected' if channel_id in guildstyle_rename_exclude_channel_ids else ''}>"
                f"{_escape(channel_label)}"
                "</option>"
            )
            if is_category:
                continue
            channel_type = "text" if hasattr(ch, "topic") else "voice"
            category_id = (
                str(int(getattr(getattr(ch, "category", None), "id", 0) or 0))
                if getattr(ch, "category", None)
                else ""
            )
            category_name = (
                str(getattr(getattr(ch, "category", None), "name", "") or "uncategorized")
                if getattr(ch, "category", None)
                else "uncategorized"
            )
            if category_id:
                channel_group_key = f"cat:{category_id}"
                channel_group_label = category_name
            else:
                channel_group_key = "uncat"
                channel_group_label = "uncategorized"
            channel_manage_options_markup.append(
                f"<option value='{_escape(channel_id)}' "
                f"data-channel-type='{_escape(channel_type)}' "
                f"data-category-id='{_escape(category_id)}' "
                f"data-channel-group='{_escape(channel_group_key)}'>"
                f"{_escape(channel_label)}"
                "</option>"
            )
            if channel_group_key not in channel_reorder_group_labels:
                channel_reorder_group_labels[channel_group_key] = channel_group_label
            channel_drag_items_markup.append(
                "<li class='gs-dnd-item' draggable='true' "
                f"data-dnd-id='{_escape(channel_id)}' "
                f"data-channel-id='{_escape(channel_id)}' "
                f"data-channel-group='{_escape(channel_group_key)}'>"
                "<span class='gs-dnd-handle' aria-hidden='true'>::</span>"
                f"<span class='gs-dnd-title'>{_escape(channel_label)}</span>"
                f"<small class='muted'>{_escape(channel_group_label)}</small>"
                "</li>"
            )
            display_position = int(getattr(ch, "position", 0) or 0) + 1
            channel_reorder_options_markup.append(
                f"<option value='{_escape(channel_id)}'>"
                f"{_escape(f'[{display_position}] {channel_label} ({category_name})')}"
                "</option>"
            )
        guildstyle_channel_option_html = "".join(channel_options_markup)
        guildstyle_channel_exclude_option_html = "".join(channel_exclude_options_markup)
        guildstyle_channel_manage_option_html = "".join(channel_manage_options_markup)
        guildstyle_channel_reorder_option_html = "".join(channel_reorder_options_markup)
        guildstyle_channel_drag_items_html = (
            "".join(channel_drag_items_markup)
            if channel_drag_items_markup
            else "<li class='gs-dnd-empty muted'>No channels found.</li>"
        )
        guildstyle_channel_reorder_group_option_html = (
            "".join(
                f"<option value='{_escape(group_key)}' {'selected' if idx == 0 else ''}>{_escape(group_label)}</option>"
                for idx, (group_key, group_label) in enumerate(channel_reorder_group_labels.items())
            )
            if channel_reorder_group_labels
            else "<option value=''>No channel groups</option>"
        )

        # Performance guard:
        # ACL matrix (channels x roles) is expensive and currently not rendered by template.
        # Keep lightweight data preparation only for sections that are visible in GuildStyle Studio.
        guildstyle_live_acl_rows_html = "<tr><td colspan='6' class='muted'>Live ACL matrix is disabled for fast loading.</td></tr>"
        guildstyle_role_inspector_rows_html = "<tr><td colspan='6' class='muted'>Role inspector is disabled for fast loading.</td></tr>"

        palette_rows: list[str] = []
        role_drag_items_markup: list[str] = []
        for role_order_index, role in enumerate(roles_for_ui, start=1):
            role_id = str(int(getattr(role, "id", 0) or 0))
            role_name = str(getattr(role, "name", "") or role_id)
            role_color_hex = _normalize_hex_color(f"#{int(getattr(getattr(role, 'color', None), 'value', 0) or 0):06X}")
            role_position = int(getattr(role, "position", 0) or 0)
            role_is_managed = bool(getattr(role, "managed", False))
            palette_rows.append(
                "<tr class='gs-role-palette-row' "
                f"data-role-id='{_escape(role_id)}' "
                f"data-role-name='{_escape(role_name)}' "
                f"data-role-color='{_escape(role_color_hex)}'>"
                f"<td><span class='gs-color-dot' style='--gs-color:{_escape(role_color_hex)}'></span>{_escape(role_name)}</td>"
                f"<td><code>{_escape(role_color_hex)}</code></td>"
                f"<td>{int(getattr(getattr(role, 'color', None), 'value', 0) or 0)}</td>"
                "</tr>"
            )
            if not role_is_managed and role_position < bot_top_role_position:
                role_drag_items_markup.append(
                    "<li class='gs-dnd-item' draggable='true' "
                    f"data-dnd-id='{_escape(role_id)}' "
                    f"data-role-id='{_escape(role_id)}' "
                    f"data-role-name='{_escape(role_name)}' "
                    f"data-role-color='{_escape(role_color_hex)}' "
                    f"data-role-position='{role_position}' "
                    f"data-role-managed='{'1' if role_is_managed else '0'}'>"
                    "<span class='gs-dnd-handle' aria-hidden='true'>::</span>"
                    f"<span class='gs-dnd-title'><span class='gs-color-dot' style='--gs-color:{_escape(role_color_hex)}'></span>{_escape(role_name)}</span>"
                    f"<small class='muted'>#{role_order_index}</small>"
                    "</li>"
                )
        guildstyle_role_palette_rows_html = (
            "".join(palette_rows)
            if palette_rows
            else "<tr><td colspan='3' class='muted'>No role colors available.</td></tr>"
        )
        guildstyle_role_drag_items_html = (
            "".join(role_drag_items_markup)
            if role_drag_items_markup
            else "<li class='gs-dnd-empty muted'>No roles found.</li>"
        )

        try:
            from skylinebot.src.commands.guildstyle import (
                GuildStyler,
                _fancy_wrap,
                _keyword_emoji,
                _title_case_from_slug,
                _trim_name,
            )

            theme_blueprints: dict[str, dict[str, Any]] = {}
            theme_role_specs: dict[str, list[Any]] = {}
            preview_cards: list[str] = []
            for theme_key, theme_title in (
                ("community", "Community"),
                ("shop", "Shop"),
                ("gaming", "Gaming"),
                ("roleplay", "Roleplay"),
            ):
                blueprint = GuildStyler._theme_blueprint(theme_key)
                role_specs = GuildStyler._role_specs_for_theme(theme_key)
                theme_blueprints[theme_key] = blueprint if isinstance(blueprint, dict) else {"categories": []}
                theme_role_specs[theme_key] = list(role_specs or [])
                for font_style in guildstyle_font_style_keys:
                    category_chips: list[str] = []
                    for category_spec in list(blueprint.get("categories", []))[:6]:
                        category_name = _trim_name(
                            _fancy_wrap(
                                category_spec.get("name", "category"),
                                category_spec.get("emoji", "C"),
                                font_style,
                            )
                        )
                        text_sample = [
                            _trim_name(_fancy_wrap(item, _keyword_emoji(item), font_style))
                            for item in list(category_spec.get("text", []))[:2]
                        ]
                        voice_sample = [
                            _trim_name(_fancy_wrap(item, _keyword_emoji(item), font_style))
                            for item in list(category_spec.get("voice", []))[:2]
                        ]
                        category_chips.append(
                            "<div class='gs-preview-category'>"
                            f"<strong>{_escape(category_name)}</strong>"
                            f"<div class='muted'>Text: {_escape(', '.join(text_sample) if text_sample else '-')}</div>"
                            f"<div class='muted'>Voice: {_escape(', '.join(voice_sample) if voice_sample else '-')}</div>"
                            "</div>"
                        )
                    role_swatches = "".join(
                        (
                            f"<span class='gs-preview-role' style='--gs-color:#{int(getattr(role_color, 'value', 0) or 0):06X}'>"
                            f"{_escape(_trim_name(_fancy_wrap(role_slug, role_emoji, font_style)))}"
                            "</span>"
                        )
                        for role_slug, role_emoji, role_color in role_specs[:12]
                    )
                    hidden_attr = (
                        ""
                        if theme_key == guildstyle_selected_theme and font_style == guildstyle_selected_font_style
                        else " hidden"
                    )
                    preview_cards.append(
                        (
                            f"<article class='gs-preview-card' data-gs-theme-key='{_escape(theme_key)}' "
                            f"data-gs-font-style='{_escape(font_style)}'{hidden_attr}>"
                            f"<h3>{_escape(theme_title)} <small class='muted'>({font_style}: {_escape(guildstyle_font_style_labels.get(font_style, font_style))})</small></h3>"
                            f"<div class='gs-preview-roles'>{role_swatches}</div>"
                            f"<div class='gs-preview-categories'>{''.join(category_chips)}</div>"
                            "</article>"
                        )
                    )
            guildstyle_theme_preview_cards_html = "".join(preview_cards)

            def _slug_from_current(raw_name: Any, *, fallback: str) -> str:
                text = str(raw_name or "").strip().lower()
                text = text.replace("_", " ").replace("-", " ")
                text = re.sub(r"[^\w\u0E00-\u0E7F ]+", " ", text, flags=re.UNICODE)
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    return fallback
                slug = text.replace(" ", "-")
                slug = re.sub(r"-{2,}", "-", slug).strip("-")
                return slug or fallback

            def _slot_slug_emoji(theme_key: str, kind: str, index: int, fallback_slug: str) -> tuple[str, str]:
                if kind == "role":
                    role_specs = theme_role_specs.get(theme_key) or []
                    if role_specs:
                        role_slug, role_emoji, _ = role_specs[index % len(role_specs)]
                        slug = str(role_slug or fallback_slug).strip() or fallback_slug
                        emoji = str(role_emoji or _keyword_emoji(slug)).strip() or _keyword_emoji(slug)
                        return slug, emoji
                    emoji = _keyword_emoji(fallback_slug)
                    return fallback_slug, emoji

                blueprint = theme_blueprints.get(theme_key) or {"categories": []}
                categories_src = list(blueprint.get("categories") or [])
                if not categories_src:
                    emoji = _keyword_emoji(fallback_slug)
                    return fallback_slug, emoji
                if kind == "category":
                    spec = categories_src[index % len(categories_src)]
                    slug = str(spec.get("name") or fallback_slug).strip() or fallback_slug
                    raw_emoji = str(spec.get("emoji") or "").strip()
                    if raw_emoji and (
                        re.fullmatch(r"<a?:[A-Za-z0-9_]{2,32}:\d{16,22}>", raw_emoji)
                        or re.search(r"[\U0001F1E6-\U0001FAFF\u2600-\u27BF]", raw_emoji)
                    ):
                        emoji = raw_emoji
                    else:
                        emoji = _keyword_emoji(slug)
                    return slug, emoji
                if kind == "channel_text":
                    text_pool = [str(item or "").strip() for cat in categories_src for item in list(cat.get("text", []) or []) if str(item or "").strip()]
                    slug = text_pool[index % len(text_pool)] if text_pool else fallback_slug
                    emoji = _keyword_emoji(slug)
                    return slug, emoji
                if kind == "channel_voice":
                    voice_pool = [str(item or "").strip() for cat in categories_src for item in list(cat.get("voice", []) or []) if str(item or "").strip()]
                    slug = voice_pool[index % len(voice_pool)] if voice_pool else fallback_slug
                    emoji = _keyword_emoji(slug)
                    return slug, emoji
                emoji = _keyword_emoji(fallback_slug)
                return fallback_slug, emoji

            def _build_style_map(slug_value: str, emoji_value: str) -> dict[str, dict[str, str]]:
                out: dict[str, dict[str, str]] = {}
                safe_slug = str(slug_value or "item").strip() or "item"
                safe_emoji = str(emoji_value or _keyword_emoji(safe_slug)).strip() or _keyword_emoji(safe_slug)
                for style_key in guildstyle_font_style_keys:
                    pretty_name = _title_case_from_slug(safe_slug)
                    styled_name = fancy_text.transform_text(pretty_name, style_key)
                    out[style_key] = {
                        "fancy": _trim_name(_fancy_wrap(safe_slug, safe_emoji, style_key)),
                        "plain": _trim_name(f"{safe_emoji} {styled_name}".strip()),
                        "styled": styled_name,
                        "pretty": pretty_name,
                        "emoji": safe_emoji,
                    }
                return out

            def _select_engine_name(
                preview_map: dict[str, Any],
                *,
                theme_key: str,
                style_key: str,
                mode_key: str,
                template_text: str,
            ) -> str:
                resolved_theme = theme_key if theme_key in preview_map else "__custom__"
                theme_pack = preview_map.get(resolved_theme) if isinstance(preview_map.get(resolved_theme), dict) else {}
                style_pack = theme_pack.get(style_key) if isinstance(theme_pack.get(style_key), dict) else {}
                if not style_pack and isinstance(theme_pack, dict):
                    style_pack = next((value for value in theme_pack.values() if isinstance(value, dict)), {})
                if not style_pack:
                    return "-"
                fancy_value = str(style_pack.get("fancy") or style_pack.get("plain") or "-")
                plain_value = str(style_pack.get("plain") or fancy_value or "-")
                styled_value = str(style_pack.get("styled") or "").strip()
                pretty_value = str(style_pack.get("pretty") or styled_value or "").strip()
                emoji_value = str(style_pack.get("emoji") or "").strip()
                if mode_key == "plain":
                    return plain_value
                if mode_key == "styled":
                    return _trim_name(styled_value or pretty_value or plain_value)
                if mode_key == "emoji_bracket":
                    return _trim_name(f"[{emoji_value}] {styled_value or pretty_value}".strip())
                if mode_key == "emoji_dash":
                    return _trim_name(f"{emoji_value} - {styled_value or pretty_value}".strip())
                if mode_key == "emoji_dot":
                    return _trim_name(f"{emoji_value} . {styled_value or pretty_value}".strip())
                if mode_key == "capsule":
                    return _trim_name(f"[{styled_value or pretty_value}]".strip())
                if mode_key == "template":
                    template_src = str(template_text or "{emoji} {name}")
                    template_src = template_src.replace("{{emoji}}", "{emoji}").replace("{{name}}", "{name}")
                    rendered = (
                        template_src
                        .replace("{emoji}", emoji_value)
                        .replace("{name}", styled_value or pretty_value)
                    )
                    rendered = re.sub(r"\s+", " ", rendered).strip()
                    return _trim_name(rendered or plain_value)
                return fancy_value

            sample_rows_meta: list[dict[str, Any]] = []
            for idx, cat_obj in enumerate(categories[:2]):
                sample_rows_meta.append(
                    {
                        "kind": "category",
                        "index": idx,
                        "label": "Category",
                        "before": str(getattr(cat_obj, "name", "") or f"category-{idx+1}"),
                    }
                )
            text_sample_src = sorted(list(getattr(bot_guild, "text_channels", []) or []), key=lambda row: int(getattr(row, "position", 0) or 0))
            for idx, text_obj in enumerate(text_sample_src[:2]):
                sample_rows_meta.append(
                    {
                        "kind": "channel_text",
                        "index": idx,
                        "label": "Text Channel",
                        "before": str(getattr(text_obj, "name", "") or f"text-{idx+1}"),
                    }
                )
            voice_sample_src = sorted(list(getattr(bot_guild, "voice_channels", []) or []), key=lambda row: int(getattr(row, "position", 0) or 0))
            for idx, voice_obj in enumerate(voice_sample_src[:1]):
                sample_rows_meta.append(
                    {
                        "kind": "channel_voice",
                        "index": idx,
                        "label": "Voice Channel",
                        "before": str(getattr(voice_obj, "name", "") or f"voice-{idx+1}"),
                    }
                )
            for idx, role_obj in enumerate(roles_for_ui[:3]):
                sample_rows_meta.append(
                    {
                        "kind": "role",
                        "index": idx,
                        "label": "Role",
                        "before": str(getattr(role_obj, "name", "") or f"role-{idx+1}"),
                    }
                )

            compare_rows: list[str] = []
            for sample in sample_rows_meta:
                sample_kind = str(sample.get("kind") or "category")
                sample_index = int(sample.get("index") or 0)
                before_name = str(sample.get("before") or "").strip() or "-"
                fallback_slug = _slug_from_current(before_name, fallback=sample_kind.replace("_", "-"))
                fallback_emoji = _keyword_emoji(fallback_slug)
                preview_map: dict[str, Any] = {
                    "__custom__": _build_style_map(fallback_slug, fallback_emoji),
                }
                for theme_key in ("community", "shop", "gaming", "roleplay"):
                    slot_slug, slot_emoji = _slot_slug_emoji(theme_key, sample_kind, sample_index, fallback_slug)
                    preview_map[theme_key] = _build_style_map(slot_slug, slot_emoji)

                after_name = _select_engine_name(
                    preview_map,
                    theme_key="__custom__",
                    style_key=guildstyle_selected_font_style,
                    mode_key=guildstyle_selected_name_mode,
                    template_text=guildstyle_selected_name_template,
                )
                preview_json = _escape(json.dumps(preview_map, ensure_ascii=False, separators=(",", ":")))
                compare_rows.append(
                    "<tr class='gs-engine-compare-row' "
                    f"data-gs-preview-map='{preview_json}'>"
                    f"<td><code>{_escape(str(sample.get('label') or 'Item'))}</code></td>"
                    f"<td><span class='gs-engine-before-value'>{_escape(before_name)}</span></td>"
                    f"<td><span class='gs-engine-after-value'>{_escape(after_name)}</span></td>"
                    "</tr>"
                )
            guildstyle_engine_compare_rows_html = (
                "".join(compare_rows)
                if compare_rows
                else "<tr><td colspan='3' class='muted'>No preview sample available.</td></tr>"
            )
        except Exception:
            guildstyle_preview_notice = "Preview uses fallback mode because GuildStyle renderer was unavailable."
    scenario_rows: list[str] = []
    scenario_delete_rows: list[str] = []
    scenario_event_rows: list[str] = []
    scenario_scheduler_rows: list[str] = []
    custom_count = 0
    for row in scenarios:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "").strip()
        if not row_id.isdigit():
            continue
        scenario_key = str(row.get("scenario_key") or "").strip()
        scenario_name = str(row.get("name") or "Scenario").strip()
        description = str(row.get("description") or "").strip()
        difficulty = str(row.get("difficulty") or "normal").strip()
        reward_xp = int(row.get("reward_xp") or 0)
        reward_coins = int(row.get("reward_coins") or 0)
        is_preset = bool(row.get("is_preset"))
        if not is_preset:
            custom_count += 1
        scenario_rows.append(
            "<tr>"
            f"<td><code>{_escape(scenario_key or row_id)}</code></td>"
            f"<td>{_escape(scenario_name)}</td>"
            f"<td>{_escape(difficulty)}</td>"
            f"<td>{reward_xp:,}</td>"
            f"<td>{reward_coins:,}</td>"
            f"<td>{'Preset' if is_preset else 'Custom'}</td>"
            f"<td title=\"{_escape(description)}\">{_escape(description[:120] + ('...' if len(description) > 120 else ''))}</td>"
            "</tr>"
        )
        scenario_event_rows.append(
            f'<option value="{_escape(row_id)}">{_escape(scenario_name)} ({_escape(scenario_key)})</option>'
        )
        scenario_scheduler_rows.append(
            f'<option value="{_escape(scenario_key)}">{_escape(scenario_name)} ({_escape(scenario_key)})</option>'
        )
        if not is_preset:
            scenario_delete_rows.append(
                f'<option value="{_escape(row_id)}">{_escape(scenario_name)} ({_escape(scenario_key or row_id)})</option>'
            )

    scenario_table_html = (
        "".join(scenario_rows)
        if scenario_rows
        else "<tr><td colspan='7' class='muted'>No scenarios yet. Apply a preset to install starter scenarios.</td></tr>"
    )
    scenario_delete_select_html = (
        "".join(scenario_delete_rows)
        if scenario_delete_rows
        else "<option value=''>No custom scenarios</option>"
    )
    scenario_event_select_html = "".join(scenario_event_rows)
    scenario_schedule_select_html = "".join(scenario_scheduler_rows)

    status = str(active_event.get("status") or "idle").strip().lower()
    event_is_active = status == "active"
    event_title = str(active_event.get("event_title") or "No active event").strip()
    event_template = str(active_event.get("template_key") or "-").strip()
    event_reward_xp = int(active_event.get("reward_xp") or 0)
    event_reward_coins = int(active_event.get("reward_coins") or 0)
    event_participants = active_event.get("participants") if isinstance(active_event.get("participants"), list) else []
    event_started_at = _format_datetime_th(active_event.get("started_at"))
    event_ends_at = _format_datetime_th(active_event.get("ends_at"))
    event_badge_class = "is-active" if event_is_active else "is-idle"
    event_badge_text = "ACTIVE" if event_is_active else "IDLE"

    leaderboard_rows: list[str] = []
    active_players_7d = 0
    recent_threshold = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    for index, row in enumerate(leaderboard[:20], start=1):
        if not isinstance(row, dict):
            continue
        user_id = int(row.get("user_id") or 0)
        if user_id <= 0:
            continue
        member = bot_guild.get_member(user_id) if bot_guild else None
        display_name = str(getattr(member, "display_name", "") or row.get("character_name") or f"User {user_id}")
        character_name = str(row.get("character_name") or "").strip() or display_name
        level = int(row.get("level") or 1)
        xp = int(row.get("xp") or 0)
        coins = int(row.get("coins") or 0)
        reputation = int(row.get("reputation") or 0)
        activity_points = [
            _as_utc(row.get("last_daily_at")),
            _as_utc(row.get("last_story_at")),
            _as_utc(row.get("last_scenario_at")),
            _as_utc(row.get("updated_at")),
        ]
        if any(point and point >= recent_threshold for point in activity_points):
            active_players_7d += 1
        leaderboard_rows.append(
            "<tr>"
            f"<td>#{index}</td>"
            f"<td>{_escape(display_name)}</td>"
            f"<td>{_escape(character_name)}</td>"
            f"<td>{level:,}</td>"
            f"<td>{xp:,}</td>"
            f"<td>{coins:,}</td>"
            f"<td>{reputation:,}</td>"
            "</tr>"
        )
    leaderboard_html = (
        "".join(leaderboard_rows)
        if leaderboard_rows
        else "<tr><td colspan='7' class='muted'>No character data yet.</td></tr>"
    )

    schedule_rows_html: list[str] = []
    for row in schedules[:80]:
        if not isinstance(row, dict):
            continue
        schedule_id = str(row.get("id") or "").strip()
        if not schedule_id.isdigit():
            continue
        enabled = bool(row.get("enabled"))
        schedule_name = str(row.get("schedule_name") or f"Schedule #{schedule_id}")
        frequency = str(row.get("frequency") or "daily").lower()
        weekday = int(row.get("weekday") or 0)
        time_text = f"{int(row.get('hour') or 0):02d}:{int(row.get('minute') or 0):02d}"
        tz_offset = int(row.get("timezone_offset_minutes") or 0)
        tz_sign = "+" if tz_offset >= 0 else "-"
        tz_abs = abs(tz_offset)
        tz_label = f"UTC{tz_sign}{tz_abs // 60:02d}:{tz_abs % 60:02d}"
        duration = int(row.get("duration_minutes") or 30)
        next_run = _format_datetime_th(row.get("next_run_at"))
        scenario_key = str(row.get("scenario_key") or "auto")
        frequency_label = "Daily" if frequency == "daily" else f"Weekly (day {weekday})"
        schedule_rows_html.append(
            "<tr>"
            f"<td>{_escape(schedule_name)}</td>"
            f"<td>{_escape(frequency_label)}</td>"
            f"<td>{_escape(time_text)} ({_escape(tz_label)})</td>"
            f"<td>{duration}m</td>"
            f"<td><code>{_escape(scenario_key)}</code></td>"
            f"<td>{_escape(next_run)}</td>"
            f"<td>{'Enabled' if enabled else 'Disabled'}</td>"
            "<td>"
            f"<form method='post' action='/dashboard/guild/{current_guild['id']}/roleplay' class='rp-inline-form'>"
            "<input type='hidden' name='action' value='toggle_schedule'>"
            f"<input type='hidden' name='schedule_id' value='{_escape(schedule_id)}'>"
            f"<button type='submit' class='ghost-btn' {'disabled' if not can_manage_scheduler else ''}>{'Disable' if enabled else 'Enable'}</button>"
            "</form>"
            f"<form method='post' action='/dashboard/guild/{current_guild['id']}/roleplay' class='rp-inline-form'>"
            "<input type='hidden' name='action' value='delete_schedule'>"
            f"<input type='hidden' name='schedule_id' value='{_escape(schedule_id)}'>"
            f"<button type='submit' class='ghost-btn danger rpDeleteScheduleButton' {'disabled' if not can_manage_scheduler else ''}>Delete</button>"
            "</form>"
            "</td>"
            "</tr>"
        )
    schedule_table_html = (
        "".join(schedule_rows_html)
        if schedule_rows_html
        else "<tr><td colspan='8' class='muted'>No schedule yet.</td></tr>"
    )

    audit_table_rows: list[str] = []
    for row in audit_rows[:50]:
        if not isinstance(row, dict):
            continue
        log_id = str(row.get("id") or "").strip()
        if not log_id.isdigit():
            continue
        actor_name = str(row.get("actor_name") or f"User {int(row.get('actor_user_id') or 0)}")
        action = str(row.get("action") or "-")
        scope = str(row.get("scope") or "-")
        note = str(row.get("note") or "").strip()
        created_at = _format_datetime_th(row.get("created_at"))
        rollback_button = (
            f"<form method='post' action='/dashboard/guild/{current_guild['id']}/roleplay'>"
            "<input type='hidden' name='action' value='rollback'>"
            f"<input type='hidden' name='audit_id' value='{_escape(log_id)}'>"
            f"<button type='submit' class='ghost-btn danger rpRollbackButton' {'disabled' if not can_rollback else ''}>Rollback</button>"
            "</form>"
        )
        audit_table_rows.append(
            "<tr>"
            f"<td>#{_escape(log_id)}</td>"
            f"<td>{_escape(created_at)}</td>"
            f"<td>{_escape(actor_name)}</td>"
            f"<td>{_escape(action)}</td>"
            f"<td>{_escape(scope)}</td>"
            f"<td title='{_escape(note)}'>{_escape(note[:110] + ('...' if len(note) > 110 else ''))}</td>"
            f"<td>{rollback_button}</td>"
            "</tr>"
        )
    audit_table_html = (
        "".join(audit_table_rows)
        if audit_table_rows
        else "<tr><td colspan='7' class='muted'>No RP audit logs yet.</td></tr>"
    )

    popular_scenario_rows: list[str] = []
    for row in scenario_stats[:12]:
        if not isinstance(row, dict):
            continue
        scenario_name = str(row.get("scenario_name") or row.get("scenario_key") or "-")
        popular_scenario_rows.append(
            "<tr>"
            f"<td>{_escape(scenario_name)}</td>"
            f"<td>{int(row.get('play_count') or 0):,}</td>"
            f"<td>{int(row.get('event_start_count') or 0):,}</td>"
            f"<td>{int(row.get('total_reward_xp') or 0):,}</td>"
            f"<td>{int(row.get('total_reward_coins') or 0):,}</td>"
            "</tr>"
        )
    scenario_analytics_html = (
        "".join(popular_scenario_rows)
        if popular_scenario_rows
        else "<tr><td colspan='5' class='muted'>No scenario analytics yet.</td></tr>"
    )

    event_analytics_rows: list[str] = []
    best_reward_event: dict[str, Any] | None = None
    best_popular_event: dict[str, Any] | None = None
    for row in event_history[:20]:
        if not isinstance(row, dict):
            continue
        participants = int(row.get("participants_count") or 0)
        xp_total = int(row.get("total_reward_xp") or 0)
        coins_total = int(row.get("total_reward_coins") or 0)
        xp_per = int(row.get("reward_xp_per_player") or 0)
        coins_per = int(row.get("reward_coins_per_player") or 0)
        score = xp_per + coins_per
        if not best_reward_event or score > int(best_reward_event.get("_score") or 0):
            best_reward_event = dict(row)
            best_reward_event["_score"] = score
        if not best_popular_event or participants > int(best_popular_event.get("participants_count") or 0):
            best_popular_event = row
        event_analytics_rows.append(
            "<tr>"
            f"<td>{_escape(str(row.get('event_title') or '-'))}</td>"
            f"<td><code>{_escape(str(row.get('scenario_key') or '-'))}</code></td>"
            f"<td>{participants:,}</td>"
            f"<td>{xp_total:,}</td>"
            f"<td>{coins_total:,}</td>"
            f"<td>{xp_per:,}</td>"
            f"<td>{coins_per:,}</td>"
            "</tr>"
        )
    event_analytics_html = (
        "".join(event_analytics_rows)
        if event_analytics_rows
        else "<tr><td colspan='7' class='muted'>No event analytics yet.</td></tr>"
    )
    best_reward_event_name = str((best_reward_event or {}).get("event_title") or "-")
    best_popular_event_name = str((best_popular_event or {}).get("event_title") or "-")
    history_event_count = len(event_history)

    actor_permission_summary = (
        f"Your RP level: {actor_level.upper()} | "
        f"Owner: {'YES' if is_owner else 'NO'} | "
        f"Admin-like: {'YES' if is_admin else 'NO'}"
    )
    guildstyle_access_summary = (
        f"Theme access: {actor_level.upper()} | "
        f"Owner: {'YES' if is_owner else 'NO'} | "
        f"Admin-like: {'YES' if is_admin else 'NO'}"
    )

    guildstyle_post_target = f"/dashboard/guild/{current_guild['id']}/guildstyle_studio"
    roleplay_tab_url = f"/dashboard/guild/{current_guild['id']}/roleplay"
    economy_tab_url = f"/dashboard/guild/{current_guild['id']}/economy"
    guildstyle_tab_url = f"/dashboard/guild/{current_guild['id']}/guildstyle_studio"
    template_name = "guildstyle_studio.html" if is_guildstyle_studio else "roleplay.html"
    body = _render_dashboard_f_template(template_name, locals())
    page_title = (
        f"SkylineBOT Theme guildstyle - {current_guild['name']}"
        if is_guildstyle_studio
        else f"SkylineBOT Roleplay - {current_guild['name']}"
    )
    return _render_layout(
        title=page_title,
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )

