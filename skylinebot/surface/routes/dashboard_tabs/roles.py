from __future__ import annotations

from typing import Any

from .. import dashboard_core as core


def _render_color_sets(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
) -> str:
    _core = core
    _color_sets_settings_from_db = _core._color_sets_settings_from_db
    json = _core.json
    _collect_color_roles_for_ui = _core._collect_color_roles_for_ui
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    settings = _color_sets_settings_from_db(int(current_guild["id"]))
    sets_json = json.dumps(settings.get("sets") or [], ensure_ascii=False)
    applied_set_id = str(settings.get("applied_set_id") or "").strip()
    color_roles_json = json.dumps(_collect_color_roles_for_ui(bot_guild), ensure_ascii=False)
    body = _render_dashboard_f_template("color_sets.html", locals())
    return _render_layout(
        title=f"SkylineBOT Color Sets - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab="colors",
        notice=notice,
    )


def _render_reaction_roles(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "reaction_roles",
) -> str:
    _core = core
    _reaction_roles_settings_from_db = _core._reaction_roles_settings_from_db
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _plan_display_name = _core._plan_display_name
    _plan_limits_from_guild_state = _core._plan_limits_from_guild_state
    _live_options_payload = _core._live_options_payload
    json = _core.json
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict((state or {}).get("guild") or {})
    guild_state_for_plan["subscription"] = plan_tier
    plan_name = _plan_display_name(plan_tier)
    plan_limits = _plan_limits_from_guild_state(guild_state_for_plan)
    reaction_roles_limit = max(1, min(100, int(plan_limits.get("reaction_roles", 10) or 10)))

    settings = _reaction_roles_settings_from_db(int(current_guild["id"]))
    items = list(settings.get("items") or [])
    used_reaction_roles = 0
    for item in items:
        options = item.get("options") if isinstance(item, dict) else []
        if isinstance(options, list):
            used_reaction_roles += len(options)

    live_options = _live_options_payload(bot_guild if bot_guild else None)
    role_options = list(live_options.get("roles") or [])
    channel_options_all = list(live_options.get("channels") or [])
    allowed_channel_types = {"text", "news"}
    channel_options = []
    for channel in channel_options_all:
        channel_type = str((channel or {}).get("type") or "").strip().lower()
        if channel_type in allowed_channel_types:
            channel_options.append(channel)

    role_options_json = json.dumps(role_options, ensure_ascii=False)
    channel_options_json = json.dumps(channel_options, ensure_ascii=False)
    items_json = json.dumps(settings.get("items") or [], ensure_ascii=False)
    body = _render_dashboard_f_template("reaction_roles.html", locals())
    return _render_layout(
        title=f"SkylineBOT Reaction Roles - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )


def _render_starboard(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "starboard",
) -> str:
    _core = core
    _starboard_settings_from_db = _core._starboard_settings_from_db
    _escape = _core._escape
    json = _core.json
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    settings = _starboard_settings_from_db(int(current_guild["id"]))
    starboard_placeholder = "{content}"
    color_value = _escape(settings.get("color") or "#6B8CFF")
    starboard_fields_json = _escape(json.dumps(settings.get("fields") or [], ensure_ascii=False))
    message_mode = str(settings.get("message_mode") or "embed").strip().lower()
    text_tab_class = "primary-btn" if message_mode == "text" else "ghost-btn"
    embed_tab_class = "primary-btn" if message_mode == "embed" else "ghost-btn"
    body = _render_dashboard_f_template("starboard.html", locals())
    return _render_layout(
        title=f"SkylineBOT Starboard - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )


def _render_customrole(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
) -> str:
    _core = core
    _plan_display_name = _core._plan_display_name
    _plan_limits_from_guild_state = _core._plan_limits_from_guild_state
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _render_role_select = _core._render_role_select
    _escape = _core._escape
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    SUBSCRIBE_PLAN_PATH = _core.SUBSCRIBE_PLAN_PATH

    prefix = str(getattr(_core.BOT_CONFIG, "PREFIX", "/")).strip() or "/"
    roles_data = state.get("custom_roles") or []
    required_role_settings = state.get("custom_roles_permission") or {}
    guild_state = state.get("guild") or {}

    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    plan_name = _plan_display_name(plan_tier)
    limits = _plan_limits_from_guild_state(guild_state_for_plan)

    max_items = int(limits["custom_roles"])
    used_items = len(roles_data)
    limit_reached = used_items >= max_items

    required_role_id = str(required_role_settings.get("required_role_id") or "").strip()
    required_role_name = "ยังไม่ได้ตั้งค่า"
    if required_role_id:
        if required_role_id.isdigit() and bot_guild:
            role_obj = bot_guild.get_role(int(required_role_id))
            if role_obj:
                required_role_name = f"@{role_obj.name}"
            else:
                required_role_name = f"Role ID {required_role_id} (ไม่พบยศนี้แล้ว)"
        else:
            required_role_name = f"Role ID {required_role_id}"

    command_examples = [
        f"{prefix}vip @member",
        f"{prefix}booster 123456789012345678",
    ]
    command_examples_markup = "".join(
        f"<li><code>{_escape(example)}</code> <button type='button' class='ghost-btn' data-copy-command='{_escape(example)}' style='width:fit-content; padding:0 10px; height:30px; margin-left:8px;'>คัดลอก</button></li>"
        for example in command_examples
    )

    orphaned_rows: list[dict[str, str]] = []
    rows_markup_parts: list[str] = []
    for row in roles_data:
        row_id = int(row.get("id") or 0)
        command_key = str(row.get("name") or "").strip()
        role_id_raw = str(row.get("role_id") or "").strip()
        role_name = "ไม่พบบทบาทนี้"
        role_missing = False

        if role_id_raw.isdigit() and bot_guild:
            row_role = bot_guild.get_role(int(role_id_raw))
            if row_role:
                role_name = f"@{row_role.name}"
            else:
                role_missing = True
                role_name = f"Role ID {role_id_raw}"
        elif role_id_raw:
            role_name = f"Role ID {role_id_raw}"
            role_missing = not role_id_raw.isdigit()
        else:
            role_missing = True

        if role_missing:
            orphaned_rows.append(
                {
                    "id": str(row_id),
                    "command": command_key or "-",
                    "role_id": role_id_raw or "-",
                }
            )

        quick_command_mention = f"{prefix}{command_key} @member"
        quick_command_id = f"{prefix}{command_key} 123456789012345678"
        role_state_badge = (
            '<span class="pill" style="background:rgba(239,68,68,.16);border-color:rgba(239,68,68,.45);color:#fecaca;">Role ถูกลบ</span>'
            if role_missing
            else '<span class="pill">พร้อมใช้งาน</span>'
        )

        rows_markup_parts.append(
            f"""
            <article class="panel-sub detail-page-section" style="margin-top:10px;">
              <div class="panel-header" style="padding:0 0 10px;">
                <div class="panel-title">
                  <h3 style="margin:0;font-size:15px;">คีย์คำสั่ง: <code>{_escape(command_key)}</code></h3>
                  <p class="muted" style="margin:4px 0 0;">Role: {_escape(role_name)} ({_escape(role_id_raw or '-')})</p>
                </div>
                <div>{role_state_badge}</div>
              </div>
              <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:0 0 10px;">
                <button type="button" class="ghost-btn" data-copy-command="{_escape(quick_command_mention)}" style="width:fit-content; padding:0 14px; height:34px;">คัดลอกคำสั่ง @member</button>
                <button type="button" class="ghost-btn" data-copy-command="{_escape(quick_command_id)}" style="width:fit-content; padding:0 14px; height:34px;">คัดลอกคำสั่ง member_id</button>
              </div>
              <form method="post" action="/dashboard/guild/{current_guild['id']}/customrole/update">
                <input type="hidden" name="id" value="{row_id}">
                <div class="field-group">
                  <div class="field-item">
                    <label>คีย์คำสั่ง (พิมพ์ในแชท)</label>
                    <input type="text" name="name" value="{_escape(command_key)}" maxlength="32" pattern="[a-z0-9_-]+" required>
                  </div>
                  <div class="field-item">
                    <label>บทบาทเป้าหมาย</label>
                    {_render_role_select("role_id", bot_guild, role_id_raw, placeholder="เลือกยศ...")}
                  </div>
                </div>
                <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                  <button class="primary-btn" type="submit" style="width:fit-content; padding:0 20px;">บันทึกการแก้ไข</button>
                </div>
              </form>
              <form method="post" action="/dashboard/guild/{current_guild['id']}/customrole/delete" style="margin-top:10px;">
                <input type="hidden" name="id" value="{row_id}">
                <button class="ghost-btn" style="color:#ff4d4d; border-color:#ff4d4d22; padding:0 16px; height:34px; width:fit-content;" type="submit">ลบรายการนี้</button>
              </form>
            </article>
            """
        )

    orphaned_count = len(orphaned_rows)
    orphaned_rows_markup = "".join(
        f"""
        <div class="panel-sub" style="margin-top:8px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
          <div>
            <strong><code>{_escape(item['command'])}</code></strong>
            <div class="muted">Role ID: <code>{_escape(item['role_id'])}</code> ไม่พบในเซิร์ฟเวอร์แล้ว</div>
          </div>
          <form method="post" action="/dashboard/guild/{current_guild['id']}/customrole/delete" style="margin:0;">
            <input type="hidden" name="id" value="{_escape(item['id'])}">
            <button class="ghost-btn" style="color:#ff4d4d; border-color:#ff4d4d22; width:fit-content; padding:0 14px; height:32px;" type="submit">ลบรายการนี้</button>
          </form>
        </div>
        """
        for item in orphaned_rows
    )
    orphaned_notice_markup = (
        f"""
        <section class='panel-sub detail-page-section' style='margin-bottom:14px;border:1px solid rgba(239,68,68,.45);'>
            <h2 style='margin-top:0;color:#fecaca;' data-icon-key='customrole_alert'>พบ {orphaned_count} รายการที่ Role ถูกลบ</h2>
            <p class='muted' style='margin:8px 0 10px;'>รายการด้านล่างจะใช้งานไม่ได้จนกว่าจะเปลี่ยน role หรือถูกลบ</p>
            {orphaned_rows_markup}
        </section>
        """
        if orphaned_count > 0
        else ""
    )

    rows_markup = "".join(rows_markup_parts)

    body = _render_dashboard_f_template("customrole.html", locals())
    return _render_layout(
        title=f"Custom Role - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab="customrole",
        notice=notice,
    )
