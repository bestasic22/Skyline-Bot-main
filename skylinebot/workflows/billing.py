from __future__ import annotations

import asyncio
import calendar
import datetime
import hashlib
import json
import os
import re
import time
import uuid
from typing import Any
from urllib.parse import quote

import httpx
from pymongo import ReturnDocument

import storage
from skylinebot.bridge.storage import get_collection, mongo_is_transient_cluster_error
from skylinebot.console.logging import logger
from skylinebot.memory.cache import cache
from skylinebot.workflows.subscription_actions import change_guild_subscription


PLAN_TO_SUBSCRIPTION_CODE: dict[str, str] = {
    "free": "free",
    "silver": "silver_guild_preminum",
    "golden": "golden_guild_premium",
    "diamond": "diamond_guild_premium",
    "permanent": "permanent_guild_premium",
}

SUBSCRIPTION_CODE_TO_PLAN: dict[str, str] = {
    "free": "free",
    "silver_guild_preminum": "silver",
    "golden_guild_premium": "golden",
    "diamond_guild_premium": "diamond",
    "permanent_guild_premium": "permanent",
}

PLAN_PRICE_THB: dict[str, float] = {
    "free": 0.0,
    "silver": 40.0,
    "golden": 120.0,
    "diamond": 250.0,
    "permanent": 500.0,
}

USER_APP_PLAN_CODE = "app_user"
USER_APP_PLAN_PRICE_THB = 69.0
PLAN_PRICING_CONFIG_KEY = "ownerbot_plan_pricing_settings_v1"
PLAN_PRICE_SETTING_KEYS: tuple[str, ...] = ("silver", "golden", "diamond", "permanent")
PLAN_PROMOTION_SETTING_KEYS: tuple[str, ...] = ("silver", "golden", "diamond", "permanent", USER_APP_PLAN_CODE)

PLAN_DURATION_DAYS = 30
PLAN_GRACE_DAYS = 1
PLAN_PURGE_AFTER_DAYS = 90
PAYMENT_SESSION_TTL_MINUTES = 10
PAYMENT_SESSION_VERIFY_INTERVAL_SECONDS = 30
BILLING_LOOP_INTERVAL_SECONDS = 30

TRUEMONEY_GIFT_RE = re.compile(r"^https?://gift\.truemoney\.com/campaign/\?v=[A-Za-z0-9_-]{8,}$", re.I)
TRUEMONEY_GIFT_AMOUNT_JSON_RE = re.compile(
    r'(?i)"(?:amount|amount_baht|voucher_amount|gift_amount|redeem_amount)"\s*:\s*"?(?P<amount>\d+(?:\.\d{1,2})?)"?'
)
TRUEMONEY_GIFT_AMOUNT_TEXT_RE = re.compile(r"(?i)(?P<amount>\d+(?:\.\d{1,2})?)\s*(?:thb|บาท)")
PAYMENT_PROVIDER_CONFIG_KEY = "ownerbot_payment_provider_settings_v1"
PAYMENT_PROVIDER_TYPES = {"promptpay", "truemoney"}
WALLET_ENABLED_PROVIDER_TYPES = {"promptpay", "truemoney"}

_billing_loop_running = False
_billing_transient_log_last_at = 0.0


def _log_billing_scheduler_error(error: Exception) -> None:
    global _billing_transient_log_last_at
    if mongo_is_transient_cluster_error(error):
        now = time.monotonic()
        if (now - float(_billing_transient_log_last_at or 0.0)) >= 45.0:
            _billing_transient_log_last_at = now
            logger.warning(f"Billing scheduler transient DB issue (will retry): {error}")
        return
    logger.error(f"Billing scheduler error: {error}")


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


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


def _normalize_plan(plan_tier: Any) -> str:
    normalized = str(plan_tier or "free").strip().lower()
    if normalized in PLAN_TO_SUBSCRIPTION_CODE:
        return normalized
    if normalized in SUBSCRIPTION_CODE_TO_PLAN:
        return SUBSCRIPTION_CODE_TO_PLAN[normalized]
    if normalized in {"gold", "gole"}:
        return "golden"
    if normalized in {"permanent", "lifetime", "forever", "permanent_guild_premium", "lifetime_guild_premium"}:
        return "permanent"
    return "free"


def _plan_price(plan_tier: Any) -> float:
    return float(PLAN_PRICE_THB.get(_normalize_plan(plan_tier), 0.0))


def _to_money(value: Any, default: float) -> float:
    try:
        amount = float(value)
    except Exception:
        amount = float(default)
    if amount < 0:
        amount = 0.0
    if amount > 1_000_000:
        amount = 1_000_000.0
    return round(float(amount), 2)


def _to_discount_percent(value: Any, default: float = 0.0) -> float:
    try:
        percent = float(value)
    except Exception:
        percent = float(default)
    if percent < 0:
        percent = 0.0
    if percent > 100:
        percent = 100.0
    return round(float(percent), 2)


def _to_int(value: Any, default: int = 0, minimum: int = 0, maximum: int = 9999) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = int(default)
    parsed = max(int(minimum), min(int(maximum), int(parsed)))
    return int(parsed)


