from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_welcome(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "welcome",
    title_override: str | None = None,
    description_override: str | None = None,
) -> str:
    _core = core
    _preview_bot_identity = _core._preview_bot_identity
    _preview_member_identity = _core._preview_member_identity
    _plan_display_name = _core._plan_display_name
    _is_plan_at_least = _core._is_plan_at_least
    _plan_limits_from_guild_state = _core._plan_limits_from_guild_state
    style_urls = _core.style_urls
    json = _core.json
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    preview_member_name, preview_member_avatar = _preview_member_identity(session)
    data = state["welcomer"]
    guild_state = state.get("guild") or {}
    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)
    can_use_image_cards = _is_plan_at_least(plan_tier, "silver")
    image_locked_attr = "" if can_use_image_cards else "disabled"
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    limits = _plan_limits_from_guild_state(guild_state_for_plan)
    max_autoroles = int(limits["autoroles"])
    current_autoroles = data.get("autoroles") or []
    if isinstance(current_autoroles, str):
        try:
            current_autoroles = json.loads(current_autoroles)
        except Exception:
            current_autoroles = []
    current_autoroles = [item for item in current_autoroles if str(item).strip()]
    welcome_preview = data.get("welcome_message_content") or "ยินดีต้อนรับ {user.mention} สู่ {server}"
    welcome_embed_image = str(data.get("welcome_embed_image") or "").strip()
    welcome_image_theme = str(data.get("welcome_image_theme") or "music").strip().lower()
    welcome_image_theme_url = str(data.get("welcome_image_theme_url") or "").strip()
    welcome_image_layout_mode = str(data.get("welcome_image_layout_mode") or "center_stack").strip().lower()
    welcome_image_avatar_position = str(data.get("welcome_image_avatar_position") or "center").strip().lower()
    welcome_image_text_align = str(data.get("welcome_image_text_align") or "center").strip().lower()
    welcome_image_font_style = str(data.get("welcome_image_font_style") or "classic").strip().lower()
    welcome_image_top_text = str(data.get("welcome_image_top_text") or "{user}").strip()
    welcome_image_bottom_text = str(data.get("welcome_image_bottom_text") or "ยินดีต้อนรับสู่ {server}").strip()
    invite_tracking_enabled = bool(data.get("invite_tracking_enabled"))
    invite_welcome_enabled = bool(data.get("invite_welcome_enabled"))
    invite_welcome_template = str(
        data.get("invite_welcome_template")
        or "สมาชิกคนนี้มาด้วยคำเชิญของ {inviter.mention} • เชิญแล้ว {inviter.count} คน"
    ).strip()
    invite_welcome_unknown_template = str(
        data.get("invite_welcome_unknown_template")
        or "ไม่สามารถตรวจสอบได้ว่าเข้ามาจากคำเชิญของใคร"
    ).strip()
    _preview_server_icon = str(
        getattr(getattr(bot_guild, "icon", None), "url", "")
        or current_guild.get("icon")
        or "https://cdn.discordapp.com/embed/avatars/0.png"
    ).strip()
    welcome_theme_presets_json = json.dumps(
        style_urls.get_theme_presets(
            user_url=str(preview_member_avatar or "https://cdn.discordapp.com/embed/avatars/0.png"),
            guild_url=_preview_server_icon,
            include_extended=False,
        ),
        ensure_ascii=False,
    )
    template_preview_user_name = json.dumps(str(preview_member_name or "member"), ensure_ascii=False)
    template_preview_user_mention = json.dumps(f"@{preview_member_name}", ensure_ascii=False)
    template_preview_server_name = json.dumps(str(current_guild.get("name") or "Guild"), ensure_ascii=False)
    _preview_user_id_raw = str(session.get("discord_id") or session.get("id") or "").strip()
    _preview_user_id = _preview_user_id_raw if _preview_user_id_raw.isdigit() else "100000000000000001"
    _preview_server_id = str(current_guild.get("id") or getattr(bot_guild, "id", "") or "").strip()
    if not _preview_server_id.isdigit():
        _preview_server_id = "100000000000000002"
    _preview_member_count = int(
        getattr(bot_guild, "member_count", 0)
        or current_guild.get("members")
        or 0
    )
    if _preview_member_count <= 0:
        _preview_member_count = 117
    template_preview_user_id = json.dumps(_preview_user_id, ensure_ascii=False)
    template_preview_server_id = json.dumps(_preview_server_id, ensure_ascii=False)
    template_preview_member_count = json.dumps(str(_preview_member_count), ensure_ascii=False)
    _preview_user_name = str(preview_member_name or "Member").strip() or "Member"
    _preview_server_name = str(current_guild.get("name") or "Guild").strip() or "Guild"
    mock_preview_users_json = json.dumps(
        [
            {
                "id": "session",
                "label": f"{_preview_user_name} (You)",
                "name": _preview_user_name,
                "mention": f"@{_preview_user_name}",
                "avatar": str(preview_member_avatar or "https://cdn.discordapp.com/embed/avatars/0.png"),
                "user_id": _preview_user_id,
            },
        ],
        ensure_ascii=False,
    )
    mock_preview_servers_json = json.dumps(
        [
            {
                "id": "current",
                "label": f"{_preview_server_name} (Current)",
                "name": _preview_server_name,
                "icon": _preview_server_icon,
                "guild_id": _preview_server_id,
                "member_count": _preview_member_count,
            },
        ],
        ensure_ascii=False,
    )
    welcome_feature_keys = (
        "welcome",
        "welcome_message",
        "welcome_embed",
        "welcome_image",
        "invite_tracking_enabled",
        "invite_welcome_enabled",
        "autorole",
        "autonick",
    )
    welcome_enabled_features = sum(1 for key in welcome_feature_keys if bool(data.get(key)))

    title_text = title_override or "ต้อนรับสมาชิก (Welcome)"
    desc_text = description_override or "ตั้งค่าข้อความต้อนรับสมาชิก พร้อมตัวอย่าง Embed แบบเรียลไทม์"

    body = _render_dashboard_f_template("welcome.html", locals())
    return _render_layout(
        title=f"SkylineBOT Welcome - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )

def _render_leaver(session: dict[str, Any], guilds: list[dict[str, Any]], current_guild: dict[str, Any], bot_guild: Any, state: dict[str, Any], notice: str | None = None) -> str:
    _core = core
    _preview_bot_identity = _core._preview_bot_identity
    _preview_member_identity = _core._preview_member_identity
    _plan_display_name = _core._plan_display_name
    _is_plan_at_least = _core._is_plan_at_least
    style_urls = _core.style_urls
    json = _core.json
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    preview_member_name, preview_member_avatar = _preview_member_identity(session)
    data = state["welcomer"]
    guild_state = state.get("guild") or {}
    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)
    can_use_image_cards = _is_plan_at_least(plan_tier, "silver")
    image_locked_attr = "" if can_use_image_cards else "disabled"
    leave_channels = data.get("leave_channels") or []
    if isinstance(leave_channels, str):
        try:
            leave_channels = json.loads(leave_channels)
        except Exception:
            leave_channels = []
    leave_channels = [str(item).strip() for item in leave_channels if str(item).strip().isdigit()]
    leave_channel_selected = leave_channels[0] if leave_channels else None

    leave_preview = data.get("leave_message") or "{user.mention} ออกจาก {server} แล้ว"
    leave_embed_title = str(data.get("leave_embed_title") or "สมาชิกออกจากเซิร์ฟเวอร์").strip()
    leave_embed_description = str(data.get("leave_embed_description") or leave_preview).strip()
    leave_image_theme = str(data.get("leave_image_theme") or "security").strip().lower()
    leave_image_theme_url = str(data.get("leave_image_theme_url") or "").strip()
    leave_image_layout_mode = str(data.get("leave_image_layout_mode") or "center_stack").strip().lower()
    leave_image_avatar_position = str(data.get("leave_image_avatar_position") or "center").strip().lower()
    leave_image_text_align = str(data.get("leave_image_text_align") or "center").strip().lower()
    leave_image_font_style = str(data.get("leave_image_font_style") or "classic").strip().lower()
    leave_image_top_text = str(data.get("leave_image_top_text") or "{user}").strip()
    leave_image_bottom_text = str(data.get("leave_image_bottom_text") or "ออกจาก {server} แล้ว").strip()
    _preview_server_icon = str(
        getattr(getattr(bot_guild, "icon", None), "url", "")
        or current_guild.get("icon")
        or "https://cdn.discordapp.com/embed/avatars/0.png"
    ).strip()
    leave_theme_presets_json = json.dumps(
        style_urls.get_theme_presets(
            user_url=str(preview_member_avatar or "https://cdn.discordapp.com/embed/avatars/0.png"),
            guild_url=_preview_server_icon,
            include_extended=False,
        ),
        ensure_ascii=False,
    )
    template_preview_user_name = json.dumps(str(preview_member_name or "member"), ensure_ascii=False)
    template_preview_user_mention = json.dumps(f"@{preview_member_name}", ensure_ascii=False)
    template_preview_server_name = json.dumps(str(current_guild.get("name") or "Guild"), ensure_ascii=False)
    _preview_user_name = str(preview_member_name or "Member").strip() or "Member"
    _preview_server_name = str(current_guild.get("name") or "Guild").strip() or "Guild"
    mock_preview_users_json = json.dumps(
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
    mock_preview_servers_json = json.dumps(
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

    body = _render_dashboard_f_template("leaver.html", locals())
    return _render_layout(title=f"SkylineBOT Leaver - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab="leaver", notice=notice)
