from __future__ import annotations

from typing import Any
from .. import dashboard_core as core

def _render_economy(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "economy",
) -> str:
    _core = core
    _normalize_economy_dashboard_settings = _core._normalize_economy_dashboard_settings
    _escape = _core._escape
    _render_role_select = _core._render_role_select
    _render_channel_select = _core._render_channel_select
    c = _core.c
    g = _core.g
    _format_datetime_th = _core._format_datetime_th
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout
    raw_settings = state.get("economy_settings") if isinstance(state.get("economy_settings"), dict) else {}
    settings = _normalize_economy_dashboard_settings(raw_settings)
    audit_rows = state.get("economy_audit") if isinstance(state.get("economy_audit"), list) else []

    def _secs_to_parts(seconds: int) -> tuple[int, int, int, int]:
        total = max(0, int(seconds or 0))
        days = total // 86400
        total %= 86400
        hours = total // 3600
        total %= 3600
        minutes = total // 60
        secs = total % 60
        return days, hours, minutes, secs

    role_income_rows = settings.get("role_income_entries") if isinstance(settings.get("role_income_entries"), list) else []
    role_income_rows = [row for row in role_income_rows if isinstance(row, dict)]
    role_row_limit = 12
    role_row_count = max(6, min(role_row_limit, len(role_income_rows) + 2))
    role_income_used = min(role_row_limit, len(role_income_rows))
    role_income_remaining = max(0, role_row_limit - role_income_used)
    role_lookup: dict[str, str] = {}
    for role in list(getattr(bot_guild, "roles", []) or []):
        role_id = str(getattr(role, "id", "")).strip()
        if not role_id:
            continue
        role_lookup[role_id] = str(getattr(role, "name", role_id))
    role_income_list_items: list[str] = []
    role_income_editor_cards: list[str] = []
    for index in range(role_row_count):
        row = role_income_rows[index] if index < len(role_income_rows) and isinstance(role_income_rows[index], dict) else {}
        role_id = str(row.get("role_id") or "").strip()
        slot_label = f"<Role Slot #{index + 1}>"
        role_name = _escape(role_lookup.get(role_id, slot_label))
        amount_value = int(row.get("amount") or 0)
        cooldown_value = int(row.get("cooldown") or 3600)
        channel_id = str(row.get("channel_id") or "").strip()
        is_active = index == 0
        active_class = " active" if is_active else ""
        role_income_list_items.append(
            f"""
            <button type="button" class="econ-role-item{active_class}" data-ri-target="{index}" data-ri-slot-label="{_escape(slot_label)}" title="{role_name}">
              <span class="econ-role-dot"></span>
              <span class="econ-role-item-name">{role_name}</span>
            </button>
            """
        )
        role_income_editor_cards.append(
            f"""
            <div class="econ-role-card{active_class}" data-ri-card="{index}">
              <div class="field-group" style="grid-template-columns:1.35fr 1fr;">
                <div class="field-item">
                  <label>Role</label>
                  {_render_role_select(f"role_income_role_{index}", bot_guild, role_id, placeholder="เลือกยศ...")}
                </div>
                <div class="field-item">
                  <label>Amount</label>
                  <div class="inline-split">
                    <input type="number" name="role_income_amount_{index}" min="0" max="10000000" value="{amount_value}">
                    <select disabled>
                      <option selected>Cash</option>
                      <option>Bank</option>
                    </select>
                  </div>
                </div>
              </div>
              <div class="field-group" style="grid-template-columns:1fr 1fr;">
                <div class="field-item">
                  <label>Cooldown (seconds)</label>
                  <input type="number" name="role_income_cooldown_{index}" min="10" max="86400" value="{cooldown_value}">
                </div>
                <div class="field-item">
                  <label>Announcement Channel</label>
                  {_render_channel_select(f"role_income_channel_{index}", bot_guild, channel_id, placeholder="No Announcement Channel", filter_types=["text", "news"])}
                </div>
              </div>
              <div class="econ-role-delete-row">
                <button type="button" class="ghost-btn danger econ-role-delete-btn" data-ri-delete="{index}">Delete role income</button>
              </div>
            </div>
            """
        )
    role_income_list_html = "".join(role_income_list_items)
    role_income_editor_html = "".join(role_income_editor_cards)

    chat_channel_ids = settings.get("chat_money_channels") if isinstance(settings.get("chat_money_channels"), list) else []
    chat_channel_set = {str(item) for item in chat_channel_ids}
    econ_cmd_channel_ids = (
        settings.get("economy_command_channels")
        if isinstance(settings.get("economy_command_channels"), list)
        else []
    )
    econ_cmd_channel_set = {str(item) for item in econ_cmd_channel_ids}
    text_channels = sorted(
        list(getattr(bot_guild, "text_channels", []) or []),
        key=lambda c: (getattr(c, "position", 0), getattr(c, "id", 0)),
    )
    chat_channel_checks = "".join(
        f"""
        <label class="econ-check-row" data-no-auto-field="1">
          <input type="checkbox" class="chat-money-channel" value="{channel.id}" {'checked' if str(channel.id) in chat_channel_set else ''}>
          <span class="econ-check-label" title="#{_escape(getattr(channel, 'name', str(channel.id)))}">#{_escape(getattr(channel, 'name', str(channel.id)))}</span>
        </label>
        """
        for channel in text_channels[:120]
    ) or '<div class="muted">ไม่พบ text channel</div>'
    chat_channel_csv = ",".join(chat_channel_ids)

    econ_cmd_channel_checks = "".join(
        f"""
        <label class="econ-check-row" data-no-auto-field="1">
          <input type="checkbox" class="economy-command-channel" value="{channel.id}" {'checked' if str(channel.id) in econ_cmd_channel_set else ''}>
          <span class="econ-check-label" title="#{_escape(getattr(channel, 'name', str(channel.id)))}">#{_escape(getattr(channel, 'name', str(channel.id)))}</span>
        </label>
        """
        for channel in text_channels[:160]
    ) or '<div class="muted">ไม่พบ text channel</div>'
    econ_cmd_channel_csv = ",".join(econ_cmd_channel_ids)

    audit_channel_select = _render_channel_select(
        "audit_channel_id",
        bot_guild,
        settings.get("audit_channel_id"),
        placeholder="เลือกช่องบันทึก...",
        filter_types=["text", "news", "forum"],
    )

    # Build picker data from user guilds and keep every emoji entry (no dedupe/trimming).
    emoji_picker_payload = _core._dashboard_emoji_picker_payload(session, guilds)
    custom_guilds = (
        emoji_picker_payload.get("custom_guilds")
        if isinstance(emoji_picker_payload.get("custom_guilds"), list)
        else []
    )
    emoji_server_sections = []
    total_server_emojis = 0
    for guild_payload in custom_guilds:
        guild_name = str(guild_payload.get("name") or guild_payload.get("id") or "Unknown Guild").strip() or "Unknown Guild"
        guild_id = str(guild_payload.get("id") or "").strip()
        emoji_rows = guild_payload.get("emojis") if isinstance(guild_payload.get("emojis"), list) else []
        guild_emoji_buttons: list[str] = []
        for emoji in emoji_rows:
            if not isinstance(emoji, dict):
                continue
            emoji_id_text = str(emoji.get("id") or "").strip()
            emoji_name = str(emoji.get("name") or "emoji").strip() or "emoji"
            if not emoji_id_text:
                continue
            is_animated = bool(emoji.get("animated"))
            emoji_value = f"<{'a' if is_animated else ''}:{emoji_name}:{emoji_id_text}>"
            emoji_url = str(emoji.get("url") or "").strip()
            if not emoji_url:
                ext = "gif" if is_animated else "png"
                emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id_text}.{ext}?size=64&quality=lossless"
            search_text = f"{emoji_name.lower()} {guild_name.lower()} {guild_id.lower()} {emoji_id_text}"
            animated_badge = '<span class="econ-emoji-badge">GIF</span>' if is_animated else ""
            guild_emoji_buttons.append(
                f'<button type="button" class="econ-emoji-btn" data-emoji="{_escape(emoji_value)}" data-search="{_escape(search_text)}" title="{_escape(emoji_name)}">'
                f'<img src="{_escape(emoji_url)}" alt="{_escape(emoji_name)}">'
                f"{animated_badge}"
                f"</button>"
            )
        total_server_emojis += len(guild_emoji_buttons)
        if guild_emoji_buttons:
            group_content = f'<div class="econ-emoji-grid server">{"".join(guild_emoji_buttons)}</div>'
        else:
            group_content = '<div class="muted">No custom emojis available in this guild.</div>'
        emoji_server_sections.append(
            f'<section class="econ-emoji-server-group" data-server-name="{_escape(guild_name.lower())}">'
            f'<div class="econ-emoji-server-head"><span class="econ-emoji-server-name">{_escape(guild_name)}</span><span class="muted">{len(guild_emoji_buttons)} emojis</span></div>'
            f"{group_content}"
            f"</section>"
        )
    server_emoji_title = f"SERVER EMOJIS ({total_server_emojis})"
    server_emoji_html = "".join(emoji_server_sections) if emoji_server_sections else '<div class="muted">No guilds were found for this user.</div>'
    unicode_rows = (
        emoji_picker_payload.get("unicode_emojis")
        if isinstance(emoji_picker_payload.get("unicode_emojis"), list)
        else []
    )
    unicode_emojis = [
        (
            str(item.get("value") or "").strip(),
            str(item.get("aliases") or "").strip(),
        )
        for item in unicode_rows
        if isinstance(item, dict) and str(item.get("value") or "").strip()
    ]
    if not unicode_emojis:
        unicode_emojis = list(_core._dashboard_unicode_emoji_catalog())
    unicode_buttons = "".join(
        f'<button type="button" class="econ-emoji-btn unicode" data-emoji="{_escape(item)}" data-search="{_escape(f"{item} {aliases}")}" title="{_escape(item)}">{_escape(item)}</button>'
        for item, aliases in unicode_emojis
    )

    def _command_page(key: str, label: str) -> str:
        d, h, m, s = _secs_to_parts(int(settings.get(f"{key}_cooldown") or 0))
        fine_type = str(settings.get(f"{key}_fine_type") or "fixed").lower()
        replies = settings.get(f"{key}_replies") if isinstance(settings.get(f"{key}_replies"), list) else []
        replies_value = _escape("\n".join(str(item) for item in replies if str(item).strip()))
        return f"""
        <section class="econ-page panel-sub" data-econ-page="{key}">
          <div class="econ-page-head">
            <h3>{_escape(label)}</h3>
            <label class="ux-toggle">
              <span class="ux-toggle-label">Enable</span>
              <input type="checkbox" name="command_{key}_enabled" {'checked' if settings.get(f'command_{key}_enabled') else ''}>
              <span class="ux-switch"></span>
            </label>
          </div>
          <div class="field-item">
            <label>Cooldown</label>
            <input type="hidden" name="{key}_cooldown" class="cooldown-total" data-prefix="{key}" value="{int(settings.get(f'{key}_cooldown') or 0)}">
            <div class="econ-cooldown-grid">
              <div><input type="number" min="0" max="365" class="cooldown-part" data-prefix="{key}" data-unit="d" value="{d}"><span>d</span></div>
              <div><input type="number" min="0" max="23" class="cooldown-part" data-prefix="{key}" data-unit="h" value="{h}"><span>h</span></div>
              <div><input type="number" min="0" max="59" class="cooldown-part" data-prefix="{key}" data-unit="m" value="{m}"><span>m</span></div>
              <div><input type="number" min="0" max="59" class="cooldown-part" data-prefix="{key}" data-unit="s" value="{s}"><span>s</span></div>
            </div>
          </div>
          <div class="field-group">
            <div class="field-item"><label>Payout Min</label><input type="number" name="{key}_payout_min" min="1" max="20000000" value="{int(settings.get(f'{key}_payout_min') or 1)}"></div>
            <div class="field-item"><label>Payout Max</label><input type="number" name="{key}_payout_max" min="1" max="20000000" value="{int(settings.get(f'{key}_payout_max') or 1)}"></div>
          </div>
          <div class="field-item"><label>Chance Of Fine (%)</label><input type="number" name="{key}_fail_rate" min="0" max="100" value="{int(settings.get(f'{key}_fail_rate') or 0)}"></div>
          <div class="field-group">
            <div class="field-item">
              <label>Type Of Fine</label>
              <select name="{key}_fine_type">
                <option value="fixed" {'selected' if fine_type == 'fixed' else ''}>Fixed</option>
                <option value="percent" {'selected' if fine_type == 'percent' else ''}>Percent</option>
              </select>
            </div>
            <div class="field-item"><label>Fine Min</label><input type="number" name="{key}_fine_min" min="0" max="20000000" value="{int(settings.get(f'{key}_fine_min') or 0)}"></div>
            <div class="field-item"><label>Fine Max</label><input type="number" name="{key}_fine_max" min="0" max="20000000" value="{int(settings.get(f'{key}_fine_max') or 0)}"></div>
          </div>
          <div class="field-item">
            <label>Custom Replies ({_escape(label)})</label>
            <textarea name="{key}_replies" rows="8" placeholder="1 บรรทัด = 1 ข้อความ">{replies_value}</textarea>
          </div>
        </section>
        """

    work_page = _command_page("work", "WORK")
    slut_page = _command_page("slut", "SLUT")
    crime_page = _command_page("crime", "CRIME")
    rob_page = _command_page("rob", "ROB")

    chat_d, chat_h, chat_m, chat_s = _secs_to_parts(int(settings.get("chat_money_cooldown") or 60))

    audit_logs_html = "".join(
        f"""
        <tr>
          <td>{_escape(str(row.get('action') or '-'))}</td>
          <td>{_escape(str(row.get('user_id') or '-'))}</td>
          <td>{_escape(str(row.get('actor_id') or '-'))}</td>
          <td>{_escape(str(row.get('amount') or 0))}</td>
          <td>{_escape(str(row.get('location') or '-'))}</td>
          <td>{_escape(_format_datetime_th(row.get('created_at')))}</td>
        </tr>
        """
        for row in audit_rows[:40]
        if isinstance(row, dict)
    ) or "<tr><td colspan='6' class='muted'>ยังไม่มีธุรกรรม</td></tr>"

    body = _render_dashboard_f_template("economy.html", locals())
    return _render_layout(
        title=f"SkylineBOT Economy - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )

