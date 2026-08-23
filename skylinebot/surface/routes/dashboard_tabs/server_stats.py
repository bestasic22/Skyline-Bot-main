from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_server_stats(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "server_stats",
    title_override: str | None = None,
    description_override: str | None = None,
) -> str:
    _core = core
    _plan_limits_from_guild_state = _core._plan_limits_from_guild_state
    _dashboard_effective_plan_tier = _core._dashboard_effective_plan_tier
    _escape = _core._escape
    _render_channel_select = _core._render_channel_select
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    data = state.get("server_stats") or {}
    title_text = title_override or "สถิติเซิร์ฟ (Server Stats)"
    desc_text = description_override or "แสดงสถิติแบบเรียลไทม์ผ่านชื่อห้องแชทอัตโนมัติ"
    configs = {c['type']: c for c in data.get('stats_configs', [])}
    guild_state = state.get("guild") or {}
    plan_tier = _dashboard_effective_plan_tier(state, session=session)
    guild_state_for_plan = dict(guild_state)
    guild_state_for_plan["subscription"] = plan_tier
    limits = _plan_limits_from_guild_state(guild_state_for_plan)
    max_stats_channels = int(limits.get("server_stats_channels", 4) or 4)
    enabled_count = len(data.get("stats_configs", []) or [])

    def get_config(t): return configs.get(t, {'channel_id': '', 'format': '', 'channel_name': ''})
    def is_enabled(t): return t in configs

    category_name = data.get('category_name', ' สถิติเซิร์ฟ')

    stat_definitions = [
        {'id': 'total_members', 'name': '👥 สมาชิกทั้งหมด', 'default_format': '╭・สมาชิกทั้งหมด: {Count}'},
        {'id': 'members', 'name': '👤 ผู้ใช้ (ไม่ใช่บอท)', 'default_format': '┃ สมาชิก: {Count}'},
        {'id': 'bots', 'name': '🤖 บอท', 'default_format': '╰・บอท: {Count}'},
        {'id': 'voice', 'name': '🔊 อยู่ในห้องเสียง', 'default_format': '🔊 ในห้องเสียง: {Count}'},
        {'id': 'boosts', 'name': '🚀 จำนวน Boost', 'default_format': '【boost: {Count}】'},
    ]

    status_definitions = [
        {'id': 'online', 'name': '🟢 ออนไลน์', 'default_format': '🟢 ออนไลน์: {Count}'},
        {'id': 'idle', 'name': '🌙 ไม่อยู่ (Idle)', 'default_format': '🌙 ไม่อยู่: {Count}'},
        {'id': 'dnd', 'name': '🔴 ห้ามรบกวน (DND)', 'default_format': '🔴 ห้ามรบกวน: {Count}'},
        {'id': 'offline', 'name': '⚪ ออฟไลน์', 'default_format': '⚪ ออฟไลน์: {Count}'},
    ]

    def render_stat_card(s):
        cfg = get_config(s['id'])
        checked = "checked" if is_enabled(s['id']) else ""
        ch_id = cfg.get('channel_id', '')
        fmt = _escape(cfg.get('format', s['default_format']))
        return f'''
        <div class="stat-card panel-sub">
            <div class="stat-card-header">
                <label class="ux-toggle-mini">
                    <input type="checkbox" name="stat_{s['id']}_enabled" {checked}>
                    <span class="ux-switch-mini"></span>
                    <strong>{s['name']}</strong>
                </label>
            </div>
            <div class="field-group" style="margin-top:10px;gap:8px;">
                <div class="field-item">
                    <label style="font-size:12px;color:var(--muted);">ช่องแสดง</label>
                    {_render_channel_select(f"stat_{s['id']}_channel", bot_guild, ch_id, filter_types=["voice"])}
                </div>
                <div class="field-item">
                    <label style="font-size:12px;color:var(--muted);">รูปแบบ (ใช้ {{Count}})</label>
                    <input type="text" name="stat_{s['id']}_format" value="{fmt}" placeholder="{s['default_format']}">
                </div>
            </div>
        </div>'''

    stat_cards = "".join(render_stat_card(s) for s in stat_definitions)
    status_cards = "".join(render_stat_card(s) for s in status_definitions)

    enabled_checked = "checked" if data.get("enabled") else ""
    enabled_val = "on" if data.get("enabled") else "off"
    content_display = "block" if data.get("enabled") else "none"
    body = _render_dashboard_f_template("server_stats.html", locals())
    return _render_layout(title=f"SkylineBOT Stats - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab=active_tab_slug, notice=notice)
