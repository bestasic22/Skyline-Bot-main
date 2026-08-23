from __future__ import annotations

import asyncio
import base64
import html
import hmac
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from ..dashboard_core import (
    BOT_CONFIG,
    DISCORD_API,
    HTMLResponse,
    JSONResponse,
    LOGS_DIR,
    REDEEM_CODE_TYPES,
    RedirectResponse,
    Request,
    SESSION_COOKIE,
    TEMPLATES_DIR,
    _append_donatebot_verify_log,
    _build_system_status_payload,
    _bot_invite_url,
    _dashboard_callback_url,
    _clean_text,
    _donate_slip_status_label,
    _ensure_dashboard_config_cache,
    _fetch_donatebot_top_donors,
    _find_redeem_code_data,
    _load_dashboard_user_profile,
    _load_oauth_profile,
    _manageable_guilds_live,
    _oauth_authorize_url,
    _parse_form,
    _is_dashboard_admin,
    _looks_like_active_premium_from_state,
    _command_catalog,
    _plan_display_name,
    _price_html_from_quote,
    _pricing_quote_from_snapshot,
    _premium_feature_rows_from_live_rules,
    _premium_table_plan_tiers,
    _render_layout,
    _render_donatebot_hub,
    _render_commands_help_page,
    _render_feature_landing_page,
    _render_guild_picker,
    _render_invite_hub,
    _render_login,
    _render_premium_doc_page,
    _render_public_doc_page,
    _render_redeem_web_page,
    _render_report_page,
    _render_system_status_page,
    _render_user_profile_premium_history_page,
    _render_user_profile_settings_page,
    _render_user_profile_topup_history_page,
    _required_plan_for_command,
    _global_copyright_text,
    _report_channel_id_from_runtime,
    _report_rate_limited,
    _session_from_request,
    _session_user_id,
    _ownerbot_runtime_from_db,
    _support_guild_id_from_env,
    _support_status_public_url,
    _validate_promote_content,
    _validate_report_challenge,
    _verify_truemoney_gift_link,
    change_guild_subscription,
    change_user_subscription,
    consume_oauth_state,
    create_session,
    datetime,
    destroy_session,
    discord,
    get_bot,
    guild_growth,
    httpx,
    cache,
    storage,
    urlencode,
)
from skylinebot.style import urls as style_urls
from skylinebot.surface.runtime import get_discord_service_state
from skylinebot.surface.runtime import set_discord_service_state
from skylinebot.console.logging import logger
from skylinebot.workflows import billing as billing_workflow
from skylinebot.workflows.redeem_control import (
    finalize_redeem_claim_success,
    redeem_block_reason,
    normalize_redeem_code,
    normalize_redeem_row,
    redeem_reason_message_th,
    reserve_redeem_claim,
    rollback_redeem_claim,
)
from skylinebot.utils import fancy_text

PUBLIC_PAGES_DIR = Path(TEMPLATES_DIR) / "public_pages"
PUBLIC_PAGE_TEMPLATES: dict[str, str] = {
    "support": "support_page.html",
    "rule_hub": "rule_page.html",
    "rule_server_support": "rule_serversupport_page.html",
    "tags": "tags_page.html",
    "personalizer": "personalizer_page.html",
    "leaderboard": "leaderboard_page.html",
    "invitebot": "invitebot_page.html",
    "serversupport": "serversupport_page.html",
    "interactions_endpoint": "interactions_endpoint_page.html",
    "linked_role_verify": "linked_role_verify_page.html",
    "privacy_policy": "privacy_policy_page.html",
    "terms_of_service": "terms_of_service_page.html",
    "studio_split_preview": "studio_split_preview_page.html",
}
_STATUS_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}
REPORT_MAX_IMAGE_BYTES = 8 * 1024 * 1024
CONTACT_EXTERNAL_URL = str(style_urls.CONTACT or "https://niceshopallforme.web.app/contact").strip()
_PUBLIC_FOOTER_SECTION_RE = re.compile(
    r"<section\s+class=[\"']public-footer[\"'][^>]*>.*?</section>",
    flags=re.IGNORECASE | re.DOTALL,
)
_MENTION_ID_RE = re.compile(r"<@!?(\d{15,22})>")
PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY = "promote_suspended_guilds_v1"
DONATEBOT_DISCORD_ID_RE = re.compile(r"^\d{15,22}$")
DONATEBOT_AVATAR_MAX_BYTES = 1 * 1024 * 1024
DONATEBOT_ALLOWED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
DONATEBOT_SLIP_MAX_BYTES = 12 * 1024 * 1024
DONATEBOT_ALLOWED_SLIP_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
DONATEBOT_TRUEMONEY_GIFT_RE = re.compile(
    r"^https?://gift\.truemoney\.com/campaign/\?v=[A-Za-z0-9_-]{8,}$",
    re.I,
)
DONATEBOT_AIFORTHAI_IMAGE_MODERATION_ENDPOINT = "https://api.aiforthai.in.th/nsfw"
DONATEBOT_AIFORTHAI_IMAGE_MODERATION_FALLBACK_ENDPOINT = "https://api.aiforthai.in.th/violent"
DONATEBOT_AIFORTHAI_DEFAULT_THRESHOLD = 0.72
DONATEBOT_AVATAR_OCR_SCAM_TOKENS: tuple[str, ...] = (
    "discord.gift/",
    "free nitro",
    "wallet connect",
    "walletconnect",
    "seed phrase",
    "private key",
    "token logger",
    "token grabber",
    "malware",
)


def _safe_int(raw_value: object, default: int = 0) -> int:
    try:
        text = str(raw_value or "").strip()
        if not text:
            return int(default)
        return int(text)
    except Exception:
        return int(default)


def _discordbotlist_vote_default_url() -> str:
    env_url = str(os.getenv("DISCORDBOTLIST_VOTE_URL", "") or "").strip()
    if env_url.lower().startswith(("http://", "https://")):
        return env_url
    runtime_url = str(style_urls.VOTE or "").strip()
    if runtime_url and "discordbotlist.com" in runtime_url.lower():
        return runtime_url
    bot_id = str(getattr(BOT_CONFIG, "DISCORD_CLIENT_ID", "") or "").strip()
    if bot_id.isdigit():
        return f"https://discordbotlist.com/bots/{bot_id}/upvote"
    return "https://discordbotlist.com/"


def _discordbotlist_vote_runtime_settings() -> dict[str, Any]:
    runtime = _ownerbot_runtime_from_db()
    result_channel_id = _safe_int(runtime.get("discordbotlist_vote_result_channel_id"), 0)
    embed_channel_id = _safe_int(runtime.get("discordbotlist_vote_embed_channel_id"), 0)
    vote_url = str(runtime.get("discordbotlist_vote_button_url") or "").strip()
    if not vote_url:
        vote_url = _discordbotlist_vote_default_url()
    secret = str(runtime.get("discordbotlist_vote_webhook_secret") or "").strip()
    if not secret:
        secret = str(os.getenv("DISCORDBOTLIST_WEBHOOK_SECRET", "") or "").strip()
    if not secret:
        secret = str(os.getenv("DISCORDBOTLIST_TOKEN", "") or "").strip()
    return {
        "result_channel_id": result_channel_id if result_channel_id > 0 else 0,
        "embed_channel_id": embed_channel_id if embed_channel_id > 0 else 0,
        "vote_url": vote_url,
        "webhook_secret": secret,
    }


def _discordbotlist_avatar_url(user_id: str, avatar_hash: str) -> str:
    uid = str(user_id or "").strip()
    avatar = str(avatar_hash or "").strip()
    if uid and avatar:
        return f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png?size=256"
    return "https://cdn.discordapp.com/embed/avatars/0.png"


def _public_origin(request: Request | None = None) -> str:
    configured = str(getattr(BOT_CONFIG, "DASHBOARD_BASE_URL", "") or "").strip().rstrip("/")
    if configured:
        return configured
    if request is None:
        return f"http://localhost:{int(getattr(BOT_CONFIG, 'WEB_PORT', 80) or 80)}"

    forwarded_host = str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    request_host = str(request.headers.get("host") or "").strip()
    host = forwarded_host or request_host or str(getattr(getattr(request, "url", None), "netloc", "") or "").strip()
    if not host:
        return f"http://localhost:{int(getattr(BOT_CONFIG, 'WEB_PORT', 80) or 80)}"

    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    request_scheme = str(getattr(getattr(request, "url", None), "scheme", "") or "").strip().lower()
    scheme = forwarded_proto if forwarded_proto in {"http", "https"} else request_scheme
    if scheme not in {"http", "https"}:
        scheme = "http"
    return f"{scheme}://{host}".rstrip("/")


def _discord_interactions_transport_mode() -> str:
    raw = str(os.getenv("DISCORD_INTERACTIONS_TRANSPORT", "") or "").strip().lower()
    if raw in {"http", "webhook", "endpoint", "interactions"}:
        return "http"
    return "gateway"


def _build_developer_portal_context(request: Request) -> dict[str, str]:
    base_url = _public_origin(request)
    dashboard_url = f"{base_url}/dashboard"
    app_name = str(getattr(BOT_CONFIG, "NAME", "") or "SkylineBOT").strip() or "SkylineBOT"
    client_id = str(getattr(BOT_CONFIG, "DISCORD_CLIENT_ID", "") or "").strip() or "YOUR_APPLICATION_ID"
    interactions_mode = _discord_interactions_transport_mode()
    suggested_endpoint_url = f"{base_url}/api/discord/interactions"
    if interactions_mode == "http":
        recommendation_value = suggested_endpoint_url
        recommendation_note = (
            "HTTP interactions mode is enabled. You can set this URL in Discord Developer Portal."
        )
    else:
        recommendation_value = "Leave empty (Gateway mode)"
        recommendation_note = (
            "Gateway mode is active by default. Do not set Interaction Endpoint URL "
            "until command handling is migrated to HTTP interactions."
        )
    discord_install_params = urlencode({"client_id": client_id})
    oauth_install_params = urlencode(
        {
            "client_id": client_id,
            "scope": "bot applications.commands",
            "permissions": "8",
            "integration_type": "0",
        }
    )
    path_text = str(getattr(getattr(request, "url", None), "path", "") or "").strip().lower()
    resolved_public_lang = "en" if path_text.startswith("/en/") or path_text == "/en" else "th"

    return {
        "APP_NAME": app_name,
        "PUBLIC_LANG": resolved_public_lang,
        "CLIENT_ID": client_id,
        "BASE_URL": base_url,
        "DASHBOARD_URL": dashboard_url,
        "TAGS_URL": f"{base_url}/tags",
        "INVITE_PAGE_URL": f"{base_url}/invite",
        "DISCORD_PROVIDED_INSTALL_URL": f"https://discord.com/oauth2/authorize?{discord_install_params}",
        "DISCORD_CUSTOM_INSTALL_URL": f"https://discord.com/oauth2/authorize?{oauth_install_params}",
        "INTERACTION_DOC_PAGE_URL": f"{base_url}/interactions-endpoint",
        "SUGGESTED_INTERACTION_ENDPOINT_URL": suggested_endpoint_url,
        "INTERACTIONS_TRANSPORT_MODE": interactions_mode,
        "INTERACTION_ENDPOINT_RECOMMENDATION_VALUE": recommendation_value,
        "INTERACTION_ENDPOINT_RECOMMENDATION_NOTE": recommendation_note,
        "LINKED_ROLE_VERIFY_URL": f"{base_url}/linked-role-verify",
        "TERMS_URL": f"{base_url}/terms-of-service",
        "PRIVACY_URL": f"{base_url}/privacy-policy",
        "CONTACT_URL": str(CONTACT_EXTERNAL_URL or f"{base_url}/contact"),
        "CURRENT_YEAR": str(datetime.datetime.now().year),
    }


def _render_public_html_template(template_name: str, context: dict[str, str]) -> str:
    template_path = PUBLIC_PAGES_DIR / template_name
    try:
        content = template_path.read_text(encoding="utf-8")
    except Exception as error:
        logger.error(f"Failed to load dashboard public template {template_path}: {error}")
        return (
            "<!DOCTYPE html><html lang='th'><head><meta charset='utf-8'>"
            "<title>Template not found</title></head><body>"
            "<h1>Page not found</h1>"
            "<p>Template page is missing. Please check server templates.</p>"
            "</body></html>"
        )

    rendered = content
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{{{key}}}}}}}", str(value))
        rendered = rendered.replace(f"{{{{{key}}}}}", html.escape(str(value), quote=True))
    return _apply_global_public_footer(rendered)


def _public_language_switcher_markup() -> str:
    return r"""
<div id="skyline-public-lang-switcher" class="public-lang-switcher" data-no-auto-i18n="1">
  <button type="button" class="public-lang-switcher-btn" aria-label="Switch language" title="Switch language">
    <span class="public-lang-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" role="img" focusable="false">
        <path d="M12 2c4.971 0 9 4.029 9 9s-4.029 9-9 9-9-4.029-9-9 4.029-9 9-9Zm6.92 8h-3.05a14.58 14.58 0 0 0-1.25-4.2A7.02 7.02 0 0 1 18.92 10ZM12 4.05c-.83 1.16-1.48 3.05-1.74 5.95h3.48C13.48 7.1 12.83 5.21 12 4.05ZM9.38 5.8A14.58 14.58 0 0 0 8.13 10H5.08a7.02 7.02 0 0 1 4.3-4.2ZM4.55 12c0 .69.1 1.35.28 1.98h3.15A19.3 19.3 0 0 1 8 12c0-.67.03-1.34.09-1.98H4.84A7.03 7.03 0 0 0 4.55 12Zm.53 3.98h3.05c.25 1.57.67 2.99 1.25 4.2a7.02 7.02 0 0 1-4.3-4.2Zm5.17 0h3.5c-.26 2.9-.91 4.79-1.75 5.95-.84-1.16-1.49-3.05-1.75-5.95Zm4.37 4.2c.58-1.21 1-2.63 1.25-4.2h3.05a7.02 7.02 0 0 1-4.3 4.2Zm1.38-6.2h3.17c.18-.63.28-1.29.28-1.98s-.1-1.35-.28-1.98h-3.17c.06.64.1 1.3.1 1.98s-.04 1.34-.1 1.98Z"></path>
      </svg>
    </span>
    <span class="public-lang-label">EN</span>
  </button>
</div>
<style id="skyline-public-lang-switcher-style">
  .public-lang-switcher {
    position: fixed;
    right: 14px;
    bottom: calc(14px + env(safe-area-inset-bottom, 0px));
    z-index: 9999;
    pointer-events: none;
  }
  .public-lang-switcher-btn {
    pointer-events: auto;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 38px;
    border: 1px solid rgba(141, 178, 255, 0.5);
    border-radius: 999px;
    padding: 7px 12px;
    background: linear-gradient(135deg, rgba(36, 68, 138, 0.94), rgba(48, 117, 217, 0.92));
    color: #f3f8ff;
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    line-height: 1;
    cursor: pointer;
    box-shadow: 0 16px 30px rgba(6, 15, 34, 0.45);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background .18s ease;
  }
  .public-lang-switcher-btn:hover {
    transform: translateY(-1px);
    border-color: rgba(182, 211, 255, 0.68);
    background: linear-gradient(135deg, rgba(44, 82, 164, 0.96), rgba(57, 131, 234, 0.95));
    box-shadow: 0 18px 34px rgba(6, 15, 34, 0.52);
  }
  .public-lang-icon {
    width: 15px;
    height: 15px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    opacity: 0.96;
  }
  .public-lang-icon svg {
    width: 15px;
    height: 15px;
    fill: currentColor;
    display: block;
  }
  .public-lang-label {
    min-width: 2ch;
    display: inline-block;
    text-align: center;
  }
  @media (max-width: 900px) {
    .public-lang-switcher {
      right: 10px;
      bottom: calc(10px + env(safe-area-inset-bottom, 0px));
    }
    .public-lang-switcher-btn {
      min-height: 36px;
      padding: 6px 10px;
      font-size: 0.78rem;
    }
  }
</style>
<script id="skyline-public-lang-switcher-script">
  (() => {
    const root = document.getElementById("skyline-public-lang-switcher");
    if (!(root instanceof HTMLElement)) return;
    const button = root.querySelector(".public-lang-switcher-btn");
    const labelNode = root.querySelector(".public-lang-label");
    if (!(button instanceof HTMLButtonElement) || !(labelNode instanceof HTMLElement)) return;

    const readCookieLang = () => {
      const cookieText = String(document.cookie || "");
      const parts = cookieText.split(";").map((part) => part.trim()).filter(Boolean);
      for (const part of parts) {
        if (!part.toLowerCase().startsWith("skyline_lang=")) continue;
        const value = part.slice("skyline_lang=".length).trim().toLowerCase();
        return value === "en" ? "en" : "th";
      }
      return "";
    };
    const readHtmlLang = () => {
      const htmlLang = String((document.documentElement && document.documentElement.lang) || "").trim().toLowerCase();
      return htmlLang.startsWith("en") ? "en" : "th";
    };
    const stripLangPrefix = (path) => String(path || "/").replace(/^\/(?:th|en)(?=\/|$)/i, "") || "/";

    let currentLang = readCookieLang() || readHtmlLang();
    if (currentLang !== "en") currentLang = "th";

    const syncLabel = () => {
      const nextLang = currentLang === "en" ? "th" : "en";
      labelNode.textContent = nextLang.toUpperCase();
      const actionLabel = nextLang === "en" ? "Switch to English" : "Switch to Thai";
      button.setAttribute("aria-label", actionLabel);
      button.setAttribute("title", actionLabel);
    };

    button.addEventListener("click", () => {
      const targetLang = currentLang === "en" ? "th" : "en";
      const currentPath = window.location && window.location.pathname ? window.location.pathname : "/";
      const suffixPath = stripLangPrefix(currentPath);
      const normalizedSuffix = suffixPath.startsWith("/") ? suffixPath : "/" + suffixPath;
      const search = window.location && window.location.search ? window.location.search : "";
      const hash = window.location && window.location.hash ? window.location.hash : "";
      const targetUrl = "/" + targetLang + normalizedSuffix + search + hash;
      window.location.assign(targetUrl);
    });

    syncLabel();
  })();
</script>
"""


def _apply_public_language_switcher(rendered_html: str) -> str:
    if 'id="skyline-public-lang-switcher"' in rendered_html or "id='skyline-public-lang-switcher'" in rendered_html:
        return rendered_html
    switcher_markup = _public_language_switcher_markup()
    if "</body>" in rendered_html:
        return rendered_html.replace("</body>", f"{switcher_markup}\n</body>", 1)
    return f"{rendered_html}\n{switcher_markup}"


def _apply_global_public_footer(rendered_html: str) -> str:
    footer_markup = f'<section class="public-footer">{html.escape(_global_copyright_text(), quote=True)}</section>'
    with_footer = rendered_html
    if _PUBLIC_FOOTER_SECTION_RE.search(rendered_html):
        with_footer = _PUBLIC_FOOTER_SECTION_RE.sub(footer_markup, rendered_html, count=1)
    elif "</main>" in rendered_html:
        with_footer = rendered_html.replace("</main>", f"    {footer_markup}\n  </main>", 1)
    elif "</body>" in rendered_html:
        with_footer = rendered_html.replace("</body>", f"  {footer_markup}\n</body>", 1)
    else:
        with_footer = f"{rendered_html}\n{footer_markup}"
    return _apply_public_language_switcher(with_footer)


def _render_developer_portal_page(request: Request, template_name: str) -> str:
    return _render_public_html_template(template_name, _build_developer_portal_context(request))


def _promote_history_display_time(raw_value: object) -> str:
    parsed: datetime.datetime | None = None
    if isinstance(raw_value, datetime.datetime):
        parsed = raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
    elif isinstance(raw_value, str):
        text = str(raw_value or "").strip()
        if text:
            try:
                parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                parsed = None
    if not isinstance(parsed, datetime.datetime):
        return "-"
    return parsed.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _promote_history_clip(text: object, limit: int = 260) -> str:
    value = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def _promote_history_source_label(raw_value: object) -> str:
    source = str(raw_value or "").strip().lower()
    if source == "web":
        return "Web Dashboard"
    if source == "discord":
        return "Discord Channel"
    return "Unknown"


def _promote_history_author_display(row: dict[str, Any]) -> str:
    author_name = str(row.get("author_name") or "").replace("\r", " ").replace("\n", " ").strip()
    author_label = str(row.get("author_label") or "").replace("\r", " ").replace("\n", " ").strip()
    author_id = _safe_int(row.get("author_id"), 0)

    display_name = author_name or author_label or "Unknown"
    mention_full_match = _MENTION_ID_RE.fullmatch(display_name)
    if mention_full_match:
        display_name = "Unknown"
        if author_id <= 0:
            author_id = _safe_int(mention_full_match.group(1), 0)

    if author_id <= 0:
        for candidate in (author_label, author_name):
            mention_match = _MENTION_ID_RE.search(candidate)
            if mention_match:
                author_id = _safe_int(mention_match.group(1), 0)
                break
        if author_id <= 0:
            raw_digit_match = re.search(r"\d{15,22}", f"{author_label} {author_name}")
            if raw_digit_match:
                author_id = _safe_int(raw_digit_match.group(0), 0)

    normalized_name = display_name.strip() or "Unknown"
    if author_id > 0 and str(author_id) not in normalized_name:
        return f"{normalized_name} ({author_id})"
    return normalized_name


def _promote_hidden_note(row: dict[str, Any]) -> str:
    note = str(row.get("owner_note") or "").replace("\r", " ").replace("\n", " ").strip()
    return note[:500]


def _promote_is_hidden(row: dict[str, Any]) -> bool:
    return bool(row.get("hidden"))


def _promote_suspension_map_from_raw(raw_value: object) -> dict[str, dict[str, str]]:
    parsed: dict[str, Any] = {}
    if isinstance(raw_value, dict):
        parsed = raw_value
    elif isinstance(raw_value, str):
        text = str(raw_value or "").strip()
        if text:
            try:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    parsed = decoded
            except Exception:
                parsed = {}
    out: dict[str, dict[str, str]] = {}
    for key, value in parsed.items():
        gid = _safe_int(key, 0)
        if gid <= 0:
            continue
        row = value if isinstance(value, dict) else {}
        out[str(gid)] = {
            "note": str(row.get("note") or "").strip()[:600],
            "by_name": str(row.get("by_name") or "").strip()[:120],
            "updated_at": str(row.get("updated_at") or "").strip()[:64],
        }
    return out


async def _promote_suspension_map_load() -> dict[str, dict[str, str]]:
    row = await storage.dashboard_config.get(config_key=PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY) or {}
    raw_value = row.get("config_value") if isinstance(row, dict) else ""
    return _promote_suspension_map_from_raw(raw_value)


async def _promote_suspension_map_save(payload: dict[str, dict[str, str]]) -> None:
    safe_payload = _promote_suspension_map_from_raw(payload)
    encoded = json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"))
    existing = await storage.dashboard_config.get(config_key=PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY)
    if existing:
        await storage.dashboard_config.update(id=existing.get("id"), config_value=encoded)
    else:
        await storage.dashboard_config.insert(
            config_key=PROMOTE_SUSPENDED_GUILDS_CONFIG_KEY,
            config_value=encoded,
        )


def _promote_history_owner_embed(row: dict[str, Any]) -> discord.Embed:
    history_id = int(row.get("id") or 0)
    guild_id = int(row.get("guild_id") or 0)
    guild_name = str(row.get("guild_name") or f"Guild {guild_id}").strip() or f"Guild {guild_id}"
    author_label = _promote_history_author_display(row)
    source_label = _promote_history_source_label(row.get("source_origin"))
    source_channel_name = str(row.get("source_channel_name") or "").strip() or "-"
    source_channel_id = int(row.get("source_channel_id") or 0)
    hidden = _promote_is_hidden(row)
    owner_note = _promote_hidden_note(row)
    content = str(row.get("content") or "").strip()
    description = owner_note if hidden and owner_note else (content[:3800] if content else "-")
    embed = discord.Embed(
        title=f"Promote Review #{history_id}",
        description=description,
        color=(discord.Color.orange() if hidden else discord.Color.blurple()),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    if hidden:
        embed.add_field(name="Display", value="Hidden by OwnerBOT", inline=True)
    embed.add_field(name="Guild", value=f"{guild_name}\n`{guild_id or '-'}`", inline=True)
    embed.add_field(name="Author", value=author_label, inline=True)
    embed.add_field(name="Source", value=f"{source_label}\n{source_channel_name} ({source_channel_id or '-'})", inline=False)
    if owner_note:
        embed.add_field(name="Owner Note", value=owner_note[:1024], inline=False)
    links = _promote_merged_links(row)
    if not hidden and links:
        embed.add_field(
            name="Links",
            value="\n".join(str(item).strip() for item in links[:6]),
            inline=False,
        )
    if not hidden:
        media_kind, media_url = _promote_pick_primary_media(row)
        if media_kind == "image" and media_url:
            embed.set_image(url=media_url)
    embed.set_footer(text=f"History ID {history_id}")
    return embed


async def _promote_sync_owner_review_message(row: dict[str, Any], *, deleted: bool = False) -> None:
    if not isinstance(row, dict):
        return
    channel_id = _safe_int(row.get("owner_channel_id"), 0)
    message_id = _safe_int(row.get("owner_message_id"), 0)
    if channel_id <= 0 or message_id <= 0:
        return
    bot = get_bot()
    if not bot:
        return
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            return
    if not channel:
        return
    try:
        review_message = await channel.fetch_message(message_id)
    except Exception:
        return
    try:
        if deleted:
            deleted_by = str(row.get("owner_action_by_name") or "").strip() or "OwnerBOT"
            await review_message.edit(
                embed=discord.Embed(
                    title=f"Promote Review #{int(row.get('id') or 0)}",
                    description=f"Deleted by {deleted_by}",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                ),
                view=None,
            )
        else:
            await review_message.edit(embed=_promote_history_owner_embed(row))
    except Exception:
        return


def _render_promote_history_page_html(
    *,
    app_name: str,
    query_text: str,
    guild_id_filter: int,
    source_filter: str,
    limit_filter: int,
    guild_filters: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    latest_guild_mode: bool = False,
    ownerbot_mode: bool = False,
    suspended_guild_ids: set[int] | None = None,
) -> str:
    safe_query = html.escape(str(query_text or ""), quote=True)
    safe_app_name = html.escape(str(app_name or "SkylineBOT"), quote=True)
    source_filter = str(source_filter or "").strip().lower()
    if source_filter not in {"web", "discord"}:
        source_filter = ""
    if limit_filter not in {50, 100, 200}:
        limit_filter = 50
    selected_guild_id = int(guild_id_filter or 0)
    suspended_ids = {int(item) for item in (suspended_guild_ids or set()) if int(item) > 0}

    guild_options = ['<option value="">All guilds</option>']
    for item in guild_filters:
        gid = int(item.get("guild_id") or 0)
        if gid <= 0:
            continue
        gname = str(item.get("guild_name") or f"Guild {gid}").strip() or f"Guild {gid}"
        selected_attr = " selected" if gid == selected_guild_id else ""
        guild_options.append(
            f'<option value="{gid}"{selected_attr}>{html.escape(gname, quote=True)} ({gid})</option>'
        )
    guild_options_html = "".join(guild_options)

    source_options_html = "".join(
        [
            f'<option value=""{" selected" if not source_filter else ""}>All sources</option>',
            f'<option value="web"{" selected" if source_filter == "web" else ""}>Web</option>',
            f'<option value="discord"{" selected" if source_filter == "discord" else ""}>Discord</option>',
        ]
    )

    limit_options_html = "".join(
        [
            f'<option value="50"{" selected" if limit_filter == 50 else ""}>50</option>',
            f'<option value="100"{" selected" if limit_filter == 100 else ""}>100</option>',
            f'<option value="200"{" selected" if limit_filter == 200 else ""}>200</option>',
        ]
    )

    table_rows: list[str] = []
    unique_guilds: set[int] = set()
    for row in rows:
        guild_id = int(row.get("guild_id") or 0)
        if guild_id > 0:
            unique_guilds.add(guild_id)
        guild_name = str(row.get("guild_name") or f"Guild {guild_id}").strip() or f"Guild {guild_id}"
        author_label = _promote_history_author_display(row)
        hidden = _promote_is_hidden(row)
        owner_note = _promote_hidden_note(row)
        content = _promote_history_clip(row.get("content") or "-", limit=260) or "-"
        if hidden:
            content = _promote_history_clip(owner_note or "Hidden by OwnerBOT", limit=260) or "Hidden by OwnerBOT"
        invite_url = str(row.get("invite_url") or "").strip()
        source_channel_id = int(row.get("source_channel_id") or 0)
        source_channel_name = str(row.get("source_channel_name") or "").strip()
        raw_attachments = row.get("attachments") if isinstance(row.get("attachments"), list) else []
        raw_content_links = row.get("content_links") if isinstance(row.get("content_links"), list) else []
        attachments = [str(item).strip() for item in raw_attachments if str(item).strip()]
        content_links = [str(item).strip() for item in raw_content_links if str(item).strip()]
        merged_links: list[str] = []
        if invite_url and not hidden:
            merged_links.append(invite_url)
        for link in [*content_links, *attachments]:
            if link and link not in merged_links:
                merged_links.append(link)
        links_markup = "<div class=\"muted\">-</div>"
        if hidden:
            links_markup = "<div class=\"muted\">Hidden by OwnerBOT</div>"
        elif merged_links:
            links_markup = "".join(
                [
                    (
                        f'<div><a href="{html.escape(link, quote=True)}" target="_blank" rel="noopener">'
                        f'{html.escape(_promote_history_clip(link, 90), quote=True)}</a></div>'
                    )
                    for link in merged_links[:8]
                ]
            )
        actions_markup = "-"
        if ownerbot_mode:
            suspend_action = "unsuspend_guild" if guild_id in suspended_ids else "suspend_guild"
            suspend_label = "Unsuspend" if guild_id in suspended_ids else "Suspend Guild"
            hide_action = "unhide" if hidden else "hide"
            hide_label = "Unhide" if hidden else "Hide + Note"
            actions_markup = (
                f'<div class="history-owner-actions">'
                f'  <form class="history-inline-form" method="post" action="/promotehistory/action">'
                f'    <input type="hidden" name="history_id" value="{int(row.get("id") or 0)}">'
                f'    <input type="hidden" name="action" value="{hide_action}">'
                f'    <input class="public-input" type="text" name="note" placeholder="Owner note..." value="{html.escape(owner_note, quote=True)}">'
                f'    <button class="history-btn ghost" type="submit">{hide_label}</button>'
                f'  </form>'
                f'  <form class="history-inline-form" method="post" action="/promotehistory/action">'
                f'    <input type="hidden" name="history_id" value="{int(row.get("id") or 0)}">'
                f'    <input type="hidden" name="action" value="edit">'
                f'    <textarea class="public-input" name="content" rows="2" placeholder="Edit promote text...">{html.escape(str(row.get("content") or ""), quote=True)}</textarea>'
                f'    <input class="public-input" type="text" name="note" placeholder="Edit note (optional)" value="{html.escape(owner_note, quote=True)}">'
                f'    <button class="history-btn" type="submit">Save Edit</button>'
                f'  </form>'
                f'  <form class="history-inline-form" method="post" action="/promotehistory/action">'
                f'    <input type="hidden" name="history_id" value="{int(row.get("id") or 0)}">'
                f'    <input type="hidden" name="action" value="{suspend_action}">'
                f'    <input class="public-input" type="text" name="note" placeholder="Suspend note..." value="{html.escape(owner_note, quote=True)}">'
                f'    <button class="history-btn ghost" type="submit">{suspend_label}</button>'
                f'  </form>'
                f'  <form class="history-inline-form" method="post" action="/promotehistory/action" onsubmit="return confirm(\'Delete this promote record?\')">'
                f'    <input type="hidden" name="history_id" value="{int(row.get("id") or 0)}">'
                f'    <input type="hidden" name="action" value="delete">'
                f'    <button class="history-btn ghost" type="submit">Delete</button>'
                f'  </form>'
                f'</div>'
            )
        table_rows.append(
            f"""
            <tr>
              <td>{html.escape(_promote_history_display_time(row.get("created_at")), quote=True)}</td>
              <td><strong>{html.escape(guild_name, quote=True)}</strong><br><span class="muted">ID: {guild_id or '-'}</span></td>
              <td>{html.escape(author_label, quote=True)}</td>
              <td>{html.escape(_promote_history_source_label(row.get("source_origin")), quote=True)}</td>
              <td>{html.escape(source_channel_name or '-', quote=True)}<br><span class="muted">{source_channel_id or '-'}</span></td>
              <td>{html.escape(content, quote=True)}</td>
              <td>{links_markup}</td>
              {f"<td>{actions_markup}</td>" if ownerbot_mode else ""}
            </tr>
            """
        )

    rows_markup = "".join(table_rows) if table_rows else (
        f"<tr><td colspan=\"{8 if ownerbot_mode else 7}\" class=\"muted\" style=\"text-align:center;\">No promote records found.</td></tr>"
    )
    if latest_guild_mode:
        summary_text = (
            f"Showing latest activity from {len(rows)} guild(s) "
            "(one latest record per guild)."
        )
    else:
        summary_text = (
            f"Showing {len(rows)} records from {len(unique_guilds)} guild(s). "
            "Default mode shows latest 50 guilds."
        )

    rendered_html = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Promote History - {safe_app_name}</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="alternate icon" type="image/png" href="/favicon.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <link rel="stylesheet" href="/dashboard/static/dashboard/public-pages.css">
  <style>
    .history-toolbar {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    .history-toolbar .field {{
      margin-top: 0;
    }}
    .history-table-wrap {{
      overflow: auto;
      border: 1px solid var(--public-line);
      border-radius: 12px;
      margin-top: 10px;
      background: rgba(10, 17, 32, 0.66);
    }}
    .history-table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 980px;
    }}
    .history-table th,
    .history-table td {{
      padding: 10px;
      border-bottom: 1px solid rgba(121, 160, 228, 0.2);
      text-align: left;
      vertical-align: top;
      font-size: .92rem;
    }}
    .history-table th {{
      background: rgba(15, 27, 50, 0.76);
      color: #d7e9ff;
      font-size: .86rem;
      white-space: nowrap;
    }}
    .history-table td {{
      color: #b6c9ea;
      line-height: 1.5;
      word-break: break-word;
    }}
    .history-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .history-btn {{
      border: 1px solid rgba(89, 145, 255, 0.58);
      border-radius: 10px;
      background: linear-gradient(140deg, var(--public-brand), var(--public-brand-2));
      color: #071628;
      font-weight: 800;
      padding: 8px 12px;
      text-decoration: none;
      cursor: pointer;
    }}
    .history-btn.ghost {{
      background: rgba(11, 18, 34, 0.6);
      color: var(--public-text);
      border-color: var(--public-line);
    }}
    .history-owner-actions {{
      display: grid;
      gap: 8px;
      min-width: 280px;
    }}
    .history-inline-form {{
      display: grid;
      gap: 6px;
      margin: 0;
    }}
    .history-inline-form .public-input {{
      padding: 7px 9px;
      min-height: 36px;
    }}
  </style>
