import datetime
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import storage
from skylinebot.console.generator import generate_redeem_code
from skylinebot.console.logging import logger
from skylinebot.config.config import Types
from skylinebot.workflows.redeem_control import (
    coerce_max_claims,
    is_valid_custom_redeem_code,
    lock_mode_from_flags,
    normalize_redeem_code,
    normalize_redeem_lock_mode,
)

router = APIRouter()
redeem_code_types = Types.redeem_code_types


@router.post("/redeem/generate/")
async def generate_redeem(request: Request):
    try:
        authorization = request.headers.get("Authorization")

        if not authorization:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authorization header not found.",
                    "error_code": "WEB-REDEEM-AUTH-HEADER-401",
                },
            )
        if authorization.startswith("Bearer "):
            authorization = authorization.replace("Bearer ", "")
        authorization = authorization.strip()
        if authorization != "Goahfo9uqehrflokanfijuvahfgiu89whnfjkgb234":
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid authorization token.",
                    "error_code": "WEB-REDEEM-AUTH-TOKEN-401",
                },
            )

        try:
            data = await request.json()
        except Exception:
            data = {}

        logger.info(f"Received request to generate redeem code with data: {data}")

        selected_code_type = str(data.get("code_type") or "").strip()
        code_validity = int(data.get("validity", 30))
        custom_code = normalize_redeem_code(data.get("code"))
        max_claims = coerce_max_claims(data.get("max_claims"), 1)
        mode_user, mode_guild, _ = normalize_redeem_lock_mode(data.get("lock_mode"))
        lock_unique_user = bool(mode_user or str(data.get("lock_unique_user", "")).strip().lower() in {"1", "true", "yes", "on"})
        lock_unique_guild = bool(mode_guild or str(data.get("lock_unique_guild", "")).strip().lower() in {"1", "true", "yes", "on"})
        lock_mode = lock_mode_from_flags(
            lock_unique_user=lock_unique_user,
            lock_unique_guild=lock_unique_guild,
        )

        if not selected_code_type or code_validity is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Missing required fields.",
                    "error_code": "WEB-REDEEM-REQUIRED-400",
                    "fields": "code_type, validity",
                    "example": {"code_type": "no_prefix", "validity": 0},
                },
            )

        if selected_code_type not in redeem_code_types:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid code type.",
                    "error_code": "WEB-REDEEM-CODETYPE-400",
                    "valid_types": list(redeem_code_types.keys()),
                },
            )

        if custom_code:
            if not is_valid_custom_redeem_code(custom_code):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid code format.",
                        "error_code": "WEB-REDEEM-CODE-FORMAT-400",
                        "hint": "Use A-Z, 0-9, -, _ and length 4-64",
                    },
                )
            duplicate_row = await storage.redeem_codes.get(code=custom_code)
            if duplicate_row:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "Code already exists.",
                        "error_code": "WEB-REDEEM-CODE-DUPLICATE-409",
                    },
                )

        code_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        code = custom_code or normalize_redeem_code(generate_redeem_code())
        await storage.redeem_codes.insert(
            code=code,
            code_type="subscription",
            code_value=selected_code_type,
            valid_for_days=None if code_validity == 0 else code_validity,
            expires_at=code_expires_at,
            claimed=False,
            claimed_by=None,
            claimed_at=None,
            claim_count=0,
            max_claims=max_claims,
            lock_unique_user=lock_unique_user,
            lock_unique_guild=lock_unique_guild,
            lock_mode=lock_mode,
            used_user_ids=[],
            used_guild_ids=[],
            claim_history=[],
        )
        return JSONResponse(
            status_code=200,
            content={
                "data": {
                    "code": code,
                    "code_type": selected_code_type,
                    "validity": code_validity,
                    "expires_at": code_expires_at.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "max_claims": max_claims,
                    "lock_mode": lock_mode,
                }
            },
        )
    except Exception as error:
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": str(error), "error_code": "WEB-REDEEM-GENERATE-500"},
        )
