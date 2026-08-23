from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_giveaways(session: dict[str, Any], guilds: list[dict[str, Any]], current_guild: dict[str, Any], bot_guild: Any, state: dict[str, Any], notice: str | None = None) -> str:
    _core = core
    cache = _core.cache
    _giveaway_dashboard_settings_from_db = _core._giveaway_dashboard_settings_from_db
    _chart_block = _core._chart_block
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    permissions = state["giveaway_permissions"]
    active = cache.giveaways.get(str(current_guild["id"]), {})
    giveaway_settings = _giveaway_dashboard_settings_from_db(int(current_guild["id"]))
    default_channel_id = giveaway_settings.get("default_channel_id")
    default_duration = str(giveaway_settings.get("default_duration") or "1h")
    default_winners = int(giveaway_settings.get("default_winners") or 1)
    default_prize = str(giveaway_settings.get("default_prize") or "")
    embed_title = str(giveaway_settings.get("embed_title") or "🎉 กิจกรรมแจกของ")
    embed_description = str(giveaway_settings.get("embed_description") or "กดปุ่มเพื่อเข้าร่วมกิจกรรมลุ้นรางวัลได้เลย")
    embed_color = str(giveaway_settings.get("embed_color") or "#6b8cff")
    chart = _chart_block(
        "สถานะกิจกรรมแจกของ",
        [
            ("กำลังรัน", len(active), "violet"),
            ("สิ้นสุ", len([item for item in active.values() if item.get("ended")]), "amber"),
        ],
    )
    body = _render_dashboard_f_template("giveaways.html", locals())
    return _render_layout(title=f"SkylineBOT Giveaways - {current_guild['name']}", body=body, session=session, guilds=guilds, current_guild=current_guild, active_tab="giveaways", notice=notice)
