from __future__ import annotations

import datetime
import re
from typing import Any

from pymongo import ReturnDocument

import storage
from skylinebot.bridge.storage import get_collection
from skylinebot.console.logging import logger

MAX_REDEEM_CLAIMS = 100_000
CUSTOM_REDEEM_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{3,63}$")


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return int(default)


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return bool(default)
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _coerce_utc_datetime(value: Any) -> datetime.datetime | None:
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 10_000_000_000:
                ts /= 1000.0
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        except Exception:
            return None
    text = str(value).strip()
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


def _normalize_int_list(value: Any) -> list[int]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, tuple):
        rows = list(value)
    else:
        rows = []
    out: list[int] = []
    for row in rows:
        parsed = _safe_int(row, 0)
        if parsed <= 0 or parsed in out:
            continue
        out.append(parsed)
    return out


def normalize_redeem_code(raw_code: Any) -> str:
    text = str(raw_code or "").strip().upper()
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    return text[:64]


def is_valid_custom_redeem_code(raw_code: Any) -> bool:
    code = normalize_redeem_code(raw_code)
    if not code:
        return False
    return bool(CUSTOM_REDEEM_CODE_RE.fullmatch(code))


def coerce_max_claims(value: Any, default: int = 1) -> int:
    parsed = _safe_int(value, default)
    if parsed < 0:
        parsed = 0
    if parsed > MAX_REDEEM_CLAIMS:
        parsed = MAX_REDEEM_CLAIMS
    return int(parsed)


def normalize_redeem_lock_mode(raw_mode: Any) -> tuple[bool, bool, str]:
    mode = str(raw_mode or "").strip().lower()
    if mode in {"user_server", "user+server", "both", "1user1server", "one_user_one_server"}:
        return True, True, "user_server"
    if mode in {"user", "one_user"}:
        return True, False, "user"
    if mode in {"server", "guild", "one_server", "one_guild"}:
        return False, True, "server"
    return False, False, "none"


def lock_mode_from_flags(*, lock_unique_user: bool, lock_unique_guild: bool) -> str:
    if lock_unique_user and lock_unique_guild:
        return "user_server"
    if lock_unique_user:
        return "user"
    if lock_unique_guild:
        return "server"
    return "none"


