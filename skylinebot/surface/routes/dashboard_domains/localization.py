from __future__ import annotations

import re
from typing import Any, Callable

_THAI_CHAR_RE = re.compile(r"[\u0E00-\u0E7F]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z]")


def _has_thai_chars(text: str) -> bool:
    return bool(_THAI_CHAR_RE.search(str(text or "")))


def _has_latin_chars(text: str) -> bool:
    return bool(_LATIN_CHAR_RE.search(str(text or "")))


def _extract_trailing_parenthesized_pair(text: str) -> tuple[str, str] | None:
    raw = str(text or "").strip()
    if len(raw) < 4 or not raw.endswith(")"):
        return None

    depth = 0
    open_index = -1
    for idx in range(len(raw) - 1, -1, -1):
        char = raw[idx]
        if char == ")":
            depth += 1
        elif char == "(":
            depth -= 1
            if depth == 0:
                open_index = idx
                break
        if depth < 0:
            return None

    if open_index <= 0:
        return None

    left = raw[:open_index].rstrip()
    right = raw[open_index + 1 : -1].strip()
    if not left or not right:
        return None
    return left, right


def _select_bilingual_brief(text: str, language: str) -> tuple[str, bool]:
    pair = _extract_trailing_parenthesized_pair(text)
    if not pair:
        return str(text or ""), False

    left, right = pair
    left_has_th = _has_thai_chars(left)
    right_has_th = _has_thai_chars(right)
    left_has_en = _has_latin_chars(left)
    right_has_en = _has_latin_chars(right)
    lang = str(language or "en").strip().lower()

    if lang == "en":
        if left_has_en and right_has_th:
            return left, True
        if right_has_en and left_has_th:
            return right, True
        return str(text or ""), False

    if left_has_th and right_has_en:
        return left, True
    if right_has_th and left_has_en:
        return right, True
    return str(text or ""), False


