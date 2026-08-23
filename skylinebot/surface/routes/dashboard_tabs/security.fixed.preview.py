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
    _can_use_antinuke_custom = _core._can_use_antinuke_custom
    _plan_display_name = _core._plan_display_name
    _allowed_antinuke_punishments = _core._allowed_antinuke_punishments
    SUBSCRIBE_PLAN_PATH = _core.SUBSCRIBE_PLAN_PATH
    _is_plan_at_least = _core._is_plan_at_least
    get_bot = _core.get_bot
    _discord_default_avatar_url = _core._discord_default_avatar_url
    _escape = _core._escape
    _with_cache_bust = _core._with_cache_bust
    _dashboard_editor_role_ids_from_db = _core._dashboard_editor_role_ids_from_db
    BOT_CONFIG = _core.BOT_CONFIG
    _render_multi_role_select = _core._render_multi_role_select
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _render_layout = _core._render_layout
    data = state["antinuke"]
    guild_state = state.get("guild") or {}
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    can_use_custom = _can_use_antinuke_custom(guild_state_for_plan)
    plan_name = _plan_display_name(plan_tier)
    allowed = _allowed_antinuke_punishments(guild_state_for_plan)

    selected_type = (data.get("type") or "normal").lower()
    if selected_type == "extream":
        selected_type = "extreme"
    if selected_type == "custom" and not can_use_custom:
        selected_type = "normal"

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
    can_customize_bot_profile = _is_plan_at_least(plan_tier, "silver")
    bot_member = getattr(bot_guild, "me", None) if bot_guild else None
    bot_nick_current = str(getattr(bot_member, "nick", "") or "").strip()
    bot_display_name_current = str(getattr(bot_member, "display_name", "") or "").strip()
    if not bot_display_name_current:
        bot_display_name_current = str(getattr(getattr(get_bot(), "user", None), "display_name", "") or "SkylineBOT").strip()
    bot_avatar_current_raw = (
        str(getattr(getattr(bot_member, "display_avatar", None), "url", "") or "").strip()
        or str(getattr(getattr(getattr(get_bot(), "user", None), "display_avatar", None), "url", "") or "").strip()
        or _discord_default_avatar_url(current_guild.get("id", "0"))
    )
    bot_avatar_current = _escape(_with_cache_bust(bot_avatar_current_raw, bucket_seconds=180))
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
                            <option value="th" selected>ไทย</option>
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
            <form method="post" action="/dashboard/guild/{current_guild['id']}/bot_profile" enctype="multipart/form-data">
                <input type="hidden" name="bot_profile_action" value="save">
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
                    <div class="field-item" style="max-width:380px;">
                        <label>สถานะปัจจุบัน</label>
                        <div style="display:flex;align-items:center;gap:12px;padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.02);">
                            <img src="{bot_avatar_current}" alt="{_escape(bot_display_name_current)}" style="width:54px;height:54px;border-radius:50%;object-fit:cover;border:1px solid var(--line);">
                            <div style="display:flex;flex-direction:column;gap:2px;">
                                <strong>{_escape(bot_display_name_current)}</strong>
                                <span class="muted" style="font-size:12px;">ชื่อ: {_escape(bot_nick_current or 'ยังไม่ตั้ง')}</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="form-actions-inline">
                    <button class="primary-btn" type="submit" {bot_profile_disabled_attr}>บันทึกการปรับแต่งบอท</button>
                </div>
            </form>
            <div class="form-actions-inline" style="margin-top:10px;gap:8px;flex-wrap:wrap;">
                <form method="post" action="/dashboard/guild/{current_guild['id']}/bot_profile" style="display:inline-block;margin:0;">
                    <input type="hidden" name="bot_profile_action" value="reset_nickname">
                    <button class="ghost-btn" type="submit" {bot_profile_disabled_attr}>รีเซ็ตชื่อเล่นบอทกลับค่าเดิม</button>
                </form>
                <form method="post" action="/dashboard/guild/{current_guild['id']}/bot_profile" style="display:inline-block;margin:0;">
                    <input type="hidden" name="bot_profile_action" value="reset_avatar">
                    <button class="ghost-btn" type="submit" {bot_profile_disabled_attr}>รีเซ็ตรูปโปรไฟล์เฉพาะกิลด์</button>
                </form>
            </div>
        </section>
        """

    body = f"""
    <div class="section-stack">
        <section class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <h1 data-i18n="tab_security">{_escape(title_text)}</h1>
                    <p>{_escape(desc_text)}</p>
                </div>
                <span class="plugin-premium-pill">Plan: {_escape(plan_name)}</span>
            </div>
            {premium_notice}
            <form method="post" action="/dashboard/guild/{current_guild['id']}/security" id="securitySettingsForm" data-plan="{_escape(plan_tier)}">
                <input type="hidden" name="redirect_tab" value="{_escape(active_tab_slug)}">
                <div class="field-group">
                    <div class="field-item">
                        <label>โหมดป้องกัน</label>
                        <select name="type" id="antinukeModeSelect">
                            <option value="normal" {"selected" if selected_type == "normal" else ""}>ปกติ (Normal)</option>
                            <option value="extreme" {"selected" if selected_type == "extreme" else ""}>เข้มงวด (Extreme)</option>
                            {custom_option}
                        </select>
                    </div>
                    <div class="field-item">
                        <label>ยศที่ข้ามการตรวจสอบ (Bypass Roles)</label>
                        {_render_multi_role_select("bypass_role_ids", bot_guild, bypass_ids)}
                        <span class="muted" style="font-size:12px;">รองรับหลายยศ</span>
                    </div>
                </div>

                <div class="ux-toggle-group">
                    <label class="ux-toggle"><span class="ux-toggle-label">เปิดใช้งาน Anti-Nuke</span><input type="checkbox" name="enabled" {"checked" if data.get("enabled") else ""}><span class="ux-switch"></span></label>
                    <label class="ux-toggle"><span class="ux-toggle-label">บล็อกบอทที่ไม่ได้รับอนุญาต</span><input type="checkbox" name="anti_bot_add" {"checked" if data.get("anti_bot_add") else ""}><span class="ux-switch"></span></label>
                    <label class="ux-toggle"><span class="ux-toggle-label">ป้องกันลบช่อง</span><input type="checkbox" name="anti_channel_delete" {"checked" if data.get("anti_channel_delete") else ""}><span class="ux-switch"></span></label>
                    <label class="ux-toggle"><span class="ux-toggle-label">ป้องกันการลบบบา</span><input type="checkbox" name="anti_role_delete" {"checked" if data.get("anti_role_delete") else ""}><span class="ux-switch"></span></label>
                    <label class="ux-toggle"><span class="ux-toggle-label">ป้องกันการสร้างเว็บฮุก</span><input type="checkbox" name="anti_webhook_create" {"checked" if data.get("anti_webhook_create") else ""}><span class="ux-switch"></span></label>
                    <label class="ux-toggle"><span class="ux-toggle-label">ป้องกันการแ @everyone</span><input type="checkbox" name="anti_everyone_mention" {"checked" if data.get("anti_everyone_mention") else ""}><span class="ux-switch"></span></label>
                </div>

                <div class="field-group">
                    <div class="field-item"><label>บลงโษ (Anti Bot Add)</label>{punishment_select("anti_bot_add_punishment", data.get("anti_bot_add_punishment"))}</div>
                    <div class="field-item"><label>จำกัดจำนวน (บอท)</label><input type="number" min="1" max="20" name="anti_bot_add_limit" value="{_escape(data.get('anti_bot_add_limit', 1))}"></div>
                    <div class="field-item"><label>บลงโษ (Anti Channel Delete)</label>{punishment_select("anti_channel_delete_punishment", data.get("anti_channel_delete_punishment"))}</div>
                    <div class="field-item"><label>จำกัดจำนวน (ลบช่อง)</label><input type="number" min="1" max="20" name="anti_channel_delete_limit" value="{_escape(data.get('anti_channel_delete_limit', 1))}"></div>
                    <div class="field-item"><label>บลงโษ (Anti Role Delete)</label>{punishment_select("anti_role_delete_punishment", data.get("anti_role_delete_punishment"))}</div>
                    <div class="field-item"><label>จำกัดจำนวน (ลบบทบาท)</label><input type="number" min="1" max="20" name="anti_role_delete_limit" value="{_escape(data.get('anti_role_delete_limit', 1))}"></div>
                    <div class="field-item"><label>บลงโษ (Anti Webhook Create)</label>{punishment_select("anti_webhook_create_punishment", data.get("anti_webhook_create_punishment"))}</div>
                    <div class="field-item"><label>จำกัดจำนวน (เว็บฮุก)</label><input type="number" min="1" max="20" name="anti_webhook_create_limit" value="{_escape(data.get('anti_webhook_create_limit', 1))}"></div>
                    <div class="field-item"><label>บลงโษ (Anti Everyone Mention)</label>{punishment_select("anti_everyone_mention_punishment", data.get("anti_everyone_mention_punishment"))}</div>
                    <div class="field-item"><label>จำกัดจำนวน (@everyone)</label><input type="number" min="1" max="20" name="anti_everyone_mention_limit" value="{_escape(data.get('anti_everyone_mention_limit', 1))}"></div>
                </div>

                <p class="muted" id="securityPlanHint" style="margin:4px 0 12px;display:none;">แพ็กเกจปัจจุบันยังไม่รองรับบทลงโทษขั้นสูง</p>
                <div class="form-actions-inline">
                    <button class="primary-btn" type="submit" data-save-btn="security">บันทึกการตั้งค่า</button>
                </div>
            </form>
        </section>
        <section class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <h2>สิทธิ์คำสั่งลบข้อความ (Delast)</h2>
                    <p>กำหนดรายชื่อผู้ใช้ที่ได้รับอนุญาตให้ใช้คำสั่ง <code>/delast_messc</code> เพิ่มเติมจากผู้ดูแลระบบ/เจ้าของเซิร์ฟเวอร์</p>
                </div>
            </div>
            {delast_access_notice}
            <form method="post" action="/dashboard/guild/{current_guild['id']}/security">
                <input type="hidden" name="redirect_tab" value="{_escape(active_tab_slug)}">
                <input type="hidden" name="security_action" value="delast_access_users">
                <div class="field-group">
                    <div class="field-item">
                        <label>User ID ที่อนุญาต (1 บรรทัดต่อ 1 ID)</label>
                        <textarea name="delast_access_user_ids" rows="6" placeholder="เช่น\n123456789012345678\n234567890123456789" {delast_access_disabled_attr}>{_escape(delast_allowed_user_ids_text)}</textarea>
                        <span class="muted" style="font-size:12px;">ใส่เฉพาะตัวเลข User ID เท่านั้น (ระบบจะตัดค่าซ้ำให้อัตโนมัติ)</span>
                    </div>
                </div>
                <div class="notice" style="margin:8px 0 12px;">
                    ลิมิตการลบต่อครั้งของแพ็กเกจปัจจุบัน: <strong>{delast_current_limit}</strong> ข้อความ
                    <span class="muted"> (Free 20 / Silver 40 / Gole 70 / Diamond 100 / Permanent 150)</span>
                </div>
                <div class="form-actions-inline">
                    <button class="primary-btn" type="submit" {delast_access_disabled_attr}>บันทึกรายชื่อผู้ใช้คำสั่งลบข้อความ</button>
                </div>
            </form>
        </section>
        {general_settings_block}
    </div>
    <script>
      (() => {{
        const form = document.getElementById('securitySettingsForm');
        if (!form) return;
        const plan = String(form.dataset.plan || 'free');
        const rank = {{ free: 0, silver: 1, golden: 2, diamond: 3, permanent: 4 }};
        const saveBtn = form.querySelector('[data-save-btn="security"]');
        const hint = form.querySelector('#securityPlanHint');
        const selects = form.querySelectorAll('select.punishment-select');

        const validate = () => {{
          let blocked = false;
          selects.forEach((select) => {{
            const selected = select.options[select.selectedIndex];
            if (!selected) return;
            const min = String(selected.dataset.minPlan || 'free');
            if ((rank[plan] ?? 0) < (rank[min] ?? 0)) blocked = true;
          }});
          if (saveBtn) saveBtn.disabled = blocked;
          if (hint) hint.style.display = blocked ? 'block' : 'none';
          return !blocked;
        }};

        selects.forEach((select) => select.addEventListener('change', validate));
        form.addEventListener('submit', (event) => {{
          if (!validate()) {{
            event.preventDefault();
            alert('แพ็กเกจปัจจุบันยังไม่รองรับระดับนี้');
          }}
        }});
        validate();
      }})();
    </script>
    """
    return _render_layout(
        title=f"SkylineBOT Security - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
