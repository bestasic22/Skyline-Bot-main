from __future__ import annotations

import asyncio
import datetime
import json
import os
import time

import httpx
import psutil
import re
from typing import Any, Callable

_STATUS_MUSIC_ANALYTICS_CACHE: dict[str, Any] = {
    "key": "",
    "built_at": 0.0,
    "payload": {},
}


def _redact_sensitive_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    redacted = text
    redacted = re.sub(
        r"(?i)\b(bearer)\s+[a-z0-9._\-]{16,}\b",
        r"\1 [REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\b(token|api[_-]?key|authorization|password|secret)\b\s*[:=]\s*([^\s,;\"']+)",
        r"\1=[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"\b[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{20,}\b",
        "[REDACTED_TOKEN]",
        redacted,
    )
    return redacted


def status_level_label(level: str) -> str:
    mapping = {
        "ok": "ปกติ",
        "warn": "เฝ้าระวัง",
        "error": "มีปัญหา",
        "info": "ข้อมูล",
    }
    return mapping.get(str(level or "info").strip().lower(), "ข้อมูล")


def status_level_rank(level: str) -> int:
    return {"ok": 1, "warn": 2, "error": 3, "info": 0}.get(
        str(level or "info").strip().lower(), 0
    )


def status_overall_level(levels: list[str]) -> str:
    if not levels:
        return "info"
    ranked = sorted(levels, key=status_level_rank, reverse=True)
    return str(ranked[0] or "info")


def _status_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return True
    if value in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _status_runtime_components() -> dict[str, bool]:
    mode = str(os.getenv("RUN_COMPONENTS", "all") or "").strip().lower()
    run_web = True
    run_bot = True

    if mode in {"web", "dashboard", "surface"}:
        run_web = True
        run_bot = False
    elif mode in {"bot", "discord"}:
        run_web = False
        run_bot = True
    elif mode in {"none", "off"}:
        run_web = False
        run_bot = False

    run_web = _status_bool_env("RUN_WEB", run_web)
    run_bot = _status_bool_env("RUN_BOT", run_bot)
    dashboard_enabled = _status_bool_env("DASHBOARD_ENABLED", True)

    return {
        "run_web": bool(run_web),
        "run_bot": bool(run_bot),
        "dashboard_enabled": bool(dashboard_enabled),
    }


def status_extract_command_errors(
    log_lines: list[str],
    *,
    clean_text_fn: Callable[[Any], str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    by_command: dict[str, int] = {}
    seen: set[str] = set()
    important_tokens = (
        "Error in file",
        "on_command_error",
        "NameError",
        "AttributeError",
        "TypeError",
        "ValueError",
        "KeyError",
        "RuntimeError",
    )
    for index, line in enumerate(log_lines):
        if not any(token.lower() in line.lower() for token in important_tokens):
            continue
        module_match = re.search(
            r"src[\\/](?P<section>commands|events|surface|engine|modules)[\\/](?P<name>[^\\/:\s]+)\.py",
            line,
            flags=re.IGNORECASE,
        )
        section = str(module_match.group("section")).lower() if module_match else "system"
        module_name = str(module_match.group("name")).lower() if module_match else "unknown"
        scope = f"{section}/{module_name}" if module_match else "system"
        detail = line
        for look_ahead in (1, 2, 3):
            next_index = index + look_ahead
            if next_index >= len(log_lines):
                break
            candidate = log_lines[next_index]
            if any(
                token in candidate
                for token in (
                    "NameError",
                    "AttributeError",
                    "TypeError",
                    "ValueError",
                    "KeyError",
                    "RuntimeError",
                    "Exception",
                )
            ):
                detail = f"{line} | {candidate}"
                break
        detail = _redact_sensitive_text(clean_text_fn(detail)).strip()
        if detail in seen:
            continue
        seen.add(detail)
        rows.append(
            {
                "scope": scope,
                "module": module_name,
                "section": section,
                "detail": detail[:240],
            }
        )
        if section == "commands" and module_name != "unknown":
            by_command[module_name] = by_command.get(module_name, 0) + 1
    rows.reverse()
    return rows[:24], by_command


def status_extract_incidents(
    log_lines: list[str],
    *,
    clean_text_fn: Callable[[Any], str],
    limit: int = 12,
) -> list[str]:
    if limit <= 0:
        return []
    keywords = (
        " > fail |",
        " internal server error",
        "traceback",
        "error in file",
        "cannot connect",
        "was unable to",
        "nameerror",
        "attributeerror",
        "runtimeerror",
    )
    incidents: list[str] = []
    seen: set[str] = set()
    for line in reversed(log_lines):
        lower = line.lower()
        if not any(key in lower for key in keywords):
            continue
        cleaned = _redact_sensitive_text(clean_text_fn(line)).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        incidents.append(cleaned[:240])
        if len(incidents) >= limit:
            break
    return incidents


def status_runtime_mode(runtime_settings: dict[str, Any]) -> dict[str, Any]:
    mode = str(runtime_settings.get("guild_mode") or "all").strip().lower()
    tester_enabled = bool(runtime_settings.get("tester_enabled", False))
    whitelist_count = len(runtime_settings.get("whitelist_guild_ids") or [])
    blacklist_count = len(runtime_settings.get("blacklist_guild_ids") or [])
    tester_count = len(runtime_settings.get("tester_guild_ids") or [])
    commands_enabled = bool(runtime_settings.get("global_command_response_enabled", True))
    bot_enabled = bool(runtime_settings.get("global_bot_response_enabled", True))

    if tester_enabled or mode == "tester":
        level = "warn"
        mode_title = "Tester Mode"
        mode_desc = f"จำกัดเฉพาะเซิร์ฟทดสอบ ({tester_count} กิลด์)"
    elif mode == "whitelist":
        level = "warn"
        mode_title = "Whitelist Mode"
        mode_desc = f"อนุญาตเฉพาะกิลด์ใน whitelist ({whitelist_count} กิลด์)"
    elif mode == "blacklist":
        level = "warn"
        mode_title = "Blacklist Mode"
        mode_desc = f"บล็อกกิลด์ใน blacklist ({blacklist_count} กิลด์)"
    else:
        level = "ok"
        mode_title = "All Guilds"
        mode_desc = "เปิดใช้งานทุกกิลด์"
    if not commands_enabled or not bot_enabled:
        level = "warn" if level != "error" else level
    return {
        "level": level,
        "title": mode_title,
        "description": mode_desc,
        "commands_enabled": commands_enabled,
        "bot_enabled": bot_enabled,
        "whitelist_count": whitelist_count,
        "blacklist_count": blacklist_count,
        "tester_count": tester_count,
    }


def status_lavalink_payload(
    bot_running: bool,
    *,
    wavelink_module: Any,
) -> dict[str, Any]:
    wavelink = wavelink_module
    nodes_container = getattr(wavelink.Pool, "nodes", None)
    nodes: list[Any] = []
    if isinstance(nodes_container, dict):
        nodes = list(nodes_container.values())
    elif isinstance(nodes_container, (list, tuple, set)):
        nodes = list(nodes_container)
    else:
        try:
            maybe_node = wavelink.Pool.get_node()
            if maybe_node:
                nodes = [maybe_node]
        except Exception:
            nodes = []

    node_rows: list[dict[str, Any]] = []
    connected_count = 0
    for node in nodes:
        status_raw = str(getattr(node, "status", "") or "").strip()
        status_lower = status_raw.lower()
        uri = str(getattr(node, "uri", "") or "-").strip() or "-"
        players_raw = getattr(node, "players", 0)
        try:
            players_count = len(players_raw) if not isinstance(players_raw, int) else int(players_raw)
        except Exception:
            players_count = 0
        latency_value = getattr(node, "ping", None)
        if latency_value is None:
            latency_value = getattr(getattr(node, "_websocket", None), "latency", None)
        if isinstance(latency_value, (int, float)):
            latency_text = f"{max(0, int(latency_value))} ms"
        else:
            latency_text = "-"
        connected = "connected" in status_lower and "connecting" not in status_lower
        if connected:
            connected_count += 1
        node_rows.append(
            {
                "identifier": str(getattr(node, "identifier", "") or uri),
                "uri": uri,
                "status": status_raw or "unknown",
                "players": players_count,
                "latency": latency_text,
                "connected": connected,
            }
        )

    if node_rows and connected_count > 0:
        level = "ok"
        status_text = f"เชื่อมต่อ {connected_count}/{len(node_rows)} node"
        detail = "Lavalink พร้อมใช้งาน"
    elif node_rows and connected_count == 0:
        level = "error"
        status_text = "มี node แต่ยังไม่เชื่อมต่อ"
        detail = "ตรวจสอบ host/port/password ของ Lavalink"
    elif bot_running:
        level = "warn"
        status_text = "ไม่พบข้อมูล node"
        detail = "ยังไม่พบการตั้งค่า node Lavalink"
    else:
        level = "warn"
        status_text = "ยังไม่พบ node ใด ๆ"
        detail = "บอทยังไม่ทำงาน หรือยังไม่เชื่อมต่อ Lavalink"

    return {
        "level": level,
        "status": status_text,
        "detail": detail,
        "nodes": node_rows,
    }



def status_bot_payload(
    *,
    runtime_settings: dict[str, Any],
    command_error_count_by_module: dict[str, int],
    get_bot_fn: Callable[[], Any],
    format_uptime_seconds_fn: Callable[[int | float | None], str],
    command_catalog_fn: Callable[[str], list[dict[str, Any]]],
    run_web_enabled: bool | None = None,
    run_bot_enabled: bool | None = None,
    dashboard_enabled: bool | None = None,
    external_discord_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    get_bot = get_bot_fn
    _format_uptime_seconds = format_uptime_seconds_fn
    _command_catalog = command_catalog_fn
    runtime_components = _status_runtime_components()
    if run_web_enabled is None:
        run_web_enabled = bool(runtime_components.get("run_web", True))
    if run_bot_enabled is None:
        run_bot_enabled = bool(runtime_components.get("run_bot", True))
    if dashboard_enabled is None:
        dashboard_enabled = bool(runtime_components.get("dashboard_enabled", True))
    external_state = external_discord_state if isinstance(external_discord_state, dict) else {}
    external_level = str(external_state.get("level") or "").strip().lower()
    external_pid_alive = bool(external_state.get("pid_alive", False))
    external_runtime_visible = bool(
        external_pid_alive
        and external_level
        and external_level not in {"stopped", "unknown"}
    )
    bot = get_bot()
    bot_user = getattr(bot, "user", None) if bot else None
    bot_has_identity = bool(bot and bot_user)
    bot_closed = bool(getattr(bot, "is_closed", lambda: False)()) if bot else True
    is_ready = bool(
        bot_has_identity
        and not bot_closed
        and bool(getattr(bot, "is_ready", lambda: False)())
    )
    bot_running = bool(bot_has_identity and not bot_closed)

    if bot_running:
        latency_raw = float(getattr(bot, "latency", 0.0) or 0.0)
        if latency_raw != latency_raw or latency_raw in (float("inf"), float("-inf")):
            latency_ms = None
        else:
            latency_ms = max(0, int(latency_raw * 1000))
        guild_count = len(getattr(bot, "guilds", []) or [])
        member_count = 0
        for guild in list(getattr(bot, "guilds", []) or []):
            member_count += int(getattr(guild, "member_count", 0) or 0)
        started_at = getattr(bot, "start_time", None)
        uptime_seconds = 0
        started_at_ts = 0
        if isinstance(started_at, datetime.datetime):
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=datetime.timezone.utc)
            uptime_seconds = max(
                0,
                int(
                    (
                        datetime.datetime.now(tz=datetime.timezone.utc)
                        - started_at.astimezone(datetime.timezone.utc)
                    ).total_seconds()
                ),
            )
            started_at_ts = int(started_at.astimezone(datetime.timezone.utc).timestamp())
            uptime_text = _format_uptime_seconds(uptime_seconds)
        else:
            uptime_text = "-"
            uptime_seconds = 0
            started_at_ts = 0
    else:
        latency_ms = None
        guild_count = 0
        member_count = 0
        uptime_text = "-"
        uptime_seconds = 0
        started_at_ts = 0

    command_catalog = _command_catalog("th") if bot_running and run_bot_enabled else []
    total_commands = len(command_catalog)
    prefix_commands = sum(1 for cmd in command_catalog if bool(cmd.get("prefix_available")))
    slash_commands = sum(1 for cmd in command_catalog if bool(cmd.get("slash_available")))
    disabled_global_commands = sorted(
        {str(name).strip().lower() for name in (runtime_settings.get("global_disabled_commands") or []) if str(name).strip()}
    )
    error_modules_sorted = sorted(command_error_count_by_module.items(), key=lambda item: item[1], reverse=True)
    estimated_unavailable = min(total_commands, len(disabled_global_commands) + len(error_modules_sorted))
    estimated_available = max(0, total_commands - estimated_unavailable)
    sample_available = [str(cmd.get("name") or "").strip() for cmd in command_catalog[:24] if str(cmd.get("name") or "").strip()]

    if not run_bot_enabled and (external_runtime_visible or bot_running):
        if external_level == "ok" and bot_running:
            level = "ok"
            status_text = "ออนไลน์ (เชื่อมผ่าน bot process อื่น)"
            detail = "เว็บเชื่อมข้อมูลบอทจาก process อื่นได้ปกติ"
        elif external_level in {"starting", "degraded"} or (external_runtime_visible and not is_ready):
            level = "warn"
            status_text = "บอททำงานจาก process อื่น แต่ยังไม่พร้อมเต็มที่"
            detail = "พบ process บอทแล้ว แต่สถานะยังอยู่ช่วงเริ่มต้นหรือเสถียรภาพลดลง"
        elif bot_running and not external_runtime_visible:
            level = "warn"
            status_text = "พบข้อมูลบอทล่าสุด แต่ heartbeat ยังไม่สด"
            detail = "เว็บใช้ข้อมูลจาก snapshot ล่าสุดของบอท และกำลังรอ heartbeat ใหม่"
        else:
            level = "error"
            status_text = "บอท process อื่นมีปัญหา"
            detail = "พบ process บอทแล้ว แต่ Discord runtime รายงานปัญหา"
    elif not run_bot_enabled:
        level = "error"
        status_text = "บอทไม่ทำงาน (RUN_COMPONENTS/RUN_BOT)"
        detail = "โหมดปัจจุบันปิด Discord bot runtime และไม่พบ process บอทภายนอก"
    elif is_ready:
        level = "ok"
        status_text = "ออนไลน์และพร้อมรับคำสั่ง"
        detail = "เชื่อมต่อ Discord Gateway แล้ว"
    elif bot_running:
        level = "warn"
        status_text = "กำลังทำงาน แต่ยังไม่พร้อมรับคำสั่ง"
        detail = "พบ bot instance แล้ว แต่สถานะ Ready ยังไม่สมบูรณ์"
    else:
        level = "error"
        status_text = "ไม่พบบอทในระบบ"
        detail = "ยังไม่พบ bot instance ที่ bind กับแอปพลิเคชัน"

    if not dashboard_enabled and run_bot_enabled:
        level = "error"
        status_text = "บอททำงาน แต่เว็บไซต์ปิดอยู่"
        detail = "DASHBOARD_ENABLED=False ทำให้เว็บไม่ออนไลน์"
    elif not run_web_enabled and run_bot_enabled:
        level = "error"
        status_text = "บอททำงาน แต่เว็บไซต์ไม่ทำงาน"
        detail = "RUN_COMPONENTS/RUN_WEB ปิดอยู่ หรือเว็บไม่พร้อมใช้งาน"

    return {
        "level": level,
        "status": status_text,
        "detail": detail,
        "running": bot_running,
        "ready": is_ready,
        "latency_ms": latency_ms,
        "guild_count": guild_count,
        "member_count": member_count,
        "uptime_text": uptime_text,
        "uptime_seconds": uptime_seconds,
        "started_at_ts": started_at_ts,
        "command_summary": {
            "total": total_commands,
            "prefix": prefix_commands,
            "slash": slash_commands,
            "disabled_global": len(disabled_global_commands),
            "disabled_global_samples": disabled_global_commands[:12],
            "error_modules": error_modules_sorted[:10],
            "estimated_available": estimated_available,
            "estimated_unavailable": estimated_unavailable,
            "sample_available": sample_available,
        },
    }



def render_system_status_page(
    *,
    session: dict[str, Any] | None,
    guilds: list[dict[str, Any]],
    payload: dict[str, Any],
    notice: str | None = None,
    status_view: str = "bot",
    escape_fn: Callable[[Any], str],
    render_layout_fn: Callable[..., str],
    status_level_label_fn: Callable[[str], str],
    support_status_public_url_fn: Callable[[], str],
) -> str:
    _escape = escape_fn
    _render_layout = render_layout_fn
    _status_level_label = status_level_label_fn
    _support_status_public_url = support_status_public_url_fn

    overall = dict(payload.get("overall") or {})
    overall_level = str(overall.get("level") or "info")
    overall_title = str(overall.get("title") or "สถานะระบบ")
    overall_detail = str(overall.get("detail") or "")
    generated_at = str(payload.get("generated_at") or "-")
    generated_at_ts = int(payload.get("generated_at_ts") or 0)
    is_public_view = bool(payload.get("public_view"))
    public_summary = dict(payload.get("public_summary") or {})
    public_overall_status = str(public_summary.get("overall_status") or "").strip()
    public_updated_at = str(public_summary.get("updated_at") or generated_at).strip() or generated_at
    public_uptime = str(public_summary.get("uptime") or "-").strip() or "-"
    request_host = str(payload.get("request_host") or "-")
    request_port = str(payload.get("request_port") or "-")
    status_view_key = str(status_view or "bot").strip().lower()
    if status_view_key not in {"service", "bot"}:
        status_view_key = "bot"
    is_service_view = status_view_key == "service"
    page_heading = "SkyLineBOT Public Status" if is_public_view else ("SkyLineBOT Service Status" if is_service_view else "SkyLineBOT Status")
    refresh_href = f"/dashboard/status?view={status_view_key}"
    switch_href = (
        f"/dashboard/status?view={'bot' if is_service_view else 'service'}"
        if is_public_view
        else ("/dashboard/status?view=bot" if is_service_view else _support_status_public_url())
    )
    switch_label = "Bot View" if is_service_view else "Service View"
    live_url = f"/dashboard/status/live?view={status_view_key}"

    def _card_html(card: dict[str, Any]) -> str:
        level = str(card.get("level") or "info")
        metrics = list(card.get("metrics") or [])
        metrics_html = "".join(
            f'<li><span>{_escape(str(label))}</span><strong>{_escape(str(value))}</strong></li>'
            for label, value in metrics
        ) or "<li><span>-</span><strong>-</strong></li>"
        return (
            f'<article class="sys-card level-{_escape(level)}">'
            f"<header><div class=\"sys-icon\">{_escape(str(card.get('icon') or '•'))}</div><div>"
            f"<h3>{_escape(str(card.get('title') or '-'))}</h3>"
            f"<p class=\"state\">{_escape(_status_level_label(level))} • {_escape(str(card.get('status') or '-'))}</p>"
            "</div></header>"
            f"<p class=\"desc\">{_escape(str(card.get('detail') or '-'))}</p>"
            f"<ul class=\"metrics\">{metrics_html}</ul>"
            "</article>"
        )

    components = list(payload.get("components") or [])
    component_filter_ids = {"web", "discord_runtime", "mongo", "ai"} if is_service_view else {"bot", "discord_runtime", "lavalink", "ownerbot"}
    filtered_components = [card for card in components if str(card.get("id") or "").strip().lower() in component_filter_ids]
    if filtered_components:
        components = filtered_components
    cards_html = "".join(_card_html(card) for card in components)

    command_summary = dict(payload.get("command_summary") or {})
    available_chips = "".join(
        f'<span class="cmd-chip ok">/{_escape(str(name))}</span>'
        for name in list(command_summary.get("sample_available") or [])[:24]
    ) or '<span class="cmd-empty">ยังไม่พบคำสั่งที่พร้อมใช้งาน</span>'
    disabled_chips = "".join(
        f'<span class="cmd-chip warn">{_escape(str(name))}</span>'
        for name in list(command_summary.get("disabled_global_samples") or [])[:12]
    ) or '<span class="cmd-empty">ยังไม่พบคำสั่งที่ปิดแบบ Global</span>'
    error_rows = list(command_summary.get("error_rows") or [])
    error_rows_html = "".join(
        f"<tr><td>{_escape(str(row.get('scope') or '-'))}</td><td>{_escape(str(row.get('detail') or '-'))}</td></tr>"
        for row in error_rows[:12]
    ) or '<tr><td colspan="2">ไม่พบ error จากโมดูลคำสั่ง</td></tr>'

    nodes = list(payload.get("lavalink_nodes") or [])
    nodes_html = "".join(
        "<tr>"
        f"<td>{_escape(str(node.get('identifier') or '-'))}</td>"
        f"<td>{_escape(str(node.get('status') or '-'))}</td>"
        f"<td>{_escape(str(node.get('latency') or '-'))}</td>"
        f"<td>{_escape(str(node.get('players') or '-'))}</td>"
        "</tr>"
        for node in nodes
    ) or '<tr><td colspan="4">ยังไม่มีข้อมูล node</td></tr>'

    incidents = list(payload.get("incidents") or [])
    incidents_html = "".join(f"<li>{_escape(str(line))}</li>" for line in incidents[:14]) or "<li>ยังไม่พบเหตุการณ์ผิดปกติจาก log ล่าสุด</li>"
    incidents_title = "Public Incident Summary" if is_public_view else ("เหตุการณ์ล่าสุดของบริการ" if is_service_view else "เหตุการณ์ล่าสุดของบอท")

    music_analytics = dict(payload.get("music_analytics") or {})
    music_period_order = list(music_analytics.get("period_order") or ["24h", "month", "year", "all"])
    music_status_rows = list(music_analytics.get("status_rows") or [])
    music_source_note = str(music_analytics.get("source_note") or "")
    music_period_label = {
        "24h": "24 ชั่วโมงล่าสุด",
        "month": "เดือน",
        "year": "ปี",
        "all": "ทั้งหมด",
    }
    music_period_buttons = "".join(
        f'<button type="button" class="music-period-btn" data-period="{_escape(period_key)}">{_escape(music_period_label.get(period_key, period_key))}</button>'
        for period_key in music_period_order
    )
    music_status_rows_html = "".join(
        f"<tr>"
        f"<td>{_escape(str(row.get('item') or '-'))}</td>"
        f"<td>{_escape(_status_level_label(str(row.get('status') or 'info')))}</td>"
        f"<td>{_escape(str(row.get('value') or '-'))}</td>"
        f"<td>{_escape(str(row.get('updated_at') or '-'))}</td>"
        f"</tr>"
        for row in music_status_rows
    ) or '<tr><td colspan="4">ยังไม่พบข้อมูลสถานะระบบเพลง</td></tr>'

    if is_public_view and is_service_view:
        command_section_html = """
      <section class="sys-section">
        <h2>Public Scope</h2>
        <p class="desc">Summary-level health only. Sensitive IDs/tokens are masked.</p>
      </section>
        """
        nodes_section_html = ""
        music_section_html = ""
    elif is_public_view:
        command_section_html = f"""
      <section class="sys-section">
        <h2>Public Runtime Summary</h2>
        <p class="desc">Important data only. Sensitive identifiers are shortened for safety.</p>
        <div class="sys-stats">
          <div class="sys-stat"><span class="label">Commands</span><span class="value">{int(command_summary.get("total") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">Available</span><span class="value">{int(command_summary.get("estimated_available") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">Unavailable</span><span class="value">{int(command_summary.get("estimated_unavailable") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">Global Disabled</span><span class="value">{int(command_summary.get("disabled_global") or 0):,}</span></div>
        </div>
        <div class="sys-table-wrap">
          <table class="sys-table">
            <thead><tr><th>Scope / Module</th><th>Latest Error (Compact)</th></tr></thead>
            <tbody>{error_rows_html}</tbody>
          </table>
        </div>
      </section>
        """
        nodes_section_html = f"""
      <section class="sys-section">
        <h2>Lavalink Nodes</h2>
        <div class="sys-table-wrap">
          <table class="sys-table">
            <thead><tr><th>Node</th><th>Status</th><th>Ping</th><th>Players</th></tr></thead>
            <tbody id="sys-nodes-body">{nodes_html}</tbody>
          </table>
        </div>
      </section>
        """
        music_section_html = f"""
      <section class="sys-section">
        <h2>Music Runtime (Public)</h2>
        <div class="music-summary">
          <span class="music-pill">Songs Played: <strong id="music-total-songs">0</strong></span>
          <span class="music-pill">Requesters: <strong id="music-total-requesters">0</strong></span>
        </div>
        <div class="music-note" id="music-source-note">{_escape(music_source_note)}</div>
        <div class="sys-table-wrap">
          <table class="sys-table">
            <thead><tr><th>Item</th><th>Status</th><th>Value</th><th>Updated</th></tr></thead>
            <tbody id="music-status-body">{music_status_rows_html}</tbody>
          </table>
        </div>
      </section>
        """
    elif is_service_view:
        command_section_html = """
      <section class="sys-section">
        <h2>มุมมอง Service</h2>
        <p class="desc">โหมดนี้เน้นสถานะเว็บ/API/ฐานข้อมูล/AI โดยไม่แสดงรายละเอียดคำสั่งบอทและระบบเพลง</p>
      </section>
        """
        nodes_section_html = ""
        music_section_html = ""
    else:
        command_section_html = f"""
      <section class="sys-section">
        <h2>สรุปคำสั่ง</h2>
        <div class="sys-stats">
          <div class="sys-stat"><span class="label">คำสั่งทั้งหมด</span><span class="value">{int(command_summary.get("total") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">Slash</span><span class="value">{int(command_summary.get("slash") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">Prefix</span><span class="value">{int(command_summary.get("prefix") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">พร้อมใช้งาน</span><span class="value">{int(command_summary.get("estimated_available") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">ใช้งานไม่ได้</span><span class="value">{int(command_summary.get("estimated_unavailable") or 0):,}</span></div>
          <div class="sys-stat"><span class="label">ปิดแบบ Global</span><span class="value">{int(command_summary.get("disabled_global") or 0):,}</span></div>
        </div>
        <div><strong style="display:block; margin-bottom:6px;">ตัวอย่างคำสั่งที่พร้อมใช้ (ล่าสุด)</strong>{available_chips}</div>
        <div style="margin-top:10px;"><strong style="display:block; margin-bottom:6px;">คำสั่งที่ถูกปิดแบบ Global</strong>{disabled_chips}</div>
        <div class="sys-table-wrap" style="margin-top:12px;">
          <table class="sys-table">
            <thead><tr><th>ขอบเขต/โมดูลคำสั่ง</th><th>Error ล่าสุด</th></tr></thead>
            <tbody>{error_rows_html}</tbody>
          </table>
        </div>
      </section>
        """
        nodes_section_html = f"""
      <section class="sys-section">
        <h2>Lavalink Nodes</h2>
        <div class="sys-table-wrap">
          <table class="sys-table">
            <thead><tr><th>Node</th><th>Status</th><th>Ping</th><th>Players</th></tr></thead>
            <tbody id="sys-nodes-body">{nodes_html}</tbody>
          </table>
        </div>
      </section>
        """
        music_section_html = f"""
      <section class="sys-section">
        <div class="music-head">
          <h2>สถานะระบบเพลง</h2>
          <div class="music-periods">{music_period_buttons}</div>
        </div>
        <div class="music-summary">
          <span class="music-pill">จำนวนการเล่นเพลง: <strong id="music-total-songs">0</strong></span>
          <span class="music-pill">จำนวนคนสั่งเพลง: <strong id="music-total-requesters">0</strong></span>
        </div>
        <div class="music-chart-wrap">
          <canvas id="music-trend-canvas" width="1200" height="260" aria-label="Music trend chart"></canvas>
        </div>
        <div class="music-note" id="music-source-note">{_escape(music_source_note)}</div>
        <div class="sys-table-wrap">
          <table class="sys-table">
            <thead><tr><th>รายการ</th><th>สถานะ</th><th>ค่า</th><th>อัปเดต</th></tr></thead>
            <tbody id="music-status-body">{music_status_rows_html}</tbody>
          </table>
        </div>
      </section>
        """

    hero_generated_at = public_updated_at if is_public_view else generated_at
    hero_badge_label = (public_overall_status or _status_level_label(overall_level)) if is_public_view else _status_level_label(overall_level)
    if is_public_view:
        public_scope_text = "Scope: Web/API, Discord, MongoDB, AI" if is_service_view else "Scope: Bot runtime, Discord, Lavalink, OwnerBOT"
        meta_html = (
            f'<span>Updated: <strong id="sys-generated-at">{_escape(hero_generated_at)}</strong></span>'
            f'<span>Overall: <strong id="sys-public-overall">{_escape(public_overall_status or "-")}</strong></span>'
            f'<span>Uptime: <strong id="sys-public-uptime">{_escape(public_uptime)}</strong></span>'
            f"<span>{_escape(public_scope_text)}</span>"
        )
        actions_html = (
            f'<a class="ghost-btn" href="{_escape(refresh_href)}">Refresh</a>'
            f'<a class="ghost-btn" href="{_escape(switch_href)}">{_escape(switch_label)}</a>'
        )
    else:
        meta_html = (
            f'<span>Updated: <strong id="sys-generated-at">{_escape(hero_generated_at)}</strong></span>'
            f'<span>Host: {_escape(request_host)}:{_escape(request_port)}</span>'
            "<span>This status view auto-refreshes in near real time.</span>"
        )
        actions_html = (
            f'<a class="ghost-btn" href="{_escape(refresh_href)}">Refresh</a>'
            f'<a class="ghost-btn" href="{_escape(switch_href)}">{_escape(switch_label)}</a>'
            '<a class="ghost-btn" href="/dashboard">Dashboard</a>'
        )

    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    live_script = """
<script>
(() => {
  const STATUS_VIEW = "__STATUS_VIEW__";
  const LIVE_URL = "__LIVE_URL__";
  const LEVEL_LABELS = { ok: "ปกติ", warn: "เฝ้าระวัง", error: "มีปัญหา", info: "ข้อมูล" };
  const PERIOD_LABELS = { "24h": "24 ชั่วโมงล่าสุด", month: "เดือน", year: "ปี", all: "ทั้งหมด" };
  let statusPayload = {};
  let activePeriod = "24h";
  let inFlight = false;

  const initialEl = document.getElementById("sys-status-initial");
  if (initialEl) {
    try {
      const parsed = JSON.parse(initialEl.textContent || "{}");
      if (parsed && typeof parsed === "object") {
        statusPayload = parsed;
        activePeriod = String(parsed?.music_analytics?.active_period || "24h");
      }
    } catch (_err) {}
  }

  const esc = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const levelLabel = (level) => LEVEL_LABELS[String(level || "info").toLowerCase()] || LEVEL_LABELS.info;

  const filteredComponents = (payload) => {
    const rows = Array.isArray(payload?.components) ? payload.components : [];
    const allow = STATUS_VIEW === "service"
      ? new Set(["web", "discord_runtime", "mongo", "ai"])
      : new Set(["bot", "discord_runtime", "lavalink", "ownerbot"]);
    const out = rows.filter((row) => allow.has(String(row?.id || "").trim().toLowerCase()));
    return out.length ? out : rows;
  };

  const setHtmlIfChanged = (node, html) => {
    if (!(node instanceof HTMLElement)) return false;
    const nextHtml = String(html ?? "");
    if (node.innerHTML === nextHtml) return false;
    node.innerHTML = nextHtml;
    return true;
  };

  const renderHero = (payload) => {
    const level = String(payload?.overall?.level || "info");
    const publicView = Boolean(payload?.public_view);
    const badgeEl = document.getElementById("sys-overall-badge");
    if (badgeEl) {
      badgeEl.className = `sys-badge level-${level}`;
      badgeEl.textContent = publicView
        ? String(payload?.public_summary?.overall_status || levelLabel(level))
        : levelLabel(level);
    }
    const titleEl = document.getElementById("sys-overall-title");
    if (titleEl) titleEl.textContent = String(payload?.overall?.title || "-");
    const detailEl = document.getElementById("sys-overall-detail");
    if (detailEl) detailEl.textContent = String(payload?.overall?.detail || "-");
    const generatedAtEl = document.getElementById("sys-generated-at");
    if (generatedAtEl) {
      generatedAtEl.textContent = publicView
        ? String(payload?.public_summary?.updated_at || payload?.generated_at || "-")
        : String(payload?.generated_at || "-");
    }
    const publicOverallEl = document.getElementById("sys-public-overall");
    if (publicOverallEl) publicOverallEl.textContent = String(payload?.public_summary?.overall_status || "-");
    const publicUptimeEl = document.getElementById("sys-public-uptime");
    if (publicUptimeEl) publicUptimeEl.textContent = String(payload?.public_summary?.uptime || "-");
  };

  const renderCards = (payload) => {
    const root = document.getElementById("sys-cards-grid");
    if (!root) return;
    const publicView = Boolean(payload?.public_view);
    const cards = filteredComponents(payload);
    const cardsHtml = cards.map((card) => {
      const level = String(card?.level || "info");
      const metrics = Array.isArray(card?.metrics) ? card.metrics : [];
      const metricsHtml = metrics.length
        ? metrics.map((metric) => {
            const label = Array.isArray(metric) ? metric[0] : "-";
            const value = Array.isArray(metric) ? metric[1] : "-";
            return `<li><span>${esc(label)}</span><strong>${esc(value)}</strong></li>`;
          }).join("")
        : "<li><span>-</span><strong>-</strong></li>";
      return `
        <article class="sys-card level-${esc(level)}">
          <header>
            <div class="sys-icon">${esc(card?.icon || "•")}</div>
            <div>
              <h3>${esc(card?.title || "-")}</h3>
              <p class="state">${esc(levelLabel(level))} • ${esc(card?.status || "-")}</p>
            </div>
          </header>
          <p class="desc">${esc(card?.detail || "-")}</p>
          <ul class="metrics">${metricsHtml}</ul>
        </article>`;
    }).join("");
    setHtmlIfChanged(root, cardsHtml);
    if (publicView) {
      const stateRows = Array.from(root.querySelectorAll(".sys-card .state"));
      stateRows.forEach((row, index) => {
        const source = cards[index] || {};
        row.textContent = String(source?.status || "-");
      });
    }
  };

  const renderNodes = (payload) => {
    const body = document.getElementById("sys-nodes-body");
    if (!body) return;
    const nodes = Array.isArray(payload?.lavalink_nodes) ? payload.lavalink_nodes : [];
    const nodesHtml = nodes.length
      ? nodes.map((row) => `<tr><td>${esc(row?.identifier || "-")}</td><td>${esc(row?.status || "-")}</td><td>${esc(row?.latency || "-")}</td><td>${esc(row?.players || "-")}</td></tr>`).join("")
      : '<tr><td colspan="4">ยังไม่มีข้อมูล node</td></tr>';
    setHtmlIfChanged(body, nodesHtml);
  };

  const renderIncidents = (payload) => {
    const list = document.getElementById("sys-incidents-list");
    if (!list) return;
    const incidents = Array.isArray(payload?.incidents) ? payload.incidents : [];
    const incidentsHtml = incidents.length
      ? incidents.slice(0, 14).map((item) => `<li>${esc(item)}</li>`).join("")
      : "<li>ยังไม่พบเหตุการณ์ผิดปกติจาก log ล่าสุด</li>";
    setHtmlIfChanged(list, incidentsHtml);
  };

  const drawMusicChart = (labels, songs, requesters) => {
    const canvas = document.getElementById("music-trend-canvas");
    if (!canvas || typeof canvas.getContext !== "function") return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const width = Math.max(320, canvas.clientWidth || 320);
    const height = 260;
    canvas.width = width;
    canvas.height = height;
    ctx.clearRect(0, 0, width, height);

    const padLeft = 44;
    const padRight = 12;
    const padTop = 18;
    const padBottom = 34;
    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;
    const maxVal = Math.max(1, ...songs, ...requesters);
    const ticks = 4;

    ctx.strokeStyle = "rgba(120,150,210,.28)";
    ctx.lineWidth = 1;
    for (let index = 0; index <= ticks; index += 1) {
      const y = padTop + (plotHeight / ticks) * index;
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(padLeft + plotWidth, y);
      ctx.stroke();
    }

    const stepX = labels.length > 1 ? plotWidth / (labels.length - 1) : 0;
    const yValue = (value) => padTop + plotHeight - (Math.max(0, Number(value || 0)) / maxVal) * plotHeight;
    const xValue = (index) => padLeft + stepX * index;

    const drawLine = (values, color) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      values.forEach((value, index) => {
        const x = xValue(index);
        const y = yValue(value);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      values.forEach((value, index) => {
        const x = xValue(index);
        const y = yValue(value);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 2.8, 0, Math.PI * 2);
        ctx.fill();
      });
    };

    drawLine(songs, "#4bc2ff");
    drawLine(requesters, "#9d7bff");

    ctx.fillStyle = "rgba(214,226,255,.78)";
    ctx.font = "12px sans-serif";
    const labelIndexes = labels.length >= 3 ? [0, Math.floor((labels.length - 1) / 2), labels.length - 1] : labels.map((_x, index) => index);
    labelIndexes.forEach((index) => {
      const text = String(labels[index] || "");
      const x = xValue(index);
      ctx.fillText(text, Math.max(0, x - 18), height - 10);
    });
  };

  const renderMusic = (payload) => {
    const section = document.getElementById("music-status-body");
    if (!section) return;
    const analytics = payload?.music_analytics || {};
    const periods = analytics?.periods || {};
    const periodOrder = Array.isArray(analytics?.period_order) && analytics.period_order.length
      ? analytics.period_order
      : ["24h", "month", "year", "all"];
    if (!periods[activePeriod]) {
      activePeriod = String(analytics?.active_period || periodOrder[0] || "24h");
    }
    const current = periods[activePeriod] || { labels: [], songs: [], requesters: [], songs_total: 0, requesters_total: 0 };

    document.querySelectorAll(".music-period-btn").forEach((button) => {
      const key = String(button?.dataset?.period || "");
      button.classList.toggle("is-active", key === activePeriod);
      button.textContent = PERIOD_LABELS[key] || key;
    });

    const songsTotalEl = document.getElementById("music-total-songs");
    if (songsTotalEl) songsTotalEl.textContent = String(current?.songs_total || 0);
    const requestersTotalEl = document.getElementById("music-total-requesters");
    if (requestersTotalEl) requestersTotalEl.textContent = String(current?.requesters_total || 0);
    const sourceEl = document.getElementById("music-source-note");
    if (sourceEl) sourceEl.textContent = String(analytics?.source_note || "");

    const statusRows = Array.isArray(analytics?.status_rows) ? analytics.status_rows : [];
    const musicRowsHtml = statusRows.length
      ? statusRows.map((row) => `<tr><td>${esc(row?.item || "-")}</td><td>${esc(levelLabel(row?.status || "info"))}</td><td>${esc(row?.value || "-")}</td><td>${esc(row?.updated_at || "-")}</td></tr>`).join("")
      : '<tr><td colspan="4">ยังไม่พบข้อมูลสถานะระบบเพลง</td></tr>';

    setHtmlIfChanged(section, musicRowsHtml);

    drawMusicChart(
      Array.isArray(current?.labels) ? current.labels : [],
      Array.isArray(current?.songs) ? current.songs.map((value) => Number(value || 0)) : [],
      Array.isArray(current?.requesters) ? current.requesters.map((value) => Number(value || 0)) : [],
    );
  };

  const renderAll = () => {
    renderHero(statusPayload);
    renderCards(statusPayload);
    renderNodes(statusPayload);
    renderIncidents(statusPayload);
    renderMusic(statusPayload);
  };

  const pollLive = async () => {
    if (inFlight) return;
    if (document.visibilityState !== "visible") return;
    inFlight = true;
    try {
      const response = await fetch(`${LIVE_URL}&_ts=${Date.now()}`, {
        method: "GET",
        cache: "no-store",
        headers: { "x-requested-with": "XMLHttpRequest" },
      });
      if (!response.ok) return;
      const nextPayload = await response.json();
      if (!nextPayload || typeof nextPayload !== "object") return;
      statusPayload = nextPayload;
      renderAll();
    } catch (_err) {
    } finally {
      inFlight = false;
    }
  };

  document.querySelectorAll(".music-period-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const nextPeriod = String(button?.dataset?.period || "");
      if (!nextPeriod) return;
      activePeriod = nextPeriod;
      renderMusic(statusPayload);
    });
  });

  renderAll();
  const pollMs = STATUS_VIEW === "bot" ? 10000 : 20000;
  const startLivePolling = () => {
    pollLive();
    setInterval(pollLive, pollMs);
  };
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(startLivePolling, { timeout: 2500 });
  } else {
    setTimeout(startLivePolling, 1200);
  }
  window.addEventListener("resize", () => renderMusic(statusPayload));
})();
</script>
""".replace("__STATUS_VIEW__", _escape(status_view_key)).replace("__LIVE_URL__", _escape(live_url))

    body = f"""
    <style>
      .sys-wrap {{ display: grid; gap: 16px; color: var(--text, #e9eef6); }}
      .sys-hero {{ background: linear-gradient(135deg, rgba(56,96,190,.28), rgba(19,28,56,.75)); border: 1px solid rgba(108,151,255,.35); border-radius: 18px; padding: 20px; display: grid; gap: 12px; }}
      .sys-badge {{ width: fit-content; border-radius: 999px; padding: 6px 12px; border: 1px solid rgba(160,180,220,.45); background: rgba(25,39,70,.55); color: #dbe9ff; font-weight: 800; font-size: .85rem; }}
      .sys-badge.level-ok {{ border-color: rgba(25,203,146,.65); background: rgba(25,203,146,.2); color: #c9ffe8; }}
      .sys-badge.level-warn {{ border-color: rgba(243,171,45,.65); background: rgba(243,171,45,.2); color: #ffe9bf; }}
      .sys-badge.level-error {{ border-color: rgba(237,91,120,.7); background: rgba(237,91,120,.22); color: #ffd8e2; }}
      .sys-hero h1 {{ margin: 0; font-size: clamp(1.4rem, 2.2vw, 2rem); color: #f3f7ff; }}
      .sys-hero p {{ margin: 0; color: #d1dcf5; }}
      .sys-meta {{ display: flex; flex-wrap: wrap; gap: 10px; font-size: .88rem; color: #b8c8ea; }}
      .sys-meta span {{ background: rgba(16,26,50,.6); border: 1px solid rgba(123,154,219,.35); border-radius: 999px; padding: 6px 10px; }}
      .sys-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }}
      .sys-card {{ background: rgba(13,22,43,.72); border: 1px solid rgba(119,147,207,.28); border-radius: 16px; padding: 14px; display: grid; gap: 10px; }}
      .sys-card.level-ok {{ border-color: rgba(25,203,146,.5); }}
      .sys-card.level-warn {{ border-color: rgba(243,171,45,.55); }}
      .sys-card.level-error {{ border-color: rgba(237,91,120,.6); }}
      .sys-card header {{ display: flex; align-items: center; gap: 10px; }}
      .sys-icon {{ width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; background: rgba(88,130,236,.23); border: 1px solid rgba(131,161,227,.35); font-size: 1.1rem; }}
      .sys-card h3 {{ margin: 0; font-size: 1rem; color: #edf4ff; }}
      .sys-card .state {{ margin: 2px 0 0; font-size: .84rem; color: #b9c7e6; }}
      .sys-card .desc {{ margin: 0; color: #d7e3fb; line-height: 1.45; font-size: .92rem; }}
      .sys-card .metrics {{ margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }}
      .sys-card .metrics li {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 8px; border-radius: 10px; background: rgba(11,19,36,.58); border: 1px solid rgba(113,138,194,.22); color: #d8e6ff; font-size: .85rem; }}
      .sys-card .metrics strong {{ color: #f5f8ff; }}
      .sys-section {{ background: rgba(13,22,43,.7); border: 1px solid rgba(116,145,205,.25); border-radius: 16px; padding: 16px; }}
      .sys-section h2 {{ margin: 0 0 12px; font-size: 1.2rem; color: #eef4ff; }}
      .sys-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin-bottom: 12px; }}
      .sys-stat {{ border: 1px solid rgba(112,141,200,.3); border-radius: 12px; padding: 10px; background: rgba(10,18,35,.6); }}
      .sys-stat .label {{ display: block; color: #b6c6e8; font-size: .82rem; }}
      .sys-stat .value {{ display: block; color: #f5f8ff; font-size: 1.15rem; font-weight: 800; }}
      .cmd-chip {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 9px; margin: 0 6px 6px 0; font-size: .82rem; border: 1px solid rgba(122,154,219,.34); background: rgba(18,31,58,.6); color: #d7e7ff; word-break: break-word; }}
      .cmd-chip.ok {{ border-color: rgba(25,203,146,.45); background: rgba(25,203,146,.18); }}
      .cmd-chip.warn {{ border-color: rgba(243,171,45,.5); background: rgba(243,171,45,.2); }}
      .cmd-empty {{ color: #b7c8ea; font-size: .9rem; }}
      .sys-table-wrap {{ overflow-x: auto; border: 1px solid rgba(117,145,200,.28); border-radius: 12px; }}
      table.sys-table {{ width: 100%; border-collapse: collapse; }}
      table.sys-table th, table.sys-table td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid rgba(92,120,176,.24); color: #d7e6ff; font-size: .87rem; vertical-align: top; }}
      table.sys-table th {{ background: rgba(19,31,58,.78); color: #f0f5ff; font-weight: 700; }}
      .sys-incidents {{ margin: 0; padding-left: 18px; color: #d5e3ff; display: grid; gap: 8px; font-size: .9rem; line-height: 1.45; }}
      .sys-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
      .sys-actions a {{ text-decoration: none; }}
      .music-head {{ display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
      .music-periods {{ display: flex; flex-wrap: wrap; gap: 8px; }}
      .music-period-btn {{ border: 1px solid rgba(117,145,200,.4); background: rgba(14,26,50,.72); color: #dce9ff; border-radius: 999px; padding: 6px 12px; font-size: .82rem; font-weight: 700; cursor: pointer; }}
      .music-period-btn.is-active {{ background: rgba(68,138,255,.32); border-color: rgba(129,172,255,.62); color: #f1f7ff; }}
      .music-summary {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px; }}
      .music-pill {{ background: rgba(14,26,50,.72); border: 1px solid rgba(117,145,200,.34); border-radius: 999px; padding: 6px 12px; color: #d7e6ff; font-size: .85rem; }}
      .music-pill strong {{ color: #f5f9ff; }}
      .music-chart-wrap {{ border: 1px solid rgba(117,145,200,.34); border-radius: 14px; background: rgba(10,20,40,.55); padding: 10px 12px; margin-bottom: 10px; }}
      #music-trend-canvas {{ width: 100%; height: 260px; display: block; }}
      .music-note {{ color: #b6caed; font-size: .82rem; margin: 0 0 10px; }}
    </style>

    <section class="sys-wrap">
      <section class="sys-hero">
        <span id="sys-overall-badge" class="sys-badge level-{_escape(overall_level)}">{_escape(hero_badge_label)}</span>
        <h1>{_escape(page_heading)}</h1>
        <p><strong id="sys-overall-title">{_escape(overall_title)}</strong> <span id="sys-overall-detail">{_escape(overall_detail)}</span></p>
        <div class="sys-meta">{meta_html}</div>
        <div class="sys-actions">{actions_html}</div>
      </section>

      <section id="sys-cards-grid" class="sys-grid">{cards_html}</section>
      {command_section_html}
      {nodes_section_html}
      {music_section_html}
      <section class="sys-section"><h2>{_escape(incidents_title)}</h2><ul id="sys-incidents-list" class="sys-incidents">{incidents_html}</ul></section>
    </section>
    <script id="sys-status-initial" type="application/json">{payload_json}</script>
    {live_script}
    """

    return _render_layout(
        title=f"{page_heading} - SkylineBOT",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=None,
        active_tab="overview",
        notice=notice,
    )
def status_tail_log_lines(
    limit: int = 500,
    *,
    logs_dir: Any,
    clean_text_fn: Callable[[Any], str],
) -> list[str]:
    LOGS_DIR = logs_dir
    _clean_text = clean_text_fn
    if limit <= 0:
        return []
    if not LOGS_DIR.exists():
        return []
    try:
        log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    except Exception:
        log_files = []
    if not log_files:
        return []
    try:
        raw_lines = log_files[0].read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    cleaned = [_clean_text(line).strip() for line in raw_lines if str(line or "").strip()]
    return cleaned[-limit:]



def format_uptime_seconds(total_seconds: int | float | None) -> str:
    seconds = max(0, int(total_seconds or 0))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} วัน")
    if hours:
        parts.append(f"{hours} ชม.")
    if minutes:
        parts.append(f"{minutes} นาที")
    if secs or not parts:
        parts.append(f"{secs} วิ")
    return " ".join(parts)

def status_music_analytics_payload(
    *,
    logs_dir: Any,
    bkk_tz: Any,
    datetime_module: Any,
    clean_text_fn: Callable[[Any], str],
    lavalink_nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    datetime = datetime_module
    _clean_text = clean_text_fn
    nodes = list(lavalink_nodes or [])
    now_local = datetime.datetime.now(tz=datetime.timezone.utc).astimezone(bkk_tz)
    now_label = now_local.strftime("%d/%m/%Y %H:%M:%S")

    def _extract_named(raw_line: str, key: str) -> str:
        pattern_primary = rf"{re.escape(key)}\s*=\s*\d+\(([^)]+)\)"
        matched_primary = re.search(pattern_primary, raw_line, flags=re.IGNORECASE)
        if matched_primary:
            return _clean_text(matched_primary.group(1)).strip()
        pattern_fallback = rf"{re.escape(key)}\s*=\s*([^\|\s]+)"
        matched_fallback = re.search(pattern_fallback, raw_line, flags=re.IGNORECASE)
        if matched_fallback:
            return _clean_text(matched_fallback.group(1)).strip()
        return ""

    def _clean_actor(raw_actor: str) -> str:
        actor = _clean_text(raw_actor).strip()
        actor = re.sub(r"\s+", " ", actor)
        if not actor:
            return ""
        return actor[:80].lower()

    def _parse_line_local_dt(
        raw_line: str,
        file_date: datetime.date,
        fallback_local_dt: datetime.datetime,
    ) -> datetime.datetime:
        time_match = re.search(r"\[(\d{2}):(\d{2}):(\d{2})\]", raw_line)
        if time_match is None:
            time_match = re.search(r"\b(\d{2}):(\d{2}):(\d{2})\b", raw_line)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            second = int(time_match.group(3))
            if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                return datetime.datetime(
                    file_date.year,
                    file_date.month,
                    file_date.day,
                    hour,
                    minute,
                    second,
                    tzinfo=bkk_tz,
                )
        return fallback_local_dt

    log_events: list[dict[str, Any]] = []
    last_music_event = "-"
    music_errors_24h = 0
    latest_music_ts: datetime.datetime | None = None
    window_24h_start = now_local - datetime.timedelta(hours=24)
    cache_key = "no-logs"
    log_files: list[Any] = []
    if logs_dir is not None and hasattr(logs_dir, "exists") and logs_dir.exists():
        try:
            log_files = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
        except Exception:
            log_files = []
        if log_files:
            signature_rows: list[str] = []
            for file_path in log_files[-40:]:
                try:
                    stats = file_path.stat()
                    signature_rows.append(
                        f"{file_path.name}:{int(getattr(stats, 'st_mtime', 0))}:{int(getattr(stats, 'st_size', 0))}"
                    )
                except Exception:
                    signature_rows.append(str(file_path.name))
            cache_key = "|".join(signature_rows)

    cache_now = float(time.time())
    cached_row = _STATUS_MUSIC_ANALYTICS_CACHE
    if (
        str(cached_row.get("key") or "") == cache_key
        and (cache_now - float(cached_row.get("built_at") or 0.0)) <= 4.0
        and isinstance(cached_row.get("payload"), dict)
    ):
        return dict(cached_row.get("payload") or {})
    logs_note = "ดึงข้อมูลจากไฟล์ log ล่าสุด"

    if logs_dir is None or not hasattr(logs_dir, "exists") or not logs_dir.exists():
        logs_note = "ไม่พบโฟลเดอร์ log สำหรับวิเคราะห์ระบบเพลง"
    else:
        try:
            log_files = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
        except Exception:
            log_files = []
        if not log_files:
            logs_note = "ยังไม่พบไฟล์ log สำหรับวิเคราะห์ระบบเพลง"
        else:
            sliced_files = log_files[-240:]
            for log_path in sliced_files:
                try:
                    raw_lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                except Exception:
                    continue
                fallback_local_dt = datetime.datetime.fromtimestamp(
                    float(getattr(log_path.stat(), "st_mtime", 0.0) or 0.0),
                    tz=datetime.timezone.utc,
                ).astimezone(bkk_tz)
                file_date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(getattr(log_path, "stem", "")))
                if file_date_match:
                    try:
                        file_date = datetime.date(
                            int(file_date_match.group(1)),
                            int(file_date_match.group(2)),
                            int(file_date_match.group(3)),
                        )
                    except Exception:
                        file_date = fallback_local_dt.date()
                else:
                    file_date = fallback_local_dt.date()

                for raw_line in raw_lines:
                    line = _clean_text(raw_line).strip()
                    if not line:
                        continue
                    lowered = line.lower()
                    is_music_context = any(
                        token in lowered
                        for token in (
                            "music",
                            "track",
                            "queue",
                            "player",
                            "lavalink",
                            "wavelink",
                            "voice",
                            "controller",
                        )
                    )
                    if not is_music_context:
                        continue

                    line_local_dt = _parse_line_local_dt(line, file_date, fallback_local_dt)
                    if line_local_dt > now_local:
                        line_local_dt = now_local

                    song_started = 1 if "has started playing on player" in lowered else 0

                    requester = ""
                    if "[music_action]" in lowered and any(
                        action_token in lowered
                        for action_token in ("action=add_track", "action=add_track_at", "action=add_playlist")
                    ):
                        requester = _clean_actor(_extract_named(line, "actor"))
                    elif "[music_setup]" in lowered and "step 1 received" in lowered:
                        requester = _clean_actor(_extract_named(line, "author"))

                    if song_started or requester:
                        log_events.append(
                            {
                                "dt": line_local_dt,
                                "song_started": song_started,
                                "requester": requester,
                            }
                        )

                    if any(token in lowered for token in ("traceback", " > fail |", "runtimeerror", "connectionreseterror")):
                        if line_local_dt >= window_24h_start:
                            music_errors_24h += 1

                    if latest_music_ts is None or line_local_dt >= latest_music_ts:
                        if "has started playing on player" in lowered:
                            title_match = re.search(
                                r"track\s+(.+?)\s+has started playing on player",
                                line,
                                flags=re.IGNORECASE,
                            )
                            title = _clean_text(title_match.group(1) if title_match else "").strip() or "ไม่ทราบชื่อเพลง"
                            last_music_event = f"เริ่มเล่น: {title}"
                            latest_music_ts = line_local_dt
                        elif "track end event received for track:" in lowered:
                            title_match = re.search(r"track end event received for track:\s*(.+)$", line, flags=re.IGNORECASE)
                            title = _clean_text(title_match.group(1) if title_match else "").strip() or "ไม่ทราบชื่อเพลง"
                            last_music_event = f"เพลงจบ: {title}"
                            latest_music_ts = line_local_dt
                        elif "queue is empty" in lowered:
                            last_music_event = "คิวเพลงว่าง"
                            latest_music_ts = line_local_dt
                        elif "disconnect" in lowered:
                            last_music_event = "บอทออกจากห้องเสียง"
                            latest_music_ts = line_local_dt

            if not log_events:
                logs_note = "ยังไม่พบ event เพลงในช่วง log ที่มีอยู่"

    def _month_start_local(raw_dt: datetime.datetime) -> datetime.datetime:
        return raw_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _next_month_local(raw_dt: datetime.datetime) -> datetime.datetime:
        start = _month_start_local(raw_dt)
        if start.month == 12:
            return start.replace(year=start.year + 1, month=1)
        return start.replace(month=start.month + 1)

    def _build_period(period_key: str) -> dict[str, Any]:
        key = str(period_key or "24h").strip().lower()
        starts: list[datetime.datetime] = []
        labels: list[str] = []
        period_start: datetime.datetime
        period_end: datetime.datetime
        bucket_kind = "hour"

        if key == "24h":
            current_hour = now_local.replace(minute=0, second=0, microsecond=0)
            period_start = current_hour - datetime.timedelta(hours=23)
            period_end = current_hour + datetime.timedelta(hours=1)
            starts = [period_start + datetime.timedelta(hours=index) for index in range(24)]
            labels = [slot.strftime("%H:%M") for slot in starts]
            bucket_kind = "hour"
        elif key == "month":
            period_start = _month_start_local(now_local)
            period_end = _next_month_local(now_local)
            total_days = max(1, (period_end - period_start).days)
            starts = [period_start + datetime.timedelta(days=index) for index in range(total_days)]
            labels = [slot.strftime("%d/%m") for slot in starts]
            bucket_kind = "day"
        elif key == "year":
            period_start = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start.replace(year=period_start.year + 1)
            for month_index in range(12):
                if month_index == 0:
                    starts.append(period_start)
                else:
                    previous = starts[-1]
                    if previous.month == 12:
                        starts.append(previous.replace(year=previous.year + 1, month=1))
                    else:
                        starts.append(previous.replace(month=previous.month + 1))
            labels = [slot.strftime("%m/%y") for slot in starts]
            bucket_kind = "month"
        else:
            event_years = [entry["dt"].year for entry in log_events if isinstance(entry.get("dt"), datetime.datetime)]
            first_year = min(event_years) if event_years else now_local.year
            period_start = datetime.datetime(first_year, 1, 1, 0, 0, 0, tzinfo=bkk_tz)
            period_end = datetime.datetime(now_local.year + 1, 1, 1, 0, 0, 0, tzinfo=bkk_tz)
            years_count = max(1, (now_local.year - first_year) + 1)
            starts = [
                datetime.datetime(first_year + index, 1, 1, 0, 0, 0, tzinfo=bkk_tz)
                for index in range(years_count)
            ]
            labels = [str(slot.year) for slot in starts]
            bucket_kind = "year"

        songs: list[int] = [0 for _ in starts]
        requester_sets: list[set[str]] = [set() for _ in starts]
        requesters_unique: set[str] = set()

        for entry in log_events:
            line_dt = entry.get("dt")
            if not isinstance(line_dt, datetime.datetime):
                continue
            if not (period_start <= line_dt < period_end):
                continue
            index = 0
            if bucket_kind == "hour":
                index = int((line_dt.replace(minute=0, second=0, microsecond=0) - period_start).total_seconds() // 3600)
            elif bucket_kind == "day":
                index = (line_dt.date() - period_start.date()).days
            elif bucket_kind == "month":
                index = (line_dt.year - period_start.year) * 12 + (line_dt.month - period_start.month)
            else:
                index = line_dt.year - period_start.year
            if index < 0 or index >= len(starts):
                continue
            songs[index] += int(entry.get("song_started") or 0)
            requester_key = str(entry.get("requester") or "").strip()
            if requester_key:
                requester_sets[index].add(requester_key)
                requesters_unique.add(requester_key)

        requesters = [len(row) for row in requester_sets]
        return {
            "labels": labels,
            "songs": songs,
            "requesters": requesters,
            "songs_total": sum(songs),
            "requesters_total": len(requesters_unique),
        }

    periods = {
        "24h": _build_period("24h"),
        "month": _build_period("month"),
        "year": _build_period("year"),
        "all": _build_period("all"),
    }

    connected_nodes = 0
    active_players = 0
    for node in nodes:
        if bool(node.get("connected")):
            connected_nodes += 1
        try:
            active_players += max(0, int(node.get("players") or 0))
        except Exception:
            continue
    total_nodes = len(nodes)
    if total_nodes <= 0:
        nodes_level = "warn"
    elif connected_nodes <= 0:
        nodes_level = "error"
    elif connected_nodes < total_nodes:
        nodes_level = "warn"
    else:
        nodes_level = "ok"

    music_status_rows = [
        {
            "item": "Lavalink Nodes",
            "status": nodes_level,
            "value": f"{connected_nodes}/{total_nodes}",
            "updated_at": now_label,
        },
        {
            "item": "Players Active",
            "status": "ok" if active_players > 0 else "info",
            "value": str(active_players),
            "updated_at": now_label,
        },
        {
            "item": "Songs Played (24h)",
            "status": "ok" if int(periods["24h"].get("songs_total") or 0) > 0 else "info",
            "value": str(int(periods["24h"].get("songs_total") or 0)),
            "updated_at": now_label,
        },
        {
            "item": "Requesters (24h)",
            "status": "ok" if int(periods["24h"].get("requesters_total") or 0) > 0 else "info",
            "value": str(int(periods["24h"].get("requesters_total") or 0)),
            "updated_at": now_label,
        },
        {
            "item": "Music Errors (24h)",
            "status": "warn" if music_errors_24h > 0 else "ok",
            "value": str(music_errors_24h),
            "updated_at": now_label,
        },
    ]
    if last_music_event and last_music_event != "-":
        music_status_rows.append(
            {
                "item": "Last Music Event",
                "status": "info",
                "value": last_music_event,
                "updated_at": now_label,
            }
        )

    result = {
        "active_period": "24h",
        "period_order": ["24h", "month", "year", "all"],
        "periods": periods,
        "status_rows": music_status_rows,
        "last_event": last_music_event,
        "source_note": logs_note,
        "updated_at": now_label,
    }
    _STATUS_MUSIC_ANALYTICS_CACHE["key"] = cache_key
    _STATUS_MUSIC_ANALYTICS_CACHE["built_at"] = float(time.time())
    _STATUS_MUSIC_ANALYTICS_CACHE["payload"] = result
    return result


async def status_mongo_payload(
    timeout_seconds: float = 3.5,
    *,
    get_collection_fn: Callable[[str], Any],
    clean_text_fn: Callable[[Any], str],
    asyncio_module: Any,
    time_module: Any,
) -> dict[str, Any]:
    get_collection = get_collection_fn
    _clean_text = clean_text_fn
    asyncio = asyncio_module
    time = time_module
    started = time.perf_counter()
    try:
        collection = await asyncio.wait_for(get_collection("guilds"), timeout=timeout_seconds)
        client = getattr(getattr(collection, "database", None), "client", None)
        if client is not None:
            await asyncio.wait_for(client.admin.command("ping"), timeout=timeout_seconds)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "level": "ok",
            "status": "เชื่อมต่อสำเร็จ",
            "detail": "MongoDB พร้อมใช้งาน",
            "latency_ms": elapsed_ms,
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "level": "error",
            "status": "เชื่อมต่อล้มเหลว",
            "detail": _clean_text(f"{type(exc).__name__}: {exc}")[:220],
            "latency_ms": elapsed_ms,
        }



async def status_ai_payload(
    timeout_seconds: float = 5.0,
    *,
    clean_text_fn: Callable[[Any], str],
    os_module: Any,
    time_module: Any,
    httpx_module: Any,
) -> dict[str, Any]:
    _clean_text = clean_text_fn
    os = os_module
    time = time_module
    httpx = httpx_module
    provider = str(os.getenv("AI_PROVIDER", "opentyphoon")).strip().lower()
    if provider not in {"openai", "ollama", "google", "opentyphoon"}:
        provider = "opentyphoon"

    if provider == "openai":
        api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        model = str(os.getenv("OPENAI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        if not api_key:
            return {
                "level": "error",
                "status": "OpenAI key ไม่พร้อม",
                "detail": "ยังไม่ได้ตั้งค่า OPENAI_API_KEY ใน environment",
                "provider": "OpenAI",
                "model": model,
                "latency_ms": None,
            }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code == 200:
                return {
                    "level": "ok",
                    "status": "OpenAI พร้อมใช้งาน",
                    "detail": f"Provider: OpenAI | Model: {model}",
                    "provider": "OpenAI",
                    "model": model,
                    "latency_ms": elapsed_ms,
                }
            if response.status_code in {401, 403}:
                return {
                    "level": "error",
                    "status": "OpenAI key ไม่ถูกต้อง",
                    "detail": f"HTTP {response.status_code}: ตรวจสอบ API key / billing",
                    "provider": "OpenAI",
                    "model": model,
                    "latency_ms": elapsed_ms,
                }
            return {
                "level": "warn",
                "status": "OpenAI ตอบกลับผิดปกติ",
                "detail": f"HTTP {response.status_code}: {response.text[:140]}",
                "provider": "OpenAI",
                "model": model,
                "latency_ms": elapsed_ms,
            }
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return {
                "level": "error",
                "status": "OpenAI unreachable",
                "detail": _clean_text(f"{type(exc).__name__}: {exc}")[:220],
                "provider": "OpenAI",
                "model": model,
                "latency_ms": elapsed_ms,
            }

    if provider == "google":
        api_key = str(os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip()
        configured_model = str(os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")).strip() or "gemini-2.0-flash"
        base_url = str(
            os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        ).strip().rstrip("/")
        if not api_key:
            return {
                "level": "error",
                "status": "Google key ไม่พร้อม",
                "detail": "ยังไม่ได้ตั้งค่า GOOGLE_API_KEY ใน environment",
                "provider": "Google",
                "model": configured_model,
                "latency_ms": None,
            }

        fallback_models = [
            configured_model,
            "gemini-2.0-flash",
            "gemini-flash-latest",
            "gemini-2.5-flash",
        ]
        candidate_models: list[str] = []
        for row in fallback_models:
            model_name = str(row or "").strip()
            if model_name.lower().startswith("models/"):
                model_name = model_name.split("/", 1)[1].strip()
            if not model_name or model_name in candidate_models:
                continue
            candidate_models.append(model_name)

        started = time.perf_counter()
        try:
            selected_model = configured_model
            used_fallback = False
            last_response: httpx.Response | None = None
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                for candidate in candidate_models:
                    response = await client.get(f"{base_url}/models/{candidate}", params={"key": api_key})
                    last_response = response
                    if response.status_code == 200:
                        selected_model = candidate
                        used_fallback = candidate != configured_model
                        break
                    text_lower = str(response.text or "").lower()
                    model_not_found = (
                        response.status_code == 404
                        and ("model is not found" in text_lower or "not found" in text_lower)
                    )
                    if model_not_found:
                        continue
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    if response.status_code in {401, 403}:
                        return {
                            "level": "error",
                            "status": "Google key ไม่ถูกต้อง",
                            "detail": f"HTTP {response.status_code}: ตรวจสอบ API key / project permission",
                            "provider": "Google",
                            "model": configured_model,
                            "latency_ms": elapsed_ms,
                        }
                    return {
                        "level": "warn",
                        "status": "Google Gemini ตอบกลับผิดปกติ",
                        "detail": f"HTTP {response.status_code}: {response.text[:140]}",
                        "provider": "Google",
                        "model": configured_model,
                        "latency_ms": elapsed_ms,
                    }
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if last_response is not None and last_response.status_code == 200:
                detail = f"Provider: Google | Model: {selected_model}"
                if used_fallback:
                    detail += f" (fallback from {configured_model})"
                return {
                    "level": "ok",
                    "status": "Google Gemini พร้อมใช้งาน",
                    "detail": detail,
                    "provider": "Google",
                    "model": selected_model,
                    "latency_ms": elapsed_ms,
                }
            return {
                "level": "warn",
                "status": "Google Gemini ยังไม่พบโมเดลที่ใช้ได้",
                "detail": f"โมเดลที่ตั้งค่า `{configured_model}` ใช้งานไม่ได้ กรุณาตรวจสอบ GOOGLE_MODEL.",
                "provider": "Google",
                "model": configured_model,
                "latency_ms": elapsed_ms,
            }
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return {
                "level": "error",
                "status": "Google Gemini unreachable",
                "detail": _clean_text(f"{type(exc).__name__}: {exc}")[:220],
                "provider": "Google",
                "model": configured_model,
                "latency_ms": elapsed_ms,
            }

    if provider == "opentyphoon":
        api_key = str(os.getenv("OPENTYPHOON_API_KEY", "")).strip()
        model = str(os.getenv("OPENTYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct")).strip() or "typhoon-v2.5-30b-a3b-instruct"
        base_url = str(os.getenv("OPENTYPHOON_BASE_URL", "https://api.opentyphoon.ai/v1")).strip().rstrip("/")
        if not api_key:
            return {
                "level": "error",
                "status": "OpenTyphoon key ไม่พร้อม",
                "detail": "ยังไม่ได้ตั้งค่า OPENTYPHOON_API_KEY ใน environment",
                "provider": "OpenTyphoon",
                "model": model,
                "latency_ms": None,
            }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code == 200:
                return {
                    "level": "ok",
                    "status": "OpenTyphoon พร้อมใช้งาน",
                    "detail": f"Provider: OpenTyphoon | Model: {model}",
                    "provider": "OpenTyphoon",
                    "model": model,
                    "latency_ms": elapsed_ms,
                }
            if response.status_code in {401, 403}:
                return {
                    "level": "error",
                    "status": "OpenTyphoon key ไม่ถูกต้อง",
                    "detail": f"HTTP {response.status_code}: ตรวจสอบ API key / project permission",
                    "provider": "OpenTyphoon",
                    "model": model,
                    "latency_ms": elapsed_ms,
                }
            return {
                "level": "warn",
                "status": "OpenTyphoon ตอบกลับผิดปกติ",
                "detail": f"HTTP {response.status_code}: {response.text[:140]}",
                "provider": "OpenTyphoon",
                "model": model,
                "latency_ms": elapsed_ms,
            }
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return {
                "level": "error",
                "status": "OpenTyphoon unreachable",
                "detail": _clean_text(f"{type(exc).__name__}: {exc}")[:220],
                "provider": "OpenTyphoon",
                "model": model,
                "latency_ms": elapsed_ms,
            }

    base_url = str(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).strip().rstrip("/")
    model = str(os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b-instruct")).strip() or "qwen2.5:0.5b-instruct"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{base_url}/api/tags")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            return {
                "level": "error",
                "status": "Ollama ตอบกลับผิดปกติ",
                "detail": f"HTTP {response.status_code}: {response.text[:140]}",
                "provider": "Ollama",
                "model": model,
                "latency_ms": elapsed_ms,
            }
        payload = response.json() if "application/json" in str(response.headers.get("content-type", "")).lower() else {}
        model_rows = payload.get("models") if isinstance(payload, dict) else []
        model_names = {
            str(item.get("name") or "").strip().lower()
            for item in list(model_rows or [])
            if isinstance(item, dict)
        }
        model_exists = model.lower() in model_names
        level = "ok" if model_exists else "warn"
        detail = (
            f"พบโมเดล {model} แล้ว"
            if model_exists
            else f"Ollama ออนไลน์ แต่ยังไม่พบโมเดล {model} (แนะนำ: ollama pull {model})"
        )
        return {
            "level": level,
            "status": "Ollama พร้อมใช้งาน" if model_exists else "Ollama ออนไลน์",
            "detail": detail,
            "provider": "Ollama",
            "model": model,
            "latency_ms": elapsed_ms,
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "level": "error",
            "status": "Ollama unreachable",
            "detail": _clean_text(f"{type(exc).__name__}: {exc}")[:220],
            "provider": "Ollama",
            "model": model,
            "latency_ms": elapsed_ms,
        }



async def build_system_status_payload(
    request: Any,
    *,
    status_view: str = "bot",
    ownerbot_runtime_from_db_fn: Callable[[], dict[str, Any]],
    status_runtime_mode_fn: Callable[[dict[str, Any]], dict[str, Any]],
    status_tail_log_lines_fn: Callable[[int], list[str]],
    status_extract_command_errors_fn: Callable[[list[str]], tuple[list[dict[str, Any]], dict[str, int]]],
    status_extract_incidents_fn: Callable[[list[str], int], list[str]],
    status_bot_payload_fn: Callable[..., dict[str, Any]],
    get_discord_service_state_fn: Callable[[], dict[str, Any]],
    status_mongo_payload_fn: Callable[[], Any],
    status_ai_payload_fn: Callable[[], Any],
    status_lavalink_payload_fn: Callable[[bool], dict[str, Any]],
    status_overall_level_fn: Callable[[list[str]], str],
    logs_dir: Any,
    clean_text_fn: Callable[[Any], str],
    bkk_tz: Any,
    psutil_module: Any,
    os_module: Any,
    time_module: Any,
    datetime_module: Any,
    asyncio_module: Any,
) -> dict[str, Any]:
    _ownerbot_runtime_from_db = ownerbot_runtime_from_db_fn
    _status_runtime_mode = status_runtime_mode_fn
    _status_tail_log_lines = status_tail_log_lines_fn
    _status_extract_command_errors = status_extract_command_errors_fn
    _status_extract_incidents = status_extract_incidents_fn
    _status_bot_payload = status_bot_payload_fn
    get_discord_service_state = get_discord_service_state_fn
    _status_mongo_payload = status_mongo_payload_fn
    _status_ai_payload = status_ai_payload_fn
    _status_lavalink_payload = status_lavalink_payload_fn
    _status_overall_level = status_overall_level_fn
    _clean_text = clean_text_fn
    status_view_key = str(status_view or "bot").strip().lower()
    if status_view_key not in {"service", "bot"}:
        status_view_key = "bot"
    is_service_view = status_view_key == "service"
    _BKK_TZ = bkk_tz
    psutil = psutil_module
    os = os_module
    time = time_module
    datetime = datetime_module
    asyncio = asyncio_module
    build_started = time.perf_counter()
    runtime_settings = _ownerbot_runtime_from_db()
    runtime_components = _status_runtime_components()
    run_web_enabled = bool(runtime_components.get("run_web", True))
    run_bot_enabled = bool(runtime_components.get("run_bot", True))
    dashboard_enabled = bool(runtime_components.get("dashboard_enabled", True))
    runtime_payload = _status_runtime_mode(runtime_settings)
    log_lines = _status_tail_log_lines(limit=600)
    command_errors, command_error_by_module = _status_extract_command_errors(log_lines)
    incidents = _status_extract_incidents(log_lines, limit=14)

    discord_runtime_raw = get_discord_service_state()
    discord_runtime_pid = None
    discord_runtime_pid_started_at = None
    try:
        pid_value = discord_runtime_raw.get("pid")
        if isinstance(pid_value, int):
            discord_runtime_pid = int(pid_value)
        elif isinstance(pid_value, str) and pid_value.strip().isdigit():
            discord_runtime_pid = int(pid_value.strip())
    except Exception:
        discord_runtime_pid = None
    try:
        pid_started_value = discord_runtime_raw.get("pid_started_at")
        if isinstance(pid_started_value, (int, float)) and float(pid_started_value) > 0:
            discord_runtime_pid_started_at = float(pid_started_value)
        else:
            pid_started_text = str(pid_started_value or "").strip()
            if pid_started_text:
                parsed_started = float(pid_started_text)
                if parsed_started > 0:
                    discord_runtime_pid_started_at = parsed_started
    except Exception:
        discord_runtime_pid_started_at = None
    discord_runtime_pid_alive = False
    if isinstance(discord_runtime_pid, int) and discord_runtime_pid > 0:
        try:
            runtime_proc = psutil.Process(discord_runtime_pid)
            runtime_status = str(runtime_proc.status() or "").strip().lower()
            pid_running = bool(runtime_proc.is_running() and runtime_status != "zombie")
            if pid_running and isinstance(discord_runtime_pid_started_at, float):
                runtime_started_at = float(runtime_proc.create_time())
                discord_runtime_pid_alive = bool(
                    abs(runtime_started_at - discord_runtime_pid_started_at) <= 2.5
                )
            elif pid_running:
                # Backward-compatible fallback for old writers that did not include
                # pid_started_at: treat as alive only when heartbeat is fresh.
                runtime_updated_at = float((discord_runtime_raw or {}).get("updated_at") or 0.0)
                runtime_age = max(0.0, float(time.time()) - runtime_updated_at) if runtime_updated_at > 0 else 9999.0
                discord_runtime_pid_alive = runtime_age <= 90.0
            else:
                discord_runtime_pid_alive = False
        except Exception:
            discord_runtime_pid_alive = False
    discord_runtime_raw["pid"] = discord_runtime_pid
    discord_runtime_raw["pid_started_at"] = discord_runtime_pid_started_at
    discord_runtime_raw["pid_alive"] = discord_runtime_pid_alive

    bot_payload = _status_bot_payload(
        runtime_settings=runtime_settings,
        command_error_count_by_module=command_error_by_module,
        run_web_enabled=run_web_enabled,
        run_bot_enabled=run_bot_enabled,
        dashboard_enabled=dashboard_enabled,
        external_discord_state=discord_runtime_raw,
    )
    discord_runtime_level = str((discord_runtime_raw or {}).get("level") or "unknown").strip().lower()
    discord_runtime_status_code = (discord_runtime_raw or {}).get("status_code")
    discord_runtime_retry_after = (discord_runtime_raw or {}).get("retry_after")
    discord_runtime_attempt = int((discord_runtime_raw or {}).get("attempt") or 0)
    discord_runtime_message = str((discord_runtime_raw or {}).get("message") or "").strip()
    discord_runtime_updated_at = float((discord_runtime_raw or {}).get("updated_at") or 0.0)
    discord_runtime_age = max(0, int(time.time() - discord_runtime_updated_at)) if discord_runtime_updated_at > 0 else None

    discord_level_map = {
        "ok": "ok",
        "starting": "warn",
        "degraded": "warn",
        "outage": "error",
        "auth_error": "error",
        "stopped": "error",
        "unknown": "warn",
    }
    discord_payload_level = discord_level_map.get(discord_runtime_level, "warn")
    external_discord_visible = bool(
        discord_runtime_pid_alive
        and discord_runtime_level
        and discord_runtime_level not in {"stopped", "unknown"}
    )

    if not run_bot_enabled and external_discord_visible:
        if discord_runtime_level == "ok":
            discord_payload_level = "ok"
            discord_status = "Discord runtime (process อื่น) พร้อมใช้งาน"
        elif discord_runtime_level in {"starting", "degraded"}:
            discord_payload_level = "warn"
            discord_status = "Discord runtime (process อื่น) ยังไม่เสถียร"
        else:
            discord_payload_level = "error"
            discord_status = "Discord runtime (process อื่น) มีปัญหา"
    elif not run_bot_enabled:
        discord_payload_level = "error"
        discord_status = "Discord runtime ถูกปิด"
    elif discord_runtime_level == "outage":
        discord_status = "Discord ล่ม / เชื่อมต่อไม่ได้"
    elif discord_runtime_level == "degraded":
        discord_status = "Discord ตอบกลับช้าหรือจำกัดการเรียก"
    elif discord_runtime_level == "starting":
        discord_status = "กำลังเชื่อมต่อ Discord"
    elif discord_runtime_level == "ok":
        discord_status = "Discord พร้อมใช้งาน"
    elif discord_runtime_level == "auth_error":
        discord_status = "Discord ปฏิเสธการยืนยันตัวตน"
    elif discord_runtime_level == "stopped":
        discord_status = "บอทหยุดการทำงาน"
    else:
        discord_status = "กำลังตรวจสอบสถานะ Discord"

    discord_detail_parts: list[str] = []
    runtime_message_has_age = False
    if discord_runtime_message:
        lowered_runtime_message = discord_runtime_message.lower()
        runtime_message_has_age = ("อัปเดตเมื่อ" in discord_runtime_message) or ("updated" in lowered_runtime_message)
        discord_detail_parts.append(discord_runtime_message)
    if isinstance(discord_runtime_status_code, int):
        discord_detail_parts.append(f"HTTP {discord_runtime_status_code}")
    if isinstance(discord_runtime_retry_after, (int, float)) and float(discord_runtime_retry_after) > 0:
        discord_detail_parts.append(f"retry in {max(1, int(round(float(discord_runtime_retry_after))))}s")
    if discord_runtime_age is not None and not runtime_message_has_age:
        discord_detail_parts.append(f"อัปเดตเมื่อ {discord_runtime_age}s ที่แล้ว")
    if discord_runtime_pid is not None:
        discord_detail_parts.append(
            f"PID {discord_runtime_pid} ({'alive' if discord_runtime_pid_alive else 'offline'})"
        )
    discord_detail = " | ".join(discord_detail_parts) if discord_detail_parts else "ยังไม่มีข้อมูลสถานะ Discord ล่าสุด"

    lavalink_payload = _status_lavalink_payload(bot_running=bool(bot_payload.get("running")))
    if not run_bot_enabled:
        if external_discord_visible:
            lavalink_payload = {
                "level": "warn",
                "status": "Lavalink อยู่บน bot process อื่น",
                "detail": "เว็บ process อ่านสถานะ node ตรงๆ ไม่ได้ ให้ดูจากฝั่ง bot process",
                "nodes": list(lavalink_payload.get("nodes") or []),
            }
        else:
            lavalink_payload = {
                "level": "error",
                "status": "Lavalink ไม่ทำงาน (บอทปิด)",
                "detail": "RUN_COMPONENTS/RUN_BOT ปิดอยู่ ทำให้ระบบเพลงไม่พร้อมใช้งาน",
                "nodes": list(lavalink_payload.get("nodes") or []),
            }
    if is_service_view:
        mongo_task = asyncio.create_task(_status_mongo_payload())
        ai_task = asyncio.create_task(_status_ai_payload())
        mongo_payload, ai_payload = await asyncio.gather(mongo_task, ai_task)
    else:
        mongo_payload = {
            "level": "info",
            "status": "Skipped in bot view",
            "detail": "MongoDB check runs on service view",
            "latency_ms": 0,
        }
        ai_payload = {
            "level": "info",
            "status": "Skipped in bot view",
            "detail": "AI provider check runs on service view",
            "provider": "-",
            "model": "-",
            "latency_ms": 0,
        }

    process = psutil.Process(os.getpid())
    memory_mb = 0.0
    cpu_percent = 0.0
    try:
        memory_mb = float(process.memory_info().rss) / (1024 * 1024)
    except Exception:
        memory_mb = 0.0
    try:
        cpu_percent = float(process.cpu_percent(interval=0.0))
    except Exception:
        cpu_percent = 0.0

    runtime_elapsed_ms = int((time.perf_counter() - build_started) * 1000)
    if not dashboard_enabled:
        web_payload = {
            "level": "error",
            "status": "เว็บไซต์ปิดการทำงาน",
            "detail": "DASHBOARD_ENABLED=False",
            "latency_ms": runtime_elapsed_ms,
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
        }
    elif not run_web_enabled:
        web_payload = {
            "level": "error",
            "status": "เว็บไซต์ไม่ทำงาน",
            "detail": "RUN_COMPONENTS/RUN_WEB ปิดอยู่",
            "latency_ms": runtime_elapsed_ms,
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
        }
    else:
        web_payload = {
            "level": "ok",
            "status": "ตอบสนองปกติ",
            "detail": "ระบบ render ทำงานได้ปกติ",
            "latency_ms": runtime_elapsed_ms,
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
        }

    components = [
        {
            "id": "web",
            "icon": "🌐",
            "title": "Web Dashboard",
            "level": web_payload["level"],
            "status": web_payload["status"],
            "detail": web_payload["detail"],
            "metrics": [
                ("Response", f"{web_payload['latency_ms']} ms"),
                ("Memory", f"{memory_mb:.2f} MB"),
                ("CPU", f"{cpu_percent:.1f}%"),
            ],
        },
        {
            "id": "bot",
            "icon": "🤖",
            "title": "Discord Bot",
            "level": bot_payload["level"],
            "status": bot_payload["status"],
            "detail": bot_payload["detail"],
            "metrics": [
                ("Ping", f"{bot_payload['latency_ms']} ms" if bot_payload.get("latency_ms") is not None else "-"),
                ("Guilds", f"{bot_payload.get('guild_count', 0):,}"),
                ("Users", f"{bot_payload.get('member_count', 0):,}"),
                ("Uptime", str(bot_payload.get("uptime_text") or "-")),
            ],
        },
        {
            "id": "discord_runtime",
            "icon": "🛰️",
            "title": "Discord API / Gateway",
            "level": discord_payload_level,
            "status": discord_status,
            "detail": discord_detail,
            "metrics": [
                ("State", discord_runtime_level or "unknown"),
                ("HTTP", str(discord_runtime_status_code) if isinstance(discord_runtime_status_code, int) else "-"),
                ("Retry", f"{max(1, int(round(float(discord_runtime_retry_after))))}s" if isinstance(discord_runtime_retry_after, (int, float)) and float(discord_runtime_retry_after) > 0 else "-"),
                ("Attempt", f"{discord_runtime_attempt:,}"),
            ],
        },
        {
            "id": "mongo",
            "icon": "🗄️",
            "title": "MongoDB",
            "level": mongo_payload["level"],
            "status": mongo_payload["status"],
            "detail": mongo_payload["detail"],
            "metrics": [
                ("Ping", f"{mongo_payload.get('latency_ms', 0)} ms"),
            ],
        },
        {
            "id": "lavalink",
            "icon": "🎵",
            "title": "Lavalink",
            "level": lavalink_payload["level"],
            "status": lavalink_payload["status"],
            "detail": lavalink_payload["detail"],
            "metrics": [
                ("Nodes", f"{len(lavalink_payload.get('nodes') or [])}"),
                ("Connected", f"{sum(1 for row in (lavalink_payload.get('nodes') or []) if row.get('connected'))}"),
            ],
        },
        {
            "id": "ai",
            "icon": "🧠",
            "title": "AI Provider",
            "level": ai_payload["level"],
            "status": ai_payload["status"],
            "detail": ai_payload["detail"],
            "metrics": [
                ("Provider", str(ai_payload.get("provider") or "-")),
                ("Model", str(ai_payload.get("model") or "-")),
                ("Ping", f"{ai_payload['latency_ms']} ms" if ai_payload.get("latency_ms") is not None else "-"),
            ],
        },
        {
            "id": "ownerbot",
            "icon": "🧭",
            "title": "OwnerBOT Runtime",
            "level": runtime_payload["level"],
            "status": runtime_payload["title"],
            "detail": runtime_payload["description"],
            "metrics": [
                ("Command Response", "เปิด" if runtime_payload.get("commands_enabled") else "ปิด"),
                ("Bot Response", "เปิด" if runtime_payload.get("bot_enabled") else "ปิด"),
                ("Whitelist", str(runtime_payload.get("whitelist_count", 0))),
                ("Tester Guilds", str(runtime_payload.get("tester_count", 0))),
            ],
        },
    ]

    if str(web_payload.get("level") or "") == "error":
        web_error_hint = f"เว็บไซต์ไม่ทำงานหรือเกิดข้อผิดพลาด ({web_payload.get('status')})"
        for item in components:
            component_id = str(item.get("id") or "").strip().lower()
            if component_id not in {"bot", "discord_runtime", "lavalink"}:
                continue
            item["level"] = "error"
            detail = str(item.get("detail") or "").strip()
            if web_error_hint.lower() not in detail.lower():
                item["detail"] = f"{detail} | {web_error_hint}" if detail else web_error_hint

    overall_levels: list[str] = []
    non_critical_ids = {"ai", "lavalink"}
    for item in components:
        level = str(item.get("level") or "info")
        item_id = str(item.get("id") or "").strip().lower()
        # Non-critical components should not force global outage by themselves.
        if level == "error" and item_id in non_critical_ids:
            level = "warn"
        overall_levels.append(level)

    overall_level = _status_overall_level(overall_levels)
    overall_title = {
        "ok": "ระบบพร้อมใช้งาน",
        "warn": "มีบางบริการต้องตรวจสอบ",
        "error": "พบปัญหาที่ต้องแก้ไข",
        "info": "สถานะระบบ",
    }.get(overall_level, "สถานะระบบ")
    overall_detail = {
        "ok": "ทุกบริการพร้อมใช้งาน",
        "warn": "บางบริการยังทำงานได้ แต่ควรตรวจสอบเพิ่มเติม",
        "error": "มี dependency อย่างน้อยหนึ่งรายการล้มเหลว",
        "info": "ข้อมูลสถานะล่าสุด",
    }.get(overall_level, "สรุปสถานะระบบ")

    command_summary = dict(bot_payload.get("command_summary") or {})
    command_summary["error_rows"] = command_errors
    music_analytics = status_music_analytics_payload(
        logs_dir=logs_dir,
        bkk_tz=_BKK_TZ,
        datetime_module=datetime,
        clean_text_fn=_clean_text,
        lavalink_nodes=lavalink_payload.get("nodes") or [],
    )

    return {
        "generated_at": datetime.datetime.now(tz=datetime.timezone.utc).astimezone(_BKK_TZ).strftime("%d/%m/%Y %H:%M:%S"),
        "generated_at_ts": int(time.time()),
        "status_view": status_view_key,
        "request_host": str(getattr(getattr(request, "url", None), "hostname", "") or ""),
        "request_port": str(getattr(getattr(request, "url", None), "port", "") or ""),
        "overall": {
            "level": overall_level,
            "title": overall_title,
            "detail": overall_detail,
        },
        "components": components,
        "command_summary": command_summary,
        "incidents": incidents[:14],
        "lavalink_nodes": lavalink_payload.get("nodes") or [],
        "music_analytics": music_analytics,
    }


