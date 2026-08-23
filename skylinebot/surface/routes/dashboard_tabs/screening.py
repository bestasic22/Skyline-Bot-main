from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_screening(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "screening",
) -> str:
    _core = core
    _escape = _core._escape
    _plan_display_name = _core._plan_display_name
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _is_plan_at_least = _core._is_plan_at_least
    _screening_categories_settings_from_db = _core._screening_categories_settings_from_db
    SCREENING_CATEGORY_ITEMS = _core.SCREENING_CATEGORY_ITEMS
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)

    automod = state.get("automod") or {}
    antinuke = state.get("antinuke") or {}
    screening_settings = _screening_categories_settings_from_db(int(current_guild["id"]))

    automod_enabled_flags = [
        bool(automod.get("antilink_enabled")),
        bool(automod.get("antispam_enabled")),
        bool(automod.get("antibadwords_enabled")),
    ]
    automod_enabled_count = sum(1 for flag in automod_enabled_flags if flag)

    antiraid_enabled_flags = [
        bool(antinuke.get("anti_bot_add")),
        bool(antinuke.get("anti_channel_delete")),
        bool(antinuke.get("anti_role_delete")),
        bool(antinuke.get("anti_webhook_create")),
        bool(antinuke.get("anti_everyone_mention")),
    ]
    antiraid_enabled_count = sum(1 for flag in antiraid_enabled_flags if flag)
    antiraid_mode = str(antinuke.get("type") or "normal").strip().lower() or "normal"
    if antiraid_mode == "extream":
        antiraid_mode = "extreme"
    antiraid_mode_label = {
        "normal": "Normal",
        "extreme": "Extreme",
        "custom": "Custom",
    }.get(antiraid_mode, antiraid_mode.title())

    category_enabled_count = 0
    category_locked_count = 0
    category_rows: list[str] = []
    for item in SCREENING_CATEGORY_ITEMS:
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip() or key
        required_tier = str(item.get("premium_tier") or "").strip().lower()
        row = screening_settings.get(key) or {}
        enabled = bool(row.get("enabled"))
        if required_tier and not _is_plan_at_least(plan_tier, required_tier):
            enabled = False
            category_locked_count += 1
        if enabled:
            category_enabled_count += 1
        state_label = "เปิดใช้งาน" if enabled else ("ล็อกพรีเมียม" if required_tier and not _is_plan_at_least(plan_tier, required_tier) else "ปิดอยู่")
        state_class = "on" if enabled else ("locked" if "ล็อก" in state_label else "off")
        category_rows.append(
            f'<li><span>{_escape(label)}</span><span class="screening-state {state_class}">{_escape(state_label)}</span></li>'
        )

    screening_status = "เปิดใช้งาน" if category_enabled_count > 0 else "ยังไม่เปิด"
    screening_status_class = "on" if category_enabled_count > 0 else "off"

    automod_status = "เปิดใช้งาน" if automod_enabled_count > 0 else "ยังไม่เปิด"
    automod_status_class = "on" if automod_enabled_count > 0 else "off"

    antiraid_status = "เปิดใช้งาน" if bool(antinuke.get("enabled")) else "ยังไม่เปิด"
    antiraid_status_class = "on" if bool(antinuke.get("enabled")) else "off"

    body = _render_dashboard_f_template("screening_overview.html", locals())
    return _render_layout(
        title=f"SkylineBOT Screening - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )


def _render_screening_categories(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
) -> str:
    _core = core
    _plan_display_name = _core._plan_display_name
    _screening_categories_settings_from_db = _core._screening_categories_settings_from_db
    _screening_categories_plan_cap = _core._screening_categories_plan_cap
    cache = _core.cache
    SCREENING_CATEGORY_ITEMS = _core.SCREENING_CATEGORY_ITEMS
    _is_plan_at_least = _core._is_plan_at_least
    SCREENING_CATEGORY_DEFAULT_COLORS = _core.SCREENING_CATEGORY_DEFAULT_COLORS
    re = _core.re
    _escape = _core._escape
    _render_channel_select = _core._render_channel_select
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    PLAN_ORDER = _core.PLAN_ORDER
    SCREENING_CATEGORY_PLAN_LIMITS_BY_TIER = _core.SCREENING_CATEGORY_PLAN_LIMITS_BY_TIER

    plan_tier_labels = {
        "free": "Free",
        "silver": "Silver",
        "golden": "Golden",
        "diamond": "Diamond",
        "permanent": "Permanent",
    }

    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)
    plan_cap = max(0, int(_screening_categories_plan_cap(plan_tier)))
    plan_limits_text = " | ".join(
        f"{plan_tier_labels.get(tier, tier.title())} {int(SCREENING_CATEGORY_PLAN_LIMITS_BY_TIER.get(tier, 0))}"
        for tier in PLAN_ORDER
    )

    settings = _screening_categories_settings_from_db(int(current_guild["id"]))
    guild_log = cache.guilds_log.get(str(current_guild["id"]), {}) or {}

    prepared_rows: list[dict[str, Any]] = []
    requested_enabled_keys: list[str] = []

    for item in SCREENING_CATEGORY_ITEMS:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        label = str(item.get("label") or "").strip() or key
        log_type = str(item.get("log_type") or "").strip().lower()
        required_tier = str(item.get("premium_tier") or "").strip().lower()
        premium_locked = bool(required_tier) and not _is_plan_at_least(plan_tier, required_tier)

        row = settings.get(key) or {}
        requested_enabled = bool(row.get("enabled")) and not premium_locked

        default_channel_id = str(guild_log.get(f"{log_type}_channel_id") or "").strip()
        selected_channel_id = str(row.get("channel_id") or default_channel_id).strip()

        color = str(row.get("color") or SCREENING_CATEGORY_DEFAULT_COLORS.get(log_type, "#6b8cff")).strip()
        if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
            color = SCREENING_CATEGORY_DEFAULT_COLORS.get(log_type, "#6b8cff")

        if requested_enabled:
            requested_enabled_keys.append(key)

        prepared_rows.append(
            {
                "key": key,
                "label": label,
                "log_type": log_type,
                "required_tier": required_tier,
                "premium_locked": premium_locked,
                "selected_channel_id": selected_channel_id,
                "color": color,
                "requested_enabled": requested_enabled,
                "raw_channel_id": str(row.get("channel_id") or "").strip(),
            }
        )

    allowed_enabled_keys = set(requested_enabled_keys[:plan_cap])

    total_categories = len(prepared_rows)
    enabled_count = 0
    premium_locked_count = 0
    cap_locked_count = 0
    cards: list[str] = []

    for row in prepared_rows:
        key = str(row.get("key") or "")
        label = str(row.get("label") or "")
        log_type = str(row.get("log_type") or "")
        required_tier = str(row.get("required_tier") or "")
        premium_locked = bool(row.get("premium_locked"))
        selected_channel_id = str(row.get("selected_channel_id") or "")
        color = str(row.get("color") or "#6b8cff")

        enabled = key in allowed_enabled_keys
        cap_locked = (not premium_locked) and (not enabled) and (enabled_count >= plan_cap)

        if premium_locked:
            premium_locked_count += 1
        if cap_locked:
            cap_locked_count += 1
        if enabled:
            enabled_count += 1

        toggle_checked = "checked" if enabled else ""
        toggle_disabled = "disabled" if premium_locked else ""

        if premium_locked:
            state_text = "Premium Locked"
            state_class = "locked"
        elif cap_locked:
            state_text = "Plan Limit"
            state_class = "locked"
        elif enabled:
            state_text = "Enabled"
            state_class = "on"
        else:
            state_text = "Disabled"
            state_class = "off"

        card_classes = ["screening-cat-card", "panel-sub"]
        if premium_locked or cap_locked:
            card_classes.extend(["is-locked", "is-disabled"])
        elif enabled:
            card_classes.append("is-enabled")
        else:
            card_classes.append("is-disabled")

        details_open_attr = "open" if enabled else ""
        tier_label = plan_tier_labels.get(required_tier, required_tier.title())
        premium_badge = (
            f'<span class="sc-chip premium">Premium {tier_label}+</span>'
            if required_tier
            else ""
        )

        channel_note = "Use dedicated channel" if str(row.get("raw_channel_id") or "").strip() else "Use default log channel"
        search_tokens = _escape(f"{label} {log_type}".lower())

        channel_select_html = _render_channel_select(
            name=f"sc_{key}_channel_id",
            bot_guild=bot_guild,
            current_id=selected_channel_id,
            placeholder="Select ..",
            filter_types=["text", "news", "forum"],
            disabled=(not enabled) or premium_locked,
        )

        cards.append(
            f"""
            <details class="{' '.join(card_classes)}" data-sc-card data-sc-search="{search_tokens}" data-sc-log-type="{_escape(log_type)}" data-sc-premium-locked="{'1' if premium_locked else '0'}" {details_open_attr}>
              <summary class="screening-cat-head">
                <div class="screening-cat-head-main">
                  <strong>{_escape(label)}</strong>
                  <div class="screening-cat-meta">
                    <span class="sc-chip state {state_class}" data-sc-state>{_escape(state_text)}</span>
                    <span class="sc-chip">{_escape(log_type)}</span>
                    {premium_badge}
                  </div>
                </div>
                <div class="screening-cat-head-actions">
                  <span class="sc-expand-indicator" aria-hidden="true"></span>
                  <label class="ux-toggle" data-sc-stop-toggle>
                    <input type="checkbox" name="sc_{_escape(key)}_enabled" data-sc-toggle {toggle_checked} {toggle_disabled}>
                    <span class="ux-switch"></span>
                  </label>
                </div>
              </summary>
              <div class="screening-cat-body">
                <p class="muted sc-card-note">{_escape(channel_note)}</p>
                <div class="field-item sc-channel-field">
                  {channel_select_html}
                </div>
                <div class="field-item sc-color-field">
                  <label>Log Color</label>
                  <input type="color" name="sc_{_escape(key)}_color" value="{_escape(color)}" data-sc-color {('disabled' if (not enabled) or premium_locked else '')}>
                </div>
              </div>
              <input type="hidden" name="sc_{_escape(key)}_log_type" value="{_escape(log_type)}">
            </details>
            """
        )

    locked_count = premium_locked_count + cap_locked_count
    disabled_count = max(0, total_categories - enabled_count - locked_count)

    body = _render_dashboard_f_template("screening_categories.html", locals())
    return _render_layout(
        title=f"SkylineBOT Screening Categories - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab="screening_categories",
        notice=notice,
    )
