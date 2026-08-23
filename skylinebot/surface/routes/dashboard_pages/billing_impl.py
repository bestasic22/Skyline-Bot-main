from __future__ import annotations

import datetime
import hashlib
import hmac
import html
import json
import re
from typing import Any
from urllib.parse import parse_qs

from ..dashboard_core import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Request,
    _clean_text,
    _ensure_dashboard_config_cache,
    _is_dashboard_admin,
    _manageable_guilds,
    _parse_form,
    _render_guild_picker,
    _render_layout,
    _render_login,
    _session_from_request,
    _session_user_id,
    cache,
    get_bot,
    storage,
    urlencode,
)
from skylinebot.workflows import billing as billing_workflow


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _as_utc_datetime(raw_value: Any) -> datetime.datetime | None:
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


def _fmt_dt(raw_value: Any) -> str:
    dt_value = _as_utc_datetime(raw_value)
    if not dt_value:
        return "-"
    dt_utc = dt_value.astimezone(datetime.timezone.utc)
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_money(value: Any) -> str:
    try:
        return f"{float(value or 0.0):,.2f}"
    except Exception:
        return "0.00"


def _parse_bool_form(form: dict[str, Any], key: str, default: bool = False) -> bool:
    raw = str(form.get(key) or "").strip().lower()
    if raw in {"1", "true", "on", "yes"}:
        return True
    if raw in {"0", "false", "off", "no"}:
        return False
    return default


def _parse_float_form(form: dict[str, Any], key: str, default: float = 0.0) -> float:
    raw = str(form.get(key) or "").strip().replace(",", "")
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _normalize_provider_name(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"promptpay", "pp"}:
        return "promptpay"
    if raw in {"truemoney", "true_money", "truewallet", "tmwallet", "tmw"}:
        return "truemoney"
    return ""


TRUEMONEY_GIFT_LINK_RE = re.compile(r"^https?://gift\.truemoney\.com/campaign/\?v=[A-Za-z0-9_-]{8,}$", re.I)


def _payload_path_get(payload: Any, path: str) -> Any:
    if not isinstance(payload, dict):
        return None
    current: Any = payload
    for part in str(path or "").split("."):
        key = str(part or "").strip()
        if not key:
            return None
        if not isinstance(current, dict) or key not in current:
            return None
        current = current.get(key)
    return current


