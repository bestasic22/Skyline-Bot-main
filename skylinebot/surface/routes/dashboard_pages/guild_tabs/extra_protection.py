from __future__ import annotations

from ... import dashboard_core as core
from .context import GuildTabRenderContext


def render(ctx: GuildTabRenderContext) -> str:
    return core._render_security(
        ctx.session,
        ctx.guilds,
        ctx.current_guild,
        ctx.bot_guild,
        ctx.state,
        notice=ctx.notice,
        active_tab_slug="extra_protection",
        title_override="การป้องกันขั้นสูง",
        description_override="ปรับชุดควบคุม Anti-Nuke และมาตรการป้องกันเชิงลึกสำหรับกิลด์ที่ต้องการความปลอดภัยสูง",
    )
