import discord
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
import datetime
import io
import os
import re
import uuid

import httpx

import storage
from skylinebot.bridge.storage import get_collection
from skylinebot.console.logging import logger
from skylinebot.memory.cache import cache
from skylinebot.style.urls import WEBSITE

DONATE_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "donate"
DASHBOARD_DONATE_ASSET_PREFIX = "/dashboard/assets/donate/"

_METHOD_ORDER = ["truemoney", "promptpay", "bank", "slipverify"]
_METHOD_META = {
    "truemoney": {"label": "TrueMoney", "emoji": "📱"},
    "promptpay": {"label": "พร้อมเพย์", "emoji": "💸"},
    "bank": {"label": "ธนาคาร", "emoji": "🏦"},
    "slipverify": {"label": "ตรวจสอบสลิป", "emoji": "🧾"},
}
_TRUEMONEY_GIFT_RE = re.compile(r"^https?://gift\.truemoney\.com/campaign/\?v=[A-Za-z0-9_-]{8,}$", re.I)


def _safe_upload_name(filename: str) -> str:
    base = Path(str(filename or "slip.png")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not stem:
        stem = f"slip_{uuid.uuid4().hex[:8]}.png"
    ext = Path(stem).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        stem = f"{Path(stem).stem or 'slip'}.png"
    return stem[:120]


def _normalize_donate_slip_status(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"approved", "pass", "passed", "success", "ผ่าน"}:
        return "approved"
    if value in {"rejected", "reject", "failed", "ไม่ผ่าน"}:
        return "rejected"
    return "pending"


def _donate_slip_status_label(status: str) -> str:
    value = _normalize_donate_slip_status(status)
    if value == "approved":
        return "ผ่าน"
    if value == "rejected":
        return "ไม่ผ่าน"
    return "รอตรวจ"


def _extract_slipok_endpoint(api_url: str) -> str:
    value = str(api_url or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.isdigit():
        return f"https://api.slipok.com/api/line/apikey/{value}"
    return ""


def _safe_color(raw: Any) -> int:
    text = str(raw or "#6b8cff").strip().lstrip("#")
    try:
        return int(text[:6], 16)
    except Exception:
        return 0x6B8CFF


def _website_base() -> str:
    site = str(os.getenv("DASHBOARD_BASE_URL") or WEBSITE or "").strip()
    if not site:
        return ""
    if not site.startswith(("http://", "https://")):
        site = f"https://{site}"
    return site.rstrip("/")


def _public_donate_url(guild_id: int) -> str:
    base = _website_base()
    if base:
        return f"{base}/dashboard/donate/{int(guild_id)}"
    return "https://discord.com"


def _normalize_image_url(raw: Any) -> str:
    image_url = str(raw or "").strip()
    if not image_url:
        return ""
    parsed = urlparse(image_url)
    if parsed.scheme in {"http", "https"}:
        return image_url
    if image_url.startswith("/"):
        base = _website_base()
        if base:
            return urljoin(base + "/", image_url.lstrip("/"))
    return image_url


def _normalize_external_link(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return value[:1024]


def _resolve_image_asset(raw: Any) -> tuple[Optional[str], Optional[discord.File]]:
    image_url = str(raw or "").strip()
    if not image_url:
        return None, None

    parsed = urlparse(image_url)
    path_only = parsed.path or image_url
    if path_only.startswith(DASHBOARD_DONATE_ASSET_PREFIX):
        filename = Path(path_only).name
        if filename:
            local_file = DONATE_UPLOAD_DIR / filename
            if local_file.is_file():
                attachment_name = f"donate_{filename}"
                return f"attachment://{attachment_name}", discord.File(str(local_file), filename=attachment_name)

    normalized = _normalize_image_url(image_url)
    return (normalized, None) if normalized else (None, None)


def _enabled_methods(settings: dict[str, Any]) -> list[str]:
    methods = settings.get("methods_enabled") or {}
    return [name for name in _METHOD_ORDER if methods.get(name)]


async def _get_donate_settings(guild_id: int) -> dict[str, Any]:
    cached = cache.donate_settings_cache.get(str(guild_id))
    if isinstance(cached, dict) and cached:
        return cached

    settings = await storage.donate_settings.get(guild_id=guild_id)
    if isinstance(settings, dict) and settings:
        cache.donate_settings_cache[str(guild_id)] = settings
        return settings

    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"donate_settings_fallback": 1, "_id": 0})
        payload = (doc or {}).get("donate_settings_fallback")
        if isinstance(payload, dict) and payload:
            cache.donate_settings_cache[str(guild_id)] = payload
            return payload
    except Exception:
        pass
    return {}


def _normalize_donate_slip_log(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "slip_id": str(raw.get("slip_id") or uuid.uuid4().hex),
        "created_at": str(raw.get("created_at") or datetime.datetime.now(tz=datetime.timezone.utc).isoformat()),
        "status": _normalize_donate_slip_status(raw.get("status")),
        "donor_name": str(raw.get("donor_name") or "ไม่ระบุชื่อ")[:80],
        "amount": int(raw.get("amount") or 0),
        "payment_method": str(raw.get("payment_method") or "other")[:30],
        "message": str(raw.get("message") or "")[:500],
        "image_url": str(raw.get("image_url") or "")[:500],
        "discord_channel_id": str(raw.get("discord_channel_id") or ""),
        "discord_message_id": str(raw.get("discord_message_id") or ""),
        "reviewed_at": str(raw.get("reviewed_at") or ""),
        "reviewed_by_id": str(raw.get("reviewed_by_id") or ""),
        "reviewed_by_name": str(raw.get("reviewed_by_name") or ""),
    }


async def _append_donate_slip_log(guild_id: int, payload: dict[str, Any], *, keep_limit: int = 200) -> None:
    normalized = _normalize_donate_slip_log(payload)
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"donate_slip_logs": 1, "_id": 0})
        current = (doc or {}).get("donate_slip_logs")
        rows = current if isinstance(current, list) else []
        merged = [normalized]
        seen_ids = {normalized["slip_id"]}
        for row in rows:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("slip_id") or "")
            if not sid or sid in seen_ids:
                continue
            merged.append(_normalize_donate_slip_log(row))
            seen_ids.add(sid)
            if len(merged) >= keep_limit:
                break
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"donate_slip_logs": merged}},
            upsert=True,
        )
    except Exception as error:
        logger.warning(f"Failed to append donate slip log for guild {guild_id}: {error}")