def _payload_first_text(payload: dict[str, Any], candidates: list[str]) -> str:
    for candidate in candidates:
        if "." in candidate:
            value = _payload_path_get(payload, candidate)
        else:
            value = payload.get(candidate)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _payload_first_amount(payload: dict[str, Any], candidates: list[str]) -> float | None:
    for candidate in candidates:
        if "." in candidate:
            value = _payload_path_get(payload, candidate)
        else:
            value = payload.get(candidate)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        text = text.replace(",", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            continue
        try:
            return float(match.group(0))
        except Exception:
            continue
    return None


def _status_force_paid(value: Any) -> bool:
    status_value = str(value or "").strip().lower()
    return status_value in {
        "paid",
        "success",
        "succeeded",
        "approved",
        "completed",
        "complete",
        "captured",
        "ok",
        "1000",
        "accc",
        "acsc",
        "acsp",
        "00",
        "1",
        "true",
    }


_SESSION_KEY_PATTERN = re.compile(r"\b[a-f0-9]{32}\b", re.I)


def _extract_session_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if len(lowered) == 32 and all(ch in "0123456789abcdef" for ch in lowered):
        return lowered
    found = _SESSION_KEY_PATTERN.search(lowered)
    if found:
        return found.group(0).lower()
    return ""


def _normalize_lookup_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.lower()


def _collect_session_lookup_tokens(payload: dict[str, Any], settings: dict[str, Any] | None = None) -> list[str]:
    candidates = [
        "session_key",
        "session",
        "sessionKey",
        "metadata.session_key",
        "meta.session_key",
        "data.session_key",
        "data.metadata.session_key",
        "order_id",
        "reference",
        "data.orderId",
        "data.reference",
        "transaction_id",
        "transactionId",
        "data.transactionId",
        "tx_ref",
    ]
    tokens: list[str] = []
    for candidate in candidates:
        if "." in candidate:
            value = _payload_path_get(payload, candidate)
        else:
            value = payload.get(candidate)
        if value is None:
            continue
        normalized = _normalize_lookup_token(value)
        if len(normalized) < 6:
            continue
        if normalized and normalized not in tokens:
            tokens.append(normalized)
    return tokens


def _session_row_lookup_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    session_key = _normalize_lookup_token(row.get("session_key"))
    if session_key:
        tokens.add(session_key)
        if len(session_key) >= 20:
            tokens.add(session_key[:20])
    transfer_reference = _normalize_lookup_token(row.get("transfer_reference"))
    if transfer_reference:
        tokens.add(transfer_reference)
    meta = row.get("meta")
    if isinstance(meta, dict):
        for key in ("truemoney_reference", "truemoney_transaction_id"):
            tm_ref = _normalize_lookup_token(meta.get(key))
            if tm_ref:
                tokens.add(tm_ref)
    return tokens


async def _resolve_session_from_tokens(tokens: list[str]) -> dict[str, Any] | None:
    normalized_tokens = [token for token in (str(item or "").strip().lower() for item in (tokens or [])) if token]
    if not normalized_tokens:
        return None
    token_set = set(normalized_tokens)
    rows = _sort_rows_by_created_desc(await storage.bot_payment_sessions.get_all())
    for pending_only in (True, False):
        for row in rows:
            status_value = str(row.get("status") or "").strip().lower()
            if pending_only and status_value != "pending":
                continue
            if not pending_only and status_value == "pending":
                continue
            row_tokens = _session_row_lookup_tokens(row)
            if row_tokens and row_tokens.intersection(token_set):
                return row
    return None


def _session_manual_verify_allowed(session_row: dict[str, Any] | None, settings: dict[str, Any] | None) -> bool:
    row = session_row if isinstance(session_row, dict) else {}
    provider_type = str(row.get("provider_type") or "promptpay").strip().lower()
    return provider_type in {"promptpay", "truemoney"}


def _slip_verify_engine_name(settings: dict[str, Any] | None) -> str:
    cfg = settings if isinstance(settings, dict) else {}
    engine = str(cfg.get("slipcheck_verify_engine") or "slipok").strip().lower()
    if engine in {"skylinebot", "skyline", "skyline_slip", "skylinebotslip", "internal", "ocr"}:
        return "SkylineBot Slip"
    return "SlipOK"


def _session_verify_notice(session_row: dict[str, Any] | None, settings: dict[str, Any] | None) -> str:
    row = session_row if isinstance(session_row, dict) else {}
    provider_type = _normalize_provider_name(row.get("provider_type")) or "promptpay"
    engine_name = _slip_verify_engine_name(settings)
    if provider_type == "promptpay":
        return f"PromptPay QR: submit slip URL/QR payload for {engine_name} verification."
    if provider_type == "truemoney":
        return f"TrueMoney QR: waiting for auto callback/inquiry. You can also submit slip for {engine_name} verification."
    return "Waiting for payment verification."


def _session_live_status_enabled(session_row: dict[str, Any] | None, settings: dict[str, Any] | None) -> bool:
    row = session_row if isinstance(session_row, dict) else {}
    cfg = settings if isinstance(settings, dict) else {}
    provider_type = _normalize_provider_name(row.get("provider_type")) or "promptpay"
    if provider_type == "truemoney":
        return bool(str(cfg.get("truemoney_inquiry_url") or "").strip()) and bool(cfg.get("truemoney_auto_verify", True))
    return False


def _session_should_auto_confirm_via_poll(session_row: dict[str, Any] | None, settings: dict[str, Any] | None) -> bool:
    row = session_row if isinstance(session_row, dict) else {}
    cfg = settings if isinstance(settings, dict) else {}
    provider_type = _normalize_provider_name(row.get("provider_type")) or "promptpay"
    if provider_type == "truemoney":
        return bool(str(cfg.get("truemoney_inquiry_url") or "").strip()) and bool(cfg.get("truemoney_auto_verify", True))
    return False

def _parse_webhook_payload(raw_body: bytes, content_type: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    lowered = str(content_type or "").lower()
    if "application/json" in lowered:
        try:
            decoded = json.loads((raw_body or b"{}").decode("utf-8", errors="ignore"))
            if isinstance(decoded, dict):
                return decoded
        except Exception:
            return {}
    if "application/x-www-form-urlencoded" in lowered or "multipart/form-data" in lowered:
        try:
            query_data = parse_qs((raw_body or b"").decode("utf-8", errors="ignore"), keep_blank_values=True)
            for key, values in query_data.items():
                if not values:
                    continue
                payload[str(key)] = values[-1]
        except Exception:
            return {}
    return payload


def _verify_hmac_signature(
    *,
    raw_body: bytes,
    secret: str,
    provided_signature: str,
    algorithm: str = "sha256",
    prefix: str = "",
) -> bool:
    if not secret or not provided_signature:
        return False
    algorithm_name = str(algorithm or "sha256").strip().lower()
    if algorithm_name not in {"sha256", "sha1", "md5"}:
        algorithm_name = "sha256"
    digestmod = getattr(hashlib, algorithm_name, hashlib.sha256)
    expected_hash = hmac.new(secret.encode("utf-8"), raw_body or b"", digestmod).hexdigest()
    normalized = str(provided_signature or "").strip()
    fixed_prefix = str(prefix or "").strip()
    if fixed_prefix and normalized.lower().startswith(fixed_prefix.lower()):
        normalized = normalized[len(fixed_prefix):].strip()
    return hmac.compare_digest(normalized.lower(), expected_hash.lower())



def _manageable_guild_id_set(guild_rows: list[dict[str, Any]]) -> set[int]:
    allowed: set[int] = set()
    for row in guild_rows:
        try:
            allowed.add(int(row.get("id")))
        except Exception:
            continue
    return allowed


def _sort_rows_by_created_desc(rows: list[dict[str, Any]], time_key: str = "created_at") -> list[dict[str, Any]]:
    def _sort_key(item: dict[str, Any]) -> tuple[int, float]:
        dt_value = _as_utc_datetime(item.get(time_key))
        if not dt_value:
            return (0, 0.0)
        return (1, dt_value.timestamp())

    return sorted(rows or [], key=_sort_key, reverse=True)


async def _parse_wallet_form_payload(request: Request) -> tuple[dict[str, Any], Any | None, str]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        try:
            parsed_form = await request.form()
        except AssertionError:
            return (
                {},
                None,
                "เซิร์ฟเวอร์ยังไม่รองรับฟอร์มอัปโหลดไฟล์",
            )
        values: dict[str, Any] = {}
        for key, value in parsed_form.items():
            if getattr(value, "filename", None):
                continue
            values[str(key)] = str(value)
        return values, parsed_form, ""
    return await _parse_form(request), None, ""


def _safe_upload_name(filename: Any) -> str:
    raw = str(filename or "slip.png").strip() or "slip.png"
    raw = raw.replace("\\", "/").split("/")[-1]
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw).strip("._")
    if not safe:
        return "slip.png"
    if "." not in safe:
        safe = f"{safe}.png"
    return safe[:96]


async def _upload_wallet_slip_image(
    *,
    session: dict[str, Any],
    raw_bytes: bytes,
    filename: str,
    request: Request | None = None,
) -> str:
    if not raw_bytes:
        return ""
    try:
        from .guild_impl import _upload_image_to_discord_cdn
    except Exception:
        return ""

    guild_candidates: list[int] = []
    for row in list(_manageable_guilds(session) or []):
        try:
            gid = int(row.get("id") or 0)
        except Exception:
            gid = 0
        if gid > 0 and gid not in guild_candidates:
            guild_candidates.append(gid)

    bot = get_bot()
    if not guild_candidates and bot is not None:
        for guild in list(getattr(bot, "guilds", []) or [])[:6]:
            try:
                gid = int(getattr(guild, "id", 0) or 0)
            except Exception:
                gid = 0
            if gid > 0 and gid not in guild_candidates:
                guild_candidates.append(gid)

    if not guild_candidates:
        return ""

    safe_name = _safe_upload_name(filename or "wallet-slip.png")
    for guild_id in guild_candidates:
        try:
            uploaded_url = await _upload_image_to_discord_cdn(
                int(guild_id),
                raw_bytes=raw_bytes,
                filename=safe_name,
                upload_target="verify",
                request=request,
                uploader_id=int(_session_user_id(session) or 0),
                source_route=str(getattr(getattr(request, "url", None), "path", "") or ""),
                source_field="wallet_slip_image",
            )
        except Exception:
            uploaded_url = ""
        uploaded_text = str(uploaded_url or "").strip()
        if uploaded_text:
            return uploaded_text
    return ""


def _normalize_plan_label(plan_tier: str) -> str:
    mapping = {
        "free": "Free",
        "silver": "Silver",
        "golden": "Gole",
        "diamond": "Diamond",
        "permanent": "Permanent",
    }
    return mapping.get(str(plan_tier or "free").strip().lower(), "Free")


def _build_wallet_page_body(
    *,
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    balance: float,
    payment_settings: dict[str, Any],
    pending_session: dict[str, Any] | None,
    topup_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    plan_rows_by_guild_id: dict[int, dict[str, Any]],
    user_app_subscription: dict[str, Any] | None,
    event_rows: list[dict[str, Any]],
    topup_ready: bool = True,
    topup_ready_message: str = "",
    keyword: str = "",
    notice: str | None = None,
) -> str:
    _ = guilds, ledger_rows, plan_rows_by_guild_id, user_app_subscription, event_rows, keyword

    notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""
    selected_provider_key = _normalize_provider_name(payment_settings.get("topup_provider")) or "promptpay"
    active_provider_key, provider_fallback_note = billing_workflow.resolve_active_payment_provider(
        settings=payment_settings,
        selected_provider=selected_provider_key,
    )

    promptpay_number = str(payment_settings.get("promptpay_number") or "").strip()
    promptpay_account_name = str(payment_settings.get("promptpay_account_name") or "").strip()
    truemoney_phone = str(payment_settings.get("truemoney_phone") or "").strip()
    truemoney_gift_phone = str(payment_settings.get("truemoney_gift_phone") or "").strip()
    truemoney_gift_url = str(payment_settings.get("truemoney_gift_url") or "").strip()
    truemoney_auto_enabled = bool(payment_settings.get("enable_truemoney_qr_provider", True))
    slip_verify_engine_name = _slip_verify_engine_name(payment_settings)
    promptpay_display_phone = promptpay_number

    provider_ready_cache: dict[str, tuple[bool, str]] = {}

    def _provider_readiness(provider_submit_key: str) -> tuple[bool, str]:
        key = _normalize_provider_name(provider_submit_key) or "promptpay"
        if key in provider_ready_cache:
            return provider_ready_cache[key]
        ready, _provider, issues = billing_workflow.validate_payment_provider_settings(
            settings=payment_settings,
            mode="topup",
            provider_type=key,
        )
        issue = str(issues[0]) if issues else ""
        provider_ready_cache[key] = (bool(ready), issue)
        return provider_ready_cache[key]

    channel_rows: list[dict[str, Any]] = []

    def _push_channel(
        *,
        channel_id: str,
        provider_key: str,
        title: str,
        subtitle: str,
        icon_text: str,
        badge: str,
        preview_kind: str,
        preview_value: str,
        required_fields: list[str],
    ) -> None:
        ready, issue = _provider_readiness(provider_key)
        channel_rows.append(
            {
                "channel_id": channel_id,
                "provider_key": provider_key,
                "title": title,
                "subtitle": subtitle,
                "icon_text": icon_text,
                "badge": badge,
                "ready": bool(ready),
                "issue": issue,
                "preview_kind": preview_kind,
                "preview_value": preview_value,
                "required_fields": list(required_fields or []),
            }
        )

    promptpay_required_fields = ["ยอดเติมเงิน (ขั้นต่ำ 10 THB)"]
    if promptpay_account_name:
        promptpay_required_fields.append(f"ชื่อผู้รับ: {promptpay_account_name}")
    if promptpay_display_phone:
        promptpay_required_fields.append(f"หมายเลข PromptPay: {promptpay_display_phone}")
    else:
        promptpay_required_fields.append("ยังไม่ได้ตั้งค่า PromptPay Number")

    truemoney_required_fields = ["ยอดเติมเงิน (ขั้นต่ำ 10 THB)"]
    if truemoney_gift_phone:
        truemoney_required_fields.append(f"TrueMoney Gift Phone: {truemoney_gift_phone}")
    truemoney_gift_required_fields = list(truemoney_required_fields)
    truemoney_gift_required_fields.append("ลิงก์ของขวัญ TrueMoney Gift Link")

    _push_channel(
        channel_id="promptpay",
        provider_key="promptpay",
        title="พร้อมเพย์ QR (PromptPay QR)",
        subtitle=(
            f"{promptpay_account_name} ({promptpay_display_phone})"
            if promptpay_account_name
            else (f"Phone: {promptpay_display_phone}" if promptpay_display_phone else "Not configured")
        ),
        icon_text="PP",
        badge="Always ON",
        preview_kind="promptpay_number",
        preview_value=promptpay_display_phone,
        required_fields=promptpay_required_fields,
    )
    _push_channel(
        channel_id="truewallet",
        provider_key="truemoney",
        title="ทรูมันนี่ Auto QR (TrueMoney Auto QR)",
        subtitle=(
            "Auto QR + auto verify"
            if truemoney_auto_enabled
            else f"Manual verify via {slip_verify_engine_name}"
        ),
        icon_text="TW",
        badge="Admin Enabled",
        preview_kind="promptpay_number",
        preview_value=truemoney_phone,
        required_fields=truemoney_required_fields,
    )
    _push_channel(
        channel_id="truegift",
        provider_key="promptpay",
        title="ลิงก์ของขวัญทรูมันนี่ (TrueMoney Gift Link)",
        subtitle="No QR needed, verify by gift link",
        icon_text="TG",
        badge="Gift Link",
        preview_kind="none",
        preview_value="",
        required_fields=truemoney_gift_required_fields,
    )

    any_ready_provider = any(bool(item.get("ready")) for item in channel_rows)
    active_channel = next((item for item in channel_rows if item.get("provider_key") == active_provider_key), None)
    if not active_channel:
        active_channel = next((item for item in channel_rows if item.get("ready")), None)
    if not active_channel and channel_rows:
        active_channel = channel_rows[0]
    default_channel_id = str((active_channel or {}).get("channel_id") or "promptpay")
    default_provider_key = str((active_channel or {}).get("provider_key") or "promptpay")
    default_provider_name = str((active_channel or {}).get("title") or "Promptpay")
    default_provider_ready = bool((active_channel or {}).get("ready"))
    default_provider_issue = str((active_channel or {}).get("issue") or "")
    default_provider_subtitle = str((active_channel or {}).get("subtitle") or "")
    default_required_fields = [
        str(label).strip()
        for label in list((active_channel or {}).get("required_fields") or [])
        if str(label).strip()
    ]
    if not default_required_fields:
        default_required_fields = ["ยอดเติมเงิน (ขั้นต่ำ 10 THB)"]
    default_required_fields_markup = "".join(
        f"<li>{_escape(label)}</li>"
        for label in default_required_fields
    )

    provider_notice_items: list[str] = []
    if not topup_ready:
        provider_notice_items.append(topup_ready_message or "Topup provider is not fully configured.")
    elif topup_ready_message:
        provider_notice_items.append(topup_ready_message)
    if provider_fallback_note and provider_fallback_note not in " ; ".join(provider_notice_items):
        provider_notice_items.append(provider_fallback_note)
    provider_notice_markup = "".join(
        f'<div class="notice">{_escape(item)}</div>'
        for item in provider_notice_items
        if str(item or "").strip()
    )

    channel_markup_items: list[str] = []
    for item in channel_rows:
        channel_id = str(item.get("channel_id") or "")
        ready = bool(item.get("ready"))
        selected_class = " is-selected" if channel_id == default_channel_id else ""
        disabled_class = "" if ready else " is-disabled"
        status_text = "พร้อมใช้งาน" if ready else "ยังไม่พร้อม"
        badge_text = str(item.get("badge") or "")
        issue_text = str(item.get("issue") or "")
        required_fields = [
            str(label).strip()
            for label in list(item.get("required_fields") or [])
            if str(label).strip()
        ]
        required_fields_attr = " | ".join(required_fields)
        channel_markup_items.append(
            f"""
            <button
              type="button"
              class="wallet-mbp-channel{selected_class}{disabled_class}"
              data-channel-id="{_escape(channel_id)}"
              data-provider-key="{_escape(str(item.get('provider_key') or 'promptpay'))}"
              data-provider-name="{_escape(str(item.get('title') or ''))}"
              data-provider-subtitle="{_escape(str(item.get('subtitle') or ''))}"
              data-provider-ready="{'1' if ready else '0'}"
              data-provider-issue="{_escape(issue_text)}"
              data-preview-kind="{_escape(str(item.get('preview_kind') or ''))}"
              data-preview-value="{_escape(str(item.get('preview_value') or ''))}"
              data-required-fields="{_escape(required_fields_attr)}"
            >
              <span class="wallet-mbp-channel-radio" aria-hidden="true"></span>
              <span class="wallet-mbp-channel-icon">{_escape(str(item.get('icon_text') or ''))}</span>
              <span class="wallet-mbp-channel-copy">
                <strong>{_escape(str(item.get('title') or ''))}</strong>
                <small>{_escape(str(item.get('subtitle') or ''))}</small>
              </span>
              <span class="wallet-mbp-channel-meta">
                <em>{_escape(badge_text)}</em>
                <b>{_escape(status_text)}</b>
              </span>
            </button>
            """
        )
    channels_markup = "".join(channel_markup_items)

    pending_card_markup = ""
    pending_session_key_for_poll = ""
    pending_live_poll_enabled = False
    pending_expires_at_epoch_ms = 0
    if pending_session:
        session_key = str(pending_session.get("session_key") or "").strip()
        verify_notice = _session_verify_notice(pending_session, payment_settings)
        manual_verify_allowed = _session_manual_verify_allowed(pending_session, payment_settings)
        amount_text = _format_money(pending_session.get("amount"))
        expires_text = _fmt_dt(pending_session.get("expires_at"))
        expires_dt = _as_utc_datetime(pending_session.get("expires_at"))
        if expires_dt:
            pending_expires_at_epoch_ms = max(0, int(expires_dt.timestamp() * 1000))
        pending_session_key_for_poll = session_key
        pending_live_poll_enabled = _session_live_status_enabled(pending_session, payment_settings)
        qr_image = str(pending_session.get("qr_image_url") or "").strip()
        provider_type = _normalize_provider_name(pending_session.get("provider_type")) or "promptpay"
        provider_name_map = {
            "promptpay": "PromptPay QR",
            "truemoney": "TrueMoney Auto QR",
        }
        provider_text = provider_name_map.get(provider_type, "PromptPay / TrueMoney")
        verify_form_markup = ""
        if manual_verify_allowed:
            gift_link_row = ""
            if provider_type in {"truemoney", "promptpay"}:
                gift_link_row = """
              <label class="switch-row">
                <span>TrueMoney Gift Link (optional)</span>
                <input type="url" name="gift_link" placeholder="https://gift.truemoney.com/campaign/?v=...">
              </label>
                """
            verify_form_markup = f"""
            <form id="walletPendingVerifyForm" method="post" action="/dashboard/topurp/verify" enctype="multipart/form-data" class="settings-grid wallet-mbp-pending-verify">
              <input type="hidden" name="session_key" value="{_escape(session_key)}">
              <label class="switch-row">
                <span>Transfer reference (optional)</span>
                <input type="text" name="transfer_reference" placeholder="UTR / Txn ID / Ref">
              </label>
              {gift_link_row}
              <label class="switch-row">
                <span>Upload slip image (optional)</span>
                <input type="file" name="slip_image_file" accept="image/png,image/jpeg,image/webp,image/gif">
              </label>
              <p class="muted" style="margin:0;">ระบบจะอัปโหลดรูปสลิปให้เป็น URL อัตโนมัติก่อนส่งตรวจสอบ {_escape(slip_verify_engine_name)}</p>
              <label class="switch-row">
                <span>Slip QR payload (optional)</span>
                <input type="text" name="slip_qr_payload" placeholder="Paste QR payload from bank slip">
              </label>
              <div class="auth-actions" style="justify-content:flex-start;">
                <button class="primary-btn" type="submit">Verify With {_escape(slip_verify_engine_name)}</button>
              </div>
            </form>
            """
        pending_card_markup = f"""
        <section class="panel page-shell page-wallet-shell wallet-mbp-pending-shell">
          <div class="wallet-mbp-wrap">
            <div class="wallet-mbp-pending-card">
              <div class="wallet-mbp-pending-head">
                <div>
                  <h3>รายการค้างชำระ</h3>
                  <p class="wallet-mbp-pending-sub">ชำระเงินและยืนยันรายการก่อนหมดเวลา</p>
                </div>
                <span id="walletPendingStatusBadge" class="wallet-v2-status-badge is-pending">Pending</span>
              </div>
              <div class="wallet-mbp-pending-grid" data-wallet-pending-session="1">
                <div class="wallet-mbp-pending-qr-wrap">
                  {f'<img class="wallet-v2-pending-qr" src="{_escape(qr_image)}" alt="Topup QR">' if qr_image else '<div class="wallet-empty">No QR image available</div>'}
                </div>
                <div class="wallet-mbp-pending-info">
                  <p id="walletPendingSessionCode" class="wallet-mbp-session-code">#{_escape(session_key[:24])}</p>
                  <div class="wallet-mbp-chip-row">
                    <span class="wallet-mbp-chip">Provider: {_escape(provider_text)}</span>
                    <span class="wallet-mbp-chip">Amount: {_escape(amount_text)} THB</span>
                    <span class="wallet-mbp-chip">Expires: {_escape(expires_text)}</span>
                  </div>
                  <div class="wallet-v2-countdown-row">
                    <span>เวลาที่เหลือ</span>
                    <strong id="walletPendingCountdown">--:--</strong>
                  </div>
                  <div class="wallet-mbp-pending-actions">
                    <button id="walletPendingCopyBtn" class="ghost-btn wallet-mbp-copy-btn" type="button">คัดลอกรหัสรายการ</button>
                  </div>
                  <p id="walletPendingVerifyNote" class="wallet-v2-verify-note">{_escape(verify_notice)}</p>
                </div>
              </div>
              {verify_form_markup}
            </div>
          </div>
        </section>
        """

    topup_history_rows: list[str] = []
    paid_total = 0.0
    paid_count = 0
    pending_count = 0
    for row in topup_rows:
        status_value = str(row.get("status") or "").strip().lower()
        if status_value == "pending":
            pending_count += 1
        if status_value == "paid":
            paid_count += 1
            try:
                paid_total += float(row.get("amount") or 0.0)
            except Exception:
                pass
    for row in topup_rows[:20]:
        topup_history_rows.append(
            f"""
            <tr>
              <td><code>{_escape(str(row.get('session_key') or '')[:16])}</code></td>
              <td>{_escape(_format_money(row.get('amount')))} THB</td>
              <td>{_escape(str(row.get('status') or '-'))}</td>
              <td>{_escape(_fmt_dt(row.get('created_at')))}</td>
            </tr>
            """
        )
    if not topup_history_rows:
        topup_history_rows.append('<tr><td colspan="4" class="muted">No payment history yet.</td></tr>')

    pending_session_key_json = json.dumps(pending_session_key_for_poll)
    pending_live_poll_enabled_json = json.dumps(bool(pending_live_poll_enabled))
    pending_expires_at_epoch_ms_json = json.dumps(int(pending_expires_at_epoch_ms or 0))
    any_ready_provider_json = json.dumps(bool(any_ready_provider))

    return f"""
    {notice_markup}
    {provider_notice_markup}

    <style id="wallet-page-v5">
      .wallet-mbp-shell {{
        margin-top: 14px;
        border-radius: 20px;
        border: 1px solid rgba(125, 160, 248, 0.28);
        background:
          radial-gradient(circle at 8% -8%, rgba(94, 170, 255, 0.28), transparent 36%),
          radial-gradient(circle at 95% 8%, rgba(98, 226, 255, 0.19), transparent 32%),
          linear-gradient(152deg, #151d34 0%, #0f1629 58%, #121c34 100%);
        box-shadow: 0 24px 58px rgba(4, 8, 20, 0.44);
        overflow: hidden;
      }}
      .wallet-mbp-wrap {{
        max-width: 1280px;
        margin: 0 auto;
        padding: 22px;
      }}
      .wallet-mbp-card {{
        border: 1px solid rgba(146, 176, 236, 0.24);
        border-radius: 18px;
        overflow: hidden;
        display: grid;
        grid-template-columns: minmax(0, 1.55fr) minmax(340px, 0.9fr);
        background: linear-gradient(180deg, rgba(11, 16, 30, 0.98), rgba(8, 12, 24, 1));
      }}
      .wallet-mbp-left {{
        padding: 28px 30px;
        display: grid;
        gap: 14px;
      }}
      .wallet-mbp-right {{
        padding: 28px;
        border-left: 1px solid rgba(146, 176, 236, 0.2);
        display: grid;
        gap: 13px;
        align-content: start;
        background: linear-gradient(180deg, rgba(18, 24, 43, 0.97), rgba(10, 14, 26, 1));
      }}
      .wallet-mbp-brand {{
        margin: 0;
        color: #f0f6ff;
        font-size: 0.88rem;
        letter-spacing: 0.16em;
        font-weight: 900;
      }}
      .wallet-mbp-steps {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .wallet-mbp-steps span {{
        min-height: 32px;
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        border: 1px solid rgba(132, 160, 221, 0.44);
        background: rgba(27, 35, 59, 0.63);
        color: #b7c7e9;
        padding: 4px 12px;
        font-size: 0.78rem;
        font-weight: 700;
      }}
      .wallet-mbp-steps span.is-active {{
        border-color: rgba(245, 210, 154, 0.77);
        background: rgba(83, 62, 27, 0.42);
        color: #ffe2b9;
      }}
      .wallet-mbp-steps span.is-done {{
        border-color: rgba(136, 230, 185, 0.68);
        background: rgba(20, 77, 55, 0.38);
        color: #ccffe8;
      }}
      .wallet-mbp-left h2 {{
        margin: 0;
        color: #f4f8ff;
        font-size: clamp(1.6rem, 2.5vw, 2.15rem);
        line-height: 1.08;
      }}
      .wallet-mbp-left h3 {{
        margin: 2px 0 0;
        color: #dbe6ff;
        font-size: 1.06rem;
      }}
      .wallet-mbp-left .muted {{
        color: #9fb2dc;
      }}
      .wallet-mbp-pane {{
        display: none;
        gap: 12px;
      }}
      .wallet-mbp-pane.is-active {{
        display: grid;
      }}
      .wallet-mbp-pane-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .wallet-mbp-pane-actions .ghost-btn,
      .wallet-mbp-pane-actions .primary-btn {{
        min-height: 38px;
        border-radius: 10px;
        font-weight: 700;
      }}
      .wallet-mbp-back-btn,
      .wallet-mbp-terms-btn {{
        min-height: 40px;
        border-radius: 11px;
        font-weight: 700;
      }}
      .wallet-mbp-agreement-box,
      .wallet-mbp-amount-box {{
        border: 1px solid rgba(130, 156, 216, 0.3);
        background: rgba(13, 20, 36, 0.9);
        border-radius: 14px;
        padding: 12px;
      }}
      .wallet-mbp-agreement-box {{
        display: grid;
        gap: 10px;
      }}
      .wallet-mbp-agreement-actions {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }}
      .wallet-mbp-agree-row {{
        display: flex;
        align-items: flex-start;
        gap: 10px;
        width: fit-content;
        max-width: 100%;
        color: #dbe5ff;
        font-size: 0.9rem;
      }}
      .wallet-mbp-agree-row input[type="checkbox"] {{
        appearance: auto !important;
        -webkit-appearance: checkbox !important;
        width: 18px !important;
        height: 18px !important;
        min-width: 18px;
        max-width: 18px;
        margin: 2px 0 0;
        flex: 0 0 18px;
        position: static !important;
        transform: none !important;
        accent-color: #7ea6ff;
      }}
      .wallet-mbp-agree-row span {{
        display: block;
        line-height: 1.45;
        word-break: break-word;
      }}
      .wallet-mbp-agree-help {{
        margin: 0;
        min-height: 1.2em;
        color: #f4bc90;
        font-size: 0.8rem;
      }}
      .wallet-mbp-agree-help.is-ok {{
        color: #98f0c7;
      }}
      .wallet-mbp-payment-gate {{
        display: grid;
        gap: 13px;
        transition: opacity .15s ease, filter .15s ease;
      }}
      .wallet-mbp-payment-gate.is-locked {{
        opacity: 0.55;
        filter: saturate(0.68);
      }}
      .wallet-mbp-payment-gate.is-locked .wallet-mbp-channel,
      .wallet-mbp-payment-gate.is-locked .wallet-mbp-quick-btn {{
        pointer-events: none;
      }}
      .wallet-mbp-quick-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .wallet-mbp-quick-btn {{
        min-width: 60px;
        min-height: 35px;
        border-radius: 10px;
        border: 1px solid rgba(138, 166, 228, 0.42);
        background: #1d2742;
        color: #e7efff;
        font-weight: 700;
      }}
      .wallet-mbp-quick-btn:disabled {{
        opacity: 0.6;
        cursor: not-allowed;
      }}
      .wallet-mbp-channel-list {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }}
      .wallet-mbp-channel {{
        min-height: 94px;
        border: 1px solid rgba(129, 156, 215, 0.35);
        border-radius: 13px;
        background: #0f172c;
        width: 100%;
        padding: 12px;
        display: grid;
        grid-template-columns: auto auto minmax(0, 1fr) auto;
        align-items: center;
        gap: 10px;
        text-align: left;
      }}
      .wallet-mbp-channel.is-selected {{
        border-color: #8fb0ff;
        background: #162241;
      }}
      .wallet-mbp-channel.is-disabled {{
        opacity: 0.58;
      }}
      .wallet-mbp-channel-radio {{
        width: 20px;
        height: 20px;
        border-radius: 999px;
        border: 2px solid #6376a6;
        background: #111931;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }}
      .wallet-mbp-channel.is-selected .wallet-mbp-channel-radio {{
        border-color: #8fb0ff;
      }}
      .wallet-mbp-channel.is-selected .wallet-mbp-channel-radio::after {{
        content: "";
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #a8beff;
        display: block;
      }}
      .wallet-mbp-channel-icon {{
        width: 38px;
        height: 38px;
        border-radius: 10px;
        border: 1px solid rgba(145, 173, 236, 0.38);
        background: #223764;
        color: #eef4ff;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8rem;
        font-weight: 800;
      }}
      .wallet-mbp-channel-copy {{
        display: grid;
        gap: 3px;
        min-width: 0;
      }}
      .wallet-mbp-channel-copy strong {{
        color: #f1f6ff;
      }}
      .wallet-mbp-channel-copy small {{
        color: #9db1dc;
        line-height: 1.35;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .wallet-mbp-channel-meta {{
        display: grid;
        gap: 4px;
        justify-items: end;
      }}
      .wallet-mbp-channel-meta em {{
        border: 1px solid rgba(132, 157, 216, 0.4);
        border-radius: 999px;
        color: #b8c7e8;
        font-style: normal;
        font-size: 0.71rem;
        padding: 2px 8px;
      }}
      .wallet-mbp-channel-meta b {{
        color: #9ff4c7;
        font-size: 0.75rem;
      }}
      .wallet-mbp-channel.is-disabled .wallet-mbp-channel-meta b {{
        color: #ffb0b0;
      }}
      .wallet-mbp-gift-help {{
        border: 1px solid rgba(148, 170, 230, 0.34);
        border-radius: 13px;
        background: linear-gradient(160deg, rgba(22, 35, 64, 0.92), rgba(14, 23, 42, 0.96));
        padding: 12px;
        display: grid;
        gap: 8px;
      }}
      .wallet-mbp-gift-head {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
      }}
      .wallet-mbp-gift-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 46px;
        min-height: 24px;
        border-radius: 999px;
        border: 1px solid rgba(245, 208, 144, 0.55);
        background: rgba(92, 64, 20, 0.42);
        color: #ffdca8;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.04em;
      }}
      .wallet-mbp-gift-head strong {{
        color: #f7e4c2;
        font-size: 0.94rem;
      }}
      .wallet-mbp-gift-help p {{
        margin: 0;
        color: #a9bddf;
        font-size: 0.83rem;
        line-height: 1.45;
      }}
      .wallet-mbp-gift-help .muted.ok {{
        color: #91f2bf;
      }}
      .wallet-mbp-gift-help .muted.warn {{
        color: #ffb8b8;
      }}
      .wallet-mbp-gift-help code {{
        border-radius: 9px;
        border: 1px solid rgba(148, 170, 230, 0.4);
        background: rgba(12, 20, 37, 0.84);
        color: #d9e7ff;
        padding: 6px 8px;
        font-size: 0.78rem;
        overflow-x: auto;
      }}
      .wallet-mbp-pay-box {{
        border: 1px solid rgba(138, 166, 231, 0.3);
        border-radius: 14px;
        background: rgba(12, 20, 37, 0.88);
        padding: 14px;
        display: grid;
        gap: 12px;
      }}
      .wallet-mbp-pay-head {{
        display: grid;
        gap: 2px;
      }}
      .wallet-mbp-pay-head strong {{
        color: #f2f7ff;
        font-size: 1.02rem;
      }}
      .wallet-mbp-pay-head small {{
        color: #a6bce6;
      }}
      .wallet-mbp-pay-qr-wrap {{
        border: 1px solid rgba(138, 166, 231, 0.28);
        border-radius: 13px;
        background: rgba(15, 23, 42, 0.9);
        min-height: 220px;
        display: grid;
        place-items: center;
        padding: 10px;
      }}
      .wallet-mbp-pay-qr {{
        width: min(100%, 240px);
        max-width: 240px;
        border-radius: 12px;
        border: 1px solid rgba(132, 160, 221, 0.4);
        background: #ffffff;
        padding: 8px;
      }}
      .wallet-mbp-required-box {{
        border: 1px solid rgba(138, 166, 231, 0.28);
        border-radius: 12px;
        background: rgba(14, 22, 40, 0.78);
        padding: 10px 12px;
        display: grid;
        gap: 8px;
      }}
      .wallet-mbp-required-title {{
        margin: 0;
        color: #c8d8fb;
        font-size: 0.84rem;
        font-weight: 700;
      }}
      .wallet-mbp-required-list {{
        margin: 0;
        padding: 0 0 0 18px;
        display: grid;
        gap: 5px;
        color: #e7efff;
        font-size: 0.86rem;
      }}
      .wallet-mbp-required-list li {{
        line-height: 1.4;
      }}
      .wallet-mbp-summary-head {{
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 12px;
        align-items: center;
      }}
      .wallet-mbp-summary-icon {{
        width: 52px;
        height: 52px;
        border-radius: 999px;
        border: 1px solid rgba(136, 164, 227, 0.4);
        background: rgba(31, 43, 72, 0.78);
        color: #ffe0b8;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.08rem;
        font-weight: 800;
      }}
      .wallet-mbp-summary-head h3 {{
        color: #ffdcb2;
      }}
      .wallet-mbp-summary-head p {{
        color: #9eb0da;
      }}
      .wallet-mbp-summary-list {{
        display: grid;
        gap: 9px;
      }}
      .wallet-mbp-summary-list > div {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
      }}
      .wallet-mbp-summary-list span {{
        color: #97abd9;
        font-size: 0.93rem;
      }}
      .wallet-mbp-summary-list strong {{
        color: #eef4ff;
        font-size: 1.02rem;
        text-align: right;
      }}
      .wallet-mbp-total-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }}
      .wallet-mbp-total-row span {{
        color: #9eb0da;
      }}
      .wallet-mbp-total-row strong {{
        color: #f8fbff;
      }}
      .wallet-mbp-submit-btn {{
        min-height: 56px;
        border-radius: 13px;
        font-size: 1.08rem;
        font-weight: 800;
      }}
      .wallet-mbp-submit-note {{
        color: #f3aaa4;
      }}
      .wallet-mbp-pending-shell {{
        margin-top: 14px;
      }}
      .wallet-mbp-pending-card {{
        border: 1px solid rgba(136, 164, 227, 0.28);
        border-radius: 18px;
        background: linear-gradient(155deg, rgba(17, 24, 42, 0.98), rgba(11, 16, 30, 0.98));
        padding: 16px;
      }}
      .wallet-mbp-pending-head {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 10px;
        margin-bottom: 10px;
      }}
      .wallet-mbp-pending-head h3 {{
        margin: 0;
      }}
      .wallet-mbp-pending-sub {{
        margin: 4px 0 0;
        color: #9fb2dc;
        font-size: 0.86rem;
      }}
      .wallet-mbp-pending-grid {{
        display: grid;
        gap: 14px;
        grid-template-columns: minmax(220px, 250px) minmax(0, 1fr);
      }}
      .wallet-mbp-pending-qr-wrap {{
        display: grid;
        place-items: center;
      }}
      .wallet-mbp-pending-info {{
        display: grid;
        gap: 8px;
      }}
      .wallet-mbp-session-code {{
        margin: 0;
        display: inline-flex;
        align-items: center;
        width: fit-content;
        border-radius: 999px;
        border: 1px solid rgba(145, 176, 241, 0.45);
        background: rgba(23, 34, 58, 0.7);
        color: #e8f1ff;
        padding: 4px 10px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        font-size: 0.78rem;
      }}
      .wallet-mbp-chip-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .wallet-mbp-chip {{
        border: 1px solid rgba(138, 166, 231, 0.36);
        border-radius: 999px;
        background: rgba(22, 34, 58, 0.66);
        color: #d9e8ff;
        padding: 5px 10px;
        font-size: 0.77rem;
      }}
      .wallet-mbp-pending-actions {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }}
      .wallet-mbp-copy-btn {{
        min-height: 38px;
        border-radius: 10px;
      }}
      .wallet-mbp-pending-verify {{
        margin-top: 12px;
      }}
      .wallet-mbp-history-shell {{
        margin-top: 14px;
      }}
      .wallet-history-toggle {{
        border: 1px solid rgba(133, 161, 223, 0.26);
        border-radius: 16px;
        background: linear-gradient(165deg, rgba(18, 28, 50, 0.95), rgba(12, 20, 38, 0.96));
        padding: 12px 14px;
      }}
      .wallet-history-head {{
        list-style: none;
        cursor: pointer;
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 8px;
      }}
      .wallet-history-head::-webkit-details-marker {{
        display: none;
      }}
      .wallet-history-head span {{
        color: #ecf4ff;
        font-weight: 700;
      }}
      .wallet-history-head small {{
        color: #9ab0de;
      }}
      .wallet-v2-status-badge {{
        border: 1px solid rgba(123, 152, 216, 0.5);
        border-radius: 999px;
        background: rgba(26, 40, 68, 0.72);
        color: #d9e8ff;
        font-size: 0.76rem;
        font-weight: 700;
        padding: 5px 10px;
        text-transform: uppercase;
        letter-spacing: 0.03em;
      }}
      .wallet-v2-status-badge.is-paid {{
        border-color: rgba(130, 227, 181, 0.6);
        color: #a9ffd4;
      }}
      .wallet-v2-status-badge.is-closed {{
        border-color: rgba(255, 161, 161, 0.58);
        color: #ffc5c5;
      }}
      .wallet-v2-pending-qr {{
        width: min(100%, 250px);
        max-width: 250px;
        height: auto;
        border-radius: 14px;
        border: 1px solid rgba(131, 159, 220, 0.35);
        background: #fff;
        padding: 8px;
      }}
      .wallet-v2-countdown-row {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
        border: 1px solid rgba(127, 156, 219, 0.28);
        border-radius: 10px;
        background: rgba(20, 31, 54, 0.7);
        padding: 8px 10px;
      }}
      .wallet-v2-countdown-row span {{
        color: #a8bce6;
        font-size: 0.84rem;
      }}
      .wallet-v2-countdown-row strong {{
        color: #edf4ff;
        font-size: 1.12rem;
      }}
      .wallet-v2-verify-note {{
        margin: 0;
        color: #f3b6b0;
      }}
      .wallet-empty {{
        border: 1px dashed rgba(132, 161, 224, 0.45);
        border-radius: 12px;
        color: #afc2e7;
        min-height: 190px;
        width: min(100%, 250px);
        display: grid;
        place-items: center;
        text-align: center;
        padding: 16px;
      }}
      @media (max-width: 1120px) {{
        .wallet-mbp-card {{
          grid-template-columns: minmax(0, 1fr);
        }}
        .wallet-mbp-right {{
          border-left: 0;
          border-top: 1px solid rgba(146, 176, 236, 0.2);
        }}
      }}
      @media (max-width: 840px) {{
        .wallet-mbp-wrap {{
          padding: 12px;
        }}
        .wallet-mbp-left,
        .wallet-mbp-right {{
          padding: 18px;
        }}
        .wallet-mbp-channel-list {{
          grid-template-columns: minmax(0, 1fr);
        }}
        .wallet-mbp-channel {{
          grid-template-columns: auto auto minmax(0, 1fr);
        }}
        .wallet-mbp-channel-meta {{
          grid-column: 2 / -1;
          justify-items: start;
          grid-auto-flow: column;
          align-items: center;
        }}
        .wallet-mbp-pending-grid {{
          grid-template-columns: minmax(0, 1fr);
        }}
      }}
    </style>

    <section class="wallet-mbp-shell page-wallet-shell">
      <div class="wallet-mbp-wrap">
        <div class="wallet-mbp-card">
          <div class="wallet-mbp-left">
            <p class="wallet-mbp-brand">SKYLINEBOT</p>
            <div class="wallet-mbp-steps">
              <span id="walletMbpStepAgreement" class="is-active">1. ยอมรับข้อตกลง</span>
              <span id="walletMbpStepPayment">2. เลือกช่องทางชำระเงิน</span>
              <span id="walletMbpStepPay">3. ชำระเงิน</span>
            </div>

            <h2>เลือกช่องทางการเติมเงิน</h2>
            <p class="muted">เปิดและยอมรับข้อตกลงก่อนสร้างรายการเติมเงิน</p>

            <a class="ghost-btn wallet-mbp-back-btn" href="/wallet">กลับหน้า Wallet</a>

            <div id="walletMbpPaneAgreement" class="wallet-mbp-pane is-active">
              <div class="wallet-mbp-agreement-box">
                <h3>ข้อตกลงการใช้งาน</h3>
                <p class="muted">กรุณาอ่านเงื่อนไขก่อนชำระเงิน หากไม่ยอมรับ ระบบจะยังไม่เปิดช่องทางชำระเงิน</p>
                <div class="wallet-mbp-agreement-actions">
                  <a
                    id="walletMbpOpenTermsBtn"
                    class="ghost-btn wallet-mbp-terms-btn"
                    href="/terms"
                    target="_blank"
                    rel="noopener"
                  >เปิดเงื่อนไข</a>
                </div>
                <label class="wallet-mbp-agree-row">
                  <input id="walletMbpAgreeCheckbox" type="checkbox" name="agreement_accepted_checkbox" value="1" form="walletMbpCreateForm">
                  <span>ฉันได้อ่านและยอมรับข้อตกลงแล้ว</span>
                </label>
                <p id="walletMbpAgreementHelp" class="wallet-mbp-agree-help">กรุณาเปิดหน้าเงื่อนไขก่อน</p>
              </div>
              <div class="wallet-mbp-pane-actions">
                <button id="walletMbpToPaymentBtn" class="primary-btn" type="button">ถัดไป: เลือกช่องทางชำระเงิน</button>
              </div>
            </div>

            <div id="walletMbpPanePayment" class="wallet-mbp-pane">
                <div id="walletMbpPaymentGate" class="wallet-mbp-payment-gate is-locked">
                <div class="wallet-mbp-amount-box">
                  <label class="switch-row">
                    <span>Amount (THB)</span>
                    <input id="walletMbpAmountInput" type="number" min="10" step="0.01" placeholder="ex. 50.00"{' disabled' if not any_ready_provider else ''}>
                  </label>
                  <div class="wallet-mbp-quick-row">
                    <button type="button" class="wallet-mbp-quick-btn" data-amount="50">50</button>
                    <button type="button" class="wallet-mbp-quick-btn" data-amount="100">100</button>
                    <button type="button" class="wallet-mbp-quick-btn" data-amount="250">250</button>
                    <button type="button" class="wallet-mbp-quick-btn" data-amount="500">500</button>
                  </div>
                </div>

                <h3>ช่องทางชำระเงิน</h3>
                <div id="walletMbpChannels" class="wallet-mbp-channel-list">
                  {channels_markup}
                </div>
              </div>
              <div class="wallet-mbp-pane-actions">
                <button id="walletMbpBackToAgreementBtn" class="ghost-btn" type="button">ย้อนกลับ</button>
                <button id="walletMbpToPayBtn" class="primary-btn" type="button">ถัดไป: ชำระเงิน</button>
              </div>
            </div>

            <div id="walletMbpPanePay" class="wallet-mbp-pane">
              <div class="wallet-mbp-pay-box">
                <div class="wallet-mbp-pay-head">
                  <strong id="walletMbpPayTitle">{_escape(default_provider_name)}</strong>
                  <small id="walletMbpPaySubtitle">{_escape(default_provider_subtitle or '-')}</small>
                </div>
                <div class="wallet-mbp-pay-qr-wrap">
                  <img id="walletMbpPayQrImage" class="wallet-mbp-pay-qr" alt="Payment QR" hidden>
                  <div id="walletMbpPayQrEmpty" class="wallet-empty">กรุณากรอกยอดและเลือกช่องทางก่อน</div>
                </div>
                <div class="wallet-mbp-required-box">
                  <p class="wallet-mbp-required-title">ข้อมูลที่ต้องกรอกสำหรับช่องทางนี้</p>
                  <ul id="walletMbpRequiredList" class="wallet-mbp-required-list">{default_required_fields_markup}</ul>
                </div>
                <div id="walletMbpGiftHelp" class="wallet-mbp-gift-help" style="display:none;">
                  <div class="wallet-mbp-gift-head">
                    <span class="wallet-mbp-gift-badge">GIFT</span>
                    <strong>TrueMoney Gift Link (for TrueMoney only)</strong>
                  </div>
                  <p>เลือกช่องทาง TrueMoney Gift Link แล้ววางลิงก์ของขวัญเพื่อส่งตรวจสอบได้ทันที</p>
                  {f'<p style="margin:0;"><strong>Phone:</strong> {_escape(truemoney_gift_phone)}</p>' if truemoney_gift_phone else ''}
                  {f'<a href="{_escape(truemoney_gift_url)}" target="_blank" rel="noopener" style="color:#d9e7ff; text-decoration:underline; word-break:break-all;">{_escape(truemoney_gift_url)}</a>' if truemoney_gift_url else '<code>https://gift.truemoney.com/campaign/?v=...</code>'}
                </div>
                <div id="walletMbpGiftInputBox" class="wallet-mbp-gift-help" style="display:none;">
                  <label class="switch-row" style="margin:0;">
                    <span>TrueMoney Gift Link</span>
                    <input id="walletMbpGiftLinkInput" type="url" placeholder="https://gift.truemoney.com/campaign/?v=...">
                  </label>
                  <p id="walletMbpGiftInputHint" class="muted" style="margin:0;">วางลิงก์ของขวัญให้ถูกต้องก่อนกดสร้างรายการ</p>
                </div>
                <p id="walletMbpPayHint" class="muted" style="margin:0;">เลือกช่องทางและยอดเงิน ระบบจะแสดง QR สำหรับชำระเงินที่นี่</p>
              </div>

              <form id="walletMbpCreateForm" method="post" action="/dashboard/topurp">
                <input type="hidden" id="walletMbpProviderInput" name="provider_type" value="{_escape(default_provider_key)}">
                <input type="hidden" id="walletMbpAmountHidden" name="amount" value="">
                <input type="hidden" id="walletMbpGiftLinkHidden" name="gift_link" value="">
                <input type="hidden" id="walletMbpAgreementAccepted" name="agreement_accepted" value="">
                <input type="hidden" id="walletMbpAgreementOpened" name="agreement_opened" value="">
                <button id="walletMbpCreateBtn" class="primary-btn wallet-mbp-submit-btn" type="submit"{' disabled' if (not any_ready_provider or not default_provider_ready) else ''}>สร้างรายการเติมเงิน</button>
              </form>
              <p id="walletMbpSubmitNote" class="wallet-mbp-submit-note">{_escape(default_provider_issue or '')}</p>
              <div class="wallet-mbp-pane-actions">
                <button id="walletMbpBackToPaymentBtn" class="ghost-btn" type="button">ย้อนกลับ</button>
              </div>
            </div>
          </div>

          <div class="wallet-mbp-right">
            <div class="wallet-mbp-summary-head">
              <div class="wallet-mbp-summary-icon">$</div>
              <div>
                <h3 id="walletMbpSummaryProvider">{_escape(default_provider_name)}</h3>
                <p id="walletMbpSummarySubtitle">{_escape(default_provider_subtitle or '-')}</p>
              </div>
            </div>
            <hr>
            <div class="wallet-mbp-summary-list">
              <div><span>ยอดเติมเงิน</span><strong id="walletMbpSummaryAmount">0.00 THB</strong></div>
              <div><span>สถานะช่องทาง</span><strong id="walletMbpSummaryReady">{'พร้อมใช้งาน' if default_provider_ready else 'ยังไม่พร้อม'}</strong></div>
              <div><span>ยอดคงเหลือ Wallet</span><strong>{_escape(_format_money(balance))} THB</strong></div>
              <div><span>รายการสำเร็จ</span><strong>{_escape(str(paid_count))}</strong></div>
              <div><span>รายการค้างชำระ</span><strong>{_escape(str(pending_count))}</strong></div>
              <div><span>ปิด QR อัตโนมัติ</span><strong>เปิดใช้งาน</strong></div>
            </div>
            <hr>
            <div class="wallet-mbp-total-row">
              <span>รวม</span>
              <strong id="walletMbpTotalAmount">0.00 THB</strong>
            </div>
            <p class="muted" style="margin:0;">ใช้แถบซ้ายเพื่อทำครบทั้ง 3 ขั้น แล้วกดสร้างรายการเติมเงิน</p>
          </div>
        </div>
        {pending_card_markup}
      </div>
    </section>

    <section class="panel page-shell page-wallet-shell wallet-mbp-history-shell">
      <div class="wallet-mbp-wrap">
        <details class="wallet-history-toggle">
          <summary class="wallet-history-head">
            <span>ประวัติการเติมเงินล่าสุด</span>
            <small>20 รายการล่าสุด จากทั้งหมด {_escape(str(len(topup_rows)))}</small>
          </summary>
          <div class="wallet-table-wrap" style="overflow:auto; margin-top:10px;">
            <table class="audit-table">
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>{''.join(topup_history_rows)}</tbody>
            </table>
          </div>
        </details>
      </div>
    </section>

    <script>
      (() => {{
        const MIN_AMOUNT = 10;
        const amountInput = document.getElementById('walletMbpAmountInput');
        const amountHidden = document.getElementById('walletMbpAmountHidden');
        const providerInput = document.getElementById('walletMbpProviderInput');
        const createBtn = document.getElementById('walletMbpCreateBtn');
        const createForm = document.getElementById('walletMbpCreateForm');
        const summaryProvider = document.getElementById('walletMbpSummaryProvider');
        const summarySubtitle = document.getElementById('walletMbpSummarySubtitle');
        const summaryAmount = document.getElementById('walletMbpSummaryAmount');
        const summaryReady = document.getElementById('walletMbpSummaryReady');
        const totalAmount = document.getElementById('walletMbpTotalAmount');
        const submitNote = document.getElementById('walletMbpSubmitNote');
        const paymentGate = document.getElementById('walletMbpPaymentGate');
        const termsBtn = document.getElementById('walletMbpOpenTermsBtn');
        const agreeCheckbox = document.getElementById('walletMbpAgreeCheckbox');
        const agreementHelp = document.getElementById('walletMbpAgreementHelp');
        const agreementAcceptedInput = document.getElementById('walletMbpAgreementAccepted');
        const agreementOpenedInput = document.getElementById('walletMbpAgreementOpened');
        const stepAgreement = document.getElementById('walletMbpStepAgreement');
        const stepPayment = document.getElementById('walletMbpStepPayment');
        const stepPay = document.getElementById('walletMbpStepPay');
        const paneAgreement = document.getElementById('walletMbpPaneAgreement');
        const panePayment = document.getElementById('walletMbpPanePayment');
        const panePay = document.getElementById('walletMbpPanePay');
        const toPaymentBtn = document.getElementById('walletMbpToPaymentBtn');
        const toPayBtn = document.getElementById('walletMbpToPayBtn');
        const backToAgreementBtn = document.getElementById('walletMbpBackToAgreementBtn');
        const backToPaymentBtn = document.getElementById('walletMbpBackToPaymentBtn');
        const payTitle = document.getElementById('walletMbpPayTitle');
        const paySubtitle = document.getElementById('walletMbpPaySubtitle');
        const payHint = document.getElementById('walletMbpPayHint');
        const payQrImage = document.getElementById('walletMbpPayQrImage');
        const payQrEmpty = document.getElementById('walletMbpPayQrEmpty');
        const requiredList = document.getElementById('walletMbpRequiredList');
        const giftHelpBox = document.getElementById('walletMbpGiftHelp');
        const giftInputBox = document.getElementById('walletMbpGiftInputBox');
        const giftLinkInput = document.getElementById('walletMbpGiftLinkInput');
        const giftLinkHidden = document.getElementById('walletMbpGiftLinkHidden');
        const giftInputHint = document.getElementById('walletMbpGiftInputHint');
        const anyReadyProvider = {any_ready_provider_json};
        const hasPendingSession = Boolean({pending_session_key_json});
        const quickButtons = Array.from(document.querySelectorAll('.wallet-mbp-quick-btn[data-amount]'));

        const channels = Array.from(document.querySelectorAll('.wallet-mbp-channel'));
        let selectedChannel = channels.find((el) => el.classList.contains('is-selected')) || channels[0] || null;
        let termsOpened = false;
        let currentStep = hasPendingSession ? 3 : 1;

        const parseAmount = () => {{
          if (!amountInput) return 0;
          const value = Number(amountInput.value || 0);
          if (!Number.isFinite(value) || value <= 0) return 0;
          return value;
        }};

        const formatAmount = (value) => {{
          const safe = Number.isFinite(value) ? value : 0;
          return `${{safe.toLocaleString('en-US', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }})}} THB`;
        }};
        const escapeHtml = (value) => String(value || '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');

        const channelReady = (channelEl) => channelEl && channelEl.getAttribute('data-provider-ready') === '1';
        const channelIssue = (channelEl) => channelEl ? String(channelEl.getAttribute('data-provider-issue') || '').trim() : '';
        const agreementAccepted = () => Boolean(agreeCheckbox && agreeCheckbox.checked);
        const agreementReady = () => termsOpened && agreementAccepted();
        const parseChannelId = (channelEl) => String(channelEl?.getAttribute('data-channel-id') || '').trim().toLowerCase();
        const parseRequiredFields = (channelEl) => {{
          const raw = String(channelEl?.getAttribute('data-required-fields') || '').trim();
          if (!raw) return ['ยอดเติมเงิน (ขั้นต่ำ 10 THB)'];
          const items = raw
            .split('|')
            .map((value) => String(value || '').trim())
            .filter(Boolean);
          return items.length ? items : ['ยอดเติมเงิน (ขั้นต่ำ 10 THB)'];
        }};
        const parseGiftLink = () => String(giftLinkInput?.value || '').trim();
        const isValidTrueMoneyGiftLink = (value) => {{
          const link = String(value || '').trim();
          return !!link && /^https?:\\/\\/gift\\.truemoney\\.com\\/campaign\\/\\?v=[A-Za-z0-9_-]{{8,}}$/i.test(link);
        }};
        const syncGiftLinkField = () => {{
          if (!giftLinkHidden) return;
          const channelId = parseChannelId(selectedChannel);
          giftLinkHidden.value = channelId === 'truegift' ? parseGiftLink() : '';
        }};
        const renderGiftInputHint = () => {{
          if (!giftInputHint) return;
          const link = parseGiftLink();
          if (!link) {{
            giftInputHint.textContent = 'วางลิงก์ของขวัญให้ถูกต้องก่อนกดสร้างรายการ';
            giftInputHint.classList.remove('ok', 'warn');
            return;
          }}
          if (isValidTrueMoneyGiftLink(link)) {{
            giftInputHint.textContent = 'ลิงก์ถูกต้อง พร้อมส่งตรวจสอบอัตโนมัติ';
            giftInputHint.classList.remove('warn');
            giftInputHint.classList.add('ok');
            return;
          }}
          giftInputHint.textContent = 'ลิงก์ไม่ถูกต้อง ต้องเป็น gift.truemoney.com/campaign/?v=...';
          giftInputHint.classList.remove('ok');
          giftInputHint.classList.add('warn');
        }};

        const buildPromptPayPreviewUrl = (phoneNumber, amount) => {{
          const clean = String(phoneNumber || '').replace(/\\D+/g, '');
          if (!clean) return '';
          const safeAmount = Number.isFinite(amount) && amount >= MIN_AMOUNT ? amount.toFixed(2) : '';
          return safeAmount
            ? `https://promptpay.io/${{encodeURIComponent(clean)}}/${{encodeURIComponent(safeAmount)}}.png`
            : `https://promptpay.io/${{encodeURIComponent(clean)}}.png`;
        }};

        const syncAgreementFields = () => {{
          const accepted = agreementAccepted();
          if (agreementAcceptedInput) agreementAcceptedInput.value = accepted ? '1' : '';
          if (agreementOpenedInput) agreementOpenedInput.value = termsOpened ? '1' : '';
        }};

        const renderStepState = () => {{
          const steps = [stepAgreement, stepPayment, stepPay];
          steps.forEach((node, index) => {{
            if (!node) return;
            const stepNo = index + 1;
            node.classList.toggle('is-active', stepNo === currentStep);
            node.classList.toggle('is-done', stepNo < currentStep);
          }});

          if (paneAgreement) paneAgreement.classList.toggle('is-active', currentStep === 1);
          if (panePayment) panePayment.classList.toggle('is-active', currentStep === 2);
          if (panePay) panePay.classList.toggle('is-active', currentStep === 3);
        }};

        const setStep = (step, force = false) => {{
          let next = Number(step) || 1;
          next = Math.max(1, Math.min(3, next));
          if (!force) {{
            if (next > 1 && !agreementReady()) next = 1;
          }}
          currentStep = next;
          renderStepState();
        }};

        const renderAgreementHint = () => {{
          if (!agreementHelp) return;
          if (!termsOpened) {{
            agreementHelp.textContent = 'กรุณาเปิดหน้าเงื่อนไขก่อน';
            agreementHelp.classList.remove('is-ok');
            return;
          }}
          if (!agreementAccepted()) {{
            agreementHelp.textContent = 'กรุณาติ๊กยอมรับข้อตกลงเพื่อไปต่อ';
            agreementHelp.classList.remove('is-ok');
            return;
          }}
          agreementHelp.textContent = 'ยืนยันข้อตกลงแล้ว สามารถเลือกช่องทางชำระเงินได้';
          agreementHelp.classList.add('is-ok');
        }};

        const updatePayPreview = () => {{
          if (!selectedChannel) return;
          const amount = parseAmount();
          const amountValid = amount >= MIN_AMOUNT;
          const channelId = parseChannelId(selectedChannel);
          const providerName = selectedChannel.getAttribute('data-provider-name') || 'Provider';
          const providerSub = selectedChannel.getAttribute('data-provider-subtitle') || '-';
          const previewKind = String(selectedChannel.getAttribute('data-preview-kind') || '').trim();
          const previewValue = String(selectedChannel.getAttribute('data-preview-value') || '').trim();

          if (payTitle) payTitle.textContent = providerName;
          if (paySubtitle) paySubtitle.textContent = providerSub;
          if (requiredList) {{
            const items = parseRequiredFields(selectedChannel);
            requiredList.innerHTML = items.map((label) => `<li>${{escapeHtml(label)}}</li>`).join('');
          }}
          if (giftHelpBox) {{
            giftHelpBox.style.display = channelId === 'truegift' ? '' : 'none';
          }}
          if (giftInputBox) {{
            giftInputBox.style.display = channelId === 'truegift' ? '' : 'none';
          }}

          let qrUrl = '';
          if (previewKind === 'promptpay_number' && previewValue) {{
            qrUrl = buildPromptPayPreviewUrl(previewValue, amountValid ? amount : 0);
          }}

          if (qrUrl) {{
            if (payQrImage) {{
              payQrImage.src = qrUrl;
              payQrImage.hidden = false;
            }}
            if (payQrEmpty) {{
              payQrEmpty.style.display = 'none';
            }}
          }} else {{
            if (payQrImage) {{
              payQrImage.hidden = true;
              payQrImage.removeAttribute('src');
            }}
            if (payQrEmpty) {{
              payQrEmpty.style.display = 'grid';
              if (channelId === 'truegift') {{
                payQrEmpty.textContent = 'ช่องทางนี้ใช้ TrueMoney Gift Link ไม่ต้องสแกน QR';
              }} else {{
                payQrEmpty.textContent = amountValid
                  ? 'ยังไม่พบข้อมูลสร้าง QR ของช่องทางนี้'
                  : 'กรุณากรอกยอดอย่างน้อย 10 THB เพื่อแสดง QR';
              }}
            }}
          }}

          if (payHint) {{
            if (!amountValid) {{
              payHint.textContent = 'กรุณากรอกยอดอย่างน้อย 10 THB เพื่อสร้าง/แสดง QR';
            }} else if (channelId === 'truegift') {{
              payHint.textContent = `วาง TrueMoney Gift Link และสร้างรายการจำนวน ${{formatAmount(amount)}} เพื่อส่งตรวจสอบทันที`;
            }} else if (channelId === 'truewallet') {{
              payHint.textContent = `สแกน QR นี้เพื่อชำระเงินจำนวน ${{formatAmount(amount)}} ผ่าน TrueMoney แล้วตรวจสอบสถานะจากรายการค้างชำระด้านล่าง`;
            }} else {{
              payHint.textContent = `สแกน QR นี้เพื่อชำระเงินจำนวน ${{formatAmount(amount)}} แล้วตรวจสอบสถานะจากรายการค้างชำระด้านล่าง`;
            }}
          }}
          renderGiftInputHint();
        }};

        const updateGateState = () => {{
          const ready = agreementReady();
          if (paymentGate) paymentGate.classList.toggle('is-locked', !ready);
          if (amountInput) amountInput.disabled = !ready || !anyReadyProvider;
          quickButtons.forEach((btn) => {{
            btn.disabled = !ready || !anyReadyProvider;
          }});
          channels.forEach((channel) => {{
            channel.classList.toggle('is-locked', !ready || !anyReadyProvider);
          }});
          if (toPaymentBtn) toPaymentBtn.disabled = !ready;
          if (!ready && currentStep > 1 && !hasPendingSession) {{
            setStep(1, true);
          }}
          syncAgreementFields();
          renderStepState();
          renderAgreementHint();
        }};

        const updateSummary = () => {{
          const gateReady = agreementReady();
          const amount = parseAmount();
          const amountValid = amount >= MIN_AMOUNT;
          if (amountHidden) amountHidden.value = amountValid ? amount.toFixed(2) : '';
          if (summaryAmount) summaryAmount.textContent = formatAmount(amountValid ? amount : 0);
          if (totalAmount) totalAmount.textContent = formatAmount(amountValid ? amount : 0);

          const providerReady = channelReady(selectedChannel);
          const channelId = parseChannelId(selectedChannel);
          const giftLinkRequired = channelId === 'truegift';
          const giftLinkValid = !giftLinkRequired || isValidTrueMoneyGiftLink(parseGiftLink());
          syncGiftLinkField();
          if (summaryProvider && selectedChannel) summaryProvider.textContent = selectedChannel.getAttribute('data-provider-name') || 'Provider';
          if (summarySubtitle && selectedChannel) summarySubtitle.textContent = selectedChannel.getAttribute('data-provider-subtitle') || '-';
          if (summaryReady) summaryReady.textContent = providerReady ? 'พร้อมใช้งาน' : 'ยังไม่พร้อม';

          if (providerInput && selectedChannel) {{
            providerInput.value = selectedChannel.getAttribute('data-provider-key') || 'promptpay';
          }}

          let issueText = '';
          if (!gateReady) {{
            issueText = 'กรุณาเปิดและยอมรับข้อตกลงก่อน';
          }} else if (!providerReady) {{
            issueText = channelIssue(selectedChannel) || 'ช่องทางนี้ยังไม่ได้ตั้งค่าระบบ';
          }} else if (currentStep >= 3 && giftLinkRequired && !giftLinkValid) {{
            issueText = 'กรุณากรอก TrueMoney Gift Link ให้ถูกต้อง';
          }}
          if (submitNote) submitNote.textContent = issueText;

          if (createBtn) {{
            createBtn.disabled = !(gateReady && providerReady && amountValid && giftLinkValid);
          }}

          if (toPayBtn) {{
            toPayBtn.disabled = !(gateReady && providerReady && amountValid);
          }}
          updatePayPreview();
        }};

        channels.forEach((channel) => {{
          channel.addEventListener('click', () => {{
            if (channel.classList.contains('is-disabled') || channel.classList.contains('is-locked')) return;
            channels.forEach((el) => el.classList.remove('is-selected'));
            channel.classList.add('is-selected');
            selectedChannel = channel;
            updateSummary();
          }});
        }});

        quickButtons.forEach((btn) => {{
          btn.addEventListener('click', () => {{
            if (btn.disabled) return;
            if (!amountInput) return;
            amountInput.value = String(btn.getAttribute('data-amount') || '');
            amountInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            amountInput.focus();
          }});
        }});

        if (toPaymentBtn) {{
          toPaymentBtn.addEventListener('click', () => {{
            if (!agreementReady()) {{
              alert('กรุณาเปิดเงื่อนไขและติ๊กยอมรับข้อตกลงก่อน');
              return;
            }}
            setStep(2);
          }});
        }}
        if (backToAgreementBtn) {{
          backToAgreementBtn.addEventListener('click', () => setStep(1, true));
        }}
        if (toPayBtn) {{
          toPayBtn.addEventListener('click', () => {{
            const amount = parseAmount();
            if (amount < MIN_AMOUNT) {{
              alert('กรุณากรอกยอดอย่างน้อย 10 THB');
              return;
            }}
            if (!selectedChannel || !channelReady(selectedChannel)) {{
              alert('ช่องทางที่เลือกยังไม่พร้อมใช้งาน');
              return;
            }}
            setStep(3);
          }});
        }}
        if (backToPaymentBtn) {{
          backToPaymentBtn.addEventListener('click', () => setStep(2, true));
        }}

        if (amountInput) {{
          amountInput.addEventListener('input', updateSummary);
        }}
        if (giftLinkInput) {{
          giftLinkInput.addEventListener('input', () => {{
            syncGiftLinkField();
            renderGiftInputHint();
            updateSummary();
          }});
        }}

        if (termsBtn) {{
          termsBtn.addEventListener('click', () => {{
            termsOpened = true;
            updateGateState();
            updateSummary();
          }});
        }}

        if (agreeCheckbox) {{
          agreeCheckbox.addEventListener('change', () => {{
            updateGateState();
            updateSummary();
          }});
        }}

        if (createForm) {{
          createForm.addEventListener('submit', (event) => {{
            syncAgreementFields();
            syncGiftLinkField();
            if (!agreementReady()) {{
              event.preventDefault();
              alert('กรุณาเปิดและยอมรับข้อตกลงก่อนชำระเงิน');
              return;
            }}
            const amount = parseAmount();
            if (amount < MIN_AMOUNT) {{
              event.preventDefault();
              alert('กรุณากรอกยอดอย่างน้อย 10 THB');
              return;
            }}
            if (!selectedChannel || !channelReady(selectedChannel)) {{
              event.preventDefault();
              alert('ช่องทางที่เลือกยังไม่พร้อมใช้งาน');
              return;
            }}
            const channelId = parseChannelId(selectedChannel);
            if (channelId === 'truegift' && !isValidTrueMoneyGiftLink(parseGiftLink())) {{
              event.preventDefault();
              alert('กรุณากรอก TrueMoney Gift Link ให้ถูกต้อง');
              giftLinkInput?.focus();
              return;
            }}
          }});
        }}

        setStep(currentStep, true);
        syncGiftLinkField();
        renderGiftInputHint();
        updateGateState();
        updateSummary();

        const sessionKey = {pending_session_key_json};
        const livePollEnabled = {pending_live_poll_enabled_json};
        let deadlineMs = Number({pending_expires_at_epoch_ms_json}) || 0;
        const countdownEl = document.getElementById('walletPendingCountdown');
        const verifyNoteEl = document.getElementById('walletPendingVerifyNote');
        const statusBadgeEl = document.getElementById('walletPendingStatusBadge');
        const pendingCard = document.querySelector('[data-wallet-pending-session="1"]');
        const verifyForm = document.getElementById('walletPendingVerifyForm');
        const sessionCodeEl = document.getElementById('walletPendingSessionCode');
        const copySessionBtn = document.getElementById('walletPendingCopyBtn');

        const formatCountdown = (seconds) => {{
          const safe = Math.max(0, Number(seconds) || 0);
          const hours = Math.floor(safe / 3600);
          const minutes = Math.floor((safe % 3600) / 60);
          const remainSeconds = safe % 60;
          if (hours > 0) {{
            return `${{String(hours).padStart(2, '0')}}:${{String(minutes).padStart(2, '0')}}:${{String(remainSeconds).padStart(2, '0')}}`;
          }}
          return `${{String(minutes).padStart(2, '0')}}:${{String(remainSeconds).padStart(2, '0')}}`;
        }};

        const renderCountdown = () => {{
          if (!countdownEl) return;
          if (!deadlineMs) {{
            countdownEl.textContent = '--:--';
            return;
          }}
          const remaining = Math.max(0, Math.floor((deadlineMs - Date.now()) / 1000));
          countdownEl.textContent = formatCountdown(remaining);
        }};

        renderCountdown();
        let countdownTimer = null;
        if (deadlineMs) {{
          countdownTimer = window.setInterval(() => {{
            renderCountdown();
            if (deadlineMs - Date.now() <= 0 && countdownTimer) {{
              window.clearInterval(countdownTimer);
              countdownTimer = null;
            }}
          }}, 1000);
        }}

        if (copySessionBtn) {{
          copySessionBtn.addEventListener('click', async () => {{
            const codeRaw = String(sessionKey || '').trim();
            if (!codeRaw) return;
            try {{
              await navigator.clipboard.writeText(codeRaw);
              copySessionBtn.textContent = 'คัดลอกแล้ว';
              window.setTimeout(() => {{
                copySessionBtn.textContent = 'คัดลอกรหัสรายการ';
              }}, 1200);
            }} catch (_error) {{
              if (sessionCodeEl) {{
                const selection = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(sessionCodeEl);
                selection?.removeAllRanges();
                selection?.addRange(range);
              }}
            }}
          }});
        }}

        if (!sessionKey || !pendingCard || !livePollEnabled) return;

        const markSessionClosed = (status, message, reloadPage) => {{
          pendingCard.classList.add('is-closed');
          if (statusBadgeEl) {{
            statusBadgeEl.className = 'wallet-v2-status-badge';
            statusBadgeEl.classList.add(status === 'paid' ? 'is-paid' : 'is-closed');
            statusBadgeEl.textContent = status === 'paid' ? 'ชำระสำเร็จ' : status;
          }}
          if (countdownEl) countdownEl.textContent = '00:00';
          if (verifyNoteEl && message) verifyNoteEl.textContent = message;
          if (verifyForm) {{
            verifyForm.querySelectorAll('input,button').forEach((el) => {{
              if (el instanceof HTMLInputElement || el instanceof HTMLButtonElement) {{
                el.disabled = true;
              }}
            }});
          }}
          if (reloadPage) {{
            window.setTimeout(() => {{ window.location.reload(); }}, 1200);
          }}
        }};

        const pollUrl = `/dashboard/topurp/status?session_key=${{encodeURIComponent(sessionKey)}}`;
        let stopped = false;
        const pollOnce = async () => {{
          if (stopped) return;
          try {{
            const response = await fetch(pollUrl, {{
              method: 'GET',
              credentials: 'same-origin',
              headers: {{ accept: 'application/json' }},
            }});
            if (!response.ok) return;
            const payload = await response.json();
            if (!payload || payload.ok !== true) return;

            const status = String(payload.status || '').toLowerCase();
            if (typeof payload.expires_in_seconds === 'number' && Number.isFinite(payload.expires_in_seconds)) {{
              deadlineMs = Date.now() + Math.max(0, Number(payload.expires_in_seconds)) * 1000;
              renderCountdown();
            }}
            if (verifyNoteEl && payload.verify_note) {{
              verifyNoteEl.textContent = String(payload.verify_note);
            }}
            if (status === 'paid') {{
              stopped = true;
              markSessionClosed('paid', 'ชำระเงินสำเร็จ กำลังอัปเดตยอดคงเหลือ...', true);
              return;
            }}
            if (status === 'expired' || status === 'cancelled') {{
              stopped = true;
              markSessionClosed(status, 'รายการนี้ปิดแล้ว กรุณาสร้างรายการใหม่', false);
            }}
          }} catch (_error) {{
            // ignore
          }}
        }};

        pollOnce();
        const pollTimer = window.setInterval(() => {{
          if (stopped) {{
            window.clearInterval(pollTimer);
            return;
          }}
          pollOnce();
        }}, 5000);
      }})();
    </script>
    """


def _build_donate_page_body(
    *,
    payment_settings: dict[str, Any],
    pending_session: dict[str, Any] | None,
    donate_rows: list[dict[str, Any]],
    keyword: str = "",
    notice: str | None = None,
) -> str:
    notice_markup = f'<div class="notice">{_escape(notice)}</div>' if notice else ""
    slip_verify_engine_name = _slip_verify_engine_name(payment_settings)
    pending_card = ""
    if pending_session:
        session_key = str(pending_session.get("session_key") or "")
        amount_text = _format_money(pending_session.get("amount"))
        expires_text = _fmt_dt(pending_session.get("expires_at"))
        qr_image = str(pending_session.get("qr_image_url") or "")
        provider_type = str(pending_session.get("provider_type") or "promptpay").strip().lower()
        provider_label = {
            "promptpay": "PromptPay / TrueMoney",
            "truemoney": "TrueMoney QR",
        }.get(provider_type, provider_type or "Unknown")
        provider_name = str(pending_session.get("provider_name") or "").strip()
        truemoney_phone = str(pending_session.get("truemoney_phone") or "")
        manual_verify_allowed = _session_manual_verify_allowed(pending_session, payment_settings)
        verify_notice = _session_verify_notice(pending_session, payment_settings)
        verify_form_markup = ""
        if manual_verify_allowed:
            transfer_link_row = (
                """
                <label class="switch-row">
                  <span>ลิงก์หลักฐาน (ถ้ามี)</span>
                  <input type="url" name="transfer_link" placeholder="https://gift.truemoney.com/campaign/?v=...">
                </label>
                """
                if provider_type in {"promptpay", "truemoney"}
                else ""
            )
            verify_form_markup = f"""
            <form method="post" action="/dashboard/donate-wallet/verify" class="settings-grid wallet-verify-form">
              <input type="hidden" name="session_key" value="{_escape(session_key)}">
              <label class="switch-row">
                <span>เลขอ้างอิงการโอน (ถ้ามี)</span>
                <input type="text" name="transfer_reference" placeholder="เลขอ้างอิงการโอน">
              </label>
              {transfer_link_row}
              <div class="auth-actions" style="justify-content:flex-start;">
                <button class="primary-btn" type="submit">{_escape(f"Verify Payment With {slip_verify_engine_name}")}</button>
              </div>
              <p class="muted" style="margin:0;">{_escape(verify_notice)}</p>
            </form>
            """
        else:
            verify_form_markup = f'<p class="muted" style="margin:0;">{_escape(verify_notice)}</p>'
        pending_card = f"""
        <article class="panel-sub wallet-pending-card donate-pending-card" style="display:grid; gap:10px;">
          <h3 style="margin:0;">รายการโดเนทรอล่าสุด</h3>
          <div class="mini-stat">Session: <code>{_escape(session_key)}</code></div>
          <div class="mini-stat">Provider: <strong>{_escape(provider_label)}</strong>{f' ({_escape(provider_name)})' if provider_name else ''}</div>
          <div class="mini-stat">ยอดเงิน: <strong>{_escape(amount_text)} THB</strong></div>
          <div class="mini-stat">หมดเวลา: {_escape(expires_text)}</div>
          {f'<div class="mini-stat">TrueMoney Wallet: <code>{_escape(truemoney_phone)}</code></div>' if truemoney_phone else ''}
          {f'<img src="{_escape(qr_image)}" alt="Donate QR" style="width:220px;height:220px;border-radius:12px;border:1px solid var(--line);">' if qr_image else ''}
          <p class="muted" style="margin:0;">โค้ดอ้างอิงรายการ: <code>{_escape(session_key)}</code> (ใช้ผูกรายการใน webhook)</p>
          {verify_form_markup}
          <p class="muted" style="margin:0;">ระบบปิดรายการอัตโนมัติเมื่อครบ 10 นาที หรือเมื่อยืนยันโดเนทสำเร็จ</p>
        </article>
        """

    donate_history_rows = []
    for row in donate_rows[:120]:
        donate_history_rows.append(
            f"""
            <tr>
              <td><code>{_escape(str(row.get("session_key") or "")[:16])}</code></td>
              <td>{_escape(_format_money(row.get("amount")))} THB</td>
              <td>{_escape(str(row.get("status") or "-"))}</td>
              <td>{_escape(str(row.get("verify_status") or "-"))}</td>
              <td>{_escape(_fmt_dt(row.get("created_at")))}</td>
              <td>{_escape(_fmt_dt(row.get("paid_at")))}</td>
            </tr>
            """
        )
    if not donate_history_rows:
        donate_history_rows.append('<tr><td colspan="6" class="muted">ยังไม่มีประวัติโดเนท</td></tr>')

    donate_paid_total = 0.0
    for row in donate_rows:
        if str(row.get("status") or "").strip().lower() != "paid":
            continue
        try:
            donate_paid_total += float(row.get("amount") or 0.0)
        except Exception:
            continue

    return f"""
    <section class="panel page-shell page-wallet-shell donate-hero-panel">
      <h1 style="margin-top:0;">Donate (แยกระบบจาก Wallet Topup)</h1>
      <p class="muted">
        หน้านี้เป็นระบบโดเนทโดยเฉพาะ ข้อมูลธุรกรรมจะแยกจากระบบเติมเงินวอลเล็ท
      </p>
      {notice_markup}
      <div class="wallet-summary-grid">
        <article class="wallet-summary-card">
          <span class="wallet-summary-label">ยอดโดเนทรวม</span>
          <strong>{_escape(_format_money(donate_paid_total))} THB</strong>
        </article>
        <article class="wallet-summary-card">
          <span class="wallet-summary-label">ประวัติโดเนท</span>
          <strong>{_escape(len(donate_rows))} รายการ</strong>
        </article>
      </div>
      <div class="wallet-form-layout">
        <form method="get" action="/donate-wallet" class="settings-grid wallet-form-card">
          <label class="switch-row">
            <span>ค้นหาประวัติ</span>
            <input type="text" name="q" value="{_escape(keyword)}" placeholder="session / status / amount">
          </label>
          <div class="auth-actions" style="justify-content:flex-start;">
            <button class="ghost-btn" type="submit">ค้นหา</button>
            <a class="ghost-btn" href="/donate-wallet">ล้างตัวกรอง</a>
          </div>
        </form>
        <form method="post" action="/dashboard/donate-wallet/create" class="settings-grid wallet-form-card">
          <label class="switch-row">
            <span>จำนวนเงินโดเนท</span>
            <input type="number" name="amount" min="1" step="0.01" required placeholder="เช่น 20">
          </label>
          <div class="auth-actions" style="justify-content:flex-start;">
            <button class="primary-btn" type="submit">สร้างรายการโดเนท</button>
            <a class="ghost-btn" href="/wallet">กลับหน้า Wallet</a>
          </div>
        </form>
      </div>
    </section>

    <section class="panel page-shell page-wallet-shell wallet-section" style="margin-top:14px;">
      <h2 style="margin-top:0;">รายการชำระเงิน (Donate)</h2>
      {pending_card or '<div class="muted">ยังไม่มีรายการรอชำระ</div>'}
    </section>

    <section class="panel page-shell page-wallet-shell wallet-section" style="margin-top:14px;">
      <h2 style="margin-top:0;">ประวัติโดเนท</h2>
      <div class="wallet-table-wrap" style="overflow:auto;">
        <table class="audit-table">
          <thead>
            <tr>
              <th>Session</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Verify</th>
              <th>Created</th>
              <th>Paid At</th>
            </tr>
          </thead>
          <tbody>{''.join(donate_history_rows)}</tbody>
        </table>
      </div>
    </section>
    """


def _login_redirect(next_path: str) -> RedirectResponse:
    return RedirectResponse(url=f"/dashboard/login?next={_escape(next_path)}", status_code=303)


async def dashboard_wallet_page(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/wallet", status_code=303)

    user_id = _session_user_id(session)
    if not user_id:
        return HTMLResponse(await _render_login("User session was not found."), status_code=401)

    user_id_int = int(user_id)
    guilds = _manageable_guilds(session)
    await billing_workflow.ensure_wallet_account(user_id_int)
    user_app_subscription = await billing_workflow.ensure_user_app_subscription(user_id_int)
    balance = await billing_workflow.get_wallet_balance(user_id_int)
    payment_settings = await billing_workflow.get_payment_provider_settings()

    selected_provider = _normalize_provider_name(payment_settings.get("topup_provider")) or "promptpay"
    active_provider, provider_fallback_note = billing_workflow.resolve_active_payment_provider(
        settings=payment_settings,
        selected_provider=selected_provider,
    )

    always_on_ready, _always_provider, always_on_issues = billing_workflow.validate_payment_provider_settings(
        settings=payment_settings,
        mode="topup",
        provider_type="promptpay",
    )
    active_ready, _provider, readiness_issues = billing_workflow.validate_payment_provider_settings(
        settings=payment_settings,
        mode="topup",
        provider_type=active_provider,
    )

    topup_ready = always_on_ready
    topup_ready_issues: list[str] = list(always_on_issues[:2]) if always_on_issues else []
    if not active_ready and active_provider != "promptpay":
        if readiness_issues:
            topup_ready_issues.append(f"Provider '{active_provider}' is not ready: {readiness_issues[0]}")
        else:
            topup_ready_issues.append(f"Provider '{active_provider}' is not ready for usage")
    topup_ready_message = "; ".join(topup_ready_issues[:3]) if topup_ready_issues else ""
    if provider_fallback_note:
        topup_ready_message = (
            f"{topup_ready_message}; {provider_fallback_note}"
            if topup_ready_message
            else provider_fallback_note
        )

    all_topup_rows = _sort_rows_by_created_desc(await storage.bot_payment_sessions.gets(user_id=user_id_int, mode="topup"))
    pending_session = next((row for row in all_topup_rows if str(row.get("status") or "") == "pending"), None)
    topup_rows = list(all_topup_rows)
    page_notice = notice or str(request.query_params.get("notice") or "").strip() or None

    body = _build_wallet_page_body(
        session=session,
        guilds=guilds,
        balance=balance,
        payment_settings=payment_settings,
        pending_session=pending_session,
        topup_rows=topup_rows,
        ledger_rows=[],
        plan_rows_by_guild_id={},
        user_app_subscription=user_app_subscription,
        event_rows=[],
        topup_ready=topup_ready,
        topup_ready_message=topup_ready_message,
        keyword="",
        notice=page_notice,
    )
    return HTMLResponse(_render_layout(title="เติมเงินวอลเลต - SkylineBOT", body=body, session=session, guilds=guilds))


async def dashboard_wallet_create_topup(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/wallet", status_code=303)

    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/wallet?notice=User session was not found", status_code=303)

    form = await _parse_form(request)
    agreement_accepted_raw = form.get("agreement_accepted")
    if agreement_accepted_raw in (None, ""):
        agreement_accepted_raw = form.get("agreement_accepted_checkbox")
    agreement_accepted = str(agreement_accepted_raw or "").strip().lower() in {"1", "true", "yes", "on"}
    if not agreement_accepted:
        query = urlencode({"notice": "กรุณาติ๊กยอมรับข้อตกลงก่อนสร้างรายการเติมเงิน"})
        return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)

    amount = _parse_float_form(form, "amount", 0.0)
    provider_type = _normalize_provider_name(form.get("provider_type")) or "promptpay"
    gift_link = str(form.get("gift_link") or "").strip()
    if gift_link and not TRUEMONEY_GIFT_LINK_RE.match(gift_link):
        query = urlencode({"notice": "ลิงก์ TrueMoney Gift ไม่ถูกต้อง (ต้องเป็น gift.truemoney.com/campaign/?v=...)"})
        return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)
    ok, message, _row = await billing_workflow.create_payment_session(
        user_id=int(user_id),
        amount=amount,
        mode="topup",
        provider_type_override=provider_type,
        note="Wallet topup via dashboard",
    )
    notice_text = message if ok else f"Failed to create payment session: {message}"
    created_row = _row if isinstance(_row, dict) else {}
    if ok and gift_link:
        created_session_key = str(created_row.get("session_key") or "").strip()
        if created_session_key:
            verify_ok, verify_message, _verified_row = await billing_workflow.confirm_payment_session(
                session_key=created_session_key,
                transfer_link=gift_link,
                force_paid=False,
            )
            if verify_ok:
                notice_text = verify_message or "ตรวจสอบ TrueMoney Gift Link สำเร็จ"
            else:
                detail = str(verify_message or "").strip()
                notice_text = (
                    f"สร้างรายการแล้ว และส่ง Gift Link แล้ว: {detail}"
                    if detail
                    else "สร้างรายการแล้ว และส่ง Gift Link แล้ว"
                )
    query = urlencode({"notice": notice_text})
    return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)


