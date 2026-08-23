import asyncio
import io
import re
import time
import traceback
from typing import Optional

import discord
from deep_translator import GoogleTranslator
from discord import app_commands
from discord.ext import commands
from langdetect import DetectorFactory, detect

from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color

DetectorFactory.seed = 0

TRANSLATE_CHUNK_SIZE = 4200
TRANSLATE_INPUT_LIMIT = 32000
TRANSLATE_EMBED_PREVIEW_LIMIT = 3500
TRANSLATE_FIELD_LIMIT = 1600
REACTION_COOLDOWN_SECONDS = 6


REACTION_LANGUAGE_MAP: dict[str, str] = {
    "🌐": "auto",
    "🇹🇭": "th",
    "🇺🇸": "en",
    "🇬🇧": "en",
    "🇯🇵": "ja",
    "🇰🇷": "ko",
    "🇨🇳": "zh-CN",
    "🇹🇼": "zh-TW",
    "🇻🇳": "vi",
    "🇮🇩": "id",
    "🇫🇷": "fr",
    "🇩🇪": "de",
    "🇪🇸": "es",
    "🇷🇺": "ru",
}


LANGUAGE_ALIASES: dict[str, str] = {
    "th": "th",
    "thai": "th",
    "ภาษาไทย": "th",
    "เป็นภาษาไทย": "th",
    "ไทย": "th",
    "en": "en",
    "eng": "en",
    "english": "en",
    "ภาษาอังกฤษ": "en",
    "เป็นภาษาอังกฤษ": "en",
    "อังกฤษ": "en",
    "ja": "ja",
    "jp": "ja",
    "japanese": "ja",
    "ญี่ปุ่น": "ja",
    "ko": "ko",
    "korean": "ko",
    "เกาหลี": "ko",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "cn": "zh-CN",
    "chinese": "zh-CN",
    "จีน": "zh-CN",
    "zh-tw": "zh-TW",
    "tw": "zh-TW",
    "traditional-chinese": "zh-TW",
    "vi": "vi",
    "vietnamese": "vi",
    "เวียดนาม": "vi",
    "id": "id",
    "indonesian": "id",
    "อินโด": "id",
    "fr": "fr",
    "french": "fr",
    "de": "de",
    "german": "de",
    "es": "es",
    "spanish": "es",
    "ru": "ru",
    "russian": "ru",
    "pt": "pt",
    "portuguese": "pt",
    "it": "it",
    "italian": "it",
    "ar": "ar",
    "arabic": "ar",
    "hi": "hi",
    "hindi": "hi",
}


LANGUAGE_LABELS: dict[str, str] = {
    "th": "Thai",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "pt": "Portuguese",
    "it": "Italian",
    "ar": "Arabic",
    "hi": "Hindi",
}


