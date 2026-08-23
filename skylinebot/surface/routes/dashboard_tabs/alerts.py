from __future__ import annotations

from typing import Any

from .. import dashboard_core as core


_PLATFORM_ORDER: tuple[str, ...] = ("twitch", "youtube", "tiktok", "github", "facebook")
_TAB_TO_PLATFORM: dict[str, str] = {
    "alerts_twitch": "twitch",
    "alerts_youtube": "youtube",
    "alerts_tiktok": "tiktok",
    "alerts_github": "github",
    "alerts_facebook": "facebook",
}

_PLATFORM_META: dict[str, dict[str, str]] = {
    "twitch": {
        "label": "Twitch",
        "icon": '<i class="bi bi-twitch" aria-hidden="true"></i>',
        "title": "Twitch Alerts",
        "desc": "ติดตามสตรีมใหม่จาก Twitch และแจ้งเตือนเข้า Discord อัตโนมัติ",
        "source_label": "ช่อง Twitch ที่ต้องการติดตาม",
        "source_placeholder": "เช่น https://www.twitch.tv/your_channel",
    },
    "youtube": {
        "label": "YouTube",
        "icon": '<i class="bi bi-youtube" aria-hidden="true"></i>',
        "title": "YouTube Alerts",
        "desc": "แจ้งเตือนวิดีโอหรือไลฟ์ใหม่จาก YouTube เข้าเซิร์ฟเวอร์ของคุณ",
        "source_label": "ช่อง YouTube ที่ต้องการติดตาม",
        "source_placeholder": "เช่น https://www.youtube.com/@channel",
    },
    "tiktok": {
        "label": "TikTok",
        "icon": '<i class="bi bi-tiktok" aria-hidden="true"></i>',
        "title": "TikTok Alerts",
        "desc": "ติดตามโพสต์ใหม่จาก TikTok และแจ้งเตือนแบบเรียลไทม์",
        "source_label": "บัญชี TikTok ที่ต้องการติดตาม",
        "source_placeholder": "เช่น https://www.tiktok.com/@username",
    },
    "github": {
        "label": "GitHub",
        "icon": '<i class="bi bi-github" aria-hidden="true"></i>',
        "title": "GitHub Alerts",
        "desc": "ติดตามกิจกรรม repository (release/commit) และแจ้งเตือนเข้า Discord",
        "source_label": "Repository GitHub ที่ต้องการติดตาม",
        "source_placeholder": "เช่น https://github.com/owner/repo",
    },
    "facebook": {
        "label": "Facebook",
        "icon": '<i class="bi bi-facebook" aria-hidden="true"></i>',
        "title": "Facebook Alerts",
        "desc": "ติดตามโพสต์ใหม่จากเพจ Facebook แล้วแจ้งเตือนอัตโนมัติ",
        "source_label": "เพจ Facebook ที่ต้องการติดตาม",
        "source_placeholder": "เช่น https://www.facebook.com/page.name",
    },
}