</head>
<body class="public-doc">
  <main class="public-shell">
    <section class="public-card hero-card">
      <h1 class="title-row"><span class="title-icon"><i class="bi bi-megaphone"></i></span>Promote History Viewer</h1>
      <p class="hero-sub">Inspect recent promote messages from the relay system. Search by guild, content, links, author, channel, and source type.</p>
      <form id="promoteHistoryFilterForm" method="get" action="/promotehistory">
        <div class="history-toolbar">
          <div class="field">
            <label class="label">Search</label>
            <input id="promoteHistorySearchInput" class="public-input" type="text" name="q" value="{safe_query}" placeholder="guild name, message, link, user, channel" autocomplete="off">
          </div>
          <div class="field">
            <label class="label">Guild Filter</label>
            <select id="promoteHistoryGuildFilter" class="public-input" name="guild_id">{guild_options_html}</select>
          </div>
          <div class="field">
            <label class="label">Source</label>
            <select id="promoteHistorySourceFilter" class="public-input" name="source">{source_options_html}</select>
          </div>
          <div class="field">
            <label class="label">Limit</label>
            <select id="promoteHistoryLimitFilter" class="public-input" name="limit">{limit_options_html}</select>
          </div>
        </div>
        <div class="history-actions">
          <button class="history-btn" type="submit"><i class="bi bi-search"></i> Search</button>
          <a class="history-btn ghost" href="/promotehistory"><i class="bi bi-arrow-clockwise"></i> Reset</a>
        </div>
      </form>
    </section>

    <section class="public-card">
      <h2 class="title-row"><span class="title-icon"><i class="bi bi-clock-history"></i></span>Latest Promote Records</h2>
      <p class="hero-sub">{html.escape(summary_text, quote=True)}</p>
      <div class="history-table-wrap">
        <table class="history-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Guild</th>
              <th>Author</th>
              <th>Source</th>
              <th>Channel</th>
              <th>Promote Content</th>
              <th>Links</th>
              {"<th>Owner Actions</th>" if ownerbot_mode else ""}
            </tr>
          </thead>
          <tbody>
            {rows_markup}
          </tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    (() => {{
      const form = document.getElementById("promoteHistoryFilterForm");
      if (!(form instanceof HTMLFormElement)) {{
        return;
      }}

      const searchInput = document.getElementById("promoteHistorySearchInput");
      const guildFilter = document.getElementById("promoteHistoryGuildFilter");
      const sourceFilter = document.getElementById("promoteHistorySourceFilter");
      const limitFilter = document.getElementById("promoteHistoryLimitFilter");

      let searchDebounceTimer = null;
      let lastQuery = new URLSearchParams(new FormData(form)).toString();

      const submitIfChanged = () => {{
        const nextQuery = new URLSearchParams(new FormData(form)).toString();
        if (nextQuery === lastQuery) {{
          return;
        }}
        lastQuery = nextQuery;
        form.requestSubmit();
      }};

      const scheduleSearchSubmit = () => {{
        if (searchDebounceTimer) {{
          window.clearTimeout(searchDebounceTimer);
        }}
        searchDebounceTimer = window.setTimeout(() => {{
          submitIfChanged();
        }}, 280);
      }};

      if (searchInput instanceof HTMLInputElement) {{
        searchInput.addEventListener("input", scheduleSearchSubmit);
      }}
      for (const selectElement of [guildFilter, sourceFilter, limitFilter]) {{
        if (selectElement instanceof HTMLSelectElement) {{
          selectElement.addEventListener("change", submitIfChanged);
        }}
      }}
    }})();
  </script>
</body>
</html>"""
    return rendered_html


def _promote_media_kind(url: object) -> str:
    link = str(url or "").strip().lower()
    if not link:
        return ""
    plain = link.split("?", 1)[0].split("#", 1)[0]
    if plain.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif")):
        return "image"
    if plain.endswith((".mp4", ".webm", ".mov", ".m4v")):
        return "video"
    return ""


def _promote_merged_links(row: dict[str, Any]) -> list[str]:
    invite_url = str(row.get("invite_url") or "").strip()
    raw_attachments = row.get("attachments") if isinstance(row.get("attachments"), list) else []
    raw_content_links = row.get("content_links") if isinstance(row.get("content_links"), list) else []
    merged: list[str] = []
    if invite_url:
        merged.append(invite_url)
    for link in [*raw_content_links, *raw_attachments]:
        normalized = str(link or "").strip()
        if not normalized or normalized in merged:
            continue
        merged.append(normalized)
    return merged


def _promote_is_discord_invite_url(url: object) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    return bool(
        re.match(
            r"^https?://(?:www\.)?(?:discord\.gg/[A-Za-z0-9-]+|discord(?:app)?\.com/invite/[A-Za-z0-9-]+)",
            raw,
            flags=re.IGNORECASE,
        )
    )


def _promote_pick_join_invite_url(row: dict[str, Any]) -> str:
    invite_url = str(row.get("invite_url") or "").strip()
    if _promote_is_discord_invite_url(invite_url):
        return invite_url
    for link in _promote_merged_links(row):
        if _promote_is_discord_invite_url(link):
            return str(link).strip()
    return ""


def _promote_pick_primary_media(row: dict[str, Any]) -> tuple[str, str]:
    raw_attachments = row.get("attachments") if isinstance(row.get("attachments"), list) else []
    for link in raw_attachments:
        normalized = str(link or "").strip()
        if not normalized:
            continue
        kind = _promote_media_kind(normalized)
        if kind in {"image", "video"}:
            return kind, normalized
    for link in _promote_merged_links(row):
        kind = _promote_media_kind(link)
        if kind in {"image", "video"}:
            return kind, link
    return "", ""


def _render_promote_server_page_html(
    *,
    app_name: str,
    query_text: str,
    source_filter: str,
    limit_filter: int,
    feed_mode: str,
    auto_refresh_enabled: bool,
    active_promote_guild_total: int,
    rows: list[dict[str, Any]],
    fallback_notice: str = "",
) -> str:
    safe_query = html.escape(str(query_text or ""), quote=True)
    safe_app_name = html.escape(str(app_name or "SkylineBOT"), quote=True)
    safe_fallback_notice = html.escape(str(fallback_notice or "").strip(), quote=True)
    source_filter = str(source_filter or "").strip().lower()
    if source_filter not in {"web", "discord"}:
        source_filter = ""
    if limit_filter not in {20, 50, 100}:
        limit_filter = 50
    mode = str(feed_mode or "").strip().lower()
    if mode not in {"latest_guild", "timeline"}:
        mode = "latest_guild"
    auto_refresh = bool(auto_refresh_enabled)
    auto_refresh_query = "1" if auto_refresh else "0"

    base_query: dict[str, str] = {
        "mode": mode,
        "limit": str(limit_filter),
        "auto_refresh": auto_refresh_query,
    }
    if query_text:
        base_query["q"] = query_text
    if source_filter:
        base_query["source"] = source_filter
    reset_url = f"/promoteserver?{urlencode({'auto_refresh': auto_refresh_query})}"
    toggle_auto_url = f"/promoteserver?{urlencode({**base_query, 'auto_refresh': ('0' if auto_refresh else '1')})}"

    feed_rows: list[str] = []
    shown_guilds: set[int] = set()
    for row in rows:
        guild_id = int(row.get("guild_id") or 0)
        if guild_id > 0:
            shown_guilds.add(guild_id)
        guild_name = str(row.get("guild_name") or f"Guild {guild_id}").strip() or f"Guild {guild_id}"
        author_label = _promote_history_author_display(row)
        source_label = _promote_history_source_label(row.get("source_origin"))
        source_channel_name = str(row.get("source_channel_name") or "").strip()
        source_channel_id = int(row.get("source_channel_id") or 0)
        created_text = _promote_history_display_time(row.get("created_at"))
        hidden = _promote_is_hidden(row)
        owner_note = _promote_hidden_note(row)
        content_raw = str(row.get("content") or "").strip()
        if hidden:
            content_raw = owner_note or "Hidden by OwnerBOT"
        content_markup = html.escape(content_raw, quote=True).replace("\n", "<br>")
        if not content_markup:
            content_markup = "<span class=\"muted\">(ไม่มีข้อความ)</span>"

        media_kind, media_url = _promote_pick_primary_media(row)
        media_markup = ""
        if not hidden and media_kind == "image":
            media_markup = (
                f'<img class="promote-feed-media" src="{html.escape(media_url, quote=True)}" '
                f'alt="promote-media-{guild_id or 0}" loading="lazy">'
            )
        elif not hidden and media_kind == "video":
            media_markup = (
                f'<video class="promote-feed-media" controls preload="none">'
                f'<source src="{html.escape(media_url, quote=True)}"></video>'
            )

        links = _promote_merged_links(row)
        links_markup = ""
        if hidden:
            links_markup = '<div class="promote-link-row"><span class="muted">Hidden by OwnerBOT</span></div>'
        elif links:
            chips: list[str] = []
            for link in links[:6]:
                label = _promote_history_clip(link, 54) or link
                chips.append(
                    f'<a class="promote-link-chip" href="{html.escape(link, quote=True)}" '
                    f'target="_blank" rel="noopener">{html.escape(label, quote=True)}</a>'
                )
            links_markup = f'<div class="promote-link-row">{"".join(chips)}</div>'
        join_invite_url = _promote_pick_join_invite_url(row)
        join_button_markup = ""
        if join_invite_url and not hidden:
            join_button_markup = (
                f'<div class="promote-action-row">'
                f'<a class="promote-join-btn" href="{html.escape(join_invite_url, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">'
                f'<i class="bi bi-box-arrow-up-right"></i> เข้าร่วมเซิร์ฟเวอร์'
                f'</a></div>'
            )

        feed_rows.append(
            f"""
            <article class="promote-feed-card">
              <header class="promote-feed-head">
                <div>
                  <h2>{html.escape(guild_name, quote=True)}</h2>
                  <p class="muted">Guild ID: {guild_id or '-'} | By {html.escape(author_label, quote=True)}</p>
                </div>
                <div class="promote-feed-meta">
                  <span class="meta-chip">{html.escape(source_label, quote=True)}</span>
                  <span class="meta-chip">{html.escape(created_text, quote=True)}</span>
                </div>
              </header>
              <p class="promote-feed-content">{content_markup}</p>
              {media_markup}
              {links_markup}
              {join_button_markup}
              <footer class="promote-feed-foot muted">
                Channel: {html.escape(source_channel_name or '-', quote=True)} ({source_channel_id or '-'})
              </footer>
            </article>
            """
        )

    feed_rows_markup = "".join(feed_rows) if feed_rows else (
        '<section class="public-card"><p class="muted" style="margin:0;">No promote records found.</p></section>'
    )
    summary_text = (
        f"Showing {len(rows)} latest posts from {len(shown_guilds)} guild(s)."
        if mode == "latest_guild"
        else f"Showing {len(rows)} latest promote posts (timeline mode)."
    )
    active_promote_text = f"Active Promote Guilds: {max(0, int(active_promote_guild_total or 0))}"
    mode_description = (
        "Latest per guild feed"
        if mode == "latest_guild"
        else "Timeline feed (เรียงล่าสุดทั้งหมด)"
    )

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Promote Server Feed - {safe_app_name}</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="alternate icon" type="image/png" href="/favicon.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <link rel="stylesheet" href="/dashboard/static/dashboard/public-pages.css">
  <style>
    .promote-shell {{
      max-width: 1080px;
      margin: 0 auto;
      display: grid;
      gap: 12px;
    }}
    .promote-feed-toolbar {{
      display: grid;
      grid-template-columns: 1.2fr .7fr .7fr .7fr;
      gap: 10px;
      margin-top: 10px;
    }}
    .promote-feed-toolbar .field {{
      margin-top: 0;
    }}
    .promote-toolbar-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
      align-items: center;
    }}
    .promote-toolbar-btn {{
      border: 1px solid rgba(89, 145, 255, 0.58);
      border-radius: 10px;
      background: linear-gradient(140deg, var(--public-brand), var(--public-brand-2));
      color: #071628;
      font-weight: 800;
      padding: 8px 12px;
      text-decoration: none;
      cursor: pointer;
    }}
    .promote-toolbar-btn.ghost {{
      background: rgba(11, 18, 34, 0.6);
      color: var(--public-text);
      border-color: var(--public-line);
    }}
    .auto-refresh-note {{
      font-size: .8rem;
      margin-left: auto;
      white-space: nowrap;
    }}
    .promote-feed-card {{
      border: 1px solid var(--public-line);
      border-radius: 14px;
      padding: 14px;
      background: radial-gradient(140% 120% at 0% 0%, rgba(38, 100, 212, 0.2), rgba(10, 17, 32, 0.8));
      box-shadow: 0 10px 26px rgba(2, 7, 18, 0.36);
    }}
    .promote-feed-head {{
      display: flex;
      gap: 10px;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .promote-feed-head h2 {{
      margin: 0;
      font-size: 1.04rem;
      color: #ebf4ff;
      font-weight: 800;
    }}
    .promote-feed-meta {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      align-items: flex-end;
    }}
    .meta-chip {{
      border: 1px solid rgba(137, 183, 255, 0.34);
      border-radius: 999px;
      padding: 4px 10px;
      font-size: .74rem;
      color: #dbe7ff;
      background: rgba(7, 18, 40, 0.7);
      white-space: nowrap;
    }}
    .promote-feed-content {{
      margin: 0 0 10px;
      color: #d6e6ff;
      line-height: 1.65;
      word-break: break-word;
      font-size: .96rem;
    }}
    .promote-feed-media {{
      display: block;
      width: 100%;
      max-height: 520px;
      object-fit: cover;
      border-radius: 12px;
      border: 1px solid rgba(137, 183, 255, 0.26);
      background: rgba(4, 9, 19, 0.8);
    }}
    .promote-link-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .promote-link-chip {{
      border-radius: 999px;
      border: 1px solid rgba(94, 166, 255, 0.4);
      background: rgba(8, 21, 45, 0.74);
      color: #b9d8ff;
      text-decoration: none;
      font-size: .79rem;
      padding: 6px 10px;
    }}
    .promote-action-row {{
      margin-top: 10px;
    }}
    .promote-join-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 10px;
      border: 1px solid rgba(99, 188, 255, 0.52);
      background: linear-gradient(140deg, rgba(79, 174, 255, .28), rgba(45, 113, 230, .2));
      color: #dff1ff;
      text-decoration: none;
      font-weight: 700;
      font-size: .84rem;
      padding: 8px 12px;
    }}
    .promote-join-btn:hover {{
      border-color: rgba(133, 210, 255, 0.82);
      filter: brightness(1.04);
    }}
    .promote-feed-foot {{
      margin-top: 10px;
      font-size: .78rem;
      border-top: 1px dashed rgba(140, 179, 241, 0.28);
      padding-top: 8px;
    }}
    @media (max-width: 960px) {{
      .promote-feed-toolbar {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
    @media (max-width: 640px) {{
      .promote-feed-head {{
        flex-direction: column;
      }}
      .promote-feed-meta {{
        align-items: flex-start;
      }}
      .promote-feed-toolbar {{
        grid-template-columns: 1fr;
      }}
      .auto-refresh-note {{
        margin-left: 0;
      }}
    }}
  </style>
</head>
<body class="public-doc">
  <main class="public-shell">
    <div class="promote-shell">
      <section class="public-card hero-card">
        <h1 class="title-row"><span class="title-icon"><i class="bi bi-broadcast-pin"></i></span>Promote Server Feed</h1>
        <p class="hero-sub">ฟีดรวมโปรโมตล่าสุดจากทุกเซิร์ฟเวอร์</p>
        <p class="hero-sub" style="margin-top:6px;">{html.escape(summary_text, quote=True)} | {html.escape(mode_description, quote=True)}</p>
        <p class="hero-sub" style="margin-top:6px;"><strong>{html.escape(active_promote_text, quote=True)}</strong></p>
        <form method="get" action="/promoteserver" data-promote-feed-form="true" data-auto-refresh-enabled="{auto_refresh_query}" data-auto-refresh-ms="15000">
          <input type="hidden" name="auto_refresh" value="{auto_refresh_query}">
          <div class="promote-feed-toolbar">
            <div class="field">
              <label class="label">Search</label>
              <input class="public-input" type="text" name="q" value="{safe_query}" placeholder="guild, author, content, link, channel">
            </div>
            <div class="field">
              <label class="label">Source</label>
              <select class="public-input" name="source">
                <option value=""{" selected" if not source_filter else ""}>All</option>
                <option value="web"{" selected" if source_filter == "web" else ""}>Web</option>
                <option value="discord"{" selected" if source_filter == "discord" else ""}>Discord</option>
              </select>
            </div>
            <div class="field">
              <label class="label">Mode</label>
              <select class="public-input" name="mode">
                <option value="latest_guild"{" selected" if mode == "latest_guild" else ""}>Latest per Guild</option>
                <option value="timeline"{" selected" if mode == "timeline" else ""}>Timeline</option>
              </select>
            </div>
            <div class="field">
              <label class="label">Limit</label>
              <select class="public-input" name="limit">
                <option value="20"{" selected" if limit_filter == 20 else ""}>20</option>
                <option value="50"{" selected" if limit_filter == 50 else ""}>50</option>
                <option value="100"{" selected" if limit_filter == 100 else ""}>100</option>
              </select>
            </div>
          </div>
          <div class="promote-toolbar-actions">
            <button class="promote-toolbar-btn" type="submit"><i class="bi bi-arrow-repeat"></i> Refresh Now</button>
            <a class="promote-toolbar-btn ghost" href="{reset_url}"><i class="bi bi-arrow-clockwise"></i> Reset</a>
            <a class="promote-toolbar-btn ghost" href="{toggle_auto_url}"><i class="bi bi-magic"></i> {"Pause Auto Refresh" if auto_refresh else "Enable Auto Refresh"}</a>
            <a class="promote-toolbar-btn ghost" href="/promotehistory"><i class="bi bi-table"></i> Open Table View</a>
            <span class="muted auto-refresh-note" data-auto-refresh-note>{"Auto refresh is ON" if auto_refresh else "Auto refresh is OFF"}</span>
          </div>
        </form>
      </section>
      {f'<section class="public-card"><p class="muted" style="margin:0;color:#ffd6a0;">{safe_fallback_notice}</p></section>' if safe_fallback_notice else ''}
      {feed_rows_markup}
    </div>
  </main>
  <script>
    (function () {{
      const form = document.querySelector('form[data-promote-feed-form=\"true\"]');
      if (!form) return;
      const enabled = String(form.dataset.autoRefreshEnabled || '') === '1';
      if (!enabled) return;
      const intervalMs = Math.max(5000, Number(form.dataset.autoRefreshMs || 15000));
      const note = document.querySelector('[data-auto-refresh-note]');
      let deadline = Date.now() + intervalMs;

      const isEditing = () => {{
        const active = document.activeElement;
        if (!active) return false;
        const tag = String(active.tagName || '').toUpperCase();
        return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      }};

      const tick = () => {{
        if (document.hidden || isEditing()) {{
          deadline = Date.now() + intervalMs;
          if (note) note.textContent = 'Auto refresh paused while editing';
          window.setTimeout(tick, 1000);
          return;
        }}

        const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        if (note) {{
          note.textContent = `Auto refresh in ${{remaining}}s`;
        }}
        if (remaining <= 0) {{
          const nextUrl = new URL(window.location.href);
          if (!nextUrl.searchParams.get('auto_refresh')) {{
            nextUrl.searchParams.set('auto_refresh', '1');
          }}
          window.location.replace(nextUrl.toString());
          return;
        }}
        window.setTimeout(tick, 1000);
      }};

      tick();
    }})();
  </script>
</body>
</html>"""


def _fallback_tag_variables() -> dict[str, str]:
    return {
        "{user}": "The user's name",
        "{user.id}": "The user's id",
        "{user.tag}": "The user's tag",
        "{user.mention}": "The user's mention",
        "{user.avatar}": "The user's avatar",
        "{user.created_at}": "The user's account creation date",
        "{user.joined_at}": "The user's join date",
        "{guild}": "The server name",
        "{server}": "The server name",
        "{server.id}": "The server id",
        "{server.icon}": "The server icon",
        "{guild.id}": "The server id",
        "{guild.icon}": "The server icon",
        "{guild.owner}": "The server owner",
        "{guild.owner.id}": "The server owner id",
        "{channel}": "The current target channel mention",
        "{channel.id}": "The current target channel id",
        "{channel.name}": "The current target channel name",
        "{channel.mention}": "The current target channel mention",
        "{welcome.channel}": "The current welcome channel mention",
        "{welcome.channel.id}": "The current welcome channel id",
        "{welcome.channel.mention}": "The current welcome channel mention",
        "{room}": "Alias of current target channel mention",
        "{room.id}": "Alias of current target channel id",
        "{time}": "The current time",
        "{member.count}": "The server member count",
    }


def _tag_group(token: str) -> str:
    key = str(token or "").strip().lower()
    if key.startswith("{user"):
        return "User"
    if key.startswith("{guild") or key.startswith("{server") or key.startswith("{member.count"):
        return "Server"
    if key.startswith("{channel") or key.startswith("{welcome.channel") or key.startswith("{room"):
        return "Channel"
    if key.startswith("{time"):
        return "System"
    return "Other"


def _build_tags_page_payload() -> dict:
    bot = get_bot()
    raw_vars = getattr(bot, "variables", None) if bot is not None else None
    variable_map = raw_vars if isinstance(raw_vars, dict) and raw_vars else _fallback_tag_variables()
    rows: list[dict[str, str]] = []
    for token in sorted(variable_map.keys(), key=lambda item: str(item or "").lower()):
        description = str(variable_map.get(token) or "").strip() or "Variable"
        rows.append(
            {
                "token": str(token),
                "description": description,
                "group": _tag_group(str(token)),
            }
        )

    usage_rows = [
        {
            "title": "Welcome Module",
            "where": "Dashboard > Guild > Welcome",
            "how_to_find": "Set Welcome Message/Embed in the Welcome page",
            "supports": "User + Server + Channel + Time",
        },
        {
            "title": "Leaver Module",
            "where": "Dashboard > Guild > Leaver",
            "how_to_find": "Set Leave Message/Embed in the Leaver page",
            "supports": "User + Server + Channel + Time",
        },
        {
            "title": "Greet Module",
            "where": "Dashboard > Guild > Welcome (Greet)",
            "how_to_find": "Set greeting text for the configured channel",
            "supports": "User + Server + Channel + Time",
        },
        {
            "title": "Birthday Message",
            "where": "Discord Command: /birthday message",
            "how_to_find": "Guild admins can run /birthday message to set birthday text",
            "supports": "User + Server + Channel + Time",
        },
        {
            "title": "Level-Up Text",
            "where": "Dashboard > Guild > Levels",
            "how_to_find": "Set level-up notification text in the Levels page",
            "supports": "User + Server + Time",
        },
    ]

    return {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "variables": rows,
        "usages": usage_rows,
    }


def _render_tags_page(request: Request) -> str:
    payload = _build_tags_page_payload()
    payload_raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.b64encode(payload_raw).decode("ascii")
    context = _build_developer_portal_context(request)
    context["TAGS_PAYLOAD_B64"] = payload_b64
    return _render_public_html_template(PUBLIC_PAGE_TEMPLATES["tags"], context)


def _leaderboard_safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except Exception:
        return int(default)


def _leaderboard_avatar_url(entity: object | None) -> str:
    fallback = "https://cdn.discordapp.com/embed/avatars/0.png"
    if entity is None:
        return fallback
    try:
        avatar_url = str(getattr(getattr(entity, "display_avatar", None), "url", "") or "").strip()
    except Exception:
        avatar_url = ""
    return avatar_url or fallback


def _leaderboard_icon_url(bot_guild: object | None, raw_guild: dict | None, guild_id: str) -> str:
    fallback = "https://cdn.discordapp.com/embed/avatars/0.png"
    icon_url = ""
    if bot_guild is not None:
        try:
            icon_url = str(getattr(getattr(bot_guild, "icon", None), "url", "") or "").strip()
        except Exception:
            icon_url = ""
    if icon_url:
        return icon_url

    raw_icon = str((raw_guild or {}).get("icon") or "").strip()
    if guild_id and raw_icon:
        return f"https://cdn.discordapp.com/icons/{guild_id}/{raw_icon}.png?size=128"
    return fallback


def _leaderboard_user_guilds(session: dict, bot_guild_map: dict[str, object]) -> list[dict[str, object]]:
    guilds: list[dict[str, object]] = []
    seen: set[str] = set()
    has_live_shared_guilds = bool(bot_guild_map)
    for raw_guild in list((session or {}).get("guilds") or []):
        if not isinstance(raw_guild, dict):
            continue
        guild_id = str(raw_guild.get("id") or "").strip()
        if not guild_id or guild_id in seen:
            continue
        bot_guild = bot_guild_map.get(guild_id)
        # When web runtime cannot access bot guild cache (for example web process
        # is running standalone), keep guilds from OAuth session so leaderboard
        # can still query DB rows by guild_id instead of showing an empty page.
        if has_live_shared_guilds and bot_guild is None:
            continue
        seen.add(guild_id)
        if bot_guild is not None:
            guild_name = str(
                getattr(bot_guild, "name", "") or raw_guild.get("name") or f"Guild {guild_id}"
            ).strip() or f"Guild {guild_id}"
            guild_members = _leaderboard_safe_int(getattr(bot_guild, "member_count", 0), 0)
        else:
            guild_name = str(raw_guild.get("name") or f"Guild {guild_id}").strip() or f"Guild {guild_id}"
            guild_members = _leaderboard_safe_int(
                raw_guild.get("approximate_member_count") or raw_guild.get("member_count"),
                0,
            )
        guilds.append(
            {
                "id": guild_id,
                "name": guild_name,
                "icon": _leaderboard_icon_url(bot_guild, raw_guild, guild_id),
                "members": guild_members,
            }
        )
    return sorted(guilds, key=lambda item: str(item.get("name") or "").lower())


def _leaderboard_user_identity(
    *,
    bot_guild: object | None,
    bot: object | None,
    user_id: int,
    identity_cache: dict[int, dict[str, str]],
) -> dict[str, str]:
    cached = identity_cache.get(int(user_id))
    if cached:
        return cached

    target = None
    if bot_guild is not None:
        try:
            target = bot_guild.get_member(int(user_id))
        except Exception:
            target = None
    if target is None and bot is not None:
        try:
            target = bot.get_user(int(user_id))
        except Exception:
            target = None

    if target is None:
        payload = {
            "name": f"User {int(user_id)}",
            "avatar": "https://cdn.discordapp.com/embed/avatars/0.png",
        }
        identity_cache[int(user_id)] = payload
        return payload

    display_name = str(
        getattr(target, "display_name", None)
        or getattr(target, "global_name", None)
        or getattr(target, "name", None)
        or f"User {int(user_id)}"
    ).strip() or f"User {int(user_id)}"
    payload = {
        "name": display_name,
        "avatar": _leaderboard_avatar_url(target),
    }
    identity_cache[int(user_id)] = payload
    return payload


def _render_leaderboard_page(request: Request, payload: dict) -> str:
    payload_raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.b64encode(payload_raw).decode("ascii")
    context = _build_developer_portal_context(request)
    context["LEADERBOARD_PAYLOAD_B64"] = payload_b64
    return _render_public_html_template(PUBLIC_PAGE_TEMPLATES["leaderboard"], context)


def _status_public_access_enabled() -> bool:
    raw = str(os.getenv("DASHBOARD_PUBLIC_STATUS_ENABLED", "1") or "").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def _request_origin_host(request: Request) -> str:
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    host = forwarded_host or str(request.headers.get("host") or "").strip()
    if not host:
        host = str(getattr(getattr(request, "url", None), "netloc", "") or "").strip()
    if not host:
        return ""
    lowered = host.lower()
    if lowered.startswith("[") and "]" in lowered:
        return lowered[1:].split("]", 1)[0]
    return lowered.split(":", 1)[0]


def _origin_or_referer_host(request: Request) -> str:
    for header_name in ("origin", "referer"):
        raw = str(request.headers.get(header_name) or "").strip()
        if not raw:
            continue
        try:
            from urllib.parse import urlparse

            parsed = urlparse(raw)
            host = str(parsed.hostname or "").strip().lower()
            if host:
                return host
        except Exception:
            continue
    return ""


def _same_origin_request(request: Request) -> bool:
    expected_host = _request_origin_host(request)
    if not expected_host:
        return False
    source_host = _origin_or_referer_host(request)
    if not source_host:
        return False
    return source_host == expected_host


_PUBLIC_STATUS_COMPONENT_IDS = {
    "web",
    "discord_runtime",
    "mongo",
    "ai",
    "bot",
    "lavalink",
    "ownerbot",
}
_PUBLIC_STATUS_METRIC_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "web": ("Response", "Memory", "CPU"),
    "bot": ("Ping", "Guilds", "Users", "Uptime"),
    "discord_runtime": ("State", "HTTP", "Retry", "Attempt"),
    "mongo": ("Ping",),
    "lavalink": ("Nodes", "Connected"),
    "ai": ("Provider", "Model", "Ping"),
    "ownerbot": ("Command Response", "Bot Response", "Whitelist", "Tester Guilds"),
}
_PUBLIC_STATUS_ERROR_CODE_RE = re.compile(
    r"(?i)\b(?:err(?:or)?\s*[-_]?\s*\d{3,5}|http\s*\d{3}|web-[a-z0-9-]+-\d{3})\b"
)
_PUBLIC_STATUS_COMMAND_RE = re.compile(r"(?<!\w)/(?:[a-z0-9][a-z0-9_-]{1,})", re.IGNORECASE)
_PUBLIC_STATUS_CHANNEL_RE = re.compile(
    r"(?i)\b(?:channel(?:_id)?|room(?:_id)?)\b\s*[:=]\s*([#a-z0-9_\-]{2,32}|\d{6,22})|<#(\d{6,22})>"
)
_PUBLIC_STATUS_GUILD_RE = re.compile(r"(?i)\bguild(?:_id)?\b\s*[:=]\s*([a-z0-9_\-]{2,48}|\d{6,22})")
_PUBLIC_STATUS_DB_SECRET_RE = re.compile(r"(?i)\b(db\s*\d+)\s+[a-z0-9_\-]{4,}\b")
_PUBLIC_STATUS_LONG_TOKEN_RE = re.compile(r"\b[a-z0-9][a-z0-9_\-]{9,}\b", re.IGNORECASE)
_PUBLIC_STATUS_SNOWFLAKE_RE = re.compile(r"\b\d{15,22}\b")


def _public_status_label(level: str) -> str:
    key = str(level or "").strip().lower()
    if key == "ok":
        return "Operational"
    if key == "warn":
        return "Warn"
    if key == "error":
        return "Error"
    return "Info"


def _public_status_detail(level: str, status_text: str) -> str:
    level_key = str(level or "").strip().lower()
    short_status = str(status_text or "").strip()
    if level_key == "ok":
        return short_status or "Service is operating normally."
    if level_key == "warn":
        return short_status or "Some parts are limited, but service is still online."
    if level_key == "error":
        return short_status or "Service issue detected. Team is investigating."
    return short_status or "Service status is being updated."


def _mask_public_identifier(value: Any, head: int = 5, tail: int = 3) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    if len(text) <= (head + tail + 1):
        return text
    return f"{text[:head]}........{text[-tail:]}"


def _mask_public_token_match(match: re.Match[str]) -> str:
    token = str(match.group(0) or "")
    if not token:
        return token
    has_digit = any(char.isdigit() for char in token)
    has_symbol = ("_" in token) or ("-" in token)
    if not has_digit and not has_symbol:
        return token
    return _mask_public_identifier(token)


