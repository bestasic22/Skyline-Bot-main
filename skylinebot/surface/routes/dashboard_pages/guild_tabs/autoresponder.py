from __future__ import annotations

from ... import dashboard_core as core
from .context import GuildTabRenderContext


def render(ctx: GuildTabRenderContext) -> str:
    return core._render_autoresponder(
        ctx.session,
        ctx.guilds,
        ctx.current_guild,
        ctx.state,
        notice=ctx.notice,
    )
