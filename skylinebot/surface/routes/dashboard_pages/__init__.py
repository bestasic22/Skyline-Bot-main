from __future__ import annotations

from fastapi import APIRouter

from . import admin, assets, guild, public


def register_all(router: APIRouter) -> None:
    assets.register(router)
    public.register(router)
    admin.register(router)
    guild.register(router)
