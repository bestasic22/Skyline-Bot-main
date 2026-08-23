from __future__ import annotations

import datetime
import math
import re
from typing import Any

import discord

import storage
from skylinebot.workflows import billing


TRUEMONEY_GIFT_RE = re.compile(r"^https?://gift\.truemoney\.com/campaign/\?v=[A-Za-z0-9_-]{8,}$", re.I)


ORDER_STATUS_PENDING_PAYMENT = "pending_payment"
ORDER_STATUS_PENDING_REVIEW = "pending_review"
ORDER_STATUS_PAID = "paid"
ORDER_STATUS_DELIVERED = "delivered"
ORDER_STATUS_REJECTED = "rejected"
ORDER_STATUS_CANCELLED = "cancelled"

PLAN_ORDER: tuple[str, ...] = ("free", "silver", "golden", "diamond", "permanent")
SHOP_PRODUCT_LIMITS_BY_PLAN: dict[str, int] = {
    "free": 1,
    "silver": 3,
    "golden": 5,
    "diamond": 10,
    "permanent": 20,
}
SHOP_FEATURE_REQUIRED_PLAN: dict[str, str] = {
    "payment_truemoney_gift": "silver",
    "payment_shipok": "golden",
    "auto_verify": "silver",
    "auto_delivery": "golden",
    "delivery_dm_text": "silver",
    "delivery_role": "diamond",
    "auto_open_failed_delivery_ticket": "diamond",
}


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def normalize_plan_tier(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower()
    if value in {"silver", "silver_guild_preminum", "silver_guild_premium"}:
        return "silver"
    if value in {"gold", "gole", "golden", "golden_guild_premium", "gole_guild_premium"}:
        return "golden"
    if value in {"diamond", "diamond_guild_premium"}:
        return "diamond"
    if value in {"permanent", "lifetime", "forever", "permanent_guild_premium", "lifetime_guild_premium"}:
        return "permanent"
    return "free"


def plan_rank(raw_value: Any) -> int:
    tier = normalize_plan_tier(raw_value)
    try:
        return PLAN_ORDER.index(tier)
    except Exception:
        return 0


def is_plan_at_least(raw_plan: Any, required_plan: str) -> bool:
    return plan_rank(raw_plan) >= plan_rank(required_plan)


def product_limit_for_plan(raw_plan: Any) -> int:
    tier = normalize_plan_tier(raw_plan)
    return int(SHOP_PRODUCT_LIMITS_BY_PLAN.get(tier, SHOP_PRODUCT_LIMITS_BY_PLAN["free"]))


def is_shop_feature_allowed(raw_plan: Any, feature_key: str) -> bool:
    required = str(SHOP_FEATURE_REQUIRED_PLAN.get(str(feature_key or "").strip(), "free"))
    return is_plan_at_least(raw_plan, required)


def feature_required_plan(feature_key: str) -> str:
    return str(SHOP_FEATURE_REQUIRED_PLAN.get(str(feature_key or "").strip(), "free"))


async def guild_plan_tier(guild_id: int) -> str:
    row = await storage.guilds.get(guild_id=int(guild_id))
    subscription = (row or {}).get("subscription", "free")
    return normalize_plan_tier(subscription)


def parse_role_ids(value: Any, *, max_items: int = 40) -> list[int]:
    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item or "").strip() for item in value]
    else:
        text = str(value or "").replace("\n", ",")
        raw_items = [item.strip() for item in text.split(",")]
    out: list[int] = []
    for item in raw_items:
        digits = "".join(ch for ch in item if ch.isdigit())
        if not digits:
            continue
        try:
            role_id = int(digits)
        except Exception:
            continue
        if role_id in out:
            continue
        out.append(role_id)
        if len(out) >= max_items:
            break
    return out


def normalize_payment_mode(raw_value: Any) -> str:
    value = str(raw_value or "manual").strip().lower()
    if value in {"truemoney", "truemoneygift", "truemoney_gift", "gift"}:
        return "truemoney_gift"
    if value in {"shipok", "slipok", "slip"}:
        return "shipok"
    if value in {"wallet", "economy_wallet", "balance"}:
        return "wallet"
    return "manual"


def normalize_delivery_type(raw_value: Any) -> str:
    value = str(raw_value or "none").strip().lower()
    if value in {"role", "grant_role", "add_role"}:
        return "role"
    if value in {"dm", "codes", "code", "digital"}:
        return "dm"
    if value in {"text", "message"}:
        return "text"
    return "none"


