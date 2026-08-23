from __future__ import annotations

from typing import Any

from .. import dashboard_core as core


def _render_donate(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "donate",
) -> str:
    _core = core
    _preview_bot_identity = _core._preview_bot_identity
    _escape = _core._escape
    _render_donate_slip_row_html = _core._render_donate_slip_row_html
    _dashboard_callback_url = _core._dashboard_callback_url
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    data = state.get("donate") or {}
    methods_enabled = data.get("methods_enabled") or {}
    slip_logs = state.get("donate_slips") or []
    preview_bot_name, preview_bot_avatar = _preview_bot_identity()
    preview_desc = _escape(data.get("desc_discord") or "Donation description")
    preview_color = _escape(data.get("color") or "#6b8cff")
    preview_image_url = _escape(data.get("image_url") or "")

    method_truemoney_checked = "checked" if methods_enabled.get("truemoney") else ""
    method_promptpay_checked = "checked" if methods_enabled.get("promptpay") else ""
    method_slipverify_checked = "checked" if methods_enabled.get("slipverify") else ""
    method_bank_checked = "checked" if methods_enabled.get("bank") else ""
    method_goal_checked = "checked" if methods_enabled.get("goal", True) else ""

    slip_rows: list[str] = []
    for row in slip_logs[:120]:
        slip_rows.append(_render_donate_slip_row_html(int(current_guild["id"]), row, with_actions=True))
    slip_table_html = (
        "".join(slip_rows)
        if slip_rows
        else '<tr><td colspan="11" class="muted">No slip history yet.</td></tr>'
    )
    method_preview_tags: list[str] = []
    if methods_enabled.get("truemoney"):
        method_preview_tags.append('<span class="mini-stat"> TrueMoney</span>')
    if methods_enabled.get("promptpay"):
        method_preview_tags.append('<span class="mini-stat"> PromptPay</span>')
    if methods_enabled.get("bank"):
        method_preview_tags.append('<span class="mini-stat"> Bank Transfer</span>')
    if methods_enabled.get("slipverify"):
        method_preview_tags.append('<span class="mini-stat"> SlipVerify</span>')
    if not method_preview_tags:
        method_preview_tags.append('<span class="mini-stat">No payment method enabled.</span>')

    public_donate_path = f"/dashboard/donate/{current_guild['id']}"
    public_donate_url = public_donate_path
    callback_url = _dashboard_callback_url()
    callback_suffix = "/dashboard/auth/callback"
    if callback_url.endswith(callback_suffix):
        base_url = callback_url[: -len(callback_suffix)].rstrip("/")
        if base_url:
            public_donate_url = f"{base_url}{public_donate_path}"
    public_donate_url_html = _escape(public_donate_url)
    public_donate_path_html = _escape(public_donate_path)

    body = _render_dashboard_f_template("donate.html", locals())
    return _render_layout(
        title=f"SkylineBOT Donate - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
