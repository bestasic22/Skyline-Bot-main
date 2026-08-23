from __future__ import annotations

from typing import Any, Callable


def render_meter(
    label: str,
    value: int,
    maximum: int,
    tone: str,
    *,
    escape_fn: Callable[[Any], str],
) -> str:
    percentage = 0 if maximum <= 0 else max(0, min(100, int((value / maximum) * 100)))
    return (
        '<div class="meter">'
        f'<div class="meter-head"><span>{escape_fn(label)}</span><strong>{value}</strong></div>'
        f'<div class="meter-track {tone}"><div class="meter-fill" style="width:{percentage}%"></div></div>'
        "</div>"
    )


def render_channel_select(
    name: str,
    bot_guild: Any,
    current_id: Any,
    placeholder: str,
    *,
    filter_types: list[str] | None = None,
    disabled: bool = False,
    escape_fn: Callable[[Any], str],
) -> str:
    options = [f'<option value="">{escape_fn(placeholder)}</option>']
    filter_types = filter_types or ["text", "news", "forum"]
    filter_key = ",".join(str(item) for item in filter_types)
    if bot_guild:
        sorted_channels = sorted(
            bot_guild.channels,
            key=lambda c: (
                getattr(getattr(c, "category", None), "position", 0)
                if getattr(c, "category", None)
                else 0,
                c.position,
            ),
        )
        for channel in sorted_channels:
            ctype = str(getattr(channel, "type", ""))
            if ctype not in filter_types:
                continue

            selected = "selected" if str(channel.id) == str(current_id) else ""
            if ctype in ["text", "news", "forum"]:
                prefix = " # "
            elif ctype == "voice":
                prefix = "  "
            elif ctype == "category":
                prefix = "  "
            else:
                prefix = " - "
            options.append(
                f'<option value="{channel.id}" {selected}>{prefix} {escape_fn(channel.name)}</option>'
            )
    disabled_attr = " disabled" if disabled else ""
    return (
        f'<select name="{name}" data-live-options="channel" data-searchable-entity="channel" data-live-filter="{escape_fn(filter_key)}" '
        f'data-placeholder="{escape_fn(placeholder)}"{disabled_attr}>'
        + "".join(options)
        + "</select>"
    )


def render_multi_role_select(
    name: str,
    bot_guild: Any,
    current_ids: list[Any] | None,
    *,
    escape_fn: Callable[[Any], str],
) -> str:
    current_ids_text = [str(i) for i in (current_ids or []) if str(i).strip()]
    roles_map = {str(r.id): r.name for r in bot_guild.roles} if bot_guild else {}

    tags_html = "".join(
        [
            f'<div class="tag-pill" data-id="{rid}">{escape_fn(roles_map.get(rid, rid))} <span class="remove" onclick="removeTag(this, \'{name}\')">&times;</span></div>'
            for rid in current_ids_text
            if rid in roles_map
        ]
    )

    options = ['<option value="">เพิ่มยศ...</option>']
    if bot_guild:
        sorted_roles = sorted(bot_guild.roles, key=lambda r: r.position, reverse=True)
        for role in sorted_roles:
            if role.is_default():
                continue
            if str(role.id) in current_ids_text:
                continue
            options.append(f'<option value="{role.id}">@ {escape_fn(role.name)}</option>')

    return f"""
    <div class="multi-role-select" id="multi_{name}" data-live-options="role-multi" data-role-name="{escape_fn(name)}">
        <div class="tags-container" id="tags_{name}">{tags_html}</div>
        <select class="tag-adder" onchange="addTag(this, '{name}')">{"".join(options)}</select>
        <input type="hidden" name="{name}" id="input_{name}" value="{','.join(current_ids_text)}">
    </div>
    """


def render_role_select(
    name: str,
    bot_guild: Any,
    current_id: Any,
    placeholder: str,
    *,
    escape_fn: Callable[[Any], str],
) -> str:
    options = [f'<option value="">{escape_fn(placeholder)}</option>']
    if bot_guild:
        sorted_roles = sorted(bot_guild.roles, key=lambda r: r.position, reverse=True)
        for role in sorted_roles:
            if role.is_default():
                continue
            selected = "selected" if str(role.id) == str(current_id) else ""
            options.append(f'<option value="{role.id}" {selected}>@ {escape_fn(role.name)}</option>')
    return (
        f'<select name="{name}" data-live-options="role" data-searchable-entity="role" data-placeholder="{escape_fn(placeholder)}">'
        + "".join(options)
        + "</select>"
    )