def _render_alerts(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "alerts",
) -> str:
    _core = core
    _normalize_alerts_settings = _core._normalize_alerts_settings
    _escape = _core._escape
    json = _core.json
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    data = _normalize_alerts_settings(state.get("alerts") or {})
    platforms = data.get("platforms") or {}
    mention_role_ids = data.get("mention_role_ids") or []
    active_tab_slug = str(active_tab_slug or "alerts").strip().lower()
    active_platform_key = _TAB_TO_PLATFORM.get(active_tab_slug)
    managed_platform_keys = [active_platform_key] if active_platform_key else list(_PLATFORM_ORDER)

    def _platform_checked(platform_key: str) -> str:
        return "checked" if platforms.get(platform_key, {}).get("enabled") else ""

    channel_options = ['<option value="">เลือกห้องแชท</option>']
    if bot_guild:
        sorted_channels = sorted(
            bot_guild.channels,
            key=lambda ch: (
                getattr(ch, "category", None).position if getattr(ch, "category", None) else 0,
                ch.position,
            ),
        )
        for channel in sorted_channels:
            channel_type = str(getattr(channel, "type", ""))
            if channel_type not in {"text", "news"}:
                continue
            channel_options.append(f'<option value="{channel.id}"># {_escape(channel.name)}</option>')
    channel_options_html = "".join(channel_options)

    platform_seed = {key: platforms.get(key, {}).get("entries", []) for key in _PLATFORM_ORDER}
    platform_seed_json = json.dumps(platform_seed, ensure_ascii=False)
    managed_platform_keys_json = json.dumps(managed_platform_keys, ensure_ascii=False)

    def _platform_block_html(platform_key: str) -> str:
        meta = _PLATFORM_META.get(platform_key, {"label": platform_key.title(), "icon": '<i class="bi bi-bell" aria-hidden="true"></i>'})
        label = str(meta.get("label") or platform_key.title())
        icon = str(meta.get("icon") or '<i class="bi bi-bell" aria-hidden="true"></i>')
        source_label = str(meta.get("source_label") or f"รายการ {label}")
        source_placeholder = str(meta.get("source_placeholder") or "วางลิงก์แหล่งข้อมูล")
        template_value = _escape(platforms.get(platform_key, {}).get("message_template") or "{platform}: {title} {url}")
        open_attr = "open" if platforms.get(platform_key, {}).get("enabled") else ""
        return f"""
        <details class="command-category alerts-platform-card alerts-platform-{platform_key}" data-platform="{platform_key}" {open_attr} style="margin-bottom:10px;">
          <summary>
            <span class="alerts-platform-title"><span class="alerts-platform-icon">{icon}</span><span>{_escape(label)} Alerts</span></span>
            <label class="ux-toggle" style="padding:0;border:0;background:transparent;">
              <input type="checkbox" name="{platform_key}_enabled" {_platform_checked(platform_key)} data-alert-toggle>
              <span class="ux-switch"></span>
            </label>
          </summary>
          <div class="command-category-body" style="display:grid;padding:10px 14px 14px;">
            <div class="field-item">
              <label>{_escape(source_label)}</label>
              <div class="alerts-help muted" style="margin:0 0 8px;">ตัวอย่าง: {_escape(source_placeholder)}</div>
              <div id="entries_{platform_key}" class="alerts-entry-list"></div>
              <button type="button" class="ghost-btn alerts-add-entry-btn" data-add-entry="{platform_key}">+ เพิ่มรายการ {label}</button>
            </div>
            <div class="field-item">
              <label>รูปแบบข้อความแจ้งเตือน</label>
              <input type="text" name="{platform_key}_template" value="{template_value}" maxlength="300">
            </div>
            <input type="hidden" name="{platform_key}_entries_json" id="entries_json_{platform_key}">
          </div>
        </details>
        """

    platform_sections_html = "".join(_platform_block_html(key) for key in managed_platform_keys)
    platform_test_buttons_html = "".join(
        (
            f'<form method="post" action="/dashboard/guild/{current_guild["id"]}/alerts/test" class="alerts-test-form">'
            f'<input type="hidden" name="platform" value="{_escape(key)}">'
            f'<input type="hidden" name="active_tab_slug" value="{_escape(active_tab_slug)}">'
            f'<button type="submit" class="ghost-btn alerts-test-btn alerts-test-btn-{_escape(key)}"><span class="alerts-platform-icon">{_PLATFORM_META.get(key, {}).get("icon", "")}</span><span>ทดสอบ {_escape(_PLATFORM_META.get(key, {}).get("label", key.title()))}</span></button>'
            f"</form>"
        )
        for key in managed_platform_keys
    )

    if active_platform_key:
        active_meta = _PLATFORM_META.get(active_platform_key, {})
        hero_title = str(active_meta.get("title") or "Social Alerts")
        hero_desc = str(active_meta.get("desc") or "")
        hero_badges_html = '<span class="plugin-premium-pill">พรีเมียม</span><span class="plugin-badge-new">ใหม่</span>'
        save_notice = f"บันทึกการตั้งค่าเฉพาะ {active_meta.get('label', active_platform_key)}"
    else:
        hero_title = "Social Alerts"
        hero_desc = "ตั้งค่าระบบแจ้งเตือน Twitch, YouTube, TikTok, GitHub และ Facebook แบบแยกแพลตฟอร์ม"
        hero_badges_html = '<span class="plugin-premium-pill">พรีเมียม</span><span class="plugin-badge-new">รวมทุกแพลตฟอร์ม</span>'
        save_notice = "บันทึกการตั้งค่าทุกแพลตฟอร์ม"

    body = _render_dashboard_f_template("alerts.html", locals())
    return _render_layout(
        title=f"SkylineBOT Alerts - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
