from pathlib import Path
import datetime
import html
import asyncio
import json
import logging
import mimetypes
import os
import re
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_redoc_html
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from skylinebot.config.config import BotConfigClass
from skylinebot.style import urls as style_urls
import storage.photo_assets as photo_assets_db
import storage.photo_asset_blobs as photo_asset_blobs_db
from skylinebot.surface.routes import dashboard_impl, redeem_code_routes, transcript
from skylinebot.surface.routes.dashboard_core import _is_dashboard_admin, _session_from_request
from skylinebot.surface.routes.dashboard_pages.public_impl import (
    dashboard_careers_page,
    dashboard_commands_help_page,
    dashboard_donatebot_hub,
    dashboard_donate_page,
    dashboard_guide_giveaways_page,
    dashboard_guide_security_page,
    dashboard_guide_ticket_page,
    dashboard_interactions_endpoint_page,
    dashboard_invite_hub,
    dashboard_invitebot_page,
    dashboard_leaderboard_page,
    dashboard_landing_home,
    dashboard_linked_role_verify_page,
    dashboard_personalizer_page,
    dashboard_personalizer_preview,
    dashboard_promote_history_action,
    dashboard_promote_history_page,
    dashboard_promote_server_page,
    dashboard_plugins_games_fun_page,
    dashboard_plugins_moderation_page,
    dashboard_plugins_social_alerts_page,
    dashboard_plugins_utilities_page,
    dashboard_premium_page,
    dashboard_privacy_page,
    dashboard_privacy_policy_page,
    dashboard_redeem_page,
    dashboard_redeem_submit,
    dashboard_report_page,
    dashboard_report_submit,
    dashboard_rule_bot_page,
    dashboard_rule_page,
    dashboard_rule_server_support_page,
    dashboard_runtime_control,
    dashboard_server_support_page,
    dashboard_docs_page,
    dashboard_subscribe_plan_page,
    dashboard_support_page,
    dashboard_system_status,
    dashboard_tags_page,
    dashboard_terms_page,
    dashboard_terms_of_service_page,
)
from skylinebot.surface.routes.dashboard_pages.billing_impl import (
    dashboard_donate_wallet_page,
    dashboard_wallet_page,
)
from skylinebot.surface.routes.dashboard_pages.guild_impl import (
    invalidate_dashboard_context_cache,
)
from skylinebot.surface.runtime import bind_bot, get_bot

