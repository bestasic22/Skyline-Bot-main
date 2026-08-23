from __future__ import annotations

from typing import Any

from .. import dashboard_core as core


def _render_probot_module_hub(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    *,
    active_slug: str,
    title: str,
    description: str,
    badges: list[str] | None = None,
    quick_links: list[tuple[Any, ...] | dict[str, Any]] | None = None,
    notice: str | None = None,
) -> str:
    _core = core
    _escape = _core._escape
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    hub_slug = str(active_slug or "tools").strip().lower() or "tools"
    safe_title = str(title or "Tools").strip() or "Tools"
    safe_description = (
        str(description or "Select a module to continue.").strip()
        or "Select a module to continue."
    )

    badge_html = ""
    for badge_raw in badges or []:
        badge = str(badge_raw or "").strip()
        if not badge:
            continue
        badge_lower = badge.lower()
        tone = "premium" if ("premium" in badge_lower or "พรีเมียม" in badge) else "new"
        badge_html += f'<span class="cmd-badge mode {tone}">{_escape(badge)}</span>'

    quick_link_cards: list[str] = []
    for row in quick_links or []:
        label = ""
        href = ""
        subtitle = "Open settings"
        icon_key = "section"

        if isinstance(row, dict):
            label = str(row.get("label") or "").strip()
            href = str(row.get("href") or "").strip()
            subtitle = str(row.get("subtitle") or subtitle).strip() or subtitle
            icon_key = str(row.get("icon_key") or icon_key).strip().lower() or icon_key
        elif isinstance(row, (list, tuple)):
            if len(row) >= 1:
                label = str(row[0] or "").strip()
            if len(row) >= 2:
                href = str(row[1] or "").strip()
            if len(row) >= 3:
                subtitle = str(row[2] or "").strip() or subtitle
            if len(row) >= 4:
                icon_key = str(row[3] or "").strip().lower() or icon_key

        if not label or not href:
            continue

        quick_link_cards.append(
            f"""
            <a class="hub-link-card" href="{_escape(href)}" data-icon-key="{_escape(icon_key)}">
              <strong>{_escape(label)}</strong>
              <span>{_escape(subtitle)}</span>
            </a>
            """
        )

    link_count = len(quick_link_cards)
    quick_links_html = "".join(quick_link_cards)
    empty_notice_html = '<div class="notice">No shortcut modules are configured yet.</div>'

    body = _render_dashboard_f_template("probot_module_hub.html", locals())
    return _render_layout(
        title=f"SkylineBOT {safe_title} - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_slug,
        notice=notice,
    )
