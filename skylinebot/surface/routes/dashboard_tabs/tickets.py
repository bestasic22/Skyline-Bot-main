from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_tickets(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "tickets",
) -> str:
    _core = core
    _preview_bot_identity = _core._preview_bot_identity
    _preview_member_identity = _core._preview_member_identity
    item = _core.item
    datetime = _core.datetime
    json = _core.json
    TRANSCRIPTS_DIR = _core.TRANSCRIPTS_DIR
    _escape = _core._escape
    _format_datetime_th = _core._format_datetime_th
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    preview_member_name, preview_member_avatar = _preview_member_identity(session)
    module = sorted(state["ticket_modules"], key=lambda item: item.get("ticket_module_id", 0))[0]
    raw_history = state.get("ticket_history") or []
    history = sorted(
        raw_history,
        key=lambda item: (
            int(item.get("created_at").timestamp()) if isinstance(item.get("created_at"), datetime.datetime) else 0,
            int(item.get("id") or 0),
        ),
        reverse=True,
    )
    open_tickets = sum(1 for row in history if not row.get("closed") and not row.get("deleted"))
    closed_tickets = sum(1 for row in history if row.get("closed") and not row.get("deleted"))
    history_items = history[:30]
    total_tickets = open_tickets + closed_tickets
    tickets_enabled = bool(module.get("enabled"))
    tickets_status_label = "เปิดใช้งาน" if tickets_enabled else "ปิดใช้งาน"
    tickets_status_class = "is-on" if tickets_enabled else "is-off"

    panel_embed_data = module.get("ticket_panel_message_embed") or {}
    if isinstance(panel_embed_data, str):
        try:
            panel_embed_data = json.loads(panel_embed_data)
        except Exception:
            panel_embed_data = {}
    if not isinstance(panel_embed_data, dict):
        panel_embed_data = {}
    button_colors = {
        "green": "#25c26e",
        "blurple": "#5865f2",
        "red": "#e14343",
        "gray": "#6b7280",
    }
    panel_title = str(panel_embed_data.get("title") or "เปิดทิกเก็ตซัพพอร์ต").strip() or "เปิดทิกเก็ตซัพพอร์ต"
    panel_content = (module.get("ticket_panel_message_content") or panel_embed_data.get("description") or "กดปุ่มด้านล่างเพื่อเปิดทิกเก็ต").strip()
    panel_button_text = str(panel_embed_data.get("button_label") or panel_embed_data.get("button_text") or "Open Ticket").strip()[:45] or "Open Ticket"
    panel_button_color = str(panel_embed_data.get("button_color") or "blurple").strip().lower()
    if panel_button_color not in button_colors:
        panel_button_color = "blurple"
    panel_button_bg = button_colors.get(panel_button_color, button_colors["blurple"])
    panel_button_emoji = str(panel_embed_data.get("button_emoji") or panel_embed_data.get("emoji") or "").strip()[:64]
    panel_button_preview_text = f"{panel_button_emoji} {panel_button_text}".strip()
    panel_image_raw = panel_embed_data.get("image_url") or panel_embed_data.get("image") or panel_embed_data.get("thumbnail")
    panel_image_url = ""
    if isinstance(panel_image_raw, dict):
        panel_image_url = str(panel_image_raw.get("url") or "").strip()
    elif isinstance(panel_image_raw, str):
        panel_image_url = panel_image_raw.strip()
    close_preview = (module.get("close_ticket_message_content") or "กดปุ่มด้านล่างเพื่อปิดทิกเก็ต").strip()

    template_preview_user_name = json.dumps(str(preview_member_name or "Member"), ensure_ascii=False)
    template_preview_user_mention = json.dumps(f"@{preview_member_name}", ensure_ascii=False)
    template_preview_server_name = json.dumps(str(current_guild.get("name") or "Guild"), ensure_ascii=False)
    _preview_user_name = str(preview_member_name or "Member").strip() or "Member"
    _preview_server_name = str(current_guild.get("name") or "Guild").strip() or "Guild"
    ticket_mock_users_json = json.dumps(
        [
            {
                "id": "session",
                "label": f"{_preview_user_name} (You)",
                "name": _preview_user_name,
                "mention": f"@{_preview_user_name}",
                "avatar": str(preview_member_avatar or "https://cdn.discordapp.com/embed/avatars/0.png"),
            },
        ],
        ensure_ascii=False,
    )
    ticket_mock_servers_json = json.dumps(
        [
            {"id": "current", "label": f"{_preview_server_name} (Current)", "name": _preview_server_name},
        ],
        ensure_ascii=False,
    )

    history_rows: list[str] = []
    for row in history_items:
        ticket_id = int(row.get("ticket_id") or 0)
        creator_id = int(row.get("creator_id") or 0) if str(row.get("creator_id") or "").isdigit() else 0
        channel_id = int(row.get("channel_id") or 0) if str(row.get("channel_id") or "").isdigit() else 0
        channel_name = "-"
        if bot_guild and channel_id:
            try:
                channel_obj = bot_guild.get_channel(channel_id)
                if channel_obj:
                    channel_name = f"#{channel_obj.name}"
            except Exception:
                channel_name = "-"
        status = "ปิ" if row.get("closed") else "กำลังปิ"
        status_class = "online" if row.get("closed") else "offline"
        status_style = "" if row.get("closed") else "color:#fbbf24;background:rgba(251,191,36,.1);border-color:rgba(251,191,36,.25);"

        transcript_link = '<span class="muted">ยังไม่มี (ต้องปิดทิกเก็ตก่อน)</span>'
        if channel_id and creator_id:
            transcript_file_id = f"{current_guild['id']}-{channel_id}-{creator_id}.html"
            transcript_path = TRANSCRIPTS_DIR / transcript_file_id
            if transcript_path.exists() and transcript_path.is_file():
                transcript_link = f'<a class="ghost-btn" href="/transcripts/{_escape(transcript_file_id)}" target="_blank" rel="noopener">เปิดประวัติแชต</a>'

        history_rows.append(
            f"<tr data-ticket-id=\"{str(ticket_id).zfill(4)}\" data-ticket-status=\"{'closed' if row.get('closed') else 'open'}\">"
            f"<td>#{str(ticket_id).zfill(4)}</td>"
            f"<td><span class=\"status-pill {status_class}\" style=\"{status_style}\">{_escape(status)}</span></td>"
            f"<td>{_escape(channel_name)}</td>"
            f"<td>{_escape(f'<@{creator_id}>' if creator_id else '-')}</td>"
            f"<td>{_escape(_format_datetime_th(row.get('created_at')))}</td>"
            f"<td>{_escape(_format_datetime_th(row.get('closed_at')))}</td>"
            f"<td>{transcript_link}</td>"
            "</tr>"
        )

    if not history_rows:
        history_rows.append(
            '<tr><td colspan="7" class="muted" style="text-align:center;">ยังไม่มีประวัติทิกเก็ตในเซิร์ฟเวอร์</td></tr>'
        )

    body = _render_dashboard_f_template("tickets.html", locals())
    return _render_layout(title=f"SkylineBOT Tickets - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab=active_tab_slug, notice=notice)