app = FastAPI(
    title="เอกสาร API SkylineBOT Surface",
    description=(
        "เอกสาร API สำหรับ SkylineBOT Surface ครอบคลุมระบบบอท, "
        "เซิร์ฟเวอร์ซัพพอร์ต และเว็บแดชบอร์ด"
    ),
    version="3.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> JSONResponse:
    """Lightweight platform health check that does not require Discord or MongoDB."""
    return JSONResponse(
        {
            "status": "ok",
            "service": "skylinebot1",
        },
        headers={"Cache-Control": "no-store"},
    )


@app.head("/healthz", include_in_schema=False)
async def healthz_head() -> Response:
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


_LOG = logging.getLogger("skylinebot.surface.interactions")
_SURFACE_ROOT = Path(__file__).resolve().parent
_STATIC_ROOT = _SURFACE_ROOT / "static"
_PHOTO_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "photo"
_PHOTO_MONGODB_MIGRATION_MAX_BYTES = 20 * 1024 * 1024
_BOT_CONFIG = BotConfigClass()
CONTACT_EXTERNAL_URL = str(style_urls.CONTACT or "https://niceshopallforme.web.app/contact").strip()


class DashboardStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if response.status_code < 400 and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "public, max-age=604800, stale-while-revalidate=86400"
        return response


_PUBLIC_SITEMAP_PATHS: tuple[str, ...] = (
    "/",
    "/tags",
    "/commands",
    "/leaderboard",
    "/promotehistory",
    "/promoteserver",
    "/invite",
    "/invitebot",
    "/donate",
    "/donatebot",
    "/wallet",
    "/donate-wallet",
    "/interactions-endpoint",
    "/linked-role-verify",
    "/status",
    "/premium",
    "/subscribe-plan",
    "/redeem",
    "/docs",
    "/support",
    "/serversupport",
    "/rule",
    "/rule/bot",
    "/rule/serversupport",
    "/personalizer",
    "/privacy",
    "/terms-of-service",
    "/terms",
    "/privacy-policy",
    "/careers",
    "/plugins/moderation",
    "/plugins/utilities",
    "/plugins/social-alerts",
    "/plugins/games-fun",
    "/report",
    "/guides/security",
    "/guides/giveaways",
    "/dashboard",
)
_PUBLIC_CANONICAL_ORIGIN = "https://skylinebot.xyz"
_PRIVATE_ROBOTS_PATHS: tuple[str, ...] = (
    "/api/",
    "/dashboard/admin/",
    "/dashboard/assets/",
    "/dashboard/auth/",
    "/dashboard/guild/",
    "/dashboard/login",
    "/dashboard/logout",
    "/dashboard/setting-profile-user/",
)
_LANGUAGE_ROUTE_PREFIXES: tuple[str, ...] = ("th", "en")
_LANGUAGE_COOKIE_KEY = "skyline_lang"
_LANGUAGE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

_DASHBOARD_PUBLIC_REDIRECT_MAP: dict[str, str] = {
    "/dashboard/commands": "/commands",
    "/dashboard/leaderboard": "/leaderboard",
    "/dashboard/promoteserver": "/promoteserver",
    "/dashboard/invite": "/invite",
    "/dashboard/invitebot": "/invitebot",
    "/dashboard/donate": "/donate",
    "/dashboard/donatebot": "/donatebot",
    "/dashboard/wallet": "/wallet",
    "/dashboard/donate-wallet": "/donate-wallet",
    "/dashboard/interactions-endpoint": "/interactions-endpoint",
    "/dashboard/linked-role-verify": "/linked-role-verify",
    "/dashboard/status": "/status",
    "/dashboard/premium": "/premium",
    "/dashboard/subscribe-plan": "/subscribe-plan",
    "/dashboard/redeem": "/redeem",
    "/dashboard/site": "/docs",
    "/dashboard/docs": "/docs",
    "/dashboard/support": "/support",
    "/dashboard/serversupport": "/serversupport",
    "/dashboard/ServerSupport": "/ServerSupport",
    "/dashboard/server-support": "/server-support",
    "/dashboard/rule": "/rule",
    "/dashboard/rule/bot": "/rule/bot",
    "/dashboard/rule/serversupport": "/rule/serversupport",
    "/dashboard/tags": "/tags",
    "/dashboard/personalizer": "/personalizer",
    "/dashboard/privacy": "/privacy",
    "/dashboard/privacy-policy": "/privacy-policy",
    "/dashboard/terms": "/terms",
    "/dashboard/terms-of-service": "/terms-of-service",
    "/dashboard/careers": "/careers",
    "/dashboard/plugins/moderation": "/plugins/moderation",
    "/dashboard/plugins/utilities": "/plugins/utilities",
    "/dashboard/plugins/social-alerts": "/plugins/social-alerts",
    "/dashboard/plugins/games-fun": "/plugins/games-fun",
    "/dashboard/report": "/report",
    "/guides/ticket": "/docs",
    "/dashboard/guides/ticket": "/docs",
    "/dashboard/guides/security": "/guides/security",
    "/dashboard/guides/giveaways": "/guides/giveaways",
}

_ERROR_CODE_DOCS_API_PATH = "/api/error-codes"
_ERROR_CODE_DOCS_WEB_PATH = "/docs#docs-web-error-codes"
_WEB_ERROR_CODE_BY_STATUS: dict[int, str] = {
    400: "WEB-REQ-400",
    401: "WEB-AUTH-401",
    403: "WEB-AUTH-403",
    404: "WEB-NOTFOUND-404",
    405: "WEB-METHOD-405",
    409: "WEB-CONFLICT-409",
    413: "WEB-PAYLOAD-413",
    415: "WEB-MEDIA-415",
    422: "WEB-VALIDATION-422",
    429: "WEB-RATE-429",
    500: "WEB-SERVER-500",
    502: "WEB-UPSTREAM-502",
    503: "WEB-SERVICE-503",
    504: "WEB-TIMEOUT-504",
}
_WEB_ERROR_CODE_BY_KEY: dict[str, str] = {
    "unauthorized": "WEB-AUTH-401",
    "forbidden": "WEB-AUTH-403",
    "invalid_request_signature": "WEB-SIGNATURE-401",
    "invalid_signature": "WEB-SIGNATURE-401",
    "invalid_json_payload": "WEB-REQ-400",
    "invalid_request_data": "WEB-VALIDATION-422",
    "runtime_control_not_configured": "WEB-RUNTIME-CONFIG-503",
    "bot_not_ready": "WEB-RUNTIME-BOT-503",
    "dispatch_failed": "WEB-RUNTIME-DISPATCH-503",
    "bot_not_bound": "WEB-RUNTIME-BIND-503",
    "invalid_component": "WEB-RUNTIME-COMPONENT-400",
    "invalid_action": "WEB-RUNTIME-ACTION-400",
    "reload_failed": "WEB-RUNTIME-RELOAD-500",
    "discord_application_public_key_is_not_configured": "WEB-INTERACTIONS-KEY-503",
    "webhook_secret_not_configured": "WEB-WEBHOOK-SECRET-503",
    "missing_user_session": "WEB-BILLING-SESSION-USER-401",
    "invalid_session_key": "WEB-BILLING-SESSION-KEY-400",
    "session_not_found": "WEB-BILLING-SESSION-NOTFOUND-404",
    "invalid_mode": "WEB-BILLING-MODE-400",
    "truemoney_secret_not_configured": "WEB-BILLING-TRUEMONEY-SECRET-503",
    "missing_session_key": "WEB-BILLING-WEBHOOK-SESSIONKEY-400",
    "payment_confirmation_failed": "WEB-BILLING-CONFIRM-400",
    "missing_thread": "WEB-CONTACT-THREAD-REQUIRED-400",
    "thread_not_found": "WEB-CONTACT-THREAD-NOTFOUND-404",
    "invalid_form": "WEB-CONTACT-FORM-400",
    "chat_disabled": "WEB-CONTACT-DISABLED-403",
    "thread_closed": "WEB-CONTACT-THREAD-CLOSED-409",
    "invalid_attachment": "WEB-CONTACT-ATTACHMENT-400",
    "empty_message": "WEB-CONTACT-EMPTY-400",
    "discord_channel_missing": "WEB-CONTACT-DISCORD-CHANNEL-409",
    "authorization_header_not_found": "WEB-REDEEM-AUTH-HEADER-401",
    "invalid_authorization_token": "WEB-REDEEM-AUTH-TOKEN-401",
    "missing_required_fields": "WEB-REDEEM-REQUIRED-400",
    "invalid_code_type": "WEB-REDEEM-CODETYPE-400",
}
_WEB_ERROR_REFERENCE: dict[str, dict[str, str | int]] = {
    "WEB-REQ-400": {
        "status": 400,
        "owner": "user",
        "category": "request",
        "summary": "Bad request",
        "hint": "ตรวจพารามิเตอร์, รูปแบบข้อมูล และข้อมูลที่ส่งในฟอร์มหรือ JSON",
    },
    "WEB-AUTH-401": {
        "status": 401,
        "owner": "user",
        "category": "auth",
        "summary": "Unauthorized",
        "hint": "เข้าสู่ระบบใหม่ หรือตรวจ token/header ว่าส่งถูกต้อง",
    },
    "WEB-AUTH-403": {
        "status": 403,
        "owner": "user",
        "category": "auth",
        "summary": "Forbidden",
        "hint": "บัญชีนี้ไม่มีสิทธิ์สำหรับ endpoint นี้ ให้ตรวจ role/permission",
    },
    "WEB-NOTFOUND-404": {
        "status": 404,
        "owner": "user",
        "category": "routing",
        "summary": "Not found",
        "hint": "ตรวจ URL, route path และ resource id ว่าถูกต้อง",
    },
    "WEB-METHOD-405": {
        "status": 405,
        "owner": "user",
        "category": "request",
        "summary": "Method not allowed",
        "hint": "endpoint นี้ไม่รองรับ method ที่ส่งมา ให้ใช้ method ตาม API docs",
    },
    "WEB-CONFLICT-409": {
        "status": 409,
        "owner": "user",
        "category": "state",
        "summary": "Conflict",
        "hint": "ข้อมูลซ้ำหรือสถานะไม่ตรงเงื่อนไข ลองรีเฟรชข้อมูลก่อนทำรายการซ้ำ",
    },
    "WEB-PAYLOAD-413": {
        "status": 413,
        "owner": "user",
        "category": "request",
        "summary": "Payload too large",
        "hint": "ขนาดไฟล์หรือ payload ใหญ่เกิน limit ของระบบ",
    },
    "WEB-MEDIA-415": {
        "status": 415,
        "owner": "user",
        "category": "request",
        "summary": "Unsupported media type",
        "hint": "ส่ง Content-Type ให้ถูกต้อง เช่น application/json หรือ multipart/form-data",
    },
    "WEB-VALIDATION-422": {
        "status": 422,
        "owner": "user",
        "category": "validation",
        "summary": "Validation failed",
        "hint": "ข้อมูลผ่านรูปแบบ JSON แต่ไม่ผ่านเงื่อนไข field ที่ระบบต้องการ",
    },
    "WEB-RATE-429": {
        "status": 429,
        "owner": "user",
        "category": "throttle",
        "summary": "Too many requests",
        "hint": "ส่งคำขอถี่เกินไป ให้เว้นช่วงแล้วลองใหม่",
    },
    "WEB-RUNTIME-400": {
        "status": 400,
        "owner": "user",
        "category": "runtime",
        "summary": "Runtime control payload is invalid",
        "hint": "ตรวจ action/component ที่ส่งเข้า runtime control ให้ตรงที่กำหนด",
    },
    "WEB-RUNTIME-ACTION-400": {
        "status": 400,
        "owner": "user",
        "category": "runtime",
        "summary": "Invalid runtime action",
        "hint": "ค่า action ต้องเป็น start, reload, stop หรือ restart",
    },
    "WEB-RUNTIME-COMPONENT-400": {
        "status": 400,
        "owner": "user",
        "category": "runtime",
        "summary": "Invalid runtime component",
        "hint": "ค่า component ต้องเป็น bot หรือ web",
    },
    "WEB-SIGNATURE-401": {
        "status": 401,
        "owner": "developer",
        "category": "security",
        "summary": "Signature verification failed",
        "hint": "ตรวจ signature secret/public key และการคำนวณลายเซ็นของ request",
    },
    "WEB-SERVER-500": {
        "status": 500,
        "owner": "developer",
        "category": "server",
        "summary": "Internal server error",
        "hint": "ตรวจ server log, traceback และ dependency ที่เกี่ยวข้อง",
    },
    "WEB-UPSTREAM-502": {
        "status": 502,
        "owner": "developer",
        "category": "upstream",
        "summary": "Bad gateway",
        "hint": "ตรวจ reverse proxy และ service upstream ว่า online และตอบกลับปกติ",
    },
    "WEB-SERVICE-503": {
        "status": 503,
        "owner": "developer",
        "category": "availability",
        "summary": "Service unavailable",
        "hint": "บริการหลักหรือ dependency ยังไม่พร้อม ให้ตรวจสถานะ bot/web/db",
    },
    "WEB-RUNTIME-CONFIG-503": {
        "status": 503,
        "owner": "developer",
        "category": "runtime",
        "summary": "Runtime control is not configured",
        "hint": "กำหนด runtime control token ให้ครบทั้ง process ที่ต้องเรียก endpoint นี้",
    },
    "WEB-RUNTIME-503": {
        "status": 503,
        "owner": "developer",
        "category": "runtime",
        "summary": "Runtime unavailable",
        "hint": "ตรวจว่า bot binding/runtime control token ถูกต้อง และ process ทำงานครบ",
    },
    "WEB-RUNTIME-BIND-503": {
        "status": 503,
        "owner": "developer",
        "category": "runtime",
        "summary": "Bot runtime is not bound",
        "hint": "ตรวจว่า web process bind กับ bot runtime แล้ว และ bot object พร้อมใช้งาน",
    },
    "WEB-RUNTIME-BOT-503": {
        "status": 503,
        "owner": "developer",
        "category": "runtime",
        "summary": "Bot runtime is not ready",
        "hint": "รอให้ bot online หรือเช็ก startup flow ว่าโหลดครบก่อนเรียก endpoint นี้",
    },
    "WEB-RUNTIME-DISPATCH-503": {
        "status": 503,
        "owner": "developer",
        "category": "runtime",
        "summary": "Interaction dispatch failed",
        "hint": "ตรวจ parser/connection ของ bot runtime และ stack trace จุด dispatch",
    },
    "WEB-RUNTIME-RELOAD-500": {
        "status": 500,
        "owner": "developer",
        "category": "runtime",
        "summary": "Runtime reload failed",
        "hint": "ตรวจ error log ของ bot.reload/reload_extension/tree.sync แล้วแก้ตามขั้นตอนที่ล้มเหลว",
    },
    "WEB-WEBHOOK-SECRET-503": {
        "status": 503,
        "owner": "developer",
        "category": "security",
        "summary": "Webhook secret is not configured",
        "hint": "ตั้งค่า secret/token สำหรับ webhook แล้วรีสตาร์ต service ที่เกี่ยวข้อง",
    },
    "WEB-INTERACTIONS-KEY-503": {
        "status": 503,
        "owner": "developer",
        "category": "security",
        "summary": "Discord interactions public key is missing",
        "hint": "ตั้งค่า DISCORD_APPLICATION_PUBLIC_KEY ให้ถูกต้องก่อนเปิด interactions endpoint",
    },
    "WEB-BILLING-AUTH-401": {
        "status": 401,
        "owner": "user",
        "category": "billing",
        "summary": "Billing endpoint requires authentication",
        "hint": "เข้าสู่ระบบใหม่ก่อนเรียก endpoint ที่เกี่ยวกับ wallet/billing",
    },
    "WEB-BILLING-SESSION-USER-401": {
        "status": 401,
        "owner": "user",
        "category": "billing",
        "summary": "Billing session is missing user context",
        "hint": "session ผู้ใช้ไม่สมบูรณ์ ให้ logout/login ใหม่แล้วลองอีกครั้ง",
    },
    "WEB-BILLING-SESSION-KEY-400": {
        "status": 400,
        "owner": "user",
        "category": "billing",
        "summary": "Billing session key is invalid",
        "hint": "ตรวจรูปแบบ session_key ว่าตรงกับค่าที่ระบบสร้างไว้",
    },
    "WEB-BILLING-SESSION-NOTFOUND-404": {
        "status": 404,
        "owner": "user",
        "category": "billing",
        "summary": "Billing session was not found",
        "hint": "session อาจหมดอายุหรือไม่เคยมีอยู่ ให้สร้างรายการใหม่",
    },
    "WEB-BILLING-FORBIDDEN-403": {
        "status": 403,
        "owner": "user",
        "category": "billing",
        "summary": "Billing session does not belong to this user",
        "hint": "ผู้ใช้ไม่มีสิทธิ์เข้าถึงรายการชำระเงินนี้",
    },
    "WEB-BILLING-MODE-400": {
        "status": 400,
        "owner": "user",
        "category": "billing",
        "summary": "Billing session mode is invalid for endpoint",
        "hint": "เรียก endpoint ให้ตรงประเภท session (topup/donate)",
    },
    "WEB-BILLING-TRUEMONEY-SECRET-503": {
        "status": 503,
        "owner": "developer",
        "category": "billing",
        "summary": "TrueMoney webhook secret is not configured",
        "hint": "ตั้งค่า truemoney webhook secret ในระบบก่อนรับ callback",
    },
    "WEB-BILLING-WEBHOOK-SIGNATURE-403": {
        "status": 403,
        "owner": "developer",
        "category": "billing",
        "summary": "Billing webhook signature is invalid",
        "hint": "ตรวจ algorithm/prefix/secret ของ signature ให้ตรงกับผู้ให้บริการ",
    },
    "WEB-BILLING-WEBHOOK-SECRET-403": {
        "status": 403,
        "owner": "developer",
        "category": "billing",
        "summary": "Billing webhook secret is invalid",
        "hint": "ตรวจ header secret ของ callback และค่า secret ในระบบให้ตรงกัน",
    },
    "WEB-BILLING-WEBHOOK-SESSIONKEY-400": {
        "status": 400,
        "owner": "user",
        "category": "billing",
        "summary": "Billing webhook payload is missing session key",
        "hint": "payload ต้องมี token ที่แม็ปกลับไปหา session_key ได้",
    },
    "WEB-BILLING-CONFIRM-400": {
        "status": 400,
        "owner": "user",
        "category": "billing",
        "summary": "Billing payment confirmation failed",
        "hint": "ตรวจข้อมูลหลักฐานการชำระเงิน แล้วลองยืนยันรายการใหม่",
    },
    "WEB-CONTACT-AUTH-401": {
        "status": 401,
        "owner": "user",
        "category": "contact",
        "summary": "Contact realtime endpoint requires login",
        "hint": "เข้าสู่ระบบก่อนใช้งาน contact realtime API",
    },
    "WEB-CONTACT-FORBIDDEN-403": {
        "status": 403,
        "owner": "user",
        "category": "contact",
        "summary": "Contact action is owner/admin only",
        "hint": "ใช้บัญชีที่มีสิทธิ์ OwnerBOT/Admin สำหรับ action นี้",
    },
    "WEB-CONTACT-THREAD-REQUIRED-400": {
        "status": 400,
        "owner": "user",
        "category": "contact",
        "summary": "Contact thread key is required",
        "hint": "ส่ง thread key ให้ครบก่อนเรียก endpoint ข้อความหรือจัดการ thread",
    },
    "WEB-CONTACT-THREAD-NOTFOUND-404": {
        "status": 404,
        "owner": "user",
        "category": "contact",
        "summary": "Contact thread was not found",
        "hint": "thread อาจถูกลบหรือไม่มีสิทธิ์เห็น thread นี้",
    },
    "WEB-CONTACT-FORM-400": {
        "status": 400,
        "owner": "user",
        "category": "contact",
        "summary": "Contact form payload is invalid",
        "hint": "ตรวจ field/form-data และชนิดข้อมูลที่ส่งในข้อความแชท",
    },
    "WEB-CONTACT-DISABLED-403": {
        "status": 403,
        "owner": "user",
        "category": "contact",
        "summary": "Contact chat is currently disabled",
        "hint": "รอผู้ดูแลเปิดระบบแชท หรือให้ OwnerBOT override สิทธิ์ก่อนส่งข้อความ",
    },
    "WEB-CONTACT-THREAD-CLOSED-409": {
        "status": 409,
        "owner": "user",
        "category": "contact",
        "summary": "Contact thread is closed",
        "hint": "เปิด thread ก่อน หรือเริ่ม thread ใหม่แล้วส่งข้อความอีกครั้ง",
    },
    "WEB-CONTACT-ATTACHMENT-400": {
        "status": 400,
        "owner": "user",
        "category": "contact",
        "summary": "Contact attachment is invalid",
        "hint": "ตรวจไฟล์แนบว่าผ่านขนาด/ชนิดไฟล์ที่ระบบรองรับ",
    },
    "WEB-CONTACT-EMPTY-400": {
        "status": 400,
        "owner": "user",
        "category": "contact",
        "summary": "Contact message is empty",
        "hint": "พิมพ์ข้อความหรือแนบไฟล์ก่อนกดส่ง",
    },
    "WEB-CONTACT-DISCORD-CHANNEL-409": {
        "status": 409,
        "owner": "developer",
        "category": "contact",
        "summary": "Discord contact mirror channel is not configured",
        "hint": "ตั้งค่า Discord guild/category สำหรับ web contact ก่อนส่งไฟล์แนบ",
    },
    "WEB-CONTACT-SEND-500": {
        "status": 500,
        "owner": "developer",
        "category": "contact",
        "summary": "Contact message persistence failed",
        "hint": "ตรวจ storage/database และ log จุด insert message",
    },
    "WEB-REDEEM-AUTH-HEADER-401": {
        "status": 401,
        "owner": "user",
        "category": "redeem",
        "summary": "Redeem generate request is missing authorization header",
        "hint": "ส่ง Authorization header ก่อนเรียก API generate redeem",
    },
    "WEB-REDEEM-AUTH-TOKEN-401": {
        "status": 401,
        "owner": "user",
        "category": "redeem",
        "summary": "Redeem generate token is invalid",
        "hint": "ตรวจ bearer token ให้ตรงกับค่า token ที่ระบบกำหนด",
    },
    "WEB-REDEEM-REQUIRED-400": {
        "status": 400,
        "owner": "user",
        "category": "redeem",
        "summary": "Redeem generate payload is missing required fields",
        "hint": "ส่ง code_type และ validity ให้ครบตามรูปแบบที่ API ต้องการ",
    },
    "WEB-REDEEM-CODETYPE-400": {
        "status": 400,
        "owner": "user",
        "category": "redeem",
        "summary": "Redeem code type is invalid",
        "hint": "เลือก code_type จากรายการ valid_types ที่ API ตอบกลับ",
    },
    "WEB-REDEEM-GENERATE-500": {
        "status": 500,
        "owner": "developer",
        "category": "redeem",
        "summary": "Redeem code generation failed",
        "hint": "ตรวจ log/traceback และ storage path ของการสร้าง redeem code",
    },
    "WEB-TIMEOUT-504": {
        "status": 504,
        "owner": "developer",
        "category": "upstream",
        "summary": "Gateway timeout",
        "hint": "ตรวจ timeout ของ proxy และ endpoint ปลายทางว่าไม่ช้า/ไม่ค้าง",
    },
    "WEB-REQUEST-4XX": {
        "status": 400,
        "owner": "user",
        "category": "request",
        "summary": "Client request error",
        "hint": "ตรวจข้อมูล input และวิธีเรียก endpoint ให้ตรงเอกสาร",
    },
    "WEB-SERVER-5XX": {
        "status": 500,
        "owner": "developer",
        "category": "server",
        "summary": "Server error",
        "hint": "ตรวจ log ฝั่งเซิร์ฟเวอร์และ dependency ทั้งหมดของเว็บ",
    },
    "WEB-UNKNOWN": {
        "status": 500,
        "owner": "developer",
        "category": "server",
        "summary": "Unknown error",
        "hint": "ตรวจ log เพื่อติดตามสาเหตุเชิงลึกของข้อผิดพลาดนี้",
    },
}


def _normalize_cors_origin(raw_value: str) -> str | None:
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    candidate = raw if "://" in raw else f"https://{raw}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return None
    scheme = str(parsed.scheme or "").strip().lower()
    netloc = str(parsed.netloc or "").strip()
    if scheme not in {"http", "https"} or not netloc:
        return None
    return f"{scheme}://{netloc}"


def _cors_allow_origins() -> list[str]:
    origins: set[str] = set()
    for raw_value in (
        str(getattr(_BOT_CONFIG, "DASHBOARD_BASE_URL", "") or ""),
        str(os.getenv("DASHBOARD_BASE_URL", "") or ""),
        str(os.getenv("SUPPORT_STATUS_PUBLIC_URL", "") or ""),
        str(os.getenv("PUBLIC_BASE_URL", "") or ""),
    ):
        normalized = _normalize_cors_origin(raw_value)
        if normalized:
            origins.add(normalized)
    extra_raw = str(os.getenv("CORS_ALLOW_ORIGINS", "") or "").strip()
    if extra_raw:
        for piece in extra_raw.split(","):
            normalized = _normalize_cors_origin(piece)
            if normalized:
                origins.add(normalized)

    local_port = int(getattr(_BOT_CONFIG, "WEB_PORT", 80) or 80)
    origins.add(f"http://localhost:{local_port}")
    origins.add(f"http://127.0.0.1:{local_port}")
    return sorted(origins)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "authorization",
        "content-type",
        "x-requested-with",
        "x-runtime-control-token",
    ],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)

if _STATIC_ROOT.exists():
    app.mount("/dashboard/static", DashboardStaticFiles(directory=str(_STATIC_ROOT)), name="dashboard_static")


def _extract_language_prefixed_path(raw_path: str) -> tuple[str | None, str]:
    path_value = str(raw_path or "").strip() or "/"
    if not path_value.startswith("/"):
        path_value = f"/{path_value}"
    parts = path_value.split("/", 2)
    if len(parts) < 2:
        return None, path_value
    lang = str(parts[1] or "").strip().lower()
    if lang not in _LANGUAGE_ROUTE_PREFIXES:
        return None, path_value
    if len(parts) < 3 or not str(parts[2] or "").strip():
        return lang, "/"
    return lang, f"/{parts[2]}"


def _extract_dashboard_guild_id(path: str) -> int | None:
    normalized = str(path or "").strip()
    if not normalized.startswith("/dashboard/guild/"):
        return None
    parts = normalized.split("/")
    if len(parts) < 4:
        return None
    guild_id_text = str(parts[3] or "").strip()
    if not guild_id_text.isdigit():
        return None
    return int(guild_id_text)


@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next):
    raw_path = str(getattr(getattr(request, "url", None), "path", "") or "") or "/"
    lang_prefix, canonical_path = _extract_language_prefixed_path(raw_path)
    active_lang_prefix = lang_prefix if lang_prefix in _LANGUAGE_ROUTE_PREFIXES else None
    if active_lang_prefix:
        # Keep /th/... and /en/... in browser URL while routing internally to canonical paths.
        request.scope["path"] = canonical_path
        setattr(request.state, "language_prefix", active_lang_prefix)
        raw_path = canonical_path

    path = raw_path.rstrip("/") or "/"
    if request.method in {"GET", "HEAD"}:
        redirect_target = _DASHBOARD_PUBLIC_REDIRECT_MAP.get(path)
        if redirect_target:
            if active_lang_prefix:
                redirect_target = f"/{active_lang_prefix}{redirect_target}"
            query = str(getattr(getattr(request, "url", None), "query", "") or "").strip()
            target = f"{redirect_target}?{query}" if query else redirect_target
            return RedirectResponse(url=target, status_code=303)

    response = await call_next(request)
    if active_lang_prefix:
        current_cookie_lang = str((request.cookies or {}).get(_LANGUAGE_COOKIE_KEY) or "").strip().lower()
        if current_cookie_lang != active_lang_prefix:
            response.set_cookie(
                key=_LANGUAGE_COOKIE_KEY,
                value=active_lang_prefix,
                path="/",
                max_age=_LANGUAGE_COOKIE_MAX_AGE_SECONDS,
                samesite="lax",
            )
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        updated_guild_id = _extract_dashboard_guild_id(path)
        if updated_guild_id is not None and int(getattr(response, "status_code", 500) or 500) < 500:
            invalidate_dashboard_context_cache(
                guild_id=updated_guild_id,
                include_manageable_guilds=(path.endswith("/access/mode")),
            )
    response = await _augment_json_error_response(request, response)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    request_scheme = str(getattr(getattr(request, "url", None), "scheme", "") or "").strip().lower()
    is_https = forwarded_proto == "https" or request_scheme == "https"
    if is_https:
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
    if path in {
        "/dashboard/static/dashboard/layout.js",
        "/dashboard/static/dashboard/layout-runtime.js",
        "/dashboard/static/dashboard/layout-unified.js",
    }:
        headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=86400"
        for existing_key in list(headers.keys()):
            lowered = str(existing_key or "").strip().lower()
            if lowered in {"pragma", "expires"}:
                try:
                    del headers[existing_key]
                except Exception:
                    pass
    return response