def _add_months_utc(base: datetime.datetime, months: int) -> datetime.datetime:
    safe_months = max(0, int(months))
    if safe_months <= 0:
        return base
    year = int(base.year) + (int(base.month) - 1 + safe_months) // 12
    month = (int(base.month) - 1 + safe_months) % 12 + 1
    day = min(int(base.day), calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


def _default_plan_pricing_settings() -> dict[str, Any]:
    return {
        "guild_prices": {
            "silver": float(PLAN_PRICE_THB.get("silver", 40.0)),
            "golden": float(PLAN_PRICE_THB.get("golden", 120.0)),
            "diamond": float(PLAN_PRICE_THB.get("diamond", 250.0)),
            "permanent": float(PLAN_PRICE_THB.get("permanent", 500.0)),
        },
        "user_app_price": float(USER_APP_PLAN_PRICE_THB),
        "promotions": {
            key: {
                "discount_percent": 0.0,
                "start_at": "",
                "end_at": "",
                "duration_value": 0,
                "duration_unit": "day",
            }
            for key in PLAN_PROMOTION_SETTING_KEYS
        },
        "updated_at": "",
    }


def _normalize_plan_promotion_entry(payload: Any) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    discount_percent = _to_discount_percent(src.get("discount_percent"), 0.0)
    duration_value = _to_int(src.get("duration_value"), 0, 0, 1200)
    duration_unit = str(src.get("duration_unit") or "day").strip().lower()
    if duration_unit not in {"day", "month"}:
        duration_unit = "day"

    start_dt = _as_utc_datetime(src.get("start_at"))
    end_dt = _as_utc_datetime(src.get("end_at"))
    if start_dt and end_dt and end_dt <= start_dt:
        end_dt = None

    return {
        "discount_percent": discount_percent,
        "start_at": start_dt.isoformat() if start_dt else "",
        "end_at": end_dt.isoformat() if end_dt else "",
        "duration_value": duration_value,
        "duration_unit": duration_unit,
    }


def normalize_plan_pricing_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_plan_pricing_settings()

    guild_prices_payload = src.get("guild_prices")
    guild_prices_src = guild_prices_payload if isinstance(guild_prices_payload, dict) else {}
    guild_prices_out = dict(out["guild_prices"])
    for key in PLAN_PRICE_SETTING_KEYS:
        fallback_price = float(guild_prices_out.get(key) or PLAN_PRICE_THB.get(key, 0.0))
        guild_prices_out[key] = _to_money(guild_prices_src.get(key), fallback_price)
    out["guild_prices"] = guild_prices_out

    out["user_app_price"] = _to_money(src.get("user_app_price"), float(out.get("user_app_price") or USER_APP_PLAN_PRICE_THB))

    promotions_payload = src.get("promotions")
    promotions_src = promotions_payload if isinstance(promotions_payload, dict) else {}
    promotions_out = dict(out["promotions"])
    for key in PLAN_PROMOTION_SETTING_KEYS:
        promotions_out[key] = _normalize_plan_promotion_entry(promotions_src.get(key))
    out["promotions"] = promotions_out

    updated_at_dt = _as_utc_datetime(src.get("updated_at"))
    out["updated_at"] = updated_at_dt.isoformat() if updated_at_dt else ""
    return out


async def get_plan_pricing_settings() -> dict[str, Any]:
    row = await storage.dashboard_config.get(config_key=PLAN_PRICING_CONFIG_KEY)
    if not row:
        return normalize_plan_pricing_settings({})
    raw = str(row.get("config_value") or "").strip()
    if not raw:
        return normalize_plan_pricing_settings({})
    try:
        decoded = json.loads(raw)
    except Exception:
        return normalize_plan_pricing_settings({})
    return normalize_plan_pricing_settings(decoded if isinstance(decoded, dict) else {})


def _plan_price_quote_from_components(
    *,
    key: str,
    plan_tier: str,
    base_price: float,
    promo_entry: dict[str, Any] | None,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    now_utc = now or _utc_now()
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
    promo = promo_entry if isinstance(promo_entry, dict) else {}
    discount_percent = _to_discount_percent(promo.get("discount_percent"), 0.0)
    promo_start_dt = _as_utc_datetime(promo.get("start_at"))
    promo_end_dt = _as_utc_datetime(promo.get("end_at"))
    if promo_start_dt and promo_end_dt and promo_end_dt <= promo_start_dt:
        promo_end_dt = None

    promo_active = (
        discount_percent > 0
        and promo_end_dt is not None
        and (promo_start_dt is None or now_utc >= promo_start_dt)
        and now_utc < promo_end_dt
    )
    promo_scheduled = (
        discount_percent > 0
        and promo_start_dt is not None
        and promo_end_dt is not None
        and now_utc < promo_start_dt
    )
    promo_expired = (
        discount_percent > 0
        and promo_end_dt is not None
        and now_utc >= promo_end_dt
    )

    safe_base = _to_money(base_price, 0.0)
    final_price = safe_base
    if promo_active and safe_base > 0:
        final_price = round(safe_base * max(0.0, (100.0 - discount_percent)) / 100.0, 2)
    discount_amount = round(max(0.0, safe_base - final_price), 2)
    if not promo_active:
        discount_amount = 0.0
    if safe_base <= 0:
        final_price = 0.0
        discount_amount = 0.0
        promo_active = False
        promo_scheduled = False
        promo_expired = False

    if promo_active:
        promo_status = "active"
    elif promo_scheduled:
        promo_status = "scheduled"
    elif promo_expired:
        promo_status = "expired"
    else:
        promo_status = "inactive"

    return {
        "key": key,
        "plan_tier": plan_tier,
        "base_price": safe_base,
        "final_price": round(final_price, 2),
        "discount_percent": discount_percent if promo_active else 0.0,
        "discount_amount": discount_amount,
        "promo_active": bool(promo_active),
        "promo_status": promo_status,
        "promo_start_at": promo_start_dt.isoformat() if promo_start_dt else "",
        "promo_end_at": promo_end_dt.isoformat() if promo_end_dt else "",
        "promo_duration_value": _to_int(promo.get("duration_value"), 0, 0, 1200),
        "promo_duration_unit": str(promo.get("duration_unit") or "day").strip().lower() or "day",
    }


def build_plan_price_quote(
    plan_tier: Any,
    *,
    settings: dict[str, Any] | None = None,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    cfg = normalize_plan_pricing_settings(settings if isinstance(settings, dict) else {})
    normalized = _normalize_plan(plan_tier)
    if normalized == "free":
        return _plan_price_quote_from_components(
            key="free",
            plan_tier="free",
            base_price=0.0,
            promo_entry={},
            now=now,
        )
    if normalized not in PLAN_PRICE_SETTING_KEYS:
        normalized = "free"
    base_price = float((cfg.get("guild_prices") or {}).get(normalized, PLAN_PRICE_THB.get(normalized, 0.0)) or 0.0)
    promo_entry = (cfg.get("promotions") or {}).get(normalized, {})
    return _plan_price_quote_from_components(
        key=normalized,
        plan_tier=normalized,
        base_price=base_price,
        promo_entry=promo_entry,
        now=now,
    )


def build_user_app_price_quote(
    *,
    settings: dict[str, Any] | None = None,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    cfg = normalize_plan_pricing_settings(settings if isinstance(settings, dict) else {})
    base_price = float(cfg.get("user_app_price") or USER_APP_PLAN_PRICE_THB)
    promo_entry = (cfg.get("promotions") or {}).get(USER_APP_PLAN_CODE, {})
    quote = _plan_price_quote_from_components(
        key=USER_APP_PLAN_CODE,
        plan_tier=USER_APP_PLAN_CODE,
        base_price=base_price,
        promo_entry=promo_entry,
        now=now,
    )
    quote["scope"] = "user"
    return quote


def build_plan_pricing_snapshot_from_settings(
    settings: dict[str, Any] | None,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    cfg = normalize_plan_pricing_settings(settings if isinstance(settings, dict) else {})
    now_utc = now or _utc_now()
    quotes = {
        "free": build_plan_price_quote("free", settings=cfg, now=now_utc),
        "silver": build_plan_price_quote("silver", settings=cfg, now=now_utc),
        "golden": build_plan_price_quote("golden", settings=cfg, now=now_utc),
        "diamond": build_plan_price_quote("diamond", settings=cfg, now=now_utc),
        "permanent": build_plan_price_quote("permanent", settings=cfg, now=now_utc),
        USER_APP_PLAN_CODE: build_user_app_price_quote(settings=cfg, now=now_utc),
    }
    return {
        "settings": cfg,
        "quotes": quotes,
        "generated_at": now_utc.isoformat(),
    }


async def get_plan_pricing_snapshot() -> dict[str, Any]:
    settings = await get_plan_pricing_settings()
    return build_plan_pricing_snapshot_from_settings(settings)


def _normalize_user_app_plan(plan_tier: Any) -> str:
    normalized = str(plan_tier or "free").strip().lower()
    mapping = {
        "free": "free",
        "app_user": USER_APP_PLAN_CODE,
        "app": USER_APP_PLAN_CODE,
        "discord_app": USER_APP_PLAN_CODE,
        "discord_app_user": USER_APP_PLAN_CODE,
        "user_app": USER_APP_PLAN_CODE,
        "user_app_plan": USER_APP_PLAN_CODE,
    }
    return mapping.get(normalized, "free")


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, tuple):
        return list(value)
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _is_truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _normalize_provider_type(value: Any, fallback: str = "promptpay") -> str:
    raw = str(value or "").strip().lower()
    if raw in {"truemoney", "true_money", "truewallet", "tmwallet", "tmw"}:
        raw = "truemoney"
    if raw in {"promptpay", "pp"}:
        raw = "promptpay"
    if raw in PAYMENT_PROVIDER_TYPES:
        return raw
    fallback_raw = str(fallback or "promptpay").strip().lower()
    if fallback_raw in {"truemoney", "true_money", "truewallet", "tmwallet", "tmw"}:
        fallback_raw = "truemoney"
    return fallback_raw if fallback_raw in PAYMENT_PROVIDER_TYPES else "promptpay"


def payment_provider_is_enabled(settings: dict[str, Any] | None, provider_type: Any) -> bool:
    cfg = settings if isinstance(settings, dict) else {}
    provider = _normalize_provider_type(provider_type, "promptpay")
    if provider == "promptpay":
        return True
    if provider == "truemoney":
        return _is_truthy(cfg.get("enable_truemoney_qr_provider"), True)
    return False


def resolve_active_payment_provider(
    *,
    settings: dict[str, Any] | None,
    selected_provider: Any,
) -> tuple[str, str]:
    requested_provider = _normalize_provider_type(selected_provider, "promptpay")
    if payment_provider_is_enabled(settings, requested_provider):
        return requested_provider, ""
    fallback_note = f"Provider '{requested_provider}' is disabled; fallback to PromptPay/TrueMoney."
    return "promptpay", fallback_note


def validate_payment_provider_settings(
    *,
    settings: dict[str, Any] | None,
    mode: str = "topup",
    provider_type: str | None = None,
) -> tuple[bool, str, list[str]]:
    cfg = settings if isinstance(settings, dict) else {}
    mode_value = str(mode or "topup").strip().lower()
    if mode_value not in {"topup", "donate"}:
        mode_value = "topup"

    selected_provider = provider_type
    if not selected_provider:
        selected_provider = cfg.get("topup_provider" if mode_value == "topup" else "donate_provider")
    provider = _normalize_provider_type(selected_provider, "promptpay")
    if provider not in WALLET_ENABLED_PROVIDER_TYPES:
        return False, provider, [f"Provider '{provider}' is disabled. Only PromptPay QR and TrueMoney QR are available."]
    if not payment_provider_is_enabled(cfg, provider):
        return False, provider, [f"Provider '{provider}' is disabled by admin toggle."]

    promptpay_number = str(cfg.get("promptpay_number") or "").strip()
    truemoney_phone = str(cfg.get("truemoney_phone") or "").strip()

    issues: list[str] = []
    if provider == "promptpay":
        # Keep PromptPay separated from TrueMoney: use PromptPay number only.
        promptpay_candidate = "".join(ch for ch in promptpay_number if ch.isdigit())
        if not promptpay_candidate:
            issues.append("PromptPay number is not configured")
        elif len(promptpay_candidate) < 10:
            issues.append("PromptPay number must contain at least 10 digits")
    elif provider == "truemoney":
        create_url = str(cfg.get("truemoney_create_payment_url") or "").strip()
        inquiry_url = str(cfg.get("truemoney_inquiry_url") or "").strip()
        callback_url = str(cfg.get("truemoney_callback_url") or "").strip()
        tm_has_auth = any(
            str(cfg.get(key) or "").strip()
            for key in ("truemoney_bearer_token", "truemoney_api_key", "truemoney_api_secret")
        )
        if not create_url:
            issues.append("TrueMoney create payment URL is not configured")
        if not inquiry_url and not callback_url:
            issues.append("TrueMoney requires inquiry URL or callback URL")
        if not tm_has_auth:
            issues.append("TrueMoney API credentials are not configured")

    return len(issues) == 0, provider, issues


def manual_proof_enabled_for_session(settings: dict[str, Any] | None, provider_type: Any, mode: Any) -> bool:
    provider_key = str(provider_type or "").strip().lower()
    return provider_key in {"promptpay", "truemoney"}


def _default_payment_settings_from_env() -> dict[str, Any]:
    promptpay_number = (
        str(os.getenv("BOT_TOPUP_PROMPTPAY_NUMBER", "") or "").strip()
        or str(os.getenv("DONATEBOT_PROMPTPAY_NUMBER", "") or "").strip()
        or str(os.getenv("PROMPTPAY_NUMBER", "") or "").strip()
    )
    promptpay_account_name = str(
        os.getenv(
            "BOT_PROMPTPAY_ACCOUNT_NAME",
            os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NAME", ""),
        )
        or ""
    ).strip()
    truemoney_phone = (
        str(os.getenv("BOT_TOPUP_TRUEMONEY_PHONE", "") or "").strip()
        or str(os.getenv("DONATEBOT_TRUEMONEY_PHONE", "") or "").strip()
        or str(os.getenv("TRUEMONEY_PHONE", "") or "").strip()
        or "0889463459"
    )
    truemoney_gift_phone = str(os.getenv("BOT_TRUEMONEY_GIFT_PHONE", "") or "").strip()
    webhook_secret = str(os.getenv("BOT_PAYMENT_WEBHOOK_SECRET", "") or "").strip()
    topup_provider = _normalize_provider_type(os.getenv("BOT_TOPUP_PROVIDER", "promptpay"), "promptpay")
    donate_provider = _normalize_provider_type(os.getenv("BOT_DONATE_PROVIDER", topup_provider), topup_provider)

    return {
        "topup_provider": topup_provider,
        "donate_provider": donate_provider,
        "enable_truemoney_qr_provider": _is_truthy(os.getenv("BOT_ENABLE_TRUEMONEY_QR_PROVIDER", "true"), True),
        "promptpay_account_name": promptpay_account_name,
        "promptpay_number": promptpay_number,
        "truemoney_phone": truemoney_phone,
        "truemoney_gift_phone": truemoney_gift_phone,
        "truemoney_gift_url": str(os.getenv("BOT_TRUEMONEY_GIFT_URL", "") or "").strip(),
        "webhook_secret": webhook_secret,
        "slipok_api_url": (
            str(
                os.getenv(
                    "BOT_SLIPOK_API_URL",
                    os.getenv("SLIPOK_API_URL", "https://api.slipok.com/api/line/apikey/1150"),
                )
                or "https://api.slipok.com/api/line/apikey/1150"
            ).strip()
        ),
        "slipok_key": str(os.getenv("BOT_SLIPOK_KEY", os.getenv("SLIPOK_KEY", "")) or "").strip(),
        "slipcheck_verify_engine": str(os.getenv("BOT_SLIPCHECK_VERIFY_ENGINE", "slipok") or "slipok").strip().lower(),
        "slipcheck_expected_receiver_name": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_NAME", os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NAME", "")) or "").strip(),
        "slipcheck_expected_receiver_first_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_FIRST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_receiver_last_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_LAST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_receiver_first_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_FIRST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_receiver_last_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_LAST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_receiver_bank": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_BANK", os.getenv("BOT_PAYMENT_BANK_NAME", "")) or "").strip(),
        "slipcheck_expected_receiver_account": str(os.getenv("BOT_SLIPCHECK_EXPECTED_RECEIVER_ACCOUNT", os.getenv("BOT_PAYMENT_BANK_ACCOUNT_NUMBER", "")) or "").strip(),
        "slipcheck_expected_sender_name": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_NAME", "") or "").strip(),
        "slipcheck_expected_sender_first_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_FIRST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_sender_last_name_th": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_LAST_NAME_TH", "") or "").strip(),
        "slipcheck_expected_sender_first_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_FIRST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_sender_last_name_en": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_LAST_NAME_EN", "") or "").strip(),
        "slipcheck_expected_sender_bank": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_BANK", "") or "").strip(),
        "slipcheck_expected_sender_account": str(os.getenv("BOT_SLIPCHECK_EXPECTED_SENDER_ACCOUNT", "") or "").strip(),
        "slipcheck_expected_reference": str(os.getenv("BOT_SLIPCHECK_EXPECTED_REFERENCE", "") or "").strip(),
        "slipcheck_expected_qr_reference": str(os.getenv("BOT_SLIPCHECK_EXPECTED_QR_REFERENCE", "") or "").strip(),
        "slipcheck_max_age_minutes": str(os.getenv("BOT_SLIPCHECK_MAX_AGE_MINUTES", "1440") or "1440").strip(),
        "slipcheck_auto_approve_confidence": str(os.getenv("BOT_SLIPCHECK_AUTO_APPROVE_CONFIDENCE", "85") or "85").strip(),
        "slipcheck_manual_review_confidence": str(os.getenv("BOT_SLIPCHECK_MANUAL_REVIEW_CONFIDENCE", "55") or "55").strip(),
        "slipcheck_duplicate_window_hours": str(os.getenv("BOT_SLIPCHECK_DUPLICATE_WINDOW_HOURS", "72") or "72").strip(),
        "slipcheck_review_channel_id": str(os.getenv("BOT_SLIPCHECK_REVIEW_CHANNEL_ID", "") or "").strip(),
        "slipcheck_review_dm_user_ids": str(os.getenv("BOT_SLIPCHECK_REVIEW_DM_USER_IDS", "") or "").strip(),
        "slipcheck_low_confidence_route": str(
            os.getenv("BOT_SLIPCHECK_LOW_CONFIDENCE_ROUTE", "both") or "both"
        ).strip().lower(),
        "truemoney_create_payment_url": str(os.getenv("BOT_TRUEMONEY_CREATE_PAYMENT_URL", "") or "").strip(),
        "truemoney_inquiry_url": str(os.getenv("BOT_TRUEMONEY_INQUIRY_URL", "") or "").strip(),
        "truemoney_api_key": str(os.getenv("BOT_TRUEMONEY_API_KEY", "") or "").strip(),
        "truemoney_api_secret": str(os.getenv("BOT_TRUEMONEY_API_SECRET", "") or "").strip(),
        "truemoney_bearer_token": str(os.getenv("BOT_TRUEMONEY_BEARER_TOKEN", "") or "").strip(),
        "truemoney_callback_url": str(os.getenv("BOT_TRUEMONEY_CALLBACK_URL", "") or "").strip(),
        "truemoney_webhook_secret": (
            str(os.getenv("BOT_TRUEMONEY_WEBHOOK_SECRET", "") or "").strip()
            or webhook_secret
        ),
        "truemoney_signature_header": (
            str(os.getenv("BOT_TRUEMONEY_SIGNATURE_HEADER", "x-truemoney-signature") or "x-truemoney-signature").strip().lower()
            or "x-truemoney-signature"
        ),
        "truemoney_signature_prefix": str(os.getenv("BOT_TRUEMONEY_SIGNATURE_PREFIX", "") or "").strip(),
        "truemoney_signature_algorithm": (
            str(os.getenv("BOT_TRUEMONEY_SIGNATURE_ALGORITHM", "sha256") or "sha256").strip().lower()
        ),
        "truemoney_amount_field": str(os.getenv("BOT_TRUEMONEY_AMOUNT_FIELD", "amount") or "amount").strip(),
        "truemoney_currency_field": str(os.getenv("BOT_TRUEMONEY_CURRENCY_FIELD", "currency") or "currency").strip(),
        "truemoney_reference_field": str(os.getenv("BOT_TRUEMONEY_REFERENCE_FIELD", "reference") or "reference").strip(),
        "truemoney_callback_field": str(os.getenv("BOT_TRUEMONEY_CALLBACK_FIELD", "callbackUrl") or "callbackUrl").strip(),
        "truemoney_qr_image_field": str(os.getenv("BOT_TRUEMONEY_QR_IMAGE_FIELD", "data.qrImageUrl") or "data.qrImageUrl").strip(),
        "truemoney_qr_code_field": str(os.getenv("BOT_TRUEMONEY_QR_CODE_FIELD", "data.qrRawData") or "data.qrRawData").strip(),
        "truemoney_payment_url_field": str(os.getenv("BOT_TRUEMONEY_PAYMENT_URL_FIELD", "data.paymentUrl") or "data.paymentUrl").strip(),
        "truemoney_reference_resp_field": str(os.getenv("BOT_TRUEMONEY_REFERENCE_RESP_FIELD", "data.orderId") or "data.orderId").strip(),
        "truemoney_transaction_id_field": str(os.getenv("BOT_TRUEMONEY_TRANSACTION_ID_FIELD", "data.transactionId") or "data.transactionId").strip(),
        "truemoney_inquiry_status_field": str(os.getenv("BOT_TRUEMONEY_INQUIRY_STATUS_FIELD", "data.status") or "data.status").strip(),
        "truemoney_paid_status_values": str(
            os.getenv("BOT_TRUEMONEY_PAID_STATUS_VALUES", "paid,success,completed,settled")
            or "paid,success,completed,settled"
        ).strip(),
        "truemoney_auto_verify": _is_truthy(os.getenv("BOT_TRUEMONEY_AUTO_VERIFY", "true"), True),
    }


def _normalize_payment_settings(payload: dict[str, Any] | None, *, seed: dict[str, Any] | None = None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = dict(seed or _default_payment_settings_from_env())

    out["topup_provider"] = _normalize_provider_type(src.get("topup_provider"), str(out.get("topup_provider") or "promptpay"))
    out["donate_provider"] = _normalize_provider_type(src.get("donate_provider"), str(out.get("donate_provider") or "promptpay"))
    out["enable_truemoney_qr_provider"] = _is_truthy(
        src.get("enable_truemoney_qr_provider"),
        _is_truthy(out.get("enable_truemoney_qr_provider"), True),
    )
    out["slipok_api_url"] = str(
        src.get("slipok_api_url")
        or out.get("slipok_api_url")
        or "https://api.slipok.com/api/line/apikey/1150"
    ).strip()[:300] or "https://api.slipok.com/api/line/apikey/1150"
    out["slipok_key"] = str(src.get("slipok_key") or out.get("slipok_key") or "").strip()[:240]
    out["slipcheck_verify_engine"] = _normalize_slip_verify_engine(
        src.get("slipcheck_verify_engine") or out.get("slipcheck_verify_engine") or "slipok",
        "slipok",
    )
    out["slipcheck_expected_receiver_name"] = str(
        src.get("slipcheck_expected_receiver_name")
        or out.get("slipcheck_expected_receiver_name")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_receiver_first_name_th"] = str(
        src.get("slipcheck_expected_receiver_first_name_th")
        or out.get("slipcheck_expected_receiver_first_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_last_name_th"] = str(
        src.get("slipcheck_expected_receiver_last_name_th")
        or out.get("slipcheck_expected_receiver_last_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_first_name_en"] = str(
        src.get("slipcheck_expected_receiver_first_name_en")
        or out.get("slipcheck_expected_receiver_first_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_last_name_en"] = str(
        src.get("slipcheck_expected_receiver_last_name_en")
        or out.get("slipcheck_expected_receiver_last_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_receiver_bank"] = str(
        src.get("slipcheck_expected_receiver_bank")
        or out.get("slipcheck_expected_receiver_bank")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_receiver_account"] = "".join(
        ch for ch in str(
            src.get("slipcheck_expected_receiver_account")
            or out.get("slipcheck_expected_receiver_account")
            or ""
        ) if ch.isdigit()
    )[:30]
    out["slipcheck_expected_sender_name"] = str(
        src.get("slipcheck_expected_sender_name")
        or out.get("slipcheck_expected_sender_name")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_sender_first_name_th"] = str(
        src.get("slipcheck_expected_sender_first_name_th")
        or out.get("slipcheck_expected_sender_first_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_last_name_th"] = str(
        src.get("slipcheck_expected_sender_last_name_th")
        or out.get("slipcheck_expected_sender_last_name_th")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_first_name_en"] = str(
        src.get("slipcheck_expected_sender_first_name_en")
        or out.get("slipcheck_expected_sender_first_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_last_name_en"] = str(
        src.get("slipcheck_expected_sender_last_name_en")
        or out.get("slipcheck_expected_sender_last_name_en")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_sender_bank"] = str(
        src.get("slipcheck_expected_sender_bank")
        or out.get("slipcheck_expected_sender_bank")
        or ""
    ).strip()[:220]
    out["slipcheck_expected_sender_account"] = "".join(
        ch for ch in str(
            src.get("slipcheck_expected_sender_account")
            or out.get("slipcheck_expected_sender_account")
            or ""
        ) if ch.isdigit()
    )[:30]
    out["slipcheck_expected_reference"] = str(
        src.get("slipcheck_expected_reference")
        or out.get("slipcheck_expected_reference")
        or ""
    ).strip()[:120]
    out["slipcheck_expected_qr_reference"] = str(
        src.get("slipcheck_expected_qr_reference")
        or out.get("slipcheck_expected_qr_reference")
        or ""
    ).strip()[:300]
    try:
        out["slipcheck_max_age_minutes"] = str(
            max(
                0,
                min(
                    60 * 24 * 30,
                    int(float(src.get("slipcheck_max_age_minutes") or out.get("slipcheck_max_age_minutes") or 1440)),
                ),
            )
        )
    except Exception:
        out["slipcheck_max_age_minutes"] = "1440"
    try:
        out["slipcheck_auto_approve_confidence"] = str(
            round(
                max(
                    50.0,
                    min(
                        100.0,
                        float(src.get("slipcheck_auto_approve_confidence") or out.get("slipcheck_auto_approve_confidence") or 85.0),
                    ),
                ),
                2,
            )
        )
    except Exception:
        out["slipcheck_auto_approve_confidence"] = "85"
    try:
        out["slipcheck_manual_review_confidence"] = str(
            round(
                max(
                    0.0,
                    min(
                        100.0,
                        float(src.get("slipcheck_manual_review_confidence") or out.get("slipcheck_manual_review_confidence") or 55.0),
                    ),
                ),
                2,
            )
        )
    except Exception:
        out["slipcheck_manual_review_confidence"] = "55"
    try:
        out["slipcheck_duplicate_window_hours"] = str(
            max(
                1,
                min(
                    24 * 90,
                    int(float(src.get("slipcheck_duplicate_window_hours") or out.get("slipcheck_duplicate_window_hours") or 72)),
                ),
            )
        )
    except Exception:
        out["slipcheck_duplicate_window_hours"] = "72"
    review_channel = str(
        src.get("slipcheck_review_channel_id")
        or out.get("slipcheck_review_channel_id")
        or ""
    ).strip()
    out["slipcheck_review_channel_id"] = review_channel if review_channel.isdigit() else ""
    out["slipcheck_review_dm_user_ids"] = ",".join(
        _slip_parse_id_list(
            src.get("slipcheck_review_dm_user_ids")
            or out.get("slipcheck_review_dm_user_ids")
            or ""
        )
    )[:600]
    route_raw = str(
        src.get("slipcheck_low_confidence_route")
        or out.get("slipcheck_low_confidence_route")
        or "both"
    ).strip().lower()
    if route_raw in {"embed", "embed_channel", "channel", "room", "guild", "discord"}:
        out["slipcheck_low_confidence_route"] = "channel"
    elif route_raw in {"dm", "direct", "direct_message", "directmessage", "user_dm"}:
        out["slipcheck_low_confidence_route"] = "dm"
    else:
        out["slipcheck_low_confidence_route"] = "both"
    out["promptpay_number"] = "".join(
        ch for ch in str(src.get("promptpay_number") or out.get("promptpay_number") or "").strip() if ch.isdigit()
    )[:20]
    out["promptpay_account_name"] = str(
        src.get("promptpay_account_name")
        or out.get("promptpay_account_name")
        or ""
    ).strip()[:120]
    out["truemoney_phone"] = "".join(
        ch for ch in str(src.get("truemoney_phone") or out.get("truemoney_phone") or "").strip() if ch.isdigit()
    )[:20]
    truemoney_gift_phone = "".join(
        ch
        for ch in str(
            src.get("truemoney_gift_phone")
            or out.get("truemoney_gift_phone")
            or ""
        ).strip()
        if ch.isdigit()
    )[:20]
    out["truemoney_gift_phone"] = truemoney_gift_phone
    out["truemoney_gift_url"] = str(
        src.get("truemoney_gift_url")
        or out.get("truemoney_gift_url")
        or ""
    ).strip()[:500]
    out["webhook_secret"] = str(src.get("webhook_secret") or out.get("webhook_secret") or "").strip()[:240]
    out["truemoney_create_payment_url"] = str(
        src.get("truemoney_create_payment_url")
        or out.get("truemoney_create_payment_url")
        or ""
    ).strip()[:280]
    out["truemoney_inquiry_url"] = str(
        src.get("truemoney_inquiry_url")
        or out.get("truemoney_inquiry_url")
        or ""
    ).strip()[:280]
    out["truemoney_api_key"] = str(src.get("truemoney_api_key") or out.get("truemoney_api_key") or "").strip()[:120]
    out["truemoney_api_secret"] = str(src.get("truemoney_api_secret") or out.get("truemoney_api_secret") or "").strip()[:240]
    out["truemoney_bearer_token"] = str(src.get("truemoney_bearer_token") or out.get("truemoney_bearer_token") or "").strip()[:500]
    out["truemoney_callback_url"] = str(src.get("truemoney_callback_url") or out.get("truemoney_callback_url") or "").strip()[:255]
    out["truemoney_webhook_secret"] = (
        str(src.get("truemoney_webhook_secret") or out.get("truemoney_webhook_secret") or "").strip()[:240]
        or out["webhook_secret"]
    )
    tm_signature_header = str(src.get("truemoney_signature_header") or out.get("truemoney_signature_header") or "").strip().lower()
    out["truemoney_signature_header"] = tm_signature_header[:80] or "x-truemoney-signature"
    out["truemoney_signature_prefix"] = str(src.get("truemoney_signature_prefix") or out.get("truemoney_signature_prefix") or "").strip()[:24]
    tm_signature_algorithm = str(src.get("truemoney_signature_algorithm") or out.get("truemoney_signature_algorithm") or "").strip().lower()
    out["truemoney_signature_algorithm"] = tm_signature_algorithm if tm_signature_algorithm in {"sha256", "sha1", "md5"} else "sha256"
    out["truemoney_amount_field"] = str(src.get("truemoney_amount_field") or out.get("truemoney_amount_field") or "amount").strip()[:120] or "amount"
    out["truemoney_currency_field"] = str(src.get("truemoney_currency_field") or out.get("truemoney_currency_field") or "currency").strip()[:120] or "currency"
    out["truemoney_reference_field"] = str(src.get("truemoney_reference_field") or out.get("truemoney_reference_field") or "reference").strip()[:120] or "reference"
    out["truemoney_callback_field"] = str(src.get("truemoney_callback_field") or out.get("truemoney_callback_field") or "callbackUrl").strip()[:120] or "callbackUrl"
    out["truemoney_qr_image_field"] = str(src.get("truemoney_qr_image_field") or out.get("truemoney_qr_image_field") or "data.qrImageUrl").strip()[:120] or "data.qrImageUrl"
    out["truemoney_qr_code_field"] = str(src.get("truemoney_qr_code_field") or out.get("truemoney_qr_code_field") or "data.qrRawData").strip()[:120] or "data.qrRawData"
    out["truemoney_payment_url_field"] = str(src.get("truemoney_payment_url_field") or out.get("truemoney_payment_url_field") or "data.paymentUrl").strip()[:120] or "data.paymentUrl"
    out["truemoney_reference_resp_field"] = str(src.get("truemoney_reference_resp_field") or out.get("truemoney_reference_resp_field") or "data.orderId").strip()[:120] or "data.orderId"
    out["truemoney_transaction_id_field"] = str(src.get("truemoney_transaction_id_field") or out.get("truemoney_transaction_id_field") or "data.transactionId").strip()[:120] or "data.transactionId"
    out["truemoney_inquiry_status_field"] = str(src.get("truemoney_inquiry_status_field") or out.get("truemoney_inquiry_status_field") or "data.status").strip()[:120] or "data.status"
    out["truemoney_paid_status_values"] = str(
        src.get("truemoney_paid_status_values")
        or out.get("truemoney_paid_status_values")
        or "paid,success,completed,settled"
    ).strip()[:300] or "paid,success,completed,settled"
    out["truemoney_auto_verify"] = _is_truthy(
        src.get("truemoney_auto_verify"),
        _is_truthy(out.get("truemoney_auto_verify"), True),
    )
    return out


async def get_payment_provider_settings() -> dict[str, Any]:
    env_default = _default_payment_settings_from_env()
    row = await storage.dashboard_config.get(config_key=PAYMENT_PROVIDER_CONFIG_KEY)
    if not row:
        return _normalize_payment_settings({}, seed=env_default)
    raw = str(row.get("config_value") or "").strip()
    if not raw:
        return _normalize_payment_settings({}, seed=env_default)
    try:
        decoded = json.loads(raw)
    except Exception:
        return _normalize_payment_settings({}, seed=env_default)
    return _normalize_payment_settings(decoded if isinstance(decoded, dict) else {}, seed=env_default)


async def _payment_settings() -> dict[str, Any]:
    return await get_payment_provider_settings()


def _promptpay_qr_url(promptpay_number: str, amount: float) -> str:
    number = "".join(ch for ch in str(promptpay_number or "").strip() if ch.isdigit())
    if not number:
        return ""
    fixed_amount = f"{max(0.0, float(amount or 0.0)):.2f}"
    return f"https://promptpay.io/{number}/{fixed_amount}.png"


def _extract_truemoney_gift_amount(page_text: str) -> float | None:
    source = str(page_text or "")
    if not source:
        return None
    compact = source.replace(",", "")
    for regex in (TRUEMONEY_GIFT_AMOUNT_JSON_RE, TRUEMONEY_GIFT_AMOUNT_TEXT_RE):
        match = regex.search(compact)
        if not match:
            continue
        try:
            amount = round(float(match.group("amount")), 2)
        except Exception:
            continue
        if 0 < amount <= 1_000_000:
            return amount
    return None


def _payload_path_get(payload: Any, path: str) -> Any:
    current = payload
    for part in str(path or "").split("."):
        key = str(part or "").strip()
        if not key:
            return None
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _payload_path_set(payload: dict[str, Any], path: str, value: Any) -> None:
    if not isinstance(payload, dict):
        return
    parts = [str(part or "").strip() for part in str(path or "").split(".") if str(part or "").strip()]
    if not parts:
        return
    current: dict[str, Any] = payload
    for key in parts[:-1]:
        nested = current.get(key)
        if not isinstance(nested, dict):
            nested = {}
            current[key] = nested
        current = nested
    current[parts[-1]] = value


def _payload_first_text(payload: Any, candidates: tuple[str, ...]) -> str:
    if not isinstance(payload, dict):
        return ""
    for candidate in candidates:
        value = _payload_path_get(payload, candidate) if "." in candidate else payload.get(candidate)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _qr_image_url_from_payload(qr_image_raw: str, qr_raw_data: str) -> str:
    qr_image_text = str(qr_image_raw or "").strip()
    if qr_image_text.lower().startswith("http://") or qr_image_text.lower().startswith("https://"):
        return qr_image_text
    if qr_image_text.lower().startswith("data:image"):
        return qr_image_text
    if qr_image_text:
        compact = "".join(ch for ch in qr_image_text if ch not in {"\n", "\r", "\t", " "})
        return f"data:image/png;base64,{compact}"
    qr_raw_text = str(qr_raw_data or "").strip()
    if qr_raw_text:
        return f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={quote(qr_raw_text, safe='')}"
    return ""


def _truemoney_paid_status_set(settings: dict[str, Any]) -> set[str]:
    raw_values = str(settings.get("truemoney_paid_status_values") or "paid,success,completed,settled").strip().lower()
    tokens: set[str] = set()
    for token in re.split(r"[,\s|;/]+", raw_values):
        normalized = str(token or "").strip().lower()
        if normalized:
            tokens.add(normalized)
    if not tokens:
        tokens = {"paid", "success", "completed", "settled"}
    tokens.update({"paid", "success", "completed", "settled", "approved", "ok", "1", "true", "00", "1000"})
    return tokens


def _truemoney_status_is_paid(status_value: Any, settings: dict[str, Any]) -> bool:
    normalized = str(status_value or "").strip().lower()
    if not normalized:
        return False
    allowed = _truemoney_paid_status_set(settings)
    if normalized in allowed:
        return True
    return any(normalized.startswith(f"{token}_") for token in allowed if token.isalpha())


def _truemoney_headers(settings: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {"content-type": "application/json"}
    api_key = str(settings.get("truemoney_api_key") or "").strip()
    api_secret = str(settings.get("truemoney_api_secret") or "").strip()
    bearer_token = str(settings.get("truemoney_bearer_token") or "").strip()
    if bearer_token:
        if bearer_token.lower().startswith("bearer "):
            headers["authorization"] = bearer_token
        else:
            headers["authorization"] = f"Bearer {bearer_token}"
    if api_key:
        headers.setdefault("x-api-key", api_key)
        headers.setdefault("resourceOwnerId", api_key)
    if api_secret:
        headers.setdefault("x-api-secret", api_secret)
    headers.setdefault("requestUId", str(uuid.uuid4()))
    return headers


async def _truemoney_generate_qr(
    *,
    settings: dict[str, Any],
    session_key: str,
    mode: str,
    amount: float,
    note: str = "",
) -> tuple[bool, str, dict[str, Any]]:
    create_url = str(settings.get("truemoney_create_payment_url") or "").strip()
    if not create_url:
        return False, "ยังไม่ได้ตั้งค่า TrueMoney create payment URL", {}

    amount_value = round(float(amount or 0.0), 2)
    amount_text = f"{amount_value:.2f}"
    mode_value = str(mode or "topup").strip().lower()
    reference_value = f"{'D' if mode_value == 'donate' else 'T'}{str(session_key or '').strip().upper()}"[:64]
    callback_url = str(settings.get("truemoney_callback_url") or "").strip()
    amount_field = str(settings.get("truemoney_amount_field") or "amount").strip()
    currency_field = str(settings.get("truemoney_currency_field") or "currency").strip()
    reference_field = str(settings.get("truemoney_reference_field") or "reference").strip()
    callback_field = str(settings.get("truemoney_callback_field") or "callbackUrl").strip()

    request_payload: dict[str, Any] = {
        "amount": amount_text,
        "currency": "THB",
        "reference": reference_value,
        "order_id": reference_value,
        "session_key": str(session_key or "").strip(),
        "mode": mode_value,
        "metadata": {"session_key": str(session_key or "").strip(), "mode": mode_value},
    }
    if note:
        request_payload["description"] = str(note or "").strip()[:160]
    if amount_field:
        _payload_path_set(request_payload, amount_field, amount_text)
    if currency_field:
        _payload_path_set(request_payload, currency_field, "THB")
    if reference_field:
        _payload_path_set(request_payload, reference_field, reference_value)
    if callback_field and callback_url:
        _payload_path_set(request_payload, callback_field, callback_url)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                create_url,
                headers=_truemoney_headers(settings),
                json=request_payload,
            )
        payload = response.json() if response.content else {}
    except Exception as exc:
        logger.error(f"[billing.truemoney] create qr request failed: {exc}")
        return False, "เรียก TrueMoney create API ไม่สำเร็จ", {}

    if not isinstance(payload, dict):
        payload = {}

    if response.status_code >= 400:
        message = _payload_first_text(payload, ("message", "error", "status.message", "detail"))
        if not message:
            message = f"TrueMoney create API ตอบกลับ HTTP {response.status_code}"
        return False, message, {"raw": payload}

    qr_image_field = str(settings.get("truemoney_qr_image_field") or "data.qrImageUrl").strip()
    qr_code_field = str(settings.get("truemoney_qr_code_field") or "data.qrRawData").strip()
    payment_url_field = str(settings.get("truemoney_payment_url_field") or "data.paymentUrl").strip()
    reference_resp_field = str(settings.get("truemoney_reference_resp_field") or "data.orderId").strip()
    transaction_id_field = str(settings.get("truemoney_transaction_id_field") or "data.transactionId").strip()

    qr_image_raw = _payload_path_get(payload, qr_image_field) if qr_image_field else None
    qr_code_raw = _payload_path_get(payload, qr_code_field) if qr_code_field else None
    payment_url_raw = _payload_path_get(payload, payment_url_field) if payment_url_field else None
    reference_raw = _payload_path_get(payload, reference_resp_field) if reference_resp_field else None
    transaction_id_raw = _payload_path_get(payload, transaction_id_field) if transaction_id_field else None

    qr_code_text = str(qr_code_raw or _payload_first_text(payload, ("qrCode", "qrRawData", "data.qrCode", "data.qrRawData"))).strip()
    qr_image_text = str(qr_image_raw or _payload_first_text(payload, ("qrImageUrl", "qrImage", "data.qrImageUrl", "data.qrImage"))).strip()
    payment_url_text = str(payment_url_raw or _payload_first_text(payload, ("paymentUrl", "checkoutUrl", "data.paymentUrl", "data.checkoutUrl"))).strip()
    reference_text = str(reference_raw or _payload_first_text(payload, ("orderId", "reference", "data.orderId", "data.reference")) or reference_value).strip()[:120]
    transaction_id_text = str(transaction_id_raw or _payload_first_text(payload, ("transactionId", "data.transactionId", "txnId"))).strip()[:120]
    qr_image_url = _qr_image_url_from_payload(qr_image_text, qr_code_text)

    if not qr_image_url and not qr_code_text and not payment_url_text:
        return False, "TrueMoney create API ไม่พบข้อมูล QR หรือ payment URL", {"raw": payload}

    return True, "", {
        "raw": payload,
        "request": request_payload,
        "qr_image_url": qr_image_url,
        "qr_code": qr_code_text,
        "payment_url": payment_url_text,
        "reference": reference_text or reference_value,
        "transaction_id": transaction_id_text,
    }


async def _truemoney_inquire_payment(
    *,
    settings: dict[str, Any],
    session_row: dict[str, Any],
) -> tuple[bool, str, dict[str, Any]]:
    inquiry_url = str(settings.get("truemoney_inquiry_url") or "").strip()
    if not inquiry_url:
        return False, "ยังไม่ได้ตั้งค่า TrueMoney inquiry URL", {}

    meta = session_row.get("meta")
    meta_payload = dict(meta) if isinstance(meta, dict) else {}
    reference_value = str(
        meta_payload.get("truemoney_reference")
        or session_row.get("transfer_reference")
        or session_row.get("session_key")
        or ""
    ).strip()
    if not reference_value:
        return False, "ไม่พบ TrueMoney reference สำหรับตรวจสอบรายการ", {}

    amount_value = round(float(session_row.get("amount") or 0.0), 2)
    amount_text = f"{amount_value:.2f}"
    reference_field = str(settings.get("truemoney_reference_field") or "reference").strip()
    amount_field = str(settings.get("truemoney_amount_field") or "amount").strip()
    currency_field = str(settings.get("truemoney_currency_field") or "currency").strip()
    inquiry_payload: dict[str, Any] = {
        "reference": reference_value,
        "order_id": reference_value,
    }
    if reference_field:
        _payload_path_set(inquiry_payload, reference_field, reference_value)
    if amount_field:
        _payload_path_set(inquiry_payload, amount_field, amount_text)
    if currency_field:
        _payload_path_set(inquiry_payload, currency_field, "THB")
    transaction_id_value = str(meta_payload.get("truemoney_transaction_id") or "").strip()
    if transaction_id_value:
        inquiry_payload["transaction_id"] = transaction_id_value

    response: httpx.Response | None = None
    payload: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(inquiry_url, headers=_truemoney_headers(settings), json=inquiry_payload)
            if response.status_code in {404, 405}:
                response = await client.get(inquiry_url, headers=_truemoney_headers(settings), params={"reference": reference_value})
        payload = response.json() if response and response.content else {}
    except Exception as exc:
        logger.error(f"[billing.truemoney] inquiry request failed: {exc}")
        return False, "เรียก TrueMoney inquiry API ไม่สำเร็จ", {}

    if not isinstance(payload, dict):
        payload = {}

    if not response:
        return False, "TrueMoney inquiry API ไม่ได้ตอบกลับข้อมูล", {}
    if response.status_code >= 400:
        message = _payload_first_text(payload, ("message", "error", "status.message", "detail"))
        if not message:
            message = f"TrueMoney inquiry API ตอบกลับ HTTP {response.status_code}"
        return False, message, {"truemoney_inquiry_raw_response": payload}

    status_field = str(settings.get("truemoney_inquiry_status_field") or "data.status").strip()
    status_value = str(
        (_payload_path_get(payload, status_field) if status_field else None)
        or _payload_first_text(payload, ("status", "paymentStatus", "data.status", "data.paymentStatus", "result", "state"))
    ).strip()
    paid_flag = str(_payload_first_text(payload, ("paid", "isPaid", "is_paid", "data.paid"))).strip().lower()
    is_paid = _truemoney_status_is_paid(status_value, settings) or paid_flag in {"1", "true", "yes"}

    tx_field = str(settings.get("truemoney_transaction_id_field") or "data.transactionId").strip()
    tx_value = str(
        (_payload_path_get(payload, tx_field) if tx_field else None)
        or _payload_first_text(payload, ("transactionId", "txId", "data.transactionId"))
        or transaction_id_value
    ).strip()[:120]

    if is_paid:
        note = "TrueMoney inquiry ยืนยันการชำระเงินสำเร็จ"
        if tx_value:
            note = f"{note} (transactionId: {tx_value})"
        return True, note, {
            "truemoney_inquiry_raw_response": payload,
            "truemoney_inquiry_status": status_value,
            "truemoney_transaction_id": tx_value,
            "truemoney_inquiry_checked_at": _utc_now().isoformat(),
        }

    return False, "TrueMoney inquiry ยังไม่พบสถานะชำระเงินสำเร็จ", {
        "truemoney_inquiry_raw_response": payload,
        "truemoney_inquiry_status": status_value,
        "truemoney_inquiry_checked_at": _utc_now().isoformat(),
    }


def _session_expired(session_row: dict[str, Any], *, now: datetime.datetime | None = None) -> bool:
    now_utc = now or _utc_now()
    expires_at = _as_utc_datetime(session_row.get("expires_at"))
    if not expires_at:
        return False
    return expires_at <= now_utc


async def is_billing_managed_guild(guild_id: int) -> bool:
    row = await storage.bot_plan_subscriptions.get(guild_id=int(guild_id))
    return bool(row)


async def ensure_wallet_account(user_id: int) -> dict[str, Any]:
    user_id = int(user_id)
    row = await storage.bot_wallet_accounts.get(user_id=user_id)
    if row:
        return row
    await storage.bot_wallet_accounts.insert(user_id=user_id)
    return await storage.bot_wallet_accounts.get(user_id=user_id) or {"user_id": user_id, "balance": 0.0}


async def get_wallet_balance(user_id: int) -> float:
    row = await ensure_wallet_account(int(user_id))
    try:
        return float(row.get("balance") or 0.0)
    except Exception:
        return 0.0


async def _append_billing_event(
    *,
    user_id: int | None,
    guild_id: int | None,
    event_type: str,
    message: str,
    level: str = "info",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return await storage.bot_billing_events.insert(
        user_id=int(user_id) if user_id else None,
        guild_id=int(guild_id) if guild_id else None,
        event_type=str(event_type or "info")[:120],
        message=str(message or "")[:2000],
        level=str(level or "info")[:30],
        meta=meta or {},
    )


async def credit_wallet(
    *,
    user_id: int,
    amount: float,
    kind: str,
    source_mode: str,
    session_key: str = "",
    guild_id: int | None = None,
    note: str = "",
    meta: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    amount_value = round(float(amount or 0.0), 2)
    if amount_value <= 0:
        return False, "Invalid amount.", None

    user_id_int = int(user_id)
    session_key_text = str(session_key or "").strip()
    kind_text = str(kind or "credit")
    source_mode_text = str(source_mode or "topup")
    if session_key_text:
        existing_ledger = await storage.bot_wallet_ledger.get(
            user_id=user_id_int,
            session_key=session_key_text,
            kind=kind_text,
            source_mode=source_mode_text,
        )
        if existing_ledger:
            return True, "Wallet top-up already processed.", existing_ledger

    now_utc = _utc_now()
    collection = await get_collection(storage.bot_wallet_accounts.COLLECTION_NAME)
    row_after = await collection.find_one_and_update(
        {"user_id": user_id_int},
        {
            "$inc": {"balance": amount_value},
            "$set": {"updated_at": now_utc},
            "$setOnInsert": {"created_at": now_utc, "locked_balance": 0.0},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if not row_after:
        return False, "Unable to update wallet balance.", None

    balance_after = float(row_after.get("balance") or 0.0)
    balance_before = round(balance_after - amount_value, 2)
    ledger_row = await storage.bot_wallet_ledger.insert(
        user_id=user_id_int,
        guild_id=int(guild_id) if guild_id else None,
        amount=amount_value,
        balance_before=balance_before,
        balance_after=balance_after,
        kind=kind_text,
        source_mode=source_mode_text,
        session_key=session_key_text,
        note=str(note or "")[:300],
        meta=meta or {},
    )
    await _append_billing_event(
        user_id=user_id_int,
        guild_id=guild_id,
        event_type="wallet_credit",
        message=f"Wallet credited +{amount_value:.2f} THB",
        level="success",
        meta={"kind": kind_text, "source_mode": source_mode_text, "session_key": session_key_text},
    )
    return True, "Wallet top-up completed.", ledger_row


async def debit_wallet(
    *,
    user_id: int,
    amount: float,
    kind: str,
    source_mode: str,
    session_key: str = "",
    guild_id: int | None = None,
    note: str = "",
    meta: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    amount_value = round(float(amount or 0.0), 2)
    if amount_value <= 0:
        return False, "Invalid amount.", None

    user_id_int = int(user_id)
    now_utc = _utc_now()
    collection = await get_collection(storage.bot_wallet_accounts.COLLECTION_NAME)
    row_after = await collection.find_one_and_update(
        {"user_id": user_id_int, "balance": {"$gte": amount_value}},
        {"$inc": {"balance": -amount_value}, "$set": {"updated_at": now_utc}},
        return_document=ReturnDocument.AFTER,
    )
    if not row_after:
        return False, "Insufficient wallet balance.", None

    balance_after = float(row_after.get("balance") or 0.0)
    balance_before = round(balance_after + amount_value, 2)
    ledger_row = await storage.bot_wallet_ledger.insert(
        user_id=user_id_int,
        guild_id=int(guild_id) if guild_id else None,
        amount=-amount_value,
        balance_before=balance_before,
        balance_after=balance_after,
        kind=str(kind or "debit"),
        source_mode=str(source_mode or "topup"),
        session_key=str(session_key or ""),
        note=str(note or "")[:300],
        meta=meta or {},
    )
    return True, "Wallet debited successfully.", ledger_row


async def create_payment_session(
    *,
    user_id: int,
    amount: float,
    mode: str,
    provider_type_override: str = "",
    guild_id: int | None = None,
    plan_tier: str = "",
    note: str = "",
) -> tuple[bool, str, dict[str, Any] | None]:
    amount_value = round(float(amount or 0.0), 2)
    if amount_value <= 0:
        return False, "Amount must be greater than 0.", None

    mode_value = str(mode or "topup").strip().lower()
    if mode_value not in {"topup", "donate"}:
        return False, "Invalid payment mode.", None
    if mode_value == "topup" and amount_value < 10:
        return False, "Amount must be at least 10 THB.", None

    settings = await _payment_settings()
    promptpay_number = str(settings.get("promptpay_number") or "").strip()
    truemoney_phone = str(settings.get("truemoney_phone") or "").strip()
    # Keep PromptPay QR isolated from TrueMoney phone.
    effective_promptpay_number = promptpay_number
    provider_selected_raw = (
        provider_type_override
        or settings.get("topup_provider" if mode_value == "topup" else "donate_provider")
    )
    requested_provider_type = _normalize_provider_type(provider_selected_raw, "promptpay")
    provider_type, provider_fallback_note = resolve_active_payment_provider(
        settings=settings,
        selected_provider=requested_provider_type,
    )

    provider_ready, provider_type, readiness_issues = validate_payment_provider_settings(
        settings=settings,
        mode=mode_value,
        provider_type=provider_type,
    )
    if not provider_ready:
        return False, str(readiness_issues[0] if readiness_issues else "Payment provider is not configured."), None
    if provider_type not in WALLET_ENABLED_PROVIDER_TYPES:
        return False, "Only PromptPay QR and TrueMoney QR are supported for wallet topup.", None

    session_key = uuid.uuid4().hex
    now_utc = _utc_now()
    expires_at = now_utc + datetime.timedelta(minutes=PAYMENT_SESSION_TTL_MINUTES)

    qr_image_url = ""
    provider_name = "PromptPay QR"
    verification_mode = "manual_slip"
    requires_manual_proof = True
    provider_note = "Pay via PromptPay QR and verify slip with SlipOK."
    if provider_fallback_note:
        provider_note = f"{provider_note} (fallback from {requested_provider_type})"
    meta: dict[str, Any] = {}
    if provider_fallback_note:
        meta["provider_fallback_note"] = provider_fallback_note
        meta["requested_provider_type"] = requested_provider_type

    if provider_type == "promptpay":
        qr_image_url = _promptpay_qr_url(effective_promptpay_number, amount_value)
        if not qr_image_url:
            return False, "PromptPay/TrueMoney number is invalid for QR generation.", None
        provider_name = "PromptPay QR"
        verification_mode = "manual_slip"
        requires_manual_proof = True
        provider_note = "Pay via PromptPay QR and verify slip with SlipOK."
    elif provider_type == "truemoney":
        ok_qr, qr_message, qr_payload = await _truemoney_generate_qr(
            settings=settings,
            session_key=session_key,
            mode=mode_value,
            amount=amount_value,
            note=note,
        )
        if not ok_qr:
            return False, qr_message or "Unable to create TrueMoney QR session.", None
        qr_image_url = str(qr_payload.get("qr_image_url") or "").strip()
        provider_name = "TrueMoney QR"
        verification_mode = "webhook_auto"
        requires_manual_proof = False
        provider_note = "Pay via TrueMoney QR (auto callback/inquiry when available)."
        truemoney_reference = str(qr_payload.get("reference") or session_key).strip()[:120]
        truemoney_transaction_id = str(qr_payload.get("transaction_id") or "").strip()[:120]
        truemoney_payment_url = str(qr_payload.get("payment_url") or "").strip()[:500]
        if not qr_image_url and truemoney_payment_url:
            qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={quote(truemoney_payment_url, safe='')}"
        meta = {
            "truemoney_reference": truemoney_reference,
            "truemoney_transaction_id": truemoney_transaction_id,
            "truemoney_payment_url": truemoney_payment_url,
            "truemoney_callback_url": str(settings.get("truemoney_callback_url") or "").strip(),
            "truemoney_raw_response": qr_payload.get("raw") if isinstance(qr_payload.get("raw"), dict) else {},
        }

    verify_note_text = "Awaiting slip verification via SlipOK."
    if provider_type == "truemoney":
        if _is_truthy(settings.get("truemoney_auto_verify"), True) and str(settings.get("truemoney_inquiry_url") or "").strip():
            verify_note_text = "TrueMoney QR created. Waiting for callback/inquiry confirmation."
        else:
            verify_note_text = "TrueMoney QR created. Waiting for callback or SlipOK verification."
    if provider_fallback_note:
        verify_note_text = f"{verify_note_text} ({provider_fallback_note})"[:300]

    row = await storage.bot_payment_sessions.insert(
        session_key=session_key,
        mode=mode_value,
        provider_type=provider_type,
        provider_name=provider_name,
        verification_mode=verification_mode,
        requires_manual_proof=requires_manual_proof,
        status="pending",
        user_id=int(user_id),
        guild_id=int(guild_id) if guild_id else None,
        plan_tier=_normalize_plan(plan_tier) if plan_tier else "",
        amount=amount_value,
        currency="THB",
        promptpay_number=effective_promptpay_number,
        truemoney_phone=truemoney_phone,
        bank_name="",
        bank_account_name="",
        bank_account_number="",
        qr_image_url=qr_image_url,
        verify_status="pending",
        verify_note=verify_note_text,
        note=(f"{provider_note}: {str(note or '').strip()}" if str(note or "").strip() else provider_note)[:300],
        meta=meta,
        expires_at=expires_at,
        created_at=now_utc,
        updated_at=now_utc,
    )
    if provider_type == "promptpay":
        return True, "PromptPay QR session created successfully.", row
    if provider_type == "truemoney":
        return True, "TrueMoney QR session created successfully.", row
    return True, "Payment session created successfully.", row


async def _verify_truemoney_gift_link(link: str, *, expected_amount: float | None = None) -> tuple[str, str]:
    normalized_link = str(link or "").strip()
    try:
        expected_amount_value = round(float(expected_amount or 0.0), 2)
    except Exception:
        expected_amount_value = 0.0
    if expected_amount_value < 0:
        expected_amount_value = 0.0
    if not normalized_link:
        return "pending", "ยังไม่ได้ส่งลิงก์ TrueMoney gift"
    if not TRUEMONEY_GIFT_RE.match(normalized_link):
        return "rejected", "รูปแบบลิงก์ TrueMoney gift ไม่ถูกต้อง"
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://gift.truemoney.com/",
        }
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.get(normalized_link, headers=headers)
        status_code = int(response.status_code)
        if 200 <= status_code < 400:
            detected_amount = _extract_truemoney_gift_amount(response.text if hasattr(response, "text") else "")
            if expected_amount_value > 0 and detected_amount is not None:
                if abs(detected_amount - expected_amount_value) > 0.01:
                    return (
                        "rejected",
                        (
                            "ยอดเงินในลิงก์ TrueMoney gift ไม่ตรงกับยอดที่ต้องชำระ "
                            f"(คาดหวัง {expected_amount_value:.2f} THB, พบ {detected_amount:.2f} THB)"
                        ),
                    )
                return "approved", f"ตรวจสอบลิงก์ TrueMoney gift สำเร็จ (ยอดตรงกัน {detected_amount:.2f} THB)"
            if expected_amount_value > 0:
                return (
                    "approved",
                    (
                        "ตรวจสอบลิงก์ TrueMoney gift สำเร็จ "
                        f"(คาดหวัง {expected_amount_value:.2f} THB, ยังอ่านยอดจากลิงก์ไม่ได้)"
                    ),
                )
            return "approved", "ตรวจสอบลิงก์ TrueMoney gift สำเร็จ"
        if status_code in {404, 410}:
            return "rejected", "ลิงก์ TrueMoney gift หมดอายุหรือใช้งานไม่ได้"
        return "pending", f"ตรวจสอบลิงก์ TrueMoney ไม่สำเร็จ (status {status_code})"
    except Exception:
        return "pending", "ยังไม่สามารถตรวจสอบลิงก์ TrueMoney gift ได้ในขณะนี้"



def _extract_slipok_endpoint(api_url: Any) -> str:
    value = str(api_url or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.isdigit():
        return f"https://api.slipok.com/api/line/apikey/{value}"
    return ""


def _normalize_slip_verify_engine(value: Any, fallback: str = "slipok") -> str:
    raw = str(value or "").strip().lower()
    if raw in {"skylinebot", "skyline", "skylinebot_slip", "skyline_slip", "self", "internal", "ocr"}:
        raw = "skylinebotslip"
    if raw in {"slipok", "shipok", "slip_ok"}:
        raw = "slipok"
    if raw in {"skylinebotslip", "slipok"}:
        return raw
    fb = str(fallback or "slipok").strip().lower()
    if fb in {"skylinebot", "skyline", "skylinebot_slip", "skyline_slip", "self", "internal", "ocr"}:
        fb = "skylinebotslip"
    if fb in {"slipok", "shipok", "slip_ok"}:
        fb = "slipok"
    return fb if fb in {"skylinebotslip", "slipok"} else "slipok"


def _slip_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


def _slip_clean_text(value: Any, *, max_len: int = 260) -> str:
    text = _slip_text(value).strip()
    if not text:
        return ""
    if len(text) > max_len:
        return text[:max_len]
    return text


def _slip_digits(value: Any, *, max_len: int = 80) -> str:
    digits = "".join(ch for ch in _slip_text(value) if ch.isdigit())
    return digits[:max_len]


def _slip_norm_compare(value: Any) -> str:
    text = _slip_text(value).strip().lower()
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    # Keep Thai, English, and digits for flexible matching.
    text = re.sub(r"[^0-9a-z\u0E00-\u0E7F]", "", text)
    return text


def _slip_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return round(float(value), 2)
        except Exception:
            return None
    text = _slip_text(value).replace(",", " ").strip()
    if not text:
        return None
    match = re.search(r"(-?\d+(?:\.\d{1,2})?)", text)
    if not match:
        return None
    try:
        return round(float(match.group(1)), 2)
    except Exception:
        return None


def _slip_parse_datetime(value: Any) -> datetime.datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
    if isinstance(value, (int, float)):
        try:
            raw = float(value)
            if raw > 10_000_000_000:
                raw /= 1000.0
            return datetime.datetime.fromtimestamp(raw, tz=datetime.timezone.utc)
        except Exception:
            return None
    text = _slip_text(value).strip()
    if not text:
        return None

    # Try ISO first.
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
    except Exception:
        pass

    candidate = text.replace(".", "/").replace("-", "/")
    formats = (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
    )
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(candidate, fmt)
            return parsed.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
        except Exception:
            continue
    return None


def _slip_collect_scalar_paths(payload: Any, *, _prefix: str = "", _depth: int = 0) -> list[tuple[str, Any]]:
    if _depth > 6:
        return []
    out: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key or "").strip()
            if not key_text:
                continue
            path = f"{_prefix}.{key_text}" if _prefix else key_text
            out.extend(_slip_collect_scalar_paths(value, _prefix=path, _depth=_depth + 1))
        return out
    if isinstance(payload, list):
        for index, value in enumerate(payload[:10]):
            path = f"{_prefix}[{index}]" if _prefix else f"[{index}]"
            out.extend(_slip_collect_scalar_paths(value, _prefix=path, _depth=_depth + 1))
        return out
    return [(_prefix, payload)]


def _slip_first_path_value(payload: dict[str, Any], paths: list[str]) -> Any:
    for path in paths:
        value = _payload_path_get(payload, path)
        if value not in (None, ""):
            return value
    return None


def _slip_guess_by_path(
    scalars: list[tuple[str, Any]],
    *,
    include_any: tuple[str, ...],
    include_all: tuple[str, ...] = (),
    exclude_any: tuple[str, ...] = (),
) -> Any:
    best_score = -1
    best_value: Any = None
    for path, value in scalars:
        if value in (None, ""):
            continue
        path_text = str(path or "").lower()
        if exclude_any and any(token in path_text for token in exclude_any):
            continue
        if include_all and not all(token in path_text for token in include_all):
            continue
        if include_any and not any(token in path_text for token in include_any):
            continue
        score = sum(2 for token in include_all if token in path_text) + sum(1 for token in include_any if token in path_text)
        if score > best_score:
            best_score = score
            best_value = value
    return best_value


def _slip_extract_fields(payload: dict[str, Any], *, slip_qr_payload: str = "") -> dict[str, Any]:
    data_payload = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    scalars = _slip_collect_scalar_paths(payload)

    known_paths: dict[str, list[str]] = {
        "sender_name": [
            "data.sender.name",
            "data.senderName",
            "data.sender.fullname",
            "data.from.name",
            "sender.name",
            "senderName",
        ],
        "sender_bank": [
            "data.sender.bank",
            "data.sender.bankName",
            "data.from.bank",
            "sender.bank",
        ],
        "sender_account": [
            "data.sender.account",
            "data.sender.accountNumber",
            "data.from.account",
            "sender.account",
            "sender.accountNumber",
        ],
        "receiver_name": [
            "data.receiver.name",
            "data.receiverName",
            "data.to.name",
            "receiver.name",
            "receiverName",
        ],
        "receiver_bank": [
            "data.receiver.bank",
            "data.receiver.bankName",
            "data.to.bank",
            "receiver.bank",
        ],
        "receiver_account": [
            "data.receiver.account",
            "data.receiver.accountNumber",
            "data.to.account",
            "receiver.account",
            "receiver.accountNumber",
        ],
        "reference": [
            "data.reference",
            "data.ref",
            "data.transRef",
            "data.transactionRef",
            "data.transactionId",
            "data.txnId",
            "reference",
            "ref",
            "transRef",
            "transactionId",
        ],
        "qr_reference": [
            "data.qrReference",
            "data.qrcodeRef",
            "data.qr.ref",
            "data.qr.reference",
            "qrcode",
            "payload",
        ],
        "amount": [
            "data.amount",
            "data.amountValue",
            "data.transaction.amount",
            "data.totalAmount",
            "amount",
        ],
        "datetime": [
            "data.datetime",
            "data.dateTime",
            "data.transDate",
            "data.transactionDate",
            "data.createdAt",
            "data.date",
            "data.time",
            "datetime",
            "createdAt",
        ],
    }

    extracted: dict[str, Any] = {}
    for key, paths in known_paths.items():
        found = _slip_first_path_value(data_payload, paths)
        if found in (None, ""):
            found = _slip_first_path_value(payload, paths)
        extracted[key] = found

    if not extracted.get("sender_name"):
        extracted["sender_name"] = _slip_guess_by_path(
            scalars,
            include_any=("sender", "from"),
            include_all=("name",),
            exclude_any=("receiver", "to"),
        )
    if not extracted.get("sender_bank"):
        extracted["sender_bank"] = _slip_guess_by_path(
            scalars,
            include_any=("sender", "from"),
            include_all=("bank",),
            exclude_any=("receiver", "to"),
        )
    if not extracted.get("sender_account"):
        extracted["sender_account"] = _slip_guess_by_path(
            scalars,
            include_any=("sender", "from"),
            include_all=("account",),
            exclude_any=("receiver", "to", "name"),
        )
    if not extracted.get("receiver_name"):
        extracted["receiver_name"] = _slip_guess_by_path(
            scalars,
            include_any=("receiver", "to", "beneficiary"),
            include_all=("name",),
            exclude_any=("sender", "from"),
        )
    if not extracted.get("receiver_bank"):
        extracted["receiver_bank"] = _slip_guess_by_path(
            scalars,
            include_any=("receiver", "to", "beneficiary"),
            include_all=("bank",),
            exclude_any=("sender", "from"),
        )
    if not extracted.get("receiver_account"):
        extracted["receiver_account"] = _slip_guess_by_path(
            scalars,
            include_any=("receiver", "to", "beneficiary"),
            include_all=("account",),
            exclude_any=("sender", "from", "name"),
        )
    if not extracted.get("reference"):
        extracted["reference"] = _slip_guess_by_path(
            scalars,
            include_any=("ref", "reference", "transactionid", "txid", "trx"),
            exclude_any=("account", "phone", "mobile"),
        )
    if not extracted.get("qr_reference") and slip_qr_payload:
        extracted["qr_reference"] = str(slip_qr_payload or "").strip()[:500]
    if extracted.get("amount") is None:
        extracted["amount"] = _slip_guess_by_path(
            scalars,
            include_any=("amount", "total"),
        )
    if not extracted.get("datetime"):
        extracted["datetime"] = _slip_guess_by_path(
            scalars,
            include_any=("datetime", "date", "time", "created"),
        )

    extracted["sender_name"] = _slip_clean_text(extracted.get("sender_name"))
    extracted["sender_bank"] = _slip_clean_text(extracted.get("sender_bank"))
    extracted["sender_account"] = _slip_digits(extracted.get("sender_account"))
    extracted["receiver_name"] = _slip_clean_text(extracted.get("receiver_name"))
    extracted["receiver_bank"] = _slip_clean_text(extracted.get("receiver_bank"))
    extracted["receiver_account"] = _slip_digits(extracted.get("receiver_account"))
    extracted["reference"] = _slip_clean_text(extracted.get("reference"), max_len=120)
    extracted["qr_reference"] = _slip_clean_text(extracted.get("qr_reference"), max_len=500)
    extracted["amount"] = _slip_to_float(extracted.get("amount"))
    extracted["datetime"] = _slip_parse_datetime(extracted.get("datetime"))
    return extracted


def _slip_compare_text(expected: str, actual: str) -> bool:
    left = _slip_norm_compare(expected)
    right = _slip_norm_compare(actual)
    if not left or not right:
        return False
    return left in right or right in left


def _slip_compare_text_any(expected_candidates: list[str], actual: str) -> bool:
    actual_text = str(actual or "").strip()
    if not actual_text:
        return False
    for candidate in list(expected_candidates or []):
        if _slip_compare_text(str(candidate or ""), actual_text):
            return True
    return False


def _slip_compare_account(expected: str, actual: str) -> bool:
    left = _slip_digits(expected)
    right = _slip_digits(actual)
    if not left or not right:
        return False
    if left == right:
        return True
    # Masked account numbers: compare ending digits.
    if len(left) >= 4 and len(right) >= 4 and left[-4:] == right[-4:]:
        return True
    return left in right or right in left


def _slip_parse_id_list(raw_value: Any, *, max_items: int = 20) -> list[str]:
    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(item or "").strip() for item in raw_value]
    else:
        candidates = re.split(r"[\s,;]+", str(raw_value or ""))
    out: list[str] = []
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text.isdigit():
            continue
        if text in out:
            continue
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _slip_check_policy(settings: dict[str, Any] | None) -> dict[str, Any]:
    src = settings if isinstance(settings, dict) else {}

    def _text(*keys: str, max_len: int = 200) -> str:
        for key in keys:
            value = str(src.get(key) or "").strip()
            if value:
                return value[:max_len]
        return ""

    def _int(*keys: str, default: int, minimum: int, maximum: int) -> int:
        for key in keys:
            raw_value = src.get(key)
            if raw_value in (None, ""):
                continue
            try:
                parsed = int(float(raw_value))
            except Exception:
                continue
            return max(minimum, min(maximum, parsed))
        return default

    def _float(*keys: str, default: float, minimum: float, maximum: float) -> float:
        for key in keys:
            raw_value = src.get(key)
            if raw_value in (None, ""):
                continue
            try:
                parsed = float(raw_value)
            except Exception:
                continue
            return round(max(minimum, min(maximum, parsed)), 2)
        return round(max(minimum, min(maximum, float(default))), 2)

    def _name_candidates(
        *,
        full_name_keys: tuple[str, ...],
        first_last_sets: tuple[tuple[str, str], ...],
    ) -> list[str]:
        candidates: list[str] = []
        for key in full_name_keys:
            value = _text(key, max_len=220)
            cleaned = _slip_clean_text(value, max_len=220)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
        for first_key, last_key in first_last_sets:
            first_name = _slip_clean_text(_text(first_key, max_len=120), max_len=120)
            last_name = _slip_clean_text(_text(last_key, max_len=120), max_len=120)
            if first_name and first_name not in candidates:
                candidates.append(first_name)
            if first_name and last_name:
                combined = f"{first_name} {last_name}".strip()
                if combined and combined not in candidates:
                    candidates.append(combined)
        return candidates

    route_raw = _text(
        "slipcheck_low_confidence_route",
        "low_confidence_route",
        max_len=40,
    ).lower()
    if route_raw in {"embed", "embed_channel", "channel", "room", "guild", "discord"}:
        low_confidence_route = "channel"
    elif route_raw in {"dm", "direct", "direct_message", "directmessage", "user_dm"}:
        low_confidence_route = "dm"
    else:
        low_confidence_route = "both"

    return {
        "verify_engine": _normalize_slip_verify_engine(
            src.get("slipcheck_verify_engine") or src.get("verify_engine") or "slipok",
            "slipok",
        ),
        "expected_receiver_name": _text("slipcheck_expected_receiver_name", "expected_receiver_name", "bank_account_name"),
        "expected_receiver_name_candidates": _name_candidates(
            full_name_keys=("slipcheck_expected_receiver_name", "expected_receiver_name", "bank_account_name"),
            first_last_sets=(
                ("slipcheck_expected_receiver_first_name_th", "slipcheck_expected_receiver_last_name_th"),
                ("slipcheck_expected_receiver_first_name_en", "slipcheck_expected_receiver_last_name_en"),
            ),
        ),
        "expected_receiver_bank": _text("slipcheck_expected_receiver_bank", "expected_receiver_bank", "bank_name"),
        "expected_receiver_account": _text("slipcheck_expected_receiver_account", "expected_receiver_account", "bank_account_number"),
        "expected_sender_name": _text("slipcheck_expected_sender_name", "expected_sender_name"),
        "expected_sender_name_candidates": _name_candidates(
            full_name_keys=("slipcheck_expected_sender_name", "expected_sender_name"),
            first_last_sets=(
                ("slipcheck_expected_sender_first_name_th", "slipcheck_expected_sender_last_name_th"),
                ("slipcheck_expected_sender_first_name_en", "slipcheck_expected_sender_last_name_en"),
            ),
        ),
        "expected_sender_bank": _text("slipcheck_expected_sender_bank", "expected_sender_bank"),
        "expected_sender_account": _text("slipcheck_expected_sender_account", "expected_sender_account"),
        "expected_reference": _text("slipcheck_expected_reference", "expected_reference", max_len=120),
        "expected_qr_reference": _text("slipcheck_expected_qr_reference", "expected_qr_reference", max_len=240),
        "max_age_minutes": _int("slipcheck_max_age_minutes", "max_age_minutes", default=1440, minimum=0, maximum=60 * 24 * 30),
        "auto_approve_confidence": _float(
            "slipcheck_auto_approve_confidence",
            "auto_approve_confidence",
            default=85.0,
            minimum=50.0,
            maximum=100.0,
        ),
        "manual_review_confidence": _float(
            "slipcheck_manual_review_confidence",
            "manual_review_confidence",
            default=55.0,
            minimum=0.0,
            maximum=100.0,
        ),
        "duplicate_window_hours": _int("slipcheck_duplicate_window_hours", "duplicate_window_hours", default=72, minimum=1, maximum=24 * 90),
        "review_channel_id": _text("slipcheck_review_channel_id", "review_channel_id", "notification_channel_id", max_len=30),
        "review_dm_user_ids": _slip_parse_id_list(
            src.get("slipcheck_review_dm_user_ids")
            or src.get("review_dm_user_ids")
            or src.get("notification_dm_user_ids")
        ),
        "low_confidence_route": low_confidence_route,
    }


async def _find_duplicate_payment_slip(
    *,
    session_row: dict[str, Any] | None,
    transfer_reference: str,
    slip_fingerprint: str,
    duplicate_window_hours: int,
) -> dict[str, Any]:
    reference_text = str(transfer_reference or "").strip()[:180]
    fingerprint_text = str(slip_fingerprint or "").strip()[:180]
    if not reference_text and not fingerprint_text:
        return {"is_duplicate": False, "reason": "", "matched_session_key": ""}

    query_or: list[dict[str, Any]] = []
    if reference_text:
        query_or.append({"transfer_reference": reference_text})
    if fingerprint_text:
        query_or.append({"meta.slip_fingerprint": fingerprint_text})
    if not query_or:
        return {"is_duplicate": False, "reason": "", "matched_session_key": ""}

    current_id = int((session_row or {}).get("id") or 0)
    now_utc = _utc_now()
    query: dict[str, Any] = {
        "$or": query_or,
        "created_at": {"$gte": now_utc - datetime.timedelta(hours=max(1, int(duplicate_window_hours or 72)))},
    }
    if current_id > 0:
        query["id"] = {"$ne": current_id}

    try:
        collection = await get_collection(storage.bot_payment_sessions.COLLECTION_NAME)
        duplicate_row = await collection.find_one(
            query,
            {"_id": 0, "id": 1, "session_key": 1, "status": 1, "verify_status": 1, "transfer_reference": 1},
        )
        if duplicate_row:
            reason = "Duplicate slip reference found in another payment session."
            if fingerprint_text and str((duplicate_row.get("transfer_reference") or "")).strip() != reference_text:
                reason = "Duplicate slip fingerprint found in another payment session."
            return {
                "is_duplicate": True,
                "reason": reason,
                "matched_session_key": str(duplicate_row.get("session_key") or ""),
                "matched_status": str(duplicate_row.get("status") or ""),
            }
    except Exception:
        return {"is_duplicate": False, "reason": "", "matched_session_key": ""}
    return {"is_duplicate": False, "reason": "", "matched_session_key": ""}


def _build_slip_fingerprint(fields: dict[str, Any], *, amount: float, transfer_reference: str = "") -> str:
    reference_text = str(transfer_reference or fields.get("reference") or "").strip().lower()
    sender_tail = _slip_digits(fields.get("sender_account"))[-6:]
    receiver_tail = _slip_digits(fields.get("receiver_account"))[-6:]
    amount_text = f"{round(float(amount or 0.0), 2):.2f}"
    dt = fields.get("datetime")
    dt_text = ""
    if isinstance(dt, datetime.datetime):
        dt_utc = dt.astimezone(datetime.timezone.utc) if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
        dt_text = dt_utc.strftime("%Y%m%d%H%M")
    basis = "|".join([reference_text, amount_text, sender_tail, receiver_tail, dt_text]).strip("|")
    if not basis:
        return ""
    return hashlib.sha1(basis.encode("utf-8", errors="ignore")).hexdigest()


async def _verify_slipok_evidence_detailed(
    *,
    settings: dict[str, Any],
    amount: float,
    slip_url: str = "",
    slip_qr_payload: str = "",
    transfer_reference: str = "",
    session_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    endpoint = _extract_slipok_endpoint(settings.get("slipok_api_url") or "")
    api_key = str(settings.get("slipok_key") or "").strip()
    url_text = str(slip_url or "").strip()
    payload_text = str(slip_qr_payload or "").strip()
    policy = _slip_check_policy(settings)
    verify_engine = _normalize_slip_verify_engine(
        policy.get("verify_engine") or settings.get("slipcheck_verify_engine") or "slipok",
        "slipok",
    )

    base_result: dict[str, Any] = {
        "status": "pending",
        "note": "",
        "confidence": 0.0,
        "matched_checks": 0,
        "total_checks": 0,
        "checks": [],
        "fields": {},
        "suspicious_flags": [],
        "duplicate": {"is_duplicate": False, "reason": "", "matched_session_key": ""},
        "provider": {"ok": False, "message": "", "http_status": 0},
        "policy": policy,
        "fingerprint": "",
        "engine": verify_engine,
    }

    if not url_text and not payload_text:
        base_result["status"] = "pending"
        base_result["note"] = "Please submit slip URL or slip QR payload for verification."
        return base_result

    expected_amount = round(float(amount or 0.0), 2)
    request_payload: dict[str, Any] = {"log": "true"}
    if expected_amount > 0:
        request_payload["amount"] = f"{expected_amount:.2f}"
    if url_text:
        request_payload["url"] = url_text
    if payload_text:
        request_payload["payload"] = payload_text
        request_payload["qrcode"] = payload_text

    payload: dict[str, Any] = {}
    http_status = 0
    provider_ok = False
    provider_message = ""
    provider_source = "slipok"
    if endpoint and api_key:
        try:
            async with httpx.AsyncClient(timeout=22.0) as client:
                response = await client.post(
                    endpoint,
                    headers={"x-authorization": api_key},
                    data=request_payload,
                )
            http_status = int(response.status_code)
            payload = response.json() if response.content else {}
            if not isinstance(payload, dict):
                payload = {}
            data_payload = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            provider_ok = bool(payload.get("success")) and bool(data_payload.get("success"))
            provider_message = str(data_payload.get("message") or payload.get("message") or "").strip()
        except Exception:
            if verify_engine == "slipok":
                base_result["status"] = "pending"
                base_result["note"] = "SlipOK verification service is unavailable. Please try again later."
                return base_result
            provider_source = "skylinebotslip"
            provider_message = "SlipOK OCR is unavailable; SkylineBotSlip fallback mode is used."
    elif verify_engine == "slipok":
        base_result["status"] = "pending"
        base_result["note"] = "SlipOK is not configured yet (missing API URL or key)."
        return base_result
    else:
        provider_source = "skylinebotslip"
        provider_message = "SkylineBotSlip local OCR mode."

    if not payload:
        parsed_payload: dict[str, Any] = {}
        if payload_text:
            try:
                decoded_payload = json.loads(payload_text)
                if isinstance(decoded_payload, dict):
                    parsed_payload = decoded_payload
                elif isinstance(decoded_payload, list):
                    parsed_payload = {"data": {"items": decoded_payload}}
            except Exception:
                parsed_payload = {}
        payload = parsed_payload if parsed_payload else {}
        if not payload:
            payload = {"data": {"payload": payload_text, "reference": transfer_reference}}
        if url_text and isinstance(payload.get("data"), dict):
            payload["data"]["slip_url"] = url_text
        if expected_amount > 0 and isinstance(payload.get("data"), dict) and payload.get("data", {}).get("amount") in (None, ""):
            payload["data"]["amount"] = f"{expected_amount:.2f}"

    base_result["provider"] = {
        "ok": (provider_ok if verify_engine == "slipok" else True),
        "message": provider_message,
        "http_status": http_status,
        "source": provider_source,
    }

    fields = _slip_extract_fields(payload, slip_qr_payload=payload_text)
    base_result["fields"] = {
        "sender_name": str(fields.get("sender_name") or ""),
        "sender_bank": str(fields.get("sender_bank") or ""),
        "sender_account": str(fields.get("sender_account") or ""),
        "receiver_name": str(fields.get("receiver_name") or ""),
        "receiver_bank": str(fields.get("receiver_bank") or ""),
        "receiver_account": str(fields.get("receiver_account") or ""),
        "reference": str(fields.get("reference") or ""),
        "qr_reference": str(fields.get("qr_reference") or ""),
        "amount": fields.get("amount"),
        "datetime_iso": (
            fields.get("datetime").astimezone(datetime.timezone.utc).isoformat()
            if isinstance(fields.get("datetime"), datetime.datetime)
            else ""
        ),
    }

    checks: list[dict[str, Any]] = []
    matched_checks = 0
    total_checks = 0
    critical_mismatch = 0

    def _append_check(
        *,
        key: str,
        label: str,
        expected_value: Any,
        actual_value: Any,
        matched: bool | None,
        critical: bool = True,
        affects_decision: bool = True,
    ) -> None:
        nonlocal matched_checks, total_checks, critical_mismatch
        if expected_value in (None, "") and matched is None:
            return
        status = "missing"
        if matched is True:
            status = "matched"
        elif matched is False:
            status = "mismatched"
        checks.append(
            {
                "key": key,
                "label": label,
                "status": status,
                "expected": _slip_clean_text(expected_value),
                "actual": _slip_clean_text(actual_value),
                "critical": bool(critical),
                "affects_decision": bool(affects_decision),
            }
        )
        if affects_decision:
            total_checks += 1
            if matched is True:
                matched_checks += 1
            elif matched is False and critical:
                critical_mismatch += 1

    _append_check(
        key="amount",
        label="Amount",
        expected_value=f"{expected_amount:.2f}" if expected_amount > 0 else "",
        actual_value=f"{float(fields.get('amount')):.2f}" if fields.get("amount") is not None else "",
        matched=(
            True
            if expected_amount > 0 and fields.get("amount") is not None and abs(float(fields.get("amount")) - expected_amount) <= 0.01
            else (False if expected_amount > 0 and fields.get("amount") is not None else None)
        ),
        critical=True,
    )
    receiver_name_candidates = list(policy.get("expected_receiver_name_candidates") or [])
    _append_check(
        key="receiver_name",
        label="Receiver Name",
        expected_value=receiver_name_candidates[0] if receiver_name_candidates else (policy.get("expected_receiver_name") or ""),
        actual_value=fields.get("receiver_name") or "",
        matched=(
            _slip_compare_text_any(receiver_name_candidates, fields.get("receiver_name") or "")
            if receiver_name_candidates
            else (
                _slip_compare_text(policy.get("expected_receiver_name") or "", fields.get("receiver_name") or "")
                if (policy.get("expected_receiver_name") or "")
                else None
            )
        ),
        critical=True,
    )
    _append_check(
        key="receiver_bank",
        label="Receiver Bank",
        expected_value=policy.get("expected_receiver_bank") or "",
        actual_value=fields.get("receiver_bank") or "",
        matched=(
            _slip_compare_text(policy.get("expected_receiver_bank") or "", fields.get("receiver_bank") or "")
            if (policy.get("expected_receiver_bank") or "")
            else None
        ),
        critical=True,
    )
    _append_check(
        key="receiver_account",
        label="Receiver Account",
        expected_value=policy.get("expected_receiver_account") or "",
        actual_value=fields.get("receiver_account") or "",
        matched=(
            _slip_compare_account(policy.get("expected_receiver_account") or "", fields.get("receiver_account") or "")
            if (policy.get("expected_receiver_account") or "")
            else None
        ),
        critical=True,
    )
    sender_name_candidates = list(policy.get("expected_sender_name_candidates") or [])
    _append_check(
        key="sender_name",
        label="Sender Name",
        expected_value=sender_name_candidates[0] if sender_name_candidates else (policy.get("expected_sender_name") or ""),
        actual_value=fields.get("sender_name") or "",
        matched=(
            _slip_compare_text_any(sender_name_candidates, fields.get("sender_name") or "")
            if sender_name_candidates
            else (
                _slip_compare_text(policy.get("expected_sender_name") or "", fields.get("sender_name") or "")
                if (policy.get("expected_sender_name") or "")
                else None
            )
        ),
        critical=False,
        affects_decision=False,
    )
    _append_check(
        key="sender_bank",
        label="Sender Bank",
        expected_value=policy.get("expected_sender_bank") or "",
        actual_value=fields.get("sender_bank") or "",
        matched=(
            _slip_compare_text(policy.get("expected_sender_bank") or "", fields.get("sender_bank") or "")
            if (policy.get("expected_sender_bank") or "")
            else None
        ),
        critical=False,
        affects_decision=False,
    )
    _append_check(
        key="sender_account",
        label="Sender Account",
        expected_value=policy.get("expected_sender_account") or "",
        actual_value=fields.get("sender_account") or "",
        matched=(
            _slip_compare_account(policy.get("expected_sender_account") or "", fields.get("sender_account") or "")
            if (policy.get("expected_sender_account") or "")
            else None
        ),
        critical=False,
        affects_decision=False,
    )

    reference_expected = str(policy.get("expected_reference") or "").strip()
    reference_actual = str(fields.get("reference") or transfer_reference or "").strip()
    _append_check(
        key="reference",
        label="Reference",
        expected_value=reference_expected,
        actual_value=reference_actual,
        matched=(
            _slip_compare_text(reference_expected, reference_actual)
            if reference_expected
            else None
        ),
        critical=False,
    )
    qr_ref_expected = str(policy.get("expected_qr_reference") or "").strip()
    qr_ref_actual = str(fields.get("qr_reference") or payload_text or "").strip()
    _append_check(
        key="qr_reference",
        label="QR Reference",
        expected_value=qr_ref_expected,
        actual_value=qr_ref_actual,
        matched=(
            _slip_compare_text(qr_ref_expected, qr_ref_actual)
            if qr_ref_expected
            else None
        ),
        critical=False,
    )

    slip_dt = fields.get("datetime")
    max_age_minutes = int(policy.get("max_age_minutes") or 0)
    if max_age_minutes > 0:
        now_utc = _utc_now()
        if isinstance(slip_dt, datetime.datetime):
            slip_dt_utc = slip_dt.astimezone(datetime.timezone.utc) if slip_dt.tzinfo else slip_dt.replace(tzinfo=datetime.timezone.utc)
            age_minutes = (now_utc - slip_dt_utc).total_seconds() / 60.0
            if age_minutes < -5:
                base_result["suspicious_flags"].append("Slip date/time is in the future.")
                _append_check(
                    key="datetime_window",
                    label="Date/Time Window",
                    expected_value=f"within {max_age_minutes} min",
                    actual_value=slip_dt_utc.isoformat(),
                    matched=False,
                    critical=True,
                )
            else:
                _append_check(
                    key="datetime_window",
                    label="Date/Time Window",
                    expected_value=f"within {max_age_minutes} min",
                    actual_value=slip_dt_utc.isoformat(),
                    matched=age_minutes <= max_age_minutes,
                    critical=False,
                )
        else:
            _append_check(
                key="datetime_window",
                label="Date/Time Window",
                expected_value=f"within {max_age_minutes} min",
                actual_value="",
                matched=None,
                critical=False,
            )

    slip_fingerprint = _build_slip_fingerprint(
        fields,
        amount=expected_amount,
        transfer_reference=(transfer_reference or fields.get("reference") or ""),
    )
    base_result["fingerprint"] = slip_fingerprint
    duplicate_info = await _find_duplicate_payment_slip(
        session_row=session_row,
        transfer_reference=(transfer_reference or fields.get("reference") or ""),
        slip_fingerprint=slip_fingerprint,
        duplicate_window_hours=int(policy.get("duplicate_window_hours") or 72),
    )
    base_result["duplicate"] = duplicate_info
    if duplicate_info.get("is_duplicate"):
        base_result["suspicious_flags"].append("Duplicate slip evidence detected.")

    if verify_engine == "slipok" and not provider_ok:
        message_low = provider_message.lower()
        if any(keyword in message_low for keyword in ("fake", "forg", "ปลอม", "tamper", "edited", "invalid")):
            base_result["suspicious_flags"].append("Provider reported suspicious or invalid slip.")

    if total_checks > 0:
        confidence = round((matched_checks / float(total_checks)) * 100.0, 2)
    else:
        if verify_engine == "slipok":
            confidence = 85.0 if provider_ok else 35.0
        else:
            confidence = 70.0
    confidence -= min(30.0, float(max(0, critical_mismatch)) * 15.0)
    if duplicate_info.get("is_duplicate"):
        confidence = min(confidence, 20.0)
    confidence = round(max(0.0, min(100.0, confidence)), 2)

    manual_review_conf = float(policy.get("manual_review_confidence") or 55.0)
    auto_approve_conf = float(policy.get("auto_approve_confidence") or 85.0)
    if manual_review_conf > auto_approve_conf:
        manual_review_conf, auto_approve_conf = auto_approve_conf, manual_review_conf

    status = "pending"
    if duplicate_info.get("is_duplicate"):
        status = "rejected"
    elif confidence < manual_review_conf:
        status = "rejected"
    elif confidence < auto_approve_conf:
        status = "pending"
    else:
        status = "approved" if (provider_ok or verify_engine == "skylinebotslip") else "pending"
    if critical_mismatch > 0 and status == "approved":
        status = "pending"

    if verify_engine == "skylinebotslip":
        summary = provider_message or "SkylineBotSlip analyzed this transfer slip."
    else:
        summary = provider_message or ("SlipOK verified the transfer slip successfully." if provider_ok else "SlipOK rejected this transfer slip.")
    summary = summary.strip()[:220]
    note = f"{summary} | Match {matched_checks}/{total_checks} | Confidence {confidence:.2f}%"
    if duplicate_info.get("is_duplicate"):
        note = f"{note} | Duplicate: {str(duplicate_info.get('matched_session_key') or '-').strip()}"

    base_result.update(
        {
            "status": status,
            "note": note[:500],
            "confidence": confidence,
            "matched_checks": matched_checks,
            "total_checks": total_checks,
            "checks": checks[:40],
        }
    )
    return base_result


async def _verify_slipok_evidence(
    *,
    settings: dict[str, Any],
    amount: float,
    slip_url: str = "",
    slip_qr_payload: str = "",
) -> tuple[str, str]:
    detailed = await _verify_slipok_evidence_detailed(
        settings=settings,
        amount=amount,
        slip_url=slip_url,
        slip_qr_payload=slip_qr_payload,
    )
    return str(detailed.get("status") or "pending"), str(detailed.get("note") or "Slip verification pending")


async def _verify_slip_evidence_detailed(
    *,
    settings: dict[str, Any],
    amount: float,
    slip_url: str = "",
    slip_qr_payload: str = "",
    transfer_reference: str = "",
    session_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await _verify_slipok_evidence_detailed(
        settings=settings,
        amount=amount,
        slip_url=slip_url,
        slip_qr_payload=slip_qr_payload,
        transfer_reference=transfer_reference,
        session_row=session_row,
    )


async def confirm_payment_session(
    *,
    session_key: str,
    transfer_reference: str = "",
    transfer_link: str = "",
    slip_qr_payload: str = "",
    force_paid: bool = False,
) -> tuple[bool, str, dict[str, Any] | None]:
    key = str(session_key or "").strip()
    if not key:
        return False, "ไม่พบ session key ของรายการชำระเงิน", None

    row = await storage.bot_payment_sessions.get(session_key=key)
    if not row:
        return False, "ไม่พบรายการชำระเงิน", None

    status = str(row.get("status") or "pending").strip().lower()
    if status == "paid":
        return True, "รายการนี้ชำระเงินแล้ว", row
    if status in {"expired", "cancelled"}:
        return False, "รายการนี้ถูกปิดไปแล้ว", row

    now_utc = _utc_now()
    if _session_expired(row, now=now_utc):
        updated = await storage.bot_payment_sessions.update(
            id=row["id"],
            status="expired",
            verify_status="rejected",
            verify_note="รายการชำระเงินหมดอายุ",
            closed_at=now_utc,
            updated_at=now_utc,
        )
        return False, "QR หมดอายุแล้ว กรุณาสร้างรายการใหม่", updated
    reference_text = str(transfer_reference or "").strip()[:200]
    link_text = str(transfer_link or "").strip()[:500]
    slip_qr_payload_text = str(slip_qr_payload or "").strip()[:1000]
    mode_value = str(row.get("mode") or "topup").strip().lower()
    provider_type = _normalize_provider_type(row.get("provider_type"), "promptpay")
    settings = await _payment_settings()
    existing_meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    meta_updates: dict[str, Any] = {}
    if slip_qr_payload_text:
        meta_updates["slip_qr_payload"] = slip_qr_payload_text

    verify_status = "pending"
    verify_note = "Waiting for payment verification"
    slip_analysis: dict[str, Any] | None = None
    if force_paid:
        verify_status = "approved"
        verify_note = "Payment was confirmed by callback"
    elif provider_type == "promptpay":
        if link_text and TRUEMONEY_GIFT_RE.match(link_text):
            verify_status, verify_note = await _verify_truemoney_gift_link(
                link_text,
                expected_amount=float(row.get("amount") or 0.0),
            )
        elif link_text or slip_qr_payload_text:
            slip_analysis = await _verify_slip_evidence_detailed(
                settings=settings,
                amount=float(row.get("amount") or 0.0),
                slip_url=link_text,
                slip_qr_payload=slip_qr_payload_text,
                transfer_reference=reference_text,
                session_row=row,
            )
            verify_status = str(slip_analysis.get("status") or "pending")
            verify_note = str(slip_analysis.get("note") or "Slip verification pending")
        else:
            verify_note = "Please submit slip URL or slip QR payload."
    elif provider_type == "truemoney":
        if link_text and TRUEMONEY_GIFT_RE.match(link_text):
            verify_status, verify_note = await _verify_truemoney_gift_link(
                link_text,
                expected_amount=float(row.get("amount") or 0.0),
            )
        elif _is_truthy(settings.get("truemoney_auto_verify"), True) and str(settings.get("truemoney_inquiry_url") or "").strip():
            paid_ok, tm_note, tm_meta = await _truemoney_inquire_payment(
                settings=settings,
                session_row=row,
            )
            verify_note = tm_note
            if isinstance(tm_meta, dict):
                meta_updates.update(tm_meta)
            if paid_ok:
                verify_status = "approved"
        elif link_text or slip_qr_payload_text:
            slip_analysis = await _verify_slip_evidence_detailed(
                settings=settings,
                amount=float(row.get("amount") or 0.0),
                slip_url=link_text,
                slip_qr_payload=slip_qr_payload_text,
                transfer_reference=reference_text,
                session_row=row,
            )
            verify_status = str(slip_analysis.get("status") or "pending")
            verify_note = str(slip_analysis.get("note") or "Slip verification pending")
        else:
            verify_note = "TrueMoney payment is waiting for callback/inquiry confirmation."
    else:
        verify_note = "Provider is disabled for this wallet flow."

    if isinstance(slip_analysis, dict):
        meta_updates["slip_analysis"] = {
            "status": str(slip_analysis.get("status") or "pending"),
            "confidence": float(slip_analysis.get("confidence") or 0.0),
            "matched_checks": int(slip_analysis.get("matched_checks") or 0),
            "total_checks": int(slip_analysis.get("total_checks") or 0),
            "checks": list(slip_analysis.get("checks") or [])[:30],
            "fields": dict(slip_analysis.get("fields") or {}),
            "suspicious_flags": list(slip_analysis.get("suspicious_flags") or [])[:10],
            "duplicate": dict(slip_analysis.get("duplicate") or {}),
            "provider": dict(slip_analysis.get("provider") or {}),
            "checked_at": _utc_now().isoformat(),
        }
        slip_fingerprint = str(slip_analysis.get("fingerprint") or "").strip()
        if slip_fingerprint:
            meta_updates["slip_fingerprint"] = slip_fingerprint

    merged_meta = dict(existing_meta)
    if meta_updates:
        merged_meta.update(meta_updates)

    updated = await storage.bot_payment_sessions.update(
        id=row["id"],
        transfer_reference=reference_text or str(row.get("transfer_reference") or ""),
        transfer_link=link_text or str(row.get("transfer_link") or ""),
        verify_status=verify_status,
        verify_note=verify_note,
        meta=merged_meta,
        last_verified_at=now_utc,
        updated_at=now_utc,
    )
    if not updated:
        return False, "อัปเดตรายการชำระเงินไม่สำเร็จ", row

    if verify_status != "approved":
        return False, verify_note, updated

    payment_collection = await get_collection(storage.bot_payment_sessions.COLLECTION_NAME)
    paid_row = await payment_collection.find_one_and_update(
        {"id": int(updated.get("id") or 0), "status": "pending"},
        {
            "$set": {
                "status": "paid",
                "paid_at": now_utc,
                "closed_at": now_utc,
                "updated_at": now_utc,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not paid_row:
        latest_row = await storage.bot_payment_sessions.get(session_key=key) or updated
        latest_status = str(latest_row.get("status") or "").strip().lower()
        if latest_status == "paid":
            return True, "รายการนี้ชำระเงินแล้ว", latest_row
        if latest_status in {"expired", "cancelled"}:
            return False, "รายการนี้ถูกปิดไปแล้ว", latest_row
        return False, "ปิดรายการชำระเงินไม่สำเร็จ", latest_row

    final_row = paid_row
    user_id = int(final_row.get("user_id") or 0)
    amount_value = float(final_row.get("amount") or 0.0)
    guild_id = int(final_row.get("guild_id") or 0) or None
    if mode_value == "topup" and user_id > 0 and amount_value > 0:
        credit_ok, credit_message, _ledger = await credit_wallet(
            user_id=user_id,
            amount=amount_value,
            kind="topup_credit",
            source_mode="topup",
            session_key=key,
            guild_id=guild_id,
            note="Wallet top-up via QR payment",
            meta={"transfer_reference": reference_text, "transfer_link": link_text},
        )
        if not credit_ok:
            return False, credit_message, final_row
    elif mode_value == "donate":
        await _append_billing_event(
            user_id=user_id if user_id > 0 else None,
            guild_id=guild_id,
            event_type="donate_paid",
            message=f"Donate paid {amount_value:.2f} THB",
            level="success",
            meta={"session_key": key},
        )

    return True, "ตรวจสอบการชำระเงินสำเร็จ", final_row


async def expire_stale_payment_sessions() -> int:
    pending_rows = await storage.bot_payment_sessions.gets(status="pending")
    now_utc = _utc_now()
    expired_count = 0
    for row in pending_rows or []:
        if not _session_expired(row, now=now_utc):
            continue
        await storage.bot_payment_sessions.update(
            id=row["id"],
            status="expired",
            verify_status="rejected",
            verify_note="เกินเวลาชำระเงิน 10 นาที",
            closed_at=now_utc,
            updated_at=now_utc,
        )
        expired_count += 1
    return expired_count


async def auto_verify_pending_truemoney_sessions() -> int:
    settings = await _payment_settings()
    pending_rows = await storage.bot_payment_sessions.gets(status="pending")
    now_utc = _utc_now()
    processed = 0
    for row in pending_rows or []:
        if _session_expired(row, now=now_utc):
            continue
        provider_type = _normalize_provider_type(row.get("provider_type"), "promptpay")
        if provider_type == "truemoney":
            if not _is_truthy(settings.get("truemoney_auto_verify"), True):
                continue
            if not str(settings.get("truemoney_inquiry_url") or "").strip():
                continue
        elif provider_type == "promptpay":
            link_text = str(row.get("transfer_link") or "").strip()
            if not link_text:
                continue
        else:
            continue
        last_verified_at = _as_utc_datetime(row.get("last_verified_at"))
        if last_verified_at and (now_utc - last_verified_at).total_seconds() < PAYMENT_SESSION_VERIFY_INTERVAL_SECONDS:
            continue
        ok, _, _ = await confirm_payment_session(session_key=str(row.get("session_key") or ""))
        if ok:
            processed += 1
    return processed


async def _collect_guild_notify_user_ids(guild_id: int, fallback_user_id: int | None = None) -> list[int]:
    user_ids: list[int] = []
    if fallback_user_id:
        try:
            user_ids.append(int(fallback_user_id))
        except Exception:
            pass
    guild_cache = cache.guilds.get(str(int(guild_id)), {})
    if isinstance(guild_cache, dict):
        owner_id = guild_cache.get("owner_id")
        if owner_id:
            try:
                user_ids.append(int(owner_id))
            except Exception:
                pass
        for extra_id in _safe_list(guild_cache.get("extra_owner_ids")):
            try:
                user_ids.append(int(extra_id))
            except Exception:
                continue
    deduped: list[int] = []
    seen: set[int] = set()
    for user_id in user_ids:
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        deduped.append(user_id)
    return deduped


async def _notify_billing_users(
    *,
    bot: Any,
    user_ids: list[int],
    message: str,
) -> None:
    if not bot or not user_ids:
        return
    for user_id in user_ids:
        try:
            user_obj = bot.get_user(int(user_id))
            if user_obj is None:
                user_obj = await bot.fetch_user(int(user_id))
            if user_obj:
                await user_obj.send(str(message or "")[:1900])
        except Exception:
            continue


async def sync_plan_subscription_with_guild_state(
    guild_id: int,
    *,
    user_id: int | None = None,
    clear_pending_plan: bool = False,
    status_override: str | None = None,
) -> dict[str, Any]:
    guild_id_int = int(guild_id)
    now_utc = _utc_now()
    row = await storage.bot_plan_subscriptions.get(guild_id=guild_id_int)

    guild_cache = cache.guilds.get(str(guild_id_int), {}) or {}
    if not isinstance(guild_cache, dict):
        guild_cache = {}
    storage_guild_cache = await storage.guilds.get(guild_id=guild_id_int) or {}
    if isinstance(storage_guild_cache, dict) and storage_guild_cache:
        guild_cache = {**guild_cache, **storage_guild_cache}

    current_plan = _normalize_plan(guild_cache.get("subscription"))
    current_period_end = _as_utc_datetime(guild_cache.get("subscription_end"))
    if current_plan in {"free", "permanent"}:
        current_period_end = None
    owner_id = int(guild_cache.get("owner_id") or 0) or None
    if not owner_id:
        for extra_owner_id in _safe_list(guild_cache.get("extra_owner_ids")):
            try:
                parsed_owner = int(extra_owner_id)
            except Exception:
                continue
            if parsed_owner > 0:
                owner_id = parsed_owner
                break

    resolved_user_id = int(user_id or 0) or owner_id
    desired_status = str(status_override or "").strip().lower()
    if desired_status not in {"active", "free", "grace", "awaiting_payment", "paused"}:
        desired_status = "free" if current_plan == "free" else "active"

    if row:
        updates: dict[str, Any] = {}
        existing_plan = _normalize_plan(row.get("current_plan"))
        # Preserve permanent tier in billing rows for legacy guild cache values.
        if existing_plan == "permanent" and current_plan == "diamond":
            current_plan = "permanent"
        existing_period_end = _as_utc_datetime(row.get("current_period_end"))
        existing_status = str(row.get("status") or "").strip().lower()

        if existing_plan != current_plan:
            updates["current_plan"] = current_plan

        if current_plan == "free":
            if existing_period_end is not None:
                updates["current_period_end"] = None
            if row.get("current_period_start"):
                updates["current_period_start"] = None
        elif current_plan == "permanent":
            if existing_period_end is not None:
                updates["current_period_end"] = None
            if not row.get("current_period_start"):
                updates["current_period_start"] = now_utc
        elif current_period_end and (
            not existing_period_end
            or abs((current_period_end - existing_period_end).total_seconds()) >= 1
        ):
            updates["current_period_end"] = current_period_end
            if not row.get("current_period_start"):
                updates["current_period_start"] = now_utc

        if clear_pending_plan and str(row.get("pending_plan") or "").strip():
            updates["pending_plan"] = ""

        if resolved_user_id and not int(row.get("user_id") or 0):
            updates["user_id"] = resolved_user_id

        if current_plan == "free":
            if existing_status != "free":
                updates["status"] = "free"
        elif existing_status in {"", "free"} or status_override:
            if existing_status != desired_status:
                updates["status"] = desired_status

        if updates:
            updates["updated_at"] = now_utc
            await storage.bot_plan_subscriptions.update(id=row["id"], **updates)
            row = await storage.bot_plan_subscriptions.get(guild_id=guild_id_int) or {**row, **updates}
        return row

    await storage.bot_plan_subscriptions.insert(
        guild_id=guild_id_int,
        user_id=resolved_user_id,
        current_plan=current_plan,
        pending_plan="",
        auto_renew=True,
        status=desired_status,
        current_period_start=now_utc if current_plan != "free" else None,
        current_period_end=(None if current_plan in {"free", "permanent"} else current_period_end),
        updated_at=now_utc,
    )
    return await storage.bot_plan_subscriptions.get(guild_id=guild_id_int) or {
        "guild_id": guild_id_int,
        "current_plan": current_plan,
        "status": desired_status,
    }


async def _ensure_plan_row_from_guild(guild_id: int, *, user_id: int | None = None) -> dict[str, Any]:
    return await sync_plan_subscription_with_guild_state(guild_id=int(guild_id), user_id=user_id)


async def _apply_guild_plan_period(
    *,
    bot: Any,
    guild_id: int,
    plan_tier: str,
    period_start: datetime.datetime,
    period_end: datetime.datetime | None,
) -> None:
    sub_code = PLAN_TO_SUBSCRIPTION_CODE.get(_normalize_plan(plan_tier), "free")
    await change_guild_subscription(
        bot=bot,
        guild_id=int(guild_id),
        subscription=sub_code,
        exact_end=period_end if period_end else None,
    )
    guild_cache = cache.guilds.get(str(int(guild_id)), {})
    if isinstance(guild_cache, dict) and guild_cache.get("id"):
        await storage.guilds.update(
            id=guild_cache["id"],
            guild_id=int(guild_id),
            subscription=sub_code,
            subscription_end=period_end,
        )


async def subscribe_guild_plan(
    *,
    bot: Any,
    guild_id: int,
    user_id: int,
    plan_tier: str,
    auto_renew: bool = True,
) -> tuple[bool, str, dict[str, Any] | None]:
    guild_id_int = int(guild_id)
    user_id_int = int(user_id)
    target_plan = _normalize_plan(plan_tier)
    if target_plan == "free":
        return False, "แพ็กเกจ Free ไม่ต้องสมัครแผน", None
    if target_plan not in {"silver", "golden", "diamond", "permanent"}:
        return False, "ไม่พบแพ็กเกจที่เลือก", None

    sub_row = await _ensure_plan_row_from_guild(guild_id_int, user_id=user_id_int)
    if not sub_row or not sub_row.get("id"):
        return False, "ไม่สามารถสร้างข้อมูลการสมัครแพ็กเกจได้", None
    now_utc = _utc_now()
    current_plan = _normalize_plan(sub_row.get("current_plan"))
    current_period_end = _as_utc_datetime(sub_row.get("current_period_end"))
    active_now = (
        current_plan == "permanent"
        or (current_plan != "free" and current_period_end and current_period_end > now_utc)
    )

    if active_now:
        if current_plan == target_plan:
            updated = await storage.bot_plan_subscriptions.update(
                id=sub_row["id"],
                user_id=user_id_int,
                auto_renew=(False if target_plan == "permanent" else bool(auto_renew)),
                status="active",
                updated_at=now_utc,
            )
            await _append_billing_event(
                user_id=user_id_int,
                guild_id=guild_id_int,
                event_type="plan_autorenew_updated",
                message=f"อัปเดตการต่ออายุอัตโนมัติแพ็กเกจ {target_plan}",
                level="info",
                meta={"auto_renew": (False if target_plan == "permanent" else bool(auto_renew))},
            )
            return True, "แผนปัจจุบันตรงกับที่เลือกแล้ว ปรับการต่ออายุอัตโนมัติสำเร็จ", updated

        updated = await storage.bot_plan_subscriptions.update(
            id=sub_row["id"],
            user_id=user_id_int,
            pending_plan=target_plan,
            auto_renew=(False if target_plan == "permanent" else bool(auto_renew)),
            status="active",
            updated_at=now_utc,
        )
        await _append_billing_event(
            user_id=user_id_int,
            guild_id=guild_id_int,
            event_type="plan_queued",
            message=f"คิวเปลี่ยนแพ็กเกจเป็น {target_plan} เมื่อแพ็กเกจปัจจุบันหมดอายุ",
            level="info",
        )
        return True, "ตั้งค่าเปลี่ยนแผนล่วงหน้าแล้ว ระบบจะเปลี่ยนเมื่อแผนปัจจุบันหมดอายุ", updated

    pricing_settings = await get_plan_pricing_settings()
    price_quote = build_plan_price_quote(target_plan, settings=pricing_settings, now=now_utc)
    price = float(price_quote.get("final_price") or 0.0)
    ok = True
    reason = ""
    if price > 0:
        ok, reason, _ledger = await debit_wallet(
            user_id=user_id_int,
            amount=price,
            kind="plan_debit",
            source_mode="plan",
            guild_id=guild_id_int,
            note=f"สมัครแพ็กเกจ {target_plan}",
            meta={
                "plan_tier": target_plan,
                "base_price": float(price_quote.get("base_price") or price),
                "final_price": price,
                "discount_percent": float(price_quote.get("discount_percent") or 0.0),
                "promo_active": bool(price_quote.get("promo_active")),
            },
        )
    if not ok:
        updated = await storage.bot_plan_subscriptions.update(
            id=sub_row["id"],
            user_id=user_id_int,
            pending_plan=target_plan,
            auto_renew=(False if target_plan == "permanent" else bool(auto_renew)),
            status="awaiting_payment",
            last_notice="insufficient_balance",
            updated_at=now_utc,
        )
        await _append_billing_event(
            user_id=user_id_int,
            guild_id=guild_id_int,
            event_type="plan_payment_required",
            message=f"ยอดเงินไม่พอสำหรับสมัครแพ็กเกจ {target_plan} ({price:.2f} THB) กรุณาเติมเงิน",
            level="warning",
        )
        return False, f"ยอดเงินไม่พอ กรุณาเติมเงินอย่างน้อย {price:.2f} THB ก่อนสมัครแพ็กเกจ", updated

    period_start = now_utc
    period_end = None if target_plan == "permanent" else (now_utc + datetime.timedelta(days=PLAN_DURATION_DAYS))
    await _apply_guild_plan_period(
        bot=bot,
        guild_id=guild_id_int,
        plan_tier=target_plan,
        period_start=period_start,
        period_end=period_end,
    )
    updated = await storage.bot_plan_subscriptions.update(
        id=sub_row["id"],
        user_id=user_id_int,
        current_plan=target_plan,
        pending_plan="",
        auto_renew=(False if target_plan == "permanent" else bool(auto_renew)),
        status="active",
        current_period_start=period_start,
        current_period_end=period_end,
        grace_notified_at=None,
        grace_until=None,
        premium_disabled_at=None,
        unpaid_since=None,
        purge_due_at=None,
        purge_done_at=None,
        last_charge_at=now_utc,
        last_charge_amount=price,
        last_notice="plan_activated",
        updated_at=now_utc,
    )
    await _append_billing_event(
        user_id=user_id_int,
        guild_id=guild_id_int,
        event_type="plan_activated",
        message=f"สมัครแพ็กเกจ {target_plan} สำเร็จ",
        level="success",
        meta={
            "period_end": (period_end.isoformat() if period_end else "lifetime"),
            "base_price": float(price_quote.get("base_price") or price),
            "final_price": price,
            "discount_percent": float(price_quote.get("discount_percent") or 0.0),
            "promo_active": bool(price_quote.get("promo_active")),
        },
    )
    return True, "สมัครแพ็กเกจสำเร็จแล้ว", updated


async def cancel_guild_plan(
    *,
    guild_id: int,
    user_id: int,
) -> tuple[bool, str, dict[str, Any] | None]:
    guild_id_int = int(guild_id)
    user_id_int = int(user_id)
    sub_row = await _ensure_plan_row_from_guild(guild_id_int, user_id=user_id_int)
    if not sub_row or not sub_row.get("id"):
        return False, "ไม่สามารถสร้างข้อมูลการสมัครแพ็กเกจได้", None
    now_utc = _utc_now()

    updated = await storage.bot_plan_subscriptions.update(
        id=sub_row["id"],
        user_id=user_id_int,
        auto_renew=False,
        pending_plan="free",
        status="active" if _normalize_plan(sub_row.get("current_plan")) != "free" else "free",
        updated_at=now_utc,
        last_notice="plan_cancel_requested",
    )
    await _append_billing_event(
        user_id=user_id_int,
        guild_id=guild_id_int,
        event_type="plan_cancel_requested",
        message="ยกเลิกการต่ออายุอัตโนมัติแล้ว (สิทธิ์ปัจจุบันยังใช้ได้จนหมดอายุ)",
        level="info",
    )
    return True, "ยกเลิกการต่ออายุอัตโนมัติแล้ว สิทธิ์ปัจจุบันยังใช้ได้จนหมดอายุ", updated


def _is_user_app_subscription_active(
    row: dict[str, Any] | None,
    *,
    now: datetime.datetime | None = None,
) -> bool:
    payload = row if isinstance(row, dict) else {}
    current_plan = _normalize_user_app_plan(payload.get("current_plan"))
    if current_plan != USER_APP_PLAN_CODE:
        return False
    period_end = _as_utc_datetime(payload.get("current_period_end"))
    if not period_end:
        return False
    now_utc = now or _utc_now()
    return period_end > now_utc


async def ensure_user_app_subscription(user_id: int) -> dict[str, Any]:
    user_id_int = int(user_id)
    now_utc = _utc_now()
    row = await storage.bot_user_app_subscriptions.get(user_id=user_id_int)
    if row and row.get("id"):
        updates: dict[str, Any] = {}
        current_plan = _normalize_user_app_plan(row.get("current_plan"))
        pending_plan = _normalize_user_app_plan(row.get("pending_plan"))
        if str(row.get("current_plan") or "").strip().lower() != current_plan:
            updates["current_plan"] = current_plan
        if str(row.get("pending_plan") or "").strip().lower() != pending_plan:
            updates["pending_plan"] = pending_plan
        if current_plan != USER_APP_PLAN_CODE:
            if row.get("current_period_start"):
                updates["current_period_start"] = None
            if row.get("current_period_end"):
                updates["current_period_end"] = None
        if updates:
            updates["updated_at"] = now_utc
            await storage.bot_user_app_subscriptions.update(id=row["id"], **updates)
            row = await storage.bot_user_app_subscriptions.get(user_id=user_id_int) or {**row, **updates}
        return row

    await storage.bot_user_app_subscriptions.insert(
        user_id=user_id_int,
        current_plan="free",
        pending_plan="",
        auto_renew=True,
        status="free",
        current_period_start=None,
        current_period_end=None,
        updated_at=now_utc,
    )
    return await storage.bot_user_app_subscriptions.get(user_id=user_id_int) or {
        "user_id": user_id_int,
        "current_plan": "free",
        "status": "free",
    }


async def get_user_app_subscription(user_id: int) -> dict[str, Any]:
    return await ensure_user_app_subscription(int(user_id))


async def user_has_active_app_plan(user_id: int) -> bool:
    row = await ensure_user_app_subscription(int(user_id))
    return _is_user_app_subscription_active(row)


async def subscribe_user_app_plan(
    *,
    user_id: int,
    auto_renew: bool = True,
) -> tuple[bool, str, dict[str, Any] | None]:
    user_id_int = int(user_id)
    row = await ensure_user_app_subscription(user_id_int)
    if not row or not row.get("id"):
        return False, "ไม่สามารถสร้างข้อมูลแผนผู้ใช้ได้", None

    now_utc = _utc_now()
    if _is_user_app_subscription_active(row, now=now_utc):
        updated = await storage.bot_user_app_subscriptions.update(
            id=row["id"],
            auto_renew=bool(auto_renew),
            pending_plan="",
            status="active",
            updated_at=now_utc,
            last_notice="user_app_plan_autorenew_updated",
        )
        await _append_billing_event(
            user_id=user_id_int,
            guild_id=None,
            event_type="plan_user_app_autorenew_updated",
            message="อัปเดตการต่ออายุ App User Plan สำเร็จ",
            level="info",
            meta={"auto_renew": bool(auto_renew), "plan_tier": USER_APP_PLAN_CODE},
        )
        return True, "คุณมี App User Plan อยู่แล้ว และอัปเดตการต่ออายุเรียบร้อย", updated

    pricing_settings = await get_plan_pricing_settings()
    user_quote = build_user_app_price_quote(settings=pricing_settings, now=now_utc)
    charge_amount = float(user_quote.get("final_price") or 0.0)
    ok = True
    reason = ""
    if charge_amount > 0:
        ok, reason, _ledger = await debit_wallet(
            user_id=user_id_int,
            amount=charge_amount,
            kind="plan_debit",
            source_mode="plan",
            guild_id=None,
            note=f"Subscribe {USER_APP_PLAN_CODE}",
            meta={
                "plan_tier": USER_APP_PLAN_CODE,
                "scope": "user",
                "base_price": float(user_quote.get("base_price") or charge_amount),
                "final_price": charge_amount,
                "discount_percent": float(user_quote.get("discount_percent") or 0.0),
                "promo_active": bool(user_quote.get("promo_active")),
            },
        )
    if not ok:
        updated = await storage.bot_user_app_subscriptions.update(
            id=row["id"],
            pending_plan=USER_APP_PLAN_CODE,
            auto_renew=bool(auto_renew),
            status="awaiting_payment",
            updated_at=now_utc,
            last_notice="insufficient_balance",
        )
        await _append_billing_event(
            user_id=user_id_int,
            guild_id=None,
            event_type="plan_user_app_payment_required",
            message=f"ยอดเงินไม่พอสำหรับสมัคร App User Plan ({charge_amount:.2f} THB)",
            level="warning",
            meta={
                "plan_tier": USER_APP_PLAN_CODE,
                "amount": charge_amount,
                "base_price": float(user_quote.get("base_price") or charge_amount),
                "discount_percent": float(user_quote.get("discount_percent") or 0.0),
            },
        )
        return False, f"ยอดเงินไม่พอสำหรับสมัคร App User Plan ({charge_amount:.2f} THB)", updated

    period_start = now_utc
    period_end = now_utc + datetime.timedelta(days=PLAN_DURATION_DAYS)
    updated = await storage.bot_user_app_subscriptions.update(
        id=row["id"],
        current_plan=USER_APP_PLAN_CODE,
        pending_plan="",
        auto_renew=bool(auto_renew),
        status="active",
        current_period_start=period_start,
        current_period_end=period_end,
        last_charge_at=now_utc,
        last_charge_amount=charge_amount,
        last_notice="user_app_plan_activated",
        updated_at=now_utc,
    )
    await _append_billing_event(
        user_id=user_id_int,
        guild_id=None,
        event_type="plan_user_app_activated",
        message="สมัคร App User Plan สำเร็จ",
        level="success",
        meta={
            "plan_tier": USER_APP_PLAN_CODE,
            "amount": charge_amount,
            "base_price": float(user_quote.get("base_price") or charge_amount),
            "discount_percent": float(user_quote.get("discount_percent") or 0.0),
            "promo_active": bool(user_quote.get("promo_active")),
            "period_end": period_end.isoformat(),
        },
    )
    return True, "สมัคร App User Plan สำเร็จแล้ว", updated


async def cancel_user_app_plan(
    *,
    user_id: int,
) -> tuple[bool, str, dict[str, Any] | None]:
    user_id_int = int(user_id)
    row = await ensure_user_app_subscription(user_id_int)
    if not row or not row.get("id"):
        return False, "ไม่สามารถโหลดข้อมูลแผนผู้ใช้ได้", None

    now_utc = _utc_now()
    current_plan = _normalize_user_app_plan(row.get("current_plan"))
    updated = await storage.bot_user_app_subscriptions.update(
        id=row["id"],
        auto_renew=False,
        pending_plan="free",
        status="active" if current_plan == USER_APP_PLAN_CODE else "free",
        last_notice="user_app_plan_cancel_requested",
        updated_at=now_utc,
    )
    await _append_billing_event(
        user_id=user_id_int,
        guild_id=None,
        event_type="plan_user_app_cancel_requested",
        message="ยกเลิกการต่ออายุ App User Plan แล้ว",
        level="info",
        meta={"plan_tier": USER_APP_PLAN_CODE},
    )
    return True, "ยกเลิกการต่ออายุอัตโนมัติแล้ว (สิทธิ์ปัจจุบันยังใช้ได้จนหมดอายุ)", updated


async def process_user_app_billing_cycle(bot: Any) -> int:
    processed = 0
    now_utc = _utc_now()
    pricing_settings = await get_plan_pricing_settings()
    renew_quote = build_user_app_price_quote(settings=pricing_settings, now=now_utc)
    renew_amount = float(renew_quote.get("final_price") or 0.0)
    rows = await storage.bot_user_app_subscriptions.get_all()
    for row in rows or []:
        row_id = int(row.get("id") or 0)
        user_id = int(row.get("user_id") or 0)
        if row_id <= 0 or user_id <= 0:
            continue

        current_plan = _normalize_user_app_plan(row.get("current_plan"))
        pending_plan = _normalize_user_app_plan(row.get("pending_plan"))
        auto_renew = bool(row.get("auto_renew", True))
        period_end = _as_utc_datetime(row.get("current_period_end"))

        if current_plan == "free":
            if pending_plan == USER_APP_PLAN_CODE and auto_renew:
                ok, _message, _updated = await subscribe_user_app_plan(
                    user_id=user_id,
                    auto_renew=auto_renew,
                )
                if ok:
                    processed += 1
            continue

        if current_plan != USER_APP_PLAN_CODE:
            continue

        if not period_end:
            await storage.bot_user_app_subscriptions.update(
                id=row_id,
                current_plan="free",
                status="free",
                pending_plan="free",
                current_period_start=None,
                current_period_end=None,
                updated_at=now_utc,
                last_notice="user_app_plan_missing_period_end",
            )
            await _append_billing_event(
                user_id=user_id,
                guild_id=None,
                event_type="plan_user_app_missing_period_end",
                message="App User Plan ถูกปิดเนื่องจากไม่พบวันหมดอายุ",
                level="warning",
                meta={"plan_tier": USER_APP_PLAN_CODE},
            )
            processed += 1
            continue

        if period_end > now_utc:
            continue

        renewed = False
        renew_reason = ""
        if auto_renew:
            ok = True
            reason = ""
            if renew_amount > 0:
                ok, reason, _ledger = await debit_wallet(
                    user_id=user_id,
                    amount=renew_amount,
                    kind="plan_debit",
                    source_mode="plan",
                    guild_id=None,
                    note=f"Auto-renew {USER_APP_PLAN_CODE}",
                    meta={
                        "plan_tier": USER_APP_PLAN_CODE,
                        "renewal": True,
                        "scope": "user",
                        "base_price": float(renew_quote.get("base_price") or renew_amount),
                        "final_price": renew_amount,
                        "discount_percent": float(renew_quote.get("discount_percent") or 0.0),
                        "promo_active": bool(renew_quote.get("promo_active")),
                    },
                )
            if ok:
                period_start = now_utc
                period_end_new = now_utc + datetime.timedelta(days=PLAN_DURATION_DAYS)
                await storage.bot_user_app_subscriptions.update(
                    id=row_id,
                    current_plan=USER_APP_PLAN_CODE,
                    pending_plan="",
                    status="active",
                    auto_renew=auto_renew,
                    current_period_start=period_start,
                    current_period_end=period_end_new,
                    last_charge_at=now_utc,
                    last_charge_amount=renew_amount,
                    last_notice="user_app_plan_renewed",
                    updated_at=now_utc,
                )
                await _append_billing_event(
                    user_id=user_id,
                    guild_id=None,
                    event_type="plan_user_app_renewed",
                    message="ต่ออายุ App User Plan สำเร็จ",
                    level="success",
                    meta={
                        "plan_tier": USER_APP_PLAN_CODE,
                        "amount": renew_amount,
                        "base_price": float(renew_quote.get("base_price") or renew_amount),
                        "discount_percent": float(renew_quote.get("discount_percent") or 0.0),
                        "promo_active": bool(renew_quote.get("promo_active")),
                        "period_end": period_end_new.isoformat(),
                    },
                )
                await _notify_billing_users(
                    bot=bot,
                    user_ids=[user_id],
                    message="App User Plan ของคุณต่ออายุอัตโนมัติสำเร็จแล้ว",
                )
                renewed = True
                processed += 1
            else:
                renew_reason = str(reason or "").strip() or "Auto-renew failed"

        if renewed:
            continue

        next_pending = USER_APP_PLAN_CODE if auto_renew else "free"
        next_status = "awaiting_payment" if auto_renew else "free"
        await storage.bot_user_app_subscriptions.update(
            id=row_id,
            current_plan="free",
            pending_plan=next_pending,
            status=next_status,
            current_period_start=None,
            current_period_end=None,
            last_notice="user_app_plan_expired",
            updated_at=now_utc,
        )
        await _append_billing_event(
            user_id=user_id,
            guild_id=None,
            event_type="plan_user_app_expired",
            message=(
                "App User Plan หมดอายุและรอตัดเงินรอบถัดไป"
                if auto_renew
                else "App User Plan หมดอายุและถูกปรับเป็น Free"
            ),
            level="warning",
            meta={
                "plan_tier": USER_APP_PLAN_CODE,
                "auto_renew": auto_renew,
                "reason": renew_reason,
            },
        )
        notify_message = (
            f"App User Plan ของคุณหมดอายุ: {renew_reason or 'ยอดเงินไม่พอสำหรับต่ออายุอัตโนมัติ'}"
            if auto_renew
            else "App User Plan ของคุณหมดอายุแล้ว"
        )
        await _notify_billing_users(bot=bot, user_ids=[user_id], message=notify_message)
        processed += 1

    return processed


async def _purge_premium_data_for_guild(guild_id: int) -> None:
    guild_id_int = int(guild_id)
    welcomer_cache = cache.welcomer_settings.get(str(guild_id_int), {}) if hasattr(cache, "welcomer_settings") else {}
    if not welcomer_cache:
        await storage.welcomer_settings.insert(guild_id=guild_id_int)
        welcomer_cache = cache.welcomer_settings.get(str(guild_id_int), {}) if hasattr(cache, "welcomer_settings") else {}

    try:
        cuted_autoroles = _safe_list(welcomer_cache.get("autoroles"))[:3]
        greet_channels = _safe_list(welcomer_cache.get("greet_channels"))[:5]
        if welcomer_cache.get("id"):
            await storage.welcomer_settings.update(
                id=welcomer_cache.get("id"),
                guild_id=guild_id_int,
                autoroles_limit=3,
                autoroles=json.dumps(cuted_autoroles),
                greet_channels=json.dumps(greet_channels),
            )
    except Exception:
        pass

    try:
        await storage.media_channels.delete_limited(limit=1, guild_id=guild_id_int)
    except Exception:
        pass
    try:
        await storage.auto_responder.delete_limited(limit=5, guild_id=guild_id_int)
    except Exception:
        pass


async def process_plan_billing_cycle(bot: Any) -> int:
    processed = 0
    now_utc = _utc_now()
    pricing_settings = await get_plan_pricing_settings()

    # Backfill missing billing rows for paid guilds before running renew/expire checks.
    # Take a stable snapshot because cache can mutate while this scheduler is running.
    guild_items_snapshot = list((getattr(cache, "guilds", {}) or {}).items())
    for guild_id_text, guild_state in guild_items_snapshot:
        try:
            guild_id_int = int(str(guild_id_text).strip())
        except Exception:
            continue
        if guild_id_int <= 0:
            continue
        guild_plan = _normalize_plan((guild_state or {}).get("subscription") if isinstance(guild_state, dict) else None)
        if guild_plan == "free":
            continue
        try:
            await sync_plan_subscription_with_guild_state(guild_id=guild_id_int)
        except Exception:
            continue

    rows = await storage.bot_plan_subscriptions.get_all()
    for row in rows or []:
        row_id = row.get("id")
        if not row_id:
            continue
        guild_id = int(row.get("guild_id") or 0)
        if guild_id <= 0:
            continue

        row = await sync_plan_subscription_with_guild_state(guild_id=guild_id)
        row_id = row.get("id") or row_id
        current_plan = _normalize_plan(row.get("current_plan"))
        pending_plan = _normalize_plan(row.get("pending_plan"))
        auto_renew = bool(row.get("auto_renew"))
        user_id = int(row.get("user_id") or 0) or None
        period_end = _as_utc_datetime(row.get("current_period_end"))
        grace_until = _as_utc_datetime(row.get("grace_until"))
        grace_notified_at = _as_utc_datetime(row.get("grace_notified_at"))
        purge_due_at = _as_utc_datetime(row.get("purge_due_at"))
        purge_done_at = _as_utc_datetime(row.get("purge_done_at"))

        # Auto-reactivate queued paid plans when currently free and wallet has enough.
        if current_plan == "free" and pending_plan in {"silver", "golden", "diamond", "permanent"} and auto_renew:
            price_quote = build_plan_price_quote(pending_plan, settings=pricing_settings, now=now_utc)
            price = float(price_quote.get("final_price") or 0.0)
            if user_id:
                ok = True
                if price > 0:
                    ok, _reason, _ = await debit_wallet(
                        user_id=user_id,
                        amount=price,
                        kind="plan_debit",
                        source_mode="plan",
                        guild_id=guild_id,
                        note=f"Auto-reactivate plan {pending_plan}",
                        meta={
                            "plan_tier": pending_plan,
                            "reactivate": True,
                            "base_price": float(price_quote.get("base_price") or price),
                            "final_price": price,
                            "discount_percent": float(price_quote.get("discount_percent") or 0.0),
                            "promo_active": bool(price_quote.get("promo_active")),
                        },
                    )
                if ok:
                    period_start = now_utc
                    period_end_new = (
                        None
                        if pending_plan == "permanent"
                        else (now_utc + datetime.timedelta(days=PLAN_DURATION_DAYS))
                    )
                    await _apply_guild_plan_period(
                        bot=bot,
                        guild_id=guild_id,
                        plan_tier=pending_plan,
                        period_start=period_start,
                        period_end=period_end_new,
                    )
                    await storage.bot_plan_subscriptions.update(
                        id=row_id,
                        current_plan=pending_plan,
                        pending_plan="",
                        status="active",
                        current_period_start=period_start,
                        current_period_end=period_end_new,
                        auto_renew=(False if pending_plan == "permanent" else auto_renew),
                        grace_notified_at=None,
                        grace_until=None,
                        premium_disabled_at=None,
                        unpaid_since=None,
                        purge_due_at=None,
                        purge_done_at=None,
                        last_charge_at=now_utc,
                        last_charge_amount=price,
                        last_notice="reactivated",
                        updated_at=now_utc,
                    )
                    notify_user_ids = await _collect_guild_notify_user_ids(guild_id, fallback_user_id=user_id)
                    await _notify_billing_users(
                        bot=bot,
                        user_ids=notify_user_ids,
                        message=f"Guild {guild_id} reactivated to {pending_plan}.",
                    )
                    await _append_billing_event(
                        user_id=user_id,
                        guild_id=guild_id,
                        event_type="plan_autorenew_debited",
                        message=f"Auto-renew charge success {price:.2f} THB for plan {pending_plan}",
                        level="success",
                        meta={
                            "plan_tier": pending_plan,
                            "amount": price,
                            "mode": "reactivate",
                            "base_price": float(price_quote.get("base_price") or price),
                            "discount_percent": float(price_quote.get("discount_percent") or 0.0),
                            "promo_active": bool(price_quote.get("promo_active")),
                        },
                    )
                    await _append_billing_event(
                        user_id=user_id,
                        guild_id=guild_id,
                        event_type="plan_reactivated",
                        message=f"Plan {pending_plan} reactivated successfully.",
                        level="success",
                    )
                    processed += 1
            continue

        if current_plan not in {"free", "permanent"} and not period_end:
            if str(row.get("last_notice") or "") != "missing_period_end":
                notify_user_ids = await _collect_guild_notify_user_ids(guild_id, fallback_user_id=user_id)
                await _notify_billing_users(
                    bot=bot,
                    user_ids=notify_user_ids,
                    message=(
                        f"Billing warning for guild {guild_id}: plan end date is missing. "
                        "Please update plan end in dashboard to continue auto-renew."
                    ),
                )
                await _append_billing_event(
                    user_id=user_id,
                    guild_id=guild_id,
                    event_type="plan_missing_period_end",
                    message="Auto-renew skipped because current_period_end is missing.",
                    level="warning",
                )
                await storage.bot_plan_subscriptions.update(
                    id=row_id,
                    last_notice="missing_period_end",
                    updated_at=now_utc,
                )
                processed += 1
            continue

        if current_plan == "free" or (current_plan != "permanent" and not period_end):
            if purge_due_at and not purge_done_at and purge_due_at <= now_utc:
                await _purge_premium_data_for_guild(guild_id)
                await storage.bot_plan_subscriptions.update(
                    id=row_id,
                    purge_done_at=now_utc,
                    last_notice="purged_after_90_days",
                    updated_at=now_utc,
                )
                notify_user_ids = await _collect_guild_notify_user_ids(guild_id, fallback_user_id=user_id)
                await _notify_billing_users(
                    bot=bot,
                    user_ids=notify_user_ids,
                    message=f"Guild {guild_id} unpaid for 90 days. Premium data has been purged.",
                )
                await _append_billing_event(
                    user_id=user_id,
                    guild_id=guild_id,
                    event_type="premium_purged",
                    message="Unpaid >90 days. Premium data purged.",
                    level="warning",
                )
                processed += 1
            continue

        if current_plan == "permanent":
            continue

        if period_end > now_utc:
            continue

        grace_limit = period_end + datetime.timedelta(days=PLAN_GRACE_DAYS)
        target_plan = pending_plan if pending_plan in {"silver", "golden", "diamond", "permanent"} else current_plan
        renew_quote = build_plan_price_quote(target_plan, settings=pricing_settings, now=now_utc)
        renew_price = float(renew_quote.get("final_price") or 0.0)
        renew_failed_reason = ""
        attempted_auto_charge = False

        if now_utc < grace_limit:
            if auto_renew and target_plan in {"silver", "golden", "diamond", "permanent"} and user_id:
                attempted_auto_charge = True
                ok = True
                reason = ""
                if renew_price > 0:
                    ok, reason, _ = await debit_wallet(
                        user_id=user_id,
                        amount=renew_price,
                        kind="plan_debit",
                        source_mode="plan",
                        guild_id=guild_id,
                        note=f"Auto-renew plan {target_plan}",
                        meta={
                            "plan_tier": target_plan,
                            "renewal": True,
                            "base_price": float(renew_quote.get("base_price") or renew_price),
                            "final_price": renew_price,
                            "discount_percent": float(renew_quote.get("discount_percent") or 0.0),
                            "promo_active": bool(renew_quote.get("promo_active")),
                        },
                    )
                if ok:
                    period_start = now_utc
                    period_end_new = (
                        None
                        if target_plan == "permanent"
                        else (now_utc + datetime.timedelta(days=PLAN_DURATION_DAYS))
                    )
                    await _apply_guild_plan_period(
                        bot=bot,
                        guild_id=guild_id,
                        plan_tier=target_plan,
                        period_start=period_start,
                        period_end=period_end_new,
                    )
                    await storage.bot_plan_subscriptions.update(
                        id=row_id,
                        current_plan=target_plan,
                        pending_plan="" if pending_plan != "free" else "free",
                        status="active",
                        current_period_start=period_start,
                        current_period_end=period_end_new,
                        auto_renew=(False if target_plan == "permanent" else auto_renew),
                        grace_notified_at=None,
                        grace_until=None,
                        premium_disabled_at=None,
                        unpaid_since=None,
                        purge_due_at=None,
                        purge_done_at=None,
                        last_charge_at=now_utc,
                        last_charge_amount=renew_price,
                        last_notice="renew_success",
                        updated_at=now_utc,
                    )
                    notify_user_ids = await _collect_guild_notify_user_ids(guild_id, fallback_user_id=user_id)
                    await _notify_billing_users(
                        bot=bot,
                        user_ids=notify_user_ids,
                        message=f"Auto-renew success for guild {guild_id}: {target_plan}.",
                    )
                    await _append_billing_event(
                        user_id=user_id,
                        guild_id=guild_id,
                        event_type="plan_autorenew_debited",
                        message=f"Auto-renew charge success {renew_price:.2f} THB for plan {target_plan}",
                        level="success",
                        meta={
                            "plan_tier": target_plan,
                            "amount": renew_price,
                            "mode": "renew",
                            "base_price": float(renew_quote.get("base_price") or renew_price),
                            "discount_percent": float(renew_quote.get("discount_percent") or 0.0),
                            "promo_active": bool(renew_quote.get("promo_active")),
                        },
                    )
                    await _append_billing_event(
                        user_id=user_id,
                        guild_id=guild_id,
                        event_type="plan_renewed",
                        message=f"Plan {target_plan} renewed successfully.",
                        level="success",
                    )
                    processed += 1
                    continue
                renew_failed_reason = str(reason or "").strip() or "Auto-renew charge failed."

            if not grace_notified_at:
                notice_message = (
                    (
                        f"Auto-renew charge failed for guild {guild_id} ({target_plan}) "
                        f"amount {renew_price:.2f} THB. Reason: {renew_failed_reason}. "
                        f"Please top up within {PLAN_GRACE_DAYS} day(s) to avoid downgrade to Free."
                    )
                    if auto_renew and attempted_auto_charge
                    else (
                        f"Guild {guild_id} plan has expired. Please top up within {PLAN_GRACE_DAYS} day(s) "
                        "to avoid downgrade to Free."
                        if auto_renew
                        else f"Guild {guild_id} plan has expired and will downgrade to Free after grace period."
                    )
                )
                notify_user_ids = await _collect_guild_notify_user_ids(guild_id, fallback_user_id=user_id)
                await _notify_billing_users(bot=bot, user_ids=notify_user_ids, message=notice_message)
                if auto_renew and attempted_auto_charge:
                    await _append_billing_event(
                        user_id=user_id,
                        guild_id=guild_id,
                        event_type="plan_autorenew_failed",
                        message=(
                            f"Auto-renew charge failed for plan {target_plan}: {renew_failed_reason} "
                            f"(amount {renew_price:.2f} THB)"
                        ),
                        level="warning",
                        meta={
                            "plan_tier": target_plan,
                            "amount": renew_price,
                            "reason": renew_failed_reason,
                            "base_price": float(renew_quote.get("base_price") or renew_price),
                            "discount_percent": float(renew_quote.get("discount_percent") or 0.0),
                            "promo_active": bool(renew_quote.get("promo_active")),
                        },
                    )
                await _append_billing_event(
                    user_id=user_id,
                    guild_id=guild_id,
                    event_type="plan_expired",
                    message=f"Plan expired for guild {guild_id} ({target_plan})",
                    level="warning",
                    meta={"plan_tier": target_plan, "period_end": period_end.isoformat()},
                )
                await _append_billing_event(
                    user_id=user_id,
                    guild_id=guild_id,
                    event_type="plan_grace_notice",
                    message=notice_message,
                    level="warning",
                )
                await storage.bot_plan_subscriptions.update(
                    id=row_id,
                    status="grace",
                    grace_notified_at=now_utc,
                    grace_until=grace_limit,
                    unpaid_since=period_end,
                    last_notice="grace_notice_sent",
                    updated_at=now_utc,
                )
                processed += 1
            continue

        # Out of grace -> downgrade to free now.
        await change_guild_subscription(
            bot=bot,
            guild_id=guild_id,
            subscription="free",
            valid_for_days=None,
        )
        purge_due_value = now_utc + datetime.timedelta(days=PLAN_PURGE_AFTER_DAYS)
        await storage.bot_plan_subscriptions.update(
            id=row_id,
            current_plan="free",
            status="free",
            premium_disabled_at=now_utc,
            unpaid_since=period_end,
            current_period_start=None,
            current_period_end=None,
            grace_until=grace_limit if grace_until is None else grace_until,
            purge_due_at=purge_due_value,
            last_notice="downgraded_to_free",
            updated_at=now_utc,
        )
        notify_user_ids = await _collect_guild_notify_user_ids(guild_id, fallback_user_id=user_id)
        await _notify_billing_users(
            bot=bot,
            user_ids=notify_user_ids,
            message=(
                f"Guild {guild_id} downgraded to Free after grace period ({PLAN_GRACE_DAYS} day(s))."
            ),
        )
        await _append_billing_event(
            user_id=user_id,
            guild_id=guild_id,
            event_type="plan_downgraded_free",
            message="Downgraded to Free after auto-renew grace period.",
            level="warning",
            meta={"purge_due_at": purge_due_value.isoformat()},
        )
        processed += 1
    return processed


async def run_billing_scheduler(bot: Any) -> None:
    global _billing_loop_running
    if _billing_loop_running:
        return
    _billing_loop_running = True
    while not bot.is_ready():
        await asyncio.sleep(1)
    while True:
        try:
            await expire_stale_payment_sessions()
            await auto_verify_pending_truemoney_sessions()
            await process_plan_billing_cycle(bot)
            await process_user_app_billing_cycle(bot)
            try:
                verify_cog = bot.get_cog("Verify") if hasattr(bot, "get_cog") else None
                if verify_cog and hasattr(verify_cog, "sync_support_plan_roles"):
                    await verify_cog.sync_support_plan_roles(force=False, reason="Billing scheduler plan role sync")
            except Exception as sync_error:
                logger.warning(f"Support plan role sync skipped: {sync_error}")
        except Exception as error:
            _log_billing_scheduler_error(error)
        await asyncio.sleep(BILLING_LOOP_INTERVAL_SECONDS)


