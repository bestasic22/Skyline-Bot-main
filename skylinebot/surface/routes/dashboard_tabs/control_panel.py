from __future__ import annotations

from typing import Any

from .. import dashboard_core as core


def _render_control_panel(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "control_panel",
) -> str:
    _core = core
    _dashboard_audit_entries_from_db = _core._dashboard_audit_entries_from_db
    _discord_default_avatar_url = _core._discord_default_avatar_url
    _with_cache_bust = _core._with_cache_bust
    _escape = _core._escape
    _format_audit_timestamp_th = _core._format_audit_timestamp_th
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    guild_state = state.get("guild") or {}
    audit_rows = _dashboard_audit_entries_from_db(int(current_guild["id"]))[:300]
    total_audit_count = len(audit_rows)
    latest_audit_action = _escape(str(audit_rows[0].get("action") or "-")) if audit_rows else "ยังไม่มีประวัติล่าสุด"
    prefix_text = _escape(str(guild_state.get("prefix") or _core.BOT_CONFIG.PREFIX))

    bot_instance: Any | None = None
    bot_guild: Any | None = None
    try:
        bot_instance = _core.get_bot()
    except Exception:
        bot_instance = None
    if bot_instance is not None:
        try:
            bot_guild = bot_instance.get_guild(int(current_guild["id"]))
        except Exception:
            bot_guild = None

    user_cache: dict[str, Any | None] = {}
    control_rows_html: list[str] = []
    for row in audit_rows:
        user_name_raw = str(row.get("user_name") or "unknown").strip() or "unknown"
        user_id_raw = str(row.get("user_id") or "").strip()
        action = _escape(str(row.get("action") or "-"))
        target = _escape(str(row.get("target") or "-"))

        user_obj = None
        if user_id_raw.isdigit():
            if user_id_raw in user_cache:
                user_obj = user_cache.get(user_id_raw)
            else:
                if bot_guild is not None:
                    try:
                        user_obj = bot_guild.get_member(int(user_id_raw))
                    except Exception:
                        user_obj = None
                if user_obj is None and bot_instance is not None:
                    try:
                        user_obj = bot_instance.get_user(int(user_id_raw))
                    except Exception:
                        user_obj = None
                user_cache[user_id_raw] = user_obj

        if user_obj is not None:
            try:
                user_name_raw = str(
                    getattr(user_obj, "display_name", "")
                    or getattr(user_obj, "global_name", "")
                    or getattr(user_obj, "name", "")
                    or user_name_raw
                ).strip() or user_name_raw
            except Exception:
                pass

        actor_kind = "system"
        actor_label = "System"
        if user_obj is not None:
            try:
                is_bot_user = bool(getattr(user_obj, "bot", False))
            except Exception:
                is_bot_user = False
            actor_kind = "bot" if is_bot_user else "admin"
            actor_label = "Bot" if is_bot_user else "Admin"
        else:
            user_name_lower = user_name_raw.lower()
            if (
                not user_id_raw
                and (
                    user_name_lower in {"-", "unknown", "system"}
                    or "system" in user_name_lower
                    or "automation" in user_name_lower
                    or "ระบบ" in user_name_raw
                )
            ):
                actor_kind = "system"
                actor_label = "System"
            elif "bot" in user_name_lower:
                actor_kind = "bot"
                actor_label = "Bot"
            else:
                actor_kind = "admin"
                actor_label = "Admin"

        user_name = _escape(user_name_raw)
        user_id = _escape(user_id_raw or "-")
        actor_label_html = _escape(actor_label)
        actor_badge_class = _escape(f"control-audit-actor-badge-{actor_kind}")

        avatar_fallback_raw = _discord_default_avatar_url(user_id_raw or user_name_raw or "0")
        avatar_url_raw = ""
        if user_obj is not None:
            try:
                avatar_url_raw = str(getattr(getattr(user_obj, "display_avatar", None), "url", "") or "").strip()
            except Exception:
                avatar_url_raw = ""
        if not avatar_url_raw:
            avatar_url_raw = str(row.get("avatar_url") or "").strip()
        if not avatar_url_raw:
            avatar_url_raw = avatar_fallback_raw
        avatar_url_raw = _with_cache_bust(avatar_url_raw, bucket_seconds=180)
        avatar_fallback_raw = _with_cache_bust(avatar_fallback_raw, bucket_seconds=180)

        user_avatar = _escape(avatar_url_raw)
        avatar_fallback = _escape(avatar_fallback_raw)
        data_user = _escape(f"{actor_label.lower()} {user_name_raw.lower()} {user_id_raw}".strip())
        data_action = _escape(str(row.get("action") or "").lower())
        data_target = _escape(str(row.get("target") or "").lower())
        event_time = _escape(_format_audit_timestamp_th(row.get("ts")))
        control_rows_html.append(
            f"""
            <tr class="control-audit-row" data-control-row data-user="{data_user}" data-action="{data_action}" data-target="{data_target}">
              <td style="min-width:240px;">
                <div class="control-audit-user">
                  <img src="{user_avatar}" alt="avatar" onerror="this.onerror=null;this.src='{avatar_fallback}';">
                  <div class="control-audit-user-copy">
                    <div class="control-audit-user-head">
                      <span class="control-audit-actor-badge {actor_badge_class}">{actor_label_html}</span>
                      <div class="control-audit-user-name">{user_name}</div>
                    </div>
                    <div class="muted control-audit-user-id">{user_id}</div>
                  </div>
                </div>
              </td>
              <td><span class="control-audit-action">{action}</span></td>
              <td><span class="control-audit-target">{target}</span></td>
              <td><span class="control-audit-time">{event_time}</span></td>
            </tr>
            """
        )

    body = _render_dashboard_f_template("control_panel.html", locals())
    return _render_layout(
        title=f"SkylineBOT Control Panel - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
