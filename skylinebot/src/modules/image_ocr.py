import asyncio
import io
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

from skylinebot.console.logging import logger
from skylinebot.memory.cache import cache
from skylinebot.style import color
from skylinebot.bridge.storage import get_collection
from storage import image_ocr_settings as db

# {guild_id: {user_id: count}}
user_image_submissions = defaultdict(lambda: defaultdict(int))
# {guild_id: {user_id: last_award_datetime}}
user_last_reset = defaultdict(dict)
_ocr_capability_logged = False


class OcrUserNoticeView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=900)
        self.owner_id = int(owner_id)

    @discord.ui.button(label="ปิดข้อความ", style=discord.ButtonStyle.secondary, custom_id="ocr_notice_dismiss")
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("ข้อความนี้สำหรับผู้ส่งรูปเท่านั้น", ephemeral=True)
            return
        try:
            await interaction.message.delete()
        except Exception:
            await interaction.response.send_message("ปิดข้อความไม่สำเร็จ", ephemeral=True)


def _is_atlas_collection_limit_error(error: Exception) -> bool:
    text = str(error or "").lower()
    return (
        "cannot create a new collection" in text and "500 collections" in text
    ) or ("atlaserror" in text and "8000" in text)


def _normalize_settings(payload: dict | None) -> dict:
    src = payload or {}
    keywords = src.get("keywords")
    if not isinstance(keywords, list):
        keywords = ["Following", "Shared", "Subscribed", "ติดตาม", "แชร์", "สมัคร"]
    cleaned_keywords = [str(item).strip() for item in keywords if str(item).strip()]
    if not cleaned_keywords:
        cleaned_keywords = ["Following", "Shared", "Subscribed", "ติดตาม", "แชร์", "สมัคร"]
    try:
        required = int(src.get("required_image_count") or src.get("image_count") or 1)
    except (TypeError, ValueError):
        required = 1
    required = max(1, min(10, required))
    return {
        "id": src.get("id"),
        "guild_id": src.get("guild_id"),
        "enabled": bool(src.get("enabled")),
        "target_channel_id": str(src.get("target_channel_id") or "").strip() or None,
        "admin_channel_id": str(src.get("admin_channel_id") or "").strip() or None,
        "notification_channel_id": str(src.get("notification_channel_id") or "").strip() or None,
        "webhook_url": str(src.get("webhook_url") or "").strip() or None,
        "notify_embed_title": str(src.get("notify_embed_title") or "ตรวจพบข้อความจากรูปภาพ").strip()[:120],
        "notify_embed_description": str(
            src.get("notify_embed_description")
            or "พบคีย์เวิร์ด: {keywords}\nผู้ใช้: {user_mention}\nจำนวนรูปสะสม: {current_count}/{required_count}"
        ).strip()[:4000],
        "notify_embed_image_url": str(src.get("notify_embed_image_url") or "").strip() or None,
        "required_image_count": required,
        "image_count": required,
        "reward_role_id": str(src.get("reward_role_id") or "").strip() or None,
        "keywords": cleaned_keywords,
    }


