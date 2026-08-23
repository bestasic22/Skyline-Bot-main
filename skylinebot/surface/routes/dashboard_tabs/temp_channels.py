from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_temp_channels(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "temp_channels",
) -> str:
    _core = core
    _temp_channels_settings_from_db = _core._temp_channels_settings_from_db
    _escape = _core._escape
    json = _core.json
    _render_channel_select = _core._render_channel_select
    _render_role_select = _core._render_role_select
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    resolved_tab_slug = "join_to_create" if str(active_tab_slug or "").strip().lower() in {"join_to_create", "temp_channels"} else "join_to_create"
    redirect_tab_path = f"/dashboard/guild/{current_guild['id']}/{resolved_tab_slug}"
    save_endpoint = f"/dashboard/guild/{current_guild['id']}/temp_channels"
    send_interface_endpoint = f"/dashboard/guild/{current_guild['id']}/temp_channels/send_interface"
    settings = _temp_channels_settings_from_db(int(current_guild["id"]), state)
    temp_fields_json = _escape(json.dumps(settings.get("fields") or [], ensure_ascii=False))
    button_defs: list[tuple[str, str]] = [
        ("name", "เปลี่ยนชื่อ"),
        ("limit", "จำนวนคน"),
        ("privacy", "ล็อก/ปลดล็อก"),
        ("chat", "ซ่อน/แสดงช่อง"),
        ("trust", "อนุญาตสมาชิก"),
        ("untrust", "ยกเลิกการอนุญาต"),
        ("kick", "เตะออกจากห้อง"),
        ("region", "Region"),
        ("block", "บล็อกสมาชิก"),
        ("unblock", "ปลดบล็อก"),
        ("claim", "Claim Owner"),
        ("transfer", "โอนเจ้าของ"),
        ("delete", "ลบห้อง"),
    ]
    buttons_state = settings.get("buttons") if isinstance(settings.get("buttons"), dict) else {}

    category_select = _render_channel_select(
        "create_vc_category_id",
        bot_guild,
        settings.get("create_vc_category_id"),
        placeholder="เลือก ..",
        filter_types=["category"],
    )
    create_channel_select = _render_channel_select(
        "create_vc_channel_id",
        bot_guild,
        settings.get("create_vc_channel_id"),
        placeholder="เลือก ..",
        filter_types=["voice", "stage_voice"],
    )
    enabled_channel_select = _render_channel_select(
        "enabled_channel_id",
        bot_guild,
        settings.get("enabled_channel_id"),
        placeholder="เลือก ..",
        filter_types=["text", "news", "forum"],
    )
    disabled_channel_select = _render_channel_select(
        "disabled_channel_id",
        bot_guild,
        settings.get("disabled_channel_id"),
        placeholder="เลือก ..",
        filter_types=["text", "news", "forum"],
    )
    send_channel_select = _render_channel_select(
        "send_channel_id",
        bot_guild,
        settings.get("send_channel_id"),
        placeholder="Select a Text Channel",
        filter_types=["text", "news", "forum"],
    )
    enable_role_select = _render_role_select("enable_role_id", bot_guild, settings.get("enable_role_id"), placeholder="เลือก ..")
    disable_role_select = _render_role_select("disable_role_id", bot_guild, settings.get("disable_role_id"), placeholder="เลือก ..")
    enabled_checked = "checked" if bool(settings.get("enabled")) else ""
    auto_delete_message_checked = "checked" if bool(settings.get("auto_delete_message")) else ""
    auto_delete_command_checked = "checked" if bool(settings.get("auto_delete_command")) else ""
    auto_delete_bot_reply_checked = "checked" if bool(settings.get("auto_delete_bot_reply")) else ""
    message_tab_class = "primary-btn" if str(settings.get("interface_mode") or "embed") == "text" else "ghost-btn"
    embed_tab_class = "primary-btn" if str(settings.get("interface_mode") or "embed") == "embed" else "ghost-btn"

    button_toggles_html = "".join(
        f"""
        <label class="tv-btn-toggle">
          <input type="checkbox" name="btn_{_escape(key)}" {'checked' if bool(buttons_state.get(key, True)) else ''}>
          <span>{_escape(label)}</span>
        </label>
        """
        for key, label in button_defs
    )

    body = _render_dashboard_f_template("temp_channels.html", locals())
    return _render_layout(
        title=f"SkylineBOT Temporary Channels - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
