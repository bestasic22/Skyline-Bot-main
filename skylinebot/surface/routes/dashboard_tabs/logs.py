from __future__ import annotations

from typing import Any

from .. import dashboard_core as core


def _render_logs(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any | None,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "logs",
) -> str:
    _core = core
    _parse_moderation_log_rows = _core._parse_moderation_log_rows
    _recent_logs = _core._recent_logs
    _escape = _core._escape
    _discord_default_avatar_url = _core._discord_default_avatar_url
    _with_cache_bust = _core._with_cache_bust
    _format_audit_timestamp_th = _core._format_audit_timestamp_th
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    rows_from_state = state.get("live_moderation_audit_rows") if isinstance(state.get("live_moderation_audit_rows"), list) else []
    rows = rows_from_state[:300] if rows_from_state else _parse_moderation_log_rows(_recent_logs())
    action_counts = {"all": len(rows), "ban": 0, "mute": 0, "warn": 0}
    rows_html: list[str] = []
    user_cache: dict[str, Any | None] = {}
    bot_instance: Any | None = None
    try:
        bot_instance = _core.get_bot()
    except Exception:
        bot_instance = None

    for row in rows:
        action_key_raw = str(row.get("action_key") or "").strip().lower()
        action_key = action_key_raw if action_key_raw in {"ban", "mute", "warn"} else "all"
        if action_key in {"ban", "mute", "warn"}:
            action_counts[action_key] += 1

        member_raw = str(row.get("member") or "-").strip()
        member_id = member_raw if member_raw.isdigit() else ""
        member_obj = None
        if member_id:
            if member_id in user_cache:
                member_obj = user_cache.get(member_id)
            else:
                if bot_guild:
                    try:
                        member_obj = bot_guild.get_member(int(member_id))
                    except Exception:
                        member_obj = None
                if member_obj is None and bot_instance is not None:
                    try:
                        member_obj = bot_instance.get_user(int(member_id))
                    except Exception:
                        member_obj = None
                user_cache[member_id] = member_obj

        member_display_raw = str(row.get("member_name") or "").strip()
        if member_obj is not None:
            try:
                member_display_raw = (
                    member_display_raw
                    or str(getattr(member_obj, "display_name", "") or getattr(member_obj, "name", "")).strip()
                )
            except Exception:
                pass
        if not member_display_raw:
            member_display_raw = member_id or member_raw or "-"

        member_sub_raw = member_id or "-"
        action_raw = str(row.get("action") or "-").strip()
        responsible_raw = str(row.get("responsible") or "-").strip() or "-"
        responsible_id_raw = str(row.get("responsible_id") or "").strip()
        responsible_is_bot = row.get("responsible_is_bot")
        if responsible_is_bot is True and not responsible_raw.lower().startswith("bot:"):
            responsible_raw = f"Bot: {responsible_raw}"
        elif responsible_is_bot is False and not responsible_raw.lower().startswith("admin:"):
            responsible_raw = f"Admin: {responsible_raw}"
        if responsible_id_raw and responsible_id_raw not in responsible_raw:
            responsible_raw = f"{responsible_raw} ({responsible_id_raw})"

        responsible_lower = responsible_raw.lower()
        actor_kind = "system"
        actor_display_raw = responsible_raw
        actor_prefix_map = {
            "admin:": "admin",
            "bot:": "bot",
            "system:": "system",
        }
        for prefix, mapped_kind in actor_prefix_map.items():
            if responsible_lower.startswith(prefix):
                actor_kind = mapped_kind
                actor_display_raw = responsible_raw[len(prefix):].strip() or "-"
                break
        else:
            if responsible_is_bot is True:
                actor_kind = "bot"
            elif responsible_is_bot is False:
                actor_kind = "admin"
            elif "ระบบอัตโนมัติ" in responsible_raw or "system" in responsible_lower or responsible_raw in {"-", "unknown"}:
                actor_kind = "system"
            else:
                actor_kind = "admin"
        actor_label = {"admin": "Admin", "bot": "Bot", "system": "System"}.get(actor_kind, "System")
        actor_badge_class = f"audit-actor-badge-{actor_kind}"
        member_search = _escape(f"{member_display_raw} {member_sub_raw} {responsible_raw} {action_raw}".lower().strip())

        avatar_url_raw = str(row.get("member_avatar_url") or "").strip()
        if not avatar_url_raw and member_obj is not None:
            try:
                avatar_url_raw = str(getattr(getattr(member_obj, "display_avatar", None), "url", "") or "").strip()
            except Exception:
                avatar_url_raw = ""
        avatar_fallback_raw = _discord_default_avatar_url(member_id or member_raw or "0")
        if not avatar_url_raw:
            avatar_url_raw = avatar_fallback_raw
        avatar_url_raw = _with_cache_bust(avatar_url_raw, bucket_seconds=180)
        avatar_fallback_raw = _with_cache_bust(avatar_fallback_raw, bucket_seconds=180)

        member_display = _escape(member_display_raw)
        member_sub = _escape(member_sub_raw)
        avatar_url = _escape(avatar_url_raw)
        avatar_fallback = _escape(avatar_fallback_raw)

        action = _escape(action_raw or "-")
        responsible = _escape(actor_display_raw or "-")
        actor_badge = _escape(actor_label)
        actor_kind_class = _escape(actor_badge_class)
        punish_time = _escape(str(row.get("punish_time") or "-"))
        remaining = _escape(str(row.get("remaining") or "-"))
        punished_at_raw = str(row.get("punished_at") or "").strip()
        if not punished_at_raw:
            ts_value = int(row.get("ts") or 0)
            if ts_value > 0:
                punished_at_raw = _format_audit_timestamp_th(ts_value)
        punished_at = _escape(punished_at_raw or "-")

        rows_html.append(
            f"""
            <tr class="audit-row audit-row-{action_key}" data-action="{action_key}" data-member="{member_search}">
              <td>
                <div class="audit-member-wrap">
                  <img class="audit-member-avatar" src="{avatar_url}" alt="{member_display}" onerror="this.onerror=null;this.src='{avatar_fallback}';">
                  <div class="audit-member-copy">
                    <span class="audit-member-name">{member_display}</span>
                    <span class="audit-member-id">{member_sub}</span>
                  </div>
                </div>
              </td>
              <td><span class="audit-action-badge audit-action-{action_key}">{action}</span></td>
              <td>
                <span class="audit-meta-value audit-actor-value">
                  <span class="audit-actor-badge {actor_kind_class}">{actor_badge}</span>
                  <span class="audit-actor-name">{responsible}</span>
                </span>
              </td>
              <td><span class="audit-meta-value">{punish_time}</span></td>
              <td><span class="audit-meta-value">{remaining}</span></td>
              <td><span class="audit-meta-value">{punished_at}</span></td>
            </tr>
            """
        )

    latest_action_label = _escape(str(rows[0].get("action") or "-")) if rows else "ยังไม่มีเหตุการณ์ล่าสุด"

    body = _render_dashboard_f_template("logs.html", locals())
    return _render_layout(
        title=f"SkylineBOT Logs - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