def _public_status_safe_text(value: Any, *, max_len: int = 220) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return ""

    text = _PUBLIC_STATUS_DB_SECRET_RE.sub(lambda m: str(m.group(1) or "").strip(), text)
    text = _PUBLIC_STATUS_SNOWFLAKE_RE.sub(lambda m: _mask_public_identifier(m.group(0), head=4, tail=3), text)
    text = _PUBLIC_STATUS_LONG_TOKEN_RE.sub(_mask_public_token_match, text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def _public_status_compact_incident(raw_text: Any) -> str:
    text = _public_status_safe_text(raw_text, max_len=260)
    if not text:
        return ""

    parts: list[str] = []
    code_match = _PUBLIC_STATUS_ERROR_CODE_RE.search(text)
    if code_match:
        code = str(code_match.group(0) or "").strip()
        normalized_code = re.sub(r"(?i)^error", "Err", code)
        normalized_code = re.sub(r"\s+", "", normalized_code)
        parts.append(normalized_code)

    command_match = _PUBLIC_STATUS_COMMAND_RE.search(text)
    if command_match:
        cmd = str(command_match.group(0) or "").strip()
        if cmd:
            parts.append(f"cmd {cmd}")

    channel_match = _PUBLIC_STATUS_CHANNEL_RE.search(text)
    channel_value = ""
    if channel_match:
        channel_value = str(channel_match.group(1) or channel_match.group(2) or "").strip()
        channel_value = _public_status_safe_text(channel_value, max_len=42)
        if channel_value:
            parts.append(f"channel {channel_value}")

    guild_match = _PUBLIC_STATUS_GUILD_RE.search(text)
    if guild_match:
        guild_value = _public_status_safe_text(guild_match.group(1), max_len=42)
        if guild_value:
            parts.append(f"guild {guild_value}")

    if parts:
        return " | ".join(parts)[:180]

    return text[:180]


def _sanitize_public_error_rows(rows: object) -> list[dict[str, str]]:
    safe_rows: list[dict[str, str]] = []
    for raw in list(rows or []):
        if not isinstance(raw, dict):
            continue
        scope = _public_status_safe_text(raw.get("scope"), max_len=48) or "system"
        compact_detail = _public_status_compact_incident(raw.get("detail"))
        if not compact_detail:
            continue
        safe_rows.append({"scope": scope, "detail": compact_detail})
        if len(safe_rows) >= 10:
            break
    return safe_rows


def _sanitize_public_component_metrics(component_id: str, metrics: object) -> list[tuple[str, str]]:
    allowed_labels = set(_PUBLIC_STATUS_METRIC_ALLOWLIST.get(component_id, ()))
    safe_rows: list[tuple[str, str]] = []
    for raw_row in list(metrics or []):
        if not isinstance(raw_row, (list, tuple)) or len(raw_row) < 2:
            continue
        label = str(raw_row[0] or "").strip()
        if not label or label not in allowed_labels:
            continue
        value = _public_status_safe_text(raw_row[1], max_len=80) or "-"
        safe_rows.append((label, value))
    return safe_rows[:4]


def _sanitize_status_payload(payload: dict) -> dict:
    safe_payload = dict(payload or {})
    safe_payload["request_host"] = ""
    safe_payload["request_port"] = ""
    safe_payload["public_view"] = True

    overall = dict(safe_payload.get("overall") or {})
    overall_level = str(overall.get("level") or "info").strip().lower() or "info"
    overall["title"] = f"System Status: {_public_status_label(overall_level)}"
    overall["detail"] = "Public view shows summary-level health only. Admin can view full diagnostics."
    safe_payload["overall"] = overall

    command_summary_raw = dict(safe_payload.get("command_summary") or {})
    command_summary = {
        "total": int(command_summary_raw.get("total") or 0),
        "prefix": int(command_summary_raw.get("prefix") or 0),
        "slash": int(command_summary_raw.get("slash") or 0),
        "disabled_global": int(command_summary_raw.get("disabled_global") or 0),
        "estimated_available": int(command_summary_raw.get("estimated_available") or 0),
        "estimated_unavailable": int(command_summary_raw.get("estimated_unavailable") or 0),
        "sample_available": [
            _public_status_safe_text(name, max_len=40)
            for name in list(command_summary_raw.get("sample_available") or [])[:10]
            if _public_status_safe_text(name, max_len=40)
        ],
        "disabled_global_samples": [
            _public_status_safe_text(name, max_len=40)
            for name in list(command_summary_raw.get("disabled_global_samples") or [])[:10]
            if _public_status_safe_text(name, max_len=40)
        ],
        "error_rows": _sanitize_public_error_rows(command_summary_raw.get("error_rows")),
    }
    safe_payload["command_summary"] = command_summary

    source_components = list(safe_payload.get("components") or [])
    public_uptime = "-"
    for raw_component in source_components:
        row = dict(raw_component or {})
        row_id = str(row.get("id") or "").strip().lower()
        if row_id != "bot":
            continue
        for metric in list(row.get("metrics") or []):
            if not isinstance(metric, (list, tuple)) or len(metric) < 2:
                continue
            if str(metric[0] or "").strip() != "Uptime":
                continue
            public_uptime = str(metric[1] or "-").strip() or "-"
            break
        if public_uptime != "-":
            break

    components: list[dict] = []
    for raw_component in source_components:
        component = dict(raw_component or {})
        component_id = str(component.get("id") or "").strip().lower()
        if component_id not in _PUBLIC_STATUS_COMPONENT_IDS:
            continue
        component_level = str(component.get("level") or "info").strip().lower() or "info"
        component_status = _public_status_label(component_level)
        component["level"] = component_level
        component["status"] = component_status
        component["detail"] = _public_status_detail(component_level, "")
        component["metrics"] = _sanitize_public_component_metrics(component_id, component.get("metrics"))
        components.append(component)
    safe_payload["components"] = components

    incident_lines: list[str] = []
    for row in list(command_summary.get("error_rows") or [])[:8]:
        if not isinstance(row, dict):
            continue
        detail = str(row.get("detail") or "").strip()
        if detail:
            incident_lines.append(detail)
    for raw_line in list(safe_payload.get("incidents") or [])[:14]:
        compact_line = _public_status_compact_incident(raw_line)
        if compact_line and compact_line not in incident_lines:
            incident_lines.append(compact_line)
        if len(incident_lines) >= 10:
            break
    for component in components:
        level = str(component.get("level") or "").strip().lower()
        title = str(component.get("title") or "Component").strip() or "Component"
        if level == "error":
            summary = f"{title}: Error"
            if summary not in incident_lines:
                incident_lines.append(summary)
        elif level == "warn":
            summary = f"{title}: Warn"
            if summary not in incident_lines:
                incident_lines.append(summary)
    if not incident_lines:
        incident_lines = ["No active incidents detected from current public checks."]
    safe_payload["incidents"] = incident_lines[:10]

    safe_payload["public_summary"] = {
        "overall_status": _public_status_label(overall_level),
        "updated_at": str(safe_payload.get("generated_at") or "-"),
        "uptime": public_uptime,
    }

    safe_payload["lavalink_nodes"] = [
        {
            "identifier": _mask_public_identifier(row.get("identifier")),
            "status": _public_status_safe_text(str(row.get("status") or "").split(".")[-1], max_len=40) or "-",
            "latency": _public_status_safe_text(row.get("latency"), max_len=40) or "-",
            "players": _public_status_safe_text(row.get("players"), max_len=40) or "-",
        }
        for row in list(safe_payload.get("lavalink_nodes") or [])[:16]
        if isinstance(row, dict)
    ]
    music_analytics = dict(safe_payload.get("music_analytics") or {})
    safe_status_rows: list[dict[str, str]] = []
    for row in list(music_analytics.get("status_rows") or [])[:8]:
        if not isinstance(row, dict):
            continue
        safe_status_rows.append(
            {
                "item": _public_status_safe_text(row.get("item"), max_len=48) or "-",
                "status": str(row.get("status") or "info").strip().lower() or "info",
                "value": _public_status_safe_text(row.get("value"), max_len=72) or "-",
                "updated_at": _public_status_safe_text(row.get("updated_at"), max_len=32) or "-",
            }
        )
    music_analytics["status_rows"] = safe_status_rows
    music_analytics["source_note"] = _public_status_safe_text(music_analytics.get("source_note"), max_len=120)
    safe_payload["music_analytics"] = music_analytics
    return safe_payload

async def dashboard_careers_page(request: Request):
    session = _session_from_request(request)
    return HTMLResponse(
        _render_feature_landing_page(
            title="SkylineBOT ร่วมงานกับเรา",
            heading="ร่วมงานกับ SkylineBOT",
            description="ร่วมงานกับทีม SkylineBOT เพื่อสร้างเครื่องมือสำหรับคอมมูนิตี้ Discord ขนาดใหญ่และงานอัตโนมัติจริง",
            highlights=[
                "ปรับปรุงระบบบอท, เวิร์กโฟลว์การดูแล และประสบการณ์ใช้งานแดชบอร์ด",
                "ทำงานกับระบบจริงที่มีผู้ใช้หลากหลายประเทศและหลายภาษา",
                "ร่วมออกแบบฟีเจอร์ใหม่ที่เน้นใช้งานได้จริงและรองรับการเติบโตของชุมชน",
            ],
            cta_href=CONTACT_EXTERNAL_URL,
            cta_label="ติดต่อทีมงาน",
            session=session,
        )
    )

async def _build_subscribe_plan_context(session: dict[str, object] | None) -> dict[str, object]:
    context: dict[str, object] = {
        "guild_plan_rows": [],
        "user_app_subscription": {},
    }
    if not session:
        return context

    user_id = _session_user_id(session)
    if not user_id:
        return context
    try:
        user_id_int = int(user_id)
    except Exception:
        return context

    manageable_guilds = await _manageable_guilds_live(session)
    guild_plan_rows: list[dict[str, object]] = []
    for guild in manageable_guilds:
        if not isinstance(guild, dict):
            continue
        try:
            guild_id_int = int(str(guild.get("id") or "0").strip())
        except Exception:
            guild_id_int = 0
        if guild_id_int <= 0:
            continue
        row = await billing_workflow.sync_plan_subscription_with_guild_state(
            guild_id=guild_id_int,
            user_id=user_id_int,
        )
        if not isinstance(row, dict):
            row = {}
        guild_plan_rows.append(
            {
                "guild_id": guild_id_int,
                "guild_name": str(guild.get("name") or guild_id_int),
                "current_plan": str(row.get("current_plan") or "free"),
                "pending_plan": str(row.get("pending_plan") or ""),
                "status": str(row.get("status") or ""),
                "auto_renew": bool(row.get("auto_renew", True)),
                "current_period_end": row.get("current_period_end"),
            }
        )

    user_app_subscription = await billing_workflow.ensure_user_app_subscription(user_id_int)
    context["guild_plan_rows"] = guild_plan_rows
    context["user_app_subscription"] = user_app_subscription if isinstance(user_app_subscription, dict) else {}
    return context

async def dashboard_premium_page(request: Request):
    session = _session_from_request(request)
    subscribe_context = await _build_subscribe_plan_context(session)
    plan_pricing_snapshot = await billing_workflow.get_plan_pricing_snapshot()
    return HTMLResponse(
        _render_premium_doc_page(
            session=session,
            subscribe_context=subscribe_context,
            interactive=False,
            plan_pricing_snapshot=plan_pricing_snapshot,
        )
    )

async def dashboard_subscribe_plan_page(request: Request):
    session = _session_from_request(request)
    subscribe_context = await _build_subscribe_plan_context(session)
    plan_pricing_snapshot = await billing_workflow.get_plan_pricing_snapshot()
    return HTMLResponse(
        _render_premium_doc_page(
            session=session,
            subscribe_context=subscribe_context,
            interactive=True,
            plan_pricing_snapshot=plan_pricing_snapshot,
            notice=str(request.query_params.get("notice") or "").strip() or None,
        )
    )

async def dashboard_home(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    await guild_growth.ensure_loaded()
    bot = get_bot()
    if bot:
        asyncio.create_task(
            guild_growth.record_snapshot(
                len(getattr(bot, "guilds", []) or []),
                source="dashboard_home",
            )
        )
    session = _session_from_request(request)
    if not session:
        return HTMLResponse(await _render_login(notice=notice, session=session))
    guilds = await _manageable_guilds_live(session)
    return HTMLResponse(_render_guild_picker(session, guilds, notice=notice))

async def dashboard_landing_home(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    await guild_growth.ensure_loaded()
    bot = get_bot()
    if bot:
        asyncio.create_task(
            guild_growth.record_snapshot(
                len(getattr(bot, "guilds", []) or []),
                source="dashboard_landing",
            )
        )
    session = _session_from_request(request)
    return HTMLResponse(
        await _render_login(
            notice=notice,
            session=session,
            seo_path="/",
            seo_image_path=str(
                style_urls.INDEX_NAV_RESOURCES_SPOTLIGHT_IMAGE
                or style_urls.DEFAULT_MUSIC_BANNER
                or "/dashboard/static/image_web_bot/giveaways_dashboard.webp"
            ).strip(),
        )
    )

async def dashboard_home_legacy_redirect(request: Request):
    notice = str(request.query_params.get("notice") or "").strip()
    if notice:
        return RedirectResponse(url=f"/dashboard?{urlencode({'notice': notice})}", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


async def dashboard_commands_index(request: Request):
    session = _session_from_request(request)
    if session:
        return RedirectResponse(url="/dashboard?notice=Choose a guild first to manage commands", status_code=303)
    return RedirectResponse(url="/commands", status_code=303)


async def dashboard_commands_help_page(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    return HTMLResponse(_render_commands_help_page(session=session))

async def dashboard_commands_help_legacy_redirect(request: Request):
    query = str(getattr(request.url, "query", "") or "").strip()
    if query:
        return RedirectResponse(url=f"/commands?{query}", status_code=303)
    return RedirectResponse(url="/commands", status_code=303)


async def dashboard_invite_hub(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    auto_value = str(request.query_params.get("auto") or "").strip().lower()
    auto_redirect = auto_value in {"1", "true", "yes", "on"}
    guild_id_query = str(request.query_params.get("guild_id") or "").strip()
    guild_id = guild_id_query if guild_id_query.isdigit() else None

    # Auto mode should jump straight to Discord Add App flow.
    # Do this before session checks so /invitebot can be used as Custom Install URL
    # without forcing dashboard login.
    if auto_redirect:
        return RedirectResponse(_bot_invite_url(guild_id), status_code=303)

    session = _session_from_request(request)
    if not session:
        login_next = "/invitebot?auto=1" if auto_redirect else "/invite"
        if guild_id:
            login_next = f"{login_next}&guild_id={guild_id}" if "?" in login_next else f"{login_next}?guild_id={guild_id}"
        return RedirectResponse(f"/dashboard/login?{urlencode({'next': login_next})}", status_code=303)

    await _ensure_support_guild_membership_from_oauth(session)
    guilds = await _manageable_guilds_live(session)
    return HTMLResponse(_render_invite_hub(session=session, guilds=guilds, notice=notice))

async def dashboard_donatebot_hub(
    request: Request,
    notice: str | None = None,
    verify_status: str | None = None,
):
    await _ensure_dashboard_config_cache()
    query = str(getattr(request.url, "query", "") or "").strip()
    if query:
        return RedirectResponse(url=f"/donate?{query}", status_code=303)
    return RedirectResponse(url="/donate", status_code=303)


def _donatebot_notice_redirect(
    *,
    notice: str,
    verify_status: str = "rejected",
) -> RedirectResponse:
    query = urlencode(
        {
            "notice": str(notice or "").strip()[:500],
            "verify_status": str(verify_status or "").strip().lower() or "rejected",
        }
    )
    return RedirectResponse(url=f"/donate?{query}", status_code=303)


async def _donatebot_parse_verify_form(request: Request) -> tuple[dict[str, str], Any, Any, str]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
        except AssertionError:
            return {}, None, None, "File upload is unavailable right now (python-multipart is missing)."
        data: dict[str, str] = {}
        avatar_upload = None
        slip_upload = None
        for key, value in form.items():
            if hasattr(value, "filename"):
                if key == "donor_avatar":
                    filename = str(getattr(value, "filename", "") or "").strip()
                    if filename:
                        avatar_upload = value
                elif key == "slip_file":
                    filename = str(getattr(value, "filename", "") or "").strip()
                    if filename:
                        slip_upload = value
                continue
            data[key] = str(value)
        return data, avatar_upload, slip_upload, ""
    return await _parse_form(request), None, None, ""


async def _donatebot_read_avatar_image(upload_obj: Any) -> tuple[bytes | None, str, str, int, str]:
    if upload_obj is None or not getattr(upload_obj, "filename", None):
        return None, "", "", 0, ""
    filename = str(getattr(upload_obj, "filename", "") or "").strip()
    if not filename:
        return None, "", "", 0, ""

    payload = await upload_obj.read()
    if not payload:
        return None, filename, "", 0, "Uploaded avatar image is empty."

    size = int(len(payload))
    if size > DONATEBOT_AVATAR_MAX_BYTES:
        return None, filename, "", 0, f"Avatar image is too large ({DONATEBOT_AVATAR_MAX_BYTES // (1024 * 1024)}MB max)."

    content_type = str(getattr(upload_obj, "content_type", "") or "").strip().lower()
    if content_type and not content_type.startswith("image/"):
        return None, filename, content_type, size, "Uploaded file must be an image."

    safe_name = filename.replace("\\", "_").replace("/", "_").replace("..", "_").strip()[:120]
    if not safe_name:
        safe_name = "donor-avatar.png"

    ext = Path(safe_name).suffix.lower()
    if ext not in DONATEBOT_ALLOWED_IMAGE_EXTENSIONS:
        if content_type.startswith("image/"):
            safe_name = f"{safe_name}.png"
        else:
            return None, safe_name, content_type, size, "Allowed image formats: PNG, JPG, JPEG, WEBP, GIF."

    return bytes(payload), safe_name, content_type, size, ""


async def _donatebot_read_slip_image(upload_obj: Any) -> tuple[bytes | None, str, str, int, str]:
    if upload_obj is None or not getattr(upload_obj, "filename", None):
        return None, "", "", 0, ""
    filename = str(getattr(upload_obj, "filename", "") or "").strip()
    if not filename:
        return None, "", "", 0, ""

    payload = await upload_obj.read()
    if not payload:
        return None, filename, "", 0, "Uploaded slip image is empty."

    size = int(len(payload))
    if size > DONATEBOT_SLIP_MAX_BYTES:
        return None, filename, "", 0, f"Slip image is too large ({DONATEBOT_SLIP_MAX_BYTES // (1024 * 1024)}MB max)."

    content_type = str(getattr(upload_obj, "content_type", "") or "").strip().lower()
    if content_type and not content_type.startswith("image/"):
        return None, filename, content_type, size, "Uploaded slip file must be an image."

    safe_name = filename.replace("\\", "_").replace("/", "_").replace("..", "_").strip()[:120]
    if not safe_name:
        safe_name = "donate-slip.png"

    ext = Path(safe_name).suffix.lower()
    if ext not in DONATEBOT_ALLOWED_SLIP_EXTENSIONS:
        if content_type.startswith("image/"):
            safe_name = f"{safe_name}.png"
        else:
            return None, safe_name, content_type, size, "Allowed slip formats: PNG, JPG, JPEG, WEBP."

    return bytes(payload), safe_name, content_type, size, ""


def _donatebot_avatar_data_url(payload: bytes, filename: str, content_type: str) -> str:
    if not payload:
        return ""
    mime = str(content_type or "").strip().lower()
    if not mime.startswith("image/"):
        ext = Path(str(filename or "avatar.png")).suffix.lower()
        if ext in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        elif ext == ".webp":
            mime = "image/webp"
        elif ext == ".gif":
            mime = "image/gif"
        else:
            mime = "image/png"
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _donatebot_validate_donor_name(raw_name: str) -> tuple[bool, str]:
    donor_name = _clean_text(raw_name).strip()[:80]
    if not donor_name:
        return True, ""
    ok, reason = _validate_promote_content(donor_name, [])
    if ok:
        return True, ""
    blocked_reason = reason or "Contains blocked words."
    return False, f"Donor name is not allowed: {blocked_reason}"


def _donatebot_unit_score(raw_value: Any) -> float:
    try:
        value = float(raw_value)
    except Exception:
        return 0.0
    if value < 0.0:
        return 0.0
    if value <= 1.0:
        return value
    if value <= 100.0:
        return value / 100.0
    return 1.0


def _donatebot_truthy(raw_value: Any) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    text = str(raw_value or "").strip().lower()
    return text in {"1", "true", "yes", "on", "y"}


def _donatebot_extract_violent_score(payload: Any) -> tuple[float, bool, bool]:
    violent_scores: list[float] = []
    violent_flagged = False
    recognized = False
    violent_tokens = ("violent", "violence", "gore", "blood", "weapon", "fight", "unsafe")

    def _visit(node: Any, *, violent_context: bool = False) -> None:
        nonlocal violent_flagged, recognized
        if isinstance(node, dict):
            labels: list[str] = []
            for raw_key, raw_value in node.items():
                key = str(raw_key or "").strip().lower()
                if key in {"label", "class", "prediction", "category", "name", "tag"}:
                    labels.append(str(raw_value or "").strip().lower())
                if key in {"flagged", "unsafe", "blocked"} and _donatebot_truthy(raw_value):
                    violent_flagged = True
                if any(token in key for token in violent_tokens):
                    recognized = True
                    if _donatebot_truthy(raw_value):
                        violent_flagged = True
                    score = _donatebot_unit_score(raw_value)
                    if score > 0.0:
                        violent_scores.append(score)
            label_text = " ".join(labels)
            label_violent = any(token in label_text for token in violent_tokens)
            if label_violent:
                recognized = True
            for score_key in ("score", "confidence", "probability", "value", "percent", "pct"):
                if score_key in node and (violent_context or label_violent):
                    score = _donatebot_unit_score(node.get(score_key))
                    if score > 0.0:
                        violent_scores.append(score)
                elif score_key in node:
                    recognized = True
                    score = _donatebot_unit_score(node.get(score_key))
                    if score > 0.0:
                        violent_scores.append(score)
            child_violent_context = violent_context or label_violent or any(
                any(token in str(key or "").strip().lower() for token in violent_tokens)
                for key in node.keys()
            )
            for value in node.values():
                if isinstance(value, (dict, list, tuple)):
                    _visit(value, violent_context=child_violent_context)
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                _visit(item, violent_context=violent_context)

    _visit(payload)
    return (max(violent_scores) if violent_scores else 0.0), violent_flagged, recognized


async def _donatebot_avatar_ocr_text(
    image_payload: bytes,
    *,
    filename: str,
    content_type: str,
) -> str:
    if not image_payload:
        return ""
    ocr_enabled = str(os.getenv("DONATEBOT_AVATAR_OCR_SUPPLEMENT_ENABLED", "1") or "1").strip().lower()
    if ocr_enabled in {"0", "false", "off", "no"}:
        return ""
    endpoint = str(os.getenv("OCR_SPACE_API_URL", "https://api.ocr.space/parse/image") or "").strip()
    if not endpoint.startswith(("http://", "https://")):
        return ""
    api_key = str(os.getenv("OCR_SPACE_API_KEY", "helloworld") or "helloworld").strip() or "helloworld"
    lang = str(os.getenv("OCR_SPACE_LANG", "auto") or "auto").strip().lower() or "auto"
    file_name = str(filename or "donor-avatar.png").strip() or "donor-avatar.png"
    mime = str(content_type or "").strip().lower() or "application/octet-stream"

    data = {
        "apikey": api_key,
        "language": lang,
        "OCREngine": "2",
        "isOverlayRequired": "false",
        "scale": "true",
    }
    files = {"file": (file_name, image_payload, mime)}
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(endpoint, data=data, files=files)
        if int(response.status_code) >= 400:
            return ""
        decoded = response.json()
    except Exception:
        return ""

    parsed_results = decoded.get("ParsedResults") if isinstance(decoded, dict) else None
    if not isinstance(parsed_results, list):
        return ""
    chunks: list[str] = []
    for row in parsed_results:
        if not isinstance(row, dict):
            continue
        txt = str(row.get("ParsedText") or "").strip()
        if txt:
            chunks.append(txt)
    return "\n".join(chunks).strip()[:6000]


def _donatebot_avatar_ocr_violation_reason(ocr_text: str) -> str:
    text = str(ocr_text or "").strip()
    if not text:
        return ""
    ok, reason = _validate_promote_content(text, [])
    if not ok:
        return f"Avatar image text is not allowed ({reason or 'blocked text'})."
    lowered = text.lower()
    for token in DONATEBOT_AVATAR_OCR_SCAM_TOKENS:
        probe = str(token or "").strip().lower()
        if probe and probe in lowered:
            return f"Avatar image text is suspicious ({probe})."
    return ""


async def _donatebot_moderate_avatar_image(
    data_url: str,
    *,
    image_payload: bytes,
    filename: str,
    content_type: str,
) -> tuple[bool, str]:
    if not str(data_url or "").startswith("data:image/"):
        return False, "Avatar image format is invalid."
    if not image_payload:
        return False, "Avatar image data is empty."

    endpoint_candidates_raw = [
        str(
            os.getenv(
                "AIFORTHAI_IMAGE_MODERATION_ENDPOINT",
                os.getenv("AIFORTHAI_NSFW_ENDPOINT", os.getenv("AIFORTHAI_VIOLENT_ENDPOINT", DONATEBOT_AIFORTHAI_IMAGE_MODERATION_ENDPOINT)),
            )
            or DONATEBOT_AIFORTHAI_IMAGE_MODERATION_ENDPOINT
        ).strip(),
        str(
            os.getenv(
                "AIFORTHAI_IMAGE_MODERATION_FALLBACK_ENDPOINT",
                DONATEBOT_AIFORTHAI_IMAGE_MODERATION_FALLBACK_ENDPOINT,
            )
            or DONATEBOT_AIFORTHAI_IMAGE_MODERATION_FALLBACK_ENDPOINT
        ).strip(),
        DONATEBOT_AIFORTHAI_IMAGE_MODERATION_ENDPOINT,
        DONATEBOT_AIFORTHAI_IMAGE_MODERATION_FALLBACK_ENDPOINT,
    ]
    moderation_endpoints: list[str] = []
    for endpoint in endpoint_candidates_raw:
        if not str(endpoint).startswith(("http://", "https://")):
            continue
        if endpoint in moderation_endpoints:
            continue
        moderation_endpoints.append(endpoint)
    if not moderation_endpoints:
        return False, "Image safety endpoint is invalid."

    api_key = str(os.getenv("AIFORTHAI_API_KEY", "") or "").strip()
    if not api_key:
        return False, "AIFORTHAI_API_KEY is missing for image safety check."
    api_key_header = str(os.getenv("AIFORTHAI_API_KEY_HEADER", "Apikey") or "Apikey").strip() or "Apikey"
    use_bearer = str(os.getenv("AIFORTHAI_USE_BEARER_AUTH", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
    try:
        threshold = float(os.getenv("AIFORTHAI_VIOLENT_THRESHOLD", str(DONATEBOT_AIFORTHAI_DEFAULT_THRESHOLD)) or DONATEBOT_AIFORTHAI_DEFAULT_THRESHOLD)
    except Exception:
        threshold = DONATEBOT_AIFORTHAI_DEFAULT_THRESHOLD
    threshold = max(0.05, min(0.995, threshold))

    headers = {
        "User-Agent": "SkylineBOT/1.0 (+https://skylinebot.xyz)",
        "Accept": "application/json",
    }
    if use_bearer:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers[api_key_header] = api_key

    file_name = str(filename or "donor-avatar.png").strip() or "donor-avatar.png"
    mime = str(content_type or "").strip().lower() or "application/octet-stream"
    request_candidates = [
        {"data": {}, "files": {"file": (file_name, image_payload, mime)}},
        {"data": {}, "files": {"image": (file_name, image_payload, mime)}},
        {"data": {"url": data_url}, "files": None},
        {"json": {"url": data_url}},
        {"json": {"image_url": data_url}},
    ]
    decoded: Any = {}
    request_ok = False
    for endpoint in moderation_endpoints:
        for candidate in request_candidates:
            try:
                async with httpx.AsyncClient(timeout=22.0) as client:
                    if "json" in candidate:
                        response = await client.post(
                            endpoint,
                            headers=headers,
                            json=candidate.get("json") or {},
                        )
                    else:
                        response = await client.post(
                            endpoint,
                            headers=headers,
                            data=candidate.get("data") or {},
                            files=candidate.get("files"),
                        )
                if int(response.status_code) in {401, 403}:
                    return False, "Image safety service rejected API key."
                if int(response.status_code) >= 400:
                    continue
                request_ok = True
                decoded = response.json()
                break
            except Exception:
                continue
        if request_ok:
            break

    if not request_ok or not isinstance(decoded, dict):
        return False, "Image safety check is temporarily unavailable. Please try again."

    violent_score, violent_flagged, recognized = _donatebot_extract_violent_score(decoded)
    if not recognized and not decoded:
        return False, "Image safety response is unsupported."
    if violent_flagged or violent_score >= threshold:
        return False, f"Avatar image is too violent (score={violent_score:.2f})."

    ocr_text = await _donatebot_avatar_ocr_text(
        image_payload,
        filename=file_name,
        content_type=mime,
    )
    ocr_reason = _donatebot_avatar_ocr_violation_reason(ocr_text)
    if ocr_reason:
        return False, ocr_reason
    return True, ""

async def dashboard_donate_page(
    request: Request,
    notice: str | None = None,
    verify_status: str | None = None,
):
    await _ensure_dashboard_config_cache()
    query_guild_id = str(request.query_params.get("guild_id") or "").strip()
    if query_guild_id.isdigit():
        target = f"/dashboard/donate/{query_guild_id}"
        if notice:
            target = f"{target}?{urlencode({'notice': notice})}"
        return RedirectResponse(target, status_code=303)

    session = _session_from_request(request)
    guilds = await _manageable_guilds_live(session) if session else []
    top_donate_rows = await _fetch_donatebot_top_donors(limit=10)

    return HTMLResponse(
        _render_donatebot_hub(
            session=session,
            guilds=guilds,
            notice=notice,
            verify_status=verify_status,
            show_guild_section=False,
            top_donate_rows=top_donate_rows,
        )
    )

async def dashboard_system_status(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    is_admin = _is_dashboard_admin(session)
    guilds = await _manageable_guilds_live(session) if session else []
    status_view = str(request.query_params.get("view") or "bot").strip().lower()
    if status_view not in {"service", "bot"}:
        status_view = "bot"
    payload = await _build_system_status_payload(request, status_view=status_view)
    if not is_admin:
        if not _status_public_access_enabled():
            return RedirectResponse("/dashboard/login?next=/dashboard/status", status_code=303)
        payload = _sanitize_status_payload(payload)
    return HTMLResponse(
        _render_system_status_page(
            session=session,
            guilds=guilds,
            payload=payload,
            notice=notice,
            status_view=status_view,
        ),
        headers=dict(_STATUS_NO_CACHE_HEADERS),
    )

async def dashboard_system_status_live(request: Request):
    session = _session_from_request(request)
    is_admin = _is_dashboard_admin(session)
    if not is_admin and not _status_public_access_enabled():
        return JSONResponse(
            {"ok": False, "error": "forbidden", "error_code": "WEB-AUTH-403"},
            status_code=403,
            headers=dict(_STATUS_NO_CACHE_HEADERS),
        )
    status_view = str(request.query_params.get("view") or "bot").strip().lower()
    if status_view not in {"service", "bot"}:
        status_view = "bot"
    payload = await _build_system_status_payload(request, status_view=status_view)
    if not is_admin:
        payload = _sanitize_status_payload(payload)
    return JSONResponse(payload, headers=dict(_STATUS_NO_CACHE_HEADERS))


async def dashboard_runtime_discord(request: Request):
    session = _session_from_request(request)
    if not session:
        expected_tokens = _runtime_control_expected_tokens()
        supplied_token = str(request.headers.get("x-runtime-control-token") or "").strip()
        if not supplied_token:
            auth_header = str(request.headers.get("authorization") or "").strip()
            if auth_header.lower().startswith("bearer "):
                supplied_token = auth_header[7:].strip()
        if not supplied_token:
            supplied_token = str(request.query_params.get("token") or "").strip()

        allow_by_token = bool(supplied_token and supplied_token in expected_tokens)
        if not allow_by_token:
            return JSONResponse(
                {"ok": False, "error": "unauthorized", "error_code": "WEB-AUTH-401"},
                status_code=401,
                headers=dict(_STATUS_NO_CACHE_HEADERS),
            )
    compact_flag = str(
        request.query_params.get("compact")
        or request.query_params.get("minimal")
        or ""
    ).strip().lower()
    if compact_flag in {"1", "true", "yes", "on"}:
        payload = get_discord_service_state(include_snapshot=False)
        payload = {
            "level": str(payload.get("level") or "unknown").strip().lower() or "unknown",
            "message": str(payload.get("message") or "").strip(),
            "status_code": payload.get("status_code"),
            "retry_after": payload.get("retry_after"),
            "attempt": payload.get("attempt"),
            "updated_at": payload.get("updated_at"),
            "pid": payload.get("pid"),
            "pid_started_at": payload.get("pid_started_at"),
            "source": str(payload.get("source") or "").strip(),
        }
        return JSONResponse(payload, headers=dict(_STATUS_NO_CACHE_HEADERS))

    payload = get_discord_service_state()
    return JSONResponse(payload, headers=dict(_STATUS_NO_CACHE_HEADERS))


def _runtime_control_expected_tokens() -> set[str]:
    # Accept tokens from both primary/runtime env names so support worker and
    # web process can be configured independently without breaking control.
    values = {
        str(getattr(BOT_CONFIG, "RUNTIME_CONTROL_TOKEN", "") or "").strip(),
        str(os.getenv("RUNTIME_CONTROL_TOKEN", "") or "").strip(),
        str(os.getenv("PRIMARY_RUNTIME_CONTROL_TOKEN", "") or "").strip(),
        str(os.getenv("DASHBOARD_SECRET", "") or "").strip(),
        str(os.getenv("SUPPORT_RUNTIME_CONTROL_TOKEN", "") or "").strip(),
        str(os.getenv("SUPPORT_PRIMARY_RUNTIME_CONTROL_TOKEN", "") or "").strip(),
    }
    return {value for value in values if value}


async def dashboard_runtime_control(request: Request):
    expected_tokens = _runtime_control_expected_tokens()
    session = _session_from_request(request)
    is_admin = _is_dashboard_admin(session)

    payload: dict = {}
    try:
        raw_payload = await request.json()
        if isinstance(raw_payload, dict):
            payload = raw_payload
    except Exception:
        payload = {}

    supplied_token = str(request.headers.get("x-runtime-control-token") or "").strip()
    if not supplied_token:
        auth_header = str(request.headers.get("authorization") or "").strip()
        if auth_header.lower().startswith("bearer "):
            supplied_token = auth_header[7:].strip()
    if not supplied_token:
        supplied_token = str(payload.get("token") or "").strip()

    allow_by_token = bool(supplied_token and supplied_token in expected_tokens)
    allow_by_admin_session = bool(is_admin and _same_origin_request(request))
    if not allow_by_token and not allow_by_admin_session:
        if not expected_tokens and not allow_by_admin_session:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "runtime_control_not_configured",
                    "error_code": "WEB-RUNTIME-CONFIG-503",
                },
                status_code=503,
            )
        return JSONResponse(
            {"ok": False, "error": "forbidden", "error_code": "WEB-AUTH-403"},
            status_code=403,
        )

    action = str(payload.get("action") or request.query_params.get("action") or "").strip().lower()
    component = str(
        payload.get("component")
        or payload.get("target")
        or request.query_params.get("component")
        or request.query_params.get("target")
        or "bot"
    ).strip().lower()
    if action not in {"start", "reload", "stop", "restart"}:
        return JSONResponse(
            {
                "ok": False,
                "error": "invalid_action",
                "error_code": "WEB-RUNTIME-ACTION-400",
                "allowed": ["start", "reload", "stop", "restart"],
            },
            status_code=400,
        )
    if component not in {"bot", "web"}:
        return JSONResponse(
            {
                "ok": False,
                "error": "invalid_component",
                "error_code": "WEB-RUNTIME-COMPONENT-400",
                "allowed": ["bot", "web"],
            },
            status_code=400,
        )

    if component == "web":
        if action == "start":
            return JSONResponse(
                {"ok": True, "component": "web", "action": "start", "message": "web already running"},
                status_code=200,
            )

        if action == "stop":
            set_discord_service_state(
                level="stopped",
                message="Runtime control applied: web stop",
                attempt=0,
            )

            async def _stop_process_later():
                await asyncio.sleep(0.25)
                try:
                    bot_obj = get_bot()
                    if bot_obj is not None and not bot_obj.is_closed():
                        await bot_obj.close()
                except Exception as error:
                    logger.warning(f"Runtime control web stop failed to close bot: {error}")
                os._exit(0)

            asyncio.create_task(_stop_process_later(), name="runtime_control_web_stop")
            return JSONResponse(
                {
                    "ok": True,
                    "component": "web",
                    "action": "stop",
                    "message": "web stop requested",
                },
                status_code=202,
            )

        # Web reload/restart both map to process restart.
        set_discord_service_state(
            level="starting",
            message="Runtime control applied: web restart",
            attempt=0,
        )

        async def _restart_web_process_later():
            await asyncio.sleep(0.2)
            try:
                bot_obj = get_bot()
                if bot_obj is not None and not bot_obj.is_closed():
                    await bot_obj.close()
            except Exception as error:
                logger.warning(f"Runtime control web restart failed to close bot: {error}")
            await asyncio.sleep(0.3)
            try:
                python_executable = sys.executable or "python"
                argv = [python_executable, *sys.argv]
                os.execv(python_executable, argv)
            except Exception as error:
                logger.error(f"Runtime control web restart failed: {error}")
                set_discord_service_state(
                    level="degraded",
                    message=f"Web restart failed: {error}",
                    attempt=0,
                )

        asyncio.create_task(_restart_web_process_later(), name="runtime_control_web_restart")
        return JSONResponse(
            {
                "ok": True,
                "component": "web",
                "action": "restart",
                "message": "web restart requested",
            },
            status_code=202,
        )

    # component == "bot"
    bot = get_bot()
    if bot is None:
        return JSONResponse(
            {"ok": False, "error": "bot_not_bound", "error_code": "WEB-RUNTIME-BIND-503"},
            status_code=503,
        )

    if action == "start":
        if not bot.is_closed():
            set_discord_service_state(
                level="ok",
                message="Runtime control start skipped: bot already running",
                attempt=0,
            )
            return JSONResponse(
                {"ok": True, "component": "bot", "action": "start", "message": "bot already running"},
                status_code=200,
            )

        set_discord_service_state(
            level="starting",
            message="Runtime control applied: start",
            attempt=0,
        )

        async def _start_bot_later():
            await asyncio.sleep(0.2)
            token = str(getattr(getattr(bot, "BotConfig", None), "TOKEN", "") or os.getenv("TOKEN", "")).strip()
            if not token:
                set_discord_service_state(
                    level="degraded",
                    message="Start failed: TOKEN not configured",
                    attempt=0,
                )
                return
            try:
                await bot.start(token)
            except Exception as error:
                logger.error(f"Runtime control start failed: {error}")
                set_discord_service_state(
                    level="degraded",
                    message=f"Start failed: {error}",
                    attempt=0,
                )

        asyncio.create_task(_start_bot_later(), name="runtime_control_start")
        return JSONResponse(
            {"ok": True, "component": "bot", "action": "start", "message": "bot start requested"},
            status_code=202,
        )

    if action == "reload":
        try:
            steps: list[str] = []
            await bot.reload()
            steps.append("bot.reload")
            try:
                await bot.reload_extension("skylinebot.src")
                steps.append("reload_extension")
            except Exception as extension_error:
                logger.warning(f"Runtime control reload extension warning: {extension_error}")
                steps.append("reload_extension_warning")
            synced_total = 0
            try:
                synced_commands = await bot.tree.sync()
                synced_total = len(synced_commands)
                steps.append(f"tree.sync:{synced_total}")
            except Exception as sync_error:
                logger.warning(f"Runtime control slash sync warning: {sync_error}")
                steps.append("tree.sync_warning")
            set_discord_service_state(
                level="ok",
                message="Runtime control applied: reload",
                attempt=0,
            )
            return JSONResponse(
                {
                    "ok": True,
                    "component": "bot",
                    "action": "reload",
                    "message": "reload completed",
                    "synced_commands": synced_total,
                    "steps": steps,
                },
                status_code=200,
            )
        except Exception as error:
            logger.error(f"Runtime control reload failed: {error}")
            return JSONResponse(
                {
                    "ok": False,
                    "error": "reload_failed",
                    "error_code": "WEB-RUNTIME-RELOAD-500",
                    "message": str(error),
                },
                status_code=500,
            )

    if action == "stop":
        set_discord_service_state(
            level="stopped",
            message="Runtime control applied: stop",
            attempt=0,
        )

        async def _close_bot_later():
            await asyncio.sleep(0.15)
            try:
                await bot.close()
            except Exception as error:
                logger.warning(f"Runtime control stop failed to close bot: {error}")

        asyncio.create_task(_close_bot_later(), name="runtime_control_stop")
        return JSONResponse(
            {"ok": True, "component": "bot", "action": "stop", "message": "bot stop requested"},
            status_code=202,
        )

    # action == "restart"
    set_discord_service_state(
        level="starting",
        message="Runtime control applied: restart",
        attempt=0,
    )

    async def _restart_process_later():
        await asyncio.sleep(0.2)
        try:
            if not bot.is_closed():
                await bot.close()
        except Exception as error:
            logger.warning(f"Runtime control restart failed to close bot: {error}")
        await asyncio.sleep(0.3)
        try:
            python_executable = sys.executable or "python"
            argv = [python_executable, *sys.argv]
            os.execv(python_executable, argv)
        except Exception as error:
            logger.error(f"Runtime control restart failed: {error}")
            set_discord_service_state(
                level="degraded",
                message=f"Restart failed: {error}",
                attempt=0,
            )

    asyncio.create_task(_restart_process_later(), name="runtime_control_restart")
    return JSONResponse(
        {"ok": True, "component": "bot", "action": "restart", "message": "process restart requested"},
        status_code=202,
    )

async def dashboard_donatebot_verify(request: Request):
    session = _session_from_request(request)
    form_data, avatar_upload, slip_upload, parse_error = await _donatebot_parse_verify_form(request)
    if parse_error:
        return _donatebot_notice_redirect(notice=parse_error, verify_status="rejected")

    gift_link = str(form_data.get("gift_link") or "").strip()
    evidence_type = str(form_data.get("evidence_type") or "auto").strip().lower()
    if evidence_type not in {"auto", "gift", "truemoney", "slip", "file"}:
        evidence_type = "auto"
    donor_message = _clean_text(form_data.get("message") or "").strip()[:500]
    amount_raw = str(form_data.get("amount") or "").strip()
    amount_value = 0
    if amount_raw:
        try:
            amount_value = max(0, min(100_000_000, int(amount_raw)))
        except Exception:
            amount_value = 0

    session_user = dict((session or {}).get("user") or {})
    session_user_id = str(session_user.get("id") or "").strip()
    session_display_name = _clean_text(
        session_user.get("global_name")
        or session_user.get("username")
        or session_user.get("name")
        or ""
    ).strip()[:80]
    logged_in_mode = bool(session and DONATEBOT_DISCORD_ID_RE.match(session_user_id))

    donor_name = ""
    donor_discord_id = ""
    donor_source = "guest"
    if logged_in_mode:
        donor_source = "session"
        donor_discord_id = session_user_id
        donor_name = session_display_name or f"User {session_user_id}"
    else:
        donor_discord_id = str(form_data.get("donor_discord_id") or "").strip()
        donor_name = _clean_text(form_data.get("donor_name") or "").strip()[:80]

        if donor_discord_id and not DONATEBOT_DISCORD_ID_RE.match(donor_discord_id):
            reason = "Discord ID format is invalid. Please use numeric Discord ID (15-22 digits)."
            await _append_donatebot_verify_log(
                request=request,
                session=session,
                gift_link=gift_link,
                donor_name=donor_name,
                donor_discord_id=donor_discord_id,
                donor_source="guest",
                amount=amount_value,
                verify_status="rejected",
                verify_note=reason,
            )
            return _donatebot_notice_redirect(notice=reason, verify_status="rejected")

        if donor_name:
            valid_name, invalid_name_reason = _donatebot_validate_donor_name(donor_name)
            if not valid_name:
                reason = invalid_name_reason or "Donor name contains blocked words."
                await _append_donatebot_verify_log(
                    request=request,
                    session=session,
                    gift_link=gift_link,
                    donor_name=donor_name,
                    donor_discord_id=donor_discord_id,
                    donor_source="guest",
                    amount=amount_value,
                    verify_status="rejected",
                    verify_note=reason,
                )
                return _donatebot_notice_redirect(notice=reason, verify_status="rejected")

        if not donor_discord_id and not donor_name:
            reason = "Guest mode requires Discord ID or donor name."
            await _append_donatebot_verify_log(
                request=request,
                session=session,
                gift_link=gift_link,
                donor_name=donor_name,
                donor_discord_id=donor_discord_id,
                donor_source="guest",
                amount=amount_value,
                verify_status="rejected",
                verify_note=reason,
            )
            return _donatebot_notice_redirect(notice=reason, verify_status="rejected")

        donor_source = "guest_discord_id" if donor_discord_id else "guest_name"
        if donor_discord_id and not donor_name:
            donor_name = f"User {donor_discord_id}"

    has_gift_link = bool(gift_link)
    has_slip_upload = slip_upload is not None and bool(getattr(slip_upload, "filename", None))

    if evidence_type in {"gift", "truemoney"} and not has_gift_link:
        reason = "Please provide a TrueMoney Gift Link."
        await _append_donatebot_verify_log(
            request=request,
            session=session,
            gift_link=gift_link,
            donor_name=donor_name,
            donor_discord_id=donor_discord_id,
            donor_source=donor_source,
            amount=amount_value,
            verify_status="rejected",
            verify_note=reason,
        )
        return _donatebot_notice_redirect(notice=reason, verify_status="rejected")
    if evidence_type in {"slip", "file"} and not has_slip_upload:
        reason = "Please upload a slip image file."
        await _append_donatebot_verify_log(
            request=request,
            session=session,
            gift_link=gift_link,
            donor_name=donor_name,
            donor_discord_id=donor_discord_id,
            donor_source=donor_source,
            amount=amount_value,
            verify_status="rejected",
            verify_note=reason,
        )
        return _donatebot_notice_redirect(notice=reason, verify_status="rejected")
    if not has_gift_link and not has_slip_upload:
        reason = "Please provide at least one evidence: TrueMoney Gift Link or Slip file."
        await _append_donatebot_verify_log(
            request=request,
            session=session,
            gift_link=gift_link,
            donor_name=donor_name,
            donor_discord_id=donor_discord_id,
            donor_source=donor_source,
            amount=amount_value,
            verify_status="rejected",
            verify_note=reason,
        )
        return _donatebot_notice_redirect(notice=reason, verify_status="rejected")
    if has_gift_link and not DONATEBOT_TRUEMONEY_GIFT_RE.match(gift_link):
        if evidence_type in {"auto", "slip", "file"} and has_slip_upload:
            gift_link = ""
            has_gift_link = False
        else:
            reason = "TrueMoney Gift Link format is invalid."
            await _append_donatebot_verify_log(
                request=request,
                session=session,
                gift_link=gift_link,
                donor_name=donor_name,
                donor_discord_id=donor_discord_id,
                donor_source=donor_source,
                amount=amount_value,
                verify_status="rejected",
                verify_note=reason,
            )
            return _donatebot_notice_redirect(notice=reason, verify_status="rejected")

    slip_payload = b""
    slip_filename = ""
    if has_slip_upload and slip_upload is not None:
        slip_payload_raw, slip_name, _slip_content_type, _slip_size, slip_error = await _donatebot_read_slip_image(slip_upload)
        if slip_error:
            await _append_donatebot_verify_log(
                request=request,
                session=session,
                gift_link=gift_link,
                donor_name=donor_name,
                donor_discord_id=donor_discord_id,
                donor_source=donor_source,
                amount=amount_value,
                verify_status="rejected",
                verify_note=slip_error,
            )
            return _donatebot_notice_redirect(notice=slip_error, verify_status="rejected")
        if slip_payload_raw:
            slip_payload = slip_payload_raw
            slip_filename = str(slip_name or "").strip()[:120]

    donor_avatar_url = str(session_user.get("avatar_url") or "").strip()[:1600] if logged_in_mode else ""
    if avatar_upload is not None:
        avatar_payload, avatar_name, avatar_content_type, _avatar_size, avatar_error = await _donatebot_read_avatar_image(avatar_upload)
        if avatar_error:
            await _append_donatebot_verify_log(
                request=request,
                session=session,
                gift_link=gift_link,
                donor_name=donor_name,
                donor_discord_id=donor_discord_id,
                donor_source=donor_source,
                amount=amount_value,
                verify_status="rejected",
                verify_note=avatar_error,
            )
            return _donatebot_notice_redirect(notice=avatar_error, verify_status="rejected")
        if not avatar_payload:
            avatar_upload = None

        if avatar_payload:
            avatar_data_url = _donatebot_avatar_data_url(
                avatar_payload,
                avatar_name,
                avatar_content_type,
            )
            if not avatar_data_url:
                reason = "Unable to read donor avatar image."
                await _append_donatebot_verify_log(
                    request=request,
                    session=session,
                    gift_link=gift_link,
                    donor_name=donor_name,
                    donor_discord_id=donor_discord_id,
                    donor_source=donor_source,
                    amount=amount_value,
                    verify_status="rejected",
                    verify_note=reason,
                )
                return _donatebot_notice_redirect(notice=reason, verify_status="rejected")

            avatar_ok, avatar_moderation_reason = await _donatebot_moderate_avatar_image(
                avatar_data_url,
                image_payload=avatar_payload,
                filename=avatar_name,
                content_type=avatar_content_type,
            )
            if not avatar_ok:
                reason = avatar_moderation_reason or "Avatar image failed safety moderation."
                await _append_donatebot_verify_log(
                    request=request,
                    session=session,
                    gift_link=gift_link,
                    donor_name=donor_name,
                    donor_discord_id=donor_discord_id,
                    donor_source=donor_source,
                    amount=amount_value,
                    verify_status="rejected",
                    verify_note=reason,
                )
                return _donatebot_notice_redirect(notice=reason, verify_status="rejected")
            donor_avatar_url = avatar_data_url

    if gift_link:
        verify_status, verify_note = await _verify_truemoney_gift_link(gift_link)
    else:
        verify_status, verify_note = ("pending", "Slip file received. Waiting for manual review.")

    detail_bits: list[str] = []
    if slip_payload:
        detail_bits.append(f"Slip: {slip_filename or 'uploaded'}")
    if donor_message:
        detail_bits.append(f"Message: {donor_message}")
    if slip_payload and verify_status == "rejected":
        verify_status = "pending"
        detail_bits.insert(0, "Gift link check failed, but slip was uploaded for manual review.")
    if detail_bits:
        verify_note = f"{verify_note} | {' | '.join(detail_bits)}"
    await _append_donatebot_verify_log(
        request=request,
        session=session,
        gift_link=gift_link,
        donor_name=donor_name,
        donor_discord_id=donor_discord_id,
        donor_avatar_url=donor_avatar_url,
        donor_source=donor_source,
        amount=amount_value,
        verify_status=verify_status,
        verify_note=verify_note,
    )
    amount_text = f"{amount_value:,} THB" if amount_value > 0 else "-"
    donor_label = donor_name or (f"User {donor_discord_id}" if donor_discord_id else "Unknown donor")
    notice_text = (
        f"Auto verify: {_donate_slip_status_label(verify_status)} | "
        f"Donor: {donor_label} | Amount: {amount_text} | {verify_note}"
    )
    return _donatebot_notice_redirect(notice=notice_text, verify_status=verify_status)


async def dashboard_discordbotlist_vote_webhook(request: Request):
    await _ensure_dashboard_config_cache()
    settings = _discordbotlist_vote_runtime_settings()
    configured_secret = str(settings.get("webhook_secret") or "").strip()
    provided_secret = str(request.headers.get("authorization") or "").strip()
    if not configured_secret:
        return JSONResponse(
            {
                "ok": False,
                "error": "webhook_secret_not_configured",
                "error_code": "WEB-WEBHOOK-SECRET-503",
            },
            status_code=503,
        )
    if not provided_secret or not hmac.compare_digest(provided_secret, configured_secret):
        return JSONResponse(
            {"ok": False, "error": "unauthorized", "error_code": "WEB-AUTH-401"},
            status_code=401,
        )

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    user_id = str(payload.get("id") or payload.get("user_id") or "").strip()
    username = str(payload.get("username") or "").strip() or "Unknown User"
    avatar_hash = str(payload.get("avatar") or "").strip()
    is_admin = bool(payload.get("admin", False))
    vote_timestamp = datetime.datetime.now(datetime.timezone.utc)

    channel_id = int(settings.get("result_channel_id") or 0)
    if channel_id <= 0:
        return JSONResponse(
            {
                "ok": True,
                "ignored": True,
                "reason": "result_channel_not_configured",
                "user_id": user_id,
            },
            status_code=200,
        )

    bot = get_bot()
    if not bot:
        return JSONResponse({"ok": False, "error": "bot_not_ready"}, status_code=503)

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            channel = None
    if channel is None or not hasattr(channel, "send"):
        return JSONResponse({"ok": False, "error": "channel_not_found"}, status_code=404)

    vote_url = str(settings.get("vote_url") or "").strip() or _discordbotlist_vote_default_url()
    embed = discord.Embed(
        title="DiscordBotList: ได้รับการโหวตใหม่",
        description=(
            f"ผู้โหวต: <@{user_id}> (`{user_id}`)\n" if user_id else f"ผู้โหวต: {username}\n"
        )
        + f"เวลา: <t:{int(vote_timestamp.timestamp())}:F>",
        color=discord.Color.green(),
        timestamp=vote_timestamp,
    )
    embed.add_field(name="Username", value=username, inline=True)
    embed.add_field(name="Source", value="discordbotlist.com", inline=True)
    embed.add_field(name="Admin Vote", value="Yes" if is_admin else "No", inline=True)
    if vote_url:
        embed.add_field(name="Vote Again", value=vote_url, inline=False)
    embed.set_thumbnail(url=_discordbotlist_avatar_url(user_id, avatar_hash))
    embed.set_footer(text="SkylineBOT Vote Webhook")

    view = None
    if vote_url.lower().startswith(("http://", "https://")):
        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label="โหวตอีกครั้ง",
                style=discord.ButtonStyle.link,
                url=vote_url,
            )
        )
    try:
        if view is not None:
            await channel.send(embed=embed, view=view)
        else:
            await channel.send(embed=embed)
    except Exception as error:
        logger.warning(f"discordbotlist vote webhook send failed: {error}")
        return JSONResponse({"ok": False, "error": "send_failed"}, status_code=500)

    return JSONResponse({"ok": True, "user_id": user_id, "channel_id": channel_id}, status_code=200)

async def dashboard_contag_alias():
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)

async def dashboard_none_fallback():
    return RedirectResponse(url="/dashboard", status_code=303)

async def dashboard_redeem_page(request: Request, notice: str | None = None):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard/login", status_code=303)
    guilds = await _manageable_guilds_live(session)
    return HTMLResponse(_render_redeem_web_page(session=session, guilds=guilds, notice=notice))


def _redeem_guild_has_active_plan(guild_state: dict[str, Any] | None) -> tuple[bool, datetime.datetime | None]:
    state = guild_state if isinstance(guild_state, dict) else {}
    if not _looks_like_active_premium_from_state(state):
        return False, None
    return True, _profile_as_utc_datetime(state.get("subscription_end"))


_REDEEM_SUPPORT_PLAN_AUTOROLE_CONFIG_KEY = "ownerbot_support_plan_autorole_v1"
_REDEEM_PLAN_TIER_ALIASES: dict[str, str] = {
    "free": "free",
    "silver": "silver",
    "silver_guild_preminum": "silver",
    "silver_guild_premium": "silver",
    "gold": "golden",
    "gole": "golden",
    "golden": "golden",
    "golden_guild_premium": "golden",
    "gole_guild_premium": "golden",
    "diamond": "diamond",
    "diamond_guild_premium": "diamond",
    "permanent": "permanent",
    "lifetime": "permanent",
    "forever": "permanent",
    "permanent_guild_premium": "permanent",
    "lifetime_guild_premium": "permanent",
}


def _redeem_normalize_plan_tier(raw_value: object) -> str:
    text = str(raw_value or "").strip().lower()
    direct = _REDEEM_PLAN_TIER_ALIASES.get(text)
    if direct:
        return direct
    if "silver" in text:
        return "silver"
    if "diamond" in text:
        return "diamond"
    if any(token in text for token in ("golden", "gole", "gold")):
        return "golden"
    if any(token in text for token in ("permanent", "lifetime", "forever")):
        return "permanent"
    return "free"


def _redeem_as_utc_datetime(raw_value: object) -> datetime.datetime | None:
    if not raw_value:
        return None
    if isinstance(raw_value, datetime.datetime):
        return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
    if isinstance(raw_value, (int, float)):
        try:
            ts = float(raw_value)
            if ts > 10_000_000_000:
                ts /= 1000.0
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        except Exception:
            return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        if text.isdigit():
            ts = float(text)
            if ts > 10_000_000_000:
                ts /= 1000.0
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def _redeem_format_datetime_utc(raw_value: object, *, none_text: str = "-") -> str:
    parsed = _redeem_as_utc_datetime(raw_value)
    if not parsed:
        return str(none_text)
    return parsed.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _redeem_datetime_to_iso(raw_value: object) -> str:
    parsed = _redeem_as_utc_datetime(raw_value)
    if not parsed:
        return ""
    return parsed.astimezone(datetime.timezone.utc).isoformat()


async def _redeem_load_support_plan_autorole_settings() -> dict[str, Any]:
    row = await storage.dashboard_config.get(config_key=_REDEEM_SUPPORT_PLAN_AUTOROLE_CONFIG_KEY)
    raw_value = str((row or {}).get("config_value") or "").strip()
    if not raw_value:
        return {}
    try:
        decoded = json.loads(raw_value)
    except Exception:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _redeem_support_role_id_from_settings(settings: dict[str, Any], plan_tier: str) -> int:
    if not isinstance(settings, dict):
        return 0
    role_map = settings.get("tier_role_ids")
    if not isinstance(role_map, dict):
        role_map = {}
    try:
        return int(role_map.get(plan_tier) or 0)
    except Exception:
        return 0


def _redeem_support_role_label(
    *,
    bot: Any,
    settings: dict[str, Any],
    plan_tier: str,
) -> tuple[str, int, int]:
    role_id = _redeem_support_role_id_from_settings(settings, plan_tier)
    try:
        support_guild_id = int(settings.get("support_guild_id") or 0)
    except Exception:
        support_guild_id = 0
    if support_guild_id <= 0:
        support_guild_id = _support_guild_id_from_env()
    if role_id <= 0:
        return "-", 0, int(support_guild_id or 0)
    role_name = ""
    if bot and support_guild_id > 0:
        support_guild = bot.get_guild(int(support_guild_id))
        role_obj = support_guild.get_role(int(role_id)) if support_guild else None
        if role_obj is not None:
            role_name = str(getattr(role_obj, "name", "") or "").strip()
    if role_name:
        return f"{role_name} ({role_id})", int(role_id), int(support_guild_id or 0)
    return f"Role ID {role_id}", int(role_id), int(support_guild_id or 0)


async def dashboard_redeem_submit(request: Request):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard/login", status_code=303)
    guilds = await _manageable_guilds_live(session)
    guild_map = {str(item.get("id")): item for item in guilds}
    form = await _parse_form(request)

    redeem_action = str(form.get("redeem_action") or "preview").strip().lower()
    if redeem_action not in {"preview", "confirm"}:
        redeem_action = "preview"

    redeem_code_input = str(form.get("redeem_code") or "").strip()
    target_guild_id = str(form.get("target_guild_id") or "").strip()
    form_values = {
        "redeem_code": redeem_code_input,
        "target_guild_id": target_guild_id,
    }
    redeem_code = normalize_redeem_code(redeem_code_input)
    if not redeem_code:
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice="กรุณากรอกโค้ด Redeem",
                form_values=form_values,
            ),
            status_code=400,
        )

    redeem_data = _find_redeem_code_data(redeem_code)
    if not redeem_data:
        redeem_data = await storage.redeem_codes.get(code=redeem_code)
    if not redeem_data and redeem_code_input and redeem_code_input != redeem_code:
        redeem_data = _find_redeem_code_data(redeem_code_input)
        if not redeem_data:
            redeem_data = await storage.redeem_codes.get(code=redeem_code_input)
    if not redeem_data:
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice="ไม่พบโค้ด",
                form_values=form_values,
            ),
            status_code=404,
        )
    redeem_data = normalize_redeem_row(redeem_data)

    code_value = str(redeem_data.get("code_value") or "").strip().lower()
    plan_tier = _redeem_normalize_plan_tier(code_value)
    plan_label = _plan_display_name(plan_tier if plan_tier != "free" else code_value)
    valid_for_days = redeem_data.get("valid_for_days")
    try:
        valid_for_days = int(valid_for_days)
    except Exception:
        valid_for_days = None
    if valid_for_days is not None and valid_for_days <= 0:
        valid_for_days = None
    bot = get_bot()
    user_id = _session_user_id(session)
    if not user_id:
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice="ไม่พบข้อมูลผู้ใช้ในเซสชัน",
                form_values=form_values,
            ),
            status_code=403,
        )
    try:
        user_id_int = int(user_id)
    except Exception:
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice="ไม่พบข้อมูลผู้ใช้ในเซสชัน",
                form_values=form_values,
            ),
            status_code=403,
        )
    if not bot:
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice="ระบบบอทยังไม่พร้อม กรุณาลองใหม่",
                form_values=form_values,
            ),
            status_code=503,
        )

    target_guild_id_int: int | None = None
    target_guild_name = "Account"
    if "guild" in code_value:
        if not target_guild_id.isdigit() or target_guild_id not in guild_map:
            return HTMLResponse(
                _render_redeem_web_page(
                    session=session,
                    guilds=guilds,
                    notice="กรุณาเลือกเซิร์ฟเวอร์ปลายทางที่คุณมีสิทธิ์จัดการ",
                    form_values=form_values,
                ),
                status_code=400,
            )
        target_guild_id_int = int(target_guild_id)
        target_guild_name = str(guild_map.get(target_guild_id, {}).get("name") or target_guild_id)
        guild_state = cache.guilds.get(str(target_guild_id_int), {}) if hasattr(cache, "guilds") else {}
        guild_premium_active, guild_premium_end = _redeem_guild_has_active_plan(guild_state)
        active_plan_name = _plan_display_name(guild_state.get("subscription")) if guild_premium_active else ""

        if not guild_premium_active:
            guild_live_row = await storage.guilds.get(guild_id=target_guild_id_int)
            guild_premium_active, guild_premium_end = _redeem_guild_has_active_plan(guild_live_row)
            if guild_premium_active:
                active_plan_name = _plan_display_name(guild_live_row.get("subscription"))

        if guild_premium_active:
            if isinstance(guild_premium_end, datetime.datetime):
                premium_end_text = guild_premium_end.astimezone(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
            else:
                premium_end_text = "ไม่มีกำหนด (แพ็กเกจถาวร)"
            plan_text = active_plan_name or "Premium"
            return HTMLResponse(
                _render_redeem_web_page(
                    session=session,
                    guilds=guilds,
                    notice=f"กิลด์นี้มีแพลน {plan_text} อยู่แล้ว (หมดอายุ {premium_end_text}) กรุณารอให้หมดอายุก่อนจึง Redeem ใหม่ได้",
                    form_values=form_values,
                ),
                status_code=409,
            )
    elif "user" in code_value:
        target_guild_name = "User account"
    else:
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice="ประเภทโค้ดไม่ถูกต้อง",
                form_values=form_values,
            ),
            status_code=400,
        )

    blocked_reason = redeem_block_reason(
        redeem_data,
        user_id=user_id_int,
        guild_id=target_guild_id_int,
    )
    if blocked_reason:
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice=redeem_reason_message_th(blocked_reason),
                form_values=form_values,
            ),
            status_code=409,
        )

    support_settings = await _redeem_load_support_plan_autorole_settings()
    support_role_label, support_role_id, support_guild_id = _redeem_support_role_label(
        bot=bot,
        settings=support_settings,
        plan_tier=plan_tier,
    )
    preview_payload = {
        "redeem_code": redeem_code,
        "target_guild_id": target_guild_id if target_guild_id_int else "",
        "target_guild_name": target_guild_name,
        "target_guild_id_display": str(target_guild_id_int) if target_guild_id_int else "-",
        "plan_label": plan_label,
        "code_created_at": _redeem_format_datetime_utc(redeem_data.get("created_at")),
        "code_expires_at": _redeem_format_datetime_utc(redeem_data.get("expires_at"), none_text="No expiry"),
        "support_role_label": support_role_label,
    }

    if redeem_action != "confirm":
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                form_values=form_values,
                preview_payload=preview_payload,
            )
        )

    claim_ok, claim_row, claim_reason = await reserve_redeem_claim(
        redeem_row=redeem_data,
        user_id=user_id_int,
        guild_id=target_guild_id_int,
        source="web",
    )
    if not claim_ok:
        notice = redeem_reason_message_th(claim_reason)
        return HTMLResponse(
            _render_redeem_web_page(
                session=session,
                guilds=guilds,
                notice=notice,
                form_values=form_values,
            ),
            status_code=409,
        )

    if "guild" in code_value:
        try:
            await change_guild_subscription(
                bot=bot,
                guild_id=target_guild_id_int,
                subscription=code_value,
                valid_for_days=valid_for_days,
            )
        except Exception as apply_error:
            await rollback_redeem_claim(
                redeem_row=claim_row,
                user_id=user_id_int,
                guild_id=target_guild_id_int,
            )
            logger.warning(
                f"Redeem apply failed (web guild): code={redeem_code} "
                f"user={user_id_int} guild={target_guild_id_int} error={apply_error}"
            )
            return HTMLResponse(
                _render_redeem_web_page(
                    session=session,
                    guilds=guilds,
                    notice="ไม่สามารถเปิดสิทธิ์จากโค้ดนี้ได้ กรุณาลองใหม่อีกครั้ง",
                    form_values=form_values,
                ),
                status_code=500,
            )
        success_notice = (
            f"Redeem success: {REDEEM_CODE_TYPES.get(code_value, code_value)} "
            f"applied to {guild_map[target_guild_id].get('name')}"
        )
    else:
        try:
            await change_user_subscription(
                bot=bot,
                user_id=user_id_int,
                subscription=code_value,
                valid_for_days=valid_for_days,
            )
        except Exception as apply_error:
            await rollback_redeem_claim(
                redeem_row=claim_row,
                user_id=user_id_int,
                guild_id=None,
            )
            logger.warning(
                f"Redeem apply failed (web user): code={redeem_code} "
                f"user={user_id_int} error={apply_error}"
            )
            return HTMLResponse(
                _render_redeem_web_page(
                    session=session,
                    guilds=guilds,
                    notice="ไม่สามารถเปิดสิทธิ์จากโค้ดนี้ได้ กรุณาลองใหม่อีกครั้ง",
                    form_values=form_values,
                ),
                status_code=500,
            )
        success_notice = f"Redeem success: {REDEEM_CODE_TYPES.get(code_value, code_value)} applied to your account."

    await finalize_redeem_claim_success(
        redeem_row=claim_row,
        user_id=user_id_int,
        guild_id=target_guild_id_int,
        source="web",
    )

    claimed_by_display = str(
        session.get("global_name")
        or session.get("username")
        or session.get("name")
        or ""
    ).strip()
    redeemed_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    code_created_iso = _redeem_datetime_to_iso(redeem_data.get("created_at"))
    code_expires_iso = _redeem_datetime_to_iso(redeem_data.get("expires_at"))
    try:
        await storage.bot_billing_events.insert(
            user_id=user_id_int,
            guild_id=target_guild_id_int,
            event_type="plan_redeem_claimed",
            level="info",
            message=success_notice,
            meta={
                "redeem_code": redeem_code,
                "plan_tier": plan_tier,
                "plan_label": plan_label,
                "support_role_id": support_role_id,
                "support_role_label": support_role_label,
                "support_guild_id": support_guild_id,
                "claimed_by_user_id": user_id_int,
                "claimed_by_display": claimed_by_display,
                "redeemed_guild_id": target_guild_id_int,
                "redeemed_guild_name": target_guild_name,
                "code_created_at": code_created_iso,
                "code_expires_at": code_expires_iso,
                "redeemed_at": redeemed_at_iso,
            },
        )
    except Exception as event_error:
        logger.warning(f"Unable to write premium history redeem event: {event_error}")

    return RedirectResponse(
        f"/dashboard/setting-profile-user/premium-history?notice={urlencode({'notice': 'Redeem completed and logged to premium history.'}).split('=',1)[1]}",
        status_code=303,
    )


