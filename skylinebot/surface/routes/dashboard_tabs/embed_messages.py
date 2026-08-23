from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_embed_messages(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "embed_messages",
) -> str:
    _core = core
    _embed_messages_settings_from_db = _core._embed_messages_settings_from_db
    _escape = _core._escape
    json = _core.json
    _render_channel_select = _core._render_channel_select
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    settings = _embed_messages_settings_from_db(int(current_guild["id"]))
    items = settings.get("items") if isinstance(settings.get("items"), list) else []
    selected_id = str(settings.get("selected_id") or "").strip()
    if items and not selected_id:
        selected_id = str(items[0].get("id") or "")
    items_json = _escape(json.dumps(items, ensure_ascii=False))
    selected_name = "new embed"
    for item in items:
        if str(item.get("id") or "") == selected_id:
            selected_name = str(item.get("name") or "new embed")
            break
    channel_select_template = _render_channel_select(
        "__embed_channel_template__",
        bot_guild,
        "",
        placeholder="เลือกห้อง",
        filter_types=["text", "news", "forum"],
    )
    body = _render_dashboard_f_template("embed_messages.html", locals())
    return _render_layout(
        title=f"SkylineBOT Embed Messages - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
