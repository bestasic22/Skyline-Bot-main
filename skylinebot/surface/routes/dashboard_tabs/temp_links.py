from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_temp_links(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "temp_links",
) -> str:
    _core = core
    _temp_links_settings_from_db = _core._temp_links_settings_from_db
    _escape = _core._escape
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    _ = state  # keep signature parity with other renderers
    settings = _temp_links_settings_from_db(int(current_guild["id"]))
    enabled = bool(settings.get("enabled"))
    channel_id = str(settings.get("channel_id") or "")
    max_uses = int(settings.get("max_uses") or 1)
    max_age_seconds = int(settings.get("max_age_seconds") or 3600)
    max_age_minutes = max(1, round(max_age_seconds / 60))
    temporary_membership = bool(settings.get("temporary_membership"))
    unique_per_member = bool(settings.get("unique_per_member", True))
    history = settings.get("history") or []
    selected_channel = bot_guild.get_channel(int(channel_id)) if (bot_guild and channel_id.isdigit()) else None

    rows: list[str] = []
    for row in history[:20]:
        invite_url = str(row.get("url") or "").strip()
        created_at = str(row.get("created_at") or "").strip()
        creator = str(row.get("creator_name") or row.get("creator_id") or "-").strip() or "-"
        channel_row = str(row.get("channel_id") or "").strip()
        uses_row = int(row.get("max_uses") or 1)
        age_row = int(row.get("max_age_seconds") or 3600)
        temp_row = "ใช่" if bool(row.get("temporary_membership")) else "ไม่"
        channel_label = "-"
        if bot_guild and channel_row.isdigit():
            ch = bot_guild.get_channel(int(channel_row))
            if ch:
                channel_label = f"#{getattr(ch, 'name', channel_row)}"
            else:
                channel_label = f"ID:{channel_row}"
        rows.append(
            "<tr>"
            f"<td><a href=\"{_escape(invite_url)}\" target=\"_blank\" rel=\"noopener\">{_escape(invite_url)}</a></td>"
            f"<td>{_escape(channel_label)}</td>"
            f"<td>{uses_row}</td>"
            f"<td>{max(1, round(age_row / 60))} นาที</td>"
            f"<td>{temp_row}</td>"
            f"<td>{_escape(creator)}</td>"
            f"<td>{_escape(created_at or '-')}</td>"
            "</tr>"
        )

    body = _render_dashboard_f_template("temp_links.html", locals())
    return _render_layout(
        title=f"SkylineBOT Temporary Links - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
