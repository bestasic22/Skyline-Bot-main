from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_moderation(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "moderation",
    title_override: str | None = None,
    description_override: str | None = None,
) -> str:
    _core = core
    _preview_bot_identity = _core._preview_bot_identity
    _preview_member_identity = _core._preview_member_identity
    _can_use_automod_custom = _core._can_use_automod_custom
    _can_use_automod_diamond = _core._can_use_automod_diamond
    _plan_display_name = _core._plan_display_name
    _allowed_automod_punishments = _core._allowed_automod_punishments
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    json = _core.json
    SUBSCRIBE_PLAN_PATH = _core.SUBSCRIBE_PLAN_PATH
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    data = state["automod"]
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    preview_member_name, preview_member_avatar = _preview_member_identity(session)
    guild_state = state.get("guild") or {}
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    can_use_custom = _can_use_automod_custom(guild_state_for_plan)
    can_use_diamond = _can_use_automod_diamond(guild_state_for_plan)
    plan_name = _plan_display_name(plan_tier)
    selected_mode = (data.get("mode") or "normal").lower()
    enabled_rule_count = sum(
        1
        for key in ("antilink_enabled", "antispam_enabled", "antibadwords_enabled")
        if bool(data.get(key))
    )
    if selected_mode in {"custom", "diamond"} and not can_use_custom:
        selected_mode = "normal"
    if selected_mode == "diamond" and not can_use_diamond:
        selected_mode = "custom" if can_use_custom else "normal"
    mode_label_by_key = {
        "normal": "Normal",
        "extreme": "Extreme",
        "custom": "Custom",
        "diamond": "Diamond",
    }
    moderation_mode_label = mode_label_by_key.get(selected_mode, selected_mode.title())

    custom_option = (
        f'<option value="custom" {"selected" if selected_mode == "custom" else ""}>กำหนดเอง (Custom)</option>'
        if can_use_custom
        else '<option value="custom" disabled>กำหนดเอง (Custom) - ต้องมี Silver ขึ้นไป</option>'
    )
    diamond_option = (
        f'<option value="diamond" {"selected" if selected_mode == "diamond" else ""}>Diamond</option>'
        if can_use_diamond
        else '<option value="diamond" disabled>Diamond - ต้องมี Diamond</option>'
    )

    allowed = _allowed_automod_punishments(guild_state_for_plan)
    current_punishment = (data.get("antispam_punishment") or "mute").lower()
    punishment_label_by_key = {
        "mute": "Mute",
        "kick": "Kick",
        "ban": "Ban",
    }
    moderation_punishment_label = punishment_label_by_key.get(current_punishment, current_punishment.title())
    punishment_options = []
    for value, label, min_plan in [
        ("mute", "ปิด (Mute)", "free"),
        ("kick", "เตะ (Kick)", "silver"),
        ("ban", "แบน (Ban)", "diamond"),
    ]:
        selected = "selected" if current_punishment == value else ""
        disabled = "disabled" if value not in allowed else ""
        punishment_options.append(
            f'<option value="{value}" data-min-plan="{min_plan}" {selected} {disabled}>{label}</option>'
        )

    premium_notice = (
        ""
        if can_use_custom
        else (
            '<div class="notice" style="margin-bottom:12px;">'
            'แพ็กเกจ Free ยังไม่สามารถใช้โหมด Custom/Diamond ได้ '
            f'<a href="{SUBSCRIBE_PLAN_PATH}" class="ghost-btn" style="margin-left:8px;">ดูแพ็กเกจ</a>'
            '</div>'
        )
    )

    title_text = title_override or "ดูแลแชต (Moderation)"
    desc_text = description_override or "จัดการลิงก์ สแปม และคำไม่เหมาะสมอัตโนมัติ"

    template_preview_user_name = json.dumps(str(preview_member_name or "Member"), ensure_ascii=False)
    template_preview_user_mention = json.dumps(f"@{preview_member_name}", ensure_ascii=False)
    template_preview_server_name = json.dumps(str(current_guild.get("name") or "Guild"), ensure_ascii=False)
    _preview_user_name = str(preview_member_name or "Member").strip() or "Member"
    _preview_server_name = str(current_guild.get("name") or "Guild").strip() or "Guild"
    moderation_mock_users_json = json.dumps(
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
    moderation_mock_servers_json = json.dumps(
        [
            {"id": "current", "label": f"{_preview_server_name} (Current)", "name": _preview_server_name},
        ],
        ensure_ascii=False,
    )

    body = _render_dashboard_f_template("moderation.html", locals())
    return _render_layout(
        title=f"SkylineBOT Moderation - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
