from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import discord
from discord.ext import commands

from skylinebot.memory.cache import cache


DEFAULT_LANG = "th"
SUPPORTED_LANGS = {"th", "en"}
# Enable runtime localization wrappers for all command responses (TH/EN).
AUTO_TRANSLATION_ENABLED = True


def _safe_float_env(name: str, default: float) -> float:
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        return float(raw)
    except Exception:
        return float(default)


def _safe_int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        return int(raw)
    except Exception:
        return int(default)


def _safe_bool_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, str(default)) or str(default)).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)

_AIFORTHAI_TRANSLATION_ENABLED = str(
    os.getenv("AIFORTHAI_TRANSLATION_ENABLED", "1")
).strip().lower() in {"1", "true", "yes", "on"}
_AIFORTHAI_API_KEY = str(os.getenv("AIFORTHAI_API_KEY", "") or "").strip()
_AIFORTHAI_API_KEY_HEADER = (
    str(os.getenv("AIFORTHAI_API_KEY_HEADER", "Apikey") or "Apikey").strip()
    or "Apikey"
)
_AIFORTHAI_USE_BEARER_AUTH = str(
    os.getenv("AIFORTHAI_USE_BEARER_AUTH", "0")
).strip().lower() in {"1", "true", "yes", "on"}
_AIFORTHAI_TIMEOUT_SECONDS = max(
    0.2, min(6.0, _safe_float_env("AIFORTHAI_TRANSLATION_TIMEOUT_SECONDS", 1.6))
)
_AIFORTHAI_MAX_TEXT_LENGTH = 1000
_AIFORTHAI_TRANSLATE_EN2TH_URL = str(
    os.getenv("AIFORTHAI_TRANSLATE_EN2TH_URL", "https://api.aiforthai.in.th/xiaofan-en-th/en2th")
    or "https://api.aiforthai.in.th/xiaofan-en-th/en2th"
).strip()
_AIFORTHAI_TRANSLATE_TH2EN_URL = str(
    os.getenv("AIFORTHAI_TRANSLATE_TH2EN_URL", "https://api.aiforthai.in.th/xiaofan-en-th/th2en")
    or "https://api.aiforthai.in.th/xiaofan-en-th/th2en"
).strip()
_AIFORTHAI_TRANSLATION_CACHE_LIMIT = max(
    64, min(8192, _safe_int_env("AIFORTHAI_TRANSLATION_CACHE_LIMIT", 1024))
)
_AIFORTHAI_CACHE_LOCK = threading.Lock()
_AIFORTHAI_TRANSLATION_CACHE: dict[tuple[str, str], str] = {}

_I18N_GOOGLE_RUNTIME_FALLBACK_ENABLED = _safe_bool_env(
    "I18N_GOOGLE_RUNTIME_FALLBACK_ENABLED", False
)
_I18N_GOOGLE_RUNTIME_MAX_TEXT_LENGTH = max(
    200, min(4500, _safe_int_env("I18N_GOOGLE_RUNTIME_MAX_TEXT_LENGTH", 1200))
)
_I18N_GOOGLE_RUNTIME_MIN_TEXT_LENGTH = max(
    4, min(48, _safe_int_env("I18N_GOOGLE_RUNTIME_MIN_TEXT_LENGTH", 8))
)
_I18N_GOOGLE_RUNTIME_CACHE_LIMIT = max(
    64, min(8192, _safe_int_env("I18N_GOOGLE_RUNTIME_CACHE_LIMIT", 1024))
)
_I18N_GOOGLE_CACHE_LOCK = threading.Lock()
_I18N_GOOGLE_TRANSLATOR_CACHE: dict[str, Any] = {}
_I18N_GOOGLE_RUNTIME_CACHE: dict[tuple[str, str], str] = {}
_I18N_GOOGLE_RUNTIME_CACHE_ORDER: list[tuple[str, str]] = []

# Translation flow:
# 1) Prefer explicit locale dictionaries/mapping.
# 2) Use external translation fallback only for unresolved cross-language text.
_I18N_FILE_FIRST_MODE = _safe_bool_env("I18N_FILE_FIRST_MODE", True)
_I18N_RULE_BASED_RUNTIME_TRANSLATION_ENABLED = _safe_bool_env(
    "I18N_RULE_BASED_RUNTIME_TRANSLATION_ENABLED", False
)
_I18N_HEURISTIC_COMMAND_FALLBACK_ENABLED = _safe_bool_env(
    "I18N_HEURISTIC_COMMAND_FALLBACK_ENABLED", False
)
_I18N_AI_RUNTIME_FALLBACK_ENABLED = _safe_bool_env(
    "I18N_AI_RUNTIME_FALLBACK_ENABLED", False
)
# Strict mode enforces single-language responses (TH or EN) by enabling
# runtime rule/heuristic/AI fallback even when legacy flags are off.
_I18N_STRICT_LANGUAGE_MODE_ENABLED = _safe_bool_env(
    "I18N_STRICT_LANGUAGE_MODE_ENABLED", False
)
_I18N_STRICT_PROVIDER_FALLBACK_ENABLED = _safe_bool_env(
    "I18N_STRICT_PROVIDER_FALLBACK_ENABLED", False
)
_I18N_PROVIDER_FALLBACK_MAX_TEXT_LENGTH = max(
    40, min(4000, _safe_int_env("I18N_PROVIDER_FALLBACK_MAX_TEXT_LENGTH", 280))
)
_I18N_RUNTIME_TRANSLATION_CACHE_LIMIT = max(
    128, min(32768, _safe_int_env("I18N_RUNTIME_TRANSLATION_CACHE_LIMIT", 4096))
)
_I18N_RUNTIME_TRANSLATION_CACHE_MAX_TEXT_LENGTH = max(
    24, min(8000, _safe_int_env("I18N_RUNTIME_TRANSLATION_CACHE_MAX_TEXT_LENGTH", 1200))
)
_I18N_RUNTIME_CACHE_LOCK = threading.Lock()
_I18N_RUNTIME_TRANSLATION_CACHE: dict[tuple[str, str], str] = {}
_I18N_RUNTIME_TRANSLATION_CACHE_ORDER: list[tuple[str, str]] = []

TH_COMMAND_TEXT_OVERRIDES: dict[str, str] = {
    "Enable/Disable AutoMod system or edit settings": "เปิด/ปิดระบบ AutoMod หรือแก้ไขการตั้งค่า",
    "Enable AutoMod system": "เปิดระบบ AutoMod",
    "Disable AutoMod system": "ปิดระบบ AutoMod",
    "Edit AutoMod settings": "แก้ไขการตั้งค่า AutoMod",
    "Enable/Disable AntiSpam system": "เปิด/ปิดระบบป้องกันสแปม",
    "Enable AntiSpam system": "เปิดระบบป้องกันสแปม",
    "Disable AntiSpam system": "ปิดระบบป้องกันสแปม",
    "Edit AntiSpam settings": "แก้ไขการตั้งค่า AntiSpam",
    "Enable/Disable AntiLink system": "เปิด/ปิดระบบป้องกันลิงก์",
    "Enable AntiLink system": "เปิดระบบป้องกันลิงก์",
    "Disable AntiLink system": "ปิดระบบป้องกันลิงก์",
    "Edit AntiLink settings": "แก้ไขการตั้งค่า AntiLink",
    "Enable/Disable AntiBadWords system": "เปิด/ปิดระบบกรองคำหยาบ",
    "Enable AntiBadWords system": "เปิดระบบกรองคำหยาบ",
    "Disable AntiBadWords system": "ปิดระบบกรองคำหยาบ",
    "Edit AntiBadWords settings": "แก้ไขการตั้งค่า AntiBadWords",
    "Enable/Disable Anti-Nuke system": "เปิด/ปิดระบบป้องกัน Anti-Nuke",
    "Enable Anti-Nuke system": "เปิดระบบป้องกัน Anti-Nuke",
    "Disable Anti-Nuke system": "ปิดระบบป้องกัน Anti-Nuke",
    "Edit Anti-Nuke settings": "แก้ไขการตั้งค่า Anti-Nuke",
    "Whitelist a user from Anti-Nuke system": "เพิ่มผู้ใช้เข้าไวท์ลิสต์ระบบ Anti-Nuke",
    "Add a user to whitelist": "เพิ่มผู้ใช้เข้าไวท์ลิสต์",
    "Delete a user from whitelist": "ลบผู้ใช้ออกจากไวท์ลิสต์",
    "Edit whitelist settings of a user": "แก้ไขการตั้งค่าไวท์ลิสต์ของผู้ใช้",
    "List all whitelisted users": "แสดงรายการผู้ใช้ไวท์ลิสต์ทั้งหมด",
    "Manage extra owners in the server": "จัดการเจ้าของเสริมในเซิร์ฟเวอร์",
    "Add an extra owner": "เพิ่มเจ้าของเสริม",
    "Remove an extra owner": "ลบเจ้าของเสริม",
    "List extra owners": "แสดงรายการเจ้าของเสริม",
    "Giveaway related commands": "คำสั่งที่เกี่ยวข้องกับ Giveaway",
    "Create a giveaway Event": "สร้างกิจกรรม Giveaway",
    "Delete a giveaway Event": "ลบกิจกรรม Giveaway",
    "End a giveaway Event": "จบกิจกรรม Giveaway",
    "List all giveaways": "แสดงรายการ Giveaway ทั้งหมด",
    "Reroll a giveaway Event": "สุ่มผู้ชนะ Giveaway ใหม่",
    "Show the role set for giveaway access": "แสดงบทบาทที่ใช้สำหรับสิทธิ์ Giveaway",
    "Set of commands to manage tickets": "ชุดคำสั่งสำหรับจัดการทิกเก็ต",
    "Setup the ticket system in the current server": "ตั้งค่าระบบทิกเก็ตในเซิร์ฟเวอร์นี้",
    "Close a ticket": "ปิดทิกเก็ต",
    "Delete a ticket": "ลบทิกเก็ต",
    "Setup AI chat room": "ตั้งค่าห้องแชท AI",
    "Set AI chat room channel": "ตั้งค่าห้องแชท AI",
    "Remove AI chat room setup": "ลบการตั้งค่าห้องแชท AI",
    "Manage promote submit/public channels": "จัดการห้องส่งโปรโมตและห้องสาธารณะ",
    "Setup promote submit/public channels": "ตั้งค่าห้องส่งโปรโมตและห้องสาธารณะ",
    "Disable promote system in this guild": "ปิดระบบโปรโมตในกิลด์นี้",
    "Enable or disable the global alerts worker for this guild": "เปิดหรือปิดระบบแจ้งเตือนอัตโนมัติของกิลด์นี้",
    "Play music in the voice channel.": "เล่นเพลงในห้องเสียง",
    "Pause the player.": "หยุดเพลงชั่วคราว",
    "Resume the player.": "เล่นเพลงต่อ",
    "Skip the current track.": "ข้ามเพลงปัจจุบัน",
    "Loop the current track.": "เปิดหรือปิดการวนเพลงปัจจุบัน",
    "Show the queue of the player.": "แสดงคิวเพลงปัจจุบัน",
    "Get or set the volume of the player.": "ดูหรือปรับระดับเสียงของเครื่องเล่น",
    "Stop the player and disconnect the bot from the voice channel.": "หยุดเพลงและให้บอทออกจากห้องเสียง",
    "Show the current playing track.": "แสดงเพลงที่กำลังเล่นอยู่",
    "Toggle autoplay mode.": "เปิดหรือปิดโหมดเล่นอัตโนมัติ",
    "Setup request text and target voice channels": "ตั้งค่าห้องคำขอเพลงและห้องเสียงเป้าหมาย",
    "Reset request text and target voice channels": "รีเซ็ตห้องคำขอเพลงและห้องเสียงเป้าหมาย",
    "Show the music settings": "แสดงการตั้งค่าระบบเพลง",
    "Configure leave message settings for your server": "ตั้งค่าข้อความลาสำหรับเซิร์ฟเวอร์ของคุณ",
    "Snipe the last deleted message in the channel": "ดูข้อความล่าสุดที่ถูกลบในห้อง",
    "Snipe the last edited message in the channel": "ดูข้อความล่าสุดที่ถูกแก้ไขในห้อง",
    "Lock a channel": "ล็อกห้อง",
    "Unlock a channel": "ปลดล็อกห้อง",

    "Configure and monitor raid shield protections": "ตั้งค่าและติดตามระบบป้องกัน Raid Shield",
    "Arm raid shield with threshold settings": "เปิดใช้งาน Raid Shield พร้อมตั้งค่าเกณฑ์",
    "Show current raid shield status": "แสดงสถานะปัจจุบันของ Raid Shield",
    "Release active raid lockdown": "ยกเลิกการล็อกดาวน์จาก Raid ที่กำลังทำงาน",
    "Manage moderation case records": "จัดการเคสงานดูแล",
    "List cases by status": "แสดงรายการเคสตามสถานะ",
    "Assign a case to a moderator": "มอบหมายเคสให้ผู้ดูแล",
    "Resolve a case with an optional note": "ปิดเคสพร้อมบันทึกหมายเหตุ (ไม่บังคับ)",
    "Capture and export moderation evidence": "บันทึกและส่งออกหลักฐานงานดูแล",
    "Capture a message snapshot as evidence": "บันทึกสแนปช็อตข้อความเป็นหลักฐาน",
    "Export case evidence to a text file": "ส่งออกหลักฐานของเคสเป็นไฟล์ข้อความ",
    "Submit and review moderation appeals": "ยื่นและตรวจสอบคำอุทธรณ์งานดูแล",
    "Submit an appeal for a moderation action": "ยื่นอุทธรณ์ต่อการดำเนินการของผู้ดูแล",
    "List pending appeals": "แสดงคำอุทธรณ์ที่รอพิจารณา",
    "Set verdict for an appeal": "ตัดสินผลคำอุทธรณ์",
    "Configure onboarding flow and metrics": "ตั้งค่าโฟลว์ onboarding และตัวชี้วัด",
    "Set or view onboarding roles": "ตั้งค่าหรือดูยศ onboarding",
    "Show onboarding funnel statistics": "แสดงสถิติ funnel onboarding",
    "Open support ticket threads in this server": "เปิดเธรดทิกเก็ตซัพพอร์ตในเซิร์ฟเวอร์นี้",
    "Open support ticket form": "เปิดฟอร์มทิกเก็ตซัพพอร์ต",
    "Configure supportserver thread settings": "ตั้งค่าระบบเธรด supportserver",
    "Auto create supportserver channels and enable system": "สร้างห้อง supportserver อัตโนมัติและเปิดใช้งานระบบ",
    "Configure supportbot ticket intake channel": "ตั้งค่าห้องรับตั๋วของ supportbot",
    "Create and track community events": "สร้างและติดตามกิจกรรมชุมชน",
    "Create a new event record": "สร้างบันทึกกิจกรรมใหม่",
    "Check in to an event": "เช็กอินเข้าร่วมกิจกรรม",
    "Show event recap and attendees": "แสดงสรุปกิจกรรมและผู้เข้าร่วม",
    "Manage trust scores and trust rules": "จัดการคะแนนความน่าเชื่อถือและกฎ Trust",
    "Show trust profile for a member": "แสดงโปรไฟล์ความน่าเชื่อถือของสมาชิก",
    "Configure trust thresholds and role rewards": "ตั้งค่าเกณฑ์ Trust และรางวัลยศ",
    "View community health metrics": "ดูตัวชี้วัดสุขภาพชุมชน",
    "Show daily health metrics": "แสดงตัวชี้วัดรายวัน",
    "Show weekly health metrics": "แสดงตัวชี้วัดรายสัปดาห์",
    "Manage partner onboarding records": "จัดการบันทึก onboarding พาร์ตเนอร์",
    "Create a partner onboarding record": "สร้างบันทึก onboarding พาร์ตเนอร์",
    "Manage sponsor slot reservations": "จัดการการจองสล็อตผู้สนับสนุน",
    "Create a sponsor slot for a partner": "สร้างสล็อตผู้สนับสนุนสำหรับพาร์ตเนอร์",
    "Manage partner CRM notes": "จัดการบันทึก CRM ของพาร์ตเนอร์",
    "Add a CRM note for a partner": "เพิ่มบันทึก CRM ให้พาร์ตเนอร์",
    "Operational toolkit for large Discord communities": "ชุดเครื่องมือปฏิบัติการสำหรับคอมมูนิตี้ Discord ขนาดใหญ่",
    "Raid shield armed.": "เปิดใช้งาน Raid Shield แล้ว",
    "Raid lockdown released.": "ยกเลิกการล็อกดาวน์จาก Raid แล้ว",
    "Auto build and decorate guild channels/roles": "สร้างและตกแต่งห้องและยศของกิลด์อัตโนมัติ",
    "Create styled categories/channels/roles from a preset or custom layout": "สร้างหมวดหมู่ ห้อง และยศแบบตกแต่งจากพรีเซ็ตหรือเลย์เอาต์กำหนดเอง",
    "Quick theme setup for GuildStyle (same flow as /guildstyle create)": "ตั้งค่าธีม GuildStyle แบบด่วน (ขั้นตอนเดียวกับ /guildstyle create)",
    "Quick roleplay setup for GuildStyle theme": "ตั้งค่าโหมดโรลเพลย์ของ GuildStyle แบบด่วน",
    "Alias for /guildstyle roplay": "คำสั่งทางลัดของ /guildstyle roplay",
    "Repair roleplay setup by creating only missing rooms/roles": "ซ่อมการตั้งค่าโรลเพลย์โดยสร้างเฉพาะห้องหรือยศที่ขาด",
    "Create or update the GuildStyle role pack only": "สร้างหรืออัปเดตเฉพาะชุดยศ GuildStyle",
    "Export guildstyle room/role layout as JSON": "ส่งออกเลย์เอาต์ห้องและยศ GuildStyle เป็น JSON",
    "Import guildstyle room/role layout JSON and apply it": "นำเข้า JSON เลย์เอาต์ห้องและยศ GuildStyle และนำไปใช้",
    "Fix verify channel + verified role mapping and permissions": "ซ่อมการผูก verify channel และ verified role พร้อมสิทธิ์",
    "Set one permission overwrite for a role in a specific room": "ตั้งค่า permission overwrite ของยศในห้องที่ระบุ",
    "Apply a ready-made permission preset to a room": "ใช้พรีเซ็ตสิทธิ์สำเร็จรูปกับห้อง",
    "Delete rooms created by the latest GuildStyle setup snapshot": "ลบห้องที่สร้างจากสแนปช็อต GuildStyle ล่าสุด",
    "Inspect role permission overwrite matrix for a room": "ตรวจสอบตาราง permission overwrite ของยศในห้อง",
    "Rename existing channels/categories with GuildStyle decoration": "เปลี่ยนชื่อห้องหรือหมวดหมู่ที่มีอยู่ด้วยสไตล์ GuildStyle",
    "Guild styling and auto setup commands": "คำสั่งตกแต่งกิลด์และตั้งค่าอัตโนมัติ",
    "`/guildstyle theme` - quick theme setup (dashboard style)\n`/guildstyle roplay` - quick roleplay theme setup\n`/guildstyle create` - create channels + roles + default room permissions\n`/guildstyle repair` - fill missing roleplay rooms/roles without overriding existing\n`/guildstyle roles` - create/update role pack only\n`/guildstyle decorate` - decorate existing channel/category names\n`/guildstyle layoutexport` - export room/role layout JSON\n`/guildstyle layoutimport` - import room/role layout JSON\n`/autorole setup` - open autorole toggle/setup menu\n`/autorole set` - set autorole target directly\n`/guildstyle verifyfix` - fix verify channel + verified role mapping\n`/guildstyle roomperm` - set view/send/connect permission per room\n`/guildstyle roompreset` - apply public/locked/staff-only/verified-only\n`/guildstyle roomperms` - inspect room access map\n`/guildstyle delete` - delete rooms created by latest guildstyle setup": "`/guildstyle theme` - ตั้งค่าธีมแบบด่วน (สไตล์แดชบอร์ด)\n`/guildstyle roplay` - ตั้งค่าโรลเพลย์แบบด่วน\n`/guildstyle create` - สร้างห้อง + ยศ + สิทธิ์เริ่มต้นของห้อง\n`/guildstyle repair` - เติมเฉพาะห้องหรือยศที่ขาดโดยไม่ทับของเดิม\n`/guildstyle roles` - สร้างหรืออัปเดตเฉพาะชุดยศ\n`/guildstyle decorate` - ตกแต่งชื่อห้องหรือหมวดหมู่ที่มีอยู่\n`/guildstyle layoutexport` - ส่งออกเลย์เอาต์ห้องและยศเป็น JSON\n`/guildstyle layoutimport` - นำเข้าเลย์เอาต์ห้องและยศจาก JSON\n`/autorole setup` - เปิดเมนูตั้งค่า autorole\n`/autorole set` - ตั้งค่าเป้าหมาย autorole โดยตรง\n`/guildstyle verifyfix` - ซ่อมการผูก verify channel + verified role\n`/guildstyle roomperm` - ตั้งค่าสิทธิ์ view/send/connect รายห้อง\n`/guildstyle roompreset` - ใช้พรีเซ็ต public/locked/staff-only/verified-only\n`/guildstyle roomperms` - ตรวจสอบแผนที่สิทธิ์การเข้าถึงห้อง\n`/guildstyle delete` - ลบห้องที่สร้างจากการตั้งค่า guildstyle ล่าสุด",
    "Translate text between multiple languages for both short and long messages": "แปลข้อความหลายภาษา รองรับทั้งข้อความสั้นและยาว",
    "You need `Manage Server` permission to use this command.": "คุณต้องมีสิทธิ์ `Manage Server` เพื่อใช้คำสั่งนี้",
    "No channels/categories matched for decoration.": "ไม่พบห้องหรือหมวดหมู่ที่ตรงสำหรับการตกแต่ง",
}