def normalize_shop_settings(row: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(row or {})
    out = dict(data)
    out["enabled"] = bool(out.get("enabled"))
    out["currency_symbol"] = str(out.get("currency_symbol") or "THB").strip()[:12] or "THB"
    out["payment_mode"] = normalize_payment_mode(out.get("payment_mode"))
    out["allow_wallet_payment"] = bool(out.get("allow_wallet_payment"))
    out["auto_verify"] = bool(out.get("auto_verify"))
    out["auto_delivery"] = bool(out.get("auto_delivery"))
    out["auto_open_ticket_on_failed_delivery"] = bool(out.get("auto_open_ticket_on_failed_delivery"))
    out["promptpay_number"] = "".join(ch for ch in str(out.get("promptpay_number") or "") if ch.isdigit())[:20]
    out["truemoney_phone"] = "".join(ch for ch in str(out.get("truemoney_phone") or "") if ch.isdigit())[:20]
    out["truemoney_gift_enabled"] = bool(out.get("truemoney_gift_enabled", True))
    out["shipok_enabled"] = bool(out.get("shipok_enabled"))
    out["slipcheck_verify_engine"] = billing._normalize_slip_verify_engine(
        out.get("slipcheck_verify_engine") or "slipok",
        "slipok",
    )
    out["slipok_api_url"] = (
        str(out.get("slipok_api_url") or "https://api.slipok.com/api/line/apikey/1150").strip()[:280]
        or "https://api.slipok.com/api/line/apikey/1150"
    )
    out["slipok_key"] = str(out.get("slipok_key") or "").strip()[:240]
    out["slipcheck_expected_receiver_name"] = str(out.get("slipcheck_expected_receiver_name") or "").strip()[:220]
    out["slipcheck_expected_receiver_first_name_th"] = str(out.get("slipcheck_expected_receiver_first_name_th") or "").strip()[:120]
    out["slipcheck_expected_receiver_last_name_th"] = str(out.get("slipcheck_expected_receiver_last_name_th") or "").strip()[:120]
    out["slipcheck_expected_receiver_first_name_en"] = str(out.get("slipcheck_expected_receiver_first_name_en") or "").strip()[:120]
    out["slipcheck_expected_receiver_last_name_en"] = str(out.get("slipcheck_expected_receiver_last_name_en") or "").strip()[:120]
    out["slipcheck_expected_receiver_bank"] = str(out.get("slipcheck_expected_receiver_bank") or "").strip()[:220]
    out["slipcheck_expected_receiver_account"] = "".join(
        ch for ch in str(out.get("slipcheck_expected_receiver_account") or "") if ch.isdigit()
    )[:30]
    out["slipcheck_expected_sender_name"] = str(out.get("slipcheck_expected_sender_name") or "").strip()[:220]
    out["slipcheck_expected_sender_first_name_th"] = str(out.get("slipcheck_expected_sender_first_name_th") or "").strip()[:120]
    out["slipcheck_expected_sender_last_name_th"] = str(out.get("slipcheck_expected_sender_last_name_th") or "").strip()[:120]
    out["slipcheck_expected_sender_first_name_en"] = str(out.get("slipcheck_expected_sender_first_name_en") or "").strip()[:120]
    out["slipcheck_expected_sender_last_name_en"] = str(out.get("slipcheck_expected_sender_last_name_en") or "").strip()[:120]
    out["slipcheck_expected_sender_bank"] = str(out.get("slipcheck_expected_sender_bank") or "").strip()[:220]
    out["slipcheck_expected_sender_account"] = "".join(
        ch for ch in str(out.get("slipcheck_expected_sender_account") or "") if ch.isdigit()
    )[:30]
    out["slipcheck_expected_reference"] = str(out.get("slipcheck_expected_reference") or "").strip()[:120]
    out["slipcheck_expected_qr_reference"] = str(out.get("slipcheck_expected_qr_reference") or "").strip()[:300]
    try:
        out["slipcheck_max_age_minutes"] = max(0, min(60 * 24 * 30, int(float(out.get("slipcheck_max_age_minutes") or 1440))))
    except Exception:
        out["slipcheck_max_age_minutes"] = 1440
    try:
        out["slipcheck_auto_approve_confidence"] = round(
            max(0.0, min(100.0, float(out.get("slipcheck_auto_approve_confidence") or 85.0))),
            2,
        )
    except Exception:
        out["slipcheck_auto_approve_confidence"] = 85.0
    try:
        out["slipcheck_manual_review_confidence"] = round(
            max(0.0, min(100.0, float(out.get("slipcheck_manual_review_confidence") or 55.0))),
            2,
        )
    except Exception:
        out["slipcheck_manual_review_confidence"] = 55.0
    try:
        out["slipcheck_duplicate_window_hours"] = max(1, min(24 * 90, int(float(out.get("slipcheck_duplicate_window_hours") or 72))))
    except Exception:
        out["slipcheck_duplicate_window_hours"] = 72
    review_channel = str(out.get("slipcheck_review_channel_id") or "").strip()
    out["slipcheck_review_channel_id"] = int(review_channel) if review_channel.isdigit() else None
    dm_raw = str(out.get("slipcheck_review_dm_user_ids") or "").strip()
    dm_ids: list[str] = []
    for token in re.split(r"[\s,;]+", dm_raw):
        token = str(token or "").strip()
        if not token.isdigit() or token in dm_ids:
            continue
        dm_ids.append(token)
        if len(dm_ids) >= 20:
            break
    out["slipcheck_review_dm_user_ids"] = ",".join(dm_ids)
    out["support_role_ids"] = parse_role_ids(out.get("support_role_ids"))
    out["buyer_view_only_roles"] = bool(out.get("buyer_view_only_roles"))
    out["shop_channel_id"] = _safe_int(out.get("shop_channel_id"), 0) or None
    out["order_log_channel_id"] = _safe_int(out.get("order_log_channel_id"), 0) or None
    out["admin_contact_channel_id"] = _safe_int(out.get("admin_contact_channel_id"), 0) or None
    return out


def normalize_shop_product(row: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(row or {})
    out = dict(data)
    out["id"] = _safe_int(out.get("id"), 0)
    out["guild_id"] = _safe_int(out.get("guild_id"), 0)
    sku_text = str(out.get("sku") or "").strip().upper()
    if not sku_text and out["id"] > 0:
        sku_text = f"P{out['id']}"
    out["sku"] = re.sub(r"[^A-Z0-9_-]", "", sku_text)[:32] or "SKU"
    out["name"] = str(out.get("name") or "Unnamed Product").strip()[:120] or "Unnamed Product"
    out["description"] = str(out.get("description") or "").strip()[:2000]
    out["price"] = round(max(0.0, _safe_float(out.get("price"), 0.0)), 2)
    out["stock"] = _safe_int(out.get("stock"), 0)
    out["image_url"] = str(out.get("image_url") or "").strip()[:500]
    out["enabled"] = bool(out.get("enabled", True))
    out["visible_role_ids"] = parse_role_ids(out.get("visible_role_ids"))
    out["buy_role_ids"] = parse_role_ids(out.get("buy_role_ids"))
    out["delivery_type"] = normalize_delivery_type(out.get("delivery_type"))
    out["delivery_role_id"] = _safe_int(out.get("delivery_role_id"), 0) or None
    out["delivery_payload"] = str(out.get("delivery_payload") or "")
    out["delivery_note"] = str(out.get("delivery_note") or "").strip()[:1200]
    out["sort_order"] = _safe_int(out.get("sort_order"), 0)
    return out


def normalize_order(row: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(row or {})
    out = dict(data)
    out["id"] = _safe_int(out.get("id"), 0)
    out["guild_id"] = _safe_int(out.get("guild_id"), 0)
    out["user_id"] = _safe_int(out.get("user_id"), 0)
    out["product_id"] = _safe_int(out.get("product_id"), 0)
    out["quantity"] = max(1, _safe_int(out.get("quantity"), 1))
    out["unit_price"] = round(max(0.0, _safe_float(out.get("unit_price"), 0.0)), 2)
    out["total_price"] = round(max(0.0, _safe_float(out.get("total_price"), 0.0)), 2)
    out["order_code"] = str(out.get("order_code") or "").strip().upper()[:40]
    out["status"] = str(out.get("status") or ORDER_STATUS_PENDING_PAYMENT).strip().lower()
    out["verify_status"] = str(out.get("verify_status") or "pending").strip().lower()
    out["delivery_status"] = str(out.get("delivery_status") or "pending").strip().lower()
    out["payment_method"] = normalize_payment_mode(out.get("payment_method"))
    return out


async def ensure_shop_settings(guild_id: int) -> dict[str, Any]:
    row = await storage.shop_settings.get(guild_id=int(guild_id))
    if not row:
        row = await storage.shop_settings.insert(guild_id=int(guild_id))
    return normalize_shop_settings(row)


async def list_products(guild_id: int, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    rows = await storage.shop_products.gets(guild_id=int(guild_id)) or []
    products = [normalize_shop_product(row) for row in rows]
    if not include_disabled:
        products = [row for row in products if row.get("enabled")]
    products.sort(key=lambda row: (int(row.get("sort_order") or 0), int(row.get("id") or 0)))
    return products


def build_order_code(guild_id: int, order_no: int) -> str:
    gid = max(0, int(guild_id) % 10000)
    ono = max(0, int(order_no))
    return f"S{gid:04d}-{ono:06d}"


def _member_role_ids(member: discord.Member | None) -> set[int]:
    if member is None:
        return set()
    role_ids: set[int] = set()
    for role in list(getattr(member, "roles", []) or []):
        role_id = _safe_int(getattr(role, "id", 0), 0)
        if role_id > 0:
            role_ids.add(role_id)
    return role_ids


def can_view_product(*, role_ids: set[int], product: dict[str, Any], settings: dict[str, Any]) -> bool:
    visible_roles = parse_role_ids(product.get("visible_role_ids"))
    if visible_roles and not role_ids.intersection(set(visible_roles)):
        return False
    if bool(settings.get("buyer_view_only_roles")):
        buy_roles = parse_role_ids(product.get("buy_role_ids"))
        if buy_roles and not role_ids.intersection(set(buy_roles)):
            return False
    return True


def can_buy_product(*, role_ids: set[int], product: dict[str, Any]) -> bool:
    buy_roles = parse_role_ids(product.get("buy_role_ids"))
    if buy_roles and not role_ids.intersection(set(buy_roles)):
        return False
    return True


async def products_for_member(
    guild_id: int,
    member: discord.Member,
    *,
    include_disabled: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    settings = await ensure_shop_settings(guild_id)
    role_ids = _member_role_ids(member)
    all_products = await list_products(guild_id, include_disabled=include_disabled)
    visible = [
        row
        for row in all_products
        if can_view_product(role_ids=role_ids, product=row, settings=settings)
    ]
    return settings, visible


async def create_order(
    *,
    guild_id: int,
    user_id: int,
    product: dict[str, Any],
    quantity: int,
    payment_method: str,
    currency_symbol: str,
) -> dict[str, Any]:
    product_data = normalize_shop_product(product)
    qty = max(1, int(quantity))
    unit_price = round(max(0.0, _safe_float(product_data.get("price"), 0.0)), 2)
    total_price = round(unit_price * qty, 2)
    row = await storage.shop_orders.insert(
        guild_id=int(guild_id),
        order_code="",
        user_id=int(user_id),
        product_id=int(product_data.get("id") or 0),
        product_snapshot={
            "sku": product_data.get("sku"),
            "name": product_data.get("name"),
            "image_url": product_data.get("image_url"),
            "delivery_type": product_data.get("delivery_type"),
        },
        quantity=qty,
        unit_price=unit_price,
        total_price=total_price,
        currency_symbol=str(currency_symbol or "THB")[:12] or "THB",
        payment_method=normalize_payment_mode(payment_method),
        status=ORDER_STATUS_PENDING_PAYMENT,
        verify_status="pending",
        verify_note="Awaiting payment proof",
        delivery_status="pending",
        delivery_note="",
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    normalized = normalize_order(row)
    order_no = _safe_int((row or {}).get("order_no"), 0)
    if order_no <= 0:
        order_no = _safe_int((row or {}).get("id"), 0)
    order_code = build_order_code(int(guild_id), order_no)
    row = await storage.shop_orders.update(
        id=int(normalized.get("id") or 0),
        order_code=order_code,
        updated_at=_utc_now(),
    )
    return normalize_order(row)


async def verify_order_evidence(
    *,
    order: dict[str, Any],
    settings: dict[str, Any],
    transfer_link: str = "",
    slip_url: str = "",
    slip_qr_payload: str = "",
) -> tuple[str, str]:
    method = normalize_payment_mode(order.get("payment_method"))
    total_amount = round(max(0.0, _safe_float(order.get("total_price"), 0.0)), 2)
    transfer_link_text = str(transfer_link or "").strip()
    slip_url_text = str(slip_url or "").strip()
    slip_payload_text = str(slip_qr_payload or "").strip()

    if method == "truemoney_gift":
        if not transfer_link_text:
            return "pending", "Please submit a TrueMoney gift link first."
        if not TRUEMONEY_GIFT_RE.match(transfer_link_text):
            return "rejected", "TrueMoney gift link format is invalid."
        return await billing._verify_truemoney_gift_link(transfer_link_text, expected_amount=total_amount)

    if method == "shipok":
        if not bool(settings.get("shipok_enabled")):
            return "pending", "Slip verification is disabled by admin."
        verify_settings = {
            "slipcheck_verify_engine": settings.get("slipcheck_verify_engine") or "slipok",
            "slipok_api_url": settings.get("slipok_api_url") or "",
            "slipok_key": settings.get("slipok_key") or "",
            "slipcheck_expected_receiver_name": settings.get("slipcheck_expected_receiver_name") or "",
            "slipcheck_expected_receiver_first_name_th": settings.get("slipcheck_expected_receiver_first_name_th") or "",
            "slipcheck_expected_receiver_last_name_th": settings.get("slipcheck_expected_receiver_last_name_th") or "",
            "slipcheck_expected_receiver_first_name_en": settings.get("slipcheck_expected_receiver_first_name_en") or "",
            "slipcheck_expected_receiver_last_name_en": settings.get("slipcheck_expected_receiver_last_name_en") or "",
            "slipcheck_expected_receiver_bank": settings.get("slipcheck_expected_receiver_bank") or "",
            "slipcheck_expected_receiver_account": settings.get("slipcheck_expected_receiver_account") or "",
            "slipcheck_expected_sender_name": settings.get("slipcheck_expected_sender_name") or "",
            "slipcheck_expected_sender_first_name_th": settings.get("slipcheck_expected_sender_first_name_th") or "",
            "slipcheck_expected_sender_last_name_th": settings.get("slipcheck_expected_sender_last_name_th") or "",
            "slipcheck_expected_sender_first_name_en": settings.get("slipcheck_expected_sender_first_name_en") or "",
            "slipcheck_expected_sender_last_name_en": settings.get("slipcheck_expected_sender_last_name_en") or "",
            "slipcheck_expected_sender_bank": settings.get("slipcheck_expected_sender_bank") or "",
            "slipcheck_expected_sender_account": settings.get("slipcheck_expected_sender_account") or "",
            "slipcheck_expected_reference": settings.get("slipcheck_expected_reference") or "",
            "slipcheck_expected_qr_reference": settings.get("slipcheck_expected_qr_reference") or "",
            "slipcheck_max_age_minutes": settings.get("slipcheck_max_age_minutes"),
            "slipcheck_auto_approve_confidence": settings.get("slipcheck_auto_approve_confidence"),
            "slipcheck_manual_review_confidence": settings.get("slipcheck_manual_review_confidence"),
            "slipcheck_duplicate_window_hours": settings.get("slipcheck_duplicate_window_hours"),
        }
        detailed = await billing._verify_slip_evidence_detailed(
            settings=verify_settings,
            amount=total_amount,
            slip_url=slip_url_text,
            slip_qr_payload=slip_payload_text,
            transfer_reference=transfer_link_text,
            session_row=None,
        )
        status = str(detailed.get("status") or "pending")
        note = str(detailed.get("note") or "Slip verification pending.")
        confidence = float(detailed.get("confidence") or 0.0)
        matched_checks = int(detailed.get("matched_checks") or 0)
        total_checks = int(detailed.get("total_checks") or 0)
        note = f"{note} (match {matched_checks}/{total_checks}, {confidence:.2f}%)"
        return status, note[:500]

    return "pending", "This payment method requires manual review by guild admin."


def _consume_delivery_codes(payload: str, quantity: int) -> tuple[list[str], str]:
    lines = [line.strip() for line in str(payload or "").splitlines() if line.strip()]
    qty = max(1, int(quantity or 1))
    if len(lines) < qty:
        return [], payload
    selected = lines[:qty]
    remaining = "\n".join(lines[qty:])
    return selected, remaining


async def _deliver_to_member(
    *,
    bot,
    guild_id: int,
    user_id: int,
    product: dict[str, Any],
    quantity: int,
) -> tuple[bool, str, str, str | None]:
    guild = bot.get_guild(int(guild_id)) if bot else None
    member = guild.get_member(int(user_id)) if guild else None
    if member is None and guild is not None:
        try:
            member = await guild.fetch_member(int(user_id))
        except Exception:
            member = None
    if member is None:
        return False, "Member is not in this guild.", "", None

    delivery_type = normalize_delivery_type(product.get("delivery_type"))
    delivery_note = str(product.get("delivery_note") or "").strip()
    delivery_payload = str(product.get("delivery_payload") or "")

    if delivery_type == "role":
        role_id = _safe_int(product.get("delivery_role_id"), 0)
        role = guild.get_role(role_id) if guild and role_id > 0 else None
        if role is None:
            return False, "Delivery role is not configured or missing.", "", None
        try:
            await member.add_roles(role, reason="Shop auto delivery")
        except Exception:
            return False, "Bot failed to grant delivery role.", "", None
        return True, f"Granted role: {role.mention}", f"role:{role.id}", None

    if delivery_type == "dm":
        selected_codes, remaining_payload = _consume_delivery_codes(delivery_payload, quantity)
        if selected_codes:
            content = "\n".join(selected_codes)
        else:
            content = delivery_payload.strip() or delivery_note or "Thank you for your purchase."
            remaining_payload = None
        try:
            await member.send(
                f"Your order was delivered successfully.\n\n{content}"
            )
        except Exception:
            return False, "Failed to send delivery message via DM.", "", None
        return True, "Delivered via DM.", content[:1800], remaining_payload

    if delivery_type == "text":
        content = delivery_payload.strip() or delivery_note or "Thank you for your purchase."
        try:
            await member.send(f"Your order was delivered successfully.\n\n{content}")
        except Exception:
            return False, "Failed to send delivery text via DM.", "", None
        return True, "Delivered text via DM.", content[:1800], None

    return True, "No automatic delivery action configured.", "", None


async def open_failed_delivery_ticket(
    *,
    bot,
    order: dict[str, Any],
    settings: dict[str, Any],
    failure_reason: str,
) -> tuple[bool, str, int | None, int | None]:
    if not bot:
        return False, "Bot is not available for ticket automation.", None, None
    guild_id = _safe_int(order.get("guild_id"), 0)
    user_id = _safe_int(order.get("user_id"), 0)
    if guild_id <= 0 or user_id <= 0:
        return False, "Invalid guild/user for support ticket.", None, None

    guild = bot.get_guild(guild_id)
    if guild is None:
        return False, "Guild not found for support ticket.", None, None

    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            member = None
    if member is None:
        return False, "Member is not available for support ticket.", None, None

    modules = await storage.ticket_settings.gets(guild_id=guild_id, enabled=True) or []
    if not modules:
        return False, "Ticket module is not enabled in this guild.", None, None
    modules = sorted(modules, key=lambda row: int(row.get("ticket_module_id") or 0))
    module = modules[0]

    module_id = _safe_int(module.get("ticket_module_id"), 0)
    if module_id <= 0:
        return False, "Ticket module is invalid.", None, None

    ticket_limit = max(1, _safe_int(module.get("ticket_limit"), 1))
    opened_for_user = await storage.tickets.count(
        guild_id=guild_id,
        ticket_module_id=module_id,
        creator_id=user_id,
        closed=False,
    )
    if int(opened_for_user or 0) >= ticket_limit:
        return False, "User reached open ticket limit.", None, None

    open_category = None
    open_category_id = _safe_int(module.get("open_ticket_category_id"), 0)
    if open_category_id > 0:
        candidate = guild.get_channel(open_category_id)
        if candidate is not None and len(list(getattr(candidate, "channels", []) or [])) < 50:
            open_category = candidate

    ticket_row = await storage.tickets.insert(
        ticket_module_id=module_id,
        guild_id=guild_id,
        creator_id=user_id,
        closed=False,
    )
    if not ticket_row:
        return False, "Unable to create ticket row.", None, None

    ticket_id = _safe_int(ticket_row.get("ticket_id"), 0)
    channel_name = f"shop-help-{str(ticket_id).zfill(4)}"
    support_roles = parse_role_ids(module.get("support_roles"))

    overwrites: dict[Any, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
    }
    me = getattr(guild, "me", None)
    if me is not None:
        overwrites[me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
            attach_files=True,
            embed_links=True,
        )
    for role_id in support_roles:
        role = guild.get_role(int(role_id))
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            )

    try:
        ticket_channel = await guild.create_text_channel(
            name=channel_name[:95],
            category=open_category,
            topic=f"Shop support | order {str(order.get('order_code') or '-')[:60]}",
            overwrites=overwrites,
        )
    except Exception:
        try:
            await storage.tickets.delete(id=int(ticket_row.get("id") or 0))
        except Exception:
            pass
        return False, "Unable to create support ticket channel.", None, None

    try:
        await storage.tickets.update(
            id=int(ticket_row.get("id") or 0),
            channel_id=int(ticket_channel.id),
        )
    except Exception:
        pass

    try:
        order_code = str(order.get("order_code") or "-")
        note_text = str(failure_reason or "Delivery failed").strip()[:1000]
        await ticket_channel.send(
            f"{member.mention} Auto support ticket from shop.\n"
            f"Order: `{order_code}`\n"
            f"Reason: {note_text}"
        )
    except Exception:
        pass

    try:
        from skylinebot.src.modules import ticket_panel

        latest_ticket_row = await storage.tickets.get(id=int(ticket_row.get("id") or 0))
        if latest_ticket_row:
            await ticket_panel.send_close_ticket_module(latest_ticket_row, bot)
    except Exception:
        pass

    return True, f"Opened support ticket: {ticket_channel.mention}", int(ticket_channel.id), ticket_id


async def finalize_paid_order(
    *,
    bot,
    order_id: int,
    reviewer_user_id: int | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    row = await storage.shop_orders.get(id=int(order_id))
    if not row:
        return False, "Order not found.", None
    order = normalize_order(row)
    if order.get("status") in {ORDER_STATUS_DELIVERED, ORDER_STATUS_CANCELLED}:
        return False, "Order is already finished.", order

    product_row = await storage.shop_products.get(id=int(order.get("product_id") or 0))
    if not product_row:
        updated = await storage.shop_orders.update(
            id=int(order.get("id") or 0),
            status=ORDER_STATUS_REJECTED,
            delivery_status="failed",
            delivery_note="Product no longer exists.",
            updated_at=_utc_now(),
        )
        return False, "Product no longer exists.", normalize_order(updated)

    product = normalize_shop_product(product_row)
    current_plan = await guild_plan_tier(int(order.get("guild_id") or 0))
    current_delivery_type = normalize_delivery_type(product.get("delivery_type"))
    if current_delivery_type == "role" and not is_shop_feature_allowed(current_plan, "delivery_role"):
        product["delivery_type"] = "none"
    elif current_delivery_type in {"dm", "text"} and not is_shop_feature_allowed(current_plan, "delivery_dm_text"):
        product["delivery_type"] = "none"
    qty = max(1, int(order.get("quantity") or 1))
    stock = int(product.get("stock") or 0)
    if stock >= 0 and stock < qty:
        updated = await storage.shop_orders.update(
            id=int(order.get("id") or 0),
            status=ORDER_STATUS_REJECTED,
            delivery_status="failed",
            delivery_note="Product stock is not enough.",
            verify_note="Product stock is not enough.",
            updated_at=_utc_now(),
        )
        return False, "Product stock is not enough.", normalize_order(updated)

    ok_delivery, delivery_note, delivered_payload, remaining_payload = await _deliver_to_member(
        bot=bot,
        guild_id=int(order.get("guild_id") or 0),
        user_id=int(order.get("user_id") or 0),
        product=product,
        quantity=qty,
    )

    product_updates: dict[str, Any] = {"updated_at": _utc_now()}
    if stock >= 0:
        product_updates["stock"] = max(0, stock - qty)
    if remaining_payload is not None:
        product_updates["delivery_payload"] = remaining_payload
    try:
        await storage.shop_products.update(id=int(product.get("id") or 0), **product_updates)
    except Exception:
        pass

    if ok_delivery:
        updated_order = await storage.shop_orders.update(
            id=int(order.get("id") or 0),
            status=ORDER_STATUS_DELIVERED,
            delivery_status="delivered",
            delivery_note=delivery_note[:400],
            delivered_payload=delivered_payload,
            reviewed_by_user_id=int(reviewer_user_id or 0) or None,
            delivered_at=_utc_now(),
            updated_at=_utc_now(),
        )
        return True, delivery_note, normalize_order(updated_order)

    settings = await ensure_shop_settings(int(order.get("guild_id") or 0))
    extra_note = ""
    support_ticket_channel_id = _safe_int(order.get("support_ticket_channel_id"), 0) or None
    support_ticket_id = _safe_int(order.get("support_ticket_id"), 0) or None
    if (
        bool(settings.get("auto_open_ticket_on_failed_delivery"))
        and support_ticket_channel_id is None
    ):
        ok_ticket, ticket_message, opened_channel_id, opened_ticket_id = await open_failed_delivery_ticket(
            bot=bot,
            order=order,
            settings=settings,
            failure_reason=delivery_note,
        )
        extra_note = str(ticket_message or "")[:220]
        if ok_ticket:
            support_ticket_channel_id = opened_channel_id
            support_ticket_id = opened_ticket_id

    delivery_note_text = str(delivery_note or "").strip()
    if extra_note:
        delivery_note_text = f"{delivery_note_text} | {extra_note}".strip(" |")

    update_payload: dict[str, Any] = {
        "id": int(order.get("id") or 0),
        "status": ORDER_STATUS_PAID,
        "delivery_status": "failed",
        "delivery_note": delivery_note_text[:400],
        "reviewed_by_user_id": int(reviewer_user_id or 0) or None,
        "updated_at": _utc_now(),
    }
    if support_ticket_channel_id:
        update_payload["support_ticket_channel_id"] = int(support_ticket_channel_id)
    if support_ticket_id:
        update_payload["support_ticket_id"] = int(support_ticket_id)

    updated_order = await storage.shop_orders.update(**update_payload)
    return False, delivery_note_text, normalize_order(updated_order)


async def mark_order_verified(
    *,
    order_id: int,
    approved: bool,
    note: str,
    reviewer_user_id: int | None = None,
) -> dict[str, Any] | None:
    row = await storage.shop_orders.get(id=int(order_id))
    if not row:
        return None
    target_status = ORDER_STATUS_PAID if approved else ORDER_STATUS_REJECTED
    verify_status = "approved" if approved else "rejected"
    updated = await storage.shop_orders.update(
        id=int(row.get("id") or 0),
        status=target_status,
        verify_status=verify_status,
        verify_note=str(note or "")[:500],
        reviewed_by_user_id=int(reviewer_user_id or 0) or None,
        paid_at=_utc_now() if approved else None,
        updated_at=_utc_now(),
    )
    return normalize_order(updated)


async def ensure_economy_wallet(guild_id: int, user_id: int) -> dict[str, Any]:
    wallet = await storage.economy_wallets.get(guild_id=int(guild_id), user_id=int(user_id))
    if wallet:
        return wallet
    settings = await storage.economy_settings.get(guild_id=int(guild_id)) or {}
    start_cash = max(0, _safe_int(settings.get("start_cash"), 0))
    start_bank = max(0, _safe_int(settings.get("start_bank"), 0))
    await storage.economy_wallets.insert(
        guild_id=int(guild_id),
        user_id=int(user_id),
        cash=start_cash,
        bank=start_bank,
        total_earned=0,
        total_spent=0,
        updated_at=_utc_now(),
        created_at=_utc_now(),
    )
    return await storage.economy_wallets.get(guild_id=int(guild_id), user_id=int(user_id)) or {
        "guild_id": int(guild_id),
        "user_id": int(user_id),
        "cash": start_cash,
        "bank": start_bank,
        "total_spent": 0,
    }


async def debit_economy_wallet(
    *,
    guild_id: int,
    user_id: int,
    amount: float,
) -> tuple[bool, str, dict[str, Any] | None]:
    amount_value = round(max(0.0, float(amount or 0.0)), 2)
    if amount_value <= 0:
        return False, "Invalid amount.", None
    wallet = await ensure_economy_wallet(int(guild_id), int(user_id))
    cash = max(0, _safe_int(wallet.get("cash"), 0))
    bank = max(0, _safe_int(wallet.get("bank"), 0))
    total_funds = cash + bank
    required = int(math.ceil(amount_value))
    if total_funds < required:
        return False, f"Insufficient balance (need {required}, have {total_funds}).", wallet

    remaining = required
    use_cash = min(cash, remaining)
    remaining -= use_cash
    use_bank = min(bank, remaining)
    remaining -= use_bank
    if remaining > 0:
        return False, "Unable to allocate enough funds from wallet.", wallet

    updated = await storage.economy_wallets.update(
        id=int(wallet.get("id") or 0),
        cash=max(0, cash - use_cash),
        bank=max(0, bank - use_bank),
        total_spent=max(0, _safe_int(wallet.get("total_spent"), 0)) + required,
        updated_at=_utc_now(),
    )
    return True, f"Wallet charged {required} (cash {use_cash}, bank {use_bank}).", updated


async def mark_order_wallet_paid(
    *,
    order_id: int,
    note: str = "",
) -> dict[str, Any] | None:
    row = await storage.shop_orders.get(id=int(order_id))
    if not row:
        return None
    updated = await storage.shop_orders.update(
        id=int(row.get("id") or 0),
        payment_method="wallet",
        status=ORDER_STATUS_PAID,
        verify_status="approved",
        verify_note=(str(note or "").strip() or "Paid by wallet")[:500],
        paid_at=_utc_now(),
        updated_at=_utc_now(),
    )
    return normalize_order(updated)


def support_contact_hint(settings: dict[str, Any] | None) -> str:
    data = normalize_shop_settings(settings or {})
    parts: list[str] = []
    contact_channel_id = _safe_int(data.get("admin_contact_channel_id"), 0)
    if contact_channel_id > 0:
        parts.append(f"Contact channel: <#{contact_channel_id}>")
    support_roles = parse_role_ids(data.get("support_role_ids"))
    if support_roles:
        role_mentions = " ".join(f"<@&{role_id}>" for role_id in support_roles[:6])
        parts.append(f"Support roles: {role_mentions}")
    if not parts:
        return "Please contact guild staff for manual help."
    return " | ".join(parts)
