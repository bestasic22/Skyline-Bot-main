import discord


from discord import app_commands


from discord.ext import commands


import psutil


import asyncio


import io


import base64


import platform


import datetime


import time
import os
import json
import tempfile
from typing import Any, Optional
from urllib.parse import urlparse


from skylinebot.src.checks import checks


from skylinebot.memory.cache import cache


import traceback, sys


import re


import storage.afk


import storage.guilds


import storage.users


from skylinebot.console.logging import logger


from skylinebot.style import color


from skylinebot.workflows import ui


from skylinebot.utils import pings
from skylinebot.utils import i18n


import requests
from gtts import gTTS


from skylinebot.config.config import BotConfigClass


BotConfig = BotConfigClass()


import storage


from skylinebot.workflows.afk_delay import afk_delay


from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.engine import bot_runtime as bot_runtime_engine
from skylinebot.src.services import CommandFlow


CLONE_LIMITS_BY_PLAN: dict[str, Optional[int]] = {
    "free": 2,
    "silver": 5,
    "golden": 8,
    "diamond": 15,
    "permanent": None,
}

VAJA_SPEAKERS: dict[str, str] = {
    "nana": "ผู้หญิง | พากย์การ์ตูน",
    "noina": "ผู้หญิง | สปอตโฆษณา",
    "farah": "ผู้หญิง | สารคดี",
    "mewzy": "ผู้หญิง | สปอตโฆษณา",
    "farsai": "ผู้หญิง | พากย์การ์ตูน",
    "prim": "ผู้หญิง | Announcer",
    "ped": "เสียงผู้หญิง | Announcer",
    "poom": "เสียงผู้ชาย | สปอตโฆษณา",
    "doikham": "เสียงผู้ชาย | ภาษาเหนือ",
    "praw": "เสียงเด็กผู้หญิง",
    "wayu": "เสียงเด็กผู้ชาย",
    "namphueng": "เสียงผู้หญิง | Anchor-style",
    "toon": "เสียงผู้หญิง | Broadcast-style",
    "sanooch": "เสียงผู้หญิง | Teacher-style",
    "thanwa": "เสียงผู้ชาย | Broadcast-style",
}
VAJA_MODE_OPTIONS: tuple[str, ...] = ("file", "voice")