async def _update_donate_slip_log_status(
    guild_id: int,
    slip_id: str,
    status: str,
    *,
    reviewer_id: str = "",
    reviewer_name: str = "",
) -> bool:
    target_id = str(slip_id or "").strip()
    if not target_id:
        return False
    target_status = _normalize_donate_slip_status(status)
    try:
        guilds_col = await get_collection("guilds")
        doc = await guilds_col.find_one({"guild_id": guild_id}, {"donate_slip_logs": 1, "_id": 0})
        rows = (doc or {}).get("donate_slip_logs")
        if not isinstance(rows, list):
            return False
        changed = False
        now_iso = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        merged: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized = _normalize_donate_slip_log(row)
            if str(normalized.get("slip_id") or "") == target_id:
                normalized["status"] = target_status
                normalized["reviewed_at"] = now_iso
                normalized["reviewed_by_id"] = str(reviewer_id or "")
                normalized["reviewed_by_name"] = str(reviewer_name or "")
                changed = True
            merged.append(normalized)
        if not changed:
            return False
        await guilds_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"donate_slip_logs": merged[:200]}},
            upsert=True,
        )
        return True
    except Exception as error:
        logger.warning(f"Failed to update donate slip status for guild {guild_id}: {error}")
        return False


async def _auto_verify_donate_evidence(
    *,
    settings: dict[str, Any],
    payment_method: str,
    amount: int,
    image_url: str = "",
    raw_bytes: bytes | None = None,
    filename: str = "slip.png",
    transfer_link: str = "",
) -> tuple[str, str]:
    method = str(payment_method or "").strip().lower()
    link = str(transfer_link or "").strip()

    if method == "truemoney" and link:
        if not _TRUEMONEY_GIFT_RE.match(link):
            return "rejected", "ลิงก์อั่งเปาไม่ถูกต้อง"
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(link)
            if 200 <= int(response.status_code) < 400:
                return "approved", "ตรวจลิงก์อั่งเปาเบื้องต้นผ่านแล้ว"
        except Exception:
            pass
        return "pending", "รับลิงก์อั่งเปาแล้ว รอตรวจสอบเพิ่มเติม"

    methods_enabled = settings.get("methods_enabled") or {}
    if not methods_enabled.get("slipverify"):
        return "pending", "ยังไม่เปิดระบบตรวจสลิปอัตโนมัติ"

    endpoint = _extract_slipok_endpoint(settings.get("slipok_api_url") or "")
    api_key = str(settings.get("slipok_key") or "").strip()
    if not endpoint or not api_key:
        return "pending", "ยังไม่ได้ตั้งค่า SlipOK API/Key"

    try:
        headers = {"x-authorization": api_key}
        payload: dict[str, Any] = {"log": "true"}
        if amount > 0:
            payload["amount"] = str(amount)
        files = None
        if raw_bytes:
            files = {
                "files": (
                    _safe_upload_name(filename),
                    raw_bytes,
                    "image/png",
                )
            }
        elif image_url:
            payload["url"] = image_url
        else:
            return "pending", "ไม่มีไฟล์หรือ URL สำหรับตรวจสอบ"
        async with httpx.AsyncClient(timeout=22.0) as client:
            if files:
                response = await client.post(endpoint, headers=headers, data=payload, files=files)
            else:
                response = await client.post(endpoint, headers=headers, data=payload)
        data = response.json() if response.content else {}
        verify_ok = bool(data.get("success")) and bool((data.get("data") or {}).get("success"))
        verify_msg = str((data.get("data") or {}).get("message") or data.get("message") or "").strip()
        if verify_ok:
            return "approved", verify_msg or "ตรวจสลิปอัตโนมัติผ่าน"
        return "rejected", verify_msg or "ตรวจสลิปอัตโนมัติไม่ผ่าน"
    except Exception:
        return "pending", "ระบบตรวจอัตโนมัติไม่พร้อมใช้งาน"


