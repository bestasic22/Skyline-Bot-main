from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .assets_impl import (
    dashboard_music_idle_image,
    dashboard_donate_asset,
    dashboard_verify_asset,
    dashboard_welcome_asset,
    dashboard_starboard_asset,
    dashboard_embed_asset,
    dashboard_promote_asset,
    dashboard_db_asset,
    dashboard_font_asset,
)


def register(router: APIRouter) -> None:
    router.add_api_route("/assets/music-idle", dashboard_music_idle_image, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/donate/{filename:path}", dashboard_donate_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/verify/{filename:path}", dashboard_verify_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/welcome/{filename:path}", dashboard_welcome_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/starboard/{filename:path}", dashboard_starboard_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/embed/{filename:path}", dashboard_embed_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/promote/{filename:path}", dashboard_promote_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/fonts/{filename:path}", dashboard_font_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/db/{asset_key}", dashboard_db_asset, methods=["GET"], include_in_schema=False)
    router.add_api_route("/assets/db/{asset_key}/{filename:path}", dashboard_db_asset, methods=["GET"], include_in_schema=False)