def _favicon_svg_path() -> Path:
    candidates = (
        _STATIC_ROOT / "favicon.svg",
        _STATIC_ROOT / "dashboard" / "favicon.svg",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _favicon_png_path() -> Path:
    candidates = (
        _STATIC_ROOT / "favicon.png",
        _STATIC_ROOT / "Favicon_SkylineBOT.png",
        _STATIC_ROOT / "dashboard" / "favicon.png",
        _STATIC_ROOT / "dashboard" / "Favicon_SkylineBOT.png",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _normalize_origin(raw_value: str) -> str | None:
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


def _is_local_origin(origin: str | None) -> bool:
    if not origin:
        return False
    try:
        host = str(urlparse(str(origin)).hostname or "").strip().lower()
    except Exception:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def _configured_public_origin() -> str | None:
    for raw_value in (
        str(os.getenv("PUBLIC_BASE_URL", "") or ""),
        str(getattr(_BOT_CONFIG, "DASHBOARD_BASE_URL", "") or ""),
        str(os.getenv("DASHBOARD_BASE_URL", "") or ""),
        _PUBLIC_CANONICAL_ORIGIN,
    ):
        configured = _normalize_origin(raw_value)
        if configured and _is_local_origin(configured) and raw_value != _PUBLIC_CANONICAL_ORIGIN:
            continue
        if configured:
            return configured.rstrip("/")
    return None


def _origin_from_request(request: Request) -> str | None:
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

    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    request_scheme = str(getattr(getattr(request, "url", None), "scheme", "") or "").strip().lower()
    scheme = forwarded_proto if forwarded_proto in {"http", "https"} else request_scheme
    if scheme not in {"http", "https"}:
        scheme = "http"
    return f"{scheme}://{raw_host}"


def _public_origin(request: Request) -> str:
    from_request = _origin_from_request(request)
    configured = _configured_public_origin()
    if configured:
        configured_host = str(urlparse(configured).netloc or "").lower()
        request_host = str(urlparse(from_request or "").netloc or "").lower()
        if configured_host == "skylinebot.xyz" or request_host in {"", configured_host, "www.skylinebot.xyz"}:
            return configured.rstrip("/")
    if from_request:
        return from_request.rstrip("/")
    if configured:
        return configured.rstrip("/")
    return f"http://localhost:{int(_BOT_CONFIG.WEB_PORT)}"


def _request_host_only(request: Request) -> str:
    raw_host = (
        str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
        or str(request.headers.get("host") or "").strip()
        or str(getattr(getattr(request, "url", None), "netloc", "") or "").strip()
    )
    if not raw_host:
        return ""
    host = raw_host.lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if host.startswith("[") and "]" in host:
        host = host[1:].split("]", 1)[0]
    elif ":" in host:
        host = host.split(":", 1)[0]
    return host.strip()


def _support_status_public_host() -> str:
    raw = str(os.getenv("SUPPORT_STATUS_PUBLIC_URL", "") or "").strip()
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"https://{raw}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return ""
    return str(parsed.hostname or "").strip().lower()


def _is_support_status_host_request(request: Request) -> bool:
    host = _request_host_only(request)
    if not host:
        return False
    configured = _support_status_public_host()
    if configured and host == configured:
        return True
    return host == "status.skylinebot.xyz"


def _safe_photo_slug(raw_slug: str) -> str:
    slug = str(raw_slug or "").strip().strip("/")
    if not slug:
        return ""
    if len(slug) > 120:
        return ""
    if any(ch in slug for ch in {"\\", "/", "\x00", "\r", "\n"}):
        return ""
    return slug


def _safe_external_photo_url(raw_url: str) -> str:
    url_value = str(raw_url or "").strip()
    if not url_value or len(url_value) > 2048:
        return ""
    try:
        parsed = urlparse(url_value)
    except Exception:
        return ""
    scheme = str(parsed.scheme or "").strip().lower()
    netloc = str(parsed.netloc or "").strip()
    if scheme not in {"http", "https"} or not netloc:
        return ""
    return url_value


def _blob_payload_to_bytes(raw_payload: object) -> bytes:
    if raw_payload is None:
        return b""
    if isinstance(raw_payload, bytes):
        return raw_payload
    if isinstance(raw_payload, bytearray):
        return bytes(raw_payload)
    if isinstance(raw_payload, memoryview):
        return raw_payload.tobytes()
    try:
        return bytes(raw_payload)
    except Exception:
        return b""


def _legacy_photo_local_path(asset: dict[str, object]) -> Path | None:
    guild_id = int(asset.get("guild_id") or 0)
    stored_filename = Path(str(asset.get("stored_filename") or "")).name
    if guild_id <= 0 or not stored_filename:
        return None
    return _PHOTO_UPLOAD_ROOT / str(guild_id) / stored_filename


def _guess_photo_media_type(asset: dict[str, object], *, fallback_name: str = "") -> str:
    media_type = str(asset.get("mime_type") or "").strip().lower()
    if media_type:
        return media_type
    guessed, _ = mimetypes.guess_type(str(fallback_name or ""))
    return str(guessed or "application/octet-stream")


def _photo_blob_response(payload: bytes, media_type: str) -> Response:
    return Response(
        content=payload,
        media_type=media_type or "application/octet-stream",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


async def _download_external_photo_payload(asset: dict[str, object]) -> tuple[bytes, str]:
    external_url = _safe_external_photo_url(str(asset.get("external_url") or ""))
    if not external_url:
        return b"", ""
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.get(external_url)
    except Exception:
        return b"", ""
    if int(response.status_code) >= 400:
        return b"", ""
    payload = bytes(response.content or b"")
    if not payload or len(payload) > _PHOTO_MONGODB_MIGRATION_MAX_BYTES:
        return b"", ""
    header_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    media_type = header_type if header_type else _guess_photo_media_type(asset, fallback_name=external_url)
    return payload, media_type


async def _load_legacy_local_photo_payload(asset: dict[str, object]) -> tuple[bytes, str]:
    target = _legacy_photo_local_path(asset)
    if target is None or not target.exists() or not target.is_file():
        return b"", ""
    try:
        payload = await asyncio.to_thread(target.read_bytes)
    except Exception:
        return b"", ""
    if not payload or len(payload) > _PHOTO_MONGODB_MIGRATION_MAX_BYTES:
        return b"", ""
    media_type = _guess_photo_media_type(asset, fallback_name=str(target))
    return payload, media_type


async def _upsert_photo_blob_document(
    *,
    asset_id: int,
    guild_id: int,
    payload: bytes,
    media_type: str,
) -> bool:
    if asset_id <= 0 or guild_id <= 0 or not payload:
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    existing = await photo_asset_blobs_db.get(asset_id=asset_id)
    if existing and existing.get("id"):
        updated = await photo_asset_blobs_db.update(
            id=int(existing["id"]),
            asset_id=asset_id,
            guild_id=guild_id,
            payload=payload,
            mime_type=str(media_type or "application/octet-stream")[:120],
            file_size=len(payload),
            updated_at=now,
        )
        return bool(updated)
    inserted = await photo_asset_blobs_db.insert(
        asset_id=asset_id,
        guild_id=guild_id,
        payload=payload,
        mime_type=str(media_type or "application/octet-stream")[:120],
        file_size=len(payload),
        created_at=now,
        updated_at=now,
    )
    return bool(inserted)


async def _migrate_photo_asset_to_mongodb(asset: dict[str, object]) -> tuple[dict[str, object], bytes, str] | None:
    asset_id = int(asset.get("id") or 0)
    guild_id = int(asset.get("guild_id") or 0)
    if asset_id <= 0 or guild_id <= 0:
        return None

    payload, media_type = await _load_legacy_local_photo_payload(asset)
    source = "local"
    if not payload:
        payload, media_type = await _download_external_photo_payload(asset)
        source = "external"
    if not payload:
        return None

    blob_ok = await _upsert_photo_blob_document(
        asset_id=asset_id,
        guild_id=guild_id,
        payload=payload,
        media_type=media_type,
    )
    if not blob_ok:
        return None

    updated = await photo_assets_db.update(
        id=asset_id,
        storage_backend="mongodb",
        external_url="",
        external_id="",
        storage_channel_id=0,
        storage_message_id=0,
        storage_guild_id=0,
        mime_type=str(media_type or "application/octet-stream")[:120],
        file_size=len(payload),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    if source == "local":
        legacy_path = _legacy_photo_local_path(asset)
        if legacy_path and legacy_path.exists() and legacy_path.is_file():
            try:
                legacy_path.unlink()
            except Exception:
                pass
    if not updated:
        return None
    return updated, payload, media_type


async def _serve_photo_asset(scope_guild_id: int, slug: str):
    safe_slug = _safe_photo_slug(slug)
    if not safe_slug:
        raise HTTPException(status_code=404, detail="photo not found")

    asset = await photo_assets_db.get(scope_guild_id=int(scope_guild_id), slug=safe_slug)
    if not asset:
        raise HTTPException(status_code=404, detail="photo not found")

    asset_id = int(asset.get("id") or 0)
    if asset_id > 0:
        blob = await photo_asset_blobs_db.get(asset_id=asset_id)
        if blob:
            payload = _blob_payload_to_bytes(blob.get("payload"))
            if payload:
                media_type = str(blob.get("mime_type") or asset.get("mime_type") or "").strip().lower()
                if not media_type:
                    media_type = _guess_photo_media_type(asset)
                return _photo_blob_response(payload, media_type)

    migrated = await _migrate_photo_asset_to_mongodb(asset)
    if migrated:
        _migrated_asset, payload, media_type = migrated
        return _photo_blob_response(payload, media_type)

    legacy_external_url = _safe_external_photo_url(str(asset.get("external_url") or ""))
    if legacy_external_url:
        return RedirectResponse(url=legacy_external_url, status_code=307)

    raise HTTPException(status_code=404, detail="photo not found")


def _build_robots_txt(origin: str) -> str:
    disallow_lines = tuple(f"Disallow: {path}" for path in _PRIVATE_ROBOTS_PATHS)
    return "\n".join(
        (
            "User-agent: Googlebot",
            "Allow: /",
            *disallow_lines,
            "",
            "User-agent: *",
            "Allow: /",
            *disallow_lines,
            "",
            f"Sitemap: {origin}/sitemap.xml",
            "",
        )
    )


def _build_sitemap_xml(origin: str) -> str:
    lastmod = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    urls = []
    for path in _PUBLIC_SITEMAP_PATHS:
        loc = f"{origin}{path}"
        urls.append(
            (
                "  <url>\n"
                f"    <loc>{loc}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                "    <changefreq>daily</changefreq>\n"
                "    <priority>0.8</priority>\n"
                "  </url>"
            )
        )
    joined_urls = "\n".join(urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{joined_urls}\n"
        "</urlset>\n"
    )


def _google_site_verification_token() -> str:
    raw = str(getattr(_BOT_CONFIG, "GOOGLE_SITE_VERIFICATION", "") or "").strip()
    if not raw:
        raw = str(os.getenv("GOOGLE_SITE_VERIFICATION", "") or "").strip()
    if raw.lower().startswith("google-site-verification="):
        raw = raw.split("=", 1)[1].strip()
    token = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    return token[:128]


def _adsense_publisher_id() -> str:
    explicit = str(getattr(_BOT_CONFIG, "GOOGLE_ADSENSE_PUBLISHER_ID", "") or "").strip()
    if not explicit:
        explicit = str(os.getenv("GOOGLE_ADSENSE_PUBLISHER_ID", "") or "").strip()
    if explicit:
        raw = explicit
    else:
        raw = str(getattr(_BOT_CONFIG, "GOOGLE_ADSENSE_CLIENT_ID", "") or "").strip()
        if not raw:
            raw = str(os.getenv("GOOGLE_ADSENSE_CLIENT_ID", "") or "").strip()
    raw = raw.strip()
    if raw.lower().startswith("ca-"):
        raw = raw[3:].strip()
    if raw and not raw.lower().startswith("pub-"):
        digits = "".join(ch for ch in raw if ch.isdigit())
        raw = f"pub-{digits}" if digits else ""
    token = "".join(ch for ch in raw if ch.isdigit() or ch == "-")
    if token and not token.startswith("pub-"):
        token = f"pub-{token}"
    return token[:64]


def _google_ads_txt_lines() -> list[str]:
    raw_custom = str(getattr(_BOT_CONFIG, "GOOGLE_ADS_TXT_LINES", "") or "").strip()
    if not raw_custom:
        raw_custom = str(os.getenv("GOOGLE_ADS_TXT_LINES", "") or "").strip()
    if raw_custom:
        normalized = raw_custom.replace("\\n", "\n")
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        return lines[:20]

    publisher_id = _adsense_publisher_id() or "pub-7880329046774106"
    return [f"google.com, {publisher_id}, DIRECT, f08c47fec0942fa0"]


def _google_site_verification_txt_line() -> str:
    token = _google_site_verification_token()
    if not token:
        return ""
    return f"google-site-verification={token}"


def _discord_interactions_public_key_hex() -> str:
    return str(getattr(_BOT_CONFIG, "DISCORD_APPLICATION_PUBLIC_KEY", "") or "").strip()


def _pynacl_available() -> bool:
    try:
        import nacl.signing  # type: ignore
    except Exception:
        return False
    return True


def _verify_discord_interaction_signature(
    *,
    public_key_hex: str,
    timestamp: str,
    signature_hex: str,
    body: bytes,
) -> bool:
    key_hex = str(public_key_hex or "").strip().lower()
    ts = str(timestamp or "").strip()
    sig_hex = str(signature_hex or "").strip().lower()
    if not key_hex or not ts or not sig_hex:
        return False
    try:
        signature = bytes.fromhex(sig_hex)
        verify_key_bytes = bytes.fromhex(key_hex)
    except ValueError:
        return False
    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey
    except Exception as exc:
        raise RuntimeError("PyNaCl is required for Discord interaction signature verification") from exc
    try:
        VerifyKey(verify_key_bytes).verify(ts.encode("utf-8") + body, signature)
    except (BadSignatureError, ValueError):
        return False
    return True


def _discord_interactions_transport_mode() -> str:
    raw = str(os.getenv("DISCORD_INTERACTIONS_TRANSPORT", "") or "").strip().lower()
    if raw in {"http", "webhook", "endpoint", "interactions"}:
        return "http"
    return "gateway"


def _discord_interaction_dispatch_target() -> tuple[object | None, str]:
    runtime_bot = get_bot()
    if runtime_bot is None:
        return None, "bot_unavailable"

    is_ready = getattr(runtime_bot, "is_ready", None)
    if callable(is_ready):
        try:
            if not bool(is_ready()):
                return None, "bot_not_ready"
        except Exception:
            return None, "bot_not_ready"

    is_closed = getattr(runtime_bot, "is_closed", None)
    if callable(is_closed):
        try:
            if bool(is_closed()):
                return None, "bot_closed"
        except Exception:
            return None, "bot_closed"

    connection = getattr(runtime_bot, "_connection", None)
    parser = getattr(connection, "parse_interaction_create", None) if connection is not None else None
    if not callable(parser):
        return None, "bot_not_bound"
    return runtime_bot, "ok"


def _dispatch_discord_interaction(payload: dict) -> tuple[bool, str]:
    runtime_bot, reason = _discord_interaction_dispatch_target()
    if runtime_bot is None:
        return False, reason

    connection = getattr(runtime_bot, "_connection", None)
    parser = getattr(connection, "parse_interaction_create", None) if connection is not None else None
    if not callable(parser):
        return False, "bot_not_bound"

    try:
        parser(payload)
    except Exception as exc:
        _LOG.error("Interactions endpoint dispatch failed: %s", exc)
        return False, "dispatch_failed"
    return True, "ok"


def _interaction_inline_unavailable_response(interaction_type: int, reason: str) -> Response:
    reason_text = str(reason or "unknown").strip().lower()
    message = (
        "SkylineBOT Interaction Endpoint is reachable, but command runtime is unavailable right now "
        f"(reason: {reason_text}). "
        "If your bot runs in Gateway mode, remove Interaction Endpoint URL in Discord Developer Portal. "
        "If you need HTTP interactions, run Discord + Web in the same process."
    )

    if interaction_type == 4:
        return JSONResponse({"type": 8, "data": {"choices": []}})

    if interaction_type in {2, 3, 5}:
        return JSONResponse({"type": 4, "data": {"content": message, "flags": 64}})

    return Response(status_code=202)


def _request_prefers_html(request: Request) -> bool:
    accept = str(request.headers.get("accept") or "").strip().lower()
    if "text/html" in accept or "application/xhtml+xml" in accept:
        return True
    if not accept:
        return request.method in {"GET", "HEAD"}
    return False


def _request_prefers_json_error(request: Request) -> bool:
    path = str(getattr(getattr(request, "url", None), "path", "") or "").strip().lower()
    accept = str(request.headers.get("accept") or "").strip().lower()
    requested_with = str(request.headers.get("x-requested-with") or "").strip().lower()
    if path.startswith("/api/"):
        return True
    if requested_with == "xmlhttprequest":
        return True
    if "application/problem+json" in accept and "text/html" not in accept:
        return True
    if "application/json" in accept and "text/html" not in accept:
        return True
    if request.method not in {"GET", "HEAD"} and not _request_prefers_html(request):
        return True
    return False


def _normalize_error_key(raw_value: object) -> str:
    text = str(raw_value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _fallback_error_code(status_code: int) -> str:
    if status_code in _WEB_ERROR_CODE_BY_STATUS:
        return str(_WEB_ERROR_CODE_BY_STATUS[status_code])
    if 400 <= status_code <= 499:
        return "WEB-REQUEST-4XX"
    if status_code >= 500:
        return "WEB-SERVER-5XX"
    return "WEB-UNKNOWN"


def _web_error_code(
    *,
    status_code: int,
    error_value: object = "",
    detail_text: object = "",
) -> str:
    error_key = _normalize_error_key(error_value)
    detail_key = _normalize_error_key(detail_text)
    if error_key and error_key in _WEB_ERROR_CODE_BY_KEY:
        return str(_WEB_ERROR_CODE_BY_KEY[error_key])
    if detail_key and detail_key in _WEB_ERROR_CODE_BY_KEY:
        return str(_WEB_ERROR_CODE_BY_KEY[detail_key])
    return _fallback_error_code(status_code)


def _web_error_docs_url(request: Request | None, error_code: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(error_code or "web-unknown").strip().lower()).strip("-")
    suffix = f"#{slug}" if slug else ""
    if request is None:
        return f"{_ERROR_CODE_DOCS_API_PATH}{suffix}"
    origin = _public_origin(request).rstrip("/")
    return f"{origin}{_ERROR_CODE_DOCS_API_PATH}{suffix}"


def _default_error_hint(owner: str, status_code: int) -> str:
    if owner == "user":
        if status_code == 401:
            return "ยืนยันตัวตนใหม่และลองทำรายการอีกครั้ง"
        if status_code == 403:
            return "ตรวจสิทธิ์ของบัญชีหรือสิทธิ์ในเซิร์ฟเวอร์ก่อนใช้งาน"
        if status_code == 404:
            return "ตรวจ URL หรือ resource id ให้ถูกต้อง"
        return "ตรวจข้อมูลที่ส่งเข้า endpoint ให้ตรงรูปแบบที่กำหนดใน docs"
    if status_code == 503:
        return "ตรวจสถานะระบบหลักและ dependency ว่าพร้อมใช้งาน"
    return "ตรวจ log ฝั่งเซิร์ฟเวอร์เพื่อหา root cause และแก้ไข"


def _web_error_metadata(
    *,
    request: Request | None,
    status_code: int,
    error_value: object = "",
    detail_text: object = "",
    forced_code: str = "",
) -> dict[str, str | int]:
    normalized_forced_code = str(forced_code or "").strip().upper()
    if normalized_forced_code:
        code = normalized_forced_code
    else:
        code = _web_error_code(
            status_code=status_code,
            error_value=error_value,
            detail_text=detail_text,
        )
    record = dict(_WEB_ERROR_REFERENCE.get(code) or {})
    owner = str(record.get("owner") or ("developer" if status_code >= 500 else "user")).strip().lower()
    category = str(record.get("category") or ("server" if status_code >= 500 else "request")).strip().lower()
    hint = str(record.get("hint") or _default_error_hint(owner, status_code)).strip()
    summary = str(record.get("summary") or "").strip()
    if not summary:
        summary = _error_message(int(status_code or 500), str(detail_text or ""))
    return {
        "error_code": code,
        "error_owner": owner,
        "error_category": category,
        "error_summary": summary,
        "error_hint": hint,
        "error_docs": _web_error_docs_url(request, code),
        "http_status": int(status_code or 500),
    }


def _decorate_error_payload(
    *,
    request: Request | None,
    payload: dict,
    status_code: int,
    error_value: object = "",
    detail_text: object = "",
) -> tuple[dict, dict[str, str | int]]:
    normalized_payload = dict(payload or {})
    payload_forced_code = str(normalized_payload.get("error_code") or "").strip().upper()
    payload_error_value = error_value
    if not str(payload_error_value or "").strip():
        payload_error_value = normalized_payload.get("error") or normalized_payload.get("code") or ""

    payload_detail = detail_text
    if not str(payload_detail or "").strip():
        payload_detail = (
            normalized_payload.get("detail")
            or normalized_payload.get("message")
            or normalized_payload.get("description")
            or ""
        )

    metadata = _web_error_metadata(
        request=request,
        status_code=status_code,
        error_value=payload_error_value,
        detail_text=payload_detail,
        forced_code=payload_forced_code,
    )
    normalized_payload.setdefault("error_code", metadata["error_code"])
    normalized_payload.setdefault("error_owner", metadata["error_owner"])
    normalized_payload.setdefault("error_category", metadata["error_category"])
    normalized_payload.setdefault("error_docs", metadata["error_docs"])
    normalized_payload.setdefault("error_hint", metadata["error_hint"])
    if int(status_code or 0) >= 400:
        normalized_payload.setdefault("ok", False)
    return normalized_payload, metadata


def _set_header_case_insensitive(headers: dict[str, str], key: str, value: str) -> None:
    target_key = str(key or "").strip()
    if not target_key:
        return
    lower_target = target_key.lower()
    for existing_key in list(headers.keys()):
        if str(existing_key).strip().lower() == lower_target:
            headers.pop(existing_key, None)
    headers[target_key] = str(value)


def _json_error_response(
    request: Request | None,
    *,
    status_code: int,
    payload: dict,
    headers: dict[str, str] | None = None,
    error_value: object = "",
    detail_text: object = "",
) -> JSONResponse:
    content, metadata = _decorate_error_payload(
        request=request,
        payload=payload,
        status_code=status_code,
        error_value=error_value,
        detail_text=detail_text,
    )
    final_headers = dict(headers or {})
    final_headers.pop("content-length", None)
    final_headers.pop("Content-Length", None)
    _set_header_case_insensitive(
        final_headers,
        "X-Skyline-Error-Code",
        str(metadata["error_code"]),
    )
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=final_headers,
    )


def _rebuild_response_with_body(response: Response, body: bytes) -> Response:
    headers = dict(response.headers)
    headers.pop("content-length", None)
    headers.pop("Content-Length", None)
    return Response(
        content=body,
        status_code=int(getattr(response, "status_code", 200) or 200),
        headers=headers,
        media_type=getattr(response, "media_type", None),
        background=getattr(response, "background", None),
    )


async def _augment_json_error_response(request: Request, response: Response) -> Response:
    status_code = int(getattr(response, "status_code", 200) or 200)
    if status_code < 400:
        return response

    content_type = str(response.headers.get("content-type") or "").strip().lower()
    if "application/json" not in content_type and "application/problem+json" not in content_type:
        return response

    try:
        if isinstance(response, JSONResponse):
            raw_body = bytes(getattr(response, "body", b"") or b"")
        else:
            body_iterator = getattr(response, "body_iterator", None)
            if body_iterator is None:
                raw_body = bytes(getattr(response, "body", b"") or b"")
            else:
                chunks: list[bytes] = []
                async for chunk in body_iterator:
                    if isinstance(chunk, (bytes, bytearray)):
                        chunks.append(bytes(chunk))
                    elif isinstance(chunk, str):
                        chunks.append(chunk.encode("utf-8", errors="ignore"))
                    elif chunk is None:
                        continue
                    else:
                        chunks.append(str(chunk).encode("utf-8", errors="ignore"))
                raw_body = b"".join(chunks)
    except Exception as error:
        _LOG.debug("Unable to inspect JSON error response body: %s", error)
        return response

    if not raw_body:
        return response

    try:
        parsed_payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        if isinstance(response, JSONResponse):
            return response
        return _rebuild_response_with_body(response, raw_body)

    if not isinstance(parsed_payload, dict):
        if isinstance(response, JSONResponse):
            return response
        return _rebuild_response_with_body(response, raw_body)

    decorated_payload, metadata = _decorate_error_payload(
        request=request,
        payload=parsed_payload,
        status_code=status_code,
    )
    headers = dict(response.headers)
    headers.pop("content-length", None)
    headers.pop("Content-Length", None)
    _set_header_case_insensitive(
        headers,
        "X-Skyline-Error-Code",
        str(metadata["error_code"]),
    )
    return JSONResponse(
        content=decorated_payload,
        status_code=status_code,
        headers=headers,
        background=getattr(response, "background", None),
    )


def _error_title(status_code: int) -> str:
    if status_code == 404:
        return "404 | Page Not Found"
    if 500 <= status_code <= 599:
        return f"{status_code} | Server Error"
    if 400 <= status_code <= 499:
        return f"{status_code} | Request Error"
    return f"{status_code} | Error"


def _error_message(status_code: int, detail_text: str) -> str:
    if status_code == 404:
        return "ไม่พบหน้าที่คุณต้องการ ลองตรวจสอบ URL หรือกลับไปหน้าแรกของเว็บไซต์"
    if status_code == 403:
        return "คุณไม่มีสิทธิ์เข้าถึงหน้านี้"
    if status_code == 401:
        return "ต้องยืนยันตัวตนก่อนเข้าใช้งานหน้านี้"
    if status_code == 405:
        return "วิธีการเรียกใช้งาน URL นี้ไม่ถูกต้อง (Method Not Allowed)"
    if status_code == 422:
        return "ข้อมูลที่ส่งมาไม่ถูกต้อง หรือไม่ครบถ้วน"
    if 500 <= status_code <= 599:
        return "เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่อีกครั้งในภายหลัง"
    if detail_text:
        return detail_text
    return "เกิดข้อผิดพลาดในการเรียกหน้าเว็บนี้"


def _normalize_error_detail(raw_detail: object) -> str:
    if raw_detail is None:
        return ""
    if isinstance(raw_detail, str):
        return raw_detail.strip()
    try:
        return json.dumps(raw_detail, ensure_ascii=False)
    except Exception:
        return str(raw_detail).strip()


def _render_error_page(
    request: Request,
    *,
    status_code: int,
    detail_text: str = "",
    error_code: str = "",
    error_owner: str = "",
    error_hint: str = "",
    error_docs: str = "",
) -> HTMLResponse:
    safe_status = int(status_code or 500)
    safe_detail = (detail_text or "").strip()
    title = _error_title(safe_status)
    subtitle = _error_message(safe_status, safe_detail)
    app_name = str(getattr(_BOT_CONFIG, "NAME", "") or "SkylineBOT").strip() or "SkylineBOT"
    current_path = str(getattr(getattr(request, "url", None), "path", "") or "/").strip() or "/"
    origin = _public_origin(request)
    dashboard_url = f"{origin}/dashboard"
    status_color = "#ffd38f" if safe_status >= 500 else "#9ed8ff"
    owner_label_map = {
        "user": "User action required",
        "developer": "Developer/system action required",
    }
    owner_text = owner_label_map.get(str(error_owner or "").strip().lower(), "Unknown")
    error_meta_rows: list[str] = []
    if str(error_code or "").strip():
        error_meta_rows.append(
            f"<strong>Error code:</strong> {html.escape(str(error_code).strip(), quote=True)}"
        )
    if str(error_owner or "").strip():
        error_meta_rows.append(
            f"<strong>Owner:</strong> {html.escape(owner_text, quote=True)}"
        )
    if str(error_hint or "").strip():
        error_meta_rows.append(
            f"<strong>Hint:</strong> {html.escape(str(error_hint).strip(), quote=True)}"
        )
    if str(error_docs or "").strip():
        safe_docs_url = html.escape(str(error_docs).strip(), quote=True)
        error_meta_rows.append(
            f'<strong>Docs:</strong> <a class="meta-link" href="{safe_docs_url}" target="_blank" rel="noopener">{safe_docs_url}</a>'
        )
    error_meta_html = ("<br>" + "<br>".join(error_meta_rows)) if error_meta_rows else ""

    html_body = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title, quote=True)} - {html.escape(app_name, quote=True)}</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <style>
    :root {{
      --bg-1: #060d1f;
      --bg-2: #101a35;
      --line: rgba(141, 181, 255, 0.28);
      --text: #e8f1ff;
      --muted: #a9bedf;
      --accent: {status_color};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 18px;
      font-family: "Outfit", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 4%, rgba(86, 153, 255, 0.25), transparent 34%),
        radial-gradient(circle at 90% 8%, rgba(61, 201, 224, 0.22), transparent 32%),
        linear-gradient(160deg, var(--bg-1) 0%, var(--bg-2) 52%, #0a1229 100%);
    }}
    .shell {{
      width: min(760px, 100%);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      background: rgba(9, 16, 33, 0.88);
      box-shadow: 0 18px 52px rgba(0, 0, 0, 0.48);
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 7px 11px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: var(--accent);
      font-weight: 800;
      margin-bottom: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(1.28rem, 2.2vw, 1.72rem);
      letter-spacing: -0.01em;
    }}
    p {{
      margin: 10px 0 0;
      color: var(--muted);
      line-height: 1.65;
    }}
    .meta {{
      margin-top: 16px;
      padding: 11px;
      border-radius: 12px;
      border: 1px dashed var(--line);
      background: rgba(16, 27, 50, 0.64);
      color: #c9dcff;
      font-size: 0.95rem;
      word-break: break-all;
    }}
    .meta-link {{
      color: #a9d6ff;
      text-decoration: underline;
    }}
    .actions {{
      margin-top: 16px;
      display: grid;
      gap: 9px;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      border-radius: 12px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid rgba(145, 184, 255, 0.46);
      color: #e5f2ff;
      background: rgba(18, 35, 63, 0.82);
    }}
    .btn.primary {{
      color: #051021;
      background: linear-gradient(135deg, #59a0ff, #43d0ea);
      border-color: rgba(124, 202, 255, 0.65);
    }}
  </style>
</head>
<body>
  <main class="shell">
    <span class="status">HTTP {safe_status}</span>
    <h1>{html.escape(title, quote=True)}</h1>
    <p>{html.escape(subtitle, quote=True)}</p>
    <div class="meta">
      <strong>Path:</strong> {html.escape(current_path, quote=True)}<br>
      <strong>Service:</strong> {html.escape(app_name, quote=True)}
      {error_meta_html}
    </div>
    <div class="actions">
      <a class="btn primary" href="/">กลับหน้าแรก</a>
      <a class="btn" href="{html.escape(dashboard_url, quote=True)}">ไปที่ Dashboard</a>
    </div>
  </main>
</body>
</html>
"""
    return HTMLResponse(content=html_body, status_code=safe_status)


@app.exception_handler(StarletteHTTPException)
async def _http_exception_html_handler(request: Request, exc: StarletteHTTPException):
    status_code = int(getattr(exc, "status_code", 500) or 500)
    detail = _normalize_error_detail(getattr(exc, "detail", ""))
    if _request_prefers_json_error(request):
        payload = {"detail": detail or "Error"}
        return _json_error_response(
            request,
            status_code=status_code,
            headers=dict(getattr(exc, "headers", None) or {}),
            payload=payload,
            detail_text=detail,
        )
    metadata = _web_error_metadata(
        request=request,
        status_code=status_code,
        detail_text=detail,
    )
    response = _render_error_page(
        request,
        status_code=status_code,
        detail_text=detail,
        error_code=str(metadata["error_code"]),
        error_owner=str(metadata["error_owner"]),
        error_hint=str(metadata["error_hint"]),
        error_docs=str(metadata["error_docs"]),
    )
    if getattr(exc, "headers", None):
        for key, value in dict(exc.headers).items():
            response.headers.setdefault(str(key), str(value))
    return response


@app.exception_handler(RequestValidationError)
async def _request_validation_html_handler(request: Request, exc: RequestValidationError):
    if _request_prefers_json_error(request):
        return _json_error_response(
            request,
            status_code=422,
            payload={"detail": exc.errors()},
            detail_text="Invalid request data",
            error_value="validation_error",
        )
    metadata = _web_error_metadata(
        request=request,
        status_code=422,
        error_value="validation_error",
        detail_text="Invalid request data",
    )
    return _render_error_page(
        request,
        status_code=422,
        detail_text="Invalid request data",
        error_code=str(metadata["error_code"]),
        error_owner=str(metadata["error_owner"]),
        error_hint=str(metadata["error_hint"]),
        error_docs=str(metadata["error_docs"]),
    )


@app.exception_handler(Exception)
async def _unhandled_exception_html_handler(request: Request, exc: Exception):
    _LOG.exception("Unhandled surface exception at %s", request.url.path, exc_info=exc)
    if _request_prefers_json_error(request):
        return _json_error_response(
            request,
            status_code=500,
            payload={"detail": "Internal Server Error"},
            error_value=type(exc).__name__,
            detail_text="Internal Server Error",
        )
    metadata = _web_error_metadata(
        request=request,
        status_code=500,
        error_value=type(exc).__name__,
        detail_text="Internal Server Error",
    )
    return _render_error_page(
        request,
        status_code=500,
        detail_text="Internal Server Error",
        error_code=str(metadata["error_code"]),
        error_owner=str(metadata["error_owner"]),
        error_hint=str(metadata["error_hint"]),
        error_docs=str(metadata["error_docs"]),
    )


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt(request: Request):
    origin = _public_origin(request)
    return Response(
        _build_robots_txt(origin),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(request: Request):
    origin = _public_origin(request)
    return Response(
        _build_sitemap_xml(origin),
        media_type="application/xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/ads.txt", include_in_schema=False)
async def ads_txt():
    lines = _google_ads_txt_lines()
    if not lines:
        raise HTTPException(status_code=404, detail="ads.txt is not configured")
    body = "\n".join(lines).strip() + "\n"
    return Response(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/google-site-verification.txt", include_in_schema=False)
async def google_site_verification_txt():
    line = _google_site_verification_txt_line()
    if not line:
        raise HTTPException(status_code=404, detail="Google site verification token is not configured")
    return Response(f"{line}\n", media_type="text/plain; charset=utf-8")


@app.get("/google{token}.html", include_in_schema=False)
async def google_site_verification_html(token: str):
    expected = _google_site_verification_token()
    if not expected or token != expected:
        raise HTTPException(status_code=404, detail="Verification file not found")
    filename = f"google{expected}.html"
    body = f"google-site-verification: {filename}\n"
    return Response(body, media_type="text/html; charset=utf-8")


@app.get("/dashboard/robots.txt", include_in_schema=False)
async def dashboard_robots_txt(request: Request):
    origin = _public_origin(request)
    return Response(
        _build_robots_txt(origin),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/favicon.svg", include_in_schema=False)
async def favicon_svg():
    icon_path = _favicon_svg_path()
    if not icon_path.exists():
        png_path = _favicon_png_path()
        if png_path.exists():
            return RedirectResponse(url="/favicon.png", status_code=307)
        raise HTTPException(status_code=404, detail="favicon.svg not found")
    return Response(
        icon_path.read_text(encoding="utf-8"),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=604800"},
    )


@app.get("/favicon.png", include_in_schema=False)
async def favicon_png():
    icon_path = _favicon_png_path()
    if not icon_path.exists():
        svg_path = _favicon_svg_path()
        if svg_path.exists():
            return RedirectResponse(url="/favicon.svg", status_code=307)
        raise HTTPException(status_code=404, detail="favicon.png not found")
    return Response(
        icon_path.read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=604800"},
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    png_path = _favicon_png_path()
    if png_path.exists():
        return Response(
            png_path.read_bytes(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=604800"},
        )
    svg_path = _favicon_svg_path()
    if svg_path.exists():
        return Response(
            svg_path.read_text(encoding="utf-8"),
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=604800"},
        )
    raise HTTPException(status_code=404, detail="favicon not found")


@app.get("/")
async def root(request: Request):
    if _is_support_status_host_request(request):
        return RedirectResponse(url="/status?view=service", status_code=303)
    return await dashboard_landing_home(request)


@app.head("/", include_in_schema=False)
async def root_head(request: Request):
    return await root(request)


@app.get("/index")
async def index(request: Request):
    if _is_support_status_host_request(request):
        return RedirectResponse(url="/status?view=service", status_code=303)
    return RedirectResponse(url="/", status_code=301)


@app.head("/index", include_in_schema=False)
async def index_head(request: Request):
    return await index(request)


@app.get("/index.html", include_in_schema=False)
async def index_html(request: Request):
    return await index(request)


@app.head("/index.html", include_in_schema=False)
async def index_html_head(request: Request):
    return await index(request)


@app.get("/photo/{slug}")
async def photo_root(slug: str):
    return await _serve_photo_asset(0, slug)


@app.get("/{guild_id}/photo/{slug}")
async def photo_by_guild(guild_id: int, slug: str):
    scope_guild_id = int(style_urls.photo_scope_guild_id(guild_id))
    return await _serve_photo_asset(scope_guild_id, slug)


@app.get("/commands")
async def commands_root(request: Request):
    return await dashboard_commands_help_page(request)


@app.get("/commands-help")
async def commands_help_root(request: Request):
    query = str(getattr(request.url, "query", "") or "").strip()
    if query:
        return RedirectResponse(url=f"/commands?{query}", status_code=303)
    return RedirectResponse(url="/commands", status_code=303)


@app.get("/leaderboard")
async def leaderboard_root(request: Request):
    return await dashboard_leaderboard_page(request)


@app.get("/promotehistory")
async def promote_history_root(request: Request):
    return await dashboard_promote_history_page(request)


@app.post("/promotehistory/action")
async def promote_history_action(request: Request):
    return await dashboard_promote_history_action(request)


@app.get("/promoteserver")
async def promote_server_root(request: Request):
    return await dashboard_promote_server_page(request)


@app.get("/tags")
async def tags_root(request: Request):
    return await dashboard_tags_page(request)


@app.get("/invite")
async def invite_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    return await dashboard_invite_hub(request, notice=notice)


@app.get("/invitebot")
async def invitebot_root(request: Request):
    auto_value = str(request.query_params.get("auto") or "").strip().lower()
    auto_redirect = auto_value in {"1", "true", "yes", "on"}
    guild_id = str(request.query_params.get("guild_id") or "").strip()
    if auto_redirect or guild_id.isdigit():
        query = str(getattr(request.url, "query", "") or "").strip()
        target = f"/invite?{query}" if query else "/invite?auto=1"
        return RedirectResponse(url=target, status_code=303)
    return await dashboard_invitebot_page(request)


@app.get("/donate")
async def donate_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    verify_status = str(request.query_params.get("verify_status") or "").strip() or None
    return await dashboard_donate_page(request, notice=notice, verify_status=verify_status)


@app.get("/donate/{guild_id}")
async def donate_guild_root(request: Request, guild_id: str):
    guild_id_value = str(guild_id or "").strip()
    if not guild_id_value.isdigit():
        return RedirectResponse(url="/donate", status_code=303)
    query = str(getattr(request.url, "query", "") or "").strip()
    target = f"/dashboard/donate/{guild_id_value}"
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(url=target, status_code=303)


@app.get("/donatebot")
async def donatebot_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    verify_status = str(request.query_params.get("verify_status") or "").strip() or None
    return await dashboard_donatebot_hub(request, notice=notice, verify_status=verify_status)


@app.get("/wallet")
async def wallet_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    return await dashboard_wallet_page(request, notice=notice)


@app.get("/donate-wallet")
async def donate_wallet_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    return await dashboard_donate_wallet_page(request, notice=notice)


@app.get("/interactions-endpoint")
async def interactions_endpoint_root(request: Request):
    return await dashboard_interactions_endpoint_page(request)


@app.get("/linked-role-verify")
async def linked_role_verify_root(request: Request):
    return await dashboard_linked_role_verify_page(request)


@app.get("/status")
async def status_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    return await dashboard_system_status(request, notice=notice)


@app.get("/premium")
async def premium_root(request: Request):
    return await dashboard_premium_page(request)


@app.get("/subscribe-plan")
async def subscribe_plan_root(request: Request):
    return await dashboard_subscribe_plan_page(request)


@app.get("/redeem")
async def redeem_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    return await dashboard_redeem_page(request, notice=notice)


@app.post("/redeem")
async def redeem_submit_root(request: Request):
    return await dashboard_redeem_submit(request)


@app.get("/docs")
async def docs_root(request: Request):
    return await dashboard_docs_page(request)


@app.get("/support")
async def support_root(request: Request):
    return await dashboard_support_page(request)


@app.get("/serversupport")
@app.get("/ServerSupport")
@app.get("/server-support")
async def server_support_root(request: Request):
    return await dashboard_server_support_page(request)


@app.get("/rule")
async def rule_root(request: Request):
    return await dashboard_rule_page(request)


@app.get("/rule/bot")
async def rule_bot_root(request: Request):
    return await dashboard_rule_bot_page(request)


@app.get("/rule/serversupport")
async def rule_server_support_root(request: Request):
    return await dashboard_rule_server_support_page(request)


def _can_access_internal_api_docs(request: Request) -> bool:
    session = _session_from_request(request)
    return bool(_is_dashboard_admin(session))


@app.get("/api/docs", include_in_schema=False)
@app.get("/api/docs/", include_in_schema=False)
async def api_docs_admin_only(request: Request):
    if not _can_access_internal_api_docs(request):
        return RedirectResponse("/docs", status_code=303)
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title="เอกสาร API ภายใน SkylineBOT",
    )


@app.get("/api/redoc", include_in_schema=False)
@app.get("/api/redoc/", include_in_schema=False)
async def api_redoc_admin_only(request: Request):
    if not _can_access_internal_api_docs(request):
        return RedirectResponse("/docs", status_code=303)
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title="เอกสาร API ภายใน SkylineBOT",
    )


@app.get("/api/openapi.json", include_in_schema=False)
@app.get("/api/openapi.json/", include_in_schema=False)
async def api_openapi_admin_only(request: Request):
    if not _can_access_internal_api_docs(request):
        return RedirectResponse("/docs", status_code=303)
    return JSONResponse(app.openapi())


@app.get("/personalizer")
async def personalizer_root(request: Request):
    return await dashboard_personalizer_page(request)


@app.get("/api/personalizer/preview")
async def personalizer_preview_root(request: Request):
    return await dashboard_personalizer_preview(request)


@app.get("/terms-of-service")
async def terms_of_service_root(request: Request):
    return await dashboard_terms_of_service_page(request)


@app.get("/terms")
async def terms_root(request: Request):
    return await dashboard_terms_page(request)


@app.get("/privacy-policy")
async def privacy_policy_root(request: Request):
    return await dashboard_privacy_policy_page(request)


@app.get("/privacy")
async def privacy_root(request: Request):
    return await dashboard_privacy_page(request)


@app.get("/careers")
async def careers_root(request: Request):
    return await dashboard_careers_page(request)


@app.get("/plugins/moderation")
async def plugins_moderation_root(request: Request):
    return await dashboard_plugins_moderation_page(request)


@app.get("/plugins/utilities")
async def plugins_utilities_root(request: Request):
    return await dashboard_plugins_utilities_page(request)


@app.get("/plugins/social-alerts")
async def plugins_social_alerts_root(request: Request):
    return await dashboard_plugins_social_alerts_page(request)


@app.get("/plugins/games-fun")
async def plugins_games_fun_root(request: Request):
    return await dashboard_plugins_games_fun_page(request)


@app.get("/contact")
async def contact_root(request: Request):
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


@app.get("/contact/realtime/threads")
async def contact_realtime_threads_root(request: Request):
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


@app.get("/contact/realtime/thread/{thread_key}/messages")
async def contact_realtime_messages_root(request: Request, thread_key: str):
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


@app.post("/contact/thread/create")
async def contact_thread_create_root(request: Request):
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


@app.post("/contact/thread/{thread_key}/message")
async def contact_thread_message_root(request: Request, thread_key: str):
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


@app.post("/contact/thread/{thread_key}/toggle")
async def contact_thread_toggle_root(request: Request, thread_key: str):
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


@app.post("/contact/message/{message_id}/delete")
async def contact_message_delete_root(request: Request, message_id: int):
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


@app.get("/report")
async def report_root(request: Request):
    notice = str(request.query_params.get("notice") or "").strip() or None
    return await dashboard_report_page(request, notice=notice)


@app.post("/report")
async def report_submit_root(request: Request):
    return await dashboard_report_submit(request)


@app.get("/guides/ticket")
async def guide_ticket_root(request: Request):
    return await dashboard_guide_ticket_page(request)


@app.get("/guides/security")
async def guide_security_root(request: Request):
    return await dashboard_guide_security_page(request)


@app.get("/guides/giveaways")
async def guide_giveaways_root(request: Request):
    return await dashboard_guide_giveaways_page(request)


@app.post("/runtime/control", include_in_schema=False)
async def runtime_control_root(request: Request):
    return await dashboard_runtime_control(request)


@app.get("/runtime/control", include_in_schema=False)
async def runtime_control_root_get(request: Request):
    return await dashboard_runtime_control(request)


@app.get(_ERROR_CODE_DOCS_API_PATH)
async def error_codes_root(request: Request):
    def _wants_html() -> bool:
        format_value = str(request.query_params.get("format") or "").strip().lower()
        if format_value in {"json", "raw"}:
            return False
        if format_value in {"html", "web", "page"}:
            return True
        accept = str(request.headers.get("accept") or "").strip().lower()
        if "text/html" in accept or "application/xhtml+xml" in accept:
            return True
        return False

    origin = _public_origin(request).rstrip("/")
    docs_page = f"{origin}{_ERROR_CODE_DOCS_WEB_PATH}"
    rows: list[dict[str, str | int]] = []
    for code in sorted(_WEB_ERROR_REFERENCE.keys()):
        record = dict(_WEB_ERROR_REFERENCE.get(code) or {})
        status_value = int(record.get("status") or 0)
        slug = re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-")
        rows.append(
            {
                "code": code,
                "status": status_value,
                "owner": str(record.get("owner") or "").strip(),
                "category": str(record.get("category") or "").strip(),
                "summary": str(record.get("summary") or "").strip(),
                "hint": str(record.get("hint") or "").strip(),
                "docs": f"{origin}{_ERROR_CODE_DOCS_API_PATH}#{slug}" if slug else f"{origin}{_ERROR_CODE_DOCS_API_PATH}",
                "slug": slug,
            }
        )
    payload = {
        "ok": True,
        "error_codes": rows,
        "docs_page": docs_page,
        "count": len(rows),
    }

    if not _wants_html():
        return JSONResponse(payload)

    owner_counts: dict[str, int] = {}
    for row in rows:
        owner_key = str(row.get("owner") or "unknown").strip().lower() or "unknown"
        owner_counts[owner_key] = int(owner_counts.get(owner_key, 0)) + 1
    owner_user_count = int(owner_counts.get("user", 0))
    owner_dev_count = int(owner_counts.get("developer", 0))
    app_name = str(getattr(_BOT_CONFIG, "NAME", "") or "SkylineBOT").strip() or "SkylineBOT"
    table_rows: list[str] = []
    for row in rows:
        code = str(row.get("code") or "").strip()
        status = int(row.get("status") or 0)
        owner = str(row.get("owner") or "").strip().lower() or "unknown"
        category = str(row.get("category") or "").strip().lower() or "-"
        summary = str(row.get("summary") or "").strip()
        hint = str(row.get("hint") or "").strip()
        docs = str(row.get("docs") or "").strip()
        slug = str(row.get("slug") or "").strip()
        badge_class = "owner-user" if owner == "user" else "owner-dev" if owner == "developer" else "owner-unknown"
        search_blob = " ".join(
            [
                code.lower(),
                str(status),
                owner,
                category,
                summary.lower(),
                hint.lower(),
            ]
        )
        table_rows.append(
            "<tr data-row data-owner=\"{owner}\" data-status=\"{status}\" data-category=\"{category}\" "
            "data-search=\"{search}\">"
            "<td><a id=\"{slug}\" href=\"#{slug}\" class=\"code-link\">{code}</a></td>"
            "<td>{status}</td>"
            "<td><span class=\"owner-pill {badge_class}\">{owner}</span></td>"
            "<td>{category}</td>"
            "<td>{summary}</td>"
            "<td>{hint}</td>"
            "<td><a href=\"{docs}\" target=\"_blank\" rel=\"noopener\">open</a></td>"
            "</tr>".format(
                owner=html.escape(owner, quote=True),
                status=status,
                category=html.escape(category, quote=True),
                search=html.escape(search_blob, quote=True),
                slug=html.escape(slug or code.lower(), quote=True),
                code=html.escape(code, quote=True),
                badge_class=badge_class,
                summary=html.escape(summary, quote=True),
                hint=html.escape(hint, quote=True),
                docs=html.escape(docs, quote=True),
            )
        )

    html_body = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Web Error Codes | {html.escape(app_name, quote=True)}</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <style>
    :root {{
      --bg-0: #040814;
      --bg-1: #0b1529;
      --bg-2: #0e1f3f;
      --line: rgba(146, 186, 255, 0.26);
      --text: #eaf3ff;
      --muted: #a7bddf;
      --brand: #76b4ff;
      --user: #6fd8a6;
      --dev: #ffb575;
      --warn: #f5d27c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at 5% 0%, rgba(90, 148, 240, 0.22), transparent 33%),
        radial-gradient(circle at 93% 0%, rgba(54, 204, 207, 0.19), transparent 29%),
        linear-gradient(165deg, var(--bg-0), var(--bg-1) 45%, var(--bg-2));
      font-family: "Outfit", "Segoe UI", sans-serif;
    }}
    .wrap {{
      width: min(1200px, 96%);
      margin: 24px auto 40px;
    }}
    .hero {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      background: rgba(8, 19, 40, 0.84);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.32);
    }}
    .hero h1 {{
      margin: 0;
      font-size: clamp(1.18rem, 2.4vw, 1.8rem);
    }}
    .hero p {{
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.55;
    }}
    .stats {{
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      margin-top: 14px;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      background: rgba(11, 26, 50, 0.88);
    }}
    .stat small {{
      display: block;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .stat strong {{
      font-size: 1.05rem;
    }}
    .toolbar {{
      margin-top: 14px;
      display: grid;
      gap: 8px;
      grid-template-columns: 1.6fr 1fr 1fr auto;
    }}
    .toolbar input,
    .toolbar select {{
      min-height: 40px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: rgba(8, 18, 36, 0.92);
      color: var(--text);
      padding: 0 11px;
      font: inherit;
    }}
    .toolbar a {{
      min-height: 40px;
      padding: 0 12px;
      border-radius: 10px;
      border: 1px solid rgba(132, 183, 255, 0.4);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      color: var(--text);
      background: rgba(12, 33, 64, 0.9);
      font-weight: 700;
    }}
    .table-wrap {{
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: auto;
      background: rgba(9, 20, 40, 0.88);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 900px;
    }}
    th, td {{
      border-bottom: 1px solid rgba(134, 170, 228, 0.16);
      text-align: left;
      padding: 10px 11px;
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      background: rgba(16, 35, 66, 0.98);
      color: #d7e8ff;
      z-index: 2;
    }}
    .owner-pill {{
      display: inline-flex;
      align-items: center;
      padding: 3px 9px;
      border-radius: 999px;
      border: 1px solid transparent;
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0.01em;
    }}
    .owner-user {{
      color: #08231a;
      background: rgba(111, 216, 166, 0.95);
      border-color: rgba(111, 216, 166, 0.55);
    }}
    .owner-dev {{
      color: #3a1900;
      background: rgba(255, 181, 117, 0.96);
      border-color: rgba(255, 181, 117, 0.56);
    }}
    .owner-unknown {{
      color: #11253f;
      background: rgba(151, 187, 248, 0.95);
      border-color: rgba(151, 187, 248, 0.52);
    }}
    .code-link {{
      color: var(--brand);
      text-decoration: none;
      font-weight: 700;
    }}
    .muted {{
      color: var(--muted);
    }}
    .empty {{
      display: none;
      padding: 14px;
      color: var(--warn);
      border-top: 1px solid rgba(134, 170, 228, 0.16);
    }}
    @media (max-width: 900px) {{
      .toolbar {{
        grid-template-columns: 1fr;
      }}
      .toolbar a {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Web Error Codes</h1>
      <p>หน้ารวมรหัสข้อผิดพลาดของเว็บ SkylineBOT ใช้ค้นหาเพื่อดูว่าเป็นฝั่ง <strong>User</strong> หรือ <strong>Developer</strong> และควรแก้อย่างไร</p>
      <div class="stats">
        <article class="stat"><small>ทั้งหมด</small><strong id="statTotal">{len(rows)}</strong></article>
        <article class="stat"><small>User</small><strong>{owner_user_count}</strong></article>
        <article class="stat"><small>Developer</small><strong>{owner_dev_count}</strong></article>
        <article class="stat"><small>API JSON</small><strong><a href="{html.escape(_ERROR_CODE_DOCS_API_PATH + '?format=json', quote=True)}" style="color:#b7d9ff;">open</a></strong></article>
      </div>
      <div class="toolbar">
        <input id="codeSearch" type="search" placeholder="ค้นหา code, category, summary, hint เช่น runtime, auth, thread">
        <select id="ownerFilter">
          <option value="">ทุก owner</option>
          <option value="user">user</option>
          <option value="developer">developer</option>
        </select>
        <select id="statusFilter">
          <option value="">ทุก status</option>
          <option value="4xx">4xx</option>
          <option value="5xx">5xx</option>
        </select>
        <a href="{html.escape(_ERROR_CODE_DOCS_API_PATH + '?format=json', quote=True)}">ดูแบบ JSON</a>
      </div>
      <p class="muted" id="visibleText" style="margin:10px 0 0;">แสดง {len(rows)} / {len(rows)} รายการ</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>HTTP</th>
              <th>Owner</th>
              <th>Category</th>
              <th>Summary</th>
              <th>Hint</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody id="codesBody">
            {''.join(table_rows)}
          </tbody>
        </table>
        <div class="empty" id="emptyState">ไม่พบรหัสที่ตรงกับเงื่อนไขค้นหา</div>
      </div>
    </section>
  </main>
  <script>
    (() => {{
      const searchEl = document.getElementById("codeSearch");
      const ownerEl = document.getElementById("ownerFilter");
      const statusEl = document.getElementById("statusFilter");
      const rows = Array.from(document.querySelectorAll("[data-row]"));
      const visibleText = document.getElementById("visibleText");
      const emptyState = document.getElementById("emptyState");
      const total = rows.length;

      const apply = () => {{
        const q = String(searchEl?.value || "").trim().toLowerCase();
        const owner = String(ownerEl?.value || "").trim().toLowerCase();
        const statusBand = String(statusEl?.value || "").trim().toLowerCase();
        let visible = 0;

        rows.forEach((row) => {{
          const blob = String(row.getAttribute("data-search") || "").toLowerCase();
          const rowOwner = String(row.getAttribute("data-owner") || "").toLowerCase();
          const rowStatusRaw = parseInt(String(row.getAttribute("data-status") || "0"), 10);
          const rowStatusBand = rowStatusRaw >= 500 ? "5xx" : rowStatusRaw >= 400 ? "4xx" : "";
          const matchQ = !q || blob.includes(q);
          const matchOwner = !owner || owner === rowOwner;
          const matchStatus = !statusBand || statusBand === rowStatusBand;
          const show = matchQ && matchOwner && matchStatus;
          row.style.display = show ? "" : "none";
          if (show) visible += 1;
        }});

        if (visibleText) visibleText.textContent = `แสดง ${{visible}} / ${{total}} รายการ`;
        if (emptyState) emptyState.style.display = visible > 0 ? "none" : "block";
      }};

      [searchEl, ownerEl, statusEl].forEach((el) => {{
        if (!el) return;
        el.addEventListener("input", apply);
        el.addEventListener("change", apply);
      }});
      apply();
    }})();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_body, status_code=200)


@app.post("/api/discord/interactions", include_in_schema=False)
@app.post("/api/discord/interactions/", include_in_schema=False)
async def discord_interactions_endpoint(request: Request):
    public_key_hex = _discord_interactions_public_key_hex()
    if not public_key_hex:
        _LOG.warning("Interactions endpoint rejected request: DISCORD_APPLICATION_PUBLIC_KEY is not configured")
        raise HTTPException(
            status_code=503,
            detail="DISCORD_APPLICATION_PUBLIC_KEY is not configured",
        )

    signature = str(request.headers.get("X-Signature-Ed25519") or "").strip()
    timestamp = str(request.headers.get("X-Signature-Timestamp") or "").strip()
    body = await request.body()

    try:
        verified = _verify_discord_interaction_signature(
            public_key_hex=public_key_hex,
            timestamp=timestamp,
            signature_hex=signature,
            body=body,
        )
    except RuntimeError as exc:
        _LOG.warning("Interactions endpoint rejected request: %s", str(exc))
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not verified:
        _LOG.warning(
            "Interactions endpoint signature verification failed (ts_present=%s sig_len=%s body_len=%s)",
            bool(timestamp),
            len(signature),
            len(body),
        )
        raise HTTPException(status_code=401, detail="Invalid request signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        _LOG.warning("Interactions endpoint rejected request: invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    interaction_type = int(payload.get("type", 0) or 0)
    if interaction_type == 1:
        _LOG.info("Interactions endpoint acknowledged Discord PING")
        return JSONResponse({"type": 1})

    dispatched, reason = _dispatch_discord_interaction(payload)
    if not dispatched:
        _LOG.warning(
            "Interactions endpoint fallback inline response (type=%s reason=%s)",
            interaction_type,
            reason,
        )
        return _interaction_inline_unavailable_response(interaction_type, reason)

    # Discord expects 202/no-body on the original webhook request when the
    # interaction response is sent asynchronously via callback endpoint.
    return Response(status_code=202)


@app.get("/api/discord/interactions", include_in_schema=False)
@app.get("/api/discord/interactions/", include_in_schema=False)
async def discord_interactions_endpoint_health():
    key = _discord_interactions_public_key_hex()
    configured = bool(key)
    key_is_hex = bool(re.fullmatch(r"[0-9a-fA-F]+", key)) if configured else False
    _target, dispatch_reason = _discord_interaction_dispatch_target()
    dispatch_ready = dispatch_reason == "ok"
    return JSONResponse(
        {
            "ok": True,
            "route": "/api/discord/interactions",
            "post_enabled": True,
            "transport_mode": _discord_interactions_transport_mode(),
            "public_key_configured": configured,
            "public_key_length": len(key),
            "public_key_hex_valid": key_is_hex,
            "pynacl_available": _pynacl_available(),
            "dispatch_ready": dispatch_ready,
            "dispatch_reason": dispatch_reason,
            "note": (
                "POST with Discord signature headers for real interactions. "
                "When responding asynchronously through callback endpoint, this route returns 202."
            ),
        }
    )


@app.get("/skylinebot/dashboard")
async def dashboard_alias_root():
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/skylinebot/dashboard/{rest:path}")
async def dashboard_alias(rest: str):
    suffix = str(rest or "").lstrip("/")
    target = f"/dashboard/{suffix}" if suffix else "/dashboard"
    return RedirectResponse(url=target, status_code=303)


app.include_router(transcript.router)
app.include_router(redeem_code_routes.router)
app.include_router(dashboard_impl.router)