class Translator(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._reaction_cooldowns: dict[tuple[int, int], float] = {}
        self._registered_context_menus: list[app_commands.ContextMenu] = []

        class CogInfo:
            name = "Translator"
            category = "Utility"
            description = "Translate text via command, Apps, and reaction"
            hidden = False
            emoji = "🌐"

        self.cog_info = CogInfo
        self._register_context_menus()

    def _register_context_menus(self) -> None:
        menu = app_commands.ContextMenu(
            name="Translate Message",
            callback=self.translate_message_app,
        )
        self.bot.tree.add_command(menu, override=True)
        self._registered_context_menus.append(menu)

    def cog_unload(self) -> None:
        for menu in self._registered_context_menus:
            try:
                self.bot.tree.remove_command(menu.name, type=menu.type)
            except Exception:
                pass
        self._registered_context_menus.clear()

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        value = str(text or "").strip()
        if len(value) <= limit:
            return value or "-"
        return value[: max(0, limit - 3)] + "..."

    @staticmethod
    def _normalize_line_endings(text: str) -> str:
        return str(text or "").replace("\r\n", "\n").replace("\r", "\n")

    def _normalize_language_code(self, raw: str | None) -> Optional[str]:
        token = str(raw or "").strip()
        if not token:
            return None
        normalized = token.lower().replace("_", "-")

        if normalized in LANGUAGE_ALIASES:
            return LANGUAGE_ALIASES[normalized]

        if re.fullmatch(r"[a-z]{2,3}", normalized):
            return normalized

        if re.fullmatch(r"[a-z]{2,3}-[a-z]{2}", normalized):
            base, region = normalized.split("-", 1)
            return f"{base}-{region.upper()}"

        return None

    @staticmethod
    def _normalize_style_token(raw: str | None) -> str | None:
        value = str(raw or "").strip().lower()
        if not value:
            return None
        if value in {"line-by-line", "linebyline"}:
            return "line_by_line"
        if value in {"normal", "bilingual", "line_by_line"}:
            return value
        return None

    def _parse_prefix_translate_input(
        self,
        target_lang: str | None,
        style: str | None,
        text: str | None,
    ) -> tuple[str | None, str, str, str]:
        """
        Parse prefix-command args and support multiple human-friendly forms:
        - !translate <target> <text>
        - !translate <text> <target>
        - !translate <text> <source> <target>
        """
        combined = " ".join(
            part for part in [str(target_lang or "").strip(), str(style or "").strip(), str(text or "").strip()] if part
        ).strip()
        if not combined:
            return None, "auto", "normal", ""

        tokens = combined.split()
        if not tokens:
            return None, "auto", "normal", ""

        first_lang = self._normalize_language_code(tokens[0])
        if first_lang:
            style_value = "normal"
            index = 1
            if index < len(tokens):
                maybe_style = self._normalize_style_token(tokens[index])
                if maybe_style:
                    style_value = maybe_style
                    index += 1
            source_text = " ".join(tokens[index:]).strip()
            return first_lang, "auto", style_value, source_text

        working = list(tokens)
        style_value = "normal"
        maybe_style = self._normalize_style_token(working[-1])
        if maybe_style and len(working) > 1:
            style_value = maybe_style
            working.pop()

        target_candidate = self._normalize_language_code(working[-1]) if working else None
        if not target_candidate:
            return None, "auto", style_value, combined

        working.pop()
        source_lang = "auto"
        if len(working) >= 2:
            maybe_source = self._normalize_language_code(working[-1])
            if maybe_source:
                source_lang = maybe_source
                working.pop()

        source_text = " ".join(working).strip()
        return target_candidate, source_lang, style_value, source_text

    @staticmethod
    def _language_label(code: str) -> str:
        normalized = str(code or "").strip()
        return LANGUAGE_LABELS.get(normalized, normalized or "Unknown")

    def _locale_to_language(self, locale: object) -> str:
        value = str(locale or "").strip().lower()
        if value.startswith("th"):
            return "th"
        if value.startswith("ja"):
            return "ja"
        if value.startswith("ko"):
            return "ko"
        if value.startswith("zh-tw"):
            return "zh-TW"
        if value.startswith("zh"):
            return "zh-CN"
        if value.startswith("vi"):
            return "vi"
        if value.startswith("id"):
            return "id"
        if value.startswith("fr"):
            return "fr"
        if value.startswith("de"):
            return "de"
        if value.startswith("es"):
            return "es"
        if value.startswith("ru"):
            return "ru"
        return "en"

    def _detect_language(self, text: str) -> str:
        sample = self._normalize_line_endings(text)[:5000].strip()
        if not sample:
            return "auto"
        if re.search(r"[\u0E00-\u0E7F]", sample):
            return "th"
        if re.search(r"[\u3040-\u30FF]", sample):
            return "ja"
        if re.search(r"[\uAC00-\uD7AF]", sample):
            return "ko"
        if re.search(r"[\u4E00-\u9FFF]", sample):
            return "zh-CN"
        if re.search(r"[\u0400-\u04FF]", sample):
            return "ru"
        try:
            detected = str(detect(sample)).strip().lower()
            return detected if detected else "auto"
        except Exception:
            return "auto"

    def _auto_target_language(self, text: str, *, preferred: str = "en") -> str:
        detected = self._detect_language(text)
        preferred_lang = self._normalize_language_code(preferred) or "en"

        if detected == "auto":
            return preferred_lang

        detected_prefix = detected.split("-", 1)[0]
        preferred_prefix = preferred_lang.split("-", 1)[0].lower()

        if detected_prefix != preferred_prefix:
            return preferred_lang

        if detected_prefix == "th":
            return "en"
        return "th"

    def _split_text_chunks(self, text: str, limit: int = TRANSLATE_CHUNK_SIZE) -> list[str]:
        normalized = self._normalize_line_endings(text)
        if len(normalized) <= limit:
            return [normalized]

        chunks: list[str] = []
        buffer = ""

        segments = re.split(r"(\n+)", normalized)
        for segment in segments:
            if not segment:
                continue

            if len(buffer) + len(segment) <= limit:
                buffer += segment
                continue

            if buffer.strip():
                chunks.append(buffer)
            buffer = ""

            if len(segment) <= limit:
                buffer = segment
                continue

            start = 0
            while start < len(segment):
                piece = segment[start : start + limit]
                if piece.strip():
                    chunks.append(piece)
                start += limit

        if buffer.strip():
            chunks.append(buffer)

        return chunks or [normalized[:limit]]

    def _translate_sync(
        self,
        text: str,
        *,
        target_lang: str,
        source_lang: str = "auto",
        line_by_line: bool = False,
    ) -> str:
        translator = GoogleTranslator(source=source_lang, target=target_lang)

        if line_by_line:
            lines = self._normalize_line_endings(text).split("\n")
            translated_lines: list[str] = []
            for line in lines:
                clean_line = str(line or "")
                if not clean_line.strip():
                    translated_lines.append(clean_line)
                    continue
                translated_value = translator.translate(clean_line)
                translated_lines.append(str(translated_value or clean_line))
            return "\n".join(translated_lines).strip()

        chunks = self._split_text_chunks(text)
        translated_chunks: list[str] = []
        for chunk in chunks:
            clean_chunk = str(chunk or "")
            if not clean_chunk.strip():
                translated_chunks.append(clean_chunk)
                continue
            translated_value = translator.translate(clean_chunk)
            translated_chunks.append(str(translated_value or clean_chunk))

        return "".join(translated_chunks).strip()

    async def _translate_text(
        self,
        text: str,
        *,
        target_lang: str,
        source_lang: str = "auto",
        line_by_line: bool = False,
    ) -> str:
        return await asyncio.to_thread(
            self._translate_sync,
            text,
            target_lang=target_lang,
            source_lang=source_lang,
            line_by_line=line_by_line,
        )

    @staticmethod
    def _extract_text_from_message(message: discord.Message) -> str:
        content = str(getattr(message, "content", "") or "").strip()
        if content:
            return content

        for embed in list(getattr(message, "embeds", []) or []):
            title = str(getattr(embed, "title", "") or "").strip()
            description = str(getattr(embed, "description", "") or "").strip()
            if title and description:
                return f"{title}\n{description}".strip()
            if description:
                return description
            if title:
                return title

        return ""

    async def _extract_reply_text(self, ctx: commands.Context) -> str:
        ref = getattr(getattr(ctx, "message", None), "reference", None)
        if not ref:
            return ""

        resolved = ref.resolved if isinstance(ref.resolved, discord.Message) else None
        if resolved is None and ref.message_id and ctx.channel is not None:
            try:
                resolved = await ctx.channel.fetch_message(ref.message_id)
            except Exception:
                resolved = None

        if not resolved:
            return ""
        return self._extract_text_from_message(resolved)

    def _prepare_output(
        self,
        *,
        source_lang: str,
        target_lang: str,
        source_text: str,
        translated_text: str,
        style: str,
        title_prefix: str,
    ) -> tuple[discord.Embed, discord.File | None]:
        embed = discord.Embed(
            title=f"{title_prefix}: {self._language_label(source_lang)} → {self._language_label(target_lang)}",
            color=color.blue,
            timestamp=discord.utils.utcnow(),
        )

        style_value = str(style or "normal").strip().lower()
        if style_value == "bilingual":
            embed.add_field(
                name="Original",
                value=self._clip(source_text, TRANSLATE_FIELD_LIMIT),
                inline=False,
            )
            embed.add_field(
                name="Translated",
                value=self._clip(translated_text, TRANSLATE_FIELD_LIMIT),
                inline=False,
            )
        else:
            embed.description = self._clip(translated_text, TRANSLATE_EMBED_PREVIEW_LIMIT)

        if style_value == "line_by_line":
            embed.set_footer(text="Style: line_by_line")
        elif style_value == "bilingual":
            embed.set_footer(text="Style: bilingual")
        else:
            embed.set_footer(text="Style: normal")

        file: discord.File | None = None
        if len(translated_text) > TRANSLATE_EMBED_PREVIEW_LIMIT:
            filename = f"translation-{target_lang}.txt"
            payload = translated_text.encode("utf-8", errors="ignore")
            file = discord.File(io.BytesIO(payload), filename=filename)

        return embed, file

    async def _send_ephemeral(
        self,
        interaction: discord.Interaction,
        *,
        content: str | None = None,
        embed: discord.Embed | None = None,
        file: discord.File | None = None,
    ) -> None:
        kwargs: dict[str, object] = {"ephemeral": True}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if file is not None:
            kwargs["file"] = file

        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)

    async def _safe_ctx_defer(self, ctx: commands.Context, *, ephemeral: bool = False) -> bool:
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return False
        if interaction.response.is_done():
            return True
        try:
            await ctx.defer(ephemeral=ephemeral)
            return True
        except (discord.NotFound, discord.InteractionResponded):
            return False
        except discord.HTTPException as interaction_error:
            if getattr(interaction_error, "code", None) == 10062:
                return False
            raise

    async def _safe_ctx_send(self, ctx: commands.Context, content: str | None = None, **kwargs):
        try:
            if content is not None:
                return await ctx.send(content, **kwargs)
            return await ctx.send(**kwargs)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except discord.HTTPException as send_error:
            if getattr(send_error, "code", None) != 10062:
                raise

        channel = getattr(ctx, "channel", None)
        if channel is None:
            return None

        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("ephemeral", None)
        if content is not None:
            return await channel.send(content, **fallback_kwargs)
        return await channel.send(**fallback_kwargs)

    @commands.hybrid_command(
        name="translate",
        help="แปลข้อความระหว่างหลายภาษาสำหรับข้อความทั้งสั้นและยาว",
        aliases=["tr", "แปล"],
        with_app_command=True,
    )
    @app_commands.describe(
        target_lang="ภาษาเป้าหมาย เช่น en, th, ja, zh-CN",
        style="รูปแบบผลลัพธ์",
        text="ข้อความที่ต้องการแปล (ถ้าเว้นไว้จะใช้ข้อความที่ reply)",
    )
    @app_commands.choices(
        style=[
            app_commands.Choice(name="Normal", value="normal"),
            app_commands.Choice(name="Bilingual", value="bilingual"),
            app_commands.Choice(name="Line by line", value="line_by_line"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=20, type=commands.BucketType.user)
    async def translate_command(
        self,
        ctx: commands.Context,
        target_lang: str = "en",
        style: str = "normal",
        *,
        text: str | None = None,
    ):
        try:
            is_slash_invocation = getattr(ctx, "interaction", None) is not None
            source_for_engine = "auto"
            style_value = "normal"
            source_text = ""

            if is_slash_invocation:
                await self._safe_ctx_defer(ctx, ephemeral=False)
                style_value = self._normalize_style_token(style) or "normal"
                source_text = str(text or "").strip()
                normalized_target = self._normalize_language_code(target_lang)
            else:
                (
                    normalized_target,
                    source_for_engine,
                    style_value,
                    source_text,
                ) = self._parse_prefix_translate_input(
                    target_lang=target_lang,
                    style=style,
                    text=text,
                )
            if not normalized_target:
                return await self._safe_ctx_send(
                    ctx,
                    "ไม่รองรับภาษาเป้าหมายนี้ ลองใช้โค้ดภาษาเช่น `en`, `th`, `ja`, `zh-CN`"
                )

            if not source_text:
                source_text = await self._extract_reply_text(ctx)

            if not source_text:
                return await self._safe_ctx_send(
                    ctx,
                    "พิมพ์ข้อความที่ต้องการแปล หรือ reply ข้อความแล้วใช้คำสั่งนี้อีกครั้ง"
                )

            if len(source_text) > TRANSLATE_INPUT_LIMIT:
                return await self._safe_ctx_send(
                    ctx,
                    f"ข้อความยาวเกินไป (จำกัด {TRANSLATE_INPUT_LIMIT:,} ตัวอักษร)"
                )

            detected_source = self._detect_language(source_text)

            translated_text = await self._translate_text(
                source_text,
                target_lang=normalized_target,
                source_lang=source_for_engine,
                line_by_line=(style_value == "line_by_line"),
            )

            source_label = detected_source if detected_source != "auto" else "auto"
            embed, file = self._prepare_output(
                source_lang=source_label,
                target_lang=normalized_target,
                source_text=source_text,
                translated_text=translated_text,
                style=style_value,
                title_prefix="Translate",
            )

            kwargs: dict[str, object] = {"embed": embed}
            if file is not None:
                kwargs["file"] = file
            await self._safe_ctx_send(ctx, **kwargs)
        except Exception as error:
            logger.error(
                f"Error in file {__file__} at translate_command: {traceback.format_exc()}"
            )
            await self._safe_ctx_send(ctx, f"แปลข้อความไม่สำเร็จ: `{error}`")

    async def translate_message_app(
        self,
        interaction: discord.Interaction,
        message: discord.Message,
    ):
        text = self._extract_text_from_message(message)
        if not text:
            return await self._send_ephemeral(
                interaction,
                content="ข้อความนี้ไม่มีเนื้อหาที่แปลได้",
            )

        if len(text) > TRANSLATE_INPUT_LIMIT:
            return await self._send_ephemeral(
                interaction,
                content=f"ข้อความยาวเกินไป (จำกัด {TRANSLATE_INPUT_LIMIT:,} ตัวอักษร)",
            )

        preferred = self._locale_to_language(getattr(interaction, "locale", None))
        target_lang = self._auto_target_language(text, preferred=preferred)

        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)

            detected_source = self._detect_language(text)
            translated_text = await self._translate_text(
                text,
                target_lang=target_lang,
                source_lang="auto",
                line_by_line=False,
            )

            source_label = detected_source if detected_source != "auto" else "auto"
            embed, file = self._prepare_output(
                source_lang=source_label,
                target_lang=target_lang,
                source_text=text,
                translated_text=translated_text,
                style="normal",
                title_prefix="Apps Translate",
            )

            await self._send_ephemeral(interaction, embed=embed, file=file)
        except Exception as error:
            logger.error(
                f"Error in file {__file__} at translate_message_app: {traceback.format_exc()}"
            )
            await self._send_ephemeral(interaction, content=f"แปลข้อความไม่สำเร็จ: `{error}`")

    def _check_reaction_cooldown(self, guild_id: int, user_id: int) -> bool:
        now = time.monotonic()
        key = (int(guild_id), int(user_id))
        last_used = self._reaction_cooldowns.get(key, 0.0)
        if now - last_used < REACTION_COOLDOWN_SECONDS:
            return False
        self._reaction_cooldowns[key] = now

        if len(self._reaction_cooldowns) > 2500:
            cutoff = now - (REACTION_COOLDOWN_SECONDS * 3)
            self._reaction_cooldowns = {
                k: v for k, v in self._reaction_cooldowns.items() if v >= cutoff
            }

        return True

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            if payload.guild_id is None:
                return
            if self.bot.user and int(payload.user_id) == int(self.bot.user.id):
                return

            emoji = str(payload.emoji)
            if emoji not in REACTION_LANGUAGE_MAP:
                return

            if not self._check_reaction_cooldown(payload.guild_id, payload.user_id):
                return

            channel = self.bot.get_channel(payload.channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(payload.channel_id)
                except Exception:
                    return

            fetch_message = getattr(channel, "fetch_message", None)
            if not callable(fetch_message):
                return

            try:
                message = await fetch_message(payload.message_id)
            except Exception:
                return

            if message is None or getattr(message, "author", None) is None:
                return
            if self.bot.user and int(message.author.id) == int(self.bot.user.id):
                return

            source_text = self._extract_text_from_message(message)
            if not source_text:
                return

            if len(source_text) > TRANSLATE_INPUT_LIMIT:
                return

            mapped = REACTION_LANGUAGE_MAP.get(emoji, "auto")
            if mapped == "auto":
                target_lang = self._auto_target_language(source_text, preferred="en")
            else:
                target_lang = mapped

            detected_source = self._detect_language(source_text)
            translated_text = await self._translate_text(
                source_text,
                target_lang=target_lang,
                source_lang="auto",
                line_by_line=False,
            )

            source_label = detected_source if detected_source != "auto" else "auto"
            embed, file = self._prepare_output(
                source_lang=source_label,
                target_lang=target_lang,
                source_text=source_text,
                translated_text=translated_text,
                style="normal",
                title_prefix="Reaction Translate",
            )

            header = (
                f"Translation requested by <@{payload.user_id}> "
                f"({self._language_label(target_lang)})"
            )
            kwargs: dict[str, object] = {
                "content": header,
                "embed": embed,
                "mention_author": False,
                "allowed_mentions": discord.AllowedMentions.none(),
            }
            if file is not None:
                kwargs["file"] = file

            await message.reply(**kwargs)
        except Exception:
            logger.error(
                f"Error in file {__file__} at on_raw_reaction_add: {traceback.format_exc()}"
            )