def _translate_command_text_to_th(text: str) -> str:
    if not isinstance(text, str):
        return text
    normalized = " ".join(text.strip().split())
    if not normalized:
        return normalized

    if normalized in TH_COMMAND_TEXT_OVERRIDES:
        return TH_COMMAND_TEXT_OVERRIDES[normalized]

    dynamic_patterns: list[tuple[str, str]] = [
        (r"^Enable/Disable (.+?) system$", r"เปิด/ปิดระบบ \1"),
        (r"^Enable (.+?) system$", r"เปิดระบบ \1"),
        (r"^Disable (.+?) system$", r"ปิดระบบ \1"),
        (r"^Edit (.+?) settings$", r"แก้ไขการตั้งค่า \1"),
        (r"^Configure the (.+?) for your server$", r"ตั้งค่า\1สำหรับเซิร์ฟเวอร์ของคุณ"),
        (r"^Setup the (.+?) Commands$", r"ตั้งค่าคำสั่ง\1"),
        (r"^Setup the (.+?) system$", r"ตั้งค่าระบบ\1"),
        (r"^List all (.+)$", r"แสดงรายการ\1ทั้งหมด"),
        (r"^Add (.+)$", r"เพิ่ม\1"),
        (r"^Remove (.+)$", r"ลบ\1"),
        (r"^Delete (.+)$", r"ลบ\1"),
        (r"^Show (.+)$", r"แสดง\1"),
        (r"^Get (.+)$", r"ดู\1"),
        (r"^Predict a persons (.+?) level$", r"ทำนายระดับ\1ของคนที่ระบุ"),
    ]
    for pattern, repl in dynamic_patterns:
        if re.match(pattern, normalized, flags=re.IGNORECASE):
            return re.sub(pattern, repl, normalized, flags=re.IGNORECASE)

    converted = _translate_with_common_patterns(normalized)
    if re.search(r"[A-Za-z]", converted):
        return "คำสั่งสำหรับใช้งานในระบบ"
    return converted


def _register_command_text_key(key: str, english_text: str, thai_text: str | None = None) -> None:
    if not isinstance(key, str) or not key.strip() or not isinstance(english_text, str):
        return

    source_text = english_text.strip()
    if not source_text:
        return

    # Handle source literals written in either language.
    # Many legacy commands are authored in Thai text directly.
    source_is_thai_only = _contains_thai(source_text) and not _contains_english(source_text)

    if source_is_thai_only:
        normalized_thai = source_text
        translated_en = _normalize_mixed_language_text(
            _translate_text_runtime_rule_based(source_text, "en"),
            "en",
        )
        if _contains_thai(translated_en) or _looks_unusable_english(translated_en):
            translated_en = _normalize_mixed_language_text(
                _translate_text_with_runtime_fallback_provider(source_text, "th2en"),
                "en",
            )
        if _contains_thai(translated_en):
            mapped_en = _map_literal_from_locales(source_text, "en")
            if isinstance(mapped_en, str) and mapped_en and not _contains_thai(mapped_en):
                translated_en = _normalize_mixed_language_text(mapped_en, "en")
        if not translated_en or _contains_thai(translated_en):
            translated_en = "Command for use in the system"
        normalized_english = translated_en or source_text
    else:
        normalized_english = source_text
        translated_th = thai_text or _translate_command_text_to_th(normalized_english)
        if translated_th == _TH_COMMAND_GENERIC_FALLBACK:
            translated_th = _normalize_mixed_language_text(
                _translate_text_runtime_rule_based(normalized_english, "th"),
                "th",
            )
        if _contains_english(translated_th):
            translated_th = _normalize_mixed_language_text(
                _translate_text_with_runtime_fallback_provider(normalized_english, "en2th"),
                "th",
            )
        normalized_thai = translated_th or normalized_english

    COMMAND_TEXT_KEYS[key] = {
        "en": normalized_english,
        "th": normalized_thai,
    }
    COMMAND_TEXT_BY_ENGLISH[_normalize_command_text(normalized_english)] = key
    COMMAND_TEXT_BY_THAI[_normalize_command_text(normalized_thai)] = key


