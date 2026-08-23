from __future__ import annotations

import datetime
import uuid
from typing import Any, Callable


def global_donatebot_settings(
    *,
    first_env_value_fn: Callable[..., str],
    normalize_http_url_fn: Callable[[Any], str],
    support_server_url: str,
) -> dict[str, str]:
    support_url = normalize_http_url_fn(
        first_env_value_fn(
            "DONATEBOT_SUPPORT_URL",
            "DONATEBOT_SUPPORT_SERVER",
            "SUPPORT_SERVER_URL",
        )
        or support_server_url
    )
    return {
        "truemoney_phone": first_env_value_fn(
            "DONATEBOT_TRUEMONEY_PHONE",
            "DONATE_TRUEMONEY_PHONE",
            "TRUEMONEY_PHONE",
        ),
        "promptpay_number": first_env_value_fn(
            "DONATEBOT_PROMPTPAY_NUMBER",
            "DONATE_PROMPTPAY_NUMBER",
            "PROMPTPAY_NUMBER",
        ),
        "bank_name": first_env_value_fn(
            "DONATEBOT_BANK_NAME",
            "DONATE_BANK_NAME",
            "BANK_NAME",
        ),
        "bank_account_number": first_env_value_fn(
            "DONATEBOT_BANK_ACCOUNT_NUMBER",
            "DONATE_BANK_ACCOUNT_NUMBER",
            "BANK_ACCOUNT_NUMBER",
        ),
        "bank_account_name": first_env_value_fn(
            "DONATEBOT_BANK_ACCOUNT_NAME",
            "DONATE_BANK_ACCOUNT_NAME",
            "BANK_ACCOUNT_NAME",
        ),
        "support_url": support_url,
    }


def donate_payment_method_label(method: Any) -> str:
    key = str(method or "").strip().lower()
    labels = {
        "truemoney": "TrueMoney",
        "promptpay": "พร้อมเพย์",
        "bank": "ธนาคาร",
        "slipverify": "SlipVerify",
        "other": "อื่น ๆ",
    }
    return labels.get(key, str(method or "อื่น ๆ"))


def normalize_donate_slip_status(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"approved", "pass", "passed", "success", "ผ่าน"}:
        return "approved"
    if value in {"rejected", "reject", "failed", "ไม่ผ่าน"}:
        return "rejected"
    return "pending"


def normalize_donate_slip_status_filter(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    if value in {"approved", "pass", "passed", "success", "ผ่าน"}:
        return "approved"
    if value in {"rejected", "reject", "failed", "ไม่ผ่าน"}:
        return "rejected"
    if value in {"pending", "wait", "waiting", "รอตรวจ"}:
        return "pending"
    return ""


def donate_slip_status_label(status: str) -> str:
    normalized = normalize_donate_slip_status(status)
    if normalized == "approved":
        return "ผ่าน"
    if normalized == "rejected":
        return "ไม่ผ่าน"
    return "รอตรวจ"


def normalize_donate_slip_log(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "slip_id": str(raw.get("slip_id") or uuid.uuid4().hex),
        "created_at": str(raw.get("created_at") or datetime.datetime.now(tz=datetime.timezone.utc).isoformat()),
        "status": normalize_donate_slip_status(raw.get("status")),
        "donor_name": str(raw.get("donor_name") or "ไม่ระบุชื่อ")[:80],
        "amount": int(raw.get("amount") or 0),
        "payment_method": str(raw.get("payment_method") or "other")[:30],
        "message": str(raw.get("message") or "")[:500],
        "image_url": str(raw.get("image_url") or "")[:500],
        "discord_channel_id": str(raw.get("discord_channel_id") or ""),
        "discord_message_id": str(raw.get("discord_message_id") or ""),
        "reviewed_at": str(raw.get("reviewed_at") or ""),
        "reviewed_by_id": str(raw.get("reviewed_by_id") or ""),
        "reviewed_by_name": str(raw.get("reviewed_by_name") or ""),
    }


def render_donate_slip_row_html(
    guild_id: int,
    row: dict[str, Any],
    *,
    with_actions: bool = True,
    normalize_donate_slip_status_fn: Callable[[Any], str],
    donate_slip_status_label_fn: Callable[[str], str],
    format_datetime_display_fn: Callable[[Any], str],
    safe_parse_datetime_fn: Callable[[Any], Any],
    escape_fn: Callable[[Any], str],
    donate_payment_method_label_fn: Callable[[Any], str],
) -> str:
    status_key = normalize_donate_slip_status_fn(row.get("status"))
    status_label = donate_slip_status_label_fn(status_key)
    status_class = f"slip-status-{status_key}"
    created_at = format_datetime_display_fn(safe_parse_datetime_fn(row.get("created_at")))
    reviewed_at = format_datetime_display_fn(safe_parse_datetime_fn(row.get("reviewed_at")))
    donor_name = escape_fn(row.get("donor_name") or "ไม่ระบุชื่อ")
    amount = int(row.get("amount") or 0)
    method_label = escape_fn(donate_payment_method_label_fn(row.get("payment_method")))
    note = escape_fn(row.get("message") or "-")
    reviewed_by = escape_fn(row.get("reviewed_by_name") or "-")
    slip_id = escape_fn(row.get("slip_id") or "")
    image_url = escape_fn(row.get("image_url") or "")
    image_link = (
        f'<a href="{image_url}" target="_blank" rel="noopener">ดูรูป</a>' if image_url else "-"
    )
    action_buttons = "-"
    if with_actions and slip_id:
        action_buttons = f"""
        <div class="slip-action-group">
          <form method="post" action="/dashboard/guild/{guild_id}/donate/slip/{slip_id}/status">
            <input type="hidden" name="status" value="pending">
            <button type="submit" class="ghost-btn">รอตรวจ</button>
          </form>
          <form method="post" action="/dashboard/guild/{guild_id}/donate/slip/{slip_id}/status">
            <input type="hidden" name="status" value="approved">
            <button type="submit" class="primary-btn">ผ่าน</button>
          </form>
          <form method="post" action="/dashboard/guild/{guild_id}/donate/slip/{slip_id}/status">
            <input type="hidden" name="status" value="rejected">
            <button type="submit" class="danger-btn">ไม่ผ่าน</button>
          </form>
        </div>
        """
    return f"""
    <tr>
      <td><code>{slip_id[:10]}</code></td>
      <td>{created_at}</td>
      <td>{donor_name}</td>
      <td>{amount:,}</td>
      <td>{method_label}</td>
      <td><span class="slip-status-badge {status_class}">{status_label}</span></td>
      <td>{note}</td>
      <td>{image_link}</td>
      <td>{reviewed_at}</td>
      <td>{reviewed_by}</td>
      <td>{action_buttons}</td>
    </tr>
    """
