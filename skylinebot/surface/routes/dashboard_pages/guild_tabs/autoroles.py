from __future__ import annotations

from ... import dashboard_core as core
from .context import GuildTabRenderContext


def render(ctx: GuildTabRenderContext) -> str:
    return core._render_probot_module_hub(
        ctx.session,
        ctx.guilds,
        ctx.current_guild,
        active_slug="autoroles",
        title="บทบาทอัตโนมัติ",
        description="ตั้งค่าเวิร์กโฟลว์บทบาทอัตโนมัติและกฎการมอบบทบาท",
        quick_links=[
            ("ไปหน้าศูนย์ต้อนรับ", f"/dashboard/guild/{ctx.current_guild['id']}/welcome_center"),
            ("ไปหน้าบทบาทรีแอ็กชัน", f"/dashboard/guild/{ctx.current_guild['id']}/reaction_roles"),
        ],
        notice=ctx.notice,
    )
