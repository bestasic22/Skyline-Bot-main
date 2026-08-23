from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_autoresponder(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "autoresponder",
) -> str:
    _core = core
    _plan_display_name = _core._plan_display_name
    _plan_limits_from_guild_state = _core._plan_limits_from_guild_state
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _escape = _core._escape
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    responders = state.get("auto_responder") or []
    guild_state = state.get("guild") or {}
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    plan_name = _plan_display_name(plan_tier)
    limits = _plan_limits_from_guild_state(guild_state_for_plan)
    max_items = int(limits["auto_responders"])
    used_items = len(responders)
    limit_reached = used_items >= max_items
    rows = "".join(
        f"""
        <tr>
            <td style="font-weight:600; color:var(--brand);">{_escape(r['keyword'])}</td>
            <td class="muted">{_escape(r['response'][:60])}{'...' if len(r['response']) > 60 else ''}</td>
            <td>
                <form method="post" action="/dashboard/guild/{current_guild['id']}/autoresponder/delete">
                    <input type="hidden" name="id" value="{r['id']}">
                    <button class="ghost-btn" style="color:#ff4d4d; border-color:#ff4d4d22; padding:4px 10px; height:32px; font-size:12px;" type="submit">ลบ</button>
                </form>
            </td>
        </tr>
        """ for r in responders
    )
    
    body = _render_dashboard_f_template("autoresponder.html", locals())
    return _render_layout(title=f"Auto Responder - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab=active_tab_slug, notice=notice)
