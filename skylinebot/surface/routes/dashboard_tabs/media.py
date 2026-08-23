from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_media(session: dict[str, Any], guilds: list[dict[str, Any]], current_guild: dict[str, Any], bot_guild: Any, state: dict[str, Any], notice: str | None = None) -> str:
    _core = core
    _escape = _core._escape
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    media_channels = state.get("media_channels") or []
    rows = "".join(
        f"""
        <tr>
            <td style="font-weight:600; color:var(--brand-3);">#{_escape(bot_guild.get_channel(int(r['channel_id'])).name if bot_guild.get_channel(int(r['channel_id'])) else 'Unknown')}</td>
            <td class="muted"><code>{r['channel_id']}</code></td>
            <td>
                <form method="post" action="/dashboard/guild/{current_guild['id']}/media/delete">
                    <input type="hidden" name="id" value="{r['id']}">
                    <button class="ghost-btn" style="color:#ff4d4d; border-color:#ff4d4d22; padding:4px 10px; height:32px; font-size:12px;" type="submit">ยกเลิก</button>
                </form>
            </td>
        </tr>
        """ for r in media_channels
    )
    
    body = _render_dashboard_f_template("media.html", locals())
    return _render_layout(title=f"Media Only - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab="media", notice=notice)
