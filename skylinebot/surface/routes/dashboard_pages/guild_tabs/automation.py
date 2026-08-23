from __future__ import annotations

from ... import dashboard_core as core
from .context import GuildTabRenderContext


def render(ctx: GuildTabRenderContext) -> str:
    return core._render_moderation(
        ctx.session,
        ctx.guilds,
        ctx.current_guild,
        ctx.bot_guild,
        ctx.state,
        notice=ctx.notice,
        active_tab_slug="automation",
        title_override="การจัดการอัตโนมัติ",
        description_override="ตั้งค่า AutoMod และการคัดกรองอัตโนมัติของเซิร์ฟเวอร์",
    )
