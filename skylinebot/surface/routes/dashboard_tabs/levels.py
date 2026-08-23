from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_levels(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "levels",
) -> str:
    _core = core
    _plan_display_name = _core._plan_display_name
    _levels_plan_caps = _core._levels_plan_caps
    _preview_bot_identity = _core._preview_bot_identity
    _preview_member_identity = _core._preview_member_identity
    _levels_settings_from_db = _core._levels_settings_from_db
    json = _core.json
    _escape = _core._escape
    SUBSCRIBE_PLAN_PATH = _core.SUBSCRIBE_PLAN_PATH
    _render_channel_select = _core._render_channel_select
    _render_role_select = _core._render_role_select
    style_urls = _core.style_urls
    Any = _core.Any
    item = _core.item
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    guild_state = state.get("guild") or {}
    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)
    caps = _levels_plan_caps(plan_tier)
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    preview_member_name, preview_member_avatar = _preview_member_identity(session)

    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value if value is not None else default)
        except Exception:
            return int(default)

    settings = _levels_settings_from_db(int(current_guild["id"]))

    settings["enabled"] = bool(settings.get("enabled")) and bool(caps.get("can_use"))
    settings["max_level"] = min(int(settings.get("max_level") or 120), int(caps.get("max_level") or 120))
    settings["notify_send_text"] = bool(settings.get("notify_send_text", True))
    settings["notify_send_embed"] = bool(settings.get("notify_send_embed", False))
    settings["notify_send_image"] = bool(settings.get("notify_send_image", False))
    settings["notify_embed_title"] = str(settings.get("notify_embed_title") or "Level up!").strip()[:200]
    settings["notify_embed_description"] = str(
        settings.get("notify_embed_description") or "{user.mention} reached level {level} (XP {xp})"
    ).strip()[:900]
    settings["notify_image_theme"] = str(settings.get("notify_image_theme") or "music").strip().lower()
    settings["notify_image_theme_url"] = str(settings.get("notify_image_theme_url") or "").strip()
    settings["notify_image_layout_mode"] = str(settings.get("notify_image_layout_mode") or "center_stack").strip().lower()
    settings["notify_image_avatar_position"] = str(settings.get("notify_image_avatar_position") or "center").strip().lower()
    settings["notify_image_text_align"] = str(settings.get("notify_image_text_align") or "center").strip().lower()
    settings["notify_image_font_style"] = str(settings.get("notify_image_font_style") or "classic").strip().lower()
    settings["notify_image_top_text"] = str(settings.get("notify_image_top_text") or "{user}").strip()[:240]
    settings["notify_image_bottom_text"] = str(settings.get("notify_image_bottom_text") or "Level {level}").strip()[:260]
    level_preview_message = str(settings.get("notify_message") or "🎉 {user} อัปเลเวลเป็น {level} (XP {xp})").strip()
    level_preview_embed_title = str(settings.get("notify_embed_title") or "Level up!").strip()
    level_preview_embed_description = str(
        settings.get("notify_embed_description") or "{user.mention} reached level {level} (XP {xp})"
    ).strip()
    template_preview_user = json.dumps(f"@{preview_member_name}", ensure_ascii=False)
    template_preview_guild = json.dumps(str(current_guild.get("name") or "Guild"), ensure_ascii=False)
    _preview_user_name = str(preview_member_name or "Member").strip() or "Member"
    _preview_server_name = str(current_guild.get("name") or "Guild").strip() or "Guild"
    _preview_server_icon = str(
        getattr(getattr(bot_guild, "icon", None), "url", "")
        or current_guild.get("icon")
        or "https://cdn.discordapp.com/embed/avatars/0.png"
    ).strip()
    levels_mock_users_json = json.dumps(
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
    levels_mock_servers_json = json.dumps(
        [
            {
                "id": "current",
                "label": f"{_preview_server_name} (Current)",
                "name": _preview_server_name,
                "icon": _preview_server_icon,
            },
        ],
        ensure_ascii=False,
    )
    level_image_theme_presets_json = json.dumps(
        style_urls.get_theme_presets(
            user_url=str(preview_member_avatar or "https://cdn.discordapp.com/embed/avatars/0.png"),
            guild_url=_preview_server_icon,
            include_extended=False,
        ),
        ensure_ascii=False,
    )
    source_caps = settings.get("sources") if isinstance(settings.get("sources"), dict) else {}
    normalized_sources = {
        "text": bool(source_caps.get("text")) and bool(caps.get("text_xp")),
        "voice": bool(source_caps.get("voice")) and bool(caps.get("voice_xp")),
        "command": bool(source_caps.get("command")) and bool(caps.get("command_xp")),
        "reaction": bool(source_caps.get("reaction")) and bool(caps.get("reaction_xp")),
    }
    settings["sources"] = normalized_sources
    rewards = settings.get("reward_roles") if isinstance(settings.get("reward_roles"), list) else []
    max_rewards = int(caps.get("max_rewards") or 0)
    if max_rewards > 0:
        rewards = rewards[:max_rewards]
    else:
        rewards = []
    settings["reward_roles"] = rewards

    lock_free = not bool(caps.get("can_use"))
    disabled_attr = "disabled" if lock_free else ""
    premium_notice_html = (
        '<div class="panel-sub" style="border:1px solid rgba(239,68,68,.45);background:rgba(127,29,29,.2);">'
        '<strong style="display:block;color:#fecaca;">แพ็ก Free ไม่สามารถใช้งานระบบเลเวลได้</strong>'
        '<p class="muted" style="margin:.45rem 0 0;">อัปเกรดเป็น Silver / Gole / Diamond / Permanent เพื่อเปิดใช้งานระบบเลเวล</p>'
        f'<div style="margin-top:10px;"><a class="primary-btn" href="{_escape(SUBSCRIBE_PLAN_PATH)}">อัปเกรดแพ็กเกจ</a></div>'
        "</div>"
    )
    notify_channel_select = _render_channel_select(
        "notify_channel_id",
        bot_guild,
        settings.get("notify_channel_id"),
        placeholder="เลือกช่องแจ้งเตือน...",
        filter_types=["text", "news", "forum"],
    )
    if lock_free:
        notify_channel_select = notify_channel_select.replace("<select ", "<select disabled ", 1)

    def _role_select(name: str, current_id: Any) -> str:
        html_select = _render_role_select(name, bot_guild, current_id, placeholder="เลือกยศ...")
        if lock_free:
            html_select = html_select.replace("<select ", "<select disabled ", 1)
        return html_select

    reward_rows_count = max(max_rewards, 3) if max_rewards > 0 else 3
    reward_rows: list[str] = []
    for index in range(reward_rows_count):
        row = rewards[index] if index < len(rewards) and isinstance(rewards[index], dict) else {}
        level_value = int(row.get("level") or (index + 1) * 10)
        role_value = str(row.get("role_id") or "")
        reward_rows.append(
            f"""
            <div class="field-group" style="grid-template-columns:160px minmax(180px,1fr);margin-bottom:8px;">
              <div class="field-item">
                <label>เลเวล #{index + 1}</label>
                <input type="number" name="reward_level_{index}" value="{level_value}" min="1" max="1000" {disabled_attr}>
              </div>
              <div class="field-item">
                <label>บทบาทที่ได้รับ</label>
                {_role_select(f"reward_role_id_{index}", role_value)}
              </div>
            </div>
            """
        )

    source_blocks = [
        ("text", "เลเวลการพิมพ์", "ได้ XP จากข้อความ"),
        ("voice", "เลเวลการเข้าห้องเสียง", "ได้ XP จากการใช้งาน Voice"),
        ("command", "เลเวลการใช้งานบอท", "ได้ XP เมื่อใช้คำสั่งบอท"),
        ("reaction", "เลเวลจากรีแอ็กชัน", "ได้ XP จากรีแอ็กชัน (Diamond)"),
    ]
    source_toggles_html = "".join(
        f"""
        <label class="ux-toggle" style="justify-content:space-between;">
          <span class="ux-toggle-label">{_escape(label)} <span class="muted" style="margin-left:6px;">{_escape(desc)}</span></span>
          <input type="checkbox" name="source_{_escape(key)}" {'checked' if settings['sources'].get(key) else ''} {'disabled' if (lock_free or not caps.get(f'{key}_xp')) else ''}>
          <span class="ux-switch"></span>
        </label>
        """
        for key, label, desc in source_blocks
    )

    levels_rows = state.get("levels_users") if isinstance(state.get("levels_users"), list) else []
    cleaned_levels: list[dict[str, Any]] = []
    for row in levels_rows:
        if isinstance(row, dict):
            cleaned_levels.append(row)
    cleaned_levels.sort(key=lambda item: int(item.get("total_xp") or 0), reverse=True)

    rank_entries: list[dict[str, Any]] = []
    for index, row in enumerate(cleaned_levels[:500], start=1):
        user_id = _safe_int(row.get("user_id"), 0)
        if user_id <= 0:
            continue
        member = bot_guild.get_member(user_id) if bot_guild else None
        display_name = str(getattr(member, "display_name", "") or f"User {user_id}")
        tag_name = str(member) if member else f"User {user_id}"
        avatar_url = str(getattr(getattr(member, "display_avatar", None), "url", "") or "https://cdn.discordapp.com/embed/avatars/0.png")
        level_value = _safe_int(row.get("level"), 0)
        total_xp = _safe_int(row.get("total_xp"), 0)
        rank_entries.append(
            {
                "user_id": str(user_id),
                "rank": index,
                "name": display_name,
                "tag": tag_name,
                "avatar": avatar_url,
                "level": level_value,
                "xp": total_xp,
            }
        )

    session_user_id = str(((session.get("user") or {}).get("id") or "")).strip()
    initial_rank = rank_entries[0] if rank_entries else {}
    if session_user_id:
        found_rank = next((entry for entry in rank_entries if str(entry.get("user_id")) == session_user_id), None)
        if found_rank:
            initial_rank = found_rank

    rank_select_options = "".join(
        f'<option value="{_escape(str(entry.get("user_id")))}" {"selected" if str(entry.get("user_id")) == str(initial_rank.get("user_id", "")) else ""}>'
        f'#{int(entry.get("rank") or 0)} {_escape(str(entry.get("name") or "Unknown"))} (Lv.{int(entry.get("level") or 0)} / {int(entry.get("xp") or 0):,} XP)'
        "</option>"
        for entry in rank_entries[:300]
    )
    if not rank_select_options:
        rank_select_options = '<option value="">ยังไม่มีข้อมูลเลเวล</option>'
    reset_target_options = "".join(
        f'<option value="{_escape(str(entry.get("user_id") or ""))}" '
        f'data-search="{_escape((str(entry.get("name") or "") + " " + str(entry.get("tag") or "") + " " + str(entry.get("user_id") or "")).lower())}" '
        f'{"selected" if str(entry.get("user_id")) == str(initial_rank.get("user_id", "")) else ""}>'
        f'#{int(entry.get("rank") or 0)} {_escape(str(entry.get("name") or "Unknown"))} (Lv.{int(entry.get("level") or 0)} / {int(entry.get("xp") or 0):,} XP)'
        "</option>"
        for entry in rank_entries[:500]
    )
    if not reset_target_options:
        reset_target_options = '<option value="">ยังไม่มีข้อมูลเลเวล</option>'
    reset_disabled_attr = "disabled" if (lock_free or not rank_entries) else ""

    def _xp_needed_for_level(level: int) -> int:
        value = 80 + int((level ** 2) * 35)
        return max(100, value)

    initial_level = _safe_int(initial_rank.get("level"), 0)
    initial_total_xp = _safe_int(initial_rank.get("xp"), 0)
    current_floor_xp = _xp_needed_for_level(initial_level) if initial_level > 0 else 0
    next_level_xp = _xp_needed_for_level(initial_level + 1)
    progress_span = max(1, next_level_xp - current_floor_xp)
    progress_value = max(0, initial_total_xp - current_floor_xp)
    progress_percent = max(0.0, min(100.0, (progress_value / progress_span) * 100.0))
    rank_json = json.dumps(rank_entries, ensure_ascii=False)

    rank_card_html = _render_dashboard_f_template("levels_rank_card.html", locals())

    body = _render_dashboard_f_template("levels.html", locals())
    return _render_layout(
        title=f"SkylineBOT Levels - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
