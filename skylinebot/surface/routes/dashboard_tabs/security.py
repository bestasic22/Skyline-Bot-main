from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_security(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "security",
    title_override: str | None = None,
    description_override: str | None = None,
) -> str:
    _core = core
    _preview_bot_identity = _core._preview_bot_identity
    _preview_member_identity = _core._preview_member_identity
    _can_use_antinuke_custom = _core._can_use_antinuke_custom
    _plan_display_name = _core._plan_display_name
    _allowed_antinuke_punishments = _core._allowed_antinuke_punishments
    SUBSCRIBE_PLAN_PATH = _core.SUBSCRIBE_PLAN_PATH
    _is_plan_at_least = _core._is_plan_at_least
    get_bot = _core.get_bot
    _render_channel_select = _core._render_channel_select
    _discord_default_avatar_url = _core._discord_default_avatar_url
    _escape = _core._escape
    _with_cache_bust = _core._with_cache_bust
    _dashboard_editor_role_ids_from_db = _core._dashboard_editor_role_ids_from_db
    BOT_CONFIG = _core.BOT_CONFIG
    _render_multi_role_select = _core._render_multi_role_select
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _default_extra_protection_settings = _core._default_extra_protection_settings
    _default_honeypot_settings = _core._default_honeypot_settings
    _normalize_extra_protection_settings = _core._normalize_extra_protection_settings
    _normalize_honeypot_settings = _core._normalize_honeypot_settings
    json = _core.json
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    data = state["antinuke"]
    extra_protection_data = _normalize_extra_protection_settings(
        state.get("extra_protection") or _default_extra_protection_settings()
    )
    honeypot_data = _normalize_honeypot_settings(
        state.get("honeypot") or _default_honeypot_settings()
    )
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    preview_member_name, preview_member_avatar = _preview_member_identity(session)
    guild_state = state.get("guild") or {}
    guild_language = str(guild_state.get("language") or "th").strip().lower()
    if guild_language not in {"th", "en"}:
        guild_language = "th"
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    can_use_custom = _can_use_antinuke_custom(guild_state_for_plan)
    plan_name = _plan_display_name(plan_tier)
    can_use_honeypot = _is_plan_at_least(plan_tier, "golden")
    allowed = _allowed_antinuke_punishments(guild_state_for_plan)

    selected_type = (data.get("type") or "normal").lower()
    if selected_type == "extream":
        selected_type = "extreme"
    if selected_type == "custom" and not can_use_custom:
        selected_type = "normal"
    security_toggle_keys = (
        "enabled",
        "anti_bot_add",
        "anti_channel_delete",
        "anti_role_delete",
        "anti_webhook_create",
        "anti_everyone_mention",
    )
    security_enabled_count = sum(1 for key in security_toggle_keys if bool(data.get(key)))
    security_mode_label = {
        "normal": "Normal",
        "extreme": "Extreme",
        "custom": "Custom",
    }.get(selected_type, selected_type.title())
    if active_tab_slug == "extra_protection":
        security_toggle_keys = (
            "enabled",
            "block_bot_add_enabled",
            "anti_spam_enabled",
            "anti_mass_mention_enabled",
            "delete_discord_invite_enabled",
            "delete_scam_links_enabled",
            "anti_virus_keywords_enabled",
        )
        security_enabled_count = sum(1 for key in security_toggle_keys if bool(extra_protection_data.get(key)))
        security_mode_label = "Shield"

    custom_option = (
        f'<option value="custom" {"selected" if selected_type == "custom" else ""}>กำหนดเอง (Custom)</option>'
        if can_use_custom
        else '<option value="custom" disabled>กำหนดเอง (Custom) - Silver ขึ้นไป</option>'
    )

    bypass_ids = [
        str(x).strip()
        for x in str(data.get("bypass_role_id") or "").split(",")
        if str(x).strip().isdigit()
    ]

    premium_notice = (
        ""
        if can_use_custom
        else (
            '<div class="notice" style="margin-bottom:12px;">'
            'แพ็กเกจ Free ยังไม่สามารถใช้ Anti-Nuke แบบ Custom ได้ '
            f'<a href="{SUBSCRIBE_PLAN_PATH}" class="ghost-btn" style="margin-left:8px;">ดูแพ็กเกจ</a>'
            "</div>"
        )
    )
    if active_tab_slug == "extra_protection":
        premium_notice = ""
    honeypot_timeout_days = max(
        1,
        min(28, int(int(honeypot_data.get("timeout_seconds") or 604800) // 86400)),
    )
    honeypot_cooldown_minutes = max(
        2,
        min(5, int(int(honeypot_data.get("status_edit_cooldown_seconds") or 120) // 60)),
    )
    honeypot_channel_select = _render_channel_select(
        "honeypot_channel_id",
        bot_guild,
        honeypot_data.get("channel_id"),
        placeholder="Select honeypot channel...",
        filter_types=["text", "news"],
        disabled=not can_use_honeypot,
    )
    honeypot_disabled_attr = "" if can_use_honeypot else "disabled"
    honeypot_plan_notice = (
        ""
        if can_use_honeypot
        else (
            '<div class="notice" style="margin-bottom:12px;">'
            'Honeypot ใช้งานได้สำหรับแพ็กเกจ Gole/Diamond/Permanent เท่านั้น '
            f'<a href="{SUBSCRIBE_PLAN_PATH}" class="ghost-btn" style="margin-left:8px;">ดูแพ็กเกจ</a>'
            "</div>"
        )
    )
    security_form_inline_style = 'style="display:none;"'
    if active_tab_slug != "extra_protection":
        security_form_inline_style = ""

    def punishment_select(name: str, current: str) -> str:
        current_value = (current or "kick").lower()
        options = []
        for value, label, min_plan in [
            ("mute", "ปิด (Mute)", "free"),
            ("kick", "เตะ (Kick)", "silver"),
            ("ban", "แบน (Ban)", "diamond"),
        ]:
            selected = "selected" if current_value == value else ""
            disabled = "disabled" if value not in allowed else ""
            options.append(
                f'<option value="{value}" data-min-plan="{min_plan}" {selected} {disabled}>{label}</option>'
            )
        return f'<select name="{name}" class="punishment-select">{"".join(options)}</select>'

    title_text = title_override or "ความปลอดภัย (Security)"
    desc_text = description_override or "ปกป้องเซิร์ฟเวอร์ของคุณจากบอทแปลกปลอมและการโจมตี (Anti-Nuke)"
    security_tab_label = {
        "security": "Security",
        "anti_raid": "Anti-Raid",
        "extra_protection": "Extra Protection",
    }.get(active_tab_slug, active_tab_slug.replace("_", " ").title())
    security_tab_icon_key = active_tab_slug if active_tab_slug in {"anti_raid", "extra_protection"} else "security"
    security_hero_badges_html = (
        f'<span class="pill"><i class="bi bi-stars" aria-hidden="true"></i> {security_tab_label}</span>'
        f'<span class="pill"><i class="bi bi-shield-check" aria-hidden="true"></i> เปิดใช้ {security_enabled_count}/{len(security_toggle_keys)}</span>'
        f'<span class="pill"><i class="bi bi-sliders2" aria-hidden="true"></i> โหมด {security_mode_label}</span>'
    )
    can_customize_bot_profile = _is_plan_at_least(plan_tier, "silver")
    bot_member = getattr(bot_guild, "me", None) if bot_guild else None
    bot_user = getattr(get_bot(), "user", None)
    bot_nick_current = str(getattr(bot_member, "nick", "") or "").strip()
    bot_display_name_current = str(getattr(bot_member, "display_name", "") or "").strip()
    bot_display_name_default = str(
        getattr(bot_user, "display_name", "") or getattr(bot_user, "name", "") or "SkylineBOT"
    ).strip() or "SkylineBOT"
    if not bot_display_name_current:
        bot_display_name_current = bot_display_name_default
    bot_nick_current_label = bot_nick_current or "ยังไม่ตั้ง"
    bot_nick_default_label = bot_display_name_default
    bot_avatar_current_raw = (
        str(getattr(getattr(bot_member, "display_avatar", None), "url", "") or "").strip()
        or str(getattr(getattr(bot_user, "display_avatar", None), "url", "") or "").strip()
        or _discord_default_avatar_url(current_guild.get("id", "0"))
    )
    bot_avatar_default_raw = (
        str(getattr(getattr(bot_user, "display_avatar", None), "url", "") or "").strip()
        or _discord_default_avatar_url(current_guild.get("id", "0"))
    )
    bot_avatar_current = _escape(_with_cache_bust(bot_avatar_current_raw, bucket_seconds=180))
    bot_avatar_default = _escape(_with_cache_bust(bot_avatar_default_raw, bucket_seconds=180))
    bot_profile_notice = (
        ""
        if can_customize_bot_profile
        else (
            '<div class="notice" style="margin-bottom:12px;">'
            'ฟีเจอร์ชื่อ/รูปโปรไฟล์บอทต่อเซิร์ฟเวอร์ ใช้ได้เฉพาะพรีเมียม (Silver/Gole/Diamond/Permanent) '
            f'<a href="{SUBSCRIBE_PLAN_PATH}" class="ghost-btn" style="margin-left:8px;">ดูแพ็กเกจ</a>'
            "</div>"
        )
    )
    bot_profile_disabled_attr = "" if can_customize_bot_profile else "disabled"
    dashboard_access = state.get("dashboard_access") if isinstance(state, dict) else {}
    is_owner_for_dashboard_roles = bool((dashboard_access or {}).get("effective_is_owner"))
    dashboard_editor_role_ids = _dashboard_editor_role_ids_from_db(int(current_guild.get("id") or 0))
    dashboard_roles_disabled_attr = "" if is_owner_for_dashboard_roles else "disabled"
    dashboard_roles_notice = (
        ""
        if is_owner_for_dashboard_roles
        else '<div class="notice" style="margin-bottom:12px;">เฉพาะเจ้าของกิลด์เท่านั้นที่ตั้งค่ายศผู้ดูแลแดชบอร์ดได้</div>'
    )
    command_access_cfg = state.get("command_access") if isinstance(state, dict) else {}
    raw_delast_allowed_user_ids = (command_access_cfg or {}).get("delast_access_user_ids", [])
    delast_allowed_user_ids: list[str] = []
    if isinstance(raw_delast_allowed_user_ids, (list, tuple, set)):
        for item in raw_delast_allowed_user_ids:
            value = str(item or "").strip()
            if value.isdigit() and value not in delast_allowed_user_ids:
                delast_allowed_user_ids.append(value)
    else:
        for item in str(raw_delast_allowed_user_ids or "").replace("\n", ",").split(","):
            value = str(item or "").strip()
            if value.isdigit() and value not in delast_allowed_user_ids:
                delast_allowed_user_ids.append(value)
    delast_allowed_user_ids_text = "\n".join(delast_allowed_user_ids)
    delast_limit_by_plan = {"free": 20, "silver": 40, "golden": 70, "diamond": 100, "permanent": 150}
    delast_current_limit = int(delast_limit_by_plan.get(plan_tier, 20))
    delast_access_notice = (
        ""
        if is_owner_for_dashboard_roles
        else '<div class="notice" style="margin-bottom:12px;">เฉพาะเจ้าของกิลด์เท่านั้นที่ตั้งค่ารายชื่อผู้ใช้คำสั่งลบข้อความได้</div>'
    )
    delast_access_disabled_attr = "" if is_owner_for_dashboard_roles else "disabled"
    extra_protection_form_html = ""
    if active_tab_slug == "extra_protection":
        xp_whitelist_users_text = "\n".join(
            str(item or "").strip()
            for item in extra_protection_data.get("bot_add_whitelist_user_ids", [])
            if str(item or "").strip()
        )
        xp_whitelist_bots_text = "\n".join(
            str(item or "").strip()
            for item in extra_protection_data.get("bot_add_whitelist_bot_ids", [])
            if str(item or "").strip()
        )
        xp_keywords_text = "\n".join(
            str(item or "").strip()
            for item in extra_protection_data.get("custom_virus_keywords", [])
            if str(item or "").strip()
        )
        xp_delete_action = str(extra_protection_data.get("delete_action") or "warn").lower()
        extra_protection_form_html = f"""
        <section class="panel security-extra-protection-shell">
            <div class="panel-header">
                <div class="panel-title">
                    <h2 data-icon-key="extra_protection">Extra Protection Controls</h2>
                    <p>This page is fully separate from Anti-Nuke settings and uses its own configuration set.</p>
                </div>
            </div>
            <form method="post" action="/dashboard/guild/{current_guild['id']}/security" class="security-extra-protection-form">
                <input type="hidden" name="redirect_tab" value="extra_protection">
                <input type="hidden" name="security_action" value="extra_protection_save">

                <section class="panel-sub detail-page-section">
                    <h2 style="margin-top:0;" data-icon-key="security">Core Switches</h2>
                    <div class="ux-toggle-group detail-page-toggle-grid">
                        <label class="ux-toggle"><span class="ux-toggle-label">Enable Extra Protection</span><input type="checkbox" name="xp_enabled" {"checked" if extra_protection_data.get("enabled") else ""}><span class="ux-switch"></span></label>
                        <label class="ux-toggle"><span class="ux-toggle-label">Block bot invite / add</span><input type="checkbox" name="xp_block_bot_add_enabled" {"checked" if extra_protection_data.get("block_bot_add_enabled") else ""}><span class="ux-switch"></span></label>
                        <label class="ux-toggle"><span class="ux-toggle-label">Anti spam burst</span><input type="checkbox" name="xp_anti_spam_enabled" {"checked" if extra_protection_data.get("anti_spam_enabled") else ""}><span class="ux-switch"></span></label>
                        <label class="ux-toggle"><span class="ux-toggle-label">Anti mass mention</span><input type="checkbox" name="xp_anti_mass_mention_enabled" {"checked" if extra_protection_data.get("anti_mass_mention_enabled") else ""}><span class="ux-switch"></span></label>
                        <label class="ux-toggle"><span class="ux-toggle-label">Delete Discord invite links</span><input type="checkbox" name="xp_delete_discord_invite_enabled" {"checked" if extra_protection_data.get("delete_discord_invite_enabled") else ""}><span class="ux-switch"></span></label>
                        <label class="ux-toggle"><span class="ux-toggle-label">Delete scam / phishing links</span><input type="checkbox" name="xp_delete_scam_links_enabled" {"checked" if extra_protection_data.get("delete_scam_links_enabled") else ""}><span class="ux-switch"></span></label>
                        <label class="ux-toggle"><span class="ux-toggle-label">Detect virus keyword patterns</span><input type="checkbox" name="xp_anti_virus_keywords_enabled" {"checked" if extra_protection_data.get("anti_virus_keywords_enabled") else ""}><span class="ux-switch"></span></label>
                    </div>
                </section>

                <section class="panel-sub detail-page-section">
                    <h2 style="margin-top:0;" data-icon-key="moderation">Thresholds & Action</h2>
                    <div class="field-group detail-page-grid">
                        <div class="field-item">
                            <label>Spam limit (messages)</label>
                            <input type="number" min="3" max="30" name="xp_spam_message_limit" value="{_escape(extra_protection_data.get('spam_message_limit', 7))}">
                        </div>
                        <div class="field-item">
                            <label>Spam window (seconds)</label>
                            <input type="number" min="3" max="180" name="xp_spam_window_seconds" value="{_escape(extra_protection_data.get('spam_window_seconds', 12))}">
                        </div>
                        <div class="field-item">
                            <label>Mass mention limit</label>
                            <input type="number" min="2" max="30" name="xp_mass_mention_limit" value="{_escape(extra_protection_data.get('mass_mention_limit', 5))}">
                        </div>
                        <div class="field-item">
                            <label>Timeout duration (seconds)</label>
                            <input type="number" min="30" max="86400" name="xp_timeout_seconds" value="{_escape(extra_protection_data.get('timeout_seconds', 300))}">
                        </div>
                        <div class="field-item">
                            <label>Action on detection</label>
                            <select name="xp_delete_action">
                                <option value="none" {"selected" if xp_delete_action == "none" else ""}>None</option>
                                <option value="warn" {"selected" if xp_delete_action == "warn" else ""}>Warn</option>
                                <option value="mute" {"selected" if xp_delete_action == "mute" else ""}>Mute / Timeout</option>
                                <option value="kick" {"selected" if xp_delete_action == "kick" else ""}>Kick</option>
                                <option value="ban" {"selected" if xp_delete_action == "ban" else ""}>Ban</option>
                            </select>
                        </div>
                    </div>
                </section>

                <section class="panel-sub detail-page-section">
                    <h2 style="margin-top:0;" data-icon-key="members">Whitelist Manager</h2>
                    <div class="field-group detail-page-grid">
                        <div class="field-item">
                            <label>Allowed user IDs (one per line)</label>
                            <textarea name="xp_whitelist_user_ids_text" rows="6" placeholder="123456789012345678">{_escape(xp_whitelist_users_text)}</textarea>
                            <span class="muted" style="font-size:12px;">These users can add bots without being blocked by Extra Protection.</span>
                        </div>
                        <div class="field-item">
                            <label>Allowed bot IDs (one per line)</label>
                            <textarea name="xp_whitelist_bot_ids_text" rows="6" placeholder="123456789012345678">{_escape(xp_whitelist_bots_text)}</textarea>
                            <span class="muted" style="font-size:12px;">Only these bot IDs are exempt from bot-add blocking.</span>
                        </div>
                    </div>
                    <div class="field-group detail-page-grid">
                        <div class="field-item">
                            <label>Add user IDs</label>
                            <input type="text" name="xp_whitelist_user_add" placeholder="Comma / space separated IDs">
                        </div>
                        <div class="field-item">
                            <label>Remove user IDs</label>
                            <input type="text" name="xp_whitelist_user_remove" placeholder="Comma / space separated IDs">
                        </div>
                        <div class="field-item">
                            <label>Add bot IDs</label>
                            <input type="text" name="xp_whitelist_bot_add" placeholder="Comma / space separated IDs">
                        </div>
                        <div class="field-item">
                            <label>Remove bot IDs</label>
                            <input type="text" name="xp_whitelist_bot_remove" placeholder="Comma / space separated IDs">
                        </div>
                    </div>
                </section>

                <section class="panel-sub detail-page-section">
                    <h2 style="margin-top:0;" data-icon-key="scan">Virus / Scam Keywords</h2>
                    <div class="field-group">
                        <div class="field-item">
                            <label>Custom keywords (one per line)</label>
                            <textarea name="xp_custom_virus_keywords" rows="6" placeholder="free nitro&#10;token logger&#10;wallet connect">{_escape(xp_keywords_text)}</textarea>
                            <span class="muted" style="font-size:12px;">Custom keywords are matched with message content and URLs in real time.</span>
                        </div>
                    </div>
                </section>

                <div class="form-actions-inline security-submit-row">
                    <button class="primary-btn" type="submit">Save extra protection</button>
                    <a class="ghost-btn" href="/dashboard/guild/{current_guild['id']}/anti_raid">Open Anti-Raid page</a>
                </div>
            </form>
        </section>
        """
    general_settings_block = ""
    if active_tab_slug == "server_settings":
        general_settings_block = f"""
        <section class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <h2>การตั้งค่า</h2>
                    <p>ตั้งค่าคำนำหน้าและภาษาหลักของกิลด์</p>
                </div>
            </div>
            <form method="post" action="/dashboard/guild/{current_guild['id']}/general">
                <div class="field-group">
                    <div class="field-item">
                        <label>คำนำหน้า</label>
                        <input type="text" name="prefix" value="{_escape(guild_state.get('prefix', BOT_CONFIG.PREFIX))}" maxlength="5">
                    </div>
                    <div class="field-item">
                        <label>ภาษา</label>
                        <select name="language">
                            <option value="th" {"selected" if guild_language == "th" else ""}>Thai (TH)</option>
                            <option value="en" {"selected" if guild_language == "en" else ""}>English (EN)</option>
                        </select>
                    </div>
                </div>
                <div class="form-actions-inline">
                    <button class="primary-btn" type="submit">บันทึกการตั้งค่า</button>
                </div>
            </form>
        </section>
        <section class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <h2>สิทธิ์ผู้ดูแลแดชบอร์ด</h2>
                    <p>เจ้าของกิลด์สามารถกำหนดยศที่อนุญาตให้แก้ไขการตั้งค่าเซิร์ฟเวอร์ได้</p>
                </div>
            </div>
            {dashboard_roles_notice}
            <form method="post" action="/dashboard/guild/{current_guild['id']}/security">
                <input type="hidden" name="redirect_tab" value="{_escape(active_tab_slug)}">
                <input type="hidden" name="security_action" value="dashboard_editor_roles">
                <div class="field-group">
                    <div class="field-item">
                        <label>ยศที่แก้ไขการตั้งค่าได้</label>
                        {_render_multi_role_select("dashboard_editor_role_ids", bot_guild, dashboard_editor_role_ids)}
                        <span class="muted" style="font-size:12px;">ผู้ใช้ต้องมียศนี้และสิทธิ์ผู้ดูแลกิลด์หรือ Manage Guild จึงจะแก้ไขได้</span>
                    </div>
                </div>
                <div class="form-actions-inline">
                    <button class="primary-btn" type="submit" {dashboard_roles_disabled_attr}>บันทึกสิทธิ์ผู้ดูแล</button>
                </div>
            </form>
        </section>
        <section class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <h2>ปรับแต่งบอทในเซิร์ฟ</h2>
                    <p>เปลี่ยนชื่อเล่นและรูปโปรไฟล์ของบอทสำหรับกิลด์</p>
                </div>
            </div>
            {bot_profile_notice}
            <form method="post" action="/dashboard/guild/{current_guild['id']}/bot_profile" enctype="multipart/form-data" id="botProfileSettingsForm"
                  data-current-avatar="{bot_avatar_current}"
                  data-default-avatar="{bot_avatar_default}"
                  data-current-nick="{_escape(bot_nick_current_label)}"
                  data-default-nick="{_escape(bot_nick_default_label)}"
                  data-current-display="{_escape(bot_display_name_current)}"
                  data-default-display="{_escape(bot_display_name_default)}">
                <input type="hidden" name="bot_profile_action" value="save" id="botProfileActionInput">
                <div class="field-group">
                    <div class="field-item">
                        <label>การดำเนินการ</label>
                        <div id="botProfileActionSwitch" style="display:flex;flex-wrap:wrap;gap:8px;">
                            <button class="ghost-btn" type="button" data-profile-action="save" {bot_profile_disabled_attr}>บันทึกชื่อ/รูปใหม่</button>
                            <button class="ghost-btn" type="button" data-profile-action="reset_nickname" {bot_profile_disabled_attr}>รีเซ็ตชื่อเล่นบอทกลับค่าเดิม</button>
                            <button class="ghost-btn" type="button" data-profile-action="reset_avatar" {bot_profile_disabled_attr}>รีเซ็ตรูปโปรไฟล์เฉพาะกิลด์</button>
                        </div>
                        <span class="muted" style="font-size:12px;">เลือกโหมด แล้วดูพรีวิวก่อนกดยืนยัน</span>
                    </div>
                </div>
                <div class="field-group">
                    <div class="field-item">
                        <label>ชื่อบอทในเซิร์ฟ (ชื่อเล่น)</label>
                        <input type="text" name="bot_nickname" value="{_escape(bot_nick_current)}" maxlength="32" placeholder="เช่น บอทของฉัน" {bot_profile_disabled_attr}>
                        <span class="muted" style="font-size:12px;">ใส่ชื่อใหม่เพื่อเปลี่ยน | เว้นว่าง = ใช้ชื่อเดิม</span>
                    </div>
                    <div class="field-item">
                        <label>รูปโปรไฟล์บอทเฉพาะเซิร์ฟ</label>
                        <input type="file" name="bot_avatar_file" accept=".png,.jpg,.jpeg,.webp,.gif" {bot_profile_disabled_attr}>
                        <span class="muted" style="font-size:12px;">รองรับ PNG/JPG/WEBP/GIF ขนาดไม่เกิน 8MB</span>
                    </div>
                </div>
                <div class="field-group">
                    <div class="field-item" style="max-width:980px;">
                        <label>พรีวิวค่าเริ่มต้น/ปัจจุบัน ---&gt; ที่ผู้ใช้จะเปลี่ยน</label>
                        <div id="botProfilePreviewShell" style="padding:12px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.02);display:flex;flex-direction:column;gap:10px;">
                            <div style="display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:12px;align-items:stretch;">
                                <div style="display:flex;align-items:center;gap:12px;padding:10px;border:1px solid var(--line);border-radius:10px;min-width:0;overflow:hidden;">
                                    <img src="{bot_avatar_current}" alt="{_escape(bot_display_name_current)}" id="botProfilePreviewFromAvatar" width="54" height="54" style="width:54px;height:54px;min-width:54px;max-width:54px;min-height:54px;max-height:54px;flex:0 0 54px;display:block;border-radius:50%;object-fit:cover;object-position:center;border:1px solid var(--line);overflow:hidden;">
                                    <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
                                        <strong id="botProfilePreviewFromDisplay">{_escape(bot_display_name_current)}</strong>
                                        <span class="muted" id="botProfilePreviewFromNick" style="font-size:12px;">ชื่อเล่นในเซิร์ฟ: {_escape(bot_nick_current_label)}</span>
                                    </div>
                                </div>
                                <div aria-hidden="true" style="display:grid;place-items:center;font-size:22px;font-weight:700;opacity:.8;">→</div>
                                <div style="display:flex;align-items:center;gap:12px;padding:10px;border:1px solid var(--line);border-radius:10px;min-width:0;overflow:hidden;">
                                    <img src="{bot_avatar_current}" alt="{_escape(bot_display_name_current)}" id="botProfilePreviewToAvatar" width="54" height="54" style="width:54px;height:54px;min-width:54px;max-width:54px;min-height:54px;max-height:54px;flex:0 0 54px;display:block;border-radius:50%;object-fit:cover;object-position:center;border:1px solid var(--line);overflow:hidden;">
                                    <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
                                        <strong id="botProfilePreviewToDisplay">{_escape(bot_display_name_current)}</strong>
                                        <span class="muted" id="botProfilePreviewToNick" style="font-size:12px;">ชื่อเล่นในเซิร์ฟ: {_escape(bot_nick_current_label)}</span>
                                    </div>
                                </div>
                            </div>
                            <div id="botProfilePreviewMeta" class="muted" style="font-size:12px;">โหมด: บันทึกชื่อ/รูปใหม่</div>
                            <div id="botProfilePreviewFileLabel" class="muted" style="font-size:12px;"></div>
                        </div>
                    </div>
                </div>
                <div class="form-actions-inline">
                    <button class="primary-btn" type="submit" id="botProfileSubmitButton" {bot_profile_disabled_attr}>ยืนยันบันทึกชื่อ/รูปใหม่</button>
                </div>
            </form>
            <div id="botProfileConfirmModal" aria-hidden="true" style="display:none;position:fixed;inset:0;z-index:9999;background:rgba(7,10,16,.72);padding:16px;align-items:center;justify-content:center;">
                <div class="panel dashboard-modal" role="dialog" aria-modal="true" aria-label="ยืนยันการเปลี่ยนแปลงของบอท" style="width:min(720px,100%);margin:0;display:flex;flex-direction:column;gap:10px;">
                    <h3 id="botProfileConfirmTitle" style="margin:0;">ยืนยันก่อนบันทึก</h3>
                    <p class="muted" style="margin:0;line-height:1.6;">ตรวจสอบได้ทั้งรูปและชื่อก่อนส่งจริง (สรุปจาก -&gt; ค่าใหม่)</p>
                    <div style="display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:12px;align-items:stretch;">
                        <div style="display:flex;align-items:center;gap:12px;padding:10px;border:1px solid var(--line);border-radius:10px;min-width:0;overflow:hidden;">
                            <img src="{bot_avatar_current}" alt="{_escape(bot_display_name_current)}" id="botProfileConfirmFromAvatar" width="54" height="54" style="width:54px;height:54px;min-width:54px;max-width:54px;min-height:54px;max-height:54px;flex:0 0 54px;display:block;border-radius:50%;object-fit:cover;object-position:center;border:1px solid var(--line);overflow:hidden;">
                            <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
                                <strong id="botProfileConfirmFromDisplay">{_escape(bot_display_name_current)}</strong>
                                <span class="muted" id="botProfileConfirmFromNick" style="font-size:12px;">ชื่อเล่นในเซิร์ฟ: {_escape(bot_nick_current_label)}</span>
                            </div>
                        </div>
                        <div aria-hidden="true" style="display:grid;place-items:center;font-size:22px;font-weight:700;opacity:.8;">→</div>
                        <div style="display:flex;align-items:center;gap:12px;padding:10px;border:1px solid var(--line);border-radius:10px;min-width:0;overflow:hidden;">
                            <img src="{bot_avatar_current}" alt="{_escape(bot_display_name_current)}" id="botProfileConfirmToAvatar" width="54" height="54" style="width:54px;height:54px;min-width:54px;max-width:54px;min-height:54px;max-height:54px;flex:0 0 54px;display:block;border-radius:50%;object-fit:cover;object-position:center;border:1px solid var(--line);overflow:hidden;">
                            <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
                                <strong id="botProfileConfirmToDisplay">{_escape(bot_display_name_current)}</strong>
                                <span class="muted" id="botProfileConfirmToNick" style="font-size:12px;">ชื่อเล่นในเซิร์ฟ: {_escape(bot_nick_current_label)}</span>
                            </div>
                        </div>
                    </div>
                    <div id="botProfileConfirmActionText" class="muted" style="font-size:12px;">โหมด: บันทึกชื่อ/รูปใหม่</div>
                    <div id="botProfileConfirmFileText" class="muted" style="font-size:12px;"></div>
                    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px;">
                        <button id="botProfileConfirmCancelBtn" type="button" class="ghost-btn">ยกเลิก</button>
                        <button id="botProfileConfirmSubmitBtn" type="button" class="primary-btn">ยืนยันส่งจริง</button>
                    </div>
                </div>
            </div>
        </section>
        """

    security_extra_sections = f"""
        <section class="panel security-delast-shell">
            <div class="panel-header">
                <div class="panel-title">
                    <h2 data-icon-key="tools">สิทธิ์คำสั่งลบข้อความ (Delast)</h2>
                    <p>กำหนดรายชื่อผู้ใช้ที่ได้รับอนุญาตให้ใช้คำสั่ง <code>/delast_messc</code> เพิ่มเติมจากผู้ดูแลระบบ/เจ้าของเซิร์ฟเวอร์</p>
                </div>
            </div>
            {delast_access_notice}
            <form method="post" action="/dashboard/guild/{current_guild['id']}/security" class="security-delast-form">
                <input type="hidden" name="redirect_tab" value="{_escape(active_tab_slug)}">
                <input type="hidden" name="security_action" value="delast_access_users">
                <div class="field-group">
                    <div class="field-item">
                        <label>User ID ที่อนุญาต (1 บรรทัดต่อ 1 ID)</label>
                        <textarea name="delast_access_user_ids" rows="6" placeholder="เช่น\n123456789012345678\n234567890123456789" {delast_access_disabled_attr}>{_escape(delast_allowed_user_ids_text)}</textarea>
                        <span class="muted" style="font-size:12px;">ใส่เฉพาะตัวเลข User ID เท่านั้น (ระบบจะตัดค่าซ้ำให้อัตโนมัติ)</span>
                    </div>
                </div>
                <div class="notice security-delast-notice">
                    ลิมิตการลบต่อครั้งของแพ็กเกจปัจจุบัน: <strong>{delast_current_limit}</strong> ข้อความ
                    <span class="muted"> (Free 20 / Silver 40 / Gole 70 / Diamond 100 / Permanent 150)</span>
                </div>
                <div class="form-actions-inline">
                    <button class="primary-btn" type="submit" {delast_access_disabled_attr}>บันทึกรายชื่อผู้ใช้คำสั่งลบข้อความ</button>
                </div>
            </form>
        </section>
    """

    if active_tab_slug == "anti_raid":
        security_extra_sections = ""
    elif active_tab_slug == "extra_protection":
        security_extra_sections = extra_protection_form_html

    template_preview_user_name = json.dumps(str(preview_member_name or "Member"), ensure_ascii=False)
    template_preview_user_mention = json.dumps(f"@{preview_member_name}", ensure_ascii=False)
    template_preview_server_name = json.dumps(str(current_guild.get("name") or "Guild"), ensure_ascii=False)
    _preview_user_name = str(preview_member_name or "Member").strip() or "Member"
    _preview_server_name = str(current_guild.get("name") or "Guild").strip() or "Guild"
    security_mock_users_json = json.dumps(
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
    security_mock_servers_json = json.dumps(
        [
            {"id": "current", "label": f"{_preview_server_name} (Current)", "name": _preview_server_name},
        ],
        ensure_ascii=False,
    )

    body = _render_dashboard_f_template("security.html", locals())
    return _render_layout(
        title=f"SkylineBOT Security - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