def _build_public_donate_embed(guild_name: str, settings: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title="💎 สนับสนุนเซิร์ฟเวอร์",
        description=(settings.get("desc_discord") or "สามารถสนับสนุนเซิร์ฟเวอร์ผ่านช่องทางด้านล่างได้เลยครับ").strip(),
        color=_safe_color(settings.get("color")),
    )
    embed.add_field(name="กิลด์", value=guild_name or "-", inline=True)

    enabled = _enabled_methods(settings)
    method_text = "\n".join(f"{_METHOD_META[m]['emoji']} {_METHOD_META[m]['label']}" for m in enabled) if enabled else "ยังไม่มีช่องทางที่เปิดใช้งาน"
    embed.add_field(name="ช่องทางที่เปิดอยู่", value=method_text, inline=True)

    reward_role_id = str(settings.get("reward_role_id") or "").strip()
    if reward_role_id.isdigit():
        embed.add_field(name="ยศพิเศษ", value=f"<@&{reward_role_id}>", inline=False)

    if (settings.get("methods_enabled") or {}).get("goal"):
        goal_title = str(settings.get("goal_title") or "ค่าขนม").strip() or "ค่าขนม"
        start = int(settings.get("goal_start_amount") or 0)
        end = int(settings.get("goal_end_amount") or 0)
        embed.add_field(name="หลอดโดเนท", value=f"{goal_title}\nเริ่ม: {start:,} | เป้าหมาย: {end:,}", inline=False)

    image_url, _ = _resolve_image_asset(settings.get("image_url"))
    if image_url:
        embed.set_image(url=image_url)

    embed.set_footer(text="ขอบคุณทุกการสนับสนุนครับ")
    return embed


def _build_method_embed(method_name: str, settings: dict[str, Any]) -> discord.Embed:
    method_name = str(method_name or "").strip().lower()
    embed = discord.Embed(color=_safe_color(settings.get("color")))

    if method_name == "truemoney":
        embed.title = "📱 ทรูมันนี่วอลเล็ท"
        number = str(settings.get("truemoney_phone") or "").strip() or "-"
        embed.description = f"เบอร์ทรูวอลเลท:\n`{number}`"
    elif method_name == "promptpay":
        embed.title = "💸 พร้อมเพย์"
        number = str(settings.get("promptpay_number") or "").strip() or "-"
        embed.description = f"หมายเลขพร้อมเพย์:\n`{number}`"
    elif method_name == "bank":
        embed.title = "🏦 โอนผ่านธนาคาร"
        bank_name = str(settings.get("bank_name") or "-").strip() or "-"
        bank_number = str(settings.get("bank_account_number") or "-").strip() or "-"
        bank_owner = str(settings.get("bank_account_name") or "-").strip() or "-"
        embed.description = (
            f"ธนาคาร: **{bank_name}**\n"
            f"เลขบัญชี: `{bank_number}`\n"
            f"ชื่อบัญชี: **{bank_owner}**"
        )
    elif method_name == "slipverify":
        embed.title = "🧾 ตรวจสอบสลิป"
        notify_channel_id = str(settings.get("notification_channel_id") or "").strip()
        channel_hint = f"<#{notify_channel_id}>" if notify_channel_id.isdigit() else "ห้องแจ้งเตือนที่ตั้งค่าไว้"
        embed.description = f"โอนแล้วส่งสลิปที่ {channel_hint} เพื่อให้ทีมงานตรวจสอบ"
    else:
        embed.title = "💎 วิธีสนับสนุน"
        embed.description = "เลือกปุ่มช่องทางด้านล่างเพื่อดูรายละเอียดได้เลย"

    image_url, _ = _resolve_image_asset(settings.get("image_url"))
    if image_url:
        embed.set_image(url=image_url)
    return embed


def _build_all_methods_embed(settings: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title="💎 ช่องทางสนับสนุนทั้งหมด",
        description=(settings.get("desc_discord") or "เลือกช่องทางที่สะดวกได้เลย").strip(),
        color=_safe_color(settings.get("color")),
    )
    methods = settings.get("methods_enabled") or {}

    if methods.get("truemoney") and settings.get("truemoney_phone"):
        embed.add_field(name="📱 ทรูมันนี่วอลเล็ท", value=f"`{settings['truemoney_phone']}`", inline=False)
    if methods.get("promptpay") and settings.get("promptpay_number"):
        embed.add_field(name="💸 พร้อมเพย์", value=f"`{settings['promptpay_number']}`", inline=False)
    if methods.get("bank") and settings.get("bank_name"):
        bank_info = (
            f"ธนาคาร: **{settings.get('bank_name') or '-'}**\n"
            f"เลขบัญชี: `{settings.get('bank_account_number') or '-'}`\n"
            f"ชื่อบัญชี: **{settings.get('bank_account_name') or '-'}**"
        )
        embed.add_field(name="🏦 ธนาคาร", value=bank_info, inline=False)
    if methods.get("slipverify"):
        notify_channel_id = str(settings.get("notification_channel_id") or "").strip()
        channel_hint = f"<#{notify_channel_id}>" if notify_channel_id.isdigit() else "ห้องแจ้งเตือนที่ตั้งค่าไว้"
        embed.add_field(name="🧾 ตรวจสอบสลิป", value=f"ส่งสลิปที่ {channel_hint}", inline=False)

    if methods.get("goal"):
        goal_title = str(settings.get("goal_title") or "ค่าขนม").strip() or "ค่าขนม"
        start = int(settings.get("goal_start_amount") or 0)
        end = int(settings.get("goal_end_amount") or 0)
        embed.add_field(name="🎯 หลอดโดเนท", value=f"{goal_title}\nเริ่ม: {start:,} | เป้าหมาย: {end:,}", inline=False)

    image_url, _ = _resolve_image_asset(settings.get("image_url"))
    if image_url:
        embed.set_image(url=image_url)

    embed.set_footer(text="โอนแล้วอย่าลืมส่งหลักฐานการโอนตามช่องที่กำหนด")
    return embed