class ImageOCR(commands.Cog):
    ocr_group = app_commands.Group(
        name="ocr",
        description="จัดการและตรวจสอบ OCR",
    )

    def __init__(self, bot):
        self.bot = bot
        self._cloud_ocr_url = os.getenv("OCR_SPACE_API_URL", "https://api.ocr.space/parse/image").strip()
        self._cloud_ocr_key = os.getenv("OCR_SPACE_API_KEY", "helloworld").strip()
        self._cloud_ocr_lang = os.getenv("OCR_SPACE_LANG", "auto").strip().lower() or "auto"
        self._local_tesseract_lang = os.getenv("OCR_TESSERACT_LANG", "tha+eng").strip() or "tha+eng"
        # OCR.Space does not accept multi-language combinations like "tha+eng".
        # For mixed Thai/English images we should use language autodetect.
        if self._cloud_ocr_lang in {"tha+eng", "eng+tha", "tha,eng", "eng,tha"}:
            self._cloud_ocr_lang = "auto"

    async def _load_fallback_settings(self, guild_id: int) -> dict:
        try:
            guilds_col = await get_collection("guilds")
            doc = await guilds_col.find_one({"guild_id": guild_id}, {"image_ocr_settings_fallback": 1, "_id": 0})
            payload = (doc or {}).get("image_ocr_settings_fallback")
            if isinstance(payload, dict):
                return _normalize_settings(payload)
        except Exception:
            pass
        return {}

    async def _save_fallback_settings(self, guild_id: int, payload: dict) -> dict:
        normalized = _normalize_settings({**(payload or {}), "guild_id": guild_id})
        try:
            guilds_col = await get_collection("guilds")
            await guilds_col.update_one(
                {"guild_id": guild_id},
                {"$set": {"image_ocr_settings_fallback": normalized}},
                upsert=True,
            )
        except Exception:
            pass
        return normalized

    async def _get_effective_settings(self, guild_id: int) -> dict:
        settings = cache.image_ocr_cache.get(str(guild_id))
        if settings:
            return _normalize_settings(settings)
        try:
            settings = await db.get(guild_id)
            if settings:
                normalized = _normalize_settings(settings)
                cache.image_ocr_cache[str(guild_id)] = normalized
                return normalized
        except Exception:
            pass
        fallback = await self._load_fallback_settings(guild_id)
        if fallback:
            cache.image_ocr_cache[str(guild_id)] = fallback
        return fallback

    def _can_use_local_tesseract(self) -> bool:
        if not pytesseract:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    async def _ocr_with_ocr_space(self, image_bytes: bytes) -> str:
        if not self._cloud_ocr_url:
            return ""
        form = aiohttp.FormData()
        form.add_field("apikey", self._cloud_ocr_key or "helloworld")
        form.add_field("language", self._cloud_ocr_lang)
        form.add_field("OCREngine", "2")
        form.add_field("isOverlayRequired", "false")
        form.add_field("scale", "true")
        form.add_field("file", image_bytes, filename="ocr-image.png", content_type="application/octet-stream")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self._cloud_ocr_url, data=form, timeout=25) as response:
                    if response.status >= 400:
                        logger.warning(f"OCR.Space HTTP {response.status}")
                        return ""
                    payload = await response.json(content_type=None)
        except Exception as error:
            logger.warning(f"OCR.Space request failed: {error}")
            return ""

        parsed_results = payload.get("ParsedResults") if isinstance(payload, dict) else None
        if not isinstance(parsed_results, list):
            return ""
        parts = []
        for item in parsed_results:
            if not isinstance(item, dict):
                continue
            txt = str(item.get("ParsedText") or "").strip()
            if txt:
                parts.append(txt)
        return "\n".join(parts).strip()

    async def get_ocr_text(self, image_bytes: bytes) -> tuple[str, str]:
        global _ocr_capability_logged
        if self._can_use_local_tesseract():
            try:
                image = Image.open(io.BytesIO(image_bytes))
                return pytesseract.image_to_string(image, lang=self._local_tesseract_lang), "local_tesseract"
            except Exception as error:
                logger.error(f"OCR Local Error: {error}")
        else:
            if not _ocr_capability_logged:
                _ocr_capability_logged = True
                logger.warning("ไม่พบ Tesseract ในเครื่อง กำลังใช้ OCR.Space แทน")

        text = await self._ocr_with_ocr_space(image_bytes)
        if text:
            return text, "ocr_space"
        return "", "none"

    def _build_notify_embed(
        self,
        *,
        settings: dict,
        message: discord.Message,
        found_keywords: list[str],
        current_count: int,
        required_count: int,
        reward_role_id: Optional[str],
        attachment_url: str,
    ) -> discord.Embed:
        title = str(settings.get("notify_embed_title") or "ตรวจพบข้อความจากรูปภาพ")[:120]
        description_tpl = str(
            settings.get("notify_embed_description")
            or "พบคีย์เวิร์ด: {keywords}\nผู้ใช้: {user_mention}\nจำนวนรูปสะสม: {current_count}/{required_count}"
        )
        description = (
            description_tpl.replace("{keywords}", ", ".join(found_keywords) or "-")
            .replace("{user_mention}", message.author.mention)
            .replace("{current_count}", str(current_count))
            .replace("{required_count}", str(required_count))
            .replace("{reward_role}", f"<@&{reward_role_id}>" if reward_role_id else "-")
        )[:4000]

        embed = discord.Embed(title=title, description=description, color=color.green)
        image_url = str(settings.get("notify_embed_image_url") or "").strip() or attachment_url
        if image_url:
            embed.set_image(url=image_url)
        return embed

    async def _send_webhook_notification(
        self, *, webhook_url: Optional[str], content: str, embed: discord.Embed
    ) -> None:
        url = str(webhook_url or "").strip()
        if not url:
            return
        payload = {"content": content[:1800], "embeds": [embed.to_dict()]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=15) as response:
                    if response.status >= 400:
                        logger.warning(f"OCR webhook notify failed with status {response.status}")
        except Exception as error:
            logger.warning(f"OCR webhook notify error: {error}")

    async def _send_user_feedback(
        self,
        *,
        message: discord.Message,
        text: str,
        attachment_url: Optional[str] = None,
    ) -> None:
        notice = str(text or "").strip()
        if not notice:
            return
        embed = discord.Embed(
            description=notice[:3500],
            color=color.yellow,
        )
        embed.set_footer(text="กดปุ่ม 'ปิดข้อความ' เพื่อซ่อนข้อความนี้ได้")
        if attachment_url:
            embed.set_image(url=attachment_url)
        try:
            await message.reply(
                embed=embed,
                view=OcrUserNoticeView(owner_id=message.author.id),
                mention_author=False,
            )
        except Exception as error:
            logger.warning(
                f"ไม่สามารถส่งข้อความ OCR ในแชทได้ | guild={getattr(message.guild, 'id', 'dm')} user={message.author.id} error={error}"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        settings = await self._get_effective_settings(message.guild.id)
        if not settings or not settings.get("enabled"):
            return
        if not message.attachments:
            return

        target_channel_id = settings.get("target_channel_id")
        if target_channel_id and str(message.channel.id) != str(target_channel_id):
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)

        for attachment in message.attachments:
            if not any(
                attachment.filename.lower().endswith(ext)
                for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"]
            ):
                continue

            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as response:
                    if response.status != 200:
                        continue
                    image_data = await response.read()

            text, ocr_source = await self.get_ocr_text(image_data)
            if not text:
                logger.warning(
                    f"OCR ไม่สามารถอ่านข้อความจากรูปได้ | guild={message.guild.id} user={message.author.id} file={attachment.filename} source={ocr_source}"
                )
                await self._send_user_feedback(
                    message=message,
                    text=(
                        "ไม่สามารถอ่านข้อความจากรูปนี้ได้\n"
                        "สาเหตุที่เป็นไปได้: รูปไม่ชัด/ตัวอักษรเล็กเกินไป/แสงน้อย/ไม่มีข้อความ\n"
                        "กรุณาส่งรูปใหม่ที่ชัดขึ้น หรือครอปเฉพาะส่วนข้อความที่ต้องการตรวจ"
                    ),
                    attachment_url=attachment.url,
                )
                admin_channel_id = settings.get("admin_channel_id")
                admin_channel = (
                    message.guild.get_channel(int(admin_channel_id))
                    if str(admin_channel_id or "").isdigit()
                    else None
                )
                if admin_channel:
                    fail_embed = discord.Embed(
                        title="ไม่สามารถอ่านข้อความจากรูปได้",
                        description=(
                            f"ผู้ส่ง: {message.author.mention}\n"
                            f"ไฟล์: `{attachment.filename}`\n"
                            f"แหล่ง OCR: `{ocr_source}`\n"
                            f"สรุป: OCR อ่านข้อความไม่ออกหรือไม่พบข้อความในภาพ"
                        ),
                        color=color.red,
                    )
                    fail_embed.set_image(url=attachment.url)
                    await admin_channel.send(embed=fail_embed)
                continue

            keywords = settings.get("keywords", [])
            found_keywords = [kw for kw in keywords if kw.lower() in text.lower()]
            logger.info(
                f"OCR processed | guild={message.guild.id} user={message.author.id} source={ocr_source} keywords_hit={len(found_keywords)} file={attachment.filename}"
            )

            if found_keywords:
                required_count = int(settings.get("required_image_count", 1) or 1)
                required_count = max(1, min(10, required_count))

                # Reset counter after 24h from last successful reward
                last_award = user_last_reset[guild_id].get(
                    user_id, datetime.now() - timedelta(hours=25)
                )
                if datetime.now() - last_award > timedelta(hours=24):
                    user_image_submissions[guild_id][user_id] = 0

                user_image_submissions[guild_id][user_id] += 1
                current_count = user_image_submissions[guild_id][user_id]

                if current_count < required_count:
                    continue

                reward_role_id = str(settings.get("reward_role_id") or "").strip() or None
                if reward_role_id and reward_role_id.isdigit():
                    role = message.guild.get_role(int(reward_role_id))
                    if role:
                        try:
                            await message.author.add_roles(
                                role, reason="OCR Image verification rewarded"
                            )
                        except Exception as error:
                            logger.error(f"Failed to add role: {error}")

                embed = self._build_notify_embed(
                    settings=settings,
                    message=message,
                    found_keywords=found_keywords,
                    current_count=current_count,
                    required_count=required_count,
                    reward_role_id=reward_role_id,
                    attachment_url=attachment.url,
                )
                notify_content = f"✅ OCR ตรวจพบคีย์เวิร์ดจาก {message.author.mention}"

                target_channel = (
                    message.guild.get_channel(int(target_channel_id))
                    if str(target_channel_id or "").isdigit()
                    else None
                )
                notification_channel_id = settings.get("notification_channel_id")
                notification_channel = (
                    message.guild.get_channel(int(notification_channel_id))
                    if str(notification_channel_id or "").isdigit()
                    else None
                )
                destination = notification_channel or target_channel
                if destination:
                    try:
                        await destination.send(content=notify_content, embed=embed)
                    except Exception as error:
                        logger.error(f"Failed to send OCR notification: {error}")

                await self._send_webhook_notification(
                    webhook_url=settings.get("webhook_url"),
                    content=notify_content,
                    embed=embed,
                )

                user_image_submissions[guild_id][user_id] = 0
                user_last_reset[guild_id][user_id] = datetime.now()
            else:
                await self._send_user_feedback(
                    message=message,
                    text=(
                        "OCR อ่านรูปได้แล้ว แต่ไม่พบคีย์เวิร์ดที่ตั้งค่าไว้\n"
                        "ระบบได้ส่งให้แอดมินตรวจสอบเพิ่มเติมแล้ว"
                    ),
                    attachment_url=attachment.url,
                )
                admin_channel_id = settings.get("admin_channel_id")
                admin_channel = (
                    message.guild.get_channel(int(admin_channel_id))
                    if str(admin_channel_id or "").isdigit()
                    else None
                )
                if admin_channel:
                    view = VerificationView(
                        author_id=message.author.id,
                        image_url=attachment.url,
                        target_channel_id=settings.get("target_channel_id"),
                    )
                    embed = discord.Embed(
                        title="ต้องตรวจสอบรูปภาพด้วยตนเอง (ไม่พบคีย์เวิร์ด)",
                        description=(
                            f"ไม่พบคีย์เวิร์ดที่กำหนด แต่รูปอาจถูกต้อง\n"
                            f"ผู้ส่ง: {message.author.mention}\n"
                            f"ข้อความที่ OCR อ่านได้ (ย่อ):\n```{text[:500]}```"
                        ),
                        color=color.yellow,
                    )
                    embed.set_image(url=attachment.url)
                    await admin_channel.send(embed=embed, view=view)

    @ocr_group.command(
        name="setup", description="ตั้งค่าระบบตรวจสอบรูปภาพอัตโนมัติ"
    )
    @app_commands.describe(
        enabled="เปิดหรือปิดระบบ",
        target_channel="ห้องที่ให้ผู้ใช้ส่งรูปตรวจสอบ",
        admin_channel="ห้องสำหรับแอดมินตรวจสอบด้วยตนเอง",
        notification_channel="ห้องที่บอทแจ้งผลการตรวจสอบ",
    )
    @commands.has_permissions(administrator=True)
    async def ocr_setup(
        self,
        interaction: discord.Interaction,
        enabled: bool = None,
        target_channel: discord.TextChannel = None,
        admin_channel: discord.TextChannel = None,
        notification_channel: discord.TextChannel = None,
    ):
        guild_id = interaction.guild_id
        settings = await self._get_effective_settings(guild_id)

        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if target_channel:
            updates["target_channel_id"] = str(target_channel.id)
        if admin_channel:
            updates["admin_channel_id"] = str(admin_channel.id)
        if notification_channel:
            updates["notification_channel_id"] = str(notification_channel.id)

        try:
            if settings and settings.get("id"):
                await db.update(settings["id"], **updates)
            elif settings:
                merged = {**settings, **updates}
                await self._save_fallback_settings(guild_id, merged)
                cache.image_ocr_cache[str(guild_id)] = _normalize_settings(merged)
                return await interaction.response.send_message("✅ อัปเดตการตั้งค่า OCR เรียบร้อยแล้ว", ephemeral=True)
            else:
                await db.insert(guild_id=guild_id, **updates)
            latest = await db.get(guild_id)
            if latest:
                cache.image_ocr_cache[str(guild_id)] = _normalize_settings(latest)
        except Exception as error:
            if not _is_atlas_collection_limit_error(error):
                raise
            merged = {**settings, **updates} if settings else {"guild_id": guild_id, **updates}
            saved = await self._save_fallback_settings(guild_id, merged)
            cache.image_ocr_cache[str(guild_id)] = saved

        await interaction.response.send_message("✅ อัปเดตการตั้งค่า OCR เรียบร้อยแล้ว", ephemeral=True)

    @ocr_group.command(name="keywords", description="จัดการคีย์เวิร์ดของ OCR")
    @app_commands.describe(action="เพิ่ม/ลบ", keyword="คีย์เวิร์ดที่ต้องการจัดการ")
    @commands.has_permissions(administrator=True)
    async def ocr_keywords(self, interaction: discord.Interaction, action: str, keyword: str):
        action_normalized = str(action or "").lower().strip()
        if action_normalized not in {"add", "remove", "เพิ่ม", "ลบ"}:
            return await interaction.response.send_message(
                "❌ action ต้องเป็น เพิ่ม/ลบ (หรือ เพิ่ม/ลบ)", ephemeral=True
            )

        guild_id = interaction.guild_id
        settings = await self._get_effective_settings(guild_id)
        if not settings:
            return await interaction.response.send_message(
                "❌ กรุณาตั้งค่า OCR ก่อนด้วย /ocr setup", ephemeral=True
            )

        keywords = settings.get("keywords", [])
        if action_normalized in {"add", "เพิ่ม"}:
            if keyword not in keywords:
                keywords.append(keyword)
                try:
                    if settings.get("id"):
                        await db.update(settings["id"], keywords=keywords)
                    else:
                        await self._save_fallback_settings(guild_id, {**settings, "keywords": keywords})
                except Exception as error:
                    if not _is_atlas_collection_limit_error(error):
                        raise
                    await self._save_fallback_settings(guild_id, {**settings, "keywords": keywords})
                settings["keywords"] = keywords
                cache.image_ocr_cache[str(guild_id)] = _normalize_settings(settings)
                await interaction.response.send_message(
                    f"✅ เพิ่มคีย์เวิร์ด `{keyword}` แล้ว", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"⚠️ มีคีย์เวิร์ด `{keyword}` อยู่แล้ว", ephemeral=True
                )
        else:
            if keyword in keywords:
                keywords.remove(keyword)
                try:
                    if settings.get("id"):
                        await db.update(settings["id"], keywords=keywords)
                    else:
                        await self._save_fallback_settings(guild_id, {**settings, "keywords": keywords})
                except Exception as error:
                    if not _is_atlas_collection_limit_error(error):
                        raise
                    await self._save_fallback_settings(guild_id, {**settings, "keywords": keywords})
                settings["keywords"] = keywords
                cache.image_ocr_cache[str(guild_id)] = _normalize_settings(settings)
                await interaction.response.send_message(
                    f"✅ ลบคีย์เวิร์ด `{keyword}` แล้ว", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"⚠️ ไม่พบคีย์เวิร์ด `{keyword}`", ephemeral=True
                )

    @ocr_group.command(name="check", description="ตรวจรูปแบบส่วนตัว (เห็นเฉพาะคุณ)")
    @app_commands.describe(image="รูปภาพที่ต้องการให้ OCR อ่าน", check_keywords="ให้ตรวจคีย์เวิร์ดที่ตั้งค่าไว้ด้วยหรือไม่")
    async def ocr_check(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        check_keywords: bool = True,
    ):
        if not interaction.guild:
            return await interaction.response.send_message("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์", ephemeral=True)

        settings = await self._get_effective_settings(interaction.guild.id)
        if not settings or not settings.get("enabled"):
            return await interaction.response.send_message("ระบบ OCR ของเซิร์ฟเวอร์นี้ยังไม่เปิดใช้งาน", ephemeral=True)

        filename = str(image.filename or "").lower()
        if not any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"]):
            return await interaction.response.send_message("รองรับเฉพาะไฟล์รูปภาพเท่านั้น", ephemeral=True)

        try:
            image_data = await image.read()
        except Exception:
            return await interaction.response.send_message("ไม่สามารถอ่านไฟล์รูปภาพได้", ephemeral=True)

        text, ocr_source = await self.get_ocr_text(image_data)
        if not text:
            embed = discord.Embed(
                description=(
                    "ไม่สามารถอ่านข้อความจากรูปนี้ได้\n"
                    "สาเหตุที่เป็นไปได้: รูปไม่ชัด/ตัวอักษรเล็กเกินไป/แสงน้อย/ไม่มีข้อความ\n"
                    "กรุณาส่งรูปใหม่ที่ชัดขึ้น หรือครอปเฉพาะส่วนข้อความที่ต้องการตรวจ"
                ),
                color=color.yellow,
            )
            embed.set_image(url=image.url)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        preview = text[:1700] if len(text) > 1700 else text
        if check_keywords:
            keywords = settings.get("keywords", [])
            found_keywords = [kw for kw in keywords if kw.lower() in text.lower()]
            if found_keywords:
                embed = discord.Embed(
                    description=(
                        f"อ่านรูปสำเร็จ และพบคีย์เวิร์ด: {', '.join(found_keywords)}\n"
                        f"แหล่ง OCR: `{ocr_source}`\n\n"
                        f"ข้อความที่อ่านได้ (ย่อ):\n```{preview}```"
                    )[:3800],
                    color=color.green,
                )
                embed.set_image(url=image.url)
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            embed = discord.Embed(
                description=(
                    f"อ่านรูปสำเร็จ แต่ยังไม่พบคีย์เวิร์ดที่ตั้งค่าไว้\n"
                    f"แหล่ง OCR: `{ocr_source}`\n\n"
                    f"ข้อความที่อ่านได้ (ย่อ):\n```{preview}```"
                )[:3800],
                color=color.yellow,
            )
            embed.set_image(url=image.url)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            description=(
                f"อ่านรูปสำเร็จ\n"
                f"แหล่ง OCR: `{ocr_source}`\n\n"
                f"ข้อความที่อ่านได้ (ย่อ):\n```{preview}```"
            )[:3800],
            color=color.green,
        )
        embed.set_image(url=image.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class VerificationView(discord.ui.View):
    def __init__(self, author_id: int, image_url: str, target_channel_id: Optional[str]):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.image_url = image_url
        self.target_channel_id = target_channel_id

    async def _get_effective_settings(self, guild_id: int) -> dict:
        settings = cache.image_ocr_cache.get(str(guild_id))
        if settings:
            return _normalize_settings(settings)
        try:
            settings = await db.get(guild_id)
            if settings:
                normalized = _normalize_settings(settings)
                cache.image_ocr_cache[str(guild_id)] = normalized
                return normalized
        except Exception:
            pass
        try:
            guilds_col = await get_collection("guilds")
            doc = await guilds_col.find_one(
                {"guild_id": guild_id},
                {"image_ocr_settings_fallback": 1, "_id": 0},
            )
            payload = (doc or {}).get("image_ocr_settings_fallback")
            if isinstance(payload, dict):
                normalized = _normalize_settings(payload)
                cache.image_ocr_cache[str(guild_id)] = normalized
                return normalized
        except Exception:
            pass
        return {}

    @discord.ui.button(label="อนุมัติ (Approve)", style=discord.ButtonStyle.green, custom_id="ocr_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await self._get_effective_settings(interaction.guild.id)
        reward_role_id = str(settings.get("reward_role_id") or "").strip()

        if reward_role_id.isdigit():
            role = interaction.guild.get_role(int(reward_role_id))
            member = interaction.guild.get_member(self.author_id)
            if role and member:
                try:
                    await member.add_roles(role)
                except Exception:
                    pass

        channel_id = settings.get("notification_channel_id") or self.target_channel_id
        destination = (
            interaction.guild.get_channel(int(channel_id))
            if str(channel_id or "").isdigit()
            else None
        )
        if destination:
            embed = discord.Embed(
                title="✅ อนุมัติรูปภาพด้วยตนเอง",
                description=(
                    f"ผู้อนุมัติ: {interaction.user.mention}\n"
                    f"ผู้ส่ง: <@{self.author_id}>"
                    + (f"\nยศที่ได้รับ: <@&{reward_role_id}>" if reward_role_id.isdigit() else "")
                ),
                color=color.green,
            )
            embed.set_image(url=self.image_url)
            await destination.send(embed=embed)

        await interaction.response.edit_message(content="✅ อนุมัติเรียบร้อยแล้ว", view=None, embed=interaction.message.embeds[0])

    @discord.ui.button(label="ปฏิเสธ (Reject)", style=discord.ButtonStyle.red, custom_id="ocr_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ ปฏิเสธรูปภาพนี้แล้ว", view=None, embed=interaction.message.embeds[0])


async def setup(bot):
    await bot.add_cog(ImageOCR(bot))