async def dashboard_site_page(request: Request):
    session = _session_from_request(request)
    return HTMLResponse(
        _render_public_doc_page(
            title="เว็บไซต์ SkylineBOT",
            heading="เว็บไซต์ SkylineBOT",
            description="ศูนย์รวม SkylineBOT สำหรับฟีเจอร์ การใช้งาน และเอกสารประกอบ",
            bullets=[
                "แดชบอร์ดนี้รองรับการตั้งค่าเซิร์ฟเวอร์แบบเรียลไทม์",
                "มีฟีเจอร์เพลง ความปลอดภัย ทิกเก็ต และคำสั่งครบถ้วน",
                "สามารถเข้าสู่ระบบ Discord แล้วเลือกกิลด์เพื่อเริ่มใช้งานได้ทันที",
            ],
            session=session,
        )
    )


async def dashboard_docs_page(request: Request):
    session = _session_from_request(request)
    esc = html.escape

    def _normalize_command_name(raw_value: object) -> str:
        name = str(raw_value or "").strip().lower()
        if name.startswith("/"):
            name = name[1:].strip()
        return " ".join(name.split())

    def _plan_label(plan_tier: str) -> str:
        map_label = {
            "free": "Free",
            "silver": "Silver",
            "golden": "Gole",
            "diamond": "Diamond",
            "permanent": "Permanent",
        }
        normalized = str(plan_tier or "free").strip().lower()
        if normalized == "free":
            return "Free"
        return f"{map_label.get(normalized, normalized.capitalize())}+"

    raw_lang = str(request.query_params.get("lang") or (session or {}).get("language") or "th").strip().lower()
    docs_language = raw_lang if raw_lang in {"th", "en"} else "th"
    command_catalog = sorted(
        [row for row in list(_command_catalog(language=docs_language) or []) if isinstance(row, dict)],
        key=lambda item: str(item.get("name") or "").lower(),
    )

    command_cards_by_category: dict[str, list[str]] = {}
    free_count = 0
    premium_count = 0

    for row in command_catalog:
        command_name = _normalize_command_name(row.get("name"))
        if not command_name:
            continue
        category = str(row.get("category") or "General").strip() or "General"
        brief_default = "No description" if docs_language == "en" else "\u0e44\u0e21\u0e48\u0e21\u0e35\u0e04\u0e33\u0e2d\u0e18\u0e34\u0e1a\u0e32\u0e22"
        brief = str(row.get("brief") or "").strip() or brief_default
        slash_available = bool(row.get("slash_available"))
        prefix_available = bool(row.get("prefix_available"))

        if slash_available and prefix_available:
            mode_label = "Slash + Prefix"
        elif slash_available:
            mode_label = "Slash"
        elif prefix_available:
            mode_label = "Prefix"
        else:
            mode_label = "Unavailable"

        usage_lines = [
            str(line).strip()
            for line in list(row.get("usage_lines") or [])
            if str(line).strip()
        ]
        if not usage_lines:
            if slash_available:
                usage_lines.append(f"/{command_name}")
            if prefix_available:
                usage_lines.append(f"!{command_name}")
            if not usage_lines:
                usage_lines.append(command_name)

        example_lines = [
            str(line).strip()
            for line in list(row.get("example_lines") or [])
            if str(line).strip()
        ]
        if not example_lines:
            example_lines = list(usage_lines)

        required_tier = str(_required_plan_for_command(command_name) or "free").strip().lower()
        if required_tier == "free":
            free_count += 1
            plan_filter = "free"
        else:
            premium_count += 1
            plan_filter = "premium"
        plan_label = _plan_label(required_tier)

        usage_html = "".join(f"<li><code>{esc(line)}</code></li>" for line in usage_lines[:5]) or "<li>-</li>"
        example_html = "".join(f"<li><code>{esc(line)}</code></li>" for line in example_lines[:5]) or "<li>-</li>"

        search_blob = " ".join(
            [
                command_name,
                category,
                brief,
                mode_label,
                plan_label,
                " ".join(usage_lines),
                " ".join(example_lines),
            ]
        ).lower()

        command_cards_by_category.setdefault(category, []).append(
            f"""
            <details class="docs-cmd-card" data-cmd-item data-cmd-search="{esc(search_blob)}" data-cmd-category="{esc(category)}" data-cmd-plan="{esc(plan_filter)}">
              <summary>
                <div class="docs-cmd-head">
                  <strong>/{esc(command_name)}</strong>
                  <span>{esc(brief)}</span>
                </div>
                <div class="docs-cmd-badges">
                  <span class="docs-badge">{esc(mode_label)}</span>
                  <span class="docs-badge">{esc(plan_label)}</span>
                </div>
              </summary>
              <div class="docs-cmd-body">
                <p class="muted"><strong>ทำอะไรได้:</strong> {esc(brief)}</p>
                <div class="docs-cmd-grid">
                  <article>
                    <h4>วิธีใช้</h4>
                    <ul>{usage_html}</ul>
                  </article>
                  <article>
                    <h4>ตัวอย่าง</h4>
                    <ul>{example_html}</ul>
                  </article>
                </div>
              </div>
            </details>
            """
        )

    category_names = sorted(command_cards_by_category.keys(), key=lambda item: item.lower())
    category_options_markup = "".join(
        f'<option value="{esc(name)}">{esc(name)}</option>'
        for name in category_names
    )
    category_blocks_markup = "".join(
        (
            f'<section class="docs-cmd-category" data-cmd-group="{esc(category)}">'
            f"<h3>{esc(category)}</h3>"
            f"<div class=\"docs-cmd-list\">{''.join(command_cards_by_category.get(category, []))}</div>"
            "</section>"
        )
        for category in category_names
    )
    if not category_blocks_markup:
        category_blocks_markup = (
            '<article class="panel">'
            "<h3>ยังไม่พบคำสั่งจาก Runtime</h3>"
            "<p class=\"muted\">กรณีนี้มักเกิดเมื่อบอทยังไม่ออนไลน์ ให้รันบอทก่อน แล้วรีเฟรชหน้า /docs อีกครั้ง</p>"
            "</article>"
        )

    total_commands = free_count + premium_count

    plan_pricing_snapshot = await billing_workflow.get_plan_pricing_snapshot()
    docs_plan_catalog = [
        {"tier": "free", "title": "Free", "desc": "เริ่มต้นใช้งานได้ทันที"},
        {"tier": "silver", "title": "Silver", "desc": "ปลดล็อกฟีเจอร์พรีเมียมหลัก"},
        {"tier": "golden", "title": "Gole", "desc": "เหมาะกับเซิร์ฟเวอร์ใช้งานหนัก"},
        {"tier": "diamond", "title": "Diamond", "desc": "ขีดจำกัดสูงและสิทธิ์ครบ"},
        {"tier": "permanent", "title": "Permanent", "desc": "สิทธิ์พรีเมียมแบบถาวร"},
    ]
    docs_plan_cards: list[str] = []
    for card in docs_plan_catalog:
        quote = _pricing_quote_from_snapshot(str(card.get("tier") or "free"), plan_pricing_snapshot)
        price_html = _price_html_from_quote(quote, period_style="month")
        docs_plan_cards.append(
            f"""
        <article class="docs-plan-card">
          <h4>{esc(str(card.get('title') or '-'))}</h4>
          <p class="docs-plan-price">{price_html}</p>
          <p class="muted">{esc(str(card.get('desc') or '-'))}</p>
        </article>
        """
        )
    plan_cards_markup = "".join(docs_plan_cards)

    premium_feature_rows = _premium_feature_rows_from_live_rules()
    premium_table_tiers = _premium_table_plan_tiers()
    premium_feature_header_cells = "".join(f"<th>{esc(_plan_display_name(tier))}</th>" for tier in premium_table_tiers)
    premium_feature_table_rows = "".join(
        (
            "<tr>"
            f"<td>{esc(row[0])}</td>"
            + "".join(
                f"<td>{esc(row[idx + 1] if idx + 1 < len(row) else '-')}</td>"
                for idx, _ in enumerate(premium_table_tiers)
            )
            + "</tr>"
        )
        for row in premium_feature_rows
    )

    body = f"""
    <style>
      .docs-hub {{
        max-width: 1180px;
        margin: 0 auto;
        display: grid;
        gap: 14px;
      }}
      .docs-jump {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .docs-chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        text-decoration: none;
        border: 1px solid rgba(125, 176, 255, 0.35);
        border-radius: 999px;
        padding: 6px 12px;
        font-size: 0.88rem;
        color: inherit;
      }}
      .docs-stat-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 8px;
      }}
      .docs-stat-card {{
        border: 1px solid rgba(130, 178, 255, 0.24);
        border-radius: 12px;
        padding: 10px;
        background: rgba(30, 49, 95, 0.26);
      }}
      .docs-stat-card strong {{
        display: block;
        font-size: 1.3rem;
        line-height: 1.1;
      }}
      .docs-steps {{
        margin: 0;
        padding-left: 18px;
        line-height: 1.7;
      }}
      .docs-rule-list {{
        margin: 0;
        padding-left: 18px;
        line-height: 1.7;
      }}
      .docs-plan-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 8px;
      }}
      .docs-plan-card {{
        border: 1px solid rgba(125, 176, 255, 0.24);
        border-radius: 12px;
        padding: 10px;
        background: rgba(27, 43, 84, 0.2);
      }}
      .docs-plan-card h4 {{
        margin: 0 0 4px;
      }}
      .docs-plan-price {{
        margin: 0 0 6px;
        font-weight: 700;
      }}
      .docs-table-wrap {{
        overflow-x: auto;
      }}
      .docs-table {{
        width: 100%;
        border-collapse: collapse;
        min-width: 740px;
      }}
      .docs-table th,
      .docs-table td {{
        border: 1px solid rgba(130, 178, 255, 0.2);
        padding: 8px;
        text-align: left;
        vertical-align: top;
      }}
      .docs-cmd-toolbar {{
        display: grid;
        grid-template-columns: 1.3fr 1fr 1fr;
        gap: 8px;
      }}
      .docs-cmd-toolbar input,
      .docs-cmd-toolbar select {{
        width: 100%;
      }}
      @media (max-width: 820px) {{
        .docs-cmd-toolbar {{
          grid-template-columns: 1fr;
        }}
      }}
      .docs-cmd-category {{
        display: grid;
        gap: 8px;
      }}
      .docs-cmd-category h3 {{
        margin: 0;
      }}
      .docs-cmd-list {{
        display: grid;
        gap: 8px;
      }}
      .docs-cmd-card {{
        border: 1px solid rgba(125, 176, 255, 0.24);
        border-radius: 12px;
        background: rgba(22, 35, 72, 0.24);
        overflow: hidden;
      }}
      .docs-cmd-card summary {{
        list-style: none;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 12px;
      }}
      .docs-cmd-card summary::-webkit-details-marker {{
        display: none;
      }}
      .docs-cmd-head {{
        display: grid;
        gap: 2px;
      }}
      .docs-cmd-head strong {{
        font-size: 1rem;
      }}
      .docs-cmd-head span {{
        font-size: 0.9rem;
        opacity: 0.92;
      }}
      .docs-cmd-badges {{
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: flex-end;
        gap: 6px;
      }}
      .docs-badge {{
        border: 1px solid rgba(130, 178, 255, 0.3);
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 0.74rem;
        font-weight: 700;
      }}
      .docs-cmd-body {{
        border-top: 1px solid rgba(130, 178, 255, 0.2);
        padding: 10px 12px;
        display: grid;
        gap: 8px;
      }}
      .docs-cmd-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
      }}
      .docs-cmd-grid h4 {{
        margin: 0 0 6px;
        font-size: 0.88rem;
      }}
      .docs-cmd-grid ul {{
        margin: 0;
        padding-left: 18px;
      }}
      @media (max-width: 900px) {{
        .docs-cmd-grid {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>

    <section class="docs-hub">
      <section class="panel">
        <h1 style="margin:0;">เอกสาร SkylineBOT</h1>
        <p class="muted" style="margin:6px 0 0;">คู่มือรวมสำหรับบอท Discord, เซิร์ฟซัพพอร์ต และเว็บแดชบอร์ด ในหน้าเดียว</p>
        <div class="docs-jump" style="margin-top:10px;">
          <a class="docs-chip" href="#docs-setup">เริ่มตั้งค่า</a>
          <a class="docs-chip" href="#docs-rules">กฎการใช้งาน</a>
          <a class="docs-chip" href="#docs-plans">ตารางแพลน</a>
          <a class="docs-chip" href="#docs-commands">คำสั่งทั้งหมด</a>
        </div>
      </section>

      <section class="panel">
        <div class="docs-stat-grid">
          <article class="docs-stat-card">
            <small class="muted">จำนวนคำสั่งทั้งหมด</small>
            <strong id="docsCmdCountTotal">{total_commands}</strong>
          </article>
          <article class="docs-stat-card">
            <small class="muted">คำสั่ง Free</small>
            <strong>{free_count}</strong>
          </article>
          <article class="docs-stat-card">
            <small class="muted">คำสั่ง Premium</small>
            <strong>{premium_count}</strong>
          </article>
          <article class="docs-stat-card">
            <small class="muted">หมวดคำสั่ง</small>
            <strong>{len(category_names)}</strong>
          </article>
        </div>
      </section>

      <section id="docs-setup" class="panel">
        <h2 style="margin:0 0 8px;">ตั้งค่ายังไง (Quick Start)</h2>
        <ol class="docs-steps">
          <li>เพิ่มบอทเข้าระบบของคุณจากหน้า <a href="/invitebot">/invitebot</a></li>
          <li>ล็อกอินเว็บแดชบอร์ดที่ <a href="/dashboard/login">/dashboard/login</a></li>
          <li>เลือกเซิร์ฟเวอร์ที่ต้องการจัดการในหน้า <a href="/dashboard">/dashboard</a></li>
          <li>ตั้งค่าหลักที่แนะนำก่อน: Welcome, Security/Anti-Raid, Ticket, AutoMod</li>
          <li>เปิดหน้า <a href="/commands">/commands</a> หรือดูหัวข้อด้านล่างเพื่อค้นหาวิธีใช้คำสั่ง</li>
          <li>ถ้าต้องการปลดล็อกขีดจำกัด/ฟีเจอร์เพิ่ม ไปที่ <a href="/subscribe-plan">/subscribe-plan</a></li>
        </ol>
      </section>

      <section id="docs-rules" class="panel">
        <h2 style="margin:0 0 8px;">กฎการใช้งาน</h2>
        <ul class="docs-rule-list">
          <li>ห้ามใช้ระบบเพื่อสแปม, ฟิชชิง, หลอกลวง, หรือโจมตีเซิร์ฟเวอร์อื่น</li>
          <li>คำสั่งด้านจัดการเซิร์ฟเวอร์ควรใช้โดยผู้ดูแลที่มีสิทธิ์เท่านั้น</li>
          <li>การใช้งานต้องสอดคล้องกับ Discord Terms และกฎของเซิร์ฟเวอร์คุณ</li>
          <li>ฟีเจอร์บางส่วนถูกจำกัดตามแพลน (Free / Silver / Gole / Diamond / Permanent)</li>
          <li>ควรเปิดใช้งานระบบความปลอดภัย (เช่น Anti-Raid, AutoMod) ก่อนเปิดรับสมาชิกจำนวนมาก</li>
          <li>รายละเอียดเชิงกฎหมายดูที่ <a href="/terms">/terms</a> และ <a href="/privacy">/privacy</a></li>
        </ul>
      </section>

      <section id="docs-plans" class="panel">
        <h2 style="margin:0 0 8px;">ตาราง Plan และสิ่งที่ทำได้</h2>
        <div class="docs-plan-grid">
          {plan_cards_markup}
        </div>
        <div class="docs-table-wrap" style="margin-top:10px;">
          <table class="docs-table">
            <thead>
              <tr>
                <th>ฟีเจอร์</th>
                {premium_feature_header_cells}
              </tr>
            </thead>
            <tbody>
              {premium_feature_table_rows}
            </tbody>
          </table>
        </div>
        <p class="muted" style="margin:8px 0 0;">หมายเหตุ: Permanent คือสิทธิ์ระดับสูงสุดแบบถาวร (ไม่ต้องต่ออายุรายเดือน)</p>
      </section>

      <section id="docs-commands" class="panel">
        <h2 style="margin:0 0 8px;">คำสั่งทั้งหมด: คืออะไร ใช้ยังไง ทำอะไรได้บ้าง</h2>
        <p class="muted" style="margin:0 0 10px;">ข้อมูลคำสั่งด้านล่างดึงจาก Runtime ของบอทโดยตรง คุณสามารถค้นหาชื่อคำสั่ง/หมวด/คำอธิบายได้ทันที</p>
        <div class="docs-cmd-toolbar">
          <input id="docsCmdSearch" type="search" placeholder="ค้นหาคำสั่ง เช่น music, ticket, automod">
          <select id="docsCmdCategory">
            <option value="">ทุกหมวด</option>
            {category_options_markup}
          </select>
          <select id="docsCmdPlan">
            <option value="">ทุกแพลน</option>
            <option value="free">Free</option>
            <option value="premium">Premium</option>
          </select>
        </div>
        <p class="muted" id="docsCmdVisibleText" style="margin:10px 0 0;">แสดง {total_commands} / {total_commands} คำสั่ง</p>
      </section>

      {category_blocks_markup}

      <section class="panel">
        <h3 style="margin:0 0 8px;">คู่มือเพิ่มเติม</h3>
        <ul class="docs-rule-list">
          <li><a href="/guides/security">/guides/security</a> แนวทางความปลอดภัยและ Anti-Nuke</li>
          <li><a href="/guides/promote">/guides/promote</a> วิธีใช้งานศูนย์โปรโมตที่เชื่อมต่อกับทุกคน</li>
          <li><a href="/guides/guildstyle-roles">/guides/guildstyle-roles</a> วิธีสร้าง Roles ใน Discord ด้วย GuildStyle Studio</li>
          <li><a href="/guides/giveaways">/guides/giveaways</a> วิธีตั้งกิจกรรมแจกของ</li>
          <li><a id="docs-web-error-codes" href="/api/error-codes">/api/error-codes</a> เอกสารรหัส Web Error พร้อม owner และแนวทางแก้</li>
          <li><a href="{html.escape(CONTACT_EXTERNAL_URL, quote=True)}">{html.escape(CONTACT_EXTERNAL_URL, quote=True)}</a> ติดต่อทีมซัพพอร์ตจากหน้าเว็บ</li>
          <li><a href="/status">/status</a> ตรวจสถานะบริการ SkylineBOT</li>
          <li><a href="/commands">/commands</a> หน้าคำสั่งแบบโฟกัสการใช้งาน</li>
        </ul>
      </section>
    </section>

    <script>
      (() => {{
        const searchInput = document.getElementById("docsCmdSearch");
        const categorySelect = document.getElementById("docsCmdCategory");
        const planSelect = document.getElementById("docsCmdPlan");
        const visibleText = document.getElementById("docsCmdVisibleText");
        const totalEl = document.getElementById("docsCmdCountTotal");
        const cards = Array.from(document.querySelectorAll("[data-cmd-item]"));
        const groups = Array.from(document.querySelectorAll("[data-cmd-group]"));

        const applyFilter = () => {{
          const q = String(searchInput?.value || "").trim().toLowerCase();
          const selectedCategory = String(categorySelect?.value || "").trim().toLowerCase();
          const selectedPlan = String(planSelect?.value || "").trim().toLowerCase();
          let visible = 0;

          cards.forEach((card) => {{
            const searchBlob = String(card.getAttribute("data-cmd-search") || "").toLowerCase();
            const category = String(card.getAttribute("data-cmd-category") || "").toLowerCase();
            const plan = String(card.getAttribute("data-cmd-plan") || "").toLowerCase();
            const matchQuery = !q || searchBlob.includes(q);
            const matchCategory = !selectedCategory || category === selectedCategory;
            const matchPlan = !selectedPlan || plan === selectedPlan;
            const shouldShow = matchQuery && matchCategory && matchPlan;
            card.style.display = shouldShow ? "" : "none";
            if (shouldShow) {{
              visible += 1;
            }}
          }});

          groups.forEach((group) => {{
            const groupCards = Array.from(group.querySelectorAll("[data-cmd-item]"));
            const hasVisible = groupCards.some((item) => item.style.display !== "none");
            group.style.display = hasVisible ? "" : "none";
          }});

          if (visibleText) {{
            const total = cards.length;
            visibleText.textContent = `แสดง ${{visible}} / ${{total}} คำสั่ง`;
          }}
          if (totalEl) {{
            totalEl.textContent = String(cards.length);
          }}
        }};

        searchInput?.addEventListener("input", applyFilter);
        categorySelect?.addEventListener("change", applyFilter);
        planSelect?.addEventListener("change", applyFilter);
        applyFilter();
      }})();
    </script>
    """
    return HTMLResponse(_render_layout(title="เอกสาร SkylineBOT", body=body, session=session))


