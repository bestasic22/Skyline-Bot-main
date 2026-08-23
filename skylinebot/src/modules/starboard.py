from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

import discord
from discord.ext import commands

import storage.dashboard_config as dashboard_config_db
from skylinebot.console.logging import logger


STARBOARD_CONFIG_KEY_PREFIX = "probot_starboard_v1_guild_"
STARBOARD_INDEX_KEY_PREFIX = "probot_starboard_index_v1_guild_"
MAX_INDEX_ITEMS = 3000
CUSTOM_EMOJI_PATTERN = re.compile(r"^<a?:[a-zA-Z0-9_]{2,}:([0-9]{5,})>$")


def _safe_int(value: Any, default: int = 0, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _normalize_color_hex(raw_value: Any, default: str = "#6B8CFF") -> str:
    text = str(raw_value or default).strip()
    if not text:
        return default
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) != 7:
        return default
    for ch in text[1:]:
        if ch not in "0123456789abcdefABCDEF":
            return default
    return text.upper()


def _default_starboard_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "active": True,
        "name": "starboard",
        "enabled_channel_id": "",
        "channel_id": "",
        "required_role_id": "",
        "stars_limit": 3,
        "custom_emoji": "⭐",
        "message_mode": "embed",
        "message_template": "[emoji] [stars] • [author] • [channel]\n[link]",
        "embed_author_name": "",
        "embed_author_url": "",
        "embed_author_icon_url": "",
        "embed_title": "Starboard Highlight",
        "embed_description": "[content]",
        "embed_thumbnail_url": "",
        "embed_image_url": "",
        "embed_footer_text": "",
        "embed_footer_icon_url": "",
        "fields": [],
        "color": "#6B8CFF",
        "ignore_self_stars": True,
        "react_to_starboard_post": False,
    }


def _normalize_starboard_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}
    out = _default_starboard_settings()

    out["enabled"] = _as_bool(src.get("enabled"), out["enabled"])
    out["active"] = _as_bool(src.get("active"), out["active"])
    out["name"] = str(src.get("name") or out["name"]).strip()[:80] or out["name"]

    enabled_channel_id = str(src.get("enabled_channel_id") or "").strip()
    channel_id = str(src.get("channel_id") or "").strip()
    role_id = str(src.get("required_role_id") or "").strip()

    out["enabled_channel_id"] = enabled_channel_id if enabled_channel_id.isdigit() else ""
    out["channel_id"] = channel_id if channel_id.isdigit() else ""
    out["required_role_id"] = role_id if role_id.isdigit() else ""

    out["stars_limit"] = _safe_int(src.get("stars_limit"), out["stars_limit"], minimum=1, maximum=20)
    out["custom_emoji"] = str(src.get("custom_emoji") or out["custom_emoji"]).strip()[:64] or out["custom_emoji"]

    mode = str(src.get("message_mode") or out["message_mode"]).strip().lower()
    out["message_mode"] = mode if mode in {"text", "embed"} else "embed"
    out["message_template"] = str(src.get("message_template") or out["message_template"]).strip()[:400] or out["message_template"]

    out["embed_author_name"] = str(src.get("embed_author_name") or out["embed_author_name"]).strip()[:256]
    out["embed_author_url"] = str(src.get("embed_author_url") or out["embed_author_url"]).strip()[:600]
    out["embed_author_icon_url"] = str(src.get("embed_author_icon_url") or out["embed_author_icon_url"]).strip()[:600]
    out["embed_title"] = str(src.get("embed_title") or out["embed_title"]).strip()[:120] or out["embed_title"]
    out["embed_description"] = str(src.get("embed_description") or out["embed_description"]).strip()[:4000] or out["embed_description"]
    out["embed_thumbnail_url"] = str(src.get("embed_thumbnail_url") or out["embed_thumbnail_url"]).strip()[:600]
    out["embed_image_url"] = str(src.get("embed_image_url") or out["embed_image_url"]).strip()[:600]
    out["embed_footer_text"] = str(src.get("embed_footer_text") or out["embed_footer_text"]).strip()[:2048]
    out["embed_footer_icon_url"] = str(src.get("embed_footer_icon_url") or out["embed_footer_icon_url"]).strip()[:600]

    normalized_fields: list[dict[str, Any]] = []
    raw_fields = src.get("fields")
    if isinstance(raw_fields, list):
        for idx, raw_field in enumerate(raw_fields[:25], start=1):
            row = raw_field if isinstance(raw_field, dict) else {}
            name = str(row.get("name") or "").strip()[:256]
            value = str(row.get("value") or "").strip()[:1024]
            if not name and not value:
                continue
            normalized_fields.append(
                {
                    "id": str(row.get("id") or f"field_{idx}").strip()[:64] or f"field_{idx}",
                    "name": name or "หัวข้อ",
                    "value": value or "-",
                    "inline": _as_bool(row.get("inline"), False),
                    "align": "center" if str(row.get("align") or "").strip().lower() == "center" else "left",
                }
            )
    out["fields"] = normalized_fields

    out["color"] = _normalize_color_hex(src.get("color"), out["color"])
    out["ignore_self_stars"] = _as_bool(src.get("ignore_self_stars"), out["ignore_self_stars"])
    out["react_to_starboard_post"] = _as_bool(src.get("react_to_starboard_post"), out["react_to_starboard_post"])
    return out


