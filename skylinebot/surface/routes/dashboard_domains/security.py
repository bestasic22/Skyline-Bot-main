from __future__ import annotations

from typing import Any, Callable


def dashboard_access_notice_from_state(state: dict[str, Any] | None) -> str:
    payload = (state or {}).get("dashboard_access") if isinstance(state, dict) else {}
    notice = str((payload or {}).get("deny_notice") or "").strip()
    return notice or "ไม่มีสิทธิ์ผู้ดูแลกิลด์ และไม่มีสิทธิ์การตั้งค่ากิลด์"


def dashboard_can_edit_settings_from_state(state: dict[str, Any] | None) -> bool:
    payload = (state or {}).get("dashboard_access") if isinstance(state, dict) else {}
    return bool((payload or {}).get("can_edit_settings"))


def blocked_context_redirect_or_dashboard(
    *,
    session: dict[str, Any] | None,
    current_guild: dict[str, Any] | None,
    state: dict[str, Any] | None,
    guild_id: int,
    request: Any | None = None,
    tab_slug: str | None = None,
    dashboard_can_edit_settings_fn: Callable[[dict[str, Any] | None], bool],
    dashboard_access_notice_fn: Callable[[dict[str, Any] | None], str],
    ownerbot_tab_block_reason_fn: Callable[..., str | None],
    ownerbot_runtime_notice_fn: Callable[[dict[str, Any] | None], str | None],
    redirect_response_cls: Callable[..., Any],
    urlencode_fn: Callable[[dict[str, str]], str],
) -> Any:
    def _resolve_tab_slug() -> str | None:
        raw_tab = str(tab_slug or "").strip().lower()
        if raw_tab:
            return "welcome" if raw_tab == "welcomer" else raw_tab
        if not request:
            return None
        path = str(getattr(getattr(request, "url", None), "path", "") or "")
        parts = [part for part in path.split("/") if part]
        try:
            guild_index = parts.index("guild")
        except ValueError:
            return None
        next_index = guild_index + 2
        if next_index >= len(parts):
            return "overview"
        resolved = str(parts[next_index] or "").strip().lower()
        if not resolved:
            return "overview"
        return "welcome" if resolved == "welcomer" else resolved

    if not session:
        return redirect_response_cls("/dashboard", status_code=303)
    if current_guild:
        if not dashboard_can_edit_settings_fn(state):
            deny_notice = dashboard_access_notice_fn(state)
            encoded = urlencode_fn({"notice": deny_notice}).split("=", 1)[1]
            return redirect_response_cls(
                f"/dashboard/guild/{guild_id}?notice={encoded}",
                status_code=303,
            )
        resolved_tab = _resolve_tab_slug()
        if resolved_tab:
            tab_block_reason = ownerbot_tab_block_reason_fn(
                session=session,
                tab_slug=resolved_tab,
            )
            if tab_block_reason:
                encoded = urlencode_fn({"notice": tab_block_reason}).split("=", 1)[1]
                return redirect_response_cls(
                    f"/dashboard/guild/{guild_id}?notice={encoded}",
                    status_code=303,
                )
        return None
    notice = ownerbot_runtime_notice_fn(state)
    if notice:
        encoded = urlencode_fn({"notice": notice}).split("=", 1)[1]
        return redirect_response_cls(
            f"/dashboard/guild/{guild_id}?notice={encoded}",
            status_code=303,
        )
    return redirect_response_cls("/dashboard", status_code=303)

