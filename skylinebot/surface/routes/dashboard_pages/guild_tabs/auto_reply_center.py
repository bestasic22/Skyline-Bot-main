from __future__ import annotations

from ... import dashboard_core as core
from .context import GuildTabRenderContext


def render(ctx: GuildTabRenderContext) -> str:
    return core._render_probot_module_hub(
        ctx.session,
        ctx.guilds,
        ctx.current_guild,
        active_slug="auto_reply_center",
        title="ตัวตอบกลับอัตโนมัติ",
        description="ศูนย์ควบคุมระบบตอบกลับอัตโนมัติและระบบแชต AI",
        quick_links=[
            ("ไปตอบกลับอัตโนมัติ", f"/dashboard/guild/{ctx.current_guild['id']}/autoresponder"),
            ("ไปแชต AI", f"/dashboard/guild/{ctx.current_guild['id']}/aichat"),
        ],
        notice=ctx.notice,
    )