def _generated_help_key(text: str) -> str:
    normalized = _normalize_command_text(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    slug = "_".join(tokens[:6]) or "text"
    digest = hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"cmd_auto_{slug}_{digest}"


def _ensure_command_help_keys(bot: commands.Bot) -> None:
    stack = list(getattr(bot, "commands", []) or [])

    while stack:
        current = stack.pop()
        help_text = getattr(current, "help", None)
        if isinstance(help_text, str) and help_text and not help_text.startswith("i18n:"):
            key = _resolve_command_text_key(help_text)
            if not key:
                key = _generated_help_key(help_text)
                _register_command_text_key(key, help_text)

        children = getattr(current, "commands", None)
        if isinstance(children, (list, tuple)):
            stack.extend(list(children))
        elif isinstance(children, dict):
            stack.extend(list(children.values()))


def _ensure_cog_description_keys(bot: commands.Bot) -> None:
    for cog in list(getattr(bot, "cogs", {}).values()):
        info = getattr(cog, "cog_info", None)
        if not info:
            continue
        description = getattr(info, "description", None)
        if not isinstance(description, str) or not description or description.startswith("i18n:"):
            continue
        key = _resolve_command_text_key(description)
        if not key:
            key = _generated_help_key(description)
            _register_command_text_key(key, description)
        try:
            info.description = f"i18n:{key}"
        except Exception:
            continue


_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


def _load_messages(locale: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"messages_{locale}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


MESSAGES: dict[str, dict[str, str]] = {
    "en": _load_messages("en"),
    "th": _load_messages("th"),
}


# Runtime phrase replacements for legacy hard-coded English strings.
# This allows broad translation coverage without touching every command file.
RUNTIME_PHRASES: dict[str, str] = {
    "You can only delete 1000 messages at a time": "คุณลบได้สูงสุดครั้งละ 1000 ข้อความ",
    "You can only delete 100 messages at a time": "คุณลบได้สูงสุดครั้งละ 100 ข้อความ",
    "Deleted {amount} messages": "ลบข้อความแล้ว {amount} ข้อความ",
    "Deleted {amount} messages of {user}": "ลบข้อความของ {user} แล้ว {amount} ข้อความ",
    "Deleted {amount} messages containing images": "ลบข้อความที่มีรูปภาพแล้ว {amount} ข้อความ",
    "Deleted {amount} messages containing links": "ลบข้อความที่มีลิงก์แล้ว {amount} ข้อความ",
    "Deleted {amount} messages of bots": "ลบข้อความของบอทแล้ว {amount} ข้อความ",
    "An Error occurred while purging messages": "เกิดข้อผิดพลาดระหว่างลบข้อความ",
    "An Error occurred while banning the user": "เกิดข้อผิดพลาดระหว่างแบนผู้ใช้",
    "An Error occurred while kicking the user": "เกิดข้อผิดพลาดระหว่างเตะผู้ใช้",
    "An Error occurred while unbanning the user": "เกิดข้อผิดพลาดระหว่างปลดแบนผู้ใช้",
    "No message to snipe": "ไม่มีข้อความให้ส่องย้อนหลัง",
    "Command access": "การเข้าถึงคำสั่ง",
    "Ticket Commands": "คำสั่งระบบทิกเก็ต",
    "Use these commands to manage tickets": "ใช้คำสั่งเหล่านี้เพื่อจัดการระบบทิกเก็ต",
    "Ticket Setup": "ตั้งค่าระบบทิกเก็ต",
    "No ticket Is Setup Yet": "ยังไม่มีการตั้งค่าทิกเก็ต",
    "Create": "สร้าง",
    "Delete This": "ลบรายการนี้",
    "Previous": "ก่อนหน้า",
    "Next": "ถัดไป",
    "Stop": "หยุด",
    "Giveaway Access": "สิทธิ์การจัดการกิจกรรม",
    "Save giveaway access": "บันทึกสิทธิ์กิจกรรม",
    "Welcome settings": "ตั้งค่าการต้อนรับ",
    "Enable welcome system": "เปิดระบบต้อนรับ",
    "Enable autorole": "เปิดระบบยศอัตโนมัติ",
    "Enable autonick": "เปิดระบบชื่อเล่นอัตโนมัติ",
    "Save welcomer settings": "บันทึกการตั้งค่าต้อนรับ",
    "Security settings": "ตั้งค่าความปลอดภัย",
    "Save moderation settings": "บันทึกการตั้งค่าดูแลแชท",
    "No Reason Provided": "ไม่ได้ระบุเหตุผล",
    "Reason:": "เหตุผล:",
    "By:": "โดย:",
    "Time:": "เวลา:",
    "Server ID:": "รหัสเซิร์ฟเวอร์:",
    "Action by": "ดำเนินการโดย",
    "Successfully Banned": "แบนสำเร็จ",
    "Successfully Kicked": "เตะสำเร็จ",
    "User Banned": "ผู้ใช้ที่ถูกแบน",
    "User Kicked": "ผู้ใช้ที่ถูกเตะ",
    "You have been banned from": "คุณถูกแบนจาก",
    "You have been kicked from": "คุณถูกเตะออกจาก",
    "Banned by": "แบนโดย",
    "Kicked by": "เตะโดย",
    "has been unbanned": "ถูกปลดแบนแล้ว",
    "has been locked": "ถูกล็อกแล้ว",
    "has been unlocked": "ถูกปลดล็อกแล้ว",
    "has been hidden": "ถูกซ่อนแล้ว",
    "has been unhidden": "ถูกยกเลิกซ่อนแล้ว",
    "Another lockall command is already running": "มีคำสั่ง lockall กำลังทำงานอยู่แล้ว",
    "Another unlockall command is already running": "มีคำสั่ง unlockall กำลังทำงานอยู่แล้ว",
    "Another hideall command is already running": "มีคำสั่ง hideall กำลังทำงานอยู่แล้ว",
    "Locking all channels": "กำลังล็อกทุกห้อง",
    "Unlocking all channels": "กำลังปลดล็อกทุกห้อง",
    "Hiding all channels": "กำลังซ่อนทุกห้อง",
    "All channels have been locked": "ล็อกทุกห้องแล้ว",
    "All channels have been unlocked": "ปลดล็อกทุกห้องแล้ว",
    "All channels have been hidden": "ซ่อนทุกห้องแล้ว",
    "An error occurred while processing the command.": "เกิดข้อผิดพลาดระหว่างประมวลผลคำสั่ง",
    "You are not authorized to use this button": "คุณไม่ได้รับอนุญาตให้ใช้ปุ่มนี้",
    "You are not allowed to interact with this button": "คุณไม่ได้รับอนุญาตให้โต้ตอบกับปุ่มนี้",
    "You cannot interact with this button": "คุณไม่สามารถโต้ตอบกับปุ่มนี้ได้",
    "You can't use this button": "คุณไม่สามารถใช้ปุ่มนี้ได้",
    "No ticket module selected": "ยังไม่ได้เลือกโมดูลทิกเก็ต",
    "Ticket module not found": "ไม่พบโมดูลทิกเก็ต",
    "Ticket panel channel not found": "ไม่พบช่องแผงทิกเก็ต",
    "This is not a ticket channel": "นี่ไม่ใช่ห้องทิกเก็ต",
    "Ticket not found": "ไม่พบทิกเก็ต",
    "is already closed": "ปิดไปแล้ว",
    "is not closed yet": "ยังไม่ถูกปิด",
    "Ticket closed successfully": "ปิดทิกเก็ตสำเร็จแล้ว",
    "Failed to close the ticket": "ปิดทิกเก็ตไม่สำเร็จ",
    "Delete Confirmation": "ยืนยันการลบ",
    "Do you want to delete the Ticket Channel?": "คุณต้องการลบห้องทิกเก็ตหรือไม่?",
    "The player is offline right now.": "ตัวเล่นเพลงออฟไลน์อยู่ตอนนี้",
    "Join a voice channel to use the controller.": "เข้าห้องเสียงก่อนจึงจะใช้ตัวควบคุมได้",
    "You need to be in the same voice channel as SkylineBOT.": "คุณต้องอยู่ห้องเสียงเดียวกับ SkylineBOT",
    "Controller is refreshing, try again in a moment.": "ตัวควบคุมกำลังรีเฟรช โปรดลองอีกครั้งในอีกสักครู่",
    "The bot is not connected to any voice channel.": "บอทยังไม่ได้เชื่อมต่อห้องเสียง",
    "You need to be in a voice channel to use this button.": "คุณต้องอยู่ในห้องเสียงก่อนจึงจะใช้ปุ่มนี้ได้",
    "You need to be in the same voice channel as the bot to use this button.": "คุณต้องอยู่ห้องเสียงเดียวกับบอทก่อนจึงจะใช้ปุ่มนี้ได้",
    "Clicking too fast.": "กดเร็วเกินไป",
    "Filter has been removed.": "นำฟิลเตอร์ออกแล้ว",
    "Filter has been set to": "ตั้งค่าฟิลเตอร์เป็น",
    "Volume is already at minimum.": "ระดับเสียงต่ำสุดอยู่แล้ว",
    "Volume is already at maximum.": "ระดับเสียงสูงสุดอยู่แล้ว",
    "Volume set to": "ตั้งระดับเสียงเป็น",
    "Player stopped.": "หยุดเล่นเพลงแล้ว",
    "Playback resumed.": "เล่นเพลงต่อแล้ว",
    "Playback paused.": "พักเพลงแล้ว",
    "Skipped current track.": "ข้ามเพลงปัจจุบันแล้ว",
    "Nothing left in queue to skip into.": "ไม่มีเพลงถัดไปในคิวให้ข้าม",
    "Loop disabled.": "ปิดวนซ้ำแล้ว",
    "Loop enabled.": "เปิดวนซ้ำแล้ว",
    "Autoplay enabled.": "เปิดเล่นอัตโนมัติแล้ว",
    "Autoplay disabled.": "ปิดเล่นอัตโนมัติแล้ว",
    "Invalid volume value.": "ค่าระดับเสียงไม่ถูกต้อง",
    "Volume must be between 0 and 100.": "ระดับเสียงต้องอยู่ระหว่าง 0 ถึง 100",
    "Music artwork": "ภาพปกเพลง",
    "Search Google": "ค้นหาบน Google",
    "Unknown": "ไม่ทราบ",
    "Bot Ping": "ปิงบอท",
    "Storage Ping": "ปิงสตอเรจ",
    "Cache Ping": "ปิงแคช",
    "An Error Occured While Fetching The Ping": "เกิดข้อผิดพลาดระหว่างตรวจสอบค่าปิง",
    "Invite Me To Your Server": "เชิญบอทเข้าร่วมเซิร์ฟเวอร์ของคุณ",
    "Heads Up! You Can Invite Me To Your Server By Clicking The Button Below.\nPlease Make Sure You Have The Required Permissions To Add Me To Your Server.\nWe hope you enjoy using our bot.": "แจ้งเตือน! คุณสามารถเชิญบอทเข้าร่วมเซิร์ฟเวอร์ได้โดยกดปุ่มด้านล่าง\nโปรดตรวจสอบว่าคุณมีสิทธิ์เพียงพอในการเพิ่มบอทเข้าร่วมเซิร์ฟเวอร์\nหวังว่าคุณจะสนุกกับการใช้งานบอทของเรา",
    "Invite Me": "เชิญบอท",
    "An Error Occured While Sending The Invite Link": "เกิดข้อผิดพลาดระหว่างส่งลิงก์เชิญบอท",
    "Support": "ซัพพอร์ต",
    "Heads Up! You Can Join Our Support Server By Clicking The Button Below.\nPlease Make Sure You Follow The Rules Of The Server.\nWe hope you enjoy using our bot.": "แจ้งเตือน! คุณสามารถเข้าร่วมเซิร์ฟเวอร์ซัพพอร์ตได้โดยกดปุ่มด้านล่าง\nโปรดปฏิบัติตามกฎของเซิร์ฟเวอร์\nหวังว่าคุณจะสนุกกับการใช้งานบอทของเรา",
    "Requested by": "ร้องขอโดย",
    "Generate Redeem Code": "สร้าง Redeem Code",
    "Generated Redeem Code": "Redeem Code ที่สร้างแล้ว",
    "Generate Redeem Code requested by": "การสร้าง Redeem Code ร้องขอโดย",
    "Selected Code Type:": "ประเภทโค้ดที่เลือก:",
    "Code Validity:": "อายุโค้ด:",
    "Code Expires:": "โค้ดหมดอายุ:",
    "Undefined": "ยังไม่กำหนด",
    "Unlimited": "ไม่จำกัด",
    "Not Set": "ยังไม่ตั้งค่า",
    " Days": " วัน",
    "Select Redeem Code Type": "เลือกประเภท Redeem Code",
    "Set Code Validity": "กำหนดอายุ Redeem Code",
    "Enter Code Validity in Days": "ใส่อายุ Redeem Code (วัน)",
    "Invalid Input. Please enter a valid number.": "ข้อมูลไม่ถูกต้อง กรุณาใส่ตัวเลขที่ถูกต้อง",
    "Redeem Code For": "Redeem Code สำหรับ",
    "Failed to generate redeem code": "สร้าง Redeem Code ไม่สำเร็จ",
    "Please Enter Redeem Code": "กรุณาใส่ Redeem Code",
    "You can get redeem code from our support server": "คุณสามารถรับ Redeem Code ได้จากเซิร์ฟเวอร์ซัพพอร์ตของเรา",
    "Enter Redeem Code": "กรอก Redeem Code",
    "Enter Your Redeem Code": "กรอก Redeem Code ของคุณ",
    "Invalid Redeem Code": "Redeem Code ไม่ถูกต้อง",
    "Redeem Code Already Claimed": "Redeem Code นี้ถูกใช้งานแล้ว",
    "Redeem Code Expired at": "Redeem Code หมดอายุเมื่อ",
    "Redeem Code Details": "รายละเอียด Redeem Code",
    "Redeem Code:": "Redeem Code:",
    "Code Type:": "ประเภทโค้ด:",
    "Code Value:": "ค่าโค้ด:",
    "Code Valid For:": "โค้ดใช้ได้:",
    "Code Expires At:": "โค้ดหมดอายุ:",
    "Code Claimed:": "สถานะการใช้โค้ด:",
    "Code Claimed By:": "โค้ดถูกใช้โดย:",
    "Code Claimed At:": "โค้ดถูกใช้เมื่อ:",
    "Code Created At:": "โค้ดถูกสร้างเมื่อ:",
    "Buy Premium": "ซื้อ Premium",
    "Premium Info": "ข้อมูล Premium",
    "Server Premium Info": "ข้อมูล Premium ของเซิร์ฟเวอร์",
    "Premium:": "Premium:",
    "Expires:": "หมดอายุ:",
    " does not have a banner.": " ไม่มีแบนเนอร์",
    " doesn't have a banner.": " ไม่มีแบนเนอร์",
    "You are not in a voice channel": "คุณไม่ได้อยู่ในห้องเสียง",
    " is not in a voice channel": " ไม่ได้อยู่ในห้องเสียง",
    " is already muted": " ถูกปิดเสียงอยู่แล้ว",
    " has been muted": " ถูกปิดเสียงแล้ว",
    " is not muted": " ยังไม่ได้ถูกปิดเสียง",
    " has been unmuted": " ถูกยกเลิกปิดเสียงแล้ว",
    " is already deafened": " ถูกปิดการได้ยินอยู่แล้ว",
    " has been deafened": " ถูกปิดการได้ยินแล้ว",
    " is not deafened": " ยังไม่ได้ถูกปิดการได้ยิน",
    " has been undeafened": " ถูกยกเลิกปิดการได้ยินแล้ว",
    " has been moved to ": " ถูกย้ายไปยัง ",
    " has no users": " ไม่มีผู้ใช้อยู่ในห้อง",
    "All users in ": "ผู้ใช้ทั้งหมดใน ",
    " have been moved to ": " ถูกย้ายไปยัง ",
    " has been disconnected": " ถูกตัดการเชื่อมต่อแล้ว",
    " has been pulled to your voice channel": " ถูกดึงเข้าห้องเสียงของคุณแล้ว",
    " have been muted": " ถูกปิดเสียงแล้ว",
    " have been unmuted": " ถูกยกเลิกปิดเสียงแล้ว",
    " have been deafened": " ถูกปิดการได้ยินแล้ว",
    " have been undeafened": " ถูกยกเลิกปิดการได้ยินแล้ว",
    " have been disconnected": " ถูกตัดการเชื่อมต่อแล้ว",
    "An error occured:": "เกิดข้อผิดพลาด:",
    "An error occurred:": "เกิดข้อผิดพลาด:",
    "An Error Occured While Sending The Support Server Link": "เกิดข้อผิดพลาดระหว่างส่งลิงก์เซิร์ฟเวอร์ซัพพอร์ต",
    "Vote": "โหวต",
    "Heads Up! You Can Vote For Me By Clicking The Button Below.\nPlease Make Sure You Follow The Rules Of The Voting Site.\nWe hope you enjoy using our bot.": "แจ้งเตือน! คุณสามารถโหวตให้บอทได้โดยกดปุ่มด้านล่าง\nโปรดปฏิบัติตามกฎของเว็บไซต์โหวต\nหวังว่าคุณจะสนุกกับการใช้งานบอทของเรา",
    "Help menu": "เมนูช่วยเหลือ",
    "Prefix for this server is": "คำนำหน้าของเซิร์ฟเวอร์นี้คือ",
    "Total commands": "จำนวนคำสั่งทั้งหมด",
    "Vote me": "โหวตให้บอท",
    "Select a category to view": "เลือกหมวดหมู่เพื่อดูคำสั่ง",
    "All Commands": "คำสั่งทั้งหมด",
    "Category not found": "ไม่พบหมวดหมู่",
    "Command not found": "ไม่พบคำสั่ง",
    "Commands": "คำสั่ง",
    "Command": "คำสั่ง",
    "Primary Command": "คำสั่งหลัก",
    "Options": "ตัวเลือก",
    "Subcommands": "คำสั่งย่อย",
    "Back": "ย้อนกลับ",
    "Report": "รายงาน",
    "Submit Report": "ส่งรายงาน",
    "Report Title": "หัวข้อรายงาน",
    "Report Description": "รายละเอียดรายงาน",
    "Separate the links with comma": "คั่นลิงก์ด้วยเครื่องหมายจุลภาค",
    "Report Attachment links": "ลิงก์แนบรายงาน",
    "Title and Description are required": "ต้องระบุหัวข้อและรายละเอียด",
    "Attachments links": "ลิงก์ไฟล์แนบ",
    "Reported by": "รายงานโดย",
    "Report submitted successfully": "ส่งรายงานเรียบร้อยแล้ว",
    "You are not allowed to use this interaction": "คุณไม่ได้รับอนุญาตให้ใช้การโต้ตอบนี้",
    "Edit Message Content": "แก้ไขข้อความ",
    "Edit Title": "แก้ไขชื่อเรื่อง",
    "Edit Description": "แก้ไขคำอธิบาย",
    "Edit Thumbnail": "แก้ไขภาพย่อ",
    "Edit Image": "แก้ไขรูปภาพ",
    "Edit Footer": "แก้ไขท้ายข้อความ",
    "Edit Author": "แก้ไขผู้เขียน",
    "Enter the new message content": "กรอกข้อความใหม่",
    "Enter the new title": "กรอกชื่อเรื่องใหม่",
    "Enter the new description": "กรอกคำอธิบายใหม่",
    "Enter the new thumbnail": "กรอกลิงก์ภาพย่อใหม่",
    "Enter the new image": "กรอกลิงก์รูปภาพใหม่",
    "Enter the new footer text": "กรอกข้อความท้ายใหม่",
    "Enter the new footer icon": "กรอกลิงก์ไอคอนท้ายใหม่",
    "Enter the new author name": "กรอกชื่อผู้เขียนใหม่",
    "Enter the new author icon": "กรอกลิงก์ไอคอนผู้เขียนใหม่",
    "Enter the new author url": "กรอกลิงก์ผู้เขียนใหม่",
    "Select the embed color": "เลือกสีของ Embed",
    "Red": "แดง",
    "Green": "เขียว",
    "Blue": "น้ำเงิน",
    "Yellow": "เหลือง",
    "Purple": "ม่วง",
    "Invalid image url": "ลิงก์รูปภาพไม่ถูกต้อง",
    "Show all commands in bot": "แสดงคำสั่งทั้งหมดของบอท",
    "Get The Bot's Ping": "ดูค่าปิงของบอท",
    "Invite The Bot To Your Server": "เชิญบอทเข้าร่วมเซิร์ฟเวอร์ของคุณ",
    "Join The Support Server": "เข้าร่วมเซิร์ฟเวอร์ซัพพอร์ต",
    "Vote For The Bot": "โหวตให้บอท",
    "Manage roles of the users": "จัดการบทบาทของผู้ใช้",
    "Report a message to bot staff": "ส่งรายงานข้อความถึงทีมงานบอท",
    "Report a replied message to bot staff": "ส่งรายงานข้อความที่ตอบกลับถึงทีมงานบอท",
    "Usage:": "วิธีใช้:",
    "You must reply to a target message first, then use": "คุณต้อง reply ข้อความเป้าหมายก่อน แล้วใช้",
    "Report channel is not configured. Please contact an admin.": "ไม่พบห้องสำหรับส่งรายงาน กรุณาติดต่อแอดมิน",
    "User Report": "รายงานจากผู้ใช้",
    "Reporter": "ผู้รายงาน",
    "Guild": "เซิร์ฟเวอร์",
    "Direct Messages": "ข้อความส่วนตัว",
    "Channel": "ห้อง",
    "Your report was submitted successfully. Thank you.": "ส่งรายงานเรียบร้อยแล้ว ขอบคุณสำหรับข้อมูล",
    "An Error Occured While Sending The Report": "เกิดข้อผิดพลาดระหว่างส่งรายงาน",
    "Usage: `{prefix}report <message>` or reply to a message then send `{prefix}report`": "วิธีใช้: `{prefix}report <ข้อความ>` หรือ reply ข้อความแล้วพิมพ์ `{prefix}report`",
    "Target Message Link": "ลิงก์ข้อความเป้าหมาย",
    "Jump to message": "ไปยังข้อความ",
    "Target Message Author": "ผู้เขียนข้อความเป้าหมาย",
    "Target Message Content": "เนื้อหาข้อความเป้าหมาย",
    "(No text content)": "(ไม่มีข้อความ)",
    "Target Message Attachments": "ไฟล์แนบของข้อความเป้าหมาย",
    "Hey users !": "สวัสดีผู้ใช้ทุกคน!",
    "Here’s all the info you need": "นี่คือข้อมูลทั้งหมดที่คุณต้องรู้",
    "about": "เกี่ยวกับ",
    "Check it out": "ลองดูได้เลย",
    "Basic Status": "สถานะพื้นฐาน",
    "User's": "ผู้ใช้",
    "Guilds": "กิลด์",
    "Python": "ไพธอน",
    "Dsc-py": "ดิสคอร์ดไลบรารี",
    "BotCpu": "ซีพียูบอท",
    "BotRam": "แรมบอท",
    "BotPid": "พีไอดีบอท",
    "Shards": "ชาร์ด",
    "HostOS": "ระบบปฏิบัติการ",
    "Invite": "เชิญ",
    "Server": "เซิร์ฟเวอร์",
    "Hosted on": "โฮสต์โดย",
    "Enable/Disable Anti-Nuke system": "เปิด/ปิดระบบป้องกัน Anti-Nuke",
    "Enable Anti-Nuke system": "เปิดระบบป้องกัน Anti-Nuke",
    "Disable Anti-Nuke system": "ปิดระบบป้องกัน Anti-Nuke",
    "Edit Anti-Nuke settings": "แก้ไขการตั้งค่า Anti-Nuke",
    "Welcomer Commands": "คำสั่งระบบต้อนรับ",
    "These are the welcomer commands": "นี่คือคำสั่งของระบบต้อนรับ",
    "Welcome Module Commands": "คำสั่งโมดูลต้อนรับ",
    "Here are the available welcome module commands": "นี่คือคำสั่งที่ใช้งานได้ของโมดูลต้อนรับ",
    "Configure the welcomer for your server": "ตั้งค่าระบบต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
    "Configure the welcome message for your server": "ตั้งค่าข้อความต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
    "Configure the welcome message settings for your server": "ตั้งค่าการตั้งค่าข้อความต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
    "Utility commands": "คำสั่งยูทิลิตี้",
    "Help commands": "คำสั่งช่วยเหลือ",
    "Get The Bot's Stats": "ดูข้อมูลสถานะของบอท",
    "The member to assign or remove the role": "สมาชิกที่ต้องการเพิ่มหรือลดยศ",
    "The role to assign or remove": "ยศที่ต้องการเพิ่มหรือลบ",
    "Display the server's banner": "แบนเนอร์ของเซิร์ฟเวอร์",
    "This Server doesn't have a banner.": "เซิร์ฟเวอร์นี้ไม่มีแบนเนอร์",
    "different list commands": "คำสั่งรายการแบบต่าง ๆ",
    "List Commands": "รายการคำสั่ง",
    "List of all the list commands": "รายการคำสั่งทั้งหมดในหมวด list",
    "List all the emojis in the server": "แสดงอีโมจิทั้งหมดในเซิร์ฟเวอร์",
    "There are no emojis in this server": "เซิร์ฟเวอร์นี้ไม่มีอีโมจิ",
    "You Can't Interact With This Button": "คุณไม่สามารถโต้ตอบกับปุ่มนี้ได้",
    "An Error Occured While Sending The Voting Link": "เกิดข้อผิดพลาดระหว่างส่งลิงก์โหวต",
}

RUNTIME_PHRASES.update(
    {
        "Voice Channel Controller": "ตัวควบคุมห้องเสียง",
        "Channel:": "ห้อง:",
        "Users Limit:": "จำนวนผู้ใช้สูงสุด:",
        "Bitrate:": "บิตเรต:",
        "Slowmode:": "โหมดช้า:",
        "NSFW:": "NSFW:",
        "Video Quality Mode:": "โหมดคุณภาพวิดีโอ:",
        "Region:": "ภูมิภาค:",
        "Created At:": "สร้างเมื่อ:",
        "Transfer Ownership": "โอนสิทธิ์ความเป็นเจ้าของ",
        "Select a user to transfer ownership to under 60 seconds.": "เลือกผู้ใช้ที่จะโอนสิทธิ์ความเป็นเจ้าของให้ภายใน 60 วินาที",
        "Change User Limit": "เปลี่ยนจำนวนผู้ใช้สูงสุด",
        "New User Limit": "จำนวนผู้ใช้ใหม่",
        "Enter the limit (0 = unlimited)": "กรอกจำนวนจำกัด (0 = ไม่จำกัด)",
        "Change Bitrate": "เปลี่ยนบิตเรต",
        "New Bitrate": "บิตเรตใหม่",
        "Enter the new bitrate in kbps": "กรอกบิตเรตใหม่เป็น kbps",
        "Change Channel Name": "เปลี่ยนชื่อห้อง",
        "New Channel Name": "ชื่อห้องใหม่",
        "Enter the new name": "กรอกชื่อใหม่",
        "Ticket Info": "ข้อมูลทิกเก็ต",
        "Why are you opening this ticket?": "คุณต้องการเปิดทิกเก็ตนี้เรื่องอะไร?",
        "Ticket Topic": "หัวข้อทิกเก็ต",
        "Participants": "ผู้เข้าร่วม",
        "Exit": "ออก",
        "Previous": "ก่อนหน้า",
        "Next": "ถัดไป",
        "Stop": "หยุด",
        "Active": "กำลังทำงาน",
        "Ended": "สิ้นสุดแล้ว",
        "Configure Bad Words": "ตั้งค่าคำต้องห้าม",
        "Bad Words": "คำต้องห้าม",
        "Comma separated bad words": "คั่นคำต้องห้ามด้วยเครื่องหมายจุลภาค",
        "Reset": "รีเซ็ต",
        "Invite": "เชิญบอท",
        "Support": "ซัพพอร์ต",
        "Back": "กลับ",
        "Create": "สร้าง",
        "Update": "อัปเดต",
        "Keyword": "คีย์เวิร์ด",
        "Enter the Keyword": "กรอกคีย์เวิร์ด",
        "Response": "การตอบกลับ",
        "Enter the Response": "กรอกข้อความตอบกลับ",
        "Support Hub": "ศูนย์ซัพพอร์ต",
        "Auto Setup": "ตั้งค่าอัตโนมัติ",
        "Member Logs": "ล็อกสมาชิก",
        "Message Logs": "ล็อกข้อความ",
        "Channel Logs": "ล็อกห้อง",
        "Role Logs": "ล็อกยศ",
        "Emoji Logs": "ล็อกอีโมจิ",
        "Webhook Logs": "ล็อกเว็บฮุก",
        "Invite Logs": "ล็อกคำเชิญ",
        "Guild Logs": "ล็อกกิลด์",
        "Voice Logs": "ล็อกห้องเสียง",
        "Anti Nuke Logs": "ล็อก Anti-Nuke",
        "Yes": "ใช่",
        "No": "ไม่",
        "Restart Now": "รีสตาร์ตตอนนี้",
        "Cancel Restart": "ยกเลิกการรีสตาร์ต",
        "Enable All ✅": "เปิดทั้งหมด ✅",
        "Disable All ⛔": "ปิดทั้งหมด ⛔",
        "Select A Setting To Edit": "เลือกการตั้งค่าที่ต้องการแก้ไข",
        "No Setting Found": "ไม่พบการตั้งค่า",
        "Add User ✨": "เพิ่มผู้ใช้ ✨",
        "Remove User": "ลบผู้ใช้",
        "Unknown User": "ผู้ใช้ไม่ทราบชื่อ",
        "No User Found": "ไม่พบผู้ใช้",
        "Rename Channel": "เปลี่ยนชื่อห้อง",
        "User Limit": "จำนวนผู้ใช้",
        "Automatic": "อัตโนมัติ",
        "US East": "สหรัฐตะวันออก",
        "US West": "สหรัฐตะวันตก",
        "US South": "สหรัฐใต้",
        "US Central": "สหรัฐตอนกลาง",
        "Singapore": "สิงคโปร์",
        "South Africa": "แอฟริกาใต้",
        "South Korea": "เกาหลีใต้",
        "Sydney": "ซิดนีย์",
        "Brazil": "บราซิล",
        "Hong Kong": "ฮ่องกง",
        "Russia": "รัสเซีย",
        "Europe": "ยุโรป",
        "India": "อินเดีย",
        "Japan": "ญี่ปุ่น",
        "No Prefix Subscription Added": "เพิ่มสิทธิ์ใช้งานแบบไม่ต้องมี Prefix แล้ว",
        "You Have Claimed No Prefix Subscription for": "คุณได้รับสิทธิ์ใช้งานแบบไม่ต้องมี Prefix ถึงวันที่",
        "Your No Prefix Subscription has been removed": "สิทธิ์ใช้งานแบบไม่ต้องมี Prefix ของคุณถูกยกเลิกแล้ว",
        "Silver Guild Premium Subscription Added": "เพิ่มพรีเมียมกิลด์ระดับ Silver แล้ว",
        "Golden Guild Premium Subscription Added": "เพิ่มพรีเมียมกิลด์ระดับ Gole แล้ว",
        "Diamond Guild Premium Subscription Added": "เพิ่มพรีเมียมกิลด์ระดับ Diamond แล้ว",
        "Subscription Removed": "ลบการสมัครใช้งานแล้ว",
        "AFK Removed": "ยกเลิกสถานะ AFK แล้ว",
        "Your AFK has been removed Globally": "สถานะ AFK ทั่วระบบของคุณถูกยกเลิกแล้ว",
        "Backup Commands": "คำสั่งสำรองข้อมูล",
        "Here are the available backup commands": "นี่คือคำสั่งสำรองข้อมูลที่ใช้งานได้",
        "Backup created successfully": "สร้างข้อมูลสำรองสำเร็จแล้ว",
        "An error occurred while creating the backup": "เกิดข้อผิดพลาดระหว่างสร้างข้อมูลสำรอง",
        "Ticket limit should be greater than 0": "จำนวนทิกเก็ตต้องมากกว่า 0",
        "Invalid image url": "ลิงก์รูปภาพไม่ถูกต้อง",
        "Invalid number": "ตัวเลขไม่ถูกต้อง",
        "The number must be less than 60": "ตัวเลขต้องน้อยกว่า 60",
    }
)

RUNTIME_PHRASES.update(
    {
        "Volume": "ระดับเสียง",
        "Volume (0-100)": "ระดับเสียง (0-100)",
        "Enter the new volume": "กรอกระดับเสียงใหม่",
        "Invite Bot": "เชิญบอท",
        "Invite Me ✨": "เชิญบอท ✨",
        "Vote Now": "โหวตตอนนี้",
        "Get Premium": "รับพรีเมียม",
        "Upgrade Premium": "อัปเกรดพรีเมียม",
        "Select Redeem Code Type": "เลือกประเภทโค้ด Redeem",
        "Set Code Validity": "กำหนดอายุโค้ด",
        "Generate Redeem Code": "สร้างโค้ด Redeem",
        "Enter Code Validity in Days": "กรอกอายุโค้ดเป็นจำนวนวัน",
        "Fun commands": "คำสั่งสนุก ๆ",
        "Ticket system": "ระบบทิกเก็ต",
        "Backup the server": "สำรองข้อมูลเซิร์ฟเวอร์",
        "Create a backup of the server": "สร้างข้อมูลสำรองของเซิร์ฟเวอร์",
        "You must be the owner of the server to use this command": "คุณต้องเป็นเจ้าของเซิร์ฟเวอร์จึงจะใช้คำสั่งนี้ได้",
        "Preview Welcome": "ดูตัวอย่างข้อความต้อนรับ",
        "Message & Embed": "ข้อความและ Embed",
        "Message": "ข้อความ",
        "Embed": "Embed",
        "Ticket Support": "ซัพพอร์ตทิกเก็ต",
        "Tickets Support": "ซัพพอร์ตทิกเก็ต",
        "Single role": "บทบาทเดียว",
        "Multiple roles": "หลายบทบาท",
        "Image OCR Verification": "ตรวจสอบ OCR จากภาพ",
        "AutoRole": "AutoRole",
        "AutoNick": "AutoNick",
        "Greet": "ทักทาย",
        "Autorole Commands": "คำสั่ง AutoRole",
        "These are the autorole commands": "นี่คือคำสั่งของ AutoRole",
        "Autorole Settings": "การตั้งค่า AutoRole",
        "AutoNick Commands": "คำสั่ง AutoNick",
        "These are the autonick commands": "นี่คือคำสั่งของ AutoNick",
        "Autonick Settings": "การตั้งค่า AutoNick",
        "Greet Commands": "คำสั่งทักทาย",
        "These are the greet commands": "นี่คือคำสั่งของระบบทักทาย",
        "Greet Settings": "การตั้งค่าระบบทักทาย",
        "Status": "สถานะ",
        "Delete After": "ลบหลังจาก",
        "Color": "สี",
        "Embed Title": "หัวข้อ Embed",
        "Embed Description": "คำอธิบาย Embed",
        "Embed Thumbnail": "รูปย่อ Embed",
        "Embed Image": "รูปภาพ Embed",
        "Embed Footer Text": "ข้อความส่วนท้าย Embed",
        "Embed Footer Icon": "ไอคอนส่วนท้าย Embed",
        "Embed Author Text": "ข้อความผู้เขียน Embed",
        "Embed Author Icon": "ไอคอนผู้เขียน Embed",
        "Embed Author URL": "ลิงก์ผู้เขียน Embed",
        "Set Format": "ตั้งค่ารูปแบบ",
        "Set Message": "ตั้งค่าข้อความ",
        "Edit Title": "แก้ไขหัวข้อ",
        "Edit Description": "แก้ไขคำอธิบาย",
        "Edit Thumbnail": "แก้ไขรูปย่อ",
        "Edit Image": "แก้ไขรูปภาพ",
        "Edit Footer": "แก้ไขส่วนท้าย",
        "Edit Author": "แก้ไขผู้เขียน",
    }
)


COMMAND_TEXT_KEYS: dict[str, dict[str, str]] = {
    "cmd_help_cog_desc": {
        "en": "Help commands",
        "th": "คำสั่งช่วยเหลือ",
    },
    "cmd_help_show_all": {
        "en": "Show all commands in bot",
        "th": "แสดงคำสั่งทั้งหมดของบอท",
    },
    "cmd_ping_help": {
        "en": "Get The Bot's Ping",
        "th": "ดูค่าปิงของบอท",
    },
    "cmd_invite_help": {
        "en": "Invite The Bot To Your Server",
        "th": "เชิญบอทเข้าร่วมเซิร์ฟเวอร์ของคุณ",
    },
    "cmd_support_help": {
        "en": "Join The Support Server",
        "th": "เข้าร่วมเซิร์ฟเวอร์ซัพพอร์ต",
    },
    "cmd_vote_help": {
        "en": "Vote For The Bot",
        "th": "โหวตให้บอท",
    },
    "cmd_stats_help": {
        "en": "Get The Bot's Stats",
        "th": "ดูข้อมูลสถานะของบอท",
    },
    "cmd_report_help": {
        "en": "Report a replied message to bot staff",
        "th": "ส่งรายงานข้อความที่ตอบกลับถึงทีมงานบอท",
    },
    "cmd_ticket_help": {
        "en": "Use these commands to manage tickets",
        "th": "ใช้คำสั่งเหล่านี้เพื่อจัดการระบบทิกเก็ต",
    },
    "cmd_welcomer_help": {
        "en": "Configure the welcomer for your server",
        "th": "ตั้งค่าระบบต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
    },
    "cmd_welcome_help": {
        "en": "Configure the welcome message for your server",
        "th": "ตั้งค่าข้อความต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
    },
    "cmd_welcome_settings_help": {
        "en": "Configure the welcome message settings for your server",
        "th": "ตั้งค่าการตั้งค่าข้อความต้อนรับสำหรับเซิร์ฟเวอร์ของคุณ",
    },
    "cmd_antinuke_toggle_help": {
        "en": "Enable/Disable Anti-Nuke system",
        "th": "เปิด/ปิดระบบป้องกัน Anti-Nuke",
    },
    "cmd_antinuke_enable_help": {
        "en": "Enable Anti-Nuke system",
        "th": "เปิดระบบป้องกัน Anti-Nuke",
    },
    "cmd_antinuke_disable_help": {
        "en": "Disable Anti-Nuke system",
        "th": "ปิดระบบป้องกัน Anti-Nuke",
    },
    "cmd_antinuke_edit_help": {
        "en": "Edit Anti-Nuke settings",
        "th": "แก้ไขการตั้งค่า Anti-Nuke",
    },
    "cmd_manage_roles_help": {
        "en": "Manage roles of the users",
        "th": "จัดการบทบาทของผู้ใช้",
    },
    "cmd_member_param_help": {
        "en": "The member to assign or remove the role",
        "th": "สมาชิกที่ต้องการเพิ่มหรือลดยศ",
    },
    "cmd_role_param_help": {
        "en": "The role to assign or remove",
        "th": "ยศที่ต้องการเพิ่มหรือลบ",
    },
}

COMMAND_TEXT_KEYS.update(
    {
        "cmd_autorole_help": {
            "en": "Configure the autorole for your server",
            "th": "ตั้งค่า autorole สำหรับเซิร์ฟเวอร์ของคุณ",
        },
        "cmd_autonick_new_members_help": {
            "en": "Configure the autonick for your server new members",
            "th": "ตั้งค่า autonick สำหรับสมาชิกใหม่ในเซิร์ฟเวอร์ของคุณ",
        },
        "cmd_greet_channel_message_help": {
            "en": "Configure the greet channel & message for your server",
            "th": "ตั้งค่าห้องและข้อความ greet สำหรับเซิร์ฟเวอร์ของคุณ",
        },
        "cmd_autorole_settings_help": {
            "en": "Configure the autorole settings for your server",
            "th": "ตั้งค่าการตั้งค่า autorole สำหรับเซิร์ฟเวอร์ของคุณ",
        },
        "cmd_autonick_help": {
            "en": "Configure the autonick for your server",
            "th": "ตั้งค่า autonick สำหรับเซิร์ฟเวอร์ของคุณ",
        },
        "cmd_autonick_settings_help": {
            "en": "Configure the autonick settings for your server",
            "th": "ตั้งค่าการตั้งค่า autonick สำหรับเซิร์ฟเวอร์ของคุณ",
        },
        "cmd_greet_settings_help": {
            "en": "Configure the greet settings for your server",
            "th": "ตั้งค่าการตั้งค่า greet สำหรับเซิร์ฟเวอร์ของคุณ",
        },
        "cmd_vcmute_help": {
            "en": "Mute a user in a voice channel",
            "th": "ปิดเสียงผู้ใช้ในห้องเสียง",
        },
        "cmd_vcunmute_help": {
            "en": "Unmute a user in a voice channel",
            "th": "ยกเลิกปิดเสียงผู้ใช้ในห้องเสียง",
        },
        "cmd_vcdeafen_help": {
            "en": "Deafen a user in a voice channel",
            "th": "ปิดการได้ยินผู้ใช้ในห้องเสียง",
        },
        "cmd_vcundeafen_help": {
            "en": "Undeafen a user in a voice channel",
            "th": "ยกเลิกปิดการได้ยินผู้ใช้ในห้องเสียง",
        },
        "cmd_vcmove_help": {
            "en": "Move a user to a voice channel",
            "th": "ย้ายผู้ใช้ไปยังห้องเสียง",
        },
        "cmd_vcmoveall_help": {
            "en": "Move all users in a voice channel to another voice channel",
            "th": "ย้ายผู้ใช้ทั้งหมดในห้องเสียงไปยังอีกห้องเสียง",
        },
        "cmd_vcdisconnect_help": {
            "en": "Disconnect a user from a voice channel",
            "th": "ตัดการเชื่อมต่อผู้ใช้ออกจากห้องเสียง",
        },
        "cmd_vcpull_help": {
            "en": "Pull a user to your voice channel",
            "th": "ดึงผู้ใช้เข้าห้องเสียงของคุณ",
        },
        "cmd_vcmuteall_help": {
            "en": "Mute all users in a voice channel",
            "th": "ปิดเสียงผู้ใช้ทั้งหมดในห้องเสียง",
        },
        "cmd_vcunmuteall_help": {
            "en": "Unmute all users in a voice channel",
            "th": "ยกเลิกปิดเสียงผู้ใช้ทั้งหมดในห้องเสียง",
        },
        "cmd_vcdeafenall_help": {
            "en": "Deafen all users in a voice channel",
            "th": "ปิดการได้ยินผู้ใช้ทั้งหมดในห้องเสียง",
        },
        "cmd_vcundeafenall_help": {
            "en": "Undeafen all users in a voice channel",
            "th": "ยกเลิกปิดการได้ยินผู้ใช้ทั้งหมดในห้องเสียง",
        },
        "cmd_vcdisconnectall_help": {
            "en": "Disconnect all users in a voice channel",
            "th": "ตัดการเชื่อมต่อผู้ใช้ทั้งหมดออกจากห้องเสียง",
        },
        "cmd_purge_help": {
            "en": "Purge messages in a channel",
            "th": "ลบข้อความในห้อง",
        },
        "cmd_purge_user_help": {
            "en": "Purge messages of a user in a channel",
            "th": "ลบข้อความของผู้ใช้ในห้อง",
        },
        "cmd_purge_images_help": {
            "en": "Purge messages containing images in a channel",
            "th": "ลบข้อความที่มีรูปภาพในห้อง",
        },
        "cmd_purge_links_help": {
            "en": "Purge messages containing links in a channel",
            "th": "ลบข้อความที่มีลิงก์ในห้อง",
        },
        "cmd_purge_bots_help": {
            "en": "Purge messages of a bot in a channel",
            "th": "ลบข้อความของบอทในห้อง",
        },
        "cmd_ban_help": {"en": "Ban a user from the server", "th": "แบนผู้ใช้ออกจากเซิร์ฟเวอร์"},
        "cmd_kick_help": {"en": "Kick a user from the server", "th": "เตะผู้ใช้ออกจากเซิร์ฟเวอร์"},
        "cmd_unban_help": {"en": "Unban a user from the server", "th": "ปลดแบนผู้ใช้จากเซิร์ฟเวอร์"},
        "cmd_unbanall_help": {
            "en": "Unban all users from the server",
            "th": "ปลดแบนผู้ใช้ทั้งหมดจากเซิร์ฟเวอร์",
        },
        "cmd_ignore_help": {"en": "Ignore users or channels", "th": "เพิกเฉยผู้ใช้หรือห้อง"},
        "cmd_ignore_user_help": {"en": "Ignore a user", "th": "เพิกเฉยผู้ใช้"},
        "cmd_unignore_user_help": {"en": "Unignore a user", "th": "ยกเลิกเพิกเฉยผู้ใช้"},
        "cmd_list_ignored_users_help": {"en": "List ignored users", "th": "แสดงรายการผู้ใช้ที่ถูกเพิกเฉย"},
        "cmd_ignore_channel_help": {"en": "Ignore a channel", "th": "เพิกเฉยห้อง"},
        "cmd_unignore_channel_help": {"en": "Unignore a channel", "th": "ยกเลิกเพิกเฉยห้อง"},
        "cmd_list_ignored_channels_help": {
            "en": "List ignored channels",
            "th": "แสดงรายการห้องที่ถูกเพิกเฉย",
        },
        "cmd_lockall_help": {"en": "Lock all channels in the server", "th": "ล็อกทุกห้องในเซิร์ฟเวอร์"},
        "cmd_unlockall_help": {
            "en": "Unlock all channels in the server",
            "th": "ปลดล็อกทุกห้องในเซิร์ฟเวอร์",
        },
        "cmd_hide_channel_help": {"en": "Hide a channel", "th": "ซ่อนห้อง"},
        "cmd_hideall_help": {"en": "Hide all channels in the server", "th": "ซ่อนทุกห้องในเซิร์ฟเวอร์"},
        "cmd_unhide_channel_help": {"en": "Unhide a channel", "th": "ยกเลิกซ่อนห้อง"},
        "cmd_unhideall_help": {
            "en": "Unhide all channels in the server",
            "th": "ยกเลิกซ่อนทุกห้องในเซิร์ฟเวอร์",
        },
        "cmd_manage_human_roles_help": {
            "en": "Manage roles of the humans in the server",
            "th": "จัดการยศของผู้ใช้จริงในเซิร์ฟเวอร์",
        },
        "cmd_manage_bot_roles_help": {
            "en": "Manage roles of the bots in the server",
            "th": "จัดการยศของบอทในเซิร์ฟเวอร์",
        },
        "cmd_mute_member_help": {"en": "Mute a member in the server", "th": "ปิดเสียงสมาชิกในเซิร์ฟเวอร์"},
        "cmd_unmute_member_help": {
            "en": "Unmute a member in the server",
            "th": "ยกเลิกปิดเสียงสมาชิกในเซิร์ฟเวอร์",
        },
        "cmd_unmute_all_members_help": {
            "en": "Unmute all members in the server",
            "th": "ยกเลิกปิดเสียงสมาชิกทั้งหมดในเซิร์ฟเวอร์",
        },
        "cmd_manage_media_channels_help": {
            "en": "Manage media channels in the server",
            "th": "จัดการห้องมีเดียในเซิร์ฟเวอร์",
        },
        "cmd_add_media_channel_help": {"en": "Add a media channel", "th": "เพิ่มห้องมีเดีย"},
        "cmd_remove_media_channel_help": {"en": "Remove a media channel", "th": "ลบห้องมีเดีย"},
        "cmd_list_media_channels_help": {"en": "List media channels", "th": "แสดงรายการห้องมีเดีย"},
        "cmd_reset_media_channels_help": {"en": "Reset all media channels", "th": "รีเซ็ตห้องมีเดียทั้งหมด"},
        "cmd_change_nickname_help": {
            "en": "Change the nickname of a member",
            "th": "เปลี่ยนชื่อเล่นของสมาชิก",
        },
        "cmd_steal_emoji_help": {
            "en": "Can Be Used To Steal Emoji/Multiple Emojis From A Server",
            "th": "ใช้เพื่อคัดลอกอีโมจิ/หลายอีโมจิจากเซิร์ฟเวอร์",
        },
        "cmd_noprefix_toggle_help": {
            "en": "Enable/Disable The No Prefix Feature",
            "th": "เปิด/ปิดฟีเจอร์ไม่ต้องใช้พรีฟิกซ์",
        },
        "cmd_afk_set_help": {"en": "Set Your AFK Status", "th": "ตั้งค่าสถานะ AFK ของคุณ"},
        "cmd_prefix_change_or_get_help": {
            "en": "Change The Bot's Prefix or Get The Current Prefix",
            "th": "เปลี่ยนพรีฟิกซ์บอทหรือดูพรีฟิกซ์ปัจจุบัน",
        },
        "cmd_relationship_set_help": {
            "en": "Set Your Relationship Status",
            "th": "ตั้งค่าสถานะความสัมพันธ์ของคุณ",
        },
        "cmd_generate_redeem_help": {
            "en": "Generate different types of redeemable codes",
            "th": "สร้างโค้ด Redeem ได้หลายประเภท",
        },
        "cmd_botinfo_help": {
            "en": "View bot and developer information",
            "th": "ดูข้อมูลบอทและทีมพัฒนา",
        },
        "cmd_botinfo_bot_help": {
            "en": "Show detailed bot information",
            "th": "แสดงข้อมูลรายละเอียดของบอท",
        },
        "cmd_botinfo_dev_help": {
            "en": "Show developer information",
            "th": "แสดงข้อมูลทีมพัฒนา",
        },
        "cmd_profile_display_help": {"en": "Display a user's profile", "th": "แสดงโปรไฟล์ผู้ใช้"},
        "cmd_avatar_display_help": {"en": "Display a user's avatar", "th": "แสดงรูปโปรไฟล์ผู้ใช้"},
        "cmd_banner_display_help": {"en": "Display a user's banner", "th": "แสดงแบนเนอร์ของผู้ใช้"},
        "cmd_banner_server_display_help": {
            "en": "Display the server's banner",
            "th": "แสดงแบนเนอร์ของเซิร์ฟเวอร์",
        },
        "cmd_list_group_help": {"en": "different list commands", "th": "คำสั่ง list แบบต่าง ๆ"},
        "cmd_list_emojis_help": {
            "en": "List all the emojis in the server",
            "th": "แสดงอีโมจิทั้งหมดในเซิร์ฟเวอร์",
        },
        "cmd_list_channels_help": {
            "en": "List all the channels in the server",
            "th": "แสดงห้องทั้งหมดในเซิร์ฟเวอร์",
        },
        "cmd_list_bots_help": {
            "en": "List all the bots in the server",
            "th": "แสดงบอททั้งหมดในเซิร์ฟเวอร์",
        },
        "cmd_list_admins_help": {
            "en": "List all the admins in the server",
            "th": "แสดงแอดมินทั้งหมดในเซิร์ฟเวอร์",
        },
        "cmd_list_bans_help": {"en": "List all the bans in the server", "th": "แสดงรายการแบนทั้งหมดในเซิร์ฟเวอร์"},
        "cmd_list_roles_help": {
            "en": "List all the roles in the server",
            "th": "แสดงยศทั้งหมดในเซิร์ฟเวอร์",
        },
        "cmd_list_boosters_help": {
            "en": "List all the boosters in the server",
            "th": "แสดงผู้บูสต์ทั้งหมดในเซิร์ฟเวอร์",
        },
        "cmd_list_members_in_role_help": {
            "en": "List all the members in a role",
            "th": "แสดงสมาชิกทั้งหมดในยศ",
        },
        "cmd_uptime_help": {"en": "Get the uptime of the bot", "th": "ดูระยะเวลาที่บอททำงาน"},
        "cmd_roleicon_set_help": {"en": "Set a role icon", "th": "ตั้งค่าไอคอนยศ"},
        "cmd_serverinfo_help": {
            "en": "Get information about the server",
            "th": "ดูข้อมูลเกี่ยวกับเซิร์ฟเวอร์",
        },
        "cmd_userinfo_help": {"en": "Get information about a user", "th": "ดูข้อมูลเกี่ยวกับผู้ใช้"},
        "cmd_roleinfo_help": {"en": "Get information about a role", "th": "ดูข้อมูลเกี่ยวกับยศ"},
        "cmd_membercount_help": {
            "en": "Get the member count of the server",
            "th": "ดูจำนวนสมาชิกของเซิร์ฟเวอร์",
        },
        "cmd_firstmessage_help": {
            "en": "Get the first message of a channel",
            "th": "ดูข้อความแรกของห้อง",
        },
        "cmd_boostcount_help": {
            "en": "Get the boost count of the server",
            "th": "ดูจำนวนบูสต์ของเซิร์ฟเวอร์",
        },
    }
)

EMBED_COLOR_PALETTE: tuple[int, ...] = (
    0x5865F2,
    0x57F287,
    0xFEE75C,
    0xEB459E,
    0xED4245,
    0x1ABC9C,
    0x3498DB,
    0x9B59B6,
)


def _normalize_command_text(text: str) -> str:
    return " ".join((text or "").strip().split()).casefold()


COMMAND_TEXT_BY_ENGLISH: dict[str, str] = {
    _normalize_command_text(values["en"]): key
    for key, values in COMMAND_TEXT_KEYS.items()
    if isinstance(values, dict) and values.get("en")
}

COMMAND_TEXT_BY_THAI: dict[str, str] = {
    _normalize_command_text(values["th"]): key
    for key, values in COMMAND_TEXT_KEYS.items()
    if isinstance(values, dict) and values.get("th")
}

MESSAGE_KEY_BY_THAI: dict[str, str] = {
    _normalize_command_text(value): key
    for key, value in MESSAGES.get("th", {}).items()
    if isinstance(value, str) and value.strip()
}

MESSAGE_KEY_BY_ENGLISH: dict[str, str] = {
    _normalize_command_text(value): key
    for key, value in MESSAGES.get("en", {}).items()
    if isinstance(value, str) and value.strip()
}


def _resolve_command_text_key(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    if text.startswith("i18n:"):
        key = text.split(":", 1)[1].strip()
        return key or None
    normalized = _normalize_command_text(text)
    return COMMAND_TEXT_BY_ENGLISH.get(normalized) or COMMAND_TEXT_BY_THAI.get(normalized)


def _resolve_message_key_from_literal(text: str) -> str | None:
    normalized = _normalize_command_text(text)
    return MESSAGE_KEY_BY_ENGLISH.get(normalized) or MESSAGE_KEY_BY_THAI.get(normalized)


def _map_literal_from_locales(text: str, target_lang: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    normalized = _normalize_command_text(text)
    if not normalized:
        return text

    command_key = COMMAND_TEXT_BY_ENGLISH.get(normalized) or COMMAND_TEXT_BY_THAI.get(normalized)
    if command_key:
        values = COMMAND_TEXT_KEYS.get(command_key, {})
        if isinstance(values, dict):
            localized = values.get(target_lang) or values.get("en")
            if isinstance(localized, str) and localized:
                return localized

    message_key = _resolve_message_key_from_literal(text)
    if message_key:
        localized = (
            MESSAGES.get(target_lang, {}).get(message_key)
            or MESSAGES.get("en", {}).get(message_key)
            or MESSAGES.get("th", {}).get(message_key)
        )
        if isinstance(localized, str) and localized:
            return localized

    return text


def _command_text_for_lang(text: str, lang: str) -> str:
    key = _resolve_command_text_key(text)
    if not key:
        return text

    source_en = text
    source_th = text
    if key in COMMAND_TEXT_KEYS:
        values = COMMAND_TEXT_KEYS[key]
        source_en = values.get("en") or source_en
        source_th = values.get("th") or source_th
        localized = values.get(lang) or values.get("en") or text
    else:
        source_en = MESSAGES.get("en", {}).get(key) or source_en
        source_th = MESSAGES.get("th", {}).get(key) or source_th
        localized = (
            MESSAGES.get(lang, {}).get(key)
            or MESSAGES["en"].get(key)
            or MESSAGES["th"].get(key)
            or text
        )

    localized = str(localized or text)

    if lang == "th":
        if not _contains_thai(localized):
            candidate_th = _translate_command_text_to_th(str(source_en or ""))
            if not _contains_thai(candidate_th):
                candidate_th = _translate_text_runtime_rule_based(str(source_en or ""), "th")
            if not _contains_thai(candidate_th):
                provider_th = _translate_text_with_runtime_fallback_provider(
                    str(source_en or ""),
                    "en2th",
                )
                if _contains_thai(provider_th):
                    candidate_th = provider_th
            if not _contains_thai(candidate_th) and _contains_thai(str(source_th or "")):
                candidate_th = str(source_th or "")
            if _contains_thai(candidate_th):
                localized = candidate_th
            else:
                localized = _TH_COMMAND_GENERIC_FALLBACK
        return _normalize_mixed_language_text(localized, "th")

    if lang == "en":
        if _contains_thai(localized) or _looks_unusable_english(localized):
            candidate_en = _translate_text_runtime_rule_based(str(source_th or ""), "en")
            candidate_en = _normalize_mixed_language_text(candidate_en, "en")
            if (
                not candidate_en
                or _contains_thai(candidate_en)
                or _looks_unusable_english(candidate_en)
            ):
                provider_en = _normalize_mixed_language_text(
                    _translate_text_with_runtime_fallback_provider(
                        str(source_th or ""),
                        "th2en",
                    ),
                    "en",
                )
                if (
                    provider_en
                    and not _contains_thai(provider_en)
                    and not _looks_unusable_english(provider_en)
                ):
                    candidate_en = provider_en
            if (
                not candidate_en
                or _contains_thai(candidate_en)
                or _looks_unusable_english(candidate_en)
            ):
                source_en_text = str(source_en or "")
                if (
                    _contains_english(source_en_text)
                    and not _contains_thai(source_en_text)
                    and not _looks_unusable_english(source_en_text)
                ):
                    candidate_en = source_en_text
                else:
                    candidate_en = "Command for use in the system"
            localized = candidate_en
        return _normalize_mixed_language_text(localized, "en")

    return localized


def translate(key_or_text: str, lang: str) -> str:
    """Public API to translate a key or literal text to a specific language."""
    # Ensure we handle keys both with and without i18n: prefix
    text = key_or_text if key_or_text.startswith("i18n:") else f"i18n:{key_or_text}"
    return _command_text_for_lang(text, lang)


def localize_command_text(text: str, guild_id: int | None) -> str:
    if not isinstance(text, str) or not text:
        return text
    lang = guild_lang(guild_id)
    localized = _command_text_for_lang(text, lang)
    if localized != text:
        return _normalize_mixed_language_text(localized, lang)
    if _I18N_FILE_FIRST_MODE:
        localized = _map_literal_from_locales(text, lang)
        if localized != text:
            return _normalize_mixed_language_text(localized, lang)
        if lang == "th" and _I18N_HEURISTIC_COMMAND_FALLBACK_ENABLED:
            translated = _translate_command_text_to_th(text)
            if translated != text and translated != _TH_COMMAND_GENERIC_FALLBACK:
                return _normalize_mixed_language_text(translated, lang)
    if (
        lang == "th"
        and not _I18N_FILE_FIRST_MODE
        and _I18N_HEURISTIC_COMMAND_FALLBACK_ENABLED
    ):
        translated = _translate_command_text_to_th(text)
        if translated != text:
            return _normalize_mixed_language_text(translated, lang)
    return _translate_text_runtime(text, guild_id)

COMMON_COMMAND_PHRASES: dict[str, str] = {
    "configure the": "ตั้งค่า",
    "for your server": "สำหรับเซิร์ฟเวอร์ของคุณ",
    "enable/disable": "เปิด/ปิด",
    "enable or disable": "เปิดหรือปิด",
    "ticket support": "ซัพพอร์ตทิกเก็ต",
    "tickets support": "ซัพพอร์ตทิกเก็ต",
    "ticket ซัพพอร์ต": "ซัพพอร์ตทิกเก็ต",
    "tickets ซัพพอร์ต": "ซัพพอร์ตทิกเก็ต",
    "single role": "บทบาทเดียว",
    "multiple roles": "หลายบทบาท",
    "image ocr verification": "ตรวจสอบ OCR จากภาพ",
}

COMMON_COMMAND_PHRASES.update(
    {
        "select a ticket module to edit": "เลือกโมดูลทิกเก็ตที่ต้องการแก้ไข",
        "select a module to edit": "เลือกโมดูลที่ต้องการแก้ไข",
        "select a module to setup": "เลือกโมดูลที่ต้องการตั้งค่า",
        "select a queue to delete": "เลือกคิวที่ต้องการลบ",
        "select a whitelisted user to edit": "เลือกผู้ใช้ในไวท์ลิสต์ที่ต้องการแก้ไข",
        "select a user to whitelist": "เลือกผู้ใช้ที่จะเพิ่มในไวท์ลิสต์",
        "select a user to transfer ownership to": "เลือกผู้ใช้ที่จะโอนสิทธิ์ความเป็นเจ้าของให้",
        "select whitelisted roles": "เลือกยศที่ยกเว้น",
        "select whitelisted channels": "เลือกห้องที่ยกเว้น",
        "select support roles": "เลือกยศซัพพอร์ต",
        "select the welcome type": "เลือกรูปแบบการต้อนรับ",
        "select the welcome channel": "เลือกห้องต้อนรับ",
        "select the embed color": "เลือกสีของ Embed",
        "select the channel to set as greet channel": "เลือกห้องที่จะใช้เป็นห้องทักทาย",
        "select the roles to set as autorole": "เลือกยศที่จะตั้งเป็น AutoRole",
        "select your relationship": "เลือกสถานะความสัมพันธ์ของคุณ",
        "select request text channel": "เลือกห้องข้อความสำหรับรับคำขอเพลง",
        "select target voice channel": "เลือกห้องเสียงเป้าหมาย",
        "select a vc channel": "เลือกห้องเสียง",
        "select a category": "เลือกหมวดหมู่",
        "select a category to view": "เลือกหมวดหมู่ที่ต้องการดู",
        "select a command to view": "เลือกคำสั่งที่ต้องการดู",
        "select a region": "เลือกภูมิภาค",
        "select a page": "เลือกหน้า",
        "select a type": "เลือกประเภท",
        "select a limit": "เลือกจำนวนจำกัด",
        "select a punishment": "เลือกบทลงโทษ",
        "select the ": "เลือก",
        "select a ": "เลือก",
        "enter the new ": "กรอก",
        "enter the ": "กรอก",
        "back to ": "กลับไป",
        "view transcript": "ดูบันทึกแชท",
        "close ticket": "ปิดทิกเก็ต",
        "open ticket": "เปิดทิกเก็ต",
        "delete ticket channel": "ลบห้องทิกเก็ต",
        "close menu": "ปิดเมนู",
        "back menu": "กลับเมนู",
        "back to home": "กลับหน้าหลัก",
        "back to welcomer": "กลับไปหน้าต้อนรับ",
        "previous page": "หน้าก่อนหน้า",
        "next page": "หน้าถัดไป",
        "stop menu": "หยุดเมนู",
        "create module": "สร้างโมดูล",
        "delete module": "ลบโมดูล",
        "enable module": "เปิดใช้งานโมดูล",
        "disable module": "ปิดใช้งานโมดูล",
        "set ticket limit": "กำหนดจำนวนทิกเก็ต",
        "send panel message": "ส่งข้อความแผงทิกเก็ต",
        "edit message text": "แก้ไขข้อความ",
        "edit message content": "แก้ไขเนื้อหาข้อความ",
        "edit embed card": "แก้ไขการ์ด Embed",
        "edit embed title": "แก้ไขหัวข้อ Embed",
        "edit embed description": "แก้ไขคำอธิบาย Embed",
        "edit embed thumbnail": "แก้ไขรูปย่อ Embed",
        "edit embed image": "แก้ไขรูปภาพ Embed",
        "edit footer": "แก้ไขส่วนท้าย",
        "edit author": "แก้ไขผู้เขียน",
        "preview welcome": "ดูตัวอย่างข้อความต้อนรับ",
        "set format": "ตั้งค่ารูปแบบ",
        "set message": "ตั้งค่าข้อความ",
        "set delete after": "ตั้งเวลาลบอัตโนมัติ",
        "default volume": "ระดับเสียงเริ่มต้น",
        "search on google": "ค้นหาบน Google",
        "upgrade premium": "อัปเกรดพรีเมียม",
        "get premium": "รับพรีเมียม",
        "buy premium to use this feature": "ซื้อพรีเมียมเพื่อใช้ฟีเจอร์นี้",
        "upgrade for no prefix": "อัปเกรดเพื่อใช้งานแบบไม่ต้องมี Prefix",
        "guild afk mode": "โหมด AFK ของเซิร์ฟเวอร์",
        "global afk mode": "โหมด AFK ทั่วระบบ",
        "add as emoji": "เพิ่มเป็นอีโมจิ",
        "add as sticker": "เพิ่มเป็นสติกเกอร์",
        "click to view": "คลิกเพื่อดู",
        "view message": "ดูข้อความ",
    }
)

COMMON_COMMAND_WORDS: dict[str, str] = {
    "commands": "คำสั่ง",
    "command": "คำสั่ง",
    "server": "เซิร์ฟเวอร์",
    "guild": "กิลด์",
    "users": "ผู้ใช้",
    "user": "ผู้ใช้",
    "members": "สมาชิก",
    "member": "สมาชิก",
    "roles": "ยศ",
    "role": "ยศ",
    "channels": "ห้อง",
    "channel": "ห้อง",
    "messages": "ข้อความ",
    "message": "ข้อความ",
    "settings": "การตั้งค่า",
    "setting": "การตั้งค่า",
    "system": "ระบบ",
    "module": "โมดูล",
    "bot": "บอท",
    "voice": "เสียง",
    "music": "เพลง",
    "ticket": "ทิกเก็ต",
    "giveaway": "กิจกรรม",
    "security": "ความปลอดภัย",
    "moderation": "การดูแล",
    "welcome": "ต้อนรับ",
    "welcomer": "ต้อนรับ",
    "automod": "ออโต้มอด",
    "utils": "ยูทิลิตี้",
    "utility": "ยูทิลิตี้",
    "stats": "สถิติ",
    "status": "สถานะ",
    "profile": "โปรไฟล์",
    "code": "โค้ด",
    "redeem": "รีดีม",
    "validity": "อายุ",
    "expires": "หมดอายุ",
    "premium": "พรีเมียม",
    "buy": "ซื้อ",
    "enter": "กรอก",
    "invalid": "ไม่ถูกต้อง",
    "claimed": "ถูกใช้แล้ว",
    "details": "รายละเอียด",
    "muted": "ปิดเสียง",
    "unmuted": "ยกเลิกปิดเสียง",
    "deafened": "ปิดการได้ยิน",
    "undeafened": "ยกเลิกปิดการได้ยิน",
    "moved": "ย้าย",
    "disconnected": "ตัดการเชื่อมต่อ",
    "pulled": "ดึงเข้า",
    "already": "อยู่แล้ว",
    "error": "ข้อผิดพลาด",
    "emoji": "อีโมจิ",
    "banner": "แบนเนอร์",
    "enable": "เปิด",
    "disable": "ปิด",
    "display": "แสดง",
    "show": "แสดง",
    "list": "แสดงรายการ",
    "manage": "จัดการ",
    "create": "สร้าง",
    "delete": "ลบ",
    "edit": "แก้ไข",
    "get": "ดู",
}

COMMON_COMMAND_WORDS.update(
    {
        "select": "เลือก",
        "page": "หน้า",
        "pages": "หน้า",
        "close": "ปิด",
        "back": "กลับ",
        "home": "หน้าหลัก",
        "new": "ใหม่",
        "open": "เปิด",
        "limit": "จำนวนจำกัด",
        "support": "ซัพพอร์ต",
        "queue": "คิว",
        "view": "ดู",
        "transcript": "บันทึกแชท",
        "panel": "แผง",
        "category": "หมวดหมู่",
        "categories": "หมวดหมู่",
        "type": "ประเภท",
        "punishment": "บทลงโทษ",
        "keyword": "คีย์เวิร์ด",
        "response": "การตอบกลับ",
        "embed": "Embed",
        "author": "ผู้เขียน",
        "footer": "ส่วนท้าย",
        "thumbnail": "รูปย่อ",
        "image": "รูปภาพ",
        "content": "เนื้อหา",
        "title": "หัวข้อ",
        "description": "คำอธิบาย",
        "color": "สี",
        "format": "รูปแบบ",
        "active": "กำลังทำงาน",
        "ended": "สิ้นสุดแล้ว",
        "participants": "ผู้เข้าร่วม",
        "automatic": "อัตโนมัติ",
        "ownership": "ความเป็นเจ้าของ",
        "rename": "เปลี่ยนชื่อ",
        "change": "เปลี่ยน",
        "bitrate": "บิตเรต",
        "yes": "ใช่",
        "no": "ไม่",
        "restart": "เริ่มใหม่",
        "cancel": "ยกเลิก",
    }
)


_PROTECTED_SEGMENT_SPLIT_RE = re.compile(
    r"(`[^`]*`|https?://[^\s]+|<t:-?\d{1,13}(?::[tTdDfFR])?>|<a?:[A-Za-z0-9_]{2,32}:\d{5,20}>|<@[!&]?\d{5,20}>|<#\d{5,20}>|</[^:\n>]{1,100}:\d{5,20}>)"
)
_DISCORD_SPECIAL_SEGMENT_RE = re.compile(
    r"^(?:<t:-?\d{1,13}(?::[tTdDfFR])?>|<a?:[A-Za-z0-9_]{2,32}:\d{5,20}>|<@[!&]?\d{5,20}>|<#\d{5,20}>|</[^:\n>]{1,100}:\d{5,20}>)$"
)
_RUNTIME_TRANSLATION_TOKEN_RE = re.compile(
    r"(`[^`]*`|https?://[^\s]+|<t:-?\d{1,13}(?::[tTdDfFR])?>|<a?:[A-Za-z0-9_]{2,32}:\d{5,20}>|<@[!&]?\d{5,20}>|<#\d{5,20}>|</[^:\n>]{1,100}:\d{5,20}>|[!/#][A-Za-z0-9_.:-]{1,64}|[A-Za-z_][A-Za-z0-9_]{1,64}\.[A-Za-z_][A-Za-z0-9_]{1,64})"
)


def _split_protected_segments(text: str) -> list[str]:
    return re.split(_PROTECTED_SEGMENT_SPLIT_RE, text)


def _is_protected_segment(part: str) -> bool:
    if not isinstance(part, str) or not part:
        return False
    if (part.startswith("`") and part.endswith("`")) or part.startswith("http://") or part.startswith("https://"):
        return True
    return bool(_DISCORD_SPECIAL_SEGMENT_RE.fullmatch(part))


def _mask_runtime_translation_tokens(payload: str) -> tuple[str, dict[str, str]]:
    text = str(payload or "")
    if not text:
        return text, {}
    token_map: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        token_key = f"SKYI18NTOKEN{len(token_map)}ZXQ"
        token_map[token_key] = str(match.group(0) or "")
        return token_key

    masked = _RUNTIME_TRANSLATION_TOKEN_RE.sub(_replace, text)
    return masked, token_map


def _restore_runtime_translation_tokens(payload: str, token_map: dict[str, str]) -> str:
    text = str(payload or "")
    if not text or not token_map:
        return text
    restored = text
    for token_key, token_value in token_map.items():
        restored = restored.replace(token_key, token_value)
    return restored


def _translate_with_common_patterns(text: str) -> str:
    if not text:
        return text

    def _translate_segment(segment: str) -> str:
        translated = segment

        for source, target in sorted(
            COMMON_COMMAND_PHRASES.items(), key=lambda item: len(item[0]), reverse=True
        ):
            translated = re.sub(
                rf"\b{re.escape(source)}\b", target, translated, flags=re.IGNORECASE
            )

        for source, target in sorted(
            COMMON_COMMAND_WORDS.items(), key=lambda item: len(item[0]), reverse=True
        ):
            translated = re.sub(
                rf"\b{re.escape(source)}\b", target, translated, flags=re.IGNORECASE
            )

        return translated

    parts = _split_protected_segments(text)
    translated_parts = []
    for part in parts:
        if _is_protected_segment(part):
            translated_parts.append(part)
        else:
            translated_parts.append(_translate_segment(part))
    return "".join(translated_parts)


_TH_COMMAND_GENERIC_FALLBACK = _translate_command_text_to_th("__i18n_unknown__")


_PATCHED = False


def _read_runtime_translation_cache(language: str, text: str) -> str | None:
    payload = str(text or "")
    if (
        not payload
        or len(payload) > _I18N_RUNTIME_TRANSLATION_CACHE_MAX_TEXT_LENGTH
    ):
        return None
    key = (str(language or DEFAULT_LANG), payload)
    with _I18N_RUNTIME_CACHE_LOCK:
        return _I18N_RUNTIME_TRANSLATION_CACHE.get(key)


def _write_runtime_translation_cache(language: str, text: str, translated: str) -> None:
    payload = str(text or "")
    if (
        not payload
        or len(payload) > _I18N_RUNTIME_TRANSLATION_CACHE_MAX_TEXT_LENGTH
    ):
        return
    key = (str(language or DEFAULT_LANG), payload)
    with _I18N_RUNTIME_CACHE_LOCK:
        if key in _I18N_RUNTIME_TRANSLATION_CACHE:
            _I18N_RUNTIME_TRANSLATION_CACHE_ORDER[:] = [
                item for item in _I18N_RUNTIME_TRANSLATION_CACHE_ORDER if item != key
            ]
        _I18N_RUNTIME_TRANSLATION_CACHE[key] = str(translated or "")
        _I18N_RUNTIME_TRANSLATION_CACHE_ORDER.append(key)
        while len(_I18N_RUNTIME_TRANSLATION_CACHE_ORDER) > _I18N_RUNTIME_TRANSLATION_CACHE_LIMIT:
            oldest = _I18N_RUNTIME_TRANSLATION_CACHE_ORDER.pop(0)
            _I18N_RUNTIME_TRANSLATION_CACHE.pop(oldest, None)


def guild_lang(guild_id: int | None) -> str:
    if guild_id is None:
        return DEFAULT_LANG
    lang = str(cache.guilds.get(str(guild_id), {}).get("language", DEFAULT_LANG)).lower()
    if lang not in SUPPORTED_LANGS:
        return DEFAULT_LANG
    return lang


def tr(key: str, guild_id: int | None = None, **kwargs: Any) -> str:
    lang = guild_lang(guild_id)
    template = (
        MESSAGES.get(lang, {}).get(key)
        or MESSAGES.get("en", {}).get(key)
        or MESSAGES.get("th", {}).get(key)
        or key
    )
    if template == key:
        template = _translate_text_runtime(template, guild_id)
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def _replace_runtime_phrase(text: str, source: str, target: str) -> str:
    if not text or not source:
        return text
    # Avoid partial-word replacements (e.g. "Red" inside "Redeem").
    # If a phrase is plain words/spaces, replace it only on word boundaries.
    if re.fullmatch(r"[A-Za-z0-9 ]+", source):
        pattern = rf"\b{re.escape(source)}\b"
    else:
        pattern = re.escape(source)
    parts = _split_protected_segments(text)
    translated_parts: list[str] = []
    for part in parts:
        if _is_protected_segment(part):
            translated_parts.append(part)
            continue
        translated_parts.append(re.sub(pattern, target, part, flags=re.IGNORECASE))
    return "".join(translated_parts)


RUNTIME_PHRASES_REVERSE: dict[str, str] = {
    str(target): str(source)
    for source, target in RUNTIME_PHRASES.items()
    if isinstance(source, str) and isinstance(target, str) and source and target
}

COMMON_COMMAND_PHRASES_REVERSE: dict[str, str] = {
    str(target): str(source)
    for source, target in COMMON_COMMAND_PHRASES.items()
    if isinstance(source, str) and isinstance(target, str) and source and target
}

COMMON_COMMAND_WORDS_REVERSE: dict[str, str] = {
    str(target): str(source)
    for source, target in COMMON_COMMAND_WORDS.items()
    if isinstance(source, str) and isinstance(target, str) and source and target
}


def _contains_thai(text: str) -> bool:
    return bool(re.search(r"[\u0E00-\u0E7F]", text or ""))


def _contains_english(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text or ""))


def _looks_unusable_english(text: str) -> bool:
    payload = str(text or "").strip()
    if not payload:
        return True
    if _contains_thai(payload):
        return True
    words = re.findall(r"[A-Za-z]+", payload)
    if not words:
        return True
    if len(payload) > 60 and " " not in payload:
        return True
    if len(words) <= 2 and any(len(word) > 28 for word in words):
        return True
    return False


def _normalize_mixed_pair_side(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip(" \t\r\n-โ€“โ€”|/,:")


def _normalize_mixed_language_segment(text: str, target_lang: str) -> str:
    segment = str(text or "")
    if not segment:
        return segment

    def _th_or_en(th_text: str, en_text: str) -> str:
        return (
            _normalize_mixed_pair_side(th_text)
            if target_lang == "th"
            else _normalize_mixed_pair_side(en_text)
        )

    # Thai (English) / English (Thai)
    segment = re.sub(
        r"([\u0E00-\u0E7F][^()\n]{0,180}?)\s*\(\s*([A-Za-z][^()\n]{0,180}?)\s*\)",
        lambda match: _th_or_en(match.group(1), match.group(2)),
        segment,
    )
    segment = re.sub(
        r"([A-Za-z][^()\n]{0,180}?)\s*\(\s*([\u0E00-\u0E7F][^()\n]{0,180}?)\s*\)",
        lambda match: _th_or_en(match.group(2), match.group(1)),
        segment,
    )

    # Thai / English and English / Thai style pairs.
    segment = re.sub(
        r"([\u0E00-\u0E7F][^/\|\n]{0,180}?)\s*(?:/|\||-|โ€“|:)\s*([A-Za-z][^/\|\n]{0,180}?)(?=$|[,.!?;)\]])",
        lambda match: _th_or_en(match.group(1), match.group(2)),
        segment,
    )
    segment = re.sub(
        r"([A-Za-z][^/\|\n]{0,180}?)\s*(?:/|\||-|โ€“|:)\s*([\u0E00-\u0E7F][^/\|\n]{0,180}?)(?=$|[,.!?;)\]])",
        lambda match: _th_or_en(match.group(2), match.group(1)),
        segment,
    )

    return segment


def _normalize_mixed_language_text(text: str, target_lang: str) -> str:
    payload = str(text or "")
    if not payload:
        return payload
    if target_lang not in {"th", "en"}:
        return payload

    masked_payload, token_map = _mask_runtime_translation_tokens(payload)
    if not masked_payload:
        return payload

    parts = _split_protected_segments(masked_payload)
    normalized_parts: list[str] = []
    for part in parts:
        if _is_protected_segment(part):
            normalized_parts.append(part)
            continue

        next_part = part
        for _ in range(3):
            updated = _normalize_mixed_language_segment(next_part, target_lang)
            if updated == next_part:
                break
            next_part = updated
        normalized_parts.append(next_part)
    normalized = "".join(normalized_parts)
    return _restore_runtime_translation_tokens(normalized, token_map)


def _chunk_text_for_translation(text: str, max_chars: int) -> list[str]:
    payload = str(text or "")
    if not payload:
        return []
    if len(payload) <= max_chars:
        return [payload]

    chunks: list[str] = []
    current = ""
    tokens = re.split(r"(\s+)", payload)
    for token in tokens:
        if token == "":
            continue
        if len(token) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(token):
                end = min(len(token), start + max_chars)
                chunks.append(token[start:end])
                start = end
            continue
        if current and len(current) + len(token) > max_chars:
            chunks.append(current)
            current = token
        else:
            current += token
    if current:
        chunks.append(current)
    return chunks


def _aiforthai_translate_chunk(text: str, direction: str) -> str | None:
    if not _AIFORTHAI_TRANSLATION_ENABLED or not _AIFORTHAI_API_KEY:
        return None
    if direction not in {"en2th", "th2en"}:
        return None

    clean_text = str(text or "")
    if not clean_text:
        return ""
    if len(clean_text) > _AIFORTHAI_MAX_TEXT_LENGTH:
        return None

    cache_key = (direction, clean_text)
    with _AIFORTHAI_CACHE_LOCK:
        cached = _AIFORTHAI_TRANSLATION_CACHE.get(cache_key)
    if isinstance(cached, str):
        return cached

    url = (
        _AIFORTHAI_TRANSLATE_EN2TH_URL
        if direction == "en2th"
        else _AIFORTHAI_TRANSLATE_TH2EN_URL
    )
    if not url:
        return None

    payload_bytes = json.dumps({"text": clean_text}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if _AIFORTHAI_USE_BEARER_AUTH:
        headers["Authorization"] = f"Bearer {_AIFORTHAI_API_KEY}"
    else:
        headers[_AIFORTHAI_API_KEY_HEADER] = _AIFORTHAI_API_KEY

    request = urllib_request.Request(
        url=url,
        data=payload_bytes,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=_AIFORTHAI_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, OSError):
        return None
    except Exception:
        return None

    translated = ""
    try:
        payload = json.loads(raw_body)
        if isinstance(payload, dict):
            translated = str(
                payload.get("translated_text")
                or payload.get("translated")
                or payload.get("translation")
                or ""
            ).strip()
    except Exception:
        translated = ""

    if not translated:
        return None

    with _AIFORTHAI_CACHE_LOCK:
        _AIFORTHAI_TRANSLATION_CACHE[cache_key] = translated
        if len(_AIFORTHAI_TRANSLATION_CACHE) > _AIFORTHAI_TRANSLATION_CACHE_LIMIT:
            _AIFORTHAI_TRANSLATION_CACHE.pop(next(iter(_AIFORTHAI_TRANSLATION_CACHE)))
    return translated


def _translate_text_with_aiforthai(text: str, direction: str) -> str:
    payload = str(text or "")
    if not payload:
        return payload
    if direction == "en2th" and not _contains_english(payload):
        return payload
    if direction == "th2en" and not _contains_thai(payload):
        return payload

    parts = _split_protected_segments(payload)
    translated_parts: list[str] = []
    for part in parts:
        if _is_protected_segment(part):
            translated_parts.append(part)
            continue

        leading = re.match(r"^\s*", part or "")
        trailing = re.search(r"\s*$", part or "")
        prefix = leading.group(0) if leading else ""
        suffix = trailing.group(0) if trailing else ""
        core_end = len(part) - len(suffix) if suffix else len(part)
        core = part[len(prefix):core_end]
        if not core:
            translated_parts.append(part)
            continue

        # Keep command-like tokens stable (e.g. /play, !help, guild_id).
        if re.fullmatch(r"[!/#@<>{}\[\]()_:.\-A-Za-z0-9]+", core):
            translated_parts.append(part)
            continue

        translated_core_parts: list[str] = []
        chunk_list = _chunk_text_for_translation(core, _AIFORTHAI_MAX_TEXT_LENGTH)
        for index, chunk in enumerate(chunk_list):
            translated_chunk = _aiforthai_translate_chunk(chunk, direction)
            if isinstance(translated_chunk, str) and translated_chunk:
                translated_core_parts.append(translated_chunk)
                continue
            translated_core_parts.append(chunk)
            if translated_chunk is None:
                translated_core_parts.extend(chunk_list[index + 1 :])
                break
        translated_core = "".join(translated_core_parts) if translated_core_parts else core
        translated_parts.append(f"{prefix}{translated_core}{suffix}")

    return "".join(translated_parts)


def _read_google_runtime_cache(direction: str, text: str) -> str | None:
    key = (direction, text)
    with _I18N_GOOGLE_CACHE_LOCK:
        return _I18N_GOOGLE_RUNTIME_CACHE.get(key)


def _write_google_runtime_cache(direction: str, text: str, translated: str) -> None:
    key = (direction, text)
    with _I18N_GOOGLE_CACHE_LOCK:
        if key in _I18N_GOOGLE_RUNTIME_CACHE:
            _I18N_GOOGLE_RUNTIME_CACHE_ORDER[:] = [
                item for item in _I18N_GOOGLE_RUNTIME_CACHE_ORDER if item != key
            ]
        _I18N_GOOGLE_RUNTIME_CACHE[key] = translated
        _I18N_GOOGLE_RUNTIME_CACHE_ORDER.append(key)
        while len(_I18N_GOOGLE_RUNTIME_CACHE_ORDER) > _I18N_GOOGLE_RUNTIME_CACHE_LIMIT:
            oldest = _I18N_GOOGLE_RUNTIME_CACHE_ORDER.pop(0)
            _I18N_GOOGLE_RUNTIME_CACHE.pop(oldest, None)


def _get_google_runtime_translator(direction: str) -> Any | None:
    if not _I18N_GOOGLE_RUNTIME_FALLBACK_ENABLED:
        return None
    if direction not in {"en2th", "th2en"}:
        return None
    target_lang = "th" if direction == "en2th" else "en"
    with _I18N_GOOGLE_CACHE_LOCK:
        cached = _I18N_GOOGLE_TRANSLATOR_CACHE.get(target_lang)
    if cached is not None:
        return cached
    try:
        from deep_translator import GoogleTranslator  # type: ignore
    except Exception:
        return None
    try:
        translator = GoogleTranslator(source="auto", target=target_lang)
    except Exception:
        return None
    with _I18N_GOOGLE_CACHE_LOCK:
        _I18N_GOOGLE_TRANSLATOR_CACHE[target_lang] = translator
    return translator


def _google_translate_chunk(text: str, direction: str) -> str | None:
    if not _I18N_GOOGLE_RUNTIME_FALLBACK_ENABLED:
        return None
    if direction not in {"en2th", "th2en"}:
        return None

    clean_text = str(text or "")
    if not clean_text:
        return ""
    if len(clean_text) > _I18N_GOOGLE_RUNTIME_MAX_TEXT_LENGTH:
        return None

    compact = " ".join(clean_text.split())
    if (
        compact
        and len(compact) < _I18N_GOOGLE_RUNTIME_MIN_TEXT_LENGTH
        and " " not in compact
    ):
        return clean_text

    cached = _read_google_runtime_cache(direction, clean_text)
    if isinstance(cached, str):
        return cached

    translator = _get_google_runtime_translator(direction)
    if translator is None:
        return None

    masked_text, token_map = _mask_runtime_translation_tokens(clean_text)
    if not masked_text.strip():
        return clean_text

    try:
        translated = translator.translate(masked_text)
    except Exception:
        return None
    if not isinstance(translated, str) or not translated.strip():
        return None

    restored = _restore_runtime_translation_tokens(translated, token_map)
    if not restored.strip():
        return None

    _write_google_runtime_cache(direction, clean_text, restored)
    return restored


def _translate_text_with_google_fallback(text: str, direction: str) -> str:
    payload = str(text or "")
    if not payload:
        return payload
    if direction == "en2th" and not _contains_english(payload):
        return payload
    if direction == "th2en" and not _contains_thai(payload):
        return payload

    parts = _split_protected_segments(payload)
    translated_parts: list[str] = []
    for part in parts:
        if _is_protected_segment(part):
            translated_parts.append(part)
            continue

        leading = re.match(r"^\s*", part or "")
        trailing = re.search(r"\s*$", part or "")
        prefix = leading.group(0) if leading else ""
        suffix = trailing.group(0) if trailing else ""
        core_end = len(part) - len(suffix) if suffix else len(part)
        core = part[len(prefix):core_end]
        if not core:
            translated_parts.append(part)
            continue

        # Keep command-like tokens stable (e.g. /play, !help, guild_id).
        if re.fullmatch(r"[!/#@<>{}\[\]()_:.\-A-Za-z0-9]+", core):
            translated_parts.append(part)
            continue

        translated_core_parts: list[str] = []
        chunk_list = _chunk_text_for_translation(core, _I18N_GOOGLE_RUNTIME_MAX_TEXT_LENGTH)
        for index, chunk in enumerate(chunk_list):
            translated_chunk = _google_translate_chunk(chunk, direction)
            if isinstance(translated_chunk, str) and translated_chunk:
                translated_core_parts.append(translated_chunk)
                continue
            translated_core_parts.append(chunk)
            if translated_chunk is None:
                translated_core_parts.extend(chunk_list[index + 1 :])
                break
        translated_core = "".join(translated_core_parts) if translated_core_parts else core
        translated_parts.append(f"{prefix}{translated_core}{suffix}")

    return "".join(translated_parts)


def _translate_text_with_runtime_fallback_provider(text: str, direction: str) -> str:
    payload = str(text or "")
    if not payload or direction not in {"en2th", "th2en"}:
        return payload
    if len(payload) > _I18N_PROVIDER_FALLBACK_MAX_TEXT_LENGTH:
        return payload

    translated = payload

    if _I18N_AI_RUNTIME_FALLBACK_ENABLED:
        ai_result = _translate_text_with_aiforthai(translated, direction)
        if isinstance(ai_result, str) and ai_result:
            translated = ai_result

    unresolved = (
        _contains_english(translated) if direction == "en2th" else _contains_thai(translated)
    )
    if unresolved:
        google_result = _translate_text_with_google_fallback(translated, direction)
        if isinstance(google_result, str) and google_result:
            translated = google_result

    return translated


def _translate_text_runtime_rule_based(text: str, language: str) -> str:
    translated = text
    if language == "th":
        for source, target in sorted(
            RUNTIME_PHRASES.items(), key=lambda item: len(item[0]), reverse=True
        ):
            translated = _replace_runtime_phrase(translated, source, target)
        translated = _translate_with_common_patterns(translated)
        return _normalize_mixed_language_text(translated, "th")

    if language == "en":
        for source, target in sorted(
            RUNTIME_PHRASES_REVERSE.items(), key=lambda item: len(item[0]), reverse=True
        ):
            translated = _replace_runtime_phrase(translated, source, target)
        for source, target in sorted(
            COMMON_COMMAND_PHRASES_REVERSE.items(), key=lambda item: len(item[0]), reverse=True
        ):
            translated = _replace_runtime_phrase(translated, source, target)
        for source, target in sorted(
            COMMON_COMMAND_WORDS_REVERSE.items(), key=lambda item: len(item[0]), reverse=True
        ):
            translated = _replace_runtime_phrase(translated, source, target)
        return _normalize_mixed_language_text(translated, "en")

    return translated


def _translate_text_runtime(text: str, guild_id: int | None) -> str:
    if not AUTO_TRANSLATION_ENABLED:
        return text
    payload = str(text or "")
    if not payload:
        return payload

    language = guild_lang(guild_id)
    cached = _read_runtime_translation_cache(language, payload)
    if isinstance(cached, str):
        return cached

    has_th = _contains_thai(payload)
    has_en = _contains_english(payload)
    if (language == "th" and not has_en) or (language == "en" and not has_th):
        _write_runtime_translation_cache(language, payload, payload)
        return payload

    translated = payload
    strict_mode = _I18N_STRICT_LANGUAGE_MODE_ENABLED
    rule_based_enabled = _I18N_RULE_BASED_RUNTIME_TRANSLATION_ENABLED or strict_mode
    heuristic_enabled = _I18N_HEURISTIC_COMMAND_FALLBACK_ENABLED or strict_mode
    provider_fallback_enabled = (
        _I18N_AI_RUNTIME_FALLBACK_ENABLED
        or _I18N_GOOGLE_RUNTIME_FALLBACK_ENABLED
        or (strict_mode and _I18N_STRICT_PROVIDER_FALLBACK_ENABLED)
    )

    # File-first mode: resolve from locale dictionaries/mapping first.
    if _I18N_FILE_FIRST_MODE:
        mapped = _map_literal_from_locales(translated, language)
        if mapped != translated:
            translated = mapped

    if rule_based_enabled:
        translated = _translate_text_runtime_rule_based(translated, language)

    if _I18N_FILE_FIRST_MODE:
        mapped = _map_literal_from_locales(translated, language)
        if mapped != translated:
            translated = mapped

    translated = _normalize_mixed_language_text(translated, language)

    if (
        language == "th"
        and _I18N_FILE_FIRST_MODE
        and heuristic_enabled
    ):
        heuristic = _translate_command_text_to_th(translated)
        if heuristic != translated and heuristic != _TH_COMMAND_GENERIC_FALLBACK:
            translated = heuristic

    # Provider fallback is fallback-only: run only if text still appears in the opposite language.
    if provider_fallback_enabled:
        if language == "th" and _contains_english(translated):
            provider_source = translated
            if _contains_thai(translated) and _contains_english(payload):
                provider_source = payload
            provider_result = _translate_text_with_runtime_fallback_provider(
                provider_source, "en2th"
            )
            if isinstance(provider_result, str) and provider_result:
                translated = provider_result
        elif language == "en" and _contains_thai(translated):
            provider_source = translated
            if _contains_english(translated) and _contains_thai(payload):
                provider_source = payload
            provider_result = _translate_text_with_runtime_fallback_provider(
                provider_source, "th2en"
            )
            if isinstance(provider_result, str) and provider_result:
                translated = provider_result

    if _I18N_FILE_FIRST_MODE:
        mapped = _map_literal_from_locales(translated, language)
        if mapped != translated:
            translated = mapped

    translated = _normalize_mixed_language_text(translated, language)
    _write_runtime_translation_cache(language, payload, translated)
    return translated


def _localize_embed(embed: discord.Embed, guild_id: int | None) -> discord.Embed:
    if not embed:
        return embed

    if embed.title:
        embed.title = _translate_text_runtime(embed.title, guild_id)
    if embed.description:
        embed.description = _translate_text_runtime(embed.description, guild_id)
    author_name = getattr(embed.author, "name", None)
    if author_name:
        embed.set_author(
            name=_translate_text_runtime(author_name, guild_id),
            url=getattr(embed.author, "url", None),
            icon_url=getattr(embed.author, "icon_url", None),
        )
    for index, field in enumerate(list(embed.fields)):
        name = _translate_text_runtime(field.name or "", guild_id)
        value = _translate_text_runtime(field.value or "", guild_id)
        inline = field.inline
        embed.set_field_at(index, name=name, value=value, inline=inline)
    footer_text = getattr(embed.footer, "text", None)
    if footer_text:
        embed.set_footer(
            text=_translate_text_runtime(footer_text, guild_id),
            icon_url=getattr(embed.footer, "icon_url", None),
        )

    color_value = getattr(getattr(embed, "color", None), "value", 0)
    if not color_value:
        seed = f"{embed.title or ''}|{embed.description or ''}|{guild_id or 0}"
        digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()
        index = int(digest[:8], 16) % len(EMBED_COLOR_PALETTE)
        embed.color = discord.Color(EMBED_COLOR_PALETTE[index])

    return embed


def _localize_view(view: Any, guild_id: int | None) -> Any:
    if not view:
        return view

    def _translate_attr(item: Any, attr_name: str) -> None:
        try:
            value = getattr(item, attr_name, None)
            if isinstance(value, str) and value:
                setattr(item, attr_name, _translate_text_runtime(value, guild_id))
        except Exception:
            return

    def _walk(item: Any) -> None:
        _translate_attr(item, "label")
        _translate_attr(item, "placeholder")
        _translate_attr(item, "title")
        _translate_attr(item, "content")
        _translate_attr(item, "description")

        options = getattr(item, "options", None)
        if isinstance(options, list):
            for option in options:
                _translate_attr(option, "label")
                _translate_attr(option, "description")

        for child in list(getattr(item, "children", []) or []):
            _walk(child)

    _walk(view)
    return view


def _localize_modal(modal: discord.ui.Modal, guild_id: int | None) -> discord.ui.Modal:
    if not modal:
        return modal

    title = getattr(modal, "title", None)
    if isinstance(title, str) and title:
        modal.title = _translate_text_runtime(title, guild_id)

    for field in list(getattr(modal, "children", []) or []):
        for attr_name in ("label", "placeholder"):
            try:
                if attr_name == "label":
                    underlying = getattr(field, "_underlying", None)
                    if underlying is not None and hasattr(underlying, "label"):
                        value = getattr(underlying, "label", None)
                        if isinstance(value, str) and value:
                            setattr(
                                underlying,
                                "label",
                                _translate_text_runtime(value, guild_id),
                            )
                        continue

                value = getattr(field, attr_name, None)
                if isinstance(value, str) and value:
                    setattr(field, attr_name, _translate_text_runtime(value, guild_id))
            except Exception:
                continue

    return modal


def localize_payload(guild_id: int | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    if not AUTO_TRANSLATION_ENABLED:
        return kwargs

    if "content" in kwargs and isinstance(kwargs.get("content"), str):
        kwargs["content"] = _translate_text_runtime(kwargs["content"], guild_id)
    if "embed" in kwargs and isinstance(kwargs.get("embed"), discord.Embed):
        kwargs["embed"] = _localize_embed(kwargs["embed"], guild_id)
    if "embeds" in kwargs and isinstance(kwargs.get("embeds"), list):
        kwargs["embeds"] = [
            _localize_embed(embed, guild_id) if isinstance(embed, discord.Embed) else embed
            for embed in kwargs["embeds"]
        ]
    if "view" in kwargs:
        kwargs["view"] = _localize_view(kwargs.get("view"), guild_id)
    return kwargs


def _localize_call(
    guild_id: int | None, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    call_args = list(args)
    call_kwargs = dict(kwargs)

    if call_args and isinstance(call_args[0], str) and "content" not in call_kwargs:
        call_kwargs["content"] = call_args.pop(0)

    call_kwargs = localize_payload(guild_id, call_kwargs)
    return tuple(call_args), call_kwargs


def _resolve_guild_id_from_message(message: discord.Message) -> int | None:
    guild = getattr(message, "guild", None) or getattr(
        getattr(message, "channel", None), "guild", None
    )
    return getattr(guild, "id", None)


def _resolve_guild_id_from_interaction_response(
    response: discord.InteractionResponse,
) -> int | None:
    interaction = getattr(response, "_parent", None)
    guild = getattr(interaction, "guild", None)
    guild_id = getattr(guild, "id", None)
    if guild_id is not None:
        return guild_id
    return getattr(interaction, "guild_id", None)


def _resolve_guild_id_from_webhook(webhook: discord.Webhook) -> int | None:
    guild_id = getattr(webhook, "guild_id", None)
    if guild_id is not None:
        return guild_id

    state = getattr(webhook, "_state", None)
    for attr_name in ("guild_id", "_guild_id"):
        value = getattr(state, attr_name, None)
        if value is not None:
            return value

    interaction = getattr(state, "_interaction", None)
    if interaction is not None:
        return getattr(interaction, "guild_id", None)

    return None


def _set_localized_description(obj: Any) -> None:
    try:
        original_description = getattr(obj, "description", None)
        if not isinstance(original_description, str) or not original_description:
            return

        def _fit_description(text: str) -> str:
            compact = " ".join((text or "").split())
            if not compact:
                return ""
            return compact[:100]

        def _clean_candidate(text: str | None) -> str:
            if not isinstance(text, str):
                return ""
            value = text.strip()
            if not value or value.startswith("i18n:"):
                return ""
            return value

        current = getattr(obj, "description_localizations", None)
        if not isinstance(current, dict):
            current = {}

        def _pick_existing(keys: tuple[str, ...]) -> str:
            for key in keys:
                value = current.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            return ""

        # Ensure unknown literals are registered so both languages can be resolved
        # consistently for app command descriptions and option descriptions.
        key = _resolve_command_text_key(original_description)
        if not key and not original_description.startswith("i18n:"):
            key = _generated_help_key(original_description)
            _register_command_text_key(key, original_description)

        resolved_en = _clean_candidate(_command_text_for_lang(original_description, "en"))
        resolved_th = _clean_candidate(_command_text_for_lang(original_description, "th"))

        english_description = ""
        thai_description = ""

        if resolved_en and not _contains_thai(resolved_en):
            english_description = resolved_en
        if resolved_th and _contains_thai(resolved_th):
            thai_description = resolved_th

        if not english_description:
            english_description = _clean_candidate(_pick_existing(("en-US", "en-GB", "en")))
        if not thai_description:
            thai_description = _clean_candidate(_pick_existing(("th", "th-TH")))

        if (
            not english_description
            and not _contains_thai(original_description)
            and not original_description.startswith("i18n:")
        ):
            english_description = original_description
        if (
            not thai_description
            and _contains_thai(original_description)
            and not original_description.startswith("i18n:")
        ):
            thai_description = original_description

        # Literal lookup fallback from locale files only (no runtime/AI translation).
        if not thai_description and english_description:
            mapped_th = _map_literal_from_locales(english_description, "th")
            if isinstance(mapped_th, str) and mapped_th.strip() and mapped_th != english_description:
                thai_description = mapped_th
        if not english_description and thai_description:
            mapped_en = _map_literal_from_locales(thai_description, "en")
            if isinstance(mapped_en, str) and mapped_en.strip() and mapped_en != thai_description:
                english_description = mapped_en

        # Runtime fallback: if one side is still missing, try rule-based translation.
        if english_description and not thai_description:
            heuristic_th = _clean_candidate(
                _translate_text_runtime_rule_based(english_description, "th")
            )
            if heuristic_th and _contains_thai(heuristic_th):
                thai_description = heuristic_th
            else:
                provider_th = _clean_candidate(
                    _translate_text_with_runtime_fallback_provider(english_description, "en2th")
                )
                if provider_th and _contains_thai(provider_th):
                    thai_description = provider_th

        if thai_description and not english_description:
            heuristic_en = _clean_candidate(
                _translate_text_runtime_rule_based(thai_description, "en")
            )
            if heuristic_en and not _contains_thai(heuristic_en):
                english_description = heuristic_en
            else:
                provider_en = _clean_candidate(
                    _translate_text_with_runtime_fallback_provider(thai_description, "th2en")
                )
                if provider_en and not _contains_thai(provider_en):
                    english_description = provider_en

        if not english_description:
            english_description = "Command for use in the system"

        thai_description = _fit_description(thai_description)
        english_description = _fit_description(english_description)
        if not thai_description and not english_description:
            return

        # Keep default description readable and stable (prefer source language).
        default_description = thai_description or english_description
        if not _contains_thai(original_description):
            default_description = english_description or thai_description

        try:
            setattr(obj, "description", default_description)
        except Exception:
            pass

        if thai_description:
            current["th"] = thai_description
            current["th-TH"] = thai_description
        if english_description:
            current["en-US"] = english_description
            current["en-GB"] = english_description
            current["en"] = english_description
        setattr(obj, "description_localizations", current)
    except Exception:
        return


def _walk_app_command_for_localization(command: Any) -> None:
    _set_localized_description(command)

    for param in list(getattr(command, "parameters", []) or []):
        _set_localized_description(param)

    children = getattr(command, "commands", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            _walk_app_command_for_localization(child)
    elif isinstance(children, dict):
        for child in children.values():
            _walk_app_command_for_localization(child)


def _canonicalize_prefix_command_help(bot: commands.Bot) -> None:
    _ensure_command_help_keys(bot)

    for command in list(getattr(bot, "commands", []) or []):
        stack = [command]
        while stack:
            current = stack.pop()
            help_text = getattr(current, "help", None)
            if isinstance(help_text, str) and help_text:
                key = _resolve_command_text_key(help_text)
                if key and not help_text.startswith("i18n:"):
                    try:
                        current.help = f"i18n:{key}"
                    except Exception:
                        pass

            brief_text = getattr(current, "brief", None)
            if isinstance(brief_text, str) and brief_text:
                key = _resolve_command_text_key(brief_text)
                if not key and not brief_text.startswith("i18n:"):
                    key = _generated_help_key(brief_text)
                    _register_command_text_key(key, brief_text)
                if key and not brief_text.startswith("i18n:"):
                    try:
                        current.brief = f"i18n:{key}"
                    except Exception:
                        pass

            children = getattr(current, "commands", None)
            if isinstance(children, (list, tuple)):
                stack.extend(list(children))
            elif isinstance(children, dict):
                stack.extend(list(children.values()))


def apply_app_command_localizations(bot: commands.Bot) -> None:
    try:
        _canonicalize_prefix_command_help(bot)
        _ensure_cog_description_keys(bot)
        for command in list(bot.tree.get_commands() or []):
            _walk_app_command_for_localization(command)
    except Exception:
        return


def patch_discord_context() -> None:
    global _PATCHED
    if _PATCHED:
        return
    if not AUTO_TRANSLATION_ENABLED:
        _PATCHED = True
        return

    original_send = commands.Context.send
    original_reply = commands.Context.reply
    original_interaction_send = discord.InteractionResponse.send_message
    original_interaction_edit = discord.InteractionResponse.edit_message
    original_interaction_send_modal = discord.InteractionResponse.send_modal
    original_interaction_edit_original = discord.Interaction.edit_original_response
    original_webhook_send = discord.Webhook.send
    original_webhook_edit_message = getattr(discord.Webhook, "edit_message", None)
    original_message_edit = discord.Message.edit
    original_message_reply = discord.Message.reply
    original_partial_message_edit = getattr(discord.PartialMessage, "edit", None)
    webhook_message_cls = getattr(discord, "WebhookMessage", None)
    original_webhook_message_edit = (
        getattr(webhook_message_cls, "edit", None) if webhook_message_cls else None
    )
    original_messageable_send = discord.abc.Messageable.send

    async def localized_send(self: commands.Context, *args, **kwargs):
        guild_id = getattr(getattr(self, "guild", None), "id", None)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_send(self, *args, **kwargs)

    async def localized_reply(self: commands.Context, *args, **kwargs):
        guild_id = getattr(getattr(self, "guild", None), "id", None)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_reply(self, *args, **kwargs)

    async def localized_interaction_send(
        self: discord.InteractionResponse, *args, **kwargs
    ):
        guild_id = _resolve_guild_id_from_interaction_response(self)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_interaction_send(self, *args, **kwargs)

    async def localized_interaction_edit(
        self: discord.InteractionResponse, *args, **kwargs
    ):
        guild_id = _resolve_guild_id_from_interaction_response(self)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_interaction_edit(self, *args, **kwargs)

    async def localized_interaction_send_modal(
        self: discord.InteractionResponse, modal: discord.ui.Modal, *args, **kwargs
    ):
        guild_id = _resolve_guild_id_from_interaction_response(self)
        modal = _localize_modal(modal, guild_id)
        return await original_interaction_send_modal(self, modal, *args, **kwargs)

    async def localized_interaction_edit_original(
        self: discord.Interaction, *args, **kwargs
    ):
        guild_id = getattr(getattr(self, "guild", None), "id", None) or getattr(
            self, "guild_id", None
        )
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_interaction_edit_original(self, *args, **kwargs)

    async def localized_webhook_send(self: discord.Webhook, *args, **kwargs):
        guild_id = _resolve_guild_id_from_webhook(self)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_webhook_send(self, *args, **kwargs)

    async def localized_webhook_edit_message(self: discord.Webhook, *args, **kwargs):
        guild_id = _resolve_guild_id_from_webhook(self)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_webhook_edit_message(self, *args, **kwargs)

    async def localized_message_edit(self: discord.Message, *args, **kwargs):
        guild_id = _resolve_guild_id_from_message(self)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_message_edit(self, *args, **kwargs)

    async def localized_message_reply(self: discord.Message, *args, **kwargs):
        guild_id = _resolve_guild_id_from_message(self)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_message_reply(self, *args, **kwargs)

    async def localized_partial_message_edit(
        self: discord.PartialMessage, *args, **kwargs
    ):
        guild = getattr(self, "guild", None) or getattr(getattr(self, "channel", None), "guild", None)
        guild_id = getattr(guild, "id", None) or getattr(self, "guild_id", None)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_partial_message_edit(self, *args, **kwargs)

    async def localized_webhook_message_edit(self: Any, *args, **kwargs):
        guild_id = _resolve_guild_id_from_message(self)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_webhook_message_edit(self, *args, **kwargs)

    async def localized_messageable_send(self: discord.abc.Messageable, *args, **kwargs):
        guild = getattr(self, "guild", None)
        guild_id = getattr(guild, "id", None)
        args, kwargs = _localize_call(guild_id, args, kwargs)
        return await original_messageable_send(self, *args, **kwargs)

    commands.Context.send = localized_send
    commands.Context.reply = localized_reply
    discord.InteractionResponse.send_message = localized_interaction_send
    discord.InteractionResponse.edit_message = localized_interaction_edit
    discord.InteractionResponse.send_modal = localized_interaction_send_modal
    discord.Interaction.edit_original_response = localized_interaction_edit_original
    discord.Webhook.send = localized_webhook_send
    if callable(original_webhook_edit_message):
        discord.Webhook.edit_message = localized_webhook_edit_message
    discord.Message.edit = localized_message_edit
    discord.Message.reply = localized_message_reply
    if callable(original_partial_message_edit):
        discord.PartialMessage.edit = localized_partial_message_edit
    if webhook_message_cls and callable(original_webhook_message_edit):
        webhook_message_cls.edit = localized_webhook_message_edit
    discord.abc.Messageable.send = localized_messageable_send
    _PATCHED = True