async def dashboard_wallet_verify_topup(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/wallet", status_code=303)

    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/wallet?notice=User session was not found", status_code=303)

    form_values, parsed_form, form_error = await _parse_wallet_form_payload(request)
    if form_error:
        query = urlencode({"notice": form_error})
        return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)

    session_key = str(form_values.get("session_key") or "").strip()
    transfer_reference = str(form_values.get("transfer_reference") or "").strip()
    transfer_link = str(form_values.get("transfer_link") or "").strip()
    gift_link = str(form_values.get("gift_link") or "").strip()
    slip_qr_payload = str(form_values.get("slip_qr_payload") or "").strip()
    if gift_link:
        transfer_link = gift_link

    uploaded_slip_url = ""
    uploaded_file_name = ""
    if parsed_form is not None:
        uploaded_file = parsed_form.get("slip_image_file")
        if uploaded_file and getattr(uploaded_file, "filename", None):
            uploaded_file_name = str(getattr(uploaded_file, "filename", "") or "").strip()
            upload_content_type = str(getattr(uploaded_file, "content_type", "") or "").strip().lower()
            ext = uploaded_file_name.lower().split(".")[-1] if "." in uploaded_file_name else ""
            if ext not in {"png", "jpg", "jpeg", "webp", "gif"} and not upload_content_type.startswith("image/"):
                query = urlencode({"notice": "รองรับเฉพาะไฟล์รูปภาพสำหรับสลิป (png/jpg/jpeg/webp/gif)"})
                return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)
            raw_bytes = await uploaded_file.read()
            if raw_bytes and len(raw_bytes) > 8 * 1024 * 1024:
                query = urlencode({"notice": "ไฟล์สลิปมีขนาดใหญ่เกินไป (สูงสุด 8MB)"})
                return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)
            if raw_bytes:
                uploaded_slip_url = await _upload_wallet_slip_image(
                    session=session,
                    raw_bytes=raw_bytes,
                    filename=uploaded_file_name or "wallet-slip.png",
                    request=request,
                )
                if not uploaded_slip_url:
                    query = urlencode(
                        {
                            "notice": "อัปโหลดรูปสลิปไม่สำเร็จ กรุณาลองใหม่ หรือใช้ Gift Link/Slip QR payload แทน",
                        }
                    )
                    return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)

    if uploaded_slip_url and not transfer_link:
        transfer_link = uploaded_slip_url

    ok, message, row = await billing_workflow.confirm_payment_session(
        session_key=session_key,
        transfer_reference=transfer_reference,
        transfer_link=transfer_link,
        slip_qr_payload=slip_qr_payload,
        force_paid=False,
    )
    if row and int(row.get("user_id") or 0) not in {0, int(user_id)}:
        return RedirectResponse(
            url="/dashboard/wallet?notice=You do not have permission for this payment session",
            status_code=303,
        )
    query = urlencode({"notice": message if ok else f"Failed to confirm payment session: {message}"})
    return RedirectResponse(url=f"/dashboard/wallet?{query}", status_code=303)