def normalize_redeem_row(raw_row: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(raw_row or {})
    max_claims = coerce_max_claims(row.get("max_claims"), 1)
    claim_count = _safe_int(row.get("claim_count"), 0)
    if claim_count < 0:
        claim_count = 0

    mode_user, mode_guild, mode_value = normalize_redeem_lock_mode(row.get("lock_mode"))
    lock_unique_user = _as_bool(row.get("lock_unique_user"), mode_user)
    lock_unique_guild = _as_bool(row.get("lock_unique_guild"), mode_guild)
    if mode_value != "none":
        lock_unique_user = bool(lock_unique_user or mode_user)
        lock_unique_guild = bool(lock_unique_guild or mode_guild)
    lock_mode = lock_mode_from_flags(
        lock_unique_user=lock_unique_user,
        lock_unique_guild=lock_unique_guild,
    )
    if mode_value != "none" and lock_mode == "none":
        lock_mode = mode_value

    used_user_ids = _normalize_int_list(row.get("used_user_ids"))
    used_guild_ids = _normalize_int_list(row.get("used_guild_ids"))
    expires_at = _coerce_utc_datetime(row.get("expires_at"))
    claimed = bool(row.get("claimed"))
    if claimed and claim_count <= 0:
        claim_count = max(1, max_claims if max_claims > 0 else 1)
    if not claimed and max_claims > 0 and claim_count >= max_claims:
        claimed = True

    remaining_claims = None if max_claims == 0 else max(0, max_claims - claim_count)
    row["code"] = normalize_redeem_code(row.get("code"))
    row["max_claims"] = max_claims
    row["claim_count"] = claim_count
    row["lock_unique_user"] = bool(lock_unique_user)
    row["lock_unique_guild"] = bool(lock_unique_guild)
    row["lock_mode"] = lock_mode
    row["used_user_ids"] = used_user_ids
    row["used_guild_ids"] = used_guild_ids
    row["expires_at"] = expires_at
    row["claimed"] = bool(claimed)
    row["remaining_claims"] = remaining_claims
    return row


def redeem_block_reason(
    redeem_row: dict[str, Any] | None,
    *,
    user_id: int,
    guild_id: int | None = None,
    now: datetime.datetime | None = None,
) -> str | None:
    row = normalize_redeem_row(redeem_row)
    if not row:
        return "invalid_code"
    now_utc = now or _utc_now()
    if row.get("expires_at") and now_utc >= row["expires_at"]:
        return "expired"
    if bool(row.get("claimed")):
        return "already_claimed"
    max_claims = int(row.get("max_claims") or 0)
    claim_count = int(row.get("claim_count") or 0)
    if max_claims > 0 and claim_count >= max_claims:
        return "usage_limit_reached"
    if bool(row.get("lock_unique_user")) and int(user_id or 0) in set(row.get("used_user_ids") or []):
        return "user_already_used"
    if bool(row.get("lock_unique_guild")):
        target_guild_id = int(guild_id or 0)
        if target_guild_id > 0 and target_guild_id in set(row.get("used_guild_ids") or []):
            return "guild_already_used"
    return None


def redeem_reason_message_th(reason: str | None) -> str:
    mapping = {
        "invalid_code": "ไม่พบโค้ด Redeem นี้",
        "expired": "โค้ดนี้หมดอายุแล้ว",
        "already_claimed": "โค้ดนี้ถูกใช้งานครบแล้ว",
        "usage_limit_reached": "โค้ดนี้ถูกใช้งานครบจำนวนที่กำหนดแล้ว",
        "user_already_used": "บัญชีนี้เคยใช้โค้ดนี้แล้ว ไม่สามารถใช้ซ้ำได้",
        "guild_already_used": "เซิร์ฟเวอร์นี้เคยใช้โค้ดนี้แล้ว ไม่สามารถใช้ซ้ำได้",
        "missing_claim_id": "ไม่พบรหัสโค้ดสำหรับบันทึกการใช้งาน",
        "reserve_failed": "ไม่สามารถจองสิทธิ์โค้ดได้ในตอนนี้",
    }
    return mapping.get(str(reason or "").strip().lower(), "ไม่สามารถใช้โค้ดนี้ได้")


async def reserve_redeem_claim(
    *,
    redeem_row: dict[str, Any],
    user_id: int,
    guild_id: int | None,
    source: str,
) -> tuple[bool, dict[str, Any], str | None]:
    normalized = normalize_redeem_row(redeem_row)
    row_id = _safe_int(normalized.get("id"), 0)
    if row_id <= 0:
        return False, normalized, "missing_claim_id"

    reason = redeem_block_reason(normalized, user_id=int(user_id or 0), guild_id=guild_id)
    if reason:
        return False, normalized, reason

    now_utc = _utc_now()
    query: dict[str, Any] = {"id": row_id, "claimed": {"$ne": True}}
    if normalized.get("expires_at"):
        query["$or"] = [
            {"expires_at": {"$exists": False}},
            {"expires_at": None},
            {"expires_at": {"$gt": now_utc}},
        ]
    max_claims = int(normalized.get("max_claims") or 0)
    if max_claims > 0:
        query["$expr"] = {"$lt": [{"$ifNull": ["$claim_count", 0]}, max_claims]}
    if bool(normalized.get("lock_unique_user")):
        query["used_user_ids"] = {"$ne": int(user_id or 0)}
    if bool(normalized.get("lock_unique_guild")) and int(guild_id or 0) > 0:
        query["used_guild_ids"] = {"$ne": int(guild_id or 0)}

    update: dict[str, Any] = {
        "$inc": {"claim_count": 1},
        "$set": {
            "claimed_by": int(user_id or 0),
            "claimed_at": now_utc,
            "last_claim_source": str(source or "unknown").strip().lower()[:40],
            "last_claim_user_id": int(user_id or 0),
        },
    }
    if int(guild_id or 0) > 0:
        update["$set"]["last_claim_guild_id"] = int(guild_id or 0)

    add_to_set_payload: dict[str, Any] = {}
    if bool(normalized.get("lock_unique_user")):
        add_to_set_payload["used_user_ids"] = int(user_id or 0)
    if bool(normalized.get("lock_unique_guild")) and int(guild_id or 0) > 0:
        add_to_set_payload["used_guild_ids"] = int(guild_id or 0)
    if add_to_set_payload:
        update["$addToSet"] = add_to_set_payload

    collection = await get_collection(storage.redeem_codes.COLLECTION_NAME)
    row_after = await collection.find_one_and_update(
        query,
        update,
        return_document=ReturnDocument.AFTER,
    )
    if not row_after:
        latest = await storage.redeem_codes.get(id=row_id)
        latest_normalized = normalize_redeem_row(latest or normalized)
        latest_reason = redeem_block_reason(
            latest_normalized,
            user_id=int(user_id or 0),
            guild_id=guild_id,
        )
        return False, latest_normalized, latest_reason or "reserve_failed"

    return True, normalize_redeem_row(dict(row_after)), None


async def finalize_redeem_claim_success(
    *,
    redeem_row: dict[str, Any],
    user_id: int,
    guild_id: int | None,
    source: str,
) -> dict[str, Any]:
    normalized = normalize_redeem_row(redeem_row)
    row_id = _safe_int(normalized.get("id"), 0)
    if row_id <= 0:
        return normalized

    claim_count = int(normalized.get("claim_count") or 0)
    max_claims = int(normalized.get("max_claims") or 0)
    claimed_final = bool(max_claims > 0 and claim_count >= max_claims)
    now_utc = _utc_now()
    claim_entry = {
        "claimed_at": now_utc,
        "source": str(source or "unknown").strip().lower()[:40],
        "user_id": int(user_id or 0),
    }
    if int(guild_id or 0) > 0:
        claim_entry["guild_id"] = int(guild_id or 0)

    collection = await get_collection(storage.redeem_codes.COLLECTION_NAME)
    row_after = await collection.find_one_and_update(
        {"id": row_id},
        {
            "$set": {
                "claimed": claimed_final,
                "claimed_by": int(user_id or 0),
                "claimed_at": now_utc,
            },
            "$push": {
                "claim_history": {
                    "$each": [claim_entry],
                    "$slice": -300,
                }
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    return normalize_redeem_row(dict(row_after or normalized))


async def rollback_redeem_claim(
    *,
    redeem_row: dict[str, Any],
    user_id: int,
    guild_id: int | None,
) -> dict[str, Any]:
    normalized = normalize_redeem_row(redeem_row)
    row_id = _safe_int(normalized.get("id"), 0)
    if row_id <= 0:
        return normalized

    update: dict[str, Any] = {
        "$inc": {"claim_count": -1},
        "$set": {"claimed": False},
    }
    pull_payload: dict[str, Any] = {}
    if bool(normalized.get("lock_unique_user")):
        pull_payload["used_user_ids"] = int(user_id or 0)
    if bool(normalized.get("lock_unique_guild")) and int(guild_id or 0) > 0:
        pull_payload["used_guild_ids"] = int(guild_id or 0)
    if pull_payload:
        update["$pull"] = pull_payload

    collection = await get_collection(storage.redeem_codes.COLLECTION_NAME)
    row_after = await collection.find_one_and_update(
        {"id": row_id},
        update,
        return_document=ReturnDocument.AFTER,
    )
    if isinstance(row_after, dict):
        claim_count = _safe_int(row_after.get("claim_count"), 0)
        if claim_count < 0:
            try:
                await collection.update_one({"id": row_id}, {"$set": {"claim_count": 0}})
            except Exception as error:
                logger.warning(f"Failed to clamp negative claim_count for redeem id={row_id}: {error}")
            row_after["claim_count"] = 0
    return normalize_redeem_row(dict(row_after or normalized))