class DonateMethodButton(discord.ui.Button):
    def __init__(self, guild_id: int, method_name: str):
        meta = _METHOD_META.get(method_name, {"label": method_name.title(), "emoji": "💠"})
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=meta["label"],
            emoji=meta["emoji"],
            custom_id=f"donate_method:{guild_id}:{method_name}",
            row=1,
        )
        self.guild_id = guild_id
        self.method_name = method_name

    async def callback(self, interaction: discord.Interaction):
        settings = cache.donate_settings_cache.get(str(self.guild_id)) or {}
        embed = _build_method_embed(self.method_name, settings)
        image_url, local_file = _resolve_image_asset(settings.get("image_url"))
        if image_url:
            embed.set_image(url=image_url)
        if local_file:
            await interaction.response.send_message(embed=embed, file=local_file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class DonateGiftLinkModal(discord.ui.Modal, title="ส่งลิงก์ของขวัญ TrueMoney"):
    def __init__(self, *, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = int(guild_id)
        self.amount = discord.ui.TextInput(
            label="จำนวนเงิน (บาท)",
            placeholder="เช่น 50",
            required=True,
            max_length=12,
        )
        self.gift_link = discord.ui.TextInput(
            label="ลิงก์ของขวัญ TrueMoney",
            placeholder="https://gift.truemoney.com/campaign/?v=...",
            required=True,
            max_length=500,
        )
        self.note = discord.ui.TextInput(
            label="ข้อความถึงเรา (ไม่บังคับ)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=300,
            placeholder="เช่น หมายเหตุการโอน",
        )
        self.add_item(self.amount)
        self.add_item(self.gift_link)
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or interaction.guild_id != self.guild_id:
            await interaction.response.send_message("ใช้ได้เฉพาะเซิร์ฟเวอร์เดิมเท่านั้น", ephemeral=True)
            return

        amount_text = str(self.amount.value or "").strip().replace(",", "")
        try:
            amount = int(float(amount_text))
        except Exception:
            amount = 0
        if amount <= 0:
            await interaction.response.send_message("จำนวนเงินไม่ถูกต้อง", ephemeral=True)
            return

        transfer_link = str(self.gift_link.value or "").strip()
        if not _TRUEMONEY_GIFT_RE.match(transfer_link):
            await interaction.response.send_message(
                "ลิงก์อั่งเปาไม่ถูกต้อง (ต้องเป็น gift.truemoney.com/campaign/?v=...)",
                ephemeral=True,
            )
            return

        settings = await _get_donate_settings(self.guild_id)
        if not settings or not settings.get("enabled"):
            await interaction.response.send_message("ระบบโดเนทยังไม่เปิดใช้งานในเซิร์ฟเวอร์นี้", ephemeral=True)
            return
        methods_enabled = settings.get("methods_enabled") or {}
        if not methods_enabled.get("truemoney"):
            await interaction.response.send_message("เซิร์ฟเวอร์นี้ยังไม่เปิดช่องทาง TrueMoney", ephemeral=True)
            return

        notify_channel_id = str(settings.get("notification_channel_id") or "").strip()
        if not notify_channel_id.isdigit():
            await interaction.response.send_message("ผู้ดูแลยังไม่ได้ตั้งค่าห้องแจ้งเตือนการโดเนท", ephemeral=True)
            return

        channel = interaction.guild.get_channel(int(notify_channel_id))
        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(int(notify_channel_id))
            except Exception:
                channel = None
        if channel is None or not hasattr(channel, "send"):
            await interaction.response.send_message("ไม่พบบอทในห้องแจ้งเตือนหรือบอทส่งข้อความไม่ได้", ephemeral=True)
            return

        auto_status, auto_note = await _auto_verify_donate_evidence(
            settings=settings,
            payment_method="truemoney",
            amount=amount,
            transfer_link=transfer_link,
        )
        slip_id = uuid.uuid4().hex
        donor_name = str(getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "Unknown"))
        note_text = str(self.note.value or "").strip()

        embed = discord.Embed(
            title="แจ้งหลักฐานลิงก์ของขวัญ TrueMoney",
            color=_safe_color(settings.get("color")),
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        embed.add_field(name="ผู้โอน", value=f"{interaction.user.mention} ({donor_name})", inline=False)
        embed.add_field(name="จำนวนเงิน", value=f"{int(amount):,} บาท", inline=True)
        embed.add_field(name="ช่องทาง", value="ทรูมันนี่วอลเล็ท (ลิงก์ของขวัญ)", inline=True)
        embed.add_field(name="สถานะตรวจอัตโนมัติ", value=_donate_slip_status_label(auto_status), inline=True)
        embed.add_field(name="ลิงก์อั่งเปา/ลิงก์อ้างอิง", value=transfer_link[:1024], inline=False)
        if note_text:
            embed.add_field(name="ข้อความถึงเรา", value=note_text[:1024], inline=False)
        if auto_note:
            embed.add_field(name="หมายเหตุการตรวจ", value=auto_note[:1024], inline=False)
        embed.set_footer(text=f"กิลด์ ID: {interaction.guild_id} • slip:{slip_id[:10]}")

        review_view = DonateSlipReviewView(
            guild_id=self.guild_id,
            slip_id=slip_id,
            transfer_link=transfer_link,
        )
        try:
            sent = await channel.send(embed=embed, view=review_view)
            sent_message_id = str(getattr(sent, "id", "") or "")
        except Exception:
            await interaction.response.send_message("ส่งลิงก์ไปห้องแจ้งเตือนไม่สำเร็จ กรุณาตรวจสอบสิทธิ์บอท", ephemeral=True)
            return

        await _append_donate_slip_log(
            self.guild_id,
            {
                "slip_id": slip_id,
                "created_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                "status": auto_status,
                "donor_name": donor_name,
                "amount": int(amount),
                "payment_method": "truemoney",
                "message": f"{note_text}\nลิงก์: {transfer_link}".strip(),
                "image_url": "",
                "discord_channel_id": str(notify_channel_id),
                "discord_message_id": sent_message_id,
                "reviewed_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat() if auto_status != "pending" else "",
                "reviewed_by_id": "system" if auto_status != "pending" else "",
                "reviewed_by_name": "Auto Verify" if auto_status != "pending" else "",
            },
        )

        await interaction.response.send_message(
            f"ส่งลิงก์ของขวัญเรียบร้อยแล้ว • สถานะตอนนี้: **{_donate_slip_status_label(auto_status)}**",
            ephemeral=True,
        )


class DonateView(discord.ui.View):
    def __init__(self, guild_id: int, settings: Optional[dict[str, Any]] = None):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.settings = settings or {}

        web_url = _public_donate_url(guild_id)
        self.add_item(discord.ui.Button(
            label="เปิดหน้าโดเนทบนเว็บ",
            style=discord.ButtonStyle.link,
            url=web_url,
            emoji="🌐",
            row=0,
        ))

        for method_name in _enabled_methods(self.settings):
            self.add_item(DonateMethodButton(guild_id, method_name))

    @discord.ui.button(label="ส่งสลิป", style=discord.ButtonStyle.success, emoji="🧾", custom_id="donate:proof:web", row=0)
    async def donate_proof_web(self, interaction: discord.Interaction, _: discord.ui.Button):
        web_url = _public_donate_url(self.guild_id)
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="เปิดฟอร์มส่งสลิปบนเว็บ",
                style=discord.ButtonStyle.link,
                url=web_url,
                emoji="🌐",
            )
        )
        await interaction.response.send_message(
            "กดปุ่มด้านล่างเพื่อส่งสลิปหรือกรอกลิงก์อั่งเปาบนเว็บได้ทันที",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="ส่งลิงก์ของขวัญ", style=discord.ButtonStyle.secondary, emoji="🎁", custom_id="donate:gift:modal", row=0)
    async def donate_gift_link(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(DonateGiftLinkModal(guild_id=self.guild_id))

    @discord.ui.button(label="ดูรายละเอียดทั้งหมด", style=discord.ButtonStyle.primary, emoji="💬", custom_id="donate:chat:all", row=0)
    async def donate_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = cache.donate_settings_cache.get(str(self.guild_id))
        if not settings:
            await interaction.response.send_message("เซิร์ฟเวอร์นี้ยังไม่ได้ตั้งค่าระบบโดเนท", ephemeral=True)
            return

        embed = _build_all_methods_embed(settings)
        image_url, local_file = _resolve_image_asset(settings.get("image_url"))
        if image_url:
            embed.set_image(url=image_url)
        if local_file:
            await interaction.response.send_message(embed=embed, file=local_file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class DonateSlipReviewView(discord.ui.View):
    def __init__(
        self,
        *,
        guild_id: int,
        slip_id: str,
        transfer_link: str = "",
        proof_url: str = "",
    ):
        super().__init__(timeout=None)
        self.guild_id = int(guild_id)
        self.slip_id = str(slip_id)
        self.transfer_link = _normalize_external_link(transfer_link)
        self.proof_url = _normalize_external_link(proof_url)

        if self.proof_url:
            self.add_item(
                discord.ui.Button(
                    label="ดูสลิปการโอน",
                    style=discord.ButtonStyle.link,
                    url=self.proof_url,
                    row=1,
                )
            )
        if self.transfer_link:
            self.add_item(
                discord.ui.Button(
                    label="เปิด TrueMoney Gift Link",
                    style=discord.ButtonStyle.link,
                    url=self.transfer_link,
                    row=1,
                )
            )

    async def _apply(
        self,
        interaction: discord.Interaction,
        *,
        status: str,
        status_text: str,
        style: discord.ButtonStyle,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not member.guild_permissions.manage_guild:
            await interaction.response.send_message("ต้องมีสิทธิ์จัดการเซิร์ฟเวอร์เพื่ออัปเดตสถานะ", ephemeral=True)
            return

        ok = await _update_donate_slip_log_status(
            self.guild_id,
            self.slip_id,
            status,
            reviewer_id=str(member.id),
            reviewer_name=str(member.display_name or member.name),
        )
        if not ok:
            await interaction.response.send_message("ไม่พบรายการสลิปในระบบ หรืออัปเดตไม่สำเร็จ", ephemeral=True)
            return

        message = interaction.message
        embed = message.embeds[0].copy() if message and message.embeds else discord.Embed(title="หลักฐานโดเนท")
        updated = False
        for i, field in enumerate(embed.fields):
            if "สถานะ" in str(field.name):
                embed.set_field_at(i, name="สถานะการตรวจสอบ", value=status_text, inline=True)
                updated = True
                break
        if not updated:
            embed.add_field(name="สถานะการตรวจสอบ", value=status_text, inline=True)
        embed.color = {
            "approved": discord.Color.green(),
            "rejected": discord.Color.red(),
            "pending": discord.Color.gold(),
        }.get(status, embed.color)
        reviewer = f"{member.display_name} ({member.id})"
        embed.set_footer(text=f"อัปเดตโดย {reviewer} • slip:{self.slip_id[:10]}")

        new_view = DonateSlipReviewView(
            guild_id=self.guild_id,
            slip_id=self.slip_id,
            transfer_link=self.transfer_link,
            proof_url=self.proof_url,
        )
        for item in new_view.children:
            if not isinstance(item, discord.ui.Button):
                continue
            if item.style == discord.ButtonStyle.link or not item.custom_id:
                continue
            item.style = style if item.custom_id.endswith(f":{status}") else discord.ButtonStyle.secondary
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="ผ่าน", style=discord.ButtonStyle.success, custom_id="donate_slip_review:approved")
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._apply(interaction, status="approved", status_text="ผ่าน", style=discord.ButtonStyle.success)

    @discord.ui.button(label="ไม่ผ่าน", style=discord.ButtonStyle.danger, custom_id="donate_slip_review:rejected")
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._apply(interaction, status="rejected", status_text="ไม่ผ่าน", style=discord.ButtonStyle.danger)

    @discord.ui.button(label="รอตรวจ", style=discord.ButtonStyle.secondary, custom_id="donate_slip_review:pending")
    async def pending(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._apply(interaction, status="pending", status_text="รอตรวจ", style=discord.ButtonStyle.secondary)


async def publish_donate_panel_message(bot: commands.Bot, guild_id: int, settings: dict[str, Any]) -> tuple[bool, str]:
    if not bot:
        return False, "ไม่พบบอทใน runtime"
    if not settings or not settings.get("enabled"):
        return False, "ระบบโดเนทยังปิดใช้งาน"

    channel_id = str(settings.get("donation_channel_id") or "").strip()
    if not channel_id.isdigit():
        return False, "ยังไม่ได้ตั้งค่าห้องโดเนท"

    guild = bot.get_guild(guild_id)
    if guild is None:
        return False, "ไม่พบบอทในกิลด์นี้"

    channel = guild.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except Exception:
            channel = None
    if channel is None or not hasattr(channel, "send"):
        return False, "ไม่พบห้องโดเนทหรือบอทส่งข้อความไม่ได้"

    embed = _build_public_donate_embed(guild.name, settings)
    image_url, local_file = _resolve_image_asset(settings.get("image_url"))
    if image_url:
        embed.set_image(url=image_url)
    view = DonateView(guild_id, settings=settings)

    try:
        if local_file:
            await channel.send(embed=embed, view=view, file=local_file)
        else:
            await channel.send(embed=embed, view=view)
    except Exception as error:
        return False, f"ส่งข้อความโดเนทไม่สำเร็จ: {error}"

    return True, "ส่งข้อความโดเนทไปยังห้องที่ตั้งค่าแล้ว"


class Donate(commands.Cog):
    donate_group = app_commands.Group(
        name="donate",
        description="คำสั่งระบบโดเนท",
    )

    def __init__(self, bot):
        self.bot = bot

    @donate_group.command(name="show", description="สนับสนุนเซิร์ฟเวอร์และดูช่องทางโดเนท")
    async def donate_show(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        settings = cache.donate_settings_cache.get(str(guild_id))

        if not settings or not settings.get("enabled"):
            await interaction.response.send_message("ระบบโดเนทยังไม่ได้เปิดใช้งานในเซิร์ฟเวอร์นี้", ephemeral=True)
            return

        embed = _build_public_donate_embed(interaction.guild.name if interaction.guild else "SkyLineBOT", settings)
        image_url, local_file = _resolve_image_asset(settings.get("image_url"))
        if image_url:
            embed.set_image(url=image_url)

        view = DonateView(guild_id, settings=settings)
        if local_file:
            await interaction.response.send_message(embed=embed, view=view, file=local_file)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    @donate_group.command(name="qr", description="สร้างโค้ดชำระเงินตามช่องทางโดเนท")
    @app_commands.describe(amount="จำนวนเงินที่ต้องการ", method="ช่องทางที่ต้องการสร้าง")
    @app_commands.choices(
        method=[
            app_commands.Choice(name="พร้อมเพย์", value="promptpay"),
            app_commands.Choice(name="ทรูมันนี่วอลเล็ท", value="truemoney"),
            app_commands.Choice(name="ธนาคาร", value="bank"),
        ]
    )
    async def donate_qr(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 10000000],
        method: app_commands.Choice[str],
    ):
        if not interaction.guild_id:
            await interaction.response.send_message("ใช้คำสั่งนี้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        settings = await _get_donate_settings(interaction.guild_id)
        selected = str(method.value or "promptpay").strip().lower()
        methods = settings.get("methods_enabled") or {}
        embed = discord.Embed(color=_safe_color(settings.get("color")))
        embed.set_footer(text="หลังจากชำระแล้ว ให้ส่งหลักฐานเพื่อยืนยัน")

        if selected == "promptpay":
            number = str(settings.get("promptpay_number") or "").strip()
            if not methods.get("promptpay") or not number.isdigit():
                await interaction.response.send_message("เซิร์ฟเวอร์นี้ยังไม่ได้เปิดพร้อมเพย์หรือยังไม่ตั้งค่าเลขพร้อมเพย์", ephemeral=True)
                return
            qr_url = f"https://promptpay.io/{number}/{amount}.png"
            embed.title = "QR พร้อมเพย์"
            embed.description = f"จำนวนเงิน: **{amount:,} บาท**\\nสแกนเพื่อชำระได้ทันที"
            embed.add_field(name="หมายเลขพร้อมเพย์", value=f"`{number}`", inline=False)
            embed.set_image(url=qr_url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if selected == "truemoney":
            number = str(settings.get("truemoney_phone") or "").strip()
            if not methods.get("truemoney") or not number:
                await interaction.response.send_message("เซิร์ฟเวอร์นี้ยังไม่ได้เปิดทรูมันนี่วอลเล็ทหรือยังไม่ตั้งค่าเบอร์", ephemeral=True)
                return
            embed.title = "โอนผ่านทรูมันนี่วอลเล็ท"
            embed.description = f"เบอร์ทรูมันนี่วอลเล็ทสำหรับโอน:\\n`{number}`\\n\\nจำนวนที่ต้องการโอน: **{amount:,} บาท**"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        bank_name = str(settings.get("bank_name") or "").strip()
        bank_number = str(settings.get("bank_account_number") or "").strip()
        bank_owner = str(settings.get("bank_account_name") or "").strip()
        if not methods.get("bank") or not bank_name:
            await interaction.response.send_message("เซิร์ฟเวอร์นี้ยังไม่ได้เปิดโอนผ่านธนาคาร", ephemeral=True)
            return
        embed.title = "โอนผ่านธนาคาร"
        embed.description = (
            f"จำนวนเงินที่ต้องการโอน: **{amount:,} บาท**\n"
            f"ธนาคาร: **{bank_name or '-'}**\n"
            f"เลขบัญชี: `{bank_number or '-'}`\n"
            f"ชื่อบัญชี: **{bank_owner or '-'}**"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @donate_group.command(name="proof", description="ส่งหลักฐานโดเนท (สลิปหรือลิงก์อั่งเปา) ให้แอดมินตรวจ")
    @app_commands.describe(
        amount="จำนวนเงินที่โอน",
        method="ช่องทางที่ใช้โอน",
        transfer_link="ลิงก์อั่งเปา TrueMoney (ถ้ามี)",
        slip="ไฟล์สลิป (png/jpg/jpeg/webp)",
        note="ข้อความถึงเรา",
    )
    @app_commands.choices(
        method=[
            app_commands.Choice(name="ทรูมันนี่วอลเล็ท", value="truemoney"),
            app_commands.Choice(name="พร้อมเพย์", value="promptpay"),
            app_commands.Choice(name="ธนาคาร", value="bank"),
            app_commands.Choice(name="ตรวจสอบสลิป", value="slipverify"),
            app_commands.Choice(name="อื่น ๆ", value="other"),
        ]
    )
    async def donate_proof(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100000000],
        method: app_commands.Choice[str],
        transfer_link: Optional[str] = None,
        slip: Optional[discord.Attachment] = None,
        note: Optional[str] = None,
    ):
        if not interaction.guild or not interaction.guild_id:
            await interaction.response.send_message("ใช้คำสั่งนี้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)
            return

        settings = await _get_donate_settings(interaction.guild_id)
        enabled = bool(settings.get("enabled"))
        methods_enabled = settings.get("methods_enabled") or {}
        notify_channel_id = str(settings.get("notification_channel_id") or "").strip()
        if not enabled:
            await interaction.response.send_message("ระบบโดเนทของเซิร์ฟเวอร์นี้ยังไม่เปิดใช้งาน", ephemeral=True)
            return
        if not notify_channel_id.isdigit():
            await interaction.response.send_message("ยังไม่ได้ตั้งค่าห้องแจ้งเตือนการโดเนท", ephemeral=True)
            return

        payment_method = str(method.value or "other").strip().lower()
        if payment_method in {"truemoney", "promptpay", "bank", "slipverify"} and not methods_enabled.get(payment_method):
            await interaction.response.send_message("ช่องทางนี้ยังไม่ถูกเปิดใช้งานโดยผู้ดูแลเซิร์ฟเวอร์", ephemeral=True)
            return

        transfer_link = str(transfer_link or "").strip()
        if transfer_link and not _TRUEMONEY_GIFT_RE.match(transfer_link):
            await interaction.response.send_message(
                "ลิงก์อั่งเปาไม่ถูกต้อง (ต้องเป็น gift.truemoney.com/campaign/?v=...)",
                ephemeral=True,
            )
            return

        raw_bytes: bytes | None = None
        slip_asset_url = ""
        safe_name = ""
        if slip:
            filename = str(getattr(slip, "filename", "slip.png") or "slip.png")
            safe_name = _safe_upload_name(filename)
            if slip.size and slip.size > 10 * 1024 * 1024:
                await interaction.response.send_message("ไฟล์สลิปมีขนาดใหญ่เกิน 10MB", ephemeral=True)
                return
            try:
                raw_bytes = await slip.read()
            except Exception:
                raw_bytes = None
            if not raw_bytes:
                await interaction.response.send_message("ไม่สามารถอ่านไฟล์สลิปได้", ephemeral=True)
                return

        if not raw_bytes and not transfer_link:
            await interaction.response.send_message("กรุณาแนบสลิปหรือวางลิงก์อั่งเปาอย่างน้อย 1 อย่าง", ephemeral=True)
            return

        channel = interaction.guild.get_channel(int(notify_channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(notify_channel_id))
            except Exception:
                channel = None
        if channel is None or not hasattr(channel, "send"):
            await interaction.response.send_message("ไม่พบห้องแจ้งเตือนการโดเนท หรือบอทไม่มีสิทธิ์ส่งข้อความ", ephemeral=True)
            return

        auto_status, auto_note = await _auto_verify_donate_evidence(
            settings=settings,
            payment_method=payment_method,
            amount=int(amount),
            image_url=slip_asset_url,
            raw_bytes=raw_bytes,
            filename=safe_name or "slip.png",
            transfer_link=transfer_link,
        )

        slip_id = uuid.uuid4().hex
        donor_name = str(getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "Unknown"))
        embed = discord.Embed(
            title="แจ้งหลักฐานการโดเนท",
            color=_safe_color(settings.get("color")),
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        embed.add_field(name="ผู้โอน", value=f"{interaction.user.mention} ({donor_name})", inline=False)
        embed.add_field(name="จำนวนเงิน", value=f"{int(amount):,} บาท", inline=True)
        embed.add_field(name="ช่องทาง", value=payment_method, inline=True)
        embed.add_field(name="สถานะตรวจอัตโนมัติ", value=_donate_slip_status_label(auto_status), inline=True)
        if transfer_link:
            embed.add_field(name="ลิงก์อั่งเปา/ลิงก์อ้างอิง", value=transfer_link[:1024], inline=False)
        if note:
            embed.add_field(name="ข้อความถึงเรา", value=str(note).strip()[:1024], inline=False)
        if auto_note:
            embed.add_field(name="หมายเหตุการตรวจ", value=auto_note[:1024], inline=False)
        embed.set_footer(text=f"กิลด์ ID: {interaction.guild_id} • slip:{slip_id[:10]}")

        sent_message_id = ""
        review_view = DonateSlipReviewView(
            guild_id=interaction.guild_id,
            slip_id=slip_id,
            transfer_link=transfer_link,
        )
        discord_file = None
        if raw_bytes:
            attachment_name = f"donate_slip_{safe_name or 'proof.png'}"
            discord_file = discord.File(io.BytesIO(raw_bytes), filename=attachment_name)
            embed.set_image(url=f"attachment://{attachment_name}")
        try:
            if discord_file:
                sent = await channel.send(embed=embed, file=discord_file, view=review_view)
            else:
                sent = await channel.send(embed=embed, view=review_view)
            sent_message_id = str(getattr(sent, "id", "") or "")
            if discord_file:
                sent_attachments = list(getattr(sent, "attachments", []) or [])
                if sent_attachments:
                    slip_asset_url = str(getattr(sent_attachments[0], "url", "") or "").strip()
            if transfer_link or slip_asset_url:
                try:
                    enriched_view = DonateSlipReviewView(
                        guild_id=interaction.guild_id,
                        slip_id=slip_id,
                        transfer_link=transfer_link,
                        proof_url=slip_asset_url,
                    )
                    await sent.edit(view=enriched_view)
                except Exception:
                    pass
        except Exception:
            await interaction.response.send_message("ส่งหลักฐานไปห้องแจ้งเตือนไม่สำเร็จ กรุณาแจ้งแอดมินตรวจสอบสิทธิ์บอท", ephemeral=True)
            return

        await _append_donate_slip_log(
            interaction.guild_id,
            {
                "slip_id": slip_id,
                "created_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                "status": auto_status,
                "donor_name": donor_name,
                "amount": int(amount),
                "payment_method": payment_method,
                "message": f"{str(note or '').strip()}\n{('ลิงก์: ' + transfer_link) if transfer_link else ''}".strip(),
                "image_url": slip_asset_url,
                "discord_channel_id": str(notify_channel_id),
                "discord_message_id": sent_message_id,
                "reviewed_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat() if auto_status != "pending" else "",
                "reviewed_by_id": "system" if auto_status != "pending" else "",
                "reviewed_by_name": "Auto Verify" if auto_status != "pending" else "",
            },
        )

        await interaction.response.send_message(
            f"ส่งหลักฐานเรียบร้อยแล้ว • สถานะตอนนี้: **{_donate_slip_status_label(auto_status)}**",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Donate(bot))