async def dashboard_leaderboard_page(request: Request):
    session = _session_from_request(request)
    selected_query_id = str(request.query_params.get("guild_id") or "").strip()
    if not session:
        next_path = "/leaderboard"
        if selected_query_id.isdigit():
            next_path = f"{next_path}?{urlencode({'guild_id': selected_query_id})}"
        return RedirectResponse(f"/dashboard/login?{urlencode({'next': next_path})}", status_code=303)

    bot = get_bot()
    bot_guild_map = {
        str(guild.id): guild
        for guild in list(getattr(bot, "guilds", []) or [])
    } if bot is not None else {}
    user_guilds = _leaderboard_user_guilds(session, bot_guild_map)

    user_guild_ids = {str(item.get("id") or "") for item in user_guilds}
    selected_guild_id = selected_query_id if selected_query_id in user_guild_ids else ""
    if not selected_guild_id and user_guilds:
        selected_guild_id = str(user_guilds[0].get("id") or "")

    selected_guild = next((item for item in user_guilds if str(item.get("id") or "") == selected_guild_id), {})
    selected_bot_guild = bot_guild_map.get(selected_guild_id) if selected_guild_id else None

    level_chat_rows: list[dict[str, object]] = []
    level_voice_rows: list[dict[str, object]] = []
    money_rows: list[dict[str, object]] = []
    invite_rows: list[dict[str, object]] = []
    invite_join_rows: list[dict[str, object]] = []
    viewer_user_id = str(_session_user_id(session) or "").strip()
    viewer_user_id_int = _leaderboard_safe_int(viewer_user_id, 0)
    viewer_rows: dict[str, dict[str, object] | None] = {
        "level_chat": None,
        "level_voice": None,
        "money": None,
        "invite": None,
    }
    total_level_chat_entries = 0
    total_level_voice_entries = 0
    total_money_entries = 0
    total_invite_entries = 0
    total_invite_join_entries = 0

    if selected_guild_id and selected_guild_id.isdigit():
        guild_id_int = int(selected_guild_id)
        raw_levels, raw_wallets, raw_invite_stats, raw_invite_members = await asyncio.gather(
            storage.levels_users.gets(guild_id=guild_id_int),
            storage.economy_wallets.gets(guild_id=guild_id_int),
            storage.invite_stats.gets(guild_id=guild_id_int),
            storage.invite_members.gets(guild_id=guild_id_int),
        )
        level_state = [row for row in list(raw_levels or []) if isinstance(row, dict)]
        wallet_state = [row for row in list(raw_wallets or []) if isinstance(row, dict)]
        invite_state = [row for row in list(raw_invite_stats or []) if isinstance(row, dict)]
        invite_member_state = [row for row in list(raw_invite_members or []) if isinstance(row, dict)]

        level_chat_state = sorted(
            level_state,
            key=lambda row: (
                _leaderboard_safe_int(row.get("text_xp"), 0),
                _leaderboard_safe_int(row.get("total_xp"), 0),
            ),
            reverse=True,
        )
        level_voice_state = sorted(
            level_state,
            key=lambda row: (
                _leaderboard_safe_int(row.get("voice_xp"), 0),
                _leaderboard_safe_int(row.get("total_xp"), 0),
            ),
            reverse=True,
        )
        wallet_state.sort(
            key=lambda row: (
                _leaderboard_safe_int(row.get("cash"), 0) + _leaderboard_safe_int(row.get("bank"), 0)
            ),
            reverse=True,
        )
        invite_state.sort(
            key=lambda row: (
                _leaderboard_safe_int(row.get("invite_count"), 0),
                _leaderboard_safe_int(row.get("last_invited_user_id"), 0),
            ),
            reverse=True,
        )
        invite_member_state.sort(
            key=lambda row: int(
                getattr(
                    row.get("updated_at") if isinstance(row.get("updated_at"), datetime.datetime) else row.get("created_at"),
                    "timestamp",
                    lambda: 0,
                )()
                if isinstance(row.get("updated_at"), datetime.datetime) or isinstance(row.get("created_at"), datetime.datetime)
                else 0
            ),
            reverse=True,
        )

        total_level_chat_entries = len(level_chat_state)
        total_level_voice_entries = len(level_voice_state)
        total_money_entries = len(wallet_state)
        total_invite_entries = len(invite_state)
        total_invite_join_entries = len(invite_member_state)

        identity_cache: dict[int, dict[str, str]] = {}
        for index, row in enumerate(level_chat_state, start=1):
            user_id = _leaderboard_safe_int(row.get("user_id"), 0)
            if user_id <= 0:
                continue
            identity = _leaderboard_user_identity(
                bot_guild=selected_bot_guild,
                bot=bot,
                user_id=user_id,
                identity_cache=identity_cache,
            )
            payload_row = {
                "rank": index,
                "user_id": str(user_id),
                "name": str(identity.get("name") or f"User {user_id}"),
                "avatar": str(identity.get("avatar") or ""),
                "level": _leaderboard_safe_int(row.get("level"), 0),
                "text_xp": _leaderboard_safe_int(row.get("text_xp"), 0),
                "total_xp": _leaderboard_safe_int(row.get("total_xp"), 0),
            }
            if index <= 100:
                level_chat_rows.append(payload_row)
            if viewer_user_id_int > 0 and user_id == viewer_user_id_int and viewer_rows.get("level_chat") is None:
                viewer_rows["level_chat"] = payload_row

        for index, row in enumerate(level_voice_state, start=1):
            user_id = _leaderboard_safe_int(row.get("user_id"), 0)
            if user_id <= 0:
                continue
            identity = _leaderboard_user_identity(
                bot_guild=selected_bot_guild,
                bot=bot,
                user_id=user_id,
                identity_cache=identity_cache,
            )
            payload_row = {
                "rank": index,
                "user_id": str(user_id),
                "name": str(identity.get("name") or f"User {user_id}"),
                "avatar": str(identity.get("avatar") or ""),
                "level": _leaderboard_safe_int(row.get("level"), 0),
                "voice_xp": _leaderboard_safe_int(row.get("voice_xp"), 0),
                "total_xp": _leaderboard_safe_int(row.get("total_xp"), 0),
            }
            if index <= 100:
                level_voice_rows.append(payload_row)
            if viewer_user_id_int > 0 and user_id == viewer_user_id_int and viewer_rows.get("level_voice") is None:
                viewer_rows["level_voice"] = payload_row

        for index, row in enumerate(wallet_state, start=1):
            user_id = _leaderboard_safe_int(row.get("user_id"), 0)
            if user_id <= 0:
                continue
            identity = _leaderboard_user_identity(
                bot_guild=selected_bot_guild,
                bot=bot,
                user_id=user_id,
                identity_cache=identity_cache,
            )
            cash = _leaderboard_safe_int(row.get("cash"), 0)
            bank = _leaderboard_safe_int(row.get("bank"), 0)
            payload_row = {
                "rank": index,
                "user_id": str(user_id),
                "name": str(identity.get("name") or f"User {user_id}"),
                "avatar": str(identity.get("avatar") or ""),
                "cash": cash,
                "bank": bank,
                "total": cash + bank,
            }
            if index <= 100:
                money_rows.append(payload_row)
            if viewer_user_id_int > 0 and user_id == viewer_user_id_int and viewer_rows.get("money") is None:
                viewer_rows["money"] = payload_row

        for index, row in enumerate(invite_state, start=1):
            inviter_id = _leaderboard_safe_int(row.get("inviter_id"), 0)
            if inviter_id <= 0:
                continue
            identity = _leaderboard_user_identity(
                bot_guild=selected_bot_guild,
                bot=bot,
                user_id=inviter_id,
                identity_cache=identity_cache,
            )
            payload_row = {
                "rank": index,
                "user_id": str(inviter_id),
                "name": str(identity.get("name") or f"User {inviter_id}"),
                "avatar": str(identity.get("avatar") or ""),
                "invite_count": _leaderboard_safe_int(row.get("invite_count"), 0),
                "last_invite_code": str(row.get("last_invite_code") or "").strip(),
                "last_invite_url": str(row.get("last_invite_url") or "").strip(),
                "last_invited_user_id": str(_leaderboard_safe_int(row.get("last_invited_user_id"), 0)),
            }
            if index <= 100:
                invite_rows.append(payload_row)
            if viewer_user_id_int > 0 and inviter_id == viewer_user_id_int and viewer_rows.get("invite") is None:
                viewer_rows["invite"] = payload_row

        for row in invite_member_state[:100]:
            invited_user_id = _leaderboard_safe_int(row.get("user_id"), 0)
            inviter_id = _leaderboard_safe_int(row.get("inviter_id"), 0)
            if invited_user_id <= 0:
                continue
            invited_identity = _leaderboard_user_identity(
                bot_guild=selected_bot_guild,
                bot=bot,
                user_id=invited_user_id,
                identity_cache=identity_cache,
            )
            inviter_identity = (
                _leaderboard_user_identity(
                    bot_guild=selected_bot_guild,
                    bot=bot,
                    user_id=inviter_id,
                    identity_cache=identity_cache,
                )
                if inviter_id > 0
                else {"name": "Unknown", "avatar": "https://cdn.discordapp.com/embed/avatars/0.png"}
            )
            joined_at_value = row.get("updated_at") if isinstance(row.get("updated_at"), datetime.datetime) else row.get("created_at")
            joined_at_ts = int(getattr(joined_at_value, "timestamp", lambda: 0)()) if isinstance(joined_at_value, datetime.datetime) else 0
            invite_join_rows.append(
                {
                    "invited_user_id": str(invited_user_id),
                    "invited_name": str(invited_identity.get("name") or f"User {invited_user_id}"),
                    "invited_avatar": str(invited_identity.get("avatar") or ""),
                    "inviter_user_id": str(inviter_id) if inviter_id > 0 else "",
                    "inviter_name": str(inviter_identity.get("name") or ("User " + str(inviter_id) if inviter_id > 0 else "Unknown")),
                    "inviter_avatar": str(inviter_identity.get("avatar") or ""),
                    "invite_code": str(row.get("invite_code") or "").strip(),
                    "invite_url": str(row.get("invite_url") or "").strip(),
                    "joined_at_ts": joined_at_ts,
                }
            )

    payload = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "viewer_user_id": viewer_user_id,
        "guilds": user_guilds,
        "selected_guild_id": selected_guild_id,
        "selected_guild_name": str(selected_guild.get("name") or ""),
        "selected_guild_members": _leaderboard_safe_int(selected_guild.get("members"), 0),
        "level_chat_rows": level_chat_rows,
        "level_voice_rows": level_voice_rows,
        "money_rows": money_rows,
        "invite_rows": invite_rows,
        "invite_join_rows": invite_join_rows,
        "viewer_rows": viewer_rows,
        "totals": {
            "guild_count": len(user_guilds),
            "level_chat_entries": total_level_chat_entries,
            "level_voice_entries": total_level_voice_entries,
            "money_entries": total_money_entries,
            "invite_entries": total_invite_entries,
            "invite_join_entries": total_invite_join_entries,
        },
    }
    return HTMLResponse(_render_leaderboard_page(request, payload))


async def dashboard_tags_page(request: Request):
    return HTMLResponse(_render_tags_page(request))


async def dashboard_promote_history_page(request: Request):
    context = _build_developer_portal_context(request)
    session = _session_from_request(request)
    ownerbot_mode = bool(_is_dashboard_admin(session))
    query_text = str(request.query_params.get("q") or "").strip()[:140]
    guild_id_filter = _safe_int(request.query_params.get("guild_id"), 0)
    source_filter = str(request.query_params.get("source") or "").strip().lower()
    if source_filter not in {"web", "discord"}:
        source_filter = ""
    limit_filter = _safe_int(request.query_params.get("limit"), 50)
    if limit_filter not in {50, 100, 200}:
        limit_filter = 50

    latest_guild_mode = bool(not query_text and guild_id_filter <= 0)
    if latest_guild_mode:
        rows = await storage.promote_history.query_recent_latest_guild_records(
            limit=limit_filter,
            source_origin=source_filter,
        )
    else:
        rows = await storage.promote_history.query_recent(
            limit=limit_filter,
            guild_id=guild_id_filter,
            source_origin=source_filter,
            search_text=query_text,
        )
    guild_filters = await storage.promote_history.recent_guild_filters(limit=300)
    suspension_map = await _promote_suspension_map_load()
    suspended_ids = {
        _safe_int(key, 0)
        for key in suspension_map.keys()
        if _safe_int(key, 0) > 0
    }

    rendered = _render_promote_history_page_html(
        app_name=str(context.get("APP_NAME") or "SkylineBOT"),
        query_text=query_text,
        guild_id_filter=guild_id_filter,
        source_filter=source_filter,
        limit_filter=limit_filter,
        guild_filters=guild_filters,
        rows=rows,
        latest_guild_mode=latest_guild_mode,
        ownerbot_mode=ownerbot_mode,
        suspended_guild_ids=suspended_ids,
    )
    return HTMLResponse(_apply_global_public_footer(rendered))


async def dashboard_promote_history_action(request: Request):
    session = _session_from_request(request)
    if not _is_dashboard_admin(session):
        return RedirectResponse(
            f"/promotehistory?{urlencode({'notice': 'OwnerBOT only'})}",
            status_code=303,
        )

    data = await _parse_form(request)
    action = str(data.get("action") or "").strip().lower()
    history_id = _safe_int(data.get("history_id"), 0)
    if history_id <= 0:
        return RedirectResponse(
            f"/promotehistory?{urlencode({'notice': 'Invalid history id'})}",
            status_code=303,
        )

    row = await storage.promote_history.get(id=history_id)
    if not isinstance(row, dict):
        return RedirectResponse(
            f"/promotehistory?{urlencode({'notice': 'Promote history not found'})}",
            status_code=303,
        )

    user = dict((session or {}).get("user") or {})
    actor_id = _safe_int(user.get("id"), 0)
    actor_name = str(user.get("global_name") or user.get("username") or f"Owner {actor_id or '-'}").strip()[:120]
    actor_note = _clean_text(data.get("note") or "").strip()[:600]
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    notice = "Action completed"
    if action == "delete":
        deleted_snapshot = {
            **row,
            "owner_action_by_id": actor_id,
            "owner_action_by_name": actor_name,
            "owner_note": actor_note,
        }
        await storage.promote_history.delete(id=history_id)
        await _promote_sync_owner_review_message(deleted_snapshot, deleted=True)
        notice = f"Deleted promote history #{history_id}"
    elif action == "edit":
        content = _clean_text(data.get("content") or "").strip()[:1800]
        if not content:
            return RedirectResponse(
                f"/promotehistory?{urlencode({'notice': 'Content is required for edit'})}",
                status_code=303,
            )
        await storage.promote_history.update(
            id=history_id,
            content=content,
            hidden=False,
            owner_note=actor_note,
            owner_action_by_id=actor_id,
            owner_action_by_name=actor_name,
            owner_action_at=now_utc,
        )
        row = await storage.promote_history.get(id=history_id) or row
        await _promote_sync_owner_review_message(row)
        notice = f"Updated promote history #{history_id}"
    elif action == "hide":
        if not actor_note:
            actor_note = "Hidden by OwnerBOT"
        await storage.promote_history.update(
            id=history_id,
            hidden=True,
            owner_note=actor_note,
            owner_action_by_id=actor_id,
            owner_action_by_name=actor_name,
            owner_action_at=now_utc,
        )
        row = await storage.promote_history.get(id=history_id) or row
        await _promote_sync_owner_review_message(row)
        notice = f"Hidden promote history #{history_id}"
    elif action == "unhide":
        await storage.promote_history.update(
            id=history_id,
            hidden=False,
            owner_note=actor_note,
            owner_action_by_id=actor_id,
            owner_action_by_name=actor_name,
            owner_action_at=now_utc,
        )
        row = await storage.promote_history.get(id=history_id) or row
        await _promote_sync_owner_review_message(row)
        notice = f"Unhidden promote history #{history_id}"
    elif action in {"suspend_guild", "unsuspend_guild"}:
        guild_id = _safe_int(row.get("guild_id"), 0)
        if guild_id <= 0:
            return RedirectResponse(
                f"/promotehistory?{urlencode({'notice': 'Guild id is missing'})}",
                status_code=303,
            )
        suspension_map = await _promote_suspension_map_load()
        if action == "suspend_guild":
            suspension_map[str(guild_id)] = {
                "note": actor_note,
                "by_name": actor_name,
                "updated_at": now_utc.isoformat(),
            }
            notice = f"Suspended promote from guild {guild_id}"
        else:
            suspension_map.pop(str(guild_id), None)
            notice = f"Unsuspended promote from guild {guild_id}"
        await _promote_suspension_map_save(suspension_map)
        await storage.promote_history.update(
            id=history_id,
            owner_note=actor_note,
            owner_action_by_id=actor_id,
            owner_action_by_name=actor_name,
            owner_action_at=now_utc,
        )
        row = await storage.promote_history.get(id=history_id) or row
        await _promote_sync_owner_review_message(row)
    else:
        return RedirectResponse(
            f"/promotehistory?{urlencode({'notice': 'Unknown action'})}",
            status_code=303,
        )

    return RedirectResponse(
        f"/promotehistory?{urlencode({'notice': notice})}",
        status_code=303,
    )


async def dashboard_promote_server_page(request: Request):
    context = _build_developer_portal_context(request)
    query_text = str(request.query_params.get("q") or "").strip()[:160]
    auto_refresh_raw = str(request.query_params.get("auto_refresh") or "1").strip().lower()
    auto_refresh_enabled = auto_refresh_raw not in {"0", "false", "off", "no", "disable", "disabled"}
    source_filter = str(request.query_params.get("source") or "").strip().lower()
    if source_filter not in {"web", "discord"}:
        source_filter = ""
    limit_filter = _safe_int(request.query_params.get("limit"), 50)
    if limit_filter not in {20, 50, 100}:
        limit_filter = 50
    feed_mode = str(request.query_params.get("mode") or "latest_guild").strip().lower()
    if feed_mode not in {"latest_guild", "timeline"}:
        feed_mode = "latest_guild"
    active_promote_guild_total = 0
    try:
        promote_rows = await storage.promote_channels.get_all()
        active_ids: set[int] = set()
        for row in list(promote_rows or []):
            if not isinstance(row, dict):
                continue
            submit_id = int(row.get("submit_channel_id") or 0)
            public_id = int(row.get("public_channel_id") or 0)
            guild_id = int(row.get("guild_id") or 0)
            if guild_id > 0 and submit_id > 0 and public_id > 0:
                active_ids.add(guild_id)
        active_promote_guild_total = len(active_ids)
    except Exception:
        active_promote_guild_total = 0

    if query_text:
        rows = await storage.promote_history.query_recent(
            limit=limit_filter,
            source_origin=source_filter,
            search_text=query_text,
        )
        feed_mode = "timeline"
    elif feed_mode == "timeline":
        rows = await storage.promote_history.query_recent(
            limit=limit_filter,
            source_origin=source_filter,
        )
    else:
        rows = await storage.promote_history.query_recent_latest_guild_records(
            limit=limit_filter,
            source_origin=source_filter,
        )

    fallback_notice = ""
    if not rows and source_filter:
        if query_text or feed_mode == "timeline":
            fallback_rows = await storage.promote_history.query_recent(
                limit=limit_filter,
                source_origin="",
                search_text=query_text,
            )
        else:
            fallback_rows = await storage.promote_history.query_recent_latest_guild_records(
                limit=limit_filter,
                source_origin="",
            )
        if fallback_rows:
            rows = fallback_rows
            fallback_notice = (
                f'No promote records found for source "{source_filter}". '
                "Showing all sources instead."
            )

    rendered = _render_promote_server_page_html(
        app_name=str(context.get("APP_NAME") or "SkylineBOT"),
        query_text=query_text,
        source_filter=source_filter,
        limit_filter=limit_filter,
        feed_mode=feed_mode,
        auto_refresh_enabled=auto_refresh_enabled,
        active_promote_guild_total=active_promote_guild_total,
        rows=rows,
        fallback_notice=fallback_notice,
    )
    return HTMLResponse(_apply_global_public_footer(rendered))


async def dashboard_personalizer_page(request: Request):
    context = _build_developer_portal_context(request)
    default_text = "Skyline Bot \u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35 123"
    sample_text = "Fancy Fonts \u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35 123"
    style_rows = fancy_text.list_styles(sample_text=sample_text)
    category_rows = fancy_text.list_categories()
    context["PERSONALIZER_DEFAULT_TEXT"] = default_text
    context["PERSONALIZER_DEFAULT_STYLE"] = "double_struck"
    context["PERSONALIZER_DEFAULT_CATEGORY"] = "all"
    context["PERSONALIZER_DEFAULT_OUTPUT"] = fancy_text.transform_text(default_text, "double_struck")
    context["PERSONALIZER_STYLES_JSON"] = json.dumps(style_rows, ensure_ascii=False)
    context["PERSONALIZER_CATEGORIES_JSON"] = json.dumps(category_rows, ensure_ascii=False)
    return HTMLResponse(_render_public_html_template(PUBLIC_PAGE_TEMPLATES["personalizer"], context))


async def dashboard_personalizer_preview(request: Request):
    raw_style = str(request.query_params.get("style") or "double_struck").strip()
    raw_text = str(request.query_params.get("text") or "")
    include_all = str(request.query_params.get("all") or "").strip().lower() in {"1", "true", "yes", "on"}
    safe_text = raw_text[:1800]
    style = fancy_text.resolve_style(raw_style)
    payload: dict[str, object] = {
        "ok": True,
        "style": style.key,
        "style_name": style.label,
        "text": safe_text,
        "result": fancy_text.transform_text(safe_text, style.key),
    }
    if include_all:
        payload["styles"] = fancy_text.convert_all(safe_text)
    return JSONResponse(payload, headers=dict(_STATUS_NO_CACHE_HEADERS))

async def dashboard_server_support_page(request: Request):
    context = _build_developer_portal_context(request)
    context["SUPPORT_SERVER_URL"] = str(style_urls.SUPPORT_SERVER or "").strip()
    context["SUPPORT_STATUS_URL"] = str(_support_status_public_url() or "").strip()
    return HTMLResponse(_render_public_html_template(PUBLIC_PAGE_TEMPLATES["serversupport"], context))

async def dashboard_support_page(request: Request):
    context = _build_developer_portal_context(request)
    context["SUPPORT_SERVER_URL"] = str(style_urls.SUPPORT_SERVER or "").strip()
    context["SUPPORT_STATUS_URL"] = str(_support_status_public_url() or "").strip()
    return HTMLResponse(_render_public_html_template(PUBLIC_PAGE_TEMPLATES["support"], context))

async def dashboard_rule_page(request: Request):
    context = _build_developer_portal_context(request)
    context["SUPPORT_SERVER_URL"] = str(style_urls.SUPPORT_SERVER or "").strip()
    context["RULE_BOT_URL"] = "/rule/bot"
    context["RULE_SERVER_SUPPORT_URL"] = "/rule/serversupport"
    return HTMLResponse(_render_public_html_template(PUBLIC_PAGE_TEMPLATES["rule_hub"], context))

async def dashboard_rule_bot_page(request: Request):
    return await dashboard_terms_page(request)

async def dashboard_rule_server_support_page(request: Request):
    context = _build_developer_portal_context(request)
    context["SUPPORT_SERVER_URL"] = str(style_urls.SUPPORT_SERVER or "").strip()
    context["RULE_BOT_URL"] = "/rule/bot"
    context["RULE_SERVER_SUPPORT_URL"] = "/rule/serversupport"
    return HTMLResponse(_render_public_html_template(PUBLIC_PAGE_TEMPLATES["rule_server_support"], context))


async def dashboard_invitebot_page(request: Request):
    return HTMLResponse(_render_developer_portal_page(request, PUBLIC_PAGE_TEMPLATES["invitebot"]))


async def dashboard_interactions_endpoint_page(request: Request):
    return HTMLResponse(_render_developer_portal_page(request, PUBLIC_PAGE_TEMPLATES["interactions_endpoint"]))


async def dashboard_linked_role_verify_page(request: Request):
    return HTMLResponse(_render_developer_portal_page(request, PUBLIC_PAGE_TEMPLATES["linked_role_verify"]))


def _verify_session_avatar_fallback(seed_value: int) -> str:
    index = abs(int(seed_value or 0)) % 5
    return f"https://cdn.discordapp.com/embed/avatars/{index}.png"


def _verify_session_back_url(guild_id: int, settings: dict[str, Any]) -> str:
    configured = str(settings.get("back_to_server_url") or "").strip()
    normalized = configured.lower()
    expected_prefixes = (
        f"https://discord.com/channels/{int(guild_id)}".lower(),
        f"http://discord.com/channels/{int(guild_id)}".lower(),
    )
    if any(normalized.startswith(prefix) for prefix in expected_prefixes):
        return configured
    return f"https://discord.com/channels/{int(guild_id)}"


def _verify_session_theme_variant(value: str) -> str:
    normalized = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum() or ch in {"-", "_"})
    if normalized in {"premium-gold", "gold-premium", "gold", "premium"}:
        return "premium-gold"
    return "cyber-green"