def _render_tokens(template: str, tokens: dict[str, str]) -> str:
    rendered = str(template or "")
    for key, value in tokens.items():
        rendered = rendered.replace(f"[{key}]", value)
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _safe_message_content(message: discord.Message) -> str:
    text = str(message.content or "").strip()
    if text:
        return text[:1800]

    attachments = [str(getattr(item, "url", "") or "").strip() for item in list(getattr(message, "attachments", []) or [])]
    attachments = [item for item in attachments if item]
    if attachments:
        return "\n".join(attachments[:3])[:1800]

    embeds = list(getattr(message, "embeds", []) or [])
    for embed in embeds:
        desc = str(getattr(embed, "description", "") or "").strip()
        if desc:
            return desc[:1800]

    return "(no text content)"


def _message_supports_embed(channel: Any, me: discord.Member | None) -> tuple[bool, bool]:
    if channel is None or me is None or not hasattr(channel, "permissions_for"):
        return True, True
    try:
        perms = channel.permissions_for(me)
    except Exception:
        return True, True

    can_view = bool(getattr(perms, "view_channel", True))
    if isinstance(channel, discord.Thread):
        can_send = bool(getattr(perms, "send_messages_in_threads", getattr(perms, "send_messages", False)))
    else:
        can_send = bool(getattr(perms, "send_messages", False))
    can_embed = bool(getattr(perms, "embed_links", True))
    return can_view and can_send, can_embed


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._settings_cache: dict[int, dict[str, Any]] = {}
        self._index_cache: dict[int, dict[str, Any]] = {}
        self._message_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._event_debounce: dict[tuple[int, int], float] = {}

    def _settings_key(self, guild_id: int) -> str:
        return f"{STARBOARD_CONFIG_KEY_PREFIX}{int(guild_id)}"

    def _index_key(self, guild_id: int) -> str:
        return f"{STARBOARD_INDEX_KEY_PREFIX}{int(guild_id)}"

    async def _set_dashboard_config(self, config_key: str, config_value: str) -> None:
        writer = getattr(dashboard_config_db, "set_config_value", None)
        if callable(writer):
            await writer(config_key=config_key, config_value=config_value)
            return
        row = await dashboard_config_db.get(config_key=config_key)
        if row and row.get("id"):
            await dashboard_config_db.update(id=int(row["id"]), config_value=config_value)
            return
        await dashboard_config_db.insert(config_key=config_key, config_value=config_value)

    async def _get_settings(self, guild_id: int, *, force: bool = False) -> dict[str, Any]:
        now = time.time()
        cached = self._settings_cache.get(int(guild_id))
        if not force and cached and (now - float(cached.get("ts", 0.0))) <= 8:
            payload = cached.get("data")
            if isinstance(payload, dict):
                return payload

        payload: dict[str, Any] = {}
        try:
            row = await dashboard_config_db.get(config_key=self._settings_key(guild_id))
            raw = str((row or {}).get("config_value") or "").strip()
            if raw:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    payload = decoded
        except Exception as error:
            logger.error(f"Starboard settings load failed ({guild_id}): {error}")
            payload = {}

        normalized = _normalize_starboard_settings(payload)
        self._settings_cache[int(guild_id)] = {"ts": now, "data": normalized}
        return normalized

    async def _get_index(self, guild_id: int, *, force: bool = False) -> dict[str, dict[str, int]]:
        now = time.time()
        cached = self._index_cache.get(int(guild_id))
        if not force and cached and (now - float(cached.get("ts", 0.0))) <= 10:
            data = cached.get("data")
            if isinstance(data, dict):
                return data

        items: dict[str, dict[str, int]] = {}
        try:
            row = await dashboard_config_db.get(config_key=self._index_key(guild_id))
            raw = str((row or {}).get("config_value") or "").strip()
            if raw:
                decoded = json.loads(raw)
                payload = decoded.get("items") if isinstance(decoded, dict) else None
                if isinstance(payload, dict):
                    for message_id, entry in payload.items():
                        if not str(message_id).isdigit() or not isinstance(entry, dict):
                            continue
                        source_channel_id = _safe_int(entry.get("source_channel_id"), 0)
                        starboard_channel_id = _safe_int(entry.get("starboard_channel_id"), 0)
                        starboard_message_id = _safe_int(entry.get("starboard_message_id"), 0)
                        updated_at = _safe_int(entry.get("updated_at"), int(time.time()))
                        if source_channel_id <= 0 or starboard_channel_id <= 0 or starboard_message_id <= 0:
                            continue
                        items[str(message_id)] = {
                            "source_channel_id": source_channel_id,
                            "starboard_channel_id": starboard_channel_id,
                            "starboard_message_id": starboard_message_id,
                            "updated_at": updated_at,
                        }
        except Exception as error:
            logger.error(f"Starboard index load failed ({guild_id}): {error}")
            items = {}

        self._index_cache[int(guild_id)] = {"ts": now, "data": items}
        return items

    async def _save_index(self, guild_id: int, index: dict[str, dict[str, int]]) -> None:
        rows = [(message_id, entry) for message_id, entry in list(index.items()) if isinstance(entry, dict)]
        if len(rows) > MAX_INDEX_ITEMS:
            rows.sort(key=lambda item: _safe_int((item[1] or {}).get("updated_at"), 0), reverse=True)
            rows = rows[:MAX_INDEX_ITEMS]
        payload = {
            "items": {
                str(message_id): {
                    "source_channel_id": _safe_int(entry.get("source_channel_id"), 0),
                    "starboard_channel_id": _safe_int(entry.get("starboard_channel_id"), 0),
                    "starboard_message_id": _safe_int(entry.get("starboard_message_id"), 0),
                    "updated_at": _safe_int(entry.get("updated_at"), int(time.time())),
                }
                for message_id, entry in rows
                if _safe_int(entry.get("source_channel_id"), 0) > 0
                and _safe_int(entry.get("starboard_channel_id"), 0) > 0
                and _safe_int(entry.get("starboard_message_id"), 0) > 0
            }
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        await self._set_dashboard_config(self._index_key(guild_id), encoded)
        self._index_cache[int(guild_id)] = {"ts": time.time(), "data": payload["items"]}

    @staticmethod
    def _emoji_key_from_setting(raw_value: Any) -> tuple[str, str | int]:
        text = str(raw_value or "").strip()
        if not text:
            return "unicode", "⭐"

        matched = CUSTOM_EMOJI_PATTERN.match(text)
        if matched:
            return "custom", int(matched.group(1))

        if text.isdigit():
            return "custom", int(text)

        try:
            partial = discord.PartialEmoji.from_str(text)
            if partial and partial.id:
                return "custom", int(partial.id)
            if partial and partial.name:
                return "unicode", str(partial.name)
        except Exception:
            pass

        return "unicode", text

    @staticmethod
    def _emoji_key_from_reaction(raw_emoji: Any) -> tuple[str, str | int]:
        emoji_id = _safe_int(getattr(raw_emoji, "id", 0), 0)
        if emoji_id > 0:
            return "custom", emoji_id
        name = str(getattr(raw_emoji, "name", "") or str(raw_emoji or "")).strip()
        return "unicode", name

    @staticmethod
    def _emoji_for_reaction(raw_value: Any) -> str | discord.PartialEmoji | None:
        text = str(raw_value or "").strip()
        if not text:
            return None
        try:
            partial = discord.PartialEmoji.from_str(text)
            if partial and (partial.id or partial.name):
                return partial
        except Exception:
            pass
        if len(text) <= 64:
            return text
        return None

    def _is_target_emoji(self, payload_emoji: Any, configured_emoji: Any) -> bool:
        return self._emoji_key_from_reaction(payload_emoji) == self._emoji_key_from_setting(configured_emoji)

    async def _resolve_channel(self, guild: discord.Guild, channel_id: int) -> Any | None:
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            channel = guild.get_thread(int(channel_id))
        if channel is None:
            channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(channel_id))
            except Exception:
                return None
        channel_guild_id = _safe_int(getattr(getattr(channel, "guild", None), "id", 0), 0)
        if channel_guild_id and channel_guild_id != guild.id:
            return None
        return channel

    async def _resolve_message(self, channel: Any, message_id: int) -> discord.Message | None:
        fetch_message = getattr(channel, "fetch_message", None)
        if not callable(fetch_message):
            return None
        try:
            return await fetch_message(int(message_id))
        except Exception:
            return None

    async def _count_eligible_reactions(self, message: discord.Message, settings: dict[str, Any]) -> int:
        target_key = self._emoji_key_from_setting(settings.get("custom_emoji"))
        reaction_obj = None
        for reaction in list(getattr(message, "reactions", []) or []):
            if self._emoji_key_from_reaction(getattr(reaction, "emoji", None)) == target_key:
                reaction_obj = reaction
                break

        if reaction_obj is None:
            return 0

        ignore_self = bool(settings.get("ignore_self_stars"))
        required_role_id = _safe_int(settings.get("required_role_id"), 0)
        unique_user_ids: set[int] = set()

        async for user in reaction_obj.users(limit=None):
            user_id = _safe_int(getattr(user, "id", 0), 0)
            if user_id <= 0 or user_id in unique_user_ids:
                continue
            if bool(getattr(user, "bot", False)):
                continue
            if ignore_self and user_id == _safe_int(getattr(getattr(message, "author", None), "id", 0), 0):
                continue

            if required_role_id > 0:
                member = message.guild.get_member(user_id)
                if member is None:
                    try:
                        member = await message.guild.fetch_member(user_id)
                    except Exception:
                        member = None
                if member is None:
                    continue
                role_ids = {int(getattr(role, "id", 0) or 0) for role in list(getattr(member, "roles", []) or [])}
                if required_role_id not in role_ids:
                    continue

            unique_user_ids.add(user_id)

        return len(unique_user_ids)

    def _build_tokens(self, message: discord.Message, stars_count: int, emoji_text: str) -> dict[str, str]:
        author_display = str(getattr(message.author, "display_name", "Unknown User") or "Unknown User")
        author_mention = str(getattr(message.author, "mention", author_display) or author_display)
        channel_mention = str(getattr(message.channel, "mention", f"#{getattr(message.channel, 'id', '?')}") or "#channel")
        content_value = _safe_message_content(message)
        return {
            "author": author_mention,
            "author_name": author_display,
            "stars": str(stars_count),
            "channel": channel_mention,
            "channel_name": str(getattr(message.channel, "name", "channel") or "channel"),
            "link": str(getattr(message, "jump_url", "") or ""),
            "content": content_value,
            "emoji": emoji_text,
            "message_id": str(getattr(message, "id", "") or ""),
        }

    def _build_starboard_embed(
        self,
        *,
        message: discord.Message,
        settings: dict[str, Any],
        stars_count: int,
        tokens: dict[str, str],
    ) -> discord.Embed:
        title = _render_tokens(str(settings.get("embed_title") or "Starboard Highlight"), tokens)[:256]
        description = _render_tokens(str(settings.get("embed_description") or "[content]"), tokens)[:4000]
        color_hex = _normalize_color_hex(settings.get("color"), "#6B8CFF")
        color_value = _safe_int(color_hex.replace("#", ""), 0x6B8CFF)

        embed = discord.Embed(
            title=title or "Starboard Highlight",
            description=description or "(no description)",
            color=color_value,
            timestamp=getattr(message, "created_at", None),
            url=str(getattr(message, "jump_url", "") or None),
        )

        author_name_raw = str(settings.get("embed_author_name") or "").strip()
        author_name = _render_tokens(author_name_raw, tokens).strip()[:256]
        author_url = _render_tokens(str(settings.get("embed_author_url") or "").strip(), tokens).strip()[:600]
        author_icon_url = _render_tokens(str(settings.get("embed_author_icon_url") or "").strip(), tokens).strip()[:600]
        if author_name:
            embed.set_author(name=author_name, url=author_url or None, icon_url=author_icon_url or None)
        else:
            avatar_url = str(getattr(getattr(message.author, "display_avatar", None), "url", "") or "").strip()
            embed.set_author(name=str(getattr(message.author, "display_name", "Unknown"))[:256], icon_url=avatar_url or None)

        thumb_url = _render_tokens(str(settings.get("embed_thumbnail_url") or "").strip(), tokens).strip()[:600]
        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        image_url = _render_tokens(str(settings.get("embed_image_url") or "").strip(), tokens).strip()[:600]
        if not image_url:
            for attachment in list(getattr(message, "attachments", []) or []):
                content_type = str(getattr(attachment, "content_type", "") or "").lower()
                if content_type.startswith("image/"):
                    image_url = str(getattr(attachment, "url", "") or "").strip()[:600]
                    break
        if image_url:
            embed.set_image(url=image_url)

        footer_text = _render_tokens(str(settings.get("embed_footer_text") or "").strip(), tokens).strip()[:2048]
        footer_icon_url = _render_tokens(str(settings.get("embed_footer_icon_url") or "").strip(), tokens).strip()[:600]
        if footer_text:
            embed.set_footer(text=footer_text, icon_url=footer_icon_url or None)
        else:
            embed.set_footer(text=f"{tokens.get('emoji', '⭐')} {stars_count}")

        raw_fields = settings.get("fields") if isinstance(settings.get("fields"), list) else []
        for field in raw_fields[:25]:
            if not isinstance(field, dict):
                continue
            name = _render_tokens(str(field.get("name") or "").strip(), tokens)[:256]
            value = _render_tokens(str(field.get("value") or "").strip(), tokens)[:1024]
            if not name and not value:
                continue
            embed.add_field(name=name or "หัวข้อ", value=value or "-", inline=_as_bool(field.get("inline"), False))

        embed.add_field(name="ต้นฉบับ", value=f"[Open message]({tokens.get('link', '')})", inline=False)
        return embed

    def _build_message_payload(
        self,
        *,
        message: discord.Message,
        settings: dict[str, Any],
        stars_count: int,
    ) -> dict[str, Any]:
        emoji_text = str(settings.get("custom_emoji") or "⭐").strip() or "⭐"
        tokens = self._build_tokens(message, stars_count, emoji_text)

        message_template = str(settings.get("message_template") or "").strip()
        rendered_content = _render_tokens(message_template, tokens).strip()
        if not rendered_content:
            rendered_content = f"{emoji_text} **{stars_count}** • {tokens.get('channel', '#channel')} • {tokens.get('link', '')}"
        content = rendered_content[:2000]

        mode = str(settings.get("message_mode") or "embed").strip().lower()
        if mode == "text":
            return {"content": content, "embed": None}

        embed = self._build_starboard_embed(
            message=message,
            settings=settings,
            stars_count=stars_count,
            tokens=tokens,
        )
        return {"content": content, "embed": embed}

    async def _fetch_post_from_index(
        self,
        *,
        guild: discord.Guild,
        source_message_id: int,
        index: dict[str, dict[str, int]],
    ) -> discord.Message | None:
        row = index.get(str(source_message_id))
        if not isinstance(row, dict):
            return None

        channel_id = _safe_int(row.get("starboard_channel_id"), 0)
        message_id = _safe_int(row.get("starboard_message_id"), 0)
        if channel_id <= 0 or message_id <= 0:
            return None

        channel = await self._resolve_channel(guild, channel_id)
        if channel is None:
            return None

        return await self._resolve_message(channel, message_id)

    def _lock_for_message(self, guild_id: int, message_id: int) -> asyncio.Lock:
        key = (int(guild_id), int(message_id))
        lock = self._message_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._message_locks[key] = lock
        if len(self._message_locks) > 6000:
            for stale_key, stale_lock in list(self._message_locks.items()):
                if stale_lock.locked():
                    continue
                self._message_locks.pop(stale_key, None)
                if len(self._message_locks) <= 4500:
                    break
        return lock

    async def _delete_starboard_post(
        self,
        *,
        guild: discord.Guild,
        source_message_id: int,
        index: dict[str, dict[str, int]],
    ) -> None:
        post_message = await self._fetch_post_from_index(guild=guild, source_message_id=source_message_id, index=index)
        if post_message is not None:
            try:
                await post_message.delete()
            except Exception:
                pass
        if str(source_message_id) in index:
            index.pop(str(source_message_id), None)
            await self._save_index(guild.id, index)

    async def _upsert_starboard_post(
        self,
        *,
        guild: discord.Guild,
        source_message: discord.Message,
        settings: dict[str, Any],
        stars_count: int,
        index: dict[str, dict[str, int]],
    ) -> None:
        target_channel_id = _safe_int(settings.get("channel_id"), 0)
        if target_channel_id <= 0:
            return

        target_channel = await self._resolve_channel(guild, target_channel_id)
        if target_channel is None or not callable(getattr(target_channel, "send", None)):
            return
        if isinstance(target_channel, discord.ForumChannel):
            return

        can_send, can_embed = _message_supports_embed(target_channel, getattr(guild, "me", None))
        if not can_send:
            return

        payload = self._build_message_payload(
            message=source_message,
            settings=settings,
            stars_count=stars_count,
        )

        content = str(payload.get("content") or "").strip()[:2000] or None
        embed = payload.get("embed")
        if embed is not None and not can_embed:
            embed = None

        existing = await self._fetch_post_from_index(
            guild=guild,
            source_message_id=source_message.id,
            index=index,
        )

        # If target channel changed in settings, recreate post in the new channel.
        if existing is not None:
            existing_channel_id = _safe_int(getattr(getattr(existing, "channel", None), "id", 0), 0)
            if existing_channel_id > 0 and existing_channel_id != target_channel_id:
                try:
                    await existing.delete()
                except Exception:
                    pass
                existing = None

        created_message: discord.Message | None = None
        if existing is not None:
            try:
                await existing.edit(content=content, embed=embed)
                created_message = existing
            except Exception:
                try:
                    await existing.delete()
                except Exception:
                    pass
                existing = None

        if existing is None:
            try:
                created_message = await target_channel.send(content=content, embed=embed)
            except Exception as error:
                logger.error(f"Starboard send failed in guild {guild.id}: {error}")
                return

        if created_message is None:
            return

        index[str(source_message.id)] = {
            "source_channel_id": _safe_int(getattr(getattr(source_message, "channel", None), "id", 0), 0),
            "starboard_channel_id": _safe_int(getattr(getattr(created_message, "channel", None), "id", 0), 0),
            "starboard_message_id": _safe_int(getattr(created_message, "id", 0), 0),
            "updated_at": int(time.time()),
        }
        await self._save_index(guild.id, index)

        if _as_bool(settings.get("react_to_starboard_post"), False):
            reaction_emoji = self._emoji_for_reaction(settings.get("custom_emoji"))
            if reaction_emoji is not None:
                try:
                    await created_message.add_reaction(reaction_emoji)
                except Exception:
                    pass

    async def _process_reaction_event(self, payload: discord.RawReactionActionEvent) -> None:
        guild_id = _safe_int(getattr(payload, "guild_id", 0), 0)
        channel_id = _safe_int(getattr(payload, "channel_id", 0), 0)
        message_id = _safe_int(getattr(payload, "message_id", 0), 0)
        if guild_id <= 0 or channel_id <= 0 or message_id <= 0:
            return

        if self.bot.user and _safe_int(getattr(payload, "user_id", 0), 0) == _safe_int(self.bot.user.id, 0):
            return

        settings = await self._get_settings(guild_id)
        if not settings.get("enabled") or not settings.get("active"):
            return

        if not self._is_target_emoji(getattr(payload, "emoji", None), settings.get("custom_emoji")):
            return

        target_channel_id = _safe_int(settings.get("channel_id"), 0)
        if target_channel_id <= 0:
            return

        if channel_id == target_channel_id:
            return

        event_key = (guild_id, message_id)
        now = time.monotonic()
        last_ts = float(self._event_debounce.get(event_key, 0.0) or 0.0)
        if now - last_ts < 0.35:
            return
        self._event_debounce[event_key] = now
        if len(self._event_debounce) > 5000:
            cutoff = now - 120.0
            self._event_debounce = {key: ts for key, ts in self._event_debounce.items() if float(ts) >= cutoff}

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        lock = self._lock_for_message(guild_id, message_id)
        async with lock:
            source_channel = await self._resolve_channel(guild, channel_id)
            if source_channel is None:
                return
            source_message = await self._resolve_message(source_channel, message_id)
            if source_message is None:
                return

            if bool(getattr(getattr(source_message, "author", None), "bot", False)):
                return

            enabled_source_channel_id = _safe_int(settings.get("enabled_channel_id"), 0)
            if enabled_source_channel_id > 0 and _safe_int(getattr(getattr(source_message, "channel", None), "id", 0), 0) != enabled_source_channel_id:
                return

            stars_count = await self._count_eligible_reactions(source_message, settings)
            threshold = _safe_int(settings.get("stars_limit"), 3, minimum=1, maximum=20)
            index = await self._get_index(guild_id)

            if stars_count < threshold:
                await self._delete_starboard_post(
                    guild=guild,
                    source_message_id=source_message.id,
                    index=index,
                )
                return

            await self._upsert_starboard_post(
                guild=guild,
                source_message=source_message,
                settings=settings,
                stars_count=stars_count,
                index=index,
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            await self._process_reaction_event(payload)
        except Exception as error:
            logger.error(f"Starboard reaction add failed: {error}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        try:
            await self._process_reaction_event(payload)
        except Exception as error:
            logger.error(f"Starboard reaction remove failed: {error}")


async def setup(bot):
    await bot.add_cog(Starboard(bot))
