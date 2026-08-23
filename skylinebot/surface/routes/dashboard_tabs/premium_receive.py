from __future__ import annotations

import datetime
from typing import Any

from .. import dashboard_core as core

_PLAN_PRICE: dict[str, str] = {
    "free": "0 THB / 30 days",
    "silver": "40 THB / 30 days",
    "golden": "120 THB / 30 days",
    "diamond": "250 THB / 30 days",
    "permanent": "500 THB / Lifetime",
}

_PLAN_DESCRIPTIONS: dict[str, str] = {
    "free": "Good for small communities that only need core features.",
    "silver": "Unlock premium essentials with higher limits and better control.",
    "golden": "More capacity and flexibility for growing servers.",
    "diamond": "Maximum limits for advanced communities and heavy usage.",
    "permanent": "One-time lifetime plan with all current features and future premium features.",
}

_PLAN_FEATURES: dict[str, list[str]] = {
    "free": [
        "Core command access",
        "Basic server setup modules",
        "No paid subscription required",
    ],
    "silver": [
        "Unlock Silver-tier features",
        "Higher module and configuration limits",
        "Better media/music feature access",
    ],
    "golden": [
        "Unlock Gole-tier features",
        "Higher limits than Silver",
        "Designed for active communities",
    ],
    "diamond": [
        "Unlock all Diamond-tier features",
        "Highest normal monthly limits",
        "Suitable for production-level usage",
    ],
    "permanent": [
        "Includes all Diamond-level rights",
        "Includes future premium features automatically",
        "One-time payment, lifetime access",
    ],
}


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


def _safe_plan_tier(raw_value: Any) -> str:
    normalized = str(raw_value or "free").strip().lower()
    if normalized in {"free", "silver", "golden", "diamond", "permanent"}:
        return normalized
    if normalized in {"gold", "gole"}:
        return "golden"
    if normalized in {"lifetime", "forever"}:
        return "permanent"
    return "free"


def _render_premium_receive(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "premium_receive",
) -> str:
    _core = core
    _escape = _core._escape
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    _global_donatebot_settings = _core._global_donatebot_settings
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _plan_display_name = _core._plan_display_name
    style_urls = _core.style_urls

    guild_id = int(current_guild["id"])
    guild_state = (state or {}).get("guild") if isinstance(state, dict) else {}
    if not isinstance(guild_state, dict):
        guild_state = {}
    plan_subscription = (state or {}).get("plan_subscription") if isinstance(state, dict) else {}
    if not isinstance(plan_subscription, dict):
        plan_subscription = {}

    plan_tier = _safe_plan_tier(_dashboard_effective_plan_tier(state, session=session))
    plan_label = str(_plan_display_name(plan_tier) or "Free").strip() or "Free"
    pending_plan_raw = str(
        plan_subscription.get("pending_plan") or guild_state.get("pending_plan") or ""
    ).strip()
    pending_plan_tier = _safe_plan_tier(pending_plan_raw)
    pending_plan_label = (
        str(_plan_display_name(pending_plan_tier) or "-").strip()
        if pending_plan_raw
        else "-"
    )
    premium_active = plan_tier in {"silver", "golden", "diamond", "permanent"}

    period_start_text = _fmt_datetime(
        plan_subscription.get("current_period_start")
        or guild_state.get("subscription_start")
        or guild_state.get("plan_period_start")
    )
    period_end_text = _fmt_datetime(
        plan_subscription.get("current_period_end")
        or guild_state.get("subscription_end")
    )
    auto_renew = bool(plan_subscription.get("auto_renew", True))

    next_path = f"/dashboard/guild/{guild_id}/premium_receive"
    plan_cards_markup_parts: list[str] = []
    for tier in ("free", "silver", "golden", "diamond", "permanent"):
        title = str(_plan_display_name(tier) or tier.title())
        description = _PLAN_DESCRIPTIONS.get(tier, "")
        feature_markup = "".join(
            f"<li><i class=\"fa-solid fa-check\" aria-hidden=\"true\"></i>{_escape(feature)}</li>"
            for feature in _PLAN_FEATURES.get(tier, [])
        )
        is_current = tier == plan_tier
        current_badge = "<span class=\"pill is-online\">Current Plan</span>" if is_current else ""

        if tier == "free":
            action_markup = (
                "<p class=\"muted\" style=\"margin:0;\">"
                "Available immediately without subscription"
                "</p>"
            )
        else:
            if is_current:
                button_label = "Current Plan"
            elif tier == "permanent":
                button_label = "Choose Lifetime Plan"
            else:
                button_label = "Choose This Plan"
            button_class = "ghost-btn" if is_current else "primary-btn"
            auto_renew_value = "false" if tier == "permanent" else ("true" if auto_renew else "false")
            action_markup = f"""
            <form method=\"post\" action=\"/dashboard/wallet/plan/subscribe\" class=\"premium-plan-form\">
              <input type=\"hidden\" name=\"guild_id\" value=\"{guild_id}\">
              <input type=\"hidden\" name=\"plan_tier\" value=\"{_escape(tier)}\">
              <input type=\"hidden\" name=\"auto_renew\" value=\"{auto_renew_value}\">
              <input type=\"hidden\" name=\"next\" value=\"{_escape(next_path)}\">
              <button class=\"{button_class}\" type=\"submit\">{_escape(button_label)}</button>
            </form>
            """

        plan_cards_markup_parts.append(
            f"""
            <article class=\"premium-plan-card {'is-current' if is_current else ''}\">
              <div class=\"premium-plan-top\">
                <h3>{_escape(title)}</h3>
                {current_badge}
              </div>
              <p class=\"premium-plan-price\">{_escape(_PLAN_PRICE.get(tier, '-'))}</p>
              <p class=\"muted\">{_escape(description)}</p>
              <ul class=\"premium-plan-feature-list\">{feature_markup}</ul>
              <div class=\"premium-plan-actions\">{action_markup}</div>
            </article>
            """
        )

    plan_cards_markup = "".join(plan_cards_markup_parts)

    cancel_plan_form = ""
    if premium_active and plan_tier != "permanent":
        cancel_plan_form = f"""
        <form method=\"post\" action=\"/dashboard/wallet/plan/cancel\" class=\"premium-cancel-form\">
          <input type=\"hidden\" name=\"guild_id\" value=\"{guild_id}\">
          <input type=\"hidden\" name=\"next\" value=\"{_escape(next_path)}\">
          <button class=\"ghost-btn\" type=\"submit\">Cancel Auto Renew</button>
        </form>
        """

    cfg = _global_donatebot_settings()
    support_url = str(cfg.get("support_url") or "").strip() or str(style_urls.SUPPORT_SERVER)
    wallet_url = "/wallet"
    profile_url = "/dashboard/setting-profile-user"
    premium_doc_url = "/premium"

    body = _render_dashboard_f_template("premium_receive.html", locals())
    return _render_layout(
        title=f"SkylineBOT Plan - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