async def dashboard_wallet_topup_status(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return JSONResponse(
            {"ok": False, "error": "unauthorized", "error_code": "WEB-BILLING-AUTH-401"},
            status_code=401,
        )

    user_id = _session_user_id(session)
    if not user_id:
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_user_session",
                "error_code": "WEB-BILLING-SESSION-USER-401",
            },
            status_code=401,
        )
    user_id_int = int(user_id)

    session_key = _extract_session_key(request.query_params.get("session_key") or "")
    if not session_key:
        return JSONResponse(
            {
                "ok": False,
                "error": "invalid_session_key",
                "error_code": "WEB-BILLING-SESSION-KEY-400",
            },
            status_code=400,
        )

    row = await storage.bot_payment_sessions.get(session_key=session_key)
    if not row:
        return JSONResponse(
            {
                "ok": False,
                "error": "session_not_found",
                "error_code": "WEB-BILLING-SESSION-NOTFOUND-404",
            },
            status_code=404,
        )
    if int(row.get("user_id") or 0) != user_id_int:
        return JSONResponse(
            {"ok": False, "error": "forbidden", "error_code": "WEB-BILLING-FORBIDDEN-403"},
            status_code=403,
        )
    if str(row.get("mode") or "").strip().lower() != "topup":
        return JSONResponse(
            {"ok": False, "error": "invalid_mode", "error_code": "WEB-BILLING-MODE-400"},
            status_code=400,
        )

    settings = await billing_workflow.get_payment_provider_settings()
    status_value = str(row.get("status") or "").strip().lower()
    if status_value == "pending" and _session_should_auto_confirm_via_poll(row, settings):
        now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
        verify_interval_seconds = max(
            5,
            int(getattr(billing_workflow, "PAYMENT_SESSION_VERIFY_INTERVAL_SECONDS", 30) or 30),
        )
        last_verified_at = _as_utc_datetime(row.get("last_verified_at"))
        should_verify_now = not last_verified_at
        if last_verified_at:
            should_verify_now = (now_utc - last_verified_at).total_seconds() >= verify_interval_seconds
        if should_verify_now:
            _ok, _message, refreshed_row = await billing_workflow.confirm_payment_session(
                session_key=session_key,
                force_paid=False,
            )
            if isinstance(refreshed_row, dict):
                row = refreshed_row

    latest_row = await storage.bot_payment_sessions.get(session_key=session_key)
    if latest_row:
        row = latest_row

    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    expires_at = _as_utc_datetime(row.get("expires_at"))
    expires_in_seconds = None
    if expires_at:
        expires_in_seconds = max(0, int((expires_at - now_utc).total_seconds()))

    final_status = str(row.get("status") or "").strip().lower()
    is_closed = final_status in {"paid", "expired", "cancelled"}
    payload: dict[str, Any] = {
        "ok": True,
        "session_key": session_key,
        "status": final_status,
        "verify_status": str(row.get("verify_status") or "").strip().lower(),
        "verify_note": str(row.get("verify_note") or "").strip(),
        "amount": float(row.get("amount") or 0.0),
        "paid_at": _fmt_dt(row.get("paid_at")),
        "expires_at": _fmt_dt(row.get("expires_at")),
        "expires_in_seconds": expires_in_seconds,
        "is_closed": is_closed,
    }
    if final_status == "paid":
        payload["wallet_balance"] = await billing_workflow.get_wallet_balance(user_id_int)
    return JSONResponse(payload, status_code=200)


