from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

DEFAULT_DEVELOPER_SOCIAL_KEY = "__default__"


def normalize_social_url(
    value: Any,
    *,
    clean_text_fn: Callable[[Any], str],
    allowed_hosts: tuple[str, ...],
) -> str:
    raw = clean_text_fn(value).strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    if not any(host == item or host.endswith(f".{item}") for item in allowed_hosts):
        return ""
    return raw


def normalize_social_icon(
    value: Any,
    platform: str,
    *,
    clean_text_fn: Callable[[Any], str],
    default_icons: dict[str, str],
) -> str:
    default_icon = default_icons.get(platform, "")
    icon = clean_text_fn(value).strip()
    if not icon:
        return default_icon
    icon_lower = icon.lower()
    if icon_lower.startswith("http://") or icon_lower.startswith("https://"):
        parsed = urlparse(icon)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            return icon[:512]
    if icon_lower.startswith("www."):
        return f"https://{icon}"[:512]
    if icon_lower.startswith("//"):
        return f"https:{icon}"[:512]
    if icon_lower.startswith("/"):
        return icon[:512]
    return icon[:48]


def parse_developer_social_links(
    value: Any,
    *,
    social_platform_keys: tuple[str, ...],
    normalize_social_url_fn: Callable[[Any], str],
    normalize_social_url_for_platform_fn: Callable[[Any, str], str] | None = None,
    normalize_social_icon_fn: Callable[[Any, str], str],
    json_loads_fn: Callable[[str], Any],
) -> dict[str, dict[str, dict[str, str]]]:
    src = value
    if isinstance(src, str):
        raw = src.strip()
        if not raw:
            return {}
        try:
            src = json_loads_fn(raw)
        except Exception:
            return {}

    out: dict[str, dict[str, dict[str, str]]] = {}

    if isinstance(src, list):
        for row in src:
            if not isinstance(row, dict):
                continue
            dev_id = str(row.get("dev_id") or row.get("user_id") or row.get("developer_id") or "").strip()
            platform = str(row.get("platform") or "").strip().lower()
            if platform not in social_platform_keys:
                continue
            if not dev_id:
                if platform == "discord":
                    continue
                dev_id = DEFAULT_DEVELOPER_SOCIAL_KEY
            if normalize_social_url_for_platform_fn:
                clean_url = normalize_social_url_for_platform_fn(row.get("url"), platform)
            else:
                clean_url = normalize_social_url_fn(row.get("url"))
            if not clean_url:
                continue
            clean_icon = normalize_social_icon_fn(row.get("icon"), platform)
            out.setdefault(dev_id, {})[platform] = {"url": clean_url, "icon": clean_icon}
        return out

    if not isinstance(src, dict):
        return {}

    for dev_key, payload in src.items():
        dev_id = str(dev_key or "").strip()
        if not dev_id:
            continue
        is_default_key = dev_id == DEFAULT_DEVELOPER_SOCIAL_KEY
        payload_map = payload if isinstance(payload, dict) else {}
        row: dict[str, dict[str, str]] = {}
        for platform in social_platform_keys:
            platform_payload = payload_map.get(platform)
            if isinstance(platform_payload, dict):
                if normalize_social_url_for_platform_fn:
                    clean_url = normalize_social_url_for_platform_fn(platform_payload.get("url"), platform)
                else:
                    clean_url = normalize_social_url_fn(platform_payload.get("url"))
                clean_icon = normalize_social_icon_fn(platform_payload.get("icon"), platform)
            else:
                if normalize_social_url_for_platform_fn:
                    clean_url = normalize_social_url_for_platform_fn(platform_payload, platform)
                else:
                    clean_url = normalize_social_url_fn(platform_payload)
                clean_icon = normalize_social_icon_fn("", platform)
            if is_default_key and platform == "discord":
                continue
            if clean_url:
                row[platform] = {
                    "url": clean_url,
                    "icon": clean_icon,
                }
        if row:
            out[dev_id] = row
    return out


def developer_social_url(
    dev_payload: dict[str, Any],
    platform: str,
    *,
    fallback: str,
    normalize_social_url_fn: Callable[[Any], str],
    normalize_social_url_for_platform_fn: Callable[[Any, str], str] | None = None,
) -> str:
    if not isinstance(dev_payload, dict):
        return fallback
    row = dev_payload.get(platform)
    if isinstance(row, dict):
        if normalize_social_url_for_platform_fn:
            url = normalize_social_url_for_platform_fn(row.get("url"), platform)
        else:
            url = normalize_social_url_fn(row.get("url"))
        return url or fallback
    if isinstance(row, str):
        if normalize_social_url_for_platform_fn:
            url = normalize_social_url_for_platform_fn(row, platform)
        else:
            url = normalize_social_url_fn(row)
        return url or fallback
    return fallback


def developer_social_icon(
    dev_payload: dict[str, Any],
    platform: str,
    *,
    normalize_social_icon_fn: Callable[[Any, str], str],
    default_icons: dict[str, str],
) -> str:
    if not isinstance(dev_payload, dict):
        return default_icons.get(platform, "")
    row = dev_payload.get(platform)
    if isinstance(row, dict):
        return normalize_social_icon_fn(row.get("icon"), platform)
    return default_icons.get(platform, "")


def render_developer_social_icon(
    icon_value: Any,
    platform: str,
    *,
    normalize_social_icon_fn: Callable[[Any, str], str],
    default_icons: dict[str, str],
    social_labels: dict[str, str],
    escape_fn: Callable[[Any], str],
) -> str:
    icon = normalize_social_icon_fn(icon_value, platform)
    default_icon = default_icons.get(platform, "")
    if not icon:
        icon = default_icon
    icon_lower = icon.lower()
    is_remote_icon = icon_lower.startswith("http://") or icon_lower.startswith("https://")
    is_relative_icon = icon.startswith("/") and not icon.startswith("//")
    if is_remote_icon or is_relative_icon:
        icon_url = escape_fn(icon)
        alt = escape_fn(social_labels.get(platform, platform).strip() or "Social")
        return (
            f'<img class="dev-social-icon-img" src="{icon_url}" alt="{alt}" '
            f'loading="lazy" decoding="async" referrerpolicy="no-referrer" '
            f'onerror="this.onerror=null;this.replaceWith(document.createTextNode(\'{escape_fn(default_icon)}\'));">'
        )
    return escape_fn(icon)


def developer_social_links_from_system(
    *,
    raw_cache: Any,
    raw_runtime: Any,
    env_payload: Any,
    parse_developer_social_links_fn: Callable[[Any], dict[str, dict[str, dict[str, str]]]],
    json_loads_fn: Callable[[str], Any],
) -> dict[str, dict[str, dict[str, str]]]:
    from_cache = parse_developer_social_links_fn(raw_cache)
    if from_cache:
        return from_cache

    if raw_runtime:
        try:
            runtime_payload = json_loads_fn(str(raw_runtime))
            if isinstance(runtime_payload, dict):
                from_runtime = parse_developer_social_links_fn(runtime_payload.get("developer_social_links"))
                if from_runtime:
                    return from_runtime
        except Exception:
            pass

    return parse_developer_social_links_fn(env_payload)
