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
        active_tab_slug="server_settings",
        title_override="ตั้งค่าเซิร์ฟเวอร์",
        description_override="รวมการตั้งค่าหลักของเซิร์ฟเวอร์และนโยบายความปลอดภัยในหน้าเดียว",
    )
