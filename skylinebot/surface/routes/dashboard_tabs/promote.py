from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_promote(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "promote",
    title_override: str | None = None,
    description_override: str | None = None,
) -> str:
    _core = core
    style_urls = _core.style_urls
    _preview_bot_identity = _core._preview_bot_identity
    _plan_display_name = _core._plan_display_name
    _is_plan_at_least = _core._is_plan_at_least
    _normalize_promote_allowed_domains = _core._normalize_promote_allowed_domains
    _normalize_promote_allowed_urls = _core._normalize_promote_allowed_urls
    _normalize_promote_blocked_words = _core._normalize_promote_blocked_words
    _promote_allowed_url_targets = _core._promote_allowed_url_targets
    _promote_blocked_url_targets = _core._promote_blocked_url_targets
    _promote_default_allowed_domains = _core._promote_default_allowed_domains
    _ownerbot_promote_policy_from_db = _core._ownerbot_promote_policy_from_db
    _promote_suspension_map_from_db = _core._promote_suspension_map_from_db
    _promote_suspension_reason = _core._promote_suspension_reason
    Any = _core.Any
    _clean_text = _core._clean_text
    PROMOTE_COOLDOWN_SECONDS = _core.PROMOTE_COOLDOWN_SECONDS
    PROMOTE_IMAGE_FLAG_CATEGORY_THRESHOLDS = _core.PROMOTE_IMAGE_FLAG_CATEGORY_THRESHOLDS
    time = _core.time
    _format_duration_th = _core._format_duration_th
    _escape = _core._escape
    _i18n = _core.i18n
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    get_bot = _core.get_bot
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    guild_language = str((state.get("guild") or {}).get("language") or "th").strip().lower()
    language = guild_language if guild_language in {"th", "en"} else "th"
    text = {
        "th": {
            "title": "ศูนย์โปรโมต",
            "desc": "ส่งข้อความโปรโมทจากหน้าเว็บเข้าคิวกระจายไปทุกกิลด์ที่เปิดระบบ",
            "status": "สถานะระบบ",
            "enabled": "เปิดใช้งานแล้ว",
            "disabled": "ยังไม่เปิดใช้งาน",
            "howto": "ต้องตั้งค่าในดิสคอร์ดด้วยคำสั่ง /promote setup ก่อนใช้งานหน้าเว็บนี้",
            "submit": "ห้องส่ง",
            "public": "ห้องสาธารณะ",
            "cooldown": "คูลดาวน์",
            "hours": "ชั่วโมง",
            "content": "ข้อความโปรโมต",
            "attachments": "ลิงก์ไฟล์แนบ (คั่นด้วย ,)",
            "upload_image": "อัปโหลดรูปภาพ (พรีเมียม)",
            "invite": "ลิงก์เชิญเซิร์ฟเวอร์ (ถ้ามี)",
            "send": "ส่งเข้าโปรโมต",
        },
        "en": {
            "title": "Promote Hub",
            "desc": "Send promote messages from web to the global relay queue",
            "status": "System Status",
            "enabled": "Enabled",
            "disabled": "Disabled",
            "howto": "You must configure /promote setup in Discord before using this page",
            "submit": "Submit Channel",
            "public": "Public Channel",
            "cooldown": "Cooldown",
            "hours": "hours",
            "content": "Promote Content",
            "attachments": "Attachment URLs (comma separated)",
            "upload_image": "Image Upload (Premium)",
            "invite": "Server Invite URL (optional)",
            "send": "Send to Promote Queue",
        },
    }[language]
    promote = state.get("promote") or {}
    owner_policy = _ownerbot_promote_policy_from_db()
    allowed_domains_custom = _normalize_promote_allowed_domains(owner_policy.get("allowed_domains"))
    allowed_urls_custom = _normalize_promote_allowed_urls(owner_policy.get("allowed_urls"))
    allowed_domains_effective, allowed_urls_effective = _promote_allowed_url_targets(
        allowed_domains_custom,
        allowed_urls_custom,
    )
    blocked_words_custom = _normalize_promote_blocked_words(owner_policy.get("blocked_words"))
    blocked_domains_custom = _normalize_promote_allowed_domains(owner_policy.get("blocked_domains"))
    blocked_urls_custom = _normalize_promote_allowed_urls(owner_policy.get("blocked_urls"))
    blocked_domains_effective, blocked_urls_effective = _promote_blocked_url_targets(
        blocked_domains_custom,
        blocked_urls_custom,
    )
    allowed_domains_display = ", ".join(allowed_domains_effective) if allowed_domains_effective else "-"
    allowed_urls_display = ", ".join(allowed_urls_effective[:8]) if allowed_urls_effective else "-"
    blocked_domains_display = ", ".join(blocked_domains_effective[:8]) if blocked_domains_effective else "-"
    blocked_urls_display = ", ".join(blocked_urls_effective[:8]) if blocked_urls_effective else "-"
    default_allowed_domains_text = ", ".join(_promote_default_allowed_domains())
    safety_allowed_domains_display = ", ".join(allowed_domains_effective[:20]) if allowed_domains_effective else "-"
    safety_allowed_urls_display = ", ".join(allowed_urls_effective[:20]) if allowed_urls_effective else "-"
    safety_blocked_domains_display = ", ".join(blocked_domains_effective[:20]) if blocked_domains_effective else "-"
    safety_blocked_urls_display = ", ".join(blocked_urls_effective[:20]) if blocked_urls_effective else "-"
    safety_blocked_words_display = ", ".join(blocked_words_custom[:30]) if blocked_words_custom else "-"
    safety_hard_block_words_display = ", ".join(_core.PROMOTE_HARD_BLOCK_WORDS[:20]) if _core.PROMOTE_HARD_BLOCK_WORDS else "-"
    safety_image_thresholds_display = ", ".join(
        f"{key} >= {value:.2f}"
        for key, value in PROMOTE_IMAGE_FLAG_CATEGORY_THRESHOLDS.items()
    ) if PROMOTE_IMAGE_FLAG_CATEGORY_THRESHOLDS else "-"
    allowed_url_help = (
        f"Allowed domains: {allowed_domains_display}"
        + (f" | Allowed URL prefixes: {allowed_urls_display}" if allowed_urls_effective else "")
    )
    guild_state = state.get("guild") or {}
    promote_suspension_map = _promote_suspension_map_from_db()
    promote_suspend_reason = _promote_suspension_reason(int(current_guild.get("id") or 0), promote_suspension_map)
    promote_is_suspended = bool(promote_suspend_reason)
    promote_suspension_markup = (
        f'<div class="notice" style="margin-top:10px;">{_escape(promote_suspend_reason)}</div>'
        if promote_is_suspended
        else ""
    )
    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)
    can_use_rich_media = _is_plan_at_least(plan_tier, "silver")
    saved_limit_map = {"free": 0, "silver": 1, "golden": 2, "diamond": 5, "permanent": 8}
    saved_limit = int(saved_limit_map.get(plan_tier, 0))
    raw_saved = promote.get("saved_messages") if isinstance(promote.get("saved_messages"), list) else []
    saved_messages: list[dict[str, Any]] = []
    for row in raw_saved:
        if not isinstance(row, dict):
            continue
        try:
            row_id = int(row.get("id"))
        except Exception:
            continue
        attachments_list = row.get("attachments")
        if not isinstance(attachments_list, list):
            attachments_list = []
        saved_messages.append(
            {
                "id": row_id,
                "name": _clean_text(row.get("name") or f"บันทึก #{row_id}")[:80].strip() or f"บันทึก #{row_id}",
                "content": _clean_text(row.get("content") or "")[:1800],
                "attachments": [str(item).strip() for item in attachments_list if str(item).strip()][:5],
                "invite_url": _clean_text(row.get("invite_url") or "").strip(),
            }
        )
    saved_messages.sort(key=lambda item: int(item.get("id") or 0))
    is_configured = bool(promote.get("submit_channel_id") and promote.get("public_channel_id"))
    promote_switch_enabled = bool(promote.get("enabled", True))
    enabled = bool(is_configured and promote_switch_enabled)
    cooldown_seconds = int(promote.get("cooldown_seconds") or PROMOTE_COOLDOWN_SECONDS or 43200)
    cooldown_hours = max(1, round(cooldown_seconds / 3600))
    user_id = str(((session.get("user") or {}).get("id") or "")).strip()
    session_user = session.get("user") or {}
    preview_sender_name = _clean_text(
        session_user.get("username")
        or session_user.get("global_name")
        or f"user {user_id or 'unknown'}"
    ).strip() or "Unknown"
    preview_sender_label = (
        f"{preview_sender_name} (`{user_id}`)"
        if user_id
        else preview_sender_name
    )
    preview_source_name = _clean_text(current_guild.get("name") or "").strip() or f"Guild {current_guild.get('id')}"
    preview_embed_title = _i18n.tr("promote_broadcast_title", current_guild.get("id"))
    preview_embed_from_label = _i18n.tr("promote_broadcast_from", current_guild.get("id"))
    preview_embed_author_label = _i18n.tr("promote_broadcast_author", current_guild.get("id"))
    preview_embed_attachments_label = _i18n.tr("promote_broadcast_attachments", current_guild.get("id"))
    preview_embed_footer = _i18n.tr("promote_broadcast_footer", current_guild.get("id"))
    preview_btn_open_server = _i18n.tr("promote_btn_open_server", current_guild.get("id"))
    preview_btn_copy_invite = _i18n.tr("promote_btn_copy_invite", current_guild.get("id"))
    preview_btn_invite_bot = _i18n.tr("promote_btn_invite_bot", current_guild.get("id"))
    preview_btn_support = _i18n.tr("promote_btn_support", current_guild.get("id"))
    preview_btn_vote = _i18n.tr("promote_btn_vote", current_guild.get("id"))
    preview_bot_invite_url = _clean_text(getattr(style_urls, "INVITE", "")).strip() or "#"
    preview_support_url = _clean_text(getattr(style_urls, "SUPPORT_SERVER", "")).strip() or "#"
    preview_vote_url = _clean_text(getattr(style_urls, "VOTE", "")).strip() or "#"
    preview_auto_invite_possible = False
    try:
        submit_channel_id = int(promote.get("submit_channel_id") or 0)
        submit_channel = bot_guild.get_channel(submit_channel_id) if bot_guild and submit_channel_id > 0 else None
        me = getattr(bot_guild, "me", None) if bot_guild else None
        if submit_channel and me and submit_channel.permissions_for(me).create_instant_invite:
            preview_auto_invite_possible = True
    except Exception:
        preview_auto_invite_possible = False
    cooldowns = dict(promote.get("cooldowns") or {})
    now_ts = int(time.time())
    last_post = int(cooldowns.get(user_id, 0) or 0) if user_id else 0
    cooldown_remaining = max(0, cooldown_seconds - max(0, now_ts - last_post))
    can_send = enabled and cooldown_remaining == 0
    if promote_is_suspended:
        submit_btn_label = "ระงับการใช้งาน Promote"
        can_send = False
    elif not enabled:
        submit_btn_label = "ยังไม่เปิดใช้งาน"
    elif cooldown_remaining > 0:
        submit_btn_label = f"ส่งได้ในอีก {_format_duration_th(cooldown_remaining)}"
    else:
        submit_btn_label = text["send"]
    title_text = title_override or text["title"]
    desc_text = description_override or text["desc"]
    save_disabled = (not enabled) or (saved_limit <= 0) or (len(saved_messages) >= saved_limit)
    rich_media_note = (
        "แพ็กเกจนี้รองรับลิงก์และรูปภาพโปรโมต"
        if can_use_rich_media
        else "แพ็กเกจ Free จะส่งได้เฉพาะข้อความ (ห้ามลิงก์และรูปภาพ)"
    )

    promote_queue_total = 0
    promote_queue_guild_total = 0
    promote_queue_pending = 0
    promote_queue_rows_markup = '<div class="muted">ยังไม่มีคิวโปรโมต</div>'
    promote_queue_guild_rows_markup = '<div class="muted">ยังไม่มีกิลด์ในคิว</div>'
    try:
        bot = get_bot()
        promote_cog = bot.get_cog("message") if bot else None
        if promote_cog and hasattr(promote_cog, "get_promote_queue_snapshot"):
            snapshot = promote_cog.get_promote_queue_snapshot(limit=40) or {}
            promote_queue_total = max(0, int(snapshot.get("total_jobs") or 0))
            promote_queue_guild_total = max(0, int(snapshot.get("unique_guilds") or 0))
            promote_queue_pending = max(0, int(snapshot.get("pending_keys") or 0))

            queue_rows = snapshot.get("queue_rows") if isinstance(snapshot.get("queue_rows"), list) else []
            guild_rows = snapshot.get("guild_rows") if isinstance(snapshot.get("guild_rows"), list) else []

            queue_html_rows: list[str] = []
            for row in queue_rows[:25]:
                queue_html_rows.append(
                    f"""
                    <div class="panel-sub" style="margin-top:8px;">
                      <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;">
                        <strong>#{int(row.get('position') or 0)} • {_escape(row.get('guild_name') or 'Unknown Guild')}</strong>
                        <span class="pill">Guild ID: {_escape(str(row.get('guild_id') or '-'))}</span>
                      </div>
                      <div class="muted" style="margin-top:6px;">ผู้ส่ง: {_escape(row.get('author') or 'Unknown')}</div>
                      <div style="margin-top:6px;white-space:pre-wrap;word-break:break-word;">{_escape(row.get('content_preview') or '-')}</div>
                    </div>
                    """
                )
            if queue_html_rows:
                promote_queue_rows_markup = "".join(queue_html_rows)

            guild_html_rows: list[str] = []
            for index, row in enumerate(guild_rows[:20], start=1):
                guild_html_rows.append(
                    f"""
                    <div class="panel-sub" style="margin-top:8px;display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;">
                      <strong>{index}. {_escape(row.get('guild_name') or 'Unknown Guild')}</strong>
                      <span class="pill">{int(row.get('count') or 0)} คิว</span>
                    </div>
                    """
                )
            if guild_html_rows:
                promote_queue_guild_rows_markup = "".join(guild_html_rows)
        elif promote_cog and hasattr(promote_cog, "promote_queue"):
            promote_queue_total = max(0, int(getattr(promote_cog.promote_queue, "qsize", lambda: 0)() or 0))
    except Exception:
        pass

    saved_rows_html: list[str] = []
    for item in saved_messages:
        attachments_joined = ", ".join(item.get("attachments") or [])
        saved_rows_html.append(
            f"""
            <form method="post" action="/dashboard/guild/{current_guild['id']}/promote/send" class="panel-sub" style="margin-top:10px;" enctype="multipart/form-data">
              <input type="hidden" name="redirect_tab" value="{_escape(active_tab_slug)}">
              <input type="hidden" name="template_id" value="{int(item.get('id') or 0)}">
              <div class="field-group">
                <div class="field-item">
                  <label>ชื่อบันทึก</label>
                  <input type="text" name="template_name" value="{_escape(item.get('name') or '')}" maxlength="80">
                </div>
                <div class="field-item">
                  <label>ID</label>
                  <input type="text" value="{int(item.get('id') or 0)}" disabled>
                </div>
                <div class="field-item" style="grid-column:1/-1;">
                  <label>{text['content']}</label>
                  <textarea name="content">{_escape(item.get('content') or '')}</textarea>
                </div>
                <div class="field-item">
                  <label>{text['attachments']}</label>
                  <input type="text" name="attachments" value="{_escape(attachments_joined)}" {'disabled' if not can_use_rich_media else ''}>
                </div>
                <div class="field-item">
                  <label>{text['invite']}</label>
                  <input type="text" name="custom_invite_url" value="{_escape(item.get('invite_url') or '')}" {'disabled' if not can_use_rich_media else ''}>
                </div>
              </div>
              <div class="form-actions-inline">
                <button class="primary-btn" type="submit" name="action" value="update_saved">บันทึกการแก้ไข</button>
                <button class="primary-btn" type="submit" name="action" value="send_saved">ส่งรายการนี้</button>
                <button class="danger-btn" type="submit" name="action" value="delete_saved">ลบ</button>
              </div>
            </form>
            """
        )
    saved_rows_markup = "".join(saved_rows_html) if saved_rows_html else '<div class="muted">ยังไม่มีรายการที่บันทึกไว้</div>'

    body = _render_dashboard_f_template("promote.html", locals())
    return _render_layout(title=f"SkylineBOT Promote - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab=active_tab_slug, notice=notice)