def _normalize_command_brief_for_language(
    text: str,
    language: str,
    *,
    i18n_module: Any,
    command_name: str = "",
) -> str:
    i18n = i18n_module
    lang = "th" if str(language or "").strip().lower() == "th" else "en"
    normalized = str(text or "")
    if not normalized:
        return normalized

    map_literal_fn = getattr(i18n, "_map_literal_from_locales", None)
    normalize_mixed_fn = getattr(i18n, "_normalize_mixed_language_text", None)
    rule_based_fn = getattr(i18n, "_translate_text_runtime_rule_based", None)

    if callable(map_literal_fn):
        mapped = map_literal_fn(normalized, lang)
        if isinstance(mapped, str) and mapped:
            normalized = mapped

    if callable(rule_based_fn):
        needs_conversion = _has_latin_chars(normalized) if lang == "th" else _has_thai_chars(normalized)
        if needs_conversion:
            candidate = rule_based_fn(normalized, lang)
            if isinstance(candidate, str) and candidate:
                normalized = candidate

    if callable(map_literal_fn):
        remapped = map_literal_fn(normalized, lang)
        if isinstance(remapped, str) and remapped:
            normalized = remapped

    if callable(normalize_mixed_fn):
        normalized_candidate = normalize_mixed_fn(normalized, lang)
        if isinstance(normalized_candidate, str) and normalized_candidate:
            normalized = normalized_candidate

    selected, picked = _select_bilingual_brief(normalized, lang)
    if picked:
        normalized = selected

    if lang == "en" and _has_thai_chars(normalized):
        if _has_latin_chars(normalized):
            normalized = re.sub(r"[\u0E00-\u0E7F]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
        if _has_thai_chars(normalized):
            fallback_name = command_name.strip() or "This"
            normalized = f"{fallback_name} command"

    return normalized


TH_CATEGORY_MAP = {
    "alerts": "การแจ้งเตือน",
    "automod": "ออโต้ม็อด",
    "fun": "ความสนุก",
    "giveaway": "กิจกรรมแจกของ",
    "general": "ทั่วไป",
    "help": "ช่วยเหลือ",
    "info": "ข้อมูล",
    "moderation": "ดูแลเซิร์ฟเวอร์",
    "more": "เพิ่มเติม",
    "music": "เพลง",
    "security": "ความปลอดภัย",
    "server": "เซิร์ฟเวอร์",
    "ticket": "ทิกเก็ต",
    "utils": "ยูทิลิตี้",
    "voice": "เสียง",
    "welcomer": "ต้อนรับ",
}


TH_BRIEF_OVERRIDES = {
    "ลบกิจกรรมแจกของ": "ลบกิจกรรม Giveaway",
    "จบกิจกรรมแจกของ": "จบกิจกรรม Giveaway",
    "คำสั่งเกี่ยวกับกิจกรรมแจกของ": "คำสั่งเกี่ยวกับ Giveaway",
    "แสดงรายการกิจกรรมแจกของทั้งหมด": "แสดงรายการ Giveaway ทั้งหมด",
    "สุ่มผู้ชนะกิจกรรมแจกของใหม่": "สุ่มผู้ชนะ Giveaway ใหม่",
    "สร้างกิจกรรมแจกของ": "สร้างกิจกรรม Giveaway",
    "Manage extra owners in the server": "จัดการเจ้าของเสริมในเซิร์ฟ",
    "ปิด/เปิดคำหยาบ": "ปิด/เปิดคำหยาบ",
    "ปิด/เปิดระบบป้องกันลิงก์": "ปิด/เปิดระบบป้องกันลิงก์",
    "ปิด/เปิดระบบป้องกันสแปม": "ปิด/เปิดระบบป้องกันสแปม",
    "ปิด/เปิดระบบ AutoMod หรือแก้ไขการตั้งค่า": "ปิด/เปิด AutoMod หรือแก้ไขการตั้งค่า",
    "ตั้งค่าห้องแชท AI": "ตั้งค่าห้องแชท AI",
    "ปลดล็อกห้อง": "ปลดล็อกห้อง",
    "ดูข้อความล่าสุดในช่อง": "ดูข้อความล่าสุดในช่อง",
    "จัดการลิงก์ชั่วคราว": "จัดการลิงก์ชั่วคราว",
    "จัดการห้องส่งโปรโมตและห้องสาธารณะ": "จัดการห้องส่งโปรโมตและห้องสาธารณะ",
    "ตั้งค่าคำสั่งตอบกลับอัตโนมัติ": "ตั้งค่าระบบตอบกลับอัตโนมัติ",
    "ตั้งค่าคำสั่งยศส่วนตัว": "ตั้งค่าระบบยศพิเศษ",
    "ส่ง Embed ไปยังห้องข้อความที่เลือก": "ส่ง Embed ไปยังห้องข้อความที่เลือก",
    "ส่งข้อความในห้องปัจจุบัน": "ส่งข้อความในห้องปัจจุบัน",
    "ตั้งค่าข้อความลาสำหรับเซิร์ฟเวอร์ของคุณ": "ตั้งค่าข้อความออกจากเซิร์ฟ",
    "Set Your AFK Status": "ตั้งสถานะ AFK ของคุณ",
    "ปิดหรือเปิดโหมดเล่นอัตโนมัติ": "ปิดหรือเปิดโหมดเล่นอัตโนมัติ",
    "Display a user's avatar": "แสดงรูปโปรไฟล์ของผู้ใช้",
    "Display a user's banner": "แสดงแบนเนอร์ของผู้ใช้",
    "Get the boost count of the server": "ดูจำนวนบูสต์ของเซิร์ฟเวอร์",
    "แสดงเพลงที่กำลังเล่น": "แสดงเพลงที่กำลังเล่น",
    "เรียกดูข้อความล่าสุดในช่อง": "เรียกดูข้อความล่าสุดในช่อง",
    "Get the first message of a channel": "ดูข้อความแรกของช่อง",
    "แสดงบทบาทที่ตั้งไว้สำหรับสิทธิ์ Giveaway": "แสดงบทบาทสำหรับสิทธิ์ Giveaway",
    "Show all commands in bot": "แสดงคำสั่งทั้งหมดของบอท",
    "Hide a channel": "ซ่อนช่อง",
    "Hide all channels in the server": "ซ่อนทุกช่องในเซิร์ฟเวอร์",
    "Ignore users or channels": "เพิกเฉยผู้ใช้หรือช่องที่กำหนด",
    "Invite The Bot To Your Server": "เชิญบอทเข้าร่วมเซิร์ฟเวอร์ของคุณ",
    "ล็อกห้อง": "ล็อกช่อง",
    "Lock all channels in the server": "ล็อกทุกช่องในเซิร์ฟเวอร์",
    "จัดการลิงก์ชั่วคราวของเซิร์ฟเวอร์": "จัดการลิงก์ชั่วคราว",
    "Manage media channels in the server": "จัดการช่องประเภทมีเดียในเซิร์ฟเวอร์",
    "Get the member count of the server": "ดูจำนวนสมาชิกของเซิร์ฟเวอร์",
    "ปิดเสียงสมาชิกในเซิร์ฟเวอร์": "ปิดเสียงสมาชิกในเซิร์ฟเวอร์",
    "Mute a member in the server": "ปิดเสียงสมาชิกในเซิร์ฟเวอร์",
    "Change the nickname of a member": "เปลี่ยนชื่อเล่นของสมาชิก",
    "Enable/Disable The No Prefix Feature": "เปิดหรือปิดฟีเจอร์ No Prefix",
    "ล้างทุกช่องในเซิร์ฟเวอร์แบบ Nuke": "ล้างช่องทั้งหมดด้วยระบบ Nuke",
    "หยุดเพลงชั่วคราว": "หยุดเพลงชั่วคราว",
    "Get The Bot's Ping": "แสดงค่า Ping ของบอท",
    "เล่นเพลงในห้องเสียง": "เล่นเพลงในห้องเสียง",
    "Change The Bot's Prefix or Get The Current Prefix": "เปลี่ยน Prefix ของบอทหรือดู Prefix ปัจจุบัน",
    "ตรวจสอบว่าผู้ใช้มีพรีเมียมหรือไม่": "ตรวจสอบว่าผู้ใช้มี Premium หรือไม่",
    "Display a user's profile": "แสดงโปรไฟล์ของผู้ใช้",
    "Purge messages in a channel": "ลบข้อความจำนวนมากในช่อง",
    "แสดงคิวเพลงทั้งหมด": "แสดงรายการคิวเพลง",
    "ใช้โค้ดรีดีม": "รับสิทธิ์ Redeem Code",
    "Set Your Relationship Status": "ตั้งค่าสถานะความสัมพันธ์ของคุณ",
    "รีเซ็ตการตั้งค่าของโมดูล": "รีเซ็ตการตั้งค่าของโมดูล",
    "เล่นเพลง": "เล่นเพลง",
    "Manage roles of the users": "จัดการบทบาทของผู้ใช้",
    "Set a role icon": "ตั้งค่าไอคอนบทบาท",
    "Get information about a role": "ดูข้อมูลของบทบาท",
    "Get information about the server": "ดูข้อมูลของเซิร์ฟเวอร์",
    "ตั้งค่าระบบในเซิร์ฟเวอร์": "ตั้งค่าระบบในเซิร์ฟเวอร์",
    "แสดงสรุปสถานะของเซิร์ฟเวอร์": "แสดงสรุปสถานะของเซิร์ฟเวอร์",
    "Get The Bot's Stats": "แสดงสถิติของบอท",
    "Can Be Used To Steal Emoji/Multiple Emojis From A Server": "คัดลอกอีโมจิหนึ่งหรือหลายรายการจากเซิร์ฟเวอร์",
    "หยุดเพลงและให้บอทออกจากห้องเสียง": "หยุดเพลงและให้บอทออกจากห้องเสียง",
    "Join The Support Server": "เข้าร่วมเซิร์ฟเวอร์ซัพพอร์ต",
    "ชุดคำสั่งสำหรับจัดการทิกเก็ต": "ชุดคำสั่งสำหรับจัดการทิกเก็ต",
    "Unban a user from the server": "ยกเลิกแบนผู้ใช้ในเซิร์ฟเวอร์",
    "Unban all users from the server": "ยกเลิกแบนผู้ใช้ทั้งหมดในเซิร์ฟเวอร์",
    "Unhide a channel": "เลิกซ่อนช่อง",
    "Unhide all channels in the server": "เลิกซ่อนทุกช่องในเซิร์ฟเวอร์",
    "ปลดล็อกช่อง": "ปลดล็อกช่อง",
    "Unlock all channels in the server": "ปลดล็อกทุกช่องในเซิร์ฟเวอร์",
    "Unmute a member in the server": "ยกเลิกปิดเสียงสมาชิกในเซิร์ฟเวอร์",
    "Get the uptime of the bot": "แสดงระยะเวลาการทำงานของบอท",
    "Get information about a user": "ดูข้อมูลของผู้ใช้",
    "ควบคุมห้องเสียง J2C แบบรีโมต": "ควบคุมห้องเสียง J2C แบบรีโมต",
    "Deafen a user in a voice channel": "ปิดการได้ยินของผู้ใช้ในห้องเสียง",
    "Deafen all users in a voice channel": "ปิดการได้ยินของผู้ใช้ทั้งหมดในห้องเสียง",
    "Disconnect a user from a voice channel": "ตัดผู้ใช้ออกจากห้องเสียง",
    "Disconnect all users in a voice channel": "ตัดผู้ใช้ทั้งหมดออกจากห้องเสียง",
    "Move a user to a voice channel": "ย้ายผู้ใช้ไปยังห้องเสียง",
    "Move all users in a voice channel to another voice channel": "ย้ายผู้ใช้ทั้งหมดไปยังอีกห้องเสียง",
    "Mute a user in a voice channel": "ปิดไมค์ผู้ใช้ในห้องเสียง",
    "Mute all users in a voice channel": "ปิดไมค์ผู้ใช้ทั้งหมดในห้องเสียง",
    "Pull a user to your voice channel": "ดึงผู้ใช้เข้าห้องเสียงของคุณ",
    "Undeafen a user in a voice channel": "เปิดการได้ยินของผู้ใช้ในห้องเสียง",
    "Undeafen all users in a voice channel": "เปิดการได้ยินของผู้ใช้ทั้งหมดในห้องเสียง",
    "Unmute a user in a voice channel": "เปิดไมค์ผู้ใช้ในห้องเสียง",
    "Unmute all users in a voice channel": "เปิดไมค์ผู้ใช้ทั้งหมดในห้องเสียง",
    "ดูหรือปรับระดับเสียง": "ดูหรือปรับระดับเสียงของเครื่อง",
    "Vote For The Bot": "โหวตให้บอท",
    "Configure the welcome message for your server": "ตั้งค่าข้อความต้อนรับของเซิร์ฟเวอร์",
    "Configure the welcomer for your server": "ตั้งค่าระบบต้อนรับของเซิร์ฟเวอร์",
    "ตั้งค่าระบบป้องกันบอทบุกและการโจมตี": "ตั้งค่าระบบป้องกันการโจมตี Anti-Nuke",
}


TH_COMMAND_BRIEF_MAP = {
    "alerts": "ตั้งค่าการแจ้งเตือน Twitch/TikTok/GitHub/YouTube/Facebook/X",
    "antinuke": "เปิด/ปิดระบบ Anti-Nuke",
    "extraowner": "จัดการเจ้าของเสริมในเซิร์ฟ",
    "whitelist": "จัดการรายการ Whitelist ของ Anti-Nuke",
    "aichat": "ตั้งค่าห้องแชท AI",
    "lock": "ล็อกห้อง",
    "unlock": "ปลดล็อกห้อง",
    "leaver": "ตั้งค่าข้อความออกจากเซิร์ฟ",
    "antibadwords": "เปิด/ปิดระบบป้องกันคำหยาบ",
    "antilink": "เปิด/ปิดระบบป้องกันลิงก์",
    "antispam": "เปิด/ปิดระบบป้องกันสแปม",
    "automod": "เปิด/ปิด AutoMod และแก้ไขการตั้งค่า",
    "autoresponder": "ตั้งค่าระบบตอบกลับอัตโนมัติ",
    "customrole": "ตั้งค่าคำสั่งระบบยศพิเศษ",
    "embed": "ส่ง Embed ไปยังห้องข้อความที่เลือก",
    "nuke": "ล้างช่องข้อความแบบเร่งด่วน",
    "premium": "ตรวจสอบว่าผู้ใช้มี Premium หรือไม่",
    "redeem": "รับสิทธิ์ Redeem Code",
    "reset": "รีเซ็ตการตั้งค่าของโมดูล",
    "say": "ส่งข้อความในห้องปัจจุบัน",
    "setup": "ตั้งค่าระบบหลักของเซิร์ฟเวอร์",
    "vccontrol": "รีโมตควบคุมห้องเสียง J2C",
    "music": "จัดการระบบเพลงในห้องเสียง",
    "queue": "แสดงรายการคิวเพลง",
    "current": "แสดงเพลงที่กำลังเล่น",
    "play": "เล่นเพลงในห้องเสียง",
    "stop": "หยุดเพลงและให้บอทออกจากห้องเสียง",
    "volume": "ดูหรือปรับระดับเสียงของเครื่อง",
    "angry": "😡 โกรธ",
    "confused": "🤔 สับสน",
    "cry": "😢 ร้องไห้",
    "cute": "ทำนายระดับความน่ารักของคนที่ระบุ",
    "dance": "💃 เต้น",
    "fakeban": "แกล้งแบนผู้ใช้",
    "fakekick": "แกล้งเตะผู้ใช้",
    "gay": "ทำนายระดับความเกย์ของคนที่ระบุ",
    "gdelete": "ลบกิจกรรม Giveaway",
    "gend": "จบกิจกรรม Giveaway",
    "giveaway": "คำสั่งเกี่ยวกับ Giveaway",
    "glist": "แสดงรายการ Giveaway ทั้งหมด",
    "greet": "ตั้งค่าช่องและข้อความทักทายของเซิร์ฟเวอร์",
    "greroll": "สุ่มผู้ชนะ Giveaway ใหม่",
    "gstart": "สร้างกิจกรรม Giveaway",
    "horny": "ทำนายระดับความหื่นของคนที่ระบุ",
    "hug": "🤗 กอดคนที่ระบุ",
    "iq": "ทำนายระดับ IQ ของคนที่ระบุ",
    "kiss": "💋 จุ๊บคนที่ระบุ",
    "laugh": "😂 หัวเราะ",
    "lesbian": "ทำนายระดับเลสเบียนของคนที่ระบุ",
    "list": "คำสั่งย่อยสำหรับแสดงรายการต่าง ๆ",
    "nukeall": "ล้างทุกช่องในเซิร์ฟเวอร์",
    "pat": "🐾 ลูบหัวคนที่ระบุ",
    "relationship": "ตั้งค่าสถานะความสัมพันธ์ของคุณ",
    "ship": "ทำนายความเข้ากันได้ของคนสองคน",
    "simp": "ทำนายระดับ Simp ของคนที่ระบุ",
    "skip": "ข้ามเพลงปัจจุบัน",
    "slap": "👋 ตบคนที่ระบุ",
    "sleep": "😴 นอน",
    "smile": "😊 ยิ้ม",
}


def translate_category_th(category: str, *, i18n_module: Any) -> str:
    i18n = i18n_module
    category = (category or "").strip()
    if category.startswith("i18n:"):
        return i18n.translate(category[5:], "th")
    return TH_CATEGORY_MAP.get(category.lower(), category)



def translate_brief_th(
    name: str,
    brief: str,
    *,
    i18n_module: Any,
    clean_text_fn: Callable[[Any], str],
) -> str:
    i18n = i18n_module
    _clean_text = clean_text_fn
    if str(brief).startswith("i18n:"):
        key = brief[5:]
        return i18n.translate(key, "th")

    if name in TH_COMMAND_BRIEF_MAP:
        return TH_COMMAND_BRIEF_MAP[name]

    normalized = _clean_text(brief)
    if normalized in TH_BRIEF_OVERRIDES:
        return TH_BRIEF_OVERRIDES[normalized]
    if normalized == "No description":
        return "ไม่มีคำอธิบาย"

    dynamic_patterns: list[tuple[str, str]] = [
        (r"^Enable/Disable (.+?) system$", r"เปิด/ปิดระบบ \1"),
        (r"^Predict a persons (.+?) level$", r"ทำนายระดับ \1 ของคนที่ระบุ"),
        (r"^Configure the (.+?) for your server$", r"ตั้งค่า \1 สำหรับเซิร์ฟเวอร์ของคุณ"),
        (r"^Setup the (.+?) Commands$", r"ตั้งค่าคำสั่ง\1"),
        (r"^Setup the (.+?) system$", r"ตั้งค่าระบบ\1"),
        (r"^Ban a user from the server$", r"แบนผู้ใช้จากเซิร์ฟ"),
        (r"^Kick a user from the server$", r"เตะผู้ใช้ออกจากเซิร์ฟ"),
    ]
    for pattern, repl in dynamic_patterns:
        if re.match(pattern, normalized):
            return re.sub(pattern, repl, normalized)
    if re.search(r"[A-Za-z]", normalized) and not re.search(r"[ก-๙]", normalized):
        return f"คำสั่ง {name} สำหรับใช้งานในระบบ"
    return normalized



def localize_command(
    command: dict[str, Any],
    language: str = "en",
    *,
    i18n_module: Any,
    translate_brief_th_fn: Callable[[str, str], str],
    translate_category_th_fn: Callable[[str], str],
) -> dict[str, Any]:
    i18n = i18n_module
    lang = "th" if str(language or "").strip().lower() == "th" else "en"
    _translate_brief_th = translate_brief_th_fn
    _translate_category_th = translate_category_th_fn
    name = str(command.get("name") or "").strip().lower()
    brief = str(command.get("brief") or "")

    if brief.startswith("i18n:"):
        key = brief[5:]
        brief = i18n.translate(key, lang)
    else:
        brief, picked_by_language = _select_bilingual_brief(brief, lang)
        if not picked_by_language:
            brief = _normalize_command_brief_for_language(
                brief,
                lang,
                i18n_module=i18n,
                command_name=name,
            )
        if lang == "th":
            if not picked_by_language:
                if brief.startswith("i18n:"):
                    brief = i18n.translate(brief[5:], "th")
                else:
                    brief = _translate_brief_th(name, brief)
            normalize_mixed_fn = getattr(i18n, "_normalize_mixed_language_text", None)
            if callable(normalize_mixed_fn):
                normalized_th = normalize_mixed_fn(brief, "th")
                if isinstance(normalized_th, str) and normalized_th:
                    brief = normalized_th

    raw_category = str(command.get("raw_category") or command.get("category") or "General")
    category = str(command.get("category") or raw_category or "General")
    if lang == "th":
        category = _translate_category_th(category)

    return {
        "name": command.get("name", ""),
        "brief": brief,
        "category": category,
        "raw_category": raw_category,
        "meta": command.get("meta", {}),
        "prefix_available": bool(command.get("prefix_available")),
        "slash_available": bool(command.get("slash_available")),
        "usage_lines": list(command.get("usage_lines") or []),
        "example_lines": list(command.get("example_lines") or []),
    }
