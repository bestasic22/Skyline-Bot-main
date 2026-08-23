from __future__ import annotations

from fastapi import APIRouter

from skylinebot.surface.runtime import bind_bot
from skylinebot.surface.routes.dashboard_core import *  # noqa: F401,F403
from skylinebot.surface.routes.dashboard_pages import register_all as _register_dashboard_pages

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_register_dashboard_pages(router)

__all__ = ["router", "bind_bot"]
