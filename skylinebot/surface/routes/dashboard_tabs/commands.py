from __future__ import annotations

from typing import Any
from .. import dashboard_core as core


def _render_commands(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "commands",
) -> str:
    _core = core
    _plan_display_name = _core._plan_display_name
    _command_catalog = _core._command_catalog
    _required_plan_for_command = _core._required_plan_for_command
    _is_plan_at_least = _core._is_plan_at_least
    _escape = _core._escape
    SUBSCRIBE_PLAN_PATH = _core.SUBSCRIBE_PLAN_PATH
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    disabled = set(state["command_access"].get("disabled_commands", []) or [])
    plan_tier = _core._dashboard_effective_plan_tier(state, session=session)
    plan_name = _plan_display_name(plan_tier)

    guild_language = str((state.get("guild") or {}).get("language") or "th").strip().lower()
    language = guild_language if guild_language in {"th", "en"} else "th"
    t = {
        "th": {
            "no_desc": "ไม่มีคำอธิบาย",
            "general": "ทั่วไป",
            "mode_both": "รองรับ / + Prefix",
            "mode_slash": "รองรับ /",
            "mode_prefix": "รองรับ Prefix",
            "status_need_plan": "ต้องใช้แพ็กเกจ {plan}",
            "status_off": "ปิด",
            "status_on": "เปิด",
            "upgrade": "อัปเกรดแพ็กเกจ",
            "btn_enable": "เปิดใช้งาน",
            "btn_disable": "ปิดใช้งาน",
            "btn_short_enable": "เปิด",
            "fav_add": "เพิ่มในรายการโปรด",
            "usage": "วิธีใช้",
            "examples": "ตัวอย่าง",
            "category": "หมวดหมู่",
            "all": "ทั้งหมด",
            "head_command": "คำสั่ง",
            "head_category": "หมวดหมู่",
            "head_mode": "โหมด",
            "head_action": "จัดการ",
            "no_disabled": "ยังไม่มีคำสั่งที่ถูกปิด",
            "enable_all": "เปิดทั้งหมด",
            "disable_all": "ปิดทั้งหมด",
        },
        "en": {
            "no_desc": "No description",
            "general": "General",
            "mode_both": "Slash + Prefix",
            "mode_slash": "Slash only",
            "mode_prefix": "Prefix only",
            "status_need_plan": "Requires {plan} plan",
            "status_off": "Disabled",
            "status_on": "Enabled",
            "upgrade": "Upgrade plan",
            "btn_enable": "Enable",
            "btn_disable": "Disable",
            "btn_short_enable": "Enable",
            "fav_add": "Add to favorites",
            "usage": "Usage",
            "examples": "Examples",
            "category": "Category",
            "all": "All",
            "head_command": "Command",
            "head_category": "Category",
            "head_mode": "Mode",
            "head_action": "Action",
            "no_disabled": "No disabled commands",
            "enable_all": "Enable all",
            "disable_all": "Disable all",
        },
    }[language]

    catalog = sorted(_command_catalog(language=language), key=lambda item: str(item.get("name") or "").lower())
    slash_only_count = 0
    prefix_only_count = 0
    both_count = 0
    category_set: set[str] = set()
    command_rows: list[str] = []
    disabled_table_rows: list[str] = []

    for command in catalog:
        command_name = str(command.get("name") or "").strip().lower()
        if not command_name:
            continue

        brief = str(command.get("brief") or t["no_desc"])
        category = str(command.get("category") or t["general"]).strip() or t["general"]
        category_set.add(category)
        required_tier = _required_plan_for_command(command_name)
        locked_by_plan = not _is_plan_at_least(plan_tier, required_tier)
        is_disabled = command_name in disabled
        slash_available = bool(command.get("slash_available"))
        prefix_available = bool(command.get("prefix_available"))

        if slash_available and prefix_available:
            mode_code = "both"
            mode_text = t["mode_both"]
            both_count += 1
        elif slash_available:
            mode_code = "slash"
            mode_text = t["mode_slash"]
            slash_only_count += 1
        else:
            mode_code = "prefix"
            mode_text = t["mode_prefix"]
            prefix_only_count += 1

        status_text = (
            t["status_need_plan"].format(plan=required_tier.capitalize())
            if locked_by_plan
            else (t["status_off"] if is_disabled else t["status_on"])
        )
        status_cls = "locked" if locked_by_plan else ("off" if is_disabled else "on")

        usage_lines = [str(line).strip() for line in list(command.get("usage_lines") or []) if str(line).strip()]
        if not usage_lines:
            if slash_available:
                usage_lines.append(f"/{command_name}")
            if prefix_available:
                usage_lines.append(f"!{command_name}")
        example_lines = [str(line).strip() for line in list(command.get("example_lines") or []) if str(line).strip()]
        if not example_lines:
            example_lines = list(usage_lines)

        usage_markup = "".join(f"<li><code>{_escape(line)}</code></li>" for line in usage_lines[:6]) or "<li>-</li>"
        example_markup = "".join(f"<li><code>{_escape(line)}</code></li>" for line in example_lines[:6]) or "<li>-</li>"

        action_markup = (
            f'<a class="ghost-btn cmd-action-btn" href="{SUBSCRIBE_PLAN_PATH}">{_escape(t["upgrade"])}</a>'
            if locked_by_plan
            else (
                '<form method="post" action="/dashboard/guild/{guild_id}/commands/toggle">'
                '<input type="hidden" name="command_name" value="{command_name}">'
                '<input type="hidden" name="action" value="{action}">'
                '<button type="submit" class="cmd-action-btn">{label}</button>'
                "</form>"
            ).format(
                guild_id=current_guild["id"],
                command_name=_escape(command_name),
                action="enable" if is_disabled else "disable",
                label=_escape(t["btn_enable"] if is_disabled else t["btn_disable"]),
            )
        )

        if is_disabled:
            disabled_table_rows.append(
                (
                    "<tr>"
                    f"<td><code>/{_escape(command_name)}</code></td>"
                    f"<td>{_escape(category)}</td>"
                    f"<td>{_escape(mode_text)}</td>"
                    "<td>"
                    f'<form method="post" action="/dashboard/guild/{current_guild["id"]}/commands/toggle">'
                    f'<input type="hidden" name="command_name" value="{_escape(command_name)}">'
                    '<input type="hidden" name="action" value="enable">'
                    f'<button type="submit" class="cmd-mini-btn cmd-mini-btn-enable">{_escape(t["btn_short_enable"])}</button>'
                    "</form>"
                    "</td>"
                    "</tr>"
                )
            )

        search_text = _escape(f"{command_name} {brief} {category} {' '.join(usage_lines)}".lower())
        command_rows.append(
            f"""
            <details class="cmd-row {status_cls}" data-command-row data-category="{_escape(category)}" data-mode="{mode_code}" data-search="{search_text}">
              <summary>
                <div class="cmd-row-left">
                  <span class="cmd-title">{_escape(command_name)}</span>
                  <span class="cmd-desc">{_escape(brief)}</span>
                </div>
                <div class="cmd-row-right">
                  <button type="button" class="cmd-fav-btn" data-fav-toggle data-command-name="{_escape(command_name)}" title="{_escape(t["fav_add"])}" aria-label="{_escape(t["fav_add"])}" aria-pressed="false">★</button>
                  <span class="cmd-badge mode {mode_code}">{_escape(mode_text)}</span>
                  <span class="cmd-badge status {status_cls}">{_escape(status_text)}</span>
                </div>
              </summary>
              <div class="cmd-row-body">
                <div class="cmd-meta-grid">
                  <div class="cmd-meta-box">
                    <strong>{_escape(t["usage"])}</strong>
                    <ul>{usage_markup}</ul>
                  </div>
                  <div class="cmd-meta-box">
                    <strong>{_escape(t["examples"])}</strong>
                    <ul>{example_markup}</ul>
                  </div>
                  <div class="cmd-meta-box">
                    <strong>{_escape(t["category"])}</strong>
                    <p>{_escape(category)}</p>
                  </div>
                </div>
                <div class="cmd-row-action">{action_markup}</div>
              </div>
            </details>
            """
        )

    categories = sorted(category_set, key=lambda item: item.lower())
    category_tabs = [
        f'<button type="button" class="cmd-cat-tab active" data-cat-tab="">{_escape(t["all"])}</button>'
    ] + [
        f'<button type="button" class="cmd-cat-tab" data-cat-tab="{_escape(cat)}">{_escape(cat)}</button>'
        for cat in categories
    ]

    disabled_count = len(disabled)
    disabled_table_markup = (
        (
            '<div class="cmd-disabled-table-wrap">'
            '<table class="cmd-disabled-table">'
            f'<thead><tr><th>{_escape(t["head_command"])}</th><th>{_escape(t["head_category"])}</th><th>{_escape(t["head_mode"])}</th><th>{_escape(t["head_action"])}</th></tr></thead>'
            f'<tbody>{"".join(disabled_table_rows)}</tbody>'
            "</table>"
            "</div>"
        )
        if disabled_table_rows
        else f'<div class="notice">{_escape(t["no_disabled"])}</div>'
    )

    bulk_tools_markup = (
        f'<form method="post" action="/dashboard/guild/{current_guild["id"]}/commands/toggle">'
        '<input type="hidden" name="action" value="enable_all">'
        f'<button type="submit" class="cmd-mini-btn cmd-mini-btn-enable">{_escape(t["enable_all"])}</button>'
        "</form>"
        f'<form method="post" action="/dashboard/guild/{current_guild["id"]}/commands/toggle">'
        '<input type="hidden" name="action" value="disable_all">'
        f'<button type="submit" class="cmd-mini-btn cmd-mini-btn-disable">{_escape(t["disable_all"])}</button>'
        "</form>"
    )

    body = _render_dashboard_f_template("commands.html", locals())
    return _render_layout(
        title=f"SkylineBOT Commands - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
