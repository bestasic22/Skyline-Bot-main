from __future__ import annotations

from typing import Any
from .. import dashboard_core as core
from skylinebot.utils.music_access import normalize_music_access_settings

def _render_music(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "music",
    title_override: str | None = None,
    description_override: str | None = None,
    show_settings_panel: bool = True,
    control_action_path: str | None = None,
    settings_action_path: str | None = None,
    compact_user_layout: bool = False,
) -> str:
    _core = core
    _plan_display_name = _core._plan_display_name
    _can_manage_music_settings = _core._can_manage_music_settings
    _can_adjust_default_music_volume = _core._can_adjust_default_music_volume
    _music_snapshot = _core._music_snapshot
    _escape = _core._escape
    _music_log_lines = _core._music_log_lines
    MUSIC_IDLE_IMAGE_ROUTE = _core.MUSIC_IDLE_IMAGE_ROUTE
    _channel_label = _core._channel_label
    _render_channel_select = _core._render_channel_select
    _render_multi_role_select = _core._render_multi_role_select
    SUBSCRIBE_PLAN_PATH = _core.SUBSCRIBE_PLAN_PATH
    style_urls = _core.style_urls
    _render_layout = _core._render_layout

    def _render_multi_entity_select(
        name: str,
        current_ids: list[Any] | None,
        options: list[tuple[str, str]],
        *,
        placeholder: str,
    ) -> str:
        selected_ids: list[str] = []
        seen: set[str] = set()
        for raw_value in list(current_ids or []):
            value = str(raw_value or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            selected_ids.append(value)

        option_map: dict[str, str] = {}
        for raw_id, raw_label in list(options or []):
            option_id = str(raw_id or "").strip()
            if not option_id or option_id in option_map:
                continue
            option_map[option_id] = str(raw_label or option_id).strip() or option_id

        tags_html = "".join(
            f'<div class="tag-pill" data-id="{_escape(item_id)}">{_escape(option_map.get(item_id, item_id))} '
            f'<span class="remove" onclick="removeTag(this, \'{_escape(name)}\')">&times;</span></div>'
            for item_id in selected_ids
        )
        select_options = [f'<option value="">{_escape(placeholder)}</option>']
        for option_id, label in option_map.items():
            if option_id in selected_ids:
                continue
            select_options.append(
                f'<option value="{_escape(option_id)}">{_escape(label)}</option>'
            )

        return f"""
        <div class="multi-role-select" id="multi_{_escape(name)}">
            <div class="tags-container" id="tags_{_escape(name)}">{tags_html}</div>
            <select class="tag-adder" onchange="addTag(this, '{_escape(name)}')">{"".join(select_options)}</select>
            <input type="hidden" name="{_escape(name)}" id="input_{_escape(name)}" value="{_escape(','.join(selected_ids))}">
        </div>
        """

    guild_language = str((state.get("guild") or {}).get("language") or "th").strip().lower()
    language = guild_language if guild_language in {"th", "en"} else "th"
    t = {
        "th": {
            "now_playing": "กำลังเล่นตอนนี้",
            "paused": "หยุดชั่วคราว",
            "playing": "กำลังเล่น",
            "offline": "ออฟไลน์",
            "no_song": "ยังไม่มีเพลงที่กำลังเล่น",
            "wait_play": "รอให้บอทเล่นเพลงในห้องเสียงก่อน",
            "voice": "ห้องเสียง",
            "queue": "คิว",
            "volume": "ระดับเสียง",
            "loop": "วนซ้ำ",
            "on": "เปิด",
            "off": "ปิด",
            "no_session": "ยังไม่มีเซสชันเพลงในกิลด์นี้ตอนนี้",
            "queue_list": "คิวเพลง",
            "queue_empty": "คิวเพลงว่าง",
            "recent_activity": "กิจกรรมล่าสุด",
            "controls": "ปุ่มควบคุมแบบเรียลไทม์",
            "controls_desc": "เพิ่มเพลงและควบคุมการเล่นจากหน้าเว็บได้ทันที",
            "add_song": "เพิ่มเพลง (ชื่อเพลงหรือ URL)",
            "add_placeholder": "เช่น dandelions หรือ https://...",
            "enqueue": "เพิ่มเข้าคิว",
            "toggle_play": "เล่น/พัก",
            "previous": "ก่อนหน้า",
            "skip": "ข้ามเพลง",
            "toggle_loop": "วนซ้ำ",
            "stop_leave": "หยุดและออก",
            "vol_down": "เสียง -10",
            "vol_up": "เสียง +10",
            "set_volume": "ตั้งระดับเสียง",
            "confirm_volume": "ยืนยันเสียง",
            "queue_table": "ตารางคิวเพลง",
            "remove": "ลบ",
            "play_now": "เล่นเลย",
            "queue_empty_table": "คิวว่างอยู่ตอนนี้",
            "music_profile": "ศูนย์ควบคุมเพลง (Music Control Center)",
            "default_volume": "ระดับเสียงเริ่มต้น",
            "default_repeat": "เปิดวนซ้ำเริ่มต้น",
            "default_autoplay": "เปิดเล่นต่ออัตโนมัติเริ่มต้น",
            "save_defaults": "บันทึกค่าเริ่มต้นเพลง",
            "setup_mode": "เปิดใช้งานระบบ Setup Music (ช่องส่งเพลงถาวร)",
            "setup_command_channel": "ห้องที่ไว้สั่งเพลง (Text Channel)",
            "setup_voice_channel": "ห้องเสียงที่บอทใช้ (Voice Channel)",
            "free_view_only": "แพ็กเกจ Free: หมวด /music settings ดูได้อย่างเดียว",
        },
        "en": {
            "now_playing": "Now Playing",
            "paused": "Paused",
            "playing": "Playing",
            "offline": "Offline",
            "no_song": "No track is playing",
            "wait_play": "Waiting for playback in voice channel",
            "voice": "Voice",
            "queue": "Queue",
            "volume": "Volume",
            "loop": "Loop",
            "on": "On",
            "off": "Off",
            "no_session": "No music session is active in this guild",
            "queue_list": "Queue",
            "queue_empty": "Queue is empty",
            "recent_activity": "Recent Activity",
            "controls": "Realtime Controls",
            "controls_desc": "Add tracks and control playback directly from this page",
            "add_song": "Add Song (name or URL)",
            "add_placeholder": "e.g. song name or https://...",
            "enqueue": "Add to Queue",
            "toggle_play": "Play/Pause",
            "previous": "Previous",
            "skip": "Skip",
            "toggle_loop": "Toggle Loop",
            "stop_leave": "Stop & Leave",
            "vol_down": "Vol -10",
            "vol_up": "Vol +10",
            "set_volume": "Set Volume",
            "confirm_volume": "Apply Volume",
            "queue_table": "Queue Table",
            "remove": "Remove",
            "play_now": "Play Now",
            "queue_empty_table": "Queue is currently empty",
            "music_profile": "Music Control Center",
            "default_volume": "Default Volume",
            "default_repeat": "Enable default repeat",
            "default_autoplay": "Enable default autoplay",
            "save_defaults": "Save Default Music",
            "setup_mode": "Enable Setup Music mode (persistent channel)",
            "setup_command_channel": "Command channel (Text)",
            "setup_voice_channel": "Voice channel for bot",
            "free_view_only": "Free plan: /music settings is view-only",
        },
    }[language]
    title_text = title_override or "เพลง (Music)"
    desc_text = description_override or t["controls_desc"]
    music_control_post_path = (
        control_action_path or f"/dashboard/guild/{current_guild['id']}/music/control"
    )
    music_settings_post_path = (
        settings_action_path or f"/dashboard/guild/{current_guild['id']}/music"
    )

    data = state["music"]
    guild_state = state.get("guild") or {}
    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    plan_name = _plan_display_name(plan_tier)
    can_manage_settings = _can_manage_music_settings(guild_state_for_plan)
    can_adjust_default_volume = _can_adjust_default_music_volume(guild_state_for_plan)

    current = _music_snapshot(bot_guild)
    queue_entries = current.get("queue_entries", [])
    queue_lines = "".join(f'<div class="mini-stat">{_escape(title)}</div>' for title in current.get("queue_titles", []))
    queue_cards = "".join(
        f"""
        <article class='music-queue-card'>
          <div>
            <h4>#{entry.get('index')} - {_escape(entry.get('title'))}</h4>
            <p>{_escape(entry.get('duration'))}</p>
          </div>
          <div class="music-queue-actions">
            <button class="queue-playnow-btn" type="button" data-queue-index="{entry.get('index')}">{t['play_now']}</button>
            <button class="queue-move-btn" type="button" data-move-direction="up" data-queue-index="{entry.get('index')}">↑</button>
            <button class="queue-move-btn" type="button" data-move-direction="down" data-queue-index="{entry.get('index')}">↓</button>
            <button class='queue-remove-btn' type='button' data-queue-index='{entry.get('index')}'>{t['remove']}</button>
          </div>
        </article>
        """
        for entry in queue_entries
    )
    music_logs = "\n".join(
        _escape(line)
        for line in _music_log_lines(
            guild_id=current_guild.get("id"),
            guild_name=current_guild.get("name"),
        )
    )
    setup_command_channel_id = data.get("music_setup_channel_id") or data.get("music_command_channel_id")
    setup_voice_channel_id = data.get("music_setup_voice_channel_id") or data.get("music_voice_channel_id")
    setup_enabled = bool(
        data.get("setup_music_mode")
        or (str(setup_command_channel_id or "").strip().isdigit() and str(setup_voice_channel_id or "").strip().isdigit())
    )
    default_volume = max(0, min(100, int(data.get("default_volume", 80) or 80)))
    music_access_policy = normalize_music_access_settings(data)
    music_usage_enabled = bool(music_access_policy.get("music_usage_enabled", True))
    music_usage_admin_only = bool(
        music_access_policy.get("music_usage_admin_only", False)
    )
    music_usage_restrict_enabled = bool(
        music_access_policy.get("music_usage_restrict_enabled", False)
    )
    music_usage_admin_bypass = bool(
        music_access_policy.get("music_usage_allow_admin_bypass", True)
    )
    music_usage_role_ids = list(music_access_policy.get("music_usage_role_ids") or [])
    music_usage_user_ids = list(music_access_policy.get("music_usage_user_ids") or [])
    music_usage_channel_ids = list(
        music_access_policy.get("music_usage_channel_ids") or []
    )
    music_usage_roles_input_html = _render_multi_role_select(
        "music_usage_role_ids", bot_guild, music_usage_role_ids
    )
    music_usage_user_options: list[tuple[str, str]] = []
    music_usage_channel_options: list[tuple[str, str]] = []
    if bot_guild:
        members = sorted(
            list(getattr(bot_guild, "members", []) or []),
            key=lambda member: str(
                getattr(member, "display_name", "")
                or getattr(member, "name", "")
                or getattr(member, "id", "")
            ).casefold(),
        )
        for member in members:
            if bool(getattr(member, "bot", False)):
                continue
            member_id = str(getattr(member, "id", "") or "").strip()
            if not member_id:
                continue
            display_name = str(
                getattr(member, "display_name", "")
                or getattr(member, "name", "")
                or member_id
            ).strip()
            username = str(getattr(member, "name", "") or "").strip()
            if username and display_name.casefold() != username.casefold():
                label = f"{display_name} (@{username})"
            else:
                label = display_name or member_id
            music_usage_user_options.append((member_id, label))

        sorted_channels = sorted(
            list(getattr(bot_guild, "channels", []) or []),
            key=lambda channel: (
                getattr(getattr(channel, "category", None), "position", -1),
                getattr(channel, "position", 0),
                str(getattr(channel, "name", "")).casefold(),
            ),
        )
        for channel in sorted_channels:
            channel_id = str(getattr(channel, "id", "") or "").strip()
            if not channel_id:
                continue
            channel_type = str(getattr(channel, "type", "") or "").strip().lower()
            if channel_type == "category":
                continue
            channel_name = str(getattr(channel, "name", "") or channel_id).strip() or channel_id
            if channel_type in {"text", "news", "forum"}:
                label = f"# {channel_name}"
            elif channel_type in {"voice", "stage_voice"}:
                label = f"[voice] {channel_name}"
            else:
                label = f"[{channel_type or 'channel'}] {channel_name}"
            music_usage_channel_options.append((channel_id, label))

    music_usage_users_input_html = _render_multi_entity_select(
        "music_usage_user_ids",
        music_usage_user_ids,
        music_usage_user_options,
        placeholder="เพิ่มผู้ใช้...",
    )
    music_usage_channels_input_html = _render_multi_entity_select(
        "music_usage_channel_ids",
        music_usage_channel_ids,
        music_usage_channel_options,
        placeholder="เพิ่มช่อง...",
    )
    music_usage_user_ids_csv = ",".join(music_usage_user_ids)
    music_usage_channel_ids_csv = ",".join(music_usage_channel_ids)
    music_artwork = _escape(current.get("artwork") or MUSIC_IDLE_IMAGE_ROUTE)
    channel_label = _channel_label(bot_guild, setup_command_channel_id)
    voice_label = _channel_label(bot_guild, setup_voice_channel_id)
    playlist_options = [
        ("thai_pop", "🇹🇭 Thai Pop"),
        ("chill", "🌙 Chill Mix"),
        ("lofi", "📚 Lo-Fi Study"),
        ("edm", "🎉 EDM Party"),
    ]
    playlist_options_html = "".join(
        f'<option value="{_escape(value)}">{_escape(label)}</option>'
        for value, label in playlist_options
    )

    now_state = t["offline"]
    if current.get("active"):
        now_state = t["paused"] if current.get("paused") else t["playing"]
    loop_state = t["on"] if current.get("loop") else t["off"]
    now_title = current.get("title") or t["no_song"]
    now_author = current.get("author") or t["wait_play"]

    settings_panel_inner = ""
    if not show_settings_panel:
        settings_panel_inner = """
            <div class="notice">โหมดผู้ใช้ทั่วไป: ใช้หน้านี้สำหรับควบคุมเพลงแบบเรียลไทม์เท่านั้น</div>
            <p class="muted" style="margin-top:10px;">การตั้งค่า Setup Music และค่าเริ่มต้นเพลงยังคงจัดการผ่านหน้าสำหรับแอดมิน</p>
        """
    elif can_manage_settings:
        settings_panel_inner = f"""
            <form method="post" action="{_escape(music_settings_post_path)}">
                <details class="panel-sub panel-collapsible" open>
                    <summary>
                        <strong> Setup Music</strong>
                        <span class="summary-sub">กำหนดช่องสั่งงานและห้องเสียงเริ่มต้นของระบบเพลง</span>
                    </summary>
                    <div class="panel-sub-body section-stack">
                        <label class="ux-toggle">
                            <span class="ux-toggle-label">{t['setup_mode']}</span>
                            <input id="setupMusicModeToggle" type="checkbox" name="setup_music_mode" {"checked" if setup_enabled else ""}>
                            <span class="ux-switch"></span>
                        </label>
                        <div id="musicSetupChannelsBlock" class="section-stack" style="display:{'grid' if setup_enabled else 'none'};">
                            <div class="field-item">
                                <label>{t['setup_command_channel']}</label>
                                {_render_channel_select("music_command_channel_id", bot_guild, setup_command_channel_id)}
                            </div>
                            <div class="field-item">
                                <label>{t['setup_voice_channel']}</label>
                                {_render_channel_select("music_voice_channel_id", bot_guild, setup_voice_channel_id, filter_types=['voice'])}
                            </div>
                        </div>
                    </div>
                </details>
                <details class="panel-sub panel-collapsible" open>
                    <summary>
                        <strong> ค่าเริ่มต้นการเล่น</strong>
                        <span class="summary-sub">ตั้งระดับเสียงและพฤติกรรมเริ่มต้นของระบบเพลง</span>
                    </summary>
                    <div class="panel-sub-body section-stack">
                        <div class="field-item">
                            <label>{t['default_volume']}</label>
                            <input type="number" min="0" max="100" name="default_volume" value="{default_volume}" {"disabled" if not can_adjust_default_volume else ""}>
                        </div>
                        <div class="ux-toggle-group" style="grid-template-columns: 1fr;">
                            <label class="ux-toggle">
                                <span class="ux-toggle-label">{t['default_repeat']}</span>
                                <input type="checkbox" name="default_repeat" {"checked" if data.get("default_repeat") else ""}>
                                <span class="ux-switch"></span>
                            </label>
                            <label class="ux-toggle">
                                <span class="ux-toggle-label">{t['default_autoplay']}</span>
                                <input type="checkbox" name="default_autoplay" {"checked" if data.get("default_autoplay") else ""}>
                                <span class="ux-switch"></span>
                            </label>
                        </div>
                    </div>
                </details>
                <details class="panel-sub panel-collapsible" open>
                    <summary>
                        <strong> Music Access Control</strong>
                        <span class="summary-sub">กำหนดว่าใครใช้ระบบเพลงได้บ้างผ่านหน้าเว็บ</span>
                    </summary>
                    <div class="panel-sub-body section-stack">
                        <label class="ux-toggle">
                            <span class="ux-toggle-label">เปิดใช้งานระบบเพลง</span>
                            <input type="checkbox" name="music_usage_enabled" {"checked" if music_usage_enabled else ""}>
                            <span class="ux-switch"></span>
                        </label>
                        <label class="ux-toggle">
                            <span class="ux-toggle-label">ให้ใช้ได้เฉพาะแอดมิน/เจ้าของ</span>
                            <input type="checkbox" name="music_usage_admin_only" {"checked" if music_usage_admin_only else ""}>
                            <span class="ux-switch"></span>
                        </label>
                        <label class="ux-toggle">
                            <span class="ux-toggle-label">จำกัดผู้ใช้แบบกำหนดรายการ</span>
                            <input id="musicUsageRestrictToggle" type="checkbox" name="music_usage_restrict_enabled" {"checked" if music_usage_restrict_enabled else ""}>
                            <span class="ux-switch"></span>
                        </label>
                        <label class="ux-toggle">
                            <span class="ux-toggle-label">ให้แอดมิน/เจ้าของข้ามข้อจำกัดได้</span>
                            <input type="checkbox" name="music_usage_allow_admin_bypass" {"checked" if music_usage_admin_bypass else ""}>
                            <span class="ux-switch"></span>
                        </label>
                        <div id="musicUsageRestrictionsBlock" class="section-stack" style="display:{'grid' if music_usage_restrict_enabled else 'none'};">
                            <div class="field-item">
                                <label>บทบาทที่อนุญาต</label>
                                {music_usage_roles_input_html}
                            </div>
                            <div class="field-item">
                                <label>ผู้ใช้ที่อนุญาต</label>
                                {music_usage_users_input_html}
                            </div>
                            <div class="field-item">
                                <label>ช่องที่อนุญาต</label>
                                {music_usage_channels_input_html}
                            </div>
                            <p class="muted">เลือกจากรายชื่อแล้วระบบจะบันทึก ID ให้อัตโนมัติ</p>
                        </div>
                    </div>
                </details>
                <div class="form-actions-fixed">
                    <button class="primary-btn" type="submit">{t['save_defaults']}</button>
                </div>
            </form>
        """
    else:
        settings_panel_inner = f"""
            <div class="notice">{t['free_view_only']}</div>
            <div style="margin-bottom:10px;">
                <a class="ghost-btn" href="{SUBSCRIBE_PLAN_PATH}">ซื้อพรีเมียมเพื่อใช้ฟีเจอร์นี้</a>
            </div>
            <details class="panel-sub panel-collapsible" open>
                <summary>
                        <strong> แพ็กเกจ Free (ดูค่าได้อย่างเดียว)</strong>
                        <span class="summary-sub">อัปเกรดแพ็กเกจเพื่อเปิดการตั้งค่าแบบเต็ม</span>
                </summary>
                <div class="panel-sub-body section-stack music-readonly-stack">
                    <label class="ux-toggle" style="pointer-events:none;opacity:.75;">
                        <span class="ux-toggle-label">{t['setup_mode']}</span>
                        <input type="checkbox" {"checked" if setup_enabled else ""} disabled>
                        <span class="ux-switch"></span>
                    </label>
                    <div id="musicSetupChannelsBlock" class="section-stack" style="display:{'grid' if setup_enabled else 'none'};">
                        <div class="field-item">
                            <label>{t['setup_command_channel']}</label>
                            {_render_channel_select("music_command_channel_id", bot_guild, setup_command_channel_id, disabled=True)}
                            <div class="mini-stat">{_escape(channel_label)}</div>
                        </div>
                        <div class="field-item">
                            <label>{t['setup_voice_channel']}</label>
                            {_render_channel_select("music_voice_channel_id", bot_guild, setup_voice_channel_id, filter_types=['voice'], disabled=True)}
                            <div class="mini-stat">{_escape(voice_label)}</div>
                        </div>
                    </div>
                    <div class="field-item">
                        <label>{t['default_volume']}</label>
                        <input type="number" min="0" max="100" value="{default_volume}" disabled>
                    </div>
                    <div class="field-item"><label>{t['default_repeat']}</label><div class="mini-stat">{t['on'] if data.get('default_repeat') else t['off']}</div></div>
                    <div class="field-item"><label>{t['default_autoplay']}</label><div class="mini-stat">{t['on'] if data.get('default_autoplay') else t['off']}</div></div>
                    <div class="field-item"><label>Music Enabled</label><div class="mini-stat">{t['on'] if music_usage_enabled else t['off']}</div></div>
                    <div class="field-item"><label>Admin/Owner only</label><div class="mini-stat">{t['on'] if music_usage_admin_only else t['off']}</div></div>
                    <div class="field-item"><label>Restricted list mode</label><div class="mini-stat">{t['on'] if music_usage_restrict_enabled else t['off']}</div></div>
                    <div class="field-item"><label>Admin bypass</label><div class="mini-stat">{t['on'] if music_usage_admin_bypass else t['off']}</div></div>
                    <div class="field-item"><label>Allowed roles</label><div class="mini-stat">{len(music_usage_role_ids)}</div></div>
                    <div class="field-item"><label>Allowed users</label><div class="mini-stat">{_escape(music_usage_user_ids_csv or '-')}</div></div>
                    <div class="field-item"><label>Allowed channels</label><div class="mini-stat">{_escape(music_usage_channel_ids_csv or '-')}</div></div>
                </div>
            </details>
        """

    settings_section_html = ""
    if show_settings_panel:
        settings_section_html = f"""
      <details class="panel-sub panel-collapsible" open>
        <summary>
          <strong>4)  {t['music_profile']}</strong>
          <span class="summary-sub">กำหนดค่า Default Setup Music ของเซิร์ฟ</span>
        </summary>
        <div class="panel-sub-body">
          {settings_panel_inner}
        </div>
      </details>
        """

    body = f"""
    <section class="panel section-stack">
      <div class="panel-header">
        <div class="panel-title">
                    <h1 data-i18n="tab_music">{_escape(title_text)}</h1>
                    <p>{_escape(desc_text)}</p>
        </div>
        <span class="plugin-premium-pill music-plan-chip">Plan: {_escape(plan_name)}</span>
      </div>

      <div class="guild-meta">
        <span class="pill">{t['queue']}: {current.get('queue_size', 0)}</span>
        <span class="pill">{t['volume']}: {current.get('volume', 0)}%</span>
        <span class="pill">{t['loop']}: {loop_state}</span>
      </div>

      <details class="panel-sub panel-collapsible" open>
        <summary>
          <strong>1) {t['now_playing']}</strong>
          <span class="summary-sub">{t['voice']}: {_escape(current.get('channel') or '-')}</span>
        </summary>
        <div class="panel-sub-body">
          <div class="music-now">
            <img class="music-artwork" data-live="music-artwork" src="{music_artwork}" alt="music artwork" onerror="this.onerror=null;this.src='{_escape(style_urls.DEFAULT_MUSIC_BANNER)}';">
            <div class="music-panel-card">
              <div class="pill" data-live="music-state">{now_state}</div>
              <h3 style="margin-top:10px;" data-live="music-title">{_escape(now_title)}</h3>
              <p class="muted" data-live="music-author">{_escape(now_author)}</p>
              <div class="pill" style="margin-top:10px;" data-live="music-channel">{t['voice']}: {_escape(current.get('channel') or '-')}</div>
              <p class="muted" style="margin-top:10px;" data-live="music-time">{_escape(current.get('position') or '0s')} / {_escape(current.get('duration') or '0s')}</p>
              <p class="muted" data-live="music-stats">{t['queue']}: {current.get('queue_size', 0)} | {t['volume']}: {current.get('volume', 0)}%</p>
              <p class="muted" data-live="music-loop-status">{t['loop']}: {loop_state}</p>
              <div class="notice" data-live="music-active-notice" style="margin-top:10px;{'display:none;' if current.get('active') else ''}">{t['no_session']}</div>
            </div>
          </div>
        </div>
      </details>

      <details class="panel-sub panel-collapsible" open>
        <summary>
          <strong>2) {t['controls']}</strong>
          <span class="summary-sub">{t['controls_desc']}</span>
        </summary>
        <div class="panel-sub-body">
          <div class="music-control-grid">
            <form id="musicQuickAddForm" method="post" action="{_escape(music_control_post_path)}">
              <input type="hidden" name="action" value="search_tracks">
              <div class="field-item">
                <label>{t['add_song']}</label>
                <div style="display:flex; gap:8px; flex-wrap:wrap;">
                  <input id="musicQueryInput" type="text" name="query" placeholder="{_escape(t['add_placeholder'])}" autocomplete="off">
                  <button class="primary-btn" type="submit" style="white-space:nowrap;">{t['enqueue']}</button>
                </div>
              </div>
            </form>
            <div class="music-search-results" data-live="music-search-results"></div>
            <div class="field-item">
              <label>เพลย์ลิสต์อัตโนมัติ (วนซ้ำ)</label>
              <div class="music-playlist-row">
                <select id="musicPlaylistSelect">{playlist_options_html}</select>
                <button id="musicAddPlaylistBtn" class="primary-btn" type="button">เพิ่มเพลย์ลิสต์</button>
              </div>
            </div>
            <div id="musicUserPlaylistsSection" class="field-item">
              <label>User Playlists (Cross-Guild)</label>
              <div class="music-user-playlist-toolbar">
                <select id="musicUserPlaylistSelect">
                  <option value="">Select playlist...</option>
                </select>
                <input id="musicUserPlaylistNameInput" type="text" placeholder="new playlist name">
                <button id="musicUserPlaylistCreateBtn" class="ux-btn" type="button">Create</button>
                <button id="musicUserPlaylistDeleteBtn" class="ux-btn" type="button">Delete</button>
              </div>
              <div class="music-user-playlist-toolbar">
                <input id="musicUserPlaylistItemInput" type="text" placeholder="song name or URL / youtube playlist URL">
                <button id="musicUserPlaylistAddItemBtn" class="primary-btn" type="button">Add Item</button>
                <button id="musicUserPlaylistRefreshBtn" class="ux-btn" type="button">Refresh</button>
              </div>
              <div class="music-user-playlist-toolbar">
                <input id="musicUserPlaylistPickInput" type="text" placeholder="indexes: 1, 1 3 5, 1-4">
                <button id="musicUserPlaylistRemoveItemsBtn" class="ux-btn" type="button">Remove Items</button>
                <button id="musicUserPlaylistPlayAllBtn" class="primary-btn" type="button">Play All</button>
                <button id="musicUserPlaylistPlaySelectedBtn" class="ux-btn" type="button">Play Selected</button>
              </div>
              <div class="mini-stat" data-live="music-user-playlist-quota">Playlist quota: -</div>
              <div class="music-user-playlist-items" data-live="music-user-playlist-items"></div>
            </div>
            <div class="music-action-row">
              <button class="ux-btn" type="button" data-music-action-btn data-action="pause_toggle">{t['toggle_play']}</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="previous">{t['previous']}</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="skip">{t['skip']}</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="loop_toggle" data-music-loop-btn>{t['toggle_loop']}</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="stop" style="color:#ff9696;">{t['stop_leave']}</button>
            </div>
            <div class="music-action-row">
              <button class="ux-btn" type="button" data-music-action-btn data-action="volume_down">{t['vol_down']}</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="volume_up">{t['vol_up']}</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="seek_backward">-10s</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="seek_forward">+10s</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="autoplay_toggle" data-music-autoplay-btn>Autoplay</button>
              <button class="ux-btn" type="button" data-music-action-btn data-action="shuffle_queue">Shuffle Queue</button>
            </div>
            <div class="music-action-row">
              <button class="ux-btn" type="button" data-music-ui-btn data-ui-action="open_queue">Queue</button>
              <button class="ux-btn" type="button" data-music-ui-btn data-ui-action="open_lyrics">Lyrics</button>
              <button class="ux-btn" type="button" data-music-ui-btn data-ui-action="save_current_track">Save</button>
              <button class="primary-btn" type="button" data-music-ui-btn data-ui-action="open_user_playlists">My Playlist</button>
            </div>
            <div class="field-item">
              <label>YouTube-style Seek Bar</label>
              <div class="music-seek-row">
                <input
                  id="musicSeekInput"
                  type="range"
                  min="0"
                  max="{max(0, int(current.get('duration_ms', 0) or 0))}"
                  value="{max(0, int(current.get('position_ms', 0) or 0))}"
                  step="1000"
                  data-live="music-seek-input"
                >
                <button id="musicSeekApplyBtn" class="ux-btn" type="button">Seek</button>
              </div>
            </div>
            <div class="field-group" style="margin-top:4px;">
              <div class="field-item">
                <label>{t['set_volume']}</label>
                <div style="display:flex; gap:8px; flex-wrap:wrap;">
                  <input id="musicVolumeInput" type="number" min="0" max="100" value="{_escape(current.get('volume', 80))}">
                  <button id="musicSetVolumeBtn" class="primary-btn" type="button" style="white-space:nowrap;">{t['confirm_volume']}</button>
                </div>
              </div>
            </div>
            <div class="music-feedback" data-live="music-feedback"></div>
          </div>
        </div>
      </details>

      <details id="musicQueueSection" class="panel-sub panel-collapsible" open>
        <summary>
          <strong>3) {t['queue_table']} + {t['recent_activity']}</strong>
          <span class="summary-sub">ตรวจสอบคิวและกิจกรรมล่าสุดแบบเรียลไทม์</span>
        </summary>
        <div class="panel-sub-body">
          <div class="guild-meta" data-live="music-queue">
            {queue_lines or f'<span class="mini-stat">{t["queue_empty"]}</span>'}
          </div>
          <div class="music-queue-cards" data-live="music-queue-cards">
            {queue_cards or f'<div class="music-queue-empty">{t["queue_empty_table"]}</div>'}
          </div>
          <div class="log-box" data-live="music-log-box" style="max-height:300px; font-size:0.85rem;">{music_logs}</div>
        </div>
      </details>

      {settings_section_html}
    </section>
    """
    return _render_layout(
        title=f"SkylineBOT Music - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
        compact_music_user_view=compact_user_layout,
    )