async def dashboard_donate_wallet_page(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/donate-wallet", status_code=303)
    user_id = _session_user_id(session)
    if not user_id:
        return HTMLResponse(await _render_login("ไม่พบข้อมูลผู้ใช้ในระบบ"), status_code=401)
    user_id_int = int(user_id)
    guilds = _manageable_guilds(session)
    payment_settings = await billing_workflow.get_payment_provider_settings()

    keyword = _clean_text(request.query_params.get("q") or "").strip().lower()
    all_donate_rows = _sort_rows_by_created_desc(await storage.bot_payment_sessions.gets(user_id=user_id_int, mode="donate"))
    pending_session = next((row for row in all_donate_rows if str(row.get("status") or "") == "pending"), None)
    donate_rows = list(all_donate_rows)
    if keyword:
        donate_rows = [
            row
            for row in donate_rows
            if keyword
            in " ".join(
                [
                    str(row.get("session_key") or ""),
                    str(row.get("status") or ""),
                    str(row.get("verify_status") or ""),
                    str(row.get("amount") or ""),
                    str(row.get("transfer_reference") or ""),
                ]
            ).lower()
        ]
    page_notice = notice or str(request.query_params.get("notice") or "").strip() or None
    body = _build_donate_page_body(
        payment_settings=payment_settings,
        pending_session=pending_session,
        donate_rows=donate_rows,
        keyword=keyword,
        notice=page_notice,
    )
    return HTMLResponse(_render_layout(title="โดเนทวอลเลต - SkylineBOT", body=body, session=session, guilds=guilds))


async def dashboard_donate_wallet_create(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/donate-wallet", status_code=303)
    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/donate-wallet?notice=ไม่พบผู้ใช้ในเซสชัน", status_code=303)

    form = await _parse_form(request)
    amount = _parse_float_form(form, "amount", 0.0)
    ok, message, _row = await billing_workflow.create_payment_session(
        user_id=int(user_id),
        amount=amount,
        mode="donate",
        note="โดเนทผ่านหน้า Donate Wallet",
    )
    query = urlencode({"notice": message if ok else f"สร้างรายการชำระเงินไม่สำเร็จ: {message}"})
    return RedirectResponse(url=f"/dashboard/donate-wallet?{query}", status_code=303)


async def dashboard_donate_wallet_verify(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/donate-wallet", status_code=303)
    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/donate-wallet?notice=ไม่พบผู้ใช้ในเซสชัน", status_code=303)

    form = await _parse_form(request)
    session_key = str(form.get("session_key") or "").strip()
    transfer_reference = str(form.get("transfer_reference") or "").strip()
    transfer_link = str(form.get("transfer_link") or "").strip()
    ok, message, row = await billing_workflow.confirm_payment_session(
        session_key=session_key,
        transfer_reference=transfer_reference,
        transfer_link=transfer_link,
        force_paid=False,
    )
    if row and int(row.get("user_id") or 0) not in {0, int(user_id)}:
        return RedirectResponse(url="/dashboard/donate-wallet?notice=ไม่มีสิทธิ์แก้ไขรายการนี้", status_code=303)
    query = urlencode({"notice": message if ok else f"ยืนยันโดเนทไม่สำเร็จ: {message}"})
    return RedirectResponse(url=f"/dashboard/donate-wallet?{query}", status_code=303)


async def dashboard_payment_webhook_confirm(request: Request):
    await _ensure_dashboard_config_cache()
    settings = await billing_workflow.get_payment_provider_settings()

    raw_body = await request.body()
    content_type = str(request.headers.get("content-type") or "").lower()
    payload = _parse_webhook_payload(raw_body, content_type)

    # Backward compatibility for callers that may send unusual content types.
    if not payload:
        try:
            if "application/json" in content_type:
                decoded = await request.json()
                if isinstance(decoded, dict):
                    payload = decoded
            else:
                form = await _parse_form(request)
                payload = dict(form or {})
        except Exception:
            payload = {}

    provider_hint = _normalize_provider_name(
        request.query_params.get("provider")
        or request.headers.get("x-payment-provider")
        or payload.get("provider")
        or payload.get("payment_provider")
    )

    common_secret = str(settings.get("webhook_secret") or "").strip()
    truemoney_secret = str(settings.get("truemoney_webhook_secret") or "").strip() or common_secret

    session_candidates = [
        "session_key",
        "session",
        "sessionKey",
        "metadata.session_key",
        "meta.session_key",
        "data.session_key",
        "data.metadata.session_key",
        "data.object.metadata.session_key",
        "reference",
        "order_id",
        "data.reference",
        "data.orderId",
        "transactionId",
        "data.transactionId",
    ]
    lookup_tokens = _collect_session_lookup_tokens(payload, settings)
    early_session_key = _extract_session_key(_payload_first_text(payload, session_candidates))

    provider = provider_hint
    session_row = None
    if early_session_key:
        session_row = await storage.bot_payment_sessions.get(session_key=early_session_key)
        if not provider:
            provider = _normalize_provider_name((session_row or {}).get("provider_type"))
            if not provider and session_row:
                mode_value = str(session_row.get("mode") or "topup").strip().lower()
                provider = _normalize_provider_name(
                    settings.get("donate_provider" if mode_value == "donate" else "topup_provider")
                )
    if not session_row and lookup_tokens:
        session_row = await _resolve_session_from_tokens(lookup_tokens)
        if not provider:
            provider = _normalize_provider_name((session_row or {}).get("provider_type"))
            if not provider and session_row:
                mode_value = str(session_row.get("mode") or "topup").strip().lower()
                provider = _normalize_provider_name(
                    settings.get("donate_provider" if mode_value == "donate" else "topup_provider")
                )

    if not provider:
        provider = _normalize_provider_name(settings.get("topup_provider")) or "promptpay"
    if provider not in {"promptpay", "truemoney"}:
        provider = "truemoney" if _normalize_provider_name((session_row or {}).get("provider_type")) == "truemoney" else "promptpay"

    truemoney_secret_verified = False
    if provider == "truemoney":
        if not truemoney_secret:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "truemoney_secret_not_configured",
                    "error_code": "WEB-BILLING-TRUEMONEY-SECRET-503",
                    "provider": provider,
                },
                status_code=503,
            )
        signature_header = str(settings.get("truemoney_signature_header") or "x-truemoney-signature").strip().lower() or "x-truemoney-signature"
        provided_signature = str(
            request.headers.get(signature_header)
            or payload.get("signature")
            or payload.get("hmac")
            or payload.get("sign")
            or ""
        ).strip()
        if provided_signature:
            if not _verify_hmac_signature(
                raw_body=raw_body,
                secret=truemoney_secret,
                provided_signature=provided_signature,
                algorithm=str(settings.get("truemoney_signature_algorithm") or "sha256"),
                prefix=str(settings.get("truemoney_signature_prefix") or ""),
            ):
                return JSONResponse(
                    {
                        "ok": False,
                        "error": "invalid_signature",
                        "error_code": "WEB-BILLING-WEBHOOK-SIGNATURE-403",
                        "provider": provider,
                    },
                    status_code=403,
                )
            truemoney_secret_verified = True
        if not truemoney_secret_verified:
            provided_secret = str(
                request.headers.get("x-payment-secret")
                or request.headers.get("x-webhook-secret")
                or payload.get("secret")
                or payload.get("webhook_secret")
                or ""
            ).strip()
            if not provided_secret or not hmac.compare_digest(provided_secret, truemoney_secret):
                return JSONResponse(
                    {
                        "ok": False,
                        "error": "invalid_secret",
                        "error_code": "WEB-BILLING-WEBHOOK-SECRET-403",
                        "provider": provider,
                    },
                    status_code=403,
                )
            truemoney_secret_verified = True

    if provider == "truemoney":
        session_candidates.extend([
            "reference",
            "order_id",
            "data.reference",
            "data.orderId",
            "transactionId",
            "data.transactionId",
        ])

    session_key = _extract_session_key(early_session_key or _payload_first_text(payload, session_candidates))
    if not session_key and session_row:
        session_key = _extract_session_key(session_row.get("session_key"))
    if not session_key and lookup_tokens:
        resolved_row = session_row or await _resolve_session_from_tokens(lookup_tokens)
        if resolved_row:
            session_row = resolved_row
            session_key = _extract_session_key(session_row.get("session_key"))
    if not session_key:
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_session_key",
                "error_code": "WEB-BILLING-WEBHOOK-SESSIONKEY-400",
                "provider": provider,
            },
            status_code=400,
        )
    if not session_row:
        session_row = await storage.bot_payment_sessions.get(session_key=session_key)

    transfer_reference = _payload_first_text(
        payload,
        [
            "transfer_reference",
            "reference",
            "transaction_id",
            "tx_ref",
            "slip_no",
            "payment_id",
            "data.reference",
            "transactionId",
            "data.transactionId",
            "transId",
        ],
    )
    transfer_link = _payload_first_text(
        payload,
        [
            "transfer_link",
            "slip_url",
            "proof_url",
            "evidence_url",
            "receipt_url",
        ],
    )

    status_value = _payload_first_text(
        payload,
        [
            "status",
            "payment_status",
            "result",
            "event",
            "type",
            "state",
            "status.code",
            "data.status",
            "data.status.code",
            "data.payment_status",
            "data.object.status",
            "data.object.payment_status",
            "data.object.type",
            "statusCode",
            "data.statusCode",
        ],
    )
    paid_flag_text = _payload_first_text(
        payload,
        ["paid", "is_paid", "success", "completed", "statusCode", "data.statusCode"],
    )
    force_paid = _status_force_paid(status_value) or _status_force_paid(paid_flag_text)
    if provider == "truemoney":
        paid_values = {
            str(item or "").strip().lower()
            for item in str(settings.get("truemoney_paid_status_values") or "paid,success,completed,settled").split(",")
            if str(item or "").strip()
        }
        if not paid_values:
            paid_values = {"paid", "success", "completed", "settled"}
        configured_status = str(
            _payload_path_get(payload, str(settings.get("truemoney_inquiry_status_field") or "data.status"))
            or ""
        ).strip().lower()
        if configured_status and configured_status in paid_values:
            force_paid = True
        if force_paid and not truemoney_secret_verified:
            force_paid = False
    else:
        force_paid = False

    if force_paid and session_row:
        amount_candidates = [
            "amount",
            "total_amount",
            "payment_amount",
            "transactionAmount",
            "data.amount",
            "data.totalAmount",
            "data.paymentAmount",
            "data.transactionAmount",
        ]
        if provider == "truemoney":
            tm_amount_field = str(settings.get("truemoney_amount_field") or "amount").strip()
            if tm_amount_field and tm_amount_field not in amount_candidates:
                amount_candidates.insert(0, tm_amount_field)
        callback_amount = _payload_first_amount(payload, amount_candidates)
        if callback_amount is not None:
            try:
                expected_amount = float(session_row.get("amount") or 0.0)
            except Exception:
                expected_amount = 0.0
            if expected_amount > 0 and abs(callback_amount - expected_amount) > 0.01:
                force_paid = False

    slip_qr_payload = _payload_first_text(
        payload,
        ["slip_qr_payload", "qr_payload", "qrcode", "qrData", "data.qrData", "payload"],
    )

    ok, message, row = await billing_workflow.confirm_payment_session(
        session_key=session_key,
        transfer_reference=transfer_reference,
        transfer_link=transfer_link,
        slip_qr_payload=slip_qr_payload,
        force_paid=force_paid,
    )
    if not ok:
        return JSONResponse(
            {
                "ok": False,
                "error": "payment_confirmation_failed",
                "error_code": "WEB-BILLING-CONFIRM-400",
                "message": message,
                "provider": provider,
                "session_key": session_key,
                "status": (row or {}).get("status"),
                "verify_status": (row or {}).get("verify_status"),
            },
            status_code=400,
        )
    return JSONResponse(
        {
            "ok": True,
            "message": message,
            "provider": provider,
            "session_key": session_key,
            "status": (row or {}).get("status"),
            "verify_status": (row or {}).get("verify_status"),
        },
        status_code=200,
    )