class Utils(commands.Cog):

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        class CogInfo:

            name = "Utils"

            category = "Extra"

            description = "Utility commands"

            hidden = False

            emoji = self.bot.emoji.UTILS or "⚒️"

        self.cog_info = CogInfo
        self.command_flow = CommandFlow(bot)
        self._aihealth_lock = asyncio.Lock()

    async def _collect_ping_metrics(self) -> tuple[int, Any, Any]:
        bot_ping = pings.bot(self.bot)
        cache_response_time = pings.cache()
        database_response_time = await pings.database()
        return bot_ping, cache_response_time, database_response_time

    def _get_ai_message_cog(self):
        return self.bot.get_cog("message") or self.bot.get_cog("Message")

    @staticmethod
    def _clip_text(text: Any, limit: int = 140) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 3)] + "..."

    @staticmethod
    def _contains_thai_characters(text: str) -> bool:
        return bool(re.search(r"[\u0E00-\u0E7F]", str(text or "")))

    def _resolve_tts_language(self, requested_lang: str, text: str) -> str:
        raw = str(requested_lang or "auto").strip().lower()
        if raw in {"th", "thai", "ภาษาไทย"}:
            return "th"
        if raw in {"en", "eng", "english"}:
            return "en"
        return "th" if self._contains_thai_characters(text) else "en"

    @staticmethod
    def _sanitize_tts_text(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @staticmethod
    def _split_tts_chunks(text: str, limit: int = 180) -> list[str]:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        if not cleaned:
            return []
        if len(cleaned) <= limit:
            return [cleaned]
        chunks: list[str] = []
        words = cleaned.split(" ")
        current = ""
        for word in words:
            if not word:
                continue
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
            while len(word) > limit:
                chunks.append(word[:limit])
                word = word[limit:]
            current = word
        if current:
            chunks.append(current)
        return chunks or [cleaned[:limit]]

    async def _synthesize_tts_gtts(self, text: str, lang: str) -> bytes:
        def _worker() -> bytes:
            audio = io.BytesIO()
            gTTS(text=text, lang=lang, slow=False).write_to_fp(audio)
            return audio.getvalue()

        return await asyncio.to_thread(_worker)

    async def _synthesize_tts_google_web(self, text: str, lang: str) -> bytes:
        def _worker() -> bytes:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
            chunks = self._split_tts_chunks(text, limit=180)
            if not chunks:
                return b""
            audio_parts: list[bytes] = []
            for chunk in chunks:
                response = requests.get(
                    "https://translate.google.com/translate_tts",
                    params={
                        "ie": "UTF-8",
                        "q": chunk,
                        "tl": lang,
                        "client": "tw-ob",
                    },
                    headers=headers,
                    timeout=20,
                )
                if response.status_code != 200 or not response.content:
                    raise RuntimeError(
                        f"Google TTS HTTP {response.status_code}: {response.text[:160]}"
                    )
                audio_parts.append(response.content)
            return b"".join(audio_parts)

        return await asyncio.to_thread(_worker)

    async def _synthesize_tts_pyttsx3(self, text: str, lang: str) -> bytes:
        def _worker() -> bytes:
            import pyttsx3  # lazy import for lightweight startup

            fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="skylinebot_tts_")
            os.close(fd)
            try:
                engine = pyttsx3.init()
                try:
                    voices = list(engine.getProperty("voices") or [])
                    if lang == "th":
                        for voice in voices:
                            voice_id = str(getattr(voice, "id", "") or "")
                            voice_name = str(getattr(voice, "name", "") or "")
                            voice_languages = str(getattr(voice, "languages", "") or "")
                            voice_blob = f"{voice_id} {voice_name} {voice_languages}".lower()
                            if "thai" in voice_blob or "th" in voice_blob:
                                engine.setProperty("voice", voice.id)
                                break
                except Exception:
                    pass
                engine.save_to_file(text, temp_path)
                engine.runAndWait()
                with open(temp_path, "rb") as file:
                    return file.read()
            finally:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

        return await asyncio.to_thread(_worker)

    @staticmethod
    def _normalize_vaja_speaker(speaker: str) -> str:
        normalized = str(speaker or "nana").strip().lower()
        return normalized if normalized in VAJA_SPEAKERS else "nana"

    @staticmethod
    def _normalize_vaja_mode(mode: str) -> str:
        normalized = str(mode or "file").strip().lower()
        if normalized in VAJA_MODE_OPTIONS:
            return normalized
        if normalized in {"voice", "vc", "speak", "say"}:
            return "voice"
        return "file"

    @staticmethod
    def _normalize_vaja_style(style: str | None) -> str | None:
        normalized = str(style or "").strip().lower()
        if not normalized or normalized in {"default", "none", "auto", "-"}:
            return None
        if normalized in VAJA_SPEAKERS:
            return normalized
        return None

    @staticmethod
    def _decode_vaja_base64_audio(raw_value: Any) -> bytes | None:
        if not isinstance(raw_value, str):
            return None
        encoded = str(raw_value or "").strip()
        if not encoded:
            return None
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        encoded = re.sub(r"\s+", "", encoded)
        if len(encoded) < 32:
            return None
        try:
            return base64.b64decode(encoded, validate=True)
        except Exception:
            return None

    @staticmethod
    def _detect_audio_extension(content_type: str, audio_bytes: bytes) -> str:
        content_type_lower = str(content_type or "").lower()
        if "mpeg" in content_type_lower or "mp3" in content_type_lower:
            return "mp3"
        if "wav" in content_type_lower or "wave" in content_type_lower:
            return "wav"
        if "ogg" in content_type_lower:
            return "ogg"
        if "flac" in content_type_lower:
            return "flac"

        head = bytes(audio_bytes[:16] or b"")
        if head.startswith(b"RIFF") and b"WAVE" in head:
            return "wav"
        if head.startswith(b"ID3") or head[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
            return "mp3"
        if head.startswith(b"OggS"):
            return "ogg"
        if head.startswith(b"fLaC"):
            return "flac"
        return "wav"

    async def _synthesize_vaja_audio(
        self,
        *,
        text: str,
        speaker: str,
        style: str | None,
    ) -> tuple[bytes, str]:
        def _worker() -> tuple[bytes, str]:
            endpoint = str(
                os.getenv("AIFORTHAI_VAJA_ENDPOINT", "https://api.aiforthai.in.th/vaja")
                or "https://api.aiforthai.in.th/vaja"
            ).strip()
            if not endpoint:
                raise RuntimeError("AIFORTHAI_VAJA_ENDPOINT ว่างเปล่า")

            api_key = str(
                os.getenv("VAJA_API_KEY", "")
                or os.getenv("AIFORTHAI_API_KEY", "")
            ).strip()
            if not api_key:
                raise RuntimeError("ยังไม่ได้ตั้งค่า VAJA_API_KEY หรือ AIFORTHAI_API_KEY")

            api_key_header = str(os.getenv("AIFORTHAI_API_KEY_HEADER", "Apikey") or "Apikey").strip() or "Apikey"
            use_bearer = str(os.getenv("AIFORTHAI_USE_BEARER_AUTH", "0") or "0").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            try:
                timeout_raw = float(str(os.getenv("VAJA_TIMEOUT_SECONDS", "45") or "45"))
            except (TypeError, ValueError):
                timeout_raw = 45.0
            timeout_seconds = max(8.0, min(90.0, timeout_raw))

            payload: dict[str, Any] = {
                "text": text,
                "speaker": speaker,
            }
            if style:
                payload["style"] = style

            headers = {"Content-Type": "application/json"}
            if use_bearer:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers[api_key_header] = api_key

            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )

            raw_content = bytes(response.content or b"")
            content_type = str(response.headers.get("Content-Type") or "").strip().lower()

            if response.status_code >= 400:
                detail = ""
                try:
                    decoded = response.json()
                    if isinstance(decoded, dict):
                        detail = str(decoded.get("message") or decoded.get("error") or "")
                except Exception:
                    pass
                if not detail:
                    detail = str(response.text or "")[:240]
                raise RuntimeError(f"VAJA HTTP {response.status_code}: {detail or 'unknown error'}")

            if "application/json" not in content_type:
                if not raw_content:
                    raise RuntimeError("VAJA ไม่ส่งข้อมูลเสียงกลับมา")
                return raw_content, self._detect_audio_extension(content_type, raw_content)

            try:
                decoded_payload = response.json()
            except Exception as error:
                raise RuntimeError(f"VAJA ส่งข้อมูล JSON ไม่ถูกต้อง: {error}") from error

            if not isinstance(decoded_payload, dict):
                raise RuntimeError("VAJA ส่งรูปแบบข้อมูลไม่ถูกต้อง")

            direct_audio_fields = (
                decoded_payload.get("audio"),
                decoded_payload.get("wav"),
                decoded_payload.get("mp3"),
                (decoded_payload.get("data") or {}).get("audio") if isinstance(decoded_payload.get("data"), dict) else None,
                (decoded_payload.get("data") or {}).get("wav") if isinstance(decoded_payload.get("data"), dict) else None,
                (decoded_payload.get("result") or {}).get("audio") if isinstance(decoded_payload.get("result"), dict) else None,
            )
            for candidate in direct_audio_fields:
                audio_bytes = self._decode_vaja_base64_audio(candidate)
                if audio_bytes:
                    return audio_bytes, self._detect_audio_extension(content_type, audio_bytes)

            url_fields = (
                decoded_payload.get("audio_url"),
                decoded_payload.get("wav_url"),
                decoded_payload.get("mp3_url"),
                decoded_payload.get("url"),
                (decoded_payload.get("data") or {}).get("audio_url") if isinstance(decoded_payload.get("data"), dict) else None,
                (decoded_payload.get("data") or {}).get("url") if isinstance(decoded_payload.get("data"), dict) else None,
                (decoded_payload.get("result") or {}).get("audio_url") if isinstance(decoded_payload.get("result"), dict) else None,
            )
            for candidate in url_fields:
                audio_url = str(candidate or "").strip()
                if not audio_url:
                    continue
                if not audio_url.startswith("http"):
                    continue
                audio_response = requests.get(audio_url, timeout=timeout_seconds)
                if audio_response.status_code >= 400:
                    raise RuntimeError(f"โหลดไฟล์เสียง VAJA ไม่สำเร็จ (HTTP {audio_response.status_code})")
                audio_bytes = bytes(audio_response.content or b"")
                if not audio_bytes:
                    raise RuntimeError("ไฟล์เสียงจาก VAJA ว่างเปล่า")
                audio_content_type = str(audio_response.headers.get("Content-Type") or content_type).strip().lower()
                return audio_bytes, self._detect_audio_extension(audio_content_type, audio_bytes)

            message = str(decoded_payload.get("message") or decoded_payload.get("error") or "").strip()
            if message:
                raise RuntimeError(f"VAJA response: {message}")
            raise RuntimeError("VAJA ไม่พบข้อมูลเสียงใน response")

        return await asyncio.to_thread(_worker)

    @staticmethod
    def _voice_client_has_active_session(voice_client: Any) -> bool:
        if voice_client is None:
            return False
        try:
            if hasattr(voice_client, "is_playing") and callable(voice_client.is_playing) and voice_client.is_playing():
                return True
        except Exception:
            pass
        try:
            if hasattr(voice_client, "is_paused") and callable(voice_client.is_paused) and voice_client.is_paused():
                return True
        except Exception:
            pass

        if bool(getattr(voice_client, "current", None)):
            return True
        if bool(getattr(voice_client, "playing", False)) or bool(getattr(voice_client, "paused", False)):
            return True

        queue_obj = getattr(voice_client, "queue", None)
        if queue_obj is None:
            return False
        try:
            if len(queue_obj) > 0:
                return True
        except Exception:
            pass
        try:
            is_empty_attr = getattr(queue_obj, "is_empty", True)
            if callable(is_empty_attr):
                if not bool(is_empty_attr()):
                    return True
            elif not bool(is_empty_attr):
                return True
        except Exception:
            pass
        return False

    def _vaja_voice_busy_message(self, voice_client: Any) -> str:
        channel_obj = getattr(voice_client, "channel", None)
        channel_label = getattr(channel_obj, "mention", None) or "`ไม่ทราบห้อง`"
        if self._voice_client_has_active_session(voice_client):
            return (
                f"บอทกำลังใช้งานเสียงอยู่ที่ {channel_label} "
                "กรุณารอให้เล่นจบก่อนเพื่อไม่ให้เสียงชนกัน"
            )
        return f"บอทเชื่อมต่อห้องเสียงอยู่ที่ {channel_label}"

    @staticmethod
    def _voice_runtime_status() -> tuple[bool, str]:
        try:
            import discord.voice_client as discord_voice_client
        except Exception:
            return True, ""

        has_nacl = bool(getattr(discord_voice_client, "has_nacl", True))
        has_dave = bool(getattr(discord_voice_client, "has_dave", True))
        if not has_nacl:
            return False, "PyNaCl library needed in order to use voice"
        if not has_dave:
            return False, "davey library needed in order to use voice"
        return True, ""

    async def _play_vaja_audio_to_voice(
        self,
        *,
        guild: discord.Guild,
        target_channel: discord.abc.Connectable,
        audio_bytes: bytes,
        extension: str,
        playback_timeout: float,
    ) -> None:
        suffix = f".{str(extension or 'wav').strip().lower() or 'wav'}"
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix="skylinebot_vaja_")
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(audio_bytes)

        created_connection = False
        voice_client = guild.voice_client
        try:
            if voice_client is None:
                voice_client = await target_channel.connect()
                created_connection = True
            elif getattr(voice_client, "channel", None) and int(getattr(voice_client.channel, "id", 0) or 0) != int(
                getattr(target_channel, "id", 0) or 0
            ):
                await voice_client.move_to(target_channel)

            if not hasattr(voice_client, "play"):
                raise RuntimeError("ระบบเสียงปัจจุบันไม่รองรับการเล่นไฟล์เสียง VAJA ในห้องเสียง")

            if self._voice_client_has_active_session(voice_client):
                raise RuntimeError(self._vaja_voice_busy_message(voice_client))

            done_event = asyncio.Event()
            playback_error: dict[str, str] = {"message": ""}

            def _after_play(error: Exception | None) -> None:
                if error:
                    playback_error["message"] = str(error)
                self.bot.loop.call_soon_threadsafe(done_event.set)

            ffmpeg_path = str(os.getenv("FFMPEG_EXECUTABLE", "ffmpeg") or "ffmpeg").strip() or "ffmpeg"
            source = discord.FFmpegPCMAudio(
                source=temp_path,
                executable=ffmpeg_path,
                options="-vn",
            )
            voice_client.play(source, after=_after_play)

            try:
                await asyncio.wait_for(done_event.wait(), timeout=max(10.0, min(480.0, float(playback_timeout))))
            except asyncio.TimeoutError:
                try:
                    voice_client.stop()
                except Exception:
                    pass
                raise RuntimeError("เล่นเสียงในห้องช้ากว่ากำหนด ระบบยกเลิกให้อัตโนมัติ")

            if playback_error["message"]:
                raise RuntimeError(f"เล่นเสียงในห้องไม่สำเร็จ: {playback_error['message']}")
        finally:
            if created_connection and guild.voice_client:
                try:
                    await guild.voice_client.disconnect(force=True)
                except Exception:
                    pass
            try:
                os.remove(temp_path)
            except Exception:
                pass

    def _aihealth_endpoint_for_provider(
        self,
        ai_cog: Any,
        provider: str,
        model: str,
    ) -> str:
        provider_name = str(provider or "").strip().lower()
        if provider_name == "openai":
            return "OpenAI SDK (chat.completions)"

        if provider_name == "ollama":
            base = str(getattr(ai_cog, "ollama_base_url", os.getenv("OLLAMA_BASE_URL", "")) or "").strip().rstrip("/")
            if not base:
                return "N/A"
            return f"{base}/chat" if base.lower().endswith("/api") else f"{base}/api/chat"

        if provider_name == "google":
            base = str(getattr(ai_cog, "google_base_url", os.getenv("GOOGLE_BASE_URL", "")) or "").strip().rstrip("/")
            model_name = str(model or "").strip() or str(getattr(ai_cog, "google_model", "gemini-2.0-flash") or "gemini-2.0-flash")
            if not base:
                return "N/A"
            return f"{base}/models/{model_name}:generateContent"

        if provider_name == "opentyphoon":
            base = str(getattr(ai_cog, "opentyphoon_base_url", os.getenv("OPENTYPHOON_BASE_URL", "")) or "").strip().rstrip("/")
            if not base:
                return "N/A"
            return f"{base}/chat/completions"

        if provider_name == "chindax":
            base = str(getattr(ai_cog, "chindax_base_url", os.getenv("CHINDAX_BASE_URL", "")) or "").strip().rstrip("/")
            path = str(getattr(ai_cog, "chindax_chat_completions_path", "/chat/completions") or "/chat/completions").strip()
            if not path.startswith("/") and not path.startswith("http"):
                path = f"/{path}"
            if not base:
                return path or "N/A"
            return f"{base}{path}" if not path.startswith("http") else path

        if provider_name == "aiforthai":
            base = str(getattr(ai_cog, "aiforthai_base_url", os.getenv("AIFORTHAI_BASE_URL", "")) or "").strip().rstrip("/")
            path = str(getattr(ai_cog, "aiforthai_chat_completions_path", "/chat/completions") or "/chat/completions").strip()
            if not path.startswith("/") and not path.startswith("http"):
                path = f"/{path}"
            if not base:
                return path or "N/A"
            return f"{base}{path}" if not path.startswith("http") else path

        if provider_name == "cloudflare":
            base = str(getattr(ai_cog, "cloudflare_base_url", os.getenv("CLOUDFLARE_BASE_URL", "")) or "").strip().rstrip("/")
            path = str(getattr(ai_cog, "cloudflare_chat_completions_path", "/chat/completions") or "/chat/completions").strip()
            if not path.startswith("/") and not path.startswith("http"):
                path = f"/{path}"
            if not base:
                return path or "N/A"
            return f"{base}{path}" if not path.startswith("http") else path

        if provider_name == "thaillm":
            base = str(getattr(ai_cog, "thaillm_base_url", os.getenv("THAILLM_BASE_URL", "")) or "").strip().rstrip("/")
            path = str(getattr(ai_cog, "thaillm_chat_completions_path", "/v1/chat/completions") or "/v1/chat/completions").strip()
            if not path.startswith("/") and not path.startswith("http"):
                path = f"/{path}"
            if "{model_key}" in path:
                path = "/v1/chat/completions"
            if not base:
                return path or "N/A"
            return f"{base}{path}" if not path.startswith("http") else path

        return "N/A"

    async def _probe_ai_provider(
        self,
        *,
        ai_cog: Any,
        provider: str,
        model: str,
        timeout_seconds: float = 16.0,
    ) -> dict[str, Any]:
        provider_name = str(provider or "").strip().lower()
        endpoint = self._aihealth_endpoint_for_provider(ai_cog, provider_name, model)
        result: dict[str, Any] = {
            "provider": provider_name,
            "model": str(model or "").strip(),
            "endpoint": endpoint,
            "status": "skip",
            "latency_ms": None,
            "detail": "",
        }

        configured = False
        try:
            configured = bool(ai_cog._provider_is_configured(provider_name))
        except Exception:
            configured = False
        if not configured:
            result["detail"] = "not configured"
            return result

        messages_payload = [
            {"role": "system", "content": "Reply with one short line only."},
            {"role": "user", "content": "ping"},
        ]
        started = time.perf_counter()
        try:
            reply = await asyncio.wait_for(
                ai_cog._ask_ai_model_with_provider(
                    "ping",
                    "Reply with one short line only.",
                    messages_payload,
                    provider=provider_name,
                    ai_model=str(model or "").strip(),
                ),
                timeout=timeout_seconds,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            text = str(reply or "").strip()
            if text:
                result["status"] = "ok"
                result["latency_ms"] = latency_ms
                result["detail"] = self._clip_text(text, limit=96)
                return result
            result["status"] = "fail"
            result["latency_ms"] = latency_ms
            result["detail"] = "empty response"
            return result
        except asyncio.TimeoutError:
            result["status"] = "fail"
            result["latency_ms"] = int((time.perf_counter() - started) * 1000)
            result["detail"] = f"timeout>{int(timeout_seconds)}s"
            return result
        except Exception as error:
            result["status"] = "fail"
            result["latency_ms"] = int((time.perf_counter() - started) * 1000)
            result["detail"] = self._clip_text(f"{type(error).__name__}: {error}", limit=140)
            return result

    def _format_aihealth_provider_block(self, row: dict[str, Any], *, active_provider: str) -> tuple[str, str]:
        provider = str(row.get("provider") or "").strip().lower()
        model = str(row.get("model") or "").strip() or "-"
        endpoint = str(row.get("endpoint") or "N/A").strip()
        status = str(row.get("status") or "skip").strip().lower()
        latency = row.get("latency_ms")
        detail = str(row.get("detail") or "").strip()
        provider_label = provider.upper()
        if provider == str(active_provider or "").strip().lower():
            provider_label = f"{provider_label} (ACTIVE)"

        if status == "ok":
            status_line = f"✅ ONLINE ({int(latency or 0)}ms)"
        elif status == "fail":
            status_line = f"❌ FAIL ({int(latency or 0)}ms)"
        else:
            status_line = "⏸️ SKIP"

        text = (
            f"Status: `{status_line}`\n"
            f"Model: `{model}`\n"
            f"Endpoint: `{endpoint}`"
        )
        if detail:
            text += f"\nDetail: `{self._clip_text(detail, 120)}`"
        return provider_label, text

    def _build_ping_embed(
        self,
        bot_ping: int,
        cache_response_time: Any,
        database_response_time: Any,
    ) -> discord.Embed:
        embed = discord.Embed(color=color.green)
        embed.set_author(
            name=self.bot.user.display_name,
            icon_url=self.bot.user.display_avatar.url,
            url=self.bot.urls.WEBSITE,
        )
        embed.set_footer(text="SkylineBOT • Skyline Development")
        embed.description = f"{self.bot.emoji.LATENCY} • **Bot Ping:** `{bot_ping}ms`"
        embed.description += f"\n{self.bot.emoji.STORAGE} • **Storage Ping:** `{database_response_time}ms`"
        embed.description += f"\n{self.bot.emoji.CACHE} • **Cache Ping:** `{cache_response_time}ms`"
        return embed

    async def _ensure_guild_user_profile(
        self, guild_id: int, user_id: int
    ) -> dict[str, Any]:
        row = await storage.guild_user_profiles.get(guild_id=guild_id, user_id=user_id)
        if row:
            normalized = await self._normalize_guild_user_profile_state(guild_id, row)
            return normalized
        created = await storage.guild_user_profiles.insert(
            guild_id=guild_id,
            user_id=user_id,
        )
        return created or {
            "guild_id": guild_id,
            "user_id": user_id,
            "relationship": "single",
            "spouse_id": 0,
            "proposal_to_id": 0,
            "proposal_from_id": 0,
        }

    def _relationship_label(self, relationship: str, guild_id: int | None) -> str:
        value = str(relationship or "single").strip().lower()
        mapping = {
            "single": i18n.tr("profile_status_single", guild_id),
            "married": i18n.tr("profile_status_married", guild_id),
            "in_relationship": i18n.tr("profile_status_in_relationship", guild_id),
            "engaged": "Engaged",
            "complicated": "Complicated",
        }
        return mapping.get(value) or value.replace("_", " ").title()

    def _as_utc_datetime(self, raw_value: Any) -> datetime.datetime | None:
        if not raw_value:
            return None
        if isinstance(raw_value, datetime.datetime):
            return (
                raw_value
                if raw_value.tzinfo is not None
                else raw_value.replace(tzinfo=datetime.timezone.utc)
            )
        text = str(raw_value).strip()
        if not text:
            return None
        try:
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return (
                parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=datetime.timezone.utc)
            )
        except Exception:
            return None

    async def _clear_proposal_pair(
        self,
        *,
        guild_id: int,
        proposer_id: int,
        target_id: int,
    ) -> None:
        proposer = await storage.guild_user_profiles.get(guild_id=guild_id, user_id=proposer_id)
        target = await storage.guild_user_profiles.get(guild_id=guild_id, user_id=target_id)
        if proposer:
            await storage.guild_user_profiles.update(
                id=proposer.get("id"),
                guild_id=guild_id,
                user_id=proposer_id,
                proposal_to_id=0,
                proposal_at=None,
            )
        if target:
            await storage.guild_user_profiles.update(
                id=target.get("id"),
                guild_id=guild_id,
                user_id=target_id,
                proposal_from_id=0,
                proposal_at=None,
            )

    async def _normalize_guild_user_profile_state(
        self,
        guild_id: int,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        if not row:
            return row
        row_id = int(row.get("id") or 0)
        user_id = int(row.get("user_id") or 0)
        spouse_id = int(row.get("spouse_id") or 0)
        relationship = str(row.get("relationship") or "single").strip().lower()
        proposal_to_id = int(row.get("proposal_to_id") or 0)
        proposal_from_id = int(row.get("proposal_from_id") or 0)
        proposal_at = self._as_utc_datetime(row.get("proposal_at"))
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        changed = False
        payload: dict[str, Any] = {"id": row_id, "guild_id": guild_id, "user_id": user_id}

        if relationship == "married" and spouse_id <= 0:
            payload["relationship"] = "single"
            payload["married_at"] = None
            changed = True

        if proposal_to_id <= 0 and proposal_from_id <= 0 and row.get("proposal_at"):
            payload["proposal_at"] = None
            changed = True

        if (proposal_to_id > 0 or proposal_from_id > 0) and proposal_at:
            if (now_utc - proposal_at).total_seconds() > 15 * 60:
                if proposal_to_id > 0:
                    try:
                        await self._clear_proposal_pair(
                            guild_id=guild_id,
                            proposer_id=user_id,
                            target_id=proposal_to_id,
                        )
                    except Exception:
                        pass
                if proposal_from_id > 0:
                    proposer_row = await storage.guild_user_profiles.get(
                        guild_id=guild_id,
                        user_id=proposal_from_id,
                    )
                    if proposer_row and int(proposer_row.get("proposal_to_id") or 0) == user_id:
                        try:
                            await self._clear_proposal_pair(
                                guild_id=guild_id,
                                proposer_id=proposal_from_id,
                                target_id=user_id,
                            )
                        except Exception:
                            pass
                payload["proposal_to_id"] = 0
                payload["proposal_from_id"] = 0
                payload["proposal_at"] = None
                changed = True

        if changed and row_id > 0 and user_id > 0:
            updated = await storage.guild_user_profiles.update(**payload)
            if updated:
                return updated
        return row

    @commands.hybrid_command(
        name="ping", with_app_command=True, help="ดูค่าปิงของบอท"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def ping_command(self, ctx: commands.Context):

        try:

            (
                bot_ping,
                cache_response_time,
                database_response_time,
            ) = await self._collect_ping_metrics()

            logger.info(
                f"Bot Ping: {bot_ping}ms, Database Response Time: {database_response_time}ms, Cache Response Time: {cache_response_time}ms"
            )

            embed = self._build_ping_embed(
                bot_ping=bot_ping,
                cache_response_time=cache_response_time,
                database_response_time=database_response_time,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(
                f"Commmand: ping, Message: {ctx.message.content}, Message ID: {ctx.message.id}, ข้อผิดพลาด: {e}"
            )

            await ctx.send("An ข้อผิดพลาด Occured While Fetching The Ping")

    @commands.hybrid_command(
        name="tts",
        aliases=["ttl"],
        with_app_command=True,
        help="แปลงข้อความเป็นเสียงไทย/อังกฤษ",
    )
    @app_commands.describe(
        lang="ภาษาเสียง: auto/th/en",
        text="ข้อความที่ต้องการให้แปลงเป็นเสียง",
    )
    @app_commands.choices(
        lang=[
            app_commands.Choice(name="Auto (ตรวจจับอัตโนมัติ)", value="auto"),
            app_commands.Choice(name="Thai", value="th"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=25, type=commands.BucketType.user)
    async def tts_command(self, ctx: commands.Context, lang: str = "auto", *, text: str = ""):
        try:
            cleaned_text = self._sanitize_tts_text(text)
            if not cleaned_text:
                return await ctx.send(
                    embed=discord.Embed(
                        description=(
                            "กรุณาใส่ข้อความด้วยครับ\n"
                            f"ตัวอย่าง: `{self.bot.BotConfig.PREFIX}tts th สวัสดีครับ` หรือ `/tts`"
                        ),
                        color=color.red,
                    ),
                    delete_after=12,
                )

            try:
                max_chars = int(str(os.getenv("TTS_MAX_TEXT_LENGTH", "450") or "450"))
            except (TypeError, ValueError):
                max_chars = 450
            max_chars = max(80, min(max_chars, 1800))

            trimmed = False
            if len(cleaned_text) > max_chars:
                clipped = cleaned_text[:max_chars]
                cleaned_text = (clipped.rsplit(" ", 1)[0] or clipped).strip()
                trimmed = True

            resolved_lang = self._resolve_tts_language(lang, cleaned_text)
            preferred_provider = str(os.getenv("TTS_PROVIDER", "google_tts") or "google_tts").strip().lower()
            if preferred_provider not in {"google_tts", "google", "gtts", "pyttsx3"}:
                preferred_provider = "google_tts"

            await self._safe_defer(ctx)

            used_provider = preferred_provider
            used_extension = "mp3"
            audio_bytes: bytes = b""

            try:
                if preferred_provider == "pyttsx3":
                    audio_bytes = await self._synthesize_tts_pyttsx3(cleaned_text, resolved_lang)
                    used_extension = "wav"
                elif preferred_provider == "gtts":
                    audio_bytes = await self._synthesize_tts_gtts(cleaned_text, resolved_lang)
                    used_extension = "mp3"
                else:
                    used_provider = "google_tts"
                    audio_bytes = await self._synthesize_tts_google_web(cleaned_text, resolved_lang)
                    used_extension = "mp3"
            except Exception as first_error:
                if preferred_provider in {"google_tts", "google", "gtts"}:
                    # fallback to local engine when network-based synthesis fails
                    try:
                        audio_bytes = await self._synthesize_tts_pyttsx3(cleaned_text, resolved_lang)
                        used_provider = "pyttsx3"
                        used_extension = "wav"
                    except Exception as second_error:
                        raise RuntimeError(
                            f"TTS failed ({preferred_provider}: {first_error}; pyttsx3: {second_error})"
                        ) from second_error
                else:
                    raise RuntimeError(f"TTS failed: {first_error}") from first_error

            if not audio_bytes:
                raise RuntimeError("TTS returned empty audio data")

            audio_stream = io.BytesIO(audio_bytes)
            audio_stream.seek(0)
            safe_lang = resolved_lang if resolved_lang in {"th", "en"} else "auto"
            audio_file = discord.File(
                fp=audio_stream,
                filename=f"skylinebot_tts_{safe_lang}.{used_extension}",
            )

            embed = discord.Embed(
                title="ข้อความเป็นคำพูด",
                description=(
                    f"Language: `{resolved_lang}`\n"
                    f"Provider: `{used_provider}`\n"
                    f"Length: `{len(cleaned_text)}` chars"
                ),
                color=color.green,
            )
            if trimmed:
                embed.add_field(
                    name="หมายเหตุ",
                    value=f"ข้อความยาวเกินระบบ จึงตัดให้เหลือ {max_chars} ตัวอักษร",
                    inline=False,
                )
            embed.set_footer(text="คำแนะนำ: ใช้ /tts หรือ !tts เพื่อแปลงข้อความไทย/อังกฤษ")

            await ctx.send(embed=embed, file=audio_file)
        except Exception as e:
            logger.error(
                f"Commmand: tts, Message: {getattr(ctx.message, 'content', 'N/A')}, Message ID: {getattr(ctx.message, 'id', 'N/A')}, ข้อผิดพลาด: {e}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description=(
                        "แปลงเสียงไม่สำเร็จครับ ลองใหม่อีกครั้ง หรือลองพิมพ์ข้อความสั้นลง"
                    ),
                    color=color.red,
                ),
                delete_after=12,
            )

    @commands.hybrid_command(
        name="vaja",
        with_app_command=True,
        help="Generate speech with AI FOR THAI VAJA and return as file or voice playback (แปลงข้อความด้วย AI FOR THAI VAJA แล้วส่งไฟล์หรือพูดในห้องเสียง)",
    )
    @app_commands.describe(
        speaker="เลือกเสียงผู้พูด",
        mode="โหมดผลลัพธ์: ส่งไฟล์เสียง หรือให้บอทพูดในห้องเสียง",
        style="สไตล์เสียง (ถ้าไม่ระบุ ระบบจะใช้ค่าเริ่มต้นของ speaker)",
        text="ข้อความที่ต้องการสังเคราะห์เสียง (สูงสุด 400 ตัวอักษร)",
    )
    @app_commands.choices(
        speaker=[
            app_commands.Choice(name="nana • ผู้หญิง • พากย์การ์ตูน", value="nana"),
            app_commands.Choice(name="noina • ผู้หญิง • สปอตโฆษณา", value="noina"),
            app_commands.Choice(name="farah • ผู้หญิง • สารคดี", value="farah"),
            app_commands.Choice(name="mewzy • ผู้หญิง • สปอตโฆษณา", value="mewzy"),
            app_commands.Choice(name="farsai • ผู้หญิง • พากย์การ์ตูน", value="farsai"),
            app_commands.Choice(name="prim • ผู้หญิง • Announcer", value="prim"),
            app_commands.Choice(name="ped • เสียงผู้หญิง • Announcer", value="ped"),
            app_commands.Choice(name="poom • เสียงผู้ชาย • สปอตโฆษณา", value="poom"),
            app_commands.Choice(name="doikham • เสียงผู้ชาย • ภาษาเหนือ", value="doikham"),
            app_commands.Choice(name="praw • เสียงเด็กผู้หญิง", value="praw"),
            app_commands.Choice(name="wayu • เสียงเด็กผู้ชาย", value="wayu"),
            app_commands.Choice(name="namphueng • เสียงผู้หญิง • Anchor-style", value="namphueng"),
            app_commands.Choice(name="toon • เสียงผู้หญิง • Broadcast-style", value="toon"),
            app_commands.Choice(name="sanooch • เสียงผู้หญิง • Teacher-style", value="sanooch"),
            app_commands.Choice(name="thanwa • เสียงผู้ชาย • Broadcast-style", value="thanwa"),
        ],
        mode=[
            app_commands.Choice(name="ส่งเป็นไฟล์เสียง", value="file"),
            app_commands.Choice(name="ให้บอทพูดในห้องเสียง", value="voice"),
        ],
        style=[
            app_commands.Choice(name="default (ไม่กำหนด)", value="default"),
            app_commands.Choice(name="nana", value="nana"),
            app_commands.Choice(name="noina", value="noina"),
            app_commands.Choice(name="farah", value="farah"),
            app_commands.Choice(name="mewzy", value="mewzy"),
            app_commands.Choice(name="farsai", value="farsai"),
            app_commands.Choice(name="prim", value="prim"),
            app_commands.Choice(name="ped", value="ped"),
            app_commands.Choice(name="poom", value="poom"),
            app_commands.Choice(name="doikham", value="doikham"),
            app_commands.Choice(name="praw", value="praw"),
            app_commands.Choice(name="wayu", value="wayu"),
            app_commands.Choice(name="namphueng", value="namphueng"),
            app_commands.Choice(name="toon", value="toon"),
            app_commands.Choice(name="sanooch", value="sanooch"),
            app_commands.Choice(name="thanwa", value="thanwa"),
        ],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=35, type=commands.BucketType.user)
    async def vaja_command(
        self,
        ctx: commands.Context,
        speaker: str = "nana",
        mode: str = "file",
        style: str = "default",
        *,
        text: str = "",
    ):
        try:
            raw_speaker = str(speaker or "").strip()
            raw_mode = str(mode or "").strip()
            raw_style = str(style or "").strip()

            selected_speaker = self._normalize_vaja_speaker(speaker)
            selected_mode = self._normalize_vaja_mode(mode)
            selected_style = self._normalize_vaja_style(style)

            raw_speaker_lower = raw_speaker.lower()
            raw_mode_lower = raw_mode.lower()

            merged_text_source = str(text or "")
            if (
                raw_style
                and raw_style.lower() not in {"default", "none", "auto", "-"}
                and selected_style is None
                and raw_speaker_lower in VAJA_SPEAKERS
                and selected_mode in VAJA_MODE_OPTIONS
            ):
                merged_text_source = f"{raw_style} {merged_text_source}".strip()
                selected_style = None

            if (
                not merged_text_source.strip()
                and raw_speaker
                and raw_speaker_lower not in VAJA_SPEAKERS
                and raw_mode_lower in {"file", "voice", "default", ""}
                and str(raw_style or "").strip().lower() in {"default", ""}
            ):
                merged_text_source = raw_speaker
                selected_speaker = "nana"
                selected_mode = "file"
                selected_style = None

            cleaned_text = self._sanitize_tts_text(merged_text_source)
            if not cleaned_text:
                return await ctx.send(
                    embed=discord.Embed(
                        description=(
                            "กรุณาใส่ข้อความที่ต้องการแปลงเสียงด้วยครับ\n"
                            f"ตัวอย่าง: `{self.bot.BotConfig.PREFIX}vaja nana file สวัสดีครับ` หรือ `/vaja`"
                        ),
                        color=color.red,
                    ),
                    delete_after=12,
                )

            try:
                max_chars = int(str(os.getenv("VAJA_MAX_TEXT_LENGTH", "400") or "400"))
            except (TypeError, ValueError):
                max_chars = 400
            max_chars = max(40, min(max_chars, 400))

            trimmed = False
            if len(cleaned_text) > max_chars:
                clipped = cleaned_text[:max_chars]
                cleaned_text = (clipped.rsplit(" ", 1)[0] or clipped).strip()
                trimmed = True

            await self._safe_defer(ctx)

            audio_bytes, audio_extension = await self._synthesize_vaja_audio(
                text=cleaned_text,
                speaker=selected_speaker,
                style=selected_style,
            )
            if not audio_bytes:
                raise RuntimeError("VAJA ไม่ส่งข้อมูลเสียงกลับมา")

            info_lines = [
                f"Speaker: `{selected_speaker}`",
                f"Mode: `{selected_mode}`",
                f"Length: `{len(cleaned_text)}` chars",
            ]
            if selected_style:
                info_lines.append(f"Style: `{selected_style}`")

            file_fallback_reason = ""
            if selected_mode == "voice":
                voice_ready, voice_reason = self._voice_runtime_status()
                if not voice_ready:
                    file_fallback_reason = voice_reason
                else:
                    if ctx.guild is None:
                        raise RuntimeError("โหมดห้องเสียงใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น")

                    author_voice = getattr(getattr(ctx, "author", None), "voice", None)
                    target_channel = getattr(author_voice, "channel", None)
                    if target_channel is None:
                        raise RuntimeError("คุณต้องเข้าห้องเสียงก่อน แล้วค่อยใช้โหมดให้บอทพูด")

                    bot_member = ctx.guild.get_member(getattr(self.bot.user, "id", 0) or 0)
                    if bot_member is None:
                        bot_member = getattr(ctx.guild, "me", None)
                    if bot_member is not None:
                        permissions = target_channel.permissions_for(bot_member)
                        if not bool(getattr(permissions, "connect", False)):
                            raise RuntimeError("บอทไม่มีสิทธิ์ Connect ในห้องเสียงเป้าหมาย")
                        if not bool(getattr(permissions, "speak", False)):
                            raise RuntimeError("บอทไม่มีสิทธิ์ Speak ในห้องเสียงเป้าหมาย")

                    existing_vc = ctx.guild.voice_client
                    if existing_vc is not None:
                        if hasattr(existing_vc, "queue"):
                            raise RuntimeError(
                                "บอทกำลังใช้ระบบเพลง/Lavalink ในห้องเสียงอยู่ "
                                "เพื่อกันเสียงชน กรุณาใช้โหมด `file` หรือให้บอทออกจากระบบเพลงก่อน"
                            )
                        existing_channel = getattr(existing_vc, "channel", None)
                        existing_channel_id = int(getattr(existing_channel, "id", 0) or 0)
                        target_channel_id = int(getattr(target_channel, "id", 0) or 0)
                        if existing_channel_id != target_channel_id:
                            if self._voice_client_has_active_session(existing_vc):
                                raise RuntimeError(self._vaja_voice_busy_message(existing_vc))
                            raise RuntimeError(
                                f"บอทเชื่อมต่ออยู่ที่ {getattr(existing_channel, 'mention', '`อีกห้องหนึ่ง`')} แล้ว "
                                "เพื่อไม่ให้ชนกัน กรุณาให้บอทออกจากห้องเดิมก่อน"
                            )
                        if self._voice_client_has_active_session(existing_vc):
                            raise RuntimeError(self._vaja_voice_busy_message(existing_vc))

                    playback_timeout = max(12.0, min(420.0, 12.0 + (len(cleaned_text) * 0.42)))
                    try:
                        await self._play_vaja_audio_to_voice(
                            guild=ctx.guild,
                            target_channel=target_channel,
                            audio_bytes=audio_bytes,
                            extension=audio_extension,
                            playback_timeout=playback_timeout,
                        )
                    except Exception as play_error:
                        play_error_text = str(play_error or "").strip()
                        lowered = play_error_text.lower()
                        if (
                            "library needed in order to use voice" in lowered
                            or "pynacl" in lowered
                            or "davey" in lowered
                            or "ffmpeg was not found" in lowered
                            or "ffmpeg not found" in lowered
                            or "no such file or directory" in lowered
                        ):
                            file_fallback_reason = play_error_text
                        else:
                            raise

                    if not file_fallback_reason:
                        embed = discord.Embed(
                            title="VAJA ข้อความเป็นคำพูด",
                            description="\n".join(info_lines + [f"Voice Channel: {target_channel.mention}"]),
                            color=color.green,
                        )
                        if trimmed:
                            embed.add_field(
                                name="หมายเหตุ",
                                value=f"ข้อความยาวเกินระบบ จึงตัดให้เหลือ {max_chars} ตัวอักษร",
                                inline=False,
                            )
                        embed.set_footer(text="ระบบเล่นจบแล้วจะออกจากห้องเสียงให้อัตโนมัติ")
                        return await ctx.send(embed=embed)

            if file_fallback_reason:
                info_lines.append("Voice Fallback: `ส่งไฟล์เสียงแทน`")
                info_lines.append(f"Reason: `{self._clip_text(file_fallback_reason, 150)}`")

            audio_stream = io.BytesIO(audio_bytes)
            audio_stream.seek(0)
            audio_file = discord.File(
                fp=audio_stream,
                filename=f"skylinebot_vaja_{selected_speaker}.{audio_extension}",
            )
            embed = discord.Embed(
                title="VAJA ข้อความเป็นคำพูด",
                description="\n".join(info_lines),
                color=(color.orange if file_fallback_reason else color.green),
            )
            if trimmed:
                embed.add_field(
                    name="หมายเหตุ",
                    value=f"ข้อความยาวเกินระบบ จึงตัดให้เหลือ {max_chars} ตัวอักษร",
                    inline=False,
                )
            if file_fallback_reason:
                embed.set_footer(text="ระบบ fallback เป็นไฟล์อัตโนมัติ เพราะเครื่อง host ยังไม่พร้อมสำหรับ voice mode")
            else:
                embed.set_footer(text="คำแนะนำ: ใช้ mode=voice เพื่อให้บอทพูดในห้องเสียง")
            await ctx.send(embed=embed, file=audio_file)
        except Exception as error:
            logger.error(
                f"Commmand: vaja, Message: {getattr(ctx.message, 'content', 'N/A')}, "
                f"Message ID: {getattr(ctx.message, 'id', 'N/A')}, ข้อผิดพลาด: {error}"
            )
            await ctx.send(
                embed=discord.Embed(
                    description=f"สังเคราะห์เสียง VAJA ไม่สำเร็จ: `{self._clip_text(error, 220)}`",
                    color=color.red,
                ),
                delete_after=16,
            )

    @commands.hybrid_command(
        name="aihealth",
        with_app_command=True,
        help="Check real-time AI provider status (เช็กสถานะ AI provider แบบเรียลไทม์)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.guild)
    async def aihealth_command(self, ctx: commands.Context):
        if self._aihealth_lock.locked():
            return await ctx.send(
                embed=discord.Embed(
                    description="กำลังมีการเช็ก AI อยู่แล้ว กรุณารอสักครู่แล้วลองใหม่ครับ",
                    color=color.orange,
                ),
                delete_after=10,
            )

        async with self._aihealth_lock:
            await self._safe_defer(ctx)
            ai_cog = self._get_ai_message_cog()
            if ai_cog is None:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่พบ AI runtime module (`message` cog) ในระบบตอนนี้ครับ",
                        color=color.red,
                    )
                )

            try:
                await ctx.trigger_typing()
            except Exception:
                pass
            active_provider = str(getattr(ai_cog, "ai_provider", "opentyphoon") or "opentyphoon").strip().lower()
            try:
                if hasattr(self.bot, "ownerbot_runtime_ai_provider"):
                    active_provider = str(
                        await self.bot.ownerbot_runtime_ai_provider(fallback=active_provider)
                        or active_provider
                    ).strip().lower()
            except Exception:
                pass

            active_model = ""
            try:
                if hasattr(self.bot, "ownerbot_runtime_ai_model"):
                    active_model = str(
                        await self.bot.ownerbot_runtime_ai_model(
                            fallback=str(ai_cog._provider_default_model(active_provider) or "")
                        )
                        or ""
                    ).strip()
            except Exception:
                active_model = ""

            providers = ["openai", "ollama", "google", "opentyphoon", "chindax", "aiforthai", "cloudflare", "thaillm"]
            if active_provider in providers:
                providers.remove(active_provider)
                providers.insert(0, active_provider)

            tasks = []
            for provider_name in providers:
                default_model = str(ai_cog._provider_default_model(provider_name) or "").strip()
                model_to_use = active_model if provider_name == active_provider and active_model else default_model
                tasks.append(
                    self._probe_ai_provider(
                        ai_cog=ai_cog,
                        provider=provider_name,
                        model=model_to_use,
                    )
                )

            rows = await asyncio.gather(*tasks, return_exceptions=False)
            ok_count = len([item for item in rows if str(item.get("status")) == "ok"])
            fail_count = len([item for item in rows if str(item.get("status")) == "fail"])
            skip_count = len([item for item in rows if str(item.get("status")) == "skip"])

            embed = discord.Embed(
                title="การตรวจสุขภาพเอไอ",
                description=(
                    f"Active Provider: `{active_provider}`\n"
                    f"Active Model: `{active_model or (ai_cog._provider_default_model(active_provider) or '-')}`\n"
                    f"Summary: ✅ `{ok_count}` | ❌ `{fail_count}` | ⏸️ `{skip_count}`"
                ),
                color=color.blue if fail_count == 0 else color.orange,
                timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
            )
            embed.set_footer(text="SkylineBOT • Realtime provider probe")

            for row in rows:
                field_name, field_value = self._format_aihealth_provider_block(
                    row,
                    active_provider=active_provider,
                )
                embed.add_field(name=field_name, value=field_value, inline=False)

            await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="report",
        with_app_command=True,
        help="ส่งรายงานข้อความที่ตอบกลับถึงทีมงานบอท",
        usage="reply + report <reason>",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=30, type=commands.BucketType.user)
    async def report_command(self, ctx: commands.Context, *, message: str = None):
        try:
            guild_id = getattr(getattr(ctx, "guild", None), "id", None)
            is_th = i18n.guild_lang(guild_id) == "th"

            reference = getattr(getattr(ctx, "message", None), "reference", None)
            referenced_message = None
            if reference and getattr(reference, "message_id", None) and ctx.channel:
                referenced_message = getattr(reference, "resolved", None)
                if not isinstance(referenced_message, discord.Message):
                    try:
                        referenced_message = await ctx.channel.fetch_message(
                            reference.message_id
                        )
                    except Exception:
                        referenced_message = None

            report_reason = message.strip() if isinstance(message, str) and message.strip() else None

            if not referenced_message and not report_reason:
                return await ctx.send(
                    embed=discord.Embed(
                        description=(
                            f"กรุณา reply ข้อความเป้าหมาย หรือระบุเหตุผล เช่น `{self.bot.BotConfig.PREFIX}report <เหตุผล>`"
                            if is_th
                            else f"Please reply to a target message or provide a reason, e.g. `{self.bot.BotConfig.PREFIX}report <reason>`"
                        ),
                        color=color.red,
                    ),
                    delete_after=10,
                )

            report_channel_id = int(
                getattr(
                    self.bot.channels,
                    "support_report_channel",
                    self.bot.channels.report_channel,
                )
                or 0
            )
            report_channel = self.bot.get_channel(report_channel_id)
            if not report_channel:
                logger.error(
                    f"User report channel not found. Channel ID: {report_channel_id}"
                )
                return await ctx.send(
                    embed=discord.Embed(
                        description=(
                            "ไม่พบห้องสำหรับส่งรายงาน กรุณาติดต่อแอดมิน"
                            if is_th
                            else "Report channel is not configured. Please contact an admin."
                        ),
                        color=color.red,
                    ),
                    delete_after=10,
                )

            report_embed = discord.Embed(
                title="รายงานผู้ใช้",
                description=report_reason or "-",
                color=color.yellow,
                timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
            )
            report_embed.add_field(
                name="Reporter",
                value=f"{ctx.author.mention} ({ctx.author.id})",
                inline=False,
            )
            report_embed.add_field(
                name="Guild",
                value=(
                    f"{ctx.guild.name} ({ctx.guild.id})"
                    if ctx.guild
                    else "Direct Messages"
                ),
                inline=True,
            )
            report_embed.add_field(
                name="Channel",
                value=(
                    f"{ctx.channel.mention} ({ctx.channel.id})"
                    if getattr(ctx, "channel", None)
                    else "Unknown"
                ),
                inline=True,
            )
            report_embed.set_author(
                name=str(ctx.author),
                icon_url=ctx.author.display_avatar.url,
            )

            if referenced_message:
                report_embed.add_field(
                    name=("ลิงก์ข้อความเป้าหมาย" if is_th else "Target Message Link"),
                    value=f"[Jump to message]({referenced_message.jump_url})",
                    inline=False,
                )
                report_embed.add_field(
                    name=("ผู้เขียนข้อความเป้าหมาย" if is_th else "Target Message Author"),
                    value=f"{referenced_message.author} ({referenced_message.author.id})",
                    inline=False,
                )
                target_content = (
                    referenced_message.content.strip()
                    if referenced_message.content and referenced_message.content.strip()
                    else ("(ไม่มีข้อความ)" if is_th else "(No text content)")
                )
                if len(target_content) > 900:
                    target_content = target_content[:900] + "..."
                report_embed.add_field(
                    name=("เนื้อหาข้อความเป้าหมาย" if is_th else "Target Message Content"),
                    value=target_content,
                    inline=False,
                )

                attachments = [a.url for a in referenced_message.attachments]
                if attachments:
                    attachment_value = "\n".join(attachments)
                    if len(attachment_value) > 900:
                        attachment_value = attachment_value[:900] + "..."
                    report_embed.add_field(
                        name=("ไฟล์แนบของข้อความเป้าหมาย" if is_th else "Target Message Attachments"),
                        value=attachment_value,
                        inline=False,
                    )

            await report_channel.send(embed=report_embed)

            await ctx.send(
                embed=discord.Embed(
                    description=(
                        "ส่งรายงานเรียบร้อยแล้ว ขอบคุณสำหรับข้อมูล"
                        if is_th
                        else "Your report was submitted successfully. Thank you."
                    ),
                    color=color.green,
                ),
                delete_after=10,
            )
        except Exception as e:
            logger.error(
                f"Commmand: report, Message: {getattr(ctx.message, 'content', 'N/A')}, Message ID: {getattr(ctx.message, 'id', 'N/A')}, ข้อผิดพลาด: {e}"
            )
            await ctx.send(
                "เกิดข้อผิดพลาดระหว่างส่งรายงาน"
                if i18n.guild_lang(getattr(getattr(ctx, "guild", None), "id", None))
                == "th"
                else "An ข้อผิดพลาด Occured While Sending The Report"
            )

    @commands.hybrid_command(
        name="invite", with_app_command=True, help="เชิญบอทเข้าร่วมเซิร์ฟเวอร์ของคุณ"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def invite_command(self, ctx: commands.Context):

        try:

            embed = discord.Embed(
                title="เชิญบอทเข้าร่วมเซิร์ฟเวอร์ของคุณ",
                description="แจ้งเตือน: คุณสามารถเชิญบอทเข้าร่วมเซิร์ฟเวอร์ได้โดยกดปุ่มด้านล่าง\nโปรดตรวจสอบว่าคุณมีสิทธิ์ที่จำเป็นในการเพิ่มบอท\nขอให้สนุกกับการใช้งานบอทของเรา",
                color=color.green,
            )

            embed.set_footer(
                text="SkylineBOT • Skyline Development",
                icon_url=self.bot.user.display_avatar.url,
            )

            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            view = discord.ui.View()

            view.add_item(
                discord.ui.Button(
                    emoji=self.bot.emoji.INVITE,
                    label="เชิญบอท ✨",
                    url=self.bot.urls.INVITE,
                )
            )

            # send as ephemeral if its a slash command

            await ctx.send(embed=embed, view=view, mention_author=False)

        except Exception as e:

            logger.error(
                f"Commmand: ping, Message: {ctx.message.content}, Message ID: {ctx.message.id}, ข้อผิดพลาด: {e}"
            )

            await ctx.send("An ข้อผิดพลาด Occured While Sending The Invite Link")

    @commands.hybrid_command(
        name="supportlink", with_app_command=True, help="เข้าร่วมเซิร์ฟเวอร์ซัพพอร์ต"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def support_command(self, ctx: commands.Context):

        try:
            await self._send_support_server_card(ctx)

        except Exception as e:

            logger.error(
                f"Commmand: supportlink, Message: {ctx.message.content}, Message ID: {ctx.message.id}, ข้อผิดพลาด: {e}"
            )

            await ctx.send("An ข้อผิดพลาด Occured While Sending The ช่วยเหลือ Server Link")

    @commands.hybrid_command(
        name="support", with_app_command=True, help="เข้าร่วมเซิร์ฟเวอร์ซัพพอร์ต"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def support_short_command(self, ctx: commands.Context):

        try:
            await self._send_support_server_card(ctx)
        except Exception as e:
            logger.error(
                f"Commmand: support, Message: {ctx.message.content}, Message ID: {ctx.message.id}, ข้อผิดพลาด: {e}"
            )
            await ctx.send("An ข้อผิดพลาด Occured While Sending The ช่วยเหลือ Server Link")

    async def _send_support_server_card(self, ctx: commands.Context) -> None:
        embed = discord.Embed(
            title="ช่วยเหลือ",
            description="แจ้งเตือน: คุณสามารถเข้าร่วมเซิร์ฟเวอร์ช่วยเหลือของเราได้โดยกดปุ่มด้านล่าง\nโปรดปฏิบัติตามกฎของเซิร์ฟเวอร์\nขอให้สนุกกับการใช้งานบอทของเรา",
            color=color.green,
        )

        embed.set_footer(
            text=f"Requested by {ctx.author.name}",
            icon_url=self.bot.user.display_avatar.url,
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="ศูนย์ช่วยเหลือ",
                url=self.bot.urls.SUPPORT_SERVER,
                emoji=self.bot.emoji.SUPPORT,
            )
        )

        # send as ephemeral if its a slash command
        await ctx.send(embed=embed, view=view, mention_author=False)

    @commands.hybrid_command(
        name="vote", with_app_command=True, help="โหวตให้บอท"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def vote_command(self, ctx: commands.Context):

        try:

            embed = discord.Embed(
                title="โหวต",
                description="แจ้งเตือน: คุณสามารถโหวตให้บอทได้โดยกดปุ่มด้านล่าง\nโปรดปฏิบัติตามกฎของเว็บไซต์โหวต\nขอให้สนุกกับการใช้งานบอทของเรา",
                color=color.green,
            )

            embed.set_footer(
                text=f"Requested by {ctx.author.name}",
                icon_url=self.bot.user.display_avatar.url,
            )

            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            view = discord.ui.View()

            view.add_item(
                discord.ui.Button(
                    label="โหวตเลย",
                    url=self.bot.urls.VOTE,
                    emoji=self.bot.emoji.VOTE,
                )
            )

            # send as ephemeral if its a slash command

            await ctx.send(embed=embed, view=view, mention_author=False)

        except Exception as e:

            logger.error(
                f"Commmand: ping, Message: {ctx.message.content}, Message ID: {ctx.message.id}, ข้อผิดพลาด: {e}"
            )

            await ctx.send("An ข้อผิดพลาด Occured While Sending The Voting Link")

    @commands.hybrid_command(
        name="stats",
        with_app_command=True,
        help="ดูข้อมูลสถานะของบอท",
        aliases=["statistics", "status"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def stats_command(self, ctx: commands.Context):

        # show the cpu uses and memory uses in % also the os and the python version

        try:

            cou_usage = psutil.cpu_percent()

            memory_usage = psutil.virtual_memory().percent

            os_name = platform.uname().system

            python_version = platform.python_version()

            embed = discord.Embed(color=color.black, type="rich")

            # embed.set_author(

            #     name=f"{self.bot.user.display_name} Status",

            #     icon_url=self.bot.user.display_avatar.url

            # )

            def format_number(num):

                return num

                # replace it with the below code if you want to format the numbers

                # if num >= 1_000_000_000:

                #     return f"{num / 1_000_000_000:.1f}b"

                # elif num >= 1_000_000:

                #     return f"{num / 1_000_000:.1f}m"

                # elif num >= 1_000:

                #     return f"{num / 1_000:.1f}k"

                # else:

                #     return str(num)

            embed.description = f"{self.bot.emoji.SEARCH} : **[Hey users !\nHere’s all the info you need\nabout {self.bot.user.display_name}. Check it out]({self.bot.urls.SUPPORT_SERVER})**"

            embed.description += f"\n\n{self.bot.emoji.BOT} : **__Basic Status__**\n"

            embed.description += f"> `User's` : **{format_number(sum([guild.member_count for guild in self.bot.guilds if guild.member_count]))}**\n"

            embed.description += (
                f"> `Guilds` : **{format_number(len(self.bot.guilds))}**\n"
            )

            embed.description += f"> `Python` : **{python_version}**\n"

            embed.description += f"> `Dsc-py` : **{discord.__version__}**\n"

            embed.description += f"> `BotCpu` : **{cou_usage}%**\n"

            embed.description += f"> `BotRam` : **{memory_usage}%**\n"

            embed.description += f"> `BotPid` : **{psutil.Process().pid}**\n"

            embed.description += f"> `Shards` : **{self.bot.shard_count}**\n"

            embed.description += f"> `HostOS` : **{os_name}**\n"

            embed.description += f"> [Invite]({self.bot.urls.INVITE}) | [ช่วยเหลือ]({self.bot.urls.SUPPORT_SERVER})  | [โหวต]({self.bot.urls.VOTE})\n"

            embed.description += f"\n> -# **Hosted on shaodwhost.fun**"

            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            if self.bot.developers:

                embed.set_footer(
                    text=f"SkylineBOT • Skyline Development",
                    icon_url=self.bot.user.display_avatar.url,
                )

            else:

                embed.set_footer(
                    text="SkylineBOT • Skyline Development",
                    icon_url=self.bot.user.display_avatar.url,
                )

            view = discord.ui.View()

            invite_me_button = discord.ui.Button(
                label="Invite Bot",
                emoji=self.bot.emoji.INVITE,
                style=discord.ButtonStyle.green,
                url=self.bot.urls.INVITE,
            )

            support_server_button = discord.ui.Button(
                label="ศูนย์ช่วยเหลือ",
                emoji=self.bot.emoji.SUPPORT,
                style=discord.ButtonStyle.green,
                url=self.bot.urls.SUPPORT_SERVER,
            )

            view.add_item(support_server_button)

            view.add_item(invite_me_button)

            await ctx.send(embed=embed, view=view)

        except Exception as e:

            logger.error(
                f"Commmand: ping, Message: {ctx.message.content}, Message ID: {ctx.message.id}, ข้อผิดพลาด: {e}"
            )

            await ctx.send("An ข้อผิดพลาด Occured While Fetching The Stats")

    async def _botinfo_mode_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        guild_id = getattr(getattr(interaction, "guild", None), "id", None)
        is_th = i18n.guild_lang(guild_id) == "th" if guild_id else False
        options = [
            ("bot", "ข้อมูลบอท" if is_th else "Bot Information"),
            ("dev", "ข้อมูลทีมพัฒนา" if is_th else "Developer Information"),
            ("website", "Website Links"),

        ]
        needle = str(current or "").strip().lower()
        out: list[app_commands.Choice[str]] = []
        for value, label in options:
            if needle and needle not in value and needle not in label.lower():
                continue
            out.append(app_commands.Choice(name=f"{label} ({value})", value=value))
        return out[:25]

    def _botinfo_links_view(self, guild_id: int | None) -> discord.ui.View:
        is_th = i18n.guild_lang(guild_id) == "th" if guild_id else False
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label=("เชิญบอท" if is_th else "Invite"),
                emoji=self.bot.emoji.INVITE,
                style=discord.ButtonStyle.green,
                url=self.bot.urls.INVITE,
            )
        )
        view.add_item(
            discord.ui.Button(
                label=("ซัพพอร์ต" if is_th else "ช่วยเหลือ"),
                emoji=self.bot.emoji.SUPPORT,
                style=discord.ButtonStyle.green,
                url=self.bot.urls.SUPPORT_SERVER,
            )
        )
        view.add_item(
            discord.ui.Button(
                label=("โหวต" if is_th else "โหวต"),
                emoji=self.bot.emoji.VOTE,
                style=discord.ButtonStyle.link,
                url=self.bot.urls.VOTE,
            )
        )
        return view

    @staticmethod
    def _normalize_clone_plan_tier(raw_value: Any) -> str:
        normalized = str(raw_value or "free").strip().lower().replace(" ", "_")
        mapping = {
            "free": "free",
            "basic": "free",
            "silver": "silver",
            "silver_guild_preminum": "silver",
            "silver_guild_premium": "silver",
            "gold": "golden",
            "gole": "golden",
            "golden": "golden",
            "golden_guild_premium": "golden",
            "diamond": "diamond",
            "diamond_guild_premium": "diamond",
            "permanent": "permanent",
            "lifetime": "permanent",
            "forever": "permanent",
            "permanent_guild_premium": "permanent",
            "lifetime_guild_premium": "permanent",
        }
        return mapping.get(normalized, "free")

    def _clone_plan_limit_for_guild(self, guild_id: int) -> tuple[str, Optional[int]]:
        raw_subscription = (
            (cache.guilds.get(str(int(guild_id)), {}) or {}).get("subscription", "free")
        )
        tier = self._normalize_clone_plan_tier(raw_subscription)
        return tier, CLONE_LIMITS_BY_PLAN.get(tier, 2)

    @staticmethod
    def _clone_limit_text(limit_value: Optional[int]) -> str:
        return "ไม่จำกัด" if limit_value is None else str(int(limit_value))

    @staticmethod
    def _sanitize_clone_emoji_name(raw_name: str, fallback_index: int) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(raw_name or "").strip())
        cleaned = cleaned.strip("_")
        if len(cleaned) < 2:
            cleaned = f"emoji_{int(fallback_index)}"
        if len(cleaned) > 32:
            cleaned = cleaned[:32].rstrip("_")
        if len(cleaned) < 2:
            cleaned = f"e{int(fallback_index)}"
        return cleaned

    async def _safe_defer(self, ctx: commands.Context) -> None:
        interaction = getattr(ctx, "interaction", None)
        if interaction is None or interaction.response.is_done():
            return
        try:
            await ctx.defer()
        except (discord.NotFound, discord.InteractionResponded):
            return
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                return
            raise

    def _normalize_botinfo_url(self, raw_url: str) -> str:
        value = str(raw_url or "").strip()
        if not value:
            return ""
        if "://" not in value:
            value = f"https://{value}"
        try:
            parsed = urlparse(value)
        except Exception:
            return ""
        scheme = str(parsed.scheme or "").lower().strip()
        netloc = str(parsed.netloc or "").strip()
        if scheme not in {"http", "https"} or not netloc:
            return ""
        normalized = parsed._replace(fragment="").geturl()
        return normalized.rstrip("/")

    def _build_botinfo_status_urls(self) -> tuple[str, str, str]:
        raw_website = str(
            getattr(getattr(self.bot, "urls", None), "WEBSITE", "") or ""
        ).strip()
        if not raw_website:
            raw_website = str(
                getattr(getattr(self.bot, "BotConfig", None), "DASHBOARD_BASE_URL", "")
                or ""
            ).strip()
        website_url = self._normalize_botinfo_url(raw_website)
        bot_status_url = (
            self._normalize_botinfo_url(f"{website_url}/dashboard/status?view=bot")
            if website_url
            else ""
        )
        configured_service_status = str(os.getenv("SUPPORT_STATUS_PUBLIC_URL") or "").strip()
        service_status_url = self._normalize_botinfo_url(configured_service_status)
        if not service_status_url and website_url:
            service_status_url = self._normalize_botinfo_url(
                f"{website_url}/dashboard/status?view=service"
            )
        return website_url, service_status_url, bot_status_url

    async def _probe_botinfo_status_url(
        self,
        url: str,
        *,
        timeout_seconds: float = 4.0,
    ) -> dict[str, Any]:
        safe_url = self._normalize_botinfo_url(url)
        if not safe_url:
            return {
                "ok": False,
                "status_code": None,
                "latency_ms": None,
                "error": "not_configured",
            }

        def _request() -> dict[str, Any]:
            started = time.perf_counter()
            try:
                response = requests.get(
                    safe_url,
                    timeout=timeout_seconds,
                    allow_redirects=True,
                    headers={"User-Agent": "SkylineBOT/botinfo-status-check"},
                )
                status_code = int(response.status_code)
                latency_ms = int((time.perf_counter() - started) * 1000)
                return {
                    "ok": 200 <= status_code < 400,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "error": "",
                }
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                return {
                    "ok": False,
                    "status_code": None,
                    "latency_ms": latency_ms,
                    "error": str(exc),
                }

        return await asyncio.to_thread(_request)

    def _format_botinfo_status_value(
        self,
        *,
        url: str,
        probe: dict[str, Any],
        is_th: bool,
    ) -> str:
        safe_url = self._normalize_botinfo_url(url)
        if not safe_url:
            return (
                "ยังไม่ได้ตั้งค่า URL สถานะ"
                if is_th
                else "Status URL is not configured."
            )

        status_code = probe.get("status_code")
        latency_ms = probe.get("latency_ms")
        if probe.get("ok"):
            label = "ออนไลน์" if is_th else "Online"
            icon = "🟢"
        else:
            label = "ไม่พร้อมใช้งาน" if is_th else "Unavailable"
            icon = "🔴"
        code_text = (
            f"HTTP {status_code}"
            if isinstance(status_code, int)
            else ("ไม่พบรหัสตอบกลับ" if is_th else "No HTTP code")
        )
        latency_text = (
            f"{int(latency_ms)}ms"
            if isinstance(latency_ms, int)
            else ("ไม่ทราบเวลา" if is_th else "Unknown latency")
        )
        return f"{safe_url}\n{icon} {label} | {code_text} | {latency_text}"

    def _botinfo_website_links_view(
        self,
        guild_id: int | None,
        *,
        service_status_url: str,
        bot_status_url: str,
        bot_invite_url: str,
    ) -> discord.ui.View:
        is_th = i18n.guild_lang(guild_id) == "th" if guild_id else False
        view = discord.ui.View()

        # Row 0: status actions
        if service_status_url:
            view.add_item(
                discord.ui.Button(
                    label=("สถานะบริการเว็บ" if is_th else "Service Status"),
                    style=discord.ButtonStyle.link,
                    url=service_status_url,
                    row=0,
                )
            )
        if bot_status_url:
            view.add_item(
                discord.ui.Button(
                    label=("สถานะบอท" if is_th else "Bot Status"),
                    style=discord.ButtonStyle.link,
                    url=bot_status_url,
                    row=0,
                )
            )

        # Row 1: bot actions
        if bot_invite_url:
            view.add_item(
                discord.ui.Button(
                    label=("เชิญบอท" if is_th else "Invite Bot"),
                    style=discord.ButtonStyle.link,
                    url=bot_invite_url,
                    row=1,
                )
            )

        support_url = str(getattr(getattr(self.bot, "urls", None), "SUPPORT_SERVER", "") or "").strip()
        if support_url:
            view.add_item(
                discord.ui.Button(
                    label=("ซัพพอร์ต" if is_th else "Support"),
                    style=discord.ButtonStyle.link,
                    url=support_url,
                    row=1,
                )
            )

        vote_url = str(getattr(getattr(self.bot, "urls", None), "VOTE", "") or "").strip()
        if vote_url:
            view.add_item(
                discord.ui.Button(
                    label=("โหวต" if is_th else "Vote"),
                    style=discord.ButtonStyle.link,
                    url=vote_url,
                    row=1,
                )
            )

        return view

    @commands.hybrid_group(
        name="clone",
        with_app_command=True,
        invoke_without_command=True,
        help="โคลนอิโมจิ/ช่อง/บทบาทจากกิลด์อื่น",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=20, type=commands.BucketType.user)
    async def clone_group(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")
        plan_tier, plan_limit = self._clone_plan_limit_for_guild(ctx.guild.id)
        plan_label_map = {
            "free": "Free",
            "silver": "Silver",
            "golden": "Golden",
            "diamond": "Diamond",
            "permanent": "Permanent",
        }
        limit_text = self._clone_limit_text(plan_limit)
        embed = discord.Embed(
            title="คำสั่งโคลน",
            color=color.blue,
            description=(
                "`/clone emoji source_guild_id:<id> [limit]` - โคลนอีโมจิจากกิลด์ต้นทาง\n"
                "`/clone server source_guild_id:<id> [include_roles] [include_channels] [limit]` - โคลนโครงสร้างเซิร์ฟเวอร์"
            ),
        )
        embed.add_field(
            name="Plan Limit",
            value=(
                f"Current: **{plan_label_map.get(plan_tier, 'Free')}**\n"
                f"Limit per action: **{limit_text}**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Plan Matrix",
            value="Free: **2** | Silver: **5** | Golden: **8** | Diamond: **15** | Permanent: **Unlimited**",
            inline=False,
        )
        await ctx.send(embed=embed)

    @clone_group.command(name="emoji", help="โคลนอีโมจิจากกิลด์อื่นเข้ากิลด์นี้")
    @app_commands.describe(
        source_guild_id="กิลด์ต้นทางที่ต้องการโคลนอีโมจิ (บอทต้องอยู่ในกิลด์นั้น)",
        limit="จำนวนอีโมจิที่จะโคลน (ตามสิทธิ์แพ็กเกจ)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.guild)
    async def clone_emoji(
        self,
        ctx: commands.Context,
        source_guild_id: int,
        limit: Optional[int] = None,
    ):
        try:
            await self._safe_defer(ctx)
            if ctx.guild is None:
                return await ctx.send("This command can only be used in a server.")
            if not await checks.check_is_moderator_permissions(ctx, "manage_emojis"):
                return

            me = ctx.guild.me
            if me is None or not (
                getattr(me.guild_permissions, "manage_emojis", False)
                or getattr(me.guild_permissions, "manage_emojis_and_stickers", False)
            ):
                return await ctx.send(
                    embed=discord.Embed(
                        description="ฉันต้องการสิทธิ์ \"จัดการอิโมจิและสติ๊กเกอร์\"",
                        color=color.red,
                    )
                )

            source_guild = self.bot.get_guild(int(source_guild_id))
            if source_guild is None:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่พบกิลด์ต้นทาง หรือบอทยังไม่ได้อยู่ในกิลด์นั้น",
                        color=color.red,
                    )
                )
            if source_guild.id == ctx.guild.id:
                return await ctx.send(
                    embed=discord.Embed(
                        description="กิลด์ต้นทางต้องไม่ใช่กิลด์เดียวกับปลายทาง",
                        color=color.red,
                    )
                )

            source_emojis = list(source_guild.emojis)
            if not source_emojis:
                return await ctx.send(
                    embed=discord.Embed(
                        description="กิลด์ต้นทางไม่มีอีโมจิให้โคลน",
                        color=color.orange,
                    )
                )

            plan_tier, plan_limit = self._clone_plan_limit_for_guild(ctx.guild.id)
            requested = max(1, int(limit or (plan_limit or len(source_emojis))))
            if plan_limit is not None:
                requested = min(requested, int(plan_limit))

            static_used = len([item for item in ctx.guild.emojis if not item.animated])
            animated_used = len([item for item in ctx.guild.emojis if item.animated])
            static_capacity = max(0, int(ctx.guild.emoji_limit or 50) - static_used)
            animated_capacity = max(0, int(ctx.guild.emoji_limit or 50) - animated_used)

            existing_names = {str(item.name or "").casefold() for item in ctx.guild.emojis}
            candidates = [
                item
                for item in source_emojis
                if str(item.name or "").casefold() not in existing_names
            ]
            if not candidates:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีอีโมจิใหม่ให้โคลน (ชื่อซ้ำทั้งหมด)",
                        color=color.orange,
                    )
                )

            created = 0
            failed = 0
            skipped_capacity = 0
            total_checked = 0
            reason = f"Clone emoji by {ctx.author} ({ctx.author.id}) from guild {source_guild.id}"

            for source_emoji in candidates:
                if created >= requested:
                    break
                total_checked += 1
                if source_emoji.animated and animated_capacity <= 0:
                    skipped_capacity += 1
                    continue
                if (not source_emoji.animated) and static_capacity <= 0:
                    skipped_capacity += 1
                    continue

                try:
                    emoji_name = self._sanitize_clone_emoji_name(
                        source_emoji.name,
                        fallback_index=(created + 1),
                    )
                    image_bytes = await source_emoji.read()
                    await ctx.guild.create_custom_emoji(
                        name=emoji_name,
                        image=image_bytes,
                        reason=reason,
                    )
                    created += 1
                    existing_names.add(emoji_name.casefold())
                    if source_emoji.animated:
                        animated_capacity = max(0, animated_capacity - 1)
                    else:
                        static_capacity = max(0, static_capacity - 1)
                except Exception:
                    failed += 1

            plan_label_map = {
                "free": "Free",
                "silver": "Silver",
                "golden": "Golden",
                "diamond": "Diamond",
                "permanent": "Permanent",
            }
            embed = discord.Embed(
                title="ผลการโคลนอิโมจิ",
                color=(color.green if created > 0 else color.orange),
            )
            embed.add_field(name="Source Guild", value=f"{source_guild.name} (`{source_guild.id}`)", inline=False)
            embed.add_field(name="Plan", value=f"{plan_label_map.get(plan_tier, 'Free')} ({self._clone_limit_text(plan_limit)})", inline=True)
            embed.add_field(name="Requested", value=str(requested), inline=True)
            embed.add_field(name="Created", value=str(created), inline=True)
            embed.add_field(name="Failed", value=str(failed), inline=True)
            embed.add_field(name="Skipped (Capacity)", value=str(skipped_capacity), inline=True)
            embed.add_field(name="Checked", value=str(total_checked), inline=True)
            await ctx.send(embed=embed)
        except Exception:
            logger.error(f"Error in clone emoji command: {traceback.format_exc()}")
            await ctx.send(
                embed=discord.Embed(
                    description="เกิดข้อผิดพลาดระหว่างโคลนอีโมจิ",
                    color=color.red,
                )
            )

    @clone_group.command(name="server", help="โคลนโครงสร้างเซิร์ฟเวอร์จากกิลด์อื่น")
    @app_commands.describe(
        source_guild_id="กิลด์ต้นทางที่ต้องการโคลน (บอทต้องอยู่ในกิลด์นั้น)",
        include_roles="โคลนยศจากกิลด์ต้นทาง",
        include_channels="โคลนห้องจากกิลด์ต้นทาง",
        limit="จำนวนรายการสูงสุดต่อประเภท (ตามสิทธิ์แพ็กเกจ)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=45, type=commands.BucketType.guild)
    async def clone_server(
        self,
        ctx: commands.Context,
        source_guild_id: int,
        include_roles: bool = True,
        include_channels: bool = True,
        limit: Optional[int] = None,
    ):
        try:
            await self._safe_defer(ctx)
            if ctx.guild is None:
                return await ctx.send("This command can only be used in a server.")
            if not await checks.check_is_moderator_permissions(ctx, "manage_guild"):
                return
            if not include_roles and not include_channels:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ต้องเลือกอย่างน้อย 1 อย่าง: include_roles หรือ include_channels",
                        color=color.red,
                    )
                )

            me = ctx.guild.me
            missing: list[str] = []
            if me is None:
                missing.extend(["manage_roles", "manage_channels"])
            else:
                if include_roles and not getattr(me.guild_permissions, "manage_roles", False):
                    missing.append("manage_roles")
                if include_channels and not getattr(me.guild_permissions, "manage_channels", False):
                    missing.append("manage_channels")
            if missing:
                return await ctx.send(
                    embed=discord.Embed(
                        description=f"I need permissions: `{', '.join(sorted(set(missing)))}`",
                        color=color.red,
                    )
                )

            source_guild = self.bot.get_guild(int(source_guild_id))
            if source_guild is None:
                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่พบกิลด์ต้นทาง หรือบอทยังไม่ได้อยู่ในกิลด์นั้น",
                        color=color.red,
                    )
                )
            if source_guild.id == ctx.guild.id:
                return await ctx.send(
                    embed=discord.Embed(
                        description="กิลด์ต้นทางต้องไม่ใช่กิลด์เดียวกับปลายทาง",
                        color=color.red,
                    )
                )

            plan_tier, plan_limit = self._clone_plan_limit_for_guild(ctx.guild.id)
            requested = max(
                1,
                int(
                    limit
                    or (plan_limit or max(len(source_guild.roles), len(source_guild.channels), 1))
                ),
            )
            if plan_limit is not None:
                requested = min(requested, int(plan_limit))

            reason = f"Clone server by {ctx.author} ({ctx.author.id}) from guild {source_guild.id}"
            role_id_map: dict[int, discord.Role] = {}
            destination_roles_by_name = {
                str(item.name or "").casefold(): item for item in ctx.guild.roles
            }

            created_roles = 0
            skipped_roles = 0
            failed_roles = 0

            if include_roles:
                source_roles = [
                    role
                    for role in sorted(source_guild.roles, key=lambda item: item.position)
                    if not role.is_default() and not role.managed
                ]
                for source_role in source_roles:
                    if created_roles >= requested:
                        break
                    lookup_key = str(source_role.name or "").casefold()
                    existing = destination_roles_by_name.get(lookup_key)
                    if existing is not None:
                        role_id_map[source_role.id] = existing
                        skipped_roles += 1
                        continue
                    try:
                        created_role = await ctx.guild.create_role(
                            name=str(source_role.name or "role")[:100],
                            permissions=source_role.permissions,
                            colour=source_role.colour,
                            hoist=source_role.hoist,
                            mentionable=source_role.mentionable,
                            reason=reason,
                        )
                        role_id_map[source_role.id] = created_role
                        destination_roles_by_name[lookup_key] = created_role
                        created_roles += 1
                    except Exception:
                        failed_roles += 1

            created_channels = 0
            created_categories = 0
            skipped_channels = 0
            failed_channels = 0
            category_id_map: dict[int, discord.CategoryChannel] = {}
            destination_categories_by_name = {
                str(item.name or "").casefold(): item for item in ctx.guild.categories
            }

            def _build_overwrites(source_channel: discord.abc.GuildChannel) -> dict[Any, discord.PermissionOverwrite]:
                mapped: dict[Any, discord.PermissionOverwrite] = {}
                for target, overwrite in (source_channel.overwrites or {}).items():
                    mapped_target = None
                    if isinstance(target, discord.Role):
                        if target.is_default():
                            mapped_target = ctx.guild.default_role
                        else:
                            mapped_target = role_id_map.get(target.id) or destination_roles_by_name.get(
                                str(target.name or "").casefold()
                            )
                    elif isinstance(target, discord.Member):
                        mapped_target = ctx.guild.get_member(target.id)
                    if mapped_target is not None:
                        mapped[mapped_target] = overwrite
                return mapped

            if include_channels:
                source_channels = sorted(
                    [item for item in source_guild.channels if not isinstance(item, discord.CategoryChannel)],
                    key=lambda channel: (
                        (channel.category.position if channel.category else -1),
                        channel.position,
                    ),
                )

                for source_channel in source_channels:
                    if created_channels >= requested:
                        break

                    destination_category = None
                    source_category = getattr(source_channel, "category", None)
                    if source_category is not None:
                        destination_category = category_id_map.get(source_category.id)
                        if destination_category is None:
                            existing_category = destination_categories_by_name.get(
                                str(source_category.name or "").casefold()
                            )
                            if existing_category is not None:
                                destination_category = existing_category
                            elif created_channels < requested:
                                try:
                                    destination_category = await ctx.guild.create_category(
                                        name=str(source_category.name or "category")[:100],
                                        overwrites=_build_overwrites(source_category),
                                        reason=reason,
                                    )
                                    created_categories += 1
                                except Exception:
                                    failed_channels += 1
                            if destination_category is not None:
                                category_id_map[source_category.id] = destination_category
                                destination_categories_by_name[
                                    str(destination_category.name or "").casefold()
                                ] = destination_category

                    if created_channels >= requested:
                        break

                    try:
                        overwrites = _build_overwrites(source_channel)
                        if isinstance(source_channel, discord.TextChannel):
                            channel_kwargs = {
                                "name": str(source_channel.name or "text-channel")[:100],
                                "category": destination_category,
                                "overwrites": overwrites,
                                "topic": source_channel.topic,
                                "slowmode_delay": source_channel.slowmode_delay,
                                "nsfw": source_channel.nsfw,
                                "reason": reason,
                            }
                            if source_channel.is_news():
                                channel_kwargs["news"] = True
                            await ctx.guild.create_text_channel(**channel_kwargs)
                            created_channels += 1
                        elif isinstance(source_channel, discord.VoiceChannel):
                            await ctx.guild.create_voice_channel(
                                name=str(source_channel.name or "voice-channel")[:100],
                                category=destination_category,
                                overwrites=overwrites,
                                bitrate=min(
                                    int(source_channel.bitrate or 64000),
                                    int(ctx.guild.bitrate_limit or source_channel.bitrate or 64000),
                                ),
                                user_limit=int(source_channel.user_limit or 0),
                                reason=reason,
                            )
                            created_channels += 1
                        elif isinstance(source_channel, discord.StageChannel):
                            await ctx.guild.create_stage_channel(
                                name=str(source_channel.name or "stage-channel")[:100],
                                category=destination_category,
                                overwrites=overwrites,
                                bitrate=min(
                                    int(source_channel.bitrate or 64000),
                                    int(ctx.guild.bitrate_limit or source_channel.bitrate or 64000),
                                ),
                                user_limit=int(source_channel.user_limit or 0),
                                reason=reason,
                            )
                            created_channels += 1
                        elif hasattr(discord, "ForumChannel") and isinstance(source_channel, discord.ForumChannel):
                            create_forum = getattr(ctx.guild, "create_forum", None)
                            if create_forum is None:
                                skipped_channels += 1
                            else:
                                await create_forum(
                                    name=str(source_channel.name or "forum-channel")[:100],
                                    category=destination_category,
                                    overwrites=overwrites,
                                    topic=str(getattr(source_channel, "topic", "") or ""),
                                    nsfw=source_channel.nsfw,
                                    reason=reason,
                                )
                                created_channels += 1
                        else:
                            skipped_channels += 1
                    except Exception:
                        failed_channels += 1

            plan_label_map = {
                "free": "Free",
                "silver": "Silver",
                "golden": "Golden",
                "diamond": "Diamond",
                "permanent": "Permanent",
            }
            embed = discord.Embed(
                title="ผลลัพธ์การโคลนเซิร์ฟเวอร์",
                color=(color.green if (created_roles + created_channels) > 0 else color.orange),
            )
            embed.add_field(
                name="Source Guild",
                value=f"{source_guild.name} (`{source_guild.id}`)",
                inline=False,
            )
            embed.add_field(
                name="Plan",
                value=f"{plan_label_map.get(plan_tier, 'Free')} ({self._clone_limit_text(plan_limit)})",
                inline=True,
            )
            embed.add_field(name="Limit", value=str(requested), inline=True)
            embed.add_field(name="Roles Created", value=str(created_roles), inline=True)
            embed.add_field(name="Roles Skipped", value=str(skipped_roles), inline=True)
            embed.add_field(name="Roles Failed", value=str(failed_roles), inline=True)
            embed.add_field(name="Categories Created", value=str(created_categories), inline=True)
            embed.add_field(name="Channels Created", value=str(created_channels), inline=True)
            embed.add_field(name="Channels Skipped", value=str(skipped_channels), inline=True)
            embed.add_field(name="Channels Failed", value=str(failed_channels), inline=True)
            await ctx.send(embed=embed)
        except Exception:
            logger.error(f"Error in clone server command: {traceback.format_exc()}")
            await ctx.send(
                embed=discord.Embed(
                    description="เกิดข้อผิดพลาดระหว่างโคลนเซิร์ฟเวอร์",
                    color=color.red,
                )
            )

    @commands.hybrid_command(
        name="botinfo",
        with_app_command=True,
        help="ดูข้อมูลบอทและทีมพัฒนา",
        usage="bot/dev/website",
    )
    @app_commands.describe(mode="เลือกโหมดบอทหรือผู้พัฒนา")
    @app_commands.autocomplete(mode=_botinfo_mode_autocomplete)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def botinfo(self, ctx: commands.Context, mode: str | None = None):
        try:
            await self._safe_defer(ctx)
            guild_id = getattr(getattr(ctx, "guild", None), "id", None)
            is_th = i18n.guild_lang(guild_id) == "th" if guild_id else False
            prefix = self.bot.BotConfig.PREFIX
            selected_mode = str(mode or "").strip().lower()
            if selected_mode not in {"bot", "dev", "website"}:
                embed = discord.Embed(
                    title=("เมนูข้อมูลบอท" if is_th else "Bot Info Menu"),
                    description=(
                        f"ใช้คำสั่ง `{prefix}botinfo bot` หรือ `/botinfo mode:bot` เพื่อดูข้อมูลบอท\n"
                        f"ใช้คำสั่ง `{prefix}botinfo dev` หรือ `/botinfo mode:dev` เพื่อดูข้อมูลทีมพัฒนา"
                        f"\nUse `{prefix}botinfo website` or `/botinfo mode:website`"
                        if is_th
                        else f"Use `{prefix}botinfo bot` or `/botinfo mode:bot` to view bot details\n"
                        f"Use `{prefix}botinfo dev` or `/botinfo mode:dev` to view developer details"
                        f"\nUse `{prefix}botinfo website` or `/botinfo mode:website` to view website links"
                    ),
                    color=color.blue,
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                return await ctx.send(embed=embed, view=self._botinfo_links_view(guild_id))

            if selected_mode == "bot":
                total_users = sum(int(guild.member_count or 0) for guild in self.bot.guilds)
                embed = discord.Embed(
                    title=("ข้อมูลบอท" if is_th else "Bot Information"),
                    color=color.green,
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )
                embed.add_field(
                    name=("ชื่อบอท" if is_th else "Bot Name"),
                    value=f"`{self.bot.user.display_name}`",
                    inline=True,
                )
                embed.add_field(
                    name=("ไอดีบอท" if is_th else "Bot ID"),
                    value=f"`{self.bot.user.id}`",
                    inline=True,
                )
                embed.add_field(
                    name=("คำสั่งทั้งหมด" if is_th else "Total Commands"),
                    value=f"`{sum(len(cog.get_commands()) for cog in self.bot.cogs.values())}`",
                    inline=True,
                )
                embed.add_field(
                    name=("เซิร์ฟเวอร์" if is_th else "Guilds"),
                    value=f"`{len(self.bot.guilds)}`",
                    inline=True,
                )
                embed.add_field(
                    name=("ผู้ใช้รวม" if is_th else "Users"),
                    value=f"`{total_users}`",
                    inline=True,
                )
                embed.add_field(
                    name=("จำนวนชาร์ด" if is_th else "Shards"),
                    value=f"`{self.bot.shard_count}`",
                    inline=True,
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                embed.set_footer(
                    text=("เรียกโดย {0}".format(ctx.author) if is_th else f"Requested by {ctx.author}"),
                    icon_url=ctx.author.display_avatar.url,
                )
                return await ctx.send(embed=embed, view=self._botinfo_links_view(guild_id))

            if selected_mode == "website":
                website_url, service_status_url, bot_status_url = self._build_botinfo_status_urls()
                bot_invite_url = str(getattr(getattr(self.bot, "urls", None), "INVITE", "") or "").strip()
                service_probe, bot_probe = await asyncio.gather(
                    self._probe_botinfo_status_url(service_status_url),
                    self._probe_botinfo_status_url(bot_status_url),
                )

                embed = discord.Embed(
                    title=("สถานะเว็บไซต์ SkylineBOT" if is_th else "SkylineBOT Website Status"),
                    description=(
                        "สถานะเว็บไซต์ 2 จุด (Service และ Bot Dashboard)"
                        if is_th
                        else "Two website status checkpoints (Service and Bot Dashboard)"
                    ),
                    color=color.green,
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )
                if website_url:
                    embed.add_field(
                        name=("เว็บไซต์หลัก" if is_th else "Main Website"),
                        value=website_url,
                        inline=False,
                    )
                embed.add_field(
                    name=("สถานะบริการเว็บไซต์" if is_th else "Website Service Status"),
                    value=self._format_botinfo_status_value(
                        url=service_status_url,
                        probe=service_probe,
                        is_th=is_th,
                    ),
                    inline=False,
                )
                embed.add_field(
                    name=("สถานะแดชบอร์ดบอท" if is_th else "Bot Dashboard Status"),
                    value=self._format_botinfo_status_value(
                        url=bot_status_url,
                        probe=bot_probe,
                        is_th=is_th,
                    ),
                    inline=False,
                )
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                embed.set_footer(
                    text=(
                        f"เรียกโดย {ctx.author}"
                        if is_th
                        else f"Requested by {ctx.author}"
                    ),
                    icon_url=ctx.author.display_avatar.url,
                )

                view = self._botinfo_website_links_view(
                    guild_id,
                    service_status_url=service_status_url,
                    bot_status_url=bot_status_url,
                    bot_invite_url=bot_invite_url,
                )
                return await ctx.send(embed=embed, view=view)

            developers = list(getattr(self.bot, "developers", []) or [])
            if not developers:
                fallback_dev = getattr(self.bot, "developer", None)
                if fallback_dev:
                    developers = [fallback_dev]

            embed = discord.Embed(
                title=("ข้อมูลทีมพัฒนา" if is_th else "Developer Information"),
                description=(
                    "รายชื่อทีมพัฒนาที่ดูแล SkylineBOT"
                    if is_th
                    else "Authorized developers maintaining SkylineBOT"
                ),
                color=color.blue,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            if developers:
                lines = [
                    f"{index}. {dev.mention} (`{dev.id}`)"
                    for index, dev in enumerate(developers, start=1)
                ]
                embed.add_field(
                    name=("ทีมพัฒนา" if is_th else "Developers"),
                    value="\n".join(lines),
                    inline=False,
                )
            else:
                embed.add_field(
                    name=("ทีมพัฒนา" if is_th else "Developers"),
                    value=("ไม่พบข้อมูลทีมพัฒนา" if is_th else "No developer data found."),
                    inline=False,
                )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(
                text=("เรียกโดย {0}".format(ctx.author) if is_th else f"Requested by {ctx.author}"),
                icon_url=ctx.author.display_avatar.url,
            )
            await ctx.send(embed=embed, view=self._botinfo_links_view(guild_id))
        except Exception as e:
            logger.error(
                f"Commmand: botinfo, Message: {getattr(getattr(ctx, 'message', None), 'content', '')}, ข้อผิดพลาด: {e}"
            )
            await ctx.send("An error occurred while processing botinfo.", delete_after=10)

    @commands.command(
        name="steal", help="ใช้เพื่อคัดลอกอีโมจิ/หลายอีโมจิจากเซิร์ฟเวอร์"
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=10, type=commands.BucketType.user)
    async def steal_command(self, ctx: commands.Context, *emojis: discord.PartialEmoji):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_emojis"):

                return await ctx.send(
                    embed=discord.Embed(
                        description="คุณต้องมีสิทธิ์จัดการอีโมจิเพื่อใช้คำสั่งนี้",
                        color=color.red,
                    ),
                    delete_after=10,
                )

            if not emojis:

                # check if the command is replied to a message

                replied_message = ctx.message.reference

                if not replied_message:

                    return await ctx.send(
                        embed=discord.Embed(
                            description="กรุณาระบุอีโมจิที่ต้องการเพิ่ม or Reply To A Message With Custom Stickers",
                            color=color.red,
                        ),
                        delete_after=10,
                    )

                reply_message = await ctx.channel.fetch_message(
                    replied_message.message_id
                )

                if not reply_message:

                    return await ctx.send(
                        embed=discord.Embed(
                            description="กรุณาระบุอีโมจิที่ต้องการเพิ่ม or Reply To A Message With Custom Stickers",
                            color=color.red,
                        ),
                        delete_after=10,
                    )

                stickers = reply_message.stickers

                if not stickers:

                    # try to get the emojis from the message

                    raw_emojis = re.findall(r"<a?:\w+:\d+>", reply_message.content)

                    stickers = []

                    for raw_emoji in raw_emojis:

                        try:

                            # also get those emojis which the bot can't see

                            # emoji = self.bot.get_emoji(int(raw_emoji.split(":")[-1].replace(">","")))

                            emoji = await commands.PartialEmojiConverter().convert(
                                ctx, raw_emoji
                            )

                            if emoji:

                                stickers.append(emoji)

                        except Exception as e:

                            logger.error(
                                f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}"
                            )

                            logger.warning(
                                f"Failed To Convert Emoji {raw_emoji} ข้อผิดพลาด: {e}"
                            )

                    if not stickers:

                        return await ctx.send(
                            embed=discord.Embed(
                                description="กรุณาระบุอีโมจิที่ต้องการเพิ่ม or Reply To A Message With Custom Stickers",
                                color=color.red,
                            ),
                            delete_after=10,
                        )

                # check if the guild have enough space to add the emojis

                # guild_stickers = await ctx.guild.fetch_stickers()

                # sticket_limit = ctx.guild.sticker_limit

                view_timeout_time = 60

                cancled = False

                added = False

                added_title = None

                async def get_embed():

                    sticker = stickers[current_page_index]

                    embed = discord.Embed(
                        title="Add as Emoji or Sticker" if not added else added_title,
                        color=color.green,
                    )

                    embed.set_image(url=sticker.url)

                    embed.set_footer(
                        text=f"{current_page_index+1}/{len(stickers)} Stickers",
                        icon_url=ctx.bot.user.display_avatar.url,
                    )

                    return embed

                current_page_index = 0

                async def get_view(disabled=False):

                    view = discord.ui.View(timeout=60)

                    previous_button = discord.ui.Button(
                        style=discord.ButtonStyle.blurple,
                        label="หน้าก่อนหน้า",
                        row=1,
                        disabled=current_page_index <= 0,
                    )

                    previous_button.callback = lambda i: previous_button_callback(i)

                    stop_button = discord.ui.Button(
                        style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=1
                    )

                    stop_button.callback = lambda i: stop_button_callback(i)

                    next_button = discord.ui.Button(
                        style=discord.ButtonStyle.blurple,
                        label="หน้าถัดไป",
                        row=1,
                        disabled=current_page_index >= len(stickers) - 1,
                    )

                    next_button.callback = lambda i: next_button_callback(i)

                    add_as_emoji_button = discord.ui.Button(
                        label="เพิ่มเป็นอีโมจิ ✨", style=discord.ButtonStyle.green, row=0
                    )

                    add_as_emoji_button.callback = (
                        lambda i: add_as_emoji_button_callback(i)
                    )

                    add_as_sticker_button = discord.ui.Button(
                        label="เพิ่มเป็นสติกเกอร์ ✨", style=discord.ButtonStyle.green, row=0
                    )

                    add_as_sticker_button.callback = (
                        lambda i: add_as_sticker_button_callback(i)
                    )

                    if not added:

                        view.add_item(add_as_emoji_button)

                        view.add_item(add_as_sticker_button)

                    if len(stickers) > 1:

                        view.add_item(previous_button)

                        # view.add_item(stop_button)

                        view.add_item(next_button)

                    if disabled:

                        for item in view.children:

                            item.disabled = True

                    return view

                async def previous_button_callback(interaction: discord.Interaction):

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                async def stop_button_callback(interaction: discord.Interaction):

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                async def next_button_callback(interaction: discord.Interaction):

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                async def add_as_emoji_button_callback(
                    interaction: discord.Interaction,
                ):

                    try:

                        if interaction.user.id != ctx.author.id:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        await interaction.response.edit_message(
                            embed=discord.Embed(
                                title=None,
                                description="กำลังเพิ่มเป็นอีโมจิ",
                                color=color.green,
                            ),
                            view=None,
                        )

                        added_emojis = []

                        failed_emojis = []

                        for sticker in stickers:

                            try:

                                added_emoji = await ctx.guild.create_custom_emoji(
                                    name=sticker.name.strip("_"),
                                    image=await sticker.read(),
                                    reason=f"Emoji Added By {ctx.author.name}",
                                )

                                added_emojis.append(added_emoji)

                            except Exception as e:

                                failed_emojis.append(sticker)

                                logger.error(
                                    f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}"
                                )

                                logger.warning(
                                    f"Falied To Add Emoji {sticker.name} To The Server {ctx.guild.name} By {ctx.author.name} ข้อผิดพลาด: {e}"
                                )

                        nonlocal added, added_title

                        added = True

                        added_title = f"{self.bot.emoji.SUCCESS} - Emojis Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60,
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                async def add_as_sticker_button_callback(
                    interaction: discord.Interaction,
                ):

                    try:

                        if interaction.user.id != ctx.author.id:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        await interaction.response.edit_message(
                            embed=discord.Embed(
                                title=None,
                                description="กำลังเพิ่มเป็นสติกเกอร์",
                                color=color.green,
                            ),
                            view=None,
                        )

                        added_stickers = []

                        failed_stickers = []

                        for sticker in stickers:

                            try:

                                image_bytes = await sticker.read()

                                # Creating a discord.File from the bytes

                                image_file = discord.File(
                                    io.BytesIO(image_bytes),
                                    filename=f"{sticker.name}.{'png'}",
                                )

                                added_sticker = await ctx.guild.create_sticker(
                                    name=sticker.name,
                                    emoji="🤖",
                                    description=f"Sticker Added By {ctx.author.name}",
                                    reason=f"Sticker Added By {ctx.author.name}",
                                    file=image_file,
                                )

                                added_stickers.append(added_sticker)

                            except Exception as e:

                                failed_stickers.append(sticker)

                                logger.warning(
                                    f"Falied To Add Sticker {sticker.name} To The Server {ctx.guild.name} By {ctx.author.name} ข้อผิดพลาด: {e}"
                                )

                        nonlocal added, added_title

                        added = True

                        added_title = f"{self.bot.emoji.SUCCESS} - Stickers Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60,
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                message = await ctx.send(embed=await get_embed(), view=await get_view())

                while not cancled:

                    view_timeout_time -= 1

                    if view_timeout_time <= 0:

                        await message.edit(view=await get_view(True))

                        break

                    await asyncio.sleep(1)

            else:

                for emoji in emojis:

                    if not emoji.is_custom_emoji():

                        return await ctx.send(
                            embed=discord.Embed(
                                description="กรุณาระบุอีโมจิที่ต้องการเพิ่ม",
                                color=color.red,
                            ),
                            delete_after=10,
                        )

                view_timeout_time = 60

                cancled = False

                added = False

                added_title = None

                async def get_embed():

                    emoji = emojis[current_page_index]

                    embed = discord.Embed(
                        title="Add as Emoji or Sticker" if not added else added_title,
                        color=color.green,
                    )

                    embed.set_image(url=emoji.url)

                    embed.set_footer(
                        text=f"{current_page_index+1}/{len(emojis)} Emojis",
                        icon_url=ctx.bot.user.display_avatar.url,
                    )

                    return embed

                current_page_index = 0

                async def get_view(disabled=False):

                    view = discord.ui.View(timeout=65)

                    previous_button = discord.ui.Button(
                        style=discord.ButtonStyle.blurple,
                        label="หน้าก่อนหน้า",
                        row=1,
                        disabled=current_page_index <= 0,
                    )

                    previous_button.callback = lambda i: previous_button_callback(i)

                    stop_button = discord.ui.Button(
                        style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=1
                    )

                    stop_button.callback = lambda i: stop_button_callback(i)

                    next_button = discord.ui.Button(
                        style=discord.ButtonStyle.blurple,
                        label="หน้าถัดไป",
                        row=1,
                        disabled=current_page_index >= len(emojis) - 1,
                    )

                    next_button.callback = lambda i: next_button_callback(i)

                    add_as_emoji_button = discord.ui.Button(
                        label="เพิ่มเป็นอีโมจิ ✨", style=discord.ButtonStyle.green, row=0
                    )

                    add_as_emoji_button.callback = (
                        lambda i: add_as_emoji_button_callback(i)
                    )

                    add_as_sticker_button = discord.ui.Button(
                        label="เพิ่มเป็นสติกเกอร์ ✨", style=discord.ButtonStyle.green, row=0
                    )

                    add_as_sticker_button.callback = (
                        lambda i: add_as_sticker_button_callback(i)
                    )

                    if not added:

                        view.add_item(add_as_emoji_button)

                        view.add_item(add_as_sticker_button)

                    if len(emojis) > 1:

                        view.add_item(previous_button)

                        # view.add_item(stop_button)

                        view.add_item(next_button)

                    if disabled:

                        for item in view.children:

                            item.disabled = True

                    return view

                async def previous_button_callback(interaction: discord.Interaction):

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                async def stop_button_callback(interaction: discord.Interaction):

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                async def next_button_callback(interaction: discord.Interaction):

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                async def add_as_emoji_button_callback(
                    interaction: discord.Interaction,
                ):

                    try:

                        if interaction.user.id != ctx.author.id:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        await interaction.response.edit_message(
                            embed=discord.Embed(
                                title=None,
                                description="กำลังเพิ่มเป็นอีโมจิ",
                                color=color.green,
                            ),
                            view=None,
                        )

                        added_emojis = []

                        failed_emojis = []

                        for emoji in emojis:

                            try:

                                added_emoji = await ctx.guild.create_custom_emoji(
                                    name=emoji.name,
                                    image=await emoji.read(),
                                    reason=f"Emoji Added By {ctx.author.name}",
                                )

                                added_emojis.append(added_emoji)

                            except Exception as e:

                                failed_emojis.append(emoji)

                                logger.warning(
                                    f"Falied To Add Emoji {emoji.name} To The Server {ctx.guild.name} By {ctx.author.name} ข้อผิดพลาด: {e}"
                                )

                        nonlocal added, added_title

                        added = True

                        added_title = f"{self.bot.emoji.SUCCESS} - Emojis Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60,
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                async def add_as_sticker_button_callback(
                    interaction: discord.Interaction,
                ):

                    try:

                        if interaction.user.id != ctx.author.id:

                            return await interaction.response.send_message(
                                embed=discord.Embed(
                                    description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                    color=color.red,
                                ),
                                ephemeral=True,
                                delete_after=10,
                            )

                        await interaction.response.edit_message(
                            embed=discord.Embed(
                                title=None,
                                description="กำลังเพิ่มเป็นสติกเกอร์",
                                color=color.green,
                            ),
                            view=None,
                        )

                        added_stickers = []

                        failed_stickers = []

                        for emoji in emojis:

                            try:

                                image_bytes = await emoji.read()

                                # Creating a discord.File from the bytes

                                image_file = discord.File(
                                    io.BytesIO(image_bytes),
                                    filename=f"{emoji.name}.{'gif' if emoji.animated else 'png'}",
                                )

                                added_sticker = await ctx.guild.create_sticker(
                                    name=emoji.name,
                                    emoji="🤖",
                                    description=f"Sticker Added By {ctx.author.name}",
                                    reason=f"Sticker Added By {ctx.author.name}",
                                    file=image_file,
                                )

                                added_stickers.append(added_sticker)

                            except Exception as e:

                                failed_stickers.append(emoji)

                                logger.warning(
                                    f"Falied To Add Sticker {emoji.name} To The Server {ctx.guild.name} By {ctx.author.name} ข้อผิดพลาด: {e}"
                                )

                        nonlocal added, added_title

                        added = True

                        added_title = f"{self.bot.emoji.SUCCESS} - Stickers Added"

                        await interaction.message.edit(
                            embed=await get_embed(),
                            view=await get_view(),
                            delete_after=60,
                        )

                    except Exception as e:

                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                message = await ctx.send(embed=await get_embed(), view=await get_view())

                while not cancled:

                    view_timeout_time -= 1

                    if view_timeout_time <= 0:

                        await message.edit(view=await get_view(True))

                        break

                    await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_command(
        name="noprefix",
        with_app_command=True,
        help="เปิด/ปิดฟีเจอร์ไม่ต้องใช้พรีฟิกซ์",
        aliases=["np"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def noprefix_command(self, ctx: commands.Context):

        try:

            async def get_embed():

                users_cache = cache.users.get(str(ctx.author.id), {})

                embed = discord.Embed(
                    title="ไม่มีคุณลักษณะคำนำหน้า",
                    color=color.green if users_cache.get("no_prefix") else color.red,
                )

                embed.description = f"**__Status:__** {self.bot.emoji.ENABLED if users_cache.get('no_prefix') else self.bot.emoji.DISABLED}"

                embed.description += f"\n**__Subscription:__** {self.bot.emoji.ENABLED if users_cache.get('no_prefix_subscription') else self.bot.emoji.DISABLED}"

                if users_cache.get("no_prefix_subscription"):

                    subscription_end = users_cache.get("no_prefix_end")

                    subscription_end_text = (
                        f"<t:{int(subscription_end.timestamp())}:R>"
                        if subscription_end
                        else "`Never`"
                    )

                    embed.description += (
                        f"\n**__Subscription Ends:__** {subscription_end_text}"
                    )

                embed.set_thumbnail(url=ctx.author.display_avatar.url)

                return embed

            timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal timeout_time

                timeout_time = timeout

            async def get_view(disabled=False):

                users_cache = cache.users.get(str(ctx.author.id), {})

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                enable_disable_button = discord.ui.Button(
                    label=(
                        "Enable No Prefix"
                        if not users_cache.get("no_prefix")
                        else "Disable No Prefix"
                    ),
                    style=(
                        discord.ButtonStyle.green
                        if not users_cache.get("no_prefix")
                        else discord.ButtonStyle.gray
                    ),
                    row=0,
                    emoji=(
                        self.bot.emoji.ENABLED
                        if not users_cache.get("no_prefix")
                        else self.bot.emoji.DISABLED
                    ),
                )

                enable_disable_button.callback = (
                    lambda i: enable_disable_button_callback(i)
                )

                enable_disable_subscription_button = discord.ui.Button(
                    label="Upgrade for No Prefix",
                    style=discord.ButtonStyle.link,
                    url=self.bot.urls.SUPPORT_SERVER,
                    row=0,
                    emoji=self.bot.emoji.SUPPORT,
                )

                cancle_button = discord.ui.Button(
                    label="ปิดเมนู",
                    style=discord.ButtonStyle.gray,
                    row=0,
                    emoji=self.bot.emoji.CANCLED,
                )

                cancle_button.callback = lambda i: cancle_button_callback(i)

                if users_cache.get("no_prefix_subscription", False):

                    view.add_item(enable_disable_button)

                    view.add_item(cancle_button)

                else:

                    view.add_item(enable_disable_subscription_button)

                    nonlocal cancled

                    cancled = True

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def enable_disable_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.defer()

                    users_cache = cache.users.get(str(ctx.author.id), {})

                    await storage.users.update(
                        id=users_cache.get("id"),
                        user_id=ctx.author.id,
                        no_prefix=not users_cache.get("no_prefix"),
                    )

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_command(
        name="afk",
        with_app_command=True,
        help="ตั้งค่าสถานะไม่อยู่ของคุณ",
        aliases=["away"],
        usage="<1m/1h/1d> <reason(OPTIONAL)>",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def afk_command(
        self, ctx: commands.Context, time: str = None, *, reason: str = None
    ):

        try:

            if time:

                time = time.lower()

                try:

                    if time.endswith("m"):

                        time = int(time[:-1]) * 60

                    elif time.endswith("h"):

                        time = int(time[:-1]) * 60 * 60

                    elif time.endswith("d"):

                        time = int(time[:-1]) * 60 * 60 * 24

                    elif time.endswith("s"):

                        time = int(time[:-1])

                    else:

                        time = int(time)

                except Exception:
                    reason = f"{time} {reason if reason else ''}"

                    time = None

            else:

                time = None

            if not reason:

                reason = "No Reason Provided"

            # by using re check the reason if it contains any mentions or urls

            if re.search(r"<@!?\d{17,19}>", reason) or re.search(
                r"https?://(?:www\.)?.+", reason
            ):

                return await ctx.send(
                    embed=discord.Embed(
                        description="คุณไม่สามารถตั้ง AFK โดยมีการเมนชันหรือลิงก์ในเหตุผลได้",
                        color=color.red,
                    ),
                    delete_after=10,
                )

            embed = discord.Embed(
                title="เลือกประเภท AFK",
                description=f"**__Afk Ends__** : {f'<t:{int(datetime.datetime.now().timestamp()+time)}:F>' if time else '`Never`'}\n**__Reason__** : {reason}",
                color=color.green,
            )

            cancled = False

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                guild_afk = (
                    cache.afk.get("guilds", {})
                    .get(str(ctx.guild.id), {})
                    .get(str(ctx.author.id), {})
                )

                global_afk = cache.afk.get("global", {}).get(str(ctx.author.id), {})

                guild_afk_button = discord.ui.Button(
                    label="โหมด AFK ในเซิร์ฟเวอร์",
                    style=discord.ButtonStyle.green,
                    row=0,
                    disabled=guild_afk.get("afk", False),
                )

                guild_afk_button.callback = lambda i: guild_afk_button_callback(i)

                global_afk_button = discord.ui.Button(
                    label="โหมด AFK ทั่วระบบ",
                    style=discord.ButtonStyle.green,
                    row=0,
                    disabled=global_afk.get("afk", False),
                )

                global_afk_button.callback = lambda i: global_afk_button_callback(i)

                cancle_button = discord.ui.Button(
                    label="ปิดเมนู", style=discord.ButtonStyle.gray, row=1
                )

                cancle_button.callback = lambda i: cancle_button_callback(i)

                view.add_item(guild_afk_button)

                view.add_item(global_afk_button)

                # view.add_item(cancle_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def guild_afk_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            description="กำลังตั้งค่า AFK ในเซิร์ฟเวอร์", color=color.green
                        ),
                        view=None,
                    )

                    nonlocal cancled

                    cancled = True

                    await storage.afk.delete(user_id=ctx.author.id)

                    data = await storage.afk.insert(
                        user_id=ctx.author.id,
                        guild_id=ctx.guild.id,
                        afk=True,
                        reason=reason,
                        afk_end=(
                            (
                                datetime.datetime.now(tz=datetime.timezone.utc)
                                + datetime.timedelta(seconds=time)
                            ).isoformat()
                            if time
                            else None
                        ),
                        created_at=datetime.datetime.now(
                            tz=datetime.timezone.utc
                        ).isoformat(),
                    )

                    try:

                        asyncio.create_task(afk_delay(self.bot, data))

                    except Exception:
                        pass

                    afk_end_text = (
                        f" and will end at <t:{int(datetime.datetime.now().timestamp()+time)}:F>"
                        if time
                        else "."
                    )

                    await interaction.message.edit(
                        embed=discord.Embed(
                            description=f"{self.bot.emoji.SUCCESS} - Guild AFK Set{afk_end_text}",
                            color=color.green,
                        ),
                        view=None,
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def global_afk_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            description="กำลังตั้งค่า AFK ทั่วระบบ", color=color.green
                        ),
                        view=None,
                    )

                    nonlocal cancled

                    cancled = True

                    await storage.afk.delete(user_id=ctx.author.id)

                    data = await storage.afk.insert(
                        user_id=ctx.author.id,
                        guild_id=None,
                        afk=True,
                        reason=reason,
                        afk_end=(
                            (
                                datetime.datetime.now(tz=datetime.timezone.utc)
                                + datetime.timedelta(seconds=time)
                            ).isoformat()
                            if time
                            else None
                        ),
                        created_at=datetime.datetime.now(
                            tz=datetime.timezone.utc
                        ).isoformat(),
                    )

                    try:

                        asyncio.create_task(afk_delay(self.bot, data))

                    except Exception:
                        pass

                    await interaction.message.edit(
                        embed=discord.Embed(
                            description=f"{self.bot.emoji.SUCCESS} - Global AFK Set{f' and Will End At <t:{int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp()+time)}:F>' if time else '.'}",
                            color=color.green,
                        ),
                        view=None,
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=embed, view=await get_view())

            await asyncio.sleep(60)

            if not cancled:

                await message.edit(view=await get_view(True))

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_command(
        name="prefix",
        help="เปลี่ยนพรีฟิกซ์บอทหรือดูพรีฟิกซ์ปัจจุบัน",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def prefix(self, ctx: commands.Context, new_prefix: str = None):

        if (
            not await checks.check_is_moderator_permissions(ctx, "manage_guild")
            and not checks.check_is_admin_predicate(ctx)
            and not await checks.check_is_owner(ctx)
            and new_prefix
        ):

            embed = discord.Embed(
                title="ข้อผิดพลาด",
                description="คุณไม่มีสิทธิ์เปลี่ยน Prefix\n**__สิทธิ์ที่ต้องมี:__** `Manage Server`",
                color=color.red,
            )

            embed.set_footer(
                text=f"Requested by {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed, delete_after=5)

            return

        if new_prefix:

            if len(new_prefix) > 10:

                embed = discord.Embed(
                    title="ข้อผิดพลาด",
                    description="Prefix ต้องไม่เกิน 10 ตัวอักษร",
                    color=color.red,
                )

                embed.set_footer(
                    text=f"Requested by {ctx.author.name}",
                    icon_url=ctx.author.display_avatar.url,
                )

                await ctx.send(embed=embed, delete_after=5)

                return

            cache_data = cache.guilds.get(str(ctx.guild.id))

            if not cache_data:

                await storage.guilds.insert(guild_id=ctx.guild.id)

                cache_data = cache.guilds.get(str(ctx.guild.id))

            if new_prefix.lower() == cache_data.get("prefix"):

                embed = discord.Embed(
                    description=f"ตั้งค่า Prefix นี้ไว้อยู่แล้ว: `{new_prefix}`. Try a different prefix.",
                    color=color.red,
                )

                await ctx.send(embed=embed, delete_after=5)

                return

            await storage.guilds.update(id=cache_data.get("id"), prefix=new_prefix)

            embed = discord.Embed(
                description=f"**__Prefix changed to__** `{new_prefix}`",
                color=color.green,
            )

            await ctx.send(embed=embed)

        else:

            cache_data = cache.guilds.get(str(ctx.guild.id))

            if not cache_data:

                await storage.guilds.insert(guild_id=ctx.guild.id)

            embed = discord.Embed(
                description=f"**__Current Prefix:__** `{cache_data.get('prefix')}`",
                color=color.green,
            )

            await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="language",
        help="Change the bot's primary server language or view current language (เปลี่ยนภาษาหลักของบอทในเซิร์ฟเวอร์ หรือดูภาษาปัจจุบัน)",
        with_app_command=True,
        aliases=["lang"],
    )
    @app_commands.describe(new_language="ภาษาที่ต้องการ: th หรือ en")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def language(self, ctx: commands.Context, new_language: str = None):
        if not getattr(ctx, "guild", None):
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น", delete_after=8)
            return

        if (
            new_language
            and not await checks.check_is_moderator_permissions(ctx, "manage_guild")
            and not checks.check_is_admin_predicate(ctx)
            and not await checks.check_is_owner(ctx)
        ):
            embed = discord.Embed(
                title="ข้อผิดพลาด",
                description="คุณไม่มีสิทธิ์เปลี่ยนภาษา\n**__สิทธิ์ที่ต้องมี:__** `Manage Server`",
                color=color.red,
            )
            embed.set_footer(
                text=f"Requested by {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )
            await ctx.send(embed=embed, delete_after=5)
            return

        cache_data = cache.guilds.get(str(ctx.guild.id))
        if not cache_data:
            await storage.guilds.insert(guild_id=ctx.guild.id)
            cache_data = cache.guilds.get(str(ctx.guild.id)) or {}

        current_language = str(cache_data.get("language") or "th").strip().lower()
        if current_language not in {"th", "en"}:
            current_language = "th"

        language_label = {"th": "ภาษาไทย (TH)", "en": "English (EN)"}

        if not new_language:
            embed = discord.Embed(
                description=f"**__Current Language:__** `{language_label[current_language]}`",
                color=color.green,
            )
            await ctx.send(embed=embed)
            return

        raw = str(new_language or "").strip().lower()
        normalized_language = {
            "th": "th",
            "thai": "th",
            "ภาษาไทย": "th",
            "ไทย": "th",
            "en": "en",
            "eng": "en",
            "english": "en",
            "ภาษาอังกฤษ": "en",
            "อังกฤษ": "en",
        }.get(raw)

        if normalized_language is None:
            embed = discord.Embed(
                description="รูปแบบภาษาไม่ถูกต้อง ใช้ได้เฉพาะ `th` หรือ `en`",
                color=color.red,
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if normalized_language == current_language:
            embed = discord.Embed(
                description=f"ตั้งค่าภาษานี้ไว้อยู่แล้ว: `{language_label[normalized_language]}`",
                color=color.red,
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        await storage.guilds.update(id=cache_data.get("id"), language=normalized_language)
        if isinstance(cache_data, dict):
            cache_data["language"] = normalized_language

        embed = discord.Embed(
            description=f"**__Language changed to__** `{language_label[normalized_language]}`",
            color=color.green,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="richpresence",
        help="Set bot Rich Presence mode: off, voice, or always (ตั้งค่า Rich Presence ของบอท)",
        with_app_command=True,
        aliases=["rpmode", "presencemode"],
    )
    @app_commands.describe(
        mode="Mode: off | voice | always",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="off", value="off"),
            app_commands.Choice(name="voice", value="voice"),
            app_commands.Choice(name="always", value="always"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.user)
    async def richpresence(self, ctx: commands.Context, mode: str = ""):
        if not await checks.check_is_owner(ctx):
            await ctx.send("คำสั่งนี้สำหรับเจ้าของบอทเท่านั้น", delete_after=8)
            return

        requested_mode = str(mode or "").strip().lower()
        mode_aliases = {
            "off": "off",
            "disable": "off",
            "disabled": "off",
            "ปิด": "off",
            "voice": "voice",
            "vc": "voice",
            "samevoice": "voice",
            "ห้องเสียง": "voice",
            "always": "always",
            "on": "always",
            "enable": "always",
            "เปิดตลอด": "always",
        }
        normalized_mode = mode_aliases.get(requested_mode, "")

        if not hasattr(self.bot, "_load_ownerbot_runtime_settings"):
            await ctx.send("Runtime settings ไม่พร้อมใช้งานในตอนนี้", delete_after=8)
            return

        current_settings = await self.bot._load_ownerbot_runtime_settings(force=True)
        if not isinstance(current_settings, dict):
            current_settings = {}
        current_mode = str(current_settings.get("rich_presence_mode") or "off").strip().lower()
        if current_mode not in {"off", "voice", "always"}:
            current_mode = "off"

        if not normalized_mode:
            mode_label = {
                "off": "ปิด",
                "voice": "เปิดเมื่อมีผู้ใช้อยู่ห้องเสียงเดียวกับบอท",
                "always": "เปิดตลอดเวลา",
            }.get(current_mode, "ปิด")
            await ctx.send(
                embed=discord.Embed(
                    title="Rich Presence Mode",
                    description=(
                        f"โหมดปัจจุบัน: **{mode_label}**\n\n"
                        "วิธีใช้:\n"
                        "`/richpresence mode:off`\n"
                        "`/richpresence mode:voice`\n"
                        "`/richpresence mode:always`"
                    ),
                    color=color.green,
                )
            )
            return

        if normalized_mode == current_mode:
            await ctx.send(f"Rich Presence ถูกตั้งไว้เป็น `{normalized_mode}` อยู่แล้ว", delete_after=8)
            return

        next_settings = dict(current_settings)
        next_settings["rich_presence_mode"] = normalized_mode
        payload = bot_runtime_engine._normalize_ownerbot_runtime_settings(next_settings)
        config_key = "ownerbot_runtime_settings"
        config_value = json.dumps(payload, ensure_ascii=False)
        existing = await storage.dashboard_config.get(config_key=config_key)
        if existing:
            await storage.dashboard_config.update(id=existing["id"], config_value=config_value)
        else:
            await storage.dashboard_config.insert(config_key=config_key, config_value=config_value)

        try:
            await self.bot._load_ownerbot_runtime_settings(force=True)
            presence_cog = self.bot.get_cog("ready") or self.bot.get_cog("Ready")
            if presence_cog and hasattr(presence_cog, "request_presence_refresh"):
                presence_cog.request_presence_refresh()
        except Exception:
            pass

        mode_text = {
            "off": "ปิด Rich Presence แล้ว",
            "voice": "เปิด Rich Presence เฉพาะตอนมีผู้ใช้อยู่ห้องเสียงเดียวกับบอทแล้ว",
            "always": "เปิด Rich Presence ตลอดเวลาแล้ว",
        }.get(normalized_mode, f"ตั้งค่า Rich Presence เป็น {normalized_mode} แล้ว")
        await ctx.send(embed=discord.Embed(description=mode_text, color=color.green))

    @commands.hybrid_command(
        name="relationship",
        help="ตั้งค่าสถานะความสัมพันธ์ของคุณ",
        with_app_command=True,
        aliases=["rs"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def relationship(self, ctx: commands.Context):

        try:
            if not getattr(ctx, "guild", None):
                await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น", delete_after=8)
                return

            available_relationships = {
                "single": self.bot.emoji.SINGLE,
                "married": self.bot.emoji.MARRIED,
                "engaged": self.bot.emoji.ENGAGED,
                "in_relationship": self.bot.emoji.IN_RELATIONSHIP,
                "complicated": self.bot.emoji.COMPLICATED,
            }

            async def _load_profile() -> dict[str, Any]:
                return await self._ensure_guild_user_profile(ctx.guild.id, ctx.author.id)

            async def get_embed():
                profile_row = await _load_profile()
                relationship_value = str(profile_row.get("relationship") or "single")
                spouse_id = int(profile_row.get("spouse_id") or 0)
                proposal_to_id = int(profile_row.get("proposal_to_id") or 0)
                proposal_from_id = int(profile_row.get("proposal_from_id") or 0)
                spouse_text = "None"
                if spouse_id > 0:
                    spouse_member = ctx.guild.get_member(spouse_id)
                    spouse_text = (
                        spouse_member.mention if spouse_member else f"<@{spouse_id}>"
                    )
                proposal_text = "None"
                if proposal_to_id > 0:
                    proposal_text = f"Outgoing to <@{proposal_to_id}>"
                elif proposal_from_id > 0:
                    proposal_text = f"Incoming from <@{proposal_from_id}>"

                embed = discord.Embed(
                    title="สถานะความสัมพันธ์",
                    description=(
                        f"**__Current Relationship:__** "
                        f"`{self._relationship_label(relationship_value, ctx.guild.id)}`\n"
                        f"**__Spouse:__** {spouse_text}\n"
                        f"**__Proposal:__** {proposal_text}"
                    ),
                    color=color.green,
                )

                embed.set_footer(
                    text=f"Requested by {ctx.author.name}",
                    icon_url=ctx.author.display_avatar.url,
                )

                embed.set_thumbnail(url=ctx.author.display_avatar.url)

                return embed

            timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal timeout_time

                timeout_time = timeout

            async def get_view(disabled=False):
                profile_row = await _load_profile()
                current_relationship = str(
                    profile_row.get("relationship") or "single"
                ).strip().lower()

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                select_relationship = discord.ui.Select(
                    placeholder="Select Your Relationship",
                    options=[
                        discord.SelectOption(
                            label=relationship.capitalize(),
                            value=relationship,
                            description=f"Set Your Relationship To {relationship.capitalize()}",
                            default=relationship
                            == current_relationship,
                        )
                        for relationship, emoji in available_relationships.items()
                    ],
                    row=0,
                )

                select_relationship.callback = lambda i: select_relationship_callback(i)

                view.add_item(select_relationship)

                cancle_button = discord.ui.Button(
                    label="ปิดเมนู",
                    style=discord.ButtonStyle.gray,
                    emoji=self.bot.emoji.CANCLED,
                    row=1,
                )

                cancle_button.callback = lambda i: cancle_button_callback(i)

                view.add_item(cancle_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def cancle_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def select_relationship_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.defer()

                    profile_row = await _load_profile()
                    selected_value = str(
                        ((interaction.data or {}).get("values") or ["single"])[0]
                    ).strip().lower()
                    if selected_value not in available_relationships:
                        selected_value = "single"
                    current_spouse_id = int(profile_row.get("spouse_id") or 0)
                    if selected_value == "married" and current_spouse_id <= 0:
                        await interaction.followup.send(
                            "ถ้าต้องการสถานะ `Married` กรุณาใช้คำสั่ง `/marry @user` ก่อน",
                            ephemeral=True,
                        )
                        selected_value = str(
                            profile_row.get("relationship") or "single"
                        ).strip().lower()
                    update_payload: dict[str, Any] = {
                        "id": profile_row.get("id"),
                        "guild_id": ctx.guild.id,
                        "user_id": ctx.author.id,
                        "relationship": selected_value,
                    }
                    if selected_value != "married":
                        update_payload["spouse_id"] = 0
                        update_payload["married_at"] = None

                    await storage.guild_user_profiles.update(**update_payload)

                    await interaction.message.edit(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                timeout_time -= 1

                if timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_command(
        name="marry",
        help="แต่งงานกับสมาชิกในเซิร์ฟเวอร์",
        with_app_command=True,
        aliases=["marriage"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=25, type=commands.BucketType.user)
    async def marry(self, ctx: commands.Context, member: discord.Member | None = None):
        try:
            if not getattr(ctx, "guild", None):
                await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น", delete_after=8)
                return
            if member is None:
                await ctx.send("โปรดระบุสมาชิกที่ต้องการแต่งงานด้วย เช่น `/marry @user`", delete_after=10)
                return
            if member.bot:
                await ctx.send("ไม่สามารถแต่งงานกับบอทได้", delete_after=8)
                return
            if member.id == ctx.author.id:
                await ctx.send("ไม่สามารถแต่งงานกับตัวเองได้", delete_after=8)
                return

            guild_id = ctx.guild.id
            author_row = await self._ensure_guild_user_profile(guild_id, ctx.author.id)
            target_row = await self._ensure_guild_user_profile(guild_id, member.id)

            author_spouse_id = int(author_row.get("spouse_id") or 0)
            target_spouse_id = int(target_row.get("spouse_id") or 0)
            author_relationship = str(author_row.get("relationship") or "single").lower()
            target_relationship = str(target_row.get("relationship") or "single").lower()
            author_outgoing = int(author_row.get("proposal_to_id") or 0)
            author_incoming = int(author_row.get("proposal_from_id") or 0)
            target_outgoing = int(target_row.get("proposal_to_id") or 0)
            target_incoming = int(target_row.get("proposal_from_id") or 0)

            if (
                author_relationship == "married"
                and author_spouse_id == member.id
                and target_relationship == "married"
                and target_spouse_id == ctx.author.id
            ):
                await ctx.send(f"{ctx.author.mention} กับ {member.mention} แต่งงานกันอยู่แล้ว")
                return

            if author_spouse_id > 0 and author_spouse_id != member.id:
                await ctx.send(
                    f"{ctx.author.mention} แต่งงานกับ <@{author_spouse_id}> อยู่แล้ว กรุณาหย่าก่อน",
                    delete_after=10,
                )
                return
            if target_spouse_id > 0 and target_spouse_id != ctx.author.id:
                await ctx.send(
                    f"{member.mention} แต่งงานกับ <@{target_spouse_id}> อยู่แล้ว",
                    delete_after=10,
                )
                return

            if author_outgoing == member.id and target_incoming == ctx.author.id:
                await ctx.send(
                    f"มีคำขอแต่งงานถึง {member.mention} อยู่แล้ว รอเขากด `Accept` หรือ `Reject` ได้เลย"
                )
                return

            if author_incoming == member.id and target_outgoing == ctx.author.id:
                await ctx.send(
                    f"{member.mention} ส่งคำขอแต่งงานถึงคุณไว้แล้ว ให้กด `Accept` ในข้อความคำขอเดิมได้เลย"
                )
                return

            if author_outgoing > 0:
                await ctx.send(
                    f"คุณมีคำขอแต่งงานที่ส่งอยู่แล้วถึง <@{author_outgoing}> กรุณารอให้จบก่อน",
                    delete_after=10,
                )
                return
            if author_incoming > 0:
                await ctx.send(
                    f"คุณมีคำขอแต่งงานที่รอการตอบรับจาก <@{author_incoming}> กรุณาตอบก่อน",
                    delete_after=10,
                )
                return
            if target_outgoing > 0 or target_incoming > 0:
                await ctx.send(
                    f"{member.mention} มีคำขอแต่งงานค้างอยู่แล้วตอนนี้",
                    delete_after=10,
                )
                return

            proposal_time = datetime.datetime.now(datetime.timezone.utc)
            await storage.guild_user_profiles.update(
                id=author_row.get("id"),
                guild_id=guild_id,
                user_id=ctx.author.id,
                proposal_to_id=member.id,
                proposal_at=proposal_time,
            )
            await storage.guild_user_profiles.update(
                id=target_row.get("id"),
                guild_id=guild_id,
                user_id=member.id,
                proposal_from_id=ctx.author.id,
                proposal_at=proposal_time,
            )

            class MarriageProposalView(discord.ui.View):
                def __init__(
                    self,
                    *,
                    cog: "Utils",
                    guild_id_value: int,
                    proposer_id: int,
                    target_id: int,
                    proposer_mention: str,
                    target_mention: str,
                ):
                    super().__init__(timeout=15 * 60)
                    self.cog = cog
                    self.guild_id_value = guild_id_value
                    self.proposer_id = proposer_id
                    self.target_id = target_id
                    self.proposer_mention = proposer_mention
                    self.target_mention = target_mention
                    self.message: discord.Message | None = None

                async def _disable_and_edit(
                    self,
                    *,
                    title: str,
                    description: str,
                    color_value: Any = color.green,
                ) -> None:
                    for item in self.children:
                        item.disabled = True
                    embed = discord.Embed(
                        title=title,
                        description=description,
                        color=color_value,
                    )
                    if self.message:
                        try:
                            await self.message.edit(embed=embed, view=self)
                        except Exception:
                            pass

                async def _is_pending(self) -> bool:
                    proposer = await self.cog._ensure_guild_user_profile(
                        self.guild_id_value, self.proposer_id
                    )
                    target = await self.cog._ensure_guild_user_profile(
                        self.guild_id_value, self.target_id
                    )
                    return (
                        int(proposer.get("proposal_to_id") or 0) == self.target_id
                        and int(target.get("proposal_from_id") or 0) == self.proposer_id
                    )

                async def on_timeout(self) -> None:
                    try:
                        if not await self._is_pending():
                            for item in self.children:
                                item.disabled = True
                            return
                        await self.cog._clear_proposal_pair(
                            guild_id=self.guild_id_value,
                            proposer_id=self.proposer_id,
                            target_id=self.target_id,
                        )
                        await self._disable_and_edit(
                            title="ข้อเสนอการแต่งงานหมดอายุแล้ว",
                            description=(
                                f"คำขอแต่งงานจาก {self.proposer_mention} ถึง "
                                f"{self.target_mention} หมดเวลาแล้ว"
                            ),
                            color_value=color.orange,
                        )
                    except Exception:
                        pass

                @discord.ui.button(
                    label="Accept",
                    style=discord.ButtonStyle.success,
                    emoji="💍",
                )
                async def accept_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    try:
                        if interaction.user.id != self.target_id:
                            return await interaction.response.send_message(
                                "ปุ่มนี้สำหรับผู้ที่ถูกขอแต่งงานเท่านั้น",
                                ephemeral=True,
                                delete_after=8,
                            )

                        await interaction.response.defer()
                        if not await self._is_pending():
                            await self._disable_and_edit(
                                title="การขอแต่งงานปิดแล้ว",
                                description="คำขอแต่งงานนี้ไม่อยู่ในสถานะที่ตอบกลับได้แล้ว",
                                color_value=color.orange,
                            )
                            return

                        proposer = await self.cog._ensure_guild_user_profile(
                            self.guild_id_value, self.proposer_id
                        )
                        target = await self.cog._ensure_guild_user_profile(
                            self.guild_id_value, self.target_id
                        )
                        proposer_spouse = int(proposer.get("spouse_id") or 0)
                        target_spouse = int(target.get("spouse_id") or 0)
                        if (proposer_spouse > 0 and proposer_spouse != self.target_id) or (
                            target_spouse > 0 and target_spouse != self.proposer_id
                        ):
                            await self.cog._clear_proposal_pair(
                                guild_id=self.guild_id_value,
                                proposer_id=self.proposer_id,
                                target_id=self.target_id,
                            )
                            await self._disable_and_edit(
                                title="การขอแต่งงานล้มเหลว",
                                description="ไม่สามารถยืนยันได้ เพราะมีการแต่งงานกับคนอื่นแล้ว",
                                color_value=color.red,
                            )
                            return

                        accepted_at = datetime.datetime.now(datetime.timezone.utc)
                        await self.cog._clear_proposal_pair(
                            guild_id=self.guild_id_value,
                            proposer_id=self.proposer_id,
                            target_id=self.target_id,
                        )
                        await storage.guild_user_profiles.update(
                            id=proposer.get("id"),
                            guild_id=self.guild_id_value,
                            user_id=self.proposer_id,
                            relationship="married",
                            spouse_id=self.target_id,
                            married_at=accepted_at,
                        )
                        await storage.guild_user_profiles.update(
                            id=target.get("id"),
                            guild_id=self.guild_id_value,
                            user_id=self.target_id,
                            relationship="married",
                            spouse_id=self.proposer_id,
                            married_at=accepted_at,
                        )
                        await self._disable_and_edit(
                            title="ยอมรับการแต่งงานแล้ว",
                            description=(
                                f"{self.target_mention} ตอบรับคำขอของ {self.proposer_mention} แล้ว\n"
                                f"ตอนนี้ทั้งคู่แต่งงานกันในเซิร์ฟเวอร์นี้เรียบร้อย"
                            ),
                            color_value=color.green,
                        )
                    except Exception as e:
                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

                @discord.ui.button(
                    label="Reject",
                    style=discord.ButtonStyle.danger,
                    emoji="❌",
                )
                async def reject_button(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    try:
                        if interaction.user.id != self.target_id:
                            return await interaction.response.send_message(
                                "ปุ่มนี้สำหรับผู้ที่ถูกขอแต่งงานเท่านั้น",
                                ephemeral=True,
                                delete_after=8,
                            )

                        await interaction.response.defer()
                        if await self._is_pending():
                            await self.cog._clear_proposal_pair(
                                guild_id=self.guild_id_value,
                                proposer_id=self.proposer_id,
                                target_id=self.target_id,
                            )
                        await self._disable_and_edit(
                            title="การแต่งงานถูกปฏิเสธ",
                            description=(
                                f"{self.target_mention} ปฏิเสธคำขอแต่งงานของ {self.proposer_mention}"
                            ),
                            color_value=color.red,
                        )
                    except Exception as e:
                        logger.error(
                            f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                        )

            proposal_embed = discord.Embed(
                title="การขอแต่งงาน",
                description=(
                    f"{ctx.author.mention} ขอแต่งงานกับ {member.mention}\n"
                    f"{member.mention} กรุณาเลือก `Accept` หรือ `Reject` ภายใน 15 นาที"
                ),
                color=color.yellow,
            )
            proposal_view = MarriageProposalView(
                cog=self,
                guild_id_value=guild_id,
                proposer_id=ctx.author.id,
                target_id=member.id,
                proposer_mention=ctx.author.mention,
                target_mention=member.mention,
            )
            proposal_message = await ctx.send(embed=proposal_embed, view=proposal_view)
            proposal_view.message = proposal_message
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_command(
        name="divorce",
        help="หย่าจากคู่สมรสในเซิร์ฟเวอร์นี้",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=20, type=commands.BucketType.user)
    async def divorce(self, ctx: commands.Context):
        try:
            if not getattr(ctx, "guild", None):
                await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น", delete_after=8)
                return

            guild_id = ctx.guild.id
            author_row = await self._ensure_guild_user_profile(guild_id, ctx.author.id)
            author_spouse_id = int(author_row.get("spouse_id") or 0)
            author_relationship = str(author_row.get("relationship") or "single").lower()

            if author_relationship != "married" or author_spouse_id <= 0:
                await ctx.send("ตอนนี้คุณยังไม่ได้แต่งงานในเซิร์ฟเวอร์นี้", delete_after=8)
                return

            spouse_row = await storage.guild_user_profiles.get(
                guild_id=guild_id, user_id=author_spouse_id
            )
            await storage.guild_user_profiles.update(
                id=author_row.get("id"),
                guild_id=guild_id,
                user_id=ctx.author.id,
                relationship="single",
                spouse_id=0,
                married_at=None,
                proposal_to_id=0,
                proposal_from_id=0,
                proposal_at=None,
            )
            if spouse_row and int(spouse_row.get("spouse_id") or 0) == ctx.author.id:
                await storage.guild_user_profiles.update(
                    id=spouse_row.get("id"),
                    guild_id=guild_id,
                    user_id=author_spouse_id,
                    relationship="single",
                    spouse_id=0,
                    married_at=None,
                    proposal_to_id=0,
                    proposal_from_id=0,
                    proposal_at=None,
                )

            await ctx.send(
                f"{ctx.author.mention} ได้หย่าจาก <@{author_spouse_id}> แล้วในเซิร์ฟเวอร์นี้"
            )
        except Exception as e:
            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

    @commands.hybrid_command(
        name="profile",
        help="แสดงโปรไฟล์ผู้ใช้",
        with_app_command=True,
        aliases=["pr"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def profile(self, ctx, user: discord.Member = None):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        try:

            await self._safe_defer(ctx)

            if not user:

                user = ctx.author

            # get the user's badges from the user's public flags as name

            # badges = [badge.name for badge in user.public_flags.all()]

            # badges_list = {

            #     "staff": "discordstaff",

            #     "partner": "discordpartner",

            #     "hypesquad": "hypesquadevents",

            #     "bug_hunter": "discordbughunter1",

            #     "mfa_sms": "supportscommands",

            #     "premium_promo_dismissed": "discordnitro",

            #     "hypesquad_bravery": "hypesquadbravery",

            #     "hypesquad_brilliance": "hypesquadbrilliance",

            #     "hypesquad_balance": "hypesquadbalance",

            #     "early_supporter": "discordearlysupporter",

            #     "team_user": "discordstaff",

            #     "system": "discordstaff",

            #     "has_unread_urgent_messages": "discordstaff",

            #     "bug_hunter_level_2": "discordbughunter2",

            #     "verified_bot": "discordbotdev",

            #     "verified_bot_developer": "discordbotdev",

            #     "discord_certified_moderator": "discordmod",

            #     "bot_http_interactions": "discordstaff",

            #     "spammer": "discordstaff",

            #     "active_developer": "activedeveloper"

            # }

            # badges = [badges_list[badge] for badge in badges if badge in badges_list]

            avatar_url = user.display_avatar.url
            guild_profile = (
                await self._ensure_guild_user_profile(ctx.guild.id, user.id)
                if getattr(ctx, "guild", None)
                else None
            )
            relationship_raw = str(
                (guild_profile or {}).get("relationship") or "single"
            ).strip().lower()
            spouse_id = int((guild_profile or {}).get("spouse_id") or 0)
            proposal_to_id = int((guild_profile or {}).get("proposal_to_id") or 0)
            proposal_from_id = int((guild_profile or {}).get("proposal_from_id") or 0)
            spouse_text = "None"
            if spouse_id > 0:
                spouse_member = ctx.guild.get_member(spouse_id) if ctx.guild else None
                spouse_text = (
                    spouse_member.mention
                    if spouse_member
                    else f"<@{spouse_id}>"
                )
            proposal_text = "None"
            if proposal_to_id > 0:
                proposal_text = f"Outgoing to <@{proposal_to_id}>"
            elif proposal_from_id > 0:
                proposal_text = f"Incoming from <@{proposal_from_id}>"

            nickname_text = user.nick or i18n.tr("profile_no_nickname", guild_id)
            joined_server_text = (
                f"<t:{int(user.joined_at.timestamp())}:F> (<t:{int(user.joined_at.timestamp())}:R>)"
                if getattr(user, "joined_at", None)
                else "-"
            )

            role_mentions = [role.mention for role in reversed(user.roles) if role.name != "@everyone"]
            if role_mentions:
                roles_text = ", ".join(role_mentions[:20])
                if len(role_mentions) > 20:
                    roles_text += f" (+{len(role_mentions) - 20})"
            else:
                roles_text = i18n.tr("profile_no_roles", guild_id)

            # profile_image_byte = ui.get_ui_profile(

            #     avatar_url=avatar_url,

            #     banner_url=banner_url,

            #     display_name=user.display_name,

            #     username=user.name,

            #     coin=self.bot.cache.users.get(str(user.id),{}).get('balance',0),

            #     userid=str(user.id),

            #     created_at=user.created_at.astimezone(datetime.timezone.utc),

            #     badges=badges

            # )

            embed = discord.Embed(
                title=i18n.tr("profile_title", guild_id, user=user.display_name),
                description="",
                color=user.accent_color,
            )

            embed.add_field(
                name=i18n.tr("profile_section_user_info", guild_id),
                value=(
                    f"**{i18n.tr('profile_id', guild_id)}:** `{user.id}`\n"
                    f"**{i18n.tr('profile_name', guild_id)}:** {user.mention}\n"
                    f"**{i18n.tr('profile_joined_discord', guild_id)}:** "
                    f"<t:{int(user.created_at.timestamp())}:F> (<t:{int(user.created_at.timestamp())}:R>)\n"
                    f"**{i18n.tr('profile_nickname', guild_id)}:** `{nickname_text}`"
                ),
                inline=False,
            )

            embed.add_field(
                name=i18n.tr("profile_section_member_info", guild_id),
                value=(
                    f"**{i18n.tr('profile_joined_server', guild_id)}:** {joined_server_text}\n"
                    f"**{i18n.tr('profile_roles', guild_id)}:**\n{roles_text}"
                ),
                inline=False,
            )

            embed.add_field(
                name=i18n.tr("profile_relationship", guild_id),
                value=(
                    f"**Status:** `{self._relationship_label(relationship_raw, guild_id)}`\n"
                    f"**Spouse:** {spouse_text}\n"
                    f"**Proposal:** {proposal_text}"
                ),
                inline=False,
            )

            embed.set_image(url=avatar_url)

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url,
            )

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label=i18n.tr("profile_download_avatar", guild_id),
                    url=avatar_url,
                    style=discord.ButtonStyle.link,
                )
            )
            website_url = str(
                getattr(getattr(self.bot, "urls", None), "WEBSITE", "") or ""
            ).strip().rstrip("/")
            if website_url and getattr(ctx, "guild", None):
                view.add_item(
                    discord.ui.Button(
                        label="View Web Profile",
                        url=f"{website_url}/dashboard/user-profile/{ctx.guild.id}/{user.id}",
                        style=discord.ButtonStyle.link,
                    )
                )

            await ctx.send(embed=embed, view=view)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in profile command: {e}")

            await ctx.send(
                i18n.tr("command_processing_error", guild_id), delete_after=5
            )

    @commands.hybrid_command(
        name="avatar",
        with_app_command=True,
        help="แสดงรูปโปรไฟล์ผู้ใช้",
        aliases=["av"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def avatar(self, ctx, user: discord.User = None):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        try:

            await self._safe_defer(ctx)

            if not user:

                user = ctx.author

            avatar_url = user.display_avatar.url

            embed = discord.Embed(
                title=i18n.tr("avatar_title", guild_id, user=user.display_name), color=user.accent_color
            )

            embed.set_image(url=avatar_url)

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url,
            )

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label=i18n.tr("avatar_download", guild_id),
                    url=avatar_url,
                    style=discord.ButtonStyle.link,
                )
            )

            await ctx.send(embed=embed, view=view)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in avatar command: {e}")

            await ctx.send(
                i18n.tr("command_processing_error", guild_id), delete_after=5
            )

    @commands.hybrid_group(
        name="banner",
        with_app_command=True,
        help="แสดงแบนเนอร์ของผู้ใช้",
        invoke_without_command=True,
        usage=["<user>", "server"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def banner(self, ctx, user: discord.User = None):

        try:

            await self._safe_defer(ctx)

            if not user:

                user = ctx.author

            user = await self.bot.fetch_user(user.id)

            if not user.banner:

                embed = discord.Embed(
                    description=f"{user.display_name} doesn't have a banner.",
                    color=color.red,
                )

                await ctx.send(embed=embed)

                return

            banner_url = user.banner.url

            embed = discord.Embed(
                title=f"{user.display_name}'s Banner", color=user.accent_color
            )

            embed.set_image(url=banner_url)

            embed.set_footer(
                text=f"Requested by {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in banner command: {e}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @banner.command(
        name="server",
        help="แสดงแบนเนอร์ของเซิร์ฟเวอร์",
        aliases=["guild"],
    )
    async def banner_server(self, ctx):

        try:

            await self._safe_defer(ctx)

            guild = await self.bot.fetch_guild(ctx.guild.id)

            if not guild.banner:

                embed = discord.Embed(
                    description=f"This Server doesn't have a banner.", color=color.red
                )

                await ctx.send(embed=embed)

                return

            banner_url = guild.banner.url

            embed = discord.Embed(title=f"{guild.name}'s Banner", color=color.green)

            embed.set_image(url=banner_url)

            embed.set_footer(
                text=f"Requested by {ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in banner command: {e}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.group(
        name="list",
        help="คำสั่งแสดงรายการแบบต่าง ๆ",
        aliases=["ls"],
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list(self, ctx: commands.Context):

        embed = discord.Embed(
            title="รายการคำสั่ง",
            color=color.green,
            description="รายการคำสั่งทั้งหมด\n\n",
        )

        if hasattr(ctx.command, "commands"):

            for command in ctx.command.commands:

                embed.description += f"**`{self.bot.BotConfig.PREFIX}{ctx.command} {command.name}`** : {command.help}\n"

        await ctx.send(embed=embed)

    @list.command(name="emojis", help="แสดงอีโมจิทั้งหมดในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_emojis(self, ctx: commands.Context):

        try:

            emojis = ctx.guild.emojis

            if not emojis:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีอีโมจิในเซิร์ฟเวอร์นี้",
                        color=color.red,
                    )
                )

            # make 5 by 5 grid of emojis

            emojis = [emojis[i : i + 10] for i in range(0, len(emojis), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"{ctx.guild.name}'s Emojis",
                    color=color.green,
                    description="",
                )

                for emoji in emojis[current_page_index]:

                    embed.description += f"> - {emoji} - `{emoji.id}`\n"

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(emojis)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(emojis) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @list.command(name="channels", help="แสดงห้องทั้งหมดในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_channels(self, ctx: commands.Context):

        try:

            channels = ctx.guild.channels

            # make 5 by 5 grid of channels

            if not channels:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีห้องในเซิร์ฟเวอร์นี้",
                        color=color.red,
                    )
                )

            channels = [channels[i : i + 10] for i in range(0, len(channels), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"{ctx.guild.name}'s Channels",
                    color=color.green,
                    description="",
                )

                for channel in channels[current_page_index]:

                    embed.description += f"> - {channel.mention}\n"

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(channels)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(channels) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @list.command(name="bots", help="แสดงบอททั้งหมดในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_bots(self, ctx: commands.Context):

        try:

            bots = [member for member in ctx.guild.members if member.bot]

            if not bots:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีบอทในเซิร์ฟเวอร์นี้", color=color.red
                    )
                )

            # make 5 by 5 grid of bots

            bots = [bots[i : i + 10] for i in range(0, len(bots), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"{ctx.guild.name}'s Bots", color=color.green, description=""
                )

                for bot in bots[current_page_index]:

                    embed.description += f"> - {bot.mention}\n"

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(bots)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(bots) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @list.command(name="admins", help="แสดงแอดมินทั้งหมดในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_admins(self, ctx: commands.Context):

        try:

            admins = [
                member
                for member in ctx.guild.members
                if member.guild_permissions.administrator and not member.bot
            ]

            if not admins:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีแอดมินในเซิร์ฟเวอร์นี้",
                        color=color.red,
                    )
                )

            # make 5 by 5 grid of admins

            admins = [admins[i : i + 10] for i in range(0, len(admins), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"{ctx.guild.name}'s Admins",
                    color=color.green,
                    description="",
                )

                for admin in admins[current_page_index]:

                    embed.description += f"> - {admin.mention}\n"

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(admins)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(admins) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @list.command(name="bans", help="แสดงรายการแบนทั้งหมดในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_bans(self, ctx: commands.Context):

        try:

            bans = []

            bot_member = ctx.guild.me or ctx.guild.get_member(getattr(self.bot.user, "id", 0))
            if not bot_member or not bot_member.guild_permissions.ban_members:
                await ctx.send(
                    embed=discord.Embed(
                        description="บอทไม่มีสิทธิ์ `Ban Members` จึงอ่านรายการแบนไม่ได้",
                        color=color.red,
                    )
                )
                return

            async for ban in ctx.guild.bans(limit=None):

                bans.append(ban.user)

            if not bans:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีรายการแบนในเซิร์ฟเวอร์นี้", color=color.red
                    )
                )

            # make 5 by 5 grid of bans

            bans = [bans[i : i + 10] for i in range(0, len(bans), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"{ctx.guild.name}'s Bans", color=color.green, description=""
                )

                for ban in bans[current_page_index]:

                    embed.description += f"> - {ban.mention}\n"

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(bans)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(bans) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @list.command(name="roles", help="แสดงยศทั้งหมดในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_roles(self, ctx: commands.Context):

        try:

            roles = ctx.guild.roles

            if not roles:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มียศในเซิร์ฟเวอร์นี้", color=color.red
                    )
                )

            # make 5 by 5 grid of roles

            roles = [roles[i : i + 10] for i in range(0, len(roles), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"{ctx.guild.name}'s Roles", color=color.green, description=""
                )

                for role in roles[current_page_index]:

                    embed.description += f"> - {role.mention}\n"

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(roles)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(roles) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @list.command(name="boosters", help="แสดงผู้บูสต์ทั้งหมดในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_boosters(self, ctx: commands.Context):

        try:

            boosters = ctx.guild.premium_subscribers

            if not boosters:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ไม่มีสมาชิกบูสต์ในเซิร์ฟเวอร์นี้",
                        color=color.red,
                    )
                )

            # make 5 by 5 grid of boosters

            boosters = [boosters[i : i + 10] for i in range(0, len(boosters), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"{ctx.guild.name}'s Boosters",
                    color=color.green,
                    description="",
                )

                for booster in boosters[current_page_index]:

                    embed.description += f"> - {booster.mention}\n"

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(boosters)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(boosters) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @list.command(name="inrole", help="แสดงสมาชิกทั้งหมดในยศ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def list_inrole(self, ctx: commands.Context, role: discord.Role):

        try:

            members = role.members

            if not members:

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"There are no members in the {role.mention} role",
                        color=color.red,
                    )
                )

            # make 5 by 5 grid of members

            members = [members[i : i + 10] for i in range(0, len(members), 10)]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                embed = discord.Embed(
                    title=f"Members in the {role.name} role",
                    color=color.green,
                    description="",
                )

                i = 1

                for member in members[current_page_index]:

                    embed.description += f"{i} • {member.mention} - `{member.id}`\n"

                    i += 1

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(members)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                if len(members) == 1:

                    nonlocal cancled

                    cancled = True

                    return None

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                previous_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.PREVIOUS,
                    row=0,
                    disabled=current_page_index <= 0,
                )

                previous_button.callback = lambda i: previous_button_callback(i)

                stop_button = discord.ui.Button(
                    style=discord.ButtonStyle.red, emoji=self.bot.emoji.STOP, row=0
                )

                stop_button.callback = lambda i: stop_button_callback(i)

                next_button = discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji=self.bot.emoji.NEXT,
                    row=0,
                    disabled=current_page_index >= len(members) - 1,
                )

                next_button.callback = lambda i: next_button_callback(i)

                view.add_item(previous_button)

                view.add_item(stop_button)

                view.add_item(next_button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def previous_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index -= 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def stop_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal cancled

                    cancled = True

                    await interaction.response.edit_message(view=await get_view(True))

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            async def next_button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index += 1

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(
                        f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
                    )

            message = await ctx.send(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.hybrid_command(
        name="id",
        help="Inspect normal and raw IDs for emoji/channel/category/role/user (ดูข้อมูลปกติและค่า Raw ของ emoji/ห้อง/หมวดหมู่/ยศ/ผู้ใช้)",
        aliases=["raw", "snowflake"],
        with_app_command=True,
    )
    @app_commands.describe(
        target="เมนชันหรือเลข ID เช่น <:Support:149...> / #channel / @role / @user / 149..."
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def id_lookup(self, ctx: commands.Context, *, target: str = None):

        try:

            if ctx.guild is None:

                return await ctx.send("This command can only be used in a server.")

            raw_target = str(target or "").strip()

            if not raw_target:

                prefix = self.bot.cache.guilds.get(str(ctx.guild.id), {}).get(
                    "prefix", self.bot.BotConfig.PREFIX
                )

                usage = (
                    f"`{prefix}id <:Support:1498050582144094218>`\n"
                    f"`{prefix}id #general`\n"
                    f"`{prefix}id @Role`\n"
                    f"`{prefix}id @User`\n"
                    f"`{prefix}id 1498050582144094218`\n"
                    "`/id target:<your_value>`"
                )

                return await ctx.send(
                    embed=discord.Embed(
                        title="การค้นหารหัส",
                        description=f"วิธีใช้:\n{usage}",
                        color=color.orange,
                    )
                )

            def emoji_raw(name: str, emoji_id: int, animated: bool) -> str:

                safe_name = re.sub(r"[^a-zA-Z0-9_]", "", str(name or "emoji")) or "emoji"

                return f"<{'a' if animated else ''}:{safe_name}:{int(emoji_id)}>"

            def channel_type_name(channel_obj: Any) -> str:

                if isinstance(channel_obj, discord.TextChannel):

                    return "Text Channel"

                if isinstance(channel_obj, discord.VoiceChannel):

                    return "Voice Channel"

                if isinstance(channel_obj, discord.CategoryChannel):

                    return "Category"

                if isinstance(channel_obj, discord.StageChannel):

                    return "Stage Channel"

                if isinstance(channel_obj, discord.ForumChannel):

                    return "Forum Channel"

                if isinstance(channel_obj, discord.Thread):

                    return "Thread"

                return type(channel_obj).__name__

            emoji_match = re.search(r"<(a?):([A-Za-z0-9_]{1,32}):(\d{15,21})>", raw_target)
            channel_match = re.search(r"<#(\d{15,21})>", raw_target)
            role_match = re.search(r"<@&(\d{15,21})>", raw_target)
            user_match = re.search(r"<@!?(\d{15,21})>", raw_target)
            number_match = re.search(r"\b(\d{15,21})\b", raw_target)

            embed = discord.Embed(title="การค้นหารหัส", color=color.green)

            if emoji_match:

                animated = bool(emoji_match.group(1))

                emoji_name = emoji_match.group(2)

                emoji_id = int(emoji_match.group(3))

                emoji_obj = self.bot.get_emoji(emoji_id) or discord.utils.get(ctx.guild.emojis, id=emoji_id)

                if emoji_obj:

                    emoji_name = emoji_obj.name

                    animated = emoji_obj.animated

                raw_value = emoji_raw(emoji_name, emoji_id, animated)

                preview = str(emoji_obj) if emoji_obj else raw_value

                ext = "gif" if animated else "png"

                embed.description = (
                    f"**Type:** `Emoji`\n"
                    f"**Name:** `{emoji_name}`\n"
                    f"**Preview:** {preview}\n"
                    f"**ID:** `{emoji_id}`\n"
                    f"**Raw:** `{raw_value}`\n"
                    f"**CDN:** `https://cdn.discordapp.com/emojis/{emoji_id}.{ext}`"
                )

                return await ctx.send(embed=embed)

            if channel_match:

                channel_id = int(channel_match.group(1))

                channel_obj = ctx.guild.get_channel(channel_id) or self.bot.get_channel(channel_id)

                if channel_obj is None:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=f"ไม่พบ Channel ID `{channel_id}`",
                            color=color.red,
                        )
                    )

                raw_value = f"<#{channel_id}>"

                embed.description = (
                    f"**Type:** `{channel_type_name(channel_obj)}`\n"
                    f"**Name:** `{channel_obj.name}`\n"
                    f"**Preview:** {channel_obj.mention}\n"
                    f"**ID:** `{channel_id}`\n"
                    f"**Raw:** `{raw_value}`"
                )

                return await ctx.send(embed=embed)

            if role_match:

                role_id = int(role_match.group(1))

                role_obj = ctx.guild.get_role(role_id)

                if role_obj is None:

                    return await ctx.send(
                        embed=discord.Embed(
                            description=f"ไม่พบ Role ID `{role_id}`",
                            color=color.red,
                        )
                    )

                raw_value = f"<@&{role_id}>"

                embed.description = (
                    f"**Type:** `Role`\n"
                    f"**Name:** `{role_obj.name}`\n"
                    f"**Preview:** {role_obj.mention}\n"
                    f"**ID:** `{role_id}`\n"
                    f"**Raw:** `{raw_value}`"
                )

                return await ctx.send(embed=embed)

            if user_match:

                user_id = int(user_match.group(1))

                member_obj = ctx.guild.get_member(user_id)

                user_obj = member_obj or self.bot.get_user(user_id)
                if user_obj is None:
                    try:
                        user_obj = await self.bot.fetch_user(user_id)
                    except Exception:
                        user_obj = None

                raw_value = f"<@{user_id}>"

                display_name = getattr(user_obj, "display_name", None) or getattr(user_obj, "name", None) or "Unknown"

                preview = member_obj.mention if member_obj else raw_value

                embed.description = (
                    f"**Type:** `User`\n"
                    f"**Name:** `{display_name}`\n"
                    f"**Preview:** {preview}\n"
                    f"**ID:** `{user_id}`\n"
                    f"**Raw:** `{raw_value}`"
                )

                return await ctx.send(embed=embed)

            if number_match:

                snowflake_id = int(number_match.group(1))

                emoji_obj = self.bot.get_emoji(snowflake_id) or discord.utils.get(ctx.guild.emojis, id=snowflake_id)
                if emoji_obj:
                    raw_value = emoji_raw(emoji_obj.name, emoji_obj.id, emoji_obj.animated)
                    embed.description = (
                        f"**Type:** `Emoji`\n"
                        f"**Name:** `{emoji_obj.name}`\n"
                        f"**Preview:** {emoji_obj}\n"
                        f"**ID:** `{emoji_obj.id}`\n"
                        f"**Raw:** `{raw_value}`"
                    )
                    return await ctx.send(embed=embed)

                channel_obj = ctx.guild.get_channel(snowflake_id) or self.bot.get_channel(snowflake_id)
                if channel_obj:
                    raw_value = f"<#{channel_obj.id}>"
                    embed.description = (
                        f"**Type:** `{channel_type_name(channel_obj)}`\n"
                        f"**Name:** `{channel_obj.name}`\n"
                        f"**Preview:** {channel_obj.mention}\n"
                        f"**ID:** `{channel_obj.id}`\n"
                        f"**Raw:** `{raw_value}`"
                    )
                    return await ctx.send(embed=embed)

                role_obj = ctx.guild.get_role(snowflake_id)
                if role_obj:
                    raw_value = f"<@&{role_obj.id}>"
                    embed.description = (
                        f"**Type:** `Role`\n"
                        f"**Name:** `{role_obj.name}`\n"
                        f"**Preview:** {role_obj.mention}\n"
                        f"**ID:** `{role_obj.id}`\n"
                        f"**Raw:** `{raw_value}`"
                    )
                    return await ctx.send(embed=embed)

                member_obj = ctx.guild.get_member(snowflake_id)
                if member_obj:
                    raw_value = f"<@{member_obj.id}>"
                    embed.description = (
                        f"**Type:** `User`\n"
                        f"**Name:** `{member_obj.display_name}`\n"
                        f"**Preview:** {member_obj.mention}\n"
                        f"**ID:** `{member_obj.id}`\n"
                        f"**Raw:** `{raw_value}`"
                    )
                    return await ctx.send(embed=embed)

                user_obj = self.bot.get_user(snowflake_id)
                if user_obj:
                    raw_value = f"<@{user_obj.id}>"
                    embed.description = (
                        f"**Type:** `User`\n"
                        f"**Name:** `{user_obj.name}`\n"
                        f"**Preview:** {raw_value}\n"
                        f"**ID:** `{user_obj.id}`\n"
                        f"**Raw:** `{raw_value}`"
                    )
                    return await ctx.send(embed=embed)

                guild_obj = self.bot.get_guild(snowflake_id)
                if guild_obj:
                    embed.description = (
                        f"**Type:** `Guild`\n"
                        f"**Name:** `{guild_obj.name}`\n"
                        f"**ID:** `{guild_obj.id}`"
                    )
                    return await ctx.send(embed=embed)

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"ไม่พบข้อมูลจาก ID `{snowflake_id}`",
                        color=color.red,
                    )
                )

            return await ctx.send(
                embed=discord.Embed(
                    description="รูปแบบไม่ถูกต้อง กรุณาส่งเป็นเมนชันหรือเลข ID",
                    color=color.red,
                )
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.command(name="uptime", help="ดูระยะเวลาที่บอททำงาน")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def uptime(self, ctx: commands.Context):

        try:

            uptime = (
                datetime.datetime.now(tz=datetime.timezone.utc) - self.bot.start_time
            ).total_seconds()

            # convert the uptime to days, hours, minutes and seconds

            uptime_text = ""

            if uptime >= 86400:

                uptime_text += f"{int(uptime/86400)}d "

                uptime %= 86400

            if uptime >= 3600:

                uptime_text += f"{int(uptime/3600)}h "

                uptime %= 3600

            if uptime >= 60:

                uptime_text += f"{int(uptime/60)}m "

                uptime %= 60

            uptime_text += f"{int(uptime)}s"

            await ctx.send(
                embed=discord.Embed(
                    title="ระยะเวลาการออนไลน์",
                    color=color.green,
                    description=f"```\n{uptime_text}```",
                )
            )

        except Exception as e:

            logger.error(
                f"ข้อผิดพลาด in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.command(name="roleicon", help="ตั้งค่าไอคอนยศ", aliases=["roleemoji"])
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def roleicon(
        self, ctx: commands.Context, role: discord.Role, emoji: discord.PartialEmoji
    ):

        try:

            if not await checks.check_is_moderator_permissions(ctx, "manage_roles"):

                return

            if not await checks.check_if_user_can_manage_this_role(ctx, role):

                return

            if ctx.guild.premium_tier < 2:

                return await ctx.send(
                    embed=discord.Embed(
                        description="ต้องมีเซิร์ฟเวอร์บูสต์ระดับ 2 เพื่อใช้คำสั่งนี้",
                        color=color.red,
                    )
                )

            try:

                def get_image_byte_by_url(url):

                    return requests.get(url).content

                await role.edit(display_icon=get_image_byte_by_url(emoji.url))

                await ctx.send(
                    embed=discord.Embed(
                        description=f"Role icon for {role.mention} has been Changed",
                        color=color.green,
                    ).set_image(
                        url=role.display_icon.url if role.display_icon else None
                    )
                )

            except discord.HTTPException as e:

                await ctx.send(
                    embed=discord.Embed(
                        description=f"An error occurred while setting the role icon for {role.mention}",
                        color=color.red,
                    )
                )

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.hybrid_command(
        name="serverinfo",
        help="ดูข้อมูลเกี่ยวกับเซิร์ฟเวอร์",
        aliases=["guildinfo", "si", "gi"],
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def serverinfo(self, ctx: commands.Context):

        try:

            guild_cache = self.bot.cache.guilds.get(str(ctx.guild.id), {})

            subscription = guild_cache.get("subscription", "free")

            subscription_end = guild_cache.get("subscription_end", None)

            message = await ctx.send(
                embed=discord.Embed(
                    description="กำลังดึงข้อมูลเซิร์ฟเวอร์...", color=color.green
                )
            )

            # Server Name : SkylineBOT test server

            # Server ID : 1267073544928366677

            # Server Region : Us-Central

            # Owner Name : CheckMate

            # Owner ID : 1058254151810830357

            # Owner Mention : @CheckMate

            # Created : July 28, 2024 4:57 PM

            # Members Count : 14 Humans, 22 Bots

            # Bans Count : 5

            # Preferred Locale : English (United States)

            # Upload Limit : 26.2 MB

            # Vanity invite Code : None

            # Invites Disabled : False

            # Invites Background : Not Set

            # Discovery Splash URL : Not Set

            # :MekoUtility: Server Settings

            # Widget Enabled : False

            # Widget Channel : Not Set

            # Verification Level : Low

            # Default Message Notifications : Only Mentions

            # Explicit Media Content Filter : All Members

            # Nsfw Level : Default

            # MFA Requirement : :MekoCross:

            # System Welcome Messages : :MekoCheck:

            # Join Sticker Reply Buttons : :MekoCheck:

            # System Boost Messages : :MekoCheck:

            # Server Setup Tips : :MekoCheck:

            # Inactive Timeout : 5 minutes

            # Inactive Channel :  voice-2

            # Safety Alerts Channel : Not set

            # Discord Updates Channel :  leave_member

            # System Messages Channel :  general

            # Rules channel : testing

            # :MekoSticker: Emojis & Stickers Info

            # Static Emoji : 50/50

            # Animated Emoji : 20/50

            # Total Emoji : 70/100

            # Total Stickers : 2/5

            # :MekoBoost: Boost Status

            # Level : 0

            # Boost Count : 0

            # Booster Role : None

            # Boost Bar : :MekoCross:

            # :MekoCategory: Channels

            # Total : 144

            # Text : 122 (7 Locked)

            # Voice : 5 (0 Locked)

            # Stage: 0 (0 Locked)

            # Categories : 17 (0 Locked)

            # :MekoRoleGreen: Server Roles

            # Total : 41

            # Normal : 18

            # Integrated : 23

            ban_count: int | str = 0
            bot_member = ctx.guild.me or ctx.guild.get_member(getattr(self.bot.user, "id", 0))
            can_read_bans = bool(bot_member and bot_member.guild_permissions.ban_members)
            if can_read_bans:
                try:
                    async for ban in ctx.guild.bans(limit=101):
                        ban_count += 1
                    if isinstance(ban_count, int) and ban_count > 100:
                        ban_count = "100+"
                except discord.Forbidden:
                    ban_count = "N/A (Missing Permissions)"
            else:
                ban_count = "N/A (Missing Permissions)"

            paged_data = [
                {
                    "image": ctx.guild.banner.url if ctx.guild.banner else None,
                    "embed": discord.Embed(
                        title=f"{self.bot.emoji.INFO} About Server",
                        description=f"""**Server Name:** {ctx.guild.name}
**Server ID:** `{ctx.guild.id}`
**Owner Name:** {ctx.guild.owner}
**Owner ID:** `{ctx.guild.owner.id}`
**Owner Mention:** {ctx.guild.owner.mention}
**Created:** <t:{int(ctx.guild.created_at.timestamp())}:d> <t:{int(ctx.guild.created_at.timestamp())}:R>
**Members Count:** `{len(ctx.guild.members)} Humans, {len([member for member in ctx.guild.members if member.bot])} Bots`
**Bans Count:** `{ban_count}`
**Preferred Locale:** `{ctx.guild.preferred_locale}`
**Upload Limit:** `{round(ctx.guild.filesize_limit/1024/1024,1)} MB`
**Vanity invite Code:** `{ctx.guild.vanity_url_code if ctx.guild.vanity_url_code else '`Not Set`'}`
**Invites Disabled:** `{ctx.guild.explicit_content_filter}`
**Discovery Splash URL:** {'[Click Here]('+ctx.guild.discovery_splash.url+')' if ctx.guild.discovery_splash else '`Not Set`'}""",
                        color=color.black,
                    ),
                    "thumbnail": (
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    ),
                    "button": {
                        "name": "About",
                        "style": discord.ButtonStyle.blurple,
                        "emoji": self.bot.emoji.INFO,
                    },
                },
                {
                    "embed": discord.Embed(
                        title=f"{self.bot.emoji.SETTINGS} Server Settings",
                        description=f"""**Widget Enabled:** `{ctx.guild.widget_enabled}`
**Widget Channel:** {ctx.guild.widget_channel.mention if ctx.guild.widget_channel else '`Not Set`'}
**Verification Level:** `{ctx.guild.verification_level}`
**Default Message Notifications:** `{ctx.guild.default_notifications.name.capitalize().replace("_"," ")}`
**Explicit Media Content Filter:** `{ctx.guild.explicit_content_filter}`
**Nsfw Level:** `{ctx.guild.nsfw_level.name.capitalize()}`
**MFA Requirement:** {self.bot.emoji.NO if ctx.guild.mfa_level == 0 else self.bot.emoji.YES}
**System Welcome Messages:** {self.bot.emoji.YES if ctx.guild.system_channel_flags.join_notifications else self.bot.emoji.NO}
**Inactive Timeout:** `{ctx.guild.afk_timeout/60} minutes`
**Inactive Channel:** {ctx.guild.afk_channel.mention if ctx.guild.afk_channel else '`Not Set`'}
**Safety Alerts Channel:** {ctx.guild.system_channel.mention if ctx.guild.system_channel else '`Not Set`'}
**Discord Updates Channel:** {ctx.guild.public_updates_channel.mention if ctx.guild.public_updates_channel else '`Not Set`'}
**System Messages Channel:** {ctx.guild.system_channel.mention if ctx.guild.system_channel else '`Not Set`'}
**Rules channel:** {ctx.guild.rules_channel.mention if ctx.guild.rules_channel else '`Not Set`'}""",
                        color=color.black,
                    ),
                    "thumbnail": (
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    ),
                    "button": {
                        "name": "Settings",
                        "style": discord.ButtonStyle.blurple,
                        "emoji": self.bot.emoji.SETTINGS,
                    },
                },
                {
                    "embed": discord.Embed(
                        title=f"{self.bot.emoji.EMOJI} Emojis & Stickers & Boost",
                        description=f"""**Static Emoji:** `{len([emoji for emoji in ctx.guild.emojis if not emoji.animated])}/{ctx.guild.emoji_limit}`
**Animated Emoji:** `{len([emoji for emoji in ctx.guild.emojis if emoji.animated])}/{ctx.guild.emoji_limit}`
**Total Emoji:** `{len(ctx.guild.emojis)}/{ctx.guild.emoji_limit}`
**Total Stickers:** `{len(ctx.guild.stickers)}/{ctx.guild.sticker_limit}`
**Boost Level:** `{ctx.guild.premium_tier}`
**Boost Count:** `{ctx.guild.premium_subscription_count}`
**Booster Role:** {ctx.guild.premium_subscriber_role.mention if ctx.guild.premium_subscriber_role else '`None`'}
**Boost Bar:** {self.bot.emoji.YES if ctx.guild.premium_subscription_count >= 2 else self.bot.emoji.NO}""",
                        color=color.black,
                    ),
                    "thumbnail": (
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    ),
                    "button": {
                        "name": "Features",
                        "style": discord.ButtonStyle.blurple,
                        "emoji": self.bot.emoji.EMOJI,
                    },
                },
                {
                    "embed": discord.Embed(
                        title=f"{self.bot.emoji.CATEGORY} Channels & Roles",
                        description=f"""**Total Channels:** {len(ctx.guild.channels)}
**Text Channels:** {len([channel for channel in ctx.guild.text_channels])} ({len([channel for channel in ctx.guild.text_channels if channel.overwrites_for(ctx.guild.default_role).read_messages])} Locked)
**Voice Channels:** {len([channel for channel in ctx.guild.voice_channels])} ({len([channel for channel in ctx.guild.voice_channels if channel.overwrites_for(ctx.guild.default_role).connect])} Locked)
**Stage Channels:** {len([channel for channel in ctx.guild.stage_channels])} ({len([channel for channel in ctx.guild.stage_channels if channel.overwrites_for(ctx.guild.default_role).connect])} Locked)
**Categories:** {len([channel for channel in ctx.guild.categories])} ({len([channel for channel in ctx.guild.categories if channel.overwrites_for(ctx.guild.default_role).read_messages])} Locked)
**Total Roles:** {len(ctx.guild.roles)}
**Normal Roles:** {len([role for role in ctx.guild.roles if not role.managed])}
**Integrated Roles:** {len([role for role in ctx.guild.roles if role.managed])}""",
                        color=color.black,
                    ),
                    "thumbnail": (
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    ),
                    "button": {
                        "name": "Extras",
                        "style": discord.ButtonStyle.blurple,
                        "emoji": self.bot.emoji.CATEGORY,
                    },
                },
                #                 {
                #                     "embed":discord.Embed(
                #                         title="Subscription Status",
                #                         description=f"""**{self.bot.emoji.PREMIUM} Subscription:** `{subscription.capitalize().replace("_"," ")}`
                # **{self.bot.emoji.TIME} Subscription End:** {f'<t:{int(subscription_end.timestamp())}:R>' if subscription_end else '`Never`'}""",
                #                         color=color.black
                #                     ),
                #                     "thumbnail":ctx.guild.icon.url if ctx.guild.icon else self.bot.user.display_avatar.url,
                #                     "button":{
                #                         "name":"Subscription",
                #                         "style":discord.ButtonStyle.green,
                #                         "emoji":self.bot.emoji.PREMIUM
                #                     }
                #                 }
            ]

            current_page_index = 0

            view_timeout_time = 60

            cancled = False

            def reset_timeout_time(timeout: int = 60):

                nonlocal view_timeout_time

                view_timeout_time = timeout

            async def get_embed():

                nonlocal current_page_index

                if current_page_index >= len(paged_data):

                    current_page_index = 0

                data = paged_data[current_page_index]

                embed = data.get(
                    "embed",
                    discord.Embed(
                        description="เกิดข้อผิดพลาดขณะประมวลผลคำสั่ง"
                    ),
                )

                embed.set_author(
                    name=ctx.guild.name,
                    icon_url=(
                        ctx.guild.icon.url
                        if ctx.guild.icon
                        else self.bot.user.display_avatar.url
                    ),
                )

                embed.set_thumbnail(url=data.get("thumbnail", None))

                embed.set_image(url=data.get("image", None))

                embed.set_footer(
                    text=f"{current_page_index+1}/{len(paged_data)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                return embed

            async def get_view(disabled=False):

                view = discord.ui.View(timeout=60)

                reset_timeout_time()

                i = 0

                for page in paged_data:

                    button = discord.ui.Button(
                        style=page.get("button", {}).get(
                            "style", discord.ButtonStyle.blurple
                        ),
                        label=page.get("button", {}).get("name", ""),
                        disabled=page == paged_data[current_page_index],
                        custom_id=str(i),
                    )

                    i += 1

                    button.callback = lambda i: button_callback(i)

                    view.add_item(button)

                if disabled:

                    for item in view.children:

                        item.disabled = True

                return view

            async def button_callback(interaction: discord.Interaction):

                try:

                    if interaction.user.id != ctx.author.id:

                        return await interaction.response.send_message(
                            embed=discord.Embed(
                                description="คุณไม่มีสิทธิ์โต้ตอบกับปุ่มนี้",
                                color=color.red,
                            ),
                            ephemeral=True,
                            delete_after=10,
                        )

                    nonlocal current_page_index

                    current_page_index = int(interaction.data["custom_id"])

                    await interaction.response.edit_message(
                        embed=await get_embed(), view=await get_view()
                    )

                except Exception as e:

                    logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

            message = await message.edit(embed=await get_embed(), view=await get_view())

            while not cancled:

                view_timeout_time -= 1

                if view_timeout_time <= 0:

                    await message.edit(view=await get_view(True))

                    break

                await asyncio.sleep(1)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.hybrid_command(
        name="userinfo",
        help="ดูข้อมูลเกี่ยวกับผู้ใช้",
        aliases=["ui", "whois"],
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def userinfo(self, ctx: commands.Context, user: discord.User = None):

        try:

            if not user:

                user = ctx.author

            if not user:

                return await ctx.send(
                    embed=discord.Embed(description="ไม่พบผู้ใช้", color=color.red)
                )

            embed = discord.Embed(
                description=f"""**Name:** {user.mention}
**Global Name:** {user.global_name}
**Display Name:** {user.display_name}
**ID:** `{user.id}`
**Bot:** {self.bot.emoji.YES if user.bot else self.bot.emoji.NO}
**Account Created At:** <t:{int(user.created_at.timestamp())}:F>
""",
                color=user.accent_color if user.accent_color else color.black,
            )

            try:

                member = ctx.guild.get_member(user.id)

            except Exception:
                member = None

            if member:

                permission_names = [
                    perm for perm, value in member.guild_permissions if value
                ]

                if member.guild_permissions.administrator:

                    guild_permissions_text = "Administrator"

                elif not permission_names:

                    guild_permissions_text = "No Permissions"

                elif len(permission_names) < 25:

                    guild_permissions_text = " | ".join(permission_names)

                else:

                    guild_permissions_text = (
                        " | ".join(permission_names[:25])
                        + f" and {len(permission_names) - 25} more"
                    )

                embed.description += f"""\n**Guild Joined At:** <t:{int(member.joined_at.timestamp())}:F>
**Status:** `{str(member.status).capitalize()}`
**__Guild Permissions:__** ```\n{guild_permissions_text}```"""

            embed.set_thumbnail(url=user.display_avatar.url)

            embed.set_image(url=user.banner.url if user.banner else None)

            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )

            embed.set_author(name=user.name, icon_url=user.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.command(
        name="roleinfo", help="ดูข้อมูลเกี่ยวกับยศ", aliases=["ri"]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):

        try:

            embed = discord.Embed(color=role.color)

            embed.set_author(
                name=role.name,
                icon_url=(
                    ctx.guild.icon.url
                    if ctx.guild.icon
                    else self.bot.user.display_avatar.url
                ),
            )

            embed.add_field(
                name=f"{self.bot.emoji.GENERAL} __General info__",
                value=f"""> **{self.bot.emoji.NAME} Name:** {role.mention}






> {self.bot.emoji.ID} Id: `{role.id}`






> {self.bot.emoji.POSITION} Position: `{role.position}`






> {self.bot.emoji.MENTIONABLE} Mentionable: {self.bot.emoji.YES if role.mentionable else self.bot.emoji.NO}






> {self.bot.emoji.HOIST} Hoist: {self.bot.emoji.YES if role.hoist else self.bot.emoji.NO}






> {self.bot.emoji.MANAGED} Managed By Bot: {self.bot.emoji.YES if role.managed else self.bot.emoji.NO}






> {self.bot.emoji.COLOR} Color: `{role.color}`






> {self.bot.emoji.MEMBERS} Members: `{len(role.members)}`






> {self.bot.emoji.CREATED} Created At: <t:{int(role.created_at.timestamp())}:F>""",
                inline=False,
            )

            embed.add_field(
                name=f"{self.bot.emoji.PERMISSIONS} __Permissions__",
                value=(
                    "```\n"
                    + (
                        "Administrator"
                        if role.permissions.administrator
                        else (
                            " | ".join(
                                [perm for perm, value in role.permissions if value]
                            )
                            if len([perm for perm, value in role.permissions if value])
                            < 25
                            else " | ".join(
                                [perm for perm, value in role.permissions if value][:25]
                            )
                            + f" and {len([perm for perm, value in role.permissions if value]) - 25} more"
                        )
                    )
                    + "```"
                    if role.permissions
                    else "No Permissions"
                ),
                inline=False,
            )

            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.hybrid_command(
        name="membercount",
        help="ดูจำนวนสมาชิกของเซิร์ฟเวอร์",
        aliases=["mc"],
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def membercount(self, ctx: commands.Context):

        try:

            embed = discord.Embed(
                description=f"```prolog\n{ctx.guild.member_count}```", color=color.black
            )

            embed.set_author(
                name=ctx.guild.name,
                icon_url=(
                    ctx.guild.icon.url
                    if ctx.guild.icon
                    else self.bot.user.display_avatar.url
                ),
            )

            embed.set_footer(
                text=f"Online: {len([member for member in ctx.guild.members if str(member.status).lower() == 'online'])} | Offline: {len([member for member in ctx.guild.members if str(member.status).lower() == 'offline'])} | DND: {len([member for member in ctx.guild.members if str(member.status).lower() == 'dnd'])} | Idle: {len([member for member in ctx.guild.members if str(member.status).lower() == 'idle'])}",
                icon_url=(
                    ctx.guild.icon.url
                    if ctx.guild.icon
                    else self.bot.user.display_avatar.url
                ),
            )

            await ctx.reply(f"{ctx.guild.member_count}")

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.command(
        name="firstmessage", help="ดูข้อความแรกของห้อง", aliases=["fm"]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def firstmessage(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):

        try:

            if not channel:

                channel = ctx.channel

            first_message = None

            async for message in channel.history(limit=1, oldest_first=True):

                first_message = message

            if not first_message:

                return await ctx.send(
                    embed=discord.Embed(
                        description=f"No messages found in {channel.mention}",
                        color=color.red,
                    )
                )

            embed = discord.Embed(
                description=f"First message found in {channel.mention}",
                color=color.green,
            )

            view = discord.ui.View()

            message_url_button = discord.ui.Button(
                style=discord.ButtonStyle.url,
                label="Click to View",
                url=first_message.jump_url,
            )

            view.add_item(message_url_button)

            await ctx.send(embed=embed, view=view)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )

    @commands.command(
        name="boostcount", help="ดูจำนวนบูสต์ของเซิร์ฟเวอร์", aliases=["bc"]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=15, type=commands.BucketType.user)
    async def boostcount(self, ctx: commands.Context):

        try:

            embed = discord.Embed(
                description=f"```prolog\n{ctx.guild.premium_subscription_count}```",
                color=color.black,
            )

            embed.set_author(
                name=ctx.guild.name,
                icon_url=(
                    ctx.guild.icon.url
                    if ctx.guild.icon
                    else self.bot.user.display_avatar.url
                ),
            )

            embed.set_footer(
                text=f"Boost Level: {ctx.guild.premium_tier}",
                icon_url=(
                    ctx.guild.icon.url
                    if ctx.guild.icon
                    else self.bot.user.display_avatar.url
                ),
            )

            await ctx.reply(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

            await ctx.send(
                "An error occurred while processing the command.", delete_after=5
            )
