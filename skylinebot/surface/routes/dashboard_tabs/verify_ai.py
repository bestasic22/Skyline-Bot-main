from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_ocr(session: dict[str, Any], guilds: list[dict[str, Any]], current_guild: dict[str, Any], bot_guild: Any, state: dict[str, Any], notice: str | None = None) -> str:
    _core = core
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    data = state.get("image_ocr") or {}
    body = _render_dashboard_f_template("ocr.html", locals())
    return _render_layout(title=f"SkylineBOT OCR - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab="ocr", notice=notice)

def _render_verify(session: dict[str, Any], guilds: list[dict[str, Any]], current_guild: dict[str, Any], bot_guild: Any, state: dict[str, Any], notice: str | None = None) -> str:
    _core = core
    _preview_bot_identity = _core._preview_bot_identity
    _normalize_verify_settings = _core._normalize_verify_settings
    _plan_display_name = _core._plan_display_name
    _verify_limits_by_tier = _core._verify_limits_by_tier
    _normalize_verify_pages = _core._normalize_verify_pages
    _default_verify_pages = _core._default_verify_pages
    json = _core.json
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    data = _normalize_verify_settings(state.get("verify") or {})
    verify_view_mode = str(state.get("verify_view_mode") or "verify").strip().lower()
    if verify_view_mode not in {"verify", "web_verify"}:
        verify_view_mode = "verify"
    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)
    verify_limits = _verify_limits_by_tier(plan_tier)
    max_pages = int(verify_limits.get("max_pages", 5))
    max_items_per_page = int(verify_limits.get("max_items_per_page", 12))
    title_max_length = int(verify_limits.get("title_max_length", 45))
    normalized_pages = _normalize_verify_pages(
        data.get("pages") or _default_verify_pages(),
        max_pages=max_pages,
        max_items_per_page=max_items_per_page,
        title_max_length=title_max_length,
    )
    pages_seed = json.dumps(normalized_pages, ensure_ascii=False)
    button_colors = {
        "green": "#25c26e",
        "blurple": "#5865f2",
        "red": "#e14343",
        "gray": "#6b7280",
    }
    selected_button_color = str(data.get("button_color") or "green")
    preview_button_color = button_colors.get(selected_button_color, button_colors["green"])
    selected_web_button_color = str(data.get("web_verify_button_color") or "green")
    preview_web_button_color = button_colors.get(selected_web_button_color, button_colors["green"])
    body = _render_dashboard_f_template("verify.html", locals())
    return _render_layout(title=f"SkylineBOT Verify - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab="verify", notice=notice)

def _render_aichat(session: dict[str, Any], guilds: list[dict[str, Any]], current_guild: dict[str, Any], bot_guild: Any, state: dict[str, Any], notice: str | None = None) -> str:
    _core = core
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    ai_chat = dict(state.get("ai_chat") or {})
    ai_chat["enabled"] = bool(ai_chat.get("channel_id"))
    ai_memories = state.get("ai_memories") or {}
    
    body = _render_dashboard_f_template("aichat.html", locals())
    return _render_layout(title=f"SkylineBOT AI - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab="aichat", notice=notice)