async def dashboard_admin_billing_history(request: Request, notice: str | None = None):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse("/dashboard", status_code=303)
    if not _is_dashboard_admin(session):
        return HTMLResponse(_render_guild_picker(session, _manageable_guilds(session), "ต้องมีสิทธิ์ผู้ดูแลระบบ"), status_code=403)

    mode_filter = str(request.query_params.get("mode") or "").strip().lower()
    status_filter = str(request.query_params.get("status") or "").strip().lower()
    keyword = _clean_text(request.query_params.get("q") or "").strip().lower()

    payment_rows = _sort_rows_by_created_desc(await storage.bot_payment_sessions.get_all())
    if mode_filter in {"topup", "donate"}:
        payment_rows = [row for row in payment_rows if str(row.get("mode") or "").strip().lower() == mode_filter]
    if status_filter:
        payment_rows = [row for row in payment_rows if str(row.get("status") or "").strip().lower() == status_filter]
    if keyword:
        filtered = []
        for row in payment_rows:
            blob = " ".join(
                [
                    str(row.get("session_key") or ""),
                    str(row.get("user_id") or ""),
                    str(row.get("guild_id") or ""),
                    str(row.get("status") or ""),
                    str(row.get("verify_status") or ""),
                    str(row.get("transfer_reference") or ""),
                    str(row.get("transfer_link") or ""),
                ]
            ).lower()
            if keyword in blob:
                filtered.append(row)
        payment_rows = filtered

    event_rows = _sort_rows_by_created_desc(await storage.bot_billing_events.get_all())
    if keyword:
        event_rows = [
            row
            for row in event_rows
            if keyword
            in " ".join(
                [
                    str(row.get("event_type") or ""),
                    str(row.get("message") or ""),
                    str(row.get("user_id") or ""),
                    str(row.get("guild_id") or ""),
                ]
            ).lower()
        ]

    payment_table_rows = []
    for row in payment_rows[:400]:
        payment_table_rows.append(
            f"""
            <tr>
              <td><code>{_escape(str(row.get("session_key") or "")[:20])}</code></td>
              <td>{_escape(str(row.get("mode") or "-"))}</td>
              <td>{_escape(str(row.get("user_id") or "-"))}</td>
              <td>{_escape(str(row.get("guild_id") or "-"))}</td>
              <td>{_escape(_format_money(row.get("amount")))} THB</td>
              <td>{_escape(str(row.get("status") or "-"))}</td>
              <td>{_escape(str(row.get("verify_status") or "-"))}</td>
              <td>{_escape(_fmt_dt(row.get("created_at")))}</td>
              <td>{_escape(_fmt_dt(row.get("paid_at")))}</td>
            </tr>
            """
        )
    if not payment_table_rows:
        payment_table_rows.append('<tr><td colspan="9" class="muted">ไม่พบข้อมูลรายการชำระเงิน</td></tr>')

    event_table_rows = []
    for row in event_rows[:400]:
        event_table_rows.append(
            f"""
            <tr>
              <td>{_escape(str(row.get("event_type") or "-"))}</td>
              <td>{_escape(str(row.get("level") or "-"))}</td>
              <td>{_escape(str(row.get("user_id") or "-"))}</td>
              <td>{_escape(str(row.get("guild_id") or "-"))}</td>
              <td>{_escape(str(row.get("message") or "-"))}</td>
              <td>{_escape(_fmt_dt(row.get("created_at")))}</td>
            </tr>
            """
        )
    if not event_table_rows:
        event_table_rows.append('<tr><td colspan="6" class="muted">ไม่พบ Billing Events</td></tr>')

    page_notice = notice or str(request.query_params.get("notice") or "").strip() or None
    notice_markup = f'<div class="notice">{_escape(page_notice)}</div>' if page_notice else ""
    body = f"""
    <section class="panel page-shell">
      <h1 style="margin-top:0;">Owner Billing History</h1>
      <p class="muted">ค้นหาได้ทั้ง user / owner / guild / session สำหรับระบบเติมเงินและโดเนท</p>
      {notice_markup}
      <form method="get" action="/dashboard/admin/billing/history" class="settings-grid" style="margin-top:10px;">
        <label class="switch-row">
          <span>ค้นหา</span>
          <input type="text" name="q" value="{_escape(keyword)}" placeholder="session key / user id / guild id">
        </label>
        <label class="switch-row">
          <span>Mode</span>
          <select name="mode">
            <option value="" {"selected" if not mode_filter else ""}>ทั้งหมด</option>
            <option value="topup" {"selected" if mode_filter == "topup" else ""}>topup</option>
            <option value="donate" {"selected" if mode_filter == "donate" else ""}>donate</option>
          </select>
        </label>
        <label class="switch-row">
          <span>Status</span>
          <select name="status">
            <option value="" {"selected" if not status_filter else ""}>ทั้งหมด</option>
            <option value="pending" {"selected" if status_filter == "pending" else ""}>pending</option>
            <option value="paid" {"selected" if status_filter == "paid" else ""}>paid</option>
            <option value="expired" {"selected" if status_filter == "expired" else ""}>expired</option>
            <option value="cancelled" {"selected" if status_filter == "cancelled" else ""}>cancelled</option>
          </select>
        </label>
        <div class="auth-actions" style="justify-content:flex-start;">
          <button class="primary-btn" type="submit">ค้นหา</button>
          <a class="ghost-btn" href="/dashboard/admin/billing/history">ล้างตัวกรอง</a>
        </div>
      </form>
    </section>

    <section class="panel page-shell" style="margin-top:14px;">
      <h2 style="margin-top:0;">รายการชำระเงินทั้งหมด ({len(payment_rows)})</h2>
      <div style="overflow:auto;">
        <table class="audit-table">
          <thead>
            <tr>
              <th>Session</th>
              <th>Mode</th>
              <th>User</th>
              <th>Guild</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Verify</th>
              <th>Created</th>
              <th>Paid</th>
            </tr>
          </thead>
          <tbody>{''.join(payment_table_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class="panel page-shell" style="margin-top:14px;">
      <h2 style="margin-top:0;">Billing Events ({len(event_rows)})</h2>
      <div style="overflow:auto;">
        <table class="audit-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Level</th>
              <th>User</th>
              <th>Guild</th>
              <th>Message</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>{''.join(event_table_rows)}</tbody>
        </table>
      </div>
    </section>
    """
    return HTMLResponse(_render_layout(title="ประวัติการชำระเงิน - SkylineBOT", body=body, session=session, guilds=_manageable_guilds(session)))


