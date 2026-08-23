from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import urlparse


def session_user_id(session: dict[str, Any] | None) -> int | None:
    if not session:
        return None
    user = session.get("user") or {}
    raw = user.get("id")
    try:
        return int(raw)
    except Exception:
        return None


def session_from_request(
    request: Any,
    *,
    get_session_fn: Callable[[str | None], dict[str, Any] | None],
    session_cookie: str,
) -> dict[str, Any] | None:
    cookie_value = None
    try:
        cookie_value = request.cookies.get(session_cookie)
    except Exception:
        cookie_value = None
    return get_session_fn(cookie_value)


def dashboard_base_url_from_request(request: Any | None = None) -> str | None:
    if request is None:
        return None
    raw_host = (
        str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
        or str(request.headers.get("host") or "").strip()
        or str(getattr(getattr(request, "url", None), "netloc", "") or "").strip()
    )
    if not raw_host:
        return None
    if any(ch in raw_host for ch in ("/", "\\", " ", "\r", "\n", "\x00", "@")):
        return None
    if not re.match(r"^[A-Za-z0-9.\-\[\]:]+$", raw_host):
        return None

    proto_header = (
        str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    )
    request_scheme = str(getattr(getattr(request, "url", None), "scheme", "") or "").strip().lower()
    scheme = proto_header if proto_header in {"http", "https"} else request_scheme
    if scheme not in {"http", "https"}:
        scheme = "http"
    return f"{scheme}://{raw_host}"


def normalize_dashboard_base_url(raw_value: Any) -> str | None:
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    candidate = raw if "://" in raw else f"http://{raw}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return None
    scheme = str(parsed.scheme or "").strip().lower()
    netloc = str(parsed.netloc or "").strip()
    if scheme not in {"http", "https"} or not netloc:
        return None
    return f"{scheme}://{netloc}"


def dashboard_callback_url(
    request: Any | None = None,
    *,
    base_url_override: str | None = None,
    normalize_base_url_fn: Callable[[Any], str | None],
    configured_dashboard_base_url: Any,
    web_port: Any,
) -> str:
    override_base = normalize_base_url_fn(base_url_override)
    if override_base:
        return f"{override_base.rstrip('/')}/dashboard/auth/callback"

    dynamic_base = dashboard_base_url_from_request(request)
    configured_base = normalize_base_url_fn(configured_dashboard_base_url)

    if dynamic_base and configured_base:
        try:
            dynamic_host = (urlparse(dynamic_base).hostname or "").lower().strip()
            configured_host = (urlparse(configured_base).hostname or "").lower().strip()
        except Exception:
            dynamic_host = ""
            configured_host = ""

        if dynamic_host and configured_host and dynamic_host == configured_host:
            return f"{dynamic_base.rstrip('/')}/dashboard/auth/callback"
        return f"{configured_base.rstrip('/')}/dashboard/auth/callback"

    if dynamic_base:
        return f"{dynamic_base.rstrip('/')}/dashboard/auth/callback"
    if configured_base:
        return f"{configured_base.rstrip('/')}/dashboard/auth/callback"
    return f"http://localhost:{web_port}/dashboard/auth/callback"

