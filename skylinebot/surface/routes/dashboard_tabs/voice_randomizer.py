from __future__ import annotations

from typing import Any

from .. import dashboard_core as core


def _sorted_voice_categories(bot_guild: Any) -> list[Any]:
    if not bot_guild:
        return []
    voice_category_ids = {
        int(getattr(channel, "category_id", 0) or 0)
        for channel in list(getattr(bot_guild, "voice_channels", []) or [])
        if int(getattr(channel, "category_id", 0) or 0) > 0
    }
    rows: list[Any] = []
    for category in sorted(list(getattr(bot_guild, "categories", []) or []), key=lambda item: int(getattr(item, "position", 0) or 0)):
        cid = int(getattr(category, "id", 0) or 0)
        if cid <= 0:
            continue
        if cid not in voice_category_ids:
            continue
        rows.append(category)
    return rows


def _render_multi_category_select(bot_guild: Any, selected_ids: list[str]) -> str:
    _escape = core._escape
    selected_text = [str(item) for item in (selected_ids or []) if str(item).isdigit()]
    category_map = {str(int(getattr(category, "id", 0) or 0)): str(getattr(category, "name", "Category")) for category in _sorted_voice_categories(bot_guild)}

    tags_html = "".join(
        f'<div class="tag-pill" data-id="{cid}">{_escape(category_map.get(cid, cid))} <span class="remove" onclick="removeTag(this, \'allowed_category_ids\')">&times;</span></div>'
        for cid in selected_text
        if cid in category_map
    )

    options = ['<option value="">Add category...</option>']
    for cid, name in category_map.items():
        if cid in selected_text:
            continue
        options.append(f'<option value="{cid}">{_escape(name)}</option>')

    return (
        '<div class="multi-role-select" id="multi_allowed_category_ids">'
        f'<div class="tags-container" id="tags_allowed_category_ids">{tags_html}</div>'
        f'<select class="tag-adder" onchange="addTag(this, \'allowed_category_ids\')">{"".join(options)}</select>'
        f'<input type="hidden" name="allowed_category_ids" id="input_allowed_category_ids" value="{_escape(",".join(selected_text))}">'
        "</div>"
    )


def _render_default_category_select(bot_guild: Any, current_id: str) -> str:
    _escape = core._escape
    options = ['<option value="">Auto (first allowed category)</option>']
    for category in _sorted_voice_categories(bot_guild):
        cid = str(int(getattr(category, "id", 0) or 0))
        selected = "selected" if cid == str(current_id or "") else ""
        options.append(f'<option value="{cid}" {selected}>{_escape(str(getattr(category, "name", "Category")))}</option>')
    return f'<select name="default_category_id">{"".join(options)}</select>'


def _render_voice_randomizer(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    active_tab_slug: str = "voice_randomizer",
) -> str:
    _core = core
    _normalize_voice_randomizer_settings = _core._normalize_voice_randomizer_settings
    _render_channel_select = _core._render_channel_select
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    data = _normalize_voice_randomizer_settings(state.get("voice_randomizer") or {})
    allowed_categories_select_html = _render_multi_category_select(bot_guild, data.get("allowed_category_ids") or [])
    default_category_select_html = _render_default_category_select(bot_guild, str(data.get("default_category_id") or ""))
    room_modes = [
        ("normal", "Normal room (all)"),
        ("occupied", "Room with users"),
        ("empty", "Empty room"),
    ]
    selected_room_mode = str(data.get("room_mode") or "normal")
    selected_button_color = str(data.get("button_color") or "green").strip().lower()
    if selected_button_color not in {"green", "blurple", "red", "gray"}:
        selected_button_color = "green"
    room_mode_options_html = "".join(
        f'<option value="{value}" {"selected" if selected_room_mode == value else ""}>{_core._escape(label)}</option>'
        for value, label in room_modes
    )

    body = _render_dashboard_f_template("voice_randomizer.html", locals())
    return _render_layout(
        title=f"SkylineBOT Voice Randomizer - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
