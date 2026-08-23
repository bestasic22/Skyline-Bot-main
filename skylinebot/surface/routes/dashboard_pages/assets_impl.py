from __future__ import annotations

from ..dashboard_core import (
    DONATE_UPLOAD_DIR,
    EMBED_UPLOAD_DIR,
    FileResponse,
    MUSIC_IDLE_IMAGE_PATH,
    Path,
    PROMOTE_UPLOAD_DIR,
    RedirectResponse,
    Response,
    STARBOARD_UPLOAD_DIR,
    VERIFY_UPLOAD_DIR,
    WELCOME_UPLOAD_DIR,
    mimetypes,
    style_urls,
)
from ..dashboard_helpers.image_storage import read_dashboard_asset_blob

FONT_ASSET_DIR = Path(__file__).resolve().parents[3] / "fonts"

async def dashboard_music_idle_image():
    if MUSIC_IDLE_IMAGE_PATH.exists():
        return FileResponse(str(MUSIC_IDLE_IMAGE_PATH), media_type="image/png")
    return RedirectResponse(style_urls.DEFAULT_MUSIC_BANNER, status_code=307)

async def dashboard_donate_asset(filename: str):
    safe_name = Path(str(filename or "")).name
    if not safe_name:
        return RedirectResponse("/dashboard", status_code=307)
    target = DONATE_UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        return RedirectResponse("/dashboard", status_code=307)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(str(target), media_type=media_type or "application/octet-stream")

async def dashboard_verify_asset(filename: str):
    safe_name = Path(str(filename or "")).name
    if not safe_name:
        return RedirectResponse("/dashboard", status_code=307)
    target = VERIFY_UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        return RedirectResponse("/dashboard", status_code=307)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(str(target), media_type=media_type or "application/octet-stream")

async def dashboard_welcome_asset(filename: str):
    safe_name = Path(str(filename or "")).name
    if not safe_name:
        return RedirectResponse("/dashboard", status_code=307)
    target = WELCOME_UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        return RedirectResponse("/dashboard", status_code=307)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(str(target), media_type=media_type or "application/octet-stream")

async def dashboard_starboard_asset(filename: str):
    safe_name = Path(str(filename or "")).name
    if not safe_name:
        return RedirectResponse("/dashboard", status_code=307)
    target = STARBOARD_UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        return RedirectResponse("/dashboard", status_code=307)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(str(target), media_type=media_type or "application/octet-stream")

async def dashboard_embed_asset(filename: str):
    safe_name = Path(str(filename or "")).name
    if not safe_name:
        return RedirectResponse("/dashboard", status_code=307)
    target = EMBED_UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        return RedirectResponse("/dashboard", status_code=307)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(str(target), media_type=media_type or "application/octet-stream")


async def dashboard_promote_asset(filename: str):
    safe_name = Path(str(filename or "")).name
    if not safe_name:
        return RedirectResponse("/dashboard", status_code=307)
    target = PROMOTE_UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        return RedirectResponse("/dashboard", status_code=307)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(str(target), media_type=media_type or "application/octet-stream")


async def dashboard_db_asset(asset_key: str, filename: str = ""):
    _ = filename
    asset, payload = await read_dashboard_asset_blob(asset_key)
    if not asset or not payload:
        return RedirectResponse("/dashboard", status_code=307)
    media_type = str(asset.get("mime_type") or "").strip().lower() or "application/octet-stream"
    headers = {
        "Cache-Control": "public, max-age=2592000, immutable",
    }
    etag = str(asset.get("sha256") or "").strip().lower()
    if etag:
        headers["ETag"] = f"\"{etag}\""
    return Response(content=payload, media_type=media_type, headers=headers)


async def dashboard_font_asset(filename: str):
    safe_name = Path(str(filename or "")).name
    if not safe_name:
        return RedirectResponse("/dashboard", status_code=307)
    allowed_names = {
        "arial.ttf",
        "arialbd.ttf",
        "dejavusans-bold.ttf",
        "protestguerrilla-regular.ttf",
        "sofadione-regular.ttf",
    }
    if safe_name.strip().lower() not in allowed_names:
        return RedirectResponse("/dashboard", status_code=307)
    target = FONT_ASSET_DIR / safe_name
    if not target.exists() or not target.is_file():
        return RedirectResponse("/dashboard", status_code=307)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(
        str(target),
        media_type=media_type or "font/ttf",
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )
