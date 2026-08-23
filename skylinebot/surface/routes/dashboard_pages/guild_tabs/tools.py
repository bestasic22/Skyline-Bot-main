from __future__ import annotations

from ... import dashboard_core as core
from .context import GuildTabRenderContext


def render(ctx: GuildTabRenderContext) -> str:
    return core._render_probot_module_hub(
        ctx.session,
        ctx.guilds,
        ctx.current_guild,
        active_slug="tools",
        title="เครื่องมือ",
        description="ศูนย์รวมเครื่องมือจัดการเซิร์ฟเวอร์ เลือกเปิดหน้าตั้งค่าที่ต้องการได้ทันที",
        quick_links=[
            (
                "One-click Apply RP Theme",
                f"/dashboard/guild/{ctx.current_guild['id']}/guildstyle_studio",
                "One-click Apply RP theme, role color picker, and room permission editor",
                "roleplay",
            ),
            (
                "ระบบเศรษฐกิจ",
                f"/dashboard/guild/{ctx.current_guild['id']}/economy",
                "จัดการเงิน รางวัล ร้านค้า และสถิติเศรษฐกิจ",
                "economy",
            ),
            (
                "ตั้งค่าเพลง",
                f"/dashboard/guild/{ctx.current_guild['id']}/music",
                "ควบคุมระบบเพลง ช่องใช้งาน และพฤติกรรมผู้เล่น",
                "music",
            ),
            (
                "จัดการคำสั่ง",
                f"/dashboard/guild/{ctx.current_guild['id']}/commands",
                "เปิด/ปิดคำสั่งหลัก ปรับสิทธิ์ และจัดระเบียบคำสั่ง",
                "commands",
            ),
            (
                "ข้อความแบบ Embed",
                f"/dashboard/guild/{ctx.current_guild['id']}/embed_messages",
                "ออกแบบและส่งข้อความ Embed ไปยังห้องต่าง ๆ",
                "embed_messages",
            ),
            (
                "คัดกรองสมาชิก",
                f"/dashboard/guild/{ctx.current_guild['id']}/screening",
                "ตั้งค่ากระบวนการคัดกรองก่อนให้สมาชิกเข้าถึงเซิร์ฟเวอร์",
                "screening",
            ),
            (
                "หมวดคำถามคัดกรอง",
                f"/dashboard/guild/{ctx.current_guild['id']}/screening_categories",
                "จัดการหมวดหมู่ ฟอร์ม และคำถามที่ใช้คัดกรอง",
                "screening_categories",
            ),
            (
                "ตั้งค่าเซิร์ฟเวอร์",
                f"/dashboard/guild/{ctx.current_guild['id']}/server_settings",
                "ตั้งค่าพื้นฐาน สิทธิ์ และข้อมูลหลักของบอทในกิลด์",
                "server_settings",
            ),
        ],
        notice=ctx.notice,
    )