def _verify_session_query_path(
    token: str,
    *,
    status: str | None = None,
    theme_variant: str | None = None,
) -> str:
    params: dict[str, str] = {}
    safe_token = str(token or "").strip()
    if safe_token:
        params["t"] = safe_token
    safe_status = str(status or "").strip().lower()
    if safe_status:
        params["status"] = safe_status
    normalized_theme = _verify_session_theme_variant(str(theme_variant or ""))
    if normalized_theme == "premium-gold":
        params["theme"] = normalized_theme
    if not params:
        return "/dashboard/verify/session"
    return f"/dashboard/verify/session?{urlencode(params)}"


def _render_verify_session_page_html(
    *,
    title: str,
    subtitle: str,
    status_badge: str,
    status_class: str,
    status_note: str,
    verify_action_url: str,
    token: str,
    can_submit: bool,
    submit_label: str,
    submit_icon: str,
    back_url: str,
    back_label: str,
    server_name: str,
    server_icon_url: str,
    user_name: str,
    user_tag: str,
    user_icon_url: str,
    reward_role_names: list[str],
    remove_role_names: list[str],
    theme_variant: str = "cyber-green",
    status_key: str = "",
) -> str:
    safe_title = html.escape(str(title or "").strip() or "Verify")
    safe_subtitle = html.escape(str(subtitle or "").strip() or "Verification page")
    safe_badge = html.escape(str(status_badge or "").strip() or "Status")
    safe_status_note = html.escape(str(status_note or "").strip() or "")
    safe_status_class = html.escape(str(status_class or "").strip() or "is-pending")
    safe_server_name = html.escape(str(server_name or "").strip() or "Server")
    safe_server_icon = html.escape(str(server_icon_url or "").strip() or _verify_session_avatar_fallback(0), quote=True)
    safe_user_name = html.escape(str(user_name or "").strip() or "User")
    safe_user_tag = html.escape(str(user_tag or "").strip() or "-", quote=True)
    safe_user_icon = html.escape(str(user_icon_url or "").strip() or _verify_session_avatar_fallback(1), quote=True)
    safe_verify_action_url = html.escape(str(verify_action_url or "/dashboard/verify/session"), quote=True)
    safe_token = html.escape(str(token or "").strip(), quote=True)
    safe_submit_label = html.escape(str(submit_label or "ยืนยันตัวตน"), quote=True)
    safe_submit_icon = html.escape(str(submit_icon or "bi bi-check2-circle"), quote=True)
    safe_back_url = html.escape(str(back_url or "https://discord.com"), quote=True)
    normalized_theme = _verify_session_theme_variant(theme_variant)
    safe_theme_class = html.escape(f"theme-{normalized_theme}", quote=True)
    safe_theme_value = html.escape(normalized_theme, quote=True)
    safe_cyber_href = html.escape(
        _verify_session_query_path(token, status=status_key, theme_variant="cyber-green"),
        quote=True,
    )
    safe_gold_href = html.escape(
        _verify_session_query_path(token, status=status_key, theme_variant="premium-gold"),
        quote=True,
    )
    theme_cyber_class = "theme-chip is-active" if normalized_theme == "cyber-green" else "theme-chip"
    theme_gold_class = "theme-chip is-active" if normalized_theme == "premium-gold" else "theme-chip"
    safe_footer_copy = html.escape(_global_copyright_text(), quote=True)
    safe_terms_url = html.escape("/terms-of-service", quote=True)
    safe_privacy_url = html.escape("/privacy-policy", quote=True)
    safe_support_url = html.escape("/support", quote=True)
    safe_back_label = html.escape(str(back_label or "กลับสู่ Server"), quote=True)

    reward_role_options = "".join(
        f"<option>+ {html.escape(name, quote=True)}</option>"
        for name in reward_role_names
    ) or "<option>ไม่มีรายการ</option>"
    remove_role_options = "".join(
        f"<option>- {html.escape(name, quote=True)}</option>"
        for name in remove_role_names
    ) or "<option>ไม่มีรายการ</option>"
    disabled_attr = "" if can_submit else "disabled"
    submit_button_class = "verify-btn primary" if can_submit else "verify-btn primary is-disabled"

    rendered_html = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="alternate icon" type="image/png" href="/favicon.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    :root {{
      color-scheme: dark;
      --bg-1: #040814;
      --bg-2: #0c1730;
      --line: rgba(134, 167, 255, .28);
      --line-soft: rgba(120, 150, 230, .22);
      --text-main: #eff6ff;
      --text-soft: #c8d8ee;
      --text-dim: #9cb3d4;
      --good: #42d689;
      --warn: #f0b44a;
      --bad: #f87171;
      --glow-left: rgba(62, 146, 255, .6);
      --glow-right: rgba(66, 214, 137, .6);
      --badge-pending-border: rgba(240, 180, 74, .5);
      --badge-pending-text: #ffe3b8;
      --badge-pending-pulse: rgba(240, 180, 74, .13);
      --btn-primary-start: #37c775;
      --btn-primary-end: #2dc4e6;
      --btn-primary-border: rgba(66, 214, 137, .45);
      --btn-primary-text: #031423;
      --btn-primary-shadow-a: rgba(45, 196, 230, .32);
      --btn-primary-shadow-b: rgba(55, 199, 117, .2);
      --btn-primary-shadow-a-strong: rgba(45, 196, 230, .4);
      --btn-primary-shadow-b-strong: rgba(55, 199, 117, .26);
      --footer-bg: linear-gradient(145deg, rgba(9, 19, 38, .88), rgba(8, 17, 35, .72));
      --footer-line: rgba(110, 156, 255, .34);
      --footer-text: #9db4d7;
      --footer-link: #d8ebff;
      --footer-link-hover: #ffffff;
    }}
    body.theme-premium-gold {{
      --bg-1: #140a01;
      --bg-2: #2d1803;
      --line: rgba(255, 195, 102, .32);
      --line-soft: rgba(245, 187, 95, .26);
      --text-main: #fff4db;
      --text-soft: #f5e1af;
      --text-dim: #ceb781;
      --glow-left: rgba(255, 179, 70, .6);
      --glow-right: rgba(255, 229, 158, .5);
      --badge-pending-border: rgba(255, 201, 88, .72);
      --badge-pending-text: #ffefc2;
      --badge-pending-pulse: rgba(255, 198, 82, .24);
      --btn-primary-start: #ebbc5a;
      --btn-primary-end: #f7dd9d;
      --btn-primary-border: rgba(235, 188, 90, .58);
      --btn-primary-text: #2b1800;
      --btn-primary-shadow-a: rgba(235, 188, 90, .32);
      --btn-primary-shadow-b: rgba(247, 221, 157, .2);
      --btn-primary-shadow-a-strong: rgba(235, 188, 90, .42);
      --btn-primary-shadow-b-strong: rgba(247, 221, 157, .26);
      --footer-bg: linear-gradient(145deg, rgba(42, 24, 4, .9), rgba(31, 18, 3, .76));
      --footer-line: rgba(244, 192, 98, .4);
      --footer-text: #d9c292;
      --footer-link: #fff0c9;
      --footer-link-hover: #fff8e8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Outfit", "Segoe UI", sans-serif;
      color: var(--text-main);
      background:
        radial-gradient(circle at 10% 8%, rgba(120, 170, 255, 0.18), transparent 38%),
        radial-gradient(circle at 88% 0%, rgba(74, 222, 128, 0.14), transparent 42%),
        linear-gradient(160deg, var(--bg-1), var(--bg-2));
      padding: 22px;
      position: relative;
      overflow-x: hidden;
      isolation: isolate;
    }}
    body::before,
    body::after {{
      content: "";
      position: fixed;
      width: clamp(220px, 35vw, 420px);
      height: clamp(220px, 35vw, 420px);
      border-radius: 50%;
      filter: blur(22px);
      opacity: .52;
      z-index: 0;
      pointer-events: none;
      animation: glow-float 8s ease-in-out infinite;
    }}
    body::before {{
      top: -90px;
      left: -80px;
      background: radial-gradient(circle, var(--glow-left) 0%, rgba(62, 146, 255, 0) 72%);
    }}
    body::after {{
      right: -90px;
      bottom: -100px;
      background: radial-gradient(circle, var(--glow-right) 0%, rgba(66, 214, 137, 0) 72%);
      animation-delay: -3.2s;
    }}
    .verify-shell {{
      width: min(980px, 100%);
      margin: 0 auto;
      display: grid;
      gap: 14px;
      position: relative;
      z-index: 1;
      animation: shell-enter .56s ease-out both;
    }}
    .verify-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: linear-gradient(160deg, rgba(8, 16, 34, 0.92), rgba(7, 24, 50, 0.82));
      box-shadow: 0 20px 52px rgba(0, 0, 0, .36);
      padding: 18px;
      backdrop-filter: blur(8px);
      position: relative;
      overflow: hidden;
      transition: border-color .22s ease, box-shadow .22s ease, transform .22s ease;
    }}
    .verify-card::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(120deg, rgba(126, 196, 255, .11), rgba(66, 214, 137, .08), transparent 55%);
      opacity: .8;
      pointer-events: none;
    }}
    .verify-card:hover {{
      border-color: rgba(149, 188, 255, .46);
      box-shadow: 0 24px 58px rgba(0, 0, 0, .42);
      transform: translateY(-1px);
    }}
    .hero-card {{
      text-align: center;
      padding-top: 22px;
      padding-bottom: 22px;
    }}
    .verify-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 7px 12px;
      font-weight: 700;
      font-size: .84rem;
      margin: 0 auto 12px;
      background: rgba(19, 34, 66, .65);
      position: relative;
      box-shadow: 0 10px 24px rgba(0, 0, 0, .2);
    }}
    .verify-badge.is-success {{ border-color: rgba(66, 214, 137, .5); color: #bcf7da; }}
    .verify-badge.is-error {{ border-color: rgba(248, 113, 113, .5); color: #ffd2d2; }}
    .verify-badge.is-pending {{
      border-color: var(--badge-pending-border);
      color: var(--badge-pending-text);
      animation: badge-pulse 1.9s ease-in-out infinite;
    }}
    .verify-title {{
      margin: 0;
      font-size: clamp(1.3rem, 2.5vw, 1.86rem);
      letter-spacing: .01em;
      position: relative;
      z-index: 1;
    }}
    .verify-subtitle {{
      margin: 8px auto 0;
      color: var(--text-soft);
      line-height: 1.6;
      max-width: 760px;
      position: relative;
      z-index: 1;
    }}
    .verify-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .profile-card {{
      border: 1px solid var(--line-soft);
      border-radius: 14px;
      padding: 12px;
      display: flex;
      align-items: center;
      gap: 12px;
      background: rgba(12, 24, 47, .6);
    }}
    .profile-card img {{
      width: 52px;
      height: 52px;
      border-radius: 50%;
      object-fit: cover;
      border: 1px solid var(--line);
      flex: 0 0 auto;
    }}
    .profile-card strong {{
      display: block;
      font-size: 1rem;
      margin-bottom: 2px;
    }}
    .profile-card span {{
      display: block;
      color: var(--text-dim);
      font-size: .86rem;
    }}
    .verify-note {{
      margin: 0;
      color: var(--text-soft);
      line-height: 1.6;
      text-align: center;
    }}
    .role-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    .role-box {{
      border: 1px solid var(--line-soft);
      border-radius: 12px;
      background: rgba(11, 22, 42, .66);
      padding: 10px;
    }}
    .role-box label {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: .87rem;
      margin-bottom: 6px;
      color: var(--text-soft);
      font-weight: 700;
    }}
    .role-box select {{
      width: 100%;
      min-height: 108px;
      border-radius: 10px;
      border: 1px solid var(--line-soft);
      background: rgba(8, 15, 31, .82);
      color: var(--text-main);
      padding: 8px;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 12px;
      margin-top: 16px;
    }}
    .actions form {{
      margin: 0;
      display: flex;
    }}
    .theme-switch {{
      margin-top: 14px;
      display: inline-flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px;
      position: relative;
      z-index: 1;
    }}
    .theme-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      border-radius: 999px;
      border: 1px solid var(--line-soft);
      background: rgba(16, 30, 57, .7);
      color: var(--text-soft);
      padding: 0 12px;
      font-size: .8rem;
      font-weight: 700;
      text-decoration: none;
      transition: transform .16s ease, filter .16s ease, border-color .16s ease;
    }}
    .theme-chip:hover {{
      transform: translateY(-1px);
      filter: brightness(1.08);
      border-color: var(--line);
    }}
    .theme-chip.is-active {{
      border-color: rgba(173, 221, 255, .65);
      color: #f2fbff;
      background: rgba(32, 61, 108, .78);
      box-shadow: 0 8px 22px rgba(7, 13, 27, .35);
    }}
    .verify-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 52px;
      min-width: 220px;
      border-radius: 14px;
      padding: 0 20px;
      border: 1px solid rgba(124, 179, 255, 0.45);
      text-decoration: none;
      font-weight: 800;
      font-size: 1.04rem;
      cursor: pointer;
      transition: transform .18s ease, filter .18s ease, box-shadow .2s ease;
      background: rgba(20, 35, 65, .74);
      color: #deecff;
      box-shadow: 0 8px 24px rgba(5, 10, 21, .42);
    }}
    .verify-btn:hover {{
      transform: translateY(-2px) scale(1.02);
      filter: brightness(1.06);
      box-shadow: 0 14px 28px rgba(5, 10, 21, .48);
    }}
    .verify-btn:active {{ transform: translateY(0); }}
    .verify-btn.primary {{
      border-color: var(--btn-primary-border);
      background: linear-gradient(120deg, var(--btn-primary-start) 0%, var(--btn-primary-end) 95%);
      color: var(--btn-primary-text);
      box-shadow: 0 14px 34px var(--btn-primary-shadow-a), 0 8px 20px var(--btn-primary-shadow-b);
      animation: primary-breathe 2.6s ease-in-out infinite;
    }}
    .verify-btn.primary.is-disabled {{
      filter: grayscale(0.45);
      cursor: not-allowed;
      opacity: .8;
      animation: none;
    }}
    .verify-btn.ghost {{
      border-color: rgba(124, 179, 255, .4);
      background: rgba(12, 23, 45, .7);
      color: #d6eaff;
    }}
    .verify-footer {{
      border: 1px solid var(--footer-line);
      border-radius: 14px;
      background: var(--footer-bg);
      backdrop-filter: blur(8px);
      padding: 12px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px 14px;
      flex-wrap: wrap;
      position: relative;
      z-index: 1;
    }}
    .verify-footer p {{
      margin: 0;
      color: var(--footer-text);
      font-size: .82rem;
      letter-spacing: .01em;
    }}
    .verify-footer nav {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .verify-footer a {{
      text-decoration: none;
      color: var(--footer-link);
      font-size: .84rem;
      font-weight: 700;
      transition: color .18s ease, transform .18s ease;
    }}
    .verify-footer a:hover {{
      color: var(--footer-link-hover);
      transform: translateY(-1px);
    }}
    @keyframes glow-float {{
      0%, 100% {{ transform: translate3d(0, 0, 0) scale(1); }}
      50% {{ transform: translate3d(0, 14px, 0) scale(1.07); }}
    }}
    @keyframes badge-pulse {{
      0%, 100% {{ box-shadow: 0 0 0 rgba(240, 180, 74, 0); }}
      50% {{ box-shadow: 0 0 0 8px var(--badge-pending-pulse); }}
    }}
    @keyframes primary-breathe {{
      0%, 100% {{ box-shadow: 0 14px 34px var(--btn-primary-shadow-a), 0 8px 20px var(--btn-primary-shadow-b); }}
      50% {{ box-shadow: 0 18px 42px var(--btn-primary-shadow-a-strong), 0 10px 24px var(--btn-primary-shadow-b-strong); }}
    }}
    @keyframes shell-enter {{
      from {{ opacity: 0; transform: translateY(8px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (max-width: 900px) {{
      .verify-grid, .role-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 600px) {{
      body {{ padding: 14px; }}
      .verify-card {{ padding: 14px; border-radius: 14px; }}
      .profile-card img {{ width: 46px; height: 46px; }}
      .verify-btn {{ width: 100%; }}
      .actions {{ display: grid; grid-template-columns: minmax(0, 320px); justify-content: center; }}
      .actions form {{ width: 100%; }}
      .verify-footer {{ justify-content: center; text-align: center; }}
      .verify-footer nav {{ justify-content: center; }}
    }}
  </style>
</head>
<body class="{safe_theme_class}">
  <main class="verify-shell">
    <section class="verify-card hero-card">
      <span class="verify-badge {safe_status_class}"><i class="bi bi-shield-check"></i>{safe_badge}</span>
      <h1 class="verify-title">{safe_title}</h1>
      <p class="verify-subtitle">{safe_subtitle}</p>
      <div class="theme-switch" aria-label="เลือกโทนสี">
        <a class="{theme_cyber_class}" href="{safe_cyber_href}">โทนเขียว-ไซไฟ</a>
        <a class="{theme_gold_class}" href="{safe_gold_href}">โทนทอง-พรีเมียม</a>
      </div>
    </section>

    <section class="verify-card verify-grid">
      <article class="profile-card">
        <img src="{safe_server_icon}" alt="{safe_server_name}">
        <div>
          <strong>{safe_server_name}</strong>
          <span><i class="bi bi-people-fill"></i> Server</span>
        </div>
      </article>
      <article class="profile-card">
        <img src="{safe_user_icon}" alt="{safe_user_name}">
        <div>
          <strong>{safe_user_name}</strong>
          <span><i class="bi bi-person-badge"></i> {safe_user_tag}</span>
        </div>
      </article>
    </section>

    <section class="verify-card">
      <p class="verify-note">{safe_status_note}</p>
      <div class="role-grid">
        <div class="role-box">
          <label><i class="bi bi-plus-circle"></i>ยศที่จะได้รับ</label>
          <select aria-label="roles-add" size="5" disabled>{reward_role_options}</select>
        </div>
        <div class="role-box">
          <label><i class="bi bi-dash-circle"></i>ยศที่จะถูกปลด</label>
          <select aria-label="roles-remove" size="5" disabled>{remove_role_options}</select>
        </div>
      </div>
      <div class="actions">
        <form method="post" action="{safe_verify_action_url}">
          <input type="hidden" name="t" value="{safe_token}">
          <input type="hidden" name="theme" value="{safe_theme_value}">
          <button class="{submit_button_class}" type="submit" {disabled_attr}>
            <i class="{safe_submit_icon}"></i>{safe_submit_label}
          </button>
        </form>
        <a class="verify-btn ghost" href="{safe_back_url}" target="_blank" rel="noopener noreferrer">
          <i class="bi bi-box-arrow-up-right"></i>{safe_back_label}
        </a>
      </div>
    </section>
    <footer class="verify-footer" role="contentinfo">
      <p>{safe_footer_copy}</p>
      <nav aria-label="Footer links">
        <a href="{safe_terms_url}" target="_blank" rel="noopener noreferrer">Terms</a>
        <a href="{safe_privacy_url}" target="_blank" rel="noopener noreferrer">Privacy</a>
        <a href="{safe_support_url}" target="_blank" rel="noopener noreferrer">Support</a>
      </nav>
    </footer>
  </main>
</body>
</html>
"""
    return _apply_public_language_switcher(rendered_html)


def _verify_session_status_payload(
    *,
    settings: dict[str, Any],
    status_key: str,
) -> tuple[str, str, str, str, str]:
    status = str(status_key or "").strip().lower()
    intro = str(settings.get("web_verify_intro") or "กดปุ่มด้านล่างเพื่อยืนยันตัวตนผ่านเว็บ").strip()
    success = str(settings.get("web_verify_success") or "ยืนยันตัวตนสำเร็จแล้ว คุณสามารถกลับไปที่เซิร์ฟเวอร์ได้เลย").strip()
    error = str(settings.get("web_verify_error") or "ไม่สามารถยืนยันตัวตนได้ กรุณาลองใหม่อีกครั้ง").strip()
    if status in {"success", "ok"}:
        return "Verify Success", "is-success", "ยืนยันสำเร็จ", success, "bi bi-check2-circle"
    if status in {"already", "exists"}:
        return "Already Verified", "is-success", "ยืนยันแล้ว", "บัญชีนี้ยืนยันตัวตนไว้แล้ว", "bi bi-person-check"
    if status in {"error", "failed", "invalid"}:
        return "Verify Failed", "is-error", "ไม่สำเร็จ", error, "bi bi-x-circle"
    if status in {"disabled"}:
        return "Verify Disabled", "is-error", "ปิดใช้งาน", "ระบบยืนยันของเซิร์ฟเวอร์นี้ยังไม่เปิดใช้งาน", "bi bi-slash-circle"
    if status in {"not_member"}:
        return "Not in Server", "is-error", "ไม่พบสมาชิก", "ไม่พบสมาชิกนี้ในเซิร์ฟเวอร์ปลายทาง", "bi bi-person-x"
    if status in {"wrong_account"}:
        return "Wrong Account", "is-error", "บัญชีไม่ตรงกัน", "กรุณาเข้าสู่ระบบด้วยบัญชี Discord เดียวกับที่กดปุ่ม Verify ในเซิร์ฟเวอร์", "bi bi-person-lock"
    return "Ready to Verify", "is-pending", "รอยืนยัน", intro, "bi bi-hourglass-split"


async def dashboard_verify_session_page(request: Request):
    token = str(request.query_params.get("t") or request.query_params.get("token") or "").strip()
    theme_variant = _verify_session_theme_variant(str(request.query_params.get("theme") or ""))
    if not token:
        return HTMLResponse(
            _render_verify_session_page_html(
                title="ไม่พบโทเคนยืนยัน",
                subtitle="ไม่พบลิงก์ยืนยันที่ถูกต้อง",
                status_badge="ลิงก์ไม่ถูกต้อง",
                status_class="is-error",
                status_note="กรุณากลับไปกดปุ่ม Verify จาก Discord อีกครั้ง",
                verify_action_url="/dashboard/verify/session",
                token="",
                can_submit=False,
                submit_label="ยืนยันตัวตน",
                submit_icon="bi bi-x-circle",
                back_url="https://discord.com",
                back_label="กลับสู่ Discord",
                server_name="Unknown Server",
                server_icon_url=_verify_session_avatar_fallback(0),
                user_name="Unknown User",
                user_tag="-",
                user_icon_url=_verify_session_avatar_fallback(1),
                reward_role_names=[],
                remove_role_names=[],
                theme_variant=theme_variant,
                status_key="error",
            ),
            status_code=400,
        )

    session = _session_from_request(request)
    session_user_id = int(_session_user_id(session) or 0)
    session_user = dict((session or {}).get("user") or {})

    bot = get_bot()
    verify_cog = bot.get_cog("Verify") if bot else None
    decode_fn = getattr(verify_cog, "decode_web_verify_token", None) if verify_cog else None
    fetch_settings_fn = getattr(verify_cog, "fetch_verify_settings", None) if verify_cog else None
    if not callable(decode_fn) or not callable(fetch_settings_fn):
        return HTMLResponse(
            _render_verify_session_page_html(
                title="บริการยืนยันไม่พร้อมใช้งาน",
                subtitle="ระบบยืนยันยังไม่พร้อมใช้งานในขณะนี้",
                status_badge="Service Offline",
                status_class="is-error",
                status_note="กรุณาลองใหม่อีกครั้งในภายหลัง",
                verify_action_url="/dashboard/verify/session",
                token=token,
                can_submit=False,
                submit_label="ยืนยันตัวตน",
                submit_icon="bi bi-x-circle",
                back_url="https://discord.com",
                back_label="กลับสู่ Discord",
                server_name="Unknown Server",
                server_icon_url=_verify_session_avatar_fallback(0),
                user_name="Unknown User",
                user_tag="-",
                user_icon_url=_verify_session_avatar_fallback(1),
                reward_role_names=[],
                remove_role_names=[],
                theme_variant=theme_variant,
                status_key="error",
            ),
            status_code=503,
        )

    payload = decode_fn(token)
    if not isinstance(payload, dict):
        return HTMLResponse(
            _render_verify_session_page_html(
                title="โทเคนยืนยันหมดอายุ",
                subtitle="ลิงก์ยืนยันหมดอายุหรือไม่ถูกต้อง",
                status_badge="Token Invalid",
                status_class="is-error",
                status_note="กรุณากดปุ่ม Verify ใน Discord ใหม่เพื่อรับลิงก์ล่าสุด",
                verify_action_url="/dashboard/verify/session",
                token=token,
                can_submit=False,
                submit_label="ยืนยันตัวตน",
                submit_icon="bi bi-x-circle",
                back_url="https://discord.com",
                back_label="กลับสู่ Discord",
                server_name="Unknown Server",
                server_icon_url=_verify_session_avatar_fallback(0),
                user_name="Unknown User",
                user_tag="-",
                user_icon_url=_verify_session_avatar_fallback(1),
                reward_role_names=[],
                remove_role_names=[],
                theme_variant=theme_variant,
                status_key="invalid",
            ),
            status_code=400,
        )

    guild_id = int(payload.get("gid") or 0)
    expected_user_id = int(payload.get("uid") or 0)
    if guild_id <= 0 or expected_user_id <= 0:
        return HTMLResponse(
            _render_verify_session_page_html(
                title="ยืนยันตัวตนไม่สำเร็จ",
                subtitle="ลิงก์ยืนยันไม่ถูกต้อง",
                status_badge="ข้อมูลไม่ครบ",
                status_class="is-error",
                status_note="ไม่สามารถอ่านข้อมูลเซิร์ฟเวอร์หรือผู้ใช้จากลิงก์นี้ได้",
                verify_action_url="/dashboard/verify/session",
                token=token,
                can_submit=False,
                submit_label="ยืนยันตัวตน",
                submit_icon="bi bi-x-circle",
                back_url="https://discord.com",
                back_label="กลับสู่ Discord",
                server_name="Unknown Server",
                server_icon_url=_verify_session_avatar_fallback(0),
                user_name="Unknown User",
                user_tag="-",
                user_icon_url=_verify_session_avatar_fallback(1),
                reward_role_names=[],
                remove_role_names=[],
                theme_variant=theme_variant,
                status_key="error",
            ),
            status_code=400,
        )

    forced_status_key = ""
    if session_user_id != expected_user_id:
        if session_user_id <= 0:
            next_path = _verify_session_query_path(token, theme_variant=theme_variant)
            return RedirectResponse(
                url=f"/dashboard/login?{urlencode({'next': next_path})}",
                status_code=303,
            )
        forced_status_key = "wrong_account"

    guild = bot.get_guild(guild_id) if bot else None
    if guild is None:
        return HTMLResponse(
            _render_verify_session_page_html(
                title="ไม่พบเซิร์ฟเวอร์",
                subtitle="ไม่พบเซิร์ฟเวอร์ปลายทางของลิงก์นี้",
                status_badge="ไม่พบเซิร์ฟเวอร์",
                status_class="is-error",
                status_note="บอทอาจไม่ได้อยู่ในเซิร์ฟเวอร์นี้แล้ว หรือเซิร์ฟเวอร์ถูกลบ",
                verify_action_url="/dashboard/verify/session",
                token=token,
                can_submit=False,
                submit_label="ยืนยันตัวตน",
                submit_icon="bi bi-x-circle",
                back_url="https://discord.com",
                back_label="กลับสู่ Discord",
                server_name=f"Server {guild_id}",
                server_icon_url=_verify_session_avatar_fallback(guild_id),
                user_name=str(session_user.get("username") or f"User {expected_user_id}"),
                user_tag=f"ID {expected_user_id}",
                user_icon_url=str(session_user.get("avatar_url") or _verify_session_avatar_fallback(expected_user_id)),
                reward_role_names=[],
                remove_role_names=[],
                theme_variant=theme_variant,
                status_key="error",
            ),
            status_code=404,
        )

    member = guild.get_member(expected_user_id)
    if member is None:
        try:
            member = await guild.fetch_member(expected_user_id)
        except Exception:
            member = None
    if member is None:
        return HTMLResponse(
            _render_verify_session_page_html(
                title="ไม่พบสมาชิก",
                subtitle=f"{str(getattr(guild, 'name', '') or f'Server {guild_id}')} - ยืนยันตัวตนผ่านเว็บ",
                status_badge="ไม่พบสมาชิก",
                status_class="is-error",
                status_note="บัญชีนี้ไม่ได้อยู่ในเซิร์ฟเวอร์เป้าหมาย หรือถูกเตะออกจากเซิร์ฟเวอร์แล้ว",
                verify_action_url="/dashboard/verify/session",
                token=token,
                can_submit=False,
                submit_label="ยืนยันตัวตน",
                submit_icon="bi bi-person-x",
                back_url="https://discord.com/channels/" + str(guild_id),
                back_label="กลับสู่ Server",
                server_name=str(getattr(guild, "name", "") or f"Server {guild_id}"),
                server_icon_url=str(getattr(getattr(guild, "icon", None), "url", "") or _verify_session_avatar_fallback(guild_id)),
                user_name=str(session_user.get("username") or f"User {expected_user_id}"),
                user_tag=f"ID {expected_user_id}",
                user_icon_url=str(session_user.get("avatar_url") or _verify_session_avatar_fallback(expected_user_id)),
                reward_role_names=[],
                remove_role_names=[],
                theme_variant=theme_variant,
                status_key="not_member",
            ),
            status_code=404,
        )

    settings = await fetch_settings_fn(guild_id)
    if not isinstance(settings, dict):
        settings = {}
    settings = dict(settings)

    server_name = str(getattr(guild, "name", "") or f"Server {guild_id}")
    server_icon_url = str(getattr(getattr(guild, "icon", None), "url", "") or _verify_session_avatar_fallback(guild_id))
    user_name = str(getattr(member, "display_name", "") or session_user.get("global_name") or session_user.get("username") or f"User {expected_user_id}")
    username = str(getattr(member, "name", "") or session_user.get("username") or "").strip()
    discriminator = str(session_user.get("discriminator") or "").strip()
    user_tag = f"@{username}" if username else f"ID {expected_user_id}"
    if username and discriminator and discriminator not in {"0", "0000"}:
        user_tag = f"{username}#{discriminator}"
    user_icon_url = str(getattr(getattr(member, "display_avatar", None), "url", "") or session_user.get("avatar_url") or _verify_session_avatar_fallback(expected_user_id))

    reward_role_source = settings.get("web_verify_reward_role_ids")
    if not isinstance(reward_role_source, list):
        reward_role_source = settings.get("reward_role_ids") or []
    reward_role_names: list[str] = []
    for role_id in list(reward_role_source or []):
        role = guild.get_role(int(role_id))
        if role:
            reward_role_names.append(str(getattr(role, "name", "") or int(role_id)))

    remove_role_source = settings.get("web_verify_remove_role_ids")
    if not isinstance(remove_role_source, list):
        remove_role_source = settings.get("remove_role_ids") or []
    remove_role_names: list[str] = []
    for role_id in list(remove_role_source or []):
        role = guild.get_role(int(role_id))
        if role:
            remove_role_names.append(str(getattr(role, "name", "") or int(role_id)))

    status_key = forced_status_key or str(request.query_params.get("status") or "").strip().lower()
    title, status_class, status_badge, status_note, status_icon = _verify_session_status_payload(
        settings=settings,
        status_key=status_key,
    )
    if not settings.get("web_verify_enabled"):
        title, status_class, status_badge, status_note, status_icon = _verify_session_status_payload(
            settings=settings,
            status_key="disabled",
        )

    back_url = _verify_session_back_url(guild_id, settings)
    back_label = str(settings.get("web_back_button_label") or "กลับสู่ Server").strip()[:45] or "กลับสู่ Server"
    submit_label = str(settings.get("web_verify_button_label") or "ยืนยันตัวตนตอนนี้").strip()[:45] or "ยืนยันตัวตนตอนนี้"
    can_submit = bool(settings.get("web_verify_enabled")) and status_key not in {"success", "already", "disabled", "wrong_account", "not_member"}

    return HTMLResponse(
        _render_verify_session_page_html(
            title=f"{title} | {server_name}",
            subtitle=f"{server_name} - ยืนยันตัวตนผ่านเว็บ",
            status_badge=status_badge,
            status_class=status_class,
            status_note=status_note,
            verify_action_url="/dashboard/verify/session",
            token=token,
            can_submit=can_submit,
            submit_label=submit_label,
            submit_icon=status_icon,
            back_url=back_url,
            back_label=back_label,
            server_name=server_name,
            server_icon_url=server_icon_url,
            user_name=user_name,
            user_tag=user_tag,
            user_icon_url=user_icon_url,
            reward_role_names=reward_role_names,
            remove_role_names=remove_role_names,
            theme_variant=theme_variant,
            status_key=status_key,
        )
    )


async def dashboard_verify_session_submit(request: Request):
    form = await request.form()
    token = str(form.get("t") or form.get("token") or "").strip()
    theme_variant = _verify_session_theme_variant(str(form.get("theme") or request.query_params.get("theme") or ""))
    if not token:
        return RedirectResponse(
            url=_verify_session_query_path("", status="error", theme_variant=theme_variant),
            status_code=303,
        )

    session = _session_from_request(request)
    session_user_id = int(_session_user_id(session) or 0)
    query_path = _verify_session_query_path(token, theme_variant=theme_variant)
    if session_user_id <= 0:
        return RedirectResponse(url=f"/dashboard/login?{urlencode({'next': query_path})}", status_code=303)

    bot = get_bot()
    verify_cog = bot.get_cog("Verify") if bot else None
    decode_fn = getattr(verify_cog, "decode_web_verify_token", None) if verify_cog else None
    fetch_settings_fn = getattr(verify_cog, "fetch_verify_settings", None) if verify_cog else None
    apply_fn = getattr(verify_cog, "apply_verification", None) if verify_cog else None
    plan_changes_fn = getattr(verify_cog, "plan_role_changes", None) if verify_cog else None
    if not callable(decode_fn) or not callable(fetch_settings_fn) or not callable(apply_fn):
        return RedirectResponse(url=f"{query_path}&status=error", status_code=303)

    payload = decode_fn(token)
    if not isinstance(payload, dict):
        return RedirectResponse(url=f"{query_path}&status=error", status_code=303)

    guild_id = int(payload.get("gid") or 0)
    expected_user_id = int(payload.get("uid") or 0)
    if expected_user_id <= 0 or guild_id <= 0:
        return RedirectResponse(url=f"{query_path}&status=error", status_code=303)
    if session_user_id != expected_user_id:
        return RedirectResponse(url=f"{query_path}&status=wrong_account", status_code=303)

    guild = bot.get_guild(guild_id) if bot else None
    if guild is None:
        return RedirectResponse(url=f"{query_path}&status=error", status_code=303)
    member = guild.get_member(expected_user_id)
    if member is None:
        try:
            member = await guild.fetch_member(expected_user_id)
        except Exception:
            member = None
    if member is None:
        return RedirectResponse(url=f"{query_path}&status=not_member", status_code=303)

    settings = await fetch_settings_fn(guild_id)
    if not isinstance(settings, dict) or not settings.get("web_verify_enabled"):
        return RedirectResponse(url=f"{query_path}&status=disabled", status_code=303)

    if callable(plan_changes_fn):
        try:
            add_roles, remove_roles = plan_changes_fn(
                member=member,
                guild=guild,
                settings=settings,
                source="web_verify",
            )
            if not add_roles and not remove_roles:
                return RedirectResponse(url=f"{query_path}&status=already", status_code=303)
        except Exception:
            pass

    success = bool(
        await apply_fn(
            member=member,
            guild=guild,
            settings=settings,
            form_values=[],
            actor=member,
            source="web_verify",
        )
    )
    return RedirectResponse(url=f"{query_path}&status={'success' if success else 'error'}", status_code=303)


async def dashboard_privacy_page(request: Request):
    return HTMLResponse(_render_developer_portal_page(request, PUBLIC_PAGE_TEMPLATES["privacy_policy"]))


async def dashboard_privacy_policy_page(request: Request):
    return await dashboard_privacy_page(request)


async def dashboard_terms_page(request: Request):
    context = _build_developer_portal_context(request)
    try:
        plan_pricing_snapshot = await billing_workflow.get_plan_pricing_snapshot()
    except Exception:
        plan_pricing_snapshot = billing_workflow.build_plan_pricing_snapshot_from_settings({})
    tos_plan_tiers = {
        "FREE": "free",
        "SILVER": "silver",
        "GOLE": "golden",
        "DIAMOND": "diamond",
        "PERMANENT": "permanent",
    }
    for key, tier in tos_plan_tiers.items():
        quote = _pricing_quote_from_snapshot(tier, plan_pricing_snapshot)
        context[f"TOS_PRICE_{key}_HTML"] = _price_html_from_quote(quote, period_style="month")
    return HTMLResponse(_render_public_html_template(PUBLIC_PAGE_TEMPLATES["terms_of_service"], context))


async def dashboard_terms_of_service_page(request: Request):
    return await dashboard_terms_page(request)

async def dashboard_bug_bounty_legacy_redirect():
    return RedirectResponse("/report", status_code=303)


async def dashboard_bug_bounty_page(request: Request):
    session = _session_from_request(request)
    return HTMLResponse(
        _render_feature_landing_page(
            title="SkylineBOT โปรแกรมแจ้งช่องโหว่",
            heading="โปรแกรมแจ้งช่องโหว่",
            description="รายงานช่องโหว่สำคัญของ SkylineBOT อย่างมีความรับผิดชอบ",
            highlights=[
                "ส่งรายละเอียดปัญหา ขั้นตอนทำซ้ำ และผลกระทบที่พบให้ครบถ้วน",
                "หลีกเลี่ยงการกระทบข้อมูลผู้ใช้หรือรบกวนเซิร์ฟเวอร์จริงโดยไม่จำเป็น",
                "ทีมงานจะตรวจสอบและตอบกลับผ่านช่องทางติดต่อที่คุณระบุไว้",
            ],
            cta_href="/report",
            cta_label="ส่งรายงานทันที",
            session=session,
        )
    )

def _build_plugins_journey_strip(active_slug: str) -> str:
    cards = [
        {
            "slug": "moderation",
            "title": "Moderation",
            "meta": "Safety Core",
            "description": "Protect channels with AutoMod and staff tools.",
            "href": "/plugins/moderation",
            "icon": "fa-shield-halved",
            "tone": "safety",
        },
        {
            "slug": "utilities",
            "title": "Utilities",
            "meta": "Ops Toolkit",
            "description": "Run embeds, tickets, OCR, and admin helpers.",
            "href": "/plugins/utilities",
            "icon": "fa-screwdriver-wrench",
            "tone": "ops",
        },
        {
            "slug": "social-alerts",
            "title": "Social Alerts",
            "meta": "Live Feed",
            "description": "Mirror creator updates into Discord channels.",
            "href": "/plugins/social-alerts",
            "icon": "fa-bullhorn",
            "tone": "alerts",
        },
        {
            "slug": "games-fun",
            "title": "Games & Fun",
            "meta": "Engagement",
            "description": "Keep members active with game loops and rewards.",
            "href": "/plugins/games-fun",
            "icon": "fa-gamepad",
            "tone": "fun",
        },
    ]
    active_key = str(active_slug or "").strip().lower()
    cards_html_parts: list[str] = []
    for card in cards:
        card_slug = str(card.get("slug") or "").strip().lower()
        is_active = card_slug == active_key
        cards_html_parts.append(
            f"""
            <a class="plugin-journey-link feature-tone-{html.escape(str(card.get('tone') or 'neutral'), quote=True)}{' active' if is_active else ''}" href="{html.escape(str(card.get('href') or ''), quote=True)}">
              <div class="plugin-journey-head">
                <span class="plugin-journey-icon"><i class="fa-solid {html.escape(str(card.get('icon') or ''), quote=True)}" aria-hidden="true"></i></span>
                <div class="plugin-journey-title">
                  <strong>{html.escape(str(card.get('title') or ''), quote=True)}</strong>
                  <span class="plugin-journey-state">{'Current Suite' if is_active else 'Open Suite'}</span>
                </div>
              </div>
              <p class="plugin-journey-description">{html.escape(str(card.get('description') or ''), quote=True)}</p>
              <div class="plugin-journey-foot">
                <span class="plugin-journey-meta">{html.escape(str(card.get('meta') or ''), quote=True)}</span>
                <span class="plugin-journey-cta">{'Viewing now' if is_active else 'Switch view'}</span>
              </div>
            </a>
            """
        )
    cards_html = "".join(cards_html_parts)
    return f"""
      <section class="panel feature-landing-shell plugin-journey-strip">
        <div class="plugin-journey-intro">
          <p class="plugin-journey-kicker">Plugin Navigator</p>
          <h2>Explore Plugin Categories</h2>
          <p class="muted">Move between safety, utility, alerting, and engagement suites without losing your rollout context.</p>
        </div>
        <div class="plugin-journey-grid">
          {cards_html}
        </div>
      </section>
    """


async def dashboard_plugins_moderation_page(request: Request):
    session = _session_from_request(request)
    plugin_journey_html = _build_plugins_journey_strip("moderation")
    add_on_tools = [
        {
            "name": "Utilities Toolkit",
            "description": "Use helper modules like embeds, temp channels, OCR scanner, and server stats.",
            "href": "/plugins/utilities",
            "cta": "Explore Utilities",
            "tag": "Add-on",
            "icon": "fa-screwdriver-wrench",
        },
        {
            "name": "Social Alerts",
            "description": "Receive Twitch, YouTube, TikTok, GitHub, and Facebook updates in Discord.",
            "href": "/plugins/social-alerts",
            "cta": "View Social Alerts",
            "tag": "Notifications",
            "icon": "fa-bullhorn",
        },
        {
            "name": "Games and Fun",
            "description": "Boost engagement with levels, giveaways, and activity loops after moderation setup.",
            "href": "/plugins/games-fun",
            "cta": "Open Games and Fun",
            "tag": "Engagement",
            "icon": "fa-gamepad",
        },
        {
            "name": "Command Directory",
            "description": "Review command syntax and moderation command variants for your staff team.",
            "href": "/commands",
            "cta": "Open Command List",
            "tag": "Reference",
            "icon": "fa-book-open",
        },
    ]
    add_on_cards_html = "".join(
        f"""
        <article class="feature-tool-card">
          <div class="feature-tool-head">
            <span class="feature-tool-icon"><i class="fa-solid {html.escape(str(item.get("icon") or "fa-puzzle-piece"), quote=True)}" aria-hidden="true"></i></span>
            <h3>{html.escape(str(item.get("name") or ""), quote=True)}</h3>
          </div>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
          <div class="feature-landing-link-row">
            <a class="ghost-btn" href="{html.escape(str(item.get("href") or ""), quote=True)}">{html.escape(str(item.get("cta") or ""), quote=True)}</a>
            <span class="feature-landing-badge">{html.escape(str(item.get("tag") or ""), quote=True)}</span>
          </div>
        </article>
        """
        for item in add_on_tools
    )

    quick_steps = [
        {
            "title": "Set your protection baseline",
            "description": "Enable AutoMod modules and set anti-spam thresholds for your server traffic profile.",
            "icon": "fa-sliders",
        },
        {
            "title": "Define manual response flow",
            "description": "Prepare staff shortcuts for delete, mute, kick, ban, lock, and role actions.",
            "icon": "fa-bolt",
        },
        {
            "title": "Connect supporting modules",
            "description": "Pair moderation with utilities and alerts so incidents are easier to trace and resolve.",
            "icon": "fa-link",
        },
    ]
    step_cards_html = "".join(
        f"""
        <article class="feature-step-card">
          <div class="feature-step-head">
            <span class="feature-step-index">{index}</span>
            <span class="feature-step-icon"><i class="fa-solid {html.escape(str(item.get("icon") or "fa-check"), quote=True)}" aria-hidden="true"></i></span>
          </div>
          <h3>{html.escape(str(item.get("title") or ""), quote=True)}</h3>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
        </article>
        """
        for index, item in enumerate(quick_steps, start=1)
    )

    command_samples = [
        "/mod delete",
        "/mod ban",
        "/mod kick",
        "/mod lock",
        "/mod unlock",
        "/purge",
        "/mute",
        "/role",
        "/mod checkperms",
    ]
    command_chip_html = "".join(
        f"<code>{html.escape(command, quote=True)}</code>"
        for command in command_samples
    )

    moderation_preview_image = "/dashboard/static/image_web_bot/moderation_banner.webp"
    moderation_preview_fallback = "/dashboard/static/image_web_bot/moderation_bot_safe_community.webp"
    extra_sections_html = f"""
      {plugin_journey_html}
      <section class="panel feature-landing-shell">
        <h2>Add-on Tools in SkylineBOT</h2>
        <p class="muted">Extend your moderation workflow with supporting modules across the bot ecosystem.</p>
        <div class="feature-landing-tool-grid">
          {add_on_cards_html}
        </div>
      </section>
      <section class="panel feature-landing-shell">
        <h2>Suggested Rollout</h2>
        <p class="muted">Start with core protection, then layer staff automation and monitoring.</p>
        <div class="feature-landing-step-grid">
          {step_cards_html}
        </div>
        <div class="feature-landing-command-strip">
          {command_chip_html}
        </div>
        <div class="feature-landing-preview-strip">
          <img src="{html.escape(moderation_preview_image, quote=True)}" onerror="this.onerror=null;this.src='{html.escape(moderation_preview_fallback, quote=True)}';" alt="SkylineBOT moderation preview">
          <div class="feature-landing-preview-copy">
            <h3>Built for fast incident response</h3>
            <p>Combine automated filters, one-click staff commands, and plugin add-ons to keep your server clean and predictable.</p>
            <div class="feature-landing-link-row">
              <a class="primary-btn" href="/dashboard">Open Dashboard</a>
              <a class="ghost-btn" href="/report">Report Issue</a>
            </div>
          </div>
        </div>
      </section>
    """

    return HTMLResponse(
        _render_feature_landing_page(
            title="ระบบดูแลและความปลอดภัย SkylineBOT",
            heading="Moderation Command Center",
            description="ตั้งค่าระบบป้องกันอัตโนมัติ การจัดการทีมงาน และโมดูลเสริมที่เกี่ยวข้องได้จากจุดเดียว",
            highlights=[
                "AutoMod modules: Anti-Link, Anti-Spam, and blocked keyword filters with tunable thresholds.",
                "Punishment flow: choose mute, kick, or ban paths based on risk level and server plan.",
                "Cleanup toolkit: /delete and /purge commands cover messages, links, emojis, embeds, bots, and specific users.",
                "Channel containment: lock, unlock, hide, and unhide individual channels or all channels during incidents.",
                "Role and member controls: run /role, /mute, /unmute, /ban, /kick, and /unban workflows quickly.",
                "Operational check: use /mod checkperms to verify missing permissions before taking action.",
            ],
            cta_href="/dashboard",
            cta_label="Open Dashboard",
            theme_key="plugins-moderation",
            hero_image_url=str(style_urls.PLUGIN_CATALOG_MODERATION_IMAGE or "").strip() or "/dashboard/static/image_web_bot/moderation_bot_safe_community.webp",
            hero_image_fallback_url="/dashboard/static/image_web_bot/moderation_bot_safe_community.webp",
            hero_badges=[
                "AutoMod ready",
                "Manual command suite",
                "Incident response flow",
            ],
            hero_metrics=[
                ("3", "AutoMod modules"),
                ("8", "Delete modes"),
                ("10+", "Staff commands"),
                ("24/7", "Safety coverage"),
            ],
            overview_heading="Core Moderation Toolkit",
            overview_description="Everything needed to prevent spam, react faster, and keep staff operations consistent.",
            extra_sections_html=extra_sections_html,
            session=session,
        )
    )


async def dashboard_plugins_utilities_page(request: Request):
    session = _session_from_request(request)
    plugin_journey_html = _build_plugins_journey_strip("utilities")
    utility_modules = [
        {
            "name": "Embed and Announcement Tools",
            "description": "Design rich posts with `/embed` and publish scheduled copy with `/say` for cleaner announcements.",
            "command": "/embed",
            "tag": "Formatting",
            "icon": "fa-pen-ruler",
        },
        {
            "name": "Ticket and Poll Workflow",
            "description": "Run support queues and server voting in one place with `ticket` and `poll` command groups.",
            "command": "/ticket",
            "tag": "Operations",
            "icon": "fa-ticket",
        },
        {
            "name": "Reminder and Translation",
            "description": "Use `reminder` commands and `/translate` to keep multilingual communities aligned.",
            "command": "/reminder",
            "tag": "Productivity",
            "icon": "fa-language",
        },
        {
            "name": "OCR and Visual Utilities",
            "description": "Scan image text and moderation clues with the `ocr` group and image checking controls.",
            "command": "/ocr setup",
            "tag": "AI Helper",
            "icon": "fa-eye",
        },
        {
            "name": "Identity and Access Panels",
            "description": "Publish verify, reaction role, and server stats panels from Discord without leaving chat.",
            "command": "/verify publish",
            "tag": "Automation",
            "icon": "fa-id-card",
        },
        {
            "name": "Server Insight Commands",
            "description": "Use `/userinfo`, `/serverinfo`, `/membercount`, and `/id` for fast lookup during admin work.",
            "command": "/serverinfo",
            "tag": "Lookup",
            "icon": "fa-chart-column",
        },
    ]
    module_cards_html = "".join(
        f"""
        <article class="feature-tool-card">
          <div class="feature-tool-head">
            <span class="feature-tool-icon"><i class="fa-solid {html.escape(str(item.get("icon") or "fa-puzzle-piece"), quote=True)}" aria-hidden="true"></i></span>
            <h3>{html.escape(str(item.get("name") or ""), quote=True)}</h3>
          </div>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
          <div class="feature-landing-link-row">
            <code>{html.escape(str(item.get("command") or ""), quote=True)}</code>
            <span class="feature-landing-badge">{html.escape(str(item.get("tag") or ""), quote=True)}</span>
          </div>
        </article>
        """
        for item in utility_modules
    )

    utility_steps = [
        {
            "title": "Create base communication blocks",
            "description": "Start with `/embed`, `/poll`, and `/ticket` so your members have clear interaction points.",
            "icon": "fa-comment-dots",
        },
        {
            "title": "Add admin automation",
            "description": "Publish `/verify`, `/reaction_roles`, and `/serverstats` panels for repeatable server flow.",
            "icon": "fa-gears",
        },
        {
            "title": "Enable daily helper commands",
            "description": "Use `/translate`, `/reminder`, `/userinfo`, and `/serverinfo` as your day-to-day utility kit.",
            "icon": "fa-clock",
        },
    ]
    utility_step_html = "".join(
        f"""
        <article class="feature-step-card">
          <div class="feature-step-head">
            <span class="feature-step-index">{index}</span>
            <span class="feature-step-icon"><i class="fa-solid {html.escape(str(item.get("icon") or "fa-check"), quote=True)}" aria-hidden="true"></i></span>
          </div>
          <h3>{html.escape(str(item.get("title") or ""), quote=True)}</h3>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
        </article>
        """
        for index, item in enumerate(utility_steps, start=1)
    )

    utility_command_samples = [
        "/embed",
        "/poll",
        "/ticket",
        "/reminder",
        "/translate",
        "/ocr setup",
        "/verify publish",
        "/reaction_roles publish",
        "/serverstats setup",
    ]
    utility_command_chip_html = "".join(
        f"<code>{html.escape(command, quote=True)}</code>"
        for command in utility_command_samples
    )

    utilities_preview_image = str(style_urls.PLUGIN_CATALOG_UTILITIES_IMAGE or "").strip() or "/dashboard/static/image_web_bot/ticket_bot_support_system.webp"
    utilities_preview_fallback = "/dashboard/static/image_web_bot/ticket_bot_support_system.webp"
    extra_sections_html = f"""
      {plugin_journey_html}
      <section class="panel feature-landing-shell">
        <h2>Utility Stack</h2>
        <p class="muted">A practical toolbox for announcements, helper automation, and server administration.</p>
        <div class="feature-landing-tool-grid">
          {module_cards_html}
        </div>
      </section>
      <section class="panel feature-landing-shell">
        <h2>Recommended Setup Flow</h2>
        <p class="muted">Start simple, then scale into automated panels and daily moderation helper commands.</p>
        <div class="feature-landing-step-grid">
          {utility_step_html}
        </div>
        <div class="feature-landing-command-strip">
          {utility_command_chip_html}
        </div>
        <div class="feature-landing-preview-strip">
          <img src="{html.escape(utilities_preview_image, quote=True)}" onerror="this.onerror=null;this.src='{html.escape(utilities_preview_fallback, quote=True)}';" alt="SkylineBOT utilities preview">
          <div class="feature-landing-preview-copy">
            <h3>Built for everyday admin tasks</h3>
            <p>Replace scattered bots with one focused utility hub: embed tools, ticket flow, OCR checks, and panel publishing.</p>
            <div class="feature-landing-link-row">
              <a class="primary-btn" href="/dashboard">Open Dashboard</a>
              <a class="ghost-btn" href="/commands">Browse Commands</a>
            </div>
          </div>
        </div>
      </section>
    """

    return HTMLResponse(
        _render_feature_landing_page(
            title="ชุดเครื่องมือยูทิลิตี้ SkylineBOT",
            heading="Utilities and Daily Admin Tools",
            description="ศูนย์รวมเครื่องมือสำหรับงานดูแลประจำวัน การสื่อสาร และอัตโนมัติผู้ช่วยในเซิร์ฟเวอร์ของคุณ",
            highlights=[
                "Announcement flow with `/embed` and `/say` to keep important updates readable and branded.",
                "Support operations via `ticket` and `poll` command groups for queue and decision workflows.",
                "Translation and reminder helpers for multilingual communities and recurring announcements.",
                "Image moderation assist with `ocr` setup, keyword matching, and private image checking.",
                "Verification and role automation through `/verify`, `/reaction_roles`, and `/serverstats`.",
                "Core lookup commands (`/userinfo`, `/serverinfo`, `/membercount`, `/id`) for fast admin response.",
            ],
            cta_href="/dashboard",
            cta_label="Open Dashboard",
            theme_key="plugins-utilities",
            hero_image_url=str(style_urls.PLUGIN_CATALOG_UTILITIES_IMAGE or "").strip() or "/dashboard/static/image_web_bot/ticket_bot_support_system.webp",
            hero_image_fallback_url="/dashboard/static/image_web_bot/ticket_bot_support_system.webp",
            hero_badges=[
                "Embed + Poll + Ticket",
                "OCR + Verify + Roles",
                "Daily admin workflows",
            ],
            hero_metrics=[
                ("12+", "Utility commands"),
                ("5", "Automation panels"),
                ("3", "Lookup toolsets"),
                ("24/7", "Operational support"),
            ],
            overview_heading="What You Can Run From Utilities",
            overview_description="Focused tools for server operations, support delivery, and communication quality.",
            extra_sections_html=extra_sections_html,
            session=session,
        )
    )


async def dashboard_plugins_social_alerts_page(request: Request):
    session = _session_from_request(request)
    plugin_journey_html = _build_plugins_journey_strip("social-alerts")
    social_platforms = [
        {
            "name": "YouTube Alerts",
            "description": "Track uploads and live sessions from channels and notify members instantly.",
            "command": "/alerts add youtube <channel_url>",
            "icon": "fa-play",
        },
        {
            "name": "Twitch Alerts",
            "description": "Detect stream and video activity for creators you manage in Discord.",
            "command": "/alerts add twitch <channel_url>",
            "icon": "fa-video",
        },
        {
            "name": "TikTok Alerts",
            "description": "Watch creator activity and push latest TikTok updates to selected channels.",
            "command": "/alerts add tiktok <profile_url>",
            "icon": "fa-music",
        },
        {
            "name": "GitHub Alerts",
            "description": "Follow repository events for dev communities and release-centric servers.",
            "command": "/alerts add github <repo_url>",
            "icon": "fa-code-branch",
        },
        {
            "name": "Facebook Alerts",
            "description": "Mirror page updates and live content into Discord announcement channels.",
            "command": "/alerts add facebook <page_url>",
            "icon": "fa-users",
        },
    ]
    social_cards_html = "".join(
        f"""
        <article class="feature-tool-card">
          <div class="feature-tool-head">
            <span class="feature-tool-icon"><i class="fa-solid {html.escape(str(item.get('icon') or 'fa-bullhorn'), quote=True)}" aria-hidden="true"></i></span>
            <h3>{html.escape(str(item.get("name") or ""), quote=True)}</h3>
          </div>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
          <div class="feature-landing-link-row">
            <code>{html.escape(str(item.get("command") or ""), quote=True)}</code>
            <span class="feature-landing-badge">Platform</span>
          </div>
        </article>
        """
        for item in social_platforms
    )

    social_steps = [
        {
            "title": "Configure the base channel",
            "description": "Set one default notify destination using `/alerts channel` before adding sources.",
            "icon": "fa-hashtag",
        },
        {
            "title": "Enable selected platforms",
            "description": "Toggle platforms with `/alerts toggle` so each feed only posts where needed.",
            "icon": "fa-toggle-on",
        },
        {
            "title": "Add and curate source URLs",
            "description": "Use `/alerts add`, `/alerts list`, and `/alerts remove` to keep feeds clean.",
            "icon": "fa-filter",
        },
    ]
    social_step_html = "".join(
        f"""
        <article class="feature-step-card">
          <div class="feature-step-head">
            <span class="feature-step-index">{index}</span>
            <span class="feature-step-icon"><i class="fa-solid {html.escape(str(item.get('icon') or 'fa-check'), quote=True)}" aria-hidden="true"></i></span>
          </div>
          <h3>{html.escape(str(item.get("title") or ""), quote=True)}</h3>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
        </article>
        """
        for index, item in enumerate(social_steps, start=1)
    )

    social_command_samples = [
        "/alerts status",
        "/alerts enable on",
        "/alerts channel #announcements",
        "/alerts toggle youtube on",
        "/alerts add youtube <channel_url>",
        "/alerts list youtube",
        "/alerts remove youtube <channel_url>",
    ]
    social_command_chip_html = "".join(
        f"<code>{html.escape(command, quote=True)}</code>"
        for command in social_command_samples
    )

    social_preview_image = str(style_urls.PLUGIN_CATALOG_SOCIAL_ALERTS_IMAGE or "").strip() or "/dashboard/static/image_web_bot/alerts_hub_multi_platform.webp"
    social_preview_fallback = "/dashboard/static/image_web_bot/alerts_hub_multi_platform.webp"
    extra_sections_html = f"""
      {plugin_journey_html}
      <section class="panel feature-landing-shell">
        <h2>Supported Alert Platforms</h2>
        <p class="muted">Social Alerts currently supports YouTube, Twitch, TikTok, GitHub, and Facebook feeds.</p>
        <div class="feature-landing-tool-grid">
          {social_cards_html}
        </div>
      </section>
      <section class="panel feature-landing-shell">
        <h2>Deployment Checklist</h2>
        <p class="muted">Turn on only what your members care about, then route feeds to dedicated channels.</p>
        <div class="feature-landing-step-grid">
          {social_step_html}
        </div>
        <div class="feature-landing-command-strip">
          {social_command_chip_html}
        </div>
        <div class="feature-landing-preview-strip">
          <img src="{html.escape(social_preview_image, quote=True)}" onerror="this.onerror=null;this.src='{html.escape(social_preview_fallback, quote=True)}';" alt="SkylineBOT social alerts preview">
          <div class="feature-landing-preview-copy">
            <h3>One feed hub, multiple platforms</h3>
            <p>Keep your Discord updated without manual reposting. Route creator, repo, and stream activity to the right audience automatically.</p>
            <div class="feature-landing-link-row">
              <a class="primary-btn" href="/dashboard">Open Dashboard</a>
              <a class="ghost-btn" href="/commands">View Commands</a>
            </div>
          </div>
        </div>
      </section>
    """

    return HTMLResponse(
        _render_feature_landing_page(
            title="ระบบแจ้งเตือนโซเชียล SkylineBOT",
            heading="Social and Creator Notification Hub",
            description="ส่งอัปเดตข้ามแพลตฟอร์มเข้า Discord ได้ทันที พร้อมตั้งค่าช่องทาง สวิตช์แพลตฟอร์ม และแหล่งที่มาได้ยืดหยุ่น",
            highlights=[
                "Global switch with `/alerts enable` and detailed platform controls via `/alerts toggle`.",
                "Separate source lists per platform with add, remove, and list commands.",
                "Dedicated default channel plus per-entry channel overrides for targeted delivery.",
                "Built-in cooldown support to keep notifications readable during high activity periods.",
                "Works for creator communities, esports teams, coding guilds, and announcement servers.",
                "Fast issue triage using `/alerts status` to inspect enabled state and feed counts.",
            ],
            cta_href="/dashboard",
            cta_label="Open Dashboard",
            theme_key="plugins-social-alerts",
            hero_image_url=str(style_urls.PLUGIN_CATALOG_SOCIAL_ALERTS_IMAGE or "").strip() or "/dashboard/static/image_web_bot/alerts_hub_multi_platform.webp",
            hero_image_fallback_url="/dashboard/static/image_web_bot/alerts_hub_multi_platform.webp",
            hero_badges=[
                "YouTube + Twitch + TikTok",
                "GitHub + Facebook",
                "Per-channel routing",
            ],
            hero_metrics=[
                ("5", "Supported platforms"),
                ("60", "Max entries per platform"),
                ("1", "Default notify channel"),
                ("24/7", "Background polling"),
            ],
            overview_heading="How Social Alerts Helps",
            overview_description="Keep members informed without manual reposting and keep each channel relevant to its audience.",
            extra_sections_html=extra_sections_html,
            session=session,
        )
    )


async def dashboard_plugins_games_fun_page(request: Request):
    session = _session_from_request(request)
    plugin_journey_html = _build_plugins_journey_strip("games-fun")
    fun_modes = [
        {
            "name": "Mini Games",
            "description": "Run `/slots`, `/coinflip`, `/dice`, `/rps`, `/xo`, and `/chess` for instant interaction.",
            "command": "/slots",
            "tag": "Quick Play",
            "icon": "fa-dice",
        },
        {
            "name": "Quiz and Guess Cycles",
            "description": "Start rotating challenge loops with quiz, guessing, number, and word-chain command sets.",
            "command": "/quizstart",
            "tag": "Event Loop",
            "icon": "fa-brain",
        },
        {
            "name": "Giveaway Engine",
            "description": "Launch and manage giveaways with start, reroll, list, and end utilities.",
            "command": "/gstart",
            "tag": "Rewards",
            "icon": "fa-gift",
        },
        {
            "name": "Level and Rank Progression",
            "description": "Use the `level` group to reward consistent participation and leaderboard activity.",
            "command": "/level",
            "tag": "Progression",
            "icon": "fa-trophy",
        },
        {
            "name": "Economy Interaction",
            "description": "Daily actions like `/work`, `/crime`, and `/rob` keep members checking in.",
            "command": "/economy",
            "tag": "Retention",
            "icon": "fa-coins",
        },
        {
            "name": "Community Rituals",
            "description": "Use `birthday`, `funroom`, and profile-style commands for social identity and culture.",
            "command": "/birthday",
            "tag": "Community",
            "icon": "fa-cake-candles",
        },
    ]
    fun_cards_html = "".join(
        f"""
        <article class="feature-tool-card">
          <div class="feature-tool-head">
            <span class="feature-tool-icon"><i class="fa-solid {html.escape(str(item.get("icon") or "fa-puzzle-piece"), quote=True)}" aria-hidden="true"></i></span>
            <h3>{html.escape(str(item.get("name") or ""), quote=True)}</h3>
          </div>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
          <div class="feature-landing-link-row">
            <code>{html.escape(str(item.get("command") or ""), quote=True)}</code>
            <span class="feature-landing-badge">{html.escape(str(item.get("tag") or ""), quote=True)}</span>
          </div>
        </article>
        """
        for item in fun_modes
    )

    fun_steps = [
        {
            "title": "Activate quick engagement",
            "description": "Start with mini-games and quiz loops to create immediate activity spikes.",
            "icon": "fa-fire",
        },
        {
            "title": "Layer progression systems",
            "description": "Enable level, economy, and giveaway commands for long-term retention incentives.",
            "icon": "fa-layer-group",
        },
        {
            "title": "Create social rituals",
            "description": "Use birthday and funroom activities to make your server feel alive every day.",
            "icon": "fa-heart",
        },
    ]
    fun_step_html = "".join(
        f"""
        <article class="feature-step-card">
          <div class="feature-step-head">
            <span class="feature-step-index">{index}</span>
            <span class="feature-step-icon"><i class="fa-solid {html.escape(str(item.get('icon') or 'fa-check'), quote=True)}" aria-hidden="true"></i></span>
          </div>
          <h3>{html.escape(str(item.get("title") or ""), quote=True)}</h3>
          <p>{html.escape(str(item.get("description") or ""), quote=True)}</p>
        </article>
        """
        for index, item in enumerate(fun_steps, start=1)
    )

    fun_command_samples = [
        "/slots",
        "/coinflip",
        "/dice",
        "/rps",
        "/quizstart",
        "/gstart",
        "/level",
        "/economy",
        "/work",
        "/birthday",
    ]
    fun_command_chip_html = "".join(
        f"<code>{html.escape(command, quote=True)}</code>"
        for command in fun_command_samples
    )

    fun_preview_image = str(style_urls.PLUGIN_CATALOG_FUN_IMAGE or "").strip() or "/dashboard/static/image_web_bot/music_banner_discord_bot.webp"
    fun_preview_fallback = "/dashboard/static/image_web_bot/music_banner_discord_bot.webp"
    extra_sections_html = f"""
      {plugin_journey_html}
      <section class="panel feature-landing-shell">
        <h2>Engagement Modules</h2>
        <p class="muted">Blend mini games, progression systems, and reward loops for stronger community retention.</p>
        <div class="feature-landing-tool-grid">
          {fun_cards_html}
        </div>
      </section>
      <section class="panel feature-landing-shell">
        <h2>Rollout Plan for Activity Growth</h2>
        <p class="muted">Launch lightweight games first, then add progression and seasonal reward mechanics.</p>
        <div class="feature-landing-step-grid">
          {fun_step_html}
        </div>
        <div class="feature-landing-command-strip">
          {fun_command_chip_html}
        </div>
        <div class="feature-landing-preview-strip">
          <img src="{html.escape(fun_preview_image, quote=True)}" onerror="this.onerror=null;this.src='{html.escape(fun_preview_fallback, quote=True)}';" alt="SkylineBOT games and fun preview">
          <div class="feature-landing-preview-copy">
            <h3>Make activity feel rewarding</h3>
            <p>Combine games, leaderboard progress, and giveaways so members always have a reason to participate.</p>
            <div class="feature-landing-link-row">
              <a class="primary-btn" href="/dashboard">Open Dashboard</a>
              <a class="ghost-btn" href="/commands">Browse Commands</a>
            </div>
          </div>
        </div>
      </section>
    """

    return HTMLResponse(
        _render_feature_landing_page(
            title="เกมและความสนุก SkylineBOT",
            heading="Games, Rewards, and Community Engagement",
            description="เปลี่ยนเซิร์ฟเวอร์ให้คึกคักด้วยมินิเกม ระบบความก้าวหน้า และกิจกรรมรางวัลแบบต่อเนื่อง",
            highlights=[
                "Mini-games include slots, coinflip, dice, RPS, XO, chess, and multiple guess/quiz loops.",
                "Giveaway tools support campaign start, end, list, reroll, and role-gated participation.",
                "Level and economy commands create repeatable daily interaction and user progression.",
                "Birthday and funroom systems help build social rituals and regular member return behavior.",
                "Retention improves when games, rewards, and identity commands are combined strategically.",
                "Use command rotation by day/week to keep engagement fresh without extra moderators.",
            ],
            cta_href="/dashboard",
            cta_label="Open Dashboard",
            theme_key="plugins-games-fun",
            hero_image_url=str(style_urls.PLUGIN_CATALOG_FUN_IMAGE or "").strip() or "/dashboard/static/image_web_bot/music_banner_discord_bot.webp",
            hero_image_fallback_url="/dashboard/static/image_web_bot/music_banner_discord_bot.webp",
            hero_badges=[
                "Mini-game command pack",
                "Levels + Economy + Giveaways",
                "Daily community rituals",
            ],
            hero_metrics=[
                ("20+", "Fun commands"),
                ("6", "Engagement modules"),
                ("3", "Progression systems"),
                ("24/7", "Activity loop"),
            ],
            overview_heading="Community Engagement Core",
            overview_description="A full set of interactive commands designed to improve retention and participation.",
            extra_sections_html=extra_sections_html,
            session=session,
        )
    )

async def _report_parse_post_form(request: Request) -> tuple[dict[str, str], Any, str]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
        except AssertionError:
            return {}, None, "เซิร์ฟเวอร์ยังไม่รองรับอัปโหลดไฟล์ กรุณาติดตั้ง python-multipart แล้วรีสตาร์ต"
        data: dict[str, str] = {}
        upload = None
        for key, value in form.items():
            if hasattr(value, "filename"):
                if key == "image":
                    upload = value
                continue
            data[key] = str(value)
        return data, upload, ""
    return await _parse_form(request), None, ""


async def _report_read_image(upload_obj: Any) -> tuple[bytes | None, str, str, int, str]:
    if upload_obj is None or not getattr(upload_obj, "filename", None):
        return None, "", "", 0, ""
    filename = str(getattr(upload_obj, "filename", "") or "").strip()
    if not filename:
        return None, "", "", 0, ""

    payload = await upload_obj.read()
    if not payload:
        return None, filename, "", 0, "ไม่พบข้อมูลรูปที่อัปโหลด"

    size = int(len(payload))
    if size > REPORT_MAX_IMAGE_BYTES:
        return None, filename, "", 0, f"รูปมีขนาดเกินกำหนด ({REPORT_MAX_IMAGE_BYTES // (1024 * 1024)}MB)"

    content_type = str(getattr(upload_obj, "content_type", "") or "").strip().lower()
    if content_type and not content_type.startswith("image/"):
        return None, filename, content_type, size, "ไฟล์ที่แนบต้องเป็นรูปภาพเท่านั้น"

    safe_name = filename.replace("\\", "_").replace("/", "_").replace("..", "_").strip()[:120]
    if not safe_name:
        safe_name = "report-image.png"

    allowed_ext = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")
    if not any(safe_name.lower().endswith(ext) for ext in allowed_ext):
        if content_type.startswith("image/"):
            safe_name = f"{safe_name}.png"
        else:
            return None, safe_name, content_type, size, "รองรับเฉพาะไฟล์ภาพ PNG, JPG, WEBP, GIF, BMP, SVG"

    return bytes(payload), safe_name, content_type, size, ""


async def dashboard_report_page(request: Request, notice: str | None = None):
    session = _session_from_request(request)
    return HTMLResponse(_render_report_page(notice=notice, session=session))


async def dashboard_report_submit(request: Request):
    session = _session_from_request(request)
    session_user = dict((session or {}).get("user") or {})
    session_user_id = str(session_user.get("id") or "").strip()
    session_username = str(session_user.get("username") or "").strip()
    session_global_name = str(session_user.get("global_name") or "").strip()
    session_discriminator = str(session_user.get("discriminator") or "").strip()
    session_user_display = session_global_name or session_username or "-"
    if session_username:
        if session_discriminator and session_discriminator not in {"0", "0000"}:
            session_user_tag = f"{session_username}#{session_discriminator}"
        else:
            session_user_tag = f"@{session_username}"
    else:
        session_user_tag = "-"

    form, upload_image, parse_error = await _report_parse_post_form(request)
    title = _clean_text(form.get("title"))
    contact = _clean_text(form.get("contact"))
    detail = _clean_text(form.get("detail"))
    related_guild_id = _clean_text(form.get("related_guild_id"))
    challenge_id = form.get("challenge_id", "")
    answer = form.get("challenge_answer", "")
    client_ip = getattr(getattr(request, "client", None), "host", "unknown") or "unknown"
    form_prefill = {
        "title": title,
        "contact": contact,
        "detail": detail,
        "related_guild_id": related_guild_id,
        "challenge_answer": answer,
    }

    if parse_error:
        return HTMLResponse(
            _render_report_page(
                notice=parse_error,
                session=session,
                form_prefill=form_prefill,
            ),
            status_code=400,
        )

    report_image_payload, report_image_name, report_image_mime, report_image_size, report_image_error = await _report_read_image(upload_image)
    if report_image_name:
        form_prefill["image_name"] = report_image_name
    if report_image_error:
        return HTMLResponse(
            _render_report_page(
                notice=report_image_error,
                session=session,
                form_prefill=form_prefill,
            ),
            status_code=400,
        )

    related_guild_name = ""
    related_guild_map: dict[str, str] = {}
    if session_user_id:
        try:
            manageable_guild_rows = await _manageable_guilds_live(session or {})
        except Exception:
            manageable_guild_rows = []
        for row in list(manageable_guild_rows or []):
            guild_id = str(row.get("id") or "").strip()
            guild_name = str(row.get("name") or guild_id).strip() or guild_id
            if guild_id:
                related_guild_map[guild_id] = guild_name
        if related_guild_id and related_guild_id not in related_guild_map:
            return HTMLResponse(
                _render_report_page(
                    notice="The selected server is invalid or you do not have access to it.",
                    session=session,
                    form_prefill=form_prefill,
                ),
                status_code=400,
            )
        related_guild_name = related_guild_map.get(related_guild_id, "")
    else:
        related_guild_id = ""
        form_prefill["related_guild_id"] = ""

    limited, retry_after = _report_rate_limited(client_ip)
    if limited:
        return HTMLResponse(
            _render_report_page(
                notice=f"Too many reports in a short time. Please wait about {retry_after} seconds and try again.",
                session=session,
                form_prefill=form_prefill,
            ),
            status_code=429,
        )

    if not title or not contact or not detail:
        return HTMLResponse(
            _render_report_page(
                notice="Please fill in title, contact channel, and detail before submitting.",
                session=session,
                form_prefill=form_prefill,
            ),
            status_code=400,
        )
    if not session_user_id and not _validate_report_challenge(challenge_id, answer):
        return HTMLResponse(
            _render_report_page(
                notice="Anti-bot challenge is invalid or expired.",
                session=session,
                form_prefill=form_prefill,
            ),
            status_code=400,
        )

    bot = get_bot()
    report_channel_id = _report_channel_id_from_runtime(bot)
    report_channel = bot.get_channel(report_channel_id) if bot and report_channel_id else None

    if isinstance(report_channel, discord.abc.Messageable):
        embed = discord.Embed(
            title="รายงานจากเว็บไซต์",
            description=detail,
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        embed.add_field(name="Title", value=title[:1024], inline=False)
        embed.add_field(name="Contact", value=contact[:1024], inline=False)
        embed.add_field(name="Reporter IP", value=client_ip[:1024], inline=False)

        related_server_value = "Not specified"
        if related_guild_id:
            if related_guild_name:
                related_server_value = f"{related_guild_name}\nID: {related_guild_id}"
            else:
                related_server_value = f"ID: {related_guild_id}"
        embed.add_field(name="Related Server", value=related_server_value[:1024], inline=False)

        if session_user_id:
            embed.add_field(
                name="Logged-in Reporter",
                value=f"{session_user_display} ({session_user_tag})\nID: {session_user_id}",
                inline=False,
            )

        report_file = None
        if report_image_payload is not None and report_image_name:
            try:
                report_file = discord.File(io.BytesIO(report_image_payload), filename=report_image_name)
                embed.set_image(url=f"attachment://{report_image_name}")
                embed.add_field(
                    name="Attachment",
                    value=f"{report_image_name} ({report_image_size:,} bytes)",
                    inline=False,
                )
            except Exception:
                report_file = None

        try:
            if report_file is not None:
                await report_channel.send(embed=embed, file=report_file)
            else:
                await report_channel.send(embed=embed)
        except Exception:
            report_channel = None

    report_user_suffix = (
        f" user_id={session_user_id} user_tag={session_user_tag} user_display={session_user_display}"
        if session_user_id
        else " user_id=-"
    )
    related_guild_log = related_guild_id or "-"
    image_name_log = report_image_name or "-"
    image_mime_log = report_image_mime or "-"
    log_line = (
        f"[WEB_REPORT] ip={client_ip}{report_user_suffix} related_guild_id={related_guild_log} "
        f"image={image_name_log} image_mime={image_mime_log} title={title} contact={contact} detail={detail}"
    )
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with (LOGS_DIR / "web_reports.log").open("a", encoding="utf-8") as handle:
            handle.write(log_line + "\n")
    except Exception:
        pass

    if report_channel is None:
        return HTMLResponse(
            _render_report_page(
                notice="Report was saved, but it could not be forwarded to Discord. Please check REPORT_CHANNEL.",
                session=session,
            ),
            status_code=202,
        )

    success_notice = "Report submitted successfully. The team has received it in Discord."
    if report_image_name:
        success_notice = "Report and attached image submitted successfully. The team has received it in Discord."
    return HTMLResponse(
        _render_report_page(
            notice=success_notice,
            session=session,
        )
    )

async def dashboard_guide_ticket_page(request: Request):
    return RedirectResponse("/docs", status_code=303)

async def dashboard_guide_security_page(request: Request):
    session = _session_from_request(request)
    return HTMLResponse(
        _render_public_doc_page(
            title="คู่มือความปลอดภัย SkylineBOT",
            heading="คู่มือความปลอดภัย",
            description="เปิดใช้งานระบบ Anti-Nuke และการป้องกันเชิงรุกในเซิร์ฟเวอร์",
            bullets=[
                "เลือกโหมดปกติ/เข้มงวด/กำหนดเองตามขนาดเซิร์ฟเวอร์",
                "ป้องกันการลบช่อง ลบบทบาท และการสร้างลิงก์เชิญที่ผิดปกติ",
                "กำหนดบทลงโทษและข้อจำกัดให้สอดคล้องกับนโยบายเซิร์ฟเวอร์",
            ],
            session=session,
        )
    )

async def dashboard_guide_giveaways_page(request: Request):
    session = _session_from_request(request)
    return HTMLResponse(
        _render_public_doc_page(
            title="คู่มือกิจกรรมแจกของ SkylineBOT",
            heading="คู่มือกิจกรรม",
            description="สร้างกิจกรรมแจกของให้มีส่วนร่วมสูงและควบคุมสิทธิ์ได้",
            bullets=[
                "ตั้งค่าบทบาทที่มีสิทธิ์จัดการกิจกรรมแจกของ",
                "ตรวจสอบกิจกรรมที่กำลังรันและที่สิ้นสุดแล้วในหน้ากิฟอะเวย์",
                "ใช้เงื่อนไขและข้อความประกาศที่ชัดเจนเพื่อป้องกันความสับสน",
            ],
            session=session,
        )
    )


async def dashboard_guide_promote_page(request: Request):
    session = _session_from_request(request)
    return HTMLResponse(
        _render_public_doc_page(
            title="คู่มือศูนย์โปรโมต SkylineBOT",
            heading="ใช้งานระบบศูนย์โปรโมตที่เชื่อมต่อกับทุกคน",
            description="ตั้งค่าห้องโปรโมตให้พร้อม แล้วส่งข้อความเข้าคิวกลางเพื่อกระจายไปยังทุกกิลด์ที่เปิดระบบ",
            bullets=[
                "เข้าแท็บโปรโมต แล้วตั้งค่าช่องส่งโปรโมตและช่องสาธารณะให้ครบก่อนใช้งาน",
                "กำหนด allowlist ของโดเมน/ลิงก์เพื่อคุมคุณภาพลิงก์โปรโมต",
                "สร้างข้อความโปรโมตพร้อมภาพ/ไฟล์แนบ (Silver ขึ้นไปรองรับ rich media)",
                "ตรวจ Preview ก่อนส่ง และกดส่งเพื่อเข้า queue กระจายแบบ global",
                "ใช้ส่วนคิวรวมเพื่อตรวจลำดับงานและดูภาพรวมกิลด์ที่อยู่ในคิว",
            ],
            session=session,
        )
    )


async def dashboard_guide_guildstyle_roles_page(request: Request):
    session = _session_from_request(request)
    return HTMLResponse(
        _render_public_doc_page(
            title="คู่มือสร้าง Roles ด้วย GuildStyle Studio",
            heading="วิธีสร้าง Roles ใน Discord ด้วยระบบ GuildStyle Studio",
            description="สร้างโครงบทบาทและสิทธิ์ให้ทั้งเซิร์ฟเวอร์จากหน้าเดียว พร้อมดูผลแบบเรียลไทม์",
            bullets=[
                "เข้าแท็บ GuildStyle Studio แล้วเลือก Theme/Font ให้เหมาะกับเซิร์ฟเวอร์",
                "กดสร้าง GuildStyle Layout เพื่อสร้างห้อง ยศ และสิทธิ์พื้นฐานแบบอัตโนมัติ",
                "เปิด Role Color Manager เพื่อเลือก Role และปรับสีได้ทันที",
                "ใช้ Permission Matrix ตั้ง View/Send/Connect/Speak รายห้องต่อแต่ละ Role",
                "ทดสอบด้วยโหมด multi-role simulation เพื่อเช็กการมองเห็นห้องก่อนใช้งานจริง",
            ],
            session=session,
        )
    )


async def dashboard_studio_split_preview_page(request: Request):
    return HTMLResponse(
        _render_developer_portal_page(request, PUBLIC_PAGE_TEMPLATES["studio_split_preview"])
    )


def _safe_dashboard_next_path(raw_value: str | None) -> str | None:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return None
    if any(ch in candidate for ch in ("\r", "\n", "\x00")):
        return None
    if candidate.startswith("//"):
        return None
    if not candidate.startswith("/dashboard"):
        return None
    return candidate


async def _ensure_support_guild_membership_from_oauth(payload: dict) -> None:
    support_guild_id = _support_guild_id_from_env()
    if support_guild_id is None:
        return

    bot_token = str(getattr(BOT_CONFIG, "TOKEN", "") or "").strip()
    if not bot_token:
        logger.warning("Support auto-join skipped: TOKEN is empty")
        return

    access_token = str((payload or {}).get("access_token") or "").strip()
    user_payload = (payload or {}).get("user") or {}
    user_id = (
        str(user_payload.get("id") or "").strip()
        if isinstance(user_payload, dict)
        else ""
    )
    if not access_token or not user_id:
        return

    support_guild_id_str = str(support_guild_id)
    for raw_guild in list((payload or {}).get("guilds") or []):
        if not isinstance(raw_guild, dict):
            continue
        if str(raw_guild.get("id") or "").strip() == support_guild_id_str:
            return

    bot = get_bot()
    if bot is not None:
        try:
            if bot.get_guild(support_guild_id) is None:
                logger.warning(
                    f"Support auto-join skipped: bot is not in support guild {support_guild_id}"
                )
                return
        except Exception:
            pass

    url = f"{DISCORD_API}/guilds/{support_guild_id}/members/{user_id}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.put(
                url,
                headers={"Authorization": f"Bot {bot_token}"},
                json={"access_token": access_token},
            )
    except Exception as error:
        logger.warning(f"Support auto-join request failed: {_clean_text(error)}")
        return

    if response.status_code in {200, 201, 204}:
        return

    detail = ""
    try:
        error_payload = response.json()
    except Exception:
        error_payload = None
    if isinstance(error_payload, dict):
        detail = str(error_payload.get("message") or error_payload.get("error") or "").strip()
    if not detail:
        detail = str(response.text or "").strip()[:240]
    logger.warning(
        f"Support auto-join failed ({response.status_code}) for user {user_id}: {detail or 'unknown error'}"
    )


async def dashboard_login(request: Request):
    next_path = _safe_dashboard_next_path(request.query_params.get("next"))
    session = _session_from_request(request)
    if session:
        return RedirectResponse(next_path or "/dashboard", status_code=303)
    if not BOT_CONFIG.DISCORD_CLIENT_SECRET:
        return HTMLResponse(await _render_login("ระบบยืนยันตัวตนแดชบอร์ดยังไม่ได้ตั้งค่า", session=session), status_code=503)
    return RedirectResponse(_oauth_authorize_url(redirect_path=next_path, request=request), status_code=303)

async def dashboard_callback(request: Request, code: str | None = None, state: str | None = None):
    session = _session_from_request(request)
    oauth_state_payload = consume_oauth_state(state)
    if not code or oauth_state_payload is None:
        return HTMLResponse(await _render_login("ไม่สามารถยืนยันการเข้าสู่ระบบด้วย Discord ได้ กรุณาลองใหม่อีกครั้ง", session=session), status_code=400)
    state_callback_url = None
    if isinstance(oauth_state_payload, dict):
        state_callback_url = str(oauth_state_payload.get("callback_url") or "").strip() or None
    callback_url = (
        _dashboard_callback_url(base_url_override=state_callback_url)
        if state_callback_url
        else _dashboard_callback_url(request=request)
    )
    try:
        payload = await _load_oauth_profile(code, callback_url=callback_url)
    except Exception as error:
        error_text = _clean_text(error)
        lower_error = error_text.lower()
        status_code = 502
        notice = f"เข้าสู่ระบบ Discord ไม่สำเร็จ: {error_text}"

        if "invalid_grant" in lower_error or 'invalid "code"' in lower_error:
            status_code = 400
            notice = "โค้ดเข้าสู่ระบบหมดอายุหรือถูกใช้ไปแล้ว กรุณากดเข้าสู่ระบบใหม่อีกครั้ง"
        elif "invalid_client" in lower_error:
            status_code = 503
            notice = "Discord Client Secret ไม่ถูกต้อง กรุณาตรวจสอบ DISCORD_CLIENT_SECRET ใน .env"
        elif "redirect_uri" in lower_error:
            status_code = 400
            notice = "Discord Redirect URI ไม่ตรงกัน กรุณาตรวจสอบ DASHBOARD_BASE_URL และ OAuth2 Redirects"

        return HTMLResponse(await _render_login(notice, session=session), status_code=status_code)
    await _ensure_support_guild_membership_from_oauth(payload)
    session_id = create_session(payload)
    redirect_path = _safe_dashboard_next_path(
        (oauth_state_payload or {}).get("redirect_path")
        if isinstance(oauth_state_payload, dict)
        else None
    )
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    request_scheme = str(getattr(getattr(request, "url", None), "scheme", "") or "").strip().lower()
    cookie_secure = forwarded_proto == "https" or request_scheme == "https"
    response = RedirectResponse(url=redirect_path or "/dashboard", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        secure=cookie_secure,
        max_age=604800,
        path="/",
    )
    return response

async def dashboard_logout(request: Request):
    destroy_session(request.cookies.get(SESSION_COOKIE))
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


def _profile_as_utc_datetime(raw_value):
    if not raw_value:
        return None
    if isinstance(raw_value, datetime.datetime):
        return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=datetime.timezone.utc)
    if isinstance(raw_value, (int, float)):
        try:
            ts = float(raw_value)
            if ts > 10_000_000_000:
                ts /= 1000.0
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        except Exception:
            return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        if text.isdigit():
            ts = float(text)
            if ts > 10_000_000_000:
                ts /= 1000.0
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def _profile_sort_rows_by_created_desc(rows: list[dict], time_key: str = "created_at") -> list[dict]:
    def _sort_key(item: dict) -> tuple[int, float]:
        dt_value = _profile_as_utc_datetime(item.get(time_key))
        if not dt_value:
            return (0, 0.0)
        return (1, dt_value.timestamp())

    return sorted(rows or [], key=_sort_key, reverse=True)


def _profile_normalize_plan_tier(raw_value: object) -> str:
    normalized = str(raw_value or "").strip().lower()
    mapping = {
        "silver_guild_preminum": "silver",
        "golden_guild_premium": "golden",
        "gole_guild_premium": "golden",
        "diamond_guild_premium": "diamond",
        "permanent_guild_premium": "permanent",
        "lifetime_guild_premium": "permanent",
    }
    normalized = mapping.get(normalized, normalized)
    if normalized in {"free", "silver", "golden", "diamond", "permanent"}:
        return normalized
    if normalized in {"gold", "gole"}:
        return "golden"
    if normalized in {"lifetime", "forever"}:
        return "permanent"
    return "free"


def _profile_filter_premium_events(rows: list[dict]) -> list[dict]:
    filtered: list[dict] = []
    for row in rows or []:
        event_type = str(row.get("event_type") or "").strip().lower()
        if event_type.startswith("plan_"):
            filtered.append(row)
    return filtered


def _profile_is_paid_plan(plan_tier: str) -> bool:
    return plan_tier in {"silver", "golden", "diamond", "permanent"}


def _profile_parse_positive_int(raw_value: object, default: int = 1) -> int:
    try:
        parsed = int(str(raw_value or "").strip())
    except Exception:
        return max(1, int(default or 1))
    return max(1, parsed)


def _profile_paginate_rows(rows: list[dict], page: int, page_size: int = 30) -> dict:
    safe_rows = list(rows or [])
    safe_page_size = max(1, int(page_size or 30))
    total_count = len(safe_rows)
    total_pages = max(1, (total_count + safe_page_size - 1) // safe_page_size) if total_count else 1
    safe_page = max(1, min(int(page or 1), total_pages))
    start = (safe_page - 1) * safe_page_size
    return {
        "rows": safe_rows[start:start + safe_page_size],
        "page": safe_page,
        "page_size": safe_page_size,
        "total_count": total_count,
        "total_pages": total_pages,
    }


def _profile_extract_admin_user_id(meta_payload: object) -> int:
    if not isinstance(meta_payload, dict):
        return 0
    for candidate in (
        meta_payload.get("admin_user_id"),
        meta_payload.get("actor_user_id"),
        meta_payload.get("admin_id"),
    ):
        try:
            parsed = int(str(candidate or "").strip())
        except Exception:
            parsed = 0
        if parsed > 0:
            return parsed
    return 0


def _profile_extract_admin_user_id_from_note(note_raw: object) -> int:
    note_text = str(note_raw or "").strip()
    if not note_text:
        return 0
    marker = "admin:"
    lowered = note_text.lower()
    if marker not in lowered:
        return 0
    start = lowered.find(marker)
    raw_slice = note_text[start + len(marker):].strip()
    digits: list[str] = []
    for ch in raw_slice:
        if ch.isdigit():
            digits.append(ch)
            continue
        break
    if not digits:
        return 0
    try:
        return int("".join(digits))
    except Exception:
        return 0


def _profile_extract_admin_note(note_raw: object) -> str:
    note_text = str(note_raw or "").strip()
    if not note_text:
        return "-"
    if "|" in note_text:
        custom_note = note_text.split("|", 1)[1].strip()
        if custom_note:
            return custom_note[:280]
    lowered = note_text.lower()
    if lowered.startswith("ownerbot ") and " by admin:" in lowered:
        return "-"
    return note_text[:280]


async def _profile_resolve_actor_labels(user_ids: set[int]) -> dict[int, str]:
    resolved: dict[int, str] = {}
    if not user_ids:
        return resolved
    bot = get_bot()
    for user_id in sorted(user_ids):
        if user_id <= 0:
            continue
        label = f"Admin ({user_id})"
        user_obj = None
        if bot:
            try:
                user_obj = bot.get_user(user_id)
            except Exception:
                user_obj = None
        if user_obj is None and bot:
            try:
                user_obj = await bot.fetch_user(user_id)
            except Exception:
                user_obj = None
        if user_obj is not None:
            user_name = str(getattr(user_obj, "name", "") or "").strip()
            user_discriminator = str(getattr(user_obj, "discriminator", "") or "").strip()
            if user_name and user_discriminator and user_discriminator != "0":
                label = f"{user_name}#{user_discriminator} ({user_id})"
            elif user_name:
                label = f"{user_name} ({user_id})"
        resolved[user_id] = label
    return resolved


async def _profile_build_topup_history_rows(*, user_id_int: int, payment_rows: list[dict]) -> list[dict]:
    merged_rows: list[dict] = []

    for row in payment_rows or []:
        safe_row = row if isinstance(row, dict) else {}
        verify_note = str(safe_row.get("verify_note") or "").strip()
        transfer_reference = str(safe_row.get("transfer_reference") or "").strip()
        transfer_link = str(safe_row.get("transfer_link") or "").strip()
        provider_name = str(safe_row.get("provider_name") or "").strip()
        note_text = verify_note or transfer_reference or transfer_link or "-"
        if note_text == "-" and provider_name:
            note_text = provider_name
        merged_rows.append(
            {
                **safe_row,
                "entry_type": "payment",
                "action_kind": "payment",
                "action_label": "เติมเงิน",
                "actor": "ผู้ใช้",
                "note": note_text,
                "_sort_at": safe_row.get("paid_at") or safe_row.get("created_at"),
            }
        )

    try:
        ledger_rows_raw = await storage.bot_wallet_ledger.gets(
            user_id=int(user_id_int),
            source_mode="ownerbot_admin",
        )
    except Exception:
        ledger_rows_raw = []
    ledger_rows = list(ledger_rows_raw or [])
    admin_user_ids: set[int] = set()
    for row in ledger_rows:
        safe_row = row if isinstance(row, dict) else {}
        admin_user_id = _profile_extract_admin_user_id(safe_row.get("meta"))
        if admin_user_id <= 0:
            admin_user_id = _profile_extract_admin_user_id_from_note(safe_row.get("note"))
        if admin_user_id > 0:
            admin_user_ids.add(admin_user_id)

    admin_labels = await _profile_resolve_actor_labels(admin_user_ids)
    action_labels = {
        "ownerbot_admin_credit": "แอดมินเพิ่มยอด",
        "ownerbot_admin_clear": "แอดมินลบยอด",
        "ownerbot_admin_set": "แอดมินเซ็ตยอด",
    }
    action_kinds = {
        "ownerbot_admin_credit": "admin_add",
        "ownerbot_admin_clear": "admin_delete",
        "ownerbot_admin_set": "admin_set",
    }
    for row in ledger_rows:
        safe_row = row if isinstance(row, dict) else {}
        kind_text = str(safe_row.get("kind") or "").strip().lower()
        admin_user_id = _profile_extract_admin_user_id(safe_row.get("meta"))
        if admin_user_id <= 0:
            admin_user_id = _profile_extract_admin_user_id_from_note(safe_row.get("note"))
        actor_text = admin_labels.get(admin_user_id) if admin_user_id > 0 else ""
        if not actor_text:
            actor_text = f"Admin ({admin_user_id})" if admin_user_id > 0 else "Admin"
        merged_rows.append(
            {
                "entry_type": "admin",
                "action_kind": action_kinds.get(kind_text, "admin_adjust"),
                "action_label": action_labels.get(kind_text, "แอดมินปรับยอด"),
                "session_key": str(safe_row.get("session_key") or "").strip(),
                "amount": safe_row.get("amount", 0.0),
                "status": "completed",
                "verify_status": "-",
                "created_at": safe_row.get("created_at"),
                "paid_at": safe_row.get("created_at"),
                "actor": actor_text,
                "note": _profile_extract_admin_note(safe_row.get("note")),
                "_sort_at": safe_row.get("created_at"),
            }
        )

    def _sort_key(item: dict) -> tuple[int, float]:
        dt_value = _profile_as_utc_datetime(item.get("_sort_at") or item.get("created_at"))
        if not dt_value:
            return (0, 0.0)
        return (1, dt_value.timestamp())

    merged_rows.sort(key=_sort_key, reverse=True)
    return merged_rows


async def _load_profile_billing_data(session: dict, guilds: list[dict]) -> dict:
    user_id = _session_user_id(session)
    if not user_id:
        return {
            "wallet_balance": 0.0,
            "topup_rows": [],
            "premium_history_rows": [],
            "plan_rows": [],
        }

    user_id_int = int(user_id)
    await billing_workflow.ensure_wallet_account(user_id_int)
    wallet_balance = await billing_workflow.get_wallet_balance(user_id_int)

    topup_rows = _profile_sort_rows_by_created_desc(
        await storage.bot_payment_sessions.gets(user_id=user_id_int, mode="topup")
    )

    premium_history_rows = _profile_filter_premium_events(
        _profile_sort_rows_by_created_desc(
            await storage.bot_billing_events.gets(user_id=user_id_int)
        )
    )

    plan_rows_by_guild: dict[int, dict] = {}
    for row in await storage.bot_plan_subscriptions.get_all() or []:
        try:
            guild_id = int(row.get("guild_id") or 0)
        except Exception:
            continue
        if guild_id > 0:
            plan_rows_by_guild[guild_id] = row

    plan_rows: list[dict] = []
    for guild in guilds or []:
        guild_id_raw = str(guild.get("id") or "").strip()
        if not guild_id_raw.isdigit():
            continue
        guild_id = int(guild_id_raw)
        row = plan_rows_by_guild.get(guild_id, {})
        guild_cache = cache.guilds.get(str(guild_id), {}) if hasattr(cache, "guilds") else {}
        if not isinstance(guild_cache, dict):
            guild_cache = {}
        guild_plan_raw = str(guild_cache.get("subscription") or "").strip()
        guild_plan = _profile_normalize_plan_tier(guild_plan_raw) if guild_plan_raw else "free"

        if row.get("id") or _profile_is_paid_plan(guild_plan):
            try:
                synced_row = await billing_workflow.sync_plan_subscription_with_guild_state(guild_id=guild_id)
            except Exception:
                synced_row = None
            if isinstance(synced_row, dict) and synced_row.get("id"):
                row = synced_row
                plan_rows_by_guild[guild_id] = synced_row

        row_plan = _profile_normalize_plan_tier(row.get("current_plan") or "free")
        row_status = str(row.get("status") or "").strip().lower()
        if row.get("id"):
            current_plan = row_plan
            # Keep permanent label in profile even when guild cache stores diamond for compatibility.
            if row_plan == "permanent" and guild_plan == "diamond":
                current_plan = "permanent"
            elif current_plan == "free" and _profile_is_paid_plan(guild_plan):
                current_plan = guild_plan
        else:
            current_plan = guild_plan if guild_plan_raw else row_plan
        pending_plan_raw = str(row.get("pending_plan") or "").strip()
        pending_plan = _profile_normalize_plan_tier(pending_plan_raw) if pending_plan_raw else ""
        if not (_profile_is_paid_plan(current_plan) or _profile_is_paid_plan(pending_plan)):
            continue
        current_period_end = row.get("current_period_end") or guild_cache.get("subscription_end")
        if current_plan == "permanent":
            current_period_end = None
        resolved_status = row_status or ("active" if current_plan != "free" else "free")
        if current_plan == "free" and _profile_is_paid_plan(pending_plan):
            resolved_status = resolved_status if resolved_status in {"awaiting_payment", "queued", "active"} else "awaiting_payment"
        plan_rows.append(
            {
                "guild_id": guild_id,
                "guild_name": str(guild.get("name") or guild_id),
                "current_plan": current_plan,
                "pending_plan": pending_plan,
                "status": resolved_status,
                "auto_renew": bool(row.get("auto_renew", True)),
                "current_period_end": current_period_end,
            }
        )

    return {
        "wallet_balance": wallet_balance,
        "topup_rows": topup_rows,
        "premium_history_rows": premium_history_rows,
        "plan_rows": plan_rows,
    }


async def dashboard_user_profile_settings(request: Request, notice: str | None = None):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard/login", status_code=303)
    guilds = await _manageable_guilds_live(session)
    profile = await _load_dashboard_user_profile(session)
    billing_view = await _load_profile_billing_data(session, guilds)
    page_notice = notice or str(request.query_params.get("notice") or "").strip() or None
    return HTMLResponse(
        _render_user_profile_settings_page(
            session=session,
            guilds=guilds,
            profile=profile,
            notice=page_notice,
            wallet_balance=float(billing_view.get("wallet_balance") or 0.0),
            topup_rows=list(billing_view.get("topup_rows") or []),
            premium_history_rows=list(billing_view.get("premium_history_rows") or []),
            plan_rows=list(billing_view.get("plan_rows") or []),
        )
    )


async def dashboard_user_profile_topup_history(request: Request, notice: str | None = None):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard/login?next=/dashboard/setting-profile-user/topup-history", status_code=303)
    guilds = await _manageable_guilds_live(session)
    profile = await _load_dashboard_user_profile(session)
    billing_view = await _load_profile_billing_data(session, guilds)
    user_id_int = int(_session_user_id(session) or 0)
    topup_history_rows = await _profile_build_topup_history_rows(
        user_id_int=user_id_int,
        payment_rows=list(billing_view.get("topup_rows") or []),
    )
    page_number = _profile_parse_positive_int(request.query_params.get("page"), default=1)
    pagination = _profile_paginate_rows(
        topup_history_rows,
        page=page_number,
        page_size=30,
    )
    page_notice = notice or str(request.query_params.get("notice") or "").strip() or None
    return HTMLResponse(
        _render_user_profile_topup_history_page(
            session=session,
            guilds=guilds,
            profile=profile,
            wallet_balance=float(billing_view.get("wallet_balance") or 0.0),
            rows=list(pagination.get("rows") or []),
            page=int(pagination.get("page") or 1),
            page_size=int(pagination.get("page_size") or 30),
            total_count=int(pagination.get("total_count") or 0),
            total_pages=int(pagination.get("total_pages") or 1),
            notice=page_notice,
        )
    )


async def dashboard_user_profile_premium_history(request: Request, notice: str | None = None):
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard/login?next=/dashboard/setting-profile-user/premium-history", status_code=303)
    guilds = await _manageable_guilds_live(session)
    profile = await _load_dashboard_user_profile(session)
    billing_view = await _load_profile_billing_data(session, guilds)
    page_number = _profile_parse_positive_int(request.query_params.get("page"), default=1)
    pagination = _profile_paginate_rows(
        list(billing_view.get("premium_history_rows") or []),
        page=page_number,
        page_size=30,
    )
    page_notice = notice or str(request.query_params.get("notice") or "").strip() or None
    return HTMLResponse(
        _render_user_profile_premium_history_page(
            session=session,
            guilds=guilds,
            profile=profile,
            wallet_balance=float(billing_view.get("wallet_balance") or 0.0),
            rows=list(pagination.get("rows") or []),
            page=int(pagination.get("page") or 1),
            page_size=int(pagination.get("page_size") or 30),
            total_count=int(pagination.get("total_count") or 0),
            total_pages=int(pagination.get("total_pages") or 1),
            notice=page_notice,
        )
    )


async def dashboard_public_user_profile(
    request: Request, guild_id: int, user_id: int
):
    session = _session_from_request(request)
    guilds = await _manageable_guilds_live(session) if session else []
    safe_guild_id = _safe_int(guild_id, 0)
    safe_user_id = _safe_int(user_id, 0)

    def _fmt_datetime(raw_value: object) -> str:
        if not raw_value:
            return "-"
        try:
            if isinstance(raw_value, datetime.datetime):
                parsed = raw_value
            else:
                text = str(raw_value).strip()
                if not text:
                    return "-"
                parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed.astimezone(
                datetime.timezone(datetime.timedelta(hours=7))
            ).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return "-"

    relation_labels = {
        "single": "โสด",
        "married": "แต่งงานแล้ว",
        "engaged": "หมั้น",
        "in_relationship": "คบกันอยู่",
        "complicated": "ซับซ้อน",
    }

    if safe_guild_id <= 0 or safe_user_id <= 0:
        body = (
            '<section class="panel"><h2>User Profile</h2>'
            '<p class="muted">Invalid guild_id or user_id.</p></section>'
        )
        return HTMLResponse(
            _render_layout(
                title="โปรไฟล์ผู้ใช้",
                body=body,
                session=session,
                guilds=guilds,
            )
        )

    bot = get_bot()
    guild = bot.get_guild(safe_guild_id) if bot else None
    if guild is None:
        body = (
            '<section class="panel"><h2>User Profile</h2>'
            '<p class="muted">Guild not found.</p></section>'
        )
        return HTMLResponse(
            _render_layout(
                title="โปรไฟล์ผู้ใช้",
                body=body,
                session=session,
                guilds=guilds,
            )
        )

    member = guild.get_member(safe_user_id)
    if member is None:
        try:
            member = await guild.fetch_member(safe_user_id)
        except Exception:
            member = None

    user_obj = member or (bot.get_user(safe_user_id) if bot else None)
    if user_obj is None and bot:
        try:
            user_obj = await bot.fetch_user(safe_user_id)
        except Exception:
            user_obj = None

    if user_obj is None:
        body = (
            '<section class="panel"><h2>User Profile</h2>'
            '<p class="muted">User not found in this guild.</p></section>'
        )
        return HTMLResponse(
            _render_layout(
                title="โปรไฟล์ผู้ใช้",
                body=body,
                session=session,
                guilds=guilds,
            )
        )

    avatar_url = str(getattr(getattr(user_obj, "display_avatar", None), "url", "") or "")
    if not avatar_url:
        avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
    display_name = str(
        getattr(user_obj, "display_name", None)
        or getattr(user_obj, "global_name", None)
        or getattr(user_obj, "name", None)
        or safe_user_id
    ).strip()
    username = str(getattr(user_obj, "name", None) or display_name).strip()
    accent_hex = "#4a78ff"
    try:
        member_color = getattr(member, "color", None)
        color_value = int(getattr(member_color, "value", 0) or 0)
        if color_value > 0:
            accent_hex = f"#{color_value:06x}"
    except Exception:
        pass

    guild_profile = (
        await storage.guild_user_profiles.get(guild_id=safe_guild_id, user_id=safe_user_id)
    ) or {}
    relation_key = str(guild_profile.get("relationship") or "single").strip().lower()
    relation_label = relation_labels.get(
        relation_key,
        relation_key.replace("_", " ").title() if relation_key else "โสด",
    )
    spouse_id = _safe_int(guild_profile.get("spouse_id"), 0)
    proposal_to_id = _safe_int(guild_profile.get("proposal_to_id"), 0)
    proposal_from_id = _safe_int(guild_profile.get("proposal_from_id"), 0)
    spouse_text = "-"
    if spouse_id > 0:
        spouse_member = guild.get_member(spouse_id)
        spouse_name = str(
            getattr(spouse_member, "display_name", None)
            or getattr(spouse_member, "name", None)
            or spouse_id
        )
        spouse_text = f"{html.escape(spouse_name)} (ID: {spouse_id})"
    proposal_text = "-"
    if proposal_to_id > 0:
        proposal_text = f"Outgoing to <@{proposal_to_id}>"
    elif proposal_from_id > 0:
        proposal_text = f"Incoming from <@{proposal_from_id}>"

    joined_guild_text = _fmt_datetime(getattr(member, "joined_at", None)) if member else "-"
    created_at_text = _fmt_datetime(getattr(user_obj, "created_at", None))
    married_at_text = _fmt_datetime(guild_profile.get("married_at"))
    role_names = []
    if member:
        for role in reversed(list(getattr(member, "roles", []) or [])):
            role_name = str(getattr(role, "name", "") or "")
            if role_name and role_name != "@everyone":
                role_names.append(role_name)
    roles_text = ", ".join(role_names[:15]) if role_names else "-"

    profile_settings_url = (
        "/dashboard/setting-profile-user"
        if _session_user_id(session) and _session_user_id(session) == safe_user_id
        else ""
    )
    guild_dash_url = f"/dashboard/guild/{safe_guild_id}"

    body = f"""
    <link rel="stylesheet" href="/dashboard/static/dashboard/pages/user-profile-settings.css">
    <section class="panel profile-user-shell">
      <div class="profile-user-banner" style="background:linear-gradient(135deg, {html.escape(accent_hex)}, #22d3ee);"></div>
      <div class="profile-user-head">
        <img src="{html.escape(avatar_url)}" alt="{html.escape(display_name)}" class="profile-user-avatar">
        <div class="profile-user-title">
          <h1>{html.escape(display_name)}</h1>
          <p>@{html.escape(username)}</p>
          <span class="profile-user-status status-online">Public Profile</span>
        </div>
      </div>

      <div class="profile-user-grid">
        <article class="profile-user-card">
          <h3>User Info</h3>
          <ul>
            <li><span>User ID</span><strong>{safe_user_id}</strong></li>
            <li><span>Guild</span><strong>{html.escape(str(getattr(guild, "name", "") or safe_guild_id))}</strong></li>
            <li><span>Joined Discord</span><strong>{html.escape(created_at_text)}</strong></li>
            <li><span>Joined Guild</span><strong>{html.escape(joined_guild_text)}</strong></li>
          </ul>
        </article>
        <article class="profile-user-card">
          <h3>Marriage & Relationship</h3>
          <ul>
            <li><span>Status</span><strong>{html.escape(relation_label)}</strong></li>
            <li><span>Spouse</span><strong>{spouse_text}</strong></li>
            <li><span>Proposal</span><strong>{proposal_text}</strong></li>
            <li><span>Married At</span><strong>{html.escape(married_at_text)}</strong></li>
            <li><span>Roles</span><strong>{html.escape(roles_text)}</strong></li>
          </ul>
        </article>
      </div>

      <div class="auth-actions" style="justify-content:flex-start; padding:0 18px 18px;">
        <a class="ghost-btn" href="{guild_dash_url}"><i class="fa-solid fa-gauge-high"></i> Guild Dashboard</a>
        {'<a class="ghost-btn" href="' + profile_settings_url + '"><i class="fa-solid fa-user"></i> My Profile</a>' if profile_settings_url else ''}
        <a class="ghost-btn" href="/dashboard"><i class="fa-solid fa-house"></i> Home</a>
      </div>
    </section>
    """

    return HTMLResponse(
        _render_layout(
            title=f"User Profile - {display_name}",
            body=body,
            session=session,
            guilds=guilds,
        )
    )