def _safe_dashboard_redirect_path(raw_value: Any, fallback: str) -> str:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return fallback
    if any(ch in candidate for ch in ("\r", "\n", "\x00")):
        return fallback
    if candidate.startswith("//"):
        return fallback
    if not candidate.startswith("/dashboard"):
        return fallback
    return candidate


def _redirect_with_notice(path: str, notice: str) -> RedirectResponse:
    base = str(path or "/dashboard/wallet").strip() or "/dashboard/wallet"
    query = urlencode({"notice": str(notice or "").strip()})
    separator = "&" if "?" in base else "?"
    return RedirectResponse(url=f"{base}{separator}{query}", status_code=303)


async def dashboard_wallet_subscribe_plan(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/wallet", status_code=303)
    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/wallet?notice=ไม่พบผู้ใช้ในเซสชัน", status_code=303)

    form = await _parse_form(request)
    next_path = _safe_dashboard_redirect_path(form.get("next"), "/dashboard/wallet")
    try:
        guild_id = int(str(form.get("guild_id") or "0").strip())
    except Exception:
        guild_id = 0
    plan_tier = str(form.get("plan_tier") or "").strip().lower()
    auto_renew = _parse_bool_form(form, "auto_renew", True)
    if guild_id <= 0:
        return _redirect_with_notice(next_path, "Guild ID is invalid")

    manageable_ids = _manageable_guild_id_set(_manageable_guilds(session))
    if guild_id not in manageable_ids:
        return _redirect_with_notice(next_path, "You do not have permission for this guild")

    bot = get_bot()
    if not bot:
        return _redirect_with_notice(next_path, "Bot runtime is not ready")

    ok, message, _row = await billing_workflow.subscribe_guild_plan(
        bot=bot,
        guild_id=guild_id,
        user_id=int(user_id),
        plan_tier=plan_tier,
        auto_renew=auto_renew,
    )
    return _redirect_with_notice(next_path, message)


async def dashboard_wallet_cancel_plan(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/wallet", status_code=303)
    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/wallet?notice=ไม่พบผู้ใช้ในเซสชัน", status_code=303)

    form = await _parse_form(request)
    next_path = _safe_dashboard_redirect_path(form.get("next"), "/dashboard/wallet")
    try:
        guild_id = int(str(form.get("guild_id") or "0").strip())
    except Exception:
        guild_id = 0
    if guild_id <= 0:
        return _redirect_with_notice(next_path, "Guild ID is invalid")

    manageable_ids = _manageable_guild_id_set(_manageable_guilds(session))
    if guild_id not in manageable_ids:
        return _redirect_with_notice(next_path, "You do not have permission for this guild")

    ok, message, _row = await billing_workflow.cancel_guild_plan(
        guild_id=guild_id,
        user_id=int(user_id),
    )
    notice_text = message if ok else f"ยกเลิกไม่สำเร็จ: {message}"
    return _redirect_with_notice(next_path, notice_text)

async def dashboard_wallet_subscribe_user_app_plan(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/wallet", status_code=303)
    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/wallet?notice=User session was not found", status_code=303)

    form = await _parse_form(request)
    next_path = _safe_dashboard_redirect_path(form.get("next"), "/dashboard/wallet")
    auto_renew = _parse_bool_form(form, "auto_renew", True)

    ok, message, _row = await billing_workflow.subscribe_user_app_plan(
        user_id=int(user_id),
        auto_renew=auto_renew,
    )
    notice_text = message if ok else f"Failed to subscribe App User Plan: {message}"
    return _redirect_with_notice(next_path, notice_text)


async def dashboard_wallet_cancel_user_app_plan(request: Request):
    await _ensure_dashboard_config_cache()
    session = _session_from_request(request)
    if not session:
        return RedirectResponse(url="/dashboard/login?next=/dashboard/wallet", status_code=303)
    user_id = _session_user_id(session)
    if not user_id:
        return RedirectResponse(url="/dashboard/wallet?notice=User session was not found", status_code=303)

    form = await _parse_form(request)
    next_path = _safe_dashboard_redirect_path(form.get("next"), "/dashboard/wallet")

    ok, message, _row = await billing_workflow.cancel_user_app_plan(
        user_id=int(user_id),
    )
    notice_text = message if ok else f"Failed to cancel App User Plan: {message}"
    return _redirect_with_notice(next_path, notice_text)
